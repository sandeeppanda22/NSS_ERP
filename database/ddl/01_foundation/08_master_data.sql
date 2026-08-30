-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 08_master_data.sql
-- Table: master_data
-- Depth: 1 (depends on master_category)
-- Sequence: #18 of 86
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §7
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE master_data
(
    master_data_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    master_category_pk UUID NOT NULL,

    value_code VARCHAR(50) NOT NULL,

    value_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_master_data_category
        FOREIGN KEY (master_category_pk)
        REFERENCES master_category (master_category_pk),

    CONSTRAINT uq_master_data_category_code
        UNIQUE (master_category_pk, value_code)
);

CREATE INDEX idx_master_data_category
    ON master_data (master_category_pk);

CREATE INDEX idx_master_data_active
    ON master_data (is_active);

CREATE INDEX idx_master_data_value_code
    ON master_data (value_code);

CREATE INDEX idx_master_data_value_name
    ON master_data USING gin (value_name gin_trgm_ops);
