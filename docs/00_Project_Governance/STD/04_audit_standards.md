# NSS ERP Audit Standards

Version: 1.0

Status: FROZEN

---

# 1. Purpose

This document defines the audit and history management standards for NSS ERP.

Auditability is a core architectural principle.

All business actions must be traceable.

---

# 2. Core Principle

History Never Deleted

The system must preserve:

* Creation History
* Modification History
* Approval History
* Assignment History
* Membership History
* Governance History
* Attendance History

---

# 3. Audit Objectives

The audit framework shall answer:

Who performed an action?

What was changed?

When was it changed?

Why was it changed?

What was the previous value?

What is the current value?

---

# 4. Mandatory Audit Columns

Every transactional table shall contain:

created_at

created_by_sangha_sevi_pk

updated_at

updated_by_sangha_sevi_pk

deleted_at

deleted_by_sangha_sevi_pk

is_active

---

# 5. Column Definitions

## created_at

Timestamp when the record was created.

Type:

TIMESTAMPTZ

---

## created_by_sangha_sevi_pk

Member who created the record.

Type:

UUID

References:

sangha_sevi

---

## updated_at

Latest modification timestamp.

Type:

TIMESTAMPTZ

---

## updated_by_sangha_sevi_pk

Member who performed the latest update.

Type:

UUID

---

## deleted_at

Soft deletion timestamp.

Type:

TIMESTAMPTZ

Nullable.

---

## deleted_by_sangha_sevi_pk

Member who performed deletion.

Type:

UUID

Nullable.

---

## is_active

Soft delete indicator.

Type:

BOOLEAN

Default:

TRUE

---

# 6. Soft Delete Standard

Physical deletion is prohibited.

Never:

DELETE FROM table_name;

Use:

is_active = FALSE

deleted_at = CURRENT_TIMESTAMP

deleted_by_sangha_sevi_pk = user

---

# 7. History Tables

Important business entities require dedicated history tables.

Examples:

membership_status_history

family_head_history

position_assignment_history

organization_hierarchy_history

---

# 8. Audit Master Table

Central audit logging shall be maintained.

Table:

audit_master

Purpose:

Track all significant business changes.

---

# 9. Audit Master Fields

audit_pk

entity_name

entity_pk

action_type

old_value_json

new_value_json

changed_by_sangha_sevi_pk

changed_at

ip_address

remarks

---

# 10. Action Types

CREATE

UPDATE

DELETE

APPROVE

REJECT

TRANSFER

RENEW

ASSIGN

REMOVE

LOGIN

LOGOUT

---

# 11. Immutable Audit Rule

Audit records shall never be edited.

Audit records shall never be deleted.

Only insert operations are allowed.

---

# 12. System Event Logging

Table:

system_event_log

Purpose:

Track system-level events.

Examples:

Login Success

Login Failure

Password Reset

Permission Change

Role Assignment

Data Import

Data Export

---

# 13. Approval Audit

Every approval workflow shall record:

Approver

Role

Decision

Timestamp

Comments

Previous Status

New Status

---

# 14. Membership Audit Requirements

Track:

Registration

Renewal

Transfer

Probation Review

Parichaya Patra Issuance

Status Changes

---

# 15. Governance Audit Requirements

Track:

Position Assignment

Position Removal

Election Results

Vacancy Creation

Acting Assignments

Committee Membership

---

# 16. Attendance Audit Requirements

Track:

Attendance Entry

Attendance Modification

Attendance Review

Attendance Deferral

Attendance Closure

---

# 17. Security Audit Requirements

Track:

User Login

Failed Login

Password Change

Role Assignment

Permission Assignment

Account Locking

Account Unlocking

---

# 18. Retention Policy

Audit records shall be retained permanently.

No automatic purge process is permitted.

---

# 19. Audit Principles

History Never Deleted

Every Change Traceable

Business Events Preserved

System Events Preserved

Audit Records Immutable

Compliance Before Convenience
