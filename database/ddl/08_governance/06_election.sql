-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 06_election.sql
-- Table: nss.election
-- Depth: 5 (depends on body_master, organization)
-- Version: 1.0
-- Authority: SOL-GOV-002 §16-18, SOL-GOV-004 §10,
--            GOV-BR-030/031/032/033/040/041,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #64
-- Owner: Governance
--
-- Design decisions:
--   - Election event that reconstitutes / fills a governance
--     body (SOL-GOV-004 §10.1). An election is scoped to the
--     body being constituted (body_master_pk NOT NULL).
--   - organization_pk FK, NULLABLE: carried where the
--     election is organization-scoped; NULL for NSS-wide /
--     Kendra-level events — mirrors body_master (§16,
--     GOV-BR-059). No new org structure introduced
--     (GOV-BR-058).
--   - election_code stable + UNIQUE (§10.4).
--   - election_status lifecycle finalized at DDL per
--     GOV-BR-041 / SOL-GOV-004 §10.7
--     (Scheduled / Nomination / Voting / Completed /
--     Cancelled) via CHECK — the status drives which child
--     steps (nomination, vote, result) are permitted.
--   - Date columns model the election timeline:
--     election_date (polling), nomination_start/end,
--     voting_start/end. All DATE, nullable except the
--     anchoring election_date; ordering enforced by CHECKs.
--   - No result/winner columns here — results live in
--     election_result (one row per decided position).
--   - is_secret_ballot (GOV-BR-045 / SOL-GOV-004 §12.6,
--     RESOLVED 2026-10-09): per-election switch between an
--     OPEN ballot (election_vote.voter_person_pk populated —
--     attributable) and a SECRET ballot (voter_person_pk NULL
--     on the choice row; the voter is recorded only in the
--     separate election_vote_participation ledger, so the
--     choice cannot be traced to the voter). One-member-one-
--     vote-per-position is enforced in BOTH modes by the
--     participation ledger. Fixed at creation and must not
--     change once voting has opened (API-enforced).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.election
(
    -- ── Identity ────────────────────────────────────────

    election_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    election_code VARCHAR(50) NOT NULL,

    body_master_pk UUID NOT NULL,

    organization_pk UUID NULL,

    -- ── Attributes ──────────────────────────────────────

    election_name VARCHAR(200) NOT NULL,

    description TEXT NULL,

    -- ── Timeline ────────────────────────────────────────

    election_date DATE NOT NULL,

    nomination_start_date DATE NULL,

    nomination_end_date DATE NULL,

    voting_start_date DATE NULL,

    voting_end_date DATE NULL,

    -- ── Mode ────────────────────────────────────────────
    -- How this cycle fills the body's posts (GOV-BR-042,
    -- "Consensus Before Election"):
    --   ELECTION   → contested cycle. Nominations are taken,
    --                then a ballot is held, then results are
    --                declared from the tally.
    --                Status path: SCHEDULED → NOMINATION
    --                             → VOTING → COMPLETED.
    --   NOMINATION → selection/consensus cycle, no ballot.
    --                Posts are filled directly from the
    --                ACCEPTED nominations; each result is
    --                declared UNCONTESTED with a NULL
    --                vote_count.
    --                Status path: SCHEDULED → NOMINATION
    --                             → COMPLETED (VOTING skipped).
    -- Consensus is attempted first where the governance rules
    -- follow the Selection + Election model (notably Mahila
    -- Parichalana Mandali); an election is held when required.
    -- Fixed at creation — API-enforced, because flipping the
    -- mode mid-cycle would orphan either the ballots or the
    -- uncontested declarations.
    election_type VARCHAR(20) NOT NULL
        DEFAULT 'ELECTION',

    -- ── Ballot ──────────────────────────────────────────
    -- Applies to election_type = 'ELECTION' only; a
    -- NOMINATION cycle casts no ballots at all.
    -- OPEN (FALSE, default) → election_vote.voter_person_pk
    -- is populated and the ballot is attributable.
    -- SECRET (TRUE) → the choice row carries a NULL voter;
    -- the voter is recorded only in election_vote_participation.
    -- (GOV-BR-045 / SOL-GOV-004 §12.6, RESOLVED 2026-10-09)
    is_secret_ballot BOOLEAN NOT NULL
        DEFAULT FALSE,

    -- ── Status ──────────────────────────────────────────

    election_status VARCHAR(20) NOT NULL
        DEFAULT 'SCHEDULED',

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

    CONSTRAINT fk_election_body
        FOREIGN KEY (body_master_pk)
        REFERENCES nss.body_master (body_master_pk),

    CONSTRAINT fk_election_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_election_code
        UNIQUE (election_code),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_election_status
        CHECK (election_status IN ('SCHEDULED', 'NOMINATION', 'VOTING', 'COMPLETED', 'CANCELLED')),

    CONSTRAINT chk_election_type
        CHECK (election_type IN ('ELECTION', 'NOMINATION')),

    -- A NOMINATION (consensus/selection) cycle holds no
    -- ballot, so it must never carry a voting window and
    -- must never reach the VOTING status.
    CONSTRAINT chk_election_nomination_mode_no_voting
        CHECK
        (
            election_type <> 'NOMINATION'
            OR (voting_start_date IS NULL
                AND voting_end_date IS NULL
                AND election_status <> 'VOTING')
        ),

    CONSTRAINT chk_election_nomination_period
        CHECK (nomination_end_date IS NULL
               OR nomination_start_date IS NULL
               OR nomination_end_date >= nomination_start_date),

    CONSTRAINT chk_election_voting_period
        CHECK (voting_end_date IS NULL
               OR voting_start_date IS NULL
               OR voting_end_date >= voting_start_date),

    CONSTRAINT chk_election_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_election_body
    ON nss.election (body_master_pk);

CREATE INDEX IF NOT EXISTS idx_election_organization
    ON nss.election (organization_pk)
    WHERE organization_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_election_status
    ON nss.election (election_status);

CREATE INDEX IF NOT EXISTS idx_election_date
    ON nss.election (election_date);

CREATE INDEX IF NOT EXISTS idx_election_active
    ON nss.election (is_active);
