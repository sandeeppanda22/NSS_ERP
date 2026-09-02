-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 01_role_master.sql
-- Table: role_master
-- Depth: 0 (Root — no FK dependencies)
-- Sequence: #13 of 89
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-ARCH-011 §4,
--            SOL-ADMIN-004 §8, SOL-BOOT-001 §4
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE role_master
(
    role_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    role_code VARCHAR(50) NOT NULL,

    role_name VARCHAR(100) NOT NULL,

    role_class VARCHAR(30) NOT NULL,

    scope_level VARCHAR(30) NULL,

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
    CONSTRAINT uq_role_master_code
        UNIQUE (role_code),

    CONSTRAINT uq_role_master_name
        UNIQUE (role_name),

    -- CHECK constraints
    CONSTRAINT chk_role_master_class
        CHECK (role_class IN ('SYSTEM', 'ORGANIZATIONAL')),

    CONSTRAINT chk_role_master_scope_level
        CHECK
        (
            scope_level IS NULL
            OR
            scope_level IN ('KENDRA', 'ANCHALIKA', 'ZILLA', 'SAKHA', 'PATHA_CHAKRA')
        ),

    CONSTRAINT chk_role_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- Indexes
CREATE INDEX idx_role_master_active
    ON role_master (is_active);

CREATE INDEX idx_role_master_code
    ON role_master (role_code);

CREATE INDEX idx_role_master_class
    ON role_master (role_class);
