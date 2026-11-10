"""
Pydantic models and controlled-value catalogues for the Finance API (Tier 12).

Backs api/routers/finance.py. Authority: docs/03_Solution/modules/finance/
(SOL-FIN-001..005, business rules FIN-BR-001..068).

Conventions:
  - The status / type / category sets below are the ONE definition used by the
    router, the /finance/reference endpoint (and therefore the UI) and the
    DDL parity test; they mirror the CHECK constraints in
    database/ddl/14_finance/.
  - The payment method is a master_data ``value_code`` (category
    PAYMENT_METHOD, admin-extendable), resolved server-side (unknown -> 422).
  - Money is Decimal, strictly positive, two decimals (NUMERIC(14,2));
    direction comes from the transaction type, not the sign.
  - Lifecycle ``status`` is never writable through PATCH; it moves only through
    the ``/transition`` endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field

# ── Controlled values (mirror the DDL CHECK constraints) ─────────────────

YEAR_STATUSES = ("PLANNED", "OPEN", "CLOSING", "CLOSED")
SCOPE_STATUSES = ("DRAFT", "ACTIVE", "CLOSING", "CLOSED")
SCOPE_TYPES = ("ORGANIZATION", "EVENT", "SPECIAL_PURPOSE", "RESTRICTED_FUND")
FUND_STATUSES = ("DRAFT", "ACTIVE", "INACTIVE")
FUND_TYPES = (
    "GENERAL", "SINKING_FUND", "PUBLICATION", "SPECIFIC_PURPOSE",
    "MEMBERSHIP_SUBSCRIPTION", "PRANAMI", "DONATION", "GRANT",
    "PROPERTY_INCOME", "MISCELLANEOUS",
)
TRANSACTION_TYPES = ("INCOME", "EXPENSE", "ADJUSTMENT")
TRANSACTION_STATUSES = ("DRAFT", "PENDING_APPROVAL", "APPROVED", "POSTED", "SETTLED", "REJECTED", "CANCELLED")
# The purpose a transaction is booked under is a FINANCE HEAD (finance_head), customizable per Sangha: there is
# no fixed category list any more. A head's rules (direction, restricted, required fund type, Pranami, UPI) are data.
HEAD_DIRECTIONS = ("INCOME", "EXPENSE")
HEAD_STATUSES = ("ACTIVE", "INACTIVE")
ACCOUNT_STATUSES = ("ACTIVE", "INACTIVE")
ACCOUNT_TYPES = ("BANK", "POST_OFFICE")
PAYMENT_REQUEST_STATUSES = ("CREATED", "PENDING", "PAID", "FAILED", "EXPIRED", "CANCELLED")
GATEWAY_EVENT_OUTCOMES = ("POSTED", "PAID_NEEDS_REVIEW", "DUPLICATE", "IGNORED", "FAILED", "EXPIRED",
                          "UNKNOWN_REQUEST", "REJECTED_SIGNATURE", "ERROR")
RECEIPT_STATUSES = ("DRAFT", "ISSUED", "CANCELLED")
PAYMENT_STATUSES = ("DRAFT", "APPROVED", "INITIATED", "COMPLETED", "CANCELLED")
TRANSFER_STATUSES = ("DRAFT", "PENDING_APPROVAL", "APPROVED", "EXECUTED", "COMPLETED", "REJECTED", "CANCELLED")

MONEY_MAX = Decimal("999999999999.99")  # NUMERIC(14,2)


def _money(value: Decimal) -> Decimal:
    if value.as_tuple().exponent < -2:
        raise ValueError("Amount can have at most two decimal places.")
    return value


# Positive INR amount with at most two decimals.
Amount = Annotated[Decimal, Field(gt=0, le=MONEY_MAX), AfterValidator(_money)]


# ═══════════════════════════════════════════════════════════════════════
# Common
# ═══════════════════════════════════════════════════════════════════════

class TransitionRequest(BaseModel):
    """Move a record along its lifecycle; ``remarks`` is mandatory for reject / cancel."""

    status: str = Field(..., description="Target status")
    remarks: str | None = Field(None, max_length=2000)


class NamedCode(BaseModel):
    code: str
    name: str


class FinanceReference(BaseModel):
    """Everything the UI needs to build its pick-lists, from one definition."""

    payment_methods: list[NamedCode]
    fund_types: list[str]
    scope_types: list[str]
    transaction_types: list[str]
    head_directions: list[str]
    account_types: list[str]
    gateway_providers: list[str]            # adapters ENABLED on this server (empty = UPI collection is off)
    statuses: dict[str, list[str]]
    transitions: dict[str, list[dict]]


# ═══════════════════════════════════════════════════════════════════════
# Financial year
# ═══════════════════════════════════════════════════════════════════════

class YearCreate(BaseModel):
    """A Financial Year always runs 01 April - 31 March; only the starting year is chosen."""

    start_year: int = Field(..., ge=2000, le=2100, description="2026 -> year 2026-27 (2026-04-01 .. 2027-03-31)")


class YearResponse(BaseModel):
    financial_year_pk: UUID
    year_code: str
    start_date: date
    end_date: date
    status: str
    transaction_count: int = 0


class YearListResponse(BaseModel):
    items: list[YearResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════
# Financial scope
# ═══════════════════════════════════════════════════════════════════════

class ScopeCreate(BaseModel):
    scope_code: str = Field(..., min_length=1, max_length=50)
    scope_name: str = Field(..., min_length=1, max_length=200)
    scope_type: str = Field(..., description="ORGANIZATION / EVENT / SPECIAL_PURPOSE / RESTRICTED_FUND")
    organization_pk: UUID | None = Field(None, description="Owning organization; omit for a scope with none (global authority only)")
    financial_year_pk: UUID | None = None
    parent_scope_pk: UUID | None = None


class ScopeUpdate(BaseModel):
    """Only while the scope is DRAFT or ACTIVE; code, type and organization are immutable."""

    scope_name: str | None = Field(None, min_length=1, max_length=200)
    financial_year_pk: UUID | None = None
    parent_scope_pk: UUID | None = None


class ScopeResponse(BaseModel):
    financial_scope_pk: UUID
    scope_code: str
    scope_name: str
    scope_type: str
    organization_pk: UUID | None
    organization_name: str | None
    financial_year_pk: UUID | None
    year_code: str | None
    parent_scope_pk: UUID | None
    parent_scope_code: str | None
    status: str
    fund_count: int = 0
    transaction_count: int = 0


class ScopeListResponse(BaseModel):
    items: list[ScopeResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Fund
# ═══════════════════════════════════════════════════════════════════════

class FundCreate(BaseModel):
    fund_code: str = Field(..., min_length=1, max_length=50)
    fund_name: str = Field(..., min_length=1, max_length=200)
    fund_type: str
    financial_scope_pk: UUID
    is_restricted: bool = False
    restriction_purpose: str | None = Field(None, max_length=2000)
    organization_pk: UUID | None = Field(None, description="The Sakha, for a SINKING_FUND (FIN-BR-023/024)")


class FundUpdate(BaseModel):
    fund_name: str | None = Field(None, min_length=1, max_length=200)
    restriction_purpose: str | None = Field(None, max_length=2000)
    is_restricted: bool | None = Field(None, description="Only while the fund is DRAFT")


class FundResponse(BaseModel):
    fund_master_pk: UUID
    fund_code: str
    fund_name: str
    fund_type: str
    financial_scope_pk: UUID
    scope_code: str
    scope_name: str
    is_restricted: bool
    restriction_purpose: str | None
    organization_pk: UUID | None
    organization_name: str | None
    status: str
    balance: Decimal = Decimal("0.00")


class FundListResponse(BaseModel):
    items: list[FundResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Transaction
# ═══════════════════════════════════════════════════════════════════════

class TransactionCreate(BaseModel):
    financial_year_pk: UUID
    financial_scope_pk: UUID
    fund_master_pk: UUID | None = None
    transaction_type: str = Field(..., description="INCOME / EXPENSE / ADJUSTMENT")
    finance_head_pk: UUID = Field(..., description="The finance head (purpose) of this entry; must belong to the scope's organization")
    amount: Amount
    transaction_date: date
    description: str | None = Field(None, max_length=2000)
    person_pk: UUID | None = None
    sangha_sevi_pk: UUID | None = None
    sangha_sevi_id: str | None = Field(
        None, max_length=20,
        description="Business id of the member the money is from / for (e.g. 'SS12'); resolves person_pk and "
                    "sangha_sevi_pk and makes the entry appear in that member's own Pranami tab",
    )


class TransactionUpdate(BaseModel):
    """DRAFT only. Omitted fields are unchanged; explicit null clears fund / description / person / sevi."""

    financial_year_pk: UUID | None = None
    financial_scope_pk: UUID | None = None
    fund_master_pk: UUID | None = None
    transaction_type: str | None = None
    finance_head_pk: UUID | None = None
    amount: Amount | None = None
    transaction_date: date | None = None
    description: str | None = Field(None, max_length=2000)
    person_pk: UUID | None = None
    sangha_sevi_pk: UUID | None = None
    sangha_sevi_id: str | None = Field(None, max_length=20, description="Member business id; null / blank unlinks the member")


class TransactionResponse(BaseModel):
    financial_transaction_pk: UUID
    transaction_reference: str
    financial_year_pk: UUID
    year_code: str
    financial_scope_pk: UUID
    scope_code: str
    scope_name: str
    scope_organization_pk: UUID | None
    scope_organization_name: str | None
    fund_master_pk: UUID | None
    fund_code: str | None
    fund_name: str | None
    transaction_type: str
    finance_head_pk: UUID | None
    finance_head_name: str | None
    transaction_category: str               # immutable snapshot of the head's code
    amount: Decimal
    transaction_date: date
    description: str | None
    person_pk: UUID | None
    person_name: str | None
    sangha_sevi_pk: UUID | None
    sangha_sevi_id: str | None
    status: str
    created_by_sangha_sevi_pk: UUID | None
    created_at: datetime
    receipted_amount: Decimal = Decimal("0.00")
    paid_amount: Decimal = Decimal("0.00")


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Receipt / payment evidence
# ═══════════════════════════════════════════════════════════════════════

class ReceiptCreate(BaseModel):
    receipt_date: date
    amount: Amount
    received_from: str | None = Field(None, max_length=200)
    payment_method_code: str | None = Field(None, description="PAYMENT_METHOD value_code, e.g. 'UPI'")
    instrument_reference: str | None = Field(None, max_length=100, description="UPI transaction id / cheque no. / bank reference")
    person_pk: UUID | None = None


class ReceiptResponse(BaseModel):
    financial_receipt_pk: UUID
    receipt_number: str
    financial_transaction_pk: UUID
    transaction_reference: str
    receipt_date: date
    amount: Decimal
    received_from: str | None
    payment_method_code: str | None
    payment_method_name: str | None
    instrument_reference: str | None
    person_pk: UUID | None
    person_name: str | None
    status: str
    cancellation_reason: str | None
    created_at: datetime


class ReceiptListResponse(BaseModel):
    items: list[ReceiptResponse]
    total: int
    page: int
    page_size: int


class PaymentCreate(BaseModel):
    payment_date: date
    amount: Amount
    paid_to: str | None = Field(None, max_length=200)
    payment_method_code: str | None = Field(None, description="PAYMENT_METHOD value_code, e.g. 'UPI'")
    instrument_reference: str | None = Field(None, max_length=100, description="UPI transaction id / cheque no. / bank reference")
    person_pk: UUID | None = None


class PaymentResponse(BaseModel):
    financial_payment_pk: UUID
    payment_reference: str
    financial_transaction_pk: UUID
    transaction_reference: str
    payment_date: date
    amount: Decimal
    paid_to: str | None
    payment_method_code: str | None
    payment_method_name: str | None
    instrument_reference: str | None
    person_pk: UUID | None
    person_name: str | None
    status: str
    created_at: datetime


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Transfer
# ═══════════════════════════════════════════════════════════════════════

class TransferCreate(BaseModel):
    financial_year_pk: UUID
    source_scope_pk: UUID
    destination_scope_pk: UUID
    source_fund_pk: UUID | None = None
    destination_fund_pk: UUID | None = None
    amount: Amount
    transfer_date: date
    purpose: str = Field(..., min_length=1, max_length=2000)


class TransferResponse(BaseModel):
    financial_transfer_pk: UUID
    transfer_reference: str
    financial_year_pk: UUID
    year_code: str
    source_scope_pk: UUID
    source_scope_code: str
    source_scope_name: str
    destination_scope_pk: UUID
    destination_scope_code: str
    destination_scope_name: str
    source_fund_pk: UUID | None
    source_fund_code: str | None
    destination_fund_pk: UUID | None
    destination_fund_code: str | None
    amount: Decimal
    transfer_date: date
    purpose: str
    status: str
    created_by_sangha_sevi_pk: UUID | None
    created_at: datetime


class TransferListResponse(BaseModel):
    items: list[TransferResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Receiving accounts (per Sangha)
# ═══════════════════════════════════════════════════════════════════════

class AccountCreate(BaseModel):
    organization_pk: UUID
    account_label: str = Field(..., min_length=1, max_length=100)
    account_type: str = Field("BANK", description="BANK / POST_OFFICE")
    bank_name: str | None = Field(None, max_length=150)
    branch_name: str | None = Field(None, max_length=150)
    account_holder_name: str = Field(..., min_length=1, max_length=200)
    account_number_last4: str | None = Field(None, description="Last four digits ONLY - the full number is never stored")
    ifsc_code: str | None = Field(None, max_length=11)
    upi_vpa: str | None = Field(None, max_length=100, description="The UPI id payments are made to, e.g. sakha@okbank")
    gateway_provider: str | None = Field(None, max_length=30, description="MOCK / RAZORPAY - an adapter enabled on the server")
    gateway_credential_ref: str | None = Field(None, max_length=40, description="NAME of a server-side credential set (never a key)")
    gateway_merchant_ref: str | None = Field(None, max_length=100, description="Provider-side merchant / linked-account id (not a secret)")
    is_default: bool = False


class AccountUpdate(BaseModel):
    """Organization is immutable. Omitted = unchanged; explicit null clears an optional field."""

    account_label: str | None = Field(None, min_length=1, max_length=100)
    account_type: str | None = None
    bank_name: str | None = Field(None, max_length=150)
    branch_name: str | None = Field(None, max_length=150)
    account_holder_name: str | None = Field(None, min_length=1, max_length=200)
    account_number_last4: str | None = None
    ifsc_code: str | None = Field(None, max_length=11)
    upi_vpa: str | None = Field(None, max_length=100)
    gateway_provider: str | None = Field(None, max_length=30)
    gateway_credential_ref: str | None = Field(None, max_length=40)
    gateway_merchant_ref: str | None = Field(None, max_length=100)
    is_default: bool | None = None


class AccountResponse(BaseModel):
    financial_account_pk: UUID
    organization_pk: UUID
    organization_name: str | None
    account_label: str
    account_type: str
    bank_name: str | None
    branch_name: str | None
    account_holder_name: str
    account_number_last4: str | None
    ifsc_code: str | None
    upi_vpa: str | None
    gateway_provider: str | None
    gateway_credential_ref: str | None
    gateway_merchant_ref: str | None
    gateway_ready: bool = False             # provider enabled on this server AND its credential set fully configured
    is_default: bool
    status: str
    head_count: int = 0                     # heads whose UPI collection settles into this account


class AccountListResponse(BaseModel):
    items: list[AccountResponse]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════
# Finance heads (customizable per Sangha, Kendra templates)
# ═══════════════════════════════════════════════════════════════════════

class HeadCreate(BaseModel):
    organization_pk: UUID | None = Field(None, description="Owning Sangha; omit for a Kendra TEMPLATE (global authority only)")
    head_code: str = Field(..., min_length=2, max_length=50, description="UPPER_SNAKE_CASE, immutable once created")
    head_name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    direction: str = Field(..., description="INCOME / EXPENSE")
    is_restricted: bool = False
    restriction_purpose: str | None = Field(None, max_length=2000)
    required_fund_type: str | None = Field(None, description="e.g. SINKING_FUND: entries must go to a fund of this type")
    is_pranami: bool = Field(False, description="Show these contributions in the member's own Pranami tab")
    allow_upi: bool = Field(False, description="May be collected by UPI (needs a collection scope and account)")
    collection_scope_pk: UUID | None = None
    collection_fund_pk: UUID | None = None
    collection_account_pk: UUID | None = None
    display_order: int = Field(100, ge=0, le=10000)


class HeadUpdate(BaseModel):
    """
    Code, organization, direction, restriction and required fund type never change once a transaction uses the head;
    name, description, order, Pranami, UPI collection and the collection targets stay editable. Explicit null clears.
    """

    head_name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    restriction_purpose: str | None = Field(None, max_length=2000)
    is_pranami: bool | None = None
    allow_upi: bool | None = None
    collection_scope_pk: UUID | None = None
    collection_fund_pk: UUID | None = None
    collection_account_pk: UUID | None = None
    display_order: int | None = Field(None, ge=0, le=10000)


class HeadResponse(BaseModel):
    finance_head_pk: UUID
    organization_pk: UUID | None
    organization_name: str | None
    is_template: bool
    head_code: str
    head_name: str
    description: str | None
    direction: str
    is_restricted: bool
    restriction_purpose: str | None
    required_fund_type: str | None
    is_pranami: bool
    allow_upi: bool
    collection_scope_pk: UUID | None
    collection_scope_code: str | None
    collection_fund_pk: UUID | None
    collection_fund_code: str | None
    collection_account_pk: UUID | None
    collection_account_label: str | None
    template_head_pk: UUID | None
    display_order: int
    status: str
    transaction_count: int = 0


class HeadListResponse(BaseModel):
    items: list[HeadResponse]
    total: int
    page: int
    page_size: int


class AdoptTemplates(BaseModel):
    organization_pk: UUID
    template_pks: list[UUID] | None = Field(None, description="Only these templates; omit for every active template")


class AdoptTemplatesResult(BaseModel):
    created: int
    skipped: int                              # heads with that code already exist in the Sangha
    items: list[HeadResponse]


# ═══════════════════════════════════════════════════════════════════════
# UPI payment requests
# ═══════════════════════════════════════════════════════════════════════

class PaymentRequestCreate(BaseModel):
    """A treasurer asks a payer to pay by UPI; the head decides the scope, fund and account."""

    finance_head_pk: UUID
    amount: Amount
    sangha_sevi_id: str | None = Field(None, max_length=20, description="The paying member (e.g. SS12), if any")
    payer_name: str | None = Field(None, max_length=200, description="For a payer who is not a member")
    note: str | None = Field(None, max_length=500)


class MyPayRequest(BaseModel):
    """A signed-in member paying their OWN Pranami; the payer is the token, never a field."""

    finance_head_pk: UUID
    amount: Amount


class PaymentRequestResponse(BaseModel):
    upi_payment_request_pk: UUID
    request_reference: str
    finance_head_pk: UUID
    head_name: str
    financial_account_pk: UUID
    account_label: str
    upi_vpa: str | None
    organization_name: str | None
    financial_scope_pk: UUID
    scope_code: str
    amount: Decimal
    payer_sangha_sevi_id: str | None
    payer_name: str | None
    note: str | None
    provider: str
    provider_order_id: str | None           # the gateway's own id for this order (for reconciliation; not a secret)
    pay_url: str | None
    upi_uri: str | None
    expires_at: datetime
    status: str
    provider_payment_id: str | None
    paid_amount: Decimal | None
    paid_at: datetime | None
    failure_reason: str | None
    review_reason: str | None
    transaction_reference: str | None
    receipt_number: str | None
    created_at: datetime


class PaymentRequestListResponse(BaseModel):
    items: list[PaymentRequestResponse]
    total: int
    page: int
    page_size: int


class MyPayableHead(BaseModel):
    """What a member may pay by UPI: heads of their own Sangha that are Pranami + UPI-enabled + ready."""

    finance_head_pk: UUID
    head_name: str
    description: str | None
    organization_name: str | None
    upi_vpa: str | None


class MyPayment(BaseModel):
    """The member-facing view of their own payment request (no internal review notes or ids)."""

    upi_payment_request_pk: UUID
    request_reference: str
    head_name: str
    amount: Decimal
    status: str
    pay_url: str | None
    upi_uri: str | None
    expires_at: datetime
    paid_at: datetime | None
    receipt_number: str | None


class WebhookAck(BaseModel):
    outcome: str


# ═══════════════════════════════════════════════════════════════════════
# Member-facing: "My Pranami"
# ═══════════════════════════════════════════════════════════════════════

class MyPranamiReceipt(BaseModel):
    receipt_number: str
    receipt_date: date
    amount: Decimal
    payment_method_name: str | None
    instrument_reference: str | None


class MyPranamiItem(BaseModel):
    financial_transaction_pk: UUID
    transaction_reference: str
    transaction_date: date
    year_code: str
    transaction_category: str
    finance_head_name: str
    amount: Decimal
    scope_name: str
    organization_name: str | None
    status: str
    receipts: list[MyPranamiReceipt] = []


class MyPranami(BaseModel):
    """
    The caller's OWN Pranami: posted / settled income of the Pranami categories linked to them
    (by Sangha Sevi or person). Nothing else of the books is exposed - no descriptions, no
    funds, no other member.
    """

    sangha_sevi_id: str | None
    items: list[MyPranamiItem]


# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════

class FundSummaryRow(BaseModel):
    fund_master_pk: UUID
    fund_code: str
    fund_name: str
    scope_code: str
    is_restricted: bool
    income: Decimal
    expense: Decimal
    transfers_in: Decimal
    transfers_out: Decimal
    balance: Decimal


class CategorySummaryRow(BaseModel):
    transaction_type: str
    transaction_category: str
    finance_head_name: str | None = None
    total: Decimal
    count: int


class FinanceSummary(BaseModel):
    """
    Posted/settled income and expense (ADJUSTMENT rows are excluded: their sign
    convention is PENDING, lifecycle §40), pending-approval counts, per-fund
    balances and per-category totals, for the caller's visible scopes.
    """

    financial_year_pk: UUID | None
    year_code: str | None
    financial_scope_pk: UUID | None
    income_total: Decimal
    expense_total: Decimal
    net: Decimal
    pending_transactions: int
    pending_transfers: int
    draft_transactions: int
    by_fund: list[FundSummaryRow]
    by_category: list[CategorySummaryRow]
