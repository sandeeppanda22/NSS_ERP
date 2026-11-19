-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 06_financial_transaction.sql
-- Table: nss.financial_transaction
-- Depth: 4 (depends on financial_year, financial_scope, fund_master, finance_head, person, sangha_sevi)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/finance/
--            04_finance_table_design.md (SOL-FIN-004 §10),
--            05_finance_lifecycle.md (SOL-FIN-005)
-- Owner: NSS_ERP_ADMIN
-- Note: The purpose of a transaction is its FINANCE HEAD (finance_head_pk, Sangha-
--       customizable; owner decision 2026-11-10). transaction_category is kept as
--       an immutable SNAPSHOT of the head's code at booking time (head codes never
--       change), so history, filters and reports survive a head being renamed or
--       switched off. The old fixed category CHECK is gone; the allowed heads are
--       data (see finance_head and the API rules).
--       The single ledger table (FIN-BR-011); receipt/payment attach as
--       evidence. amount is NUMERIC(14,2) and strictly positive: direction is
--       carried by transaction_type, not the sign. PROPOSED - precision and
--       the ADJUSTMENT sign convention are not frozen (SOL-FIN-004 §19,
--       lifecycle §40 reversal mechanism PENDING).
--       transaction_reference is the business id; its generator is not yet
--       defined, so the API will mint it via next_id() once a FINANCIAL_
--       TRANSACTION id_sequence_master row is approved.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.financial_transaction
(
    financial_transaction_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    transaction_reference VARCHAR(50) NOT NULL,

    financial_year_pk UUID NOT NULL,

    financial_scope_pk UUID NOT NULL,

    fund_master_pk UUID NULL,

    transaction_type VARCHAR(20) NOT NULL,

    finance_head_pk UUID NOT NULL,

    transaction_category VARCHAR(50) NOT NULL,

    amount NUMERIC(14, 2) NOT NULL,

    transaction_date DATE NOT NULL,

    description TEXT NULL,

    person_pk UUID NULL,

    sangha_sevi_pk UUID NULL,

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

    CONSTRAINT uq_financial_transaction_reference UNIQUE (transaction_reference),

    CONSTRAINT fk_financial_transaction_year
        FOREIGN KEY (financial_year_pk)
        REFERENCES nss.financial_year (financial_year_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transaction_scope
        FOREIGN KEY (financial_scope_pk)
        REFERENCES nss.financial_scope (financial_scope_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transaction_head
        FOREIGN KEY (finance_head_pk)
        REFERENCES nss.finance_head (finance_head_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transaction_fund
        FOREIGN KEY (fund_master_pk)
        REFERENCES nss.fund_master (fund_master_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transaction_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_financial_transaction_sangha_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_financial_transaction_amount CHECK (amount > 0),

    CONSTRAINT chk_financial_transaction_type
        CHECK (transaction_type IN ('INCOME', 'EXPENSE', 'ADJUSTMENT')),

    CONSTRAINT chk_financial_transaction_status
        CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'POSTED',
                          'SETTLED', 'REJECTED', 'CANCELLED')),

    CONSTRAINT chk_financial_transaction_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_financial_transaction_year
    ON nss.financial_transaction (financial_year_pk);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_scope
    ON nss.financial_transaction (financial_scope_pk);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_fund
    ON nss.financial_transaction (fund_master_pk) WHERE fund_master_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_financial_transaction_type
    ON nss.financial_transaction (transaction_type);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_head
    ON nss.financial_transaction (finance_head_pk);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_category
    ON nss.financial_transaction (transaction_category);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_date
    ON nss.financial_transaction (transaction_date);
CREATE INDEX IF NOT EXISTS idx_financial_transaction_person
    ON nss.financial_transaction (person_pk) WHERE person_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_financial_transaction_sangha_sevi
    ON nss.financial_transaction (sangha_sevi_pk) WHERE sangha_sevi_pk IS NOT NULL;
