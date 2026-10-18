-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 09_election_result.sql
-- Table: nss.election_result
-- Depth: 6 (depends on election, election_nomination,
--            position_master, person)
-- Version: 1.0
-- Authority: SOL-GOV-002 §23-24, SOL-GOV-004 §13,
--            GOV-BR-039/046/047/048/049,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #75
-- Owner: Governance
--
-- Design decisions:
--   - The decided outcome for ONE position in an election
--     (SOL-GOV-004 §13.1) — one row per position result.
--   - election_pk NOT NULL FK — result belongs to one
--     election.
--   - position_master_pk NOT NULL FK — the position decided.
--   - winning_nomination_pk NULLABLE FK → election_nomination:
--     the nomination declared elected. Nullable because a
--     position may be declared VACANT / TIE / UNCONTESTED
--     with no winning nomination (result_status governs,
--     GOV-BR-048).
--   - winner_person_pk NULLABLE FK → person: denormalized
--     authoritative Person of the winner for direct lookup
--     and for the hand-off into body_member_assignment
--     (GOV-BR-039/057). NULL when no winner.
--   - vote_count NULLABLE INTEGER: tally for the winning
--     nomination where a poll occurred; NULL for
--     uncontested/declared outcomes.
--   - result_status lifecycle finalized at DDL per
--     GOV-BR-048 (Declared / Uncontested / Tie / Vacant /
--     Cancelled) via CHECK.
--   - Hand-off is deliberate: declaring a result does NOT
--     itself write body_member_assignment — that is a
--     downstream business/API step (SOL-GOV-004 §13.5).
--     Keeps result (the electoral fact) separate from
--     assignment (the governance fact).
--   - One active result per (election, position) enforced by
--     a partial unique index (GOV-BR-046).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.election_result
(
    -- ── Identity ────────────────────────────────────────

    election_result_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    election_pk UUID NOT NULL,

    position_master_pk UUID NOT NULL,

    -- ── Outcome ─────────────────────────────────────────

    winning_nomination_pk UUID NULL,

    winner_person_pk UUID NULL,

    vote_count INTEGER NULL,

    result_status VARCHAR(20) NOT NULL
        DEFAULT 'DECLARED',

    declared_at TIMESTAMPTZ NULL,

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

    CONSTRAINT fk_election_result_election
        FOREIGN KEY (election_pk)
        REFERENCES nss.election (election_pk),

    CONSTRAINT fk_election_result_position
        FOREIGN KEY (position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_election_result_winning_nomination
        FOREIGN KEY (winning_nomination_pk)
        REFERENCES nss.election_nomination (election_nomination_pk),

    CONSTRAINT fk_election_result_winner
        FOREIGN KEY (winner_person_pk)
        REFERENCES nss.person (person_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_election_result_status
        CHECK (result_status IN ('DECLARED', 'UNCONTESTED', 'TIE', 'VACANT', 'CANCELLED')),

    CONSTRAINT chk_election_result_vote_count
        CHECK (vote_count IS NULL OR vote_count >= 0),

    CONSTRAINT chk_election_result_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_election_result_election
    ON nss.election_result (election_pk);

CREATE INDEX IF NOT EXISTS idx_election_result_position
    ON nss.election_result (position_master_pk);

CREATE INDEX IF NOT EXISTS idx_election_result_winning_nomination
    ON nss.election_result (winning_nomination_pk)
    WHERE winning_nomination_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_election_result_winner
    ON nss.election_result (winner_person_pk)
    WHERE winner_person_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_election_result_status
    ON nss.election_result (result_status);

CREATE INDEX IF NOT EXISTS idx_election_result_active
    ON nss.election_result (is_active);

-- One active result per position per election (GOV-BR-046).
CREATE UNIQUE INDEX IF NOT EXISTS uq_election_result_active_position
    ON nss.election_result (election_pk, position_master_pk)
    WHERE is_active = TRUE;
