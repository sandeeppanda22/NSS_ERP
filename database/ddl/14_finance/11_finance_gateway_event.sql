-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 11_finance_gateway_event.sql
-- Table: nss.finance_gateway_event
-- Depth: 9 (depends on upi_payment_request)
-- Version: 1.0
-- Authority: owner decision 2026-11-10 (UPI collection through a payment gateway).
-- Owner: NSS_ERP_ADMIN
-- Note: Append-only log of every webhook the gateway sent, valid or not.
--       It is the idempotency guard (a provider event id is processed once:
--       the partial unique index covers SIGNED events only, so a forged event
--       can never block a real one) and the forensic record of rejected calls.
--       payload may carry payer details (UPI id, contact): it is operational
--       evidence, never shown to members, and a retention period is an owner
--       decision (like system_event_log). No soft delete: it is never edited
--       or removed by the application.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_gateway_event
(
    finance_gateway_event_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    provider VARCHAR(30) NOT NULL,

    event_id VARCHAR(150) NOT NULL,

    event_type VARCHAR(80) NULL,

    upi_payment_request_pk UUID NULL,

    signature_valid BOOLEAN NOT NULL,

    payload JSONB NOT NULL,

    outcome VARCHAR(30) NOT NULL,

    detail TEXT NULL,

    received_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_finance_gateway_event_request
        FOREIGN KEY (upi_payment_request_pk)
        REFERENCES nss.upi_payment_request (upi_payment_request_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_gateway_event_outcome
        CHECK (outcome IN ('POSTED', 'PAID_NEEDS_REVIEW', 'DUPLICATE', 'IGNORED', 'FAILED',
                           'EXPIRED', 'UNKNOWN_REQUEST', 'REJECTED_SIGNATURE', 'ERROR'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_gateway_event_signed
    ON nss.finance_gateway_event (provider, event_id)
    WHERE signature_valid = TRUE;

CREATE INDEX IF NOT EXISTS idx_finance_gateway_event_request
    ON nss.finance_gateway_event (upi_payment_request_pk) WHERE upi_payment_request_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_finance_gateway_event_received
    ON nss.finance_gateway_event (received_at DESC);
