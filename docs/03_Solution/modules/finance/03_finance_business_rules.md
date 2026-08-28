# NSS ERP — Finance Business Rules

**Document ID:** SOL-FIN-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Finance
**Parent System:** Nilachala Saraswata Sangha ERP

**Related Documents:**
- SOL-FIN-001 — Finance Module Design
- SOL-FIN-002 — Finance ERD
- SOL-DB-001 — Database Design Standards

**Primary Authoritative References:**
- NSS Bye-Laws — Section F: Funds (REF-003-F[A], F[b], F[c])
- NSS Bye-Laws — Section G: Accounts and Audit
- Mahila Sangha Bye-Laws — Section 7: Funds (REF-MS-7(i), 7(ii), 7(iii))

---

# 1. Rule Classification

Every Finance rule shall identify its authority.

| Classification | Meaning |
|----------------|---------|
| **BYE-LAW** | Directly established by authoritative Bye-Laws |
| **ERP-FROZEN** | Explicitly established as an NSS ERP design rule |
| **CROSS-MODULE** | Inherited from another frozen ERP module |
| **PENDING** | Requires further business/source decision |

The ERP shall not represent an ERP design decision as a statutory
provision unless the authoritative source actually establishes it.

---

# 2. Financial Year

## FIN-BR-001 — Financial Year Authority

**Classification:** ERP-FROZEN

The NSS ERP Finance Module shall use Financial Year as the primary
financial accounting and reporting period.

Calendar Year shall not be the primary Finance reporting period.

---

## FIN-BR-002 — Financial Year Period

**Classification:** ERP-FROZEN

The NSS ERP Financial Year shall run:

```
01 April YYYY
     through
31 March YYYY+1
```

Example:

```
FY 2026-27
01-Apr-2026 to 31-Mar-2027
```

---

## FIN-BR-003 — One Financial Year per Transaction

**Classification:** ERP-FROZEN

Every financial transaction shall belong to exactly one Financial Year.

---

## FIN-BR-004 — Financial Year Boundary

**Classification:** ERP-FROZEN

A transaction dated on or before 31 March belongs to the Financial Year
ending on that 31 March.

A transaction dated on or after 1 April belongs to the new Financial
Year.

---

## FIN-BR-005 — Event Across Financial Years

**Classification:** ERP-FROZEN

A special event may span more than one Financial Year.

Financial transactions shall nevertheless belong to the Financial Year
in which the financial activity occurs.

The event does not create an alternative accounting year.

---

# 3. Financial Scope

## FIN-BR-006 — Financial Scope Required

**Classification:** ERP-FROZEN

Every financial transaction shall belong to a Financial Scope.

---

## FIN-BR-007 — Financial Scope Is Not Organization

**Classification:** ERP-FROZEN

Financial Scope shall not be treated as synonymous with Organization.

One Organization may have multiple Financial Scopes.

Example:

```
Kendra
 +-- Regular Kendra Finance
 +-- Janmautsaba Finance
 +-- Specific-Purpose Finance
```

---

## FIN-BR-008 — Organizational Financial Scope

**Classification:** ERP-FROZEN

A Financial Scope may be associated with an Organization.

The Organization Module remains authoritative for organizational identity
and hierarchy.

Finance shall not create an alternative organizational hierarchy.

---

## FIN-BR-009 — Special-Event Financial Scope

**Classification:** ERP-FROZEN

An approved special event may have an independent Financial Scope.

Examples include:

- Janmautsaba
- Rasautsaba
- Camps
- Conferences
- Other approved programmes

The event does not receive a separate Finance subsystem.

---

## FIN-BR-010 — Special-Event Scope Independence

**Classification:** ERP-FROZEN

A special-event Financial Scope shall remain separately identifiable
from the organization's regular financial activity where separate
tracking is required.

The event shall continue to use the common Finance Module.

A separate Finance system shall not be created for each event.

---

# 4. Transaction Model

## FIN-BR-011 — Unified Financial Transaction Model

**Classification:** ERP-FROZEN

Finance shall use a common financial transaction model rather than
creating independent transaction tables for every income source.

The logical transaction shall contain, directly or through controlled
relationships:

- Financial Year
- Financial Scope
- Fund/category
- Transaction type/classification
- Amount
- Transaction date
- Reference
- Source/destination context where applicable
- Audit information

---

## FIN-BR-012 — Income Classification

**Classification:** BYE-LAW

Income shall be represented through controlled transaction
classification.

