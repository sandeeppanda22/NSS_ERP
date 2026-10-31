# database/seed/02_organization/

Organization Module seed data — the three unique organizations required
before downstream modules, plus 175 real Sakha Sangha branches from the
official NSS branch directory.

Authority: SOL-ORG-005 §48, SOL-ARCH-010 §8

## Seed Execution Order

Execute AFTER:
- All Foundation DDL + seed (`database/ddl/01_foundation/`, `database/seed/01_foundation/`)
- All Organization DDL (`database/ddl/02_organization/`)

| # | File | Seeds Into | Depends On |
|--:|------|-----------|-----------|
| 03 | `03_organization.sql` | `organization` | Foundation `master_category`/`master_data` seed, Foundation `country`/`postal_code` seed, Organization DDL complete |
| — | `../01_foundation/09_sakha_postal_codes.sql` | `postal_code` | Foundation `country`/`state` seed; must run **before** `05_sakha_branches.sql` (build Phase 4 runs it here, not in Phase 2) |
| 05 | `05_sakha_branches.sql` | `organization` | `03_organization.sql` (needs `KEN` as parent); Foundation `master_data` seed; `09_sakha_postal_codes.sql` |
| 06 | `06_id_sequence_org_sync.sql` | `id_sequence_master` | `03_organization.sql` + `05_sakha_branches.sql` (reads seeded `organization_code`s) |
| 07 | `07_advisory_board_organization_patch.sql` | `master_data` + `organization` | Idempotent patch (run with `run_sql`/`Invoke-Sql`, not existence-gated): adds the `ADVISORY_BOARD` organization type and the singleton `Advisory Board` organization (`ADB`, short_code `NSSAB`, parent = the Kendra found by type). The Advisory Board governance body stays NULL-organization and is not linked to it |

There is no `01_*`, `02_*` or `04_*` file in this folder (the first two were retired type/status
masters, the last was the deleted Tier 4 verification-org seed). `database/scripts/02_build.sh`/`.ps1`
run these as Phase 4, in the order 03 → `09_sakha_postal_codes` → 05 → 06 → 07 (07 is an idempotent `run_sql` patch, 2026-10-30).

> **Moved:** The former `01_organization_type_master.sql` and
> `02_organization_status_master.sql` seed files are gone. Type and status
> seed data now live in Foundation's generic master-data seed files —
> `database/seed/01_foundation/01_master_category.sql` (categories) and
> `database/seed/01_foundation/02_master_data.sql` (the `ORGANIZATION_TYPE`
> and `STATUS` value rows). `03_organization.sql` looks these up at insert
> time via joins on `master_data`/`master_category` (`category_code` +
> `value_code`) rather than FK'ing to dedicated master tables.

> **Removed:** The former `04_tier4_verification_orgs.sql` (ANC1, SKH1,
> ANC2, SKH2 — 4 test organizations for Tier 4 verification) has been
> deleted. Real Sakha branches are now seeded via `05_sakha_branches.sql`.

## Execution Command

```bash
# As nss_db_owner against the nss_erp database (manual run; 02_build.sh does this for you):
psql -U nss_db_owner -d nss_erp -f database/seed/02_organization/03_organization.sql
psql -U nss_db_owner -d nss_erp -f database/seed/01_foundation/09_sakha_postal_codes.sql
psql -U nss_db_owner -d nss_erp -f database/seed/02_organization/05_sakha_branches.sql
psql -U nss_db_owner -d nss_erp -f database/seed/02_organization/06_id_sequence_org_sync.sql
```

(A plain `0*.sql` glob over this folder alone would skip the Sakha postal codes and leave the
branches seeded with a NULL `postal_code_pk` where a PIN exists in the source data.)

---

## Seed File Descriptions

### 03_organization.sql

Seeds the 3 unique organizations of NSS. No `organization_id` — unique
organizations are identified by `organization_code` alone. Sequence-generated
IDs are for multi-instance org types (Sakha, Anchalika, etc.). Type and
status are resolved per row via joins against `nss.master_data`/
`nss.master_category` on `category_code = 'ORGANIZATION_TYPE'` /
`'STATUS'` and the relevant `value_code`.

