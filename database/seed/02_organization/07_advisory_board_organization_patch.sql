-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 07_advisory_board_organization_patch.sql (idempotent patch)
-- Version: 1.0 (2026-10-30, owner decision: "Advisory Board should be an
--          org type" / "Advisory Board needs a correspondence register")
-- =====================================================
-- Adds, to an existing OR fresh database:
--   1. master_data ORGANIZATION_TYPE value ADVISORY_BOARD (the 14th type);
--   2. the one singleton organization of that type — 'Advisory Board',
--      organization_code 'ADB', short_code 'NSSAB', ACTIVE, parent = the Kendra
--      organization (located by TYPE, never by a hard-coded pk).
--
-- Why a patch and not only a seed edit: 02_master_data.sql and
-- 03_organization.sql are existence-gated by 02_build.sh / 02_build.ps1 /
-- render_build.sh (run_seed / Invoke-Seed skip a table that already exists),
-- so rows added to them never reach an existing database. This file is applied
-- with run_sql / Invoke-Sql right after the Phase 4 organization seeds and is a
-- no-op on every re-run. The type value is ALSO in 02_master_data.sql so the
-- seed stays the complete catalogue on a fresh build (same pairing as
-- 04_role_permission_mahila_advisory_board_patch.sql); the organization row
-- lives ONLY here (single source — it is not duplicated in 03_organization.sql).
--
-- short_code is seeded (3-5 uppercase alphanumerics, chk_organization_short_code)
-- because correspondence reference numbers are <short_code>/{IN|OUT}/<FY>/<seq>
-- (helpers.next_correspondence_reference_number), and a register organization
-- with no short_code cannot mint one or receive a dispatched inward counterpart.
-- No premises address, no organization_id (singletons carry none).
--
-- The Advisory Board GOVERNANCE BODY (body_master 'ADVISORY_BOARD',
-- organization_pk NULL) is deliberately NOT linked to this organization: the
-- §63 composite-grant rule and the Sakha-nomination logic depend on it staying
-- NULL-organization. This organization exists to own the correspondence register.
-- =====================================================

-- 1. ORGANIZATION_TYPE value ------------------------------------------------
INSERT INTO nss.master_data (master_category_pk, value_code, value_name, description, display_order)
SELECT mc.master_category_pk,
       'ADVISORY_BOARD',
       'Advisory Board',
       'Advisory Board — singleton organization under the Kendra that owns the Advisory Board''s correspondence register (the governance body of the same name is a separate NULL-organization record)',
       14
FROM nss.master_category mc
WHERE mc.category_code = 'ORGANIZATION_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- 2. The singleton organization ---------------------------------------------
INSERT INTO nss.organization
    (organization_name, organization_type_master_data_pk,
     status_master_data_pk, parent_organization_pk,
     organization_code, short_code)
SELECT
    'Advisory Board',
    ot.master_data_pk,
    os.master_data_pk,
    (SELECT k.organization_pk
       FROM nss.organization k
       JOIN nss.master_data kt ON kt.master_data_pk = k.organization_type_master_data_pk
      WHERE kt.value_code = 'KENDRA' AND k.is_active = TRUE
      ORDER BY k.created_at
      LIMIT 1),
    'ADB',
    'NSSAB'
FROM nss.master_data ot
JOIN nss.master_category mc_type
     ON mc_type.master_category_pk = ot.master_category_pk
CROSS JOIN nss.master_data os
JOIN nss.master_category mc_status
     ON mc_status.master_category_pk = os.master_category_pk
WHERE mc_type.category_code = 'ORGANIZATION_TYPE'
  AND ot.value_code = 'ADVISORY_BOARD'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code = 'ACTIVE'
  AND NOT EXISTS (
        SELECT 1
        FROM nss.organization x
        WHERE x.organization_type_master_data_pk = ot.master_data_pk
  )
ON CONFLICT (organization_code) DO NOTHING;
