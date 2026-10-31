"""
NSS ERP — Administration Pydantic schemas.

Request/response models for admin endpoints (Tier 5).
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from api.schemas.auth import UpdateProfileRequest


# ── Request schemas ──────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    """POST /api/v1/admin/users"""
    person_pk: UUID = Field(
        ...,
        description="Person to create user account for (must exist in nss.person)",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Initial password (8–128 chars, 1 uppercase, 1 digit)",
    )
    force_password_change: bool = Field(
        default=True,
        description="Require password change on first login",
    )
    # Optional: also create sangha_sevi record
    create_sangha_sevi: bool = Field(
        default=False,
        description="If true, also create a Sangha Sevi (membership) record",
    )
    membership_type_pk: str | None = Field(
        None, description="UUID of membership_type master_data row (required if create_sangha_sevi)",
    )
    organization_pk: str | None = Field(
        None, description="UUID of organization/sakha (required if create_sangha_sevi)",
    )
    joining_date: str | None = Field(
        None, description="Joining date ISO (required if create_sangha_sevi)",
    )
    local_sakha_erp_id: str | None = Field(
        None, max_length=30,
        description="Local Sakha register number (raw, e.g. 1192). Backend composes <short_code><number>.",
    )
    # Mandatory credential (MBR-010/014/019A/B), mirroring
    # CreateSanghaSeviRequest below — this branch creates a sangha_sevi row
    # too (when create_sangha_sevi=true), so it owes the member the same
    # Anumati/Parichaya Patra. Omit credential_document_number to
    # auto-generate a new FY number; supply it to record an already-issued
    # legacy credential instead. Ignored when create_sangha_sevi=false.
    credential_document_number: str | None = Field(
        None, max_length=30,
        description="Existing document number for a legacy (already-issued) credential; omit to auto-generate a new one.",
    )
    credential_issue_date: str | None = Field(
        None, description="Deprecated — issue date is now derived from credential_issue_year's Dola Purnima. An explicit ISO (YYYY-MM-DD) date still wins if supplied.",
    )
    credential_issue_year: int | None = Field(
        None, ge=1900, le=2200,
        description="Membership year; the credential's issue date is that year's Dola Purnima (422 if that date is unknown or still in the future).",
    )
    credential_valid_from: str | None = Field(
        None, description="Legacy credential's validity start (YYYY-MM-DD); defaults to the current FY start when auto-generating.",
    )
    credential_valid_to: str | None = Field(
        None, description="Legacy credential's validity end (YYYY-MM-DD); defaults to the current FY end when auto-generating.",
    )


class ResetPasswordRequest(BaseModel):
    """POST /api/v1/admin/users/{user_account_pk}/reset-password"""
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password set by admin",
    )
    force_password_change: bool = Field(
        default=True,
        description="Require the user to change this password on next login",
    )


class UpdateStatusRequest(BaseModel):
    """PATCH /api/v1/admin/users/{user_account_pk}/status"""
    account_status: str = Field(
        ...,
        description="New status: ACTIVE, LOCKED, or INACTIVE",
        pattern="^(ACTIVE|LOCKED|INACTIVE)$",
    )


class UpdatePersonProfileRequest(UpdateProfileRequest):
    """PATCH /api/v1/admin/persons/{person_pk}

    Admin counterpart to PATCH /api/v1/auth/profile. Same field set and
    PATCH semantics as UpdateProfileRequest (apply_person_profile_update()
    is the single shared validation path for both surfaces — SOL-PERSON,
    2026-10-03), plus an optional *reason* that is folded into the audit
    log summary rather than stored on nss.person itself.
    """
    reason: str | None = Field(
        None, max_length=500,
        description="Why the profile is being corrected (recorded in the audit log).",
    )


class PersonProfileResponse(BaseModel):
    """GET /api/v1/admin/persons/{person_pk}

    Raw editable field values for the Profile Details edit card — the
    read counterpart to UpdatePersonProfileRequest/apply_person_profile_update().
    Deliberately mirrors that field set 1:1 so the form can be pre-filled
    and PATCHed back with no translation layer.
    """
    person_pk: UUID
    first_name: str
    middle_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    gender_master_data_pk: UUID | None = None
    marital_status_master_data_pk: UUID | None = None
    blood_group_master_data_pk: UUID | None = None
    country_phone_code: str | None = None
    mobile_number: str | None = None
    email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_relationship_master_data_pk: UUID | None = None
    remarks: str | None = None


class SanghaSeviBatchCheckRequest(BaseModel):
    """POST /api/v1/admin/sangha-sevi/check-batch

    person_pks must be a list of UUIDs (non-UUID / non-list -> 422). An
    omitted or empty list, or more than 100 entries, yields an empty map
    (unchanged behaviour).
    """
    person_pks: list[UUID] = Field(default_factory=list)


class AssignRoleRequest(BaseModel):
    """POST /api/v1/admin/users/{user_account_pk}/roles"""
    role_code: str = Field(
        ...,
        description="Role code from role_master (e.g., NSS_ERP_ADMIN)",
    )
    scope_level: str = Field(
        ...,
        description=(
            "Scope level: NSS-WIDE, KENDRA, ANCHALIKA, ZILLA, SAKHA, "
            "PATHA_CHAKRA, KENDRA_MAHILA_SANGHA, ADVISORY_BOARD"
        ),
        # Must stay in step with chk_admin_scope_level in
        # database/ddl/07_administration/02_admin_scope.sql and with the
        # scope_level values in 00_bootstrap/02_role_master.sql — one value
        # per ORGANIZATIONAL role, or that role cannot be assigned at all.
        pattern="^(NSS-WIDE|KENDRA|ANCHALIKA|ZILLA|SAKHA|PATHA_CHAKRA|KENDRA_MAHILA_SANGHA|ADVISORY_BOARD)$",
    )
    organization_pk: UUID | None = Field(
        default=None,
        description="Organization PK (required unless scope_level is NSS-WIDE)",
    )


class CreateSanghaSeviRequest(BaseModel):
    """POST /api/v1/admin/sangha-sevi — standalone SS membership creation."""
    person_pk: UUID = Field(
        ..., description="Person to create Sangha Sevi record for",
    )
    membership_type_pk: str = Field(
        ..., description="UUID of membership_type master_data row",
    )
    organization_pk: str | None = Field(
        None,
        description=(
            "UUID of organization/sakha. Optional: a single-Sakha admin has "
            "it auto-resolved server-side; an NSS-wide or multi-Sakha admin "
            "must supply it."
        ),
    )
    joining_date: str | None = Field(
        None,
        description=(
            "Sangha Joining Date, ISO (YYYY-MM-DD). OPTIONAL (MBR-047) — "
            "omit when the date is not known. NULL means 'not recorded', "
            "not 'joined today'; it is never defaulted."
        ),
    )
    local_sakha_erp_id: str | None = Field(
        None, max_length=30,
        description="Local Sakha register number (raw, e.g. 1192). Backend composes <short_code><number>.",
    )
    # Optional: also create a login (user account) for this person. Because
    # login is by sangha_sevi_id, an account is only usable once the person
    # is a Sangha Sevi — so the Sangha Sevi flow is the natural place to
    # offer account creation (rather than the person-anchored Create User
    # flow). The account branch itself requires ADMIN_USER_MANAGE.
    create_user_account: bool = Field(
        default=False,
        description="If true, also create a login/user account for this person.",
    )
    password: str | None = Field(
        None, min_length=8, max_length=128,
        description="Initial password (required if create_user_account; 8–128 chars, 1 uppercase, 1 digit).",
    )
    force_password_change: bool = Field(
        default=True,
        description="Require password change on first login (only used if create_user_account).",
    )
    # Mandatory credential (MBR-010/014/019A/B): a PROBATIONARY member must
    # be issued an Anumati Patra; REGULAR/ASSOCIATE must be issued a
    # Parichaya Patra. Two paths:
    #   - Omit credential_document_number: a new number is auto-generated
    #     for the current financial year (Kendra-wide sequence for
    #     Parichaya Patra, Sakha-wide for Anumati Patra — MBR-030A).
    #   - Provide credential_document_number (+ optionally the other
    #     credential_* fields): records an already-issued legacy
    #     credential instead of minting a new one.
    credential_document_number: str | None = Field(
        None, max_length=30,
        description="Existing document number for a legacy (already-issued) credential; omit to auto-generate a new one.",
    )
    credential_issue_date: str | None = Field(
        None, description="Deprecated — issue date is now derived from credential_issue_year's Dola Purnima. An explicit ISO (YYYY-MM-DD) date still wins if supplied.",
    )
    credential_issue_year: int | None = Field(
        None, ge=1900, le=2200,
        description="Membership year; the credential's issue date is that year's Dola Purnima (422 if that date is unknown or still in the future).",
    )
    credential_valid_from: str | None = Field(
        None, description="Legacy credential's validity start (YYYY-MM-DD); defaults to the current FY start when auto-generating.",
    )
    credential_valid_to: str | None = Field(
        None, description="Legacy credential's validity end (YYYY-MM-DD); defaults to the current FY end when auto-generating.",
    )


class UserAccountResponse(BaseModel):
    """Single user account in list and detail views."""
    user_account_pk: UUID
    person_pk: UUID
    person_id: str | None = None
    sangha_sevi_id: str | None = None
    sangha_sevi_id_generated: str | None = None  # Set only when SS was just created
    # Set only when a credential was just issued (create_sangha_sevi=true
    # branch) — mirrors CreateSanghaSeviResponse's fields.
    credential_type: str | None = None
    credential_document_number: str | None = None
    person_name: str | None = None
    organization_name: str | None = None
    organization_pk: UUID | None = None  # home Sakha (active SS org, else claimed org)
    local_sakha_erp_id: str | None = None
    darshak_local_number: str | None = None
    darshak_organization_name: str | None = None
    # Home-org membership type's value_code (e.g. "PROBATIONARY"), so a
    # Darshaka member's local_sakha_erp_id isn't mislabeled "Regular".
    home_membership_type_code: str | None = None
    account_status: str
    force_password_change: bool
    last_login_at: datetime | None = None
    password_expires_at: datetime | None = None
    created_at: datetime
    is_active: bool


class UserListResponse(BaseModel):
    """GET /api/v1/admin/users — paginated list."""
    users: list[UserAccountResponse]
    total: int
    page: int
    page_size: int


class AccountlessSanghaSeviResponse(BaseModel):
    """
    A Sangha Sevi who holds an SS ID but cannot log in — either no
    user_account row exists at all, or the only one is soft-deleted.

    Feeds the "Create Account" picker on the User Accounts page. Account
    provisioning itself keys on person_pk (uq_user_account_person — one
    account per PERSON, not per membership), which is why person_pk is
    carried here alongside the SS identifiers the admin actually recognises.
    """
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_pk: UUID
    person_id: str | None = None
    person_name: str | None = None
    organization_name: str | None = None
    local_sakha_erp_id: str | None = None
    membership_type_code: str | None = None
    membership_status_code: str | None = None
    joining_date: date | None = None
    # TRUE when a soft-deleted account occupies the UNIQUE(person_pk) slot.
    # POST /admin/users reactivates in place for these rather than inserting,
    # so the UI must say "Restore Access", not "Create Account".
    has_deleted_account: bool = False


class AccountlessSanghaSeviListResponse(BaseModel):
    """GET /api/v1/admin/sangha-sevi/without-account — paginated list."""
    members: list[AccountlessSanghaSeviResponse]
    total: int
    page: int
    page_size: int


class RoleAssignmentResponse(BaseModel):
    """A single role assignment with scope."""
    user_role_pk: UUID
    role_code: str
    role_name: str
    scope_level: str | None = None
    organization_pk: UUID | None = None
    organization_name: str | None = None
    assigned_at: datetime
    is_active: bool


class AutoGrantedScopeResponse(BaseModel):
    """
    A §63 composite auto-grant — a scope derived live from a governance
    position (body_member_assignment / acting_position_assignment), not
    from any real user_role row. Carries no user_role_pk because none
    exists: nothing is stored, nothing can be revoked here — it disappears
    the moment the person leaves the position. Shown read-only alongside
    RoleAssignmentResponse in the admin UI, badged "Auto-Admin (§63)".
    """
    role_code: str
    role_name: str
    scope_level: str | None = None
    organization_pk: UUID | None = None
    organization_name: str | None = None


class UserDetailResponse(BaseModel):
    """GET /api/v1/admin/users/{user_account_pk} — full detail."""
    user_account_pk: UUID
    person_pk: UUID
    person_id: str | None = None
    sangha_sevi_id: str | None = None
    person_name: str | None = None
    organization_name: str | None = None
    organization_pk: UUID | None = None  # home Sakha (active SS org, else claimed org)
    local_sakha_erp_id: str | None = None
    darshak_local_number: str | None = None
    darshak_organization_name: str | None = None
    home_membership_type_code: str | None = None
    account_status: str
    force_password_change: bool
    last_login_at: datetime | None = None
    password_expires_at: datetime | None = None
    failed_login_attempts: int
    locked_until: datetime | None = None
    created_at: datetime
    is_active: bool
    roles: list[RoleAssignmentResponse]
    auto_granted_scopes: list[AutoGrantedScopeResponse] = []


class CreateSanghaSeviResponse(BaseModel):
    """POST /api/v1/admin/sangha-sevi — response."""
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_pk: UUID
    person_name: str | None = None
    organization_name: str | None = None
    # Set only when a login account was bundled into this SS creation.
    user_account_pk: UUID | None = None
    # The mandatory credential issued alongside this Sangha Sevi
    # (MBR-010/014/019A/B) — "ANUMATI_PATRA" or "PARICHAYA_PATRA".
    credential_type: str
    credential_document_number: str
