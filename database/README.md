# database/

Hand-written PostgreSQL DDL and seed data — the schema authority for the NSS ERP.

**DDL Execution Authority:** PostgreSQL role `nss_admin`
**Runtime Read/Write:** PostgreSQL role `app_backend`
**Architecture Authority:** SOL-ARCH-010 (DDL Creation Order),
SOL-ARCH-011 (Bootstrap Architecture), module table-design documents

> **Note:** PostgreSQL `nss_admin` is the *database-level* role that owns
> tables and executes DDL/seed scripts. It is **not** the ERP application
> role `NSS_ADMIN` (which is an RBAC role defined in `role_master` and
> enforced by the application layer). See SOL-ARCH-011 §7.2 for the
> full identity distinction.

---

## Execution Order

### Full Build (from scratch)

The build follows the bootstrap sequence defined in SOL-ARCH-011.
Prerequisites (superuser) must complete before the nss_admin phases.

```bash
# ─────────────────────────────────────────────────
# Prerequisites (run as PostgreSQL superuser)
# ─────────────────────────────────────────────────
psql -U postgres -d postgres -f database/scripts/00_create_database.sql
psql -U postgres -d nss_erp  -f database/scripts/01_extensions.sql

# ─────────────────────────────────────────────────
# Phase 0: Bootstrap RBAC Definitions
#          (3 tables, Depths 0–1)
#          Authority: SOL-ARCH-011 §4
# ─────────────────────────────────────────────────
for f in database/ddl/00_bootstrap/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

for f in database/seed/00_bootstrap/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 1: Foundation DDL (12 tables, Depths 0–4)
# ─────────────────────────────────────────────────
for f in database/ddl/01_foundation/0[2-9]*.sql database/ddl/01_foundation/1*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 2: Foundation Seed Data
# ─────────────────────────────────────────────────
for f in database/seed/01_foundation/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 3: Organization DDL (3 tables, Depths 0–3)
# ─────────────────────────────────────────────────
for f in database/ddl/02_organization/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 4: Organization Seed Data
# ─────────────────────────────────────────────────
for f in database/seed/02_organization/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 6+: Person, Auth/Admin remaining, etc.
#           (not yet implemented)
# ─────────────────────────────────────────────────
```

### Execution Sequence (all implemented tables)

Sequence numbers (`Seq#`) are the global position from
SOL-ARCH-010. Within the same depth, tables have no mutual FK
dependency and may be created in any order.

| Phase | Module | File | Table | Depth | Seq# |
|------:|--------|------|-------|------:|-----:|
| 0 | Bootstrap | `01_role_master.sql` | `role_master` | 0 | #13 |
| 0 | Bootstrap | `02_permission_master.sql` | `permission_master` | 0 | #14 |
| 0 | Bootstrap | `03_role_permission.sql` | `role_permission` | 1 | #20 |
| 1 | Foundation | `02_master_category.sql` | `master_category` | 0 | #1 |
| 1 | Foundation | `03_system_setting.sql` | `system_setting` | 0 | #2 |
| 1 | Foundation | `04_id_sequence_master.sql` | `id_sequence_master` | 0 | #3 |
| 1 | Foundation | `05_country.sql` | `country` | 0 | #4 |
| 1 | Foundation | `06_document_master.sql` | `document_master` | 0 | #5 |
| 1 | Foundation | `07_field_change_log.sql` | `field_change_log` | 0 | #6 |
| 1 | Foundation | `08_master_data.sql` | `master_data` | 1 | #18 |
| 1 | Foundation | `09_state.sql` | `state` | 1 | #19 |
| 1 | Foundation | `10_district.sql` | `district` | 2 | #26 |
| 1 | Foundation | `12_postal_code.sql` | `postal_code` | 2 | #88 |
| 1 | Foundation | `11_city_village.sql` | `city_village` | 3 | #32 |
| 1 | Foundation | `13_city_village_postal_code_map.sql` | `city_village_postal_code_map` | 4 | #89 |
| 3 | Organization | `01_organization_type_master.sql` | `organization_type_master` | 0 | #7 |
| 3 | Organization | `02_organization_status_master.sql` | `organization_status_master` | 0 | #8 |
| 3 | Organization | `03_organization.sql` | `organization` | 3 | #33 |

