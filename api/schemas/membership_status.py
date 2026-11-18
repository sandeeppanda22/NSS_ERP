"""Pydantic models for Membership Status change requests (see
api/services/membership_status_service.py for the rules)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StatusChangeCreate(BaseModel):
    to_status_code: str = Field(..., description="ACTIVE, SUSPENDED, LAPSED, EXPELLED or DECEASED")
    effective_date: date = Field(..., description="Date the new status takes effect (today or earlier)")
    reason: str = Field(..., min_length=3, max_length=500)


class StatusDecision(BaseModel):
    remarks: str | None = Field(None, max_length=500)


class StatusRejection(BaseModel):
    remarks: str = Field(..., min_length=3, max_length=500)


class StatusChangeRequestResponse(BaseModel):
    membership_status_change_request_pk: UUID
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    member_name: str
    organization_name: str | None = None
    from_status_code: str
    from_status_name: str
    to_status_code: str
    to_status_name: str
    effective_date: date
    reason: str
    requested_via: str
    request_status: str
    requested_by_name: str | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    decision_remarks: str | None = None
    created_at: datetime


class StatusChangeRequestListResponse(BaseModel):
    requests: list[StatusChangeRequestResponse]
    total: int


class StatusHistoryItem(BaseModel):
    status_code: str
    status_name: str
    effective_from: datetime
    effective_to: datetime | None = None
    reason: str | None = None


class MemberStatusOverview(BaseModel):
    sangha_sevi_pk: UUID
    current_status_code: str
    current_status_name: str
    pending_request: StatusChangeRequestResponse | None = None
    history: list[StatusHistoryItem]
    can_request: bool
    can_decide: bool
    allowed_status_codes: list[str]
