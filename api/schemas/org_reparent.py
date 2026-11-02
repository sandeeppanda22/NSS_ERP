"""
Pydantic models for the Sakha re-parent approval API (/api/v1/org-reparent).

Backs api/routers/org_reparent.py and the 202 payload of
PATCH /admin/organizations/{pk} — one shared response shape, built by
api/services/org_reparent_service.py::build_request_payload().
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReparentStepResponse(BaseModel):
    organization_reparent_step_pk: UUID
    step_order: int
    step_role: str                      # SAKHA_PRESIDENT | DEST_PARENT_PRESIDENT | KENDRA_PRESIDENT
    step_status: str                    # PENDING | APPROVED | REJECTED
    assigned_body_master_pk: UUID
    assigned_body_name: str | None = None
    assigned_organization_pk: UUID | None = None
    assigned_organization_name: str | None = None
    assigned_position_code: str | None = None
    assigned_position_name: str | None = None
    assigned_person_pk: UUID | None = None
    assigned_person_name: str | None = None
    fallback_reason: str | None = None
    decided_by_person_pk: UUID | None = None
    decided_by_person_name: str | None = None
    decided_at: datetime | None = None
    remarks: str | None = None
    # Viewer-relative: this step is PENDING, every earlier step is APPROVED,
    # the viewer currently holds the assigned seat (live, incl. acting cover)
    # and the viewer is not the requester.
    viewer_can_decide: bool = False


class ReparentRequestResponse(BaseModel):
    organization_reparent_request_pk: UUID
    sakha_organization_pk: UUID
    sakha_organization_name: str | None = None
    sakha_organization_code: str | None = None
    from_parent_organization_pk: UUID | None = None
    from_parent_organization_name: str | None = None
    to_parent_organization_pk: UUID
    to_parent_organization_name: str | None = None
    request_status: str                 # PENDING | APPROVED | REJECTED | CANCELLED
    request_reason: str | None = None
    requested_by_person_pk: UUID
    requested_by_person_name: str | None = None
    requested_by_sangha_sevi_id: str | None = None
    decided_at: datetime | None = None
    decided_by_person_pk: UUID | None = None
    decided_by_person_name: str | None = None
    decision_remarks: str | None = None
    created_at: datetime
    steps: list[ReparentStepResponse] = []
    viewer_can_cancel: bool = False


class ReparentRequestListResponse(BaseModel):
    items: list[ReparentRequestResponse]
    total: int


class ReparentDecisionRequest(BaseModel):
    """Approve/reject one step. Remarks are mandatory on a rejection."""

    decision: Literal["APPROVE", "REJECT"]
    remarks: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _remarks_required_on_reject(self):
        if self.decision == "REJECT" and not (self.remarks and self.remarks.strip()):
            raise ValueError("Remarks are required when rejecting a re-parent request.")
        return self


class ReparentCancelRequest(BaseModel):
    remarks: str | None = Field(None, max_length=2000)
