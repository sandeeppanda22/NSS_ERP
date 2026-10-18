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

    created_at: datetime
    is_active: bool


class CorrespondenceListResponse(BaseModel):
    items: list[CorrespondenceResponse]
    total: int


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
