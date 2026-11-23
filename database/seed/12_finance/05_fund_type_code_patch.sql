-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 05_fund_type_code_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-23)
-- Authority: owner request 2026-11-22/23: a fund's code is made automatically from the Sangha's code + the fund TYPE's code (EKM-GEN), and the
--            type codes live with the other master data ("add these codes with other master data"). Master Data Driven (frozen principle).
-- =====================================================
-- Master category FUND_TYPE_CODE: ONE row per fund type (nss.fund_master.fund_type, its DDL CHECK list):
--     value_code   the SHORT CODE, 3-5 unique letters (the database guarantees it is unique within the category)
--     value_name   the fund type's display name
--     description  the fund type it stands for, exactly as stored in fund_master.fund_type (GENERAL, SINKING_FUND, ...)  <- how the API finds it
-- A new fund type needs a row here before a fund of that type can be created without typing its code. Run with run_sql / Invoke-Sql on every
-- build; ON CONFLICT DO NOTHING, so a re-run never overwrites a code an admin has edited or deactivated. Must run AFTER the Finance tables.
-- =====================================================

INSERT INTO nss.master_category (category_code, category_name, description, display_order)
VALUES
    ('FUND_TYPE_CODE', 'Fund Type Code',
     'Short code (3-5 letters) of each fund type, the second half of an automatic fund code: <Sangha code>-<type code>, e.g. EKM-GEN. The description holds the fund type it stands for.', 29)
ON CONFLICT (category_code) DO NOTHING;

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, description, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.fund_type, v.display_order
FROM nss.master_category mc
JOIN (VALUES
    ('GEN',  'General fund',                 'GENERAL',                  10),
    ('SINK', 'Sinking Fund',                 'SINKING_FUND',             20),
    ('PUB',  'Publication fund',             'PUBLICATION',              30),
    ('SPEC', 'Specific-purpose fund',        'SPECIFIC_PURPOSE',         40),
    ('SUBS', 'Membership subscription fund', 'MEMBERSHIP_SUBSCRIPTION',  50),
    ('PRAN', 'Pranami fund',                 'PRANAMI',                  60),
    ('DON',  'Donation fund',                'DONATION',                 70),
    ('GRNT', 'Grant fund',                   'GRANT',                    80),
    ('PROP', 'Property income fund',         'PROPERTY_INCOME',          90),
    ('MISC', 'Miscellaneous fund',           'MISCELLANEOUS',           100)
) AS v (value_code, value_name, fund_type, display_order)
  ON mc.category_code = 'FUND_TYPE_CODE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;
