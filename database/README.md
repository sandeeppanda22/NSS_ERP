# database/

Hand-written PostgreSQL DDL and seed data — the schema authority for the NSS ERP.

**DDL Execution Authority:** PostgreSQL role `nss_db_owner`
**Runtime Read:** PostgreSQL role `nss_db_backend` (read-only `SELECT`)
**Runtime Write:** PostgreSQL role `nss_db_writer` (`SELECT` + `INSERT`/`UPDATE` on every `nss.*`
table, no `DELETE`/DDL — Tier 5, see `scripts/05_create_writer_role.sql`)
**Architecture Authority:** SOL-ARCH-010 (DDL Creation Order),
SOL-ARCH-011 (Bootstrap Architecture), module table-design documents

> **Note:** PostgreSQL `nss_db_owner` is the *database-level* role that owns
> tables and executes DDL/seed scripts. It is **not** the ERP application
> role `NSS_ERP_ADMIN` (which is an RBAC role defined in `role_master` and
> enforced by the application layer). See SOL-ARCH-011 §7.2 for the
> full identity distinction.

> **Tier 5 (Authentication + Administration) is released in v0.11.0** (merged to `develop`/`main`). Relative to the last released schema (v0.10.4) it adds `ddl/06_authentication/` (5 tables),
> `ddl/07_administration/` (2 tables), `family_admin` (Family), `darshak_attendance_registration`
> and `credential_sequence_counter` (Membership), and `system_event_log` (Foundation, with
> `fn_audit_trigger()` attached to every other `nss.*` table) — **11 new tables**, plus
> `post_office`, `festival_master`, `festival_calendar_date` (Foundation; all-India geography and
> member-assisted geographic entry) — **14 new tables, 48 in total**; the
> `nss_db_writer` role (`scripts/05_create_writer_role.sql`) and `scripts/06_setup_env.sh`; the
> top-level `scripts/bootstrap_admin.py` + `seed/04_admin/`; and several new triggers
> (Organization address restriction + Kumari/Sevak one-per-Sakha, Family move-transition guard,
> Membership Sakha-only). It also **removes every Tier 4 "verification"/demo seed file**,
> `database/migrations/` and `database/fixes/` entirely (neither folder exists any more; the
> FAM-036 performance indexes now live in the table DDL itself). See `database/seed/README.md`,
> `database/scripts/README.md`, and `docs/PROJECT_DOCUMENTATION.md` → Architecture ("Tier 5").

> **Tier 6 (Governance) is in progress — uncommitted on `feature/tier6-governance`.** It adds
> `ddl/08_governance/` (10 tables + `11_governance_immutability.sql` ballot-immutability triggers,
> build Phases 11b/11c with `seed/08_governance/`: 8 body types, 10 positions, 3 NSS-wide bodies),
> two Membership tables (`sakha_local_number_counter`, `membership_change_request`; Phase 7 is now
> 16 tables), `13_darshak_attendance_registration.sql` v1.1 (`initiated_by_sangha_sevi_pk` +
> `request_source`), `02_admin_scope.sql` v1.1 / `role_master` (`ADVISORY_BOARD` scope level), a
> 10th role (`NSS_ERP_ADVISORY_BOARD_ADMIN`, granted at runtime — no `role_permission` rows) and two
> permissions (`GOVERNANCE_VIEW`/`GOVERNANCE_MANAGE`) — **12 new tables, 60 in total**, plus an
> optional local-only demo seed (Phase 15, `RUN_DEMO_SEED`, `seed/demo/`, not in `render_build.sh`).

---

## Execution Order

### Full Build (from scratch)

The build follows the bootstrap sequence defined in SOL-ARCH-011. Prerequisites (superuser)
must complete before the `nss_db_owner` phases. Full walkthrough: `scripts/README.md` and
`docs/03_Solution/architecture/GETTING_STARTED.md`.

