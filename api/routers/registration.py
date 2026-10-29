"""
NSS ERP — Self-Registration router.

Tier 5 endpoints:
  POST /api/v1/register                 — Self-register (person always; account+claim only if has_membership)
  POST /api/v1/register/check-duplicate — Pre-submit duplicate contact check (body, not query — avoids PII in access logs)
  POST /api/v1/register/lookup-existing — "Previously registered" lookup (person_id + DOB) for the claim flow below
  POST /api/v1/register/claim           — Submit a membership claim for an already-registered, SS-less person
  GET  /api/v1/register/reference-data  — Dropdown reference data for the form
  GET  /api/v1/register/states          — States lookup (cascading geography)
  GET  /api/v1/register/districts       — Districts lookup (by state)
  GET  /api/v1/register/postal-codes    — Postal-code lookup (by district)

Flow (POST /register):
  1. Validate input (person details, password policy)
  2. Generate person_id (P<next>) via id_sequence_master
  3. Insert person record
  4. If membership details provided: create user_account (PENDING_APPROVAL),
     record password history, and insert registration_claim
  5. Return person_id (+ person_pk) — if no membership was claimed, no
     account exists yet; the person can submit one later via
     POST /register/claim

Business rules (AUTH-BR-081 through AUTH-BR-098):
  - Mobile OR email required (person CHECK constraint)
  - A user_account is NEVER created for a person with no membership claim —
    an account with no path to a Sangha Sevi can never log in (login
    requires an active sangha_sevi) and must not surface in User Accounts
    or Registration Approvals (user decision, 2026-10-06). Registering
    with has_membership=False creates a person record only; the typed
    password is discarded, not persisted anywhere.
  - No sangha_sevi or membership_sakha_affiliation created at registration
  - Membership intent stored in nss.registration_claim table
  - Local Sakha Number: required for every membership type except Darshaka
    (PROBATIONARY) — a legacy member migrating a known paper-register
    number may still enter it (optional for Darshaka), but a brand-new
    Darshaka applicant has none to self-report; Darshak members are
    enrolled in a separate short_code+marker namespace (MBR-030C) with
    the number system-generated at admin approval.
  - Local Sakha Number is NOT validated at registration (admin verifies)
  - PENDING_APPROVAL accounts cannot login
  - Sakha admin approves claim → creates membership records → activates account

Authority: SOL-AUTH-001, SOL-AUTH-002, SOL-AUTH-006, SOL-AUTH-007
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.config import settings
from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.helpers import log_audit, next_id, resolve_or_create_city_village, resolve_or_create_postal_code, resolve_or_create_post_office, check_duplicate_contact, record_password_history, require_sakha_organization, validate_mobile, validate_email, get_master_data_pk, is_probationary_membership_type
from api.services.auth_service import hash_password, validate_password_policy
from api.routers.foundation import fetch_countries, fetch_states, fetch_districts, fetch_cities, fetch_postal_codes, fetch_post_offices, fetch_master_data
from api.routers.organization import fetch_organizations
from api.schemas.foundation import CountryResponse, StateResponse, DistrictResponse, CityVillageResponse, PostalCodeResponse, PostOfficeResponse, MasterDataResponse
from api.schemas.organization import OrganizationResponse

router = APIRouter(prefix="/api/v1/register", tags=["registration"])


# ── Request / Response schemas ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    """POST /api/v1/register"""

    # Person fields
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: "date" = Field(..., description="Date of birth (YYYY-MM-DD)")
    gender_master_data_pk: str = Field(
        ..., min_length=1, description="UUID of gender master_data row"
    )
    marital_status_master_data_pk: str | None = Field(
        None, description="UUID of marital_status master_data row"
    )
    blood_group_master_data_pk: str | None = Field(
        None, description="UUID of blood_group master_data row"
    )

    # Contact
    country_phone_code: str | None = Field(None, max_length=10)
    mobile_number: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)

    # Address — MANDATORY (user decision, 2026-10-03). Previously optional
    # and, worse, never actually persisted to nss.person_address (only the
    # geography columns on nss.person were written) — the Address card on
    # the member dashboard was permanently empty regardless of what a
    # registrant typed here. Both gaps are fixed together: these fields are
    # now required, and register() below writes a person_address row.
    country_pk: str = Field(
        ..., description="UUID of country",
    )
    state_pk: str = Field(
        ..., description="UUID of state",
    )
    district_pk: str = Field(
        ..., description="UUID of district",
    )
    city_village_name: str = Field(
        ..., max_length=200,
        description="City/village name — lookup/create against Foundation table",
    )
    postal_code_pk: str | None = Field(
        None, description="UUID of postal_code (deprecated — use postal_code_value)",
    )
    postal_code_value: str = Field(
        ..., max_length=20,
        description="PIN code as text — lookup/create against Foundation table",
    )
    post_office_name: str | None = Field(
        None, max_length=150,
        description="Post office name, optional — lookup/create against Foundation table, scoped to the resolved PIN",
    )
    address_line_1: str = Field(
        ..., min_length=1, max_length=255,
        description="Full address line 1 (house/street) — stored on person_address",
    )
    address_line_2: str | None = Field(
        None, max_length=255,
        description="Full address line 2, optional",
    )
    landmark: str | None = Field(
        None, max_length=255,
        description="Nearby landmark, optional",
    )

    # Membership claim (optional — "Not Applicable" toggle)
    has_membership: bool = Field(
        default=False,
        description="True if registering with membership claim details",
    )
    membership_type_master_data_pk: str | None = Field(
        None, description="UUID of membership_type master_data row",
    )
    organization_pk: str | None = Field(
        None, description="UUID of Sakha/org the member claims to belong to",
    )
    joining_date: Optional["date"] = None

    # Local Sakha Number (shown after sakha selection) — required for every
    # membership type except Darshaka (see module docstring).
    claimed_local_sakha_number: str | None = Field(
        None, max_length=20,
        description="Local Sakha Number — required for all membership types except Darshaka",
    )

    # Existing Parichaya Patra / Anumati Patra document number, for a
    # registrant who already holds one (legacy member). Optional — omit to
    # have a new one auto-generated at approval time for the current FY.
    claimed_credential_document_number: str | None = Field(
        None, max_length=30,
        description="Existing Parichaya/Anumati Patra number, if already issued. Omit to auto-generate a new one at approval.",
    )

    # Darshak attendance at another Sangha (optional)
    is_attending_as_darshak: bool = Field(
        default=False,
        description="True if user is attending another Sangha as a Darshak",
    )
    darshak_organization_pk: str | None = Field(
        None, description="UUID of Sakha the user is attending as Darshak",
    )
    darshak_local_sakha_number: str | None = Field(
        None, max_length=20,
        description="Local Sakha Number at the darshak (attending) Sakha — required when is_attending_as_darshak is True",
    )

    # Password
    password: str = Field(..., min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    """Successful registration response."""
    person_pk: str
    person_id: str
    person_name: str
    message: str


from datetime import date  # noqa: E402 — needed for forward ref resolution


# ── POST /api/v1/register/check-duplicate ──────────────────────────────
# POST-with-body, not GET-with-query-params (changed 2026-10-05): mobile
# number and email are PII, and a GET's query string is part of the URL —
# it lands in plaintext in uvicorn's access log, any reverse proxy in
# front of it, and Render's own request logs, with no way to suppress
# just this route. A POST body never appears in the request line, so it
# doesn't get logged by default. This is a live pre-submit check (not a
# bookmarkable/shareable URL), so there's no UX reason it needed to be a
# GET in the first place.

class CheckDuplicateRequest(BaseModel):
    mobile_number: str | None = Field(None, description="Mobile number to check")
    country_phone_code: str | None = Field(None, description="Country phone code")
    email: str | None = Field(None, description="Email to check")


@router.post("/check-duplicate")
def check_duplicate(
    body: CheckDuplicateRequest,
    conn=Depends(get_connection),
):
    """
    Check if a mobile number or email already exists in person table.

    Returns { mobile_exists: bool, email_exists: bool } so the
    registration form can warn the user on Step 1 before they fill
    the entire form.
    """
    result = {"mobile_exists": False, "email_exists": False}

    with conn.cursor() as cur:
        if body.mobile_number and body.country_phone_code:
            cur.execute(
                """
                SELECT 1 FROM nss.person
                WHERE country_phone_code = %s
                  AND mobile_number = %s
                  AND is_active = TRUE
                LIMIT 1
                """,
                (body.country_phone_code, body.mobile_number),
            )
            result["mobile_exists"] = cur.fetchone() is not None

        if body.email:
            cur.execute(
                """
                SELECT 1 FROM nss.person
                WHERE LOWER(email) = LOWER(%s)
                  AND is_active = TRUE
                LIMIT 1
                """,
                (body.email,),
            )
            result["email_exists"] = cur.fetchone() is not None

    return result


# ── "Previously registered" flow ────────────────────────────────────────
# A person who registered with has_membership=False has a person record
# and NOTHING else — no account, no claim (user decision, 2026-10-06; see
# module docstring). These two endpoints let that same person come back
# later and submit a membership claim without re-entering their personal
# details, creating the user_account + registration_claim only now.
#
# Both are public (no auth — the registrant has no JWT, same as the rest
# of /register/*), so identity is verified with person_id + date_of_birth
# instead: not secret, but not guessable from a person_id alone, and it's
# exactly what the registrant already knows from their own registration.

class LookupExistingRequest(BaseModel):
    person_id: str = Field(..., min_length=1, max_length=30)
    date_of_birth: "date" = Field(
        ..., description="Date of birth as given at original registration"
    )


class LookupExistingResponse(BaseModel):
    person_pk: str
    person_id: str
    person_name: str


def _verify_existing_person_for_claim(cur, person_id: str, dob) -> tuple:
    """
    Shared identity + eligibility check for the lookup and claim endpoints.

    Returns (person_pk, person_id, person_name, existing_account) where
    *existing_account* is None, or (user_account_pk, is_active) of a row that
    claim_existing() must REUSE (uq_user_account_person is a plain UNIQUE, so
    a second INSERT for the same person always fails):
      - an active PENDING_APPROVAL account whose claim was REJECTED
        (AUTH-BR-093: the rejected claimant keeps the person + account and
        "may submit a new registration_claim"), or
      - a soft-deleted account (reactivated, like POST /admin/users does).

    Raises HTTPException if the person_id/DOB pair doesn't match, or if this
    person already has a live account, a pending claim, or an active Sangha
    Sevi — all of which mean this flow no longer applies to them. The 409s
    are only reachable AFTER person_id + DOB both match, i.e. they disclose
    nothing to a caller who has not already proven the pair.
    """
    cur.execute(
        """
        SELECT person_pk, person_id,
               CONCAT_WS(' ', first_name, middle_name, last_name)
        FROM nss.person
        WHERE person_id = %s AND date_of_birth = %s AND is_active = TRUE
        """,
        (person_id.strip(), dob),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching registration found. Check your Person ID and date of birth.",
        )
    person_pk, resolved_person_id, person_name = row

    cur.execute(
        """
        SELECT 1 FROM nss.registration_claim
        WHERE person_pk = %s AND claim_status = 'PENDING' AND is_active = TRUE
        LIMIT 1
        """,
        (str(person_pk),),
    )
    if cur.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A membership claim is already pending approval for this Person ID.",
        )

    cur.execute(
        "SELECT user_account_pk, is_active, account_status FROM nss.user_account WHERE person_pk = %s",
        (str(person_pk),),
    )
    account = cur.fetchone()
    existing_account = None
    if account is not None:
        ua_pk, ua_active, ua_status = account
        if not ua_active:
            existing_account = (ua_pk, False)
        else:
            # AUTH-BR-093: only a PENDING_APPROVAL account that has a REJECTED
            # claim (and, checked above, no pending one) may resubmit.
            cur.execute(
                """
                SELECT 1 FROM nss.registration_claim
                WHERE user_account_pk = %s AND claim_status = 'REJECTED' AND is_active = TRUE
                LIMIT 1
                """,
                (str(ua_pk),),
            )
            if ua_status == "PENDING_APPROVAL" and cur.fetchone() is not None:
                existing_account = (ua_pk, True)
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This Person ID already has a registered account. Use the login page, or Forgot Password.",
                )

    cur.execute(
        "SELECT 1 FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE LIMIT 1",
        (str(person_pk),),
    )
    if cur.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Person ID is already a Sangha Sevi. Please log in.",
        )

    return person_pk, resolved_person_id, person_name, existing_account


@router.post("/lookup-existing", response_model=LookupExistingResponse)
def lookup_existing(
    body: LookupExistingRequest,
    conn=Depends(get_connection),
) -> LookupExistingResponse:
    """
    Verify a previously-registered, SS-less person by Person ID + DOB, so
    the "Already registered? Add membership" flow can skip straight to the
    membership step instead of re-asking for personal details.
    """
    with conn.cursor() as cur:
        person_pk, person_id, person_name, _ = _verify_existing_person_for_claim(
            cur, body.person_id, body.date_of_birth
        )
    return LookupExistingResponse(
        person_pk=str(person_pk),
        person_id=person_id,
        person_name=person_name or "",
    )


class ClaimExistingRequest(BaseModel):
    person_id: str = Field(..., min_length=1, max_length=30)
    date_of_birth: "date" = Field(
        ..., description="Re-verified server-side — this endpoint is unauthenticated"
    )

    membership_type_master_data_pk: str = Field(..., min_length=1)
    organization_pk: str = Field(..., min_length=1)
    joining_date: Optional["date"] = None
    claimed_local_sakha_number: str | None = Field(None, max_length=20)
    claimed_credential_document_number: str | None = Field(None, max_length=30)
    is_attending_as_darshak: bool = False
    darshak_organization_pk: str | None = None
    darshak_local_sakha_number: str | None = Field(None, max_length=20)

    password: str = Field(..., min_length=8, max_length=128)


@router.post("/claim", response_model=RegisterResponse, status_code=201)
def claim_existing(
    body: ClaimExistingRequest,
    conn=Depends(get_write_connection),
) -> RegisterResponse:
    """
    Submit a membership claim for an already-registered person who has no
    Sangha Sevi yet — creates the user_account + registration_claim that
    POST /register skipped when they originally registered without
    membership details. Mirrors the has_membership branch of register().
    """
    violations = validate_password_policy(body.password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=violations,
        )

    if body.is_attending_as_darshak:
        if not body.darshak_organization_pk:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="darshak_organization_pk is required when is_attending_as_darshak is True.",
            )
        if not body.darshak_local_sakha_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="darshak_local_sakha_number is required when is_attending_as_darshak is True.",
            )

    with conn.cursor() as cur:
        person_pk, person_id, person_name, existing_account = _verify_existing_person_for_claim(
            cur, body.person_id, body.date_of_birth
        )

        # AUTH-BR-086: Local Sakha Number and Parichaya/Anumati Patra Number
        # are required for every membership type EXCEPT Darshaka — a legacy
        # member migrating a known paper-register number may still enter it
        # here (optional), but a brand-new Darshaka applicant has none to
        # self-report; both numbers are system-generated at admin approval
        # instead.
        if not is_probationary_membership_type(cur, body.membership_type_master_data_pk):
            if not body.claimed_local_sakha_number:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Local Sakha Number is required.",
                )
            if not body.claimed_credential_document_number or not body.claimed_credential_document_number.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="claimed_credential_document_number (Parichaya Patra Number) is required for this membership type.",
                )

        require_sakha_organization(cur, body.organization_pk)

        password_hash_val = hash_password(body.password)
        password_expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.PASSWORD_EXPIRY_DAYS
        )

        if existing_account is not None:
            # Reuse the one-and-only account row for this person
            # (uq_user_account_person): AUTH-BR-093 resubmission after a
            # rejection, or a soft-deleted account — reactivated in place,
            # same shape as POST /admin/users' reactivation branch.
            user_account_pk = existing_account[0]
            cur.execute(
                """
                UPDATE nss.user_account
                SET is_active = TRUE,
                    deleted_at = NULL,
                    account_status = 'PENDING_APPROVAL',
                    password_hash = %s,
                    force_password_change = FALSE,
                    password_changed_at = NOW(),
                    password_expires_at = %s,
                    failed_login_attempts = 0,
                    locked_until = NULL,
                    last_failed_login_at = NULL,
                    updated_at = NOW()
                WHERE user_account_pk = %s
                """,
                (password_hash_val, password_expires_at, str(user_account_pk)),
            )
            log_audit(
                cur,
                action="REACTIVATE" if not existing_account[1] else "UPDATE",
                table_name="user_account",
                record_pk=str(user_account_pk),
                actor_user_account_pk=str(user_account_pk),
                module="registration",
                summary="Reused user account for a resubmitted membership claim",
            )
        else:
            cur.execute(
                """
                INSERT INTO nss.user_account (
                    person_pk,
                    password_hash,
                    account_status,
                    force_password_change,
                    password_expires_at
                ) VALUES (%s, %s, 'PENDING_APPROVAL', FALSE, %s)
                RETURNING user_account_pk
                """,
                (str(person_pk), password_hash_val, password_expires_at),
            )
            user_account_pk = cur.fetchone()[0]

            log_audit(
                cur,
                action="CREATE",
                table_name="user_account",
                record_pk=str(user_account_pk),
                actor_user_account_pk=str(user_account_pk),
                module="registration",
                summary="Created user account via previously-registered membership claim",
            )

        record_password_history(cur, str(user_account_pk), password_hash_val, "INITIAL")

        cur.execute(
            """
            INSERT INTO nss.registration_claim (
                user_account_pk,
                person_pk,
                claimed_organization_pk,
                claimed_membership_type_master_data_pk,
                claimed_local_sakha_number,
                claimed_credential_document_number,
                claimed_joining_date,
                darshak_organization_pk,
                darshak_local_sakha_number,
                claim_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
            RETURNING registration_claim_pk
            """,
            (
                str(user_account_pk),
                str(person_pk),
                body.organization_pk,
                body.membership_type_master_data_pk,
                body.claimed_local_sakha_number,
                body.claimed_credential_document_number,
                body.joining_date,
                body.darshak_organization_pk if body.is_attending_as_darshak else None,
                body.darshak_local_sakha_number if body.is_attending_as_darshak else None,
            ),
        )
        claim_pk = cur.fetchone()[0]

        log_audit(
            cur,
            action="CREATE",
            table_name="registration_claim",
            record_pk=str(claim_pk),
            actor_user_account_pk=str(user_account_pk),
            module="registration",
            summary=f"Submitted registration claim for {body.organization_pk}",
        )

    return RegisterResponse(
        person_pk=str(person_pk),
        person_id=person_id,
        person_name=person_name or "",
        message=(
            "Membership claim submitted. Your registration is pending approval "
            "by your Sakha administrator. You will be able to log in once approved."
        ),
    )


# ── GET /api/v1/register/reference-data ────────────────────────────────
# Public, no auth (see check_duplicate above for the same pattern) — the
# person filling out this form has no JWT yet, that's the whole point of
# self-registration. Foundation's countries/master-data and Organization's
# Sakha list are otherwise gated behind require_permission() now (Tier 5),
# which silently broke every dropdown on this page. Reuses the exact same
# query functions those authenticated endpoints call (fetch_countries()
# etc., factored out of foundation.py/organization.py for this purpose) —
# same SQL, same response shape, just a second, unauthenticated door onto
# it — so there's no duplicated logic to drift out of sync.
#
# Bundles every reference list the registration page needs on load into
# one response instead of 6 separate round trips (countries + 4 master-data
# categories + Sakhas). States/districts stay separate below since they're
# cascading and depend on what the operator picks.

class RegisterReferenceDataResponse(BaseModel):
    countries: list[CountryResponse]
    genders: list[MasterDataResponse]
    marital_statuses: list[MasterDataResponse]
    blood_groups: list[MasterDataResponse]
    membership_types: list[MasterDataResponse]
    sakhas: list[OrganizationResponse]


@router.get("/reference-data", response_model=RegisterReferenceDataResponse)
def get_register_reference_data(
    conn=Depends(get_connection),
) -> RegisterReferenceDataResponse:
    """Everything the registration page's dropdowns need, in one call."""
    with conn.cursor() as cur:
        countries = fetch_countries(cur)
        genders = fetch_master_data(cur, category_code="GENDER")
        marital_statuses = fetch_master_data(cur, category_code="MARITAL_STATUS")
        blood_groups = fetch_master_data(cur, category_code="BLOOD_GROUP")
        membership_types = fetch_master_data(cur, category_code="MEMBERSHIP_TYPE")
        sakhas = fetch_organizations(cur, type_code="SAKHA_SANGHA", limit=500)
    return RegisterReferenceDataResponse(
        countries=countries,
        genders=genders,
        marital_statuses=marital_statuses,
        blood_groups=blood_groups,
        membership_types=membership_types,
        sakhas=sakhas,
    )


@router.get("/countries", response_model=list[CountryResponse])
def get_register_countries(
    conn=Depends(get_connection),
) -> list[CountryResponse]:
    """
    Public countries lookup for location cascades. Unauthenticated like the
    rest of /register/*, so member-facing authenticated screens that must not
    require the admin-only FOUNDATION_VIEW permission (e.g. the dashboard's
    Create-Family Sakha picker) can reuse it instead of /foundation/countries.
    """
    with conn.cursor() as cur:
        return fetch_countries(cur)


@router.get("/states", response_model=list[StateResponse])
def get_register_states(
    country_pk: UUID | None = Query(None, description="Filter by parent country"),
    conn=Depends(get_connection),
) -> list[StateResponse]:
    """Public states lookup for the registration page's location cascade."""
    with conn.cursor() as cur:
        return fetch_states(cur, country_pk)


@router.get("/districts", response_model=list[DistrictResponse])
def get_register_districts(
    state_pk: UUID | None = Query(None, description="Filter by parent state"),
    conn=Depends(get_connection),
) -> list[DistrictResponse]:
    """Public districts lookup for the registration page's location cascade."""
    with conn.cursor() as cur:
        return fetch_districts(cur, state_pk)


@router.get("/cities", response_model=list[CityVillageResponse])
def get_register_cities(
    district_pk: UUID | None = Query(None, description="Filter by parent district"),
    conn=Depends(get_connection),
) -> list[CityVillageResponse]:
    """
    Public cities/villages lookup for the registration page's location
    cascade — offered as suggestions alongside the free-text
    city_village_name field, not a hard-restricted list: many villages
    (every state except Odisha, nationwide gap flagged 2026-10-01) have no
    district association yet, and resolve_or_create_city_village() already
    creates a new row on the fly for a name typed that isn't on file.
    """
    with conn.cursor() as cur:
        return fetch_cities(cur, district_pk)


@router.get("/postal-codes", response_model=list[PostalCodeResponse])
def get_register_postal_codes(
    state_pk: UUID | None = Query(None, description="Filter by state"),
    country_pk: UUID | None = Query(None, description="Filter by country"),
    conn=Depends(get_connection),
) -> list[PostalCodeResponse]:
    """Public postal-codes lookup for the registration page's location cascade."""
    with conn.cursor() as cur:
        return fetch_postal_codes(cur, state_pk, country_pk)


@router.get("/post-offices", response_model=list[PostOfficeResponse])
def get_register_post_offices(
    postal_code_pk: UUID = Query(..., description="PIN whose post offices to list"),
    conn=Depends(get_connection),
) -> list[PostOfficeResponse]:
    """
    Public post-offices lookup for the registration page's location
    cascade — offered as suggestions alongside the Post Office field, not
    a hard-restricted list: resolve_or_create_post_office() creates a new
    row on the fly for a name typed that isn't on file (same pattern as
    cities/postal codes above).
    """
    with conn.cursor() as cur:
        return fetch_post_offices(cur, postal_code_pk)


@router.get("/sakhas", response_model=list[OrganizationResponse])
def get_register_sakhas(
    country_pk: UUID | None = Query(None, description="Filter by country"),
    state_pk: UUID | None = Query(None, description="Filter by state"),
    district_pk: UUID | None = Query(None, description="Filter by district"),
    postal_code_pk: UUID | None = Query(None, description="Filter by postal code"),
    conn=Depends(get_connection),
) -> list[OrganizationResponse]:
    """
    Public "find my Sakha" lookup for the registration page.

    SOL-ARCH-010 Amendment (2026-10-01): narrows the Sakha Sangha list by
    the same country/state/district/postal-code the registrant already picked
    for their address cascade (via /register/states, /districts, /postal-codes
    above), instead of making them scroll an unfiltered list of up to 500
    Sakhas. Falls back to the full list when no geography is selected yet,
    same as the existing `sakhas` array returned by /reference-data.
    """
    with conn.cursor() as cur:
        return fetch_organizations(
            cur, type_code="SAKHA_SANGHA", country_pk=country_pk, state_pk=state_pk,
            district_pk=district_pk, postal_code_pk=postal_code_pk, limit=500,
        )


# ── POST /api/v1/register ──────────────────────────────────────────────

@router.post("", response_model=RegisterResponse, status_code=201)
def register(
    body: RegisterRequest,
    conn=Depends(get_write_connection),
) -> RegisterResponse:
    """
    Self-register as a new person.

    Creates person + user_account(PENDING_APPROVAL) in a single transaction.
    If membership details provided, stores a registration_claim for admin review.
    No sangha_sevi or membership records created at this stage.
    """

    # ── 1. Validate password policy ─────────────────────────────────────
    violations = validate_password_policy(body.password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=violations,
        )

    # ── 2. Validate contact (mobile OR email required) ──────────────────
    if not body.mobile_number and not body.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one of mobile_number or email is required.",
        )
    # MBR-CONTACT-01/02: country-wise mobile + email format validation.
    validate_mobile(body.country_phone_code, body.mobile_number)
    validate_email(body.email)

    # ── 3. Validate membership claim fields if has_membership ───────────
    if body.has_membership:
        missing = []
        if not body.membership_type_master_data_pk:
            missing.append("membership_type_master_data_pk")
        if not body.organization_pk:
            missing.append("organization_pk")
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Membership claim fields required: {', '.join(missing)}",
            )

    # ── 3b. Validate darshak attendance fields ──────────────────────────
    if body.is_attending_as_darshak:
        if not body.darshak_organization_pk:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="darshak_organization_pk is required when is_attending_as_darshak is True.",
            )
        if not body.darshak_local_sakha_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="darshak_local_sakha_number is required when is_attending_as_darshak is True.",
            )

    # ── 3c. Validate address fields (user decision, 2026-10-03) ─────────
    # Pydantic's `...` only guards presence/type, not a blank string — a UI
    # bug or a bare {"country_pk": ""} would otherwise sail through.
    missing_address = []
    if not body.country_pk or not body.country_pk.strip():
        missing_address.append("country_pk")
    if not body.state_pk or not body.state_pk.strip():
        missing_address.append("state_pk")
    if not body.district_pk or not body.district_pk.strip():
        missing_address.append("district_pk")
    if not body.city_village_name or not body.city_village_name.strip():
        missing_address.append("city_village_name")
    if not body.postal_code_value or not body.postal_code_value.strip():
        missing_address.append("postal_code_value")
    if not body.address_line_1 or not body.address_line_1.strip():
        missing_address.append("address_line_1")
    if missing_address:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Address fields required: {', '.join(missing_address)}",
        )

    with conn.cursor() as cur:

        # ── 3d. Parichaya Patra Number is mandatory for every membership
        # type except Darshaka (PROBATIONARY) — Darshak members hold an
        # Anumati Patra issued later, not claimed at registration.
        if body.has_membership and not is_probationary_membership_type(cur, body.membership_type_master_data_pk):
            if not body.claimed_credential_document_number or not body.claimed_credential_document_number.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="claimed_credential_document_number (Parichaya Patra Number) is required for this membership type.",
                )

        # ── 4. Check duplicate mobile + email ──────────────────────────
        check_duplicate_contact(
            cur,
            mobile_number=body.mobile_number,
            country_phone_code=body.country_phone_code,
            email=body.email,
        )

        # ── 5a. MBR-038A: claimed membership org must be a Sakha Sangha ──
        #   Enforce Sakha-only selection at submission time (fail fast with a
        #   clean 422) rather than letting a non-Sakha claim reach approval.
        #   Mirrors the DB trigger and the claim_approval / admin guards.
        if body.has_membership and body.organization_pk:
            require_sakha_organization(cur, body.organization_pk)

        # ── 5b. Validate Local Sakha Number requirement (AUTH-BR-086) ────
        #   Required for every membership type except Darshaka (PROBATIONARY)
        #   — a legacy member migrating a known paper-register number may
        #   still enter it here (optional), but a brand-new Darshaka
        #   applicant has none to self-report; the number is
        #   system-generated at admin approval instead.
        if (
            body.has_membership
            and not is_probationary_membership_type(cur, body.membership_type_master_data_pk)
            and not body.claimed_local_sakha_number
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Local Sakha Number is required.",
            )

        # ── 6. Generate person_id ───────────────────────────────────────
        person_id = next_id(cur, "PERSON")

        # ── 6a. Pre-generate person_pk (2026-10-21, Registration-Time
        # Geography Creation) ───────────────────────────────────────────
        # person_pk is normally left to the column's gen_random_uuid()
        # DEFAULT and read back via RETURNING after the INSERT (below).
        # Here it is generated client-side INSTEAD, before the person row
        # exists, so it can be threaded into the city_village/postal_code/
        # post_office auto-create calls just below — those genuinely-new
        # geo rows are stamped PENDING + submitted_by_person_pk=<this
        # value> (surfaced later in the submitting person's eventual
        # Sakha's Location-Approvals queue), while the person row itself
        # still gets this exact pk at INSERT time (explicit value instead
        # of the DEFAULT). Ordering is otherwise unchanged.
        person_pk = str(uuid4())

        # ── 7. Insert person ────────────────────────────────────────────
        cur.execute(
            """
            INSERT INTO nss.person (
                person_pk,
                person_id,
                first_name,
                middle_name,
                last_name,
                date_of_birth,
                gender_master_data_pk,
                marital_status_master_data_pk,
                blood_group_master_data_pk,
                country_phone_code,
                mobile_number,
                email,
                country_pk,
                state_pk,
                district_pk,
                city_village_pk,
                postal_code_pk
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING person_pk
            """,
            (
                person_pk,
                person_id,
                body.first_name.strip().title(),
                body.middle_name.strip().title() if body.middle_name else None,
                body.last_name.strip().title() if body.last_name else None,
                body.date_of_birth,
                body.gender_master_data_pk,
                body.marital_status_master_data_pk,
                body.blood_group_master_data_pk,
                body.country_phone_code,
                body.mobile_number,
                body.email.strip().lower() if body.email else None,
                body.country_pk or None,
                body.state_pk or None,
                body.district_pk or None,
                None,  # city_village_pk — set below, once the geo rows exist
                None,  # postal_code_pk — set below
            ),
        )
        person_pk = cur.fetchone()[0]

        # ── 7a. Resolve geography AFTER the person row exists ──────────
        # Newly created city_village/postal_code/post_office rows carry
        # submitted_by_person_pk=<person_pk> with an immediate FK to
        # nss.person (16_foundation_audit_fk.sql), so the person row must
        # already be inserted when they are created; the person's own
        # city_village_pk/postal_code_pk are then filled in by the UPDATE.
        # ── 6b. Resolve postal code from text value (lookup/create) ────
        # Resolved BEFORE city_village (2026-10-21): the PIN disambiguates
        # the village lookup. Village names repeat within a district (e.g.
        # 18 distinct "Hosahalli" villages in Tumakuru, one per PIN), so
        # resolving the village on (name, district) alone would bind the
        # registrant to an arbitrary one — potentially carrying a PIN that
        # contradicts the one they just typed.
        resolved_postal_code_pk = body.postal_code_pk or None
        if body.postal_code_value and body.state_pk and body.country_pk:
            pc_val = body.postal_code_value.strip()
            if pc_val:
                resolved_postal_code_pk = resolve_or_create_postal_code(
                    cur, pc_val, body.state_pk, body.country_pk,
                    pending_submitter_person_pk=person_pk,
                )

        # ── 6c. Resolve city_village_name → city_village_pk ────────────
        city_village_pk = None
        if body.city_village_name and body.district_pk:
            cv_name = body.city_village_name.strip()
            if cv_name:
                city_village_pk = resolve_or_create_city_village(
                    cur, cv_name, body.district_pk,
                    pending_submitter_person_pk=person_pk,
                    postal_code_pk=resolved_postal_code_pk,
                )

        # ── 6d. Resolve post_office_name → post_office_pk (optional) ───
        # Scoped to the resolved PIN — a post office cannot exist without
        # one, so this is skipped entirely until postal_code_pk resolves.
        resolved_post_office_pk = None
        if body.post_office_name and resolved_postal_code_pk:
            po_name = body.post_office_name.strip()
            if po_name:
                resolved_post_office_pk = resolve_or_create_post_office(
                    cur, po_name, resolved_postal_code_pk,
                    pending_submitter_person_pk=person_pk,
                )

        if city_village_pk or resolved_postal_code_pk:
            cur.execute(
                """
                UPDATE nss.person
                   SET city_village_pk = %s, postal_code_pk = %s
                 WHERE person_pk = %s
                """,
                (city_village_pk, resolved_postal_code_pk, person_pk),
            )

        log_audit(
            cur,
            action="CREATE",
            table_name="person",
            record_pk=str(person_pk),
            module="registration",
            summary=f"Self-registered person {body.first_name} {body.last_name}",
        )

        # ── 7b. Create the person_address row (user decision, 2026-10-03) ──
        # The geography picked above (country/state/district/city/PIN) is
        # stored on person for cascade/lookup purposes, but the FULL postal
        # address — what actually goes on an envelope — lives on a separate
        # person_address row, which nothing wrote until now (the Address
        # card on the dashboard was always empty). address_type defaults to
        # PERMANENT: registration asks for exactly one address.
        permanent_address_type_pk = get_master_data_pk(
            cur, "ADDRESS_TYPE", "PERMANENT",
        )
        cur.execute(
            """
            INSERT INTO nss.person_address (
                person_pk,
                address_type_master_data_pk,
                address_line_1,
                address_line_2,
                landmark,
                city_village_pk,
                postal_code_pk,
                post_office_pk,
                is_primary
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING person_address_pk
            """,
            (
                str(person_pk),
                permanent_address_type_pk,
                body.address_line_1.strip(),
                body.address_line_2.strip() if body.address_line_2 else None,
                body.landmark.strip() if body.landmark else None,
                city_village_pk,
                resolved_postal_code_pk,
                resolved_post_office_pk,
            ),
        )
        person_address_pk = cur.fetchone()[0]
        log_audit(
            cur,
            action="CREATE",
            table_name="person_address",
            record_pk=str(person_address_pk),
            module="registration",
            summary=f"Recorded permanent address for {body.first_name} {body.last_name}",
        )

        # ── 8-10. Account + claim — ONLY when membership is claimed ──────
        # A user_account must never be created for a person with no path to
        # a Sangha Sevi (user decision, 2026-10-06): an account with no SS
        # can never log in (login requires an active sangha_sevi) and has no
        # business showing up in User Accounts / Registration Approvals. A
        # person registering with has_membership=False is recorded as a
        # person only; the password they typed here is never persisted. An
        # admin (or the registrant later, via the "previously registered"
        # flow — POST /register/claim) creates the account+claim when the
        # person actually has membership details to submit.
        account_created = False
        if body.has_membership:
            account_created = True

            # ── 8. Create user_account (PENDING_APPROVAL) ────────────────
            password_hash_val = hash_password(body.password)
            password_expires_at = datetime.now(timezone.utc) + timedelta(
                days=settings.PASSWORD_EXPIRY_DAYS
            )

            cur.execute(
                """
                INSERT INTO nss.user_account (
                    person_pk,
                    password_hash,
                    account_status,
                    force_password_change,
                    password_expires_at
                ) VALUES (%s, %s, 'PENDING_APPROVAL', FALSE, %s)
                RETURNING user_account_pk
                """,
                (str(person_pk), password_hash_val, password_expires_at),
            )
            user_account_pk = cur.fetchone()[0]

            log_audit(
                cur,
                action="CREATE",
                table_name="user_account",
                record_pk=str(user_account_pk),
                actor_user_account_pk=str(user_account_pk),
                module="registration",
                summary="Created user account via self-registration",
            )

            # ── 9. Record initial password in history ────────────────────
            record_password_history(cur, str(user_account_pk), password_hash_val, "INITIAL")

            # ── 10. Insert registration_claim ─────────────────────────────
            cur.execute(
                """
                INSERT INTO nss.registration_claim (
                    user_account_pk,
                    person_pk,
                    claimed_organization_pk,
                    claimed_membership_type_master_data_pk,
                    claimed_local_sakha_number,
                    claimed_credential_document_number,
                    claimed_joining_date,
                    darshak_organization_pk,
                    darshak_local_sakha_number,
                    claim_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
                RETURNING registration_claim_pk
                """,
                (
                    str(user_account_pk),
                    str(person_pk),
                    body.organization_pk,
                    body.membership_type_master_data_pk,
                    body.claimed_local_sakha_number,
                    body.claimed_credential_document_number,
                    body.joining_date,
                    body.darshak_organization_pk if body.is_attending_as_darshak else None,
                    body.darshak_local_sakha_number if body.is_attending_as_darshak else None,
                ),
            )
            claim_pk = cur.fetchone()[0]

            log_audit(
                cur,
                action="CREATE",
                table_name="registration_claim",
                record_pk=str(claim_pk),
                actor_user_account_pk=str(user_account_pk),
                module="registration",
                summary=f"Submitted registration claim for {body.organization_pk}",
            )

    # ── Build response ──────────────────────────────────────────────────
    name_parts = [body.first_name.strip().title()]
    if body.middle_name:
        name_parts.append(body.middle_name.strip().title())
    if body.last_name:
        name_parts.append(body.last_name.strip().title())
    person_name = " ".join(name_parts)

    return RegisterResponse(
        person_pk=str(person_pk),
        person_id=person_id,
        person_name=person_name,
        message=(
            "Registration successful. Your registration is pending approval "
            "by your Sakha administrator. You will be able to log in once approved."
        ) if account_created else (
            "Registration successful. Your Person ID is "
            f"{person_id} — keep it safe. No login account was created yet "
            "since no membership details were submitted. When you're ready to "
            "join a Sakha, use \"Already registered? Add membership\" on the "
            "registration page with this Person ID, or ask your Sakha "
            "administrator to set up your Sangha Sevi record."
        ),
    )
