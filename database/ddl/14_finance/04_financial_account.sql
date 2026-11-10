-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 04_financial_account.sql
-- Table: nss.financial_account
-- Depth: 2 (depends on organization)
-- Version: 1.0
-- Authority: owner decision 2026-11-10 (UPI collection into EACH Sangha's own
--            account), FIN-BR-044..047 (bank accounts; the full ERP bank-
--            account model is still PENDING - this is the minimum UPI needs),
--            REF-003-F[b] / REF-MS-7(ii) (funds banked in a Post Office
--            Savings Bank or a nationalised bank).
-- Owner: NSS_ERP_ADMIN
-- Note: A receiving account of one organization (a Sakha, the Kendra, ...).
--       Deliberately stores NO full account number (only the last four digits
--       for identification) and NO secrets: gateway_credential_ref is the NAME
--       of a server-side credential set (environment variables
--       UPI_<REF>_KEY_ID / _KEY_SECRET / _WEBHOOK_SECRET), never a key itself.
--       gateway_merchant_ref is the provider-side merchant / linked-account id
--       (an identifier, not a secret). gateway_provider is validated by the
--       API against the registered adapters (not a CHECK, so a new adapter
--       needs no rebuild).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_account
(
    financial_account_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_pk UUID NOT NULL,

    account_label VARCHAR(100) NOT NULL,

    account_type VARCHAR(20) NOT NULL
        DEFAULT 'BANK',

    bank_name VARCHAR(150) NULL,

    branch_name VARCHAR(150) NULL,

    account_holder_name VARCHAR(200) NOT NULL,

    account_number_last4 VARCHAR(4) NULL,

    ifsc_code VARCHAR(11) NULL,

    upi_vpa VARCHAR(100) NULL,

    gateway_provider VARCHAR(30) NULL,

    gateway_credential_ref VARCHAR(40) NULL,

    gateway_merchant_ref VARCHAR(100) NULL,

    is_default BOOLEAN NOT NULL
        DEFAULT FALSE,

    status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

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

    CONSTRAINT uq_financial_account_label UNIQUE (organization_pk, account_label),

    CONSTRAINT fk_financial_account_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_financial_account_type
        CHECK (account_type IN ('BANK', 'POST_OFFICE')),

    CONSTRAINT chk_financial_account_status
        CHECK (status IN ('ACTIVE', 'INACTIVE')),

    CONSTRAINT chk_financial_account_last4
        CHECK (account_number_last4 IS NULL OR account_number_last4 ~ '^[0-9]{4}$'),

    CONSTRAINT chk_financial_account_ifsc
        CHECK (ifsc_code IS NULL OR ifsc_code ~ '^[A-Z]{4}0[A-Z0-9]{6}$'),

    CONSTRAINT chk_financial_account_vpa
        CHECK (upi_vpa IS NULL OR upi_vpa ~ '^[A-Za-z0-9._-]{2,}@[A-Za-z]{2,}$'),

    -- Only an environment-variable-safe NAME, so a key can never be pasted here by mistake.
    CONSTRAINT chk_financial_account_credential_ref
        CHECK (gateway_credential_ref IS NULL OR gateway_credential_ref ~ '^[A-Z][A-Z0-9_]{0,39}$'),

    -- A gateway account needs its credential set to be usable.
    CONSTRAINT chk_financial_account_gateway
        CHECK (gateway_provider IS NULL OR gateway_credential_ref IS NOT NULL),

    CONSTRAINT chk_financial_account_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- At most one default account per organization.
CREATE UNIQUE INDEX IF NOT EXISTS uq_financial_account_default
    ON nss.financial_account (organization_pk)
    WHERE is_default = TRUE AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_financial_account_org
    ON nss.financial_account (organization_pk);
