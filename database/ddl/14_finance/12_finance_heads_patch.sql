-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 12_finance_heads_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-10)
-- Authority: owner decision 2026-11-10 (customizable finance heads).
-- =====================================================
-- 06_financial_transaction.sql is existence-gated, so a database that already ran
-- the ORIGINAL shape (fixed transaction_category CHECK, no finance_head_pk) never
-- sees its new columns. This patch brings such a database up to the same shape as
-- a fresh build; on a fresh build every statement is a no-op.
--
-- Order matters: it must run AFTER the table finance_head exists (build Phase 11i
-- DDL) and AFTER seed/12_finance/02_finance_head_templates_patch.sql, whose 12
-- Kendra templates carry exactly the old category codes - that is what lets the
-- backfill below map every existing transaction to a head losslessly.
-- Backfilled rows point at the TEMPLATE head (organization_pk NULL) of their old
-- category; that is historical and read-only: the API requires NEW transactions
-- to use a head owned by the scope's organization.
-- =====================================================

ALTER TABLE nss.financial_transaction
    ADD COLUMN IF NOT EXISTS finance_head_pk UUID NULL;

ALTER TABLE nss.financial_transaction
    DROP CONSTRAINT IF EXISTS chk_financial_transaction_category;

-- Old shape was VARCHAR(40); the snapshot is as wide as head_code.
ALTER TABLE nss.financial_transaction
    ALTER COLUMN transaction_category TYPE VARCHAR(50);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_financial_transaction_head'
                      AND conrelid = 'nss.financial_transaction'::regclass) THEN
        ALTER TABLE nss.financial_transaction
            ADD CONSTRAINT fk_financial_transaction_head
            FOREIGN KEY (finance_head_pk)
            REFERENCES nss.finance_head (finance_head_pk) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_financial_transaction_head
    ON nss.financial_transaction (finance_head_pk);

-- Backfill from the template whose code equals the old category.
UPDATE nss.financial_transaction t
   SET finance_head_pk = h.finance_head_pk
  FROM nss.finance_head h
 WHERE t.finance_head_pk IS NULL
   AND h.organization_pk IS NULL
   AND h.head_code = t.transaction_category;

-- Only tighten once every row has a head (never fails a build on an unexpected category).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM nss.financial_transaction WHERE finance_head_pk IS NULL) THEN
        ALTER TABLE nss.financial_transaction ALTER COLUMN finance_head_pk SET NOT NULL;
    ELSE
        RAISE WARNING 'financial_transaction: % row(s) have no finance head (unknown old category); finance_head_pk stays nullable',
            (SELECT COUNT(*) FROM nss.financial_transaction WHERE finance_head_pk IS NULL);
    END IF;
END $$;