Statutory income categories (NSS Bye-Law F[A]):

- Monthly subscriptions and special subscriptions from members
- Annual Pranamis of all kinds from all Sakha Sanghas including Mahila
- Special Pranamis for Sinking Fund
- Donations or Pranamis from devotees
- Government/Semi-Government/official grants
- Sale proceeds of published books/journals
- Specific-purpose donations/Pranamis
- Income from immovable properties
- Miscellaneous income

---

## FIN-BR-013 — Separate Source Classification

**Classification:** ERP-FROZEN

A unified transaction model shall not mean that all income sources lose
their statutory distinction.

Pranami, donation, grant, publication income, Sinking Fund contribution,
etc. must remain separately identifiable for reporting and utilization
where required.

---

## FIN-BR-014 — No Separate Table per Income Source

**Classification:** ERP-FROZEN

The ERP shall not create a separate primary transaction table merely
because the statutory source category differs.

```
NOT:
  pranami_transaction
  donation_transaction
  grant_transaction
  publication_income_transaction

PREFERRED:
  financial_transaction
       +
  controlled classification
```

The exact physical implementation remains subject to Table Design.

---

# 5. Fund Model

## FIN-BR-015 — Fund as Controlled Financial Entity

**Classification:** ERP-FROZEN

Finance shall represent a Fund as a controlled financial entity/category
capable of carrying:

- Identity
- Purpose
- Scope
- Restriction status
- Utilization rules
- Financial activity

The final physical representation shall be determined in
04_finance_table_design.md.

---

## FIN-BR-016 — Statutory Fund Categories

**Classification:** BYE-LAW

The Finance classification model shall support the statutory fund
sources established by the NSS Bye-Laws (F[A](i) through F[A](ix)).

---

## FIN-BR-017 — No Unapproved Fund Category

**Classification:** ERP-FROZEN

The ERP shall not represent an internally invented category as a
statutory fund category.

Additional operational classifications may be introduced only as
approved ERP classifications and shall not be misrepresented as Bye-Law
categories.

---

## FIN-BR-018 — Fund Is Not Necessarily Organization

**Classification:** ERP-FROZEN

A Fund shall not be assumed to belong one-to-one to an Organization.

A Financial Scope may contain multiple Funds.

---

# 6. Restricted Funds

## FIN-BR-019 — Specific-Purpose Restriction

**Classification:** BYE-LAW

Any funds raised or donations received for a specific purpose shall be
spent and utilized only for that particular purpose.

Source: F[c](iv), MS-7(iii)(j)

---

## FIN-BR-020 — Restricted Fund Identification

**Classification:** ERP-FROZEN

A restricted/purpose-specific financial activity shall carry an explicit
restriction or purpose classification.

The system shall not treat such money as unrestricted merely because it
is stored in the common Finance transaction model.

---

## FIN-BR-021 — Utilization Enforcement

**Classification:** ERP-FROZEN

The Finance system shall validate utilization against the applicable
restriction before an expense/payment is approved.

The enforcement mechanism shall operate through:

```
Fund / Financial Category
        |
Purpose / Restriction
        |
Expense / Payment
```

The exact database constraint versus application/service enforcement is a
Table/API implementation decision.

---

## FIN-BR-022 — Publication Income Separation

**Classification:** BYE-LAW

Publication proceeds of the Kendra Sangha shall be shown in a separate
account and used only for "Satsikshya Bistar" in consultation with the
Parichalak.

Source: F[A](vi)

The Finance system shall preserve this separate financial identity.

---

# 7. Sinking Fund

## FIN-BR-023 — Sakha-Specific Sinking Fund

**Classification:** BYE-LAW

Special Pranamis from Sakha Sanghas may establish a Sinking Fund in the
name of the respective Sakha Sangha under the control of the Kendra
Sangha.

Source: F[A](iii)

Therefore the Sinking Fund shall preserve:

```
Sinking Fund
    |
Respective Sakha (identity)
    |
Controlled by Kendra Sangha
```

---

## FIN-BR-024 — Sinking Fund Identity

**Classification:** ERP-FROZEN

Each Sakha-specific Sinking Fund shall remain separately identifiable.

The ERP shall not merge all Sakha Sinking Fund balances into one
undifferentiated balance.

---

## FIN-BR-025 — Kendra Control of Sinking Fund

**Classification:** BYE-LAW

The Sinking Fund associated with a respective Sakha remains under the
control of the Kendra Sangha.

