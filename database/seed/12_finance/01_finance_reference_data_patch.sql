-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 01_finance_reference_data_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-10)
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §12.3, §18, §19),
--            owner decision 2026-11-10 (payment methods are master_data)
-- =====================================================
-- The Foundation seeds are existence-gated, so Finance carries its OWN
-- reference data here (applied with run_sql / Invoke-Sql on every build,
-- INSERT ... ON CONFLICT DO NOTHING: a re-run never overwrites a value an
-- admin has since renamed or deactivated). Must run AFTER Phase 11i (the
-- initial financial_year row).
--
-- Adds:
--   id_sequence_master   FINANCIAL_TRANSACTION (FTX), FINANCIAL_RECEIPT (RCT),
--                        FINANCIAL_PAYMENT (PAY), FINANCIAL_TRANSFER (FTR)
--                        -> FTX1, RCT1 ... Unpadded like P1 / SS1.
--   master_category      PAYMENT_METHOD (value list PENDING in SOL-FIN-004 §19;
--                        CANDIDATE set below, admin-extendable through
--                        POST /api/v1/foundation/master-data)
--   financial_year       the initial Financial Year 2026-27 (SOL-FIN-004 §18:
--                        at least one), status OPEN.
-- =====================================================

INSERT INTO nss.id_sequence_master
    (sequence_code, sequence_name, prefix, current_value, padding_length)
VALUES
    ('FINANCIAL_TRANSACTION', 'Financial Transaction Reference', 'FTX', 0, 0),
    ('FINANCIAL_RECEIPT',     'Financial Receipt Number',        'RCT', 0, 0),
    ('FINANCIAL_PAYMENT',     'Financial Payment Reference',     'PAY', 0, 0),
    ('FINANCIAL_TRANSFER',    'Financial Transfer Reference',    'FTR', 0, 0)
ON CONFLICT DO NOTHING;

INSERT INTO nss.master_category (category_code, category_name, description, display_order)
VALUES
    ('PAYMENT_METHOD', 'Payment Method',
     'How money was received or paid (SOL-FIN-004 §12.3 - value list PENDING; candidate set, admin-extendable; owner decision 2026-11-10)', 27)
ON CONFLICT (category_code) DO NOTHING;

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
JOIN (VALUES
    ('PAYMENT_METHOD', 'CASH',          'Cash',                         1),
    ('PAYMENT_METHOD', 'CHEQUE',        'Cheque',                       2),
    ('PAYMENT_METHOD', 'BANK_TRANSFER', 'Bank Transfer (NEFT/RTGS/IMPS)', 3),
    ('PAYMENT_METHOD', 'UPI',           'UPI',                          4),
    ('PAYMENT_METHOD', 'DEMAND_DRAFT',  'Demand Draft',                 5),
    ('PAYMENT_METHOD', 'OTHER',         'Other',                        6)
) AS v (category_code, value_code, value_name, display_order)
  ON v.category_code = mc.category_code
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

INSERT INTO nss.financial_year (year_code, start_date, end_date, status)
VALUES ('2026-27', DATE '2026-04-01', DATE '2027-03-31', 'OPEN')
ON CONFLICT (year_code) DO NOTHING;
