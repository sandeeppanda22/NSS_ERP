# NSS ERP — Finance Module Design

**Document ID:** SOL-FIN-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Finance
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Finance Module provides the financial management foundation for the
Nilachala Saraswata Sangha ERP.

The module shall support financial activities arising from:

- NSS organizational operations
- Organizational units at applicable levels
- Membership-related financial activities
- Pranamis
- Donations
- Grants
- Publication income
- Sinking Fund activities
- Specific-purpose funds
- Property and other lawful income
- Special events and programmes
- Other approved financial activities

The module shall preserve the financial rules established by the
authoritative NSS Bye-Laws and shall not introduce financial practices
that are not established or approved by the project.

---

# 2. Source Authority

The Finance Module shall derive its statutory and financial rules
from the authoritative NSS Bye-Laws.

The principal sources are:

### NSS Bye-Law — Section F (Funds of the Kendra Sangha)

| Document ID | Subject |
|-------------|---------|
| REF-003-F[A] | Funds of the Kendra Sangha — 9 fund sources |
| REF-003-F[b] | Maintenance of the Funds — banking and custody |
| REF-003-F[c] | Utilisation of the Funds — spending authority and restrictions |

### Mahila Sangha Bye-Law — Clause 7 (Funds)

| Document ID | Subject |
|-------------|---------|
| REF-MS-7(i) | Funds Comprising — 7 fund sources |
| REF-MS-7(ii) | Maintenance of Funds — banking and custody |
| REF-MS-7(iii) | Utilisation of Funds — spending authority and restrictions |

The Finance Module shall not supersede the Bye-Laws.

Where a conflict exists between Finance Module design and an authoritative
Bye-Law provision, the authoritative provision shall prevail.

---

# 3. Finance Module Scope

The Finance Module shall provide a common financial framework rather than
creating an independent finance system for each organizational module.

The module shall support financial activity associated with:

1. Organizational financial scopes
2. Special-event financial scopes
3. Specific-purpose financial scopes
4. Funds
5. Income
6. Expenses
7. Receipts
8. Payments
9. Transfers
10. Financial-year reporting
11. Fund utilization
12. Financial audit support
13. Financial reporting

Detailed accounting mechanisms shall be defined only where supported by
approved requirements.

---

# 4. Financial Scope Principle

## FIN-ARCH-001 — Financial Scope Independence

A financial activity shall belong to an explicitly identified Financial
Scope.

A Financial Scope may represent:

- An organizational financial scope
- A special event
- A specific-purpose financial activity
- A restricted fund
- Another formally approved financial context

Financial Scope shall not be treated as synonymous with Organization.

An organization may have multiple financial scopes.

For example:

```
Kendra
   |
   +-- Regular Kendra Finance
   |
   +-- Janmautsaba 2027 Finance
   |
   +-- Publication Fund
```

Similarly, a Sakha may maintain its normal financial activity while a
special event conducted by that Sakha may have a separately identifiable
financial scope.

---

# 5. Organizational Finance

The Finance Module shall support financial activities associated with
organizational entities represented by the Organization Module.

Applicable organizational levels may include:

- Kendra
- Anchalika
- Zilla
- Sakha
- Other statutorily recognized organizational units

The exact financial authority and scope applicable to each organizational
level shall follow the approved organizational and financial governance
rules.

Finance shall not independently redefine the statutory
organizational hierarchy.

The Organization Module remains authoritative for organizational identity
and hierarchy.

---

# 6. Special-Event Finance

## FIN-ARCH-002 — Special-Event Financial Scope

Special events and programmes may have independently identifiable
financial scopes.

Examples include:

- Janmautsaba
- Rasautsaba
- UPBS-related events
- Camps
- Conferences
- Other approved special programmes

A special-event financial scope shall remain associated with the relevant
organizational context where applicable, while maintaining its own
financial identification and reporting boundary.

A special event shall not create a separate financial accounting system.

It shall use the common Finance Module.

---

# 7. Financial Year Authority

## FIN-ARCH-003 — Financial Year as the Governing Financial Period

All Finance Module financial activity shall be associated with an NSS
Financial Year.

The Financial Year shall be the primary financial accounting and
reporting period.

Calendar Year shall not be used as the primary financial accounting or
reporting period.

The NSS Financial Year shall be:

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

The Financial Year shall be represented as a controlled Finance entity.

Financial activities shall not be assigned to an arbitrary calendar-year
period as their primary financial period.

---

# 8. Financial-Year Coverage

The following Finance activities shall be associated with a Financial
Year:

- Income
- Expenses
- Pranamis
- Donations
- Grants
- Publication income
- Sinking Fund activity
- Specific-purpose fund activity
- Receipts
- Payments
- Transfers
- Budgets, where budgeting is implemented
- Fund utilization
- Financial reports
- Event financial activity

