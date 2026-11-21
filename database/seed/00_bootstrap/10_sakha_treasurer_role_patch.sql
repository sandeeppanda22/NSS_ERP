-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 10_sakha_treasurer_role_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-20) - Finance (Tier 12)
-- Authority: owner decision 2026-11-20: "let the Treasurer be the admin for all financial transactions of their scope".
-- =====================================================
-- Role NSS_ERP_SAKHA_TREASURER: held automatically (the §63 composite rule in api/services/rbac_service.py, derived live from the seat -
-- nothing is stored per person) by whoever holds the TREASURER seat of a Sakha's Governing Body, substantively or as acting cover. Its
-- admin scope is that one Sakha (and what sits under it). It carries FINANCE ONLY:
--   FINANCE_VIEW       read everything of the Sakha's finance
--   FINANCE_MANAGE     record receipts, payments, transactions and transfers, ask for UPI payments, link members
--   FINANCE_CONFIGURE  heads, contributions, events and receiving accounts (owner 2026-11-20). The controls that bind the Treasurer THEMSELVES stay out
--                      of reach BY SEAT, not by permission: the API refuses the seated Treasurer a change of the Treasurer's approval limit
--                      (PUT /approval-policy, a head's treasurer_limit) and of a head's "needs no approval" flag
--                      (api/services/finance_approval.py::require_not_the_treasurer) - the Sakha's President / Secretary admin sets those.
-- It deliberately does NOT carry:
--   FINANCE_APPROVE    approvals of a Sakha's entries stay with the seats (the Treasurer, then the President - the chain in
--                      api/services/finance_approval.py, never a permission); recording / configuring / approving stay separate (FIN-BR-040).
-- It reaches no other module: a Treasurer is not thereby an administrator of members, accounts or organizations.
-- INSERT ... ON CONFLICT DO NOTHING; never removes or re-activates anything.
-- =====================================================

INSERT INTO nss.role_master (role_code, role_name, role_class, scope_level, description, display_order)
VALUES
    ('NSS_ERP_SAKHA_TREASURER',
     'Sakha Treasurer',
     'ORGANIZATIONAL',
     'SAKHA',
     'Finance recorder of a Sakha: held automatically by the seated (or acting) Treasurer of the Sakha''s Governing Body. Views and records '
     'the Sakha''s finance; configuration is the Sakha admin''s and approvals stay with the Treasurer and President seats. Carries no other access.',
     12)
ON CONFLICT (role_code) DO NOTHING;

WITH mappings (role_code, permission_code) AS (
    VALUES
    ('NSS_ERP_SAKHA_TREASURER', 'FINANCE_VIEW'),
    ('NSS_ERP_SAKHA_TREASURER', 'FINANCE_MANAGE'),
    ('NSS_ERP_SAKHA_TREASURER', 'FINANCE_CONFIGURE')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN nss.role_master r       ON r.role_code = m.role_code AND r.is_active = TRUE
JOIN nss.permission_master p ON p.permission_code = m.permission_code AND p.is_active = TRUE
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
