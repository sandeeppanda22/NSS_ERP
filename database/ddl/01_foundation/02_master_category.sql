-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 02_master_category.sql
-- Table: master_category
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #1 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §6
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE master_category
(
    master_category_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    category_code VARCHAR(50) NOT NULL,

    category_name VARCHAR(100) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT uq_master_category_code
        UNIQUE (category_code),

    CONSTRAINT uq_master_category_name
        UNIQUE (category_name),

    CONSTRAINT chk_master_category_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_master_category_active
    ON master_category (is_active);

CREATE INDEX idx_master_category_code
    ON master_category (category_code);
