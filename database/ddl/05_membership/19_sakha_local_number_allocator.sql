-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 19_sakha_local_number_allocator.sql
-- Function: nss.fn_next_sakha_local_number()
-- Depends: 05_membership/06_membership_sakha_affiliation.sql,
--          05_membership/17_sakha_local_number_counter.sql
-- Version: 1.0 (2026-11-01)
-- Authority: MBR-030, MBR-030C, MBR-048
-- Owner: NSS_ERP_ADMIN
--
-- Purpose: the ONE allocation rule for the bare numeric part of a Local
--          Sakha ERP Number, shared by api/helpers.py::
--          next_sakha_local_number() (the only caller).
--
-- Rule:    next = the first counter value, counting up from the
--          per-(organization, namespace) counter, whose composed id
--          (p_prefix || number) is not already present in
--          membership_sakha_affiliation for that organization.
--          - The counter row is upserted with ON CONFLICT, so concurrent
--            allocators for one (organization, namespace) serialize on the
--            row lock: two creations never receive the same number.
--          - The existence probe covers ARCHIVED rows too, so a number held
--            by an archived affiliation is never reissued (MBR-030,
--            MBR-022), and an explicitly typed / legacy-imported number
--            (which bypasses the counter) is simply skipped over instead of
--            colliding — without dragging the sequence up to a large legacy
--            value (the counter only ever moves one step per probe).
--          - p_prefix is the already-composed id prefix: <short_code> for
--            REGULAR, <short_code><marker> for DARSHAK, so the two
--            namespaces never probe each other's ids.
-- Idempotent: CREATE OR REPLACE — wired via run_sql.
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_next_sakha_local_number(
    p_organization_pk UUID,
    p_namespace       VARCHAR,
    p_prefix          VARCHAR
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_next INTEGER;
    v_tries INTEGER := 0;
BEGIN
    LOOP
        INSERT INTO nss.sakha_local_number_counter
            (organization_pk, namespace, current_value)
        VALUES (p_organization_pk, p_namespace, 1)
        ON CONFLICT (organization_pk, namespace)
        DO UPDATE SET current_value = nss.sakha_local_number_counter.current_value + 1,
                      updated_at = NOW()
        RETURNING current_value INTO v_next;

        EXIT WHEN NOT EXISTS (
            SELECT 1
            FROM   nss.membership_sakha_affiliation msa
            WHERE  msa.organization_pk = p_organization_pk
              AND  msa.local_sakha_erp_id = p_prefix || v_next::TEXT
        );

        v_tries := v_tries + 1;
        IF v_tries > 100000 THEN
            RAISE EXCEPTION 'Local Sakha number allocation did not converge for organization % (%)',
                p_organization_pk, p_namespace;
        END IF;
    END LOOP;

    RETURN v_next;
END;
$$;
