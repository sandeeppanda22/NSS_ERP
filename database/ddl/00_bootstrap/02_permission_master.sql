-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 02_permission_master.sql
-- Table: permission_master
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #14 of 89
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-ARCH-011 §4,
--            SOL-ADMIN-004 §9, SOL-BOOT-001 §5
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE nss.permission_master
(
    permission_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    permission_code VARCHAR(80) NOT NULL,

    permission_name VARCHAR(150) NOT NULL,

    module_code VARCHAR(50) NOT NULL,

    description TEXT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- Unique constraints
    CONSTRAINT uq_permission_master_code
        UNIQUE (permission_code),

    -- CHECK constraints
    CONSTRAINT chk_permission_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- Indexes
CREATE INDEX idx_permission_master_active
    ON nss.permission_master (is_active);

CREATE INDEX idx_permission_master_code
    ON nss.permission_master (permission_code);

CREATE INDEX idx_permission_master_module
    ON nss.permission_master (module_code);
