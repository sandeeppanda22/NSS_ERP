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
  3. Local Sakha Number (AUTH-BR-086 as amended by GDR-009, 2026-11-01):
     a LEGACY claim (is_legacy_member) must carry its existing number; a
     non-legacy claim must carry none and is auto-numbered by the shared
     allocator (Regular/Associate series, or the Darshak series for a
     Darshaka — MBR-030C / MBR-048). Same rule for the attendance Sakha
     (darshak_is_legacy_member). One validator:
     helpers.validate_claim_local_numbers()
  4. Create (or link) the sangha_sevi record
  5. Create the home membership_sakha_affiliation
  6b. Issue the Anumati/Parichaya Patra (only for a newly-created sangha_sevi —
      api/helpers.py::issue_credential_at_enrolment(); legacy number recorded, else minted)
  7. If darshak_organization_pk set, open a Darshak-series affiliation there
     (legacy number supplied, else allocated) — skipped only if the member
     already holds an OPEN affiliation at that Sakha; any other collision is
     a 409 that rolls the whole approval back
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
    ensure_darshak_attendance_affiliation, validate_claim_local_numbers, log_audit,
    create_sangha_sevi_with_home_affiliation, insert_sakha_affiliation,
    build_order_by, natural_sort_key, require_sakha_organization,
    issue_credential_at_enrolment, resolve_legacy_patra_number, is_probationary_membership_type,
    require_non_darshaka_for_attendance,
    patra_card_type_for_membership_type,
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
    is_legacy_member: bool = False
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
    darshak_is_legacy_member: bool = False
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
    # Admin verification of the legacy rule (GDR-009): flag + number are
    # validated TOGETHER against the claim's current values, so to turn a
    # legacy claim into a new one send is_legacy_member=false AND
    # claimed_local_sakha_number="" AND claimed_credential_document_number=""
    # in the same request (the Patra number follows the same flag — GDR-009 §2A).
    is_legacy_member: bool | None = None
    claimed_local_sakha_number: str | None = Field(None, max_length=20)
    claimed_credential_document_number: str | None = Field(None, max_length=30)
    claimed_joining_date: str | None = None
    darshak_organization_pk: UUID | None = None
    darshak_is_legacy_member: bool | None = None
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
                   rc.created_at,
                   rc.is_legacy_member
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
            is_legacy_member=r[11],
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
                   rc.claimed_membership_type_master_data_pk,
                   rc.is_legacy_member,
                   rc.darshak_is_legacy_member
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
        is_legacy_member=r[23],
        darshak_is_legacy_member=r[24],
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
            SELECT rc.claim_status, rc.person_pk, rc.claimed_organization_pk,
                   rc.is_legacy_member, rc.claimed_local_sakha_number,
                   rc.darshak_organization_pk, rc.darshak_is_legacy_member,
                   rc.darshak_local_sakha_number,
                   rc.claimed_credential_document_number,
                   rc.claimed_membership_type_master_data_pk
            FROM nss.registration_claim rc
            WHERE rc.registration_claim_pk = %s AND rc.is_active = TRUE
            """,
            (str(registration_claim_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Claim not found.")

        (claim_status, person_pk, current_org_pk, cur_legacy, cur_number,
         cur_darshak_org, cur_darshak_legacy, cur_darshak_number,
         cur_patra_number, cur_membership_type_pk) = row

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
        eff_org_pk = body.claimed_organization_pk or current_org_pk
        eff_type_pk = body.claimed_membership_type_master_data_pk or cur_membership_type_pk
        # GDR-009 §2B: a Darshaka has no attendance Sakha. Supplying one is a
        # 422; a claim that is (or becomes) Darshaka while still carrying one
        # has it removed here (flag + number included) so the admin is never
        # stuck — approval would otherwise refuse it.
        attendance_cleared = False
        if is_probationary_membership_type(cur, str(eff_type_pk) if eff_type_pk else None):
            if body.darshak_organization_pk is not None:
                require_non_darshaka_for_attendance(cur, str(eff_type_pk))
            if cur_darshak_org is not None:
                attendance_cleared = True
                cur_darshak_org = cur_darshak_legacy = cur_darshak_number = None
                claim_sets.append("darshak_organization_pk = NULL")
        # Legacy rule (GDR-009): validate the EFFECTIVE flag+number pair —
        # incoming values merged over the stored ones — with the one shared
        # validator, then write the normalised pair back. Same for the
        # attendance Sakha, whose effective org may itself be edited here.
        if attendance_cleared or any(v is not None for v in (
            body.is_legacy_member, body.claimed_local_sakha_number,
            body.darshak_is_legacy_member, body.darshak_local_sakha_number,
            body.darshak_organization_pk, body.claimed_credential_document_number,
        )):
            eff_legacy = cur_legacy if body.is_legacy_member is None else body.is_legacy_member
            eff_number = cur_number if body.claimed_local_sakha_number is None else body.claimed_local_sakha_number
            eff_darshak_org = body.darshak_organization_pk or cur_darshak_org
            eff_darshak_legacy = cur_darshak_legacy if body.darshak_is_legacy_member is None else body.darshak_is_legacy_member
            eff_darshak_number = cur_darshak_number if body.darshak_local_sakha_number is None else body.darshak_local_sakha_number
            new_number, new_darshak_number = validate_claim_local_numbers(
                is_legacy_member=eff_legacy,
                claimed_local_sakha_number=eff_number,
                darshak_organization_pk=eff_darshak_org,
                darshak_is_legacy_member=eff_darshak_legacy,
                darshak_local_sakha_number=eff_darshak_number,
            )
            claim_sets.append("is_legacy_member = %s")
            claim_params.append(bool(eff_legacy))
            claim_sets.append("claimed_local_sakha_number = %s")
            claim_params.append(new_number)
            claim_sets.append("darshak_is_legacy_member = %s")
            claim_params.append(bool(eff_darshak_org and eff_darshak_legacy))
            claim_sets.append("darshak_local_sakha_number = %s")
            claim_params.append(new_darshak_number)
            # GDR-009 §2A: the Patra number is validated with the same
            # effective flag (merged over the stored values), so flag and
            # both numbers can never disagree.
            eff_patra = cur_patra_number if body.claimed_credential_document_number is None else body.claimed_credential_document_number
            claim_sets.append("claimed_credential_document_number = %s")
            claim_params.append(resolve_legacy_patra_number(
                cur, eff_legacy, eff_patra,
                card_type=patra_card_type_for_membership_type(cur, eff_type_pk),
                issuing_organization_pk=eff_org_pk,
            ))
        if body.claimed_joining_date is not None:
            claim_sets.append("claimed_joining_date = %s")
            claim_params.append(body.claimed_joining_date or None)
        if body.darshak_organization_pk is not None:
            claim_sets.append("darshak_organization_pk = %s")
            claim_params.append(str(body.darshak_organization_pk))

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
                   mt.value_code AS membership_type_code,
                   rc.is_legacy_member,
                   rc.darshak_is_legacy_member
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
         membership_type_code, is_legacy_member, darshak_is_legacy_member) = claim

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

        # GDR-009 §2B: a Darshaka cannot hold a cross-Sakha attendance
        # affiliation (must transfer). Registration and claim edit refuse it;
        # this also catches a claim stored in that state.
        if darshak_org_pk:
            require_non_darshaka_for_attendance(cur, membership_type_pk)

        # AUTH-BR-086 as amended by GDR-009 (owner 2026-11-01): a LEGACY
        # claim must carry the existing Local Sakha Number (422 if it does
        # not); a non-legacy claim must carry none, and the number is
        # auto-generated below by the shared allocator (Regular/Associate
        # series, or the Darshak series for a Darshaka). The same rule
        # applies separately to the attendance Sakha. The admin verified
        # (and could correct) both via PATCH before getting here; this
        # re-check also catches a row stored in a contradictory state.
        local_sakha_number, darshak_local_sakha_number = validate_claim_local_numbers(
            is_legacy_member=is_legacy_member,
            claimed_local_sakha_number=local_sakha_number,
            darshak_organization_pk=darshak_org_pk,
            darshak_is_legacy_member=darshak_is_legacy_member,
            darshak_local_sakha_number=darshak_local_sakha_number,
        )

        # GDR-009 §2A: the Parichaya/Anumati Patra number follows the SAME
        # legacy flag — legacy: the card's existing number (format-checked,
        # 409 if already issued); new: blank, minted by the shared allocator
        # inside issue_credential_at_enrolment() below.
        credential_document_number = resolve_legacy_patra_number(
            cur, is_legacy_member, credential_document_number,
            card_type=patra_card_type_for_membership_type(cur, membership_type_pk),
            issuing_organization_pk=org_pk,
        )

        # MBR-038A: a sangha_sevi's organization must be Sakha-like.
        # Mirrors the DB trigger (trg_enforce_sakha_only_sangha_sevi) with a
        # clean 422. Guards both sangha_sevi inserts below, which share org_pk.
        require_sakha_organization(cur, str(org_pk))

        # 5/6. Create (or link) the sangha_sevi AND its home affiliation.
        # Creation always goes through the shared helper, which opens the home
        # affiliation with the claimed Local Sakha Number (validated, 409 if
        # taken) or an auto-generated one — a Sangha Sevi is never created
        # without a Local Sakha ID, and an org with no short_code is a loud 422.
        sangha_sevi_id = None
        sangha_sevi_pk = None
        sangha_sevi_newly_created = False
        home_local_sakha_erp_id = None
        actor_pk = user.actor_pk

        existing = None
        if not is_darshaka:
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
            # Link to existing SS record; make sure it holds an open
            # affiliation at the claimed Sakha (create one if it does not).
            sangha_sevi_pk = existing[0]
            sangha_sevi_id = existing[1]
            cur.execute(
                """
                SELECT 1 FROM nss.membership_sakha_affiliation
                WHERE sangha_sevi_pk = %s AND organization_pk = %s AND effective_to IS NULL
                """,
                (str(sangha_sevi_pk), str(org_pk)),
            )
            if cur.fetchone() is None:
                aff_pk = insert_sakha_affiliation(
                    cur,
                    sangha_sevi_pk=str(sangha_sevi_pk),
                    organization_pk=str(org_pk),
                    local_number=local_sakha_number or None,
                    effective_from=joining_date,
                    is_darshak=is_darshaka,
                )
                log_audit(cur, action="CREATE", table_name="membership_sakha_affiliation",
                          record_pk=str(aff_pk), actor_pk=actor_pk,
                          actor_user_account_pk=str(user.user_account_pk),
                          module="claim_approval",
                          summary="Created primary sakha affiliation")
        else:
            created_ss = create_sangha_sevi_with_home_affiliation(
                cur,
                person_pk=str(person_pk),
                membership_type_pk=str(membership_type_pk),
                organization_pk=str(org_pk),
                joining_date=joining_date,
                actor_pk=actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
                module="claim_approval",
                local_number=local_sakha_number,
                is_darshak=is_darshaka,
                audit_suffix=" via claim approval",
            )
            sangha_sevi_pk = created_ss["sangha_sevi_pk"]
            sangha_sevi_id = created_ss["sangha_sevi_id"]
            sangha_sevi_newly_created = True
            home_local_sakha_erp_id = created_ss["local_sakha_erp_id"]

        # 6b. Mandatory credential (MBR-010/014/019A/B): every new Sangha
        # Sevi is issued an Anumati Patra (Darshaka) or Parichaya Patra
        # (Regular/Associate) — a legacy member's existing number is
        # recorded, otherwise minted. Same rule admin.py enforces, via the
        # same shared helper issue_credential_at_enrolment(). Only for a newly-created SS
        # record: linking to an existing one (the person is already a
        # Sangha Sevi elsewhere) means they already hold a credential.
        if sangha_sevi_newly_created:
            # GDR-009 §2A: a legacy member's validated card number is
            # recorded; otherwise the number is auto-minted (Parichaya
            # Kendra-wide, Anumati per Sakha).
            credential_type, credential_pk, credential_doc_number = issue_credential_at_enrolment(
                cur,
                is_legacy_member=is_legacy_member,
                membership_type_pk=str(membership_type_pk),
                document_number=credential_document_number,
                sangha_sevi_pk=str(sangha_sevi_pk),
                organization_pk=str(org_pk),
                local_sakha_erp_id=home_local_sakha_erp_id,
                joining_date=joining_date,
                date_of_birth=fetch_person_date_of_birth(cur, person_pk),
            )
            log_audit(cur, action="CREATE", table_name=credential_type.lower(),
                      record_pk=credential_pk, actor_pk=actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="claim_approval",
                      summary=f"Issued {credential_type} {credential_doc_number} via claim approval")

        # 7. Darshak attendance affiliation (at a different Sakha). Legacy
        # attendee: the existing Darshak number; otherwise the allocator's
        # next number in that Sakha's Darshak series. Skipped only when the
        # member already holds an OPEN affiliation there; any other
        # collision is a 409 that rolls the whole approval back.
        if darshak_org_pk:
            ensure_darshak_attendance_affiliation(
                cur,
                sangha_sevi_pk=str(sangha_sevi_pk),
                organization_pk=str(darshak_org_pk),
                local_number=darshak_local_sakha_number,
                effective_from=joining_date,
                actor_pk=actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
                module="claim_approval",
            )

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
