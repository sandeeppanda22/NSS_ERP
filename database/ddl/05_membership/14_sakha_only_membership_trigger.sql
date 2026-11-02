-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 14_sakha_only_membership_trigger.sql
-- Purpose: Enforces MBR-038A — a Member's organizational
--          association (sangha_sevi.organization_pk and
--          membership_sakha_affiliation.organization_pk)
--          must reference an organization of a Sakha-like
--          type (SAKHA_SANGHA or SAKHA_ASANA — owner
--          2026-10-31, via nss.fn_is_sakha_like_org_type from
--          02_organization/10_sakha_like_org_type_function.sql). The sole exception is the single
--          reserved system/bootstrap account
--          (sangha_sevi.is_system_account = TRUE), which
--          may reference the apex KENDRA directly.
-- Depends: 01_sangha_sevi.sql, 06_membership_sakha_affiliation.sql,
--          02_organization/03_organization.sql,
--          01_foundation/08_master_data.sql
-- Version: 1.1 (2026-10-31: SAKHA_ASANA accepted; DROP TRIGGER IF EXISTS
--          added so the file re-runs cleanly via run_sql)
-- Authority: MBR-038A
-- Owner: NSS_ERP_ADMIN
-- Note: This is a cross-table business rule (joins to
--       master_data/organization) and therefore cannot be
--       expressed as a single-table CHECK constraint — it
--       requires a BEFORE INSERT/UPDATE trigger. Mirrored
--       by API-layer validation (defense in depth).
-- =====================================================

-- ── Trigger function: sangha_sevi ──────────────────────

CREATE OR REPLACE FUNCTION nss.fn_enforce_sakha_only_sangha_sevi()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_org_type_code VARCHAR(50);
BEGIN
    -- System account is exempt (MBR-038A single exception).
    IF NEW.is_system_account = TRUE THEN
        RETURN NEW;
    END IF;

    SELECT md.value_code
    INTO v_org_type_code
    FROM nss.organization o
    JOIN nss.master_data md
        ON md.master_data_pk = o.organization_type_master_data_pk
    WHERE o.organization_pk = NEW.organization_pk;

    IF NOT nss.fn_is_sakha_like_org_type(v_org_type_code) THEN
        RAISE EXCEPTION
            'MBR-038A violation: sangha_sevi.organization_pk must reference a Sakha organization (SAKHA_SANGHA or SAKHA_ASANA) (found type: %). Only the reserved system account (is_system_account = TRUE) may reference a non-Sakha organization.',
            COALESCE(v_org_type_code, 'UNKNOWN')
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_sakha_only_sangha_sevi ON nss.sangha_sevi;
CREATE TRIGGER trg_enforce_sakha_only_sangha_sevi
    BEFORE INSERT OR UPDATE OF organization_pk, is_system_account
    ON nss.sangha_sevi
    FOR EACH ROW
    EXECUTE FUNCTION nss.fn_enforce_sakha_only_sangha_sevi();

-- ── Trigger function: membership_sakha_affiliation ─────

CREATE OR REPLACE FUNCTION nss.fn_enforce_sakha_only_affiliation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_org_type_code   VARCHAR(50);
    v_is_system_acct  BOOLEAN;
BEGIN
    SELECT ss.is_system_account
    INTO v_is_system_acct
    FROM nss.sangha_sevi ss
    WHERE ss.sangha_sevi_pk = NEW.sangha_sevi_pk;

    -- System account is exempt (MBR-038A single exception).
    IF v_is_system_acct = TRUE THEN
        RETURN NEW;
    END IF;

    SELECT md.value_code
    INTO v_org_type_code
    FROM nss.organization o
    JOIN nss.master_data md
        ON md.master_data_pk = o.organization_type_master_data_pk
    WHERE o.organization_pk = NEW.organization_pk;

    IF NOT nss.fn_is_sakha_like_org_type(v_org_type_code) THEN
        RAISE EXCEPTION
            'MBR-038A violation: membership_sakha_affiliation.organization_pk must reference a Sakha organization (SAKHA_SANGHA or SAKHA_ASANA) (found type: %). Only the reserved system account (sangha_sevi.is_system_account = TRUE) may reference a non-Sakha organization.',
            COALESCE(v_org_type_code, 'UNKNOWN')
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_sakha_only_affiliation ON nss.membership_sakha_affiliation;
CREATE TRIGGER trg_enforce_sakha_only_affiliation
    BEFORE INSERT OR UPDATE OF organization_pk, sangha_sevi_pk
    ON nss.membership_sakha_affiliation
    FOR EACH ROW
    EXECUTE FUNCTION nss.fn_enforce_sakha_only_affiliation();
