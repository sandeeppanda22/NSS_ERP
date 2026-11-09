-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 05_assets_property_permissions_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-02) - Assets & Property (Module #22)
-- Authority: AP-074 (access via the centralized RBAC framework),
--            GDR-010 (Proposed - owner approval pending)
-- =====================================================
-- 01_permission_master.sql and 03_role_permission.sql are existence-gated by
-- 02_build.sh / 02_build.ps1 / render_build.sh, so rows added to them never
-- reach an existing database. This single file carries the module's RBAC
-- (it is the only place these rows live): applied with run_sql / Invoke-Sql
-- right after the 04 patch, INSERT ... ON CONFLICT DO NOTHING. Never removes
-- or re-activates anything (withdrawals are the 06 revoke patch's job).
--
-- Permissions (2):  ASSET_VIEW, ASSET_MANAGE   (28 -> 30)
--
-- Grants (12 rows; role_permission 166 -> 178). Owner decisions 2026-11-02
-- (GDR-010): ASSET_MANAGE is held only by the roles that run PHYSICAL
-- organizations or the whole system; Anchalika / Zilla admins are VIEW-ONLY
-- (they see the physical organizations beneath them through the ordinary
-- admin-scope rule but cannot change anything); the Mahila admin has no
-- Assets & Property access at all. Reads and writes are bounded server-side by
-- admin scope on the CURRENT CUSTODIAN organization, so a grant carries no
-- global reach by itself:
--   NSS_ERP_ADMIN / NSS_ERP_KENDRA_ADMIN        VIEW + MANAGE (global reach;
--       Kendra Sangha is custodian of all Nilachala Kutir / Smruti Mandir /
--       Sikshya Kendra property, AP-049)
--   NSS_ERP_SAKHA_ADMIN                         VIEW + MANAGE (Sakha office-
--       bearers function as custodians, AP-020)
--   NSS_ERP_PATHA_CHAKRA_ADMIN                  VIEW + MANAGE (subtree)
--   NSS_ERP_ANCHALIKA_ADMIN / ZILLA_ADMIN       VIEW only (subtree)
--   NSS_ERP_AUDITOR / NSS_ERP_REPORT_VIEWER     VIEW only
-- Deliberately NOT granted: NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN (owner
-- decision 2026-11-02), NSS_ERP_ATTENDANCE_MARKER (single-purpose role),
-- NSS_ERP_ADVISORY_BOARD_ADMIN (no property/asset provision for the Advisory
-- Board in the source; least privilege - owner decision needed, see GDR-010).
-- A database that already ran the ORIGINAL 16-row version of this patch has
-- the 4 now-withdrawn grants (Mahila VIEW + MANAGE, Anchalika MANAGE, Zilla
-- MANAGE) deactivated by 06_assets_property_permissions_revoke_patch.sql.
-- =====================================================

INSERT INTO nss.permission_master
    (permission_code, permission_name, module_code, description, display_order)
VALUES
    ('ASSET_VIEW',
     'View Assets & Property',
     'ASSET',
     'Read-only access to properties, assets, custodianship history, statutory records, '
     'maintenance records and attached documents whose CURRENT custodian organization '
     'falls within the actor''s admin scope.',
     29),
    ('ASSET_MANAGE',
     'Manage Assets & Property',
     'ASSET',
     'Register and edit properties and assets, record lifecycle events, assign/transfer '
     'custodianship, and record statutory obligations, maintenance and document links '
     'for records whose CURRENT custodian organization falls within the actor''s admin '
     'scope. Acquisition/disposal APPROVAL stays with Governance and payments with '
     'Finance (AP-025/045/039). A record with no custodian is manageable only by '
     'NSS-wide administrators.',
     30)
ON CONFLICT (permission_code) DO NOTHING;

WITH mappings (role_code, permission_code) AS (
    VALUES
    ('NSS_ERP_ADMIN', 'ASSET_VIEW'),
    ('NSS_ERP_ADMIN', 'ASSET_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ASSET_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'ASSET_MANAGE'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'ASSET_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'ASSET_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'ASSET_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'ASSET_MANAGE'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'ASSET_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'ASSET_MANAGE'),
    ('NSS_ERP_AUDITOR', 'ASSET_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'ASSET_VIEW')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN nss.role_master r       ON r.role_code = m.role_code AND r.is_active = TRUE
JOIN nss.permission_master p ON p.permission_code = m.permission_code AND p.is_active = TRUE
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
