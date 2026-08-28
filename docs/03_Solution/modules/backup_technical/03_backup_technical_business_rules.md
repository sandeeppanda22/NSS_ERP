# NSS ERP — Backup & Technical Business Rules

**Document ID:** SOL-BACKUP-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Backup & Technical
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business and technical-governance rules for the
Backup & Technical Module.

The current frozen database foundation consists of:

    backup_master
    restore_history

No additional technical tables are frozen by this document.

---

# 2. Rule Classification

Rules are classified as:

- FROZEN — directly established by the current project baseline
- SOURCE-ALIGNED — supported by project-wide standards
- PENDING — requires detailed technical decision
- FUTURE — outside the current frozen scope

---

# 3. Core Backup Rules

## BACKUP-BR-001 — Centralized Backup Management

**Status:** FROZEN

The NSS ERP shall maintain a centralized Backup & Technical capability.

The current database foundation is:

    backup_master
    restore_history

---

## BACKUP-BR-002 — Backup Records

**Status:** SOURCE-ALIGNED

Backup operations shall have a persistent historical record.

The authoritative ERP table for backup records is:

    backup_master

---

## BACKUP-BR-003 — Restore Records

**Status:** SOURCE-ALIGNED

Restore operations shall have a persistent historical record.

The authoritative ERP table for restore history is:

    restore_history

---

# 4. Historical Preservation

## BACKUP-BR-004 — Backup History Preservation

**Status:** SOURCE-ALIGNED

Historical backup records shall remain traceable according to the approved
technical retention policy.

A completed backup record shall not be casually removed from the ERP
history.

---

## BACKUP-BR-005 — Restore History Preservation

**Status:** SOURCE-ALIGNED

Restore history shall be preserved as an operational technical record.

A completed restore operation shall remain traceable.

---

## BACKUP-BR-006 — History Never Deleted

**Status:** SOURCE-ALIGNED

The project-wide principle:

    History Never Deleted

applies to authoritative backup and restore history.

Physical deletion of historical records shall not be part of normal
operational workflows.

---

# 5. Backup Integrity

## BACKUP-BR-007 — Backup Must Represent a Recovery Asset

**Status:** SOURCE-ALIGNED

A recorded backup is intended to represent a recoverable system copy.

The technical implementation should provide appropriate mechanisms to
determine whether the backup is usable.

---

## BACKUP-BR-008 — Backup Verification

**Status:** PENDING

The exact backup-verification mechanism is not frozen.

Possible mechanisms include:

    Integrity validation
    Backup verification
    Restore testing

The final mechanism requires technical architecture approval.

---

# 6. Backup Status

## BACKUP-BR-009 — Backup Outcome

**Status:** SOURCE-ALIGNED

The system should distinguish between successful and unsuccessful backup
operations.

The exact controlled status values are not frozen.

---

## BACKUP-BR-010 — Failed Backup Traceability

**Status:** SOURCE-ALIGNED

Where a backup operation is initiated but fails, the failure should remain
traceable according to the final technical implementation.

No separate:

    backup_failure

table is currently frozen.

---

# 7. Restore Rules

## BACKUP-BR-011 — Restore Is a Controlled Operation

**Status:** SOURCE-ALIGNED

Database restoration is a high-impact technical operation.

It shall be performed only through authorized technical/administrative
procedures.

---

## BACKUP-BR-012 — Restore History Required

**Status:** SOURCE-ALIGNED

A controlled restore operation shall leave a corresponding record in:

    restore_history

---

## BACKUP-BR-013 — Failed Restore Traceability

**Status:** SOURCE-ALIGNED

A failed restore attempt should remain traceable where the operation was
initiated.

The exact failure-state model is not frozen.

---

## BACKUP-BR-014 — No Silent Restore

**Status:** SOURCE-ALIGNED

A restore operation shall not occur as an untraceable operational action.

The relevant restore activity must remain historically identifiable.

---

# 8. Backup-to-Restore Relationship

## BACKUP-BR-015 — Restore Source

**Status:** PENDING

A restore will normally originate from a particular backup.

The logical relationship is:

    backup_master
          ↓
    restore_history

However, the available source does not freeze the physical FK structure.

Therefore no mandatory FK is declared by this business-rule document.

---

# 9. Security

## BACKUP-BR-016 — Restricted Backup Access

**Status:** SOURCE-ALIGNED

Access to backup and restore operations shall be restricted to appropriately
authorized technical/administrative users.

---

## BACKUP-BR-017 — Existing Authentication

**Status:** FROZEN

The Backup & Technical Module shall reuse the existing NSS ERP
Authentication/Identity framework.

It shall not create a separate technical-user identity system.

---

## BACKUP-BR-018 — Existing RBAC

**Status:** FROZEN

Authorization for backup and restore operations shall use the common RBAC
framework.

No independent Backup RBAC system shall be created.

---

## BACKUP-BR-019 — Backup Data Sensitivity

**Status:** SOURCE-ALIGNED

A database backup may contain the complete NSS ERP dataset.

