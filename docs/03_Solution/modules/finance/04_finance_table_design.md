# NSS ERP — Finance Table Design

**Document ID:** SOL-FIN-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Finance
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the database table-design baseline for the Finance
Module.

The Finance Module provides:

- Financial Year management
- Financial Scope identification
- Fund classification and restriction
- Financial transaction recording
- Receipt evidence
- Payment evidence

The current frozen Finance schema contains exactly seven tables:

```
financial_year
financial_scope
fund_master
financial_transaction
financial_receipt
financial_payment
financial_transfer
```

---

# 2. Source Boundary

The Finance table design is derived from:

- SOL-FIN-001 — Finance Module Design (FIN-ARCH-001, 002, 003)
- SOL-FIN-002 — Finance ERD (logical entity model)
- SOL-FIN-003 — Finance Business Rules (FIN-BR-001 through FIN-BR-068)
- SOL-DB-001 — Database Design Standards

The historical seven-table proposal (pranami, pranami_receipt, donation,
grant, publication_income, sinking_fund, financial_year) is superseded
by this design.

---

# 3. Table Inventory

| # | Table | Purpose |
|--:|-------|---------|
| 1 | `financial_year` | Financial Year period entity |
| 2 | `financial_scope` | Financial context boundary |
| 3 | `fund_master` | Controlled fund/category with restriction |
| 4 | `financial_transaction` | Unified financial transaction |
| 5 | `financial_receipt` | Receipt evidence linked to transaction |
| 6 | `financial_payment` | Payment evidence linked to transaction |
| 7 | `financial_transfer` | Transfer between authorized scopes/funds |

---

# 4. Common Database Standards

All Finance tables shall follow the project-wide database standards.

## 4.1 Technical Primary Key

The project standard uses:

```
<table_name>_pk
```

Therefore:

```
financial_year_pk
financial_scope_pk
fund_master_pk
financial_transaction_pk
financial_receipt_pk
financial_payment_pk
financial_transfer_pk
```

---

## 4.2 Primary Key Type

The project database architecture uses UUID technical primary keys.

Finance tables shall use UUID-based technical PKs.

---

## 4.3 Business Identifier

Where a Finance entity requires a human/business identifier, it shall be
separate from the technical PK.

Example:

```
financial_year_pk         (UUID — relational)
year_code                 (VARCHAR — business, e.g. "2026-27")
```

The technical PK remains the relational identifier.

---

# 5. Audit Metadata

The project database standard identifies the following audit/lifecycle
fields for applicable tables:

```
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk

is_active
```

Finance tables shall include these fields where applicable.

The exact applicability to each table shall be confirmed during DDL
finalization.

---

# 6. Soft Delete

Finance records shall not be physically deleted where historical
preservation is required (FIN-BR-051).

The standard soft-delete mechanism (`is_active`, `deleted_at`,
`deleted_by_sangha_sevi_pk`) shall be used where applicable.

---

# 7. `financial_year`

## 7.1 Purpose

`financial_year` represents the NSS Financial Year — the primary
financial accounting and reporting period.

Source: FIN-BR-001, FIN-BR-002, FIN-ARCH-003

---

## 7.2 Primary Key

```
financial_year_pk
```

---

## 7.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| financial_year_pk | Technical PK (UUID) | Frozen |
| year_code | Business identifier (e.g. "2026-27") | Frozen |
| start_date | Period start (e.g. 2026-04-01) | Frozen |
| end_date | Period end (e.g. 2027-03-31) | Frozen |
| status | Period lifecycle (e.g. OPEN, CLOSED) | Frozen concept; exact values pending |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 7.4 Unique Constraint

```
year_code
```

shall be unique.

---

## 7.5 CHECK Constraints

- `start_date < end_date`
- `status` shall be controlled

---

## 7.6 Relationships

```
financial_year
      |
      | 1 : N
      v
financial_transaction

financial_year
      |
      | 1 : N
      v
financial_scope (where scope is FY-specific)
```

---

# 8. `financial_scope`

