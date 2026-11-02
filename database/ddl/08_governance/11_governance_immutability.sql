-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 11_governance_immutability.sql
-- Purpose: Enforce ballot immutability at the database
--          level. A cast ballot (election_vote) and its
--          participation record (election_vote_participation)
--          are append-only: once written they can never be
--          UPDATEd. The only way to clear them is the reset
--          flow, which SOFT-deletes them (is_active -> FALSE,
--          deleted_at set; president-unilateral or admin-with-
--          president-approval) — nss_db_writer has no DELETE
--          grant, and history is never hard-deleted. That one
--          bookkeeping transition is the only UPDATE allowed;
--          it is captured by the audit trigger (15_audit_trigger.sql).
-- Version: 1.0
-- Authority: GOV-BR-045, SOL-GOV-004 §12 (immutable ballots,
--            RESOLVED 2026-10-09)
-- Owner: Governance
-- Depends: 08_election_vote.sql,
--          10_election_vote_participation.sql
--
-- Why a trigger and not a GRANT/REVOKE: the application uses
-- one DB role for all writes, so column/row privileges can't
-- express "insert + delete but never update" per table. A
-- BEFORE UPDATE trigger that RAISEs is the portable, explicit
-- guard — it fires before the row changes and before the
-- AFTER audit trigger, so a blocked update leaves no trace
-- beyond the raised error.
-- =====================================================

-- ── Guard function ──────────────────────────────────────
-- Rejects any UPDATE on the table it is attached to. Generic
-- so it can guard additional append-only tables later.

CREATE OR REPLACE FUNCTION nss.fn_block_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Soft-delete exception (reset flow, 2026-10-28): nss_db_writer has no
    -- DELETE grant, so the reset flow retires ballots by flipping
    -- is_active TRUE -> FALSE (+ deleted_at / audit columns). Any UPDATE
    -- that changes ONLY those bookkeeping columns on a live row is allowed;
    -- every other change (e.g. rewriting the chosen nomination) is blocked.
    IF OLD.is_active = TRUE AND NEW.is_active = FALSE
       AND NEW.deleted_at IS NOT NULL
       AND (to_jsonb(NEW) - ARRAY['is_active', 'deleted_at', 'deleted_by_sangha_sevi_pk',
                                   'updated_at', 'updated_by_sangha_sevi_pk'])
         = (to_jsonb(OLD) - ARRAY['is_active', 'deleted_at', 'deleted_by_sangha_sevi_pk',
                                   'updated_at', 'updated_by_sangha_sevi_pk'])
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'Row in nss.% is immutable and cannot be updated; '
        'clear it via the reset flow (soft delete) instead.',
        TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$;

-- ── Attach to the immutable ballot tables ───────────────

DROP TRIGGER IF EXISTS trg_immutable_election_vote
    ON nss.election_vote;
CREATE TRIGGER trg_immutable_election_vote
    BEFORE UPDATE ON nss.election_vote
    FOR EACH ROW EXECUTE FUNCTION nss.fn_block_update();

DROP TRIGGER IF EXISTS trg_immutable_election_vote_participation
    ON nss.election_vote_participation;
CREATE TRIGGER trg_immutable_election_vote_participation
    BEFORE UPDATE ON nss.election_vote_participation
    FOR EACH ROW EXECUTE FUNCTION nss.fn_block_update();
