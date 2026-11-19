-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 20_finance_head_due_date_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-19)
-- Authority: owner decision 2026-11-19 (a due date for every Pranami, set when its payment portal is opened).
-- =====================================================
-- 05_finance_head.sql is existence-gated, so a database that already has the table never sees the column. On a fresh build this is a
-- no-op (the column is already in the CREATE TABLE). Must run AFTER the table exists (build Phase 11i DDL).
-- =====================================================

ALTER TABLE nss.finance_head ADD COLUMN IF NOT EXISTS due_date DATE NULL;
