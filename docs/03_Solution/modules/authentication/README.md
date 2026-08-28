# NSS ERP Authentication & Security Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0/v0.1.0 (lifecycle doc). Full Solution design now 5
files. The `backend/authentication/` Django app already has real models (`Role`, `UserRole`,
`LoginAudit`) and a working login view — see `backend/authentication/README.md` — but they are
a different, simpler schema than the one designed here (see Note below).

**Naming note:** this Solution-layer document set (`SOL-AUTH-001`…`005`) is unrelated to the
governance-layer `AUTH-001` under `docs/00_Project_Governance/AUTH/` (the Authoritative
Reference Standard) — see `CLAUDE.md` §6's terminology note. Same three letters, two entirely
different documents.

---

## Documents

01_authentication_security_module_overview.md (`SOL-AUTH-001`) — Version 1.0.0
Purpose: Centralized security foundation — authentication, account security, password
security, identity verification, secure session access; authorization management via
Roles/Permissions/Organizational Scope.

02_authentication_security_erd.md — Version 1.0.0
Purpose: Entity relationship design for the seven-table security foundation.

03_authentication_security_lifecycle.md — Version 0.1.0, DRAFT, Document ID `SOL-AUTH-005`
Purpose: `user_account` states (ACTIVE/LOCKED/INACTIVE), append-only `password_history`,
conceptual session lifecycle (application layer), RBAC deferred to Administration, account
deactivation preserves business records, Person-death integration.

04_authentication_security_business_rules.md — Version 1.0.0, AUTH-BR-001–AUTH-BR-080 (was
`03_...` before the lifecycle doc was inserted and file numbers shifted down one slot)
Purpose: Business rules — Argon2 password hashing, JWT authentication, session management,
encrypted sensitive data (including Aadhaar), Row-Level Security identified as security
principles. Explicitly does not freeze `login_history`/`session_history`/MFA/password-reset/
lockout tables — "security standards do not by themselves authorize new database tables."

05_authentication_security_table_design.md — Version 1.0.0 (was `04_...`)
Purpose: Physical table design — seven tables split between identity/credential security here
and RBAC management in Administration.

---

## Key facts

- Seven tables: `user_account`, `password_history`, `role_master`, `permission_master`,
  `role_permission`, `user_role`, `admin_scope`. This module owns identity verification and
  credential security (`user_account` + `password_history`); RBAC *management* of the other
  five is owned by `docs/03_Solution/modules/administration/` (they appear here too because
  authentication needs to *evaluate* roles/permissions/scope, not because it manages them).
- No `login_history`, `session_history`, MFA, password-reset, or lockout tables frozen yet.

## Note — design/code gap

`backend/authentication/models.py` currently implements `Role`, `UserRole`, `LoginAudit` (plain
auto-increment PKs, FK to Django's built-in `auth.User`) — none of `user_account`,
`password_history`, `permission_master`, `role_permission`, or `admin_scope` from this design
exist in code. `LoginAudit` is a rough precursor to a future `login_history` concept, but this
design doc explicitly does not freeze that table yet. Treat the current Django models as a
placeholder to be replaced, not an implementation of this design.

---

## Current Status

Design Complete · ERD Complete · Lifecycle Documented (SOL-AUTH-005 — does not yet
cross-reference `SOL-LIFE-001`/`002`, see `CLAUDE.md` §13) · Business Rules Drafted (SOURCE
ALIGNED) · Table Design Drafted (SOURCE ALIGNED) · SQL Implementation Not Started ·
`backend/authentication/` exists but implements an unrelated, simpler schema
