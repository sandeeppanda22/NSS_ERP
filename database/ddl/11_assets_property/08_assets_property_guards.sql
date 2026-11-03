-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 08_assets_property_guards.sql (idempotent: CREATE OR REPLACE + DROP/CREATE TRIGGER)
-- Not a table - run with run_sql / Invoke-Sql on every build, after 01..07.
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            03_assets_property_lifecycle.md (§3-§6, AP-LIF-001..005),
--            04_assets_property_business_rules.md (AP-004..008, AP-017/018,
--            AP-046/047, AP-072), GDR-010
--
-- DB-level backstop for the rules the API (api/routers/assets_property.py)
-- enforces first. "Enforced in the API (and DB where cheap)":
--
--   nss.fn_ap_entity_guard()  BEFORE UPDATE on nss.property / nss.asset
--     - identifiers immutable (the PK and property_id / asset_id: AP-004..008)
--     - status transitions limited to SOL-AP-003 §3.2 / §4.2:
--         property: REGISTERED -> ACTIVE
--                   ACTIVE -> UNDER_MAINTENANCE | DISPOSED
--                   UNDER_MAINTENANCE -> ACTIVE | DISPOSED
--         asset:    REGISTERED -> IN_CUSTODY
--                   IN_CUSTODY -> UNDER_MAINTENANCE | RETIRED
--                   UNDER_MAINTENANCE -> IN_CUSTODY | RETIRED
--       DISPOSED / RETIRED are terminal (AP-046/047, AP-LIF-003);
--       UNDER_MAINTENANCE -> DISPOSED/RETIRED is AP-LIF-002.
--     - leaving REGISTERED needs at least one custodianship record
--       (AP-LIF-001)
--
--     - DISPOSED / RETIRED also CLOSE the active custodianship (owner decision
--       2026-11-03, GDR-010 §2F): the API ENDs it (end reason DISPOSED /
--       RETIRED) in the same transaction as the status change. Nothing here
--       needs to change for that: the custody-required check applies only
--       when LEAVING REGISTERED, and the custodianship guard below already
--       permits ACTIVE -> ENDED.
--
--   nss.fn_custodianship_terminal_guard()  BEFORE INSERT on nss.custodianship
--     - a DISPOSED property / RETIRED asset (AP-046/047) accepts no new
--       custodianship (assign / transfer are refused by the API too)
--
--   nss.fn_custodianship_guard()  BEFORE UPDATE on nss.custodianship
--     - ENDED rows are immutable: history is never overwritten (AP-018/072)
--     - the target (property/asset), custodian organization and
--       effective_from never change after creation
--     - status moves only ASSIGNED -> ACTIVE -> ENDED (SOL-AP-003 §5.2)
--
-- All violations raise ERRCODE check_violation so the global
-- psycopg2.IntegrityError handler maps them to 422 rather than 500.
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_ap_entity_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_has_custody BOOLEAN;
BEGIN
    IF TG_TABLE_NAME = 'property' THEN
        IF NEW.property_pk IS DISTINCT FROM OLD.property_pk
           OR NEW.property_id IS DISTINCT FROM OLD.property_id THEN
            RAISE EXCEPTION 'AP-005 violation: property identifiers are immutable.'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        IF NEW.asset_pk IS DISTINCT FROM OLD.asset_pk
           OR NEW.asset_id IS DISTINCT FROM OLD.asset_id THEN
            RAISE EXCEPTION 'AP-007 violation: asset identifiers are immutable.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT EXISTS (
            SELECT 1
            FROM (VALUES
                ('property', 'REGISTERED',        'ACTIVE'),
                ('property', 'ACTIVE',            'UNDER_MAINTENANCE'),
                ('property', 'ACTIVE',            'DISPOSED'),
                ('property', 'UNDER_MAINTENANCE', 'ACTIVE'),
                ('property', 'UNDER_MAINTENANCE', 'DISPOSED'),
                ('asset',    'REGISTERED',        'IN_CUSTODY'),
                ('asset',    'IN_CUSTODY',        'UNDER_MAINTENANCE'),
                ('asset',    'IN_CUSTODY',        'RETIRED'),
                ('asset',    'UNDER_MAINTENANCE', 'IN_CUSTODY'),
                ('asset',    'UNDER_MAINTENANCE', 'RETIRED')
            ) AS t (tbl, from_status, to_status)
            WHERE t.tbl = TG_TABLE_NAME
              AND t.from_status = OLD.status
              AND t.to_status = NEW.status
        ) THEN
            RAISE EXCEPTION 'SOL-AP-003 violation: % status % -> % is not a valid lifecycle transition.',
                TG_TABLE_NAME, OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;

        IF OLD.status = 'REGISTERED' THEN
            IF TG_TABLE_NAME = 'property' THEN
                SELECT EXISTS (
                    SELECT 1 FROM nss.custodianship c
                    WHERE c.property_pk = OLD.property_pk AND c.is_active = TRUE
                ) INTO v_has_custody;
            ELSE
                SELECT EXISTS (
                    SELECT 1 FROM nss.custodianship c
                    WHERE c.asset_pk = OLD.asset_pk AND c.is_active = TRUE
                ) INTO v_has_custody;
            END IF;
            IF NOT v_has_custody THEN
                RAISE EXCEPTION 'AP-LIF-001 violation: a % needs a custodianship record before leaving REGISTERED.',
                    TG_TABLE_NAME
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_property_guard ON nss.property;
CREATE TRIGGER trg_property_guard
    BEFORE UPDATE ON nss.property
    FOR EACH ROW EXECUTE FUNCTION nss.fn_ap_entity_guard();

