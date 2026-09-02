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
Phase 0 establishes RBAC definitions before any business data.

```bash
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
# Phase 1: Extensions
# ─────────────────────────────────────────────────
psql -U nss_admin -d nss_erp -f database/ddl/01_foundation/01_extensions.sql

# ─────────────────────────────────────────────────
# Phase 2: Foundation DDL (12 tables, Depths 0–4)
# ─────────────────────────────────────────────────
for f in database/ddl/01_foundation/0[2-9]*.sql database/ddl/01_foundation/1*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 3: Foundation Seed Data
# ─────────────────────────────────────────────────
for f in database/seed/01_foundation/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 4: Organization DDL (3 tables, Depths 0–3)
# ─────────────────────────────────────────────────
for f in database/ddl/02_organization/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# ─────────────────────────────────────────────────
# Phase 5: Organization Seed Data
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
| 1 | Foundation | `01_extensions.sql` | pg_trgm, pgcrypto, btree_gin | — | — |
| 2 | Foundation | `02_master_category.sql` | `master_category` | 0 | #1 |
| 2 | Foundation | `03_system_setting.sql` | `system_setting` | 0 | #2 |
| 2 | Foundation | `04_id_sequence_master.sql` | `id_sequence_master` | 0 | #3 |
| 2 | Foundation | `05_country.sql` | `country` | 0 | #4 |
| 2 | Foundation | `06_document_master.sql` | `document_master` | 0 | #5 |
| 2 | Foundation | `07_field_change_log.sql` | `field_change_log` | 0 | #6 |
| 2 | Foundation | `08_master_data.sql` | `master_data` | 1 | #18 |
| 2 | Foundation | `09_state.sql` | `state` | 1 | #19 |
| 2 | Foundation | `10_district.sql` | `district` | 2 | #26 |
| 2 | Foundation | `12_postal_code.sql` | `postal_code` | 2 | #88 |
| 2 | Foundation | `11_city_village.sql` | `city_village` | 3 | #32 |
| 2 | Foundation | `13_city_village_postal_code_map.sql` | `city_village_postal_code_map` | 4 | #89 |
| 4 | Organization | `01_organization_type_master.sql` | `organization_type_master` | 0 | #7 |
| 4 | Organization | `02_organization_status_master.sql` | `organization_status_master` | 0 | #8 |
| 4 | Organization | `03_organization.sql` | `organization` | 3 | #33 |

**Total implemented: 15 tables (12 Foundation + 3 Organization)**
**Phase 0 planned: 3 tables (Bootstrap RBAC) — column design pending**

See module READMEs for per-file details:
- `ddl/01_foundation/README.md` / `seed/01_foundation/README.md`
- `ddl/02_organization/README.md` / `seed/02_organization/README.md`

Bootstrap RBAC READMEs will be created during the Phase 0 vertical slice.

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
├── ddl/
│   ├── 00_bootstrap/     3 RBAC tables (Depths 0–1) — DESIGN PENDING
│   ├── 01_foundation/    12 tables (Depths 0–4) — IMPLEMENTED
│   ├── 02_organization/  3 tables (Depths 0–3) — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
├── seed/
│   ├── 00_bootstrap/     permissions + 7 roles + mappings — DESIGN PENDING
│   ├── 01_foundation/    reference data — IMPLEMENTED
│   ├── 02_organization/  type masters + 3 unique orgs — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
└── README.md             this file
```

---

## Module Implementation Status

| Module | Tables | DDL Status | Next Action |
|--------|-------:|-----------|-------------|
| Bootstrap RBAC | 3 | ⏳ DESIGN | Freeze role_master, permission_master, role_permission columns |
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

## Validation

Module-level validation scripts live at the repository root:

| Script | Scope |
|--------|-------|
| `validate_foundation.sh` | Foundation DDL + seed (12 tables) |

Usage:

```bash
./validate_foundation.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
```

Defaults: `nss_erp`, `nss_admin`, `localhost`, `5432`.

Organization validation script is planned but not yet created.

---

## Superseded Artifacts

The following exist on `develop` from an earlier prototype iteration and
are NOT consistent with the frozen architecture (SOL-ARCH-009/010):

- `ddl/03_person/*` — uses per-domain masters instead of `master_data` pattern
- `seed/03_person/*` — seeds into non-existent tables (`gender_master`, etc.)
