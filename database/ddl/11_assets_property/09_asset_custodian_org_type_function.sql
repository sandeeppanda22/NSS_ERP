-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 09_asset_custodian_org_type_function.sql (idempotent: CREATE OR REPLACE + DROP/CREATE TRIGGER)
-- Not a table - run with run_sql / Invoke-Sql on every build, after
-- 08_assets_property_guards.sql (and after the Phase 3
-- 10_sakha_like_org_type_function.sql it calls).
-- Version: 1.0 (2026-11-02)
-- Authority: owner rule 2026-11-02, GDR-010 §2C; AP-014 / AP-020;
--            SOL-AP-005 §9 (custodian organization).
--
-- THE single SQL definition of "organization types that may hold property /
-- assets". NSS has CONCEPTUAL organizations (Zilla / Anchalika Sangha -
-- administrative groupings with no premises) and PHYSICAL ones (Sakha incl.
-- Sakha Asana, Patha Chakra, Kendra, Nilachala Kutira, Smruti Mandira).
-- Property and assets are HELD only by physical organizations; wing
-- organizations (Kumari, Sevak, local/central Mahila Sangha, Paribarik) and the
-- Advisory Board organization are not custodians.
--   Python counterpart: api/helpers.py::ASSET_CUSTODIAN_ORG_TYPES
--   JS counterpart:     NSS.ASSET_CUSTODIAN_ORG_TYPES (nss-config.js)
-- The Sakha pair is NOT repeated here: it comes from
-- nss.fn_is_sakha_like_org_type().
--
-- nss.fn_custodianship_custodian_guard()  BEFORE INSERT OR UPDATE OF
--   custodian_organization_pk ON nss.custodianship
--   - a custodianship can never be stored (or re-pointed) onto a
--     non-eligible organization. The trigger is row-level and fires only for
--     new/changed rows: CREATE TRIGGER does not scan or validate existing
--     rows, so pre-existing custodianships on a non-eligible organization are
--     left untouched (03_validate reports them as a WARN). Closing such a row
--     (UPDATE of status / effective_to only) is not blocked.
--   - raises ERRCODE check_violation so the global psycopg2.IntegrityError
--     handler maps it to 422 rather than 500.
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_is_asset_custodian_org_type(p_org_type_code TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT COALESCE(
        nss.fn_is_sakha_like_org_type(p_org_type_code)
        OR p_org_type_code IN ('PATHA_CHAKRA', 'KENDRA', 'NILACHALA_KUTIRA', 'SMRUTI_MANDIRA'),
        FALSE);
$$;


CREATE OR REPLACE FUNCTION nss.fn_custodianship_custodian_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_org_type_code TEXT;
BEGIN
    SELECT md.value_code
    INTO v_org_type_code
    FROM nss.organization o
    JOIN nss.master_data md
        ON md.master_data_pk = o.organization_type_master_data_pk
    WHERE o.organization_pk = NEW.custodian_organization_pk;

    IF NOT nss.fn_is_asset_custodian_org_type(v_org_type_code) THEN
        RAISE EXCEPTION 'GDR-010 violation: organization type % cannot hold property or assets; only physical organizations (Sakha, Patha Chakra, Kendra, Nilachala Kutira, Smruti Mandira) can be custodians.',
            COALESCE(v_org_type_code, '(unknown)')
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_custodianship_custodian_guard ON nss.custodianship;
CREATE TRIGGER trg_custodianship_custodian_guard
    BEFORE INSERT OR UPDATE OF custodian_organization_pk ON nss.custodianship
    FOR EACH ROW EXECUTE FUNCTION nss.fn_custodianship_custodian_guard();
