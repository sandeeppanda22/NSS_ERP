-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 07_sinking_reimbursement_patch.sql (idempotent patch)
-- Version: 1.0
-- Authority: Bye-Law C(i)(2)(xviii); business rule FIN-BR-026; owner request 2026-11-24.
-- =====================================================
-- What the Sinking Fund reimbursement needs besides its two tables (run_sql on every build, ON CONFLICT DO NOTHING, so an
-- admin's edit survives): the reference number sequence (SRB), the Kendra template head the Sakha's payment is booked on (income,
-- only into a SINKING_FUND), and the Bye-Law purpose a take-over expenditure is paid for. Runs after the Finance tables.
-- =====================================================

INSERT INTO nss.id_sequence_master (sequence_code, sequence_name, prefix, current_value, padding_length)
VALUES ('SINKING_REIMBURSEMENT', 'Sinking Fund Reimbursement Reference', 'SRB', 0, 0)
ON CONFLICT DO NOTHING;

INSERT INTO nss.finance_head
    (organization_pk, head_code, head_name, description, direction, is_restricted, restriction_purpose,
     required_fund_type, is_pranami, display_order)
VALUES
    (NULL, 'SINKING_REIMBURSEMENT', 'Sinking Fund reimbursement',
     'A Sakha repaying what the Kendra spent from its Sinking Fund while temporarily taking over the Sakha''s seva and pujas (Bye-Law C(i)(2)(xviii), FIN-BR-026).',
     'INCOME', FALSE, NULL, 'SINKING_FUND', FALSE, 45)
ON CONFLICT (head_code) WHERE organization_pk IS NULL DO NOTHING;

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, 'KENDRA_SAKHA_TAKEOVER',
       'Temporary take-over of a Sakha''s seva and pujas, reimbursed by the Sakha (C(i)(2)(xviii))', 55
  FROM nss.master_category mc
 WHERE mc.category_code = 'DISBURSEMENT_PURPOSE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;