```bash
# Prerequisites (PostgreSQL superuser)
psql -U postgres -d postgres -f database/scripts/00_create_database.sql   # DB + 3 roles
psql -U postgres -d nss_erp  -f database/scripts/01_extensions.sql        # extensions + nss schema
./database/scripts/06_setup_env.sh      # sets passwords on all 3 roles, writes api/.env (+ JWT secret)

# Build (as nss_db_owner) — runs pip install, then Phases 0-14 (plus the optional Phase 15 demo seed when `RUN_DEMO_SEED` is set), and calls
# scripts/bootstrap_admin.py as Phase 13 (seeds admin SS1 / Admin@123)
./database/scripts/02_build.sh          # Windows: database\scripts\02_build.ps1
./database/scripts/03_validate.sh       # optional post-build checks (see its known gaps below)

# Run the API from the repository root
python3 -m uvicorn api.main:app --reload --port 8001
```

`02_build.sh` already runs `04_grant_backend.sql` (Phase 9) and `05_create_writer_role.sql`
(Phase 12); running them by hand is only needed if you skip the build script. The API needs
`api/.env` with `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`, plus
`DB_WRITE_USER`/`DB_WRITE_PASSWORD`/`JWT_SECRET_KEY` for Tier 5 endpoints — `06_setup_env.sh`
generates all of them.

Build phases (authoritative detail in `scripts/README.md`):

| Phase | Content |
|------:|---------|
| 0 | Bootstrap RBAC — 3 tables + seed (10 roles, 25 permissions, 140 mappings) |
| 1 | Foundation DDL — 14 tables (incl. `post_office`, `festival_master`/`festival_calendar_date`) |
| 2 | Foundation seed (incl. all-India PINs, post offices, ~673k `city_village` rows, festival calendar) |
| 3 | Organization DDL — 1 table + 2 triggers |
| 4 | Organization seed — 3 unique orgs, 56 Sakha PINs, 175 Sakha branches, counter sync |
| 5 | Person DDL — 2 tables |
| 6 | Family DDL — 6 tables + move-transition guard trigger |
| 7 | Membership DDL — 16 tables + Sakha-only trigger |
| 7b | Foundation audit FKs (`05_membership/16_foundation_audit_fk.sql`) |
| 8 | (reserved — demo seeds removed) |
| 9 | Grant `nss_db_backend` read-only |
| 10 | Authentication DDL — 5 tables |
| 11 | Administration DDL — 2 tables |
| 11b | Governance DDL — 10 tables + ballot-immutability triggers (`08_governance/`) |
| 11c | Governance seed — body types, positions, 3 NSS-wide bodies |
| 11d | Correspondence DDL — 4 tables (`09_correspondence/`) |
| 12 | Grant `nss_db_writer` |
| 13 | Admin bootstrap (`scripts/bootstrap_admin.py`) |
| 14 | Audit DDL — `system_event_log` + `fn_audit_trigger()` attached to every table |
| 15 | (optional, local dev) demo seed via `RUN_DEMO_SEED` — `seed/demo/nss_demo_seed.sql`, gitignored, not in `render_build.sh` |

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
| 1 | Foundation | `12_postal_code.sql` | `postal_code` | 1 | #87 |
| 1 | Foundation | `13_post_office.sql` | `post_office` | 2 | — |
| 1 | Foundation | `11_city_village.sql` | `city_village` | 3 | #32 |
| 1 | Foundation | `16_festival_master.sql` / `17_festival_calendar_date.sql` | `festival_master`, `festival_calendar_date` | 0 / 1 | — |
| 3 | Organization | `03_organization.sql` | `organization` | 1 | #33 |

The Organization row above covers Phase 3's single table; the remaining modules' per-file
Depth/Seq# breakdown lives in their own module READMEs rather than being duplicated here:
- `ddl/02_organization/README.md` (1 table + 2 triggers)
- `ddl/03_person/README.md` (2 tables: `person`, `person_address`)
- `ddl/04_family/README.md` (6 tables: `family_group`, `family_relationship`,
  `family_head_history`, `family_transition_history`, `family_link`, `family_admin`, plus the
  move-transition guard trigger)
