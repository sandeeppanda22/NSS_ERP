# database/scripts/

Executable bootstrap/build/validate scripts for the raw-SQL DDL track.
Run from the repository root.

> **Getting started?** See `docs/03_Solution/architecture/GETTING_STARTED.md` for the full
> step-by-step setup sequence (database, API, tests, and database rebuild). This file is the
> detailed script reference.

## Script Reference

| File | Run as | Target DB | Purpose |
|---|---|---|---|
| `00_create_database.sql` | superuser (`postgres`) | `postgres` | Creates `nss_erp` database, `nss_db_owner`/`nss_db_backend`/`nss_db_writer` roles (all with LOGIN, NOSUPERUSER, no password), and grants `CONNECT` on `nss_erp` to `nss_db_backend` and `nss_db_writer`. Installs `dblink` (used to `CREATE DATABASE` idempotently; its internal connection string hardcodes a local-dev `postgres` superuser password — edit it for any non-local environment). Fully idempotent. |
| `01_extensions.sql` | superuser (`postgres`) | `nss_erp` | Installs `pgcrypto`, `pg_trgm`, `btree_gin`, `postgis`. Creates `nss` schema owned by `nss_db_owner`. Idempotent. |
| `06_setup_env.sh` (bash only — no `.ps1` counterpart) | superuser (`postgres`; optionally pass a different superuser name as the first arg) | `postgres` | Verifies the 3 roles exist, prompts for each role's password, runs `ALTER ROLE ... PASSWORD` on all three, and writes `api/.env` (`DB_NAME`/`DB_USER=nss_db_backend`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`, `DB_WRITE_USER`/`DB_WRITE_PASSWORD`, a random `JWT_SECRET_KEY` from `openssl rand -hex 32`, plus `JWT_ACCESS_TOKEN_MINUTES=30`/`JWT_REFRESH_TOKEN_DAYS=7`/`JWT_ABSOLUTE_SESSION_DAYS=30`). Run once after `00_create_database.sql`; if `api/.env` already exists it exits without changes unless `--force` is given. Its closing "Next steps" text points to `./database/scripts/02_build.sh`, then `python3 -m uvicorn api.main:app --reload --port 8001` from the repository root. |
| `02_build.sh` / `.ps1` | `nss_db_owner` | `nss_erp` | First runs `pip install -r requirements.txt`, then all implemented DDL + seed (Phases 0–14: Bootstrap RBAC through Audit DDL, incl. Governance Phases 11b/11c and Correspondence Phase 11d; Phase 8 is an empty placeholder), then an optional Phase 15 demo seed (see below). Idempotent re-run: in `02_build.sh`/`.ps1`, table DDL/seed is existence-gated (`run_ddl`/`run_seed` in bash, `Invoke-Ddl`/`Invoke-Seed` in PowerShell, via `to_regclass`; a pre-existing table's DDL and seed are both skipped); non-table files (triggers, grants, FKs): a file whose output contains `already exists` or `duplicate key value violates unique constraint` is reported `[SKIP]`, any other psql error aborts the build. **64 tables** created in total (see phase table below). |
| `03_validate.sh` / `.ps1` | `nss_db_owner` | `nss_erp` | Post-build checks: table existence, row counts (each is a **minimum** — `count >= expected`, below it is a `[WARN]`, not a failure), duplicate checks, FK orphan checks, key-column presence. Covers Bootstrap RBAC, Foundation (11 tables; not `post_office`/`festival_*`/`system_event_log`), Organization, Person, Authentication, Administration. Family, Membership, `system_event_log` and Governance (Module 8) get existence checks (plus a few column/FK-orphan checks for Governance) only (see "Validation coverage" below). Does not execute any DDL/seed. |
| `04_grant_backend.sql` | `nss_db_owner` | `nss_erp` | Grants `nss_db_backend` read-only access: `USAGE` on `nss` schema, `SELECT` on all tables, `ALTER DEFAULT PRIVILEGES` for future tables. Idempotent. Run as Phase 9 inside `02_build.sh`. |
| `05_create_writer_role.sql` | `nss_db_owner` | `nss_erp` | Grants `nss_db_writer` `USAGE` on the `nss` schema, `SELECT` and `INSERT`/`UPDATE` on **all** current tables in `nss` (not just auth/admin tables), and the same three via `ALTER DEFAULT PRIVILEGES` for future tables. No `DELETE`/`TRUNCATE`/`REFERENCES`/`TRIGGER`, no DDL (soft-delete only). Idempotent. Run as Phase 12 inside `02_build.sh`. |

Not in this folder but part of the same bootstrap: `scripts/bootstrap_admin.py` (Phase 13, see
`scripts/README.md`) and, for Render, `render_build.sh` (repo root — see "Render parity" below).

Build and validate scripts accept optional args:

- **bash:** `DB_NAME DB_USER DB_HOST DB_PORT` (positional, defaults: `nss_erp nss_db_owner localhost 5432`)
- **PowerShell:** `-DbName -DbUser -DbHost -DbPort` (named, same defaults)

## Build Phases (internal execution order)

The build script (`02_build.sh` / `.ps1`) executes DDL and seed files in the frozen
SOL-ARCH-011 phase order. Authority: SOL-ARCH-010 (DDL Creation Order), SOL-ARCH-011
(Bootstrap Architecture).

### Phase 0 — Bootstrap RBAC (SOL-ARCH-011 §4)

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/00_bootstrap/01_role_master.sql` | `role_master` | 0 |
| DDL | `ddl/00_bootstrap/02_permission_master.sql` | `permission_master` | 0 |
| DDL | `ddl/00_bootstrap/03_role_permission.sql` | `role_permission` | 1 |
| Seed | `seed/00_bootstrap/01_permission_master.sql` | 25 permissions (`BOOTSTRAP_VIEW`, `FOUNDATION_VIEW`/`_MANAGE`/`_CALENDAR_MANAGE`, `ORGANIZATION_VIEW`/`_MANAGE`, `PERSON_VIEW`/`_MANAGE`/`_VIEW_SENSITIVE`, `FAMILY_VIEW`/`_MANAGE`, `MEMBERSHIP_VIEW`/`_MANAGE`/`_APPROVE`, `ADMIN_USER_VIEW`/`_MANAGE`, `ADMIN_ROLE_MANAGE`, `ADMIN_SCOPE_MANAGE`, `ADMIN_PERMISSION_VIEW`, `AUDIT_VIEW`, `REPORT_VIEW`, `GOVERNANCE_VIEW`/`_MANAGE`, `CORRESPONDENCE_VIEW`/`_MANAGE`) | — |
| Seed | `seed/00_bootstrap/02_role_master.sql` | 10 frozen roles | — |
| Seed | `seed/00_bootstrap/03_role_permission.sql` | 140 role↔permission mappings (`NSS_ERP_ADMIN` 25, `NSS_ERP_KENDRA_ADMIN` 24 — `FOUNDATION_CALENDAR_MANAGE` is ADMIN-only; `NSS_ERP_SAKHA_ADMIN` 15; `ANCHALIKA`/`ZILLA`/`PATHA_CHAKRA`/`KENDRA_MAHILA_SANGHA` admins 14 each, `NSS_ERP_AUDITOR` 13, `NSS_ERP_REPORT_VIEWER` 7; `NSS_ERP_ADVISORY_BOARD_ADMIN` has no rows — it is auto-granted at runtime by `rbac_service.load_composite_grants`) | — |

### Phase 1 — Foundation DDL (14 tables, Depths 0–4)

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/01_foundation/02_master_category.sql` | `master_category` | 0 |
| DDL | `ddl/01_foundation/03_system_setting.sql` | `system_setting` | 0 |
| DDL | `ddl/01_foundation/04_id_sequence_master.sql` | `id_sequence_master` | 0 |
| DDL | `ddl/01_foundation/05_country.sql` | `country` | 0 |
| DDL | `ddl/01_foundation/06_document_master.sql` | `document_master` | 0 |
| DDL | `ddl/01_foundation/07_field_change_log.sql` | `field_change_log` | 0 |
| DDL | `ddl/01_foundation/08_master_data.sql` | `master_data` | 1 |
| DDL | `ddl/01_foundation/09_state.sql` | `state` | 1 |
| DDL | `ddl/01_foundation/10_district.sql` | `district` | 2 |
| DDL | `ddl/01_foundation/11_city_village.sql` | `city_village` | 3 |
| DDL | `ddl/01_foundation/12_postal_code.sql` | `postal_code` | 1 |
| DDL | `ddl/01_foundation/13_post_office.sql` | `post_office` | 2 |
| DDL | `ddl/01_foundation/16_festival_master.sql` | `festival_master` | 0 |
| DDL | `ddl/01_foundation/17_festival_calendar_date.sql` | `festival_calendar_date` | 1 |

### Phase 2 — Foundation Seed Data

| Step | File | Seeds |
|-----:|------|-------|
| Seed | `seed/01_foundation/01_master_category.sql` | 13 master categories (incl. ORGANIZATION_TYPE, unified STATUS, BLOOD_GROUP) |
| Seed | `seed/01_foundation/02_master_data.sql` | 89 master data rows (13 org types, 16 unified statuses, 30 relationship types incl. `SELF`, 8 blood groups, etc.) |
| Seed | `seed/01_foundation/03_id_sequence_master.sql` | 14 ID sequence definitions |
| Seed | `seed/01_foundation/04_country.sql` | 5 countries |
| Seed | `seed/01_foundation/05_state.sql` | 112 states/provinces/territories |
| Seed | `seed/01_foundation/06_district.sql` | 785 Indian districts (36 state/UT blocks, numeric LGD `district_code`) |
| Seed | `seed/01_foundation/07_system_setting.sql` | 5 system settings |
| Seed | `seed/01_foundation/08_postal_code.sql` | 3 postal codes (Bhubaneswar, Puri, Cuttack) |
| Seed | `seed/01_foundation/08b_postal_code_bulk.sql` | All-India postal_code bulk seed (17,869 PINs, one row per PIN, 36 states/UTs) |
| Seed | `seed/01_foundation/08c_post_office_bulk.sql` | All post offices per PIN into `post_office` (India Post 2025 directory) |
| Seed | `seed/01_foundation/10_festival_calendar.sql` | Festival Calendar seed (2024–2028) |
| Seed | `seed/01_foundation/11_city_village.sql` | All-India city/village bulk seed (673,408 rows: 672,619 village + 789 urban-only) |
| Seed | `seed/01_foundation/11b_city_village_urban_recovery.sql` | Additive recovery of one locality per orphan urban PIN |

`seed/01_foundation/09_sakha_postal_codes.sql` also lives in this folder but is **not** run here
— it runs in Phase 4, since it only exists to serve the Sakha branch seed.

### Phase 3 — Organization DDL (1 table + 2 triggers, Depth 1)

Organization type and status are now stored in Foundation `master_data`
(category `ORGANIZATION_TYPE` for types, unified `STATUS` for lifecycle
statuses). The standalone `organization_type_master` and
`organization_status_master` tables are retired.

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/02_organization/03_organization.sql` | `organization` | 1 |
| DDL | `ddl/02_organization/04_organization_address_restriction_trigger.sql` | *(trigger, no table — ORG-BR-099)* | — |
| DDL | `ddl/02_organization/05_organization_kumari_sevak_uniqueness_trigger.sql` | *(trigger, no table — ORG-BR-102)* | — |

### Phase 4 — Organization Seed Data

| Step | File | Seeds |
|-----:|------|-------|
| Seed | `seed/02_organization/03_organization.sql` | 3 organizations (resolves type/status via master_data) |
| Seed | `seed/01_foundation/09_sakha_postal_codes.sql` | Postal codes for the 175 Sakha branches below |
| Seed | `seed/02_organization/05_sakha_branches.sql` | 175 real Sakha Sangha branches |
| Seed | `seed/02_organization/06_id_sequence_org_sync.sql` | Advances `id_sequence_master` counters to match seeded `organization_code`s (must run after Organization DDL + seed, not in Phase 2 — see file header) |

Run order inside Phase 4 is `03_organization.sql` → `01_foundation/09_sakha_postal_codes.sql` →
`05_sakha_branches.sql` → `06_id_sequence_org_sync.sql`. (There is no `04_*` file in
`seed/02_organization/` — the former `04_tier4_verification_orgs.sql` was deleted.)

### Phase 5 — Person DDL (2 tables, Depths 2–3)

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/03_person/02_person.sql` | `person` | 2 |
| DDL | `ddl/03_person/03_person_address.sql` | `person_address` | 3 |

`ddl/03_person/01_person_master_tables.sql` is superseded — gender/marital
status/address type data now lives in Foundation `master_data` seed (Phase 2)
and is not run.

### Phase 6 — Family DDL (6 tables + 1 trigger, Depths 2–4)

| Step | File | Table |
|-----:|------|-------|
| DDL | `ddl/04_family/01_family_group.sql` | `family_group` |
| DDL | `ddl/04_family/02_family_relationship.sql` | `family_relationship` |
| DDL | `ddl/04_family/03_family_head_history.sql` | `family_head_history` |
| DDL | `ddl/04_family/04_family_transition_history.sql` | `family_transition_history` |
| DDL | `ddl/04_family/05_family_link.sql` | `family_link` |
| DDL | `ddl/04_family/06_family_admin.sql` | `family_admin` |
| DDL | `ddl/04_family/07_family_move_transition_guard.sql` | *(deferred constraint trigger on `family_relationship`, no table)* |

### Phase 7 — Membership DDL (16 tables + 1 trigger, Depths 2–4)

`sangha_sevi` is created first — all other membership tables depend on it.

| Step | File | Table |
|-----:|------|-------|
| DDL | `ddl/05_membership/01_sangha_sevi.sql` | `sangha_sevi` |
| DDL | `ddl/05_membership/02_membership_status_history.sql` | `membership_status_history` |
| DDL | `ddl/05_membership/03_membership_renewal_request.sql` | `membership_renewal_request` |
| DDL | `ddl/05_membership/04_membership_renewal_history.sql` | `membership_renewal_history` |
| DDL | `ddl/05_membership/05_membership_transfer_history.sql` | `membership_transfer_history` |
| DDL | `ddl/05_membership/06_membership_sakha_affiliation.sql` | `membership_sakha_affiliation` |
| DDL | `ddl/05_membership/07_membership_journey_event.sql` | `membership_journey_event` |
| DDL | `ddl/05_membership/08_probationary_member_review.sql` | `probationary_member_review` |
| DDL | `ddl/05_membership/09_parichaya_patra.sql` | `parichaya_patra` |
| DDL | `ddl/05_membership/10_parichaya_patra_history.sql` | `parichaya_patra_history` |
| DDL | `ddl/05_membership/11_anumati_patra.sql` | `anumati_patra` |
| DDL | `ddl/05_membership/12_anumati_patra_history.sql` | `anumati_patra_history` |
| DDL | `ddl/05_membership/13_darshak_attendance_registration.sql` | `darshak_attendance_registration` |
| DDL | `ddl/05_membership/14_sakha_only_membership_trigger.sql` | *(trigger, no table — MBR-038A)* |
| DDL | `ddl/05_membership/15_credential_sequence_counter.sql` | `credential_sequence_counter` |
| DDL | `ddl/05_membership/17_sakha_local_number_counter.sql` | `sakha_local_number_counter` (Tier 6) |
| DDL | `ddl/05_membership/18_membership_change_request.sql` | `membership_change_request` (Tier 6) |

### Phase 7b — Deferred Foundation Audit FKs

| Step | File | Purpose |
|-----:|------|---------|
| DDL | `ddl/05_membership/16_foundation_audit_fk.sql` | `ALTER TABLE` adding the real `submitted_by_`/`reviewed_by_sangha_sevi_pk` FKs on `district`, `postal_code`, `post_office`, `city_village` (plain nullable UUIDs when Foundation is created, because `sangha_sevi` depends transitively on Foundation geography) |

### Phase 8 — (reserved — no demo data)

Every Tier 4 verification/demo seed file (`seed/02_organization/04_tier4_verification_orgs.sql`,
`seed/03_person/02_tier4_verification_persons.sql`, `seed/04_family/01_tier4_verification_family.sql`
+ `02_tier4_verification_family_links.sql`, `seed/05_membership/01_tier4_verification_membership.sql`,
plus `99_extended_test_data.sql`/`99_fix_memberships.sql`) has been deleted — a fresh build seeds zero
demo Person/Family/Membership rows. Real data comes from the registration/approval flow or the
single seeded admin superuser (Phase 13). The phase number is kept (as an empty comment block in
`02_build.sh`/`.ps1`) so later phase numbers didn't shift.

### Phase 8b — Performance Indexes (no longer a separate step)

Released as v0.10.4 as `database/migrations/add_performance_indexes.sql`; `database/migrations/`
(and the short-lived `database/fixes/`) no longer exist. The 4 composite partial indexes for the
FAM-036 majority-rule CTE hot path are baked into the respective table DDL files under
`database/ddl/` (search for `family_majority`). See
`docs/03_Solution/architecture/PERFORMANCE_TUNING.md` for details.

### Phase 9 — Grant Backend Access

| Step | File | Purpose |
|-----:|------|---------|
| Grant | `04_grant_backend.sql` | Grants `nss_db_backend` read-only access. Must run after all DDL so `GRANT SELECT ON ALL TABLES` covers every table just created. |

### Phase 10 — Authentication DDL (5 tables)

The Depth column below is the per-module numbering used in the module READMEs; each SQL file's own
`-- Depth:` header comment records a value one lower for every table here (`user_account` 2,
`password_history`/`registration_claim`/`password_reset_token`/`user_session` 3) — cosmetic only, the build order
is what matters. The same applies to Phase 11 (`user_role` header says 3, `admin_scope` 4).

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/06_authentication/01_user_account.sql` | `user_account` | 3 |
| DDL | `ddl/06_authentication/02_password_history.sql` | `password_history` | 4 |
| DDL | `ddl/06_authentication/03_registration_claim.sql` | `registration_claim` | 3 |
| DDL | `ddl/06_authentication/04_password_reset_token.sql` | `password_reset_token` | 4 |
| DDL | `ddl/06_authentication/05_user_session.sql` | `user_session` | 4 |

### Phase 11 — Administration DDL (2 tables, Depths 4–5)

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/07_administration/01_user_role.sql` | `user_role` | 4 |
| DDL | `ddl/07_administration/02_admin_scope.sql` | `admin_scope` | 5 |

### Phase 11b — Governance DDL (10 tables + ballot immutability)

Unified Body Governance Model (GOV-BR-004).

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/08_governance/01_body_type_master.sql` | `body_type_master` | 0 |
| DDL | `ddl/08_governance/02_position_master.sql` | `position_master` | 0 |
| DDL | `ddl/08_governance/03_body_master.sql` | `body_master` | 4 |
| DDL | `ddl/08_governance/04_body_member_assignment.sql` | `body_member_assignment` | 5 |
| DDL | `ddl/08_governance/05_acting_position_assignment.sql` | `acting_position_assignment` | 5 |
| DDL | `ddl/08_governance/06_election.sql` | `election` | 5 |
| DDL | `ddl/08_governance/07_election_nomination.sql` | `election_nomination` | 6 |
| DDL | `ddl/08_governance/08_election_vote.sql` | `election_vote` | 6 |
| DDL | `ddl/08_governance/09_election_result.sql` | `election_result` | 6 |
| DDL | `ddl/08_governance/10_election_vote_participation.sql` | `election_vote_participation` | 6 |
| DDL | `ddl/08_governance/11_governance_immutability.sql` | *(ballot-immutability function + triggers, no table)* | — |

### Phase 11c — Governance Seed Data

Starter catalogues for the two Depth-0 masters, plus the 3 NSS-wide singleton `body_master` rows.

| Step | File | Seeds |
|-----:|------|-------|
| Seed | `seed/08_governance/01_body_type_master.sql` | 8 body types (`KENDRA_GOVERNING_BODY`, `SAKHA_GOVERNING_BODY`, `ADVISORY_BOARD`, `MAHILA_PARICHALANA_MANDALI`, `SEVAK_SANGHA_EXECUTIVE`, plus `ANCHALIKA_GOVERNING_BODY`/`ZILLA_GOVERNING_BODY`/`PATHA_CHAKRA_GOVERNING_BODY` added 2026-10-09 for the §63 composite auto-grant rule) |
| Seed | `seed/08_governance/02_position_master.sql` | 10 positions (`PRESIDENT`, `VICE_PRESIDENT`, `PARICHALAK`, `SECRETARY`, `ASSISTANT_SECRETARY`, `JOINT_SECRETARY`, `TREASURER`, `CASHIER`, `MUKHYA_PUJAKA`, `MEMBER`) |
| Seed | `seed/08_governance/03_body_master.sql` | 3 NSS-wide bodies: Kendra Governing Body, Advisory Board, central Mahila Parichalana Mandali |

Both catalogues remain caller-extensible via the Governance API (`POST`/`PATCH /body-types`,
`/positions`) for anything the starter seed doesn't cover.

### Phase 12 — Grant Writer Access

| Step | File | Purpose |
|-----:|------|---------|
| Grant | `05_create_writer_role.sql` | Grants `nss_db_writer` schema `USAGE`, `SELECT` and `INSERT`/`UPDATE` on **every** table in `nss` (current and, via default privileges, future) — the API's write routers span Family/Membership/Foundation/Organization as well as auth/admin. Never `DELETE`. Must run after Phases 10–11 so the auth/admin tables are covered by the `ALL TABLES` grant; `system_event_log` (Phase 14) is covered by the default privileges. |

### Phase 13 — Admin Bootstrap Seed

| Step | File | Seeds |
|-----:|------|-------|
| Script | `scripts/bootstrap_admin.py` (Python, not `psql`) | Reads `database/seed/04_admin/01_admin_bootstrap.sql` and executes it as **one multi-statement script in a single transaction** through `api/database.py::get_write_pool()` (needs `DB_WRITE_USER`/`DB_WRITE_PASSWORD` in `api/.env`), binding one `%(password_hash)s` parameter to a **runtime-generated Argon2 hash** (`user_account.password_hash` has no default and cannot be pre-computed into a plain seed file). Seeds `P1`/`SS1` ("NSS Admin", `REGULAR` membership, `is_system_account = TRUE`, attached to Kendra `KEN`), `user_account` (`ACTIVE`, `force_password_change = FALSE`), `password_history`, `user_role` (`NSS_ERP_ADMIN`), `admin_scope` (`NSS-WIDE`). Default login: `SS1` (or `P1`) / `Admin@123` (or `--password <pw>`) — **change this password before using outside local dev.** Every INSERT is guarded by `WHERE NOT EXISTS`; the only `UPDATE`s are the two `GREATEST(current_value, 1)` counter advances on the `PERSON`/`SANGHA_SEVI` `id_sequence_master` rows (reserving `P1`/`SS1`). Failure handling: `02_build.sh`/`.ps1` count a failure but keep going (final exit 1); `render_build.sh` only prints a `[WARN]` and continues. |

> **Note:** Phase 13 seeds only the admin account above. There are no
> `seed/06_authentication/` or `seed/07_administration/` seed files — the
> authentication and administration **tables** are created by their DDL
> (Phases 10–11); they need no seed data beyond the admin bootstrap.

### Phase 14 — Audit DDL (1 table + trigger)

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/01_foundation/14_system_event_log.sql` | `system_event_log` | — |
| DDL | `ddl/01_foundation/15_audit_trigger.sql` | *(`fn_audit_trigger()`, no table)* | — |

Must run **after** every other phase — `15_audit_trigger.sql` attaches `trg_audit_<table>`
(`AFTER INSERT OR UPDATE OR DELETE`) to every table currently in the `nss` schema, except
`system_event_log` and `field_change_log`, via a `DO $$` loop over `pg_tables`. The trigger
writes row-level events to `system_event_log` and field-level detail (one row per field, for
CREATE/UPDATE/DELETE) to `field_change_log`. Actor identity comes from the
`nss.actor_sangha_sevi_pk`/`nss.actor_user_account_pk` session variables, which the app sets on
the **write** connection in `api/dependencies/auth.py::get_write_connection()` — they must be set
on the same connection the write runs on, or the trigger sees NULL. Because this phase runs after
Phase 13, the admin-bootstrap rows and all seed data are not audited.

### Phase 15 — Demo / test seed (optional, local dev only)

| Step | File | Purpose |
|-----:|------|---------|
| Seed | `seed/demo/nss_demo_seed.sql` (gitignored) | Runs only when `RUN_DEMO_SEED` is truthy (`true`/`1`/`yes`/`on`, case/whitespace-insensitive) **and** the file exists; otherwise skipped (silently if not requested, with a warning if requested but missing). Runs after the Phase 14 audit trigger so demo rows are audited. Gives each active Sakha 10 members with credentials for exercising search/governance/election screens. Never mirrored into `render_build.sh`. |

### Tables created per phase

| Phase | Module | Tables |
|------:|--------|-------:|
| 0 | Bootstrap RBAC | 3 |
| 1 | Foundation | 14 |
| 3 | Organization | 1 |
| 5 | Person | 2 |
| 6 | Family | 6 |
| 7 | Membership | 16 |
| 10 | Authentication | 5 |
| 11 | Administration | 2 |
| 11b | Governance | 10 |
| 11d | Correspondence | 4 |
| 14 | Audit (Foundation) | 1 |
| | **Total** | **64** |

### Validation coverage (`03_validate.sh`/`.ps1`)

The two wrappers are meant to run the same checks (~156 check calls in `.sh`, ~144 in `.ps1`; the `.ps1` lacks the Governance key-column and FK-orphan checks, so the two wrappers are not fully identical; including the `city_village.district_pk`
column and its minimum district-coverage percentage). Covered: Bootstrap RBAC (3 tables), Foundation's
11 tables (not `post_office`, `festival_*`, `system_event_log`), `organization`, `person`/`person_address`, the 5 Authentication tables, and
`user_role`/`admin_scope`. The 6 `family_*` tables, the 16 Membership tables (incl.
`credential_sequence_counter`, `sakha_local_number_counter`, `membership_change_request`), `system_event_log` and all 10 Governance tables (Module 8) get **existence checks**, plus (`.sh` only) 3 Governance key-column and 3 FK-orphan checks. The 4 Correspondence tables (Tier 6) get existence, 9 key-column, 5 FK-orphan and a `reference_number` uniqueness check (no seed; the deferred `financial_transaction` FK is not checked). Row-count checks
pass when `count >= expected` and only WARN below it; the minimums track the current seed:
`role_master` 10, `master_data` 89, `id_sequence_master` 14, `system_setting` 5, `organization` 178
(after Phase 4), `person` 0, `user_account`/`user_role`/`admin_scope` 1 (the bootstrap admin). The geography minimums are current: `state` 112, `district` 780 (785 seeded),
`postal_code` 17800 (17,869 seeded), `city_village` 673000.

### Render parity

`render_build.sh` (repo root, run by `render.yaml`) repeats Phases 0–7b and 9–14 (including 11b/11c Governance and 11d Correspondence) with the same file
order and the same `[OK]`/`[SKIP]`/abort rule; its phase/file order currently matches `02_build.sh` v2.6, and it carries the same existence-gated `run_ddl`/`run_seed` model (header "Version 3.0"). `RUN_DB_BOOTSTRAP` gates only its Phase 13 admin seed, not DDL/seed.
Differences: it has no Phase 15 demo seed (`RUN_DEMO_SEED` is honoured only by `02_build.sh`/`.ps1`); it builds Tailwind and installs Python deps first; it substitutes for
`00_create_database.sql`/`01_extensions.sql` by running `CREATE SCHEMA IF NOT EXISTS nss`,
`ALTER DATABASE ... SET search_path`, and best-effort `pgcrypto`/`pg_trgm`/`btree_gin` (no
`postgis`); it creates the three `nss_db_*` roles inline (reusing `DB_PASSWORD`, or
`DB_WRITE_PASSWORD` for the writer) just before Phase 9; and a Phase 13 failure is non-fatal.

### Not executed (future phases)

- Pass 2 audit-actor FK constraints (`*_by_sangha_sevi_pk` — still deferred, including on every
  Tier 5 table)
- MFA enforcement (Tier 5.1) — self-reset OTP (forgot-password) and permission-gating on
  Tier 1–4 endpoints are both already implemented, not future work
- All remaining modules (Attendance, etc.) — Governance (Phase 11b/11c, 10 tables) and Correspondence (Phase 11d, 4 tables) is now
  implemented and wired into the build; it is no longer future work

## Role Naming Convention

| Pattern | Layer | Examples |
|---|---|---|
| `nss_db_*` | PostgreSQL infrastructure | `nss_db_owner`, `nss_db_backend`, `nss_db_writer` |
| `NSS_ERP_*` | Application RBAC (`role_master`) | `NSS_ERP_ADMIN`, `NSS_ERP_KENDRA_ADMIN` |

## Cross-Platform Principle (Frozen)

The SQL DDL, seed data, and application code are **identical across platforms**. `.sh`
(macOS/Linux) and `.ps1` (Windows) scripts are developer/operational wrappers only — they
must not contain different business logic, database statements, or schema definitions.
Platform-specific behaviour is limited to shell mechanics (variable substitution, exit
codes, colour output). Both wrappers execute the same DDL and seed files in the same order.

## Starting the API

See `docs/03_Solution/architecture/GETTING_STARTED.md` → Sections 3–5 for API setup, startup, and testing.
