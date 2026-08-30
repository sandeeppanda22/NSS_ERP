-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 12_postal_code.sql
-- Table: postal_code
-- Depth: 1 (depends on country)
-- Version: 1.0
-- Authority: SOL-ARCH-010 Amendment (PIN Code Geographic
--            Model, 2026-08-28)
-- Owner: NSS_ADMIN
-- Note: PIN codes are country-scoped. One PIN code can
--       serve multiple city/villages (M:N via map table).
-- =====================================================

CREATE TABLE postal_code
(
    postal_code_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    country_pk UUID NOT NULL,

    postal_code VARCHAR(20) NOT NULL,

    post_office_name VARCHAR(150) NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_postal_code_country
        FOREIGN KEY (country_pk)
        REFERENCES country (country_pk),

    CONSTRAINT uq_postal_code_country
        UNIQUE (country_pk, postal_code)
);

CREATE INDEX idx_postal_code_country
    ON postal_code (country_pk);

CREATE INDEX idx_postal_code_code
    ON postal_code (postal_code);

CREATE INDEX idx_postal_code_active
    ON postal_code (is_active);

CREATE INDEX idx_postal_code_post_office
    ON postal_code USING gin (post_office_name gin_trgm_ops)
    WHERE post_office_name IS NOT NULL;