Backup access shall therefore be treated as privileged technical access.

---

# 10. Audit

## BACKUP-BR-020 — Backup Auditability

**Status:** SOURCE-ALIGNED

Significant backup operations may require centralized Audit records.

The Audit Module remains the common audit authority.

---

## BACKUP-BR-021 — Restore Auditability

**Status:** SOURCE-ALIGNED

Restore operations should be auditable because they are high-impact
technical operations.

---

## BACKUP-BR-022 — No Duplicate Audit Framework

**Status:** FROZEN

The Backup & Technical Module shall not create:

    backup_audit
    restore_audit

The common Audit Module shall be used.

---

# 11. Backup Schedule

## BACKUP-BR-023 — Backup Frequency

**Status:** PENDING

The current source does not establish a final backup frequency.

Therefore the system does not currently freeze:

    Hourly
    Daily
    Weekly
    Monthly

as a mandatory backup schedule.

The schedule shall be determined through technical operations planning.

---

# 12. Backup Retention

## BACKUP-BR-024 — Retention Policy

**Status:** PENDING

The current source does not establish a specific backup retention period.

No fixed number of:

    Days
    Weeks
    Months
    Years

is frozen by this document.

---

# 13. Backup Storage

## BACKUP-BR-025 — Storage Architecture

**Status:** PENDING

The current source does not freeze a specific backup-storage technology.

The final implementation may use an approved technical storage architecture.

No specific provider is declared mandatory by this document.

---

## BACKUP-BR-026 — No Storage Table Yet

**Status:** FROZEN

The current database foundation does not include:

    backup_storage

or equivalent storage-management tables.

Such a table requires a separate approved requirement.

---

# 14. Database Scope

## BACKUP-BR-027 — PostgreSQL Database Protection

**Status:** SOURCE-ALIGNED

The Backup & Technical architecture shall protect the NSS ERP PostgreSQL
database.

The exact PostgreSQL backup tooling is an implementation decision.

---

## BACKUP-BR-028 — No Business-Module Duplication

**Status:** FROZEN

Backup tables shall not duplicate business-domain data.

The following shall remain owned by their respective modules:

    Person
    Membership
    Organization
    Governance
    Attendance
    Finance
    UPBS
    Other business domains

---

# 15. Application Files

## BACKUP-BR-029 — Application/File Backup Boundary

**Status:** PENDING

The current Backup foundation does not define a complete application-file
backup model.

Document and file backup requirements shall be resolved through the
appropriate technical/document-management architecture.

---

# 16. Disaster Recovery

## BACKUP-BR-030 — Disaster Recovery Is Broader Than Backup

**Status:** SOURCE-ALIGNED

Backup is one component of disaster recovery.

The current two-table foundation does not itself define a complete Disaster
Recovery architecture.

---

## BACKUP-BR-031 — Disaster Recovery Plan

**Status:** PENDING

No complete:

    Disaster Recovery Plan

is frozen by the current Backup & Technical foundation.

---

## BACKUP-BR-032 — Failover

**Status:** PENDING

The current source does not freeze:

    Failover Architecture
    High Availability Architecture
    Automatic Failover

These require separate technical architecture decisions.

---

# 17. Restore Authorization

## BACKUP-BR-033 — Authorized Restore

**Status:** SOURCE-ALIGNED

Restore operations shall be restricted to authorized technical personnel.

---

## BACKUP-BR-034 — Restore Approval

**Status:** PENDING

Whether every restore requires a formal approval workflow is not frozen.

The final operational policy must determine when approval is required.

---

# 18. Restore Testing

## BACKUP-BR-035 — Restore Testing

**Status:** PENDING

Periodic restore testing may be required to establish recoverability.

The current source does not freeze:

    Testing Frequency
    Test Environment
    Test Scope
    Acceptance Criteria

---

# 19. Backup Verification

## BACKUP-BR-036 — Recoverability

**Status:** SOURCE-ALIGNED

The existence of a backup record alone should not be interpreted as proof
that the backup is recoverable.

The final technical solution should provide appropriate verification.

---

# 20. Technical Failure Handling

## BACKUP-BR-037 — Failure Must Be Visible

**Status:** SOURCE-ALIGNED

Backup and restore failures should be distinguishable from successful
operations.

The exact technical state model is pending.

---

# 21. Audit History

## BACKUP-BR-038 — Technical Operations Are Traceable

**Status:** SOURCE-ALIGNED

Significant technical operations shall remain traceable through the
appropriate combination of:

    backup_master
    restore_history
    Audit Framework

---

# 22. No Silent Data Destruction

## BACKUP-BR-039 — Restore Must Not Be Treated as Ordinary CRUD

**Status:** SOURCE-ALIGNED

Restore operations can alter the state of the entire ERP database.

They shall not be treated as ordinary user CRUD operations.

---

# 23. Historical Integrity

## BACKUP-BR-040 — Restore Does Not Erase Restore History

**Status:** SOURCE-ALIGNED

A subsequent restore shall not silently erase the historical record that a
previous restore occurred.

