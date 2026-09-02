# NSS ERP — Administration Correspondence Register Business Rules

**Document ID:** SOL-ADMIN-008
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration (Correspondence Register Capability)
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing the Correspondence Register capability.

Business rules constrain data validity, enforce operational semantics, and define the behavioural expectations that the application must implement.

**Governing ERD:** SOL-ADMIN-006
**Governing Lifecycle:** SOL-ADMIN-007

---

# 2. Rule Classification

Rules in this document are classified by source authority:

    CONSTITUTIONAL    — derived from NSS Bye-Laws or Mahila Sangha Bye-Laws
    SOURCE-DERIVED    — derived from the original project proposal or source material
    ERP-FROZEN        — established through architectural decisions during ERP design
    PENDING           — proposed but not yet frozen; requires explicit approval

Each rule is tagged with its classification.

---

# 3. Reference Numbering Rules

## 3.1 Format

| Direction | Format | Example |
|-----------|--------|---------|
| INWARD | `<ORG_SHORT_CODE>/IN/YYYY-YY/NNN` | ESS/IN/2026-27/001 |
| OUTWARD | `<ORG_SHORT_CODE>/OUT/YYYY-YY/NNN` | ESS/OUT/2026-27/001 |

Where `<ORG_SHORT_CODE>` is the `organization_short_code` (VARCHAR(5),
UNIQUE) of the organization that owns the correspondence register.

Additional examples:

```text
KEN/IN/2026-27/001     — Kendra inward #1
KEN/OUT/2026-27/042    — Kendra outward #42
```

**Classification:** ERP-FROZEN (per CORR-EXT-001; replaces previous
`NSS/IN/YYYY-YY/NNN` format)

## 3.2 Annual Period

- The numbering period follows the NSS annual period: 01 April – 31 March
- Sequence resets to 001 at the start of each new period (01 April)
- The YYYY-YY portion reflects the period (e.g., 2026-27 = April 2026 to March 2027)

**Classification:** ERP-FROZEN

## 3.3 Sequence Allocation

- INWARD and OUTWARD maintain separate sequences
- Each direction has its own independent counter per organization per annual period
- Sequence is monotonically increasing within an organization, direction, and period
- The system shall not intentionally skip numbers during normal registration
- Each organization (Kendra, Sakha, Anchalika, Zilla, etc.) maintains its own
  independent correspondence register

**Classification:** ERP-FROZEN (per CORR-EXT-001 — sequences are
per-organization, not global)

## 3.4 Immutability

- Once assigned, a reference number shall not be changed
- A reference number shall not be reassigned to a different correspondence record
- If a correspondence record is entered in error, it remains in the register with its original number (it may be marked CLOSED with appropriate remarks)

**Classification:** ERP-FROZEN

## 3.5 Sequence Mechanism

- Reference numbers are generated via Foundation id_sequence_master
- Sequences are per-organization, per-direction, per-financial-year
- The exact PostgreSQL sequence strategy (advisory lock, serial, application-managed) is a Table Design decision
- Concurrency handling (simultaneous registrations) is a Table Design decision

**Classification:** ERP-FROZEN (mechanism choice); Table Design (implementation detail)

## 3.6 No Finance Dependency

- Reference numbering does not require a FK to Finance financial_year
- The annual period is an organizational convention, not a financial entity dependency
- Foundation id_sequence_master manages the period boundary

**Classification:** ERP-FROZEN

---

# 4. Sender and Recipient Rules

## 4.1 Type Constraint

For each sender and recipient:

    Exactly one of the following must be populated:
        - person_pk        (when type = PERSON)
        - organization_pk  (when type = ORGANIZATION)
        - external_name    (when type = EXTERNAL)

The remaining fields for that party must be NULL.

**Classification:** ERP-FROZEN

## 4.2 Type Values

    PERSON         — a known NSS person (exists in person table)
    ORGANIZATION   — a known NSS organizational unit (exists in organization table)
    EXTERNAL       — a party not represented in the ERP

**Classification:** ERP-FROZEN

