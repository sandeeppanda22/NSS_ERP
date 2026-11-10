-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 05_financial_receipt.sql
-- Table: nss.financial_receipt
-- Depth: 5 (depends on financial_transaction, person, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §11),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: Receipts are never deleted; cancellation uses status +
--       cancellation_reason (FIN-BR-033). receipt_number numbering scheme is
--       PENDING (FIN-BR-034): column and uniqueness only.
--       payment_method_master_data_pk (how the money came in: UPI, cash ...,
--       master_data category PAYMENT_METHOD) and instrument_reference (UPI
--       transaction id / cheque number) are additions to SOL-FIN-004 §11.3,
--       owner decision 2026-11-10.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_receipt
(
    financial_receipt_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    receipt_number VARCHAR(50) NOT NULL,

    financial_transaction_pk UUID NOT NULL,

    receipt_date DATE NOT NULL,

    amount NUMERIC(14, 2) NOT NULL,

    received_from VARCHAR(200) NULL,

    payment_method_master_data_pk UUID NULL,

    instrument_reference VARCHAR(100) NULL,

    person_pk UUID NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'DRAFT',

    cancellation_reason TEXT NULL,

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

    CONSTRAINT uq_financial_receipt_number UNIQUE (receipt_number),

    CONSTRAINT fk_financial_receipt_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_financial_receipt_method
        FOREIGN KEY (payment_method_master_data_pk)
        REFERENCES nss.master_data (master_data_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_receipt_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_financial_receipt_amount CHECK (amount > 0),

    CONSTRAINT chk_financial_receipt_status
        CHECK (status IN ('DRAFT', 'ISSUED', 'CANCELLED')),

    CONSTRAINT chk_financial_receipt_cancellation
        CHECK (status <> 'CANCELLED' OR cancellation_reason IS NOT NULL),

    CONSTRAINT chk_financial_receipt_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_financial_receipt_transaction
    ON nss.financial_receipt (financial_transaction_pk);
CREATE INDEX IF NOT EXISTS idx_financial_receipt_person
    ON nss.financial_receipt (person_pk) WHERE person_pk IS NOT NULL;
