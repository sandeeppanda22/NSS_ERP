# NSS ERP — Backup & Technical Table Design

**Document ID:** SOL-BACKUP-004
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Backup & Technical
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the database table-design baseline for the current
Backup & Technical Module.

The current frozen foundation contains exactly:

    backup_master
    restore_history

No additional Backup & Technical tables are introduced by this document.

---

# 2. Current Frozen Tables

| # | Table | Purpose |
|---:|---|---|
| 1 | `backup_master` | Backup operation records |
| 2 | `restore_history` | Restore operation history |

Total:

    2 tables

The authoritative PostgreSQL schema review identifies these two tables under
Backup & Technical.

---

# 3. Schema Boundary

The current source confirms the table identities but does not provide a
complete authoritative column-level definition for either table.

Therefore this document distinguishes:

    Confirmed Table Identity
    Project Database Standards
    Logical Data Requirements
    Pending Physical Column Design

Inferred fields are not declared frozen merely because they are technically
reasonable.

---

# 4. Database Naming Standard

The Backup & Technical tables shall follow the common NSS database naming
standard.

Primary keys use:

    <table_name>_pk

Therefore:

    backup_master_pk
    restore_history_pk

---

# 5. Primary Key Standard

Each table shall have a unique technical primary key.

## `backup_master`

    backup_master_pk

## `restore_history`

    restore_history_pk

The exact UUID generation mechanism shall follow the project-wide
PostgreSQL standard.

---

# 6. UUID Architecture

The project database architecture uses UUID-based technical identifiers.

Therefore the primary keys shall use the approved UUID architecture.

Business identifiers, if later required, shall remain separate from the
technical PK.

---

# 7. `backup_master`

## 7.1 Purpose

`backup_master` represents backup-operation records maintained by the ERP.

It does not contain the physical backup data itself.

---

## 7.2 Technical Identity

```text
backup_master_pk
```

---

## 7.3 Logical Data Responsibility

The table should be capable of representing sufficient information about a
backup operation to establish:

```
Backup Identity
Backup Timing
Backup Outcome
Relevant Technical Context
```

The exact physical columns are not frozen by the current source.

---

# 8. Possible Backup Metadata

The following are logical concepts that may be required:

```
Backup Identifier
Backup Date/Time
Backup Status
Backup Type
Backup Location/Reference
Verification Result
Remarks
```

These are **design candidates**, not frozen columns.

They must not be implemented as mandatory schema fields until approved.

---

# 9. Backup Status

A backup operation may need a status.

Conceptually:

```
SUCCESS
FAILED
IN_PROGRESS
```

However, the current source does not freeze the exact status enumeration.

Therefore no final status master/enum is defined here.

---

# 10. Backup Type

A future implementation may distinguish different backup types.

Examples:

```
Full
Incremental
Differential
```

These are examples only.

The current source does not establish a frozen Backup Type catalogue.

Therefore no final enumeration is declared.

---

# 11. Backup Storage Reference

A backup record may need to identify where the physical backup is stored.

The current source does not establish a separate storage model.

Therefore this document does not freeze:

```
backup_storage
```

or a mandatory storage FK.

---

# 12. Physical Backup Asset

`backup_master` is metadata about the backup.

It is not itself the physical backup file.

Conceptually:

```text
backup_master
      │
      │ describes
      ▼
Physical Backup Asset
```

The physical storage architecture is outside the current frozen database
foundation.

---

# 13. `restore_history`

## 13.1 Purpose

`restore_history` records restoration operations performed against the NSS
ERP environment.

---

## 13.2 Technical Identity

```text
restore_history_pk
```

---

## 13.3 Logical Data Responsibility

The table should be capable of representing sufficient information about a
restore operation to establish:

```
Restore Identity
Restore Timing
Restore Outcome
Source Backup
Relevant Technical Context
```

The exact physical columns are not frozen by the current source.

---

# 14. Possible Restore Metadata

The following are logical concepts that may be required:

```
Restore Identifier
Restore Date/Time
Restore Status
Source Backup
Restore Environment
Initiated By
Verification Result
Remarks
```

These are design candidates, not frozen columns.

---

# 15. Restore Status

A restore operation may need a status.

Conceptually:

```
SUCCESS
FAILED
IN_PROGRESS
```

The exact controlled status values are not frozen by the current source.

---

# 16. Restore Source Backup

A restore normally originates from a particular backup.

Conceptually:

```text
backup_master
      │
      │ source backup
      ▼
restore_history
```

However, the source does not explicitly freeze the physical FK.

Therefore the exact relationship remains pending.

---

# 17. Possible Foreign Key

A future physical implementation may use:

```text
restore_history.backup_master_pk
        │
        ▼
backup_master.backup_master_pk
```

But this is **NOT FROZEN** by this document.

It must be confirmed during final schema design.

---

# 18. No Unsupported FK

The table design shall not introduce a foreign key merely because a
relationship appears logically useful.

Every FK must be supported by an approved relationship and business rule.

---

# 19. Actor / Technical User

A backup or restore operation may need to identify the responsible
technical/administrative user.

The existing Authentication/Identity architecture remains authoritative.

The Backup Module shall not create:

```
backup_user
technical_user
```

---

# 20. Possible Actor FK

Conceptually:

```text
Authenticated User
        │
        ▼
Backup / Restore Operation
```

The exact FK column and target identity table are not frozen by the current
source.

---

# 21. Timestamp

Backup and restore operations require temporal traceability.

The final physical design should retain the relevant date/time.

The exact column name and timezone convention shall follow the project-wide
database standard.

---

# 22. Audit Metadata vs Central Audit

Standard record metadata such as:

```
created_at
created_by
updated_at
updated_by
```

does not replace centralized Audit history.

