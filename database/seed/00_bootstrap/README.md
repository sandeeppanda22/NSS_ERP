# database/seed/00_bootstrap/

Bootstrap RBAC seed data — role catalogue, permission catalogue, and role-permission
mappings, per SOL-BOOT-001.

Authority: SOL-BOOT-001, SOL-ARCH-011 §4

## Seed Execution Order

Execute AFTER `database/ddl/00_bootstrap/` (all 3 tables) — this is the first seed
data loaded, before Foundation.

## Status

| File | Status |
|---|---|
| `02_role_master.sql` | 8 roles seeded (3 SYSTEM: `NSS_ADMIN`, `AUDITOR`, `REPORT_VIEWER`; 5 ORGANIZATIONAL, one per scope level: `KENDRA_ADMIN`, `ANCHALIKA_ADMIN`, `ZILLA_ADMIN`, `SAKHA_ADMIN`, `PATHA_CHAKRA_ADMIN`) |
| `01_permission_master.sql` | Empty — permission catalogue not yet frozen |
| `03_role_permission.sql` | Empty — depends on the permission catalogue above |

Numbered `01`/`02`/`03` reflects the DDL file numbering (`permission_master` before
`role_master` before `role_permission`), not execution readiness — `02_role_master.sql`
is the only one with actual data right now.

## Design Notes

The 8 seeded roles include a `PATHA_CHAKRA_ADMIN` role (scope `PATHA_CHAKRA`) that
isn't listed in either SOL-BOOT-001 §4.2 or the Administration module's frozen role
catalogue (`docs/03_Solution/modules/administration/05_administration_table_design.md`
§8.7), both of which describe only 7 roles / 4 scope levels. Not yet reconciled — see
`docs/PROJECT_DOCUMENTATION.md` → Open questions / TODOs.
