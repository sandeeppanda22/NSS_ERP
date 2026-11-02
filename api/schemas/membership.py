"""
Pydantic response models for the Membership API (Tier 4).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Three-tier identity model:
  - Sangha Sevi ID (SS1) — NSS-wide, permanent, on sangha_sevi
  - ERP Number / Local Sakha Number (ESS1192) — Sakha-scoped,
    auto-generated, on membership_sakha_affiliation
  - Kendra Number (345/2026/2027) — Kendra-wide, annual,
    on parichaya_patra.document_number

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class MemberResponse(BaseModel):
    """
    Sangha Sevi (member) with resolved person, type, status, and org context.

    Includes person name, membership type name, status name, and
    organization name via JOINs. Also includes the current active
    local_sakha_erp_id from membership_sakha_affiliation.
    """

    # Identity
    sangha_sevi_pk: UUID
    sangha_sevi_id: str

    # Person (resolved)
    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    country_phone_code: str | None
    mobile_number: str | None
    email: str | None

    # Membership type (resolved from master_data)
    membership_type_master_data_pk: UUID
    membership_type_code: str
    membership_type_name: str

    # Status (resolved from master_data — unified STATUS)
    membership_status_master_data_pk: UUID
    status_code: str
    status_name: str

    # Current organization (resolved)
    organization_pk: UUID
    organization_name: str
    organization_code: str | None

    # Current Local Sakha ERP ID (from active affiliation)
    local_sakha_erp_id: str | None

    # Cross-Sakha darshak attendance (SOL-MEM-006) — a second, simultaneous
    # active membership_sakha_affiliation row at a different org than the
    # home organization above. None when the member isn't attending
    # anywhere else as a Darshak.
    darshak_organization_pk: UUID | None = None
    darshak_organization_name: str | None = None
    darshak_local_sakha_number: str | None = None

    # Dates
    # joining_date is nullable (MBR-047): the Sangha Joining Date is optional
    # to capture, and NULL means "not recorded". Typing this as a required
    # `date` made the whole member-list response 500 on any such row.
    joining_date: date | None = None
    renewal_due_date: date | None

    remarks: str | None
    is_active: bool


class SakhaAffiliationResponse(BaseModel):
    """
    Sakha affiliation record — authoritative source of Local Sakha ERP ID.
    """

    membership_sakha_affiliation_pk: UUID
    sangha_sevi_pk: UUID

    # Organization (resolved)
    organization_pk: UUID
    organization_name: str
    organization_code: str | None

    local_sakha_erp_id: str
    effective_from: date
    effective_to: date | None
    affiliation_status: str
    source_event_type: str
    legacy_sakha_number: str | None


class ParichayaPatraResponse(BaseModel):
    """
    Parichaya Patra (Identity Card) with snapshot context.

    document_number = Kendra number (e.g., 345/2026/2027).
    affiliated_organization_name and local_sakha_erp_id are
    point-in-time snapshots of what was printed on the card.
    """

    parichaya_patra_pk: UUID
    sangha_sevi_pk: UUID
    document_number: str
    issue_date: date
    valid_from: date
    valid_to: date
    status: str

    # Snapshot: Sakha at issuance (resolved)
    affiliated_organization_pk: UUID | None
    affiliated_organization_name: str | None
    affiliated_organization_code: str | None

    # Snapshot: Local Sakha number at issuance
    local_sakha_erp_id: str | None

    document_reference: str | None
    remarks: str | None


class AnumatiPatraResponse(BaseModel):
    """
    Anumati Patra (Probationary Member Credential).
    """

    anumati_patra_pk: UUID
    sangha_sevi_pk: UUID
    document_number: str
    issue_date: date
    valid_from: date
    valid_to: date
    status: str
    document_reference: str | None
    remarks: str | None


class JourneyEventResponse(BaseModel):
    """
    Membership lifecycle journey event.
    """

    membership_journey_event_pk: UUID
    sangha_sevi_pk: UUID
    event_type: str
    event_date: date
    event_reference: str | None
    remarks: str | None


class MemberListResponse(BaseModel):
    """
    Envelope for /members and /search list results.

    `total` is the true row count matching the filters — independent
    of `len(members)`, which is capped by MAX_LIMIT (or, for /search,
    the search-specific cap). Callers MUST compare `total` to
    `len(members)` to detect truncation; the array alone cannot
    reveal whether more rows exist.
    """

    members: list[MemberResponse]
    total: int


class MemberDirectoryResponse(BaseModel):
    """
    One row of the general-member-facing Member Directory (GET
    /membership/directory, any logged-in user — not admin-only).

    Deliberately NOT MemberResponse: a general member sees a smaller,
    owner-approved field set (2026-10-27) — full name, Sakha affiliation,
    membership type/status, city/district, and contact details (phone,
    mobile, email). It excludes anything MemberResponse carries that
    wasn't approved for this audience (e.g. darshak cross-Sakha
    attendance, local_sakha_erp_id, master-data PKs) and adds the two
    location fields MemberResponse has no use for (district_name,
    city_village_name, from person.district_pk/city_village_pk —
    ORG-BR-099-adjacent "quick reference" location, not person_address).
    membership_type_code/status_code are included (unlike MemberResponse's
    *_master_data_pk) only so the frontend can reuse NSS.typeBadgeClass/
    statusBadgeClass — the same badge convention as every other member
    list in the app — rather than inventing a name-keyed badge map.
    photo_document_master_pk is carried through for forward
    compatibility; no document-serving endpoint renders it yet.

    position_code/position_name (owner ask 2026-10-27): the member's
    current PRESIDENT or SECRETARY seat, if any, on ANY governance body
    (Sakha GB, Mahila PM, Advisory Board, ...) — deliberately only these
    two position codes, not every office a member might hold, per the
    owner's "president and secretary only" ask. None/None when the
    member holds neither. A member holding both somehow (not possible
    today — one person, one Sakha, one GB) would show PRESIDENT first
    (position_master.display_order).

    sangha_sevi_pk (added 2026-10-27): the internal PK, needed by callers
    that must act on a specific member afterwards (e.g. attendance
    marking posts sangha_sevi_pk, not the business ID) — not itself
    sensitive, unlike the fields deliberately excluded above.
    """

    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    photo_document_master_pk: UUID | None
    position_code: str | None
    position_name: str | None

    organization_pk: UUID
    organization_name: str
    local_sakha_erp_id: str | None
    membership_type_code: str
    membership_type_name: str
    status_code: str
    status_name: str

    district_name: str | None
    city_village_name: str | None

    country_phone_code: str | None
    mobile_number: str | None
    email: str | None


class MemberDirectoryListResponse(BaseModel):
    """Envelope for /membership/directory — same total/len(members) contract as MemberListResponse."""

    members: list[MemberDirectoryResponse]
    total: int


class OrgDarshakSummaryResponse(BaseModel):
    """
    Darshak (probationary + cross-Sakha attendance) summary for one
    organization — used by the Sakha/Kendra "Darshak" dashboard card
    (docs/03_Solution/ui/mockups/03_sakha_dashboard.html,
    02_kendra_dashboard.html).
    """

    home_probationary_count: int
    attending_from_other_sakha_count: int
