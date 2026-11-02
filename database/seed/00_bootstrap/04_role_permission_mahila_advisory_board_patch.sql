-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 04_role_permission_mahila_advisory_board_patch.sql (idempotent patch)
-- Version: 1.0 (2026-10-30, owner decision)
-- =====================================================
-- 03_role_permission.sql is existence-gated by 02_build.sh / 02_build.ps1 /
-- render_build.sh (run_seed / Invoke-Seed skip a pre-existing role_permission
-- table), so rows added to it never reach an existing database. This file
-- carries them: applied with run_sql / Invoke-Sql right after the
-- role_permission seed, ON CONFLICT DO NOTHING (a no-op on a fresh build,
-- where the seed already inserted every row, and on every re-run).
--
-- Adds ONLY:
--   NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN  +ORGANIZATION_MANAGE, GOVERNANCE_MANAGE,
--                                       ATTENDANCE_MANAGE   (15 -> 18 rows)
--   NSS_ERP_ADVISORY_BOARD_ADMIN        GOVERNANCE_VIEW, GOVERNANCE_MANAGE,
--                                       MEMBERSHIP_VIEW,
--                                       CORRESPONDENCE_VIEW, CORRESPONDENCE_MANAGE,
--                                       ORGANIZATION_VIEW, FOUNDATION_VIEW,
--                                       PERSON_VIEW (owner decision 2026-10-30)
--                                       (0 -> 8 rows; the last four were added the
--                                       same day when the Advisory Board became an
--                                       organization type with its own correspondence
--                                       register — see 02_organization/
--                                       07_advisory_board_organization_patch.sql)
-- Never removes or re-activates anything. Keep in step with the matching rows
-- in 03_role_permission.sql.
-- =====================================================
WITH mappings (role_code, permission_code) AS (
    VALUES
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ORGANIZATION_MANAGE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'GOVERNANCE_MANAGE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ATTENDANCE_MANAGE'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'GOVERNANCE_MANAGE'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'CORRESPONDENCE_MANAGE'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'PERSON_VIEW')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN nss.role_master r       ON r.role_code = m.role_code AND r.is_active = TRUE
JOIN nss.permission_master p ON p.permission_code = m.permission_code AND p.is_active = TRUE
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
