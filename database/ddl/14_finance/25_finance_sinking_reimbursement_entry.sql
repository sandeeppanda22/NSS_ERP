-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 25_finance_sinking_reimbursement_entry.sql
-- Table: nss.finance_sinking_reimbursement_entry
-- Depth: 5 (depends on finance_sinking_reimbursement, financial_transaction)
-- Version: 1.0
-- Authority: Bye-Law C(i)(2)(xviii); business rule FIN-BR-026; owner request 2026-11-24.
-- Owner: NSS_ERP_ADMIN
-- Note: Links an income entry (the Sakha paying back into its Sinking Fund) to the obligation it settles. The entry is an ordinary
--       financial_transaction and goes through the ordinary lifecycle; it counts as reimbursed only once POSTED / SETTLED. An entry belongs
--       to at most one obligation.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_sinking_reimbursement_entry
(
    finance_sinking_reimbursement_entry_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    finance_sinking_reimbursement_pk UUID NOT NULL,

    financial_transaction_pk UUID NOT NULL,

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

    CONSTRAINT fk_finance_sinking_entry_reimbursement
        FOREIGN KEY (finance_sinking_reimbursement_pk)
        REFERENCES nss.finance_sinking_reimbursement (finance_sinking_reimbursement_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_sinking_entry_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_sinking_entry_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_sinking_entry_transaction
    ON nss.finance_sinking_reimbursement_entry (financial_transaction_pk) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_sinking_entry_reimbursement
    ON nss.finance_sinking_reimbursement_entry (finance_sinking_reimbursement_pk);
