-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 19_upi_payment_request_line.sql
-- Table: nss.upi_payment_request_line
-- Depth: 8 (depends on upi_payment_request, finance_head, financial_scope, fund_master, financial_transaction, financial_receipt)
-- Version: 1.0
-- Authority: owner request 2026-11-17 (a member pays several Pranami / contributions in ONE UPI payment).
-- Owner: NSS_ERP_ADMIN
-- Note: A payment request normally carries ONE head (upi_payment_request.finance_head_pk) and books ONE transaction. A request that
--       pays several contributions at once has one LINE per contribution here (and its own head / scope / fund / amount): the
--       request's amount is the sum of its lines, its finance_head_pk / financial_scope_pk / fund_master_pk are those of the first
--       line (they are NOT NULL on the request), and the gateway order is a single order for the total into ONE receiving account
--       (every line collects into that same account, i.e. the same Sangha). When the signed webhook says it is paid, each line is
--       booked as its own transaction with its own receipt (financial_transaction_pk / financial_receipt_pk are filled in), all or
--       nothing. A request with no lines is an ordinary single-head request. Soft delete only; history is never removed.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.upi_payment_request_line
(
    upi_payment_request_line_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    upi_payment_request_pk UUID NOT NULL,

    line_no SMALLINT NOT NULL,

    finance_head_pk UUID NOT NULL,

    financial_scope_pk UUID NOT NULL,

    fund_master_pk UUID NULL,

    amount NUMERIC(14, 2) NOT NULL,

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

    CONSTRAINT fk_uprl_request
        FOREIGN KEY (upi_payment_request_pk)
        REFERENCES nss.upi_payment_request (upi_payment_request_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_uprl_head
        FOREIGN KEY (finance_head_pk)
        REFERENCES nss.finance_head (finance_head_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_uprl_scope
        FOREIGN KEY (financial_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_uprl_fund
        FOREIGN KEY (fund_master_pk)
        REFERENCES nss.fund_master (fund_master_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_uprl_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_uprl_receipt
        FOREIGN KEY (financial_receipt_pk)
        REFERENCES nss.financial_receipt (financial_receipt_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_uprl_amount
        CHECK (amount > 0),

    CONSTRAINT chk_uprl_line_no
        CHECK (line_no BETWEEN 1 AND 50),

    CONSTRAINT chk_uprl_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- A line number and a head each appear once per request.
CREATE UNIQUE INDEX IF NOT EXISTS uq_uprl_line_no
    ON nss.upi_payment_request_line (upi_payment_request_pk, line_no) WHERE is_active = TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_uprl_head
    ON nss.upi_payment_request_line (upi_payment_request_pk, finance_head_pk) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_uprl_head
    ON nss.upi_payment_request_line (finance_head_pk) WHERE is_active = TRUE;