Source: F[A](iii)

---

## FIN-BR-026 — Sinking Fund Expenditure and Reimbursement

**Classification:** BYE-LAW

Where the Kendra Sangha temporarily takes over Seva/Puja in a
Sakha/Asana Mandir and expenditure is incurred from the Sinking Fund,
the expenditure shall subsequently be reimbursed by the Sakha Sangha.

The Finance model shall therefore be capable of preserving:

```
Sinking Fund
     |
Kendra expenditure
     |
Reason / beneficiary Sakha
     |
Reimbursement obligation
     |
Subsequent reimbursement
```

---

# 8. Statutory Financial Flows

## FIN-BR-027 — Annual Pranamis from Sakha Sanghas

**Classification:** BYE-LAW

The Kendra Sangha's funds include annual Pranamis of all kinds from all
Sakha Sanghas including Mahila Sanghas.

Source: F[A](ii)

The Finance model shall support a traceable financial flow between the
contributing organizational context and Kendra financial records.

---

## FIN-BR-028 — Kendra-to-Mahila Financial Flow

**Classification:** BYE-LAW

The Mahila Bye-Laws recognize grants received from the Kendra Sangha as
one of its fund sources.

Source: MS-7(i)(d)

The Finance model shall support an authorized Kendra-to-Mahila financial
flow.

---

## FIN-BR-029 — Donations to Saraswata Matha / Guru Dhama

**Classification:** BYE-LAW

The Kendra Governing Body may sanction donations from Kendra funds to the
Saraswata Matha and Guru Dhama for specific purposes by following the
prescribed procedures.

Source: F[c](v)

Such a transaction shall preserve:

- Source financial scope
- Source fund
- Recipient
- Purpose
- Authorization
- Amount
- Financial Year
- Audit trail

---

## FIN-BR-030 — No Invented Transfer Types

**Classification:** ERP-FROZEN

The ERP shall not introduce statutory transfer types that are not
supported by the authoritative sources.

Operational transfers may exist where separately approved as ERP
functionality.

---

# 9. Receipt Model

## FIN-BR-031 — Receipt as Financial Evidence

**Classification:** ERP-FROZEN

A receipt shall represent evidence of an income/receipt transaction where
a receipt is required.

Receipt information shall remain traceable to its underlying financial
transaction.

---

## FIN-BR-032 — Receipt Is Not the Transaction

**Classification:** ERP-FROZEN

A receipt shall not replace the authoritative financial transaction.

Conceptually:

```
Financial Transaction
        |
Receipt / Evidence
```

A receipt may contain presentation/numbering information while the
transaction contains the financial fact.

---

## FIN-BR-033 — Receipt History

**Classification:** ERP-FROZEN

Issued receipts shall not be physically deleted.

Cancellation/correction shall preserve historical traceability.

---

## FIN-BR-034 — Receipt Numbering

**Classification:** PENDING

The exact receipt-number generation scheme is not frozen.

---

# 10. Payment Model

## FIN-BR-035 — Payment as Settlement Evidence

**Classification:** ERP-FROZEN

A Payment shall represent settlement/evidence associated with an
expense or outgoing financial transaction where required.

Conceptually:

```
Financial Transaction
        |
Payment / Evidence
```

---

## FIN-BR-036 — Payment Is Not Independent Financial Fact

**Classification:** ERP-FROZEN

A payment record shall not become a second authoritative representation
of the same financial transaction.

---

## FIN-BR-037 — Payment History

**Classification:** ERP-FROZEN

Completed payments shall not be physically deleted.

Corrections shall preserve historical traceability.

---

# 11. Financial Authorization

## FIN-BR-038 — Common RBAC

**Classification:** CROSS-MODULE

Finance shall use the common Authentication and Administration/RBAC
architecture.

Finance shall not create independent:

- Users
- Roles
- Permissions
- Organizational scopes

---

## FIN-BR-039 — Kendra Treasurer Authority

**Classification:** BYE-LAW

The Kendra Treasurer is responsible for the Kendra Sangha funds and for
maintaining proper cash and bank accounts covering receipts and
disbursements.

---

## FIN-BR-040 — Kendra Disbursement Authorization

**Classification:** BYE-LAW

The Kendra Treasurer may disburse funds only on the written orders of the
President for execution of a scheme approved by the Governing Body.

Therefore the Kendra Finance workflow must preserve the distinction
between:

