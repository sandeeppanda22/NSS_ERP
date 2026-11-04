"""
Pydantic response models for the Audit API (Tier 5).

Exposes the field-level change history stored in nss.field_change_log.
Audit columns are the payload here (not excluded, unlike other modules)
because the change log IS the audit trail.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class FieldChangeLogResponse(BaseModel):
    """
    A single field-level change recorded by the DB audit trigger.

    One row per field per operation:
      action='CREATE' → old_value is None
      action='UPDATE' → both values present (new may be None if cleared)
      action='DELETE' → new_value is None

    Actor: both changed_by_sangha_sevi_pk and changed_by_user_account_pk
    are recorded, because an authenticated account does not always have
    a Sangha Sevi record. changed_by_sangha_sevi_id and changed_by_name
    are resolved via LEFT JOIN so callers get a human-readable actor
    without a second lookup. All actor fields are None when the change
    came from an unattributed context (public registration, seed, system).
    """

    field_change_log_pk: UUID
    action: str | None
    table_name: str
    record_pk: UUID
    field_name: str
    old_value: str | None
    new_value: str | None
    change_reason: str | None
    changed_at: datetime
    changed_by_sangha_sevi_pk: UUID | None
    changed_by_sangha_sevi_id: str | None
    changed_by_user_account_pk: UUID | None
    changed_by_name: str | None


class SystemEventResponse(BaseModel):
    """One row of nss.system_event_log (list view: no JSON payload)."""

    system_event_log_pk: UUID
    event_at: datetime
    action: str
    table_name: str
    record_pk: UUID
    module: str | None
    summary: str | None
    is_success: bool | None
    actor_sangha_sevi_pk: UUID | None
    actor_sangha_sevi_id: str | None
    actor_user_account_pk: UUID | None
    actor_name: str | None


class SystemEventDetailResponse(SystemEventResponse):
    """A single event including its JSONB ``detail`` payload (before/after values, request context)."""

    detail: Any | None


class SystemEventPage(BaseModel):
    """
    One page of system events plus the paging facts the explorer needs.

    ``total`` is the exact match count up to ``total_cap`` rows; when more rows
    match, ``total_capped`` is true and ``total`` equals the cap (the UI shows
    "10,000+"). ``event_from`` echoes the lower bound that was applied, which is
    the default 24-hour window when the caller gave neither ``event_from`` nor
    ``record_pk``.
    """

    items: list[SystemEventResponse]
    total: int
    total_capped: bool
    event_from: datetime | None
    limit: int
    offset: int


class SystemEventFacets(BaseModel):
    """Values for the explorer's filter dropdowns."""

    tables: list[str]
    actions: list[str]
    modules: list[str]


class LiveChangeMarkerRow(BaseModel):
    """One row of nss.live_change_marker."""

    table_name: str
    change_seq: int
    changed_at: datetime
    on_live_whitelist: bool


class LiveChangeMarkersResponse(BaseModel):
    """
    Diagnostics view of nss.live_change_marker (the table behind GET /live/changes).

    ``whitelist_without_marker`` lists whitelisted tables that have no marker row
    yet (no trigger has fired and none was seeded - the build has not run the
    trigger file, or the table does not exist).
    """

    server_time: datetime
    markers: list[LiveChangeMarkerRow]
    latest_change_seq: int | None
    latest_table_name: str | None
    whitelist_size: int
    whitelist_without_marker: list[str]
