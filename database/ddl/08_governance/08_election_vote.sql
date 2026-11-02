-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 08_election_vote.sql
-- Table: nss.election_vote
-- Depth: 6 (depends on election, election_nomination,
--            position_master, person)
-- Version: 1.0
-- Authority: SOL-GOV-002 §21-22, SOL-GOV-004 §12,
--            GOV-BR-037/038/044/045,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #74
-- Owner: Governance
--
-- Design decisions:
--   - One ballot cast in an election: a vote for a nominated
--     candidate at a position (SOL-GOV-004 §12.1).
--   - election_pk NOT NULL FK — the vote belongs to one
--     election.
--   - election_nomination_pk NOT NULL FK — the vote is cast
--     FOR a specific nomination (candidate + position),
--     which is the authoritative link to candidate and
--     position (GOV-BR-037).
--   - position_master_pk NOT NULL FK — denormalized for
--     one-member-one-vote-PER-POSITION enforcement and
--     per-position tallying without walking the nomination
--     row.
--   - voter_person_pk FK = the Person casting the ballot.
--     NULLABLE (RESOLVED 2026-10-09). Populated for an OPEN
--     ballot (election.is_secret_ballot = FALSE) → the ballot
--     is attributable. NULL for a SECRET ballot
--     (is_secret_ballot = TRUE) → the choice row cannot be
--     traced to the voter. Eligibility and one-member-one-
--     vote-per-position are enforced in BOTH modes by the
--     election_vote_participation ledger (10_*), which always
--     records the voter. Voter must be an active NSS member
--     and not an ASSOCIATE member (GOV-BR-043) — validated at
--     the API layer, same pattern as GOV-BR-056.
--
--   *** VOTE SECRECY — RESOLVED 2026-10-09 (GOV-BR-045 /
--       §12.6) ***
--     Secrecy is now a per-election switch, election.is_secret
--     _ballot. The attributable-vs-anonymous split is realised
--     by (a) this table's NULLABLE voter_person_pk (the
--     choice) and (b) the separate election_vote_participation
--     ledger (the "who voted", for one-vote enforcement). In a
--     secret election the two are never joinable back to a
--     specific choice.
--
--   *** IMMUTABILITY — RESOLVED 2026-10-09 ***
--     A cast ballot is immutable: 11_governance_immutability.sql
--     attaches a BEFORE UPDATE trigger that rejects any UPDATE
--     of an election_vote row. The only way to clear ballots is
--     the reset flow, which hard-DELETEs them (president-
--     unilateral, or admin with president approval) — the
--     delete is still captured by the audit trigger.
--
--   - vote_date / cast_at records when the ballot was cast.
--   - No candidate_person_pk column: candidate is reached
--     through election_nomination to avoid a second source
--     of truth that could disagree with the nomination.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.election_vote
(
    -- ── Identity ────────────────────────────────────────

    election_vote_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    election_pk UUID NOT NULL,

    election_nomination_pk UUID NOT NULL,

    position_master_pk UUID NOT NULL,

    -- Populated for an OPEN ballot; NULL for a SECRET ballot.
    -- See header + 10_election_vote_participation.sql.
    voter_person_pk UUID NULL,

    -- ── Attributes ──────────────────────────────────────

    cast_at TIMESTAMPTZ NULL,

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

    CONSTRAINT fk_election_vote_election
        FOREIGN KEY (election_pk)
        REFERENCES nss.election (election_pk),

    CONSTRAINT fk_election_vote_nomination
        FOREIGN KEY (election_nomination_pk)
        REFERENCES nss.election_nomination (election_nomination_pk),

    CONSTRAINT fk_election_vote_position
        FOREIGN KEY (position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_election_vote_voter
        FOREIGN KEY (voter_person_pk)
        REFERENCES nss.person (person_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_election_vote_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_election_vote_election
    ON nss.election_vote (election_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_nomination
    ON nss.election_vote (election_nomination_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_position
    ON nss.election_vote (position_master_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_voter
    ON nss.election_vote (voter_person_pk);

CREATE INDEX IF NOT EXISTS idx_election_vote_active
    ON nss.election_vote (is_active);

-- One member, one vote PER POSITION in a given election
-- (GOV-BR-038). For an OPEN ballot this partial unique index
-- is a backstop on the choice row. For a SECRET ballot the
-- voter is NULL here (NULLs are distinct, so the index is
-- inert) — authoritative one-vote enforcement for BOTH modes
-- lives on election_vote_participation (10_*).
CREATE UNIQUE INDEX IF NOT EXISTS uq_election_vote_active_voter_position
    ON nss.election_vote (election_pk, position_master_pk, voter_person_pk)
    WHERE is_active = TRUE;
