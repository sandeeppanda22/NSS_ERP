-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 13_city_village_postal_code_map.sql
-- Table: city_village_postal_code_map
-- Depth: 4 (depends on city_village + postal_code)
-- Version: 1.0
-- Authority: SOL-ARCH-010 Amendment (PIN Code Geographic
--            Model, 2026-08-28)
-- Owner: NSS_ADMIN
-- Note: M:N relationship between city_village and
--       postal_code. One PIN code can serve multiple
--       localities; one locality can have multiple PINs.
-- =====================================================

CREATE TABLE city_village_postal_code_map
(
    city_village_postal_code_map_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    city_village_pk UUID NOT NULL,

    postal_code_pk UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_cv_pc_map_city_village
        FOREIGN KEY (city_village_pk)
        REFERENCES city_village (city_village_pk),

    CONSTRAINT fk_cv_pc_map_postal_code
        FOREIGN KEY (postal_code_pk)
        REFERENCES postal_code (postal_code_pk),

    CONSTRAINT uq_cv_pc_map
        UNIQUE (city_village_pk, postal_code_pk)
);

CREATE INDEX idx_cv_pc_map_city_village
    ON city_village_postal_code_map (city_village_pk);

CREATE INDEX idx_cv_pc_map_postal_code
    ON city_village_postal_code_map (postal_code_pk);
