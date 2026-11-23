-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 06_scope_type_code_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-23)
-- Authority: owner request 2026-11-23: "do the same for scope code and scope type" - a financial scope's code is made automatically from the Sangha's
--            code + the scope TYPE's code (EKM-ORG, EKM-EVT), the type codes being master data like the fund type codes (05_fund_type_code_patch.sql).
--            Master Data Driven (frozen principle).
-- =====================================================
-- Master category SCOPE_TYPE_CODE: ONE row per scope type (nss.financial_scope.scope_type, its DDL CHECK list):
--     value_code   the SHORT CODE, 3-5 unique letters (unique within the category by the database)
--     value_name   the scope type's display name
--     description  the scope type it stands for, exactly as stored in financial_scope.scope_type  <- how the API finds it
-- A new scope type needs a row here before a scope of that type can be created without typing its code. Run with run_sql / Invoke-Sql on every build;
-- ON CONFLICT DO NOTHING, so a re-run never overwrites a code an admin has edited or deactivated. Must run AFTER the Finance tables.
-- =====================================================

INSERT INTO nss.master_category (category_code, category_name, description, display_order)
VALUES
    ('SCOPE_TYPE_CODE', 'Scope Type Code',
     'Short code (3-5 letters) of each financial scope type, the second half of an automatic scope code: <Sangha code>-<type code>, e.g. EKM-ORG. The description holds the scope type it stands for.', 30)
ON CONFLICT (category_code) DO NOTHING;

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, description, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.scope_type, v.display_order
FROM nss.master_category mc
JOIN (VALUES
    ('ORG',  'Organization scope (a Sangha''s general finance)', 'ORGANIZATION',    10),
    ('EVT',  'Event scope (a festival or event)',                'EVENT',           20),
    ('SPL',  'Special-purpose scope',                            'SPECIAL_PURPOSE', 30),
    ('RSTR', 'Restricted-fund scope',                            'RESTRICTED_FUND', 40)
) AS v (value_code, value_name, scope_type, display_order)
  ON mc.category_code = 'SCOPE_TYPE_CODE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;
