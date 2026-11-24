-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 24_finance_sinking_reimbursement.sql
-- Table: nss.finance_sinking_reimbursement
-- Depth: 4 (depends on financial_transaction)
-- Version: 1.0
-- Authority: Bye-Law C(i)(2)(xviii); business rule FIN-BR-026; owner request 2026-11-24.
-- Owner: NSS_ERP_ADMIN
-- Note: When the Kendra Sangha takes over the seva and pujas of a Sakha as a temporary measure, what it spends out of that Sakha's Sinking Fund
--       "shall be reimbursed by the Sakha Sangha subsequently" (C(i)(2)(xviii)). One row = one such expenditure and the obligation it creates:
--       the amount owed is the expenditure's amount, fixed when it is registered; the Sakha, the fund and the date come from the expenditure
--       itself (financial_transaction -> fund_master), so they are not stored twice. What has been reimbursed is never stored: it is read from the
--       POSTED / SETTLED income entries linked in finance_sinking_reimbursement_entry, so it cannot drift from the books.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_sinking_reimbursement
(
    finance_sinking_reimbursement_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    reimbursement_reference VARCHAR(50) NOT NULL,

    expenditure_transaction_pk UUID NOT NULL,

    takeover_reason VARCHAR(1000) NOT NULL,

    resolution_reference VARCHAR(100) NULL,

    amount_due NUMERIC(14, 2) NOT NULL,

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

    CONSTRAINT uq_finance_sinking_reimbursement_reference
        UNIQUE (reimbursement_reference),

    CONSTRAINT fk_finance_sinking_reimbursement_expenditure
        FOREIGN KEY (expenditure_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_sinking_reimbursement_amount
        CHECK (amount_due > 0),

    CONSTRAINT chk_finance_sinking_reimbursement_reason
        CHECK (BTRIM(takeover_reason) <> ''),

    CONSTRAINT chk_finance_sinking_reimbursement_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- One live obligation per expenditure (a removed one frees the expenditure to be registered again).
CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_sinking_reimbursement_expenditure
    ON nss.finance_sinking_reimbursement (expenditure_transaction_pk) WHERE is_active = TRUE;