Where common audit fields apply, they shall follow the project-wide audit
standard.

---

# 23. Centralized Audit

Backup and restore operations may also generate centralized Audit events.

Conceptually:

```text
Backup Operation
      │
      ├── backup_master
      │
      └── Audit

Restore Operation
      │
      ├── restore_history
      │
      └── Audit
```

No:

```
backup_audit
```

or:

```
restore_audit
```

table is introduced.

---

# 24. Historical Preservation

The table design follows the project principle:

```
History Never Deleted
```

Historical backup and restore records shall remain traceable.

---

# 25. Delete Policy

The final PostgreSQL implementation shall prevent ordinary business
operations from physically deleting historical backup/restore records.

The exact database permission and deletion mechanism shall be finalized
during implementation.

---

# 26. Restore Does Not Delete Restore History

A subsequent restore operation shall not erase historical records of earlier
restore operations.

---

# 27. Backup Does Not Replace Historical Records

A new backup does not replace the historical record of previous backups.

Each relevant backup operation remains independently traceable.

---

# 28. Failure Records

A failed backup or restore operation may need to remain recorded.

No separate:

```
backup_failure
```

or:

```
restore_failure
```

table is frozen.

Failure state should be represented through the final approved operation
model.

---

# 29. Verification

Backup verification and restore testing may require operational information.

The current two-table foundation does not establish a dedicated:

```
backup_verification
```

table.

Any such requirement requires separate approval.

---

# 30. Backup Schedule

The current database foundation does not establish:

```
backup_schedule
```

No scheduling table is introduced.

Scheduling is a technical infrastructure concern unless a persistent ERP
business requirement later requires database representation.

---

# 31. Retention Policy

The current foundation does not establish:

```
backup_retention_policy
```

Retention policy is not represented as a frozen database entity.

---

# 32. Storage Model

The current foundation does not establish:

```
backup_storage
```

The storage architecture may be external to the ERP database.

---

# 33. Disaster Recovery

The current foundation does not establish:

```
disaster_recovery_plan
```

or:

```
failover_configuration
```

These require separate technical architecture if required.

---

# 34. Indexing Principles

The final schema should consider indexes for:

```
Backup date/time
Backup status
Restore date/time
Restore status
Source backup reference
Technical actor
Other operational search fields
```

Exact indexes cannot be frozen until the final column set is approved.

---

# 35. Unique Constraints

The final schema shall introduce unique constraints only where required by
approved business/technical rules.

No additional unique constraint is frozen by this document.

---

# 36. NOT NULL Rules

NOT NULL requirements shall be derived from approved requirements.

The current source does not provide sufficient column-level detail to
freeze them.

---

# 37. CHECK Constraints

CHECK constraints should enforce approved technical/business invariants
where appropriate.

No specific Backup & Technical CHECK constraint is frozen here.

---

# 38. Foreign Key Rules

Any future foreign key shall:

1. Reference an authoritative target PK.
2. Use the project naming standard.
3. Preserve referential integrity.
4. Have explicitly approved delete behavior.

---

# 39. Delete Behavior

The final SQL shall define appropriate ON DELETE behavior.

Historical backup and restore information must not be accidentally destroyed
through cascading deletion.

---

# 40. Security

Backup metadata may reveal information about the technical infrastructure.

Access to the tables shall therefore follow the common security and RBAC
architecture.

---

# 41. Direct CRUD

Ordinary ERP users shall not receive unrestricted CRUD access to backup and
restore records.

Technical operations should be performed through controlled procedures.

---

# 42. Direct SQL Access

Direct database modification of Backup & Technical records shall be
restricted to authorized technical administration.

Exceptional modifications must remain traceable.

---

# 43. Backup File Security

The physical backup file may contain the complete ERP database.

Physical backup assets therefore require stronger protection than ordinary
application data.

The physical storage security model is outside this table design.

---

# 44. Organizational Scope

If backup/restore operations are ever organizationally scoped, the existing
Organization/RBAC architecture shall be reused.

No duplicate technical organization model is introduced.

---

# 45. Business Data Duplication Prohibited

The Backup & Technical tables shall not duplicate:

```
Person
Membership
Organization
Governance
Attendance
Finance
UPBS
Other business-domain data
```

The backup infrastructure protects the database itself.

---

# 46. Current Frozen Table Set

```text
backup_master
restore_history
```

Total:

```
2 tables
```

---

# 47. Tables Explicitly Not Added

```text
backup_storage
backup_schedule
backup_retention_policy
backup_failure
backup_verification
restore_request
restore_approval
disaster_recovery_plan
failover_configuration
backup_audit
restore_audit
backup_user
technical_user
```

These require separate approved requirements if ever needed.

---

# 48. Final Physical Schema Requirements

Before PostgreSQL DDL is generated, the following must be explicitly
finalized:

```
Exact columns
Exact data types
Exact NULL/NOT NULL rules
Exact PK definitions
Exact FK definitions
Exact unique constraints
Exact CHECK constraints
Exact indexes
Exact audit metadata
Exact delete behavior
Exact status representation
Exact source-backup relationship
```

---

# 49. Database-First Principle

The module follows the project design sequence:

```text
Technical Requirements
        ↓
Business/Technical Rules
        ↓
ERD
        ↓
Table Design
        ↓
PostgreSQL DDL
        ↓
Technical Implementation
        ↓
Testing
        ↓
Release
```

The physical database shall not be generated from assumptions that have not
been approved.

---

# 50. Source Alignment

The authoritative schema review identifies the current Backup & Technical
foundation as:

```
backup_master
restore_history
```

for a total of two tables.

The current source does not provide an authoritative column-by-column
definition for these tables. Accordingly, this document records the table
identities and design boundaries without falsely freezing inferred columns.

---

# 51. Status

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
