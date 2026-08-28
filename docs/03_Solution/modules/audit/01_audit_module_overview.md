# NSS ERP — Audit Module Overview

**Document ID:** SOL-AUDIT-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Audit
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The Audit Module provides the centralized audit and system-event history
foundation for the NSS ERP.

Its purpose is to ensure that significant system actions and auditable
changes remain traceable throughout the ERP lifecycle.

The Audit Module supports:

- Audit history
- System event logging
- Change traceability
- Administrative accountability
- Historical preservation
- Investigation and review
- Compliance support

---

# 2. Current Frozen Foundation

The current Audit foundation consists of exactly two tables:

    audit_master
    system_event_log

Total:

    2 tables

---

# 3. Audit Module Scope

The Audit Module provides a centralized mechanism for recording and
reviewing significant system activity.

Conceptually:

    User / System Action
            ↓
       Audit Event
            ↓
       Audit History

---

# 4. Audit vs Business Data

Audit records are different from normal business records.

For example:

    Membership
    Registration
    Attendance
    Finance
    Governance

contain the actual business state.

Audit records provide evidence of:

    Who changed it
    What happened
    When it happened
    What action occurred
    What was affected

---

# 5. Audit Principle

The ERP shall preserve accountability for significant system actions.

Where an operation requires auditability, the audit record shall remain
available for historical review.

---

# 6. History Preservation

The NSS ERP follows the principle:

    History Never Deleted

Audit history therefore forms part of the permanent historical record of the
system.

Historical audit information shall not be casually removed merely because
the underlying business record has changed.

---

# 7. `audit_master`

`audit_master` is part of the current frozen Audit foundation.

It represents the audit-definition/configuration side of the Audit domain.

The exact column-level design will be established in the Audit Table Design
document.

---

# 8. `system_event_log`

`system_event_log` is part of the current frozen Audit foundation.

It represents system-event history.

It provides the mechanism for recording significant system events that
require traceability.

---

# 9. High-Level Architecture

```text
                     NSS ERP
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
   Membership       Governance        Finance
        │               │                │
        └───────────────┼────────────────┘
                        │
                        ▼
                  Audit Framework
                        │
                ┌───────┴────────┐
                ▼                ▼
          audit_master    system_event_log
```

---

# 10. Cross-Module Nature

Audit is a **cross-cutting ERP capability**.

It is not limited to one business module.

Potential audited areas include:

```
Membership
Organization
Governance
Attendance
Sevak
UPBS
Finance
Applications
Administration
Security
```

The exact event coverage is defined through the relevant module rules and
common audit standards.

---

# 11. User Accountability

Where a significant action is performed by an authenticated user, the audit
record should identify the responsible user according to the project's
identity and audit architecture.

The Audit Module shall reuse the existing NSS identity/user framework.

It shall not create a separate user identity system.

---

# 12. System-Generated Events

Not all events are necessarily generated directly by a human user.

The Audit framework may also record significant system-generated events.

Examples may include:

```
Automated status change
Scheduled process
System reconciliation
Automatic closure
Security event
```

Exact system-event coverage requires detailed rules.

---

# 13. Audit Event Concept

An audit event conceptually contains:

```
Actor
Action
Target
Timestamp
Context
Result
```

The exact database representation shall be defined in the Audit Table
Design.

---

# 14. Change Traceability

For auditable changes, the system should be capable of determining:

```
Previous State
New State
Who Changed It
When It Changed
Why It Changed
```

where the relevant business rule requires this level of detail.

---

# 15. Audit Is Not a Business History Table

The Audit Module shall not replace domain-specific history tables.

For example:

```
membership_transfer_history
```

is a Membership-domain history entity.

It is not replaced by:

```
system_event_log
```

Both may exist:

```text
Business History
    ↓
membership_transfer_history

Audit History
    ↓
system_event_log
```

---

# 16. Business History vs Audit History

Business history answers:

```
What happened to this business entity?
```

Audit history answers:

```
What system action caused or recorded this change?
```

These are complementary concepts.

---

# 17. Example — Membership Transfer

A membership transfer may produce:

```text
Membership Domain
    ↓
membership_transfer_history

Audit Domain
    ↓
system_event_log
```

The transfer-history record represents the business event.

The audit record provides system accountability.

---

# 18. Example — UPBS Event Cancellation

If an authorized user cancels a UPBS event:

```text
UPBS
    ↓
Event Status = CANCELLED

Audit
    ↓
Cancellation action recorded
```

The UPBS event remains the business record.

The Audit record preserves accountability for the action.

---

# 19. Example — Post-Completion Correction

