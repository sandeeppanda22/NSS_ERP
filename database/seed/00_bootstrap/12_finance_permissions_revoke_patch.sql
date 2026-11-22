-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 12_finance_permissions_revoke_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-22) - Finance (Tier 12)
-- Authority: owner decision 2026-11-22: "all finance related should come from finance roles" - the Kendra, Sakha, Patha Chakra, Anchalika and Zilla
--            ADMIN roles no longer carry finance permissions. Finance comes from the finance roles (NSS_ERP_SAKHA_TREASURER, NSS_ERP_SAKHA_FINANCE_ADMIN,
--            NSS_ERP_KENDRA_FINANCE_ADMIN), held by assignment or, for a Sakha's / the Kendra's Treasurer, President and Secretary, by seat
--            (api/services/rbac_service.py composite rules).
-- =====================================================
-- The ORIGINAL 08_ / 09_ patches granted these 11 rows to admin roles; they now insert only the NSS ERP Administrator's and the read-only roles'. A FRESH
-- database never has the 11 (this patch is then a no-op); a database built earlier has them ACTIVE and this patch withdraws them.
--
-- Convention (as 06_assets_property_permissions_revoke_patch.sql): SOFT-DELETED (is_active = FALSE, deleted_at = NOW()), never DELETEd - history is
-- never hard-deleted and nss_db_writer has no DELETE. rbac_service filters rp.is_active = TRUE, so it takes effect when permissions are next loaded.
-- Idempotent (only active rows are touched). Never re-activates; the 08_/09_ patches' ON CONFLICT DO NOTHING cannot bring them back either.
-- Kept on purpose: NSS_ERP_ADMIN (the super administrator, all) and NSS_ERP_AUDITOR / NSS_ERP_REPORT_VIEWER (FINANCE_VIEW: read-only system roles).
-- =====================================================

UPDATE nss.role_permission rp
   SET is_active  = FALSE,
       deleted_at = NOW()
  FROM nss.role_master r, nss.permission_master p,
       (VALUES
           ('NSS_ERP_KENDRA_ADMIN',       'FINANCE_VIEW'),
           ('NSS_ERP_KENDRA_ADMIN',       'FINANCE_MANAGE'),
           ('NSS_ERP_KENDRA_ADMIN',       'FINANCE_APPROVE'),
           ('NSS_ERP_KENDRA_ADMIN',       'FINANCE_CONFIGURE'),
           ('NSS_ERP_SAKHA_ADMIN',        'FINANCE_VIEW'),
           ('NSS_ERP_SAKHA_ADMIN',        'FINANCE_MANAGE'),
           ('NSS_ERP_SAKHA_ADMIN',        'FINANCE_CONFIGURE'),
           ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'FINANCE_VIEW'),
           ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'FINANCE_MANAGE'),
           ('NSS_ERP_ANCHALIKA_ADMIN',    'FINANCE_VIEW'),
           ('NSS_ERP_ZILLA_ADMIN',        'FINANCE_VIEW')
       ) AS withdrawn (role_code, permission_code)
 WHERE r.role_master_pk       = rp.role_master_pk
   AND p.permission_master_pk = rp.permission_master_pk
   AND r.role_code            = withdrawn.role_code
   AND p.permission_code      = withdrawn.permission_code
   AND rp.is_active           = TRUE;
