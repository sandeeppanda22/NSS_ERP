-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 01_financial_year.sql
-- Table: nss.financial_year
-- Depth: 1 (no Finance FK dependencies)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §7),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: Financial Year runs 01 April - 31 March (IMPLEMENTATION_DEPENDENCY_ORDER §38).
--       Status values from the lifecycle doc §3.1. Closed-year modification,
--       closing checklist and reopening are PENDING (lifecycle §40) and are
--       not modelled here.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_year
(
    financial_year_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- Business identifier, e.g. '2026-27'.
    year_code VARCHAR(20) NOT NULL,

    start_date DATE NOT NULL,

    end_date DATE NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'PLANNED',

    -- ── Lifecycle / Audit ───────────────────────────────

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT uq_financial_year_code UNIQUE (year_code),

    CONSTRAINT chk_financial_year_dates CHECK (start_date < end_date),

    CONSTRAINT chk_financial_year_status
        CHECK (status IN ('PLANNED', 'OPEN', 'CLOSING', 'CLOSED')),

    CONSTRAINT chk_financial_year_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_financial_year_status
    ON nss.financial_year (status);
