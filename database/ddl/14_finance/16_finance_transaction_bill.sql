-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 16_finance_transaction_bill.sql
-- Table: nss.finance_transaction_bill
-- Depth: 4 (depends on financial_transaction)
-- Version: 1.0
-- Authority: owner decision 2026-11-17 (every spend of a Sakha is supported by bills that add up to the amount).
-- Owner: NSS_ERP_ADMIN
-- Note: One row per bill / receipt / invoice supporting an EXPENSE transaction (the vendor's, or the member's who paid on
--       the Sangha's behalf and is being reimbursed). The app has no file upload yet (owner decision 2026-11-17): a bill is a
--       RECORD (vendor, number, date, amount, optional https link such as a Drive photo); the paper stays with the Treasurer.
--       The API requires the live bills to add up to the transaction amount before a Sakha spend can be submitted.
--       Soft delete only (a wrong bill is removed from the live list, the row stays for the audit trail).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_transaction_bill
(
    finance_transaction_bill_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    financial_transaction_pk UUID NOT NULL,

    vendor_name VARCHAR(200) NOT NULL,

    bill_number VARCHAR(100) NULL,

    bill_date DATE NOT NULL,

    amount NUMERIC(14, 2) NOT NULL,

    document_url VARCHAR(500) NULL,

    description TEXT NULL,

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

    CONSTRAINT fk_ftb_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_ftb_amount
        CHECK (amount > 0),

    CONSTRAINT chk_ftb_vendor_not_blank
        CHECK (BTRIM(vendor_name) <> ''),

    -- Only an https link is ever stored (it is shown to approvers as a link).
    CONSTRAINT chk_ftb_url
        CHECK (document_url IS NULL OR document_url ~* '^https://[^[:space:]]+$'),

    CONSTRAINT chk_ftb_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_ftb_transaction
    ON nss.finance_transaction_bill (financial_transaction_pk) WHERE is_active = TRUE;