- `ddl/05_membership/README.md` (16 tables, `sangha_sevi` first, plus the Sakha-only trigger)
- `ddl/06_authentication/README.md` (5 tables) and `ddl/07_administration/README.md` (2 tables) —
  Tier 5
- `ddl/08_governance/README.md` (10 tables + immutability triggers) — Tier 6
- `ddl/09_correspondence/README.md` (4 tables, Correspondence Register) — Tier 6
- `ddl/01_foundation/README.md` also documents
  `festival_master`/`festival_calendar_date`, and Phase 14's
  `system_event_log` (15th Foundation table) and `fn_audit_trigger()`

**Total implemented: 64 tables** — 3 Bootstrap RBAC + 15 Foundation (12 reference/geography + 2 festival + `system_event_log`) +
1 Organization + 2 Person + 6 Family + 16 Membership + 5 Authentication + 2 Administration + 10 Governance + 4 Correspondence
(verified by counting `CREATE TABLE` across `database/ddl/**`). Of those, 11 are Tier 5 additions
(see the banner above), 3 more Foundation tables arrived on the same branch, and 16 are Tier 6 (10 Governance + 4 Correspondence + 2 Membership); the v0.10.4
baseline was 34.
**Organization type/status moved to Foundation `master_data` — standalone tables retired.**
**Phase 0 seed complete:** `role_master` (10 roles), `permission_master` (25), `role_permission`
(140) are all populated, so `require_permission(...)` checks succeed for roles with mappings.

See module READMEs for per-file details:
- `ddl/00_bootstrap/README.md` / `seed/00_bootstrap/README.md`
- `ddl/01_foundation/README.md` / `seed/01_foundation/README.md`
- `ddl/02_organization/README.md` / `seed/02_organization/README.md`
- `ddl/03_person/README.md` / `seed/03_person/README.md`
- `ddl/04_family/README.md` / `seed/04_family/README.md`
- `ddl/05_membership/README.md` / `seed/05_membership/README.md`
- `ddl/06_authentication/README.md`, `ddl/07_administration/README.md` (no seed folders of their
  own — see `seed/04_admin/README.md`)

---

## Two-Pass DDL Strategy (SOL-ARCH-010 §5, SOL-ARCH-011 §6)

- **Pass 1:** CREATE TABLE statements (files in `ddl/`) — no audit-actor FKs
- **Pass 2:** ALTER TABLE ADD CONSTRAINT for `*_by_sangha_sevi_pk` columns —
  executed after `sangha_sevi` table exists and contains at least one record

Pass 2 is not yet implemented. `sangha_sevi` (Membership DDL, Phase 7) exists, and
`scripts/bootstrap_admin.py` (Phase 13, Tier 5) seeds the bootstrap administrator
`SS1` — but no `ALTER TABLE ADD CONSTRAINT` step for the `*_by_sangha_sevi_pk` columns has been
added to the build scripts, including for the Tier 5 tables themselves (`user_account`,
`user_role`, `admin_scope`, etc. all carry the same nullable, unconstrained audit-actor columns)
— Pass 2 remains deferred.

---

## Directory Structure

