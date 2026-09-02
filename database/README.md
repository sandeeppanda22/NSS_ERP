# database/

Hand-written PostgreSQL DDL and seed data — the schema authority for the NSS ERP.

**Owner:** NSS_ADMIN (table creation and seed insertion)
**Runtime:** NSS_APP (application read/write)
**Authority:** SOL-ARCH-010 (DDL Creation Order), module table-design documents

## Execution Order

### Full Build (from scratch)

```bash
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
# Phase 4: Organization DDL (3 tables, Depths 0–4)
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
```

### Execution Sequence (all tables)

| Phase | Module | File | Table | Depth | Seq# |
|------:|--------|------|-------|------:|-----:|
| 1 | Foundation | `01_extensions.sql` | pg_trgm, uuid-ossp | — | — |
| 2 | Foundation | `02_master_category.sql` | `master_category` | 0 | #1 |
| 2 | Foundation | `03_system_setting.sql` | `system_setting` | 0 | #2 |
| 2 | Foundation | `04_id_sequence_master.sql` | `id_sequence_master` | 0 | #3 |
| 2 | Foundation | `05_country.sql` | `country` | 0 | #4 |
| 2 | Foundation | `06_document_master.sql` | `document_master` | 0 | #5 |
| 2 | Foundation | `07_field_change_log.sql` | `field_change_log` | 0 | #6 |
| 2 | Foundation | `08_master_data.sql` | `master_data` | 1 | #18 |
| 2 | Foundation | `09_state.sql` | `state` | 1 | #19 |
| 2 | Foundation | `10_district.sql` | `district` | 2 | #24 |
| 2 | Foundation | `11_city_village.sql` | `city_village` | 3 | #28 |
| 2 | Foundation | `12_postal_code.sql` | `postal_code` | 3 | #29 |
| 2 | Foundation | `13_city_village_postal_code_map.sql` | `city_village_postal_code_map` | 4 | #32 |
| 4 | Organization | `01_organization_type_master.sql` | `organization_type_master` | 0 | #7 |
| 4 | Organization | `02_organization_status_master.sql` | `organization_status_master` | 0 | #8 |
| 4 | Organization | `03_organization.sql` | `organization` | 4 | #33 |

**Total implemented: 15 tables (12 Foundation + 3 Organization)**

See module READMEs for per-file details:
- `ddl/01_foundation/README.md` / `seed/01_foundation/README.md`
- `ddl/02_organization/README.md` / `seed/02_organization/README.md`

## Directory Structure

```
database/
├── ddl/
│   ├── 01_foundation/    12 tables (Depths 0–4) — IMPLEMENTED
│   ├── 02_organization/  3 tables (Depths 0–4) — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
├── seed/
│   ├── 01_foundation/    reference data — IMPLEMENTED
│   ├── 02_organization/  type masters + 3 unique orgs — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
└── README.md             this file
```

## Module Implementation Status

| Module | Tables | DDL Status |
|--------|-------:|-----------|
| Foundation | 12 | IMPLEMENTED |
| Organization | 3 | IMPLEMENTED |
| Person | — | SUPERSEDED — will be rewritten |
| Membership | — | NOT YET |

## Naming Convention

- Internal UUID surrogate keys: `<entity>_pk`
- Business/external identifiers: `<entity>_code` (never `_id`)
- Foreign keys: `fk_<source_table>_<target_concept>`
- Unique constraints: `uq_<table>_<columns>`
- Check constraints: `chk_<table>_<rule>`
- Indexes: `idx_<table>_<columns>`

## Two-Pass DDL Strategy (SOL-ARCH-010 §5)

- **Pass 1:** CREATE TABLE statements (files in `ddl/`) — no audit-actor FKs
- **Pass 2:** ALTER TABLE ADD CONSTRAINT for `*_by_sangha_sevi_pk` columns —
  executed after `sangha_sevi` table exists and contains at least one record

## Superseded Artifacts

The following exist on `develop` from an earlier prototype iteration and
are NOT consistent with the frozen architecture (SOL-ARCH-009/010):

- `ddl/03_person/*` — uses per-domain masters instead of `master_data` pattern
- `seed/03_person/*` — seeds into non-existent tables (`gender_master`, etc.)
