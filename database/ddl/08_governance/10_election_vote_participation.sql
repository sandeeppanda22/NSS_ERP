-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 10_election_vote_participation.sql
-- Table: nss.election_vote_participation
-- Depth: 6 (depends on election, position_master, person)
-- Version: 1.0
-- Authority: SOL-GOV-002 §21-22, SOL-GOV-004 §12,
--            GOV-BR-038/044/045 (secret-ballot resolution
--            2026-10-09)
-- Owner: Governance
--
-- Design decisions:
--   - The voter-participation ledger: one row per (election,
--     position, voter) recording THAT a member cast a ballot
--     for a position — never WHICH candidate they chose.
--   - This is the authoritative one-member-one-vote-PER-
--     POSITION gate (GOV-BR-038) in BOTH ballot modes:
--       OPEN   → election_vote.voter_person_pk is also stored
--                (attributable); participation is the mirror
--                that drives the "already voted" check.
--       SECRET → election_vote.voter_person_pk is NULL, so the
--                choice is anonymous; participation is the ONLY
--                place the voter is recorded, and it carries no
--                link to the chosen nomination — so the two can
--                never be joined back to reveal a secret vote.
--   - voted_at: when the member cast the ballot.
--   - IMMUTABLE: like election_vote, a participation row is
--     append-only. 11_governance_immutability.sql rejects any
--     UPDATE. The reset flow hard-DELETEs participation rows
--     together with the ballots (president-unilateral, or admin
--     with president approval); the delete is audit-logged.
--   - No election_nomination_pk / candidate column here BY
--     DESIGN — storing the choice would defeat secrecy.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE
--       columns included in Pass 1. Their FK constraints are
--       deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.election_vote_participation
(
    -- ── Identity ────────────────────────────────────────

    election_vote_participation_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    election_pk UUID NOT NULL,

    position_master_pk UUID NOT NULL,

    voter_person_pk UUID NOT NULL,

    -- ── Attributes ──────────────────────────────────────

    voted_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    remarks TEXT NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Foreign Keys ────────────────────────────────────

    CONSTRAINT fk_election_vote_participation_election
        FOREIGN KEY (election_pk)
        REFERENCES nss.election (election_pk),

    CONSTRAINT fk_election_vote_participation_position
        FOREIGN KEY (position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_election_vote_participation_voter
        FOREIGN KEY (voter_person_pk)
        REFERENCES nss.person (person_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_election_vote_participation_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_election_vote_participation_election
    ON nss.election_vote_participation (election_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_participation_position
    ON nss.election_vote_participation (position_master_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_participation_voter
    ON nss.election_vote_participation (voter_person_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_participation_active
    ON nss.election_vote_participation (is_active);

-- Authoritative one-member-one-vote PER POSITION gate
-- (GOV-BR-038), for BOTH open and secret ballots.
CREATE UNIQUE INDEX IF NOT EXISTS uq_election_vote_participation_active_voter_position
    ON nss.election_vote_participation (election_pk, position_master_pk, voter_person_pk)
    WHERE is_active = TRUE;