The project source requires post-completion corrections to preserve:

* Original value
* Requested value
* Reason
* Requester
* Timestamp
* Approver
* Approval timestamp
* Final change
* Audit trail

Therefore audit is an important part of centralized correction handling.

---

# 20. Audit and Approval

Where an action requires approval, the Audit Module records the relevant
auditable activity.

The approval workflow itself belongs to the appropriate approval/business
module.

Audit records the traceability of the action.

---

# 21. Audit and RBAC

The Audit Module shall work with the existing ERP RBAC model.

It shall not define a separate permission architecture.

Authorization determines:

```
Who may perform an action
```

Audit determines:

```
What authorized action occurred
```

---

# 22. Audit Access

Audit information should be accessible only to appropriately authorized
users.

Not every ordinary ERP user should automatically have unrestricted access
to the complete audit history.

The detailed permission matrix belongs to the common Administration/RBAC
design.

---

# 23. Audit Confidentiality

Audit records may contain sensitive operational information.

Access to audit history shall therefore follow:

```
Authentication
+
Authorization
+
Organizational Scope
```

where applicable.

---

# 24. Audit Immutability Principle

Audit records should be treated as historical evidence.

Normal users shall not be able to casually edit or remove audit records.

Any exceptional administrative correction of audit data must itself be
controlled and auditable.

---

# 25. No Silent Audit Modification

The system shall not silently modify historical audit information.

Any approved correction affecting audit records must preserve sufficient
traceability to explain the correction.

---

# 26. Audit Timestamp

Auditable events require a timestamp.

The timestamp shall represent when the system recorded the event.

The exact timezone/storage convention shall follow the project-wide database
and application standards.

---

# 27. Actor Identity

Where applicable, audit events shall identify the actor responsible for the
action.

The actor may be:

```
Authenticated User
System Process
```

The final actor representation will follow the common authentication and
identity architecture.

---

# 28. Target Identification

An audit event may need to identify the affected:

```
Module
Entity
Record
```

The exact implementation shall be defined in the detailed Audit Table
Design.

---

# 29. Action Classification

Audit events should distinguish different action types where required.

Examples:

```
CREATE
UPDATE
DELETE
APPROVE
REJECT
CANCEL
LOGIN
LOGOUT
EXPORT
STATUS_CHANGE
```

This is an example classification only.

The final controlled action catalogue requires confirmation before being
frozen.

---

# 30. System Event Logging

`system_event_log` provides the foundation for significant system-event
recording.

Examples may include:

```
Authentication events
Administrative actions
Workflow events
Scheduled events
Critical system events
```

The final event catalogue shall be established separately.

---

# 31. Audit Event vs Application Log

The Audit Module is not intended to replace ordinary application/debug
logging.

Application logs may be used for:

```
Debugging
Performance diagnostics
Error investigation
```

Audit records are used for:

```
Accountability
Business traceability
Compliance
Historical review
```

---

# 32. Audit Event vs Error Log

An application error does not automatically constitute an audit event.

Only events requiring auditability should become authoritative audit
records.

---

# 33. Audit Coverage

Modules should identify significant auditable operations during their
business-rule and functional-design stages.

Examples:

```
Membership approval
Membership status change
Transfer
Governance assignment
UPBS cancellation
Financial approval
Administrative changes
```

---

# 34. Audit Coverage Must Not Be Invented

A module should not be assumed to audit every database update merely because
the table has:

```
updated_at
```

The common audit standard determines which actions require centralized audit
history.

---

# 35. Standard Audit Fields

Normal business tables may contain standard audit metadata such as:

```
created_at
created_by_sangha_sevi_pk
updated_at
updated_by_sangha_sevi_pk
deleted_at
deleted_by_sangha_sevi_pk
```

These fields are different from the centralized:

```
system_event_log
```

---

# 36. Two-Level Audit Model

The ERP therefore distinguishes:

```text
Level 1
Business Record Audit Metadata

created_at
created_by
updated_at
updated_by


Level 2
Centralized Audit/Event History

audit_master
system_event_log
```

---

# 37. Audit and Soft Delete

Soft deletion of a business record does not mean that the audit history is
deleted.

Example:

```text
Business Record
    ↓
is_active = FALSE

Audit History
    ↓
Deletion/deactivation event preserved
```

---

# 38. Audit and Historical Records

Historical business records and centralized audit records complement each
other.

Neither should be used as a substitute for the other.

---

# 39. Audit and Finance

Financial operations may require enhanced auditability.

Examples:

```
Receipt generation
Donation approval
Grant processing
Financial corrections
```

