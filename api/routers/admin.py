"""
NSS ERP — Administration router.

Tier 5 endpoints (all require authentication + appropriate permissions):
  GET    /api/v1/admin/users                                — List user accounts
  GET    /api/v1/admin/sangha-sevi/without-account           — List SS with no usable login (Create Account picker)
  GET    /api/v1/admin/users/check-account/{person_pk}       — Does this person already have a login?
  POST   /api/v1/admin/users                                — Create user account
  POST   /api/v1/admin/sangha-sevi                          — Create Sangha Sevi record (standalone)
  POST   /api/v1/admin/persons                              — Create person record
  GET    /api/v1/admin/persons/check-contact                — Duplicate mobile/email check
  GET    /api/v1/admin/sangha-sevi/check/{person_pk}         — Does this person have a Sangha Sevi record?
  POST   /api/v1/admin/sangha-sevi/check-batch              — Batch Sangha-Sevi existence check
  GET    /api/v1/admin/users/{user_account_pk}              — User detail + roles
  POST   /api/v1/admin/users/{user_account_pk}/reset-password — Admin reset password
  PATCH  /api/v1/admin/users/{user_account_pk}/status       — Activate/lock/deactivate
  DELETE /api/v1/admin/users/{user_account_pk}              — Soft-delete user account
  GET    /api/v1/admin/users/{user_account_pk}/roles        — List role assignments
  POST   /api/v1/admin/users/{user_account_pk}/roles        — Assign role + scope
  DELETE /api/v1/admin/users/{user_account_pk}/roles/{user_role_pk} — Revoke role
  GET    /api/v1/admin/organizations                        — List organizations
  GET    /api/v1/admin/organizations/kumari-sevak-sakha-options — Sakha options for Kumari/Sevak scope
  GET    /api/v1/admin/organizations/code-availability      — Is a proposed org short-code free?
  GET    /api/v1/admin/organizations/next-code              — Suggested next org short-code
  GET    /api/v1/admin/sakha-scope-options                   — Sakha scope options for role assignment
  PATCH  /api/v1/admin/organizations/{pk}/short-code        — Update short code (NSS_ERP_ADMIN only)
  POST   /api/v1/admin/organizations                        — Create organization (NSS_ERP_ADMIN only)
  PATCH  /api/v1/admin/organizations/{pk}                   — Update org details (ORGANIZATION_MANAGE or scoped admin)
  GET    /api/v1/admin/dashboard-stats                       — Aggregated stats for admin dashboard cards
  PATCH  /api/v1/admin/patra/{patra_type}/{patra_pk}/document-number — Correct an issued Parichaya/Anumati Patra number (MBR-030H)
  GET    /api/v1/admin/credentials/members                   — Per-member credential health (OK/EXPIRING/LAPSED/MISSING)
  GET    /api/v1/admin/credentials/members/{sangha_sevi_pk}/timeline — Full Anumati+Parichaya credential history
  POST   /api/v1/admin/credentials/members/{sangha_sevi_pk}/issue — Issue/renew the expected credential (optional manual number, MBR-030H)
  POST   /api/v1/admin/credentials/members/{sangha_sevi_pk}/promote — Promote Darshaka → Regular (expire Anumati, issue Parichaya; MBR-010)

Authority: SOL-ADMIN-001 through SOL-ADMIN-004,
           Tier 5 design decisions (2026-09-15, 2026-09-20)
"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.rbac import require_any_permission, require_permission
from api.helpers import (
    next_id, peek_next_id, resolve_or_create_city_village, resolve_or_create_postal_code,
    get_active_status_pk, compose_local_sakha_erp_id, log_audit,
    apply_person_profile_update,
    insert_sakha_affiliation, is_probationary_membership_type,
    require_entity, check_duplicate_contact, record_password_history,
    validate_and_hash_password,
    build_order_by, natural_sort_key,
    require_sakha_organization, resolve_kumari_sevak_parent_sakha,
    resolve_scoped_sakha, ORGANIZATION_ADDRESS_JOINS_SQL,
    get_kendra_organization_pk, next_credential_document_number,
    issue_membership_credential, USER_ACCOUNT_MEMBERSHIP_JOINS_SQL,
    validate_mobile, validate_email,
    fetch_person_date_of_birth,
    parse_optional_date, normalize_patra_document_number,
    set_membership_credential_status, close_sakha_affiliation,
    get_master_data_pk, previous_festival_date_on_or_before,
    PROBATIONARY_MEMBERSHIP_TYPE_CODE,
)
from api.schemas.admin import (
    AccountlessSanghaSeviListResponse,
    AccountlessSanghaSeviResponse,
    AssignRoleRequest,
    AutoGrantedScopeResponse,
    CreateSanghaSeviRequest,
    CreateSanghaSeviResponse,
    CreateUserRequest,
    ResetPasswordRequest,
    RoleAssignmentResponse,
    UpdateStatusRequest,
    UpdatePersonProfileRequest,
    PersonProfileResponse,
    UserAccountResponse,
    UserDetailResponse,
    UserListResponse,
)
from api.schemas.auth import MessageResponse
from api.services.rbac_service import (
    UserContext,
    actor_scope_org_pks as _actor_scope_org_pks,
    org_in_scope as _org_in_scope,
    org_subtree_pks as _org_subtree_pks,
    require_org_in_scope as _require_org_in_scope,
    require_person_in_scope as _require_person_in_scope,
    require_account_in_scope as _require_account_in_scope,
    load_composite_grants as _load_composite_grants,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── GET /users ──────────────────────────────────────────────────────────

# Sortable columns for the User Accounts table, mapped to the SQL that
# orders them. Every key here must be a column the table actually shows,
# and no caller input reaches the SQL — build_order_by rejects anything
# not in this map. Business IDs use natural ordering so SS2 precedes SS10.
_USER_SORT_COLUMNS: dict[str, str | list[str]] = {
    "person_id": natural_sort_key("p.person_id"),
    "sangha_sevi_id": natural_sort_key("ss.sangha_sevi_id"),
    "person_name": "CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)",
    "organization_name": "COALESCE(o.organization_name, co.organization_name)",
    "local_sakha_erp_id": natural_sort_key(
        "COALESCE(msa.local_sakha_erp_id, rc.claimed_local_sakha_number)"
    ),
    "darshak_local_number": natural_sort_key("dmsa.local_sakha_erp_id"),
    "account_status": "ua.account_status",
    "force_password_change": "ua.force_password_change",
    "last_login_at": "ua.last_login_at",
    "created_at": "ua.created_at",
}


@router.get("/users", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by sangha_sevi_id or person name"),
    account_status: str | None = Query(None, description="Filter by status"),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_dir: str | None = Query(None, description="Sort direction: asc or desc"),
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
) -> UserListResponse:
    """
    List user accounts with pagination, filtering and sorting.

    Requires: ADMIN_USER_VIEW or ADMIN_USER_MANAGE or MEMBERSHIP_APPROVE permission.
    Scope-aware: NSS-WIDE admins see all users; org-scoped admins
    see only users whose Sangha Sevi organization matches their scope.

    Sorting is done in SQL rather than in the browser because the list is
    paginated — sorting the fetched page alone would reorder 20 rows and
    present it as an ordering of all of them.
    """
    offset = (page - 1) * page_size
    order_by = build_order_by(
        sort_by, sort_dir, _USER_SORT_COLUMNS, "ua.created_at DESC"
    )

    # Build WHERE clause dynamically
    conditions = ["TRUE"]
    params: list = []

    # Only accounts tied to an active Sangha Sevi belong in the User Accounts
    # view. An account with no Sangha Sevi (a bare person, or an in-flight
    # self-registration) must not surface here — a claim-based one is handled
    # in Registration Approvals, and a claimless orphan must never be
    # approvable. Equivalent to INNER JOINing sangha_sevi, but kept as a WHERE
    # filter so the shared join constant (reused by get_user_detail) is
    # untouched.
    conditions.append("ss.sangha_sevi_pk IS NOT NULL")

    if account_status:
        conditions.append("ua.account_status = %s")
        params.append(account_status)

    if search:
        conditions.append(
            "(ss.sangha_sevi_id ILIKE %s OR "
            "p.first_name ILIKE %s OR p.last_name ILIKE %s)"
        )
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    with conn.cursor() as cur:
        # ── Scope-based filtering (ADMIN-BR-076, subtree-aware) ──
        # Global authority (NSS_ERP_ADMIN / NSS-WIDE) sees everything;
        # every other admin sees only users whose Sangha-Sevi org — or
        # pending-claim org — falls inside their scope subtree, matching
        # exactly what they are allowed to manage.
        allowed = _actor_scope_org_pks(cur, user)
        if allowed is not None:
            if not allowed:
                # Scope-bounded admin with no org anchor → nothing visible.
                return UserListResponse(users=[], total=0, page=page, page_size=page_size)
            placeholders = ",".join(["%s"] * len(allowed))
            allowed_list = list(allowed)
            conditions.append(
                f"(ss.organization_pk IN ({placeholders})"
                f" OR rc.claimed_organization_pk IN ({placeholders}))"
            )
            params.extend(allowed_list)
            params.extend(allowed_list)

        where_clause = " AND ".join(conditions)

        # Count total
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            LEFT JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk
                  AND ss.is_active = TRUE
            LEFT JOIN nss.registration_claim rc
                  ON rc.person_pk = ua.person_pk
                  AND rc.claim_status = 'PENDING'
                  AND rc.is_active = TRUE
            WHERE {where_clause}
            """,
            params,
        )
        total = cur.fetchone()[0]

        # Fetch page
        cur.execute(
            f"""
            SELECT ua.user_account_pk,
                   ua.person_pk,
                   p.person_id,
                   ss.sangha_sevi_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS person_name,
                   COALESCE(o.organization_name, co.organization_name) AS organization_name,
                   COALESCE(msa.local_sakha_erp_id, rc.claimed_local_sakha_number) AS local_sakha_erp_id,
                   dmsa.local_sakha_erp_id AS darshak_local_number,
                   dorg2.organization_name AS darshak_organization_name,
                   mt.value_code AS home_membership_type_code,
                   ua.account_status,
                   ua.force_password_change,
                   ua.last_login_at,
                   ua.password_expires_at,
                   ua.created_at,
                   ua.is_active
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            {USER_ACCOUNT_MEMBERSHIP_JOINS_SQL}
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    users = [
        UserAccountResponse(
            user_account_pk=r[0],
            person_pk=r[1],
            person_id=r[2],
            sangha_sevi_id=r[3],
            person_name=r[4] if r[4] and r[4].strip() else None,
            organization_name=r[5],
            local_sakha_erp_id=r[6],
            darshak_local_number=r[7],
            darshak_organization_name=r[8],
            home_membership_type_code=r[9],
            account_status=r[10],
            force_password_change=r[11],
            last_login_at=r[12],
            password_expires_at=r[13],
            created_at=r[14],
            is_active=r[15],
        )
        for r in rows
    ]

    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /sangha-sevi/without-account ────────────────────────────────────

@router.get("/sangha-sevi/without-account", response_model=AccountlessSanghaSeviListResponse)
def list_sangha_sevi_without_account(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by sangha_sevi_id or person name"),
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
) -> AccountlessSanghaSeviListResponse:
    """
    List Sangha Sevis who hold an SS ID but cannot log in — the anti-join
    the "Create Account" picker on the User Accounts page runs to find who
    it can offer.

    A Sangha Sevi qualifies when either no nss.user_account row exists for
    their person_pk at all, or the only one is soft-deleted (is_active =
    FALSE) — uq_user_account_person is a plain UNIQUE, not partial, so a
    soft-deleted row still occupies the slot and must be reported (as
    has_deleted_account) rather than hidden, since POST /admin/users
    reactivates that row in place instead of inserting a new one.

    Requires: ADMIN_USER_VIEW or ADMIN_USER_MANAGE or MEMBERSHIP_APPROVE
    permission. Scope-aware: NSS-WIDE admins see all; org-scoped admins see
    only members whose Sangha Sevi organization falls inside their scope.
    """
    offset = (page - 1) * page_size

    conditions = ["ss.is_active = TRUE", "(ua.user_account_pk IS NULL OR ua.is_active = FALSE)"]
    params: list = []

    if search:
        conditions.append(
            "(ss.sangha_sevi_id ILIKE %s OR "
            "p.first_name ILIKE %s OR p.last_name ILIKE %s)"
        )
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    with conn.cursor() as cur:
        # ── Scope-based filtering (ADMIN-BR-076) ── same subtree rule as
        # list_users — an org-scoped admin may only see (and therefore only
        # offer accounts to) Sangha Sevis anchored inside their own scope.
        allowed = _actor_scope_org_pks(cur, user)
        if allowed is not None:
            if not allowed:
                return AccountlessSanghaSeviListResponse(
                    members=[], total=0, page=page, page_size=page_size
                )
            placeholders = ",".join(["%s"] * len(allowed))
            conditions.append(f"ss.organization_pk IN ({placeholders})")
            params.extend(list(allowed))

        where_clause = " AND ".join(conditions)
        order_by = ", ".join(natural_sort_key("ss.sangha_sevi_id"))

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM nss.sangha_sevi ss
            JOIN nss.person p ON p.person_pk = ss.person_pk
            LEFT JOIN nss.user_account ua ON ua.person_pk = ss.person_pk
            WHERE {where_clause}
            """,
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT ss.sangha_sevi_pk,
                   ss.sangha_sevi_id,
                   ss.person_pk,
                   p.person_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS person_name,
                   o.organization_name,
                   msa.local_sakha_erp_id,
                   mtt.value_code AS membership_type_code,
                   mts.value_code AS membership_status_code,
                   ss.joining_date,
                   (ua.user_account_pk IS NOT NULL) AS has_deleted_account
            FROM nss.sangha_sevi ss
            JOIN nss.person p ON p.person_pk = ss.person_pk
            LEFT JOIN nss.user_account ua ON ua.person_pk = ss.person_pk
            LEFT JOIN nss.organization o ON o.organization_pk = ss.organization_pk
            LEFT JOIN nss.membership_sakha_affiliation msa
                  ON msa.sangha_sevi_pk = ss.sangha_sevi_pk
                  AND msa.organization_pk = ss.organization_pk
                  AND msa.affiliation_status IN ('ACTIVE', 'REACTIVATED')
                  AND msa.effective_to IS NULL
            LEFT JOIN nss.master_data mtt ON mtt.master_data_pk = ss.membership_type_master_data_pk
            LEFT JOIN nss.master_data mts ON mts.master_data_pk = ss.membership_status_master_data_pk
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    members = [
        AccountlessSanghaSeviResponse(
            sangha_sevi_pk=r[0],
            sangha_sevi_id=r[1],
            person_pk=r[2],
            person_id=r[3],
            person_name=r[4] if r[4] and r[4].strip() else None,
            organization_name=r[5],
            local_sakha_erp_id=r[6],
            membership_type_code=r[7],
            membership_status_code=r[8],
            joining_date=r[9],
            has_deleted_account=bool(r[10]),
        )
        for r in rows
    ]

    return AccountlessSanghaSeviListResponse(
        members=members,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── POST /persons (admin person creation) ──────────────────────────────

class AdminCreatePersonRequest(BaseModel):
    """POST /api/v1/admin/persons — admin creates a person directly."""
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    gender_master_data_pk: str = Field(
        ..., min_length=1, description="UUID of gender master_data row"
    )
    country_phone_code: str | None = Field(None, max_length=10)
    mobile_number: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)


@router.post("/persons", status_code=201)
def admin_create_person(
    body: AdminCreatePersonRequest,
    user: UserContext = Depends(require_permission("PERSON_MANAGE")),
    conn=Depends(get_write_connection),
):
    """
    Create a new person record (admin-only).

    Requires: PERSON_MANAGE permission.
    Returns the person_pk, person_id, and person_name.
    """
    if not body.mobile_number and not body.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one of mobile_number or email is required.",
        )
    # MBR-CONTACT-01/02: country-wise mobile + email format validation.
    validate_mobile(body.country_phone_code, body.mobile_number)
    validate_email(body.email)

    with conn.cursor() as cur:
        check_duplicate_contact(
            cur,
            mobile_number=body.mobile_number,
            country_phone_code=body.country_phone_code,
            email=body.email,
        )

        actor = user.actor_pk
        person_id = next_id(cur, "PERSON", actor_pk=actor)

        cur.execute(
            """
            INSERT INTO nss.person (
                person_id, first_name, middle_name, last_name,
                date_of_birth, gender_master_data_pk,
                country_phone_code, mobile_number, email
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING person_pk
            """,
            (
                person_id,
                body.first_name.strip().title(),
                body.middle_name.strip().title() if body.middle_name else None,
                body.last_name.strip().title() if body.last_name else None,
                body.date_of_birth or None,
                body.gender_master_data_pk,
                body.country_phone_code,
                body.mobile_number,
                body.email.strip().lower() if body.email else None,
            ),
        )
        person_pk = cur.fetchone()[0]
        log_audit(cur, action="CREATE", table_name="person", record_pk=str(person_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Created person {body.first_name} {body.last_name}")

    name_parts = [body.first_name.strip().title()]
    if body.middle_name:
        name_parts.append(body.middle_name.strip().title())
    if body.last_name:
        name_parts.append(body.last_name.strip().title())

    return {
        "person_pk": str(person_pk),
        "person_id": person_id,
        "person_name": " ".join(name_parts),
    }


# ── GET /persons/check-contact ──────────────────────────────────────────

@router.get("/persons/check-contact")
def check_person_contact(
    mobile_number: str | None = Query(None, max_length=20),
    country_phone_code: str | None = Query(None, max_length=10),
    email: str | None = Query(None, max_length=255),
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
):
    """
    Non-destructive duplicate-contact lookup for the Create Person form.

    Returns, for whichever of ``mobile_number`` / ``email`` is supplied,
    the existing active person (if any) already using it — so the UI can
    warn inline *before* submit. Purely advisory: the authoritative 409 is
    still raised by ``check_duplicate_contact`` on create.
    """
    def _match(sql: str, params: list):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        if not row:
            return None
        return {"person_id": row[0], "person_name": row[1]}

    mobile_conflict = None
    if mobile_number and country_phone_code:
        mobile_conflict = _match(
            """
            SELECT person_id,
                   TRIM(CONCAT_WS(' ', first_name, middle_name, last_name))
            FROM nss.person
            WHERE country_phone_code = %s AND mobile_number = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            [country_phone_code, mobile_number],
        )

    email_conflict = None
    if email:
        email_conflict = _match(
            """
            SELECT person_id,
                   TRIM(CONCAT_WS(' ', first_name, middle_name, last_name))
            FROM nss.person
            WHERE LOWER(email) = LOWER(%s) AND is_active = TRUE
            LIMIT 1
            """,
            [email],
        )

    return {
        "mobile_conflict": mobile_conflict,
        "email_conflict": email_conflict,
    }


@router.post("/users", response_model=UserAccountResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> UserAccountResponse:
    """
    Create a new user account for an existing person.

    Requires: ADMIN_USER_MANAGE or PERSON_MANAGE permission (ADMIN-BR-078 —
    account provisioning is a scoped operation, not reserved to the global
    authority). Scope-bounded: a non-global admin may provision only for a
    person anchored inside their scope subtree (ADMIN-BR-076).
    Validates: person exists, no existing account, password policy.
    Optionally creates a Sangha Sevi (membership) record if
    create_sangha_sevi=true.
    """
    # Validate + hash password
    password_hash, password_expires_at = validate_and_hash_password(body.password)

    # Validate SS creation fields if requested
    if body.create_sangha_sevi:
        missing = []
        if not body.membership_type_pk:
            missing.append("membership_type_pk")
        # joining_date is NOT required (MBR-047): the Sangha Joining Date is
        # optional to capture and NULL means "not recorded".
        # organization_pk is NOT required here: a single-Sakha admin has it
        # auto-resolved below (resolve_scoped_sakha). An NSS-wide/multi-Sakha
        # admin who omits it still gets a clear 422 from the resolver.
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Sangha Sevi fields required: {', '.join(missing)}",
            )

    generated_ss_id = None
    generated_credential_type = None
    generated_credential_document_number = None

    with conn.cursor() as cur:
        actor = user.actor_pk

        # Check person exists
        require_entity(cur, "person", str(body.person_pk), label="Person")

        # ADMIN-BR-076/078: a scope-bounded admin may provision an account
        # only for a person anchored inside their scope. When a Sangha Sevi
        # is created in the same call, the in-scope organization check (after
        # resolution, below) is that anchor; otherwise the person must already
        # sit inside the actor's scope subtree.
        if not body.create_sangha_sevi:
            _require_person_in_scope(cur, user, str(body.person_pk), "create accounts")

        # Check no existing account for this person
        cur.execute(
            "SELECT user_account_pk, is_active FROM nss.user_account WHERE person_pk = %s",
            (str(body.person_pk),),
        )
        existing = cur.fetchone()
        if existing is not None:
            ex_pk, ex_active = existing
            if ex_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A user account already exists for this person.",
                )
            # Reactivate the soft-deleted account with new credentials
            cur.execute(
                """
                UPDATE nss.user_account
                SET is_active = TRUE,
                    deleted_at = NULL,
                    account_status = 'ACTIVE',
                    password_hash = %s,
                    force_password_change = %s,
                    password_expires_at = %s,
                    failed_login_attempts = 0,
                    locked_until = NULL,
                    last_failed_login_at = NULL,
                    updated_at = NOW()
                WHERE user_account_pk = %s
                RETURNING user_account_pk, created_at
                """,
                (
                    password_hash,
                    body.force_password_change,
                    password_expires_at,
                    str(ex_pk),
                ),
            )
            reactivated = cur.fetchone()
            ua_pk = reactivated[0]
            ua_created_at = reactivated[1]
            log_audit(cur, action="REACTIVATE", table_name="user_account", record_pk=str(ua_pk),
                      actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                      module="admin", summary=f"Reactivated user account for person {body.person_pk}")
            record_password_history(cur, str(ua_pk), password_hash, "ADMIN_RESET", actor_pk=actor)
        else:
            cur.execute(
                """
                INSERT INTO nss.user_account (
                    person_pk,
                    password_hash,
                    account_status,
                    force_password_change,
                    password_expires_at
                ) VALUES (%s, %s, 'ACTIVE', %s, %s)
                RETURNING user_account_pk, created_at
                """,
                (
                    str(body.person_pk),
                    password_hash,
                    body.force_password_change,
                    password_expires_at,
                ),
            )
            new_row = cur.fetchone()
            ua_pk = new_row[0]
            ua_created_at = new_row[1]
            log_audit(cur, action="CREATE", table_name="user_account", record_pk=str(ua_pk),
                      actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                      module="admin", summary=f"Created user account for person {body.person_pk}")
            record_password_history(cur, str(ua_pk), password_hash, "ADMIN_RESET", actor_pk=actor)

        # ── Optionally create Sangha Sevi record ──────────────
        if body.create_sangha_sevi:
            # Check no existing SS for this person
            cur.execute(
                "SELECT sangha_sevi_id FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
                (str(body.person_pk),),
            )
            if cur.fetchone() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This person already has a Sangha Sevi record.",
                )

            # Get ACTIVE status pk
            active_status_pk = get_active_status_pk(cur)

            # MBR-038A: membership must be tied to a Sakha Sangha.
            # Auto-resolve the Sakha when omitted (single-Sakha admin), or
            # require an explicit in-scope pick otherwise — mirrors the
            # Sangha Sevi create path.
            if not body.organization_pk:
                body.organization_pk = resolve_scoped_sakha(
                    cur, user=user, requested_organization_pk=body.organization_pk
                )
            require_sakha_organization(cur, body.organization_pk)
            # ADMIN-BR-076: the account is anchored to this Sakha — it must
            # fall inside the actor's scope subtree.
            _require_org_in_scope(cur, user, body.organization_pk, "create accounts")

            generated_ss_id = next_id(cur, "SANGHA_SEVI", actor_pk=actor)
            # MBR-047: optional. "" from an untouched UI field becomes NULL,
            # and a malformed value becomes a 422 instead of a 500.
            joining_date_val = parse_optional_date(
                body.joining_date, "Sangha Joining Date",
            )
            cur.execute(
                """
                INSERT INTO nss.sangha_sevi (
                    sangha_sevi_id, person_pk,
                    membership_type_master_data_pk,
                    membership_status_master_data_pk,
                    organization_pk, joining_date
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING sangha_sevi_pk
                """,
                (
                    generated_ss_id,
                    str(body.person_pk),
                    body.membership_type_pk,
                    str(active_status_pk),
                    body.organization_pk,
                    joining_date_val,
                ),
            )
            ss_pk = cur.fetchone()[0]
            log_audit(cur, action="CREATE", table_name="sangha_sevi", record_pk=str(ss_pk),
                      actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                      module="admin", summary=f"Created sangha sevi {generated_ss_id}")

            # Create membership_sakha_affiliation if local_sakha_erp_id provided
            if body.local_sakha_erp_id:
                aff_pk = insert_sakha_affiliation(
                    cur,
                    sangha_sevi_pk=str(ss_pk),
                    organization_pk=body.organization_pk,
                    local_number=body.local_sakha_erp_id,
                    effective_from=joining_date_val,
                    is_darshak=is_probationary_membership_type(
                        cur, body.membership_type_pk
                    ),
                )
                log_audit(cur, action="CREATE", table_name="membership_sakha_affiliation", record_pk=str(aff_pk),
                          actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                          module="admin", summary="Created sakha affiliation")

            # ── Mandatory credential (MBR-010/014/019A/B) ──────────
            # PROBATIONARY -> Anumati Patra; REGULAR/ASSOCIATE -> Parichaya
            # Patra. Same shared gatekeeper as /sangha-sevi — this branch
            # also creates a sangha_sevi row, so it owes the member the
            # same credential (previously a gap: this path minted a
            # Sangha Sevi record with no card issued at all).
            generated_credential_type, generated_credential_pk, generated_credential_document_number = (
                issue_membership_credential(
                    cur,
                    sangha_sevi_pk=str(ss_pk),
                    membership_type_pk=body.membership_type_pk,
                    organization_pk=body.organization_pk,
                    document_number=body.credential_document_number,
                    issue_date=date.fromisoformat(body.credential_issue_date) if body.credential_issue_date else None,
                    issue_year=body.credential_issue_year,
                    valid_from=date.fromisoformat(body.credential_valid_from) if body.credential_valid_from else None,
                    valid_to=date.fromisoformat(body.credential_valid_to) if body.credential_valid_to else None,
                    joining_date=joining_date_val,
                    date_of_birth=fetch_person_date_of_birth(cur, body.person_pk),
                )
            )
            log_audit(cur, action="CREATE", table_name=generated_credential_type.lower(),
                      record_pk=generated_credential_pk, actor_pk=actor,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="admin",
                      summary=f"Issued {generated_credential_type} {generated_credential_document_number} via create_user")

        # Fetch sangha_sevi_id + person_name for response
        cur.execute(
            """
            SELECT ss.sangha_sevi_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)
            FROM nss.person p
            LEFT JOIN nss.sangha_sevi ss ON ss.person_pk = p.person_pk
                  AND ss.is_active = TRUE
            WHERE p.person_pk = %s
            """,
            (str(body.person_pk),),
        )
        info = cur.fetchone()

    return UserAccountResponse(
        user_account_pk=ua_pk,
        person_pk=body.person_pk,
        sangha_sevi_id=info[0] if info else None,
        sangha_sevi_id_generated=generated_ss_id,
        credential_type=generated_credential_type,
        credential_document_number=generated_credential_document_number,
        person_name=info[1] if info and info[1] and info[1].strip() else None,
        account_status="ACTIVE",
        force_password_change=body.force_password_change,
        last_login_at=None,
        password_expires_at=password_expires_at,
        created_at=ua_created_at,
        is_active=True,
    )


# ── POST /sangha-sevi ─────────────────────────────────────────────────

@router.post("/sangha-sevi", response_model=CreateSanghaSeviResponse, status_code=201)
def create_sangha_sevi(
    body: CreateSanghaSeviRequest,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> CreateSanghaSeviResponse:
    """
    Create a Sangha Sevi (membership) record for an existing person.

    Standalone endpoint — decoupled from user account creation.
    Requires: ADMIN_USER_MANAGE or PERSON_MANAGE permission.
    Scoped admins can only create SS for organizations within their scope
    (ADMIN-BR-076), and may bundle a login account within that scope
    (ADMIN-BR-078). The in-scope check runs after Sakha resolution, below.
    """
    # Optional bundled login-account creation. Account provisioning is a
    # scoped operation (ADMIN-BR-078): any admin authorized to create the
    # Sangha Sevi within scope may also bundle its login. Validate the
    # password up front (before any write) so a bad request fails fast.
    ua_pk = None
    password_hash = None
    password_expires_at = None
    if body.create_user_account:
        if not body.password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="password is required when create_user_account is true.",
            )
        password_hash, password_expires_at = validate_and_hash_password(body.password)

    with conn.cursor() as cur:
        # Check person exists
        require_entity(cur, "person", str(body.person_pk), label="Person")

        # Check no existing SS for this person
        cur.execute(
            "SELECT sangha_sevi_id FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
            (str(body.person_pk),),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This person already has a Sangha Sevi record.",
            )

        # Get ACTIVE status pk
        active_status_pk = get_active_status_pk(cur)

        # Auto-resolve the target Sakha when the caller omitted it: a
        # single-Sakha admin gets their own Sakha filled in; an NSS-wide or
        # multi-Sakha admin is asked to pick. This is the member-attach
        # analogue of the Kumari/Sevak parent-Sakha auto-select pattern.
        # Explicit picks are left untouched.
        if not body.organization_pk:
            body.organization_pk = resolve_scoped_sakha(
                cur, user=user, requested_organization_pk=body.organization_pk
            )

        # MBR-038A: membership must be tied to a Sakha Sangha.
        require_sakha_organization(cur, body.organization_pk)

        # ADMIN-BR-076: the Sangha Sevi (and any bundled account) is anchored
        # to this Sakha — it must fall inside the actor's scope subtree. Covers
        # both the resolved and the explicitly-picked organization.
        _require_org_in_scope(cur, user, body.organization_pk, "create Sangha Sevi records")

        # Generate SS ID and insert
        actor = user.actor_pk
        ss_id = next_id(cur, "SANGHA_SEVI", actor_pk=actor)
        # MBR-047: Sangha Joining Date is optional; "" becomes NULL.
        joining_date_val = parse_optional_date(
            body.joining_date, "Sangha Joining Date",
        )
        cur.execute(
            """
            INSERT INTO nss.sangha_sevi (
                sangha_sevi_id, person_pk,
                membership_type_master_data_pk,
                membership_status_master_data_pk,
                organization_pk, joining_date
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING sangha_sevi_pk
            """,
            (
                ss_id,
                str(body.person_pk),
                body.membership_type_pk,
                str(active_status_pk),
                body.organization_pk,
                joining_date_val,
            ),
        )
        ss_pk = cur.fetchone()[0]
        log_audit(cur, action="CREATE", table_name="sangha_sevi", record_pk=str(ss_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Created sangha sevi {ss_id}")

        # ── Mandatory credential (MBR-010/014/019A/B) ──────────
        # PROBATIONARY -> Anumati Patra; REGULAR/ASSOCIATE -> Parichaya
        # Patra. Auto-generates a new FY document number unless the caller
        # supplied one (an already-issued legacy credential being entered).
        credential_type, credential_pk, credential_document_number = issue_membership_credential(
            cur,
            sangha_sevi_pk=str(ss_pk),
            membership_type_pk=body.membership_type_pk,
            organization_pk=body.organization_pk,
            document_number=body.credential_document_number,
            issue_date=date.fromisoformat(body.credential_issue_date) if body.credential_issue_date else None,
            issue_year=body.credential_issue_year,
            valid_from=date.fromisoformat(body.credential_valid_from) if body.credential_valid_from else None,
            valid_to=date.fromisoformat(body.credential_valid_to) if body.credential_valid_to else None,
            joining_date=joining_date_val,
            date_of_birth=fetch_person_date_of_birth(cur, body.person_pk),
        )
        log_audit(cur, action="CREATE", table_name=credential_type.lower(), record_pk=credential_pk,
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Issued {credential_type} {credential_document_number}")

        # Create membership_sakha_affiliation if local_sakha_erp_id provided
        if body.local_sakha_erp_id:
            aff_pk = insert_sakha_affiliation(
                cur,
                sangha_sevi_pk=str(ss_pk),
                organization_pk=body.organization_pk,
                local_number=body.local_sakha_erp_id,
                effective_from=joining_date_val,
                is_darshak=is_probationary_membership_type(
                    cur, body.membership_type_pk
                ),
            )
            log_audit(cur, action="CREATE", table_name="membership_sakha_affiliation", record_pk=str(aff_pk),
                      actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                      module="admin", summary="Created sakha affiliation")

        # ── Optionally create a login (user account) ──────────
        # Mirrors POST /users' account block, inverted: here the Sangha Sevi
        # is created first and the account is bundled onto it. Validated
        # above (ADMIN_USER_MANAGE + password present).
        if body.create_user_account:
            cur.execute(
                "SELECT user_account_pk, is_active FROM nss.user_account WHERE person_pk = %s",
                (str(body.person_pk),),
            )
            existing = cur.fetchone()
            if existing is not None:
                ex_pk, ex_active = existing
                if ex_active:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A user account already exists for this person.",
                    )
                # Reactivate the soft-deleted account with new credentials.
                cur.execute(
                    """
                    UPDATE nss.user_account
                    SET is_active = TRUE,
                        deleted_at = NULL,
                        account_status = 'ACTIVE',
                        password_hash = %s,
                        force_password_change = %s,
                        password_expires_at = %s,
                        failed_login_attempts = 0,
                        locked_until = NULL,
                        last_failed_login_at = NULL,
                        updated_at = NOW()
                    WHERE user_account_pk = %s
                    RETURNING user_account_pk
                    """,
                    (password_hash, body.force_password_change, password_expires_at, str(ex_pk)),
                )
                ua_pk = cur.fetchone()[0]
                log_audit(cur, action="REACTIVATE", table_name="user_account", record_pk=str(ua_pk),
                          actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                          module="admin", summary=f"Reactivated user account for person {body.person_pk}")
                record_password_history(cur, str(ua_pk), password_hash, "ADMIN_RESET", actor_pk=actor)
            else:
                cur.execute(
                    """
                    INSERT INTO nss.user_account (
                        person_pk, password_hash, account_status,
                        force_password_change, password_expires_at
                    ) VALUES (%s, %s, 'ACTIVE', %s, %s)
                    RETURNING user_account_pk
                    """,
                    (str(body.person_pk), password_hash, body.force_password_change, password_expires_at),
                )
                ua_pk = cur.fetchone()[0]
                log_audit(cur, action="CREATE", table_name="user_account", record_pk=str(ua_pk),
                          actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                          module="admin", summary=f"Created user account for person {body.person_pk}")
                record_password_history(cur, str(ua_pk), password_hash, "ADMIN_RESET", actor_pk=actor)

        # Fetch person name and org name for response
        cur.execute(
            """
            SELECT CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name),
                   o.organization_name
            FROM nss.person p
            LEFT JOIN nss.organization o ON o.organization_pk = %s
            WHERE p.person_pk = %s
            """,
            (body.organization_pk, str(body.person_pk)),
        )
        info = cur.fetchone()

    return CreateSanghaSeviResponse(
        sangha_sevi_pk=ss_pk,
        sangha_sevi_id=ss_id,
        person_pk=body.person_pk,
        person_name=info[0] if info and info[0] and info[0].strip() else None,
        organization_name=info[1] if info else None,
        user_account_pk=ua_pk,
        credential_type=credential_type,
        credential_document_number=credential_document_number,
    )


# ── GET /sangha-sevi/check/{person_pk} ─────────────────────────────────

@router.get("/sangha-sevi/check/{person_pk}")
def check_sangha_sevi(
    person_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
):
    """
    Check if a person already has an active Sangha Sevi record.

    Returns { has_sangha_sevi: bool, sangha_sevi_id: str|null }.
    Used by the Create Sangha Sevi tab to warn the admin before proceeding.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sangha_sevi_id FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
            (str(person_pk),),
        )
        row = cur.fetchone()

    return {
        "has_sangha_sevi": row is not None,
        "sangha_sevi_id": row[0] if row else None,
    }


# ── POST /sangha-sevi/check-batch ─────────────────────────────────────

@router.post("/sangha-sevi/check-batch")
def check_sangha_sevi_batch(
    body: dict,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
):
    """
    Batch check which persons already have active Sangha Sevi records
    OR pending registration claims.

    Request:  { "person_pks": ["<uuid>", ...] }
    Response: {
      "<person_pk>": {
        "sangha_sevi_id": "SS1",          -- present if active SS exists
        "pending_claim_pk": "<uuid>",     -- present if PENDING claim exists
        "pending_claim_org": "Ekamra..."  -- claimed org name
      }, ...
    }
    Only persons with an active SS or a pending claim appear in the map.
    """
    person_pks = body.get("person_pks", [])
    if not person_pks or len(person_pks) > 100:
        return {}

    pk_strs = [str(pk) for pk in person_pks]
    result = {}

    with conn.cursor() as cur:
        # Check active Sangha Sevi records
        cur.execute(
            """SELECT person_pk::text, sangha_sevi_id
                 FROM nss.sangha_sevi
                WHERE person_pk = ANY(%s::uuid[]) AND is_active = TRUE""",
            (pk_strs,),
        )
        for r in cur.fetchall():
            result[r[0]] = {"sangha_sevi_id": r[1]}

        # Check pending registration claims
        cur.execute(
            """SELECT rc.person_pk::text,
                      rc.registration_claim_pk::text,
                      COALESCE(o.organization_name, '')
                 FROM nss.registration_claim rc
                 LEFT JOIN nss.organization o
                   ON o.organization_pk = rc.claimed_organization_pk
                WHERE rc.person_pk = ANY(%s::uuid[])
                  AND rc.claim_status = 'PENDING'
                  AND rc.is_active = TRUE""",
            (pk_strs,),
        )
        for r in cur.fetchall():
            entry = result.get(r[0], {})
            entry["pending_claim_pk"] = r[1]
            entry["pending_claim_org"] = r[2]
            result[r[0]] = entry

    return result


# ── GET /users/check-account/{person_pk} ───────────────────────────────

@router.get("/users/check-account/{person_pk}")
def check_user_account(
    person_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
):
    """
    Check whether a person already has a usable login.

    Returns { has_account: bool, is_active: bool|null }. has_account is
    TRUE for a live account (blocks Create Account with a 409 upstream)
    and also TRUE for a soft-deleted one (is_active: false) — POST
    /admin/users reactivates that row in place rather than inserting, so
    the Create User wizard's Step 3 needs to know a slot is already
    occupied even though nothing is currently listable there.

    Used by the Create User wizard right after a person is selected — it
    used to piggyback on GET /admin/users?search=<person_id>, but that
    endpoint's search only matches sangha_sevi_id/first_name/last_name, so
    a person_id never matched anything and the check silently always came
    back negative.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT is_active FROM nss.user_account WHERE person_pk = %s",
            (str(person_pk),),
        )
        row = cur.fetchone()

    return {
        "has_account": row is not None,
        "is_active": bool(row[0]) if row else None,
    }


# ── GET /users/{pk} ────────────────────────────────────────────────────

@router.get("/users/{user_account_pk}", response_model=UserDetailResponse)
def get_user(
    user_account_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
) -> UserDetailResponse:
    """
    Get full user account detail including role assignments.

    Requires: ADMIN_USER_VIEW or ADMIN_USER_MANAGE permission.
    """
    with conn.cursor() as cur:
        # User account + person info
        cur.execute(
            f"""
            SELECT ua.user_account_pk,
                   ua.person_pk,
                   p.person_id,
                   ss.sangha_sevi_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS person_name,
                   COALESCE(o.organization_name, co.organization_name) AS organization_name,
                   COALESCE(msa.local_sakha_erp_id, rc.claimed_local_sakha_number) AS local_sakha_erp_id,
                   dmsa.local_sakha_erp_id AS darshak_local_number,
                   dorg2.organization_name AS darshak_organization_name,
                   mt.value_code AS home_membership_type_code,
                   ua.account_status,
                   ua.force_password_change,
                   ua.last_login_at,
                   ua.password_expires_at,
                   ua.failed_login_attempts,
                   ua.locked_until,
                   ua.created_at,
                   ua.is_active
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            {USER_ACCOUNT_MEMBERSHIP_JOINS_SQL}
            WHERE ua.user_account_pk = %s
            """,
            (str(user_account_pk),),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # ── Scope check: org-scoped admins can only view users in their subtree ──
    # Subtree-aware (ADMIN-BR-076): a Kendra admin can view any user anchored
    # to a descendant Sakha. Considers both the active Sangha-Sevi org and any
    # pending-claim org so claim-only users stay visible to their approver.
    with conn.cursor() as cur2:
        allowed = _actor_scope_org_pks(cur2, user)
        if allowed is not None:
            person_pk_str = str(row[1])  # row[1] = person_pk
            cur2.execute(
                """
                SELECT ss.organization_pk
                FROM nss.sangha_sevi ss
                WHERE ss.person_pk = %s AND ss.is_active = TRUE
                UNION
                SELECT rc.claimed_organization_pk
                FROM nss.registration_claim rc
                WHERE rc.person_pk = %s AND rc.claim_status = 'PENDING'
                      AND rc.is_active = TRUE
                """,
                (person_pk_str, person_pk_str),
            )
            target_org_pks = {str(r[0]) for r in cur2.fetchall() if r[0] is not None}
            if not target_org_pks or not target_org_pks & allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This user is outside your admin scope.",
                )

    # Fetch role assignments
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ur.user_role_pk,
                   rm.role_code,
                   rm.role_name,
                   asc2.scope_level,
                   asc2.organization_pk,
                   o.organization_name,
                   ur.created_at AS assigned_at,
                   ur.is_active
            FROM nss.user_role ur
            JOIN nss.role_master rm ON rm.role_master_pk = ur.role_master_pk
            LEFT JOIN nss.admin_scope asc2 ON asc2.user_role_pk = ur.user_role_pk
            LEFT JOIN nss.organization o ON o.organization_pk = asc2.organization_pk
            WHERE ur.user_account_pk = %s
            ORDER BY ur.is_active DESC, ur.created_at DESC
            """,
            (str(user_account_pk),),
        )
        role_rows = cur.fetchall()

    roles = [
        RoleAssignmentResponse(
            user_role_pk=r[0],
            role_code=r[1],
            role_name=r[2],
            scope_level=r[3],
            organization_pk=r[4],
            organization_name=r[5],
            assigned_at=r[6],
            is_active=r[7],
        )
        for r in role_rows
    ]

    # §63 composite auto-grants — derived live from governance positions,
    # shown read-only alongside the real user_role assignments above.
    with conn.cursor() as cur:
        composite_scopes, _composite_permissions = _load_composite_grants(cur, row[1])
        auto_granted_scopes = []
        if composite_scopes:
            org_pks = [str(s.organization_pk) for s in composite_scopes if s.organization_pk]
            org_names: dict[str, str] = {}
            if org_pks:
                cur.execute(
                    "SELECT organization_pk, organization_name FROM nss.organization "
                    "WHERE organization_pk = ANY(%s::uuid[])",
                    (org_pks,),
                )
                org_names = {str(r[0]): r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT role_code, role_name FROM nss.role_master "
                "WHERE role_code = ANY(%s)",
                (sorted({s.role_code for s in composite_scopes}),),
            )
            role_names = {r[0]: r[1] for r in cur.fetchall()}
            auto_granted_scopes = [
                AutoGrantedScopeResponse(
                    role_code=s.role_code,
                    role_name=role_names.get(s.role_code, s.role_code),
                    scope_level=s.scope_level,
                    organization_pk=s.organization_pk,
                    organization_name=org_names.get(str(s.organization_pk)) if s.organization_pk else None,
                )
                for s in composite_scopes
            ]

    return UserDetailResponse(
        user_account_pk=row[0],
        person_pk=row[1],
        person_id=row[2],
        sangha_sevi_id=row[3],
        person_name=row[4] if row[4] and row[4].strip() else None,
        organization_name=row[5],
        local_sakha_erp_id=row[6],
        darshak_local_number=row[7],
        darshak_organization_name=row[8],
        home_membership_type_code=row[9],
        account_status=row[10],
        force_password_change=row[11],
        last_login_at=row[12],
        password_expires_at=row[13],
        failed_login_attempts=row[14],
        locked_until=row[15],
        created_at=row[16],
        is_active=row[17],
        roles=roles,
        auto_granted_scopes=auto_granted_scopes,
    )


# ── POST /users/{pk}/reset-password ────────────────────────────────────

@router.post(
    "/users/{user_account_pk}/reset-password",
    response_model=MessageResponse,
)
def reset_password(
    user_account_pk: UUID,
    body: ResetPasswordRequest,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Admin-initiated password reset.

    Requires: ADMIN_USER_MANAGE or PERSON_MANAGE permission, bounded to the
    actor's scope (ADMIN-BR-076/078). Sets force_password_change by default.
    """
    # Validate + hash new password
    new_hash, new_expiry = validate_and_hash_password(body.new_password)

    with conn.cursor() as cur:
        # Check target user exists
        require_entity(cur, "user_account", str(user_account_pk), label="User account")

        # ADMIN-BR-076: a scope-bounded admin may reset only in-scope accounts.
        _require_account_in_scope(cur, user, user_account_pk, "reset passwords")

        actor = user.actor_pk

        # Update password
        cur.execute(
            """
            UPDATE nss.user_account
            SET password_hash = %s,
                password_expires_at = %s,
                force_password_change = %s,
                failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (
                new_hash,
                new_expiry,
                body.force_password_change,
                str(user_account_pk),
            ),
        )
        log_audit(cur, action="PASSWORD_CHANGE", table_name="user_account", record_pk=str(user_account_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary="Admin reset password")

        # Record in password_history
        record_password_history(cur, str(user_account_pk), new_hash, "ADMIN_RESET", actor_pk=actor)

    return MessageResponse(message="Password has been reset.")


# ── PATCH /users/{pk}/status ───────────────────────────────────────────

@router.patch(
    "/users/{user_account_pk}/status",
    response_model=MessageResponse,
)
def update_status(
    user_account_pk: UUID,
    body: UpdateStatusRequest,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Change a user account's status (ACTIVE, LOCKED, INACTIVE).

    Requires: ADMIN_USER_MANAGE or PERSON_MANAGE permission, bounded to the
    actor's scope (ADMIN-BR-076/078).
    Cannot change own status (safety).

    This endpoint only ever touches nss.user_account.account_status — it
    never creates or links a sangha_sevi record. Approving a Sangha Sevi
    from a registration claim happens in exactly one place:
    claim_approval.py::approve_claim() (Registration Approvals tab). A
    PENDING_APPROVAL account with an outstanding claim must go through that
    flow instead of being flipped to ACTIVE here — see the PENDING-claim
    guard below. (Previously this endpoint independently auto-generated a
    sangha_sevi on activation, duplicating and diverging from
    approve_claim()'s logic — e.g. it never created the
    membership_sakha_affiliation row or composed a proper local_sakha_erp_id,
    so activating this way silently produced a Sangha Sevi with no real
    local number.)
    """
    # Prevent self-modification
    # str() comparison: see delete_user's identical guard for why a bare
    # `==` between a uuid.UUID and a str silently never matches.
    if str(user_account_pk) == str(user.user_account_pk):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot change your own account status.",
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ua.account_status, ua.person_pk
            FROM nss.user_account ua
            WHERE ua.user_account_pk = %s AND ua.is_active = TRUE
            """,
            (str(user_account_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )
        current_status, person_pk = row

        # ADMIN-BR-076: a scope-bounded admin may act only on in-scope accounts.
        _require_person_in_scope(cur, user, str(person_pk), "change account status")

        actor = user.actor_pk

        # A PENDING registration_claim must be approved/rejected via the
        # Registration Approvals flow (claim_approval.py) — the single
        # place a Sangha Sevi gets created from a claim. Block activation
        # here rather than silently skipping membership creation.
        if body.account_status == "ACTIVE" and current_status == "PENDING_APPROVAL":
            cur.execute(
                """
                SELECT 1 FROM nss.registration_claim
                WHERE user_account_pk = %s AND claim_status = 'PENDING'
                LIMIT 1
                """,
                (str(user_account_pk),),
            )
            if cur.fetchone() is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "This account has a pending registration claim. "
                        "Approve or reject it from Registration Approvals — "
                        "that is where the Sangha Sevi record gets created."
                    ),
                )

            # A user_account cannot be activated unless the person already
            # has an active Sangha Sevi record. An account with no claim and
            # no Sangha Sevi (e.g. a bare person registered without membership
            # details) must not be approvable here — approving it would leave
            # an ACTIVE account that can never log in (login requires a Sangha
            # Sevi). The admin must create the Sangha Sevi record first.
            cur.execute(
                """
                SELECT 1 FROM nss.sangha_sevi
                WHERE person_pk = %s AND is_active = TRUE
                LIMIT 1
                """,
                (str(person_pk),),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "This person has no Sangha Sevi record. Create the "
                        "Sangha Sevi record first (Create Sangha Sevi), then "
                        "approve the account."
                    ),
                )

        # Update the status
        cur.execute(
            """
            UPDATE nss.user_account
            SET account_status = %s,
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (body.account_status, str(user_account_pk)),
        )
        log_audit(cur, action="STATUS_CHANGE", table_name="user_account", record_pk=str(user_account_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Changed status to {body.account_status}")

    return MessageResponse(message=f"Account status changed to {body.account_status}.")


# ── GET /persons/{pk} ────────────────────────────────────────────────

@router.get("/persons/{person_pk}", response_model=PersonProfileResponse)
def get_person_profile(
    person_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
) -> PersonProfileResponse:
    """
    Fetch the raw editable field values for the Profile Details edit card.

    Read counterpart to PATCH /api/v1/admin/persons/{pk} — same field set,
    1:1, so the admin UI can pre-fill the edit form and PATCH it straight
    back. Requires: ADMIN_USER_MANAGE or PERSON_MANAGE, bounded to the
    actor's scope (ADMIN-BR-076), same as the write side.
    """
    with conn.cursor() as cur:
        _require_person_in_scope(cur, user, str(person_pk), "view profile details")

        cur.execute(
            """
            SELECT person_pk, first_name, middle_name, last_name, date_of_birth,
                   gender_master_data_pk, marital_status_master_data_pk,
                   blood_group_master_data_pk, country_phone_code, mobile_number,
                   email, emergency_contact_name, emergency_contact_phone,
                   emergency_relationship_master_data_pk, remarks
            FROM nss.person
            WHERE person_pk = %s AND is_active = TRUE
            """,
            (str(person_pk),),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found.",
        )

    return PersonProfileResponse(
        person_pk=row[0], first_name=row[1], middle_name=row[2], last_name=row[3],
        date_of_birth=row[4], gender_master_data_pk=row[5],
        marital_status_master_data_pk=row[6], blood_group_master_data_pk=row[7],
        country_phone_code=row[8], mobile_number=row[9], email=row[10],
        emergency_contact_name=row[11], emergency_contact_phone=row[12],
        emergency_relationship_master_data_pk=row[13], remarks=row[14],
    )


# ── PATCH /persons/{pk} ─────────────────────────────────────────────────

@router.patch("/persons/{person_pk}", response_model=MessageResponse)
def update_person_profile(
    person_pk: UUID,
    body: UpdatePersonProfileRequest,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Admin correction of a member's personal-info fields.

    Admin counterpart to PATCH /api/v1/auth/profile — same field set, same
    validation rules, same PATCH semantics (only non-None fields applied).
    Both surfaces are delegated to helpers.apply_person_profile_update(),
    the single shared code path, so admin corrections and self-service
    edits can never drift apart.

    Requires: ADMIN_USER_MANAGE or PERSON_MANAGE, bounded to the actor's
    scope (ADMIN-BR-076) — the same dual-gate already used by the sibling
    Detail-view actions (status change, delete account) on this screen.

    Every change is captured twice: nss.person.updated_at /
    updated_by_sangha_sevi_pk record who/when, the DB-level audit trigger
    records the full before/after field diff automatically, and this
    endpoint additionally writes an explicit log_audit() entry carrying
    the optional *reason* (there is no reason column on nss.person itself
    — a reason belongs to the edit event, not the row).
    """
    with conn.cursor() as cur:
        _require_person_in_scope(cur, user, str(person_pk), "edit profile details")

        changed = apply_person_profile_update(
            cur,
            person_pk=str(person_pk),
            body=body,
            updated_by_sangha_sevi_pk=user.actor_pk,
        )
        if not changed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No fields to update.",
            )

        log_audit(
            cur,
            action="UPDATE",
            table_name="person",
            record_pk=str(person_pk),
            actor_pk=user.actor_pk,
            actor_user_account_pk=str(user.user_account_pk),
            module="admin",
            summary=(
                "Corrected profile details"
                + (f" — {body.reason.strip()}" if body.reason and body.reason.strip() else "")
            ),
        )

    return MessageResponse(message="Profile updated.")


# ── DELETE /users/{pk} ────────────────────────────────────────────────

@router.delete(
    "/users/{user_account_pk}",
    response_model=MessageResponse,
)
def delete_user(
    user_account_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Soft-delete a user account.

    Requires: ADMIN_USER_MANAGE or PERSON_MANAGE permission, bounded to the
    actor's scope (ADMIN-BR-076/078).
    Sets is_active=FALSE, deleted_at=NOW() on user_account.
    Also soft-revokes all active role assignments and admin scopes.
    Cannot delete own account (safety).
    """
    now = datetime.now(timezone.utc)

    # Prevent self-deletion
    # Compare via str(): user.user_account_pk may come back from the DB
    # driver as either a str or a uuid.UUID depending on connection setup
    # (register_uuid), and uuid.UUID.__eq__ against a str is always False
    # even for the same value — a bare `==` here silently never fires.
    if str(user_account_pk) == str(user.user_account_pk):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot delete your own account.",
        )

    with conn.cursor() as cur:
        # Check user exists and is active
        cur.execute(
            """
            SELECT ua.user_account_pk, ua.person_pk, p.first_name, p.last_name,
                   ss.sangha_sevi_id, ss.sangha_sevi_pk
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            LEFT JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk
                  AND ss.is_active = TRUE
            WHERE ua.user_account_pk = %s AND ua.is_active = TRUE
            """,
            (str(user_account_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )
        _, person_pk, first_name, last_name, sevi_id, sevi_pk = row
        display = sevi_id or f"{first_name} {last_name}".strip()

        # ADMIN-BR-076: a scope-bounded admin may delete only in-scope accounts.
        _require_person_in_scope(cur, user, str(person_pk), "delete accounts")

        actor = user.actor_pk

        # Soft-delete user_account
        cur.execute(
            """
            UPDATE nss.user_account
            SET is_active = FALSE,
                deleted_at = %s,
                account_status = 'INACTIVE',
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (now, str(user_account_pk)),
        )
        log_audit(cur, action="DELETE", table_name="user_account", record_pk=str(user_account_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary="Soft-deleted user account")

        # Soft-revoke all active roles
        cur.execute(
            """
            UPDATE nss.user_role
            SET is_active = FALSE,
                revoked_at = %s,
                deleted_at = %s,
                updated_at = NOW()
            WHERE user_account_pk = %s AND is_active = TRUE
            """,
            (now, now, str(user_account_pk)),
        )

        # Soft-deactivate all admin scopes for those roles
        cur.execute(
            """
            UPDATE nss.admin_scope
            SET is_active = FALSE,
                deleted_at = %s,
                updated_at = NOW()
            WHERE user_role_pk IN (
                SELECT user_role_pk FROM nss.user_role
                WHERE user_account_pk = %s
            )
            AND is_active = TRUE
            """,
            (now, str(user_account_pk)),
        )

        # Soft-delete Sangha Sevi record (if exists)
        if sevi_pk:
            cur.execute(
                """
                UPDATE nss.sangha_sevi
                SET is_active = FALSE,
                    deleted_at = %s,
                    updated_at = NOW()
                WHERE sangha_sevi_pk = %s AND is_active = TRUE
                """,
                (now, str(sevi_pk)),
            )
            log_audit(cur, action="DELETE", table_name="sangha_sevi", record_pk=str(sevi_pk),
                      actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                      module="admin", summary=f"Soft-deleted SS {sevi_id} (user account deletion)")

            # Soft-delete active affiliations for this SS.
            # chk_mem_sakha_aff_status_consistency requires that any row
            # with effective_to set also have affiliation_status='ARCHIVED'
            # — closing a row without archiving it violates that CHECK.
            cur.execute(
                """
                UPDATE nss.membership_sakha_affiliation
                SET effective_to = %s,
                    affiliation_status = 'ARCHIVED',
                    updated_at = NOW()
                WHERE sangha_sevi_pk = %s AND effective_to IS NULL
                """,
                (now, str(sevi_pk)),
            )

        # Soft-delete any pending registration claims for this person
        cur.execute(
            """
            UPDATE nss.registration_claim
            SET claim_status = 'REJECTED',
                admin_remarks = 'Auto-rejected: user account deleted',
                reviewed_at = %s,
                updated_at = NOW()
            WHERE person_pk = %s AND claim_status = 'PENDING'
            """,
            (now, str(person_pk)),
        )

    return MessageResponse(message=f"User account '{display}' has been deleted.")


# ── GET /users/{pk}/roles ──────────────────────────────────────────────

@router.get(
    "/users/{user_account_pk}/roles",
    response_model=list[RoleAssignmentResponse],
)
def list_user_roles(
    user_account_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
) -> list[RoleAssignmentResponse]:
    """
    List all role assignments for a user (active and revoked).

    Requires: ADMIN_USER_VIEW or ADMIN_USER_MANAGE permission.
    Scope-aware: org-scoped admins can only view roles for users in their orgs.
    """
    # ── Scope check: subtree-aware (ADMIN-BR-076) ──
    # Org-scoped admins can only view roles for users inside their subtree.
    with conn.cursor() as cur:
        _require_account_in_scope(cur, user, user_account_pk, "view roles for accounts")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ur.user_role_pk,
                   rm.role_code,
                   rm.role_name,
                   asc2.scope_level,
                   asc2.organization_pk,
                   o.organization_name,
                   ur.created_at AS assigned_at,
                   ur.is_active
            FROM nss.user_role ur
            JOIN nss.role_master rm ON rm.role_master_pk = ur.role_master_pk
            LEFT JOIN nss.admin_scope asc2 ON asc2.user_role_pk = ur.user_role_pk
            LEFT JOIN nss.organization o ON o.organization_pk = asc2.organization_pk
            WHERE ur.user_account_pk = %s
            ORDER BY ur.is_active DESC, ur.created_at DESC
            """,
            (str(user_account_pk),),
        )
        rows = cur.fetchall()

    return [
        RoleAssignmentResponse(
            user_role_pk=r[0],
            role_code=r[1],
            role_name=r[2],
            scope_level=r[3],
            organization_pk=r[4],
            organization_name=r[5],
            assigned_at=r[6],
            is_active=r[7],
        )
        for r in rows
    ]


# ── POST /users/{pk}/roles ─────────────────────────────────────────────

@router.post(
    "/users/{user_account_pk}/roles",
    response_model=RoleAssignmentResponse,
    status_code=201,
)
def assign_role(
    user_account_pk: UUID,
    body: AssignRoleRequest,
    user: UserContext = Depends(require_permission("ADMIN_ROLE_MANAGE")),
    conn=Depends(get_write_connection),
) -> RoleAssignmentResponse:
    """
    Assign a role with scope to a user.

    Requires: ADMIN_ROLE_MANAGE permission.
    Validates:
      - Target user exists and is active
      - Role code exists
      - Organization exists (if scope_level is not NSS-WIDE)
      - No duplicate active assignment for same role
    """
    with conn.cursor() as cur:
        # Validate target user
        cur.execute(
            "SELECT user_account_pk FROM nss.user_account WHERE user_account_pk = %s AND is_active = TRUE",
            (str(user_account_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )

        # Validate role
        cur.execute(
            "SELECT role_master_pk, role_name, scope_level FROM nss.role_master WHERE role_code = %s AND is_active = TRUE",
            (body.role_code,),
        )
        role_row = cur.fetchone()
        if role_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role not found: {body.role_code}",
            )
        role_master_pk, role_name, role_scope_level = role_row

        # Every role has exactly one fixed scope_level of its own (SOL-ADMIN-004
        # §8.7 — e.g. NSS_ERP_ADMIN is always NSS-WIDE, NSS_ERP_SAKHA_ADMIN is
        # always SAKHA). The scope-level <select> in the Assign-Role UI lists
        # all 7 levels independently of the chosen role, so without this check
        # a caller could request e.g. NSS_ERP_SAKHA_ADMIN at ZILLA scope — a
        # combination the role was never designed to hold and that no
        # permission set or dashboard tier expects.
        if body.scope_level != role_scope_level:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"{body.role_code} must be assigned at {role_scope_level} scope, "
                    f"not {body.scope_level}."
                ),
            )

        # Validate scope. Per the DB CHECK constraint
        # (chk_admin_scope_org_consistency, database/ddl/07_administration/
        # 02_admin_scope.sql), FOUR scope levels require organization_pk IS
        # NULL — not just NSS-WIDE: KENDRA, KENDRA_MAHILA_SANGHA, and
        # ADVISORY_BOARD are also apex/no-single-org scopes. This check
        # previously only exempted NSS-WIDE, so assigning any of the other
        # three would either 404 here (if no org_pk given, wrongly treated
        # as missing-required-field) or violate the DB constraint on INSERT
        # (if an org_pk was supplied, since the constraint forbids one).
        # KENDRA is additionally owner-confirmed (2026-10-22) as fully
        # NSS-WIDE-equivalent in authority, not just in this null-org shape
        # — see UserContext.is_nss_wide()/has_scope_for_org() in
        # api/services/rbac_service.py.
        organization_name = None
        _NULL_ORG_SCOPE_LEVELS = ("NSS-WIDE", "KENDRA", "KENDRA_MAHILA_SANGHA", "ADVISORY_BOARD")
        if body.scope_level not in _NULL_ORG_SCOPE_LEVELS:
            if body.organization_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="organization_pk is required for non-NSS-WIDE scope levels.",
                )
            cur.execute(
                "SELECT organization_name FROM nss.organization WHERE organization_pk = %s AND is_active = TRUE",
                (str(body.organization_pk),),
            )
            org_row = cur.fetchone()
            if org_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found.",
                )
            organization_name = org_row[0]
        else:
            if body.organization_pk is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"organization_pk must be null for {body.scope_level} scope.",
                )

        # Check for duplicate active assignment (same role + same scope + same org)
        # A user CAN have the same role with different scopes (e.g. SAKHA_ADMIN
        # for Sakha A and Sakha B), but NOT the same role+scope+org twice.
        cur.execute(
            """
            SELECT ur.user_role_pk
            FROM nss.user_role ur
            JOIN nss.admin_scope asc2 ON asc2.user_role_pk = ur.user_role_pk
            WHERE ur.user_account_pk = %s
              AND ur.role_master_pk = %s
              AND ur.is_active = TRUE
              AND asc2.scope_level = %s
              AND asc2.is_active = TRUE
              AND (asc2.organization_pk = %s OR (asc2.organization_pk IS NULL AND %s IS NULL))
            """,
            (
                str(user_account_pk),
                str(role_master_pk),
                body.scope_level,
                str(body.organization_pk) if body.organization_pk else None,
                str(body.organization_pk) if body.organization_pk else None,
            ),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User already has an active {body.role_code} role with scope {body.scope_level}"
                       + (f" for this organization." if body.organization_pk else "."),
            )

        # Insert user_role
        actor = user.actor_pk
        cur.execute(
            """
            INSERT INTO nss.user_role (
                user_account_pk,
                role_master_pk
            ) VALUES (%s, %s)
            RETURNING user_role_pk, created_at
            """,
            (str(user_account_pk), str(role_master_pk)),
        )
        ur_pk, assigned_at = cur.fetchone()
        log_audit(cur, action="CREATE", table_name="user_role", record_pk=str(ur_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Assigned role {body.role_code}")

        # Insert admin_scope
        cur.execute(
            """
            INSERT INTO nss.admin_scope (
                user_role_pk,
                scope_level,
                organization_pk
            ) VALUES (%s, %s, %s)
            """,
            (
                str(ur_pk),
                body.scope_level,
                str(body.organization_pk) if body.organization_pk else None,
            ),
        )

    return RoleAssignmentResponse(
        user_role_pk=ur_pk,
        role_code=body.role_code,
        role_name=role_name,
        scope_level=body.scope_level,
        organization_pk=body.organization_pk,
        organization_name=organization_name,
        assigned_at=assigned_at,
        is_active=True,
    )


# ── DELETE /users/{pk}/roles/{user_role_pk} ────────────────────────────

@router.delete(
    "/users/{user_account_pk}/roles/{user_role_pk}",
    response_model=MessageResponse,
)
def revoke_role(
    user_account_pk: UUID,
    user_role_pk: UUID,
    user: UserContext = Depends(require_permission("ADMIN_ROLE_MANAGE")),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Revoke (soft-delete) a role assignment.

    Requires: ADMIN_ROLE_MANAGE permission.
    Sets is_active=FALSE + revoked_at + revoked_by on user_role.
    Also deactivates the associated admin_scope.

    Cannot revoke your own role assignment (safety) — a user must not be
    able to strip their own access and lock themselves out.
    """
    # Prevent self-revocation
    # str() comparison: see delete_user's identical guard for why a bare
    # `==` between a uuid.UUID and a str silently never matches.
    if str(user_account_pk) == str(user.user_account_pk):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot revoke your own role assignment.",
        )

    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        # Validate user_role belongs to this user and is active
        cur.execute(
            """
            SELECT ur.user_role_pk
            FROM nss.user_role ur
            WHERE ur.user_role_pk = %s
              AND ur.user_account_pk = %s
              AND ur.is_active = TRUE
            """,
            (str(user_role_pk), str(user_account_pk)),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active role assignment not found for this user.",
            )

        actor = user.actor_pk

        # Soft-revoke user_role
        cur.execute(
            """
            UPDATE nss.user_role
            SET is_active = FALSE,
                revoked_at = %s,
                deleted_at = %s,
                updated_at = NOW()
            WHERE user_role_pk = %s
            """,
            (now, now, str(user_role_pk)),
        )
        log_audit(cur, action="DELETE", table_name="user_role", record_pk=str(user_role_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary="Revoked role assignment")

        # Soft-deactivate admin_scope
        cur.execute(
            """
            UPDATE nss.admin_scope
            SET is_active = FALSE,
                deleted_at = %s,
                updated_at = NOW()
            WHERE user_role_pk = %s
              AND is_active = TRUE
            """,
            (now, str(user_role_pk)),
        )

    return MessageResponse(message="Role assignment revoked.")


# ══════════════════════════════════════════════════════════════════════════
# Organization Management
# ══════════════════════════════════════════════════════════════════════════


# ── GET /organizations ────────────────────────────────────────────────────

# Sortable columns for the Organizations list.
_ORG_SORT_COLUMNS: dict[str, str | list[str]] = {
    "organization_code": natural_sort_key("o.organization_code"),
    "organization_name": "o.organization_name",
    "short_code": "o.short_code",
    "type_name": "ot.value_name",
    "city_village_name": "cv.city_village_name",
    "district_name": "d.district_name",
    "state_name": "s.state_name",
}


@router.get("/organizations")
def list_organizations_admin(
    type_code: str | None = Query(None, description="Filter by organization type code"),
    search: str | None = Query(None, description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_dir: str | None = Query(None, description="Sort direction: asc or desc"),
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
):
    """
    List organizations with short_code for admin management.

    Requires: ADMIN_USER_VIEW or ADMIN_USER_MANAGE permission.

    Sorted in SQL because the list is paginated.
    """
    offset = (page - 1) * page_size
    order_by = build_order_by(
        sort_by, sort_dir, _ORG_SORT_COLUMNS, "o.organization_code"
    )
    conditions = ["o.is_active = TRUE"]
    params: list = []

    if type_code:
        conditions.append("ot.value_code = %s")
        params.append(type_code)

    if search:
        conditions.append(
            "(o.organization_name ILIKE %s OR o.organization_code ILIKE %s OR o.short_code ILIKE %s)"
        )
        like = f"%{search}%"
        params.extend([like, like, like])

    with conn.cursor() as cur:
        # ── Scope filter (ADMIN-BR-076, subtree-aware) ──
        # Global authority sees all orgs; a scoped admin sees only their org
        # subtree — the same set of orgs they may edit via update_organization.
        allowed = _actor_scope_org_pks(cur, user)
        if allowed is not None:
            if not allowed:
                return {
                    "total": 0, "page": page, "page_size": page_size,
                    "organizations": [],
                }
            placeholders = ",".join(["%s"] * len(allowed))
            conditions.append(f"o.organization_pk IN ({placeholders})")
            params.extend(list(allowed))

        where = " AND ".join(conditions)

        # Count
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM nss.organization o
            JOIN nss.master_data ot ON ot.master_data_pk = o.organization_type_master_data_pk
            JOIN nss.master_category mc ON mc.master_category_pk = ot.master_category_pk
            WHERE mc.category_code = 'ORGANIZATION_TYPE' AND {where}
            """,
            params,
        )
        total = cur.fetchone()[0]

        # Data
        cur.execute(
            f"""
            SELECT o.organization_pk,
                   o.organization_code,
                   o.organization_name,
                   o.short_code,
                   ot.value_code AS type_code,
                   ot.value_name AS type_name,
                   o.address_line_1,
                   pc.postal_code,
                   o.phone_number,
                   o.mobile_number,
                   o.email,
                   o.org_email,
                   o.website_url,
                   o.org_website_url,
                   o.youtube_channel_url,
                   o.org_youtube_channel_url,
                   o.country_pk,
                   c.country_name,
                   o.state_pk,
                   s.state_name,
                   o.district_pk,
                   d.district_name,
                   o.city_village_pk,
                   cv.city_village_name,
                   o.postal_code_pk,
                   -- Needed by the UI's canEditOrg() → isOrgOrDescendantOf()
                   -- walk, which decides whether a scoped admin may edit a
                   -- row. Without it that walk terminated on the first
                   -- iteration, so a Zilla/Anchalika admin saw no Edit button
                   -- on any of their descendant orgs.
                   o.parent_organization_pk,
                   o.country_phone_code
            FROM nss.organization o
            JOIN nss.master_data ot ON ot.master_data_pk = o.organization_type_master_data_pk
            JOIN nss.master_category mc ON mc.master_category_pk = ot.master_category_pk
            {ORGANIZATION_ADDRESS_JOINS_SQL}
            WHERE mc.category_code = 'ORGANIZATION_TYPE' AND {where}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "organizations": [
            {
                "organization_pk": str(r[0]),
                "organization_code": r[1],
                "organization_name": r[2],
                "short_code": r[3],
                "type_code": r[4],
                "type_name": r[5],
                "address_line_1": r[6],
                "postal_code": r[7],
                "phone_number": r[8],
                "mobile_number": r[9],
                # email/website_url/youtube_channel_url are the NSS-wide
                # defaults every org row carries (DB DEFAULT, never NULL);
                # org_* are the nullable per-org overrides. The UI falls
                # back to the NSS-wide value when no override is set.
                "email": r[10],
                "org_email": r[11],
                "website_url": r[12],
                "org_website_url": r[13],
                "youtube_channel_url": r[14],
                "org_youtube_channel_url": r[15],
                "country_pk": str(r[16]) if r[16] else None,
                "country_name": r[17],
                "state_pk": str(r[18]) if r[18] else None,
                "state_name": r[19],
                "district_pk": str(r[20]) if r[20] else None,
                "district_name": r[21],
                "city_village_pk": str(r[22]) if r[22] else None,
                "city_village_name": r[23],
                "postal_code_pk": str(r[24]) if r[24] else None,
                "parent_organization_pk": str(r[25]) if r[25] else None,
                "country_phone_code": r[26],
            }
            for r in rows
        ],
    }


# ── GET /organizations/kumari-sevak-sakha-options ──────────────────────────

@router.get("/organizations/kumari-sevak-sakha-options")
def get_kumari_sevak_sakha_options(
    type_code: str = Query(..., description="KUMARI_SANGHA or SEVAK_SANGHA"),
    # Bug fix: NSS_ERP_SAKHA_ADMIN only holds PERSON_MANAGE (see seed
    # database/seed/00_bootstrap/03_role_permission.sql), not
    # ADMIN_USER_MANAGE. Gating on ADMIN_USER_MANAGE alone made the
    # Sakha-admin branch below (and the identical gate on
    # create_organization) unreachable by any seeded role, contradicting
    # ORG-BR-101's documented "NSS admin or the Sakha's own admin" rule.
    # Matches the require_any_permission gate already used by the
    # ORG-BR-103 sibling endpoints (create_sangha_sevi, sakha-scope-options).
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
):
    """
    Parent-Sakha selection data for the Kumari/Sevak Sangha create/update
    form (ORG-BR-101/102).

    Returns the Sakha list the caller may choose from, plus an
    auto_select_pk hint when the choice isn't ambiguous:
      - NSS_ERP_ADMIN: every active Sakha, mode "choose" (no auto-select).
      - NSS_ERP_SAKHA_ADMIN scoped to exactly one Sakha: that Sakha only,
        mode "locked", auto_select_pk set.
      - NSS_ERP_SAKHA_ADMIN scoped to more than one Sakha: if exactly one
        of their Sakhas lacks an active org of this type, mode "locked"
        with that Sakha auto-selected; otherwise mode "choose" over just
        their own scoped Sakhas.

    This mirrors resolve_kumari_sevak_parent_sakha's authority/selection
    logic but never raises on ambiguity — it always returns a pickable
    list, since the point of this endpoint is to render that choice.
    """
    if type_code not in ("KUMARI_SANGHA", "SEVAK_SANGHA"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="type_code must be KUMARI_SANGHA or SEVAK_SANGHA.",
        )

    is_nss_admin = any(s.role_code == "NSS_ERP_ADMIN" for s in user.scopes)
    scoped_sakha_pks = sorted({
        str(s.organization_pk)
        for s in user.scopes
        if s.role_code == "NSS_ERP_SAKHA_ADMIN" and s.organization_pk
    })

    if not is_nss_admin and not scoped_sakha_pks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only NSS_ERP_ADMIN or a Sakha's own NSS_ERP_SAKHA_ADMIN may "
                "create or update a Kumari/Sevak Sangha (ORG-BR-101)."
            ),
        )

    with conn.cursor() as cur:
        if is_nss_admin:
            cur.execute(
                """
                SELECT o.organization_pk, o.organization_name, o.organization_code
                FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
                ORDER BY o.organization_name
                """
            )
            sakhas = [
                {"organization_pk": str(r[0]), "organization_name": r[1], "organization_code": r[2]}
                for r in cur.fetchall()
            ]
            return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}

        cur.execute(
            """
            SELECT o.organization_pk, o.organization_name, o.organization_code
            FROM nss.organization o
            WHERE o.organization_pk = ANY(%s::uuid[]) AND o.is_active = TRUE
            ORDER BY o.organization_name
            """,
            (scoped_sakha_pks,),
        )
        sakhas = [
            {"organization_pk": str(r[0]), "organization_name": r[1], "organization_code": r[2]}
            for r in cur.fetchall()
        ]

        if len(scoped_sakha_pks) == 1:
            return {"mode": "locked", "auto_select_pk": scoped_sakha_pks[0], "sakhas": sakhas}

        cur.execute(
            """
            SELECT o.parent_organization_pk
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.parent_organization_pk = ANY(%s::uuid[])
              AND md.value_code = %s
              AND o.is_active = TRUE
            """,
            (scoped_sakha_pks, type_code),
        )
        already_has = {str(r[0]) for r in cur.fetchall()}
        lacking = [pk for pk in scoped_sakha_pks if pk not in already_has]

        if len(lacking) == 1:
            return {"mode": "locked", "auto_select_pk": lacking[0], "sakhas": sakhas}

        return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}


