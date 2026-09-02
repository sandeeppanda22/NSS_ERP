# NSS ERP Administration Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0/v0.1.0 (lifecycle doc). Full Solution design is 9
files (5 core + 4 Correspondence Register); there is no
`backend/administration/` Django app — `backend/authentication/` currently implements a much
simpler `Role`/`UserRole`/`LoginAudit` model set that predates this design (see Note below).

---

## Documents

01_administration_module_overview.md (`SOL-ADMIN-001`) — Version 1.0.0
Purpose: Centralized administrative control framework — Users, Roles, Permissions,
Organizational Scope, Administrative Access, System Administration. §55/§56 record
`CORR-DECISION-003` (Correspondence Register ownership).

02_administration_erd.md — Version 1.0.0
Purpose: Entity relationship design for the RBAC authorization framework.

03_administration_lifecycle.md — Version 0.1.0, DRAFT, Document ID `SOL-ADMIN-005`
Purpose: `role_master`/`permission_master` (ACTIVE/INACTIVE), `role_permission`/`user_role`
(ASSIGNED/REVOKED), `admin_scope` (ASSIGNED/MODIFIED/REVOKED), governance position ≠ role,
account deactivation freezes RBAC, Person-death integration.

04_administration_business_rules.md — Version 1.0.0, ADMIN-BR-001–ADMIN-BR-075
Purpose: Business rules for centralized RBAC + organizational scope. No module-specific
permission architectures permitted — e.g. Sevak-specific rules explicitly delegate to this
central framework rather than inventing their own.

05_administration_table_design.md — Version 1.0.0
Purpose: Physical table design. Contains the **Table Ownership Declaration (Frozen)**
that splits RBAC-adjacent tables exclusively between this module and Authentication (see Key
facts below).

06_correspondence_register_erd.md (`SOL-ADMIN-006`)
Purpose: 3 entities — `correspondence`, `correspondence_document` (junction to Foundation's
`document_master`), `correspondence_finance_reference` (M:N junction to Finance's
`financial_transaction`). Defines `CORR-ARCH-001` (Financial Traceability — reference, never
own, a Finance transaction) and `CORR-ARCH-002` (Cross-Module Record Traceability — a reusable
platform capability any module can use to associate its own records with a communication,
without transferring ownership to Administration).

07_correspondence_register_lifecycle.md (`SOL-ADMIN-007`)
Purpose: Four-state model `REGISTERED → PENDING_ACTION → ACTIONED → CLOSED`. Reopen is only
permitted from `ACTIONED` or `CLOSED` back to `PENDING_ACTION` (never `CLOSED → ACTIONED`
directly); `CLOSED` is soft-terminal (reopenable), no `DRAFT` state, reopen requires non-empty
remarks.

08_correspondence_register_business_rules.md (`SOL-ADMIN-008`)
Purpose: 18 rules (`CORR-BR-001`–`018`). 17 ERP-FROZEN (reference-number format/immutability,
sender/recipient constraints, reopen-remarks requirement, no-backdating, Finance-reference
integrity, never-hard-delete, no domain logic in correspondence, etc.); 1 PENDING
(`CORR-BR-018` — the `relationship_type` candidate values for `correspondence_finance_reference`
are deferred until Finance's own transaction taxonomy is frozen).

09_correspondence_register_table_design.md (`SOL-ADMIN-009`)
Purpose: 3 tables — `correspondence`, `correspondence_document`, `correspondence_finance_reference`.
UUID PKs, standard audit columns, CHECK constraints (sender/recipient: exactly one of
person/organization/external-name populated); two-pass DDL (the Finance FK and all
audit-actor FKs deferred to Pass 2).

---

## Key facts

- **Table Ownership Declaration (Frozen) — 8
  Administration-owned tables**: `role_master`, `permission_master`, `role_permission`,
  `user_role`, `admin_scope` (the original 5 RBAC tables) plus `correspondence`,
  `correspondence_document`, `correspondence_finance_reference` (Correspondence Register).
  **`user_account` and `password_history` are exclusively Authentication & Security-
  owned** (`docs/03_Solution/modules/authentication/`) — both modules may reference the other's
  tables via FK, but ownership is exclusive and canonical per this declaration.
- **Correspondence Register (`CORR-DECISION-003`, `CORR-ARCH-001`/`002`, frozen)** —
  Administration owns a generic inward/outward official-communication register (registration,
  reference numbering, sender/recipient, subject, medium, status/follow-up), explicitly *not* a
  generic application/workflow engine and *not* an owner of the underlying business matter or
  of financial transactions (those stay with Finance under `FIN-ARCH-001`). Domain-specific
  requests (membership renewal, property matters, governance decisions, etc.) remain owned by
  their respective modules — Administration doesn't become a generic "Correspondence &
  Applications" module.
- Role + Scope model for effective access; **Position ≠ Role** and **Membership ≠ Role** are
  explicit boundaries (a Governance body position or a membership category never implies an
  application permission by itself).
- No `role_history`/`scope_history`/`permission_group` tables frozen.

## Note — design/code gap

`backend/authentication/models.py` implements `Role`, `UserRole`, `LoginAudit` — a much
simpler, unrelated placeholder schema (plain auto-increment PKs, no `permission_master`/
`admin_scope` concept) that predates and does not match this design. There is no
`backend/administration/` app; if one is scaffolded later it should target this design rather
than extend the current `authentication.Role` model as-is.

---

## Current Status

Design Complete · ERD Complete · Lifecycle Documented (SOL-ADMIN-005 — does not yet
cross-reference `SOL-LIFE-001`/`002`, see `docs/PROJECT_DOCUMENTATION.md` → "Open questions /
TODOs") · Business Rules Drafted (SOURCE
ALIGNED) · Table Design Drafted (SOURCE ALIGNED) · Correspondence Register fully designed
(SOL-ADMIN-006–009, one PENDING rule) · SQL Implementation Not Started ·
`backend/administration/` Django app does not exist yet