The exact Finance audit rules shall be established by Finance requirements
and common audit standards.

---

# 40. Audit and Governance

Governance-related changes may require strong auditability.

Examples:

```
Position assignment
Acting assignment
Governing body changes
Approval decisions
Election results
```

The Audit Module provides the common technical audit foundation.

---

# 41. Audit and Membership

Membership operations may require auditability for:

```
Approval
Status change
Renewal
Transfer
Cessation
Reinstatement
Correction
```

The exact membership-specific audit rules remain owned by the Membership
domain.

---

# 42. Audit and Attendance

Attendance operations may require auditability for:

```
Attendance correction
Post-completion correction
Administrative override
Reconciliation
```

The Attendance Module defines the business event.

Audit records preserve the system action.

---

# 43. Audit and UPBS

UPBS operations may require auditability for:

```
Registration changes
Delegate changes
Accommodation changes
Event cancellation
Event rescheduling
Post-event corrections
```

The UPBS Module owns the business rules.

The Audit Module provides centralized audit history.

---

# 44. Audit and Sevak

The Sevak source explicitly requires auditability for:

```
Status changes
Enrollment
Event actions
Cancellation/rescheduling
Post-completion correction
```

Historical records and audit trails must be preserved.

---

# 45. Centralized Correction Principle

Where a business record has reached a locked/completed historical state,
post-completion corrections should use the centralized ERP correction and
audit mechanism defined by the applicable domain.

The original value must remain traceable.

---

# 46. Audit Reports

The Audit Module may provide authorized users with audit-history views.

Potential views include:

```
Recent Audit Events
Events by User
Events by Module
Events by Entity
Events by Date
Status Changes
Administrative Actions
```

These are conceptual capabilities.

The exact report set requires separate UI/report design.

---

# 47. Audit Search

Authorized audit users should eventually be able to filter audit history by
appropriate criteria.

Potential criteria:

```
Date
User
Module
Action
Entity
Record
Event Type
```

Final searchable fields depend on the final schema.

---

# 48. Audit Retention

Audit history is intended to be preserved as part of the ERP historical
record.

The exact technical retention/archive policy is not frozen by this overview.

It must not silently contradict the project-wide historical-preservation
principle.

---

# 49. Audit and Backup

Audit data must be included in the normal database backup strategy.

The Backup & Technical domain owns:

```
backup_master
restore_history
```

The Audit Module does not create a separate backup mechanism.

---

# 50. Audit and Security

Security-sensitive actions may require audit records.

The Audit Module provides historical traceability while Authentication &
Security controls access.

These remain separate responsibilities.

---

# 51. Audit and Notifications

Where an auditable operation also generates a notification:

```text
Business Action
     │
     ├── Audit
     │
     └── Notification
```

Audit and notification are independent concerns.

---

# 52. No Duplicate Notification System

The Audit Module shall not create:

```
audit_notification
```

or another notification mechanism.

It shall use the common Notification framework where required.

---

# 53. No Duplicate User System

The Audit Module shall not create:

```
audit_user
```

or another identity system.

It shall reference the existing ERP authentication/identity architecture.

---

# 54. Current Table Count

```text
audit_master
system_event_log

TOTAL = 2
```

---

# 55. Current Scope

The current Audit Module scope is:

```text
Audit Definitions
        +
System Event History
        +
Centralized Traceability
        +
Historical Preservation
```

---

# 56. Future Expansion Boundary

The current two-table foundation does not automatically authorize creation
of:

```
audit_change_detail
audit_field_change
audit_login_history
audit_access_log
audit_approval_history
```

If detailed requirements require such entities, they must be separately
approved and designed.

---

# 57. Architecture Principle

The Audit Module follows:

```text
Business Module
      │
      ▼
Business Action
      │
      ├── Business Record
      │
      └── Audit Record
                 │
                 ▼
         Centralized History
```

---

# 58. Core Principle

The central Audit principle is:

```
Significant system actions must remain traceable.
```

This supports:

```
Accountability
Historical integrity
Governance
Compliance
Investigation
Operational transparency
```

---

# 59. Current Foundation Summary

```text
AUDIT
│
├── audit_master
│
└── system_event_log
```

Total:

```text
2 tables
```

---

# 60. Design Boundary

This overview establishes:

```
Audit Module Scope
Audit Responsibilities
Cross-Module Role
Historical Principles
Identity Boundary
RBAC Boundary
Business-History Boundary
Application-Log Boundary
Future Expansion Boundary
```

The exact ERD, business rules, and table columns shall be defined in the
subsequent Audit solution documents.

---

# 61. Status

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
