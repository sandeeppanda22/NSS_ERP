# NSS ERP — Audit Entity Relationship Design

**Document ID:** SOL-AUDIT-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Audit
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
currently frozen Audit foundation.

The current Audit foundation contains exactly two tables:

    audit_master
    system_event_log

---

# 2. Current Frozen Tables

```text
audit_master
system_event_log
```

Total:

```
2 tables
```

The project schema baseline explicitly identifies these as the current
Audit tables.

---

# 3. ERD Principle

Audit is a cross-cutting capability.

It records activity originating from other ERP modules rather than owning
the business entities themselves.

Therefore the logical architecture is:

```text
Business Module
      │
      │ significant action
      ▼
Audit Framework
      │
      ├── audit_master
      │
      └── system_event_log
```

---

# 4. High-Level ERD

```text
                         NSS ERP
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
     Membership         Governance          Finance
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            │ Auditable Action
                            ▼
                    ┌─────────────────┐
                    │  AUDIT DOMAIN   │
                    └────────┬────────┘
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
        ┌─────────────────┐    ┌────────────────────┐
        │  audit_master   │    │ system_event_log   │
        └─────────────────┘    └────────────────────┘
```

---

# 5. `audit_master`

## Purpose

`audit_master` is one of the two frozen Audit foundation tables.

It represents the audit-definition/configuration side of the Audit domain.

---

# 6. `audit_master` Identity

The project database naming standard applies.

Primary key:

```
audit_master_pk
```

The exact additional columns are defined only when supported by the
approved table-design requirements.

---

# 7. `system_event_log`

## Purpose

`system_event_log` is the second frozen Audit foundation table.

It represents system-event history.

It records significant system events requiring centralized traceability.

---

# 8. `system_event_log` Identity

The project database naming standard applies.

Primary key:

```
system_event_log_pk
```

The exact additional columns are defined only when supported by the
approved table-design requirements.

---

# 9. Logical Relationship Between the Two Tables

The available source establishes both tables as part of the Audit foundation.

It does NOT establish a definitive FK relationship between:

```
audit_master
```

and:

```
system_event_log
```

Therefore this document does NOT declare a physical:

```
audit_master_pk
    ↓
system_event_log.audit_master_pk
```

relationship as frozen.

The exact relationship requires confirmation during detailed table design.

---

# 10. Cross-Module Relationship

The more important Audit relationship is logical rather than a traditional
business-domain parent/child relationship.

Conceptually:

```text
Business Entity
      │
      ▼
Business Action
      │
      ▼
Audit Event
      │
      ▼
system_event_log
```

---

# 11. Example — Membership

```text
Membership
    │
    ▼
Membership Status Change
    │
    ▼
Audit
    │
    ▼
system_event_log
```

The Audit Module does not own the Membership record.

Membership remains the authoritative business domain.

---

# 12. Example — Governance

```text
Governance
    │
    ▼
Position Assignment
    │
    ▼
Audit
    │
    ▼
system_event_log
```

The Governance module remains the owner of the position assignment.

---

# 13. Example — UPBS

```text
UPBS
    │
    ▼
Registration / Event Action
    │
    ▼
Audit
    │
    ▼
system_event_log
```

UPBS remains the owner of the UPBS business record.

---

# 14. Example — Finance

```text
Finance
    │
    ▼
Financial Action
    │
    ▼
Audit
    │
    ▼
system_event_log
```

Finance remains the authoritative financial domain.

---

# 15. Audit Does Not Own Business Entities

The Audit Module shall not become the parent of:

```
Person
Membership
Organization
Governance
Attendance
Finance
UPBS
Sevak
```

Audit records activity against those domains.

---

# 16. No Duplicate Business History

Audit shall not replace domain-specific history tables.

For example:

```text
Membership
    │
    ├── Business History
    │      └── Membership-specific history
    │
    └── Audit
           └── system_event_log
```

Both may exist because they serve different purposes.

---

# 17. Audit vs Business History

Business history answers:

```
What happened to the business entity?
```

Audit history answers:

```
What auditable system action occurred?
```

These concepts remain separate.

---

# 18. Actor Relationship

An audit event may logically reference the actor who performed the action.

Conceptually:

```text
NSS User / Sangha Sevi
          │
          ▼
     Audit Event
```

The exact FK and actor representation are governed by the existing
Authentication/Identity architecture.

This document does not invent a new actor table.

---

# 19. No `audit_user` Table

The ERD shall not create:

```
audit_user
```

The Audit Module reuses the existing authentication/identity architecture.

---

# 20. Target Entity Relationship

An audit event may logically identify:

```
Module
Entity
Record
```

Conceptually:

```text
Audit Event
    │
    ├── Module
    ├── Entity
    └── Record Identifier
```

The source does not establish a polymorphic FK implementation.

Therefore no unsupported FK structure is frozen here.

---

# 21. Action Relationship

An audit event may identify the action performed.

Conceptually:

```text
Actor
  +
Action
  +
Target
  +
Timestamp
      │
      ▼
Audit Event
```

The exact action catalogue and physical representation require detailed
business/table design.

---

# 22. Event Logging Relationship

The logical event flow is:

```text
System Action
     │
     ▼
Audit Processing
     │
     ▼
system_event_log
```

---

# 23. `audit_master` Role

The exact relationship and purpose of `audit_master` beyond being part of
the frozen Audit foundation are not sufficiently defined in the available
source.

Therefore:

```
audit_master
```

