# database/seed/

Reference/lookup data, mirroring `database/ddl/` (run after the corresponding DDL, driven by
`database/scripts/02_build.sh`/`.ps1`).

| Folder | Contents |
|---|---|
| `00_bootstrap/` | **Implemented** — `role_master`: 11 roles; `permission_master`: 28 permissions (adds `GOVERNANCE_*`, `CORRESPONDENCE_VIEW`/`_MANAGE`, `GEO_ENTRY_APPROVE`, `ATTENDANCE_VIEW`/`_MANAGE`); `role_permission`: 166 role-to-permission mappings (+ idempotent `04_role_permission_mahila_advisory_board_patch.sql`) |
| `01_foundation/` | **Implemented** — 14 files (`01`–`11b`, incl. bulk geography): master categories (13), master data values (90, across GENDER/MARITAL_STATUS/ADDRESS_TYPE/DOCUMENT_TYPE/MEMBERSHIP_TYPE/STATUS/RELATIONSHIP_TYPE/ORGANIZATION_TYPE/BLOOD_GROUP), `id_sequence_master` rows (14; `PERSON` padded to 10 digits, `SAKHA` unpadded), country (5), state (112), districts (785, India only), system settings (5), postal codes (3 in `08_postal_code.sql`, all-India PINs in `08b`, 56 Sakha-branch PINs in `09_sakha_postal_codes.sql` which runs in build Phase 4), post offices (`08c`), Dola Purnima festival calendar (`10`), ~673k `city_village` rows (`11`/`11b`) |
| `02_organization/` | **Implemented** — 3 unique named organizations (Kendra `KEN`, Nilachala Kutira `NKT`, Smruti Mandira `SMR`) + the singleton `Advisory Board` organization (`ADB`, via the idempotent `07_advisory_board_organization_patch.sql`) + 175 real Sakha Sangha branches (`SKH1`–`SKH175`) + `06_id_sequence_org_sync.sql` (advances org-code counters). The 14 organization types and the status values live in Foundation `master_data`, not here |
| `03_person/` | No seed data — `person`/`person_address` start with zero rows (the superseded `01_person_master_tables.sql` stub has been deleted) |
| `08_governance/` | **Tier 6** — `body_type_master` (8), `position_master` (10), `body_master` (3 NSS-wide singleton bodies: KENDRA_GB, ADVISORY_BOARD, KENDRA_MAHILA_PM) |
| `04_admin/` | **Tier 5** — `01_admin_bootstrap.sql`: one admin superuser (`P1`/`SS1`, `NSS_ERP_ADMIN` role, `NSS-WIDE` scope). Run via `python3 scripts/bootstrap_admin.py` (build Phase 13), not plain `psql` — see `04_admin/README.md` |
| `04_family/` | No seed data (README only) — unrelated to `04_admin/`; the shared `04_` prefix just mirrors `ddl/04_family/` |
| `05_membership/` | No seed data (README only) |
| `demo/` | **Optional, local-only** — `nss_demo_seed.sql` (gitignored; may be absent on a clean clone): 10 fully-formed members with credentials per active Sakha, for exercising search/governance/election screens. Run as build Phase 15 only when `RUN_DEMO_SEED` is truthy; never on Render |

There are no `06_authentication/` or `07_administration/` seed folders (those modules' only seed
data is the `04_admin/` bootstrap), and no `99_*.sql` scripts.

> **Removed:** All Tier 4/5 verification seed data and extended test data
> (`02_tier4_verification_*`, `01_tier4_verification_*`, `99_extended_test_data.sql`,
> `99_fix_memberships.sql`) have been deleted. A default build yields zero demo Person, Family, or
> Membership rows (unless the optional local `demo/` seed is requested via `RUN_DEMO_SEED`); real data is created at runtime through the registration flow and governance
> workflows.
