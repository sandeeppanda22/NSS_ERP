-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 06_assets_property_permissions_revoke_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-02) - Assets & Property (Module #22)
-- Authority: AP-074 (access via the centralized RBAC framework),
--            GDR-010 (Proposed - owner approval pending); owner decisions
--            2026-11-02: (1) the Mahila admin gets NO Assets & Property
--            access; (2) Anchalika / Zilla admins are VIEW-ONLY.
-- =====================================================
-- The ORIGINAL version of 05_assets_property_permissions_patch.sql granted 16
-- rows. Four of them were withdrawn by the owner:
--     NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN  ASSET_VIEW
--     NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN  ASSET_MANAGE
--     NSS_ERP_ANCHALIKA_ADMIN             ASSET_MANAGE
--     NSS_ERP_ZILLA_ADMIN                 ASSET_MANAGE
-- 05 now inserts only the remaining 12, so a FRESH database never has these 4
-- rows (this patch is then a no-op); a database that already ran the old 05
-- has them ACTIVE and this patch withdraws them.
--
-- Convention (role_permission DDL + 03_role_permission.sql header: "mapping is
-- immutable once created; deactivate via is_active"; the table has
-- chk_role_permission_soft_delete, nss_db_writer has no DELETE, history is
-- never hard-deleted): the rows are SOFT-DELETED (is_active = FALSE,
-- deleted_at = NOW()), never DELETEd. rbac_service already filters
-- rp.is_active = TRUE in both permission loaders, so the withdrawal takes
-- effect immediately (existing JWTs pick it up when permissions are next
-- loaded). The audit trigger (fn_audit_trigger) records the UPDATE.
-- Idempotent: only rows still active are touched; a second run changes nothing.
-- Never re-activates anything; re-granting one of these 4 later would mean a
-- new owner decision and an edit of both 05 and this file.
-- =====================================================

UPDATE nss.role_permission rp
   SET is_active  = FALSE,
       deleted_at = NOW()
  FROM nss.role_master r, nss.permission_master p,
       (VALUES
           ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ASSET_VIEW'),
           ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ASSET_MANAGE'),
           ('NSS_ERP_ANCHALIKA_ADMIN',            'ASSET_MANAGE'),
           ('NSS_ERP_ZILLA_ADMIN',                'ASSET_MANAGE')
       ) AS withdrawn (role_code, permission_code)
 WHERE r.role_master_pk       = rp.role_master_pk
   AND p.permission_master_pk = rp.permission_master_pk
   AND r.role_code            = withdrawn.role_code
   AND p.permission_code      = withdrawn.permission_code
   AND rp.is_active           = TRUE;
