-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 08_master_data.sql
-- Table: master_data
-- Depth: 1 (depends on master_category)
-- Sequence: #18 of 87
-- Version: 1.1 — idempotent CREATE TABLE/INDEX + ALTER-based column backfill
-- Authority: SOL-ARCH-010, SOL-FND-004 §7
-- Owner: NSS_ERP_ADMIN
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.master_data
(
    master_data_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    master_category_pk UUID NOT NULL,

    value_code VARCHAR(50) NOT NULL,

    value_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

    -- Module-scope filter for shared categories (e.g. STATUS).
    -- NULL = applies to all modules (default for single-module
    -- categories like GENDER, BLOOD_GROUP).
    -- Array of module codes: '{ORGANIZATION,MEMBERSHIP,PERSON}'.
    -- API filters: WHERE '<MODULE>' = ANY(applicable_modules).
    applicable_modules TEXT[] NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_master_data_category
        FOREIGN KEY (master_category_pk)
        REFERENCES nss.master_category (master_category_pk),

    CONSTRAINT uq_master_data_category_code
        UNIQUE (master_category_pk, value_code),

    CONSTRAINT chk_master_data_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_master_data_category
    ON nss.master_data (master_category_pk);

CREATE INDEX IF NOT EXISTS idx_master_data_active
    ON nss.master_data (is_active);

CREATE INDEX IF NOT EXISTS idx_master_data_value_code
    ON nss.master_data (value_code);

CREATE INDEX IF NOT EXISTS idx_master_data_value_name
    ON nss.master_data USING gin (value_name gin_trgm_ops);
