-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 08_organization_singleton_trigger.sql
-- Object: nss.fn_enforce_organization_singleton() +
--         trigger trg_enforce_organization_singleton on nss.organization
-- Depth: 2 (depends on organization, master_data)
-- Version: 2.0 (2026-10-30, owner decision; supersedes v1.0, which was
--          nss.fn_enforce_advisory_board_singleton() and covered only
--          ADVISORY_BOARD — that trigger/function are dropped below)
--
-- Purpose:
--   Owner decision 2026-10-30: these organizations are each SINGLE in NSS.
--   At most one ACTIVE organization may exist for each rule:
--     1. type KENDRA
--     2. type NILACHALA_KUTIRA
--     3. type SMRUTI_MANDIRA
--     4. type ADVISORY_BOARD  (code 'ADB'; rbac_service.
--        NULL_ORG_SCOPE_ORG_TYPE resolves the ADVISORY_BOARD admin scope to
--        "the" Advisory Board organization, so a second one would make that
--        scope ambiguous)
--     5. the central (NSS/Kendra) Mahila Sangha = type MAHILA_SANGHA whose
--        parent_organization_pk is an organization of type KENDRA.
--        MAHILA_SANGHA is ALSO the type of the many local per-Sakha Mahila
--        Sanghas (parent = a Sakha); those stay unrestricted — rule 5 only
--        looks at MAHILA_SANGHA rows whose parent is a KENDRA.
--
-- Fires on INSERT and on UPDATE OF organization_type_master_data_pk,
-- is_active, parent_organization_pk. Inside the function an UPDATE is only
-- checked when a relevant column ACTUALLY CHANGED (rules 1-4: type or
-- is_active; rule 5: type, is_active or parent), so unrelated updates — and
-- a row that is already part of a pre-existing duplicate — are never blocked
-- by it.
--
-- Safe on live data: creating the trigger never scans existing rows, so a
-- build/seed on a database that already holds a duplicate does not fail; only
-- a NEW offending write (a second active row inserted, or a row re-activated /
-- re-typed / re-parented into a violating state) is refused. Check live data
-- with the diagnostic SELECT in database/scripts/README.md.
--
-- Same BEFORE-trigger pattern as 05_organization_kumari_sevak_uniqueness_
-- trigger.sql (a partial unique index cannot resolve value_code through
-- nss.master_data). A transaction-scoped advisory lock per rule serialises
-- concurrent inserts so two sessions cannot both pass the check.
-- Idempotent: CREATE OR REPLACE + DROP ... IF EXISTS.
-- =====================================================

-- Retire the v1.0 ADVISORY_BOARD-only trigger/function (trigger first).
DROP TRIGGER IF EXISTS trg_enforce_advisory_board_singleton
    ON nss.organization;
DROP FUNCTION IF EXISTS nss.fn_enforce_advisory_board_singleton();

CREATE OR REPLACE FUNCTION nss.fn_enforce_organization_singleton()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_org_type_code    VARCHAR(50);
    v_parent_type_code VARCHAR(50);
    v_rule             TEXT;
    v_existing_pk      UUID;
    v_type_changed     BOOLEAN := TRUE;
    v_active_changed   BOOLEAN := TRUE;
    v_parent_changed   BOOLEAN := TRUE;
BEGIN
    IF NEW.is_active IS NOT TRUE THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        v_type_changed   := NEW.organization_type_master_data_pk
                            IS DISTINCT FROM OLD.organization_type_master_data_pk;
        v_active_changed := NEW.is_active IS DISTINCT FROM OLD.is_active;
        v_parent_changed := NEW.parent_organization_pk
                            IS DISTINCT FROM OLD.parent_organization_pk;
        IF NOT (v_type_changed OR v_active_changed OR v_parent_changed) THEN
            RETURN NEW;
        END IF;
    END IF;

    SELECT md.value_code INTO v_org_type_code
    FROM nss.master_data md
    WHERE md.master_data_pk = NEW.organization_type_master_data_pk;

    IF v_org_type_code IN ('KENDRA', 'NILACHALA_KUTIRA', 'SMRUTI_MANDIRA', 'ADVISORY_BOARD') THEN
        -- Rules 1-4: one active organization per type. A parent change alone
        -- cannot create a second one.
        IF TG_OP = 'UPDATE' AND NOT (v_type_changed OR v_active_changed) THEN
            RETURN NEW;
        END IF;
        v_rule := v_org_type_code;
        PERFORM pg_advisory_xact_lock(hashtext('nss.organization singleton:' || v_rule));

        SELECT o.organization_pk INTO v_existing_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = v_org_type_code
          AND o.is_active = TRUE
          AND o.organization_pk <> NEW.organization_pk
        LIMIT 1;

    ELSIF v_org_type_code = 'MAHILA_SANGHA' AND NEW.parent_organization_pk IS NOT NULL THEN
        -- Rule 5: only the Kendra-parented Mahila Sangha is a singleton.
        SELECT pmd.value_code INTO v_parent_type_code
        FROM nss.organization p
        JOIN nss.master_data pmd ON pmd.master_data_pk = p.organization_type_master_data_pk
        WHERE p.organization_pk = NEW.parent_organization_pk;

        IF v_parent_type_code IS DISTINCT FROM 'KENDRA' THEN
            RETURN NEW;
        END IF;
        v_rule := 'CENTRAL_MAHILA_SANGHA';
        PERFORM pg_advisory_xact_lock(hashtext('nss.organization singleton:' || v_rule));

        SELECT o.organization_pk INTO v_existing_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        JOIN nss.organization p ON p.organization_pk = o.parent_organization_pk
        JOIN nss.master_data pmd ON pmd.master_data_pk = p.organization_type_master_data_pk
        WHERE md.value_code = 'MAHILA_SANGHA'
          AND pmd.value_code = 'KENDRA'
          AND o.is_active = TRUE
          AND o.organization_pk <> NEW.organization_pk
        LIMIT 1;
    ELSE
        RETURN NEW;
    END IF;

    IF v_existing_pk IS NOT NULL THEN
        RAISE EXCEPTION
            'Organization singleton violation (%): an active organization already exists (organization_pk %). Only one is allowed.',
            v_rule, v_existing_pk
            USING ERRCODE = 'unique_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_organization_singleton
    ON nss.organization;

CREATE TRIGGER trg_enforce_organization_singleton
    BEFORE INSERT OR UPDATE OF
        organization_type_master_data_pk, is_active, parent_organization_pk
    ON nss.organization
    FOR EACH ROW
    EXECUTE FUNCTION nss.fn_enforce_organization_singleton();
