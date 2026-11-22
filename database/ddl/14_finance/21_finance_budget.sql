-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 21_finance_budget.sql
-- Table: nss.finance_budget
-- Depth: 3 (depends on financial_year, organization)
-- Version: 1.0
-- Authority: NSS Bye-Law (Kendra Governing Body passes an annual budget; the draft is referred to the Advisory Board
--            for its considered views before the Governing Body's final consideration); business rule FIN-BR-041;
--            owner request 2026-11-22.
-- Owner: NSS_ERP_ADMIN
-- Note: ONE budget per Kendra organization per financial year. It moves through four recorded facts, never skipping one:
--         DRAFT -> REFERRED (sent to the Advisory Board on referred_on)
--               -> VIEWS_RECEIVED (the Advisory Board's considered views are on file: reference, date, summary)
--               -> PASSED (the Governing Body's resolution: reference + date).
--       The Advisory Board's views are REQUIRED to be on file before the budget can pass, but they are views, not a veto:
--       whatever they say, the Governing Body decides. A budget can be sent back to DRAFT until it is PASSED (the referral
--       facts are cleared, the audit trail keeps what they were); a PASSED budget is final.
--       The budget guides, it does not block: spending without a budget line, or above one, is shown as a flag only.
--       Referring files a letter in the Correspondence register (Kendra -> Advisory Board, auto-numbered, with the Advisory Board's own
--       inward copy); the Advisory Board's reply is filed the same way and its number becomes advisory_reference. The two letters are
--       linked here; reopening clears the links and the letters stay in Correspondence.
--       The lines live in nss.finance_budget_line (22_...).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_budget
(
    finance_budget_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    financial_year_pk UUID NOT NULL,

    organization_pk UUID NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'DRAFT',

    notes TEXT NULL,

    -- Referred to the Advisory Board.
    referred_on DATE NULL,

    -- The Advisory Board's considered views (a letter / minute reference, its date, what they said).
    advisory_reference VARCHAR(100) NULL,

    advisory_views_date DATE NULL,

    advisory_views_summary TEXT NULL,

    -- The Governing Body's resolution passing the budget.
    resolution_reference VARCHAR(100) NULL,

    resolution_date DATE NULL,

    -- The two letters filed in the Correspondence register by the budget itself (history stays there, never deleted): the referral to
    -- the Advisory Board (OUTWARD from the Kendra) and the Advisory Board's reply (OUTWARD from the Advisory Board).
    referral_correspondence_pk UUID NULL,

    views_correspondence_pk UUID NULL,

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

    CONSTRAINT fk_finance_budget_year
        FOREIGN KEY (financial_year_pk)
        REFERENCES nss.financial_year (financial_year_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_budget_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_budget_referral_letter
        FOREIGN KEY (referral_correspondence_pk)
        REFERENCES nss.correspondence (correspondence_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_budget_views_letter
        FOREIGN KEY (views_correspondence_pk)
        REFERENCES nss.correspondence (correspondence_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_budget_status
        CHECK (status IN ('DRAFT', 'REFERRED', 'VIEWS_RECEIVED', 'PASSED')),

    -- Each step's facts are present from that step on, and absent before it.
    CONSTRAINT chk_finance_budget_referral
        CHECK ((status = 'DRAFT') = (referred_on IS NULL)),

    CONSTRAINT chk_finance_budget_views
        CHECK (
            (status IN ('VIEWS_RECEIVED', 'PASSED')
             AND advisory_reference IS NOT NULL AND BTRIM(advisory_reference) <> ''
             AND advisory_views_date IS NOT NULL
             AND advisory_views_summary IS NOT NULL AND BTRIM(advisory_views_summary) <> '')
            OR
            (status IN ('DRAFT', 'REFERRED')
             AND advisory_reference IS NULL AND advisory_views_date IS NULL AND advisory_views_summary IS NULL)
        ),

    CONSTRAINT chk_finance_budget_resolution
        CHECK (
            (status = 'PASSED'
             AND resolution_reference IS NOT NULL AND BTRIM(resolution_reference) <> ''
             AND resolution_date IS NOT NULL)
            OR
            (status <> 'PASSED' AND resolution_reference IS NULL AND resolution_date IS NULL)
        ),

    -- The order of the facts: referral, then the views, then the resolution.
    CONSTRAINT chk_finance_budget_order
        CHECK (
            (advisory_views_date IS NULL OR referred_on IS NULL OR advisory_views_date >= referred_on)
            AND (resolution_date IS NULL OR advisory_views_date IS NULL OR resolution_date >= advisory_views_date)
        ),

    CONSTRAINT chk_finance_budget_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_budget_year_org
    ON nss.finance_budget (financial_year_pk, organization_pk) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_budget_organization
    ON nss.finance_budget (organization_pk);
