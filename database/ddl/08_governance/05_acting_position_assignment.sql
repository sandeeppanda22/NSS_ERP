-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 05_acting_position_assignment.sql
-- Table: nss.acting_position_assignment
-- Depth: 5 (depends on body_master, position_master, person)
-- Version: 1.0
-- Authority: SOL-GOV-002 §12-15, SOL-GOV-004 §9,
--            GOV-BR-018/019/020/060/061,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #63
-- Owner: Governance
--
-- Design decisions:
--   - Captures temporary / acting occupancy of a position
--     in a body (e.g. acting President while the seat is
--     vacant or the holder is unavailable) — SOL-GOV-004 §9.
--     Kept separate from body_member_assignment so the
--     substantive history is never confused with interim
--     cover (GOV-BR-018).
--   - person_pk NOT NULL = the acting person (authoritative
--     Person identity, GOV-BR-057/074). No sangha_sevi FK:
--     an acting assignment is defined against the Person
--     performing the role (SOL-GOV-004 §9.3); membership
--     context, where relevant, is resolved via the
--     substantive assignment.
--   - effective_from NOT NULL; effective_to NULL while the
--     acting term is open. acting_status lifecycle mirrors
--     the assignment lifecycle (GOV-BR-087) via CHECK.
--   - reason: free-text justification for the acting cover
--     (vacancy, leave, suspension of holder, ...).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.acting_position_assignment
(
    -- ── Identity ────────────────────────────────────────

    acting_position_assignment_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    body_master_pk UUID NOT NULL,

    position_master_pk UUID NOT NULL,

    person_pk UUID NOT NULL,

    -- ── Acting Period ───────────────────────────────────

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    -- ── Status ──────────────────────────────────────────

    acting_status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

    reason TEXT NULL,

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

    CONSTRAINT fk_acting_position_assignment_body
        FOREIGN KEY (body_master_pk)
        REFERENCES nss.body_master (body_master_pk),

    CONSTRAINT fk_acting_position_assignment_position
        FOREIGN KEY (position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_acting_position_assignment_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_acting_position_assignment_status
        CHECK (acting_status IN ('ASSIGNED', 'ACTIVE', 'ENDED', 'HISTORICAL')),

    CONSTRAINT chk_acting_position_assignment_effective_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from),

    CONSTRAINT chk_acting_position_assignment_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_acting_position_assignment_body
    ON nss.acting_position_assignment (body_master_pk);

CREATE INDEX IF NOT EXISTS idx_acting_position_assignment_position
    ON nss.acting_position_assignment (position_master_pk);

CREATE INDEX IF NOT EXISTS idx_acting_position_assignment_person
    ON nss.acting_position_assignment (person_pk);

CREATE INDEX IF NOT EXISTS idx_acting_position_assignment_status
    ON nss.acting_position_assignment (acting_status);

CREATE INDEX IF NOT EXISTS idx_acting_position_assignment_active
    ON nss.acting_position_assignment (is_active);

-- Prevents the same person being recorded as acting in the
-- same position of the same body across two concurrently-
-- active (open-ended) rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_acting_position_assignment_active_holder
    ON nss.acting_position_assignment (body_master_pk, position_master_pk, person_pk)
    WHERE is_active = TRUE AND effective_to IS NULL;
