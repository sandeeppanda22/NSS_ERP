-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 07_election_nomination.sql
-- Table: nss.election_nomination
-- Depth: 6 (depends on election, position_master, person)
-- Version: 1.0
-- Authority: SOL-GOV-002 §19-20, SOL-GOV-004 §11,
--            GOV-BR-034/035/036/042/043,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #73
-- Owner: Governance
--
-- Design decisions:
--   - A candidate nominated for a specific position in an
--     election (SOL-GOV-004 §11.1).
--   - election_pk NOT NULL FK — nomination belongs to one
--     election.
--   - position_master_pk NOT NULL FK — a nomination is for
--     one position (GOV-BR-034). Position catalogue is
--     reused, not duplicated.
--   - candidate_person_pk NOT NULL FK = authoritative Person
--     being nominated (GOV-BR-057/074). Candidate must be an
--     active NSS member; ASSOCIATE members may not stand for
--     any post, and PROBATIONARY members may not stand for
--     Sakha President/Secretary (GOV-BR-043) — validated at
--     the API layer against membership_type_master_data_pk
--     and the stable body_type_code/position_code seeded in
--     database/seed/08_governance/, same separation as
--     GOV-BR-056 (not re-implemented here as a CHECK, since
--     the catalogues are owner-extensible via the API and a
--     DDL CHECK can't follow new codes added later).
--   - proposer_person_pk NULLABLE FK = the Person proposing
--     the candidate, where recorded (SOL-GOV-004 §11.4).
--     Nullable because the source does not always mandate a
--     recorded proposer; seconder is out of scope at DDL and
--     deferred to business/API if later required.
--   - nomination_status lifecycle finalized at DDL per
--     GOV-BR-043 (Nominated / Accepted / Withdrawn /
--     Rejected) via CHECK.
--   - probationary_exception_approver_sangha_sevi_pk /
--     probationary_exception_reason (GOV-BR-043-A, owner-
--     decided 2026-10-14): the Parichalak-approved,
--     per-nomination exception letting a PROBATIONARY
--     candidate stand for Sakha President/Secretary. Both
--     NULLABLE and both-or-neither (CHECK) — exception
--     presence is signalled by the approver FK being set,
--     no separate boolean flag. Candidate credential
--     validity (Anumati Patra) is checked at the API layer,
--     not re-stated as a DDL CHECK (same reasoning as the
--     base rule above).
--   - One active nomination per (election, position,
--     candidate) enforced by a partial unique index — a
--     candidate cannot be nominated twice for the same
--     position in the same election while active
--     (GOV-BR-035).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.election_nomination
(
    -- ── Identity ────────────────────────────────────────

    election_nomination_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    election_pk UUID NOT NULL,

    position_master_pk UUID NOT NULL,

    candidate_person_pk UUID NOT NULL,

    proposer_person_pk UUID NULL,

    -- ── Attributes ──────────────────────────────────────

    nomination_date DATE NULL,

    nomination_status VARCHAR(20) NOT NULL
        DEFAULT 'NOMINATED',

    remarks TEXT NULL,

    -- ── Probationary Exception (GOV-BR-043-A) ────────────

    probationary_exception_approver_sangha_sevi_pk UUID NULL,

    probationary_exception_reason TEXT NULL,

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

    CONSTRAINT fk_election_nomination_election
        FOREIGN KEY (election_pk)
        REFERENCES nss.election (election_pk),

    CONSTRAINT fk_election_nomination_position
        FOREIGN KEY (position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_election_nomination_candidate
        FOREIGN KEY (candidate_person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_election_nomination_proposer
        FOREIGN KEY (proposer_person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_election_nomination_probationary_approver
        FOREIGN KEY (probationary_exception_approver_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_election_nomination_status
        CHECK (nomination_status IN ('NOMINATED', 'ACCEPTED', 'WITHDRAWN', 'REJECTED')),

    CONSTRAINT chk_election_nomination_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        ),

    -- GOV-BR-043-A: the exception is both-or-neither — an
    -- approver with no reason, or a reason with no approver,
    -- is never valid.
    CONSTRAINT chk_election_nomination_probationary_exception
        CHECK
        (
            (probationary_exception_approver_sangha_sevi_pk IS NULL
                AND probationary_exception_reason IS NULL)
            OR
            (probationary_exception_approver_sangha_sevi_pk IS NOT NULL
                AND probationary_exception_reason IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_election_nomination_election
    ON nss.election_nomination (election_pk);

CREATE INDEX IF NOT EXISTS idx_election_nomination_position
    ON nss.election_nomination (position_master_pk);

CREATE INDEX IF NOT EXISTS idx_election_nomination_candidate
    ON nss.election_nomination (candidate_person_pk);

CREATE INDEX IF NOT EXISTS idx_election_nomination_proposer
    ON nss.election_nomination (proposer_person_pk)
    WHERE proposer_person_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_election_nomination_status
    ON nss.election_nomination (nomination_status);

CREATE INDEX IF NOT EXISTS idx_election_nomination_active
    ON nss.election_nomination (is_active);

-- A candidate may hold one LIVE (NOMINATED/ACCEPTED) nomination for a
-- given position within a given election (GOV-BR-035). WITHDRAWN and
-- REJECTED nominations are terminal history and do not block re-filing
-- (2026-10-28). Existing databases: live DROP INDEX + CREATE of this index
-- (the build is existence-gated and will not re-run this file).
CREATE UNIQUE INDEX IF NOT EXISTS uq_election_nomination_active_candidate
    ON nss.election_nomination (election_pk, position_master_pk, candidate_person_pk)
    WHERE is_active = TRUE AND nomination_status IN ('NOMINATED', 'ACCEPTED');
