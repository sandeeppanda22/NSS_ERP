# NSS ERP — Audit Table Design

**Document ID:** SOL-AUDIT-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Audit
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the database table-design baseline for the current
Audit Module.

The current frozen Audit foundation contains exactly:

    audit_master
    system_event_log

No additional Audit tables are introduced by this document.

---

# 2. Current Frozen Tables

| # | Table | Purpose |
|---:|---|---|
| 1 | `audit_master` | Audit-domain master/configuration foundation |
| 2 | `system_event_log` | Centralized system-event history |

Total:

    2 tables

The project schema review explicitly identifies these two tables under Audit.

---

# 3. Important Schema Boundary

The available authoritative project source establishes the table identities,
but does not provide a complete authoritative column-by-column schema for
either table.

Therefore this document separates:

    Confirmed Table Identity
    Confirmed Architectural Responsibility
    Project-Wide Database Standards
    Pending Physical Column Design

No inferred column is declared FROZEN merely because it is technically
reasonable.

---

# 4. Database Naming Standard

The Audit tables shall follow the common NSS database naming conventions.

Primary keys use:

    <table_name>_pk

Therefore the technical PK names are:

    audit_master_pk
    system_event_log_pk

---

# 5. UUID Primary Keys

The project database architecture uses UUID-based primary keys.

Therefore:

    audit_master_pk
    system_event_log_pk

shall use the approved UUID PK convention.

The exact PostgreSQL UUID generation mechanism shall follow the project-wide
database standard.

---

# 6. Foreign Key Standard

Where foreign keys are introduced, they shall reference the target table's
primary key.

The project standard does not permit business identifiers to be used as
relational substitutes for PKs.

---

# 7. `audit_master`

## 7.1 Purpose

`audit_master` is one of the two frozen Audit foundation tables.

Its detailed business role is part of the Audit domain.

---

## 7.2 Primary Key

Confirmed technical identity:

    audit_master_pk

---

## 7.3 Column Status

The available project source does not provide an authoritative complete
column list for `audit_master`.

Therefore the following are NOT declared as frozen columns by this document:

    audit_code
    audit_name
    audit_type
    description
    is_active
    created_at
    updated_at

They may be required, but their final inclusion must be established through
the detailed schema design.

---

## 7.4 Master-Data Principle

If `audit_master` contains controlled audit definitions/categories, those
values shall follow the common NSS master-data principles.

The system shall avoid hard-coding controlled business categories in
application code.

---

## 7.5 Uniqueness

No specific unique constraint is declared for `audit_master` until the
business meaning of its identifiers is formally frozen.

---

# 8. `system_event_log`

## 8.1 Purpose

`system_event_log` is the centralized system-event history table of the
current Audit foundation.

It represents significant system events requiring historical traceability.

---

## 8.2 Primary Key

Confirmed technical identity:

    system_event_log_pk

---

## 8.3 Event Identity

Every system event must be uniquely identifiable.

The primary key provides the technical identity.

A separate human-readable event identifier is not declared as frozen unless
required by the detailed design.

---

# 9. System Event Information

Conceptually, an auditable system event may need to establish:

    Actor
    Action
    Timestamp
    Module
    Entity
    Record
    Context
    Result

These are **logical requirements**, not a frozen physical column list.

---

# 10. Actor Information

An event may need to identify the user or system process responsible for
the event.

Conceptually:

    actor
        ↓
    system_event_log

The exact FK and actor representation shall reuse the existing
Authentication/Identity architecture.

---

# 11. No Audit User Table

The Audit schema shall NOT introduce:

    audit_user

The authoritative user identity remains part of the existing ERP
Authentication/Identity architecture.

---

# 12. Actor Types

The final design may need to distinguish:

    Human User
    System Process

However, the exact physical representation is not frozen by the available
source.

---

# 13. Timestamp

A system event requires temporal information.

The final schema should retain sufficient timestamp information to establish
when the event occurred/was recorded.

The exact column name and timezone/storage convention shall follow the
project-wide database standard.

---

# 14. Target Identification

An audit event may need to identify the affected:

    Module
    Entity
    Record

However, the available source does not define a final polymorphic
relationship.

Therefore no unsupported FK structure is frozen here.

---

# 15. Action Identification

The audit event may need to identify the action performed.

