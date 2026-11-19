-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 03_fund_master.sql
-- Table: nss.fund_master
-- Depth: 3 (depends on financial_scope, organization)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §9),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: Restriction is a property of the fund (is_restricted), not a
--       lifecycle state (lifecycle §5.1). A Sinking Fund references its Sakha
--       through organization_pk (FIN-BR-023/024). Fund-type additions need
--       approval (FIN-BR-017).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.fund_master
(
    fund_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    fund_code VARCHAR(50) NOT NULL,

    fund_name VARCHAR(200) NOT NULL,

    fund_type VARCHAR(30) NOT NULL,

    financial_scope_pk UUID NOT NULL,

    is_restricted BOOLEAN NOT NULL
        DEFAULT FALSE,

    restriction_purpose TEXT NULL,

    organization_pk UUID NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'DRAFT',

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

    -- A fund code is unique within its Financial Scope.
    CONSTRAINT uq_fund_master_scope_code UNIQUE (financial_scope_pk, fund_code),

    CONSTRAINT fk_fund_master_scope
        FOREIGN KEY (financial_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fund_master_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_fund_master_type
        CHECK (fund_type IN (
            'GENERAL', 'SINKING_FUND', 'PUBLICATION', 'SPECIFIC_PURPOSE',
            'MEMBERSHIP_SUBSCRIPTION', 'PRANAMI', 'DONATION', 'GRANT',
            'PROPERTY_INCOME', 'MISCELLANEOUS')),

    CONSTRAINT chk_fund_master_status
        CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE')),

    -- A restricted fund must say what it is restricted to (FIN-BR-019).
    CONSTRAINT chk_fund_master_restriction_purpose
        CHECK (is_restricted = FALSE OR restriction_purpose IS NOT NULL),

    CONSTRAINT chk_fund_master_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_fund_master_org
    ON nss.fund_master (organization_pk) WHERE organization_pk IS NOT NULL;
