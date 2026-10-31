-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 05_organization_kumari_sevak_uniqueness_trigger.sql
-- Object: nss.fn_enforce_kumari_sevak_one_per_sakha() +
--         trigger on nss.organization
-- Depth: 2 (depends on organization, master_data)
-- Version: 1.0
-- Authority: ORG-BR-102 (governance decision, 2026-09-26)
-- Owner: NSS_ERP_ADMIN
--
-- Purpose:
--   At most one active KUMARI_SANGHA and one active SEVAK_SANGHA may
--   exist per Sakha at a time (ORG-BR-102's "the Sakha which doesn't
--   have this yet" auto-selection depends on this being a real
--   invariant, not an assumption enforced only in the API).
--
-- "Sakha" here means ANY parent organization (the check keys on
-- parent_organization_pk, never on the parent's type), so a SAKHA_ASANA
-- parent is covered exactly like a SAKHA_SANGHA (owner 2026-10-31, GDR-008:
-- a Sakha Asana hosts the same wings). No Sakha-type literal is used, hence
-- no fn_is_sakha_like_org_type call and no behaviour change was needed.
--
-- Not a partial unique index: the predicate needs organization_type_
-- master_data_pk resolved to its value_code via nss.master_data, and
-- Postgres forbids subqueries in index predicates. A BEFORE trigger
-- is the same pattern already used for MBR-038A
-- (trg_enforce_sakha_only_sangha_sevi) and ORG-BR-099
-- (trg_enforce_organization_address_restriction).
--
-- No migration/fix script: this ships as DDL, re-runnable via
-- the standard build (DROP ... IF EXISTS makes it idempotent).
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_enforce_kumari_sevak_one_per_sakha()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_org_type_code VARCHAR(50);
    v_existing_pk UUID;
BEGIN
    SELECT md.value_code INTO v_org_type_code
    FROM nss.master_data md
    WHERE md.master_data_pk = NEW.organization_type_master_data_pk;

    IF v_org_type_code NOT IN ('KUMARI_SANGHA', 'SEVAK_SANGHA') THEN
        RETURN NEW;
    END IF;

    IF NEW.parent_organization_pk IS NULL OR NEW.is_active IS NOT TRUE THEN
        RETURN NEW;
    END IF;

    SELECT o.organization_pk INTO v_existing_pk
    FROM nss.organization o
    JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
    WHERE o.parent_organization_pk = NEW.parent_organization_pk
      AND md.value_code = v_org_type_code
      AND o.is_active = TRUE
      AND o.organization_pk <> NEW.organization_pk
    LIMIT 1;

    IF v_existing_pk IS NOT NULL THEN
        RAISE EXCEPTION
            'ORG-BR-102 violation: Sakha % already has an active % (organization_pk %). Only one active % per Sakha is allowed.',
            NEW.parent_organization_pk, v_org_type_code, v_existing_pk, v_org_type_code
            USING ERRCODE = 'unique_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_kumari_sevak_one_per_sakha
    ON nss.organization;

CREATE TRIGGER trg_enforce_kumari_sevak_one_per_sakha
    BEFORE INSERT OR UPDATE OF
        organization_type_master_data_pk, parent_organization_pk, is_active
    ON nss.organization
    FOR EACH ROW
    EXECUTE FUNCTION nss.fn_enforce_kumari_sevak_one_per_sakha();
