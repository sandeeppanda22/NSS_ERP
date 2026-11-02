-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 20_home_affiliation_guard.sql
-- Purpose: DB-level guarantee that every ACTIVE, non-system Sangha Sevi has
--          exactly one open (ACTIVE/REACTIVATED) HOME affiliation — at
--          sangha_sevi.organization_pk, with a non-empty local_sakha_erp_id —
--          by commit time. Owner 2026-11-01: "a member without a Local Sakha
--          ID should not be allowed in the first place to the db."
-- Depends: 05_membership/01_sangha_sevi.sql,
--          05_membership/06_membership_sakha_affiliation.sql
-- Version: 1.0 (2026-11-01)
-- Authority: MBR-030, MBR-038A, MBR-048
-- Owner: NSS_ERP_ADMIN
--
-- Design:
--   * DEFERRABLE INITIALLY DEFERRED constraint triggers: the check runs at
--     COMMIT, so the normal insert order (sangha_sevi first, because the
--     affiliation FKs it) and the transfer sequence (close old affiliation,
--     open new one, move sangha_sevi.organization_pk) all pass as long as the
--     END state is consistent. "At most one" is already enforced by
--     uq_mem_sakha_aff_active (sangha_sevi_pk, organization_pk) WHERE
--     effective_to IS NULL; this guard adds the "at least one" half.
--   * Constraint triggers only fire for rows touched in the transaction, so
--     creating them scans NOTHING: a database that already holds violators
--     builds and seeds normally. Existing violators are only reported (WARN) by 03_validate.
--     (They are only blocked if a later write touches the specific columns
--     below on that row.) There is deliberately NO automatic backfill (owner
--     2026-11-01); 03_validate WARNs with a diagnostic SELECT instead.
--   * sangha_sevi: fires on INSERT and UPDATE OF organization_pk, is_active,
--     is_system_account. Inactive (soft-deleted) sevis and the reserved
--     system account (is_system_account = TRUE, SS1 at the Kendra, MBR-038A)
--     are exempt.
--   * membership_sakha_affiliation: fires on UPDATE OF the identity/lifecycle
--     columns and on DELETE, re-checking the owning sevi (closing the home
--     affiliation without a replacement fails at commit). INSERT cannot
--     remove a home affiliation, so it is not guarded.
--   * Darshak: a cross-Sakha Darshak attendance affiliation is a SECOND open
--     row at a different organization; it neither satisfies nor violates the
--     home check (the check keys on sangha_sevi.organization_pk).
--     A PROBATIONARY (Darshaka) member's own home affiliation carries a
--     Darshak-namespace id (e.g. ESSD3) and satisfies it like any other.
--
-- Idempotent: CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS — wired
-- via run_sql.
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_assert_sevi_has_home_affiliation(p_sangha_sevi_pk UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_org       UUID;
    v_sevi_id   VARCHAR;
BEGIN
    SELECT ss.organization_pk, ss.sangha_sevi_id
    INTO   v_org, v_sevi_id
    FROM   nss.sangha_sevi ss
    WHERE  ss.sangha_sevi_pk = p_sangha_sevi_pk
      AND  ss.is_active = TRUE
      AND  ss.is_system_account = FALSE;

    IF NOT FOUND THEN
        RETURN;  -- deleted, inactive or system account: exempt
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM   nss.membership_sakha_affiliation msa
        WHERE  msa.sangha_sevi_pk = p_sangha_sevi_pk
          AND  msa.organization_pk = v_org
          AND  msa.effective_to IS NULL
          AND  msa.affiliation_status IN ('ACTIVE', 'REACTIVATED')
          AND  btrim(msa.local_sakha_erp_id) <> ''
    ) THEN
        RAISE EXCEPTION
            'MBR-030 violation: active Sangha Sevi % has no open home Sakha affiliation with a Local Sakha ID at its organization.',
            v_sevi_id
            USING ERRCODE = 'check_violation';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION nss.fn_trg_sevi_home_affiliation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM nss.fn_assert_sevi_has_home_affiliation(NEW.sangha_sevi_pk);
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION nss.fn_trg_affiliation_home_affiliation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM nss.fn_assert_sevi_has_home_affiliation(OLD.sangha_sevi_pk);
    ELSE
        PERFORM nss.fn_assert_sevi_has_home_affiliation(NEW.sangha_sevi_pk);
        IF OLD.sangha_sevi_pk IS DISTINCT FROM NEW.sangha_sevi_pk THEN
            PERFORM nss.fn_assert_sevi_has_home_affiliation(OLD.sangha_sevi_pk);
        END IF;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS ctrg_sevi_home_affiliation ON nss.sangha_sevi;
CREATE CONSTRAINT TRIGGER ctrg_sevi_home_affiliation
    AFTER INSERT OR UPDATE OF organization_pk, is_active, is_system_account
    ON nss.sangha_sevi
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION nss.fn_trg_sevi_home_affiliation();

DROP TRIGGER IF EXISTS ctrg_affiliation_home_affiliation ON nss.membership_sakha_affiliation;
CREATE CONSTRAINT TRIGGER ctrg_affiliation_home_affiliation
    AFTER UPDATE OF sangha_sevi_pk, organization_pk, local_sakha_erp_id, effective_to, affiliation_status
          OR DELETE
    ON nss.membership_sakha_affiliation
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION nss.fn_trg_affiliation_home_affiliation();
