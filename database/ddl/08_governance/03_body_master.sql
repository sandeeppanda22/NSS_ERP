-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 03_body_master.sql
-- Table: nss.body_master
-- Depth: 4 (depends on body_type_master, organization)
-- Version: 1.0
-- Authority: SOL-GOV-002 §6-8, SOL-GOV-004 §6/§16/§17,
--            GOV-BR-007/008/058/059/086,
--            DDL_CREATION_ORDER (SOL-ARCH-010) #38
-- Owner: Governance
--
-- Design decisions:
--   - Actual governance body (Kendra Governing Body,
--     Sakha Governing Body — Sakha A, Advisory Board,
--     Mahila Parichalana Mandali, ...)
--   - body_type_master_pk FK — every body is classified
--     (GOV-BR-006)
--   - organization_pk FK to nss.organization, NULLABLE:
--     NSS-wide / Kendra-level bodies may carry NULL;
--     org-scoped bodies (e.g. a specific Sakha Governing
--     Body) carry the org (SOL-GOV-004 §16, GOV-BR-059).
--     No new organization structure is introduced
--     (SOL-GOV-004 §44, GOV-BR-058).
--   - body_code stable + UNIQUE (§6.5)
--   - body_status: lifecycle vocabulary finalized at DDL
--     per GOV-BR-086 / SOL-GOV-004 §6.7 (Active,
--     Reconstituted, Historical) + INACTIVE for parity
--     with project soft-state. Enforced via CHECK (same
--     pattern as user_account.account_status).
--   - effective_from / effective_to express body term;
--     history preserved, never physically deleted
--     (GOV-BR-063/068, §31)
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.body_master
(
    -- ── Identity ────────────────────────────────────────

    body_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    body_type_master_pk UUID NOT NULL,

    body_code VARCHAR(50) NOT NULL,

    -- ── Attributes ──────────────────────────────────────

    body_name VARCHAR(200) NOT NULL,

    description TEXT NULL,

    -- ── Organizational Scope ────────────────────────────

    organization_pk UUID NULL,

    -- ── Lifecycle ───────────────────────────────────────

    body_status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

    effective_from DATE NULL,

    effective_to DATE NULL,

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

    CONSTRAINT fk_body_master_body_type
        FOREIGN KEY (body_type_master_pk)
        REFERENCES nss.body_type_master (body_type_master_pk),

    CONSTRAINT fk_body_master_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_body_master_code
        UNIQUE (body_code),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_body_master_status
        CHECK (body_status IN ('ACTIVE', 'RECONSTITUTED', 'HISTORICAL', 'INACTIVE')),

    CONSTRAINT chk_body_master_effective_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from),

    CONSTRAINT chk_body_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_body_master_body_type
    ON nss.body_master (body_type_master_pk);

CREATE INDEX IF NOT EXISTS idx_body_master_organization
    ON nss.body_master (organization_pk)
    WHERE organization_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_body_master_status
    ON nss.body_master (body_status);

CREATE INDEX IF NOT EXISTS idx_body_master_active
    ON nss.body_master (is_active);
