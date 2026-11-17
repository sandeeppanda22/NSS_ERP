-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 14_finance_head_fixed_amount_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-15)
-- Authority: owner decision 2026-11-15 (simple contribution heads with a fixed amount; a Kendra head that every
--            Sakha receives automatically, money going to each Sakha's own account).
-- =====================================================
-- 05_finance_head.sql is existence-gated, so a database that already has the table never sees these columns.
-- On a fresh build every statement is a no-op (the columns and CHECKs are already in the CREATE TABLE).
-- Must run AFTER the table exists (build Phase 11i DDL).
-- =====================================================

ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS fixed_amount NUMERIC(14, 2) NULL;
ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS due_period VARCHAR(10) NULL;
ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS allow_part_payment BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS applies_to_all_sakhas BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_fixed_amount'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_fixed_amount
            CHECK (fixed_amount IS NULL OR fixed_amount > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_due_period'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_due_period
            CHECK (due_period IS NULL OR due_period IN ('YEARLY', 'MONTHLY', 'ONE_TIME'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_amount_period'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_amount_period
            CHECK (fixed_amount IS NULL OR due_period IS NOT NULL);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_all_sakhas'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_all_sakhas
            CHECK (applies_to_all_sakhas = FALSE
                   OR (direction = 'INCOME' AND organization_pk IS NOT NULL AND allow_upi = FALSE));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_finance_head_source
    ON nss.finance_head (template_head_pk) WHERE template_head_pk IS NOT NULL;