## 8.1 Purpose

`financial_scope` represents the financial context boundary within which
financial activity is managed.

A Financial Scope may represent:

- Organizational finance
- Special-event finance
- Specific-purpose finance
- Other approved financial contexts

Source: FIN-ARCH-001, FIN-BR-006, FIN-BR-007

---

## 8.2 Primary Key

```
financial_scope_pk
```

---

## 8.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| financial_scope_pk | Technical PK (UUID) | Frozen |
| scope_code | Business identifier | Frozen |
| scope_name | Human-readable label | Frozen |
| scope_type | Type classifier | Frozen concept |
| organization_pk | FK to Organization (nullable) | Frozen |
| financial_year_pk | FK to Financial Year (nullable — scope may span years) | Design candidate |
| parent_scope_pk | Self-referencing FK (nullable — for hierarchical scopes) | Design candidate |
| status | Lifecycle status | Frozen concept |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 8.4 Scope Type

Controlled values:

```
ORGANIZATION
EVENT
SPECIAL_PURPOSE
RESTRICTED_FUND
```

Additional types require explicit approval.

---

## 8.5 Organization Relationship

```
financial_scope.organization_pk
        ->
organization.organization_pk
```

Nullable: a Financial Scope is not required to reference an Organization
(e.g. special-purpose scopes).

An Organization may have multiple Financial Scopes (FIN-BR-007).

---

## 8.6 Unique Constraint

```
scope_code
```

shall be unique.

---

## 8.7 Relationships

```
financial_scope
      |
      | 1 : N
      v
financial_transaction

financial_scope
      |
      | 1 : N
      v
fund_master
```

---

# 9. `fund_master`

## 9.1 Purpose

`fund_master` represents a controlled fund or financial category within
a Financial Scope.

A Fund may carry utilization restrictions.

Source: FIN-BR-015, FIN-BR-016, FIN-BR-017

---

## 9.2 Primary Key

```
fund_master_pk
```

---

## 9.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| fund_master_pk | Technical PK (UUID) | Frozen |
| fund_code | Business identifier | Frozen |
| fund_name | Human-readable label | Frozen |
| fund_type | Type classifier | Frozen concept |
| financial_scope_pk | FK to Financial Scope | Frozen |
| is_restricted | Restriction flag | Frozen |
| restriction_purpose | Description of restriction (nullable) | Frozen |
| organization_pk | FK to Organization (nullable — for Sakha-specific funds) | Frozen |
| status | Lifecycle status | Frozen concept |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 9.4 Fund Type

Controlled values (initial set derived from statutory sources):

```
GENERAL
SINKING_FUND
PUBLICATION
SPECIFIC_PURPOSE
MEMBERSHIP_SUBSCRIPTION
PRANAMI
DONATION
GRANT
PROPERTY_INCOME
MISCELLANEOUS
```

Additional types require explicit approval (FIN-BR-017).

---

## 9.5 Sinking Fund — Sakha Identity

For Sinking Fund entries, `organization_pk` shall reference the
respective Sakha Sangha, establishing per-Sakha identity under Kendra
control (FIN-BR-023, FIN-BR-024).

---

## 9.6 Restricted Fund

Where `is_restricted = TRUE`, the system shall enforce utilization rules
(FIN-BR-019, FIN-BR-021).

Publication income and specific-purpose donations are statutorily
restricted (FIN-BR-022, FIN-BR-019).

---

## 9.7 Unique Constraint

```
(financial_scope_pk, fund_code)
```

A fund code shall be unique within its Financial Scope.

---

## 9.8 Relationships

```
fund_master
      |
      | 1 : N
      v
financial_transaction
```

---

# 10. `financial_transaction`

## 10.1 Purpose

`financial_transaction` is the unified financial transaction entity.

It records all financial movements: income, expense, and other
classified financial activity.

Source: FIN-BR-011, FIN-BR-014

---

## 10.2 Primary Key

```
financial_transaction_pk
```

---

