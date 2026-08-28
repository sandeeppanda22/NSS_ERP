# NSS ERP — Backup & Technical Entity Relationship Design

**Document ID:** SOL-BACKUP-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Backup & Technical
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the
currently frozen Backup & Technical foundation.

The current foundation contains exactly two tables:

    backup_master
    restore_history

---

# 2. Current Frozen Tables

```text
backup_master
restore_history
```

Total:

```
2 tables
```

The current PostgreSQL schema review explicitly identifies these two tables
under Backup & Technical.

---

# 3. ERD Principle

Backup & Technical is an infrastructure-oriented domain.

Its primary responsibility is to maintain:

```
Backup Records
Restore History
```

It does not own the NSS ERP business entities being backed up.

---

# 4. High-Level Architecture

```text
                     NSS ERP
                        │
                        ▼
                PostgreSQL Database
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
          BACKUP                 RESTORE
             │                     │
             ▼                     ▼
     ┌─────────────────┐   ┌──────────────────┐
     │  backup_master  │   │ restore_history  │
     └─────────────────┘   └──────────────────┘
```

---

# 5. `backup_master`

## Purpose

`backup_master` represents the backup records maintained by the Backup &
Technical Module.

It is one of the two frozen foundation tables.

---

# 6. `backup_master` Identity

The project-wide database naming standard applies.

Primary key:

```
backup_master_pk
```

The exact column structure is defined in the subsequent Table Design
document.

---

# 7. `restore_history`

## Purpose

`restore_history` represents the historical record of restore operations.

It is the second frozen Backup & Technical table.

---

# 8. `restore_history` Identity

The project-wide database naming standard applies.

Primary key:

```
restore_history_pk
```

The exact column structure is defined in the subsequent Table Design
document.

---

# 9. Logical Backup Flow

```text
NSS ERP PostgreSQL Database
            │
            ▼
       Backup Operation
            │
            ▼
      backup_master
```

The backup record provides the ERP with historical information about the
backup operation.

---

# 10. Logical Restore Flow

```text
Existing Backup
      │
      ▼
Restore Operation
      │
      ▼
restore_history
```

The restore history provides a historical record of restoration activity.

---

# 11. Backup vs Restore

The ERD intentionally separates:

```text
Backup
    ↓
backup_master

Restore
    ↓
restore_history
```

A backup operation and a restore operation are different technical events.

---

# 12. Possible Backup-to-Restore Relationship

Conceptually, a restore operation will normally be associated with a backup
from which the restoration was performed.

The logical concept is:

```text
backup_master
      │
      │ used by
      ▼
restore_history
```

However, the current source does **not** explicitly define a physical FK
between these two tables.

Therefore this relationship is:

```
LOGICAL / EXPECTED CONCEPT
```

and is **NOT FROZEN as a physical FK** by this ERD.

---

# 13. No Assumed Foreign Key

This document does not declare:

```text
restore_history.backup_master_pk
        ↓
backup_master.backup_master_pk
```

as a frozen physical relationship.

The exact relationship must be confirmed during detailed table design.

---

# 14. Backup History

Conceptually:

```text
Backup Operation
      │
      ▼
backup_master
      │
      ▼
Historical Backup Record
```

The system should retain sufficient information to understand what backup
was performed and when.

---

# 15. Restore History

Conceptually:

```text
Restore Operation
      │
      ▼
restore_history
      │
      ▼
Historical Restore Record
```

Restore history must remain traceable after the restore operation completes.

---

# 16. Backup Record Does Not Contain ERP Data

`backup_master` is a record about a backup operation.

It is not a copy of:

```
Person
Membership
Finance
Governance
UPBS
Attendance
Other ERP data
```

The actual backup data remains part of the technical backup infrastructure.

---

# 17. Restore History Does Not Replace Business History

`restore_history` records restoration activity.

It does not represent:

```
Membership History
Attendance History
Finance History
Governance History
UPBS History
```

