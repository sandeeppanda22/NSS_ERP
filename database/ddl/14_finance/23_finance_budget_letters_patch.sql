-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 23_finance_budget_letters_patch.sql
-- Table: nss.finance_budget (adds referral_correspondence_pk, views_correspondence_pk)
-- Version: 1.0
-- Authority: owner request 2026-11-22 (referring the Kendra budget to the Advisory Board, and the Advisory Board's reply, create
--            Correspondence entries automatically); business rule FIN-BR-041.
-- Note: Idempotent (run_sql, EVERY build, after 21_/22_ and after the Correspondence DDL). A fresh build already has the columns in
--       21_finance_budget.sql; this patch adds them to a database whose finance_budget table was created before they existed
--       (run_ddl skips an existing table). Existing rows keep NULL: a budget referred before this change has no letters.
-- =====================================================

ALTER TABLE nss.finance_budget ADD COLUMN IF NOT EXISTS referral_correspondence_pk UUID NULL;
ALTER TABLE nss.finance_budget ADD COLUMN IF NOT EXISTS views_correspondence_pk UUID NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_finance_budget_referral_letter' AND conrelid = 'nss.finance_budget'::regclass) THEN
        ALTER TABLE nss.finance_budget ADD CONSTRAINT fk_finance_budget_referral_letter
            FOREIGN KEY (referral_correspondence_pk) REFERENCES nss.correspondence (correspondence_pk) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_finance_budget_views_letter' AND conrelid = 'nss.finance_budget'::regclass) THEN
        ALTER TABLE nss.finance_budget ADD CONSTRAINT fk_finance_budget_views_letter
            FOREIGN KEY (views_correspondence_pk) REFERENCES nss.correspondence (correspondence_pk) ON DELETE RESTRICT;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_finance_budget_referral_letter ON nss.finance_budget (referral_correspondence_pk) WHERE referral_correspondence_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_finance_budget_views_letter ON nss.finance_budget (views_correspondence_pk) WHERE views_correspondence_pk IS NOT NULL;
