# NSS ERP — Finance Lifecycle Rules

**Document ID:** SOL-FIN-005
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Finance
**Parent System:** Nilachala Saraswata Sangha ERP

**Related Documents:**
- SOL-FIN-001 — Finance Module Design
- SOL-FIN-002 — Finance ERD
- SOL-FIN-003 — Finance Business Rules
- SOL-FIN-004 — Finance Table Design
- SOL-DB-001 — Database Design Standards

---

# 1. Purpose

This document defines the lifecycle of Finance entities within NSS ERP.

It establishes lifecycle states and permitted transitions for:

- Financial Year
- Financial Scope
- Fund
- Financial Transaction
- Receipt
- Payment
- Financial Transfer
- Restricted Fund utilization
- Financial corrections
- Financial closure

This document does not introduce accounting rules that are not established
in the Finance Business Rules.

---

# 2. Lifecycle Principles

## FIN-LC-001 — Financial Year First

Every financial transaction shall exist within a Financial Year.

```text
Financial Year
      ↓
Financial Scope
      ↓
Fund
      ↓
Financial Transaction
```

---

## FIN-LC-002 — Financial Year Based

All Finance lifecycle processing shall use Financial Year rather than
Calendar Year.

Financial Year:

```text
01 April YYYY
      ↓
31 March YYYY+1
```

---

## FIN-LC-003 — Historical Preservation

Financial records shall not be physically deleted.

Lifecycle transitions shall preserve historical information.

---

# 3. Financial Year Lifecycle

## 3.1 States

```text
PLANNED
    ↓
OPEN
    ↓
CLOSING
    ↓
CLOSED
```

A cancelled/invalid Financial Year shall not be physically deleted.

---

## 3.2 PLANNED

A Financial Year may be created before its start date.

Example:

```text
FY 2027–28
01-Apr-2027 → 31-Mar-2028
```

State:

```text
PLANNED
```

---

## 3.3 OPEN

At the beginning of the Financial Year, it becomes operational.

```text
PLANNED → OPEN
```

Financial transactions may be recorded.

---

## 3.4 CLOSING

At the end of the Financial Year:

```text
OPEN → CLOSING
```

The system shall initiate controlled financial closing activities.

The exact closing checklist is not yet frozen.

---

## 3.5 CLOSED

After required closing activities are completed:

```text
CLOSING → CLOSED
```

A CLOSED Financial Year remains available for:

* reporting
* audit
* historical review

---

## 3.6 Closed-Year Modification

A normal transaction shall not be created directly in a CLOSED
Financial Year.

A correction shall require the approved correction/reopening mechanism.

The exact mechanism remains PENDING.

---

# 4. Financial Scope Lifecycle

## 4.1 States

```text
DRAFT
    ↓
ACTIVE
    ↓
CLOSING
    ↓
CLOSED
```

---

## 4.2 DRAFT

A Financial Scope may be configured before financial activity begins.

Example:

```text
Janmautsaba 2027 Finance
```

---

## 4.3 ACTIVE

```text
DRAFT → ACTIVE
```

Once active, the Financial Scope may receive financial transactions
subject to authorization.

---

## 4.4 CLOSING

A scope may enter:

```text
ACTIVE → CLOSING
```

when its financial activity is being finalized.

This is particularly relevant for special events.

---

## 4.5 CLOSED

```text
CLOSING → CLOSED
```

A closed scope cannot receive ordinary new financial transactions.

Historical records remain available.

---

## 4.6 Scope Inactivation

Closing/inactivating a Financial Scope shall not delete:

* transactions
* receipts
* payments
* transfers
* funds
* audit history

---

# 5. Fund Lifecycle

## 5.1 States

```text
DRAFT
    ↓
ACTIVE
    ↓
INACTIVE
```

A Fund may also be marked as restricted.

Restriction is a property of the Fund and does not itself represent a
lifecycle state.

---

## 5.2 Fund Creation

A Fund shall be created with:

* Fund code
* Fund name
* Fund type
* applicable Financial Scope where required
* restriction status
* purpose where restricted

---

## 5.3 Restricted Fund Activation

A restricted Fund shall not become ACTIVE unless its purpose/restriction
has been defined.

```text
is_restricted = TRUE
        ↓
purpose/restriction required
        ↓
ACTIVE
```

---

## 5.4 Fund Inactivation

An inactive Fund cannot receive ordinary new transactions.

Historical transactions remain preserved.

---

# 6. Financial Transaction Lifecycle