## 4.3 PERSON Validation

- sender_person_pk / recipient_person_pk must reference an existing person record
- No restriction on person's membership status (a non-member person may send/receive correspondence)
- No restriction on person's active/inactive status for historical correspondence

**Classification:** ERP-FROZEN

## 4.4 ORGANIZATION Validation

- sender_organization_pk / recipient_organization_pk must reference an existing organization record
- Represents NSS organizational units (Kendra, Sakha, Anchalika, Zilla, etc.)
- No restriction on organization's active/inactive status for historical correspondence

**Classification:** ERP-FROZEN

## 4.5 EXTERNAL Party Rules

- external_name is mandatory when type = EXTERNAL
- external_organization is optional (captures the organization name for an external party)
- No referential integrity check — these are free-text fields
- Examples: "District Collector", "State Revenue Department", "Postal Department"

Note: external_organization fields (sender_external_organization, recipient_external_organization) must be reflected in the ERD and Table Design. These are established in ERD Decision #2 (SOL-ADMIN-006 §4.4).

**Classification:** ERP-FROZEN

## 4.6 Direction and Party Semantics

    INWARD correspondence:
        sender     = who sent the communication TO NSS
        recipient  = which NSS person/organization received it

    OUTWARD correspondence:
        sender     = which NSS person/organization sent it
        recipient  = who the communication was sent TO

**Classification:** ERP-FROZEN

## 4.7 Self-Correspondence

- Internal NSS-to-NSS correspondence is permitted (e.g., Kendra circular to all Sakhas)
- Both sender and recipient may be PERSON or ORGANIZATION types simultaneously
- This covers internal circulars, memos, and inter-unit communications

**Classification:** ERP-FROZEN

---

# 5. Responsible Party Rules

## 5.1 Assignment

- At least one of responsible_person_pk or responsible_organization_pk must be populated before transitioning to PENDING_ACTION
- Both may be populated simultaneously (person within an organizational unit)
- Neither is required at REGISTERED state (may be assigned later)

**Classification:** ERP-FROZEN

## 5.2 Responsible Person

- Must reference an existing person record
- Represents the individual accountable for acting on or following up the correspondence
- May differ from the recipient (e.g., letter received by Secretary, action assigned to Treasurer)

**Classification:** ERP-FROZEN

## 5.3 Responsible Organization

- Must reference an existing organization record
- Represents the NSS organizational unit accountable for this correspondence
- Used when responsibility falls on an office/unit rather than a specific individual
- Example: "Kendra Office" responsible for government correspondence

**Classification:** ERP-FROZEN

## 5.4 Change of Responsibility

- Responsible person/organization may be reassigned at any state
- Reassignment does not automatically trigger a state transition
- Reassignment should be auditable (captured via standard audit mechanism)

**Classification:** ERP-FROZEN

---

# 6. Status and State Transition Rules

## 6.1 Valid States

    REGISTERED
    PENDING_ACTION
    ACTIONED
    CLOSED

Controlled via Foundation master_data. No additional states shall be introduced without an explicit architectural decision.

**Classification:** ERP-FROZEN

## 6.2 Transition Preconditions

| Transition | Precondition |
|-----------|-------------|
| REGISTERED → PENDING_ACTION | responsible_person_pk OR responsible_organization_pk populated |
| REGISTERED → ACTIONED | None beyond valid registration |
| REGISTERED → CLOSED | None beyond valid registration |
| PENDING_ACTION → ACTIONED | None (user asserts action taken) |
| ACTIONED → CLOSED | None (user asserts matter complete) |
| ACTIONED → PENDING_ACTION | Remarks required explaining why reopened |
| CLOSED → PENDING_ACTION | Remarks required explaining why reopened |

**Classification:** ERP-FROZEN

## 6.3 Remarks on Reopen

- Reopening (from ACTIONED or CLOSED to PENDING_ACTION) requires non-empty remarks
- Remarks must document the reason for reopening
- This is a data-entry requirement, not merely a UI suggestion

