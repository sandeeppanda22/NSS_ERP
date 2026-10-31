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
| `03_role_permission.sql` | Populated — 166 role-to-permission mappings: `NSS_ERP_ADMIN` 27 (all permissions, including `FOUNDATION_CALENDAR_MANAGE`, which no other role holds), `NSS_ERP_KENDRA_ADMIN` 26 (all but that one), `NSS_ERP_SAKHA_ADMIN` 18, `NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN` 18 (Kendra's operational set minus the 8 `ADMIN_*`/`AUDIT_VIEW`/`FOUNDATION_MANAGE`/`PERSON_VIEW_SENSITIVE` permissions; reach limited to every `MAHILA_SANGHA` organization + subtree), `NSS_ERP_ANCHALIKA_ADMIN`/`ZILLA_ADMIN`/`PATHA_CHAKRA_ADMIN` 15 each, `NSS_ERP_AUDITOR` 14, `NSS_ERP_REPORT_VIEWER` 8, `NSS_ERP_ATTENDANCE_MARKER` 2, `NSS_ERP_ADVISORY_BOARD_ADMIN` 8 (`GOVERNANCE_VIEW`, `GOVERNANCE_MANAGE` confined server-side to Advisory Board bodies, `MEMBERSHIP_VIEW` for the officer search, plus `CORRESPONDENCE_VIEW`/`_MANAGE`, `ORGANIZATION_VIEW`, `FOUNDATION_VIEW` for the Advisory Board organization's own correspondence register, and `PERSON_VIEW` (owner 2026-10-30; correspondence person pickers)); the role is additionally auto-granted at runtime to the Advisory Board President/Secretary by `rbac_service.load_composite_grants` (§63) |
| `04_role_permission_mahila_advisory_board_patch.sql` | Idempotent patch (`ON CONFLICT DO NOTHING`), run with `run_sql` / `Invoke-Sql` right after the `role_permission` seed in `02_build.sh`, `02_build.ps1` and `render_build.sh`. The seed is existence-gated and never re-runs, so this carries the 2026-10-30 grants (Mahila admin +`ORGANIZATION_MANAGE`/`GOVERNANCE_MANAGE`/`ATTENDANCE_MANAGE`; Advisory Board admin's 8 rows) to existing databases; a no-op on a fresh build |

Numbered `01`/`02`/`03` reflects the DDL file numbering (`permission_master` before
`role_master` before `role_permission`), not execution readiness — dependency order at
execution time is `02_role_master.sql` and `01_permission_master.sql` first (either order,
no cross-dependency), then `03_role_permission.sql` last (depends on both).

## Design Notes

The 11 seeded roles match the frozen catalogue in SOL-ADMIN-004 §8.7
(updated to 11 roles / 8 scope levels incl. `NSS_ERP_ATTENDANCE_MARKER`, 2026-10-27). `NSS_ERP_PATHA_CHAKRA_ADMIN`
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
