-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 01_organization_type_master.sql
-- Table: organization_type_master
-- Depth: 0 (no dependencies)
-- Sequence: #7 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-ORG-005 §7–§12
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE nss.organization_type_master
(
    organization_type_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_type_code VARCHAR(30) NOT NULL,

    organization_type_name VARCHAR(100) NOT NULL,

    description VARCHAR(500) NULL,

    sort_order INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT uq_organization_type_code
        UNIQUE (organization_type_code),

    CONSTRAINT uq_organization_type_name
        UNIQUE (organization_type_name),

    CONSTRAINT chk_organization_type_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE INDEX idx_organization_type_active
    ON nss.organization_type_master (is_active);