A special event may span more than one Financial Year.

Where this occurs, financial transactions shall remain associated with
their actual Financial Year.

---

# 9. Sources of Funds — NSS Kendra Sangha

The authoritative NSS Bye-Law (REF-003-F[A]) identifies the following
fund sources:

| # | Source | Bye-Law Reference |
|---|--------|-------------------|
| 1 | Monthly subscriptions and other subscriptions of special nature realised from members | F[A](i) |
| 2 | Annual Pranamis of all kinds of all Sakha Sanghas including Mahila Sanghas | F[A](ii) |
| 3 | Special Pranamis of all Sakha Sanghas for opening a Sinking Fund in the name of the respective Sakha Sanghas under the control of Kendra Sangha | F[A](iii) |
| 4 | Donations or Pranamis of various kinds from devotees | F[A](iv) |
| 5 | Grants from Government, Semi-Government and official bodies | F[A](v) |
| 6 | Sale proceeds of books/journals published by Kendra Sangha | F[A](vi) |
| 7 | Donations or Pranamis from devotees for specific purposes | F[A](vii) |
| 8 | Income from all immovable properties of the Kendra Sangha | F[A](viii) |
| 9 | Miscellaneous income | F[A](ix) |

### Publication Income — Separate Account Requirement

F[A](vi) explicitly requires:

> Any amount received from this head should be shown in separate account
> and the funds so collected would only be spent in "Satsikshya Bistar";
> in consultation with the Parichalak.

This establishes a statutory requirement for:

1. Separate account identification for publication income
2. Restricted utilization (Satsikshya Bistar only)
3. Parichalak consultation requirement for utilization

---

# 10. Sources of Funds — Mahila Sangha

The authoritative Mahila Sangha Bye-Law (REF-MS-7(i)) identifies the
following fund sources:

| # | Source | Bye-Law Reference |
|---|--------|-------------------|
| 1 | Pranamis of various categories | 7(i)(a) |
| 2 | Voluntary donations received from devotees and patronisers | 7(i)(b) |
| 3 | Donations of various kinds for specific purpose | 7(i)(c) |
| 4 | Grants from Government, Semi-Government and Non-Official Bodies including Kendra Sangha | 7(i)(d) |
| 5 | Miscellaneous contributions | 7(i)(e) |
| 6 | Earnings from landed properties and other sources | 7(i)(f) |
| 7 | Landed properties held in the name of the President | 7(i)(g) |

---

# 11. Maintenance of Funds

## NSS Kendra Sangha (REF-003-F[b])

Funds shall be kept in:

- Post Office Savings Bank, OR
- Any nationalised Commercial Bank

In the following account types:

- Current accounts
- Fixed Deposit accounts
- Savings Bank accounts
- Or combination of banks and Post Office

In the name of: Nilachala Saraswata Sangha

Operated jointly by: Secretary AND Treasurer of the Kendra Sangha

## Mahila Sangha (REF-MS-7(ii))

Funds shall be kept in:

- Postal Savings Bank, OR
- State Bank of India, OR
- Both

Operated jointly by: Treasurer AND Secretary of the Sangha

---

# 12. Utilisation of Funds

## NSS Kendra Sangha (REF-003-F[c])

Key utilisation rules:

1. Funds utilised as per decisions of the Governing Body
2. Permitted purposes:
   - Management of Kendra Sangha
   - Nilachala Kutir
   - Smruti Mandir at Puri
   - Sikshya Kendra at Biratung
   - Affiliated Sakha Sanghas
   - Institutions run or sponsored by Kendra Sangha
3. Pancha Yagna expenditure (Atithi Satkar at Sikshya Kendra)
4. Specific-purpose funds: spent for that particular purpose only
5. Governing Body may sanction donations to Saraswata Matha / Guru Dhama
   for specific purpose
6. Secretary/Assistant Secretary: legal representative for receiving
   donations/grants with Governing Body prior approval

## Mahila Sangha (REF-MS-7(iii))

Key utilisation rules:

1. Spent by Governing Body in consultation with NSS Parichalak
2. Permitted purposes:
   - Birthday Ceremony at Nilachala Kutir
   - Day-to-day Kutir expenditure
   - Training centres, educational institutions, Sanskrit Pathasala
   - Publication of books on Shri Shri Thakur
   - Maintenance/cleanliness of compound
   - Repair, maintenance, additions to Kutir buildings
   - Contributions to NSS-sponsored activities
   - President/Vice-President expenses
3. All expenditure supported by a relevant resolution of the Governing Body
4. Specific-purpose donations: spent for that purpose alone

---

# 13. Restricted and Specific-Purpose Funds

The Finance Module shall support financial activities whose utilization
is restricted to an approved purpose.

