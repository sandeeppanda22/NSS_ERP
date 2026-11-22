-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 11_finance_admin_roles_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-22) - Finance (Tier 12)
-- Authority: owner decision 2026-11-22: scopes and funds - the books themselves - are set up by a FINANCE ADMINISTRATOR, and being an admin does
--            not make someone one by default. A finance administrator is (1) the seated Treasurer, President or Secretary of a Sakha, for
--            that Sakha (by seat, api/services/finance_approval.py::office_sakhas) or (2) an admin who has been GIVEN a Finance role - these two.
-- =====================================================
-- NSS_ERP_SAKHA_FINANCE_ADMIN   assigned (Assign role) at SAKHA scope: sets up one Sakha's scopes and funds; records and configures its finance.
-- NSS_ERP_KENDRA_FINANCE_ADMIN  assigned at KENDRA scope: the same for the Kendra (and, as the Kendra's reach covers them, the Sangha beneath it);
--                               it also carries FINANCE_APPROVE because the Kendra has no seat chain: its entries move by permission.
--                               HELD BY SEAT (api/services/rbac_service.py composite rules) by the Kendra Governing Body's TREASURER and SECRETARY, per the
--                               Bye-Law: the Treasurer is in charge of the Kendra's funds and keeps their accounts (REF-003-C(i)(7)(a)); the Secretary keeps
--                               all records, accounts and documents and prepares the draft annual budget (C(i)(5)(b),(e)); the funds are operated jointly by
--                               the Secretary and the Treasurer (REF-003-F[b]). The PRESIDENT only gives the written order for a disbursement (C(i)(7)(b)),
--                               recorded on the disbursement itself - he holds no finance role by seat.
-- Neither carries any ADMIN_* permission: a Finance role is not an admin role. The NSS ERP Administrator (super administrator) is a finance
-- administrator by role and needs nothing assigned. INSERT ... ON CONFLICT DO NOTHING; never removes or re-activates anything.
-- =====================================================

INSERT INTO nss.role_master (role_code, role_name, role_class, scope_level, description, display_order)
VALUES
    ('NSS_ERP_SAKHA_FINANCE_ADMIN',
     'Sakha Finance Administrator',
     'ORGANIZATIONAL',
     'SAKHA',
     'Sets up a Sakha''s financial scopes and funds, and views, records and configures its finance. Given by assignment; a Sakha''s seated '
     'Treasurer, President and Secretary are finance administrators of their Sakha by seat and need no assignment.',
     13),
    ('NSS_ERP_KENDRA_FINANCE_ADMIN',
     'Kendra Finance Administrator',
     'ORGANIZATIONAL',
     'KENDRA',
     'Sets up financial scopes and funds under the Kendra, and views, records, configures and approves its finance. Given by assignment.',
     14)
ON CONFLICT (role_code) DO NOTHING;

WITH mappings (role_code, permission_code) AS (
    VALUES
    ('NSS_ERP_SAKHA_FINANCE_ADMIN',  'FINANCE_VIEW'),
    ('NSS_ERP_SAKHA_FINANCE_ADMIN',  'FINANCE_MANAGE'),
    ('NSS_ERP_SAKHA_FINANCE_ADMIN',  'FINANCE_CONFIGURE'),
    ('NSS_ERP_KENDRA_FINANCE_ADMIN', 'FINANCE_VIEW'),
    ('NSS_ERP_KENDRA_FINANCE_ADMIN', 'FINANCE_MANAGE'),
    ('NSS_ERP_KENDRA_FINANCE_ADMIN', 'FINANCE_CONFIGURE'),
    ('NSS_ERP_KENDRA_FINANCE_ADMIN', 'FINANCE_APPROVE')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN nss.role_master r       ON r.role_code = m.role_code AND r.is_active = TRUE
JOIN nss.permission_master p ON p.permission_code = m.permission_code AND p.is_active = TRUE
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