---

# 24. Backup Records vs Physical Backup Files

## BACKUP-BR-041 — Metadata vs Backup Asset

**Status:** SOURCE-ALIGNED

`backup_master` represents ERP-level backup metadata/history.

It is not itself the physical database backup file.

---

# 25. Restore History vs Restored Database

## BACKUP-BR-042 — History vs Recovered State

**Status:** SOURCE-ALIGNED

`restore_history` records the restoration operation.

It does not represent the recovered database itself.

---

# 26. Backup Lifecycle

## BACKUP-BR-043 — Backup Lifecycle

**Status:** SOURCE-ALIGNED

A backup operation conceptually follows:

    Initiated
        ↓
    Executed
        ↓
    Result Determined
        ↓
    Backup Record Preserved

Exact lifecycle statuses remain pending.

---

# 27. Restore Lifecycle

## BACKUP-BR-044 — Restore Lifecycle

**Status:** SOURCE-ALIGNED

A restore operation conceptually follows:

    Restore Authorized
        ↓
    Restore Executed
        ↓
    Result Determined
        ↓
    Restore History Preserved

Exact lifecycle statuses remain pending.

---

# 28. Technical User Identity

## BACKUP-BR-045 — Existing Identity Model

**Status:** FROZEN

Technical users shall use the existing NSS ERP identity/authentication
architecture.

No:

    backup_user

table shall be introduced.

---

# 29. Organizational Scope

## BACKUP-BR-046 — Common Organizational Scope

**Status:** SOURCE-ALIGNED

Where technical administration is organizationally scoped, the existing
Organization and administrative-scope architecture shall be reused.

No duplicate technical organization hierarchy shall be created.

---

# 30. Backup and Notification

## BACKUP-BR-047 — Operational Notifications

**Status:** PENDING

The current source does not freeze specific notifications for:

    Backup Success
    Backup Failure
    Restore Success
    Restore Failure

If required, the common Notification framework shall be used.

---

## BACKUP-BR-048 — No Duplicate Notification System

**Status:** FROZEN

The Backup & Technical Module shall not create a separate notification
engine.

---

# 31. Backup and Reports

## BACKUP-BR-049 — Reporting Boundary

**Status:** PENDING

The current source does not freeze a dedicated Backup reporting catalogue.

Any reporting requirements shall use the common Reports & Analytics
architecture.

---

# 32. Physical Deletion

## BACKUP-BR-050 — Historical Record Protection

**Status:** SOURCE-ALIGNED

Historical backup and restore records shall not be physically deleted as
part of ordinary business operations.

---

# 33. Administrative Override

## BACKUP-BR-051 — Exceptional Administrative Actions

**Status:** PENDING

The exact procedure for exceptional administrative deletion/correction of
technical records is not frozen.

Any such mechanism must preserve auditability.

---

# 34. Backup Table Count

## BACKUP-BR-052 — Frozen Table Foundation

**Status:** FROZEN

The current Backup & Technical database foundation contains exactly:

    backup_master
    restore_history

Total:

    2 tables

---

# 35. Tables Not Frozen

## BACKUP-BR-053 — No Additional Technical Tables

**Status:** FROZEN

The following are not part of the current frozen foundation:

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
    backup_user

They shall not be implemented without approved requirements.

---

# 36. Business Rule Summary

| Rule Area | Status |
|---|---|
| Centralized Backup Management | FROZEN |
| `backup_master` | FROZEN |
| `restore_history` | FROZEN |
| Backup History Preservation | SOURCE-ALIGNED |
| Restore History Preservation | SOURCE-ALIGNED |
| History Never Deleted | SOURCE-ALIGNED |
| Backup Integrity | SOURCE-ALIGNED |
| Backup Verification Method | PENDING |
| Restore Authorization | SOURCE-ALIGNED |
| Restore Approval | PENDING |
| Backup Frequency | PENDING |
| Backup Retention | PENDING |
| Storage Provider | PENDING |
| Disaster Recovery | PENDING |
| Failover | PENDING |
| Restore Testing | PENDING |
| Audit Integration | SOURCE-ALIGNED |
| Duplicate Audit Framework | PROHIBITED |
| Duplicate User System | PROHIBITED |
| Duplicate Notification System | PROHIBITED |
| Additional Backup Tables | NOT FROZEN |

---

# 37. Core Principle

The central Backup & Technical principle is:

    NSS ERP data must have a controlled, traceable,
    and recoverable backup/restore capability.

---

# 38. Design Boundary

These rules establish the current Backup & Technical business/technical
governance baseline.

They do NOT yet freeze:

    RPO
    RTO
    Backup Frequency
    Backup Retention
    Storage Provider
    Storage Topology
    Encryption Architecture
    Disaster Recovery Architecture
    High Availability Architecture
    Failover Architecture

Those require separate technical decisions.

---

# 39. Status

DOCUMENT STATUS:

    DRAFT — SOURCE ALIGNED

VERSION:

    1.0.0

---

# End of Document