@router.get("/sakha-scope-options")
def get_sakha_scope_options(
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
):
    """
    Sakha-selection data for member-attach forms (Create Sangha Sevi, Create
    User with membership). The member-attach analogue of
    /organizations/kumari-sevak-sakha-options — same auto-select/lock shape,
    but with no one-per-Sakha cardinality (a Sakha holds many members):

      - NSS-wide admin: every active Sakha, mode "choose" (no auto-select).
      - Admin scoped to exactly one Sakha: that Sakha only, mode "locked",
        auto_select_pk set.
      - Admin scoped to more than one Sakha: their own Sakhas, mode "choose".

    Never raises on ambiguity — it always returns a pickable list, mirroring
    resolve_scoped_sakha's authorization (exact-match SAKHA scopes).

    Returns { mode, auto_select_pk, sakhas: [{organization_pk,
    organization_name, organization_code}] }.
    """
    with conn.cursor() as cur:
        if user.is_nss_wide():
            cur.execute(
                """
                SELECT o.organization_pk, o.organization_name, o.organization_code
                FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
                ORDER BY o.organization_name
                """
            )
            sakhas = [
                {"organization_pk": str(r[0]), "organization_name": r[1], "organization_code": r[2]}
                for r in cur.fetchall()
            ]
            return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}

        scoped_sakha_pks = sorted({
            str(s.organization_pk)
            for s in user.scopes
            if s.scope_level == "SAKHA" and s.organization_pk
        })
        if not scoped_sakha_pks:
            return {"mode": "choose", "auto_select_pk": None, "sakhas": []}

        cur.execute(
            """
            SELECT o.organization_pk, o.organization_name, o.organization_code
            FROM nss.organization o
            WHERE o.organization_pk = ANY(%s::uuid[]) AND o.is_active = TRUE
            ORDER BY o.organization_name
            """,
            (scoped_sakha_pks,),
        )
        sakhas = [
            {"organization_pk": str(r[0]), "organization_name": r[1], "organization_code": r[2]}
            for r in cur.fetchall()
        ]

        if len(scoped_sakha_pks) == 1:
            return {"mode": "locked", "auto_select_pk": scoped_sakha_pks[0], "sakhas": sakhas}

        return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}


