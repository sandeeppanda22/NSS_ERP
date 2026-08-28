# NSS ERP — Finance Module ERD

**Document ID:** SOL-FIN-002
**Version:** 1.0.0
**Status:** DRAFT — LOGICAL DESIGN
**Module:** Finance
**Parent System:** Nilachala Saraswata Sangha ERP
**Depends On:** SOL-FIN-001 — Finance Module Design

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
NSS ERP Finance Module.

The ERD translates the architectural principles established in
SOL-FIN-001 into a logical financial-domain model.

This document does not constitute the final PostgreSQL table design.

Physical table names, column definitions, constraints, indexes and exact
foreign-key implementation shall be finalized in:

```
SOL-FIN-004 — Finance Table Design
```

---

# 2. Design Principles

The Finance ERD follows these principles:

1. Financial Year is the governing financial period.
2. Financial Scope is distinct from Organization.
3. An Organization may have multiple Financial Scopes.
4. Special events may have independent Financial Scopes.
5. Specific-purpose and restricted funds must remain identifiable.
6. Financial transactions must be attributable to a Financial Scope.
7. Financial transactions must belong to a Financial Year.
8. Financial classification shall be master-data driven where appropriate.
9. Person, Organization and Membership remain authoritative in their
   respective modules.
10. Authentication and Administration remain authoritative for identity
    and authorization.
11. Audit remains centralized.
12. Finance shall not duplicate ownership of external domains.
13. Historical financial records shall be preserved.

---

# 3. High-Level ERD

```text
                         FINANCIAL_YEAR
                               |
                               |
                               v
                       FINANCIAL_SCOPE
                         /     |      \
                        /      |       \
                       v       v        v
               ORGANIZATION   EVENT   SPECIAL_PURPOSE
                    |
                    |
                    v
                 FUND
                    |
                    |
                    v
              FINANCIAL_TRANSACTION
                 /      |       \
                /       |        \
               v        v         v
            INCOME    EXPENSE   TRANSFER
               |
               |
               v
          RECEIPT / PAYMENT
```

The diagram represents the logical relationship model.

It does not imply that every concept above must become an independent
physical table.

---

# 4. Financial Year

## Entity: Financial Year

The Financial Year is the primary financial-period entity.

### Logical responsibilities

- Identify the financial year
- Define start date
- Define end date
- Maintain financial-period status
- Provide the reporting boundary for financial activity

### Relationship

```text
FINANCIAL_YEAR
      |
      | 1 : N
      v
FINANCIAL_SCOPE

FINANCIAL_YEAR
      |
      | 1 : N
      v
FINANCIAL_TRANSACTION
```

### Period

The NSS financial year is:

```text
01 April YYYY
     through
31 March YYYY+1
```

Example:

```text
FY 2026-27
01-Apr-2026 to 31-Mar-2027
```

A calendar year shall not replace the Financial Year as the primary
financial accounting period.

---

# 5. Financial Scope

## Entity: Financial Scope

Financial Scope is the central boundary of Finance.

It identifies the context within which financial activity is managed.

A Financial Scope may represent:

- Organizational finance
- Special-event finance
- Specific-purpose finance
- Restricted financial activity
- Other approved financial contexts

### Relationship

```text
FINANCIAL_YEAR
      |
      | 1 : N
      v
FINANCIAL_SCOPE
      |
      | 1 : N
      v
FINANCIAL_TRANSACTION
```

A Financial Scope may optionally be associated with an Organization.

Therefore:

```text
FINANCIAL_SCOPE
       |
       +---- ORGANIZATION
       |
       +---- EVENT
       |
       +---- SPECIAL PURPOSE
```

The exact physical representation of these relationships remains pending
Table Design.

---

# 6. Organization Relationship

Organization remains owned by the Organization Module.

Finance references the Organization rather than recreating organizational
hierarchy.

Logical relationship:

```text
ORGANIZATION
      |
      | 1 : N
      v
FINANCIAL_SCOPE
```

An Organization may therefore have multiple Financial Scopes.

Example:

```text
Kendra
  |
  +-- Regular Finance
  |
  +-- Janmautsaba Finance
  |
  +-- Specific Purpose Fund
```

Finance shall not assume:

```text
one organization = one financial scope
```

---

# 7. Special Event Relationship

A special event may have a Financial Scope.

Logical relationship:

```text
EVENT
  |
  | 1 : 0..N
  v
FINANCIAL_SCOPE
```

Examples:

```text
Janmautsaba
     |
     +-- Financial Scope

Rasautsaba
     |
     +-- Financial Scope
```

The Event domain is not owned by Finance.

Finance only maintains the financial context associated with the event.

The exact Event entity and its future module ownership are not frozen by
this document.

---

# 8. Fund

## Entity: Fund

A Fund represents a controlled financial category or restricted pool of
financial resources.

Examples supported by the authoritative financial model include:

- General/regular financial activity
- Sinking Fund
- Publication-related income
- Specific-purpose funds
- Other approved fund categories

### Relationship

