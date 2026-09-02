-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 03_role_permission.sql
-- Table: role_permission
-- Depth: 1 (depends on role_master, permission_master)
-- Sequence: #20 of 89
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-ARCH-011 §4,
--            SOL-ADMIN-004 §10, SOL-BOOT-001 §6
-- Owner: NSS_ADMIN
-- =====================================================

CREATE TABLE role_permission
(
    role_permission_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    role_master_pk UUID NOT NULL,

    permission_master_pk UUID NOT NULL,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- Foreign keys
    CONSTRAINT fk_role_permission_role
        FOREIGN KEY (role_master_pk)
        REFERENCES role_master (role_master_pk),

    CONSTRAINT fk_role_permission_permission
        FOREIGN KEY (permission_master_pk)
        REFERENCES permission_master (permission_master_pk),

    -- Unique constraint: no duplicate mapping
    CONSTRAINT uq_role_permission_mapping
        UNIQUE (role_master_pk, permission_master_pk),

    -- CHECK constraints
    CONSTRAINT chk_role_permission_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- Indexes
CREATE INDEX idx_role_permission_role
    ON role_permission (role_master_pk);

CREATE INDEX idx_role_permission_permission
    ON role_permission (permission_master_pk);

CREATE INDEX idx_role_permission_active
    ON role_permission (is_active);