Those remain owned by their respective domains.

---

# 18. Technical Event Boundary

The logical architecture is:

```text
Technical Operation
       │
       ├─────────────┐
       │             │
       ▼             ▼
    Backup         Restore
       │             │
       ▼             ▼
backup_master   restore_history
```

---

# 19. Audit Relationship

Backup and restore operations may also produce centralized Audit events.

Conceptually:

```text
Backup Operation
      │
      ├──► backup_master
      │
      └──► Audit Framework

Restore Operation
      │
      ├──► restore_history
      │
      └──► Audit Framework
```

Audit remains a separate cross-cutting domain.

---

# 20. No Duplicate Audit Table

The ERD does not introduce:

```
backup_audit
```

or:

```
restore_audit
```

The centralized Audit Module remains responsible for system-wide audit
history.

---

# 21. Authentication Relationship

Backup and restore operations may be performed by an authorized technical
user.

Conceptually:

```text
Authenticated User
        │
        ▼
Authorized Technical Action
        │
        ▼
Backup / Restore
```

The existing Authentication/Identity architecture remains authoritative.

---

# 22. No Technical User Table

The ERD does not introduce:

```
backup_user
technical_user
```

The Backup & Technical Module reuses the common identity and RBAC
architecture.

---

# 23. RBAC Relationship

```text
Authentication
       │
       ▼
RBAC
       │
       ▼
Authorized Technical User
       │
       ├── Backup
       └── Restore
```

RBAC remains outside the Backup & Technical module.

---

# 24. Security Boundary

Backup data can contain the complete ERP database.

Therefore:

```text
Backup Storage
      │
      ▼
Restricted Technical Access
```

The security implementation is governed by the common Security framework.

---

# 25. Storage Boundary

The current ERD does not create:

```
backup_storage
```

or:

```
storage_location
```

The actual storage infrastructure is a technical implementation concern.

---

# 26. Backup Schedule Boundary

The current ERD does not create:

```
backup_schedule
```

The project source does not establish a frozen backup scheduling entity.

Scheduling shall be handled through the technical architecture if required.

---

# 27. Retention Boundary

The current ERD does not create:

```
backup_retention_policy
```

Retention policy is a technical governance concern and is not part of the
current frozen two-table foundation.

---

# 28. Disaster Recovery Boundary

The current ERD does not create:

```
disaster_recovery_plan
```

or:

```
failover_configuration
```

A complete Disaster Recovery/Business Continuity architecture requires
separate technical design.

---

# 29. Application File Backup Boundary

The current ERD is focused on backup and restore management records.

It does not create a separate:

```
application_file_backup
```

entity.

Application/document storage and its backup strategy require separate
technical design.

---

# 30. Logical Relationship Diagram

```text
                     ┌─────────────────────────┐
                     │     NSS ERP DATABASE    │
                     └────────────┬────────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
              Backup Operation          Restore Operation
                     │                         │
                     ▼                         ▼
          ┌─────────────────┐       ┌──────────────────┐
          │  backup_master  │       │ restore_history  │
          └─────────────────┘       └──────────────────┘
```

---

# 31. Optional Logical Association

Where the technical implementation records the source backup for a restore:

```text
┌─────────────────┐
│ backup_master   │
└────────┬────────┘
         │
         │ logical "restored from"
         ▼
┌──────────────────┐
│ restore_history  │
└──────────────────┘
```

This is a logical association only until the physical FK is formally
approved.

---

# 32. Historical Preservation

Backup and restore records are historical technical records.

The project principle:

```
History Never Deleted
```

applies to these records.

---

# 33. Restore History Preservation

A completed restore operation shall remain historically traceable.

The fact that a restore has completed does not justify deleting its history.

---

# 34. Backup History Preservation

Historical backup records shall remain available according to the approved
technical retention policy.

The technical retention policy itself is not frozen by this ERD.

---

# 35. Failure Events

A failed backup or failed restore may need to remain historically visible.

