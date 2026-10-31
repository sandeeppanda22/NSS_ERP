"""
Pydantic response models for the Person API (Tier 3).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Sensitive fields excluded per PER-BR-081:
  - aadhaar_encrypted (BYTEA)  — never exposed
  - aadhaar_hash (VARCHAR)     — never exposed
Only aadhaar_last4 is returned for masked display.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class PersonResponse(BaseModel):
    """
    Person with resolved master-data context.

    Includes gender_name, marital_status_name, blood_group_name, and
    emergency_relationship_name via JOINs so the UI can display full
    context in a single API call.
    """

    # Identity
    person_pk: UUID
    person_id: str

    # Demographics
    first_name: str
    middle_name: str | None
    last_name: str | None
    date_of_birth: date | None
    date_of_death: date | None

    # Gender (resolved)
    gender_master_data_pk: UUID | None
    gender_code: str | None
    gender_name: str | None

    # Marital status (resolved)
    marital_status_master_data_pk: UUID | None
    marital_status_code: str | None
    marital_status_name: str | None

    # Blood group (resolved)
    blood_group_master_data_pk: UUID | None
    blood_group_code: str | None
    blood_group_name: str | None

    # Contact
    country_phone_code: str | None
    mobile_number: str | None
    email: str | None

    # Sensitive identity — masked display only
    aadhaar_last4: str | None

    # Photo
    photo_document_master_pk: UUID | None

    # Emergency contact (resolved)
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_relationship_master_data_pk: UUID | None
    emergency_relationship_code: str | None
    emergency_relationship_name: str | None

    # Other
    remarks: str | None

    # Lifecycle
    is_active: bool


class PersonSummaryResponse(BaseModel):
    """
    Lightweight Person summary for list/search results.

    Omits Aadhaar, emergency contact, and photo details to keep
    list payloads compact.
    """

    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    date_of_birth: date | None
    date_of_death: date | None
    gender_code: str | None
    gender_name: str | None
    marital_status_code: str | None
    marital_status_name: str | None
    blood_group_code: str | None
    blood_group_name: str | None
    country_phone_code: str | None
    mobile_number: str | None
    email: str | None
    is_active: bool


class PersonAddressResponse(BaseModel):
    """
    Person address with resolved location context.

    SOL-ARCH-010 Amendment (2026-10-01): the former
    city_village_postal_code_map junction is retired. Location now
    resolves via two independent, nullable direct FKs
    (city_village_pk, postal_code_pk) → district + state + country
    chain, matching the pattern already used by nss.organization.
    """

    person_address_pk: UUID
    person_pk: UUID

    # Address type (resolved)
    address_type_master_data_pk: UUID
    address_type_code: str
    address_type_name: str

    # Address fields
    address_line_1: str
    address_line_2: str | None
    landmark: str | None

    # Location (resolved via direct, independently-nullable FKs)
    city_village_pk: UUID | None
    postal_code_pk: UUID | None
    city_village_name: str | None
    postal_code: str | None
    district_name: str | None
    state_name: str | None
    country_name: str | None

    is_primary: bool
    remarks: str | None
    is_active: bool

    # Added so an address can be round-tripped into the edit form (member
    # address editor) without re-deriving ids from names.
    post_office_pk: UUID | None = None
    post_office_name: str | None = None
    district_pk: UUID | None = None
    state_pk: UUID | None = None
    country_pk: UUID | None = None


class PersonListResponse(BaseModel):
    """
    Envelope for /persons and /search list results.

    `total` is the true row count matching the filters — independent
    of `len(persons)`, which is capped by MAX_LIMIT (or, for /search,
    the search-specific cap). Callers MUST compare `total` to
    `len(persons)` to detect truncation; the array alone cannot
    reveal whether more rows exist.
    """

    persons: list[PersonSummaryResponse]
    total: int


class PersonAddressCreateRequest(BaseModel):
    """
    POST /api/v1/person/persons/{person_pk}/addresses.

    city_village_pk / postal_code_pk / post_office_pk may reference a PENDING
    row the person (or their Sangha Sevi) proposed via the foundation
    ``.../propose`` endpoints; any other PENDING row is refused.
    """

    address_type_master_data_pk: UUID
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: str | None = Field(None, max_length=255)
    landmark: str | None = Field(None, max_length=255)
    city_village_pk: UUID | None = None
    postal_code_pk: UUID | None = None
    post_office_pk: UUID | None = None
    is_primary: bool = False
    remarks: str | None = None


class PersonAddressUpdateRequest(BaseModel):
    """
    PATCH /api/v1/person/persons/{person_pk}/addresses/{person_address_pk}.

    Partial update: only fields present in the request body change. An
    optional field sent explicitly as null (or "" for text) is cleared;
    address_type_master_data_pk, address_line_1 and is_primary cannot be null.
    """

    address_type_master_data_pk: UUID | None = None
    address_line_1: str | None = Field(None, max_length=255)
    address_line_2: str | None = Field(None, max_length=255)
    landmark: str | None = Field(None, max_length=255)
    city_village_pk: UUID | None = None
    postal_code_pk: UUID | None = None
    post_office_pk: UUID | None = None
    is_primary: bool | None = None
    remarks: str | None = None
