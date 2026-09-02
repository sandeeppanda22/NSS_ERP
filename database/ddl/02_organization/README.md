# database/ddl/02_organization/

Organization Module DDL — 3 tables per SOL-ORG-005, SOL-ARCH-010.

Authority: SOL-ORG-005 v1.2.0, SOL-ARCH-010

## DDL Execution Order

Execute AFTER all Foundation DDL (`database/ddl/01_foundation/`).

| # | File | Table | Depth | Sequence |
|--:|------|-------|------:|:--------:|
| 01 | `01_organization_type_master.sql` | `organization_type_master` | 0 | #7 |
| 02 | `02_organization_status_master.sql` | `organization_status_master` | 0 | #8 |
| 03 | `03_organization.sql` | `organization` | 4 | #33 |

## Design Notes

- **No `organization_address` table** — address is inline on `organization`
  per frozen design (SOL-ORG-005 §44).
- **No `hierarchical_level` column** — organizational level is determined by
  `organization_type_pk`; hierarchy depth derived from `parent_organization_pk`
  (SOL-ORG-005 §33).
- **`organization_id` is nullable** — unique organizations (Kendra, Kutira,
  Smruti Mandira) are identified by `organization_code` alone.
  `organization_id` is sequence-generated for multi-instance types only.
- **Self-referencing FK** on `organization.parent_organization_pk` is included
  in the CREATE TABLE statement.
- **Soft-delete** on all three tables: `deleted_at` + `is_active` with
  CHECK constraint ensuring consistency.
- `organization` depends on Foundation tables: `country`, `state`, `district`.