## 6.1 States

```text
DRAFT
    ↓
PENDING_APPROVAL
    ↓
APPROVED
    ↓
POSTED
    ↓
SETTLED
```

Not every transaction necessarily requires every state.

The applicable workflow depends on transaction type.

---

# 7. Transaction DRAFT

A financial transaction begins in:

```text
DRAFT
```

The system may capture:

* Financial Year
* Financial Scope
* Fund
* Transaction type
* Category
* Date
* Amount
* Person/Membership
* Purpose
* Supporting information

A DRAFT transaction has no finalized financial effect.

---

# 8. Transaction Approval

Where approval is required:

```text
DRAFT
   ↓
PENDING_APPROVAL
   ↓
APPROVED
```

Approval shall use the common Administration/RBAC framework.

The applicable authority depends on the Financial Scope and governing
rules.

---

# 9. Transaction Posting

An approved transaction becomes financially recorded:

```text
APPROVED → POSTED
```

The exact accounting/posting mechanism is not equivalent to a full
double-entry ledger because such a ledger has not yet been frozen.

---

# 10. Transaction Settlement

Where the transaction requires actual receipt or payment:

```text
POSTED → SETTLED
```

Receipt/payment evidence may be associated.

---

# 11. Transaction Rejection

A transaction awaiting approval may be rejected:

```text
PENDING_APPROVAL → REJECTED
```

A rejected transaction remains in history.

It shall not be physically deleted.

---

# 12. Transaction Cancellation

A transaction may be cancelled where permitted:

```text
DRAFT → CANCELLED

PENDING_APPROVAL → CANCELLED

APPROVED → CANCELLED
```

Cancellation shall preserve:

* cancellation reason
* cancelling user
* cancellation timestamp
* original transaction identity

The exact rules for cancelling a POSTED transaction remain PENDING.

---

# 13. Transaction Correction

Financial corrections shall preserve the original record.

The preferred logical model is:

```text
Original Transaction
        ↓
Correction / Reversal
        ↓
Corrected Financial Position
```

The original record shall not be overwritten in a way that destroys its
historical value.

The exact reversal/adjustment table design remains an implementation
decision.

---

# 14. Income Transaction Lifecycle

```text
DRAFT
  ↓
PENDING_APPROVAL
  ↓
APPROVED
  ↓
POSTED
  ↓
RECEIPT ISSUED
  ↓
SETTLED
```

The receipt is evidence associated with the transaction.

It is not a replacement for the transaction.

---

# 15. Expense Transaction Lifecycle

```text
DRAFT
  ↓
PENDING_APPROVAL
  ↓
APPROVED
  ↓
POSTED
  ↓
PAYMENT
  ↓
SETTLED
```

The applicable authorization depends on the Financial Scope and
governing rules.

---

# 16. Receipt Lifecycle

## 16.1 States

```text
DRAFT
    ↓
ISSUED
    ↓
CANCELLED
```

---

## 16.2 Receipt Draft

A receipt may be prepared before issuance.

It shall reference the applicable financial transaction.

---

## 16.3 Receipt Issuance

```text
DRAFT → ISSUED
```

Once issued, the receipt becomes historical financial evidence.

---

## 16.4 Receipt Cancellation

```text
ISSUED → CANCELLED
```

Cancellation shall require:

* reason
* authorized user
* timestamp

The receipt number shall not be silently reused.

---

# 17. Payment Lifecycle

## 17.1 States

```text
DRAFT
    ↓
APPROVED
    ↓
INITIATED
    ↓
COMPLETED
```

Failure/cancellation may occur according to the payment mechanism.

---

## 17.2 Payment Completion

A payment becomes completed only after the applicable payment evidence
has been recorded.

---

## 17.3 Payment Cancellation

A payment shall preserve its history after cancellation.

The payment number shall not be silently reused.

---

# 18. Financial Transfer Lifecycle

## 18.1 States

```text
DRAFT
    ↓
PENDING_APPROVAL
    ↓
APPROVED
    ↓
EXECUTED
    ↓
COMPLETED
```

---

## 18.2 Transfer Source and Destination

Every transfer shall identify:

```text
Source Financial Scope
        ↓
Source Fund
        ↓
Amount
        ↓
Destination Financial Scope
        ↓
Destination Fund
```

---

## 18.3 Transfer Validation

The system shall validate:

1. Source scope is active
2. Destination scope is active
3. Source and destination are different
4. Amount is greater than zero
5. Applicable Fund restrictions are satisfied
6. User has authorization
7. Financial Year is valid

