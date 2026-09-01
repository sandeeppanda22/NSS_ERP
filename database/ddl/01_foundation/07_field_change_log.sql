-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 07_field_change_log.sql
-- Table: field_change_log
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #6 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §41,
--            Data Change Architecture (2026-08-26)
-- Owner: NSS_ADMIN
-- Note: Shared field-level change tracking.
--       No FK dependencies — references are stored as
--       UUID values without constraints to avoid
--       circular dependencies. Application layer
--       enforces referential integrity.
-- =====================================================

CREATE TABLE field_change_log
(
    field_change_log_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    table_name VARCHAR(100) NOT NULL,

    record_pk UUID NOT NULL,

    field_name VARCHAR(100) NOT NULL,

    old_value TEXT NULL,

    new_value TEXT NULL,

    change_reason TEXT NULL,

    changed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    changed_by_sangha_sevi_pk UUID NULL
);

CREATE INDEX idx_field_change_log_table_record
    ON field_change_log (table_name, record_pk);

CREATE INDEX idx_field_change_log_changed_at
    ON field_change_log (changed_at);

CREATE INDEX idx_field_change_log_field
    ON field_change_log (table_name, field_name);