The exact failure-state model is not frozen.

The ERD therefore does not introduce separate:

```
backup_failure
```

or:

```
restore_failure
```

tables.

---

# 36. Verification Boundary

Backup verification and restore testing may produce operational records.

No separate verification table is frozen by the current foundation.

---

# 37. Backup and Restore Testing

Conceptually:

```text
Backup
  │
  ▼
Verification / Restore Test
  │
  ▼
Technical Result
```

The exact persistence model requires future technical design if needed.

---

# 38. Database Boundary

The logical source is:

```text
NSS ERP
   │
   ▼
PostgreSQL
   │
   ├── Backup
   │
   └── Restore
```

The Backup & Technical module manages the records surrounding these
operations.

---

# 39. No Business-Module Foreign Keys

The Backup & Technical tables should not contain foreign keys to every
business module merely because those modules are included in a database
backup.

For example, the ERD does not introduce:

```
person_pk
membership_pk
finance_pk
upbs_event_pk
```

simply to represent backup scope.

---

# 40. Scope Representation

The exact representation of:

```
Full Database Backup
Partial Backup
Module Backup
Configuration Backup
```

is not frozen by the available source.

Therefore no such relationship is introduced.

---

# 41. Cross-Module Architecture

```text
                 ┌──────────────┐
                 │ Membership   │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │ Governance   │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │ Finance      │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │ UPBS         │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ PostgreSQL   │
                 └──────┬───────┘
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
      backup_master        restore_history
```

---

# 42. No Duplicate Business Data

The Backup & Technical module does not duplicate business-domain tables.

The database backup itself contains the system data at the technical
infrastructure level; the ERP schema does not reproduce that data inside
Backup tables.

---

# 43. Current Frozen ERD

```text
┌──────────────────────┐
│ BACKUP & TECHNICAL   │
│                      │
│ ┌──────────────────┐ │
│ │ backup_master    │ │
│ └──────────────────┘ │
│                      │
│ ┌──────────────────┐ │
│ │ restore_history  │ │
│ └──────────────────┘ │
│                      │
└──────────────────────┘
```

No physical relationship between the two tables is frozen by this document.

---

# 44. Relationship Matrix

| Source              | Target            | Relationship Status        |
| ------------------- | ----------------- | -------------------------- |
| PostgreSQL Database | `backup_master`   | Logical                    |
| Backup Operation    | `backup_master`   | Logical                    |
| Restore Operation   | `restore_history` | Logical                    |
| `backup_master`     | `restore_history` | Logical/possible           |
| Backup Operation    | Audit             | Cross-cutting logical      |
| Restore Operation   | Audit             | Cross-cutting logical      |
| Technical User      | Backup/Restore    | Authorization relationship |

---

# 45. Frozen vs Pending

## Frozen

```text
backup_master
restore_history
```

## Logical

```text
Backup Operation → backup_master
Restore Operation → restore_history
Backup → Restore source relationship
Operation → Audit
User → Authorized Operation
```

## Pending

```text
Physical backup-to-restore FK
Backup schedule
Storage model
Retention model
Verification model
Disaster recovery model
Failover model
```

---

# 46. Future Expansion

If future requirements introduce:

```
Backup Scheduling
Storage Management
Restore Requests
Restore Approvals
Disaster Recovery
Backup Verification
Multi-location Backup
Archive Management
```

each capability shall receive a separate approved design.

It shall not be silently added to the current two-table freeze.

---

# 47. Database Design Boundary

The ERD establishes the logical structure.

The subsequent Table Design document must establish:

```
Exact columns
Data types
PKs
FKs
Unique constraints
Indexes
NULL/NOT NULL rules
Delete behavior
```

---

# 48. Source Alignment

The authoritative PostgreSQL schema review identifies Backup & Technical
as:

```text
backup_master
restore_history
```

with a total of two tables.

No additional Backup & Technical table is identified in the current frozen
schema baseline.

---

# 49. Status

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
