-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 06_financial_payment.sql
-- Table: nss.financial_payment
-- Depth: 6 (depends on financial_transaction, person, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §12),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: Payments are never deleted (FIN-BR-037). The payment method is a
--       master_data FK (category PAYMENT_METHOD, admin-extendable; owner
--       decision 2026-11-10 - the value catalogue is PENDING in SOL-FIN-004
--       §19). instrument_reference holds the UPI transaction id / cheque or
--       draft number / bank reference (not in the design doc; added with the
--       payment method). Payment lifecycle per lifecycle §17.1;
--       CANCELLED is added for the 'cancellation' path in §17.3 and
--       FAILED is intentionally absent (failure/retry lifecycle PENDING).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_payment
(
    financial_payment_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    payment_reference VARCHAR(50) NOT NULL,

    financial_transaction_pk UUID NOT NULL,

    payment_date DATE NOT NULL,

    amount NUMERIC(14, 2) NOT NULL,

    paid_to VARCHAR(200) NULL,

    payment_method_master_data_pk UUID NULL,

    instrument_reference VARCHAR(100) NULL,

    person_pk UUID NULL,

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

    CONSTRAINT uq_financial_payment_reference UNIQUE (payment_reference),

    CONSTRAINT fk_financial_payment_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_financial_payment_method
        FOREIGN KEY (payment_method_master_data_pk)
        REFERENCES nss.master_data (master_data_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_payment_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_financial_payment_amount CHECK (amount > 0),

    CONSTRAINT chk_financial_payment_status
        CHECK (status IN ('DRAFT', 'APPROVED', 'INITIATED', 'COMPLETED',
                          'CANCELLED')),

    CONSTRAINT chk_financial_payment_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_financial_payment_transaction
    ON nss.financial_payment (financial_transaction_pk);
CREATE INDEX IF NOT EXISTS idx_financial_payment_person
    ON nss.financial_payment (person_pk) WHERE person_pk IS NOT NULL;
