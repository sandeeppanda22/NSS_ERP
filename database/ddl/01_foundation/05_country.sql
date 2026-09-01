-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 05_country.sql
-- Table: country
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #4 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §13
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE country
(
    country_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    country_code CHAR(2) NOT NULL,

    country_name VARCHAR(100) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT uq_country_code
        UNIQUE (country_code),

    CONSTRAINT uq_country_name
        UNIQUE (country_name),

    CONSTRAINT chk_country_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_country_active
    ON country (is_active);

CREATE INDEX idx_country_code
    ON country (country_code);