## 10.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| financial_transaction_pk | Technical PK (UUID) | Frozen |
| transaction_reference | Business reference (unique) | Frozen |
| financial_year_pk | FK to Financial Year | Frozen |
| financial_scope_pk | FK to Financial Scope | Frozen |
| fund_master_pk | FK to Fund (nullable where fund is not applicable) | Frozen |
| transaction_type | INCOME / EXPENSE / ADJUSTMENT | Frozen concept |
| transaction_category | Controlled classification | Frozen concept |
| amount | Transaction amount | Frozen |
| transaction_date | Date of financial activity | Frozen |
| description | Transaction description (nullable) | Frozen |
| person_pk | FK to Person (nullable — donor, member, etc.) | Frozen |
| membership_pk | FK to Membership (nullable — subscription-related) | Frozen |
| status | Transaction lifecycle | Frozen concept |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 10.4 Transaction Type

Controlled values:

```
INCOME
EXPENSE
ADJUSTMENT
```

---

## 10.5 Transaction Category

Controlled values (initial set from statutory sources):

```
MEMBERSHIP_SUBSCRIPTION
PRANAMI_ANNUAL
PRANAMI_SPECIAL
PRANAMI_SINKING_FUND
DONATION_GENERAL
DONATION_SPECIFIC_PURPOSE
GRANT
PUBLICATION_INCOME
PROPERTY_INCOME
MISCELLANEOUS_INCOME
EXPENSE_GENERAL
EXPENSE_RESTRICTED
```

Additional categories require explicit approval.

The exact seed list is subject to DDL finalization.

---

## 10.6 Financial Year — Mandatory

```
financial_transaction.financial_year_pk
        ->
financial_year.financial_year_pk
```

NOT NULL. Every transaction must belong to a Financial Year (FIN-BR-067).

---

## 10.7 Financial Scope — Mandatory

```
financial_transaction.financial_scope_pk
        ->
financial_scope.financial_scope_pk
```

NOT NULL. Every transaction must belong to a Financial Scope (FIN-BR-066).

---

## 10.8 Fund — Optional

```
financial_transaction.fund_master_pk
        ->
fund_master.fund_master_pk
```

Nullable. Not every transaction requires explicit fund classification.

---

## 10.9 Person Relationship

```
financial_transaction.person_pk
        ->
person.person_pk
```

Nullable. Used where a person is financially relevant (donor, member,
contributor).

---

## 10.10 Membership Relationship

```
financial_transaction.membership_pk
        ->
sangha_sevi.sangha_sevi_pk
```

Nullable. Used for membership-subscription-related transactions.

The exact Membership FK target depends on the finalized Membership schema.

---

## 10.11 Unique Constraint

```
transaction_reference
```

shall be unique across the system.

---

## 10.12 NOT NULL Constraints

The following shall be NOT NULL:

- financial_year_pk
- financial_scope_pk
- transaction_type
- amount
- transaction_date

---

## 10.13 Indexes

Recommended indexes:

- financial_year_pk
- financial_scope_pk
- fund_master_pk
- transaction_type
- transaction_category
- transaction_date
- person_pk (where not null)

---

# 11. `financial_receipt`

## 11.1 Purpose

`financial_receipt` represents receipt evidence associated with an
income transaction.

Source: FIN-BR-031, FIN-BR-032, FIN-BR-033

---

## 11.2 Primary Key

```
financial_receipt_pk
```

---

## 11.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| financial_receipt_pk | Technical PK (UUID) | Frozen |
| receipt_number | Business receipt number | Frozen concept; numbering scheme pending |
| financial_transaction_pk | FK to Financial Transaction | Frozen |
| receipt_date | Date of receipt issuance | Frozen |
| amount | Receipt amount | Frozen |
| received_from | Description/reference of payer | Frozen concept |
| person_pk | FK to Person (nullable) | Frozen |
| status | Receipt lifecycle (ISSUED / CANCELLED) | Frozen concept |
| cancellation_reason | Reason for cancellation (nullable) | Frozen |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 11.4 Transaction Relationship

