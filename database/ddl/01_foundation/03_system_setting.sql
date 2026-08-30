-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 03_system_setting.sql
-- Table: system_setting
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #2 of 86
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §10
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE system_setting
(
    system_setting_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    setting_key VARCHAR(100) NOT NULL,

    setting_value TEXT NOT NULL,

    description TEXT NULL,

    data_type VARCHAR(20) NOT NULL
        DEFAULT 'STRING',

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT uq_system_setting_key
        UNIQUE (setting_key),

    CONSTRAINT chk_system_setting_data_type
        CHECK
        (
            data_type IN
            (
                'STRING',
                'INTEGER',
                'BOOLEAN',
                'DATE',
                'JSON'
            )
        )
);

CREATE INDEX idx_system_setting_active
    ON system_setting (is_active);

CREATE INDEX idx_system_setting_key
    ON system_setting (setting_key);
