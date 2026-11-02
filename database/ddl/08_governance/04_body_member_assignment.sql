-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 04_body_member_assignment.sql
-- Table: nss.body_member_assignment
-- Depth: 5 (depends on body_master, position_master,
--            person, sangha_sevi)
-- Version: 1.0
-- Authority: SOL-GOV-002 §12-15, SOL-GOV-004 §8,
--            GOV-BR-015/016/017/055/057/072/073/074,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #62
-- Owner: Governance
--
-- Design decisions:
--   - Core transaction table of the Unified Body
--     Governance Model (SOL-GOV-004 §8.1). Replaces all
--     body-specific member tables (GOV-BR-004).
--   - Identity: person_pk NOT NULL = authoritative Person
--     identity (GOV-BR-057/074); no duplicate Person is
--     created in Governance (SOL-GOV-004 §43).
--   - sangha_sevi_pk NOT NULL = the office holder must be an
--     NSS member. A person with no Sangha Sevi record is not
--     part of NSS and cannot hold a governance position, so
--     the membership link is mandatory (GOV-BR-056/074). The
--     API additionally validates the Sangha Sevi is active and
--     belongs to person_pk before the assignment is accepted;
--     Governance never creates/modifies the membership record
--     itself (GOV-BR-055).
--   - effective_from NOT NULL + effective_to NULL express
--     the assignment term; history is preserved and never
--     overwritten (GOV-BR-016/017, §8.5/§8.6).
--   - assignment_status vocabulary finalized at DDL per
--     SOL-GOV-003 GOV-BR-087 lifecycle
--     (Assigned/Active/Ended/Historical) via CHECK.
--     PENDING_REMOVAL added 2026-10-08 (GOV-BR item #18): a forced
--     removal initiated via NSS-admin break-glass sits here until the
--     body's own sitting President approves (-> ENDED) or rejects
--     (-> ACTIVE) it. Originally scoped to Sakha-nominated seats only
--     (e.g. Advisory Board); generalized 2026-10-15 to any position in
--     any governance body — removing someone always requires that
--     body's own GB meeting resolution first (the concerned Sakha's GB,
--     for a Sevak Sangha Executive seat) and that body's own President
--     sign-off (or, while that seat is vacant, another of its own
--     sitting office bearers — no fixed VP/Secretary priority order).
--     The request may be filed by that body's own scoped admin or one
--     of its own office bearers, not only the platform super-admin.
--     Never reached by the nominating Sakha's own direct self-
--     withdrawal of its Advisory Board nominee (still instant, via /end).
--     RESIGNED added 2026-10-15: a distinct terminal status for
--     voluntary self-withdrawal. Reachable ONLY via the office
--     holder resigning their own seat (POST /assignments/{id}/resign) —
--     no admin, scope-holder or NSS-wide override may set it; that is
--     what distinguishes it from an admin-driven ENDED. Carries a
--     mandatory resignation_reason. Counts as vacated, same as ENDED.
--   - resignation_reason: free text, set only together with
--     assignment_status = 'RESIGNED' (enforced at API, not DB).
--   - assignment_reference: free-text link to the source
--     act (e.g. election_result code / resolution ref). Since
--     2026-10-15 also carries the mandatory GB meeting resolution
--     reference for a forced removal (gb_resolution_reference at API).
--   - Occupancy rule (§8.9/§35): a hard single-holder-
--     per-position constraint is intentionally NOT
--     enforced at DB level because MEMBER seats allow
--     multiple holders. Per-body composition / single-
--     holder rules are enforced in business/API design
--     (SOL-GOV-004 §25). The partial unique index below
--     only prevents the SAME person holding the SAME
--     position in the SAME body in two concurrently-active
--     rows.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.body_member_assignment
(
    -- ── Identity ────────────────────────────────────────

    body_member_assignment_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    body_master_pk UUID NOT NULL,

    position_master_pk UUID NOT NULL,

    person_pk UUID NOT NULL,

    sangha_sevi_pk UUID NOT NULL,

    -- ── Assignment Period ───────────────────────────────

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    -- ── Status ──────────────────────────────────────────

    assignment_status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

    assignment_reference VARCHAR(100) NULL,

    remarks TEXT NULL,

    resignation_reason TEXT NULL,

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

    CONSTRAINT fk_body_member_assignment_body
        FOREIGN KEY (body_master_pk)
        REFERENCES nss.body_master (body_master_pk),

    CONSTRAINT fk_body_member_assignment_position
        FOREIGN KEY (position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_body_member_assignment_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_body_member_assignment_sangha_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_body_member_assignment_status
        CHECK (assignment_status IN ('ASSIGNED', 'ACTIVE', 'ENDED', 'HISTORICAL', 'PENDING_REMOVAL', 'RESIGNED')),

    CONSTRAINT chk_body_member_assignment_effective_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from),

    CONSTRAINT chk_body_member_assignment_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_body_member_assignment_body
    ON nss.body_member_assignment (body_master_pk);

CREATE INDEX IF NOT EXISTS idx_body_member_assignment_position
    ON nss.body_member_assignment (position_master_pk);

CREATE INDEX IF NOT EXISTS idx_body_member_assignment_person
    ON nss.body_member_assignment (person_pk);

CREATE INDEX IF NOT EXISTS idx_body_member_assignment_sangha_sevi
    ON nss.body_member_assignment (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_body_member_assignment_status
    ON nss.body_member_assignment (assignment_status);

CREATE INDEX IF NOT EXISTS idx_body_member_assignment_active
    ON nss.body_member_assignment (is_active);

-- Prevents the same person holding the same position in the
-- same body across two concurrently-active (open-ended) rows.
-- Does NOT cap seats per position (MEMBER allows many) — that
-- is a business/API composition rule (SOL-GOV-004 §25/§8.9).
CREATE UNIQUE INDEX IF NOT EXISTS uq_body_member_assignment_active_holder
    ON nss.body_member_assignment (body_master_pk, position_master_pk, person_pk)
    WHERE is_active = TRUE AND effective_to IS NULL;