| # | `organization_code` | Name | Type (`value_code`) | Parent |
|--:|---------------------|------|------|--------|
| 1 | `KEN` | Nilachala Saraswata Sangha | `KENDRA` | NULL (apex governing body) |
| 2 | `NKT` | Nilachala Kutira | `NILACHALA_KUTIRA` | NULL (Eternal Abode, Puri) |
| 3 | `SMR` | Sri Shri Nigamananda Smruti Mandir | `SMRUTI_MANDIRA` | NULL (memorial temple, Puri) |

All three are seeded with status `ACTIVE` and country = IN (India).
Kendra's representative office address is seeded inline: Satsikshya Mandir,
A/4, Unit-9, Bhubaneswar - 751022, Odisha, India.

### 05_sakha_branches.sql

Seeds 175 real Sakha Sangha branches from the official NSS branch directory
document (v2.0). All parented to Kendra (`KEN`). Codes: `SKH1`–`SKH175`
(unpadded). SKH1 = Ekamra Saraswata Sangha.

Features:
- PIN codes resolved to `postal_code_pk` FK for 121 of 175 branches (63 carry a PIN in the source
  directory; 58 more are recovered by matching the address's `Po-<office>` token against the India
  Post directory); the other 54 have NULL `postal_code_pk`
- After the INSERT, backfills `country_pk`/`state_pk`/`district_pk`: primarily from the
  `Dist-<Name>` token in each address (165 of 175, mapped onto the LGD `district_code`), with a
  PIN-derived modal district as fallback; only SKH164 (USA) is left without a district
- Depends on `database/seed/01_foundation/09_sakha_postal_codes.sql` for
  postal code records
- `short_code` column: NULL by default, admin-assignable via admin panel
  (3-5 uppercase alphanumeric, e.g. "EKM" for Ekamra)
- Country: `IN` for Indian branches, `US` for America Saraswata Sangha
- CTE-based bulk INSERT with master_data + postal_code JOINs
- Idempotent via `ON CONFLICT (organization_code) DO NOTHING` (insert-if-missing only — a
  re-run never overwrites a branch row that already exists, so live edits are preserved)

### 06_id_sequence_org_sync.sql

Advances each org-type `id_sequence_master.current_value` counter to at least the largest
numeric suffix of an existing `organization_code` of that type (e.g. after `05_sakha_branches.sql`
seeds `SKH1`-`SKH175`, `SAKHA`'s counter is synced to `175`), so `next_id()`/`peek_next_id()`
never mints a duplicate code. Idempotent and monotonic (`GREATEST()` never lowers a counter).
Was previously the tail end of `database/seed/01_foundation/03_id_sequence_master.sql` (Phase 2)
— moved here because it queries `nss.organization`, which doesn't exist until Phase 3
(Organization DDL); running it in Phase 2 fails a clean build with
`relation "nss.organization" does not exist`.

---

## Notes

- Organization types and statuses are frozen per SOL-ORG-005 §48 / GOV-002,
  but the seed rows themselves now live in Foundation's `master_data`
  (see "Moved" note above) — not in this folder.
- **Unique org hierarchy (ERP-FROZEN):**
  KEN, NKT, SMR are peer root organizations (`parent = NULL`).
  KEN remains the apex governing body. Physical location/operational
  association != organizational parent-child relationship.
  Constitutional/functional roles are distinguished by
  `organization_type_master_data_pk`.
- Unique organizations have no `organization_id` — identified by
  `organization_code` alone. `organization_id` (sequence-generated via
  `id_sequence_master`) is for multi-instance types only.
- Beyond the seeded Sakha branches, additional organizations (Anchalika,
  Zilla, etc.) are created at runtime through governance workflows.
- Foundation seed data (`master_category`, `master_data`, `country`,
  `postal_code`) must be loaded before Organization seed.
- All addresses are editable at runtime — seed values are initial state only.
