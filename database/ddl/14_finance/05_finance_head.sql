-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 05_finance_head.sql
-- Table: nss.finance_head
-- Depth: 3 (depends on organization, financial_scope, fund_master, financial_account)
-- Version: 1.0
-- Authority: owner decision 2026-11-10 (finance heads must be customizable, per
--            Sangha, with Kendra templates) - replaces the fixed 12-value
--            transaction-category CHECK of SOL-FIN-004 §10.5; FIN-BR-017 (no
--            unapproved fund category) is honoured by letting only finance
--            administrators create heads.
-- Owner: NSS_ERP_ADMIN
-- Note: A finance head is the PURPOSE a transaction is booked under (Annual
--       Pranami, Festival donation, Electricity ...). organization_pk NULL = a
--       TEMPLATE published by the Kendra (blueprint + the heads of scopes that
--       have no organization); a Sangha adopts templates into its own
--       catalogue (organization_pk = that Sangha, template_head_pk = source).
--       A head carries the RULES its transactions follow: direction,
--       restricted money (FIN-BR-019..022), a required fund type (Sinking Fund,
--       FIN-BR-023/024), whether it appears in the member's own Pranami tab,
--       and whether and WHERE it can be collected by UPI.
--       Cross-row consistency (the collection scope / fund / account belong to
--       the head's organization) is enforced by the API.
--       head_code is immutable once created; its direction and restriction
--       are immutable once a transaction uses the head (API).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_head
(
    finance_head_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_pk UUID NULL,

    head_code VARCHAR(50) NOT NULL,

    head_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

    direction VARCHAR(10) NOT NULL,

    is_restricted BOOLEAN NOT NULL
        DEFAULT FALSE,

    restriction_purpose TEXT NULL,

    required_fund_type VARCHAR(30) NULL,

    is_pranami BOOLEAN NOT NULL
        DEFAULT FALSE,

    allow_upi BOOLEAN NOT NULL
        DEFAULT FALSE,

    collection_scope_pk UUID NULL,

    collection_fund_pk UUID NULL,

    collection_account_pk UUID NULL,

    template_head_pk UUID NULL,

    display_order INTEGER NOT NULL
        DEFAULT 100,

    status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

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

    CONSTRAINT uq_finance_head_org_code UNIQUE (organization_pk, head_code),

    CONSTRAINT fk_finance_head_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_head_collection_scope
        FOREIGN KEY (collection_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_head_collection_fund
        FOREIGN KEY (collection_fund_pk)
        REFERENCES nss.fund_master (fund_master_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_head_collection_account
        FOREIGN KEY (collection_account_pk)
        REFERENCES nss.financial_account (financial_account_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_head_template
        FOREIGN KEY (template_head_pk)
        REFERENCES nss.finance_head (finance_head_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_head_code
        CHECK (head_code ~ '^[A-Z][A-Z0-9_]{1,49}$'),

    CONSTRAINT chk_finance_head_direction
        CHECK (direction IN ('INCOME', 'EXPENSE')),

    CONSTRAINT chk_finance_head_status
        CHECK (status IN ('ACTIVE', 'INACTIVE')),

    CONSTRAINT chk_finance_head_fund_type
        CHECK (required_fund_type IS NULL OR required_fund_type IN (
            'GENERAL', 'SINKING_FUND', 'PUBLICATION', 'SPECIFIC_PURPOSE',
            'MEMBERSHIP_SUBSCRIPTION', 'PRANAMI', 'DONATION', 'GRANT',
            'PROPERTY_INCOME', 'MISCELLANEOUS')),

    -- A restricted head must say what it is restricted to (FIN-BR-020).
    CONSTRAINT chk_finance_head_restriction
        CHECK (is_restricted = FALSE OR restriction_purpose IS NOT NULL),

    -- Pranami and UPI collection are about money coming IN.
    CONSTRAINT chk_finance_head_income_only
        CHECK (direction = 'INCOME' OR (is_pranami = FALSE AND allow_upi = FALSE)),

    -- UPI collection needs to know where to book and where the money lands.
    CONSTRAINT chk_finance_head_upi_target
        CHECK (allow_upi = FALSE OR (collection_scope_pk IS NOT NULL AND collection_account_pk IS NOT NULL)),

    -- A template (no organization) is a blueprint: it can never collect money itself.
    CONSTRAINT chk_finance_head_template_inert
        CHECK (organization_pk IS NOT NULL
               OR (allow_upi = FALSE AND collection_scope_pk IS NULL
                   AND collection_fund_pk IS NULL AND collection_account_pk IS NULL)),

    CONSTRAINT chk_finance_head_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- UNIQUE (organization_pk, head_code) treats NULLs as distinct, so templates need their own rule.
CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_head_template_code
    ON nss.finance_head (head_code)
    WHERE organization_pk IS NULL;

CREATE INDEX IF NOT EXISTS idx_finance_head_org
    ON nss.finance_head (organization_pk) WHERE organization_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_finance_head_pranami
    ON nss.finance_head (organization_pk) WHERE is_pranami = TRUE AND allow_upi = TRUE;
