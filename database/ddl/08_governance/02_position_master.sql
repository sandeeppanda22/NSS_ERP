-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 02_position_master.sql
-- Table: nss.position_master
-- Depth: 0 (no governance FK dependencies)
-- Version: 1.0
-- Authority: SOL-GOV-002 §9-11, SOL-GOV-004 §7,
--            GOV-BR-010/012/013/014, DDL_CREATION_ORDER
--            (SOL-ARCH-010) #12
-- Owner: Governance
--
-- Design decisions:
--   - Reusable governance positions (PRESIDENT,
--     VICE_PRESIDENT, PARICHALAK, SECRETARY,
--     ASSISTANT_SECRETARY, TREASURER, MUKHYA_PUJAKA,
--     MEMBER) — frozen catalogue, SOL-GOV-002 §10
--   - position_code stable + UNIQUE (§7.4)
--   - display_order drives governance-body display
--   - Position is NOT an RBAC role: NO FK to role_master
--     (GOV-BR-014, SOL-GOV-004 §41). Governance position
--     and application permission are separate domains.
--   - A position is reusable across bodies (GOV-BR-013) —
--     body/position pairing lives in body_member_assignment
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.position_master
(
    -- ── Identity ────────────────────────────────────────

    position_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    position_code VARCHAR(50) NOT NULL,

    -- ── Attributes ──────────────────────────────────────

    position_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

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

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_position_master_code
        UNIQUE (position_code),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_position_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_position_master_display_order
    ON nss.position_master (display_order);

CREATE INDEX IF NOT EXISTS idx_position_master_active
    ON nss.position_master (is_active);
