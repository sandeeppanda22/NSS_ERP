"""
Pydantic models for the Assets & Property API (Module #22, Tier 6).

Backs api/routers/assets_property.py — properties (immovable), assets
(movable), custodianship history, property statutory records, maintenance
records and document links.

Authority: docs/03_Solution/modules/assets_property/ (SOL-AP-001..005,
business rules AP-001..AP-074), GDR-010.

Conventions:
  - Controlled values (property type, asset type, obligation type, maintenance
    type, custodianship end reason, document relationship) travel as plain
    master_data ``value_code`` strings (``*_code``) and are resolved to a
    master_data PK server-side (unknown code -> 422). They are admin-extendable
    master data, never enums here (GDR-010).
  - ``acquisition_method_code`` (ACQUISITION_METHOD, optional, null clears on
    PATCH) follows the same convention.
  - Lifecycle ``status`` values are the frozen SOL-AP-003 sets.
  - Deliberately NO financial fields anywhere (AP-060/061/063): no cost,
    payment, valuation or depreciation columns.
  - Audit columns are not exposed except where the timestamp is the business
    fact.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _not_future(value: date | None, label: str) -> date | None:
    if value is not None and value > date.today():
        raise ValueError(f"{label} must not be in the future.")
    return value


# ═══════════════════════════════════════════════════════════════════════
# Property (immovable)
# ═══════════════════════════════════════════════════════════════════════

class PropertyCreate(BaseModel):
    """
    Register a property. property_id is minted by the server (PROP<n>) and
    status always starts REGISTERED (SOL-AP-003 §3.1).

    custodian_organization_pk is OPTIONAL only for NSS-wide administrators;
    every scope-bounded admin must name an in-scope custodian (otherwise they
    would create a record nobody in their scope can see or manage). When
    given, custody is opened immediately and — per SOL-AP-003 §3.3 — the
    property advances REGISTERED -> ACTIVE in the same transaction.
    """

    property_name: str = Field(..., min_length=1, max_length=200)
    property_type_code: str = Field(..., description="PROPERTY_TYPE master_data value_code, e.g. 'LAND'")
    location_description: str | None = Field(None, max_length=2000)
    holding_arrangement: str | None = Field(
        None, max_length=2000,
        description="Recorded/legal holder, free text (AP-009/012/013). NOT the custodian.",
    )
    notes: str | None = Field(None, max_length=2000)
    acquired_at: date | None = None
    belongs_to_organization_pk: UUID | None = Field(
        None,
        description="Optional 'belongs to' organization (any active organization type) when it differs from the "
                    "physical custodian, e.g. Mahila Sangha under the supervision of the Kendra Sangha. "
                    "Informational only - no authorization effect. null clears it on PATCH.",
    )
    acquisition_method_code: str | None = Field(
        None,
        description="Optional ACQUISITION_METHOD master_data value_code (how it was acquired, AP-023), e.g. "
                    "'PURCHASE'. Informational only. Unknown code -> 422; null clears it on PATCH.",
    )
    custodian_organization_pk: UUID | None = None
    custodian_effective_from: date | None = Field(
        None, description="Defaults to today; must not be in the future.")

    @field_validator("custodian_effective_from")
    @classmethod
    def _cef(cls, v):
        return _not_future(v, "custodian_effective_from")


class PropertyUpdate(BaseModel):
    """PATCH semantics — only fields present in the body are applied. Identifiers and status are immutable here."""

    property_name: str | None = Field(None, min_length=1, max_length=200)
    property_type_code: str | None = None
    location_description: str | None = Field(None, max_length=2000)
    holding_arrangement: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    acquired_at: date | None = None
    belongs_to_organization_pk: UUID | None = Field(
        None,
        description="Optional 'belongs to' organization (any active organization type) when it differs from the "
                    "physical custodian, e.g. Mahila Sangha under the supervision of the Kendra Sangha. "
                    "Informational only - no authorization effect. null clears it on PATCH.",
    )
    acquisition_method_code: str | None = Field(
        None,
        description="Optional ACQUISITION_METHOD master_data value_code (how it was acquired, AP-023), e.g. "
                    "'PURCHASE'. Informational only. Unknown code -> 422; null clears it on PATCH.",
    )


class PropertyResponse(BaseModel):
    property_pk: UUID
    property_id: str
    property_name: str
    property_type_code: str
    property_type_name: str
    status: str
    location_description: str | None
    holding_arrangement: str | None
    notes: str | None
    acquired_at: date | None
    current_custodianship_pk: UUID | None
    current_custodian_organization_pk: UUID | None
    current_custodian_organization_name: str | None
    current_custodian_since: date | None
    created_at: datetime
    updated_at: datetime | None
    belongs_to_organization_pk: UUID | None = None
    belongs_to_organization_name: str | None = None
    acquisition_method_code: str | None = None
    acquisition_method_name: str | None = None
    # Effective custodian (GDR-010 §2F): the ACTIVE custodian, or - for a
    # DISPOSED property / RETIRED asset, whose custody was closed by the
    # terminal transition - the LAST (most recently ENDED) custodian.
    # ``current_custodian_*`` carries that effective custodian either way.
    custodian_is_last: bool = False
    custodian_ended_at: date | None = None


class PropertyListResponse(BaseModel):
    items: list[PropertyResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Asset (movable)
# ═══════════════════════════════════════════════════════════════════════

class AssetCreate(BaseModel):
    """Register an asset. asset_id is minted by the server (AST<n>); status starts REGISTERED. See PropertyCreate for the custodian rule."""

    asset_name: str = Field(..., min_length=1, max_length=200)
    asset_type_code: str = Field(..., description="ASSET_TYPE master_data value_code, e.g. 'EQUIPMENT'")
    location_description: str | None = Field(None, max_length=2000)
    condition: str | None = Field(
        None, max_length=2000,
        description="Free text — no condition grading system is frozen (SOL-AP-005 §8.6).",
    )
    notes: str | None = Field(None, max_length=2000)
    acquired_at: date | None = None
    belongs_to_organization_pk: UUID | None = Field(
        None,
        description="Optional 'belongs to' organization (any active organization type) when it differs from the "
                    "physical custodian, e.g. Mahila Sangha under the supervision of the Kendra Sangha. "
                    "Informational only - no authorization effect. null clears it on PATCH.",
    )
    acquisition_method_code: str | None = Field(
        None,
        description="Optional ACQUISITION_METHOD master_data value_code (how it was acquired, AP-023), e.g. "
                    "'PURCHASE'. Informational only. Unknown code -> 422; null clears it on PATCH.",
    )
    custodian_organization_pk: UUID | None = None
    custodian_effective_from: date | None = None

    @field_validator("custodian_effective_from")
    @classmethod
    def _cef(cls, v):
        return _not_future(v, "custodian_effective_from")


class AssetUpdate(BaseModel):
    asset_name: str | None = Field(None, min_length=1, max_length=200)
    asset_type_code: str | None = None
    location_description: str | None = Field(None, max_length=2000)
    condition: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    acquired_at: date | None = None
    belongs_to_organization_pk: UUID | None = Field(
        None,
        description="Optional 'belongs to' organization (any active organization type) when it differs from the "
                    "physical custodian, e.g. Mahila Sangha under the supervision of the Kendra Sangha. "
                    "Informational only - no authorization effect. null clears it on PATCH.",
    )
    acquisition_method_code: str | None = Field(
        None,
        description="Optional ACQUISITION_METHOD master_data value_code (how it was acquired, AP-023), e.g. "
                    "'PURCHASE'. Informational only. Unknown code -> 422; null clears it on PATCH.",
    )


class AssetResponse(BaseModel):
    asset_pk: UUID
    asset_id: str
    asset_name: str
    asset_type_code: str
    asset_type_name: str
    status: str
    location_description: str | None
    condition: str | None
    notes: str | None
    acquired_at: date | None
    current_custodianship_pk: UUID | None
    current_custodian_organization_pk: UUID | None
    current_custodian_organization_name: str | None
    current_custodian_since: date | None
    created_at: datetime
    updated_at: datetime | None
    belongs_to_organization_pk: UUID | None = None
    belongs_to_organization_name: str | None = None
    acquisition_method_code: str | None = None
    acquisition_method_name: str | None = None
    # Effective custodian (GDR-010 §2F): the ACTIVE custodian, or - for a
    # DISPOSED property / RETIRED asset, whose custody was closed by the
    # terminal transition - the LAST (most recently ENDED) custodian.
    # ``current_custodian_*`` carries that effective custodian either way.
    custodian_is_last: bool = False
    custodian_ended_at: date | None = None


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle transition (shared by property and asset)
# ═══════════════════════════════════════════════════════════════════════

class TransitionRequest(BaseModel):
    """
    Record a lifecycle event (SOL-AP-003). Disposal / retirement is RECORDED
    here, not approved here: the authority is Governance (AP-025/045), so
    ``remarks`` should carry the governing-body decision reference. It is
    stored in the audit trail (no financial or approval columns exist).
    """

    status: str = Field(..., description="Target status, e.g. UNDER_MAINTENANCE / DISPOSED (property) or IN_CUSTODY / RETIRED (asset)")
    remarks: str | None = Field(None, max_length=2000)


# ═══════════════════════════════════════════════════════════════════════
# Custodianship
# ═══════════════════════════════════════════════════════════════════════

class CustodianshipAssign(BaseModel):
    """First custodian of a property/asset that currently has none (AP-016/017)."""

    custodian_organization_pk: UUID
    effective_from: date | None = Field(None, description="Defaults to today; must not be in the future.")
    notes: str | None = Field(None, max_length=2000)

    @field_validator("effective_from")
    @classmethod
    def _ef(cls, v):
        return _not_future(v, "effective_from")


class CustodianshipTransfer(BaseModel):
    """
    Close the current custodianship and open a new one (AP-018/041/042).
    The property/asset keeps its lifecycle status (AP-041).

    end_reason_code defaults to TRANSFER; use DISSOLUTION_VESTING for a
    statutory vesting on dissolution so it stays distinguishable from a
    routine transfer (AP-058/059). location_description (optional) updates the
    record's location in the same transaction — location change and custody
    change are independent operations that may coincide (AP-043).
    """

    new_custodian_organization_pk: UUID
    end_reason_code: str = Field("TRANSFER", description="CUSTODIANSHIP_END_REASON value_code")
    effective_from: date | None = Field(None, description="Transfer date; defaults to today, not in the future, not before the current custodianship began.")
    notes: str | None = Field(None, max_length=2000)
    location_description: str | None = Field(None, max_length=2000)

    @field_validator("effective_from")
    @classmethod
    def _ef(cls, v):
        return _not_future(v, "effective_from")


class CustodianshipResponse(BaseModel):
    custodianship_pk: UUID
    property_pk: UUID | None
    asset_pk: UUID | None
    custodian_organization_pk: UUID
    custodian_organization_name: str
    status: str
    effective_from: date
    effective_to: date | None
    end_reason_code: str | None
    end_reason_name: str | None
    notes: str | None
    created_at: datetime


class CustodianshipListResponse(BaseModel):
    items: list[CustodianshipResponse]
    total: int


class CustodianshipTransferResponse(BaseModel):
    previous: CustodianshipResponse
    current: CustodianshipResponse


# ═══════════════════════════════════════════════════════════════════════
# Statutory records (property only — AP-040)
# ═══════════════════════════════════════════════════════════════════════

class StatutoryRecordCreate(BaseModel):
    """Identifies an obligation; payments are Finance's (AP-039) — no amount/date fields exist."""

    obligation_type_code: str = Field(..., description="STATUTORY_OBLIGATION_TYPE value_code: LAND_REVENUE / MUNICIPAL_TAX / LAND_RECORD / OTHER")
    description: str | None = Field(None, max_length=2000)
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)


