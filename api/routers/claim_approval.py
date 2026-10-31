"""
NSS ERP — Registration Claim Approval router.

Sakha Admin endpoints for reviewing pending registration claims:
  GET   /api/v1/admin/claims            — List pending claims (scoped)
  GET   /api/v1/admin/claims/{claim_pk} — Claim detail
  PATCH /api/v1/admin/claims/{claim_pk} — Edit claim/person before approval
  POST  /api/v1/admin/claims/{claim_pk}/approve — Approve a claim
  POST  /api/v1/admin/claims/{claim_pk}/reject  — Reject a claim

Flow (approve):
  1. Validate claim is PENDING
  2. Verify admin has scope for the claimed organization
  3. Require claimed_local_sakha_number for non-Darshaka (AUTH-BR-086); a
     Darshaka claim without one is auto-numbered in the Darshak namespace
     (MBR-030C / MBR-048)
  4. For Darshaka: generate sangha_sevi_id + create sangha_sevi record
  5. For non-Darshaka: verify claimed_local_sakha_number matches an existing
     sangha_sevi record, or create one with that number
  6. Create membership_sakha_affiliation
  6b. Issue the mandatory Anumati/Parichaya Patra credential (only for a
      newly-created sangha_sevi — see api/helpers.py::issue_membership_credential())
  7. If darshak_organization_pk set, create darshak affiliation (its own
     Local Sakha Number, required — see darshak_local_sakha_number)
  8. Set user_account.account_status = 'ACTIVE'
  9. Set registration_claim.claim_status = 'APPROVED'

Authority: SOL-AUTH-006 (AUTH-BR-090, AUTH-BR-092, AUTH-BR-094)
"""

import logging
from datetime import date, datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.rbac import require_any_permission
from api.helpers import (
    next_id, get_active_status_pk, compose_local_sakha_erp_id, log_audit,
    build_order_by, natural_sort_key, require_sakha_organization,
    issue_membership_credential, next_sakha_local_number,
    validate_mobile, validate_email,
    fetch_person_date_of_birth,
)
from api.services.rbac_service import (
    UserContext,
    actor_scope_org_pks,
    org_in_scope,
)

router = APIRouter(prefix="/api/v1/admin/claims", tags=["claim-approval"])


# ── Schemas ─────────────────────────────────────────────────────────────

class ClaimListItem(BaseModel):
    registration_claim_pk: str
    person_pk: str
    person_id: str
    person_name: str
    claimed_organization_pk: str
    organization_name: str | None = None
    claimed_membership_type: str | None = None
    claimed_local_sakha_number: str | None = None
    claimed_joining_date: str | None = None
    claim_status: str
    created_at: datetime


class ClaimListResponse(BaseModel):
    claims: list[ClaimListItem]
    total: int
    page: int
    page_size: int


class ClaimDetailResponse(ClaimListItem):
    user_account_pk: str
    claimed_credential_document_number: str | None = None
    darshak_organization_pk: str | None = None
    darshak_organization_name: str | None = None
    darshak_local_sakha_number: str | None = None
    country_phone_code: str | None = None
    mobile_number: str | None = None
    email: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    admin_remarks: str | None = None
    claimed_membership_type_master_data_pk: str | None = None


class ApproveRequest(BaseModel):
    admin_remarks: str | None = Field(None, max_length=500)


class RejectRequest(BaseModel):
    admin_remarks: str = Field(..., min_length=1, max_length=500,
                               description="Reason for rejection (required)")


