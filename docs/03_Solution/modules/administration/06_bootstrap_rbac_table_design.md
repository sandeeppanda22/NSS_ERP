# NSS ERP — Phase 0 Bootstrap RBAC Table Design

**Document ID:** SOL-BOOT-001
**Version:** 1.0.0
**Status:** DRAFT — COLUMN FREEZE CANDIDATE
**Module:** Bootstrap RBAC (Phase 0)
**Parent Documents:**
- SOL-ARCH-011 — Bootstrap Architecture
- SOL-ARCH-010 — DDL Creation Order
- SOL-ADMIN-004 — Administration Table Design (§8–10)

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the frozen column-level physical design for the
three Phase 0 Bootstrap RBAC tables:

    role_master
    permission_master
    role_permission

These tables are created before Foundation (SOL-ARCH-011 §4, Phase 0)
and have zero FK dependencies on any other module.

---

# 2. Scope

This document covers:

- Physical column definitions (name, type, nullability, default)
- Primary keys
- Foreign keys
- Unique constraints
- CHECK constraints
- Indexes

This document does NOT cover:

- Permission catalogue (PENDING — SOL-ADMIN-004 §9.5)
- Role seed data (7 frozen roles defined in SOL-ADMIN-004 §8.7)
- Role-permission mappings (depend on permission catalogue)
- Tables outside Phase 0 (user_account, user_role, admin_scope, password_history)

---

# 3. Design Standards

All columns follow the established project conventions:

| Convention | Pattern |
|------------|---------|
| Primary key | `<table>_pk UUID DEFAULT gen_random_uuid()` |
| Business code | `<concept>_code VARCHAR NOT NULL UNIQUE` |
| Display name | `<concept>_name VARCHAR NOT NULL` |
| Timestamps | `TIMESTAMPTZ` |
| Soft delete | `is_active BOOLEAN + deleted_at TIMESTAMPTZ` with CHECK |
| Audit actor | `*_by_sangha_sevi_pk UUID` — column present, FK deferred to Pass 2 |
| FK naming | `fk_<source_table>_<target_concept>` |
| UQ naming | `uq_<table>_<columns>` |
| CHK naming | `chk_<table>_<rule>` |
| IDX naming | `idx_<table>_<columns>` |

---

# 4. `role_master`

**SOL-ARCH-010:** Depth 0, Sequence #13
**Owner:** Administration (SOL-ADMIN-004 §2)
**FK dependencies:** None

## 4.1 Column Definitions

