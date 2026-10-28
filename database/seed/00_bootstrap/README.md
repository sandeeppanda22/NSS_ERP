# database/seed/00_bootstrap/

Bootstrap RBAC seed data — role catalogue, permission catalogue, and role-permission
mappings, per SOL-BOOT-001.

Authority: SOL-BOOT-001, SOL-ARCH-011 §4

## Seed Execution Order

Execute AFTER `database/ddl/00_bootstrap/` (all 3 tables) — this is the first seed
data loaded, before Foundation (Phase 0 of `database/scripts/02_build.sh`/`.ps1`, which runs them
in file order `01` → `02` → `03`).

## Status

| File | Status |
|---|---|
| `02_role_master.sql` | 11 roles seeded (3 SYSTEM: `NSS_ERP_ADMIN`, `NSS_ERP_AUDITOR`, `NSS_ERP_REPORT_VIEWER`; 8 ORGANIZATIONAL — 7 scope-level admins, one per scope level: `NSS_ERP_KENDRA_ADMIN`, `NSS_ERP_ANCHALIKA_ADMIN`, `NSS_ERP_ZILLA_ADMIN`, `NSS_ERP_SAKHA_ADMIN`, `NSS_ERP_PATHA_CHAKRA_ADMIN`, `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN`, `NSS_ERP_ADVISORY_BOARD_ADMIN` (added 2026-10-09, §63 composite auto-grant rule) — plus Tier 6 `NSS_ERP_ATTENDANCE_MARKER`, assignable to several members per Sakha) |
| `01_permission_master.sql` | Populated — 28 permissions (incl. `GEO_ENTRY_APPROVE`, `ATTENDANCE_VIEW`/`_MANAGE`): `BOOTSTRAP_VIEW`, `FOUNDATION_VIEW`/`_MANAGE`/`_CALENDAR_MANAGE`, `ORGANIZATION_VIEW`/`_MANAGE`, `PERSON_VIEW`/`_MANAGE`/`_VIEW_SENSITIVE`, `FAMILY_VIEW`/`_MANAGE`, `MEMBERSHIP_VIEW`/`_MANAGE`/`_APPROVE`, `ADMIN_USER_VIEW`/`_MANAGE`, `ADMIN_ROLE_MANAGE`, `ADMIN_SCOPE_MANAGE`, `ADMIN_PERMISSION_VIEW`, `AUDIT_VIEW`, `REPORT_VIEW`, `GOVERNANCE_VIEW`/`_MANAGE` and `CORRESPONDENCE_VIEW`/`_MANAGE` (Tier 6) |
| `03_role_permission.sql` | Populated — 155 role-to-permission mappings (counts below predate the Tier 6/9 additions): `NSS_ERP_ADMIN` 25 (all permissions, including `FOUNDATION_CALENDAR_MANAGE`, which no other role holds), `NSS_ERP_KENDRA_ADMIN` 24 (all but that one), `NSS_ERP_SAKHA_ADMIN` 15, `NSS_ERP_ANCHALIKA_ADMIN`/`ZILLA_ADMIN`/`PATHA_CHAKRA_ADMIN`/`KENDRA_MAHILA_SANGHA_ADMIN` 14 each, `NSS_ERP_AUDITOR` 13, `NSS_ERP_REPORT_VIEWER` 7 (`CORRESPONDENCE_VIEW` to every role with rows; `CORRESPONDENCE_MANAGE` to the org-scoped admin roles). `NSS_ERP_ADVISORY_BOARD_ADMIN` has no rows — it is granted at runtime by `api/services/rbac_service.py::load_composite_grants` (§63) |

Numbered `01`/`02`/`03` reflects the DDL file numbering (`permission_master` before
`role_master` before `role_permission`), not execution readiness — dependency order at
execution time is `02_role_master.sql` and `01_permission_master.sql` first (either order,
no cross-dependency), then `03_role_permission.sql` last (depends on both).

## Design Notes

The 10 seeded roles match the frozen catalogue in SOL-ADMIN-004 §8.7
(updated to 10 roles / 7 scope levels). `NSS_ERP_PATHA_CHAKRA_ADMIN`
(scope `PATHA_CHAKRA`), `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN`
(scope `KENDRA_MAHILA_SANGHA`), and, later, `NSS_ERP_ADVISORY_BOARD_ADMIN`
(scope `ADVISORY_BOARD`, added 2026-10-09 as part of the §63 composite
auto-grant rule) were added to both the seed and the design doc
to align with the organizational hierarchy (see
`docs/03_Solution/modules/organization/04_organization_business_rules.md` §28) and the
`scope_level` CHECK
constraint on `role_master`. The 3 SYSTEM roles carry `scope_level = 'NSS-WIDE'`
(an explicit value, not NULL) — the CHECK constraint on `role_master` was widened
accordingly.

Role assignment is independent of governance position — see §8.7 for
the full rationale.
