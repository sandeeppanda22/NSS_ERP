-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 09_financial_transfer.sql
-- Table: nss.financial_transfer
-- Depth: 7 (depends on financial_year, financial_scope, fund_master)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §13),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: Movement between two different scopes (FIN-BR-027..030). The
--       detailed inter-organization workflow is PENDING (lifecycle §40.10).
--       Fund-level checks (restricted fund rules) belong in the API.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_transfer
(
    financial_transfer_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    transfer_reference VARCHAR(50) NOT NULL,

    financial_year_pk UUID NOT NULL,

    source_scope_pk UUID NOT NULL,

    destination_scope_pk UUID NOT NULL,

    source_fund_pk UUID NULL,

    destination_fund_pk UUID NULL,

    amount NUMERIC(14, 2) NOT NULL,

    transfer_date DATE NOT NULL,

    purpose TEXT NOT NULL,

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

    CONSTRAINT uq_financial_transfer_reference UNIQUE (transfer_reference),

    CONSTRAINT fk_financial_transfer_year
        FOREIGN KEY (financial_year_pk)
        REFERENCES nss.financial_year (financial_year_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transfer_source_scope
        FOREIGN KEY (source_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transfer_destination_scope
        FOREIGN KEY (destination_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transfer_source_fund
        FOREIGN KEY (source_fund_pk)
        REFERENCES nss.fund_master (fund_master_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transfer_destination_fund
        FOREIGN KEY (destination_fund_pk)
        REFERENCES nss.fund_master (fund_master_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_financial_transfer_scopes_differ
        CHECK (source_scope_pk <> destination_scope_pk),

    CONSTRAINT chk_financial_transfer_amount CHECK (amount > 0),

    CONSTRAINT chk_financial_transfer_status
        CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'EXECUTED',
                          'COMPLETED', 'REJECTED', 'CANCELLED')),

    CONSTRAINT chk_financial_transfer_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_financial_transfer_year
    ON nss.financial_transfer (financial_year_pk);
CREATE INDEX IF NOT EXISTS idx_financial_transfer_source
    ON nss.financial_transfer (source_scope_pk);
CREATE INDEX IF NOT EXISTS idx_financial_transfer_destination
    ON nss.financial_transfer (destination_scope_pk);
