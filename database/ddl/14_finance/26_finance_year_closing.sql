-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 26_finance_year_closing.sql
-- Table: nss.finance_year_closing
-- Depth: 3 (depends on financial_year, organization)
-- Version: 1.0
-- Authority: owner request 2026-11-25 ("year closing should be Sakha and Kendra wise"); business rules FIN-BR-003, FIN-BR-004.
-- Owner: NSS_ERP_ADMIN
-- Note: The financial year stays ONE calendar record (financial_year, PLANNED -> OPEN -> CLOSING -> CLOSED, set by the NSS-wide authority). On top
--       of it each Sangha - a Sakha, or the Kendra - closes ITS OWN books for the year: one row per (year, Sangha). No row means the Sangha is
--       still OPEN in that year; CLOSING = it takes no new entries but may finish what is in progress; CLOSED = its books for the year are shut
--       (nothing unfinished may remain). The year itself can be CLOSED only when every Sangha with activity in it has closed.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_year_closing
(
    finance_year_closing_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    financial_year_pk UUID NOT NULL,

    organization_pk UUID NOT NULL,

    status VARCHAR(10) NOT NULL,

    closing_started_on DATE NOT NULL
        DEFAULT CURRENT_DATE,

    closed_on DATE NULL,

    remarks VARCHAR(500) NULL,

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

    CONSTRAINT fk_finance_year_closing_year
        FOREIGN KEY (financial_year_pk)
        REFERENCES nss.financial_year (financial_year_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_year_closing_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_year_closing_status
        CHECK (status IN ('CLOSING', 'CLOSED')),

    CONSTRAINT chk_finance_year_closing_dates
        CHECK (
            (status = 'CLOSING' AND closed_on IS NULL)
            OR
            (status = 'CLOSED' AND closed_on IS NOT NULL AND closed_on >= closing_started_on)
        ),

    CONSTRAINT chk_finance_year_closing_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_year_closing_year_organization
    ON nss.finance_year_closing (financial_year_pk, organization_pk) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_year_closing_organization
    ON nss.finance_year_closing (organization_pk);
