# database/

Hand-written PostgreSQL DDL and seed data — the schema authority for the NSS ERP.

**Owner:** NSS_ADMIN (table creation and seed insertion)
**Runtime:** NSS_APP (application read/write)
**Authority:** SOL-ARCH-010 (DDL Creation Order), module table-design documents

## Execution Order

### Full Foundation Build (from scratch)

```bash
# 1. Extensions
psql -U nss_admin -d nss_erp -f database/ddl/01_foundation/01_extensions.sql

# 2. Foundation DDL (Depths 0–4, 12 tables)
for f in database/ddl/01_foundation/0[2-9]*.sql database/ddl/01_foundation/1*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done

# 3. Foundation Seed Data
for f in database/seed/01_foundation/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done
```

See `ddl/01_foundation/README.md` and `seed/01_foundation/README.md` for
detailed per-file execution tables.

## Directory Structure

```
database/
├── ddl/
│   ├── 01_foundation/    12 tables (Depths 0–4) — IMPLEMENTED
│   ├── 02_organization/  placeholder (Depth 3) — NOT YET IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
├── seed/
│   ├── 01_foundation/    reference data — IMPLEMENTED
│   └── 03_person/        superseded prototype — WILL BE REPLACED
└── README.md             this file
```

## Module Implementation Status

| Module | DDL Status | Branch |
|--------|-----------|--------|
| Foundation (12 tables) | IMPLEMENTED | `feature/database-foundation` |
| Organization | NOT YET | `feature/database-foundation` (future) |
| Person | SUPERSEDED — will be rewritten | `feature/person-ddl` (future) |
| Membership | NOT YET | `feature/membership-design` (future) |

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

- `ddl/01_foundation/02_id_sequence_master.sql` (old) → replaced by `04_id_sequence_master.sql`
- `ddl/01_foundation/03_location_master_tables.sql` (old) → replaced by `05–11_*.sql`
- `ddl/02_organization/*` — 0-byte placeholders
- `ddl/03_person/*` — uses per-domain masters instead of `master_data` pattern
- `seed/01_foundation/*` (old) → replaced by new numbered seeds
- `seed/03_person/*` — seeds into non-existent tables (`gender_master`, etc.)
