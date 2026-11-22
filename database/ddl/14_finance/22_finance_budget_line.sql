-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 22_finance_budget_line.sql
-- Table: nss.finance_budget_line
-- Depth: 4 (depends on finance_budget, finance_head)
-- Version: 1.0
-- Authority: business rule FIN-BR-041 (Kendra annual budget); owner request 2026-11-22.
-- Owner: NSS_ERP_ADMIN
-- Note: One planned amount per finance head of a budget (anticipated income on an INCOME head, anticipated spending on an
--       EXPENSE head). The head's direction decides which side it is on, so it is not stored twice. Lines can be changed in any
--       budget status (owner 2026-11-22, "edit always"; past DRAFT the API requires a reason, kept in the audit trail); "actual" is never stored - it is read from the POSTED / SETTLED
--       transactions of that head in that year, so it cannot drift from the books.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_budget_line
(
    finance_budget_line_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    finance_budget_pk UUID NOT NULL,

    finance_head_pk UUID NOT NULL,

    amount NUMERIC(14, 2) NOT NULL,

    notes VARCHAR(500) NULL,

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

    CONSTRAINT fk_finance_budget_line_budget
        FOREIGN KEY (finance_budget_pk)
        REFERENCES nss.finance_budget (finance_budget_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_budget_line_head
        FOREIGN KEY (finance_head_pk)
        REFERENCES nss.finance_head (finance_head_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_budget_line_amount
        CHECK (amount > 0),

    CONSTRAINT chk_finance_budget_line_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_budget_line_head
    ON nss.finance_budget_line (finance_budget_pk, finance_head_pk) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_budget_line_head
    ON nss.finance_budget_line (finance_head_pk);
