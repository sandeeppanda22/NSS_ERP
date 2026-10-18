-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 01_body_type_master.sql
-- Table: nss.body_type_master
-- Depth: 0 (no governance FK dependencies)
-- Version: 1.0
-- Authority: SOL-GOV-002 §4-5, SOL-GOV-004 §5,
--            GOV-BR-003/006, DDL_CREATION_ORDER (SOL-ARCH-010) #11
-- Owner: Governance
--
-- Design decisions:
--   - Classification master for governance bodies
--     (KENDRA_GOVERNING_BODY, SAKHA_GOVERNING_BODY,
--     ADVISORY_BOARD, MAHILA_PARICHALANA_MANDALI,
--     SEVAK_SANGHA_EXECUTIVE, COMMITTEE, ...)
--   - body_type_code stable + UNIQUE (GOV-BR-006, §5.5)
--   - Own master table (like role_master), NOT a
--     master_data category — matches frozen DDL order #11
--   - Historically-used types are soft-deleted, never
--     physically removed (§5.6, GOV-BR-063)
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.body_type_master
(
    -- ── Identity ────────────────────────────────────────

    body_type_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    body_type_code VARCHAR(50) NOT NULL,

    -- ── Attributes ──────────────────────────────────────

    body_type_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

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

    CONSTRAINT uq_body_type_master_code
        UNIQUE (body_type_code),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_body_type_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_body_type_master_active
    ON nss.body_type_master (is_active);
