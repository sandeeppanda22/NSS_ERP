# database/ddl/02_organization/

Organization Module DDL — 1 core table (Depth 1) plus 3 enforcement triggers, per SOL-ORG-005, SOL-ARCH-010, plus 2 Sakha re-parent approval tables (06/07, Tier 6, owner rule 2026-10-30).

Authority: SOL-ORG-005 v1.2.0, SOL-ARCH-010

## DDL Execution Order

Execute AFTER all Foundation DDL (`database/ddl/01_foundation/`).

| # | File | Table | Depth | Sequence |
|--:|------|-------|------:|:--------:|
| 03 | `03_organization.sql` | `organization` | 1 | #33 |
| 04 | `04_organization_address_restriction_trigger.sql` | *(trigger `fn_enforce_organization_address_restriction()`, no table)* | 2 | — |
| 05 | `05_organization_kumari_sevak_uniqueness_trigger.sql` | *(trigger `fn_enforce_kumari_sevak_one_per_sakha()`, no table)* | 2 | — |
| 08 | `08_organization_singleton_trigger.sql` | *(trigger `fn_enforce_organization_singleton()`, no table; replaces the v1.0 ADVISORY_BOARD-only trigger, dropped idempotently)* | 2 | — |
| 06 | `06_organization_reparent_request.sql` | `organization_reparent_request` | 2 | — |
| 07 | `07_organization_reparent_step.sql` | `organization_reparent_step` | 3 | — |
| 09 | `09_organization_reparent_step_source_role_patch.sql` | (patch) | — | idempotent: widens the existing step table's `step_role`/`step_order` CHECKs (2026-10-31); `run_sql` after the table DDL |
| 10 | `10_sakha_like_org_type_function.sql` | `nss.fn_is_sakha_like_org_type()` | — | the one SQL definition of Sakha-like types (SAKHA_SANGHA + SAKHA_ASANA); called by the MBR-038A membership triggers and the Advisory Board one-seat-per-Sakha trigger; Phase 3 `run_sql` |

**06/07 run in build Phase 11f, not Phase 3**: they FK `user_account`, `person`, `sangha_sevi`,
`body_master` and `position_master`, which only exist later. They back the owner rule of 2026-10-30
— re-parenting a Sakha needs the Sakha President -> leaving Anchalika/Zilla President -> destination
Anchalika/Zilla President -> Kendra President chain (the leaving step is absent when the parent is Kendra; `step_role` `SOURCE_PARENT_PRESIDENT`, `step_order` 1..4) unless a Kendra Governing Body member or the NSS_ERP_ADMIN super administrator does it directly (Sakha Sangha and Sakha Asana alike) (API:
`api/routers/org_reparent.py`, `api/services/org_reparent_service.py`). The Sakha's
`parent_organization_pk` changes only when the final step approves; a partial unique index allows
one PENDING request per Sakha. No seed data.

**08 singleton trigger** (owner 2026-10-30, GDR-005): at most one ACTIVE organization of type `KENDRA`, `NILACHALA_KUTIRA`, `SMRUTI_MANDIRA`, `ADVISORY_BOARD`, and one central Mahila Sangha (`MAHILA_SANGHA` whose parent is a `KENDRA`; local per-Sakha Mahila Sanghas are unrestricted). Fires on INSERT and UPDATE OF type / `is_active` / parent, never scans existing rows (a database that already holds a duplicate still builds; only new offending writes are blocked). Run as Phase 3 `run_sql`, idempotent on existing databases.

File numbers start at 03 because `01`/`02` (the retired type/status master tables, below) no
longer exist. Run as Phase 3 of `02_build.sh`/`.ps1`.

> **Retired:** `01_organization_type_master.sql` and
> `02_organization_status_master.sql` (and the tables they created,
> `organization_type_master` / `organization_status_master`) no longer
> exist. Type and status values now live in Foundation's generic
> `master_category`/`master_data` tables, under categories
> `ORGANIZATION_TYPE` and `STATUS` — one dedicated master-table pair per
> domain concept was redundant with the `master_data` pattern the
> project already committed to (frozen "Master Data Driven" principle).
> `organization.organization_type_master_data_pk` and
> `organization.status_master_data_pk` both reference
> `nss.master_data(master_data_pk)` instead.

## Design Notes

- **Triggers (DB-level invariants, mirrored in `api/routers/admin.py`):**
  - `04_…address_restriction_trigger.sql` (v1.1, ORG-BR-099 narrowed 2026-09-28) — `ANCHALIKA_SANGHA`,
    `ZILLA_SANGHA` and `PATHA_CHAKRA` may never carry a physical premises address
    (`address_line_1`/`address_line_2`/`city_village_pk`/`postal_code_pk`/`latitude`/`longitude`
    must be NULL), but **may** carry `country_pk`/`state_pk`/`district_pk` (administrative
    jurisdiction).
  - `05_…kumari_sevak_uniqueness_trigger.sql` (ORG-BR-102) — at most one active `KUMARI_SANGHA`
    and one active `SEVAK_SANGHA` per Sakha; a BEFORE trigger rather than a partial unique index
    because the predicate needs `master_data.value_code`, and Postgres forbids subqueries in
    index predicates.

- **No `organization_address` table** — address is inline on `organization`
  per frozen design (SOL-ORG-005 §44).
- **No `hierarchical_level` column** — organizational level is determined by
  `organization_type_master_data_pk`; hierarchy depth derived from
  `parent_organization_pk` (SOL-ORG-005 §33).
- **`organization_id` is nullable** — unique organizations (Kendra, Kutira,
  Smruti Mandira) are identified by `organization_code` alone.
  `organization_id` is sequence-generated for multi-instance types only.
- **Self-referencing FK** on `organization.parent_organization_pk` is included
  in the CREATE TABLE statement.
- **Soft-delete** on `organization`: `deleted_at` + `is_active` with
  CHECK constraint ensuring consistency.
- `organization` depends on Foundation tables: `master_data` (type/status),
  `country`, `state`, `district`, `city_village`, `postal_code`.