```
database/
├── scripts/
│   ├── 00_create_database.sql    Create DB + 3 roles + dblink (superuser, postgres DB)
│   ├── 01_extensions.sql         Install extensions + nss schema (superuser, nss_erp DB)
│   ├── 02_build.sh / .ps1        Full schema build (Phases 0-14, optional 15)
│   ├── 03_validate.sh / .ps1     Post-build validation (partial coverage — see below)
│   ├── 04_grant_backend.sql      Grant nss_db_backend read-only access to nss schema
│   ├── 05_create_writer_role.sql Grant nss_db_writer SELECT + INSERT/UPDATE (no DELETE) on nss.*
│   └── 06_setup_env.sh           Set role passwords + generate api/.env (bash only)
├── ddl/
│   ├── 00_bootstrap/     3 RBAC tables (Depths 0-1)
│   ├── 01_foundation/    15 tables: 14 reference/runtime tables (files 02-13, 16-17, Depths 0-3) +
│   │                     `14_system_event_log.sql` (audit trail, Tier 5); `15_audit_trigger.sql`
│   │                     (`fn_audit_trigger()` attached to every other `nss.*` table) creates
│   │                     no table. (No `01_*` file — extensions moved to scripts/01_extensions.sql)
│   ├── 02_organization/  1 table (`organization`) + 2 triggers (files 03-05; no 01/02 —
│   │                     type/status masters retired)
│   ├── 03_person/        2 tables (`person`, `person_address`); the superseded
│   │                     `01_person_master_tables.sql` stub has been deleted
│   ├── 04_family/        6 tables (incl. `family_admin`) + `07_family_move_transition_guard.sql`
│   ├── 05_membership/    16 tables (`sangha_sevi` first; incl. `darshak_attendance_registration`,
│   │                     `credential_sequence_counter`, `sakha_local_number_counter`, `membership_change_request`) + `14_sakha_only_membership_trigger.sql`, `16_foundation_audit_fk.sql` (ALTER only)
│   ├── 06_authentication/ 5 tables: user_account, password_history, registration_claim,
│   │                     password_reset_token, user_session (Tier 5)
│   ├── 07_administration/ 2 tables: user_role, admin_scope (Tier 5)
│   └── 08_governance/    10 tables (bodies, assignments, elections, ballots) + `11_governance_immutability.sql` (Tier 6)
├── seed/
│   ├── 00_bootstrap/     10 roles, 25 permissions, 140 role-permission mappings
│   ├── 01_foundation/    reference + bulk geography data (files 01-11b; `09_sakha_postal_codes.sql` runs in Phase 4)
│   ├── 02_organization/  3 unique orgs + 175 real Sakha branches + org-code counter sync
│   ├── 03_person/        no seed data (README only)
│   ├── 04_admin/         one admin superuser, via scripts/bootstrap_admin.py (not plain psql)
│   ├── 04_family/        no seed data (README only)
│   ├── 05_membership/    no seed data (README only)
│   ├── 08_governance/    8 body types, 10 positions, 3 NSS-wide bodies (Tier 6)
│   └── demo/             optional local-only demo seed (gitignored; RUN_DEMO_SEED)
│                         (no seed folders for 06_authentication/07_administration)
└── README.md             this file
```

(`04_admin` and `04_family` are two distinct seed folders that happen to share the `04_` prefix:
`04_family` mirrors `ddl/04_family/` and is empty, while `04_admin` is a Tier 5 addition with no
DDL-folder counterpart. Only `04_admin` contains SQL that `02_build.sh` runs.)
There is no `database/migrations/` or `database/fixes/` folder.

---

## Module Implementation Status

| Module | Tables | DDL Status | Next Action |
|--------|-------:|-----------|-------------|
| Bootstrap RBAC | 3 | ✅ IMPLEMENTED, seeded (10 roles / 25 permissions / 140 mappings) | — |
| Foundation | 15 | ✅ IMPLEMENTED (12 original/geography incl. `post_office`, 2 festival tables, + `system_event_log`) | — |
| Organization | 1 | ✅ IMPLEMENTED (+ 2 triggers) | — |
| Person | 2 | ✅ IMPLEMENTED | — |
| Family | 6 | ✅ IMPLEMENTED (`family_admin` Tier 5; + move-transition guard trigger) | — |
| Membership | 16 | ✅ IMPLEMENTED (`darshak_attendance_registration`, `credential_sequence_counter` Tier 5; `sakha_local_number_counter`, `membership_change_request` Tier 6; + Sakha-only trigger) | — |
| Authentication | 5 | ✅ Tier 5, released in v0.11.0 | — |
| Administration | 2 (`user_role`/`admin_scope`; the 3 RBAC definition tables live in Bootstrap) | ✅ Tier 5, released in v0.11.0 | — |
| Governance | 10 | 🚧 Tier 6, in progress (uncommitted on `feature/tier6-governance`) | Verify, commit, merge to `develop` |
| Heritage | 4 | ⬜ NOT YET | — |

