"""
NSS ERP — Geo-Entry Approval schemas.

Pydantic request/response models for api/routers/geo_approval.py — the
Member-Assisted Geographic Entry approval queue (SOL-ARCH-010 Amendment,
2026-10-03; SOL-FND-004 §16.8, FND-BR-085..090).

The four entities (district, postal-code, post-office, city-village) have
different table-specific columns, so GeoEntryResponse carries them in a
single `value` dict rather than four near-duplicate response models —
mirrors the generic entity-registry approach the router itself uses.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GeoEntryResponse(BaseModel):
    """
    One row from a member-assisted geographic entry table, in any
    entry_status (PENDING/APPROVED/CORRECTED).

    `value` holds the entity-specific columns (e.g. for district:
    state_pk, district_code, district_name, display_order).
    """

    entity: str
    entry_pk: UUID
    value: dict
    entry_status: str
    submitted_by_sangha_sevi_pk: UUID | None
    submitted_by_sangha_sevi_id: str | None = None
    submitted_by_organization_pk: UUID | None = None
    submitted_by_organization_name: str | None = None
    # Registration-Time Geography Creation (2026-10-21): a row created by
    # the public self-registration auto-create path (api/helpers.py
    # resolve_or_create_*) has no sangha_sevi yet — it is attributed to
    # the creating PERSON instead. NULL for every row submitted via the
    # member-authenticated "propose" flow (submitted_by_sangha_sevi_pk
    # set instead) and for seeded/admin-created rows.
    submitted_by_person_pk: UUID | None = None
    submitted_by_person_id: str | None = None
    submitted_by_person_name: str | None = None
    reviewed_by_sangha_sevi_pk: UUID | None
    reviewed_at: datetime | None
    admin_remarks: str | None
    corrected_into_pk: UUID | None
    is_active: bool
    created_at: datetime


class GeoEntryListResponse(BaseModel):
    entries: list[GeoEntryResponse]
    total: int
    page: int
    page_size: int


class ApproveGeoEntryRequest(BaseModel):
    """POST /api/v1/admin/geo-entries/{entity}/{pk}/approve — admin_remarks is optional."""

    admin_remarks: str | None = Field(None, max_length=500)


class CorrectGeoEntryRequest(BaseModel):
    """
    POST /api/v1/admin/geo-entries/{entity}/{pk}/correct.

    *corrected_value* shape depends on *entity* (FND-BR-087 — the
    canonical value is mandatory, there is no bare rejection path):
      - district:     {"district_name": str, "district_code": str | None}
      - postal-code:  {"postal_code": str}
      - post-office:  {"post_office_name": str}
      - city-village: {"city_village_name": str, "city_village_type": str}

    *admin_remarks* is mandatory — this is the correction audit trail.
    """

    corrected_value: dict
    admin_remarks: str = Field(..., min_length=1, max_length=500)


class CorrectGeoEntryResponse(BaseModel):
    message: str
    original_pk: UUID
    canonical_pk: UUID
    canonical_was_newly_created: bool