**Total implemented: 18 tables (3 Bootstrap RBAC + 12 Foundation + 3 Organization)**
**Phase 0 seed partial: `role_master` seeded (8 roles); `permission_master`/`role_permission` empty, pending the permission catalogue freeze**

See module READMEs for per-file details:
- `ddl/00_bootstrap/README.md` / `seed/00_bootstrap/README.md`
- `ddl/01_foundation/README.md` / `seed/01_foundation/README.md`
- `ddl/02_organization/README.md` / `seed/02_organization/README.md`

---

## Two-Pass DDL Strategy (SOL-ARCH-010 §5, SOL-ARCH-011 §6)

- **Pass 1:** CREATE TABLE statements (files in `ddl/`) — no audit-actor FKs
- **Pass 2:** ALTER TABLE ADD CONSTRAINT for `*_by_sangha_sevi_pk` columns —
  executed after `sangha_sevi` table exists and contains at least one record

Pass 2 is not yet implemented. It will be created when the Membership
module vertical slice produces the `sangha_sevi` table (Depth 4, #35).
The bootstrap administrator's Sangha Sevi identity is the precondition
for enforcing these constraints (SOL-ARCH-011 §7.3).

---

## Directory Structure

```
database/
├── scripts/
│   ├── 00_create_database.sql   Create DB + roles + dblink (superuser, postgres DB)
│   ├── 01_extensions.sql        Install extensions (superuser, nss_erp DB)
│   ├── 02_build.sh              Full schema build (all implemented phases)
│   └── 03_validate.sh           Post-build validation (all modules)
├── ddl/
│   ├── 00_bootstrap/     3 RBAC tables (Depths 0–1) — IMPLEMENTED
│   ├── 01_foundation/    12 tables (Depths 0–4) — IMPLEMENTED
│   ├── 02_organization/  3 tables (Depths 0–3) — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
├── seed/
│   ├── 00_bootstrap/     8 roles seeded; permission catalogue PENDING
│   ├── 01_foundation/    reference data — IMPLEMENTED
│   ├── 02_organization/  type masters + 3 unique orgs — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
└── README.md             this file
```

---

## Module Implementation Status

| Module | Tables | DDL Status | Next Action |
|--------|-------:|-----------|-------------|
| Bootstrap RBAC | 3 | ✅ IMPLEMENTED | `permission_master`/`role_permission` seed pending permission catalogue freeze |
| Foundation | 12 | ✅ IMPLEMENTED | — |
| Organization | 3 | ✅ IMPLEMENTED | — |
| Person | 1 | ⬜ SUPERSEDED — will be rewritten | Freeze column list |
| Authentication | 2 | ⏳ DESIGN | Freeze user_account, password_history columns |
| Administration | 5 | ⏳ DESIGN | 3 RBAC tables in Bootstrap; correspondence columns pending |
| Heritage | 4 | ⬜ NOT YET | — |
| Family | 3 | ⬜ NOT YET | — |
| Membership | 9 | ⬜ NOT YET | — |

Table counts are from the frozen SOL-ARCH-010 inventory. Modules not
listed above have frozen table counts but are further down the
implementation tier order (SOL-ARCH-008).

---

## Naming Convention

- Internal UUID surrogate keys: `<entity>_pk`
- Business/external identifiers: `<entity>_code` (never `_id` for business keys)
- Foreign keys: `fk_<source_table>_<target_concept>`
- Unique constraints: `uq_<table>_<columns>`
- Check constraints: `chk_<table>_<rule>`
- Indexes: `idx_<table>_<columns>`

---

## Scripts

All executable scripts live in `database/scripts/`. Run from the
repository root. Each accepts optional positional parameters:

```
DB_NAME  (default: nss_erp)
DB_USER  (default: nss_admin)
DB_HOST  (default: localhost)
DB_PORT  (default: 5432)
```

### 00_create_database.sql — Database and Role Setup

Run **once** by a PostgreSQL **superuser** (e.g. `postgres`) against
the `postgres` database. Installs `dblink` (for idempotent database
creation), creates the `nss_admin` and `app_backend` roles, creates
the `nss_erp` database, and grants CONNECT to `app_backend`.

Fully idempotent — safe to re-run.

```bash
psql -U postgres -d postgres -f database/scripts/00_create_database.sql
```

**Important:** This creates PostgreSQL-level roles only (`NOLOGIN` —
grant LOGIN per environment via `ALTER ROLE`). The ERP application
role `NSS_ADMIN` is a row in `role_master` (Phase 0 seed) and is a
separate security boundary (SOL-ARCH-011 §7.2). `nss_admin` is
intentionally not a SUPERUSER.

No credentials are stored in this file. Set passwords externally via
`ALTER ROLE ... PASSWORD '...'` or `.pgpass` / environment variables.

### 01_extensions.sql — PostgreSQL Extensions

Run by a PostgreSQL **superuser** against the `nss_erp` database,
after `00_create_database.sql`. Installs application extensions
required by Foundation DDL. Idempotent — safe to re-run.

```bash
psql -U postgres -d nss_erp -f database/scripts/01_extensions.sql
```

| Extension | Purpose |
|-----------|---------|
| `pgcrypto` | UUID generation (`gen_random_uuid` for PK defaults) |
| `pg_trgm` | Trigram indexes for fuzzy/partial text search |
| `btree_gin` | GIN indexes on non-array scalar types |
| `postgis` | Geospatial types, indexes, and functions (distance, containment) |

### 02_build.sh — Full Schema Build

Executes all DDL and seed scripts for currently implemented modules
in SOL-ARCH-011 phase order. Runs as `nss_admin`.

```bash
./database/scripts/02_build.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
```

Phases executed:

| Phase | Module | Content |
|------:|--------|---------|
| 0 | Bootstrap RBAC | 3 tables + seed (roles, permissions, mappings) |
| 1 | Foundation | 12 tables (Depths 0–4) |
| 2 | Foundation | Seed data (categories, locations, settings, postal codes) |
| 3 | Organization | 3 tables (Depths 0–3) |
| 4 | Organization | Seed data (types, statuses, named orgs) |

**Not executed:** `03_person/` (superseded prototype), Pass 2
audit-actor FK constraints (deferred until `sangha_sevi` exists).

The script uses `set -euo pipefail` and `ON_ERROR_STOP=1` — any
failed SQL file halts the build immediately.

**This script is NOT idempotent.** Running it twice on the same
database will fail on `CREATE TABLE`. For a fresh rebuild, drop and
recreate the database first.

### 03_validate.sh — Post-Build Validation

Validates that all implemented modules were built correctly.
**Does NOT execute any DDL or seed scripts** — run `02_build.sh`
first. Covers all currently implemented modules.

```bash
./database/scripts/03_validate.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
```

Validation checks per module:

| Module | Tables | Checks |
|--------|-------:|--------|
| Bootstrap RBAC | 3 | Existence, 8 roles seeded, unique `role_code`, FK integrity (`role_permission` → both parents) |
| Foundation | 12 | Existence, row counts (categories, locations, settings, postal codes), unique codes, FK integrity (location hierarchy, `master_data` → `master_category`), deferred columns on `document_master` |
| Organization | 3 | Existence, 8 types / 6 statuses / 3 orgs seeded, unique codes, FK integrity (org → type, status, country, city_village, postal_code) |

**Extend this script when new modules are added to `02_build.sh`.**

---

## Superseded Artifacts

The following exist on `develop` from an earlier prototype iteration and
are NOT consistent with the frozen architecture (SOL-ARCH-009/010):

- `ddl/03_person/*` — uses per-domain masters instead of `master_data` pattern
- `seed/03_person/*` — seeds into non-existent tables (`gender_master`, etc.)
