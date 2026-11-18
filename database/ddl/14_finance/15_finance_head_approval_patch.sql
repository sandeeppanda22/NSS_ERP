-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 15_finance_head_approval_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-17)
-- Authority: owner decision 2026-11-17 (Sakha approval chain: Treasurer, then President / Secretary; income on a
--            pre-defined head needs no approval; the Treasurer approves spending alone up to a per-head limit).
-- =====================================================
-- 05_finance_head.sql is existence-gated, so a database that already has the table never sees these columns. On a fresh
-- build every statement is a no-op. Runs AFTER 14_finance_head_fixed_amount_patch.sql.
-- =====================================================

ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS skips_approval BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS treasurer_limit NUMERIC(14, 2) NULL;
ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS requires_member BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_skips_approval'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_skips_approval
            CHECK (skips_approval = FALSE OR direction = 'INCOME');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_treasurer_limit'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_treasurer_limit
            CHECK (treasurer_limit IS NULL OR (direction = 'EXPENSE' AND treasurer_limit > 0));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_finance_head_requires_member'
                      AND conrelid = 'nss.finance_head'::regclass) THEN
        ALTER TABLE nss.finance_head ADD CONSTRAINT chk_finance_head_requires_member
            CHECK (requires_member = FALSE OR direction = 'EXPENSE');
    END IF;
END $$;
