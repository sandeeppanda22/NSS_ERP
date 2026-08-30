# NSS ERP — Administration Correspondence Register Lifecycle

**Document ID:** SOL-ADMIN-007
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration (Correspondence Register Capability)
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the state transitions and lifecycle rules for the Correspondence Register entities.

The Correspondence Register records official communications. It does not manage the lifecycle of the underlying business matter — that remains with the owning module (Finance, Membership, Governance, etc.).

**Governing ERD:** SOL-ADMIN-006

---

# 2. Scope

This lifecycle covers:

    correspondence              — state transitions of a correspondence record
    correspondence_document     — association/dissociation of documents
    correspondence_finance_reference — linking/unlinking Finance transactions

This lifecycle does NOT cover:

    Finance transaction lifecycle       — Finance module
    Document storage lifecycle          — Foundation module
    Domain-specific request lifecycle   — Respective owning module
    Membership renewal lifecycle        — Membership module
    Governance decision lifecycle       — Governance module

---

# 3. correspondence Lifecycle

## 3.1 States

    REGISTERED       — correspondence recorded in the register
    PENDING_ACTION   — action required from responsible person/office
    ACTIONED         — required action has been performed
    CLOSED           — correspondence fully resolved, no further action expected

States are controlled via Foundation master_data (status_master_data_pk).

## 3.2 State Transition Diagram

    ┌──────────────┐
    │  REGISTERED  │
    └──────┬───────┘
           │
           │ assign_action
           ▼
    ┌──────────────────┐
    │  PENDING_ACTION  │◄─────────────┐
    └──────┬───────────┘              │
           │                          │
           │ mark_actioned            │ reopen
           ▼                          │
    ┌──────────────┐                  │
    │   ACTIONED   │──────────────────┘
    └──────┬───────┘
           │
           │ close
           ▼
    ┌──────────────┐
    │    CLOSED    │──────────────────→ PENDING_ACTION (reopen)
    └──────────────┘

## 3.3 Transitions

| From | To | Trigger | Guard |
|------|-----|---------|-------|
| REGISTERED | PENDING_ACTION | assign_action | At least one responsible party must be assigned: responsible_person_pk OR responsible_organization_pk |
| REGISTERED | ACTIONED | mark_actioned | Allowed when no separate action is required (e.g., filed for record only) |
| REGISTERED | CLOSED | close | Allowed when correspondence requires no action and is complete on registration |
| PENDING_ACTION | ACTIONED | mark_actioned | Action performed; remarks should document what was done |
| ACTIONED | CLOSED | close | All follow-up complete; no further action expected |
| ACTIONED | PENDING_ACTION | reopen | Further action discovered after initial actioning |
| CLOSED | PENDING_ACTION | reopen | Reopened due to new information or follow-up requirement |

## 3.4 Transition Rules

### 3.4.1 REGISTERED → PENDING_ACTION

- Triggered when the correspondence requires action from a responsible person or office
- Guard: at least one responsible party must be assigned: `responsible_person_pk` OR `responsible_organization_pk`
- This is the normal initial transition for correspondence that requires follow-up

### 3.4.2 REGISTERED → ACTIONED

- Permitted when the correspondence is informational or the required action was performed immediately at the point of registration
- Example: A circular received and filed — no separate action required beyond registration

### 3.4.3 REGISTERED → CLOSED

- Permitted when correspondence is purely for record and requires no action whatsoever
- Example: Duplicate copy of a previously actioned letter; acknowledgement receipt

### 3.4.4 PENDING_ACTION → ACTIONED

- The responsible person or authorized user marks the correspondence as actioned
- Remarks should record what action was taken
- Does NOT mean the matter is closed — only that the immediate action is done

### 3.4.5 ACTIONED → CLOSED

- All follow-up is complete
- No further communication, payment, decision, or action is expected
- The correspondence is retained in the register for historical reference

### 3.4.6 ACTIONED → PENDING_ACTION (reopen)

- New information surfaces that requires further action
- Example: Government reminder received after initial response was sent
- Remarks should document why the correspondence was reopened

### 3.4.7 CLOSED → PENDING_ACTION (reopen)

- A previously closed correspondence requires renewed attention
- Example: Follow-up letter received months after closure
- Remarks should document the reason for reopening

### 3.4.8 CLOSED → ACTIONED — NOT PERMITTED

CLOSED → ACTIONED is explicitly rejected as a valid transition. Reopening always means new work is pending; therefore the target state is always PENDING_ACTION.

If a closed correspondence requires attention, the path is:

    CLOSED → PENDING_ACTION → ACTIONED → CLOSED