Where the Bye-Laws require separate accounts or separate utilization for
a particular fund or income source, the Finance Module shall preserve that
separation.

Statutoryly identified restricted funds:

| Fund | Restriction | Source |
|------|-------------|--------|
| Publication income | Separate account; Satsikshya Bistar only; Parichalak consultation | F[A](vi) |
| Specific-purpose donations (NSS) | Spent for that particular purpose only | F[c](iv) |
| Specific-purpose donations (Mahila) | Spent for that purpose alone | MS-7(iii)(j) |
| Sinking Fund | In the name of the respective Sakha Sanghas under control of Kendra | F[A](iii) |

Funds shall not be treated as unrestricted merely because the underlying
transaction is recorded in the common Finance Module.

---

# 14. Sinking Fund

The Bye-Law identifies a Sinking Fund established through:

> Special Pranamis of all Sakha Sanghas for opening a Sinking fund in
> the name of the respective Sakha Sanghas under the control of Kendra
> Sangha.

This establishes:

1. The Sinking Fund is per-Sakha (in the name of the respective Sakha)
2. The fund is under the control of Kendra Sangha
3. The source is Special Pranamis from the Sakha

The Finance Module shall support Sinking Fund as a distinct fund
category with Sakha-level identification and Kendra-level control.

---

# 15. Income

The Finance Module shall support recording of income according to the
approved source classification.

Source categories derived from the authoritative Bye-Laws:

- Membership subscription
- Pranami (various categories)
- Donation (general)
- Donation (specific-purpose)
- Grant (Government/Semi-Government/official)
- Publication income
- Property income
- Sinking Fund contribution
- Miscellaneous lawful income

The detailed receipt and transaction model shall be defined in the
Finance Business Rules and Table Design documents.

---

# 16. Expenses and Utilization

Financial utilization shall be recorded against the applicable Financial
Scope and Financial Year.

Where a fund has a restricted purpose, utilization shall be validated
against the applicable restriction.

The Finance Module shall not permit unrestricted classification of a
restricted fund without an approved rule.

Detailed expense categories and approval workflows remain subject to
Finance Business Rules.

---

# 17. Receipts and Payments

The Finance Module shall distinguish financial transactions from their
associated receipt or payment evidence where required.

The final design shall determine:

- Receipt numbering
- Payment numbering
- Transaction references
- Payment methods
- Supporting documents
- Approval requirements
- Cancellation/reversal
- Adjustment handling

These details are not frozen by this Design document.

---

# 18. Transfers

The Finance Module may need to support transfers between authorized
financial scopes or funds.

Examples may include:

- Sakha Pranami to Kendra (statutory flow)
- Kendra grant to Mahila (statutory flow)
- Organizational fund transfers
- Event-related transfers

Transfer rules shall preserve:

- Source scope
- Destination scope
- Financial Year
- Fund classification
- Amount
- Authorization
- Audit trail

The exact transfer model remains to be established in Finance Business
Rules.

---

# 19. Budgeting

Budget functionality is recognized as a potential Finance capability.

However, the current authoritative source material does not by itself
freeze a complete ERP budgeting model.

Therefore the following remain to be established:

- Budget ownership
- Budget period
- Budget categories
- Budget approval
- Budget revision
- Budget-versus-actual reporting
- Event budgets
- Fund-specific budgets

No budget schema shall be frozen solely from this Design document.

---

# 20. Financial Authority and Approval

Financial authority shall follow the applicable NSS governance and
organizational rules.

The Finance Module shall consume the common:

- Authentication
- Administration / RBAC
- Organizational scope
- Governance

framework.

Finance shall not create an independent authentication or authorization
framework.

### Statutory Financial Authority

| Authority | NSS | Mahila |
|-----------|-----|--------|
| Utilisation decisions | Governing Body | Governing Body (in consultation with NSS Parichalak) |
| Joint account operation | Secretary + Treasurer | Treasurer + Secretary |
| Legal/grant representation | Secretary / Assistant Secretary | — |
| Expenditure resolution | Required (implied) | Explicitly required for all items |

The exact financial approval matrix shall be defined in Finance Business
Rules after the authoritative governance provisions are fully mapped.

---

# 21. Auditability

Financial transactions shall be auditable.

The Finance Module shall use the common NSS ERP audit architecture.

It shall not create an independent audit framework.

Financial records shall preserve sufficient information to establish:

- Who performed the action
- What was changed
- When it occurred
- Applicable Financial Year
- Financial Scope
- Fund/category
- Transaction reference
- Applicable authorization

Centralized audit responsibilities remain with the Audit Module.

---

# 22. Organizational Scope and Access

Finance access shall respect the common organizational authorization
framework.

