-- =====================================================
-- NSS ERP
-- Module: Live refresh (cross-cutting; owner decision 2026-11-03)
-- File: 01_live_change_marker.sql
-- Table: nss.live_change_marker (+ sequence nss.live_change_seq)
-- Version: 1.0 (2026-11-03)
--
-- One tiny row per watched table: "the last COMMITTED write to this table got
-- change_seq N". GET /api/v1/live/changes reads these rows; the client
-- compares each table's change_seq with the one it saw last. The rows are
-- bumped by statement-level triggers (02_live_change_triggers.sql), so a bump
-- becomes visible exactly when the writing transaction commits and vanishes
-- with a rollback - there is no clock and no look-back window.
--
-- System table, not business data: table_name is its natural primary key (the
-- project's *_pk convention is for business tables), there are no actor /
-- soft-delete columns (nothing here is ever "deleted" by users; the trigger
-- file seeds the rows), and it is EXCLUDED from fn_audit_trigger()
-- (01_foundation/15_audit_trigger.sql) - every write anywhere would otherwise
-- cause a second audit row here. Recorded in CROSS_MODULE_PRINCIPLES.md §7.1.
--
-- Existence-gated (run_ddl / Invoke-Ddl). The idempotent trigger list lives
-- in 02_live_change_triggers.sql and runs on every build.
-- =====================================================

-- ONE global sequence: change_seq is unique and increasing across all tables.
CREATE SEQUENCE IF NOT EXISTS nss.live_change_seq;

CREATE TABLE IF NOT EXISTS nss.live_change_marker (
    table_name  TEXT        PRIMARY KEY,
    change_seq  BIGINT      NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

COMMENT ON TABLE nss.live_change_marker IS
    'Live-refresh change marker: one row per watched table, bumped by statement-level triggers (nss.fn_live_change_marker). Read by GET /api/v1/live/changes. Not audited.';