| # | Column | Type | Null | Default | Description |
|--:|--------|------|:----:|---------|-------------|
| 1 | `role_master_pk` | UUID | NO | `gen_random_uuid()` | Technical primary key |
| 2 | `role_code` | VARCHAR(50) | NO | — | Stable machine identifier (e.g. `NSS_ADMIN`) |
| 3 | `role_name` | VARCHAR(100) | NO | — | Human-readable display name |
| 4 | `role_class` | VARCHAR(30) | NO | — | Classification: `SYSTEM` or `ORGANIZATIONAL` |
| 5 | `scope_level` | VARCHAR(30) | YES | NULL | Applicable org scope: `KENDRA`, `ANCHALIKA`, `ZILLA`, `SAKHA`, or NULL for system-wide |
| 6 | `description` | TEXT | YES | NULL | Purpose and responsibility summary |
| 7 | `display_order` | INTEGER | NO | 0 | UI sort order |
| 8 | `created_at` | TIMESTAMPTZ | NO | `CURRENT_TIMESTAMP` | Record creation timestamp |
| 9 | `created_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 10 | `updated_at` | TIMESTAMPTZ | YES | NULL | Last modification timestamp |
| 11 | `updated_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 12 | `deleted_at` | TIMESTAMPTZ | YES | NULL | Soft-delete timestamp |
| 13 | `deleted_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 14 | `is_active` | BOOLEAN | NO | TRUE | Soft-delete flag |

## 4.2 Constraints

| Constraint | Type | Definition |
|------------|------|------------|
| PK | PRIMARY KEY | `role_master_pk` |
| `uq_role_master_code` | UNIQUE | `role_code` |
| `uq_role_master_name` | UNIQUE | `role_name` |
| `chk_role_master_class` | CHECK | `role_class IN ('SYSTEM', 'ORGANIZATIONAL')` |
| `chk_role_master_scope_level` | CHECK | `scope_level IS NULL OR scope_level IN ('KENDRA', 'ANCHALIKA', 'ZILLA', 'SAKHA')` |
| `chk_role_master_soft_delete` | CHECK | `(is_active = TRUE AND deleted_at IS NULL) OR (is_active = FALSE AND deleted_at IS NOT NULL)` |

## 4.3 Indexes

| Index | Columns | Type |
|-------|---------|------|
| `idx_role_master_active` | `is_active` | btree |
| `idx_role_master_code` | `role_code` | btree |
| `idx_role_master_class` | `role_class` | btree |

## 4.4 Design Notes

- `role_code` is the stable relational identifier. Application code
  references roles by `role_code`, never by `role_name` or
  `role_master_pk` literals.

- `role_class` distinguishes system-wide roles (`SYSTEM`: NSS_ADMIN,
  AUDITOR, REPORT_VIEWER) from organizational-scope roles
  (`ORGANIZATIONAL`: KENDRA_ADMIN, ANCHALIKA_ADMIN, ZILLA_ADMIN,
  SAKHA_ADMIN). This classification is enforced by CHECK constraint,
  not application code.

- `scope_level` is NULL for system-wide roles. For organizational
  roles, it identifies the organizational scope at which the role
  operates. This is metadata about the role's intended scope — the
  actual scope assignment is in `admin_scope` (Phase 4).

- `display_order` follows the Foundation master-table convention.

- Audit-actor columns (`*_by_sangha_sevi_pk`) are present but their FK
  constraints are deferred to Pass 2 (SOL-ARCH-010 §5, SOL-ARCH-011 §6).
  During Phase 0 seed insertion, these columns are NULL because no
  Sangha Sevi identity exists yet.

---

# 5. `permission_master`

**SOL-ARCH-010:** Depth 0, Sequence #14
**Owner:** Administration (SOL-ADMIN-004 §2)
**FK dependencies:** None

## 5.1 Column Definitions

| # | Column | Type | Null | Default | Description |
|--:|--------|------|:----:|---------|-------------|
| 1 | `permission_master_pk` | UUID | NO | `gen_random_uuid()` | Technical primary key |
| 2 | `permission_code` | VARCHAR(80) | NO | — | Stable machine identifier (e.g. `PERSON_CREATE`) |
| 3 | `permission_name` | VARCHAR(150) | NO | — | Human-readable display name |
| 4 | `module_code` | VARCHAR(50) | NO | — | Owning business module (e.g. `PERSON`, `ORGANIZATION`, `MEMBERSHIP`) |
| 5 | `description` | TEXT | YES | NULL | What the permission authorizes |
| 6 | `display_order` | INTEGER | NO | 0 | UI sort order within module |
| 7 | `created_at` | TIMESTAMPTZ | NO | `CURRENT_TIMESTAMP` | Record creation timestamp |
| 8 | `created_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 9 | `updated_at` | TIMESTAMPTZ | YES | NULL | Last modification timestamp |
| 10 | `updated_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 11 | `deleted_at` | TIMESTAMPTZ | YES | NULL | Soft-delete timestamp |
| 12 | `deleted_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 13 | `is_active` | BOOLEAN | NO | TRUE | Soft-delete flag |

## 5.2 Constraints

| Constraint | Type | Definition |
|------------|------|------------|
| PK | PRIMARY KEY | `permission_master_pk` |
| `uq_permission_master_code` | UNIQUE | `permission_code` |
| `chk_permission_master_soft_delete` | CHECK | `(is_active = TRUE AND deleted_at IS NULL) OR (is_active = FALSE AND deleted_at IS NOT NULL)` |

## 5.3 Indexes

| Index | Columns | Type |
|-------|---------|------|
| `idx_permission_master_active` | `is_active` | btree |
| `idx_permission_master_code` | `permission_code` | btree |
| `idx_permission_master_module` | `module_code` | btree |

## 5.4 Design Notes

- `permission_code` follows a `<MODULE>_<ACTION>` convention
  (e.g. `PERSON_CREATE`, `ORGANIZATION_VIEW`, `MEMBERSHIP_APPROVE`).
  The exact catalogue is PENDING (SOL-ADMIN-004 §9.5).

- `module_code` identifies which business module owns the permission.
  This is a controlled value but is NOT an FK to a module table — it
  is a logical grouping for display and filtering. The valid values
  correspond to the project's module list.

- `permission_name` is NOT required to be unique across the system.
  Only `permission_code` is unique. Different modules might have
  similarly named permissions (e.g. "View Report") but their codes
  will differ (`FINANCE_VIEW_REPORT` vs `ATTENDANCE_VIEW_REPORT`).

- Audit-actor columns follow the same Pass 2 deferral as `role_master`.

---

# 6. `role_permission`

**SOL-ARCH-010:** Depth 1, Sequence #20
**Owner:** Administration (SOL-ADMIN-004 §2)
**FK dependencies:** `role_master` (Depth 0), `permission_master` (Depth 0)

## 6.1 Column Definitions