# ── GET /organizations/code-availability ───────────────────────────────────

@router.get("/organizations/code-availability")
def check_organization_code_availability(
    field: str = Query(..., description="organization_code or short_code"),
    value: str = Query(..., description="The value being typed"),
    exclude_pk: str | None = Query(
        None, description="Organization to exclude (the row being edited)"
    ),
    # Bug fix (sibling of the kumari-sevak-sakha-options / create_organization
    # gate fix): this backs the live short_code/organization_code duplicate
    # check the Create-Org form and inline short-code editor call while
    # typing. A Sakha admin creating a KUMARI_SANGHA/SEVAK_SANGHA (ORG-BR-101,
    # now reachable) or editing an in-scope org's short code would otherwise
    # get 403 on every keystroke despite being authorized for the underlying
    # create/save action.
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
):
    """
    Live duplicate check for organization_code / short_code as the user
    types. Reports whether the value is already taken and, if so, which
    organization holds it.

    Checks against ALL rows regardless of is_active, because the DB
    uniqueness constraints (uq_organization_code; the partial unique
    index uq_organization_short_code WHERE short_code IS NOT NULL) are
    NOT scoped to active rows — a soft-deleted org still owns the value
    and an INSERT/UPDATE reusing it would still be rejected. The
    conflicting org's is_active flag is returned so the UI can label an
    inactive holder.
    """
    if field not in ("organization_code", "short_code"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="field must be 'organization_code' or 'short_code'.",
        )

    normalized = value.strip()
    # short_code is stored uppercase (chk_organization_short_code); compare
    # case-insensitively so the preview matches what will actually be stored.
    if field == "short_code":
        normalized = normalized.upper()

    if not normalized:
        return {"field": field, "value": value, "available": True, "conflict": None}

    # Column name is from a fixed whitelist above — safe to interpolate.
    conditions = [f"o.{field} = %s"]
    params: list = [normalized]
    if exclude_pk:
        conditions.append("o.organization_pk <> %s")
        params.append(exclude_pk)
    where = " AND ".join(conditions)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT o.organization_pk, o.organization_name, o.organization_code,
                   o.short_code, o.is_active, md.value_name AS type_name
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE {where}
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()

    if row is None:
        return {"field": field, "value": normalized, "available": True, "conflict": None}

    return {
        "field": field,
        "value": normalized,
        "available": False,
        "conflict": {
            "organization_pk": str(row[0]),
            "organization_name": row[1],
            "organization_code": row[2],
            "short_code": row[3],
            "is_active": row[4],
            "type_name": row[5],
        },
    }


