-- =====================================================
-- 08_family_head_history_audit_columns.sql
-- Audit columns missing from nss.family_head_history
-- =====================================================
-- The API closes a head record with `updated_at = CURRENT_TIMESTAMP`
-- (transfer-head, a head leaving the family), and every sibling Family table
-- (family_relationship, family_link, family_admin) carries updated_at /
-- updated_by_sangha_sevi_pk, but 03_family_head_history.sql only had the
-- created_* pair. 03 now declares them; it is existence-gated by the build
-- scripts and skipped on any database that already has the table, so this
-- idempotent patch carries the columns to existing databases (run_sql).
-- =====================================================
ALTER TABLE nss.family_head_history
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS updated_by_sangha_sevi_pk UUID NULL;