Table counts for the implemented modules above are the actual counts of tables created by their
DDL files (total 60). Family (6) and Membership (16) exceed the frozen SOL-ARCH-010 inventory
figures used in earlier planning (3 and 9 respectively) — the implemented slice grew during
design; this is a known SOL-ARCH-010 inventory drift to reconcile in a future governance pass,
not a build error. Modules not listed above have frozen table counts but are further down the
implementation tier order (SOL-ARCH-008).

---

## Naming Convention

- Internal UUID surrogate keys: `<entity>_pk`
- Business/external identifiers: `<entity>_id` for entity identifiers (`person_id`, `organization_id`, `family_group_id`/`family_id`, `sangha_sevi_id`) and `<entity>_code` for Foundation/reference-data codes (`category_code`, `value_code`, `organization_code`); values are unpadded sequence values (`P1`, `SS1`, `SKH1`, `F1`)
- Foreign keys: `fk_<source_table>_<target_concept>`
- Unique constraints: `uq_<table>_<columns>`
- Check constraints: `chk_<table>_<rule>`
- Indexes: `idx_<table>_<columns>`

---

## Scripts

All executable scripts live in `database/scripts/`. Run from the
repository root. `02_build.sh` and `03_validate.sh` (and their `.ps1` twins) accept optional
positional parameters:

```
DB_NAME  (default: nss_erp)
DB_USER  (default: nss_db_owner)
DB_HOST  (default: localhost)
DB_PORT  (default: 5432)
```

### 00_create_database.sql — Database and Role Setup

Run **once** by a PostgreSQL **superuser** (e.g. `postgres`) against the `postgres` database.
Installs `dblink` (for idempotent database creation), creates the `nss_db_owner`, `nss_db_backend`
and `nss_db_writer` roles (LOGIN, NOSUPERUSER, no password), creates the `nss_erp` database owned
by `nss_db_owner`, and grants `CONNECT` on it to `nss_db_backend` and `nss_db_writer`.
Fully idempotent — safe to re-run.

```bash
psql -U postgres -d postgres -f database/scripts/00_create_database.sql
```

**Important:** this creates PostgreSQL-level roles only — set passwords via
`database/scripts/06_setup_env.sh` (which also writes `api/.env`) or manually with
`ALTER ROLE ... PASSWORD '...'`. The ERP application role `NSS_ERP_ADMIN` is a row in
`role_master` (Phase 0 seed) and a separate security boundary (SOL-ARCH-011 §7.2).
`nss_db_owner` is intentionally not a SUPERUSER. The script's internal `dblink_exec` call
hardcodes a local-dev placeholder password for the `postgres` superuser connection it opens back
to itself — change it before running against a shared/non-local environment.

### 01_extensions.sql — PostgreSQL Extensions and `nss` Schema

Run by a PostgreSQL **superuser** against the `nss_erp` database, after
`00_create_database.sql`. Installs the extensions, creates the `nss` schema owned by
`nss_db_owner`, and sets `search_path` to `nss, public` on the database. Idempotent.

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

Runs `pip install -r requirements.txt`, then executes all DDL and seed scripts for the
implemented modules in SOL-ARCH-011 phase order, as `nss_db_owner` (see the phase table under
"Full Build" above and `scripts/README.md` for per-file detail).

```bash
./database/scripts/02_build.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
```

**Not executed:** Pass 2 audit-actor FK constraints (deferred — see
Two-Pass DDL Strategy above).

Table DDL and seeds are **existence-gated** (`run_ddl`/`run_seed`, deterministic
`to_regclass('nss.<table>')` check; `[EXISTS]`/`[SKIP]` for a table already present — its DDL **and**
seed are skipped, so edited seed rows or altered DDL on an existing table need a full rebuild). All
of `02_build.sh`, `02_build.ps1` (`Invoke-Ddl`/`Invoke-Seed`) and `render_build.sh` have this gate;
the error-text rule below remains the fallback for non-table files. Non-table objects (triggers, functions, grants, FKs) still go through `run_sql`.

