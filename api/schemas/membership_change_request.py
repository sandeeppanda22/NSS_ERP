"""
Pydantic models for the Membership Change Request API (Tier 6, MBR-048/MBR-049).

Backs api/routers/membership_change_request.py — the Sakha Transfer / Apply
for Darshak two-step request/release/accept workflow on
nss.membership_change_request.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChangeRequestCreate(BaseModel):
    """
    Create a TRANSFER or DARSHAK change request.

    *sangha_sevi_pk* is the member the request is for — a member filing for
    themself, or an admin filing on their behalf (see
    membership_change_request.py's create_change_request() for who may set
    it to someone other than their own sangha_sevi_pk).
    """

    sangha_sevi_pk: UUID
    request_type: str = Field(..., pattern="^(TRANSFER|DARSHAK)$")
    new_organization_pk: UUID
    transfer_reason: str | None = Field(None, max_length=500)


class SourceDecisionRequest(BaseModel):
    """Source Sakha's release/reject decision (PENDING_SOURCE_RELEASE stage)."""

    decision: str = Field(..., pattern="^(RELEASE|REJECT)$")
    remarks: str | None = Field(None, max_length=2000)


class DestinationDecisionRequest(BaseModel):
    """
    Destination Sakha's accept/reject decision (PENDING_DESTINATION_ACCEPT
    stage).

    *new_local_number* / *is_legacy_import*: by default the new affiliation's
    Local Sakha ERP Number is auto-generated (MBR-048,
    api/helpers.py::next_sakha_local_number()). An admin recording a legacy
    paper-register case may instead set is_legacy_import=True and supply the
    exact historical number via new_local_number — the two are read together;
    new_local_number without is_legacy_import is rejected (422) so a plain
    typo cannot silently bypass auto-numbering.
    """

    decision: str = Field(..., pattern="^(ACCEPT|REJECT)$")
    remarks: str | None = Field(None, max_length=2000)
    is_legacy_import: bool = False
    new_local_number: str | None = Field(None, max_length=30)


class ChangeRequestResponse(BaseModel):
    membership_change_request_pk: UUID
    sangha_sevi_pk: UUID
    sangha_sevi_id: str | None = None
    member_name: str | None = None

    request_type: str

    old_organization_pk: UUID
    old_organization_name: str | None = None
    new_organization_pk: UUID
    new_organization_name: str | None = None

    transfer_reason: str | None = None

    requested_by_sangha_sevi_pk: UUID
    requested_date: date
    status: str

    source_decided_by_sangha_sevi_pk: UUID | None = None
    source_decided_at: datetime | None = None
    source_remarks: str | None = None

    destination_decided_by_sangha_sevi_pk: UUID | None = None
    destination_decided_at: datetime | None = None
    destination_remarks: str | None = None

    new_local_number: str | None = None
    effective_date: date | None = None

    remarks: str | None = None
    created_at: datetime


class ChangeRequestListResponse(BaseModel):
    requests: list[ChangeRequestResponse]
    total: int
