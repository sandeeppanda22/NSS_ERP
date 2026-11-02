-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 10_sakha_like_org_type_function.sql
-- Purpose: THE single SQL definition of "Sakha-like organization types".
--          Owner decision 2026-10-31: a Sakha Asana (SAKHA_ASANA) is a
--          Sakha Sangha without its own building and counts as a full
--          Sakha everywhere (same SAKHA_GOVERNING_BODY, President,
--          members, attendance, correspondence, Advisory Board
--          representation). DB triggers/functions that ask "is this a
--          Sakha?" call this function instead of hard-coding
--          'SAKHA_SANGHA':
--            - 05_membership/14_sakha_only_membership_trigger.sql (MBR-038A)
--            - 08_governance/12_governance_seat_limits.sql
--              (Advisory Board one seat per Sakha)
--          Python counterpart: api/helpers.py::SAKHA_LIKE_ORG_TYPES;
--          JS counterpart: NSS.SAKHA_LIKE_ORG_TYPES (nss-config.js).
-- Depends: nothing (pure function over the type code).
-- Version: 1.0 (2026-10-31)
-- Idempotent: CREATE OR REPLACE; wired via run_sql in Phase 3 of
--          02_build.sh/02_build.ps1/render_build.sh, before the
--          membership and governance trigger files that call it.
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_is_sakha_like_org_type(p_org_type_code TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT COALESCE(p_org_type_code IN ('SAKHA_SANGHA', 'SAKHA_ASANA'), FALSE);
$$;