| # | Column | Type | Null | Default | Description |
|--:|--------|------|:----:|---------|-------------|
| 1 | `role_permission_pk` | UUID | NO | `gen_random_uuid()` | Technical primary key |
| 2 | `role_master_pk` | UUID | NO | — | FK → `role_master.role_master_pk` |
| 3 | `permission_master_pk` | UUID | NO | — | FK → `permission_master.permission_master_pk` |
| 4 | `created_at` | TIMESTAMPTZ | NO | `CURRENT_TIMESTAMP` | Record creation timestamp |
| 5 | `created_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 6 | `deleted_at` | TIMESTAMPTZ | YES | NULL | Soft-delete timestamp |
| 7 | `deleted_by_sangha_sevi_pk` | UUID | YES | NULL | Audit actor — FK deferred to Pass 2 |
| 8 | `is_active` | BOOLEAN | NO | TRUE | Soft-delete flag |

## 6.2 Constraints

| Constraint | Type | Definition |
|------------|------|------------|
| PK | PRIMARY KEY | `role_permission_pk` |
| `fk_role_permission_role` | FOREIGN KEY | `role_master_pk` → `role_master.role_master_pk` |
| `fk_role_permission_permission` | FOREIGN KEY | `permission_master_pk` → `permission_master.permission_master_pk` |
| `uq_role_permission_mapping` | UNIQUE | `(role_master_pk, permission_master_pk)` |
| `chk_role_permission_soft_delete` | CHECK | `(is_active = TRUE AND deleted_at IS NULL) OR (is_active = FALSE AND deleted_at IS NOT NULL)` |

## 6.3 Indexes

| Index | Columns | Type |
|-------|---------|------|
| `idx_role_permission_role` | `role_master_pk` | btree |
| `idx_role_permission_permission` | `permission_master_pk` | btree |
| `idx_role_permission_active` | `is_active` | btree |

## 6.4 Design Notes

- `role_permission` is a pure mapping table. It has no `updated_at` or
  `updated_by_sangha_sevi_pk` columns because a role-permission mapping
  is either active or soft-deleted — there is no meaningful "update" to
  the mapping itself. Reassigning a permission means soft-deleting the
  old mapping and creating a new one.

- The unique constraint on `(role_master_pk, permission_master_pk)`
  prevents duplicate active mappings. If a mapping is soft-deleted and
  later re-activated, the application creates a new row (the old
  soft-deleted row remains for audit history).

- Both FK columns are NOT NULL — a role-permission mapping without
  both sides is meaningless.

- No `ON DELETE CASCADE`. Deactivating a role does not automatically
  remove its permission mappings. The mappings remain as historical
  evidence. Application logic handles cascade deactivation if needed.

---

# 7. Frozen Role Seed Data Reference

The 7 frozen roles (SOL-ADMIN-004 §8.7) will be seeded in Phase 0:

| role_code | role_name | role_class | scope_level |
|-----------|-----------|------------|-------------|
| `NSS_ADMIN` | NSS Administrator | `SYSTEM` | NULL |
| `AUDITOR` | Auditor | `SYSTEM` | NULL |
| `REPORT_VIEWER` | Report Viewer | `SYSTEM` | NULL |
| `KENDRA_ADMIN` | Kendra Administrator | `ORGANIZATIONAL` | `KENDRA` |
| `ANCHALIKA_ADMIN` | Anchalika Administrator | `ORGANIZATIONAL` | `ANCHALIKA` |
| `ZILLA_ADMIN` | Zilla Administrator | `ORGANIZATIONAL` | `ZILLA` |
| `SAKHA_ADMIN` | Sakha Administrator | `ORGANIZATIONAL` | `SAKHA` |

`SELF_SERVICE_MEMBER` is explicitly excluded (SOL-ADMIN-004 §8.10).

The seed SQL will be created after this column design is frozen.

---

# 8. Permission Catalogue Status

The permission catalogue is NOT frozen (SOL-ADMIN-004 §9.5).

The `permission_master` table structure is frozen by this document.
The actual permission rows will be defined when the catalogue is
approved. Until then, Phase 0 seed scripts for `permission_master`
and `role_permission` remain empty or contain only a minimal
bootstrapping set if separately approved.

---

# 9. Pass 2 Audit-Actor FK Summary

The following columns across all three tables will receive FK
constraints in Pass 2, after `sangha_sevi` exists:

| Table | Column | FK Target |
|-------|--------|-----------|
| `role_master` | `created_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `role_master` | `updated_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `role_master` | `deleted_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `permission_master` | `created_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `permission_master` | `updated_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `permission_master` | `deleted_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `role_permission` | `created_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |
| `role_permission` | `deleted_by_sangha_sevi_pk` | `sangha_sevi.sangha_sevi_pk` |

These columns are nullable during Phase 0 because no Sangha Sevi
identity exists yet (SOL-ARCH-011 §7.3).

---

# 10. Status

```
DOCUMENT STATUS:
DRAFT — COLUMN FREEZE CANDIDATE

DOCUMENT ID:
SOL-BOOT-001

VERSION:
1.0.0

TABLES:
3 (role_master, permission_master, role_permission)

TOTAL COLUMNS:
35 (14 + 13 + 8)

NEXT:
Review and freeze → generate DDL files in database/ddl/00_bootstrap/
```
