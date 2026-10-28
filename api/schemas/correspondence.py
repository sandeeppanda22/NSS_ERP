"""
Pydantic models for the Correspondence Register API (Tier 6, SOL-ADMIN-009).

Backs api/routers/correspondence.py — register/view/transition correspondence
filed under an organization's inward/outward register
(nss.correspondence), plus its document (nss.correspondence_document) and
finance-reference (nss.correspondence_finance_reference) sub-resources.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CorrespondenceCreate(BaseModel):
    """
    Register a new inward/outward correspondence entry.

    reference_number is never supplied by the client — it is minted by
    api/helpers.py::next_correspondence_reference_number() from
    register_organization_pk + direction (CORR-EXT-001). medium/status are
    passed as plain value_codes (e.g. "POST", "REGISTERED") and resolved to
    master_data PKs server-side via get_master_data_pk().

    Sender/recipient conditional integrity mirrors the DB's compound CHECK
    (chk_correspondence_sender/recipient_consistency, §4.6): exactly one of
    {*_person_pk, *_organization_pk, *_external_name} per party.
    """

    register_organization_pk: UUID
    direction: str = Field(..., pattern="^(INWARD|OUTWARD)$")

    correspondence_date: date
    received_or_sent_date: date
    follow_up_date: date | None = None

    subject: str = Field(..., max_length=255)
    remarks: str | None = Field(None, max_length=2000)

    sender_type: str = Field(..., pattern="^(PERSON|ORGANIZATION|EXTERNAL)$")
    sender_person_pk: UUID | None = None
    sender_organization_pk: UUID | None = None
    sender_external_name: str | None = Field(None, max_length=150)
    sender_external_organization: str | None = Field(None, max_length=150)
    sender_person_capacity: str | None = Field(None, pattern="^(PERSONAL|ORGANIZATIONAL)$")
    sender_person_organization_pk: UUID | None = None

    recipient_type: str = Field(..., pattern="^(PERSON|ORGANIZATION|EXTERNAL)$")
    recipient_person_pk: UUID | None = None
    recipient_organization_pk: UUID | None = None
    recipient_external_name: str | None = Field(None, max_length=150)
    recipient_external_organization: str | None = Field(None, max_length=150)

    responsible_person_pk: UUID | None = None
    responsible_organization_pk: UUID | None = None

    # Reply threading (v1.2, owner 2026-10-26: "we should also add reply
    # option to letter too. which will have its own numbers (conceptually
    # same process)") — deliberately NOT a separate numbering scheme; a
    # reply is an ordinary new row (its own reference_number via the normal
    # counter) that additionally links back to the letter it answers.
    in_reply_to_correspondence_pk: UUID | None = None

    medium: str = Field(..., description="CORRESPONDENCE_MEDIUM value_code, e.g. 'POST'")

    @model_validator(mode="after")
    def _check_party_consistency(self) -> "CorrespondenceCreate":
        def _one_of(label: str, type_value: str, person_pk, org_pk, ext_name) -> None:
            if type_value == "PERSON" and not (person_pk and not org_pk and not ext_name):
                raise ValueError(f"{label}_type is PERSON: set {label}_person_pk only.")
            if type_value == "ORGANIZATION" and not (org_pk and not person_pk and not ext_name):
                raise ValueError(f"{label}_type is ORGANIZATION: set {label}_organization_pk only.")
            if type_value == "EXTERNAL" and not (ext_name and not person_pk and not org_pk):
                raise ValueError(f"{label}_type is EXTERNAL: set {label}_external_name only.")

        _one_of("sender", self.sender_type, self.sender_person_pk, self.sender_organization_pk, self.sender_external_name)
        _one_of("recipient", self.recipient_type, self.recipient_person_pk, self.recipient_organization_pk, self.recipient_external_name)

        if self.sender_type == "PERSON":
            if not self.sender_person_capacity:
                raise ValueError("sender_type is PERSON: sender_person_capacity is required.")
            if self.sender_person_capacity == "ORGANIZATIONAL" and not self.sender_person_organization_pk:
                raise ValueError("sender_person_capacity is ORGANIZATIONAL: sender_person_organization_pk is required.")
            if self.sender_person_capacity == "PERSONAL" and self.sender_person_organization_pk:
                raise ValueError("sender_person_capacity is PERSONAL: sender_person_organization_pk must be empty.")
        else:
            if self.sender_person_capacity or self.sender_person_organization_pk:
                raise ValueError("sender_person_capacity/sender_person_organization_pk only apply when sender_type is PERSON.")

        # §7.1 / §7.2 (ERP-FROZEN): neither date may be in the future — a
        # correspondence that hasn't happened/been received/sent yet cannot
        # be registered. follow_up_date (§7.3) is deliberately exempt: it is
        # a forward-looking target date by design.
        today = date.today()
        if self.correspondence_date > today:
            raise ValueError("correspondence_date must not be in the future.")
        if self.received_or_sent_date > today:
            raise ValueError("received_or_sent_date must not be in the future.")

        return self


class CorrespondenceBroadcastCreate(BaseModel):
    """
    Register ONE circular letter sent FROM register_organization_pk to
    EVERY active descendant organization of a given type (owner-confirmed
    2026-10-26: "sometimes, kendra/anchalika/zilla send letter to all
    sakhas under it" — generalizes the exact §4.7 ERP-FROZEN example,
    "Kendra circular to all Sakhas", to any sender + any descendant org
    type, not just Kendra-to-Sakha specifically).

    The register itself has no "one row, many recipients" concept — the
    DB's sender/recipient CHECK requires exactly one recipient per row
    (§4.6) — so a circular is still N ordinary OUTWARD rows under the
    hood, one per recipient, each with its own reference_number (§4.1:
    every org keeps its own per-direction counter). What this endpoint
    adds is doing all N in one admin action with one shared subject/
    date/medium/remarks, instead of requiring N manual repeats of
    POST /correspondence + POST /{pk}/dispatch.

    Sender is always ORGANIZATION = register_organization_pk — a
    circular is sent BY the organization, not a named individual, so
    there is deliberately no sender_type/sender_person_* override here
    (unlike the single-letter CorrespondenceCreate).
    """

    register_organization_pk: UUID
    recipient_organization_type_code: str = Field(
        ..., description="ORGANIZATION_TYPE value_code, e.g. 'SAKHA_SANGHA' — "
                          "every active descendant of this type under register_organization_pk",
    )

    correspondence_date: date
    received_or_sent_date: date
    follow_up_date: date | None = None

    subject: str = Field(..., max_length=255)
    remarks: str | None = Field(None, max_length=2000)

    medium: str = Field(..., description="CORRESPONDENCE_MEDIUM value_code, e.g. 'POST'")

    @model_validator(mode="after")
    def _check_dates(self) -> "CorrespondenceBroadcastCreate":
        # Same §7.1/§7.2 ERP-FROZEN rule as CorrespondenceCreate.
        today = date.today()
        if self.correspondence_date > today:
            raise ValueError("correspondence_date must not be in the future.")
        if self.received_or_sent_date > today:
            raise ValueError("received_or_sent_date must not be in the future.")
        return self


class StatusTransitionRequest(BaseModel):
    """
    Move a correspondence record to a new status (§6.2 precondition table).

    §6.3: reopening (ACTIONED/CLOSED -> PENDING_ACTION) requires non-empty
    remarks — enforced in the router, since the requirement is conditional
    on the *current* status, not expressible as a plain field constraint
    here.
    """

    new_status: str = Field(..., pattern="^(REGISTERED|PENDING_ACTION|ACTIONED|CLOSED)$")
    remarks: str | None = Field(None, max_length=2000)


class ResponsiblePartyAssignRequest(BaseModel):
    """Assign (or clear) who is responsible for acting on this correspondence (§5.4)."""

    responsible_person_pk: UUID | None = None
    responsible_organization_pk: UUID | None = None

    @model_validator(mode="after")
    def _check_at_most_one(self) -> "ResponsiblePartyAssignRequest":
        if self.responsible_person_pk and self.responsible_organization_pk:
            raise ValueError("Set at most one of responsible_person_pk / responsible_organization_pk.")
        return self


class CorrespondenceResponse(BaseModel):
    correspondence_pk: UUID
    register_organization_pk: UUID
    register_organization_name: str | None = None
    reference_number: str
    direction: str

    correspondence_date: date
    received_or_sent_date: date
    follow_up_date: date | None = None

    subject: str
    remarks: str | None = None

    sender_type: str
    sender_person_pk: UUID | None = None
    sender_person_name: str | None = None
    sender_organization_pk: UUID | None = None
    sender_organization_name: str | None = None
    sender_external_name: str | None = None
    sender_external_organization: str | None = None
    sender_person_capacity: str | None = None
    sender_person_organization_pk: UUID | None = None
    sender_sakha_erp_id_snapshot: str | None = None

    recipient_type: str
    recipient_person_pk: UUID | None = None
    recipient_person_name: str | None = None
    recipient_organization_pk: UUID | None = None
    recipient_organization_name: str | None = None
    recipient_external_name: str | None = None
    recipient_external_organization: str | None = None

    responsible_person_pk: UUID | None = None
    responsible_organization_pk: UUID | None = None

    medium_master_data_pk: UUID
    medium_value_code: str | None = None
    status_master_data_pk: UUID
    status_value_code: str | None = None

    # Two-sided org-to-org register (v1.1, owner-confirmed 2026-10-25).
    # counterpart_reference_number is resolved for display only (the pk
    # alone is useless to a human reading the register) — never written,
    # always derived by joining to the counterpart row.
    counterpart_correspondence_pk: UUID | None = None
    counterpart_reference_number: str | None = None

    # Reply threading (v1.2) — in_reply_to_reference_number is resolved for
    # display only, same pattern as counterpart_reference_number above.
    in_reply_to_correspondence_pk: UUID | None = None
    in_reply_to_reference_number: str | None = None

    created_at: datetime
    is_active: bool


class CorrespondenceListResponse(BaseModel):
    items: list[CorrespondenceResponse]
    total: int


class CorrespondenceBroadcastResponse(BaseModel):
    recipient_count: int
    items: list[CorrespondenceResponse]


class DocumentAssociationCreate(BaseModel):
    document_master_pk: UUID
    document_purpose: str = Field(..., pattern="^(ORIGINAL|RESPONSE|ATTACHMENT|SUPPORTING)$")
    remarks: str | None = Field(None, max_length=2000)


class DocumentAssociationResponse(BaseModel):
    correspondence_document_pk: UUID
    correspondence_pk: UUID
    document_master_pk: UUID
    document_purpose: str
    remarks: str | None = None
    created_at: datetime


class DocumentAssociationListResponse(BaseModel):
    items: list[DocumentAssociationResponse]
    total: int


class FinanceReferenceCreate(BaseModel):
    financial_transaction_pk: UUID
    relationship_type: str = Field(..., description="CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE value_code, e.g. 'PAYMENT'")
    remarks: str | None = Field(None, max_length=2000)


class FinanceReferenceResponse(BaseModel):
    correspondence_finance_reference_pk: UUID
    correspondence_pk: UUID
    financial_transaction_pk: UUID
    relationship_type_master_data_pk: UUID
    relationship_type_value_code: str | None = None
    remarks: str | None = None
    created_at: datetime


class FinanceReferenceListResponse(BaseModel):
    items: list[FinanceReferenceResponse]
    total: int


# ── History + reply-thread path tracker (owner-confirmed 2026-10-26) ────
#
# "can we add history with path tracker for correspondance?" — two parts:
#   1. History: the full activity log for ONE record (status transitions —
#      manual and the 2026-10-26 event-driven auto ones alike —, responsible-
#      party reassignment, creation, dispatch/auto-dispatch, broadcast),
#      reusing the EXISTING generic audit write path (log_audit() ->
#      nss.system_event_log) rather than a new per-module history table —
#      consistent with the project's own "shared Change History framework,
#      not separate rename/history tables per module" decision. Purely
#      additive/read-only: every entry already exists because every
#      correspondence write already calls log_audit(); this just surfaces
#      them filtered to one record_pk.
#   2. Path tracker: the reply thread (in_reply_to_correspondence_pk) walked
#      BOTH directions — ancestors ("what this is ultimately replying to",
#      oldest first) and descendants ("every reply this drew, recursively").
#      Scope/access note: GET /{pk} itself (get_correspondence) has no
#      per-record scope check beyond CORRESPONDENCE_VIEW/MANAGE — this
#      endpoint mirrors that exact gate for consistency rather than
#      introducing a new, stricter model just for history.

class CorrespondenceHistoryEventResponse(BaseModel):
    """One nss.system_event_log row for this correspondence_pk."""
    event_at: datetime
    action: str
    summary: str | None = None
    actor_name: str | None = None


class CorrespondenceThreadNodeResponse(BaseModel):
    """One other correspondence record in the reply thread (ancestor or
    descendant) — never the record itself."""
    correspondence_pk: UUID
    reference_number: str
    subject: str
    direction: str
    status_value_code: str
    # Ancestors: 1 = what this directly replies to, 2 = what THAT replies
    # to, etc. Descendants: 1 = a direct reply to this record, 2 = a reply
    # to that reply, etc. Always >= 1 (the record itself is never included).
    depth: int


class CorrespondenceHistoryResponse(BaseModel):
    events: list[CorrespondenceHistoryEventResponse]
    thread_ancestors: list[CorrespondenceThreadNodeResponse]
    thread_descendants: list[CorrespondenceThreadNodeResponse]


# ── Member "Send Application" (approval-chain extension) ────────────────
#
# Additive to the 9 existing endpoints/schemas above — backs the new
# member-facing endpoints in api/routers/correspondence.py
# (/my-applications, /addressed-to-me, /approval-steps/*) and
# nss.correspondence_approval_step (database/ddl/09_correspondence/
# 05_correspondence_approval_step.sql). Does not change CorrespondenceCreate
# or the §6.2 status model; a member application is still a plain
# nss.correspondence row (direction=OUTWARD, sender_type=PERSON) — these
# schemas only add the 3-mode addressing convenience and the optional
# 2-step chain for the Kendra-via-Sakha-President mode.

class MemberApplicationCreate(BaseModel):
    """
    File a "Send Application" correspondence as a member, addressed one of
    six ways (a/b/c owner-confirmed 2026-10-21; d/e/f owner-confirmed
    2026-10-25, gender-gated):
      - SAKHA_ORG: to the member's own Sakha, as an organization.
      - SAKHA_OFFICE_BEARER: to a specific, currently-seated office-bearer
        of the member's own Sakha Governing Body / Mahila Parichalana
        Mandali (recipient_person_pk required).
      - KENDRA_VIA_SAKHA_PRESIDENT: to a specific, currently-seated
        Kendra-level office-bearer (recipient_person_pk required), routed
        through the member's own Sakha President first — creates a
        2-step nss.correspondence_approval_step chain; the Kendra
        office-bearer is not visible/addressed until step 1 is approved.
      - MAHILA_OFFICE_BEARER: to a specific, currently-seated office-bearer
        of the member's own (Sakha-level) Mahila Parichalana Mandali
        (recipient_person_pk required). FEMALE members only — server-side
        enforced, never trust client-side gating alone.
      - KENDRA_MAHILA_VIA_SAKHA_PRESIDENT: to a specific, currently-seated
        office-bearer of the CENTRAL (Kendra-level, NSS-wide) Mahila
        Parichalana Mandali (recipient_person_pk required), routed through
        the member's own Sakha President first — same 2-step chain
        mechanism as KENDRA_VIA_SAKHA_PRESIDENT, targeting the central
        Mahila PM body instead of the Kendra Governing Body. FEMALE
        members only.
      - SEVAK_OFFICE_BEARER: to a specific, currently-seated office-bearer
        of the member's own (Sakha-level) Sevak Sangha Executive
        (recipient_person_pk required). MALE members only.

    register_organization_pk, correspondence_date, received_or_sent_date,
    sender_*, direction and medium are all derived server-side (never
    client-supplied) — see create_member_application() in the router.
    """

    addressing_mode: str = Field(
        ...,
        pattern=(
            "^(SAKHA_ORG|SAKHA_OFFICE_BEARER|KENDRA_VIA_SAKHA_PRESIDENT"
            "|MAHILA_OFFICE_BEARER|KENDRA_MAHILA_VIA_SAKHA_PRESIDENT|SEVAK_OFFICE_BEARER)$"
        ),
    )
    recipient_person_pk: UUID | None = None
    subject: str = Field(..., max_length=255)
    remarks: str | None = Field(None, max_length=2000)
    follow_up_date: date | None = None

    @model_validator(mode="after")
    def _check_recipient_for_mode(self) -> "MemberApplicationCreate":
        if self.addressing_mode == "SAKHA_ORG":
            if self.recipient_person_pk is not None:
                raise ValueError("recipient_person_pk must not be set for addressing_mode SAKHA_ORG.")
        else:
            if self.recipient_person_pk is None:
                raise ValueError(f"recipient_person_pk is required for addressing_mode {self.addressing_mode}.")
        return self


class ApprovalStepResponse(BaseModel):
    correspondence_approval_step_pk: UUID
    correspondence_pk: UUID
    step_number: int
    approver_person_pk: UUID
    approver_person_name: str | None = None
    approver_position_master_pk: UUID
    approver_position_name: str | None = None
    approver_position_code: str | None = None
    approver_organization_pk: UUID | None = None
    approver_organization_name: str | None = None
    # Additive, display-only (2026-10-24, owner ask #3 — "when onbehalf is
    # selected ... show he is absent.. and acting text beside the selected
    # person everywhere"). Non-null only when the named approver currently
    # has a LIVE (acting_status = 'ACTIVE') acting-position delegate
    # covering the exact seat (body + position) they hold. Never changes
    # who may act on this step — approver_person_pk/approval authority are
    # untouched; this is visibility only.
    acting_person_name: str | None = None
    step_status: str
    decided_at: datetime | None = None
    remarks: str | None = None
    created_at: datetime


class MemberApplicationResponse(CorrespondenceResponse):
    """CorrespondenceResponse plus the approval chain, if any (empty for modes a/b)."""

    approval_steps: list[ApprovalStepResponse] = Field(default_factory=list)


class MemberApplicationListResponse(BaseModel):
    items: list[MemberApplicationResponse]
    total: int


class ApprovalStepDecisionRequest(BaseModel):
    """The Sakha President's decision on a pending step-1 approval."""

    decision: str = Field(..., pattern="^(APPROVE|REJECT)$")
    remarks: str | None = Field(None, max_length=2000)