A user shall only access financial information for the organizational
scope permitted by the Administration/RBAC architecture, subject to
approved Finance-specific access rules.

Finance shall not redefine:

- Kendra hierarchy
- Anchalika hierarchy
- Zilla hierarchy
- Sakha hierarchy
- Application roles

Those remain owned by the Organization and Administration modules.

---

# 23. Reporting

Finance reporting shall be primarily Financial-Year based.

The principal reporting dimensions shall include, where applicable:

```
Financial Year
    ↓
Financial Scope
    ↓
Fund / Financial Category
    ↓
Transaction
```

Reports may provide organizational, event, fund and consolidated views.

The Reports Module remains the common reporting layer.

Finance shall provide the authoritative financial data required by
Reports.

---

# 24. Inter-Module Relationships

The Finance Module consumes information from:

| Module | Relationship |
|--------|-------------|
| Foundation | Master-data infrastructure, common reference data |
| Person | Person identity where financially relevant |
| Organization | Organizational financial scope |
| Membership | Membership subscriptions, Sangha Sevi identity |
| Publications | Publication-related income |
| Governance | Financial authority and approval context |
| Authentication | User identity |
| Administration | Role and organizational authorization scope |
| Audit | Centralized audit trail |
| Reports | Financial reporting and analytics |

Finance shall not duplicate the ownership of these domains.

---

# 25. Financial Data Ownership

The Finance Module shall own financial-domain records.

The following principles apply:

- Person owns person identity.
- Organization owns organizational identity.
- Membership owns membership identity.
- Publications owns publication identity.
- Finance owns financial transactions and financial scope.
- Audit owns centralized audit records.
- Reports consumes authoritative Finance data for reporting.

Shared references shall use the established cross-module database
standards.

---

# 26. Existing Historical Finance Proposal

An earlier NSS ERP schema review proposed the following Finance tables:

```
pranami
pranami_receipt
donation
grant
publication_income
sinking_fund
financial_year
```

This historical proposal is retained as reference material only.

It is NOT automatically treated as the final frozen Finance schema.

The final Finance schema shall be derived from:

1. Authoritative Bye-Law provisions
2. Approved Finance Business Rules
3. Financial Scope requirements
4. Financial-Year requirements
5. Cross-module database standards
6. Approved Finance Table Design

---

# 27. What This Design Freezes

This document establishes the following architectural principles:

| # | Principle |
|---|-----------|
| 1 | Finance is a standalone Solution module |
| 2 | Finance is a common financial framework (not per-module) |
| 3 | Financial Scope is distinct from Organization (FIN-ARCH-001) |
| 4 | An organization may have multiple financial scopes |
| 5 | Special events may have independent financial scopes (FIN-ARCH-002) |
| 6 | Financial Year is the primary financial period (FIN-ARCH-003) |
| 7 | NSS Financial Year: 01 April to 31 March |
| 8 | Calendar Year is not the primary financial accounting period |
| 9 | All financial activities are associated with a Financial Year |
| 10 | Restricted/specific-purpose funds retain utilization boundaries |
| 11 | Publication income requires separate account (statutory) |
| 12 | Sinking Fund is per-Sakha under Kendra control |
| 13 | Finance consumes common Auth/RBAC/Audit infrastructure |
| 14 | Finance does not create duplicate organizational or security infrastructure |
| 15 | Financial reporting is primarily Financial-Year based |
| 16 | NSS and Mahila fund sources are both statutorily established |

---

# 28. Not Yet Frozen

The following shall NOT be considered frozen by this document:

```
Exact Finance table list
General ledger design
Double-entry accounting model
Chart of accounts
Bank reconciliation
Vendor management
Invoice management
Tax/GST/TDS functionality
Payment gateway integration
Online payment processing
Budget schema
Expense approval workflow
Receipt workflow
Payment workflow
Transfer workflow
Financial closing process
Opening/closing balances
Reconciliation rules
Detailed event accounting
Inter-organization accounting
Exact financial permissions
Exact financial reporting schema
FDR/investment tracking
Depreciation / fixed asset model
External audit compliance model
```

These require separate approved requirements/business-rule decisions
before implementation.

---

# 29. Design Principles

The Finance Module shall follow the NSS ERP architectural principles:

- Database First → API First → UI First within implementation
- Master-data-driven design
- Common security architecture
- Common audit architecture
- Organizational scope enforcement
- Financial-Year-based accounting
- Historical-data preservation
- No duplicate domain ownership
- Configuration over hardcoding
- Authoritative-source supremacy

---

# 30. Status

```
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0

MODULE:
Finance

DOCUMENT ID:
SOL-FIN-001

TABLE DESIGN:
NOT YET FROZEN

API:
NOT YET DESIGNED

UI:
NOT YET DESIGNED
```

---

# End of Document
