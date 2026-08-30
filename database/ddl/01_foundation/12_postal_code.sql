-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 12_postal_code.sql
-- Table: postal_code
-- Depth: 2 (depends on country, state)
-- Version: 1.1
-- Authority: SOL-ARCH-010 Amendment (PIN Code Geographic
--            Model, 2026-08-28)
-- Owner: NSS_ADMIN
-- Note: PIN codes are country-scoped with an explicit
--       state association. One PIN code can serve
--       multiple city/villages (M:N via map table).
--       state_pk provides direct administrative
--       ownership — the postal-to-locality mapping
--       remains in city_village_postal_code_map.
--       Uniqueness is (country_pk, postal_code) because
--       a PIN is globally unique within a country's
--       postal system; state_pk is a reference FK,
--       not part of the unique key.
-- =====================================================

CREATE TABLE postal_code
(
    postal_code_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    country_pk UUID NOT NULL,

    state_pk UUID NOT NULL,

    postal_code VARCHAR(20) NOT NULL,

    post_office_name VARCHAR(150) NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_postal_code_country
        FOREIGN KEY (country_pk)
        REFERENCES country (country_pk),

    CONSTRAINT fk_postal_code_state
        FOREIGN KEY (state_pk)
        REFERENCES state (state_pk),

    CONSTRAINT uq_postal_code_country
        UNIQUE (country_pk, postal_code),

    CONSTRAINT chk_postal_code_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_postal_code_country
    ON postal_code (country_pk);

CREATE INDEX idx_postal_code_state
    ON postal_code (state_pk);

CREATE INDEX idx_postal_code_code
    ON postal_code (postal_code);

CREATE INDEX idx_postal_code_active
    ON postal_code (is_active);

CREATE INDEX idx_postal_code_post_office
    ON postal_code USING gin (post_office_name gin_trgm_ops)
    WHERE post_office_name IS NOT NULL;