---

## 18.4 Transfer Execution

```text
APPROVED → EXECUTED
```

Execution records the actual financial movement.

---

## 18.5 Transfer Completion

```text
EXECUTED → COMPLETED
```

Completion shall preserve source and destination history.

---

# 19. Restricted Fund Lifecycle

A restricted Fund follows:

```text
Fund Created
     ↓
Purpose Defined
     ↓
Fund Active
     ↓
Contribution Received
     ↓
Restricted Balance Available
     ↓
Eligible Expense
     ↓
Utilization Approved
     ↓
Expense Posted
```

---

# 20. Restricted Fund Rejection

If an expense does not satisfy the Fund's restriction:

```text
Expense
   ↓
Restriction Validation
   ↓
FAILED
```

The expense shall not be approved as a utilization of that Fund.

---

# 21. Sinking Fund Lifecycle

Sinking Fund follows the common Fund lifecycle but retains Sakha identity.

```text
Sakha
  ↓
Sinking Fund Created
  ↓
Kendra-Controlled
  ↓
Pranami Contribution
  ↓
Balance Available
  ↓
Approved Utilization
  ↓
Expenditure
  ↓
Reimbursement where applicable
```

---

# 22. Sinking Fund Reimbursement

Where Kendra expenditure is incurred from a Sakha's Sinking Fund under
the circumstances established by the Bye-Laws:

```text
Sinking Fund
      ↓
Kendra expenditure
      ↓
Sakha responsibility
      ↓
Reimbursement
```

The original expenditure shall not be rewritten after reimbursement.

The reimbursement shall be recorded as a separate financial event.

---

# 23. Special Event Finance Lifecycle

A special event may follow:

```text
Event Created
      ↓
Financial Scope Created
      ↓
Fund/Budget Configuration
      ↓
Financial Scope ACTIVE
      ↓
Income / Expense
      ↓
Event Completed
      ↓
Financial Scope CLOSING
      ↓
Financial Scope CLOSED
```

Event completion does not delete financial history.

---

# 24. Financial Year Closing

The closing process shall conceptually follow:

```text
OPEN
 ↓
CLOSING
 ↓
Validate outstanding transactions
 ↓
Validate restricted funds
 ↓
Validate transfers
 ↓
Validate receipts/payments
 ↓
Generate required reports
 ↓
Audit preparation
 ↓
CLOSED
```

The detailed closing checklist remains PENDING.

---

# 25. Closed Financial Year

After closure:

Allowed:

* reporting
* historical viewing
* audit
* approved correction process

Not ordinarily allowed:

* new ordinary transactions
* new ordinary receipts
* new ordinary payments
* new ordinary transfers

---

# 26. Financial-Year Reopening

A closed Financial Year shall not be reopened through ordinary user
operation.

If reopening is eventually supported, it shall require explicit
authorization.

The exact reopening workflow is PENDING.

---

# 27. Audit Integration

Every material Finance lifecycle transition shall be auditable.

Examples:

```text
Transaction Created
Transaction Approved
Transaction Rejected
Transaction Posted
Transaction Cancelled
Receipt Issued
Receipt Cancelled
Payment Completed
Transfer Approved
Transfer Completed
Fund Activated
Fund Closed
Financial Year Closed
```

Finance shall use the common Audit Module.

---

# 28. Authorization Integration

Lifecycle transitions shall use the common Administration/RBAC framework.

The Finance Module shall not create independent role or permission
infrastructure.

The exact permission matrix is governed by:

* statutory authority
* Financial Scope
* Administration/RBAC
* approved Finance authorization rules

---

# 29. Lifecycle Immutability

The following historical events shall not be silently overwritten:

* Issued receipt
* Completed payment
* Completed transfer
* Posted transaction
* Closed Financial Year
* Closed Financial Scope
* Historical Fund utilization

Corrections shall create traceable corrective history.

---

# 30. Invalid Transitions

The system shall reject invalid lifecycle transitions.

Examples:

```text
CLOSED → ACTIVE
without authorized reopening

CANCELLED → APPROVED

REJECTED → POSTED

INACTIVE FUND → POSTED transaction
without reactivation

CLOSED FINANCIAL SCOPE → new ordinary transaction
```

---

# 31. Lifecycle and Financial Year

A transaction's lifecycle shall not change its Financial Year.

For example:

A transaction created in FY 2026–27 and approved after 31 March shall
not automatically become a FY 2027–28 transaction.

