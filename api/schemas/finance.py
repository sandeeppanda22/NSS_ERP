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
INCOME_CATEGORIES = (
    "MEMBERSHIP_SUBSCRIPTION", "PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND",
    "DONATION_GENERAL", "DONATION_SPECIFIC_PURPOSE", "GRANT", "PUBLICATION_INCOME",
    "PROPERTY_INCOME", "MISCELLANEOUS_INCOME",
)
EXPENSE_CATEGORIES = ("EXPENSE_GENERAL", "EXPENSE_RESTRICTED")
TRANSACTION_CATEGORIES = INCOME_CATEGORIES + EXPENSE_CATEGORIES
# What a member sees as "Pranami" in their own dashboard (GET /finance/my-pranami): income of these
# categories that is already counted (POSTED / SETTLED) and linked to them.
PRANAMI_CATEGORIES = ("PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND")
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
    income_categories: list[str]
    expense_categories: list[str]
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
    transaction_category: str
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
    transaction_category: str | None = None
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
    transaction_category: str
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
