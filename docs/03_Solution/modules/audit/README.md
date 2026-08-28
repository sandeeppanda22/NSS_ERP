# NSS ERP Audit Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0. Full Solution design complete (4 files); there is no
`backend/audit/` Django app. Cross-cutting audit/traceability capability — not a business
module in its own right.

---

## Documents

01_audit_module_overview.md (`SOL-AUDIT-001`) — Version 1.0.0
Purpose: Centralized audit and system-event history foundation; audit history, system event
logging, change traceability, administrative accountability, compliance support.

02_audit_erd.md — Version 1.0.0
Purpose: Entity relationship design for the two frozen tables.

03_audit_business_rules.md — Version 1.0.0, AUD-BR-001–AUD-BR-071
Purpose: Business rules governing what gets audited and how — includes explicit PENDING/FUTURE
markers for anything beyond the two frozen tables (e.g. field-level audit, login-history,
access-log, approval-history are explicitly NOT frozen).

04_audit_table_design.md — Version 1.0.0
Purpose: Physical table design — `audit_master`, `system_event_log`. No assumed FK between the
two tables.

---

## Key facts

- Two frozen foundation tables only: `audit_master`, `system_event_log`.
- History Never Deleted applies to audit records themselves.
- Explicitly distinguishes Audit (system-action traceability) from ordinary business-record
  history (e.g. `membership_status_history`) — see `docs/PROJECT_DOCUMENTATION.md` for the
  project-wide History Never Deleted principle.

---

## Current Status

Design Complete · ERD Complete · Business Rules Drafted (SOURCE ALIGNED) · Table Design
Drafted (SOURCE ALIGNED) · SQL Implementation Not Started · `backend/audit/` Django app does
not exist yet
