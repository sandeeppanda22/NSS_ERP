-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 09_finance_configure_permission_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-17) - Finance (Tier 12)
-- Authority: owner decision 2026-11-17: a Sakha admin must be able to set up what its Sakha collects, without being able to
--            approve any payment (recording / configuring / approving stay separate, FIN-BR-040).
-- =====================================================
-- Permission FINANCE_CONFIGURE: create and edit finance heads, contributions, events, receiving accounts and the Treasurer's
-- approval limits within the actor's admin scope. It approves NOTHING: moving a transaction, payment or transfer forward still
-- needs FINANCE_APPROVE (or, for a Sakha, the Treasurer / President seat).
-- Grants: NSS_ERP_ADMIN, NSS_ERP_KENDRA_ADMIN, NSS_ERP_SAKHA_ADMIN (the first two already approve; the Sakha admin gains
-- configuration only). INSERT ... ON CONFLICT DO NOTHING; never removes or re-activates anything.
-- =====================================================

INSERT INTO nss.permission_master
    (permission_code, permission_name, module_code, description, display_order)
VALUES
    ('FINANCE_CONFIGURE',
     'Configure Finance',
     'FINANCE',
     'Create and edit finance heads, contributions, events, receiving accounts and the Treasurer''s '
     'approval limits within the actor''s admin scope. Approves nothing.',
     34)
ON CONFLICT (permission_code) DO NOTHING;

WITH mappings (role_code, permission_code) AS (
    VALUES
    ('NSS_ERP_ADMIN', 'FINANCE_CONFIGURE'),
    ('NSS_ERP_KENDRA_ADMIN', 'FINANCE_CONFIGURE'),
    ('NSS_ERP_SAKHA_ADMIN', 'FINANCE_CONFIGURE')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN nss.role_master r       ON r.role_code = m.role_code AND r.is_active = TRUE
JOIN nss.permission_master p ON p.permission_code = m.permission_code AND p.is_active = TRUE
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