Examples of possible action concepts include:

    CREATE
    UPDATE
    STATUS_CHANGE
    APPROVE
    REJECT
    CANCEL
    CORRECT

These examples are NOT a frozen action enumeration.

The final action catalogue requires separate approval.

---

# 16. Event Context

An event may require contextual information such as:

    Organization Scope
    Module
    Source
    Request/Workflow Reference

The exact fields shall be established only where the business requirement
requires them.

---

# 17. Event Result

Some system events may need to indicate whether the operation:

    Succeeded
    Failed
    Was Rejected

This is a possible design requirement, not a frozen column definition.

---

# 18. Business Record vs Audit Record

The Audit table shall not duplicate the complete business record.

For example, if Membership changes:

```text
Membership Table
    ↓
Actual Membership State

system_event_log
    ↓
Audit Event
```

The audit record should preserve the event context rather than becoming a
second Membership table.

---

# 19. Field-Level Change Data

The current frozen Audit foundation does not establish a separate:

```
audit_field_change
```

or:

```
audit_change_detail
```

table.

Therefore field-level history is NOT added to the current two-table freeze.

If field-level before/after values are later required, that design must be
separately approved.

---

# 20. Before / After Values

Where a business rule requires original and revised values to remain
traceable, the appropriate domain history/correction mechanism shall be
used.

The Audit Module shall not invent a universal before/after schema without
an approved requirement.

---

# 21. Correction Audit

The project already requires post-completion correction workflows in some
modules.

For example, the existing Sevak rules require preservation of:

```
Original Value
Requested Value
Reason
Requester
Request Timestamp
Approver
Approval Timestamp
Final Change
Audit Trail
```

Therefore Audit must support the traceability requirement.

However, the exact physical implementation of these fields belongs to the
relevant business/correction design.

---

# 22. Audit and Standard Record Metadata

Normal business tables may contain:

```
created_at
created_by_sangha_sevi_pk
updated_at
updated_by_sangha_sevi_pk
deleted_at
deleted_by_sangha_sevi_pk
is_active
```

These standard fields do not replace centralized audit history.

---

# 23. Audit and Soft Delete

Audit history shall remain preserved when a business record is soft-deleted.

Conceptually:

```
Business Record
    ↓
is_active = FALSE
```

while:

```
system_event_log
    ↓
Historical audit event remains
```

---

# 24. Historical Preservation

The Audit table design follows:

```
History Never Deleted
```

Audit records are historical records and must remain available for authorized
review.

---

# 25. Delete Policy

The final SQL design shall prevent normal business operations from
physically deleting historical audit events.

Exact PostgreSQL permissions and deletion protections will be defined in the
implementation/security stage.

---

# 26. Audit Immutability

Audit records should be treated as immutable historical evidence.

Normal application workflows shall not update an already recorded audit
event.

Any exceptional correction must itself be controlled and auditable.

---

# 27. Audit and Authentication

`system_event_log` may need to reference the existing authenticated user
identity.

The Audit schema shall reuse the existing authentication/person/member
architecture.

It shall not create duplicate identity tables.

---

# 28. Audit and Organizational Scope

Where organizational scope is relevant, audit visibility may depend on the
existing:

```
Organization
RBAC
Administrative Scope
```

architecture.

Audit shall not create a separate organizational hierarchy.

---

# 29. Audit and Module Ownership

The Audit Module records events originating from other modules.

It does not become the owner of their business entities.

Example:

```text
Membership
    │
    └── business ownership remains Membership

Audit
    │
    └── event traceability
```

---

# 30. Audit and Business History

Where a domain already maintains historical records, both may coexist.

Example:

```text
Membership
    │
    ├── Membership History
    │
    └── Audit Event
```

Neither should be removed merely because the other exists.

---

# 31. Indexing Principles

The final implementation should index fields needed for:

```
Event lookup
Date filtering
Actor filtering
Module filtering
Entity filtering
Business record lookup
```

Exact indexes cannot be frozen until the final event schema is approved.

---

# 32. Unique Constraints

Only technically/business-required unique constraints shall be introduced.

No additional unique constraints are frozen by this document.

---

# 33. NOT NULL Rules

NOT NULL requirements shall be derived from approved Audit business rules.

The current source does not provide enough column-level information to
freeze them here.

---

# 34. CHECK Constraints

CHECK constraints should enforce approved controlled business rules where
appropriate.

No specific Audit CHECK constraint is frozen by this document.

