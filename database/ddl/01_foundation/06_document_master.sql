-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 06_document_master.sql
-- Table: document_master
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #5 of 86
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-FND-004 §41, DOC-ARCH-001
-- Owner: NSS_ADMIN
-- Note: Logical design from Person module (§54);
--       physical DDL owned by Foundation.
--       person_pk and uploaded_by_sangha_sevi_pk are
--       NULLABLE and enforced via deferred Pass 2
--       constraints after those tables exist.
-- =====================================================

CREATE TABLE document_master
(
    document_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    document_type_code VARCHAR(50) NOT NULL,

    document_number VARCHAR(100) NULL,

    document_name VARCHAR(255) NOT NULL,

    storage_path TEXT NOT NULL,

    file_size_bytes BIGINT NULL,

    mime_type VARCHAR(100) NULL,

    version INTEGER NOT NULL
        DEFAULT 1,

    checksum VARCHAR(128) NULL,

    description TEXT NULL,

    uploaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT chk_document_version_positive
        CHECK (version >= 1),

    CONSTRAINT chk_document_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_document_master_type_code
    ON document_master (document_type_code);

CREATE INDEX idx_document_master_active
    ON document_master (is_active);

CREATE INDEX idx_document_master_number
    ON document_master (document_number)
    WHERE document_number IS NOT NULL;