```
Scheme approval (Governing Body)
      |
President's written order
      |
Treasurer disbursement
```

The ERP shall not collapse these into a single generic approval.

---

## FIN-BR-041 — Kendra Annual Budget

**Classification:** BYE-LAW

The Kendra Governing Body shall pass an annual budget considering
anticipated income and expenditure.

The draft budget or financially consequential resolution shall be
referred to the Advisory Board for its considered views before final
Governing Body consideration.

---

## FIN-BR-042 — Mahila Financial Authority

**Classification:** BYE-LAW

The Mahila Governing Body shall maintain proper accounts of receipts,
including Pranamis, donations and grants, and disbursements on different
accounts, and shall prepare its annual budget estimate.

---

## FIN-BR-043 — Mahila Expenditure Support

**Classification:** BYE-LAW

Mahila expenditure shall be supported by the applicable Governing Body
resolution, and specific-purpose donations shall be used only for that
purpose.

Source: MS-7(iii)(i), MS-7(iii)(j)

---

## FIN-BR-044 — Other Organizational Levels

**Classification:** PENDING

The exact Finance authorization matrix for:

- Anchalika
- Zilla
- Sakha
- Special-event scopes
- Other financial scopes

shall be frozen only after the applicable authoritative rules and
approved organizational procedures are mapped.

No generic authority matrix shall be invented from the Kendra rules.

---

# 12. Financial Accounts

## FIN-BR-045 — Kendra Fund Accounts

**Classification:** BYE-LAW

Kendra funds are to be maintained in Post Office Savings Bank and/or
nationalized Commercial Bank accounts in the name of Nilachala Saraswata
Sangha, operated jointly by the Secretary and Treasurer.

Source: F[b]

---

## FIN-BR-046 — Mahila Fund Accounts

**Classification:** BYE-LAW

Mahila funds are to be maintained in the prescribed postal/state-bank
arrangement and operated jointly by the Treasurer and Secretary.

Source: MS-7(ii)

---

## FIN-BR-047 — Bank Account Model

**Classification:** PENDING

The exact ERP bank-account model remains pending.

The ERP must not assume that one Organization has only one bank account.

---

# 13. Expense and Utilization

## FIN-BR-048 — Kendra Utilization

**Classification:** BYE-LAW

Kendra funds shall be utilized according to Governing Body decisions and
for the purposes permitted by the Bye-Laws.

Source: F[c](i), F[c](ii)

Permitted purposes include:

- Management of Kendra Sangha
- Nilachala Kutir
- Smruti Mandir at Puri
- Sikshya Kendra at Biratung
- Affiliated Sakha Sanghas
- Institutions run or sponsored by Kendra Sangha
- Pancha Yagna / Atithi Satkar at Sikshya Kendra

---

## FIN-BR-049 — Specific-Purpose Utilization

**Classification:** BYE-LAW

Funds raised or donations received for a specific purpose shall be spent
and utilized for that particular purpose only.

Source: F[c](iv)

---

## FIN-BR-050 — Mahila Utilization

**Classification:** BYE-LAW

Mahila funds may be used for the purposes specified in its Bye-Laws,
subject to the applicable consultation, resolution and purpose
requirements.

Source: MS-7(iii)

---

# 14. Financial History

## FIN-BR-051 — No Physical Deletion

**Classification:** ERP-FROZEN

Financial transactions shall not be physically deleted merely because:

- A Financial Scope becomes inactive
- An Organization changes status
- An Event closes
- A Fund becomes inactive
- A Financial Year closes

---

## FIN-BR-052 — Corrections

**Classification:** ERP-FROZEN

Financial corrections shall preserve historical traceability.

The exact reversal/adjustment mechanism remains a Table/API design
decision.

---

# 15. Financial Reporting

## FIN-BR-053 — Financial-Year Reporting

**Classification:** ERP-FROZEN

Financial reports shall default to Financial Year.

---

## FIN-BR-054 — Scope Reporting

**Classification:** ERP-FROZEN

Reports shall support financial-scope-level reporting.

---

## FIN-BR-055 — Fund Reporting

**Classification:** ERP-FROZEN

Restricted and specific-purpose financial activity shall remain
separately reportable.

---

## FIN-BR-056 — Event Reporting

**Classification:** ERP-FROZEN

Special-event Financial Scopes shall be separately reportable where such
a scope has been established.

---

# 16. Audit

## FIN-BR-057 — Common Audit Architecture

**Classification:** CROSS-MODULE