**Classification:** ERP-FROZEN

## 6.4 No Backdating of Transitions

- State transitions are recorded with the actual timestamp of the transition
- A user may not backdate a state change (e.g., "mark as actioned on last Tuesday")
- The correspondence_date and received_or_sent_date may reflect historical dates, but state transitions always use current system time

**Classification:** ERP-FROZEN

## 6.5 Bulk Operations

Bulk state transitions are not part of the frozen lifecycle architecture. If implemented as an operational capability later, they must comply with the same individual transition guards and audit requirements established in this document and SOL-ADMIN-007.

**Classification:** Not frozen — implementation capability if needed

---

# 7. Date Rules

## 7.1 correspondence_date

- The date of the communication itself (date on the letter, date of email, etc.)
- Mandatory for all correspondence
- May be in the past (registering a letter dated last week)
- Must not be in the future (a correspondence that hasn't happened yet cannot be registered)

**Classification:** ERP-FROZEN

## 7.2 received_or_sent_date

- INWARD: the date NSS received the communication
- OUTWARD: the date NSS sent the communication
- Mandatory for all correspondence
- May differ from correspondence_date (letter dated 1st, received 5th)
- Must not be in the future

**Classification:** ERP-FROZEN

## 7.3 follow_up_date

- Expected date by which follow-up action should be completed
- Nullable (not all correspondence requires follow-up by a date)
- May be in the future (that is the normal use — a target date)
- Informational only at this stage — no automatic escalation or notification is frozen

**Classification:** ERP-FROZEN

## 7.4 Date Ordering

- No strict ordering is enforced between correspondence_date and received_or_sent_date
- In practice, received_or_sent_date >= correspondence_date for inward (received after dated)
- But edge cases exist (misdated letters, backdated circulars) — the system does not reject

**Classification:** ERP-FROZEN

---

# 8. Document Association Rules

## 8.1 document_purpose Values

    ORIGINAL       — the primary communication document
    RESPONSE       — a response to this correspondence
    ATTACHMENT     — an attachment or enclosure
    SUPPORTING     — supporting/reference document

**Classification:** ERP-FROZEN (values); Table Design (CHECK vs master_data enforcement)

## 8.2 Multiple Documents

- A correspondence may have zero or more documents
- Multiple documents of the same purpose are permitted (e.g., multiple ATTACHMENTs)
- At least one ORIGINAL document is recommended but not enforced at the schema level

**Classification:** ERP-FROZEN

## 8.3 Shared Documents

- The same document_master record may be associated with multiple correspondence records
- Example: A government circular received once but relevant to three different matters
- Each association has its own document_purpose (may differ per correspondence)

**Classification:** ERP-FROZEN

## 8.4 Timing

- Documents may be associated at any correspondence state (including CLOSED)
- Late-arriving documents (e.g., response received after closure) may be attached without reopening
- Attaching a document does not trigger a state transition

**Classification:** ERP-FROZEN

---

# 9. Finance Reference Rules

## 9.1 Relationship Scope

Any Finance transaction type may be referenced from correspondence. This includes but is not limited to:

    Donation received
    Purchase payment
    Tax payment
    Refund
    Salary/honorarium
    Bank transaction
    Adjustment
    Any other Finance transaction

The M:N reference is a reusable cross-module capability — not limited to property-related or any single category of Finance transaction.

**Classification:** ERP-FROZEN

## 9.2 relationship_type Values

Candidate values (to be confirmed when Finance module model is frozen):

    PAYMENT         — correspondence resulted in or documents a payment
    RECEIPT         — correspondence resulted in or documents a receipt
    REFUND          — correspondence relates to a refund transaction
    TAX             — correspondence relates to a tax transaction
    ADJUSTMENT      — correspondence relates to a financial adjustment
    OTHER           — relationship exists but doesn't fit above categories

**Classification:** PENDING (values not frozen until Finance transaction model is established as the authority for what types exist)

Whether controlled via CHECK constraint or master_data is a Table Design decision.

## 9.3 Referential Integrity

- financial_transaction_pk must reference an existing Finance transaction
- The Finance transaction must already exist before the reference is created
- Administration cannot create Finance transactions through this mechanism

**Classification:** ERP-FROZEN

## 9.4 M:N Semantics

- One correspondence → many Finance transactions: permitted
- One Finance transaction → many correspondence records: permitted
- Duplicate references (same correspondence + same transaction + same relationship_type): application should prevent, enforcement mechanism is Table Design decision

**Classification:** ERP-FROZEN

## 9.5 Finance Transaction Lifecycle Independence

- If a Finance transaction is reversed, voided, or cancelled by Finance, the correspondence_finance_reference remains
- The reference documents a historical relationship, not a current state assertion
- No automatic unlinking when the referenced transaction changes state

**Classification:** ERP-FROZEN

---

# 10. Medium Rules

## 10.1 Initial Values

    POST            — postal mail
    EMAIL           — electronic mail
    HAND_DELIVERY   — delivered in person
    CIRCULAR        — official circular/notice
    FAX             — facsimile
    COURIER         — courier service

Controlled via Foundation master_data. Extensible without schema change.

**Classification:** ERP-FROZEN

## 10.2 Mandatory

- Medium is mandatory for all correspondence records
- Represents the channel through which the communication was transmitted

**Classification:** ERP-FROZEN

## 10.3 Extensibility

- New medium values may be added via Foundation master_data administration
- No code change required to add a new medium
- Deactivation of a medium does not affect existing correspondence records using that value

**Classification:** ERP-FROZEN

---

# 11. Subject and Remarks Rules

## 11.1 Subject

- Mandatory for all correspondence records
- Brief descriptive title of the communication
- No minimum/maximum length enforced at business-rule level (UI may suggest limits)

**Classification:** ERP-FROZEN

## 11.2 Remarks

- Optional (nullable)
- Used for additional notes, context, or internal observations
- May be updated at any state

**Classification:** ERP-FROZEN

---

# 12. Cross-Module Boundary Rules

## 12.1 Correspondence Does Not Own Business Matters

The Correspondence Register records the communication. It does not own, manage, or drive the underlying business process.

| Correspondence records... | Owned by... |
|--------------------------|-------------|
| "Letter requesting membership renewal" | Correspondence |
| The membership renewal process itself | Membership |
| "Government demand for property tax" | Correspondence |
| The property tax payment | Finance |
| The property record | Assets & Property |
| "Circular about annual programme" | Correspondence |
| The programme/event planning | Programmes & Events |

**Classification:** ERP-FROZEN (CORR-DECISION-003)

## 12.2 Form / Application / Correspondence Distinction

    FORM
        Structured data captured by the user.
        Owned by the domain module that defines the form.

    APPLICATION
        A request submitted by a person/organization.
        Owned by the domain module that processes the request.

    CORRESPONDENCE
        The official communication documenting or
        accompanying the form/application/request.
        Owned by Administration (Correspondence Register).

Example:

    Membership renewal:
        Form data → Membership
        Renewal request → Membership
        Application letter → Correspondence
        Acknowledgement letter → Correspondence

**Classification:** ERP-FROZEN (CORR-ARCH-002)

## 12.3 No Domain Logic in Correspondence

- Correspondence shall not contain domain-specific processing logic
- No membership approval/rejection within correspondence
- No financial calculation within correspondence
- No property valuation within correspondence
- Correspondence records the fact of communication only

**Classification:** ERP-FROZEN

## 12.4 Reusable Platform Capability

- Any module may reference correspondence records related to its business
- The consuming module does not transfer ownership to Administration
- The correspondence remains Administration-owned regardless of which module uses it
- Cross-module references are optional — no module is required to use correspondence

**Classification:** ERP-FROZEN (CORR-ARCH-002)

## 12.5 No Separate Application Module

The existence of forms, applications, and requests does not justify a separate Application module. Each domain module owns its request/application process. Correspondence provides the reusable communication-registration facility. No generic form engine or Application module is introduced.

**Classification:** ERP-FROZEN (CORR-DECISION-003)

---

# 13. Data Integrity Rules

## 13.1 Mandatory Fields (Registration)

| Field | Required at Registration |
|-------|------------------------|
| direction | Yes |
| sender_type | Yes |
| sender (person_pk / organization_pk / external_name) | Yes — per type |
| recipient_type | Yes |
| recipient (person_pk / organization_pk / external_name) | Yes — per type |
| correspondence_date | Yes |
| received_or_sent_date | Yes |
| medium_master_data_pk | Yes |
| status_master_data_pk | Yes (auto-set to REGISTERED) |
| subject | Yes |
| reference_number | Yes (system-generated) |
| responsible_person_pk | No (may be assigned later) |
| responsible_organization_pk | No (may be assigned later) |
| follow_up_date | No |
| remarks | No |

**Classification:** ERP-FROZEN

## 13.2 Soft-Delete Policy

- Correspondence records are never hard-deleted
- If a record was entered in error, it remains with its reference number
- It may be marked CLOSED with remarks indicating the error
- Physical deletion strategy (soft-delete flag, archive) is a Table Design decision

**Classification:** ERP-FROZEN

## 13.3 Uniqueness

- reference_number must be unique across the register
- correspondence_pk (UUID) is the primary key
- No natural-key uniqueness beyond reference_number (two letters from the same sender on the same date are distinct records)

**Classification:** ERP-FROZEN

---

# 14. Rules NOT Established

This document explicitly does not establish:

    Approval workflow for correspondence registration
        → No approval required to register correspondence

    Notification rules
        → Not frozen; future enhancement

    Escalation rules for overdue follow-up
        → Not frozen; future enhancement

    Archival/retention policy
        → Not frozen; operational policy

    Print/export format for registers
        → UI/reporting concern

    External party master/contacts database
        → Deferred; free text for now

    Specific permission names for correspondence operations
        → RBAC matrix concern

    Template letters or standard formats
        → Not introduced

    Auto-classification of correspondence
        → Not introduced

    Separate Application module
        → Explicitly rejected (CORR-DECISION-003)

---

# 15. Business Rules Summary

| Rule ID | Rule | Classification |
|---------|------|---------------|
| CORR-BR-001 | Reference number format: NSS/{IN\|OUT}/YYYY-YY/NNN | ERP-FROZEN |
| CORR-BR-002 | Numbering period: 01 April – 31 March | ERP-FROZEN |
| CORR-BR-003 | Separate sequences per direction per period | ERP-FROZEN |
| CORR-BR-004 | Reference number immutable once assigned | ERP-FROZEN |
| CORR-BR-005 | Sender/recipient: exactly one of person/org/external per type | ERP-FROZEN |
| CORR-BR-006 | Responsible party required for PENDING_ACTION (person OR org) | ERP-FROZEN |
| CORR-BR-007 | Reopen requires non-empty remarks | ERP-FROZEN |
| CORR-BR-008 | No backdating of state transitions | ERP-FROZEN |
| CORR-BR-009 | correspondence_date and received_or_sent_date must not be future | ERP-FROZEN |
| CORR-BR-010 | Medium is mandatory | ERP-FROZEN |
| CORR-BR-011 | Subject is mandatory | ERP-FROZEN |
| CORR-BR-012 | Finance reference: transaction must exist before linking | ERP-FROZEN |
| CORR-BR-013 | Finance reference: M:N permitted | ERP-FROZEN |
| CORR-BR-014 | No cascade from referenced module records | ERP-FROZEN |
| CORR-BR-015 | Correspondence never hard-deleted | ERP-FROZEN |
| CORR-BR-016 | Documents associable at any state | ERP-FROZEN |
| CORR-BR-017 | Correspondence does not own domain business logic | ERP-FROZEN |
| CORR-BR-018 | Finance relationship_type values | PENDING |

---

# 16. Status

DOCUMENT STATUS:

    DRAFT — SOURCE ALIGNED

VERSION:

    1.0.0
