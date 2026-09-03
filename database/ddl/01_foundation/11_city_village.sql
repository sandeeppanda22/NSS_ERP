-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 11_city_village.sql
-- Table: city_village
-- Depth: 3 (depends on district)
-- Sequence: #32 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §16
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE nss.city_village
(
    city_village_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    district_pk UUID NOT NULL,

    city_village_code VARCHAR(20) NOT NULL,

    city_village_name VARCHAR(150) NOT NULL,

    city_village_type VARCHAR(20) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_city_village_district
        FOREIGN KEY (district_pk)
        REFERENCES nss.district (district_pk),

    CONSTRAINT uq_city_village_district_code
        UNIQUE (district_pk, city_village_code),

    CONSTRAINT uq_city_village_district_name
        UNIQUE (district_pk, city_village_name),

    CONSTRAINT chk_city_village_type
        CHECK
        (
            city_village_type IN
            (
                'CITY',
                'TOWN',
                'VILLAGE'
            )
        ),

    CONSTRAINT chk_city_village_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_city_village_district
    ON nss.city_village (district_pk);

CREATE INDEX idx_city_village_active
    ON nss.city_village (is_active);

CREATE INDEX idx_city_village_name
    ON nss.city_village USING gin (city_village_name gin_trgm_ops);
