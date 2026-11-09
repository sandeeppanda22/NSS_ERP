# database/ddl/11_assets_property/

Assets & Property DDL (Module #22, Tier 6) — 7 tables plus one idempotent trigger file. Written 2026-11-02,
merged into the local `develop` (2026-11-09); the owner's later full DB run (after a rebuild) exercised it through the backend suites. Built as Phase 11g of `02_build.sh`/`.ps1` and `render_build.sh`
(after Governance/Correspondence/Attendance/re-parent approval, before the Phase 12 writer grant and Phase 14 audit
trigger, so both cover these tables). Design authority: `docs/03_Solution/modules/assets_property/`
(SOL-AP-001..005, rules AP-001..AP-074); implementation decisions on the PENDING items: GDR-010 (`Proposed`).

| File | Table | Notes |
|---|---|---|
| `01_property.sql` | `property` | Immovable property. `property_id` (`PROP<n>`, UNIQUE, immutable), `property_type_master_data_pk` (master_data `PROPERTY_TYPE`), `status` CHECK `REGISTERED/ACTIVE/UNDER_MAINTENANCE/DISPOSED`, free-text `location_description` / `holding_arrangement` (AP-022 / AP-013 PENDING), `acquired_at`. No financial columns. |
| `02_asset.sql` | `asset` | Movable asset. `asset_id` (`AST<n>`), `asset_type_master_data_pk` (`ASSET_TYPE`), `status` CHECK `REGISTERED/IN_CUSTODY/UNDER_MAINTENANCE/RETIRED`, free-text `condition`. |
| `03_custodianship.sql` | `custodianship` | Temporal custody by an **organization** (AP-015). Exactly one of `property_pk` / `asset_pk` (XOR CHECK, AP-019); status `ASSIGNED/ACTIVE/ENDED`; `effective_from/_to`; `end_reason_master_data_pk` (`CUSTODIANSHIP_END_REASON`) required exactly when ENDED; partial UNIQUE indexes allow one ACTIVE custodianship per property / per asset (AP-017). |
| `04_property_statutory_record.sql` | `property_statutory_record` | Property-**only** (AP-040: `property_pk NOT NULL`, no `asset_pk` column). `obligation_type_master_data_pk` (`STATUTORY_OBLIGATION_TYPE`), reference number, notes. No payment columns (Finance). |
| `05_maintenance_record.sql` | `maintenance_record` | Historical record on a property XOR an asset; `maintenance_type_master_data_pk` (`MAINTENANCE_TYPE`), `performed_at`. No cost columns. |
| `06_property_document.sql` / `07_asset_document.sql` | `property_document`, `asset_document` | Explicit junctions to Foundation `document_master` (DOC-ARCH-001, no polymorphic FK); nullable `relationship_type_master_data_pk` (`ASSET_PROPERTY_DOCUMENT_RELATIONSHIP`); partial UNIQUE (entity, document) `WHERE is_active`. |
| `08_assets_property_guards.sql` | (functions + 4 triggers; `trg_custodianship_terminal_guard` BEFORE INSERT refuses a new custodianship on a DISPOSED property / RETIRED asset, GDR-010 §2F — the terminal transition itself ENDs the active custodianship, which the existing guards already permit) | Idempotent (`run_sql`/`Invoke-Sql` every build): `fn_ap_entity_guard()` on `property`/`asset` (immutable ids, SOL-AP-003 transitions, DISPOSED/RETIRED terminal, custody required to leave REGISTERED) and `fn_custodianship_guard()` (ENDED rows immutable, target/custodian/`effective_from` immutable, status only ASSIGNED→ACTIVE→ENDED). Violations raise `check_violation` (→ HTTP 422). The API enforces the same rules first; keep `assets_property.py`'s transition tables and this file in step. |
| `09_asset_custodian_org_type_function.sql` | (function + 1 trigger) | Idempotent (`run_sql`/`Invoke-Sql` every build, after 08): THE SQL definition of custodian-eligible (physical) organization types `nss.fn_is_asset_custodian_org_type(text)` (Sakha pair via `fn_is_sakha_like_org_type()` + Patha Chakra, Kendra, Nilachala Kutira, Smruti Mandira; owner rule 2026-11-02, GDR-010 §2C; Python `ASSET_CUSTODIAN_ORG_TYPES`, JS `NSS.ASSET_CUSTODIAN_ORG_TYPES`) and `trg_custodianship_custodian_guard` (BEFORE INSERT OR UPDATE OF `custodian_organization_pk` on `custodianship`, `check_violation` → 422). Creating the trigger does not scan existing rows; `03_validate` WARNs on pre-existing custodianships held by a non-eligible organization. |
| `10_assets_property_belongs_to_patch.sql` | (2 columns + 2 FKs + 2 partial indexes) | Idempotent (`run_sql`/`Invoke-Sql` every build, after 09): `belongs_to_organization_pk UUID NULL` → `organization` on `property` and `asset` (`ADD COLUMN IF NOT EXISTS`; FK added only if missing; `fk_*_belongs_to_org`, `idx_*_belongs_to_org`). Owner decision 2026-11-02, GDR-010 §2D: the organization a record *belongs to* when that differs from its physical custodian (e.g. custodian Kendra, belongs to Mahila Sangha). Informational only - no effect on authorization, scope, the custodian rule or lifecycle. Also present in `01_property.sql`/`02_asset.sql` for fresh builds (those files are existence-gated). |
| `11_assets_property_acquisition_method_patch.sql` | (2 columns + 2 FKs + 2 partial indexes) | Idempotent (`run_sql`/`Invoke-Sql` every build, after 10): `acquisition_method_master_data_pk UUID NULL` → `master_data` (category `ACQUISITION_METHOD`) on `property` and `asset` (`fk_*_acquisition_method`, `idx_*_acquisition_method`). Owner decision 2026-11-03, GDR-010 §2E: HOW the record was acquired (AP-023). Informational only. Also in `01`/`02` for fresh builds. |
| `12_assets_property_terminal_custody_patch.sql` | (data patch, 2 UPDATEs) | Idempotent (`run_sql`/`Invoke-Sql` every build, AFTER `seed/11_assets_property/01_…reference_data_patch.sql`, which seeds the `DISPOSED`/`RETIRED` custodianship end reasons it needs). Owner decision 2026-11-03, GDR-010 §2F: ENDs the still-ACTIVE custodianship of every DISPOSED property / RETIRED asset (`effective_to` = the record's last-change date, never before `effective_from`). A no-op on fresh builds and on re-runs; `03_validate` FAILs if any such ACTIVE row remains. |

Common to all tables: `*_pk` UUID PK (`gen_random_uuid()`), the project audit columns (plain nullable `*_by_sangha_sevi_pk` UUIDs;
the FK to `sangha_sevi` is added by the build Phase 13c patch, `../13_audit_actor_fk/`), `is_active` + `deleted_at` soft delete with the standard consistency CHECK. History is never
hard-deleted (the writer role has no DELETE privilege).

Reference data and RBAC are **not** in this folder: the seven master categories (incl. `ACQUISITION_METHOD`), the `PROPERTY`/`ASSET` id sequences
(`database/seed/11_assets_property/01_assets_property_reference_data_patch.sql`) and the `ASSET_VIEW`/`ASSET_MANAGE`
permissions with their 12 grants (`database/seed/00_bootstrap/05_assets_property_permissions_patch.sql`; Anchalika/Zilla admins view-only, Mahila admin none; `06_assets_property_permissions_revoke_patch.sql` soft-deletes the 4 grants an earlier version created) are idempotent
patches, because the Foundation / RBAC seeds are existence-gated and never re-run on an existing database.

API: `api/routers/assets_property.py` + `api/schemas/assets_property.py` (26 endpoints). Tests:
`tests/db/test_assets_property_schema.py`, `tests/api/test_assets_property.py`,
`tests/security/test_assets_property_security.py` (shared `tests/assets_property_support.py`).
`03_validate.sh`/`.ps1` check existence, key columns, FK orphans, the XOR / one-ACTIVE-custodian invariants, the guard
triggers, the id sequences, the master categories, the `ASSET_VIEW`/`ASSET_MANAGE` grants (and that the 4 withdrawn grants are not active) the `belongs_to_organization_pk` / `acquisition_method_master_data_pk` columns + FK orphans, the terminal-record insert guard and the "no ACTIVE custodianship on a terminal record" check.

Folder index: [`../README.md`](../README.md). Deep doc: `docs/PROJECT_DOCUMENTATION.md`.