# ── PATCH /organizations/{pk}/short-code ──────────────────────────────────

@router.patch("/organizations/{organization_pk}/short-code")
def update_short_code(
    organization_pk: UUID,
    body: dict,
    user: UserContext = Depends(
        require_any_permission("ORGANIZATION_MANAGE", "ORGANIZATION_VIEW")
    ),
    conn=Depends(get_write_connection),
):
    """
    Set or update the short_code for an organization.

    Body: { "short_code": "EKM" }  (3-5 uppercase alphanumeric, or null to clear)

    Access rules (ADMIN-BR-076/077 — subtree-aware, same as update_organization):
      - NSS_ERP_ADMIN / NSS-WIDE: the sole blanket authority — edits any org.
      - Any scoped admin (KENDRA/ANCHALIKA/ZILLA/SAKHA), regardless of whether
        they hold ORGANIZATION_MANAGE or only ORGANIZATION_VIEW, edits only
        organizations inside their scope subtree (their org + descendants).
        Permission alone never confers global reach.
    """
    import re as _re

    short_code = body.get("short_code")

    # Validate format
    if short_code is not None:
        short_code = short_code.strip().upper()
        if not _re.match(r'^[A-Z0-9]{3,5}$', short_code):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="short_code must be 3-5 uppercase alphanumeric characters.",
            )

    with conn.cursor() as cur:
        # Check org exists
        cur.execute(
            "SELECT organization_name FROM nss.organization WHERE organization_pk = %s AND is_active = TRUE",
            (str(organization_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )
        org_name = row[0]

        # ADMIN-BR-076: bound short-code edits to the actor's scope subtree.
        _require_org_in_scope(cur, user, organization_pk, "edit organizations")

        # Check uniqueness (the DB constraint handles this too, but nicer error)
        if short_code is not None:
            cur.execute(
                """
                SELECT organization_pk, organization_name FROM nss.organization
                WHERE short_code = %s AND organization_pk != %s AND is_active = TRUE
                """,
                (short_code, str(organization_pk)),
            )
            conflict = cur.fetchone()
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"short_code '{short_code}' is already assigned to {conflict[1]}.",
                )

        actor = user.actor_pk
        cur.execute(
            """
            UPDATE nss.organization
            SET short_code = %s, updated_at = NOW()
            WHERE organization_pk = %s
            """,
            (short_code, str(organization_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="organization", record_pk=str(organization_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Updated short_code to {short_code}")

    action = f"set to '{short_code}'" if short_code else "cleared"
    return {"message": f"Short code for {org_name} {action}.", "short_code": short_code}


# ── PATCH /organizations/{pk} ────────────────────────────────────────────

# ── Type-to-type parent hierarchy (ORG-BR-087 onward) ────────────────────
# Each org type can only have specific parent types — the frozen NSS
# Bye-Law hierarchy (docs/03_Solution/modules/organization/
# 04_organization_business_rules.md):
#   KENDRA is parent to ANCHALIKA_SANGHA/ZILLA_SANGHA/PATHA_CHAKRA/
#     PARIBARIK_SANGHA directly (and to MAHILA_SANGHA — see below).
#   ANCHALIKA_SANGHA/ZILLA_SANGHA are siblings under KENDRA only,
#     never nested under each other.
#   SAKHA_SANGHA/SAKHA_ASANA sit only under ANCHALIKA_SANGHA/ZILLA_SANGHA.
#   KUMARI_SANGHA/SEVAK_SANGHA sit only under SAKHA_SANGHA.
#   MAHILA_SANGHA is two-tier by parent, not by a separate type code:
#     parent=KENDRA is the single Kendra/Central Mahila Sangha;
#     parent=SAKHA_SANGHA is a local, per-Sakha Mahila Sangha. The
#     Bye-Law's central-supervises-branches relationship is a
#     governance relationship, deliberately NOT encoded here.
#   PARIBARIK_ASANA (Gruhasana) is conceptually attached to a
#     sangha_sevi, not to an org — parent=SAKHA_SANGHA is a proxy
#     for "that sangha_sevi's current Sakha", not a literal org edge.
# Module-level (not local to create_organization) so update_organization's
# parent-reassignment (below) enforces the exact same rule rather than
# duplicating it.
_ALLOWED_PARENT_TYPES = {
    "ANCHALIKA_SANGHA": {"KENDRA"},
    "ZILLA_SANGHA": {"KENDRA"},
    "PATHA_CHAKRA": {"KENDRA"},
    "PARIBARIK_SANGHA": {"KENDRA"},
    "SAKHA_SANGHA": {"ANCHALIKA_SANGHA", "ZILLA_SANGHA"},
    "SAKHA_ASANA": {"ANCHALIKA_SANGHA", "ZILLA_SANGHA"},
    "KUMARI_SANGHA": {"SAKHA_SANGHA"},
    "SEVAK_SANGHA": {"SAKHA_SANGHA"},
    "MAHILA_SANGHA": {"KENDRA", "SAKHA_SANGHA"},
    "PARIBARIK_ASANA": {"SAKHA_SANGHA"},
}

# ORG-BR-099 (narrowed 2026-09-28): these 3 types may never carry a physical
# premises address. Module-level — used by both update_organization's and
# create_organization's guards, and previously duplicated identically in
# each (a real gap the "shared helper" rule below is meant to catch).
_NO_ADDRESS_TYPES = {"ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA"}

# ORG-BR-101/102: the two "wing" types a Sakha's own NSS_ERP_SAKHA_ADMIN may
# also create/preview for their own Sakha, in addition to NSS_ERP_ADMIN.
# Module-level — shared by create_organization and the next-code preview
# endpoint (previously duplicated identically in each).
_SAKHA_GATED_TYPES = {"KUMARI_SANGHA", "SEVAK_SANGHA"}


class UpdateOrganizationRequest(BaseModel):
    """PATCH /api/v1/admin/organizations/{organization_pk}"""
    organization_name: str | None = Field(None, max_length=200)
    address_line_1: str | None = Field(None, max_length=200)
    address_line_2: str | None = Field(None, max_length=200)
    phone_number: str | None = Field(None, max_length=20)
    country_phone_code: str | None = Field(None, max_length=10)
    mobile_number: str | None = Field(None, max_length=20)
    org_email: str | None = Field(None, max_length=254)
    org_website_url: str | None = Field(None, max_length=500)
    org_youtube_channel_url: str | None = Field(None, max_length=500)
    # Location FK fields
    country_pk: str | None = Field(None)
    state_pk: str | None = Field(None)
    district_pk: str | None = Field(None)
    city_village_pk: str | None = Field(None)
    postal_code_pk: str | None = Field(None)
    # Postal code as text (lookup/create against Foundation table)
    postal_code_value: str | None = Field(
        None, max_length=20,
        description="PIN code as text — lookup/create against Foundation table",
    )
    # City/Village as text (lookup/create against Foundation table)
    city_village_name: str | None = Field(None, max_length=200)
    # Re-parent this organization (e.g. assigning a Sakha Sangha to its
    # Anchalika/Zilla Sangha). Validated against _ALLOWED_PARENT_TYPES,
    # same rule create_organization enforces at creation time.
    parent_organization_pk: str | None = Field(
        None, description="UUID of the new parent organization"
    )


@router.patch("/organizations/{organization_pk}")
def update_organization(
    organization_pk: UUID,
    body: UpdateOrganizationRequest,
    user: UserContext = Depends(
        require_any_permission("ORGANIZATION_MANAGE", "ORGANIZATION_VIEW")
    ),
    conn=Depends(get_write_connection),
):
    """
    Update editable fields of an organization.

    Access rules (ADMIN-BR-076/077 — subtree-aware):
      - NSS_ERP_ADMIN / NSS-WIDE: the sole blanket authority — edits any org.
      - Any scoped admin (KENDRA/ANCHALIKA/ZILLA/SAKHA), regardless of whether
        they hold ORGANIZATION_MANAGE or only ORGANIZATION_VIEW, edits only
        organizations inside their scope subtree (their org + descendants).
        Permission alone never confers global reach.

    Editable fields: organization_name, address_line_1, address_line_2,
    phone_number, mobile_number, org_email, org_website_url,
    org_youtube_channel_url, country/state/district/city/postal-code
    location fields, and parent_organization_pk (re-parenting — e.g.
    assigning a Sakha Sangha to its Anchalika/Zilla Sangha, validated
    against _ALLOWED_PARENT_TYPES).
    """

    # ── Scope check (subtree-aware; global only for NSS_ERP_ADMIN) ──
    with conn.cursor() as cur:
        _require_org_in_scope(cur, user, organization_pk, "edit organizations")

    # Build dynamic SET clause from provided fields
    updates = {}
    if body.organization_name is not None:
        updates["organization_name"] = body.organization_name.strip()
    if body.address_line_1 is not None:
        updates["address_line_1"] = body.address_line_1.strip() or None
    if body.address_line_2 is not None:
        updates["address_line_2"] = body.address_line_2.strip() or None
    if body.phone_number is not None:
        updates["phone_number"] = body.phone_number.strip() or None
    if body.country_phone_code is not None:
        updates["country_phone_code"] = body.country_phone_code.strip() or None
    if body.mobile_number is not None:
        updates["mobile_number"] = body.mobile_number.strip() or None
    if body.org_email is not None:
        updates["org_email"] = body.org_email.strip() or None
        validate_email(updates["org_email"])  # MBR-CONTACT-02
    if body.org_website_url is not None:
        updates["org_website_url"] = body.org_website_url.strip() or None
    if body.org_youtube_channel_url is not None:
        updates["org_youtube_channel_url"] = body.org_youtube_channel_url.strip() or None

    # MBR-CONTACT-01: validate the EFFECTIVE org mobile (country-wise). Partial
    # PATCH — merge incoming code/number over the stored row before checking.
    if "mobile_number" in updates or "country_phone_code" in updates:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT country_phone_code, mobile_number FROM nss.organization WHERE organization_pk = %s",
                (str(organization_pk),),
            )
            cur_contact = cur.fetchone() or (None, None)
        eff_code = updates.get("country_phone_code") if "country_phone_code" in updates else cur_contact[0]
        eff_mobile = updates.get("mobile_number") if "mobile_number" in updates else cur_contact[1]
        validate_mobile(eff_code, eff_mobile)

    # Location FK fields — empty string means clear (set to NULL)
    for fk_field in ("country_pk", "state_pk", "district_pk", "city_village_pk", "postal_code_pk"):
        val = getattr(body, fk_field, None)
        if val is not None:
            updates[fk_field] = val.strip() if val.strip() else None

    # City/Village text — lookup/create against nss.city_village
    # Resolves to city_village_pk for storage in organization
    city_village_name_val = None
    if body.city_village_name is not None:
        city_village_name_val = body.city_village_name.strip() or None

    if (
        not updates and city_village_name_val is None
        and body.city_village_name is None and body.postal_code_value is None
        and body.parent_organization_pk is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No fields provided to update.",
        )

    with conn.cursor() as cur:
        # Check org exists (fetch type code too, for the ORG-BR-099 guard below)
        cur.execute(
            """
            SELECT o.organization_name, md.value_code
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.organization_pk = %s AND o.is_active = TRUE
            """,
            (str(organization_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )
        org_type_code = row[1]

        # ── Physical premises address prohibited for non-physical types
        # (ORG-BR-099, narrowed 2026-09-28) — clean 422 mirror of
        # trg_enforce_organization_address_restriction. country_pk/
        # state_pk/district_pk are jurisdiction, not premises, and stay
        # allowed for every type (handled via the FK-fields loop above).
        # _NO_ADDRESS_TYPES is module-level — see its definition above.
        if org_type_code in _NO_ADDRESS_TYPES and (
            updates.get("address_line_1") or updates.get("address_line_2")
            or body.city_village_name or body.postal_code_value
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"'{org_type_code}' may never carry a physical premises address (ORG-BR-099).",
            )

        # ── Re-parent (e.g. assigning a Sakha Sangha to its Anchalika/
        # Zilla Sangha) — same _ALLOWED_PARENT_TYPES rule create_organization
        # enforces at creation time (ORG-BR-087 onward). ─────────────────
        if body.parent_organization_pk is not None:
            new_parent_pk = body.parent_organization_pk.strip() or None
            allowed_parents = _ALLOWED_PARENT_TYPES.get(org_type_code)
            if not allowed_parents:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"'{org_type_code}' organizations cannot be re-parented through this endpoint.",
                )
            if not new_parent_pk:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"'{org_type_code}' requires a parent organization of type "
                           f"{', '.join(sorted(allowed_parents))}.",
                )
            if new_parent_pk == str(organization_pk):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="An organization cannot be its own parent.",
                )
            cur.execute(
                """
                SELECT md.value_code
                FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE o.organization_pk = %s AND o.is_active = TRUE
                """,
                (new_parent_pk,),
            )
            parent_row = cur.fetchone()
            if parent_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent organization not found.",
                )
            if parent_row[0] not in allowed_parents:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"'{org_type_code}' can only have parent of type "
                           f"{', '.join(sorted(allowed_parents))}. Got '{parent_row[0]}'.",
                )
            updates["parent_organization_pk"] = new_parent_pk

        actor = user.actor_pk

        # ── Postal code text → lookup/create → postal_code_pk ────────
        # Resolved BEFORE city_village (2026-10-21): the PIN disambiguates
        # the village lookup — village names repeat within a district, so
        # name+district alone can match several rows. No data dependency
        # blocks this reorder: each block falls back to the organization's
        # OWN existing district_pk/state_pk/country_pk independently, never
        # to a value the other block produces. See
        # resolve_or_create_city_village().
        if body.postal_code_value is not None:
            pc_val = body.postal_code_value.strip() if body.postal_code_value else None
            if not pc_val:
                # Empty string → clear postal_code_pk
                updates["postal_code_pk"] = None
            else:
                # Need state_pk and country_pk
                state_for_pc = updates.get("state_pk")
                country_for_pc = updates.get("country_pk")
                if not state_for_pc or not country_for_pc:
                    cur.execute(
                        "SELECT state_pk, country_pk FROM nss.organization WHERE organization_pk = %s",
                        (str(organization_pk),),
                    )
                    org_loc = cur.fetchone()
                    if not state_for_pc:
                        state_for_pc = str(org_loc[0]) if org_loc and org_loc[0] else None
                    if not country_for_pc:
                        country_for_pc = str(org_loc[1]) if org_loc and org_loc[1] else None

                if not state_for_pc or not country_for_pc:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="State and Country are required to set PIN Code.",
                    )

                updates["postal_code_pk"] = resolve_or_create_postal_code(
                    cur, pc_val, state_for_pc, country_for_pc, actor_pk=actor,
                )

        # ── City/Village text → lookup/create → city_village_pk ────────
        if body.city_village_name is not None:
            if city_village_name_val is None:
                # Empty string → clear city_village_pk
                updates["city_village_pk"] = None
            else:
                # Need district_pk to look up / create
                district_for_cv = updates.get("district_pk")
                if not district_for_cv:
                    # Fetch current district from organization
                    cur.execute(
                        "SELECT district_pk FROM nss.organization WHERE organization_pk = %s",
                        (str(organization_pk),),
                    )
                    org_row = cur.fetchone()
                    district_for_cv = str(org_row[0]) if org_row and org_row[0] else None

                if not district_for_cv:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="District is required to set City/Village.",
                    )

                # Lookup/create city_village by name + district (+ PIN).
                # Prefer a PIN just resolved above; otherwise fall back to
                # the organization's OWN existing postal_code_pk (mirrors
                # the district_for_cv fallback above) — an admin renaming
                # city_village_name without touching postal_code_value
                # must not lose PIN disambiguation.
                postal_code_for_cv = updates.get("postal_code_pk")
                if postal_code_for_cv is None and "postal_code_pk" not in updates:
                    cur.execute(
                        "SELECT postal_code_pk FROM nss.organization WHERE organization_pk = %s",
                        (str(organization_pk),),
                    )
                    org_pc_row = cur.fetchone()
                    postal_code_for_cv = str(org_pc_row[0]) if org_pc_row and org_pc_row[0] else None

                updates["city_village_pk"] = resolve_or_create_city_village(
                    cur, city_village_name_val, district_for_cv, actor_pk=actor,
                    postal_code_pk=postal_code_for_cv,
                )

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No fields provided to update.",
            )

        # Build SET clause
        set_parts = ["updated_at = NOW()"]
        params: list = []
        for col, val in updates.items():
            set_parts.append(f"{col} = %s")
            params.append(val)
        params.append(str(organization_pk))

        cur.execute(
            f"UPDATE nss.organization SET {', '.join(set_parts)} WHERE organization_pk = %s",
            params,
        )
        log_audit(cur, action="UPDATE", table_name="organization", record_pk=str(organization_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary="Updated organization details")

    return {
        "message": f"Organization updated successfully.",
        "updated_fields": list(updates.keys()),
    }


# ── POST /organizations ────────────────────────────────────────────────────

# ── Organization-type → id_sequence_master mapping ────────────────────────
# Multi-instance org types each draw their system business ID
# (organization.organization_id) from a type-specific id_sequence_master
# row. Unique apex types (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA) are not
# listed — they are singletons and carry no sequence-based ID. Module-level
# so both create_organization (which mints via next_id) and the read-only
# next-code preview endpoint (which peeks via peek_next_id) share one map.
_TYPE_TO_SEQUENCE = {
    "ANCHALIKA_SANGHA": "ANCHALIKA",
    "ZILLA_SANGHA": "ZILLA",
    "SAKHA_SANGHA": "SAKHA",
    "SAKHA_ASANA": "SAKHA_ASANA",
    "PATHA_CHAKRA": "PATHA_CHAKRA",
    "PARIBARIK_ASANA": "PARIBARIK_ASANA",
    "PARIBARIK_SANGHA": "PARIBARIK_SANGHA",
    "KUMARI_SANGHA": "KUMARI_SANGHA",
    "SEVAK_SANGHA": "SEVAK_SANGHA",
    "MAHILA_SANGHA": "MAHILA_SANGHA",
}


class CreateOrganizationRequest(BaseModel):
    """POST /api/v1/admin/organizations"""
    organization_name: str = Field(..., min_length=1, max_length=200)
    organization_type_code: str = Field(
        ..., description="value_code from master_data (ORGANIZATION_TYPE category)"
    )
    parent_organization_pk: str | None = Field(
        None, description="UUID of parent organization"
    )
    organization_code: str | None = Field(None, max_length=20)
    short_code: str | None = Field(None, max_length=10)
    address_line_1: str | None = Field(None, max_length=200)
    country_pk: str | None = Field(None)
    state_pk: str | None = Field(None)
    district_pk: str | None = Field(None)
    city_village_name: str | None = Field(
        None, max_length=200,
        description="City/village name — lookup/create against Foundation table",
    )
    postal_code_pk: str | None = Field(None)
    postal_code_value: str | None = Field(
        None, max_length=20,
        description="PIN code as text — lookup/create against Foundation table",
    )
    phone_number: str | None = Field(None, max_length=20)
    country_phone_code: str | None = Field(None, max_length=10)
    mobile_number: str | None = Field(None, max_length=20)
    org_email: str | None = Field(None, max_length=254)
    org_website_url: str | None = Field(None, max_length=500)
    org_youtube_channel_url: str | None = Field(None, max_length=500)
    has_own_premises: bool = Field(
        False,
        description="ORG-BR-098: only meaningful for SAKHA_SANGHA. FALSE is the "
                     "day-to-day 'Sakha Asana' case — never a distinct stored type.",
    )


@router.post("/organizations", status_code=201)
def create_organization(
    body: CreateOrganizationRequest,
    # Bug fix: gating on ADMIN_USER_MANAGE alone made this endpoint's own
    # Sakha-admin exception (below, for KUMARI_SANGHA/SEVAK_SANGHA per
    # ORG-BR-101) unreachable, since NSS_ERP_SAKHA_ADMIN only holds
    # PERSON_MANAGE (see database/seed/00_bootstrap/03_role_permission.sql).
    # Matches the require_any_permission gate on the ORG-BR-103 sibling
    # endpoint create_sangha_sevi. The is_nss_admin / _SAKHA_GATED_TYPES
    # check below still enforces NSS_ERP_ADMIN-only for every other type.
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_write_connection),
):
    """
    Create a new organization.

    Requires: ADMIN_USER_MANAGE permission + NSS_ERP_ADMIN role for most
    types; KUMARI_SANGHA/SEVAK_SANGHA may also be created by the target
    Sakha's own NSS_ERP_SAKHA_ADMIN (PERSON_MANAGE), per ORG-BR-101/102.
    Resolves organization_type_code → master_data_pk.
    Handles city_village_name lookup/create.
    Auto-generates organization_code if not provided. KUMARI_SANGHA/
    SEVAK_SANGHA instead inherit all location/contact detail from their
    parent Sakha and carry no organization_code / short_code of their own
    (see the wing block below).
    """

    # ── NSS_ERP_ADMIN gate ──────────────────────────────────────────
    # KUMARI_SANGHA/SEVAK_SANGHA are the one exception (ORG-BR-101): the
    # Sakha's own NSS_ERP_SAKHA_ADMIN may also create these two types for
    # a Sakha within their own admin_scope. resolve_kumari_sevak_parent_sakha
    # (called below, inside the cursor block) enforces that authority and
    # resolves/locks the parent Sakha; every other type stays NSS_ERP_ADMIN-only.
    is_nss_admin = user.is_super_admin()
    # _SAKHA_GATED_TYPES is module-level — see its definition above.
    if not is_nss_admin and body.organization_type_code not in _SAKHA_GATED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only NSS_ERP_ADMIN can create organizations.",
        )

    with conn.cursor() as cur:

        # ── Creatable-type whitelist (ORG-BR-096/097/101) ───────────
        # Through the standard Create Organization flow, only these
        # four types may be created directly by NSS_ERP_ADMIN.
        # PARIBARIK_SANGHA is additionally gated to NSS_ERP_KENDRA_ADMIN
        # (ORG-BR-097). KUMARI_SANGHA/SEVAK_SANGHA are creatable by
        # NSS_ERP_ADMIN *or* the target Sakha's own NSS_ERP_SAKHA_ADMIN
        # (ORG-BR-101) — handled separately below via
        # resolve_kumari_sevak_parent_sakha, which also resolves/locks
        # the parent Sakha (ORG-BR-102).
        # Everything else (SAKHA_ASANA, MAHILA_SANGHA, PARIBARIK_ASANA,
        # and the 3 unique apex types) is never created through this
        # endpoint — auto-created or a pre-existing singleton.
        _STANDARD_CREATABLE_TYPES = {
            "ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA", "SAKHA_SANGHA",
        }
        if body.organization_type_code == "PARIBARIK_SANGHA":
            is_kendra_admin = any(
                s.role_code == "NSS_ERP_KENDRA_ADMIN" for s in user.scopes
            )
            if not is_kendra_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only NSS_ERP_KENDRA_ADMIN can create a Paribarik Sangha.",
                )
        elif body.organization_type_code in _SAKHA_GATED_TYPES:
            # Resolves/locks parent_organization_pk per ORG-BR-101/102 and
            # enforces that a Sakha admin only acts within their own scope.
            body.parent_organization_pk = resolve_kumari_sevak_parent_sakha(
                cur,
                user=user,
                organization_type_code=body.organization_type_code,
                requested_parent_pk=body.parent_organization_pk,
            )
        elif body.organization_type_code not in _STANDARD_CREATABLE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"'{body.organization_type_code}' is not creatable through the "
                    f"standard Create Organization flow (ORG-BR-096)."
                ),
            )

        # ── Block unique types that already exist ──────────────────
        _UNIQUE_TYPES = {"KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA"}
        if body.organization_type_code in _UNIQUE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Organization type '{body.organization_type_code}' is unique and already exists. Cannot create another.",
            )

        # ── Physical premises address prohibited for non-physical types
        # (ORG-BR-099, narrowed 2026-09-28) ──────────────────────────
        # Clean 422 mirror of trg_enforce_organization_address_restriction.
        # country_pk/state_pk/district_pk are administrative jurisdiction,
        # not a physical premises, and are allowed for every type.
        # _NO_ADDRESS_TYPES is module-level — see its definition above.
        if body.organization_type_code in _NO_ADDRESS_TYPES and any([
            body.address_line_1, body.city_village_name,
            body.postal_code_pk, body.postal_code_value,
        ]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"'{body.organization_type_code}' may never carry a physical "
                    f"premises address (ORG-BR-099)."
                ),
            )

        # ── Jurisdiction (country/state/district) mandatory for these
        # same 3 types — they have no premises, but every Anchalika/Zilla/
        # Patha Chakra does administer a specific state/district, and that
        # jurisdiction has to be recorded at creation time.
        if body.organization_type_code in _NO_ADDRESS_TYPES and not (
            body.country_pk and body.state_pk and body.district_pk
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"'{body.organization_type_code}' requires country, state, "
                    f"and district (its administrative jurisdiction)."
                ),
            )

        # ── Hierarchical parent validation (ORG-BR-087 onward) ──────
        # _ALLOWED_PARENT_TYPES is module-level — see its definition
        # above update_organization for the full rule breakdown.
        # ── Parent org instance auto-resolution (ORG-BR-100) ─────────
        # ANCHALIKA_SANGHA/ZILLA_SANGHA/PATHA_CHAKRA have exactly one
        # legal parent TYPE (KENDRA) and, today, exactly one legal
        # parent INSTANCE (the single Kendra row) — so if the client
        # didn't supply parent_organization_pk, resolve and lock it
        # here rather than making the user pick from a one-item list.
        # Does NOT extend to KUMARI_SANGHA/SEVAK_SANGHA: their parent
        # type (SAKHA_SANGHA) is singular but multiple Sakha instances
        # exist, so the admin must still pick which Sakha manually.
        _AUTO_RESOLVE_SINGLE_INSTANCE_PARENT_TYPES = {
            "ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA",
        }
        if (
            body.organization_type_code in _AUTO_RESOLVE_SINGLE_INSTANCE_PARENT_TYPES
            and not body.parent_organization_pk
        ):
            kendra_pk = get_kendra_organization_pk(cur)
            if kendra_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Cannot auto-resolve parent Kendra: no active KENDRA "
                        "organization exists (ORG-BR-100)."
                    ),
                )
            body.parent_organization_pk = kendra_pk

        allowed_parents = _ALLOWED_PARENT_TYPES.get(body.organization_type_code)

        if allowed_parents and body.parent_organization_pk:
            # Validate parent org type
            cur.execute(
                """
                SELECT md.value_code
                FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE o.organization_pk = %s AND o.is_active = TRUE
                """,
                (body.parent_organization_pk,),
            )
            parent_type_row = cur.fetchone()
            if parent_type_row and parent_type_row[0] not in allowed_parents:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"'{body.organization_type_code}' can only have parent of type "
                        f"{', '.join(sorted(allowed_parents))}. Got '{parent_type_row[0]}'."
                    ),
                )
        elif allowed_parents and not body.parent_organization_pk:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"'{body.organization_type_code}' requires a parent organization of type "
                    f"{', '.join(sorted(allowed_parents))}."
                ),
            )

        # ── Resolve organization_type_code → master_data_pk ─────────
        cur.execute(
            """
            SELECT md.master_data_pk
            FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'ORGANIZATION_TYPE'
              AND md.value_code = %s
              AND md.is_active = TRUE
            LIMIT 1
            """,
            (body.organization_type_code,),
        )
        type_row = cur.fetchone()
        if type_row is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown organization type: {body.organization_type_code}",
            )
        org_type_pk = str(type_row[0])

        # ── Resolve ACTIVE status master_data_pk ────────────────────
        active_status_pk = get_active_status_pk(cur)

        # ── Validate parent org if provided ─────────────────────────
        if body.parent_organization_pk:
            cur.execute(
                "SELECT organization_pk FROM nss.organization WHERE organization_pk = %s AND is_active = TRUE",
                (body.parent_organization_pk,),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent organization not found.",
                )

        # ── Kumari/Sevak wings inherit identity + detail from parent ─
        # A KUMARI_SANGHA/SEVAK_SANGHA is not an independently-located
        # body: it operates from its parent Sakha's premises and shares
        # the Sakha's identity (ORG-BR-092/104, and the wing-membership-
        # shares-the-Sakha's-IDs convention, MBR-046). So its location/
        # contact detail is inherited wholesale from the parent Sakha, and
        # it carries NO organization_code / short_code of its own (the
        # parent Sakha already holds those). Any client-supplied code or
        # detail for these two types is ignored — org_code and short_code
        # are forced NULL below, and the detail is taken from the parent.
        wing_inherit = None
        if body.organization_type_code in _SAKHA_GATED_TYPES:
            cur.execute(
                """
                SELECT organization_code, address_line_1, country_pk, state_pk,
                       district_pk, city_village_pk, postal_code_pk, phone_number,
                       country_phone_code, mobile_number, org_email, org_website_url,
                       org_youtube_channel_url
                FROM nss.organization
                WHERE organization_pk = %s AND is_active = TRUE
                """,
                (body.parent_organization_pk,),
            )
            wing_inherit = cur.fetchone()
            if wing_inherit is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent Sakha not found.",
                )

        # ── organization_id / organization_code ─────────────────────
        # ORG-BR-105: the org-type sequence (id_sequence_master, keyed via
        # module-level _TYPE_TO_SEQUENCE) materialises as the visible
        # organization_code — this is the "org code" the operator sees, and
        # matches the established data convention (e.g. SAKHA → SKH1, SKH2…).
        # organization_id is a legacy identifier not minted through this
        # flow; it is left NULL (the dominant existing convention). Wings
        # (KUMARI/SEVAK) mint nothing here — they carry no code of their own
        # and share the parent Sakha's identity (ORG-BR-104).
        seq_code = _TYPE_TO_SEQUENCE.get(body.organization_type_code)
        actor = user.actor_pk
        org_id = None

        # ── organization_code ───────────────────────────────────────
        if wing_inherit is not None:
            # Wings (KUMARI_SANGHA/SEVAK_SANGHA, and the local per-Sakha
            # MAHILA_SANGHA once it becomes creatable) carry NO
            # organization_code and NO short_code of their own. They are part
            # of a Sakha Sangha, which already holds those identifiers, and a
            # wing shares the Sakha's identity rather than minting a separate
            # one (MBR-046, ORG-BR-104). Both are left NULL — the nullable
            # organization_code column and the partial short_code unique index
            # (WHERE short_code IS NOT NULL) both permit this.
            org_code = None
        elif body.organization_code:
            # Explicit override (API/admin). Honoured and uniqueness-checked;
            # the standard UI does not send this — it shows the auto-generated
            # sequence code as a read-only preview instead (ORG-BR-105).
            org_code = body.organization_code.strip().upper()
            cur.execute(
                "SELECT organization_pk FROM nss.organization WHERE organization_code = %s AND is_active = TRUE",
                (org_code,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Organization code '{org_code}' already exists.",
                )
        else:
            # ORG-BR-105: auto-generate the org code from the org-type
            # sequence (atomic next_id — the authoritative counterpart to the
            # form's non-consuming next-code preview). Materialising it here,
            # on submit, is the only point the sequence is actually consumed.
            org_code = next_id(cur, seq_code, actor_pk=actor) if seq_code else None

        # ── Short code uniqueness ────────────────────────────────────
        # Wings leave short_code unset (see wing note above).
        short_code = None
        if wing_inherit is None and body.short_code:
            short_code = body.short_code.strip().upper()
            cur.execute(
                "SELECT organization_pk FROM nss.organization WHERE short_code = %s AND is_active = TRUE",
                (short_code,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Short code '{short_code}' already exists.",
                )

        # ── Resolve inheritable location/contact insert values ──────
        # Wings take these wholesale from the parent Sakha (fetched into
        # wing_inherit above); every other type resolves them from the
        # request body (free-text city/village + postal are looked up or
        # created against the Foundation tables).
        if wing_inherit is not None:
            (_parent_code, ins_address_line_1, ins_country_pk, ins_state_pk,
             ins_district_pk, ins_city_village_pk, ins_postal_code_pk,
             ins_phone_number, ins_country_phone_code, ins_mobile_number, ins_org_email,
             ins_org_website_url, ins_org_youtube_channel_url) = wing_inherit
        else:
            # ── Resolve postal_code_value → postal_code_pk ──────────
            # Resolved BEFORE city_village (2026-10-21): the PIN
            # disambiguates the village lookup — village names repeat
            # within a district, so name+district alone can match
            # several rows. See resolve_or_create_city_village().
            resolved_postal_code_pk = body.postal_code_pk or None
            if body.postal_code_value and body.state_pk and body.country_pk:
                pc_val = body.postal_code_value.strip()
                if pc_val:
                    resolved_postal_code_pk = resolve_or_create_postal_code(
                        cur, pc_val, body.state_pk, body.country_pk, actor_pk=actor,
                    )

            # ── Resolve city_village_name → city_village_pk ─────────
            city_village_pk = None
            if body.city_village_name and body.district_pk:
                cv_name = body.city_village_name.strip()
                if cv_name:
                    city_village_pk = resolve_or_create_city_village(
                        cur, cv_name, body.district_pk, actor_pk=actor,
                        postal_code_pk=resolved_postal_code_pk,
                    )

            ins_address_line_1 = body.address_line_1.strip() if body.address_line_1 else None
            ins_country_pk = body.country_pk or None
            ins_state_pk = body.state_pk or None
            ins_district_pk = body.district_pk or None
            ins_city_village_pk = city_village_pk
            ins_postal_code_pk = resolved_postal_code_pk
            ins_phone_number = body.phone_number.strip() if body.phone_number else None
            ins_country_phone_code = body.country_phone_code.strip() if body.country_phone_code else None
            ins_mobile_number = body.mobile_number.strip() if body.mobile_number else None
            ins_org_email = body.org_email.strip() if body.org_email else None
            validate_email(ins_org_email)  # MBR-CONTACT-02
            validate_mobile(ins_country_phone_code, ins_mobile_number)  # MBR-CONTACT-01
            ins_org_website_url = body.org_website_url.strip() if body.org_website_url else None
            ins_org_youtube_channel_url = body.org_youtube_channel_url.strip() if body.org_youtube_channel_url else None

        # ── INSERT organization ──────────────────────────────────────
        cur.execute(
            """
            INSERT INTO nss.organization (
                organization_id,
                organization_name,
                organization_type_master_data_pk,
                status_master_data_pk,
                parent_organization_pk,
                organization_code,
                short_code,
                address_line_1,
                country_pk,
                state_pk,
                district_pk,
                city_village_pk,
                postal_code_pk,
                has_own_premises,
                phone_number,
                country_phone_code,
                mobile_number,
                org_email,
                org_website_url,
                org_youtube_channel_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING organization_pk
            """,
            (
                org_id,
                body.organization_name.strip(),
                org_type_pk,
                active_status_pk,
                body.parent_organization_pk or None,
                org_code,
                short_code,
                ins_address_line_1,
                ins_country_pk,
                ins_state_pk,
                ins_district_pk,
                ins_city_village_pk,
                ins_postal_code_pk,
                # ORG-BR-098: only meaningful for SAKHA_SANGHA; harmless
                # (ignored) FALSE default for every other org type.
                bool(body.has_own_premises),
                ins_phone_number,
                ins_country_phone_code,
                ins_mobile_number,
                ins_org_email,
                ins_org_website_url,
                ins_org_youtube_channel_url,
            ),
        )
        new_org_pk = cur.fetchone()[0]
        log_audit(cur, action="CREATE", table_name="organization", record_pk=str(new_org_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="admin", summary=f"Created organization {body.organization_name}")

        # ── Auto-create the mandatory Sakha Governing Body (GOV-BR-059) ──
        # Every Sakha Sangha must have exactly one Sakha Governing Body.
        # Created here, same transaction, so the body never has to be
        # manually created for a new Sakha. Mirrors governance.py's
        # create_body() INSERT shape (body_status/effective_from
        # defaults, no end date, description NULL).
        if body.organization_type_code == "SAKHA_SANGHA":
            cur.execute(
                """
                SELECT body_type_master_pk FROM nss.body_type_master
                WHERE body_type_code = 'SAKHA_GOVERNING_BODY' AND is_active = TRUE
                """
            )
            sgb_type_row = cur.fetchone()
            if sgb_type_row is not None:
                sgb_body_code = f"{org_code}_GOVERNING_BODY" if org_code else f"SGB_{new_org_pk}"
                cur.execute(
                    """
                    INSERT INTO nss.body_master (
                        body_type_master_pk, body_code, body_name, description,
                        organization_pk, body_status, effective_from, effective_to
                    ) VALUES (%s, %s, %s, NULL, %s, 'ACTIVE', %s, NULL)
                    RETURNING body_master_pk
                    """,
                    (str(sgb_type_row[0]), sgb_body_code,
                     f"{body.organization_name.strip()} Governing Body",
                     str(new_org_pk), date.today()),
                )
                sgb_pk = cur.fetchone()[0]
                log_audit(cur, action="CREATE", table_name="body_master", record_pk=str(sgb_pk),
                          actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                          module="governance",
                          summary=f"Auto-created Sakha Governing Body for {body.organization_name}")

    return {
        "organization_pk": str(new_org_pk),
        "organization_id": org_id,
        "organization_code": org_code,
        "organization_name": body.organization_name.strip(),
        "message": f"Organization '{body.organization_name.strip()}' created successfully.",
    }


# ── GET /organizations/next-code ──────────────────────────────────────────

@router.get("/organizations/next-code")
def preview_next_organization_code(
    organization_type_code: str = Query(
        ..., description="value_code from master_data (ORGANIZATION_TYPE category)"
    ),
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_MANAGE", "PERSON_MANAGE")
    ),
    conn=Depends(get_connection),
):
    """
    Preview the organization_code that create_organization WOULD mint for
    *organization_type_code*, without consuming the sequence (ORG-BR-105).

    The Create Organization form calls this when a non-wing type is selected
    to show the auto-generated code live ("this is what the code will be if
    you submit"). The value is advisory only — it is peeked, never minted, so
    it does not burn a number and a concurrent create may shift the real value.
    The authoritative code is assigned solely on POST /organizations.

    Returns ``next_code = null`` for:
      • wing types (KUMARI_SANGHA/SEVAK_SANGHA) — they carry no code of their
        own, inheriting the parent Sakha's identity (ORG-BR-104); and
      • any type with no id_sequence_master sequence.
    """
    # _SAKHA_GATED_TYPES is module-level — see its definition above.
    if organization_type_code in _SAKHA_GATED_TYPES:
        return {
            "organization_type_code": organization_type_code,
            "sequence_code": None,
            "next_code": None,
        }
    seq_code = _TYPE_TO_SEQUENCE.get(organization_type_code)
    next_code = None
    if seq_code:
        with conn.cursor() as cur:
            next_code = peek_next_id(cur, seq_code)
    return {
        "organization_type_code": organization_type_code,
        "sequence_code": seq_code,
        "next_code": next_code,
    }


# ── GET /dashboard-stats ──────────────────────────────────────────────────

@router.get("/dashboard-stats")
def dashboard_stats(
    org_pk: str | None = Query(
        None,
        description=(
            "Scope the stats to this organization's subtree instead of the "
            "actor's full combined scope. Lets the member Dashboard request "
            "one call per admin tab so a dual-role admin (e.g. NSS-WIDE "
            "Kendra admin + Sakha-scoped admin) gets distinct numbers per "
            "tab instead of the same actor-wide union on every tab. Must "
            "fall within the actor's own scope (ADMIN-BR-076); omit for the "
            "legacy actor-wide behavior."
        ),
    ),
    user: UserContext = Depends(
        require_any_permission("ADMIN_USER_VIEW", "ADMIN_USER_MANAGE", "MEMBERSHIP_APPROVE")
    ),
    conn=Depends(get_connection),
):
    """
    Aggregate stats for the admin dashboard cards.

    Returns per-role stats scoped to the admin's organization(s).
    NSS-WIDE admins see totals across all orgs; org-scoped admins
    see only their scoped orgs. Pass *org_pk* to scope to one specific
    organization's subtree (e.g. one admin tab's own scope row) rather than
    the actor's combined scope across every role they hold.
    """
    with conn.cursor() as cur:
        if org_pk is not None:
            # Single-tab scoping: validate org_pk is actually within this
            # actor's reach, then compute totals for JUST that org's
            # subtree — not the actor's full union — so two tabs backed by
            # two different scope rows get two different answers.
            _require_org_in_scope(cur, user, org_pk, "view dashboard stats")
            allowed = _org_subtree_pks(cur, org_pk)
            is_nss_wide = False
        else:
            # Determine scoped org PKs (None = all orgs / NSS-WIDE), subtree-aware.
            allowed = _actor_scope_org_pks(cur, user)
            is_nss_wide = allowed is None

        if not is_nss_wide and not allowed:
            # An admin whose scope resolves to zero orgs genuinely has zero of
            # everything — except attendance, which is not "0", it is untracked.
            return {
                "members": 0,
                "families": 0,
                "renewals_due": 0,
                "anchalika_sanghas": 0,
                "zilla_sanghas": 0,
                "patha_chakras": 0,
                "paribarik_sanghas": 0,
                "sakha_sanghas": 0,
                "mahila_sanghas": 0,
                "attendance_pct": None,
                "attendance_tracked": False,
            }
        scoped_org_pks = None if is_nss_wide else list(allowed)

        # Pre-compute placeholders for scoped queries
        placeholders = (
            ",".join(["%s"] * len(scoped_org_pks))
            if scoped_org_pks else ""
        )

        # ── Active members count ──
        # HOME membership only: active sangha_sevi whose home org (ss.organization_pk)
        # is in scope. Deliberately NOT affiliation-based — a membership_sakha_affiliation
        # join also pulls in Parichay Patra holders whose HOME is a different Sakha but
        # who attend here as cross-Sakha Darshaks (SOL-MEM-006), so on any multi-Sakha
        # rollup the same person is counted once at their home Sakha AND again at every
        # Sakha they visit, inflating the figure. Home scoping counts each member exactly
        # once and keeps this card consistent with the dedicated Kendra dashboard
        # (/organizations/{pk}/stats member_count), which scopes the same way.
        # The reserved system account (is_system_account = TRUE, MBR-038A — e.g.
        # nssadmin) is NOT a real member and is excluded from both scopes, so it
        # never inflates the count on the NSS-wide rollup where no org filter
        # would otherwise exclude it.
        if is_nss_wide:
            cur.execute("""
                SELECT COUNT(DISTINCT ss.sangha_sevi_pk)
                FROM nss.sangha_sevi ss
                WHERE ss.is_active = TRUE
                  AND ss.is_system_account = FALSE
            """)
        else:
            cur.execute(f"""
                SELECT COUNT(DISTINCT ss.sangha_sevi_pk)
                FROM nss.sangha_sevi ss
                WHERE ss.is_active = TRUE
                  AND ss.is_system_account = FALSE
                  AND ss.organization_pk IN ({placeholders})
            """, scoped_org_pks)
        members = cur.fetchone()[0]

        # ── Families count ──
        # Count active family_group records scoped by sakha_organization_pk
        if is_nss_wide:
            cur.execute("""
                SELECT COUNT(*)
                FROM nss.family_group fg
                WHERE fg.is_active = TRUE
            """)
        else:
            cur.execute(f"""
                SELECT COUNT(*)
                FROM nss.family_group fg
                WHERE fg.is_active = TRUE
                  AND fg.sakha_organization_pk IN ({placeholders})
            """, scoped_org_pks)
        families = cur.fetchone()[0]

        # ── Renewals due ──
        # Real query against nss.membership_renewal_request. No API route
        # writes to this table yet (the renewal module is unbuilt), so today
        # this legitimately returns 0 — but it is a genuine COUNT, so the card
        # starts showing real figures the moment rows land in the table,
        # instead of being a literal that could never change.
        if is_nss_wide:
            cur.execute("""
                SELECT COUNT(*)
                FROM nss.membership_renewal_request rr
                JOIN nss.sangha_sevi ss
                     ON ss.sangha_sevi_pk = rr.sangha_sevi_pk
                WHERE rr.status = 'PENDING'
                  AND ss.is_active = TRUE
            """)
        else:
            cur.execute(f"""
                SELECT COUNT(*)
                FROM nss.membership_renewal_request rr
                JOIN nss.sangha_sevi ss
                     ON ss.sangha_sevi_pk = rr.sangha_sevi_pk
                WHERE rr.status = 'PENDING'
                  AND ss.is_active = TRUE
                  AND ss.organization_pk IN ({placeholders})
            """, scoped_org_pks)
        renewals_due = cur.fetchone()[0]

        # ── Organization counts ──
        # One pass, several numbers. The dashboard cards previously bound a
        # single "Total Organizations" label to whatever unrelated value
        # happened to be spare — meaningless, since NSS (Kendra) is the one
        # apex org and everything else is a child of it. Instead, break out
        # each Kendra-child tier that isn't already its own card: Anchalika
        # Sangha, Zilla Sangha, Patha Chakra, and Paribarik Sangha (the
        # family organisation attached to Kendra per the Bye-Law Preamble —
        # ORGANIZATION_TYPE value PARIBARIK_SANGHA). Sakha Sangha's parent is
        # an Anchalika/Zilla, not Kendra directly, so it stays the separate
        # sakha_sanghas count that already existed; mahila_sanghas likewise
        # unchanged.
        org_count_sql = """
            SELECT COUNT(*) FILTER (WHERE ot.value_code = 'ANCHALIKA_SANGHA'
                                       AND pt.value_code = 'KENDRA'),
                   COUNT(*) FILTER (WHERE ot.value_code = 'ZILLA_SANGHA'
                                       AND pt.value_code = 'KENDRA'),
                   COUNT(*) FILTER (WHERE ot.value_code = 'PATHA_CHAKRA'
                                       AND pt.value_code = 'KENDRA'),
                   COUNT(*) FILTER (WHERE ot.value_code = 'PARIBARIK_SANGHA'
                                       AND pt.value_code = 'KENDRA'),
                   COUNT(*) FILTER (WHERE ot.value_code = 'SAKHA_SANGHA'),
                   COUNT(*) FILTER (WHERE ot.value_code = 'MAHILA_SANGHA')
            FROM   nss.organization o
            JOIN   nss.master_data ot
                   ON ot.master_data_pk = o.organization_type_master_data_pk
            LEFT JOIN nss.organization p
                   ON p.organization_pk = o.parent_organization_pk
            LEFT JOIN nss.master_data pt
                   ON pt.master_data_pk = p.organization_type_master_data_pk
            WHERE  o.is_active = TRUE
        """
        if is_nss_wide:
            cur.execute(org_count_sql)
        else:
            cur.execute(
                org_count_sql + f" AND o.organization_pk IN ({placeholders})",
                scoped_org_pks,
            )
        (
            anchalika_sanghas,
            zilla_sanghas,
            patha_chakras,
            paribarik_sanghas,
            sakha_sanghas,
            mahila_sanghas,
        ) = cur.fetchone()

        # ── Attendance % (Tier 6, 2026-10-27) ──
        # Mirrors api/routers/attendance.py::organization_stats' own
        # present/(present+absent) computation (EXCUSED_ABSENCE excluded
        # from the denominator, ATT-008), aggregated across every Sakha in
        # scope instead of one org at a time. attendance_tracked is False
        # only when literally no Weekly Sangha Puja event has been
        # recorded yet in scope (pre-adoption) — once any event exists,
        # a real percentage (including 0%) is returned instead of "Not
        # tracked yet".
        att_sql = """
            SELECT COUNT(DISTINCT w.weekly_sangha_puja_pk),
                   COUNT(*) FILTER (WHERE md.value_code = 'PRESENT'),
                   COUNT(*) FILTER (WHERE md.value_code = 'ABSENT')
            FROM   nss.weekly_sangha_puja w
            LEFT JOIN nss.weekly_sangha_puja_attendance a
                   ON a.weekly_sangha_puja_pk = w.weekly_sangha_puja_pk AND a.is_active = TRUE
            LEFT JOIN nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            WHERE  w.is_active = TRUE
        """
        if is_nss_wide:
            cur.execute(att_sql)
        else:
            cur.execute(att_sql + f" AND w.sakha_pk IN ({placeholders})", scoped_org_pks)
        total_puja_events, att_present, att_absent = cur.fetchone()
        attendance_tracked = total_puja_events > 0
        att_denom = att_present + att_absent
        attendance_pct = round(att_present / att_denom * 100, 1) if att_denom else None

    return {
        "members": members,
        "families": families,
        "renewals_due": renewals_due,
        "anchalika_sanghas": anchalika_sanghas,
        "zilla_sanghas": zilla_sanghas,
        "patha_chakras": patha_chakras,
        "paribarik_sanghas": paribarik_sanghas,
        "sakha_sanghas": sakha_sanghas,
        "mahila_sanghas": mahila_sanghas,
        "attendance_pct": attendance_pct,
        "attendance_tracked": attendance_tracked,
    }


# ═══════════════════════════════════════════════════════════════
#  Patra number correction (MBR-030H)
# ═══════════════════════════════════════════════════════════════

_PATRA_TABLES = {
    "parichaya": ("parichaya_patra", "PARICHAYA_PATRA", "affiliated_organization_pk"),
    "anumati": ("anumati_patra", "ANUMATI_PATRA", "issuing_organization_pk"),
}


class CorrectPatraNumberRequest(BaseModel):
    document_number: str = Field(
        ..., max_length=30,
        description=(
            "Corrected Patra number. Either the bare number (e.g. 1) — the "
            "year is attached automatically — or the full number with its "
            "year (e.g. 1/2026/2027), which is verified against the Patra's "
            "issue date (MBR-030H)."
        ),
    )
    reason: str | None = Field(
        None, max_length=500,
        description="Why the number is being corrected (recorded in the audit log).",
    )


class CorrectPatraNumberResponse(BaseModel):
    patra_type: str
    patra_pk: str
    previous_document_number: str
    document_number: str


@router.patch(
    "/patra/{patra_type}/{patra_pk}/document-number",
    response_model=CorrectPatraNumberResponse,
)
def correct_patra_document_number(
    patra_type: str,
    patra_pk: UUID,
    body: CorrectPatraNumberRequest,
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_MANAGE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> CorrectPatraNumberResponse:
    """
    Correct the number on an already-issued Parichaya or Anumati Patra.

    MBR-030H (user decision, 2026-10-03). A supplied Patra number is trusted
    as typed at entry time, on the understanding that the approving admin
    verifies it and can fix it afterwards — this is that path. Before this
    existed, a mis-entered number was permanently immutable through the API.

    *patra_type* is "parichaya" or "anumati".

    The replacement number obeys the same entry rules as initial issuance: a
    bare number gets the correct year pair appended, and a number supplied
    with a year must match the Patra's own issue date. Admin only; every
    correction is audit-logged with the old and new value.

    Requires: MEMBERSHIP_MANAGE or ADMIN_USER_MANAGE, and the Patra's Sakha
    must fall inside the actor's scope (ADMIN-BR-076).
    """
    key = patra_type.strip().lower()
    if key not in _PATRA_TABLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="patra_type must be 'parichaya' or 'anumati'.",
        )
    table, card_type, org_column = _PATRA_TABLES[key]
    label = card_type.replace("_", " ").title()

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT document_number, issue_date, {org_column}, status
            FROM nss.{table}
            WHERE {table}_pk = %s
            """,
            (str(patra_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{label} not found.",
            )
        previous_document_number, issue_date, org_pk, patra_status = row

        # ADMIN-BR-076: only inside the actor's scope subtree.
        # parichaya_patra.affiliated_organization_pk is nullable (the card
        # snapshot may predate Sakha tracking); with no Sakha to scope
        # against, only a globally-authorized actor may correct it.
        if org_pk is not None:
            _require_org_in_scope(
                cur, user, str(org_pk), f"correct {label} numbers",
            )
        elif _actor_scope_org_pks(cur, user) is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This {label} has no Sakha recorded on it, so only an "
                    f"NSS-wide administrator can correct its number."
                ),
            )

        # Same normalization/validation as issuance — the year is checked
        # against this Patra's own issue_date, not today.
        new_document_number = normalize_patra_document_number(
            body.document_number, issue_date, card_type,
        )
        if not new_document_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"A {label} number is required.",
            )

        if new_document_number == previous_document_number:
            return CorrectPatraNumberResponse(
                patra_type=key,
                patra_pk=str(patra_pk),
                previous_document_number=previous_document_number,
                document_number=new_document_number,
            )

        actor = user.actor_pk
        cur.execute(f"SAVEPOINT {table}_correct")
        try:
            cur.execute(
                f"""
                UPDATE nss.{table}
                SET document_number = %s,
                    updated_at = NOW()
                WHERE {table}_pk = %s
                """,
                (new_document_number, str(patra_pk)),
            )
        except psycopg2.errors.UniqueViolation:
            cur.execute(f"ROLLBACK TO SAVEPOINT {table}_correct")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{label} number '{new_document_number}' is already in use.",
            )
        cur.execute(f"RELEASE SAVEPOINT {table}_correct")

        log_audit(
            cur, action="UPDATE", table_name=table, record_pk=str(patra_pk),
            actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
            module="admin",
            summary=(
                f"Corrected {label} number from "
                f"'{previous_document_number}' to '{new_document_number}'"
                f" (status {patra_status})"
                + (f" — {body.reason.strip()}" if body.reason and body.reason.strip() else "")
            ),
        )

    return CorrectPatraNumberResponse(
        patra_type=key,
        patra_pk=str(patra_pk),
        previous_document_number=previous_document_number,
        document_number=new_document_number,
    )


# ═══════════════════════════════════════════════════════════════
#  Member credential administration (MBR-010 / MBR-019B / MBR-030H)
#
#  One place for an admin to see every member's credential health,
#  read a member's full credential timeline, issue/renew the one
#  credential they should hold (optionally typing the Parichaya
#  number by hand when it was never auto-generated), and promote a
#  Darshaka to Regular — the only path that expires an Anumati Patra
#  and issues the Parichaya Patra in its place.
# ═══════════════════════════════════════════════════════════════

# Soft-warning window: an ACTIVE credential whose valid_to is within
# this many days of today is flagged EXPIRING (not yet LAPSED) on the
# credential-health table. Server-controlled constant — safe to inline
# into SQL.
_CREDENTIAL_EXPIRING_WINDOW_DAYS = 60


def _expected_card_type(membership_type_code: str | None) -> str:
    """
    The ONE credential a member of this type must hold (MBR-019B): a
    Darshaka (PROBATIONARY) carries an Anumati Patra, everyone else a
    Parichaya Patra. Deliberately identical to the branch
    issue_membership_credential() takes internally, so the admin view's
    "expected" column can never contradict what the issue endpoint mints.
    """
    return (
        "ANUMATI_PATRA"
        if membership_type_code == PROBATIONARY_MEMBERSHIP_TYPE_CODE
        else "PARICHAYA_PATRA"
    )


class CredentialMemberStateResponse(BaseModel):
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str | None
    membership_type_code: str
    membership_type_name: str
    organization_pk: UUID
    organization_name: str | None
    expected_card_type: str
    credential_state: str  # OK / EXPIRING / LAPSED / MISSING
    credential_document_number: str | None
    credential_valid_to: date | None


class CredentialMemberListResponse(BaseModel):
    members: list[CredentialMemberStateResponse]
    total: int
    page: int
    page_size: int


@router.get("/credentials/members", response_model=CredentialMemberListResponse)
def list_member_credential_state(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    state: str | None = Query(
        None,
        description="Filter by credential health: OK, EXPIRING, LAPSED or MISSING.",
    ),
    membership_type: str | None = Query(
        None,
        description="Filter by membership type value_code (e.g. PROBATIONARY, REGULAR).",
    ),
    search: str | None = Query(
        None, description="Match Sangha Sevi ID or member name (case-insensitive)."
    ),
    user: UserContext = Depends(
        require_any_permission(
            "MEMBERSHIP_VIEW", "MEMBERSHIP_MANAGE", "ADMIN_USER_MANAGE"
        )
    ),
    conn=Depends(get_connection),
) -> CredentialMemberListResponse:
    """
    One row per active Sangha Sevi with the health of the single
    credential they are supposed to hold (MBR-019B):

      - OK        — holds the expected ACTIVE credential, not near expiry.
      - EXPIRING  — holds it, but valid_to is within
                    _CREDENTIAL_EXPIRING_WINDOW_DAYS days of today.
      - LAPSED    — holds it, but it expired before today.
      - MISSING   — holds no ACTIVE credential of the expected type.

    The "expected" credential is Anumati for a Darshaka and Parichaya for
    everyone else — the same rule the issue endpoint applies. Results are
    scoped to the actor's admin subtree (ADMIN-BR-076); a scoped admin with
    no org anchor sees nothing. Ordered worst-health-first.

    Requires MEMBERSHIP_VIEW / MEMBERSHIP_MANAGE / ADMIN_USER_MANAGE.
    """
    state_key = state.strip().upper() if state and state.strip() else None
    if state_key and state_key not in ("OK", "EXPIRING", "LAPSED", "MISSING"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="state must be one of OK, EXPIRING, LAPSED, MISSING.",
        )

    conditions = ["ss.is_active = TRUE"]
    params: list = []

    if membership_type and membership_type.strip():
        conditions.append("mt.value_code = %s")
        params.append(membership_type.strip().upper())

    if search and search.strip():
        conditions.append(
            "(ss.sangha_sevi_id ILIKE %s"
            " OR CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) ILIKE %s)"
        )
        like = f"%{search.strip()}%"
        params.extend([like, like])

    with conn.cursor() as cur:
        # ADMIN-BR-076 subtree scoping — mirrors list_users().
        allowed = _actor_scope_org_pks(cur, user)
        if allowed is not None:
            if not allowed:
                return CredentialMemberListResponse(
                    members=[], total=0, page=page, page_size=page_size
                )
            placeholders = ",".join(["%s"] * len(allowed))
            conditions.append(f"ss.organization_pk IN ({placeholders})")
            params.extend(list(allowed))

        where_clause = " AND ".join(conditions)
        win = int(_CREDENTIAL_EXPIRING_WINDOW_DAYS)
        probationary = PROBATIONARY_MEMBERSHIP_TYPE_CODE

        # CURRENT_DATE + <int> is a date in PostgreSQL; both the expected-type
        # and the state CASEs key off the same probationary code so the view
        # agrees with _expected_card_type()/issue_membership_credential().
        inner_sql = f"""
            SELECT ss.sangha_sevi_pk,
                   ss.sangha_sevi_id,
                   CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS person_name,
                   mt.value_code AS membership_type_code,
                   mt.value_name AS membership_type_name,
                   ss.organization_pk,
                   o.organization_name,
                   CASE WHEN mt.value_code = '{probationary}'
                        THEN ap.document_number ELSE pp.document_number END
                        AS credential_document_number,
                   CASE WHEN mt.value_code = '{probationary}'
                        THEN ap.valid_to ELSE pp.valid_to END
                        AS credential_valid_to,
                   CASE WHEN mt.value_code = '{probationary}'
                        THEN 'ANUMATI_PATRA' ELSE 'PARICHAYA_PATRA' END
                        AS expected_card_type,
                   CASE
                     WHEN mt.value_code = '{probationary}' THEN
                       CASE WHEN ap.anumati_patra_pk IS NULL THEN 'MISSING'
                            WHEN ap.valid_to < CURRENT_DATE THEN 'LAPSED'
                            WHEN ap.valid_to <= CURRENT_DATE + {win} THEN 'EXPIRING'
                            ELSE 'OK' END
                     ELSE
                       CASE WHEN pp.parichaya_patra_pk IS NULL THEN 'MISSING'
                            WHEN pp.valid_to < CURRENT_DATE THEN 'LAPSED'
                            WHEN pp.valid_to <= CURRENT_DATE + {win} THEN 'EXPIRING'
                            ELSE 'OK' END
                   END AS credential_state
            FROM nss.sangha_sevi ss
            JOIN nss.person p ON p.person_pk = ss.person_pk
            JOIN nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk
            LEFT JOIN nss.organization o ON o.organization_pk = ss.organization_pk
            LEFT JOIN nss.parichaya_patra pp
                   ON pp.sangha_sevi_pk = ss.sangha_sevi_pk AND pp.status = 'ACTIVE'
            LEFT JOIN nss.anumati_patra ap
                   ON ap.sangha_sevi_pk = ss.sangha_sevi_pk AND ap.status = 'ACTIVE'
            WHERE {where_clause}
        """

        outer_where = ""
        outer_params: list = []
        if state_key:
            outer_where = "WHERE q.credential_state = %s"
            outer_params.append(state_key)

        cur.execute(
            f"SELECT COUNT(*) FROM ({inner_sql}) q {outer_where}",
            params + outer_params,
        )
        total = cur.fetchone()[0]

        offset = (page - 1) * page_size
        cur.execute(
            f"""
            SELECT * FROM ({inner_sql}) q {outer_where}
            ORDER BY CASE q.credential_state
                         WHEN 'MISSING' THEN 0
                         WHEN 'LAPSED' THEN 1
                         WHEN 'EXPIRING' THEN 2
                         ELSE 3 END,
                     q.person_name
            LIMIT %s OFFSET %s
            """,
            params + outer_params + [page_size, offset],
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    members = [
        CredentialMemberStateResponse(
            sangha_sevi_pk=r["sangha_sevi_pk"],
            sangha_sevi_id=r["sangha_sevi_id"],
            person_name=r["person_name"] if r["person_name"] and r["person_name"].strip() else None,
            membership_type_code=r["membership_type_code"],
            membership_type_name=r["membership_type_name"],
            organization_pk=r["organization_pk"],
            organization_name=r["organization_name"],
            expected_card_type=r["expected_card_type"],
            credential_state=r["credential_state"],
            credential_document_number=r["credential_document_number"],
            credential_valid_to=r["credential_valid_to"],
        )
        for r in rows
    ]
    return CredentialMemberListResponse(
        members=members, total=total, page=page, page_size=page_size
    )


class CredentialHistoryEntryResponse(BaseModel):
    change_type: str
    change_date: date
    previous_status: str | None
    new_status: str
    remarks: str | None


class CredentialTimelineEntryResponse(BaseModel):
    card_type: str  # ANUMATI_PATRA / PARICHAYA_PATRA
    credential_pk: UUID
    document_number: str
    issue_date: date
    valid_from: date
    valid_to: date
    status: str
    local_sakha_erp_id: str | None
    history: list[CredentialHistoryEntryResponse]


class CredentialTimelineResponse(BaseModel):
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str | None
    membership_type_code: str
    entries: list[CredentialTimelineEntryResponse]


def _load_member_for_credentials(cur, sangha_sevi_pk: str) -> dict:
    """
    Resolve an ACTIVE Sangha Sevi for the credential endpoints — the
    membership type, home organization and person, plus the current open
    affiliation's local number (the Parichaya snapshot). 404 if the member
    does not exist or is soft-deleted. Single lookup shared by the timeline,
    issue and promote endpoints so they agree on identity and scope anchor.
    """
    cur.execute(
        """
        SELECT ss.sangha_sevi_pk,
               ss.sangha_sevi_id,
               ss.person_pk,
               ss.membership_type_master_data_pk,
               mt.value_code AS membership_type_code,
               ss.organization_pk,
               CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS person_name,
               msa.local_sakha_erp_id
        FROM nss.sangha_sevi ss
        JOIN nss.person p ON p.person_pk = ss.person_pk
        JOIN nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk
        LEFT JOIN LATERAL (
            SELECT local_sakha_erp_id
            FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = ss.sangha_sevi_pk AND effective_to IS NULL
            ORDER BY effective_from DESC
            LIMIT 1
        ) msa ON TRUE
        WHERE ss.sangha_sevi_pk = %s AND ss.is_active = TRUE
        """,
        (str(sangha_sevi_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sangha Sevi not found.",
        )
    name = row[6]
    return {
        "sangha_sevi_pk": str(row[0]),
        "sangha_sevi_id": row[1],
        "person_pk": str(row[2]),
        "membership_type_pk": str(row[3]),
        "membership_type_code": row[4],
        "organization_pk": str(row[5]),
        "person_name": name if name and name.strip() else None,
        "local_sakha_erp_id": row[7],
    }


@router.get(
    "/credentials/members/{sangha_sevi_pk}/timeline",
    response_model=CredentialTimelineResponse,
)
def member_credential_timeline(
    sangha_sevi_pk: UUID,
    user: UserContext = Depends(
        require_any_permission(
            "MEMBERSHIP_VIEW", "MEMBERSHIP_MANAGE", "ADMIN_USER_MANAGE"
        )
    ),
    conn=Depends(get_connection),
) -> CredentialTimelineResponse:
    """
    A member's full credential history, oldest first — every Anumati and
    Parichaya Patra they have ever held, each with its own lifecycle rows
    from parichaya_patra_history / anumati_patra_history. This is the
    "old Anumati, then Parichaya" timeline: a member promoted from Darshaka
    shows their EXPIRED Anumati Patra followed by their ACTIVE Parichaya
    Patra (MBR-010/019C).

    Scoped to the actor's subtree (ADMIN-BR-076).
    Requires MEMBERSHIP_VIEW / MEMBERSHIP_MANAGE / ADMIN_USER_MANAGE.
    """
    with conn.cursor() as cur:
        member = _load_member_for_credentials(cur, str(sangha_sevi_pk))
        _require_org_in_scope(
            cur, user, member["organization_pk"], "view member credentials"
        )

        # Both credential tables, every status, with their history rows.
        # ordinal keeps a stable card_type sort key; UNION ALL then one
        # ORDER BY issue_date gives the oldest-first timeline.
        cur.execute(
            """
            SELECT 'ANUMATI_PATRA' AS card_type, anumati_patra_pk AS credential_pk,
                   document_number, issue_date, valid_from, valid_to, status,
                   NULL::varchar AS local_sakha_erp_id
            FROM nss.anumati_patra WHERE sangha_sevi_pk = %s
            UNION ALL
            SELECT 'PARICHAYA_PATRA', parichaya_patra_pk,
                   document_number, issue_date, valid_from, valid_to, status,
                   local_sakha_erp_id
            FROM nss.parichaya_patra WHERE sangha_sevi_pk = %s
            ORDER BY issue_date, card_type
            """,
            (member["sangha_sevi_pk"], member["sangha_sevi_pk"]),
        )
        cred_cols = [d[0] for d in cur.description]
        creds = [dict(zip(cred_cols, r)) for r in cur.fetchall()]

        # History for all of this member's credentials, in one pass each.
        cur.execute(
            """
            SELECT h.anumati_patra_pk AS credential_pk, h.change_type, h.change_date,
                   h.previous_status, h.new_status, h.remarks
            FROM nss.anumati_patra_history h
            JOIN nss.anumati_patra c ON c.anumati_patra_pk = h.anumati_patra_pk
            WHERE c.sangha_sevi_pk = %s
            UNION ALL
            SELECT h.parichaya_patra_pk, h.change_type, h.change_date,
                   h.previous_status, h.new_status, h.remarks
            FROM nss.parichaya_patra_history h
            JOIN nss.parichaya_patra c ON c.parichaya_patra_pk = h.parichaya_patra_pk
            WHERE c.sangha_sevi_pk = %s
            ORDER BY change_date
            """,
            (member["sangha_sevi_pk"], member["sangha_sevi_pk"]),
        )
        hist_cols = [d[0] for d in cur.description]
        hist_rows = [dict(zip(hist_cols, r)) for r in cur.fetchall()]

    by_cred: dict[str, list[CredentialHistoryEntryResponse]] = {}
    for h in hist_rows:
        by_cred.setdefault(str(h["credential_pk"]), []).append(
            CredentialHistoryEntryResponse(
                change_type=h["change_type"],
                change_date=h["change_date"],
                previous_status=h["previous_status"],
                new_status=h["new_status"],
                remarks=h["remarks"],
            )
        )

    entries = [
        CredentialTimelineEntryResponse(
            card_type=c["card_type"],
            credential_pk=c["credential_pk"],
            document_number=c["document_number"],
            issue_date=c["issue_date"],
            valid_from=c["valid_from"],
            valid_to=c["valid_to"],
            status=c["status"],
            local_sakha_erp_id=c["local_sakha_erp_id"],
            history=by_cred.get(str(c["credential_pk"]), []),
        )
        for c in creds
    ]
    return CredentialTimelineResponse(
        sangha_sevi_pk=UUID(member["sangha_sevi_pk"]),
        sangha_sevi_id=member["sangha_sevi_id"],
        person_name=member["person_name"],
        membership_type_code=member["membership_type_code"],
        entries=entries,
    )


class IssueCredentialRequest(BaseModel):
    document_number: str | None = Field(
        None, max_length=30,
        description=(
            "Optional. Type the Patra number by hand when it was never "
            "auto-generated (e.g. a legacy card). A bare number gets the "
            "correct year pair appended; a number with a year is verified "
            "against the issue date (MBR-030H). Omit to auto-mint (MBR-030A)."
        ),
    )
    issue_date: str | None = Field(
        None, description="ISO date. Overrides the default issue date."
    )
    issue_year: int | None = Field(
        None, description="For a Parichaya Patra, issue on this year's Dola Purnima."
    )
    valid_from: str | None = Field(None, description="ISO date; defaults by rule.")
    valid_to: str | None = Field(None, description="ISO date; defaults by rule.")
    president_override: bool = Field(
        False,
        description=(
            "Sakha President authorisation to re-issue a Parichaya Patra that "
            "lapsed (MBR-030G); ignored otherwise."
        ),
    )
    remarks: str | None = Field(
        None, max_length=500, description="Recorded on the credential's timeline row."
    )


class IssueCredentialResponse(BaseModel):
    sangha_sevi_pk: UUID
    card_type: str
    credential_pk: UUID
    document_number: str


@router.post(
    "/credentials/members/{sangha_sevi_pk}/issue",
    response_model=IssueCredentialResponse,
    status_code=201,
)
def issue_member_credential(
    sangha_sevi_pk: UUID,
    body: IssueCredentialRequest,
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_MANAGE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> IssueCredentialResponse:
    """
    Issue (or renew) the one credential a member should hold — an Anumati
    Patra for a Darshaka, a Parichaya Patra for everyone else — for a member
    who has none active. This is where an admin types a Parichaya number by
    hand when it was never auto-generated: pass *document_number* and it is
    stored verbatim (year-validated per MBR-030H); omit it to auto-mint.

    All issuance rules are enforced by issue_membership_credential() — the
    same choke point registration and admin member-creation use — so this
    adds no new credential logic, only the admin entry point and scope gate.
    A member who already holds an ACTIVE credential of the expected type gets
    a 409 (correct an existing number via the PATCH endpoint instead).

    Scoped to the actor's subtree (ADMIN-BR-076).
    Requires MEMBERSHIP_MANAGE or ADMIN_USER_MANAGE.
    """
    actor = user.actor_pk
    with conn.cursor() as cur:
        member = _load_member_for_credentials(cur, str(sangha_sevi_pk))
        _require_org_in_scope(
            cur, user, member["organization_pk"], "issue member credentials"
        )

        card_type, credential_pk, document_number = issue_membership_credential(
            cur,
            sangha_sevi_pk=member["sangha_sevi_pk"],
            membership_type_pk=member["membership_type_pk"],
            organization_pk=member["organization_pk"],
            document_number=body.document_number,
            issue_date=date.fromisoformat(body.issue_date) if body.issue_date else None,
            issue_year=body.issue_year,
            valid_from=date.fromisoformat(body.valid_from) if body.valid_from else None,
            valid_to=date.fromisoformat(body.valid_to) if body.valid_to else None,
            date_of_birth=fetch_person_date_of_birth(cur, member["person_pk"]),
            president_override=body.president_override,
            local_sakha_erp_id=member["local_sakha_erp_id"],
            history_remarks=body.remarks.strip() if body.remarks and body.remarks.strip() else None,
        )
        log_audit(
            cur, action="CREATE", table_name=card_type.lower(), record_pk=credential_pk,
            actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
            module="admin",
            summary=(
                f"Issued {card_type} {document_number} for {member['sangha_sevi_id']}"
                + (f" — {body.remarks.strip()}" if body.remarks and body.remarks.strip() else "")
            ),
        )

    return IssueCredentialResponse(
        sangha_sevi_pk=sangha_sevi_pk,
        card_type=card_type,
        credential_pk=UUID(credential_pk),
        document_number=document_number,
    )


# Journey-event type recorded when a Darshaka is promoted to Regular.
# membership_journey_event.event_type is an open VARCHAR catalogue (no CHECK),
# so this is a convention, kept as a named constant to prevent typo drift.
_PROMOTION_JOURNEY_EVENT_TYPE = "PROMOTION_TO_REGULAR"


class PromoteToRegularRequest(BaseModel):
    effective_date: str | None = Field(
        None,
        description=(
            "ISO date the promotion takes effect. Defaults to the most recent "
            "Dola Purnima on/before today (MBR-011A — promotions batch to Dola "
            "Purnima). Used for the new Parichaya Patra's issue date, the Sakha "
            "affiliation close/open dates and the journey event."
        ),
    )
    document_number: str | None = Field(
        None, max_length=30,
        description="Optional hand-entered Parichaya number (MBR-030H); omit to auto-mint.",
    )
    remarks: str | None = Field(
        None, max_length=500, description="Recorded on the journey event and credential history."
    )


class PromoteToRegularResponse(BaseModel):
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    previous_membership_type_code: str
    new_membership_type_code: str
    expired_anumati_patra_pk: UUID | None
    archived_affiliation_local_id: str | None
    new_affiliation_local_id: str | None
    parichaya_patra_pk: UUID
    parichaya_document_number: str
    effective_date: date


@router.post(
    "/credentials/members/{sangha_sevi_pk}/promote",
    response_model=PromoteToRegularResponse,
)
def promote_darshak_to_regular(
    sangha_sevi_pk: UUID,
    body: PromoteToRegularRequest,
    user: UserContext = Depends(
        require_any_permission("MEMBERSHIP_MANAGE", "ADMIN_USER_MANAGE")
    ),
    conn=Depends(get_write_connection),
) -> PromoteToRegularResponse:
    """
    Promote a Darshaka (PROBATIONARY) member to Regular (MBR-010 / MBR-011A /
    MBR-030C). The sequence, all in one transaction:

      1. Expire the member's ACTIVE Anumati Patra (status → EXPIRED; the row
         and its history are preserved, never deleted — MBR-019C).
      2. Flip membership_type PROBATIONARY → REGULAR on sangha_sevi.
      3. Archive the open DARSHAK-namespace Sakha affiliation (ESSD…) and open
         a new REGULAR-namespace one (ESS…) at the same Sakha; the Sangha Sevi
         ID (Tier 1) never changes.
      4. Issue the Parichaya Patra (auto-minted, or the hand-typed number).
      5. Record a PROMOTION_TO_REGULAR journey event.

    This is the only path that changes a membership type or retires a
    credential, so it is admin-only and scope-gated. Refuses (422) a member
    who is not currently PROBATIONARY or who has no open Sakha affiliation.

    Scoped to the actor's subtree (ADMIN-BR-076).
    Requires MEMBERSHIP_MANAGE or ADMIN_USER_MANAGE.
    """
    actor = user.actor_pk
    with conn.cursor() as cur:
        member = _load_member_for_credentials(cur, str(sangha_sevi_pk))
        _require_org_in_scope(
            cur, user, member["organization_pk"], "promote members"
        )

        if member["membership_type_code"] != PROBATIONARY_MEMBERSHIP_TYPE_CODE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Only a Darshaka (probationary) member can be promoted to "
                    f"Regular; this member is {member['membership_type_code']}."
                ),
            )

        # Effective date — defaults to the Dola Purnima the promotion batches
        # to (MBR-011A), resolved from the festival calendar, never computed.
        if body.effective_date and body.effective_date.strip():
            effective_date = date.fromisoformat(body.effective_date.strip())
        else:
            effective_date = previous_festival_date_on_or_before(
                cur, "DOLA_PURNIMA", date.today()
            )
            if effective_date is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "No confirmed Dola Purnima date is on file on or before "
                        f"{date.today().isoformat()}, so no default promotion date "
                        "can be resolved. Supply effective_date explicitly, or have "
                        "an administrator confirm the date in the festival calendar."
                    ),
                )

        remarks = body.remarks.strip() if body.remarks and body.remarks.strip() else None
        regular_type_pk = get_master_data_pk(cur, "MEMBERSHIP_TYPE", "REGULAR")

        # 1 — expire the ACTIVE Anumati Patra (if one exists). Preserved, not
        #     deleted (MBR-019C); set_membership_credential_status writes the
        #     EXPIRED history row.
        cur.execute(
            "SELECT anumati_patra_pk FROM nss.anumati_patra "
            "WHERE sangha_sevi_pk = %s AND status = 'ACTIVE'",
            (member["sangha_sevi_pk"],),
        )
        ap_row = cur.fetchone()
        expired_anumati_pk = None
        if ap_row is not None:
            expired_anumati_pk = str(ap_row[0])
            set_membership_credential_status(
                cur,
                card_type="ANUMATI_PATRA",
                credential_pk=expired_anumati_pk,
                new_status="EXPIRED",
                change_type="EXPIRED",
                change_date=effective_date,
                remarks="Expired on promotion to Regular"
                + (f" — {remarks}" if remarks else ""),
            )
            log_audit(
                cur, action="UPDATE", table_name="anumati_patra",
                record_pk=expired_anumati_pk, actor_pk=actor,
                actor_user_account_pk=str(user.user_account_pk), module="admin",
                summary=f"Expired Anumati Patra on promotion of {member['sangha_sevi_id']}",
            )

        # 2 — flip membership type to Regular.
        cur.execute(
            """
            UPDATE nss.sangha_sevi
            SET membership_type_master_data_pk = %s, updated_at = NOW()
            WHERE sangha_sevi_pk = %s
            """,
            (regular_type_pk, member["sangha_sevi_pk"]),
        )
        log_audit(
            cur, action="UPDATE", table_name="sangha_sevi",
            record_pk=member["sangha_sevi_pk"], actor_pk=actor,
            actor_user_account_pk=str(user.user_account_pk), module="admin",
            summary=f"Promoted {member['sangha_sevi_id']} from Darshaka to Regular",
        )

        # 3 — archive the open DARSHAK affiliation, open a new REGULAR one at
        #     the same Sakha. The home affiliation is the open-ended row.
        cur.execute(
            """
            SELECT membership_sakha_affiliation_pk, organization_pk, local_sakha_erp_id
            FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = %s AND effective_to IS NULL
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            (member["sangha_sevi_pk"],),
        )
        aff_row = cur.fetchone()
        if aff_row is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "This member has no open Sakha affiliation to archive — the "
                    "promotion cannot open the new Regular-namespace affiliation."
                ),
            )
        old_aff_pk, aff_org_pk, archived_local_id = str(aff_row[0]), str(aff_row[1]), aff_row[2]

        close_sakha_affiliation(
            cur, membership_sakha_affiliation_pk=old_aff_pk, effective_to=effective_date,
        )
        new_aff_pk = insert_sakha_affiliation(
            cur,
            sangha_sevi_pk=member["sangha_sevi_pk"],
            organization_pk=aff_org_pk,
            effective_from=effective_date,
            is_darshak=False,
        )
        cur.execute(
            "SELECT local_sakha_erp_id FROM nss.membership_sakha_affiliation "
            "WHERE membership_sakha_affiliation_pk = %s",
            (new_aff_pk,),
        )
        new_local_id = cur.fetchone()[0]
        log_audit(
            cur, action="UPDATE", table_name="membership_sakha_affiliation",
            record_pk=old_aff_pk, actor_pk=actor,
            actor_user_account_pk=str(user.user_account_pk), module="admin",
            summary=f"Archived Darshaka affiliation {archived_local_id} on promotion",
        )
        log_audit(
            cur, action="CREATE", table_name="membership_sakha_affiliation",
            record_pk=str(new_aff_pk), actor_pk=actor,
            actor_user_account_pk=str(user.user_account_pk), module="admin",
            summary=f"Opened Regular affiliation {new_local_id} on promotion",
        )

        # 4 — issue the Parichaya Patra (Regular type now). issue_date is the
        #     promotion's Dola Purnima; the new local id is the printed snapshot.
        card_type, parichaya_pk, parichaya_number = issue_membership_credential(
            cur,
            sangha_sevi_pk=member["sangha_sevi_pk"],
            membership_type_pk=regular_type_pk,
            organization_pk=aff_org_pk,
            document_number=body.document_number,
            issue_date=effective_date,
            local_sakha_erp_id=new_local_id,
            history_remarks="Issued on promotion to Regular"
            + (f" — {remarks}" if remarks else ""),
        )
        log_audit(
            cur, action="CREATE", table_name="parichaya_patra", record_pk=parichaya_pk,
            actor_pk=actor, actor_user_account_pk=str(user.user_account_pk), module="admin",
            summary=f"Issued Parichaya Patra {parichaya_number} on promotion of {member['sangha_sevi_id']}",
        )

        # 5 — journey event.
        cur.execute(
            """
            INSERT INTO nss.membership_journey_event (
                sangha_sevi_pk, event_type, event_date, remarks,
                created_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING membership_journey_event_pk
            """,
            (
                member["sangha_sevi_pk"], _PROMOTION_JOURNEY_EVENT_TYPE,
                effective_date, remarks, actor,
            ),
        )
        journey_pk = cur.fetchone()[0]
        log_audit(
            cur, action="CREATE", table_name="membership_journey_event",
            record_pk=str(journey_pk), actor_pk=actor,
            actor_user_account_pk=str(user.user_account_pk), module="admin",
            summary=f"Recorded promotion-to-Regular journey event for {member['sangha_sevi_id']}",
        )

    return PromoteToRegularResponse(
        sangha_sevi_pk=sangha_sevi_pk,
        sangha_sevi_id=member["sangha_sevi_id"],
        previous_membership_type_code=PROBATIONARY_MEMBERSHIP_TYPE_CODE,
        new_membership_type_code="REGULAR",
        expired_anumati_patra_pk=UUID(expired_anumati_pk) if expired_anumati_pk else None,
        archived_affiliation_local_id=archived_local_id,
        new_affiliation_local_id=new_local_id,
        parichaya_patra_pk=UUID(parichaya_pk),
        parichaya_document_number=parichaya_number,
        effective_date=effective_date,
    )
