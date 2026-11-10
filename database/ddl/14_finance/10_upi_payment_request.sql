-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 10_upi_payment_request.sql
-- Table: nss.upi_payment_request
-- Depth: 8 (depends on financial_account, finance_head, financial_scope,
--           fund_master, financial_transaction, financial_receipt, person, sangha_sevi)
-- Version: 1.0
-- Authority: owner decision 2026-11-10 (UPI collection through a payment gateway,
--            money to each Sangha's own account).
-- Owner: NSS_ERP_ADMIN
-- Note: One request to collect money by UPI. The gateway tells us it was paid
--       through a SIGNED webhook (finance_gateway_event); only then is the
--       transaction posted and the receipt issued - never from a browser
--       redirect. financial_transaction_pk / financial_receipt_pk stay NULL
--       while a PAID request waits for review (review_reason says why:
--       amount mismatch, no open financial year, ...).
--       request_reference is minted by next_id() (PRQ<n>).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.upi_payment_request
(
    upi_payment_request_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    request_reference VARCHAR(50) NOT NULL,

    financial_account_pk UUID NOT NULL,

    finance_head_pk UUID NOT NULL,

    financial_scope_pk UUID NOT NULL,

    fund_master_pk UUID NULL,

    amount NUMERIC(14, 2) NOT NULL,

    payer_person_pk UUID NULL,

    payer_sangha_sevi_pk UUID NULL,

    payer_name VARCHAR(200) NULL,

    note VARCHAR(500) NULL,

    provider VARCHAR(30) NOT NULL,

    provider_order_id VARCHAR(100) NULL,

    pay_url TEXT NULL,

    upi_uri TEXT NULL,

    expires_at TIMESTAMPTZ NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'CREATED',

    provider_payment_id VARCHAR(100) NULL,

    paid_amount NUMERIC(14, 2) NULL,

    paid_at TIMESTAMPTZ NULL,

    failure_reason TEXT NULL,

    review_reason TEXT NULL,

    financial_transaction_pk UUID NULL,

    financial_receipt_pk UUID NULL,

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

    CONSTRAINT uq_upi_payment_request_reference UNIQUE (request_reference),

    -- The provider's order id identifies the request when its webhook arrives.
    CONSTRAINT uq_upi_payment_request_provider_order UNIQUE (provider, provider_order_id),

    CONSTRAINT fk_upi_payment_request_account
        FOREIGN KEY (financial_account_pk)
        REFERENCES nss.financial_account (financial_account_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_head
        FOREIGN KEY (finance_head_pk)
        REFERENCES nss.finance_head (finance_head_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_scope
        FOREIGN KEY (financial_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_fund
        FOREIGN KEY (fund_master_pk)
        REFERENCES nss.fund_master (fund_master_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_person
        FOREIGN KEY (payer_person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_sangha_sevi
        FOREIGN KEY (payer_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_upi_payment_request_receipt
        FOREIGN KEY (financial_receipt_pk)
        REFERENCES nss.financial_receipt (financial_receipt_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_upi_payment_request_amount CHECK (amount > 0),

    CONSTRAINT chk_upi_payment_request_status
        CHECK (status IN ('CREATED', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'CANCELLED')),

    -- A PAID request always carries the evidence of payment.
    CONSTRAINT chk_upi_payment_request_paid
        CHECK (status <> 'PAID' OR (paid_at IS NOT NULL AND provider_payment_id IS NOT NULL AND paid_amount IS NOT NULL)),

    -- The posted transaction and its receipt only ever exist for a PAID request.
    CONSTRAINT chk_upi_payment_request_posted
        CHECK (financial_transaction_pk IS NULL OR status = 'PAID'),

    CONSTRAINT chk_upi_payment_request_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_upi_payment_request_account ON nss.upi_payment_request (financial_account_pk);
CREATE INDEX IF NOT EXISTS idx_upi_payment_request_head ON nss.upi_payment_request (finance_head_pk);
CREATE INDEX IF NOT EXISTS idx_upi_payment_request_scope ON nss.upi_payment_request (financial_scope_pk);
CREATE INDEX IF NOT EXISTS idx_upi_payment_request_status ON nss.upi_payment_request (status);
CREATE INDEX IF NOT EXISTS idx_upi_payment_request_payer_person ON nss.upi_payment_request (payer_person_pk) WHERE payer_person_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_upi_payment_request_review
    ON nss.upi_payment_request (status) WHERE status = 'PAID' AND financial_transaction_pk IS NULL;