The applicable Financial Year must remain based on the approved
transaction-date/accounting rule.

The detailed treatment of late approvals is PENDING.

---

# 32. Lifecycle and Special Events

An event may close independently of the Financial Year.

Example:

```text
Janmautsaba Event
10-Dec-2026 → 15-Dec-2026

Financial Year:
FY 2026–27
01-Apr-2026 → 31-Mar-2027
```

Closing the event does not close FY 2026–27.

---

# 33. Lifecycle and Restricted Funds

Closing a Financial Scope does not erase restricted Fund history.

Any unused restricted balance shall remain historically identifiable.

The treatment of carried-forward restricted balances is PENDING.

---

# 34. Lifecycle and Sinking Fund

A Sakha's Sinking Fund remains identifiable even when:

* the Sakha becomes inactive
* the Financial Year closes
* a special utilization occurs
* reimbursement is pending

Historical Sinking Fund identity shall be preserved.

---

# 35. Lifecycle Error Handling

Lifecycle transition failures shall provide an actionable reason.

Examples:

```text
Financial Year is CLOSED

Financial Scope is INACTIVE

Fund is INACTIVE

Restricted Fund purpose does not permit this expense

User lacks required authorization

Transfer source and destination are identical

Transaction has already been posted

Receipt has already been issued
```

---

# 36. Lifecycle Events

The implementation shall generate auditable lifecycle events for
material state changes.

The exact event schema belongs to the common Audit/Event architecture.

---

# 37. API Implication

The lifecycle shall eventually be enforced by API/service operations.

The API shall not expose unrestricted direct status modification such as:

```text
PATCH /transaction
{
    "status": "POSTED"
}
```

without transition validation.

The exact API contract is deferred to the Finance API phase.

---

# 38. UI Implication

The Finance UI shall display only valid actions for the current state.

Example:

```text
DRAFT
 ├── Edit
 ├── Submit
 └── Cancel

PENDING_APPROVAL
 ├── Approve
 ├── Reject
 └── Return

APPROVED
 ├── Post
 └── Cancel (if permitted)

POSTED
 └── View / Correct through approved mechanism
```

Exact UI behavior is deferred to the UI phase.

---

# 39. Lifecycle State Ownership

| Entity          | Primary Lifecycle                        |
| --------------- | ---------------------------------------- |
| Financial Year  | PLANNED → OPEN → CLOSING → CLOSED        |
| Financial Scope | DRAFT → ACTIVE → CLOSING → CLOSED        |
| Fund            | DRAFT → ACTIVE → INACTIVE                |
| Transaction     | DRAFT → APPROVAL → POSTED → SETTLED      |
| Receipt         | DRAFT → ISSUED → CANCELLED               |
| Payment         | DRAFT → APPROVED → INITIATED → COMPLETED |
| Transfer        | DRAFT → APPROVAL → EXECUTED → COMPLETED  |

---

# 40. Deferred Lifecycle Decisions

The following remain explicitly PENDING:

1. Exact Financial Year closing checklist
2. Financial Year reopening mechanism
3. Late approval treatment
4. Carry-forward restricted balances
5. Exact reversal/adjustment mechanism
6. Exact bank reconciliation lifecycle
7. Budget lifecycle
8. Ledger/journal lifecycle
9. Tax lifecycle
10. Detailed inter-organization transfer workflow
11. Detailed payment failure/retry lifecycle

---

# 41. Lifecycle Summary

```text
                    FINANCIAL YEAR
                          │
                          ▼
                  FINANCIAL SCOPE
                          │
                          ▼
                       FUND
                          │
                          ▼
                FINANCIAL TRANSACTION
                   │              │
                   ▼              ▼
                RECEIPT         PAYMENT
                   │              │
                   └──────┬───────┘
                          │
                          ▼
                        AUDIT


TRANSFER:

SOURCE SCOPE/FUND
        │
        ▼
     APPROVAL
        │
        ▼
    EXECUTION
        │
        ▼
    COMPLETION


SPECIAL EVENT:

EVENT
  │
  ▼
FINANCIAL SCOPE
  │
  ▼
FINANCIAL ACTIVITY
  │
  ▼
CLOSING
  │
  ▼
CLOSED
```

---

# 42. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0

DOCUMENT ID:
SOL-FIN-005

LIFECYCLE MODEL:
DEFINED

PHYSICAL TABLE DESIGN:
DEFINED

API:
NOT YET DESIGNED

UI:
NOT YET DESIGNED
```

# End of Document