```text
FINANCIAL_SCOPE
      |
      | 1 : N
      v
FUND
      |
      | 1 : N
      v
FINANCIAL_TRANSACTION
```

A Fund may carry utilization restrictions.

The exact Fund classification structure is to be finalized in the
Business Rules and Table Design documents.

---

# 9. Financial Transaction

## Entity: Financial Transaction

Financial Transaction represents the financial movement recorded by the
Finance Module.

A transaction shall be associated with:

- Financial Year
- Financial Scope
- Applicable Fund
- Financial classification
- Amount
- Transaction date
- Transaction reference
- Audit information

Logical relationship:

```text
FINANCIAL_YEAR
      |
      +--------------------+
                           |
                           v
                    FINANCIAL_SCOPE
                           |
                           v
                         FUND
                           |
                           v
                 FINANCIAL_TRANSACTION
```

The exact transaction model is not frozen at this stage.

---

# 10. Income

Income represents money received by an applicable Financial Scope/Fund.

Potential income classifications include:

```text
Membership Subscription
Pranami
Donation
Grant
Publication Income
Property Income
Sinking Fund Contribution
Specific-Purpose Contribution
Miscellaneous Lawful Income
```

Logical relationship:

```text
FINANCIAL_TRANSACTION
        |
        +-- INCOME classification
```

The final physical representation of Income may be implemented through
transaction classification rather than a separate income table.

This remains a Table Design decision.

---

# 11. Expense

Expense represents authorized utilization of financial resources.

Logical relationship:

```text
FINANCIAL_SCOPE
      |
      v
     FUND
      |
      v
FINANCIAL_TRANSACTION
      |
      +-- EXPENSE classification
```

Where a Fund has restricted utilization, the Expense transaction shall
preserve the applicable restriction and purpose.

The detailed expense classification and approval model remain pending.

---

# 12. Receipt

A Receipt represents evidence of money received where receipt processing
is required.

Logical relationship:

```text
INCOME TRANSACTION
       |
       | 0..N
       v
    RECEIPT
```

Potential receipt sources include:

- Membership subscription
- Pranami
- Donation
- Grant
- Publication income
- Other approved income

The exact receipt numbering and physical receipt structure are not yet
frozen.

---

# 13. Payment

A Payment represents evidence of an outgoing financial settlement where
payment processing is required.

Logical relationship:

```text
EXPENSE TRANSACTION
       |
       | 0..N
       v
     PAYMENT
```

The exact payment model remains pending Finance Business Rules.

---

# 14. Transfer

Transfers represent movement between authorized financial contexts.

Conceptually:

```text
SOURCE FINANCIAL SCOPE
          |
          v
       TRANSFER
          |
          v
DESTINATION FINANCIAL SCOPE
```

A transfer shall preserve:

- Source scope
- Destination scope
- Financial Year
- Fund/category
- Amount
- Authorization
- Audit trail

The exact accounting treatment of transfers is not yet frozen.

---

# 15. Membership Subscription Relationship

Membership owns membership identity and membership lifecycle.

Finance records the associated financial activity.

Logical relationship:

```text
MEMBERSHIP
     |
     | 1 : N
     v
FINANCIAL_TRANSACTION
```

This does not transfer Membership ownership to Finance.

Finance only records the financial transaction associated with the
membership activity.

---

# 16. Publication Income Relationship

Publication identity remains owned by the Publications/Heritage domain.

Finance records the resulting financial activity.

Logical relationship:

```text
PUBLICATION
     |
     | 1 : N
     v
FINANCIAL_TRANSACTION
```

Publication-related income may be associated with a restricted or
separately identifiable Fund where required by the authoritative rules.

---

# 17. Person Relationship

Person remains the authoritative identity domain.

A financial transaction may identify a Person where required.

Examples:

- Donor
- Pranami contributor
- Member
- Other financially relevant person

Logical relationship:

```text
PERSON
  |
  | 1 : N
  v
FINANCIAL_TRANSACTION
```

Person does not own the financial transaction.

Finance owns the financial-domain record.

---

# 18. Membership / Person Identity

Where a financial activity relates specifically to a Sangha Sevi, Finance
may reference the authoritative Membership identity.

Logical relationship:

```text
PERSON
  |
  v
MEMBERSHIP
  |
  v
FINANCIAL_TRANSACTION
```

Finance shall not create a duplicate Sangha Sevi identity.

---

# 19. Authentication and Authorization

Authentication and Administration remain external authoritative modules.

Logical relationship:

```text
AUTHENTICATION
      |
      v
ADMINISTRATION
      |
      v
FINANCE ACCESS
```

Finance consumes:

- Authenticated user identity
- Application role
- Organizational scope
- Finance-specific permissions

Finance shall not create its own user, role or permission infrastructure.

---

# 20. Audit Relationship

Finance transactions require auditability.

The Audit Module remains responsible for centralized audit records.

Logical relationship:

```text
FINANCE TRANSACTION
        |
        v
COMMON AUDIT ARCHITECTURE
        |
        v
AUDIT MODULE
```