Finance shall use the common Audit Module.

Finance shall not create a separate audit framework.

---

## FIN-BR-058 — Financial Audit Support

**Classification:** BYE-LAW

Finance shall preserve sufficient records to support the required annual
audit and presentation of audited accounts.

The Kendra Bye-Laws provide for audited statements of accounts to be
placed before the General Body.

---

# 17. Mahila Finance

## FIN-BR-059 — Common Finance Infrastructure

**Classification:** ERP-FROZEN

Mahila financial activity shall use the common Finance Module.

A separate Mahila Finance application/subsystem shall not be created.

---

## FIN-BR-060 — Mahila Fund Sources

**Classification:** BYE-LAW

Mahila financial sources include:

- Pranamis of various categories
- Voluntary donations from devotees and patronisers
- Specific-purpose donations
- Government/Semi-Government/Non-Official grants including Kendra Sangha
- Miscellaneous contributions
- Landed-property and other earnings

Source: MS-7(i)(a) through MS-7(i)(g)

---

## FIN-BR-061 — Mahila Specific-Purpose Funds

**Classification:** BYE-LAW

Specific-purpose Mahila donations shall remain separately identifiable
and shall be utilized only for the stated purpose.

Source: MS-7(iii)(j)

---

# 18. Special Events

## FIN-BR-062 — Event Finance Uses Common Finance

**Classification:** ERP-FROZEN

A special event shall use the common Finance Module.

---

## FIN-BR-063 — Event Financial Scope

**Classification:** ERP-FROZEN

Where separately tracked finances are required, the event shall have a
Financial Scope.

---

## FIN-BR-064 — Event Does Not Create Financial Year

**Classification:** ERP-FROZEN

An event shall not create its own accounting year.

All event transactions remain Financial-Year based.

---

# 19. Transaction Integrity

## FIN-BR-065 — Financial Transaction Identity

**Classification:** ERP-FROZEN

Each financial transaction shall have a unique system identity.

---

## FIN-BR-066 — Financial Scope Required

**Classification:** ERP-FROZEN

A financial transaction shall not exist without an applicable Financial
Scope.

---

## FIN-BR-067 — Financial Year Required

**Classification:** ERP-FROZEN

A financial transaction shall not exist without an applicable Financial
Year.

---

## FIN-BR-068 — Classification Required

**Classification:** ERP-FROZEN

Every financial transaction shall have an approved financial
classification.

---

# 20. Pending Accounting Decisions

The following are intentionally NOT frozen by this document:

```
1.  Double-entry accounting
2.  General ledger
3.  Chart of accounts
4.  Journal structure
5.  Bank reconciliation
6.  Cash ledger design
7.  Opening balances
8.  Closing balances
9.  Tax/GST/TDS
10. Vendor management
11. Invoice management
12. Online payment gateway
13. Digital payment integration
14. Budget database model
15. Exact receipt numbering
16. Exact payment numbering
17. Exact transfer workflow
18. Exact inter-organization accounting treatment
19. Exact bank-account schema
20. Detailed financial closing workflow
```

These shall not be implemented as frozen requirements until separately
approved.

---

# 21. Resolved Design Decisions

The seven previously unresolved ERD decisions are now treated as follows:

| # | Decision | Result |
|---|----------|--------|
| 1 | Transaction model | ERP-FROZEN: unified financial transaction model |
| 2 | Fund model | ERP-FROZEN: controlled Fund entity/category |
| 3 | Receipt model | ERP-FROZEN: receipt evidence linked to transaction |
| 4 | Payment model | ERP-FROZEN: payment evidence linked to transaction |
| 5 | Restricted-fund enforcement | ERP-FROZEN: explicit restriction + utilization validation |
| 6 | Financial authorization | Partially frozen: Kendra/Mahila source-derived; other scopes PENDING |
| 7 | Sinking Fund | BYE-LAW + ERP-FROZEN: Sakha-specific, Kendra-controlled |

---

# 22. Historical Schema Proposal

The previously proposed Finance tables:

```
pranami
pranami_receipt
donation
grant
publication_income
sinking_fund
financial_year
```

are historical design material.

They shall not automatically become the physical schema.

The final table design shall be derived from these Business Rules and the
Finance ERD.

---

# 23. Status

```
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0

DOCUMENT ID:
SOL-FIN-003

BUSINESS RULES:
INITIAL RULE SET ESTABLISHED (FIN-BR-001 through FIN-BR-068)

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