class UpdateClaimRequest(BaseModel):
    """Admin edits to a pending registration claim before approval."""
    claimed_organization_pk: UUID | None = None
    claimed_membership_type_master_data_pk: UUID | None = None
    claimed_local_sakha_number: str | None = Field(None, max_length=20)
    claimed_credential_document_number: str | None = Field(None, max_length=30)
    claimed_joining_date: str | None = None
    darshak_organization_pk: UUID | None = None
    darshak_local_sakha_number: str | None = Field(None, max_length=20)
    first_name: str | None = Field(None, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    country_phone_code: str | None = Field(None, max_length=5)
    mobile_number: str | None = Field(None, max_length=15)
    email: str | None = Field(None, max_length=200)



# ── GET /api/v1/admin/claims ────────────────────────────────────────────

# Sortable columns for the Registration Approvals table. See
# helpers.build_order_by — nothing outside this map can reach the SQL.
_CLAIM_SORT_COLUMNS: dict[str, str | list[str]] = {
    "person_id": natural_sort_key("p.person_id"),
    "person_name": "CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)",
    "organization_name": "org.organization_name",
    "claimed_membership_type": "mt.value_name",
    "claimed_local_sakha_number": natural_sort_key("rc.claimed_local_sakha_number"),
    "created_at": "rc.created_at",
}


@router.get("", response_model=ClaimListResponse)
def list_claims(
    claim_status: str = Query("PENDING", pattern="^(PENDING|APPROVED|REJECTED)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_dir: str | None = Query(None, description="Sort direction: asc or desc"),
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_connection),
) -> ClaimListResponse:
    """
    List registration claims, filtered by status.
    Scoped: Sakha admins see only claims for their organization(s).
    NSS-WIDE admins see all claims.

    Sorted in SQL, not in the browser — the list is paginated, so sorting
    the fetched page would reorder only the rows already on screen.

    The default stays oldest-first: this is an approval queue, and the
    longest-waiting claim should surface first.
    """
    offset = (page - 1) * page_size
    order_by = build_order_by(
        sort_by, sort_dir, _CLAIM_SORT_COLUMNS, "rc.created_at ASC"
    )

    # Build scope filter (ADMIN-BR-076, subtree-aware): a Kendra/Anchalika
    # admin sees claims for any descendant Sakha, not just an org whose PK is
    # literally in their scope. Global authority sees all claims.
    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        scope_filter = ""
        scope_params: list = []
    else:
        if not allowed:
            return ClaimListResponse(claims=[], total=0, page=page, page_size=page_size)
        placeholders = ",".join(["%s"] * len(allowed))
        scope_filter = f"AND rc.claimed_organization_pk IN ({placeholders})"
        scope_params = list(allowed)

    with conn.cursor() as cur:
        # Count
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM nss.registration_claim rc
            WHERE rc.claim_status = %s
              AND rc.is_active = TRUE
              {scope_filter}
            """,
            [claim_status] + scope_params,
        )
        total = cur.fetchone()[0]

        # Fetch
        cur.execute(
            f"""
            SELECT rc.registration_claim_pk,
                   p.person_pk,
                   p.person_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS person_name,
                   rc.claimed_organization_pk,
                   org.organization_name,
                   mt.value_name AS membership_type,
                   rc.claimed_local_sakha_number,
                   rc.claimed_joining_date,
                   rc.claim_status,
                   rc.created_at
            FROM nss.registration_claim rc
            JOIN nss.person p ON p.person_pk = rc.person_pk
            JOIN nss.organization org ON org.organization_pk = rc.claimed_organization_pk
            LEFT JOIN nss.master_data mt ON mt.master_data_pk = rc.claimed_membership_type_master_data_pk
            WHERE rc.claim_status = %s
              AND rc.is_active = TRUE
              {scope_filter}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
            """,
            [claim_status] + scope_params + [page_size, offset],
        )
        rows = cur.fetchall()

    claims = [
        ClaimListItem(
            registration_claim_pk=str(r[0]),
            person_pk=str(r[1]),
            person_id=r[2],
            person_name=r[3] or "",
            claimed_organization_pk=str(r[4]),
            organization_name=r[5],
            claimed_membership_type=r[6],
            claimed_local_sakha_number=r[7],
            claimed_joining_date=str(r[8]) if r[8] else None,
            claim_status=r[9],
            created_at=r[10],
        )
        for r in rows
    ]

    return ClaimListResponse(claims=claims, total=total, page=page, page_size=page_size)


# ── GET /api/v1/admin/claims/{claim_pk} ─────────────────────────────────

@router.get("/{registration_claim_pk}", response_model=ClaimDetailResponse)
def get_claim(
    registration_claim_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_connection),
) -> ClaimDetailResponse:
    """Get full detail for a registration claim."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rc.registration_claim_pk,
                   p.person_pk,
                   p.person_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name),
                   rc.claimed_organization_pk,
                   org.organization_name,
                   mt.value_name,
                   rc.claimed_local_sakha_number,
                   rc.claimed_credential_document_number,
                   rc.claimed_joining_date,
                   rc.claim_status,
                   rc.created_at,
                   rc.user_account_pk,
                   rc.darshak_organization_pk,
                   dorg.organization_name,
                   rc.darshak_local_sakha_number,
                   p.country_phone_code,
                   p.mobile_number,
                   p.email,
                   CONCAT_WS(' ', rp.first_name, rp.last_name),
                   rc.reviewed_at,
                   rc.admin_remarks,
                   rc.claimed_membership_type_master_data_pk
            FROM nss.registration_claim rc
            JOIN nss.person p ON p.person_pk = rc.person_pk
            JOIN nss.organization org ON org.organization_pk = rc.claimed_organization_pk
            LEFT JOIN nss.master_data mt ON mt.master_data_pk = rc.claimed_membership_type_master_data_pk
            LEFT JOIN nss.organization dorg ON dorg.organization_pk = rc.darshak_organization_pk
            LEFT JOIN nss.user_account rua ON rua.user_account_pk = rc.reviewed_by_user_account_pk
            LEFT JOIN nss.person rp ON rp.person_pk = rua.person_pk
            WHERE rc.registration_claim_pk = %s
              AND rc.is_active = TRUE
            """,
            (str(registration_claim_pk),),
        )
        r = cur.fetchone()

    if r is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    # Scope check (ADMIN-BR-076, subtree-aware): admin can see claims for any
    # org inside their scope subtree; global authority sees all.
    with conn.cursor() as cur:
        if not org_in_scope(cur, user, r[4]):
            raise HTTPException(status_code=403, detail="Not authorized for this organization.")

    return ClaimDetailResponse(
        registration_claim_pk=str(r[0]),
        person_pk=str(r[1]),
        person_id=r[2],
        person_name=r[3] or "",
        claimed_organization_pk=str(r[4]),
        organization_name=r[5],
        claimed_membership_type=r[6],
        claimed_local_sakha_number=r[7],
        claimed_credential_document_number=r[8],
        claimed_joining_date=str(r[9]) if r[9] else None,
        claim_status=r[10],
        created_at=r[11],
        user_account_pk=str(r[12]),
        darshak_organization_pk=str(r[13]) if r[13] else None,
        darshak_organization_name=r[14],
        darshak_local_sakha_number=r[15],
        country_phone_code=r[16],
        mobile_number=r[17],
        email=r[18],
        reviewed_by=r[19],
        reviewed_at=r[20],
        admin_remarks=r[21],
        claimed_membership_type_master_data_pk=str(r[22]) if r[22] else None,
    )


# ── PATCH /api/v1/admin/claims/{claim_pk} ────────────────────────────

@router.patch("/{registration_claim_pk}")
def update_claim(
    registration_claim_pk: UUID,
    body: UpdateClaimRequest,
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_write_connection),
):
    """
    Admin edits to a pending registration claim before approval.

    Updates both the claim record and the person record as needed.
    Only PENDING claims can be edited.
    """
    with conn.cursor() as cur:
        # Fetch current claim
        cur.execute(
            """
            SELECT rc.claim_status, rc.person_pk, rc.claimed_organization_pk
            FROM nss.registration_claim rc
            WHERE rc.registration_claim_pk = %s AND rc.is_active = TRUE
            """,
            (str(registration_claim_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Claim not found.")

        claim_status, person_pk, current_org_pk = row

        if claim_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Cannot edit a {claim_status} claim.",
            )

        # Scope check (ADMIN-BR-076, subtree-aware): a Kendra/Anchalika admin
        # editing a claim for a descendant Sakha is in scope. Previously this
        # used direct-pk matching, which 403'd any org above the exact scoped
        # org — the "edited a user's personal info → 403" bug.
        if not org_in_scope(cur, user, current_org_pk):
            raise HTTPException(status_code=403, detail="Not authorized for this organization.")

        # ── Update claim fields ──────────────────────────────────────
        claim_sets = []
        claim_params = []

        if body.claimed_organization_pk is not None:
            # ADMIN-BR-076: re-pointing the claim must not hand it to an org
            # outside the editing admin's scope, and MBR-038A: the claimed org
            # must be a Sakha — checked now, not only when approve runs.
            if not org_in_scope(cur, user, body.claimed_organization_pk):
                raise HTTPException(status_code=403, detail="Not authorized for the new organization.")
            require_sakha_organization(cur, str(body.claimed_organization_pk))
            claim_sets.append("claimed_organization_pk = %s")
            claim_params.append(str(body.claimed_organization_pk))
        if body.claimed_membership_type_master_data_pk is not None:
            claim_sets.append("claimed_membership_type_master_data_pk = %s")
            claim_params.append(str(body.claimed_membership_type_master_data_pk))
        if body.claimed_local_sakha_number is not None:
            claim_sets.append("claimed_local_sakha_number = %s")
            claim_params.append(body.claimed_local_sakha_number.strip() or None)
        if body.claimed_credential_document_number is not None:
            claim_sets.append("claimed_credential_document_number = %s")
            claim_params.append(body.claimed_credential_document_number.strip() or None)
        if body.claimed_joining_date is not None:
            claim_sets.append("claimed_joining_date = %s")
            claim_params.append(body.claimed_joining_date or None)
        if body.darshak_organization_pk is not None:
            claim_sets.append("darshak_organization_pk = %s")
            claim_params.append(str(body.darshak_organization_pk))
        if body.darshak_local_sakha_number is not None:
            claim_sets.append("darshak_local_sakha_number = %s")
            claim_params.append(body.darshak_local_sakha_number.strip() or None)

        actor_pk = user.actor_pk

        if claim_sets:
            claim_sets.append("updated_at = NOW()")
            cur.execute(
                f"""
                UPDATE nss.registration_claim
                SET {', '.join(claim_sets)}
                WHERE registration_claim_pk = %s
                """,
                claim_params + [str(registration_claim_pk)],
            )
            log_audit(cur, action="UPDATE", table_name="registration_claim",
                      record_pk=str(registration_claim_pk), actor_pk=actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="claim_approval",
                      summary="Updated claim details before approval")

        # ── Update person fields ─────────────────────────────────────
        person_sets = []
        person_params = []

        # MBR-CONTACT-01/02: validate the EFFECTIVE contact values. This is a
        # partial edit, so merge incoming changes over the current person row
        # before validating country-wise mobile + email format.
        if (body.email is not None
                or body.mobile_number is not None
                or body.country_phone_code is not None):
            cur.execute(
                "SELECT country_phone_code, mobile_number, email FROM nss.person WHERE person_pk = %s",
                (str(person_pk),),
            )
            cur_contact = cur.fetchone() or (None, None, None)
            eff_code = (body.country_phone_code.strip() or None) if body.country_phone_code is not None else cur_contact[0]
            eff_mobile = (body.mobile_number.strip() or None) if body.mobile_number is not None else cur_contact[1]
            eff_email = (body.email.strip().lower() if body.email.strip() else None) if body.email is not None else cur_contact[2]
            validate_mobile(eff_code, eff_mobile)
            validate_email(eff_email)

        if body.first_name is not None:
            person_sets.append("first_name = %s")
            person_params.append(body.first_name.strip().title())
        if body.middle_name is not None:
            person_sets.append("middle_name = %s")
            person_params.append(body.middle_name.strip().title() if body.middle_name.strip() else None)
        if body.last_name is not None:
            person_sets.append("last_name = %s")
            person_params.append(body.last_name.strip().title() if body.last_name.strip() else None)
        if body.country_phone_code is not None:
            person_sets.append("country_phone_code = %s")
            person_params.append(body.country_phone_code.strip() or None)
        if body.mobile_number is not None:
            person_sets.append("mobile_number = %s")
            person_params.append(body.mobile_number.strip() or None)
        if body.email is not None:
            person_sets.append("email = %s")
            person_params.append(body.email.strip().lower() if body.email.strip() else None)

        if person_sets:
            person_sets.append("updated_at = NOW()")
            cur.execute(
                f"""
                UPDATE nss.person
                SET {', '.join(person_sets)}
                WHERE person_pk = %s
                """,
                person_params + [str(person_pk)],
            )
            log_audit(cur, action="UPDATE", table_name="person",
                      record_pk=str(person_pk), actor_pk=actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="claim_approval",
                      summary="Updated person from claim edit")

    return {"message": "Claim updated successfully."}


# ── POST /api/v1/admin/claims/{claim_pk}/approve ───────────────────────

@router.post("/{registration_claim_pk}/approve")
def approve_claim(
    registration_claim_pk: UUID,
    body: ApproveRequest = ApproveRequest(),
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_write_connection),
):
    """
    Approve a pending registration claim.

    Creates sangha_sevi + affiliation, activates user_account.
    AUTH-BR-090, AUTH-BR-094.
    """
    with conn.cursor() as cur:
        # 1. Fetch claim
        cur.execute(
            """
            SELECT rc.registration_claim_pk,
                   rc.user_account_pk,
                   rc.person_pk,
                   rc.claimed_organization_pk,
                   rc.claimed_membership_type_master_data_pk,
                   rc.claimed_local_sakha_number,
                   rc.claimed_credential_document_number,
                   rc.claimed_joining_date,
                   rc.darshak_organization_pk,
                   rc.darshak_local_sakha_number,
                   rc.claim_status,
                   mt.value_code AS membership_type_code
            FROM nss.registration_claim rc
            LEFT JOIN nss.master_data mt ON mt.master_data_pk = rc.claimed_membership_type_master_data_pk
            WHERE rc.registration_claim_pk = %s
              AND rc.is_active = TRUE
            """,
            (str(registration_claim_pk),),
        )
        claim = cur.fetchone()

        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found.")

        (claim_pk, user_account_pk, person_pk, org_pk, membership_type_pk,
         local_sakha_number, credential_document_number, joining_date,
         darshak_org_pk, darshak_local_sakha_number, claim_status,
         membership_type_code) = claim

        if claim_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Claim is already {claim_status}.",
            )

        # 2. Scope check (ADMIN-BR-076, subtree-aware)
        if not org_in_scope(cur, user, org_pk):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have admin scope for this organization.",
            )

        # 3. Determine if Darshaka
        is_darshaka = membership_type_code == "PROBATIONARY"

        # AUTH-BR-086: the Local Sakha Number is REQUIRED for non-Darshaka
        # claims and OPTIONAL for Darshaka. A Darshaka claim without one gets
        # the next number in the Sakha's Darshak namespace minted here
        # (MBR-030C / MBR-048 auto-sequencing) — that is the "system-generated
        # at admin approval" the registration flow promises.
        if not local_sakha_number:
            if not is_darshaka:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Claim has no Local Sakha Number. Reject and ask for correction.",
                )
            local_sakha_number = next_sakha_local_number(cur, str(org_pk), is_darshak=True)

        # Cross-Sakha darshak attendance must carry its own Local Sakha
        # Number at the attending Sakha too — separate namespace from the
        # home Sakha's number above.
        if darshak_org_pk and not darshak_local_sakha_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Claim has a Darshak Sakha but no Local Sakha Number for it. Reject and ask for correction.",
            )

        # MBR-038A: a sangha_sevi's organization must be Sakha-like.
        # Mirrors the DB trigger (trg_enforce_sakha_only_sangha_sevi) with a
        # clean 422. Guards both sangha_sevi inserts below, which share org_pk.
        require_sakha_organization(cur, str(org_pk))

        # 4. Lookup ACTIVE status master_data_pk
        active_status_pk = get_active_status_pk(cur)

        # 5. Create or link sangha_sevi
        sangha_sevi_id = None
        sangha_sevi_pk = None
        sangha_sevi_newly_created = False
        actor_pk = user.actor_pk

        if is_darshaka:
            # New Darshaka: generate new sangha_sevi_id
            sangha_sevi_id = next_id(cur, "SANGHA_SEVI", actor_pk=actor_pk)
            cur.execute(
                """
                INSERT INTO nss.sangha_sevi (
                    sangha_sevi_id,
                    person_pk,
                    membership_type_master_data_pk,
                    membership_status_master_data_pk,
                    organization_pk,
                    joining_date
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING sangha_sevi_pk
                """,
                (
                    sangha_sevi_id,
                    str(person_pk),
                    str(membership_type_pk),
                    str(active_status_pk),
                    str(org_pk),
                    joining_date,
                ),
            )
            ss_pk = cur.fetchone()[0]
            log_audit(cur, action="CREATE", table_name="sangha_sevi",
                      record_pk=str(ss_pk), actor_pk=actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="claim_approval",
                      summary=f"Created sangha sevi {sangha_sevi_id} via claim approval")
            sangha_sevi_pk = ss_pk
            sangha_sevi_newly_created = True
        else:
            # Check if person already has an active sangha_sevi record
            cur.execute(
                """
                SELECT ss.sangha_sevi_pk, ss.sangha_sevi_id
                FROM nss.sangha_sevi ss
                WHERE ss.person_pk = %s
                  AND ss.is_active = TRUE
                """,
                (str(person_pk),),
            )
            existing = cur.fetchone()
            if existing:
                # Link to existing SS record
                sangha_sevi_pk = existing[0]
                sangha_sevi_id = existing[1]
            else:
                # No existing record — auto-generate SS ID (SS1, SS2, ...)
                sangha_sevi_id = next_id(cur, "SANGHA_SEVI", actor_pk=actor_pk)
                cur.execute(
                    """
                    INSERT INTO nss.sangha_sevi (
                        sangha_sevi_id,
                        person_pk,
                        membership_type_master_data_pk,
                        membership_status_master_data_pk,
                        organization_pk,
                        joining_date
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING sangha_sevi_pk
                    """,
                    (
                        sangha_sevi_id,
                        str(person_pk),
                        str(membership_type_pk),
                        str(active_status_pk),
                        str(org_pk),
                        joining_date,
                    ),
                )
                ss_pk = cur.fetchone()[0]
                log_audit(cur, action="CREATE", table_name="sangha_sevi",
                          record_pk=str(ss_pk), actor_pk=actor_pk,
                          actor_user_account_pk=str(user.user_account_pk),
                          module="claim_approval",
                          summary=f"Created sangha sevi {sangha_sevi_id} via claim approval")
                sangha_sevi_pk = ss_pk
                sangha_sevi_newly_created = True

        # 6. Create membership_sakha_affiliation
        # Tier 2 local ID, namespace-separated by membership state (MBR-030C):
        #   Regular/Associate  <short_code><number>          ESS123
        #   Darshak            <short_code><marker><number>  ESSD123
        # local_sakha_number is guaranteed non-empty (checked in step 3
        # above), and compose_local_sakha_erp_id raises a clean 422 itself
        # if the org has no short_code assigned yet — same failure mode as
        # the standalone Create Sangha Sevi flow, not a silent skip.
        affiliation_local_id = compose_local_sakha_erp_id(
            cur, org_pk, local_sakha_number, is_darshak=is_darshaka
        )
        cur.execute(
            """
            -- effective_from is NOT NULL (06_membership_sakha_affiliation.sql)
            -- and is a DIFFERENT fact from the member's Sangha joining date:
            -- it records when this Sakha affiliation began, which is known
            -- even when the joining date is not (MBR-047). So COALESCE to
            -- today is correct HERE, and deliberately not used on
            -- sangha_sevi.joining_date above.
            INSERT INTO nss.membership_sakha_affiliation (
                sangha_sevi_pk,
                organization_pk,
                local_sakha_erp_id,
                effective_from,
                affiliation_status,
                source_event_type
            ) VALUES (%s, %s, %s, COALESCE(%s, CURRENT_DATE), 'ACTIVE', 'ENROLLMENT')
            ON CONFLICT DO NOTHING
            RETURNING membership_sakha_affiliation_pk
            """,
            (
                str(sangha_sevi_pk),
                str(org_pk),
                affiliation_local_id,
                joining_date,
            ),
        )
        aff_row = cur.fetchone()
        if aff_row:
            aff_pk = aff_row[0]
            log_audit(cur, action="CREATE", table_name="membership_sakha_affiliation",
                      record_pk=str(aff_pk), actor_pk=actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="claim_approval",
                      summary="Created primary sakha affiliation")
        else:
            logger.warning(
                "Affiliation INSERT conflict for claim %s, SS %s, org %s, local_id %s",
                str(registration_claim_pk), str(sangha_sevi_pk),
                str(org_pk), affiliation_local_id,
            )

        # 6b. Mandatory credential (MBR-010/014/019A/B): every new Sangha
        # Sevi must be issued an Anumati Patra (Darshaka) or Parichaya
        # Patra (Regular/Associate) — same rule admin.py's create_sangha_sevi
        # enforces, via the same shared helper. Only for a newly-created SS
        # record: linking to an existing one (the person is already a
        # Sangha Sevi elsewhere) means they already hold a credential.
        if sangha_sevi_newly_created:
            # MBR-030H (2026-10-03): the registrant may have typed a bare
            # sequence number OR a full "<no>/<year>/<year>" number. Pass it
            # through untouched — issue_membership_credential() normalizes and
            # validates it against the Patra's own ISSUE DATE via
            # normalize_patra_document_number(). This previously composed the
            # year here from date.today()'s financial year, which stamped the
            # wrong year on any Patra whose issue date fell in a different
            # year than the approval date.
            credential_type, credential_pk, credential_doc_number = issue_membership_credential(
                cur,
                sangha_sevi_pk=str(sangha_sevi_pk),
                membership_type_pk=str(membership_type_pk),
                organization_pk=str(org_pk),
                document_number=credential_document_number,
                joining_date=joining_date,
                date_of_birth=fetch_person_date_of_birth(cur, person_pk),
            )
            log_audit(cur, action="CREATE", table_name=credential_type.lower(),
                      record_pk=credential_pk, actor_pk=actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="claim_approval",
                      summary=f"Issued {credential_type} {credential_doc_number} via claim approval")

        # 7. Darshak attendance affiliation (at a different Sakha)
        if darshak_org_pk:
            darshak_affiliation_local_id = compose_local_sakha_erp_id(
                cur, darshak_org_pk, darshak_local_sakha_number, is_darshak=True
            )
            cur.execute(
                """
                INSERT INTO nss.membership_sakha_affiliation (
                    sangha_sevi_pk,
                    organization_pk,
                    local_sakha_erp_id,
                    effective_from,
                    affiliation_status,
                    source_event_type
                ) VALUES (%s, %s, %s, COALESCE(%s, CURRENT_DATE), 'ACTIVE', 'ENROLLMENT')
                ON CONFLICT DO NOTHING
                RETURNING membership_sakha_affiliation_pk
                """,
                (str(sangha_sevi_pk), str(darshak_org_pk), darshak_affiliation_local_id, joining_date),
            )
            darshak_aff_row = cur.fetchone()
            if darshak_aff_row:
                darshak_aff_pk = darshak_aff_row[0]
                log_audit(cur, action="CREATE", table_name="membership_sakha_affiliation",
                          record_pk=str(darshak_aff_pk), actor_pk=actor_pk,
                          actor_user_account_pk=str(user.user_account_pk),
                          module="claim_approval",
                          summary="Created darshak attendance affiliation")

        # 8. Activate user_account
        cur.execute(
            """
            UPDATE nss.user_account
            SET account_status = 'ACTIVE',
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (str(user_account_pk),),
        )
        log_audit(cur, action="STATUS_CHANGE", table_name="user_account",
                  record_pk=str(user_account_pk), actor_pk=actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="claim_approval",
                  summary="Activated user account via claim approval")

        # 9. Update claim
        cur.execute(
            """
            UPDATE nss.registration_claim
            SET claim_status = 'APPROVED',
                reviewed_by_user_account_pk = %s,
                reviewed_at = NOW(),
                admin_remarks = %s,
                updated_at = NOW()
            WHERE registration_claim_pk = %s
            """,
            (str(user.user_account_pk), body.admin_remarks, str(claim_pk)),
        )
        # Fetch person_name for audit summary
        cur.execute(
            "SELECT CONCAT_WS(' ', first_name, middle_name, last_name) FROM nss.person WHERE person_pk = %s",
            (str(person_pk),),
        )
        person_name = (cur.fetchone() or ("",))[0] or "unknown"
        log_audit(cur, action="APPROVE", table_name="registration_claim",
                  record_pk=str(claim_pk), actor_pk=actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="claim_approval",
                  summary=f"Approved registration claim for {person_name}")

    return {
        "message": "Claim approved. Account activated.",
        "sangha_sevi_id": sangha_sevi_id,
        "person_pk": str(person_pk),
    }


# ── POST /api/v1/admin/claims/{claim_pk}/reject ────────────────────────

@router.post("/{registration_claim_pk}/reject")
def reject_claim(
    registration_claim_pk: UUID,
    body: RejectRequest,
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_write_connection),
):
    """
    Reject a pending registration claim.
    AUTH-BR-093: account stays PENDING_APPROVAL, person can resubmit.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rc.claimed_organization_pk, rc.claim_status
            FROM nss.registration_claim rc
            WHERE rc.registration_claim_pk = %s
              AND rc.is_active = TRUE
            """,
            (str(registration_claim_pk),),
        )
        row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Claim not found.")

        org_pk, claim_status = row

        if claim_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Claim is already {claim_status}.",
            )

        if not org_in_scope(cur, user, org_pk):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have admin scope for this organization.",
            )

        cur.execute(
            """
            UPDATE nss.registration_claim
            SET claim_status = 'REJECTED',
                reviewed_by_user_account_pk = %s,
                reviewed_at = NOW(),
                admin_remarks = %s,
                updated_at = NOW()
            WHERE registration_claim_pk = %s
            """,
            (str(user.user_account_pk), body.admin_remarks, str(registration_claim_pk)),
        )
        actor_pk = user.actor_pk
        log_audit(cur, action="REJECT", table_name="registration_claim",
                  record_pk=str(registration_claim_pk), actor_pk=actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="claim_approval",
                  summary="Rejected registration claim",
                  detail={"reason": body.admin_remarks})

    return {"message": "Claim rejected.", "admin_remarks": body.admin_remarks}