```
financial_receipt.financial_transaction_pk
        ->
financial_transaction.financial_transaction_pk
```

NOT NULL. A receipt must reference a transaction.

---

## 11.5 Receipt History

Receipts shall not be physically deleted (FIN-BR-033).

Cancellation uses status + cancellation_reason.

---

## 11.6 Unique Constraint

```
receipt_number
```

shall be unique (exact numbering scheme pending — FIN-BR-034).

---

# 12. `financial_payment`

## 12.1 Purpose

`financial_payment` represents payment/settlement evidence associated
with an expense transaction.

Source: FIN-BR-035, FIN-BR-036, FIN-BR-037

---

## 12.2 Primary Key

```
financial_payment_pk
```

---

## 12.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| financial_payment_pk | Technical PK (UUID) | Frozen |
| payment_reference | Business payment reference | Frozen |
| financial_transaction_pk | FK to Financial Transaction | Frozen |
| payment_date | Date of payment | Frozen |
| amount | Payment amount | Frozen |
| paid_to | Description/reference of payee | Frozen concept |
| payment_method | Method (CASH / BANK / etc.) | Frozen concept; values pending |
| person_pk | FK to Person (nullable) | Frozen |
| status | Payment lifecycle | Frozen concept |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 12.4 Transaction Relationship

```
financial_payment.financial_transaction_pk
        ->
financial_transaction.financial_transaction_pk
```

NOT NULL. A payment must reference a transaction.

---

## 12.5 Payment History

Payments shall not be physically deleted (FIN-BR-037).

---

# 13. `financial_transfer`

## 13.1 Purpose

`financial_transfer` represents an authorized financial movement between
Financial Scopes or Funds.

Source: FIN-BR-027, FIN-BR-028, FIN-BR-029, FIN-BR-030

---

## 13.2 Primary Key

```
financial_transfer_pk
```

---

## 13.3 Logical Attributes

| Attribute | Purpose | Status |
|-----------|---------|--------|
| financial_transfer_pk | Technical PK (UUID) | Frozen |
| transfer_reference | Business transfer reference | Frozen |
| financial_year_pk | FK to Financial Year | Frozen |
| source_scope_pk | FK to source Financial Scope | Frozen |
| destination_scope_pk | FK to destination Financial Scope | Frozen |
| source_fund_pk | FK to source Fund (nullable) | Frozen |
| destination_fund_pk | FK to destination Fund (nullable) | Frozen |
| amount | Transfer amount | Frozen |
| transfer_date | Date of transfer | Frozen |
| purpose | Transfer purpose/reason | Frozen |
| status | Transfer lifecycle | Frozen concept |
| is_active | Soft-delete flag | Frozen |
| Audit metadata | Standard audit fields | Frozen |

---

## 13.4 Source and Destination

```
financial_transfer.source_scope_pk
        ->
financial_scope.financial_scope_pk

financial_transfer.destination_scope_pk
        ->
financial_scope.financial_scope_pk
```

Both NOT NULL. A transfer must have explicit source and destination.

---

## 13.5 Financial Year — Mandatory

```
financial_transfer.financial_year_pk
        ->
financial_year.financial_year_pk
```

NOT NULL.

---

## 13.6 Unique Constraint

```
transfer_reference
```

shall be unique.

---

## 13.7 CHECK Constraint

```
source_scope_pk != destination_scope_pk
```

A transfer to the same scope is not a transfer.

---

# 14. Cross-Module Dependencies

| Finance Table | External Dependency | Module |
|---------------|-------------------|--------|
| financial_scope | organization_pk | Organization |
| fund_master | organization_pk (Sakha for Sinking Fund) | Organization |
| financial_transaction | person_pk | Person |
| financial_transaction | membership_pk | Membership |
| financial_receipt | person_pk | Person |
| financial_payment | person_pk | Person |
| All tables | created_by_sangha_sevi_pk, updated_by_sangha_sevi_pk | Authentication/Person |
| All tables | Centralized audit | Audit |

---

# 15. DDL Creation Order

