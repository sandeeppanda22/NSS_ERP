-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 02_financial_scope.sql
-- Table: nss.financial_scope
-- Depth: 2 (depends on financial_year, organization)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §8),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: A Financial Scope is NOT an Organization (FIN-ARCH-001): one
--       organization may own several scopes (FIN-BR-007). organization_pk is
--       nullable (special-purpose scopes). Scope-type additions need approval.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_scope
(
    financial_scope_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    scope_code VARCHAR(50) NOT NULL,

    scope_name VARCHAR(200) NOT NULL,

    scope_type VARCHAR(30) NOT NULL,

    organization_pk UUID NULL,

    -- Nullable: a scope may span years.
    financial_year_pk UUID NULL,

    -- Hierarchical scopes (design candidate, SOL-FIN-004 §8.3).
    parent_scope_pk UUID NULL,

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

    CONSTRAINT uq_financial_scope_code UNIQUE (scope_code),

    CONSTRAINT fk_financial_scope_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_scope_year
        FOREIGN KEY (financial_year_pk)
        REFERENCES nss.financial_year (financial_year_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_scope_parent
        FOREIGN KEY (parent_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_financial_scope_parent_not_self
        CHECK (parent_scope_pk IS NULL OR parent_scope_pk <> financial_scope_pk),

    CONSTRAINT chk_financial_scope_type
        CHECK (scope_type IN
            ('ORGANIZATION', 'EVENT', 'SPECIAL_PURPOSE', 'RESTRICTED_FUND')),

    CONSTRAINT chk_financial_scope_status
        CHECK (status IN ('DRAFT', 'ACTIVE', 'CLOSING', 'CLOSED')),

    CONSTRAINT chk_financial_scope_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_financial_scope_org
    ON nss.financial_scope (organization_pk) WHERE organization_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_financial_scope_year
    ON nss.financial_scope (financial_year_pk) WHERE financial_year_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_financial_scope_parent
    ON nss.financial_scope (parent_scope_pk) WHERE parent_scope_pk IS NOT NULL;