Error handling: `set -euo pipefail` and psql `ON_ERROR_STOP=1`. A file whose output contains
`already exists` or `duplicate key value violates unique constraint` is reported `[SKIP]` and the
build continues, so **re-running against an existing database is supported** (idempotent); any
other error aborts immediately. (Phase 13, the admin bootstrap, is the exception — a failure is
counted, the build continues, and the final exit code is 1.) `render_build.sh` at the repository
root mirrors this sequence for Render/Neon (`RUN_DB_BOOTSTRAP` — `true`/`1`/`yes`/`on`, case/whitespace-insensitive; default off — gates only the Phase 13 admin seed) — keep the two in sync.

### 03_validate.sh — Post-Build Validation

Validates the build. **Does NOT execute any DDL or seed scripts** — run `02_build.sh` first.

```bash
./database/scripts/03_validate.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
```

| Module | Checks |
|--------|--------|
| Bootstrap RBAC (3 tables) | Existence, `role_master` row minimum, unique `role_code`, `role_permission` FK integrity |
| Foundation (11 tables; not `post_office`/`festival_*`/`system_event_log`) | Existence, row minimums, unique codes, FK integrity, deferred `document_master` columns |
| Organization (1 table) | Existence, row minimum, unique `organization_code`, FK integrity |
| Person (2 tables) | Existence, FK integrity, address FK columns |
| Authentication (5 tables) | Existence, `user_account`/`password_history` key columns, unique `person_pk`, FK integrity |
| Administration (2 tables) | Existence, key columns, FK integrity |

| Family (6), Membership (16, incl. `credential_sequence_counter`, `sakha_local_number_counter`, `membership_change_request`), `system_event_log` | Existence only (no seed data, no key-column or FK checks) |
| Governance (10 tables, Module 8) | Existence for all 10, plus 3 key columns and 3 FK-orphan checks in the `.sh` only (the `.ps1` has the table checks but not the key-column/FK checks); no seed minimums |
| Correspondence (4 tables: `correspondence`, `correspondence_document`, `correspondence_finance_reference`, `correspondence_sequence_counter`) | Existence, 9 key columns, 5 FK-orphan checks, unique `correspondence.reference_number` (no seed). The `correspondence_finance_reference` -> `financial_transaction` FK is deliberately not checked (Finance not built) |

Row-count checks assert `count >= expected` and only WARN when lower; the minimums track the
current seed (`role_master` 10, 89 master_data, 14 sequences, 5 settings, 178 organizations; `person` 0).
Geography minimums: `state` 112, `district` 780, `postal_code` 17800, `city_village` 673000. The
`.sh` and `.ps1` versions run ~156 check calls in `.sh` vs ~144 in `.ps1` (the gap is the 3 Governance key-column and 3 FK checks missing from the `.ps1`, plus minor differences), including `city_village.district_pk` existence and minimum coverage (Simplified Geography Model).

**Extend this script when new modules are added to `02_build.sh`.**

### 04_grant_backend.sql / 05_create_writer_role.sql / 06_setup_env.sh

- `04_grant_backend.sql` (Phase 9): `USAGE` on `nss` + `SELECT` on all tables (and future tables via
  `ALTER DEFAULT PRIVILEGES`) for `nss_db_backend`.
- `05_create_writer_role.sql` (Phase 12): `USAGE`, `SELECT`, and `INSERT`/`UPDATE` (current and
  future tables) on the whole `nss` schema for `nss_db_writer` — **not** limited to auth/admin
  tables; no `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, or DDL.
- `06_setup_env.sh` (superuser, bash only): sets passwords on the 3 roles and writes `api/.env`
  including a random `JWT_SECRET_KEY`.

---

## Superseded Artifacts

`ddl/03_person/01_person_master_tables.sql` and `seed/03_person/01_person_master_tables.sql` were
deleted (2026-10-01; dead code, zero references) — gender/marital_status/address_type live in
Foundation `master_data`. Likewise the Foundation `city_village_postal_code_map` junction table.
