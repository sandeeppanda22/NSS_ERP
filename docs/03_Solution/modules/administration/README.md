# NSS ERP Administration Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0/v0.1.0 (lifecycle doc). Full Solution design now 5
files; there is no `backend/administration/` Django app — `backend/authentication/` currently
implements a much simpler `Role`/`UserRole`/`LoginAudit` model set that predates this design
(see Note below).

---

## Documents

01_administration_module_overview.md (`SOL-ADMIN-001`) — Version 1.0.0
Purpose: Centralized administrative control framework — Users, Roles, Permissions,
Organizational Scope, Administrative Access, System Administration.

02_administration_erd.md — Version 1.0.0
Purpose: Entity relationship design for the six-table authorization framework.

03_administration_lifecycle.md — Version 0.1.0, DRAFT, Document ID `SOL-ADMIN-005`
Purpose: `role_master`/`permission_master` (ACTIVE/INACTIVE), `role_permission`/`user_role`
(ASSIGNED/REVOKED), `admin_scope` (ASSIGNED/MODIFIED/REVOKED), governance position ≠ role,
account deactivation freezes RBAC, Person-death integration.

04_administration_business_rules.md — Version 1.0.0, ADMIN-BR-001–ADMIN-BR-075 (was `03_...`
before the lifecycle doc was inserted and file numbers shifted down one slot)
Purpose: Business rules for centralized RBAC + organizational scope. No module-specific
permission architectures permitted — e.g. Sevak-specific rules explicitly delegate to this
central framework rather than inventing their own.

05_administration_table_design.md — Version 1.0.0 (was `04_...`)
Purpose: Physical table design — six source-supported authorization tables.

---

## Key facts

- Six tables: `user_account`, `role_master`, `permission_master`, `role_permission`,
  `user_role`, `admin_scope`. `password_history` deliberately stays under Authentication &
  Security (`docs/03_Solution/modules/authentication/`), not here.
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
cross-reference `SOL-LIFE-001`/`002`, see `CLAUDE.md` §13) · Business Rules Drafted (SOURCE
ALIGNED) · Table Design Drafted (SOURCE ALIGNED) · SQL Implementation Not Started ·
`backend/administration/` Django app does not exist yet
