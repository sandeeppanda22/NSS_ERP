-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 10_district.sql
-- Table: district
-- Depth: 2 (depends on state)
-- Sequence: #26 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §15
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE district
(
    district_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    state_pk UUID NOT NULL,

    district_code VARCHAR(20) NOT NULL,

    district_name VARCHAR(100) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_district_state
        FOREIGN KEY (state_pk)
        REFERENCES state (state_pk),

    CONSTRAINT uq_district_state_code
        UNIQUE (state_pk, district_code),

    CONSTRAINT uq_district_state_name
        UNIQUE (state_pk, district_name),

    CONSTRAINT chk_district_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_district_state
    ON district (state_pk);

CREATE INDEX idx_district_active
    ON district (is_active);

CREATE INDEX idx_district_name
    ON district USING gin (district_name gin_trgm_ops);
