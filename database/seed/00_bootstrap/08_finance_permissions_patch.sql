-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 08_finance_permissions_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-10) - Finance (Tier 12)
-- Authority: SOL-FIN-003 FIN-BR-038..046 (financial authorization; the exact
--            matrix is PENDING for non-Kendra/Mahila scopes), lifecycle §28
--            (Finance uses the common RBAC framework, no parallel roles).
-- =====================================================
-- Existence-gated seeds never reach an existing DB, so this single file carries
-- the module's RBAC (INSERT ... ON CONFLICT DO NOTHING; never removes or
-- re-activates anything).
--
-- Permissions (3): FINANCE_VIEW, FINANCE_MANAGE, FINANCE_APPROVE
--   FIN-BR-040 forbids collapsing scheme approval, the President's order and
--   the Treasurer's disbursement into one generic approval, so recording
--   (MANAGE) and approving/posting/executing (APPROVE) are separate grants;
--   the API additionally refuses to let the maker approve their own record.
--
-- Grants (owner decision 2026-11-22: "all finance related should come from finance roles"): only the NSS ERP Administrator (VIEW + MANAGE +
-- APPROVE) and the two system read-only roles (AUDITOR / REPORT_VIEWER: VIEW). The Kendra, Sakha, Patha Chakra, Anchalika and Zilla ADMIN roles
-- carry NO finance permission - finance comes from the finance roles (11_finance_admin_roles_patch.sql, 10_sakha_treasurer_role_patch.sql), held by
-- assignment or by the Treasurer / President / Secretary seat. Databases built before this decision had those grants; 12_finance_permissions_revoke_
-- patch.sql withdraws them.
-- Deliberately NOT granted: Mahila admin, Advisory Board admin, attendance
-- marker (least privilege; Mahila funds have their own bye-law clause 7 -
-- owner decision needed). Reads/writes are bounded server-side by admin scope
-- on the Financial Scope's organization; a scope with no organization is
-- manageable only by NSS-wide administrators.
-- =====================================================

INSERT INTO nss.permission_master
    (permission_code, permission_name, module_code, description, display_order)
VALUES
    ('FINANCE_VIEW',
     'View Finance',
     'FINANCE',
     'Read-only access to financial years, scopes, funds, transactions, receipts, '
     'payments and transfers of Financial Scopes within the actor''s admin scope.',
     31),
    ('FINANCE_MANAGE',
     'Manage Finance',
     'FINANCE',
     'Create and edit financial scopes, funds, transactions, receipts, payments and '
     'transfers (drafts and submission) within the actor''s admin scope.',
     32),
    ('FINANCE_APPROVE',
     'Approve Finance',
     'FINANCE',
     'Approve, post, reject, execute and cancel financial transactions, payments and '
     'transfers, and open/close financial years. Never on the actor''s own record.',
     33)
ON CONFLICT (permission_code) DO NOTHING;

WITH mappings (role_code, permission_code) AS (
    VALUES
    ('NSS_ERP_ADMIN', 'FINANCE_VIEW'),
    ('NSS_ERP_ADMIN', 'FINANCE_MANAGE'),
    ('NSS_ERP_ADMIN', 'FINANCE_APPROVE'),
    ('NSS_ERP_AUDITOR', 'FINANCE_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'FINANCE_VIEW')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN nss.role_master r       ON r.role_code = m.role_code AND r.is_active = TRUE
JOIN nss.permission_master p ON p.permission_code = m.permission_code AND p.is_active = TRUE
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