---

# 35. Foreign Keys

The following logical relationships may eventually require FKs:

```text
Audit Actor
    ↓
Existing User / Identity

Audit Context
    ↓
Existing Module / Organization references
```

However, the available source does not freeze exact FK columns.

Therefore no unsupported FK is added here.

---

# 36. `audit_master` → `system_event_log`

The available source confirms both tables but does not explicitly establish
a physical FK between them.

Therefore:

```text
audit_master
      │
      │ ?
      ▼
system_event_log
```

remains **NOT FROZEN**.

The relationship must not be assumed.

---

# 37. No Polymorphic FK Assumption

The table design shall not automatically introduce a polymorphic FK such
as:

```
target_table
target_id
```

without explicit architectural approval.

Such a structure has significant integrity implications and requires a
formal design decision.

---

# 38. No Login-History Table

The current Audit foundation does not include:

```
audit_login_history
```

Authentication/Security owns authentication events.

A future centralized login-audit requirement requires separate design.

---

# 39. No Access-History Table

The current Audit foundation does not include:

```
audit_access_log
```

Any access-audit requirement requires separate approval and design.

---

# 40. No Approval-History Table

The current Audit foundation does not include:

```
audit_approval_history
```

Approval history remains part of the Applications/Approvals architecture,
while significant approval actions may also be auditable.

---

# 41. No Notification Table

The Audit Module does not introduce:

```
audit_notification
```

Notifications use the common Notification framework.

---

# 42. No Document Table

The Audit Module does not create a duplicate document repository.

If audit evidence requires document references, the common Document
Management architecture shall be reused.

---

# 43. No User Table

The Audit Module does not create:

```
audit_user
```

Existing authentication and identity remain authoritative.

---

# 44. Standard Audit Metadata

Where the common audit standard applies to Audit-related configuration
records, the approved project-wide metadata convention shall be used.

The final applicability of:

```
created_at
created_by
updated_at
updated_by
deleted_at
deleted_by
is_active
```

shall be confirmed for each table.

---

# 45. Security

Audit tables may contain sensitive information.

Database/application access shall therefore be restricted through the
common security and RBAC architecture.

---

# 46. Read Access

Authorized users may eventually need:

```
View
Search
Filter
Report
Export
```

capabilities.

These are UI/report concerns and are not frozen as database permissions
here.

---

# 47. Write Access

Normal business users shall not directly insert/update audit records through
ordinary CRUD screens.

Audit records should be generated through controlled application/system
operations.

---

# 48. Direct SQL Modification

Direct manual modification of audit records shall be restricted to
authorized technical/administrative procedures.

Any approved exceptional modification must itself remain traceable.

---

# 49. Audit Event Retention

The database shall preserve authoritative audit history.

Exact archival/retention-period policy is not frozen by this document.

---

# 50. Backup

Audit data shall be included in the common PostgreSQL backup and recovery
strategy.

The Audit Module shall not create its own backup tables.

---

# 51. Current Table Set

```text
audit_master
system_event_log
```

Total:

```
2
```

---

# 52. Tables Explicitly Not Added

```text
audit_field_change
audit_change_detail
audit_login_history
audit_access_log
audit_approval_history
audit_user
audit_target
audit_action_master
audit_notification
```

These require separate approved requirements if ever needed.

---

# 53. Final Physical Schema Boundary

Before SQL generation, the following must be explicitly finalized:

```
Exact columns
Exact data types
Exact NULL/NOT NULL rules
Exact FK relationships
Exact unique constraints
Exact CHECK constraints
Exact indexes
Exact audit metadata
Exact deletion protections
Exact event/action representation
```

---

# 54. Database-First Principle

The Audit implementation shall follow:

```text
Business Rules
      ↓
Logical ERD
      ↓
Table Design
      ↓
PostgreSQL DDL
      ↓
ORM
      ↓
API
      ↓
UI
```

The physical database must not be generated from assumptions that are not
supported by approved requirements.

---

# 55. Source Alignment

The current schema review explicitly identifies the Audit foundation as:

```
audit_master
system_event_log
```

with a total of two tables.

The broader project source establishes that auditability is required for
significant status changes, enrollment and event actions, and that physical
deletion is prohibited for historical records.

The existing post-completion correction rules require preservation of the
original value, requested value, reason, requester, approver, final change,
and audit trail.

---

# 56. Status

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
