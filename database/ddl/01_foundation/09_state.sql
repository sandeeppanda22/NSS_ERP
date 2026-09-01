-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 09_state.sql
-- Table: state
-- Depth: 1 (depends on country)
-- Sequence: #19 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §14
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE state
(
    state_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    country_pk UUID NOT NULL,

    state_code VARCHAR(20) NOT NULL,

    state_name VARCHAR(100) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_state_country
        FOREIGN KEY (country_pk)
        REFERENCES country (country_pk),

    CONSTRAINT uq_state_country_code
        UNIQUE (country_pk, state_code),

    CONSTRAINT uq_state_country_name
        UNIQUE (country_pk, state_name),

    CONSTRAINT chk_state_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_state_country
    ON state (country_pk);

CREATE INDEX idx_state_active
    ON state (is_active);

CREATE INDEX idx_state_name
    ON state USING gin (state_name gin_trgm_ops);
