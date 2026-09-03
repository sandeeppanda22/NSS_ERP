-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 04_id_sequence_master.sql
-- Table: id_sequence_master
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #3 of 87
-- Version: 2.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §11
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE nss.id_sequence_master
(
    id_sequence_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sequence_code VARCHAR(50) NOT NULL,

    sequence_name VARCHAR(100) NOT NULL,

    prefix VARCHAR(20) NOT NULL,

    current_value BIGINT NOT NULL
        DEFAULT 0,

    padding_length INTEGER NOT NULL
        DEFAULT 8,

    description TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT uq_id_sequence_code
        UNIQUE (sequence_code),

    CONSTRAINT uq_id_sequence_name
        UNIQUE (sequence_name),

    CONSTRAINT chk_id_sequence_padding
        CHECK (padding_length BETWEEN 4 AND 12),

    CONSTRAINT chk_id_sequence_current_value
        CHECK (current_value >= 0),

    CONSTRAINT chk_id_sequence_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_id_sequence_active
    ON nss.id_sequence_master (is_active);

CREATE INDEX idx_id_sequence_code
    ON nss.id_sequence_master (sequence_code);