DROP TRIGGER IF EXISTS trg_asset_guard ON nss.asset;
CREATE TRIGGER trg_asset_guard
    BEFORE UPDATE ON nss.asset
    FOR EACH ROW EXECUTE FUNCTION nss.fn_ap_entity_guard();


CREATE OR REPLACE FUNCTION nss.fn_custodianship_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'ENDED' THEN
        RAISE EXCEPTION 'AP-018 violation: an ENDED custodianship is history and cannot be modified.'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.property_pk IS DISTINCT FROM OLD.property_pk
       OR NEW.asset_pk IS DISTINCT FROM OLD.asset_pk
       OR NEW.custodian_organization_pk IS DISTINCT FROM OLD.custodian_organization_pk
       OR NEW.effective_from IS DISTINCT FROM OLD.effective_from THEN
        RAISE EXCEPTION 'AP-018 violation: custodianship target, custodian and effective_from are immutable; end it and open a new one.'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status
       AND NOT (
            (OLD.status = 'ASSIGNED' AND NEW.status = 'ACTIVE')
         OR (OLD.status = 'ACTIVE'   AND NEW.status = 'ENDED')
       ) THEN
        RAISE EXCEPTION 'SOL-AP-003 §5 violation: custodianship status % -> % is not valid.',
            OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_custodianship_guard ON nss.custodianship;
CREATE TRIGGER trg_custodianship_guard
    BEFORE UPDATE ON nss.custodianship
    FOR EACH ROW EXECUTE FUNCTION nss.fn_custodianship_guard();


CREATE OR REPLACE FUNCTION nss.fn_custodianship_terminal_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_status TEXT;
BEGIN
    IF NEW.property_pk IS NOT NULL THEN
        SELECT status INTO v_status FROM nss.property WHERE property_pk = NEW.property_pk;
        IF v_status = 'DISPOSED' THEN
            RAISE EXCEPTION 'AP-046 violation: a DISPOSED property accepts no new custodianship.'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.asset_pk IS NOT NULL THEN
        SELECT status INTO v_status FROM nss.asset WHERE asset_pk = NEW.asset_pk;
        IF v_status = 'RETIRED' THEN
            RAISE EXCEPTION 'AP-047 violation: a RETIRED asset accepts no new custodianship.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_custodianship_terminal_guard ON nss.custodianship;
CREATE TRIGGER trg_custodianship_terminal_guard
    BEFORE INSERT ON nss.custodianship
    FOR EACH ROW EXECUTE FUNCTION nss.fn_custodianship_terminal_guard();