Standard per-table audit metadata shall follow
DATABASE_DESIGN_STANDARDS.md.

Finance shall not create a separate audit framework.

---

# 21. Reports Relationship

Reports consumes Finance data.

Logical relationship:

```text
FINANCE
   |
   +---- Financial Year
   +---- Financial Scope
   +---- Fund
   +---- Income
   +---- Expense
   +---- Transfers
   |
   v
REPORTS
```

Reports does not become the owner of Finance data.

---

# 22. Cross-Module Logical Model

```text
                    FOUNDATION
                        |
                        |
                FINANCIAL MASTER DATA
                        |
                        v
                FINANCIAL YEAR
                        |
                        v
              +-------------------+
              | FINANCIAL SCOPE   |
              +-------------------+
                /       |       \
               /        |        \
              v         v         v
       ORGANIZATION   EVENT   SPECIAL PURPOSE
              |
              v
             FUND
              |
              v
     FINANCIAL TRANSACTION
       /       |        \
      /        |         \
     v         v          v
  INCOME    EXPENSE    TRANSFER
     |          |
     v          v
  RECEIPT     PAYMENT

External authoritative domains:

PERSON ────────────────┐
MEMBERSHIP ────────────┤
PUBLICATIONS ──────────┤
ORGANIZATION ──────────┤
AUTHENTICATION ────────┤
ADMINISTRATION ────────┤
AUDIT ─────────────────┤
REPORTS ───────────────┘
```

---

# 23. Financial Year as Mandatory Relationship

Financial transactions shall not exist outside a Financial Year.

Conceptually:

```text
FINANCIAL_YEAR
      |
      | 1 : N
      v
FINANCIAL_TRANSACTION
```

This applies equally to:

- Organizational finance
- Special-event finance
- Specific-purpose funds
- Restricted funds
- Publication income
- Donations
- Pranamis
- Expenses
- Transfers

A transaction occurring on 31 March and another occurring on 1 April
belong to different Financial Years even if they relate to the same
event or Financial Scope.

---

# 24. Special Event Across Financial Years

A special event may span multiple Financial Years.

Example:

```text
                    JANMAUTSABA
                         |
              +----------+----------+
              |                     |
         FY 2026-27            FY 2027-28
              |                     |
         Transactions          Transactions
```

The event remains one event/domain object, while financial transactions
remain associated with their actual Financial Year.

---

# 25. Restricted Fund Relationship

```text
FINANCIAL_SCOPE
      |
      v
     FUND
      |
      +---- restriction / purpose
      |
      v
FINANCIAL_TRANSACTION
      |
      v
UTILIZATION
```

A restricted fund shall not be treated as unrestricted merely because its
transactions are stored in the common Finance system.

---

# 26. Candidate Logical Entities

The following are logical entities identified at this stage:

```text
Financial Year
Financial Scope
Fund
Financial Transaction
Receipt
Payment
Transfer
Income Classification
Expense Classification
Financial Category
```

External entities include:

```text
Person
Membership
Organization
Publication
Event
User Account
Audit Record
```

Not every logical entity above is required to become a physical table.

---

# 27. Historical Seven-Table Proposal Mapping

The historical schema proposal can be mapped conceptually as follows:

| Historical Table | Logical ERD Concept |
|-----------------|---------------------|
| financial_year | Financial Year |
| pranami | Income / Pranami transaction |
| pranami_receipt | Receipt |
| donation | Income / Donation transaction |
| grant | Income / Grant transaction |
| publication_income | Income / Publication transaction |
| sinking_fund | Fund / Restricted Fund activity |

This mapping is informative only.

It does not freeze the historical seven tables as the final physical
schema.

---

# 28. Unresolved ERD Decisions

The following remain open until Finance Business Rules and Table Design:

1. Whether Financial Scope requires a dedicated physical table.
2. Whether Event is a dedicated entity in the Finance schema or referenced
   through another module.
3. Whether Fund is a physical table or controlled master data.
4. Whether Income and Expense require separate physical tables.
5. Whether Receipt and Payment are separate physical entities.
6. Whether Transfer is a dedicated entity.
7. Whether a general Financial Transaction table is required.
8. Whether double-entry accounting is required.
9. Whether ledger/journal entities are required.
10. Whether opening and closing balances require physical persistence.
11. Whether bank accounts require Finance entities.
12. Whether budgeting requires dedicated entities.
13. Exact donor/member relationships.
14. Exact inter-organizational transfer relationships.
15. Exact event-finance relationships.
16. Exact financial authorization relationships.

These decisions shall not be inferred from this ERD.

---

# 29. ERD Status

```
DOCUMENT STATUS:
DRAFT — LOGICAL DESIGN

VERSION:
1.0.0

DOCUMENT ID:
SOL-FIN-002

PHYSICAL TABLE DESIGN:
NOT YET FROZEN

DDL:
NOT YET CREATED

API:
NOT YET DESIGNED

UI:
NOT YET DESIGNED
```

---

# End of Document