## 3.5 Semantic Distinction: ACTIONED vs CLOSED

    ACTIONED
        The immediate required action has been performed.
        The matter may still be in progress elsewhere.
        Further correspondence or follow-up is possible.

    CLOSED
        The correspondence is fully resolved.
        No further action, response, or follow-up is expected.
        The record remains for audit and historical reference.

Example:

    Government property tax demand letter:
        REGISTERED   → letter recorded
        PENDING_ACTION → awaiting payment
        ACTIONED     → payment made (Finance transaction created)
        CLOSED       → receipt received, matter complete

## 3.6 Direction and Lifecycle

Both INWARD and OUTWARD correspondence follow the same state machine.

The lifecycle does not change based on direction. However, typical patterns differ:

    INWARD (received by NSS):
        Usually enters as REGISTERED → PENDING_ACTION
        because received correspondence typically requires a response or action.

    OUTWARD (sent by NSS):
        May enter as REGISTERED → ACTIONED or REGISTERED → CLOSED
        because the act of sending may itself be the action.

These are usage patterns, not lifecycle constraints. Both directions support all transitions.

## 3.7 Initial State

All correspondence records enter the system in REGISTERED state.

There is no DRAFT state. A correspondence record exists only once it is formally registered.

## 3.8 Terminal States

CLOSED is the only terminal state, but it is soft-terminal — reopening is permitted.

No correspondence record is ever hard-deleted from the register. Deletion is not a lifecycle event.

---

# 4. Creation Lifecycle

## 4.1 Inward Correspondence Creation

    1. User registers inward correspondence
    2. System generates reference number (NSS/IN/YYYY-YY/NNN)
    3. Record enters REGISTERED state
    4. User optionally attaches documents
    5. User optionally assigns responsible person/office
    6. If responsible party assigned → transition to PENDING_ACTION

Steps 4–6 may occur at creation time or subsequently.

## 4.2 Outward Correspondence Creation

    1. User registers outward correspondence
    2. System generates reference number (NSS/OUT/YYYY-YY/NNN)
    3. Record enters REGISTERED state
    4. User optionally attaches documents (copy of sent letter, etc.)
    5. User determines if follow-up expected
    6. If follow-up expected → PENDING_ACTION
       If no follow-up → ACTIONED or CLOSED

## 4.3 Reference Number Assignment

- Reference number is assigned at creation and is immutable
- Sequence uses Foundation id_sequence_master
- Reference numbers are generated sequentially within the configured direction and annual period (01 Apr – 31 Mar)
- The system shall not intentionally skip numbers during normal registration
- Sequence allocation and concurrency behaviour are defined in Business Rules

---

# 5. correspondence_document Lifecycle

## 5.1 Association

Documents may be associated with a correspondence record at any point in the correspondence lifecycle (including after CLOSED, for late-arriving documents).

    ┌─────────────────────┐
    │ Document uploaded    │
    │ to document_master  │
    │ (Foundation)        │
    └──────────┬──────────┘
               │
               ▼
    ┌─────────────────────────────┐
    │ correspondence_document     │
    │ record created              │
    │ (Administration junction)   │
    └─────────────────────────────┘

## 5.2 Rules

- A document may be associated at any correspondence state
- A document may be associated with multiple correspondence records
- Association requires specifying document_purpose (ORIGINAL, RESPONSE, ATTACHMENT, SUPPORTING)
- The document itself is stored/managed by Foundation (document_master)
- Administration only manages the junction record

## 5.3 Dissociation

- A document association may be removed (junction record soft-deleted or hard-deleted — Table Design decision)
- Dissociation does not delete the document from document_master
- Dissociation should be audited (who removed, when, why)

## 5.4 Document Lifecycle Independence

The document's own lifecycle (upload, version, archive, delete) is governed by Foundation.

Correspondence only manages the relationship, not the document itself.

---

# 6. correspondence_finance_reference Lifecycle

## 6.1 Linking

A Finance transaction may be linked to a correspondence record when:

- A financial consequence arises from the correspondence (demand → payment)
- A financial transaction is documented by the correspondence (payment → receipt letter)
- A correspondence references an existing financial transaction

## 6.2 Rules

- Linking may occur at any correspondence state (including CLOSED)
- The Finance transaction must already exist in Finance before linking
- Administration does not create Finance transactions — it only references them
- Linking requires specifying relationship_type
- One correspondence may link to multiple Finance transactions
- One Finance transaction may be linked from multiple correspondence records (M:N)

## 6.3 Unlinking

- A finance reference may be removed if linked in error
- Unlinking does not affect the Finance transaction itself
- Unlinking should be audited

## 6.4 Finance Transaction Lifecycle Independence

The Finance transaction's own lifecycle (creation, approval, reconciliation, reversal) is entirely governed by Finance.

