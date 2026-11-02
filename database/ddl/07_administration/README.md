# database/ddl/07_administration/

Administration Module DDL — 2 tables (RBAC role-assignment + scope). **Implemented
(released in v0.11.0)** (see
`docs/PROJECT_DOCUMENTATION.md` → Tier 5).

Authority: SOL-ADMIN-004, SOL-AUTH-004, Tier 5 decisions (2026-09-15).

## DDL Execution Order

Execute AFTER Bootstrap RBAC DDL (`database/ddl/00_bootstrap/` — `role_master`) and
Authentication DDL (`database/ddl/06_authentication/` — `user_account`). Run as Phase 11 in
`database/scripts/02_build.sh`/`.ps1`, immediately after Phase 10 (Authentication). No seed folder
of its own — the `NSS_ERP_ADMIN`/`NSS-WIDE` `user_role`/`admin_scope` rows for the bootstrap admin
come from `database/seed/04_admin/` (Phase 13). The Depth column is the per-module numbering; the
SQL files' own `-- Depth:` headers say 3 (`user_role`) and 4 (`admin_scope`) — cosmetic only.

| # | File | Table | Depth | Depends on |
|--:|------|-------|------:|------------|
| 01 | `01_user_role.sql` | `user_role` | 4 | `user_account`, `role_master` |
| 02 | `02_admin_scope.sql` | `admin_scope` | 5 | `user_role`, `organization` |

> **Amendment (per `docs/03_Solution/architecture/DDL_CREATION_ORDER.md`):** `admin_scope` moved
> from Depth 4 to Depth 5 — its FK is to `user_role_pk`, not directly to `user_account_pk`.

## What These Tables Are For

- **`user_role`** — junction table assigning one of the 10 frozen `role_master` roles to a
  `user_account`. Multi-role per user is supported (a user can hold several rows), and a user
  can even hold the **same** role twice with different scopes (e.g. `NSS_ERP_SAKHA_ADMIN` for
  two different Sakhas) — duplicate-scope prevention (same role + same scope_level + same org)
  is enforced in the API layer (`api/routers/admin.py::assign_role()`), not by a DB constraint.
  Revocation is soft (`is_active = FALSE`, `revoked_at`, `revoked_by_sangha_sevi_pk`) — no
  separate `role_history` table (frozen decision).
- **`admin_scope`** — the organizational scope attached to *one specific* `user_role` assignment
  (`UNIQUE (user_role_pk)` — exactly one scope row per role assignment, not per user globally).
  `scope_level` is one of `NSS-WIDE`/`KENDRA`/`ANCHALIKA`/`ZILLA`/`SAKHA`/`PATHA_CHAKRA`/`KENDRA_MAHILA_SANGHA`/`ADVISORY_BOARD` (same 8 values as `role_master.scope_level`; `ADVISORY_BOARD` added in `02_admin_scope.sql` v1.1);
  `organization_pk` must be `NULL` for `NSS-WIDE`, `KENDRA`, `KENDRA_MAHILA_SANGHA` and `ADVISORY_BOARD` and non-`NULL` for every other level (enforced
  by a CHECK constraint, not just convention). This is what `UserContext.has_scope_for_org()`/
  `is_nss_wide()` (`api/services/rbac_service.py`) reads to decide whether a given admin action
  is allowed against a given organization.

## Key FK Relationships

- `user_role.user_account_pk` → `nss.user_account`; `.role_master_pk` → `nss.role_master`.
- `admin_scope.user_role_pk` → `user_role`, `UNIQUE`; `.organization_pk` → `nss.organization`
  (nullable — `NULL` only for `NSS-WIDE` scope).

Audit-actor FKs are nullable columns in this pass, same as every other module — deferred to
Pass 2.

## Non-Obvious Constraints

- **No `UNIQUE (user_account_pk, role_master_pk)` on `user_role`** — deliberate: a user can have
  the same role with different scopes (see above). Don't add one without also revisiting the
  API-layer duplicate check.
- **`chk_admin_scope_org_consistency`** — `CHECK ((scope_level IN ('NSS-WIDE','KENDRA','KENDRA_MAHILA_SANGHA','ADVISORY_BOARD') AND
  organization_pk IS NULL) OR (scope_level NOT IN (...same four...) AND organization_pk IS NOT NULL))` — the DB-level
  guarantee behind `UserContext.is_nss_wide()`.
- **`chk_user_role_revocation`** — ties `revoked_at` to `is_active`: an active assignment must
  have `revoked_at IS NULL`; a revoked one must have `is_active = FALSE` (but `revoked_at` isn't
  itself required to be non-NULL on revocation by this particular CHECK — only `is_active`
  matters here; the API always sets both together).

See `api/services/rbac_service.py::load_user_context()` for how these two tables are actually
read at request time, and `docs/PROJECT_DOCUMENTATION.md` → Key Workflow #9 for the full
login/RBAC flow.
