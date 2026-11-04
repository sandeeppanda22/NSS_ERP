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
| `02_build.sh` / `.ps1` | `nss_db_owner` | `nss_erp` | First runs `pip install -r requirements.txt`, then all implemented DDL + seed (Phases 0–14: Bootstrap RBAC through Audit DDL, incl. Governance Phases 11b/11c, Correspondence Phase 11d, Attendance Phase 11e, Organization re-parent approval Phase 11f, Assets & Property Phase 11g and Live refresh Phase 11h; Phase 8 is an empty placeholder), then an optional Phase 15 demo seed (see below). Idempotent re-run: in `02_build.sh`/`.ps1`, table DDL/seed is existence-gated (`run_ddl`/`run_seed` in bash, `Invoke-Ddl`/`Invoke-Seed` in PowerShell, via `to_regclass`; a pre-existing table's DDL and seed are both skipped); non-table files (triggers, grants, FKs): a file whose output contains `already exists` or `duplicate key value violates unique constraint` is reported `[SKIP]`, any other psql error aborts the build. **79 tables** created in total (see phase table below). Also runs ~12 **idempotent patch files** on every build via `run_sql`/`Invoke-Sql` (not existence-gated; marked `Patch`/`run_sql` in the phase tables) — they carry changes to already-existing tables/seeds to databases built before the change, which is why an existing DB needs only a re-run of `02_build`, not a rebuild, for those changes. |
| `03_validate.sh` / `.ps1` | `nss_db_owner` | `nss_erp` | Post-build checks: table existence, row counts (each is a **minimum** — `count >= expected`, below it is a `[WARN]`, not a failure), duplicate checks, FK orphan checks, key-column presence. Covers every one of the 79 tables (existence), row minimums for the seeded tables, FK-orphan checks, key columns, and the objects delivered by the idempotent patches (see "Validation coverage" below). The `.sh` and `.ps1` run the same checks (verified check-by-check, 2026-11-01). Does not execute any DDL/seed. |
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
| Seed | `seed/00_bootstrap/01_permission_master.sql` | 28 permissions (`BOOTSTRAP_VIEW`, `FOUNDATION_VIEW`/`_MANAGE`/`_CALENDAR_MANAGE`, `ORGANIZATION_VIEW`/`_MANAGE`, `PERSON_VIEW`/`_MANAGE`/`_VIEW_SENSITIVE`, `FAMILY_VIEW`/`_MANAGE`, `MEMBERSHIP_VIEW`/`_MANAGE`/`_APPROVE`, `ADMIN_USER_VIEW`/`_MANAGE`, `ADMIN_ROLE_MANAGE`, `ADMIN_SCOPE_MANAGE`, `ADMIN_PERMISSION_VIEW`, `AUDIT_VIEW`, `REPORT_VIEW`, `GOVERNANCE_VIEW`/`_MANAGE`, `CORRESPONDENCE_VIEW`/`_MANAGE`) | — |
| Seed | `seed/00_bootstrap/02_role_master.sql` | 11 frozen roles | — |
| Seed | `seed/00_bootstrap/03_role_permission.sql` | 166 role↔permission mappings (`NSS_ERP_ADMIN` 27, `NSS_ERP_KENDRA_ADMIN` 26 — `FOUNDATION_CALENDAR_MANAGE` is ADMIN-only; `NSS_ERP_SAKHA_ADMIN` 18; `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` 18; `ANCHALIKA`/`ZILLA`/`PATHA_CHAKRA` admins 15 each, `NSS_ERP_AUDITOR` 14, `NSS_ERP_REPORT_VIEWER` 8, `NSS_ERP_ATTENDANCE_MARKER` 2; `NSS_ERP_ADVISORY_BOARD_ADMIN` 8) | — |
| Patch | `seed/00_bootstrap/04_role_permission_mahila_advisory_board_patch.sql` | idempotent `run_sql` after the seed above (the seed is existence-gated): Mahila admin +3, Advisory Board admin 8 rows | — |
| Patch | `seed/00_bootstrap/05_assets_property_permissions_patch.sql` | idempotent `run_sql` right after `04` (Assets & Property, GDR-010): `ASSET_VIEW`/`ASSET_MANAGE` + 12 grants (28 → 30 permissions, 166 → 178 mappings) | — |
| Patch | `seed/00_bootstrap/06_assets_property_permissions_revoke_patch.sql` | idempotent `run_sql` right after `05` (owner decisions 2026-11-02): soft-deletes (`is_active = FALSE`) the 4 grants an earlier `05` created (Mahila VIEW+MANAGE, Anchalika/Zilla MANAGE); no-op on fresh builds | — |
| Patch | `ddl/11_assets_property/11_assets_property_acquisition_method_patch.sql` | idempotent `run_sql` after `10` (GDR-010 §2E): nullable `acquisition_method_master_data_pk` + FK + partial index on `property` and `asset` for databases built before the column existed | — |
| Patch | `ddl/11_assets_property/12_assets_property_terminal_custody_patch.sql` | idempotent `run_sql` AFTER `seed/11_assets_property/01_…reference_data_patch.sql` (needs its `DISPOSED`/`RETIRED` end reasons; GDR-010 §2F): ENDs the still-ACTIVE custodianship of already DISPOSED properties / RETIRED assets; no-op on fresh builds | — |
| Patch | `ddl/11_assets_property/10_assets_property_belongs_to_patch.sql` | idempotent `run_sql` after `09` (GDR-010 §2D): nullable `belongs_to_organization_pk` + FK + index on `property` and `asset` for databases built before the column existed | — |

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
| Seed | `seed/01_foundation/01_master_category.sql` | 19 master categories (incl. ORGANIZATION_TYPE, unified STATUS, BLOOD_GROUP, the two CORRESPONDENCE_* and three ATTENDANCE_* categories) |
| Seed | `seed/01_foundation/02_master_data.sql` | 118 master data rows (14 org types incl. the singleton `ADVISORY_BOARD`, 16 unified statuses, 30 relationship types incl. `SELF`, 8 blood groups, etc.) |
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

### Phase 3 — Organization DDL (1 table + 3 triggers + 1 function, Depth 1)

Organization type and status are now stored in Foundation `master_data`
(category `ORGANIZATION_TYPE` for types, unified `STATUS` for lifecycle
statuses). The standalone `organization_type_master` and
`organization_status_master` tables are retired.

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/02_organization/03_organization.sql` | `organization` | 1 |
| DDL | `ddl/02_organization/04_organization_address_restriction_trigger.sql` | *(trigger, no table — ORG-BR-099)* | — |
| DDL | `ddl/02_organization/05_organization_kumari_sevak_uniqueness_trigger.sql` | *(trigger, no table — ORG-BR-102)* | — |
| DDL | `ddl/02_organization/08_organization_singleton_trigger.sql` | *(trigger `fn_enforce_organization_singleton`, no table — ORG-BR-108; `run_sql`, idempotent; drops the v1.0 `fn_enforce_advisory_board_singleton`)* | — |
| DDL | `ddl/02_organization/10_sakha_like_org_type_function.sql` | *(function `fn_is_sakha_like_org_type` — single SQL definition of SAKHA_SANGHA + SAKHA_ASANA; `run_sql`, idempotent; must precede the Phase 7 membership triggers and the Phase 11b Advisory Board seat trigger that call it)* | — |

**Singleton organizations (owner 2026-10-30).** The trigger refuses a second ACTIVE organization for each
of: type `KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`, `ADVISORY_BOARD`, and the central Mahila Sangha
(`MAHILA_SANGHA` whose parent is a `KENDRA`; local per-Sakha Mahila Sanghas are unrestricted). Creating the
trigger never scans existing rows, so a build on a database that already holds a duplicate does not fail —
only NEW offending writes are blocked. **Run this before the next build** to see what the live data holds
(read-only; every `active_rows` must be 1, or the rule is absent):

```sql
SELECT r.rule, COUNT(*) AS active_rows
FROM (
    SELECT md.value_code AS rule
    FROM nss.organization o
    JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
    WHERE o.is_active = TRUE
      AND md.value_code IN ('KENDRA', 'NILACHALA_KUTIRA', 'SMRUTI_MANDIRA', 'ADVISORY_BOARD')
    UNION ALL
    SELECT 'CENTRAL_MAHILA_SANGHA'
    FROM nss.organization o
    JOIN nss.master_data md  ON md.master_data_pk  = o.organization_type_master_data_pk
    JOIN nss.organization p  ON p.organization_pk  = o.parent_organization_pk
    JOIN nss.master_data pmd ON pmd.master_data_pk = p.organization_type_master_data_pk
    WHERE o.is_active = TRUE AND md.value_code = 'MAHILA_SANGHA' AND pmd.value_code = 'KENDRA'
) r
GROUP BY r.rule
ORDER BY r.rule;
```

`03_validate.sh`/`.ps1` run the same query as a single check (sum of `active_rows - 1` over the rules; any
duplicate FAILs it) plus a trigger-present check.

### Phase 4 — Organization Seed Data

| Step | File | Seeds |
|-----:|------|-------|
| Seed | `seed/02_organization/03_organization.sql` | 3 organizations (resolves type/status via master_data) |
| Seed | `seed/01_foundation/09_sakha_postal_codes.sql` | Postal codes for the 175 Sakha branches below |
| Seed | `seed/02_organization/05_sakha_branches.sql` | 175 real Sakha Sangha branches |
| Seed | `seed/02_organization/06_id_sequence_org_sync.sql` | Advances `id_sequence_master` counters to match seeded `organization_code`s (must run after Organization DDL + seed, not in Phase 2 — see file header) |
| Patch | `seed/02_organization/07_advisory_board_organization_patch.sql` | Idempotent `run_sql` after the sync above (2026-10-30): the `ADVISORY_BOARD` organization-type value + the singleton `Advisory Board` organization (`ADB` / `NSSAB`, parent = the Kendra by type); no-op on re-run. Wired identically in `02_build.sh`, `02_build.ps1` and `render_build.sh` |

Run order inside Phase 4 is `03_organization.sql` → `01_foundation/09_sakha_postal_codes.sql` →
`05_sakha_branches.sql` → `06_id_sequence_org_sync.sql` → `07_advisory_board_organization_patch.sql`. (There is no `04_*` file in
`seed/02_organization/` — the former `04_tier4_verification_orgs.sql` was deleted.)

### Phase 5 — Person DDL (2 tables, Depths 2–3)

| Step | File | Table | Depth |
|-----:|------|-------|------:|
| DDL | `ddl/03_person/02_person.sql` | `person` | 2 |
| DDL | `ddl/03_person/03_person_address.sql` | `person_address` | 3 |

`ddl/03_person/01_person_master_tables.sql` is superseded — gender/marital
status/address type data now lives in Foundation `master_data` seed (Phase 2)
and is not run.

### Phase 6 — Family DDL (6 tables + 1 trigger + 1 patch, Depths 2–4)

| Step | File | Table |
|-----:|------|-------|
| DDL | `ddl/04_family/01_family_group.sql` | `family_group` |
| DDL | `ddl/04_family/02_family_relationship.sql` | `family_relationship` |
| DDL | `ddl/04_family/03_family_head_history.sql` | `family_head_history` |
| DDL | `ddl/04_family/04_family_transition_history.sql` | `family_transition_history` |
| DDL | `ddl/04_family/05_family_link.sql` | `family_link` |
| DDL | `ddl/04_family/06_family_admin.sql` | `family_admin` |
| DDL | `ddl/04_family/07_family_move_transition_guard.sql` | *(deferred constraint trigger on `family_relationship`, no table)* |
| Patch | `ddl/04_family/08_family_head_history_audit_columns.sql` | `updated_at` etc. on an existing `family_head_history` (`run_sql`, idempotent; validate asserts `family_head_history.updated_at`) |

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
| DDL (`run_sql`, idempotent) | `ddl/05_membership/19_sakha_local_number_allocator.sql` | *(function `fn_next_sakha_local_number`)* |
| DDL (`run_sql`, idempotent) | `ddl/05_membership/20_home_affiliation_guard.sql` | *(deferred constraint triggers: active non-system `sangha_sevi` needs an open home affiliation by commit; does not scan existing rows)* |

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
| SQL | `ddl/06_authentication/06_registration_claim_legacy_member_patch.sql` | idempotent patch (`run_sql`/`Invoke-Sql`, GDR-009): adds `is_legacy_member` / `darshak_is_legacy_member` + agreement CHECKs to an existing `registration_claim`; existing claims default to legacy iff they already carry a number | — |
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
| DDL | `ddl/08_governance/12_governance_seat_limits.sql` | *(seat-count functions + triggers on `body_member_assignment`; `run_sql`. Its `body_type_master.max_members` column/seed is existence-gated — needs a full rebuild to take effect)* | — |
| Patch | `ddl/08_governance/13_governance_nomination_refile_index.sql` | live-only `uq_election_nomination_active_candidate` (`run_sql`; validate checks the index definition mentions `nomination_status`) | — |

### Phase 11d / 11e / 11f — Correspondence (5 tables), Attendance (4 tables) and Organization re-parent approval (2 tables) DDL

Phase 11d runs `ddl/09_correspondence/01..05` (`correspondence`, `correspondence_document`, `correspondence_finance_reference`, `correspondence_sequence_counter`, `correspondence_approval_step`); Phase 11e runs `ddl/10_attendance/01..04` (`weekly_sangha_puja`, `weekly_sangha_puja_attendance`, `attendance_exception`, `attendance_review`) then the idempotent patch `05_attendance_live_version_index_patch.sql` (`idx_wspa_puja_last_change`, owner 2026-10-31, for the live attendance register; validate asserts the index). Both are placed after Governance so Phase 12's writer grant and Phase 14's audit trigger cover them; `render_build.sh` mirrors both. `ddl/08_governance/12_governance_seat_limits.sql` is also part of Phase 11b.

Phase 11f runs `ddl/02_organization/06_organization_reparent_request.sql` and `07_organization_reparent_step.sql` (`organization_reparent_request`, `organization_reparent_step` — the Sakha re-parent approval chain, owner rule 2026-10-30). The files live in the Organization folder but run here, after Governance, because they FK `user_account`, `person`, `sangha_sevi`, `body_master` and `position_master`; being before Phase 12/14 they get the writer grant (`GRANT ... ON ALL TABLES`, incl. future ones — verified in `05_create_writer_role.sql` by design, not run) and the audit trigger. `render_build.sh` mirrors it; The idempotent patch `09_organization_reparent_step_source_role_patch.sql` then widens the existing step CHECKs (`SOURCE_PARENT_PRESIDENT`, `step_order` 1..4; the DDL is existence-gated). `03_validate.sh`/`.ps1` check existence/key columns/FK integrity, plus that the step-role CHECK allows `SOURCE_PARENT_PRESIDENT` (patch 09 ran).

### Phase 11g — Assets & Property DDL (7 tables)

Phase 11g (Module #22, GDR-010) runs `ddl/11_assets_property/01..07` (`property`, `asset`, `custodianship`, `property_statutory_record`, `maintenance_record`, `property_document`, `asset_document`; existence-gated `run_ddl`/`Invoke-Ddl`), then two idempotent non-table files via `run_sql`/`Invoke-Sql` on every build: `ddl/11_assets_property/08_assets_property_guards.sql` (lifecycle / identifier-immutability / custodianship-history trigger functions and their 3 triggers), `ddl/11_assets_property/09_asset_custodian_org_type_function.sql` (owner rule 2026-11-02, GDR-010 §2C: `nss.fn_is_asset_custodian_org_type()` + `trg_custodianship_custodian_guard`, so a custodianship can only name a physical organization; never scans existing rows) and `ddl/11_assets_property/10_assets_property_belongs_to_patch.sql` (GDR-010 §2D: nullable `belongs_to_organization_pk` + FK + partial index on `property`/`asset`; also in `01_property.sql`/`02_asset.sql` for fresh builds) `ddl/11_assets_property/11_assets_property_acquisition_method_patch.sql` (GDR-010 §2E: nullable `acquisition_method_master_data_pk` + FK + partial index on `property`/`asset`; also in `01`/`02` for fresh builds), `seed/11_assets_property/01_assets_property_reference_data_patch.sql` (the `PROPERTY`/`ASSET` id sequences, 7 master categories incl. `ACQUISITION_METHOD` and 38 values incl. the `DISPOSED`/`RETIRED` end reasons — a patch because the Foundation seeds are existence-gated) and, after it, `ddl/11_assets_property/12_assets_property_terminal_custody_patch.sql` (GDR-010 §2F: ENDs the still-ACTIVE custodianship of already DISPOSED/RETIRED records; no-op on fresh builds). `08` also holds `trg_custodianship_terminal_guard` (no new custodianship on a DISPOSED/RETIRED record). The module's two permissions arrive in Phase 0 via `seed/00_bootstrap/05_assets_property_permissions_patch.sql` (permission_master 28 → 30, role_permission 166 → 178), followed by `06_assets_property_permissions_revoke_patch.sql` (soft-deletes the 4 withdrawn grants on databases that ran the original 16-row `05`). Placed before Phase 12 / Phase 14, so the writer grant and the generic audit trigger (`field_change_log`, AP-071) cover the new tables. `render_build.sh` repeats all of it in the same order.

### Phase 11h — Live refresh (1 table)

`ddl/12_live_refresh/01_live_change_marker.sql` (existence-gated `run_ddl`: table `live_change_marker` + sequence `live_change_seq`), then `02_live_change_triggers.sql` (`run_sql`, idempotent, EVERY build): `fn_live_change_marker()` (SECURITY DEFINER), one `trg_live_change_marker` statement-level trigger per table in the literal `watched` array (55 tables; an entry `'table!col,col'` lists routine-churn columns that must NOT bump the marker — today only `user_account`, login bookkeeping — and the trigger becomes `UPDATE OF <all other columns>`; must equal `api/routers/live.py::LIVE_FEED_TABLES`; tables that do not exist yet are skipped, triggers on tables removed from the list are dropped), seeded marker rows (an existing DB gets new triggers/rows by re-running this file, which every build does), and `GRANT SELECT` to `nss_db_backend`. Runs after Phase 11g (all watched tables exist) and before Phase 12/14; Phase 14's audit trigger excludes `live_change_marker`. `03_validate` checks existence, key columns, that the triggers exist, that every trigger has a marker row (WARN) and that the marker table is not audited.

### Phase 11c — Governance Seed Data

Starter catalogues for the two Depth-0 masters, plus the 3 NSS-wide singleton `body_master` rows.

| Step | File | Seeds |
|-----:|------|-------|
| Seed | `seed/08_governance/01_body_type_master.sql` | 8 body types (`KENDRA_GOVERNING_BODY`, `SAKHA_GOVERNING_BODY`, `ADVISORY_BOARD`, `MAHILA_PARICHALANA_MANDALI`, `SEVAK_SANGHA_EXECUTIVE`, plus `ANCHALIKA_GOVERNING_BODY`/`ZILLA_GOVERNING_BODY`/`PATHA_CHAKRA_GOVERNING_BODY` added 2026-10-09 for the §63 composite auto-grant rule) |
| Seed | `seed/08_governance/02_position_master.sql` | 10 positions (`PRESIDENT`, `VICE_PRESIDENT`, `PARICHALAK`, `SECRETARY`, `ASSISTANT_SECRETARY`, `JOINT_SECRETARY`, `TREASURER`, `CASHIER`, `MUKHYA_PUJAKA`, `MEMBER`) |
| Seed | `seed/08_governance/03_body_master.sql` | 3 NSS-wide bodies: Kendra Governing Body, Advisory Board, central Mahila Parichalana Mandali, plus one empty Sakha Governing Body shell per active `SAKHA_SANGHA` |
| Patch | `seed/08_governance/04_sakha_asana_governing_body_patch.sql` | Idempotent `run_sql` after the seed above (2026-10-30): one empty `SAKHA_GOVERNING_BODY` shell per ACTIVE `SAKHA_ASANA` organization that has none (a Sakha Asana is a Sakha Sangha without its own building and has its own Governing Body/President); no-op when none missing. Wired identically in `02_build.sh`, `02_build.ps1`, `render_build.sh` |

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
| 11d | Correspondence | 5 |
| 11e | Attendance | 4 |
| 11f | Organization re-parent approval | 2 |
| 11g | Assets & Property | 7 |
| 11h | Live refresh (`live_change_marker`) | 1 |
| 14 | Audit (Foundation) | 1 |
| | **Total** | **79** |

### Validation coverage (`03_validate.sh`/`.ps1`)

**Patch-effect checks (2026-10-31, extended 2026-11-01)** — a patch that silently SKIPs would otherwise go unnoticed, so validate asserts its outcome: per-role `role_permission` minimums (Advisory Board admin 8, Mahila admin 18, Sakha admin 18, Attendance Marker 2 — the Mahila/Advisory Board rows come from `04_role_permission_mahila_advisory_board_patch.sql`), exactly one active `ADVISORY_BOARD` organization (`07_advisory_board_organization_patch.sql`), `nss.fn_is_sakha_like_org_type()` present (`10_sakha_like_org_type_function.sql`), every active `SAKHA_ASANA` has a `SAKHA_GOVERNING_BODY` (`04_sakha_asana_governing_body_patch.sql`). Mismatches FAIL (not WARN). **None of the 2026-10-30..11-01 validate/build changes has been executed against a database** (and the `.ps1` files have never been run by the maintainers).

The two wrappers run the same ~234 check calls in the same order (parsed and diffed check-by-check on 2026-11-01: labels, SQL, thresholds and WARN-vs-FAIL helpers are identical; only the Attendance idx/FK-orphan pair is swapped in order). Covered:

- Bootstrap RBAC (3 tables, row minimums, FK orphans) and per-role permission minimums.
- Foundation: 13 tables, row minimums, uniqueness, FK orphans, `city_village.district_pk` + its >= 98 % coverage, deferred/`submitted_by_person_pk` columns (`post_office` is covered by the latter column check only).
- Organization (`organization` >= 179 = 3 + 175 Sakhas + the Advisory Board), FK orphans, all 14 `ORGANIZATION_TYPE` values, exactly one active `ADVISORY_BOARD` organization, `fn_is_sakha_like_org_type()`, the singleton trigger + no duplicate singleton, every active `SAKHA_ASANA` has a `SAKHA_GOVERNING_BODY`.
- Person (`person_address` + address FK columns), Authentication (5), Administration (2).
- Family (6), Membership (16 incl. `credential_sequence_counter`, `sakha_local_number_counter`, `membership_change_request`) and `system_event_log`: **existence only**, plus `fn_next_sakha_local_number()`, `fn_assert_sevi_has_home_affiliation()`, the two deferred home-affiliation constraint triggers, the `registration_claim` legacy columns + CHECKs, and the WARN diagnostics below.
- Governance (10): existence, key columns, 3 FK-orphan checks, re-file index. Correspondence (5): existence, key columns, FK orphans, `reference_number` uniqueness (the deferred `financial_transaction` FK is not checked). Attendance (4): existence, key columns, FK orphans, `(sakha_pk, puja_date)` uniqueness, `idx_wspa_puja_last_change`. Re-parent approval (2): existence, key columns, FK orphans, the step-role CHECK.

Row-count checks pass when `count >= expected` and only WARN below it; the minimums track the seeds (recomputed from the seed files 2026-11-01):
`role_master` 11, `permission_master` 30, `role_permission` 178 (minimum; 182 rows on a DB that ran the original asset patch, 4 inactive), `master_category` 26, `master_data` 156, `id_sequence_master` 16 (the last five include the Assets & Property patches), `system_setting` 5, `organization` 179
(after Phase 4), `person` 0, `user_account`/`user_role`/`admin_scope` 1 (the bootstrap admin). The geography minimums are current: `state` 112, `district` 780 (785 seeded),
`postal_code` 17800 (17,869 seeded), `city_village` 659000. Per-role `role_permission` minimums (FAIL, not WARN): Advisory Board admin 8, Mahila admin 18, Sakha admin 18, Attendance Marker 2; plus `ASSET_MANAGE` actively granted to ≥ 4 roles, `ASSET_VIEW` to ≥ 8, and a FAIL check that the 4 withdrawn grants (Mahila VIEW+MANAGE, Anchalika/Zilla MANAGE) are not active; the `belongs_to_organization_pk` columns exist with no FK orphans. Assets & Property (7 tables): existence, 13 key columns, FK orphans, property-XOR-asset and one-ACTIVE-custodian invariants, the 3 guard triggers, `fn_is_asset_custodian_org_type()` + `trg_custodianship_custodian_guard` (FAIL if missing), a **WARN** count of existing custodianships held by a non-eligible organization (diagnostic below), the `PROPERTY`/`ASSET` sequences and the 6 master categories (FAIL if a patch did not run).

**Home-affiliation check (2026-11-01).** `03_validate` asserts `fn_next_sakha_local_number()` and the two
deferred triggers exist (FAIL if missing) and counts active non-system `sangha_sevi` rows with no open home
`membership_sakha_affiliation` (**WARN** only — there is deliberately no backfill; such rows show `–` as Local
Sakha ID in the Mark Attendance roster / Member Directory). To list them:

```sql
SELECT ss.sangha_sevi_id, ss.organization_pk, o.organization_name, o.short_code
FROM   nss.sangha_sevi ss
JOIN   nss.organization o ON o.organization_pk = ss.organization_pk
WHERE  ss.is_active AND NOT ss.is_system_account
  AND  NOT EXISTS (SELECT 1 FROM nss.membership_sakha_affiliation msa
                   WHERE msa.sangha_sevi_pk = ss.sangha_sevi_pk
                     AND msa.organization_pk = ss.organization_pk
                     AND msa.effective_to IS NULL
                     AND msa.affiliation_status IN ('ACTIVE','REACTIVATED')
                     AND btrim(msa.local_sakha_erp_id) <> '')
ORDER  BY ss.sangha_sevi_id;
```

**Credential invariant check (2026-11-01, GDR-009 §2A).** Every active, non-system member must hold exactly one
credential of the type their membership type requires — an ACTIVE `parichaya_patra` for Regular/Associate, an ACTIVE
`anumati_patra` for PROBATIONARY. `03_validate` counts violations as a **WARN** only (no DB trigger, no backfill). To list them:

```sql
SELECT ss.sangha_sevi_id, mt.value_code AS membership_type, ss.organization_pk
FROM   nss.sangha_sevi ss
JOIN   nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk
WHERE  ss.is_active AND NOT ss.is_system_account
  AND  CASE WHEN mt.value_code = 'PROBATIONARY'
            THEN NOT EXISTS (SELECT 1 FROM nss.anumati_patra ap
                             WHERE ap.sangha_sevi_pk = ss.sangha_sevi_pk AND ap.status = 'ACTIVE')
            ELSE NOT EXISTS (SELECT 1 FROM nss.parichaya_patra pp
                             WHERE pp.sangha_sevi_pk = ss.sangha_sevi_pk AND pp.status = 'ACTIVE')
       END
ORDER  BY ss.sangha_sevi_id;
```

### Render parity

`render_build.sh` (repo root, run by `render.yaml`) repeats Phases 0–7b and 9–14 (including 11b/11c Governance, 11d Correspondence, 11e Attendance, 11f Organization re-parent approval, 11g Assets & Property and 11h Live refresh) with the same file
order and the same `[OK]`/`[SKIP]`/abort rule; its phase/file order matches `02_build.sh` v2.8 (verified by extracting and diffing every `run_ddl`/`run_seed`/`run_sql` label, 2026-11-01), and it carries the same existence-gated `run_ddl`/`run_seed` model (header "Version 3.0"). `RUN_DB_BOOTSTRAP` gates only its Phase 13 admin seed, not DDL/seed.
Differences / known drift: it has no Phase 15 demo seed (`RUN_DEMO_SEED` is honoured only by `02_build.sh`/`.ps1`); it builds Tailwind and installs Python deps first (`npm install` in a `runtime: python` service is untested); it substitutes for
`00_create_database.sql`/`01_extensions.sql` by running `CREATE SCHEMA IF NOT EXISTS nss`,
`ALTER DATABASE ... SET search_path`, and best-effort `pgcrypto`/`pg_trgm`/`btree_gin` (no
`postgis` — nothing in `database/` or `api/` references it, so this is harmless; `01_extensions.sql` installs it locally only); it creates the three `nss_db_*` roles inline (reusing `DB_PASSWORD`, or
`DB_WRITE_PASSWORD` for the writer) just before Phase 9; a Phase 13 failure is non-fatal; and `render.yaml` declares an unused `DATABASE_URL`.

**Functions and grants.** New functions (`fn_next_sakha_local_number`, `fn_assert_sevi_has_home_affiliation`, `fn_is_sakha_like_org_type`, the singleton/seat-limit functions) are plain `SECURITY INVOKER` and nothing in `database/` issues `REVOKE`, so PostgreSQL's default `EXECUTE` to `PUBLIC` lets `nss_db_writer` call them (no explicit function grant is needed or issued). The tables they read/write (`sakha_local_number_counter`, `membership_sakha_affiliation`, …) are covered by Phase 12's `GRANT … ON ALL TABLES` + `ALTER DEFAULT PRIVILEGES` (SELECT/INSERT/UPDATE), so the invoker's rights suffice. Only `fn_audit_trigger()` is `SECURITY DEFINER`. Not verified against a live Neon instance.

### Run order for an existing database

**Custodianships held by a non-eligible organization (Assets & Property, GDR-010 §2C)** — the `trg_custodianship_custodian_guard` trigger only checks new/re-pointed rows, so any custodianship stored before the rule (or against a conceptual/wing/Advisory Board organization) is counted as a **WARN** by `03_validate` and never auto-repaired (transfer the record to a physical organization through the API). To list them:

```sql
SELECT c.custodianship_pk, c.property_pk, c.asset_pk, o.organization_name, md.value_code AS organization_type, c.status
FROM nss.custodianship c
JOIN nss.organization o ON o.organization_pk = c.custodian_organization_pk
JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
WHERE c.is_active = TRUE AND NOT nss.fn_is_asset_custodian_org_type(md.value_code);
```

`02_build` (re-run) → `03_validate`. No rebuild is needed for anything delivered as a patch above (they run on every build). A **full rebuild** is still required for changes to the *body* of an existing table's DDL or seed that has no patch (e.g. `body_type_master.max_members`, `election_type`, the widened `admin_scope` CHECK, the `city_village`/`postal_code`/`post_office` `submitted_by_person_pk` column). The home-affiliation guard, singleton trigger and Local Sakha ID allocator never scan existing rows, so a database already holding violators still builds; `03_validate` then WARNs (diagnostic SELECTs above).

### Known gaps

- Nothing from 2026-10-30..11-01 (patches, validate additions, `.ps1` edits) has run against a database; the `.ps1` scripts have no CI or Windows host.
- No automatic backfill of members lacking a home affiliation / Local Sakha ID, or an ACTIVE credential (owner decision; WARN only).
- Row minimums are lower bounds and WARN only; they do not detect a seed that was partially loaded above the minimum.
- Existence-gated seeds mean a changed seed file never reaches an existing table unless a patch file exists for it.

### Not executed (future phases)

- Pass 2 audit-actor FK constraints (`*_by_sangha_sevi_pk` — still deferred, including on every
  Tier 5 table)
- MFA enforcement (Tier 5.1) — self-reset OTP (forgot-password) and permission-gating on
  Tier 1–4 endpoints are both already implemented, not future work
- All remaining modules — Governance (Phase 11b/11c, 10 tables), Correspondence (Phase 11d, 5 tables), Attendance (Phase 11e, 4 tables) and Organization re-parent approval (Phase 11f, 2 tables) are
  implemented and wired into the build; they are no longer future work

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