class StatutoryRecordUpdate(BaseModel):
    obligation_type_code: str | None = None
    description: str | None = Field(None, max_length=2000)
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)


class StatutoryRecordResponse(BaseModel):
    property_statutory_record_pk: UUID
    property_pk: UUID
    obligation_type_code: str
    obligation_type_name: str
    description: str | None
    reference_number: str | None
    notes: str | None
    created_at: datetime


class StatutoryRecordListResponse(BaseModel):
    items: list[StatutoryRecordResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════
# Maintenance records (property or asset)
# ═══════════════════════════════════════════════════════════════════════

class MaintenanceCreate(BaseModel):
    """What WAS done (AP-029) — not a schedule (AP-032), and no cost fields (AP-031)."""

    maintenance_type_code: str = Field(..., description="MAINTENANCE_TYPE value_code, e.g. REPAIR_MINOR")
    description: str | None = Field(None, max_length=2000)
    performed_at: date | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("performed_at")
    @classmethod
    def _pa(cls, v):
        return _not_future(v, "performed_at")


class MaintenanceUpdate(BaseModel):
    maintenance_type_code: str | None = None
    description: str | None = Field(None, max_length=2000)
    performed_at: date | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("performed_at")
    @classmethod
    def _pa(cls, v):
        return _not_future(v, "performed_at")


class MaintenanceResponse(BaseModel):
    maintenance_record_pk: UUID
    property_pk: UUID | None
    asset_pk: UUID | None
    maintenance_type_code: str
    maintenance_type_name: str
    description: str | None
    performed_at: date | None
    notes: str | None
    created_at: datetime


class MaintenanceListResponse(BaseModel):
    items: list[MaintenanceResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════
# Document links (Foundation document_master — AP-067..069)
# ═══════════════════════════════════════════════════════════════════════

class DocumentLinkCreate(BaseModel):
    document_master_pk: UUID
    relationship_type_code: str | None = Field(
        None, description="ASSET_PROPERTY_DOCUMENT_RELATIONSHIP value_code, e.g. TITLE_DEED (optional)")
    notes: str | None = Field(None, max_length=2000)


class DocumentLinkResponse(BaseModel):
    link_pk: UUID
    property_pk: UUID | None
    asset_pk: UUID | None
    document_master_pk: UUID
    document_type_code: str
    document_name: str
    document_number: str | None
    relationship_type_code: str | None
    relationship_type_name: str | None
    notes: str | None
    created_at: datetime


class DocumentLinkListResponse(BaseModel):
    items: list[DocumentLinkResponse]
    total: int