Correspondence only manages the reference. If a Finance transaction is reversed or voided by Finance, the correspondence_finance_reference remains as a historical record of the relationship. The reference documents "this correspondence was related to that transaction" regardless of the transaction's current state.

---

# 7. Cross-Module Reference Lifecycle

## 7.1 General Principle

When other module references are physically implemented (Table Design decision), they shall follow the same lifecycle pattern as correspondence_finance_reference:

- Linking at any correspondence state
- Referenced record must exist in its owning module
- Unlinking permitted with audit
- Referenced record's lifecycle is independent

## 7.2 No Cascade

Changes to a referenced record in another module do NOT cascade to the correspondence:

    Finance transaction reversed → correspondence remains unchanged
    Membership record cancelled → correspondence remains unchanged
    Property record archived → correspondence remains unchanged

The correspondence documents the communication, not the current state of the business matter.

---

# 8. Audit Requirements

## 8.1 State Transitions

Every state transition shall be auditable:

    who           — user who triggered the transition
    when          — timestamp of the transition
    from_state    — previous state
    to_state      — new state
    remarks       — reason/context (especially for reopen)

## 8.2 Document Association Changes

    who           — user who added/removed the association
    when          — timestamp
    action        — associated / dissociated
    document_pk   — which document

## 8.3 Finance Reference Changes

    who           — user who linked/unlinked
    when          — timestamp
    action        — linked / unlinked
    transaction_pk — which Finance transaction

## 8.4 Audit Mechanism

Audit requirements defined in this document shall be implemented according to the project-wide Data Change Architecture.

The applicable mechanisms are:

- Standard audit columns — who/when
- Module-owned history — previous state where historical reconstruction is required
- Foundation.field_change_log — field-level change traceability

The Correspondence Register does not introduce a separate generic audit mechanism unless required by its Table Design.

---

# 9. Authorization Boundary

## 9.1 Who Can Perform Transitions

Authorization for correspondence operations uses the standard Administration RBAC mechanism:

    Permission + Organizational Scope → Effective Access

## 9.2 Scope Relevance

Correspondence operations may be scoped by responsible_organization_pk:

    Kendra-scope user → may manage correspondence assigned to Kendra
    Sakha-scope user  → may manage correspondence assigned to their Sakha

The exact permission catalogue and scope rules are defined in the RBAC matrix (not in this document).

## 9.3 This Document Does Not Define

- Specific permission names
- Role-to-permission mappings
- Scope inheritance rules
- Approval workflows for state transitions

These belong to the centralized RBAC design.

---

# 10. What This Lifecycle Does NOT Cover

    Domain-specific business matter resolution
        → Governed by the owning module

    Financial transaction creation/approval
        → Governed by Finance

    Document upload/storage/versioning
        → Governed by Foundation

    Membership request processing
        → Governed by Membership

    Governance decision-making
        → Governed by Governance

    Workflow automation / BPM
        → Not introduced

    Email/notification triggers
        → Future enhancement, not frozen here

    Escalation rules
        → Not introduced

---

# 11. Lifecycle Decisions Frozen

| Decision | Status |
|----------|--------|
| Four-state model (REGISTERED → PENDING_ACTION → ACTIONED → CLOSED) | FROZEN |
| Reopen permitted from ACTIONED and CLOSED → PENDING_ACTION only | FROZEN |
| CLOSED → ACTIONED is NOT a valid transition | FROZEN |
| No DRAFT state — record exists only when registered | FROZEN |
| Reference number assigned at creation, immutable | FROZEN |
| Both directions (INWARD/OUTWARD) follow same state machine | FROZEN |
| Documents may be associated at any state | FROZEN |
| Finance references may be linked at any state | FROZEN |
| No cascade from referenced module records | FROZEN |
| CLOSED is soft-terminal (reopenable) | FROZEN |
| No hard-delete lifecycle event | FROZEN |
| Responsible party guard: person OR organization (not person only) | FROZEN |
| Audit follows project-wide Data Change Architecture | FROZEN |

---

# 12. Open Questions

| Question | Status |
|----------|--------|
| Exact history-table requirements for correspondence state reconstruction | Table Design decision |
| Dissociation physical implementation (soft-delete flag vs. hard-delete) | Table Design decision |
| Notification/alert on follow_up_date approaching | Future enhancement — not frozen |
| Bulk state transitions (e.g., year-end closure of old correspondence) | Business Rules decision |
| Maximum reopen count or time limit | Business Rules decision — currently unlimited |

---

# 13. Status

DOCUMENT STATUS:

    DRAFT — SOURCE ALIGNED

VERSION:

    1.0.0