is retained as a frozen table identity, but its detailed relational role
shall be finalized in the business-rule/table-design stages.

---

# 24. No Invented Audit Detail Tables

The following are NOT part of the current ERD:

```text
audit_field_change
audit_change_detail
audit_login_history
audit_access_log
audit_approval_history
audit_user
audit_target
audit_action_master
```

Their introduction would require an approved requirement.

---

# 25. Audit and Standard Audit Fields

Normal business tables may contain:

```
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
```

These fields do not create direct parent/child ERD relationships with
`system_event_log`.

They are record-level metadata.

---

# 26. Audit and Soft Delete

A soft-deleted business record may have:

```text
Business Record
    ↓
is_active = FALSE
```

while its audit history remains:

```text
system_event_log
    ↓
Historical event preserved
```

---

# 27. Audit and Historical Preservation

The system-wide principle is:

```
History Never Deleted
```

Therefore the Audit ERD must support preservation of historical events.

---

# 28. No Cascade Destruction of Audit History

The final physical SQL design shall avoid relationships that could
accidentally destroy audit history when a business record is deactivated
or removed from operational use.

Exact ON DELETE rules belong to the physical schema design.

---

# 29. Audit and Authentication

The logical relationship is:

```text
Authenticated Actor
        │
        ▼
     Audit Event
```

Authentication owns:

```
User Account
Role
Permission
```

Audit owns:

```
Audit History
```

---

# 30. Audit and RBAC

RBAC determines:

```
Who may perform an action.
```

Audit determines:

```
What auditable action occurred.
```

Therefore:

```text
RBAC
 │
 ├── Authorization
 │
 └── Audit
       │
       └── Traceability
```

---

# 31. Audit and Notification

An action may produce both an audit event and a notification.

Conceptually:

```text
Business Action
      │
      ├──────────► Audit
      │              │
      │              ▼
      │       system_event_log
      │
      └──────────► Notification
```

Notification is not an Audit child entity.

---

# 32. Audit and Approval

An approval action may generate an audit event.

Conceptually:

```text
Approval Workflow
      │
      ▼
Approval Action
      │
      ├── Business Approval Record
      │
      └── Audit Event
```

The approval entity remains owned by the Applications/Approvals domain.

---

# 33. Audit and Correction

For post-completion corrections:

```text
Correction Request
       │
       ▼
Approval
       │
       ▼
Business Record Correction
       │
       ▼
Audit Event
```

The original value must remain historically traceable where required by
the applicable business rules.

---

# 34. Logical Audit Architecture

```text
                         BUSINESS MODULES
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
            Business         Business        Business
             Action           Action          Action
                │               │               │
                └───────────────┼───────────────┘
                                ▼
                         AUDIT FRAMEWORK
                                │
                      ┌─────────┴─────────┐
                      ▼                   ▼
                audit_master       system_event_log
```

---

# 35. Current ERD Boundary

The current frozen ERD contains:

```text
audit_master
system_event_log
```

No additional physical entities are frozen.

---

# 36. Logical vs Physical Relationships

This document distinguishes:

### Confirmed

```text
Audit domain
    ├── audit_master
    └── system_event_log
```

### Logical

```text
Business Action
    ↓
Audit Event
    ↓
system_event_log
```

### Not Yet Frozen

```text
audit_master → system_event_log FK
Actor → Audit FK
Target → Audit FK
Action → Audit FK
```

---

# 37. Relationship Matrix

| Source          | Target                    | Status         |
| --------------- | ------------------------- | -------------- |
| Business Module | Audit                     | LOGICAL        |
| Business Action | `system_event_log`        | LOGICAL        |
| Actor           | Audit Event               | LOGICAL        |
| Target Entity   | Audit Event               | LOGICAL        |
| `audit_master`  | `system_event_log`        | NOT FROZEN     |
| Audit           | Business Entity ownership | NOT APPLICABLE |

---

# 38. ERD Diagram — Minimal Frozen Model

```text
┌───────────────────────┐
│     AUDIT DOMAIN      │
│                       │
│  ┌─────────────────┐  │
│  │  audit_master   │  │
│  └─────────────────┘  │
│                       │
│  ┌─────────────────┐  │
│  │system_event_log │  │
│  └─────────────────┘  │
│                       │
└───────────────────────┘
```

No unsupported FK line is shown between the two tables.

---

# 39. Cross-Module ERD Concept

```text
┌────────────────────┐
│ Business Module    │
│                    │
│ Business Entity    │
└─────────┬──────────┘
          │
          │ Action
          ▼
┌────────────────────┐
│ Audit Framework    │
│                    │
│ system_event_log   │
└────────────────────┘
```

---

# 40. Design Principle

Audit is a **cross-cutting historical service/domain**.

It should not force every business entity to become a child of an Audit
table.

Instead, significant actions are represented in centralized audit history.

---

# 41. Future Extension Boundary

If later requirements establish field-level change tracking, login auditing,
access auditing, approval auditing, or other specialized audit domains,
those shall be designed as separate approved extensions.

They are not part of this frozen ERD.

---

# 42. Source Alignment

The current PostgreSQL schema review identifies exactly:

```text
audit_master
system_event_log
```

under the Audit module, for a total of two Audit tables.

The broader project standards require end-to-end traceability across:

```text
REF
↓
REQ
↓
SOLUTION
↓
CODE
↓
TEST
↓
RELEASE
```

and require controlled traceability for project artifacts.

---

# 43. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```

---

# End of Document
