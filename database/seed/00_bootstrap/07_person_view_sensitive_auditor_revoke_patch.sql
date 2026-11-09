-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 07_person_view_sensitive_auditor_revoke_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-04) - Aadhaar capture + sensitive-field gating
-- Authority: PER-BR-080/081, GDR-011 (Proposed - owner approval pending);
--            owner decision 2026-11-04: PERSON_VIEW_SENSITIVE now gates the
--            Aadhaar last-4 and the full-number reveal, and the NSS_ERP_AUDITOR
--            role does NOT hold it (an auditor reads the audit trail, not
--            identity numbers).
-- =====================================================
-- 03_role_permission.sql (existence-gated, unchanged) still seeds the row
--     NSS_ERP_AUDITOR  PERSON_VIEW_SENSITIVE
-- on a fresh build; this patch then withdraws it, the same arrangement as
-- 06_assets_property_permissions_revoke_patch.sql. role_permission therefore
-- keeps 178 rows, 177 of them active. NSS_ERP_ADMIN and NSS_ERP_KENDRA_ADMIN
-- keep their grants.
--
-- Convention: the row is SOFT-DELETED (is_active = FALSE, deleted_at = NOW()),
-- never DELETEd (history is never hard-deleted; nss_db_writer has no DELETE;
-- chk_role_permission_soft_delete). rbac_service filters rp.is_active = TRUE,
-- so the withdrawal applies as soon as permissions are next loaded. The audit
-- trigger records the UPDATE. Idempotent: only a still-active row is touched.
-- Never re-activates anything; re-granting would be a new owner decision and
-- an edit of this file.
-- =====================================================

UPDATE nss.role_permission rp
   SET is_active  = FALSE,
       deleted_at = NOW()
  FROM nss.role_master r, nss.permission_master p,
       (VALUES
           ('NSS_ERP_AUDITOR', 'PERSON_VIEW_SENSITIVE')
       ) AS withdrawn (role_code, permission_code)
 WHERE r.role_master_pk       = rp.role_master_pk
   AND p.permission_master_pk = rp.permission_master_pk
   AND r.role_code            = withdrawn.role_code
   AND p.permission_code      = withdrawn.permission_code
   AND rp.is_active           = TRUE;
