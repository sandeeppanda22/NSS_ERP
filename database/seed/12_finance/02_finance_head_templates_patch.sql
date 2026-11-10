-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 02_finance_head_templates_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-10)
-- Authority: owner decision 2026-11-10 (customizable finance heads with Kendra
--            templates); SOL-FIN-004 §10.5 (the former fixed category list,
--            whose 12 codes are kept verbatim as the starting templates).
-- =====================================================
-- Kendra-published TEMPLATE heads (organization_pk NULL). A Sangha adopts them into
-- its own catalogue (POST /finance/heads/adopt-templates) and then renames, switches
-- off or adds heads of its own. ON CONFLICT DO NOTHING: a re-run never overwrites
-- a template an administrator has since edited. Runs after Phase 11i DDL and BEFORE
-- ddl/14_finance/12_finance_heads_patch.sql (which maps old categories onto these).
-- =====================================================

INSERT INTO nss.finance_head
    (organization_pk, head_code, head_name, description, direction, is_restricted, restriction_purpose,
     required_fund_type, is_pranami, display_order)
VALUES
    (NULL, 'MEMBERSHIP_SUBSCRIPTION', 'Membership subscription', 'Subscription paid by a member.', 'INCOME', FALSE, NULL, NULL, FALSE, 10),
    (NULL, 'PRANAMI_ANNUAL',          'Annual Pranami',           'Annual Pranami (Bye-Law Section F[A](ii)).', 'INCOME', FALSE, NULL, NULL, TRUE, 20),
    (NULL, 'PRANAMI_SPECIAL',         'Special Pranami',          'Special Pranami.', 'INCOME', FALSE, NULL, NULL, TRUE, 30),
    (NULL, 'PRANAMI_SINKING_FUND',    'Pranami to Sinking Fund',  'Special Pranami that builds a Sakha''s Sinking Fund, held under the Kendra (FIN-BR-023/024).', 'INCOME', FALSE, NULL, 'SINKING_FUND', TRUE, 40),
    (NULL, 'DONATION_GENERAL',        'General donation',         'Donation with no stated purpose.', 'INCOME', FALSE, NULL, NULL, FALSE, 50),
    (NULL, 'DONATION_SPECIFIC_PURPOSE','Specific-purpose donation','Donation given for a stated purpose; spendable only for that purpose (FIN-BR-019).', 'INCOME', TRUE, 'The purpose stated by the donor (FIN-BR-019).', NULL, FALSE, 60),
    (NULL, 'GRANT',                   'Grant',                    'Grant received (for example Kendra to Mahila Sangha, FIN-BR-028).', 'INCOME', FALSE, NULL, NULL, FALSE, 70),
    (NULL, 'PUBLICATION_INCOME',      'Publication income',       'Publication proceeds, kept separate (FIN-BR-022).', 'INCOME', TRUE, 'Satsikshya Bistar, in consultation with the Parichalak (FIN-BR-022).', NULL, FALSE, 80),
    (NULL, 'PROPERTY_INCOME',         'Property income',          'Income from property.', 'INCOME', FALSE, NULL, NULL, FALSE, 90),
    (NULL, 'MISCELLANEOUS_INCOME',    'Miscellaneous income',     'Other income.', 'INCOME', FALSE, NULL, NULL, FALSE, 100),
    (NULL, 'EXPENSE_GENERAL',         'General expense',          'Expense from unrestricted money.', 'EXPENSE', FALSE, NULL, NULL, FALSE, 110),
    (NULL, 'EXPENSE_RESTRICTED',      'Restricted expense',       'Expense from a restricted fund, only for its stated purpose (FIN-BR-021).', 'EXPENSE', TRUE, 'Only for the purpose of the restricted fund it is paid from (FIN-BR-021).', NULL, FALSE, 120)
ON CONFLICT (head_code) WHERE organization_pk IS NULL DO NOTHING;