Finance DDL shall be created in dependency order:

```
1. financial_year          (no Finance FK dependencies)
2. financial_scope         (depends on Organization — external)
3. fund_master             (depends on financial_scope, Organization)
4. financial_transaction   (depends on financial_year, financial_scope, fund_master, Person, Membership)
5. financial_receipt       (depends on financial_transaction, Person)
6. financial_payment       (depends on financial_transaction, Person)
7. financial_transfer      (depends on financial_year, financial_scope, fund_master)
```

---

# 16. External Module Prerequisites

Before Finance DDL can be created, the following must exist:

```
Organization tables (organization_pk)
Person tables (person_pk)
Membership tables (sangha_sevi_pk or equivalent)
Authentication (created_by/updated_by identity)
```

This places Finance after Organization, Person, Membership, and
Authentication in the implementation order.

---

# 17. Historical Proposal Comparison

| Historical Table | New Table | Notes |
|-----------------|-----------|-------|
| financial_year | financial_year | Retained — enhanced with status |
| pranami | financial_transaction | Absorbed into unified model |
| pranami_receipt | financial_receipt | Generalized to all income types |
| donation | financial_transaction | Absorbed into unified model |
| grant | financial_transaction | Absorbed into unified model |
| publication_income | financial_transaction | Absorbed into unified model |
| sinking_fund | fund_master + financial_transaction | Modeled as restricted Fund with transactions |
| — | financial_scope | NEW — implements FIN-ARCH-001 |
| — | fund_master | NEW — controlled fund entity |
| — | financial_payment | NEW — expense evidence |
| — | financial_transfer | NEW — inter-scope movement |

---

# 18. Seed / Master Data

The following seed data shall be required at DDL time or application
startup:

### Financial Year

At least one initial Financial Year record.

### Fund Types

Initial fund_type controlled values:

```
GENERAL
SINKING_FUND
PUBLICATION
SPECIFIC_PURPOSE
MEMBERSHIP_SUBSCRIPTION
PRANAMI
DONATION
GRANT
PROPERTY_INCOME
MISCELLANEOUS
```

### Scope Types

Initial scope_type controlled values:

```
ORGANIZATION
EVENT
SPECIAL_PURPOSE
RESTRICTED_FUND
```

### Transaction Types

```
INCOME
EXPENSE
ADJUSTMENT
```

---

# 19. Not Yet Frozen

The following remain subject to finalization during DDL authoring:

```
Exact VARCHAR lengths
Exact NUMERIC precision/scale for amounts
Exact status value catalogues
Receipt numbering generation mechanism
Payment method value catalogue
Exact CHECK constraint expressions
Exact index definitions
RLS policies
Exact seed data rows
Budget-related tables (if budgeting is approved)
Bank-account tables (pending FIN-BR-047)
Financial closing mechanism tables
```

---

# 20. Tables Explicitly Not Added

The following are NOT part of the current frozen Finance schema:

```
budget
budget_line
bank_account
bank_reconciliation
journal
ledger
chart_of_accounts
vendor
invoice
tax_record
payment_gateway
financial_approval
financial_authority
opening_balance
closing_balance
```

These require separate approved requirements before introduction.

---

# 21. Referential Integrity

All foreign keys shall reference authoritative technical primary keys.

Foreign keys shall not reference:

- Display names
- Labels
- Business text

unless explicitly designed as an approved business-key relationship.

---

# 22. Delete Behaviour

The final SQL must explicitly define ON DELETE behaviour.

Recommended:

- ON DELETE RESTRICT for financial_year, financial_scope, fund_master
  (prevent deletion where transactions exist)
- ON DELETE RESTRICT for financial_transaction references from
  receipt/payment

Cascading deletion shall not destroy historical financial records.

---

# 23. Status

```
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0

DOCUMENT ID:
SOL-FIN-004

TABLES FROZEN:
7

DDL:
NOT YET CREATED

API:
NOT YET DESIGNED

UI:
NOT YET DESIGNED
```

---

# End of Document
