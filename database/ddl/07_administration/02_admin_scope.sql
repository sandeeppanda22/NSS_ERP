-- =====================================================
-- NSS ERP
-- Module: Administration
-- File: 02_admin_scope.sql
-- Table: nss.admin_scope
-- Depth: 4 (depends on user_role, organization)
-- Version: 1.1 — chk_admin_scope_org_consistency: added KENDRA and
--          KENDRA_MAHILA_SANGHA to the NULL-organization_pk exemption
--          (§63 composite auto-grant rule, owner-confirmed 2026-10-09),
--          mirroring the already-approved ADVISORY_BOARD precedent.
--          Fixes a dormant inconsistency with this file's own header
--          comment below ("NULL for NSS_WIDE scope (ADMIN + KENDRA
--          roles)"): NSS_ERP_KENDRA_ADMIN and
--          NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN attach to bodies seeded
--          with organization_pk = NULL (Kendra GB and the central
--          Mahila Parichalana Mandali; see 03_body_master.sql), so
--          their admin_scope rows must likewise carry NULL
--          organization_pk.
-- Version: 1.0
-- Authority: SOL-ADMIN-004 §12, SOL-AUTH-004 §13,
--            Tier 5 decisions (2026-09-15)
-- Owner: Administration
--
-- Design decisions:
--   - organization_pk FK to nss.organization; NULL for
--     NSS_WIDE scope (ADMIN + KENDRA roles)
--   - scope_level ENUM matches role_master.scope_level
--     values; must be consistent with org type
--   - Scope is per user_role assignment, not per user
--     globally — a user can have different scopes for
--     different roles
--   - No separate scope_history table (frozen decision)
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.admin_scope
(
    -- ── Identity ────────────────────────────────────────

    admin_scope_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    user_role_pk UUID NOT NULL,

    -- ── Scope Definition ────────────────────────────────

    scope_level VARCHAR(30) NOT NULL,

    organization_pk UUID NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Foreign Keys ────────────────────────────────────

    CONSTRAINT fk_admin_scope_user_role
        FOREIGN KEY (user_role_pk)
        REFERENCES nss.user_role (user_role_pk),

    CONSTRAINT fk_admin_scope_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- ── Unique Constraints ──────────────────────────────
    -- One scope record per user_role assignment
    CONSTRAINT uq_admin_scope_user_role
        UNIQUE (user_role_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_admin_scope_level
        CHECK (scope_level IN ('NSS-WIDE', 'KENDRA', 'ANCHALIKA', 'ZILLA', 'SAKHA', 'PATHA_CHAKRA', 'KENDRA_MAHILA_SANGHA', 'ADVISORY_BOARD')),

    -- NSS-WIDE, KENDRA, KENDRA_MAHILA_SANGHA, and ADVISORY_BOARD scopes must
    -- have NULL organization_pk (all four correspond to bodies with
    -- organization_pk IS NULL in body_master — see 03_body_master.sql: Kendra
    -- Governing Body, the central Mahila Parichalana Mandali, and the
    -- Advisory Board); all other scopes must have a non-NULL organization_pk
    CONSTRAINT chk_admin_scope_org_consistency
        CHECK
        (
            (scope_level IN ('NSS-WIDE', 'KENDRA', 'KENDRA_MAHILA_SANGHA', 'ADVISORY_BOARD') AND organization_pk IS NULL)
            OR
            (scope_level NOT IN ('NSS-WIDE', 'KENDRA', 'KENDRA_MAHILA_SANGHA', 'ADVISORY_BOARD') AND organization_pk IS NOT NULL)
        ),

    CONSTRAINT chk_admin_scope_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_admin_scope_user_role
    ON nss.admin_scope (user_role_pk);

CREATE INDEX IF NOT EXISTS idx_admin_scope_organization
    ON nss.admin_scope (organization_pk)
    WHERE organization_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_admin_scope_level
    ON nss.admin_scope (scope_level);

CREATE INDEX IF NOT EXISTS idx_admin_scope_active
    ON nss.admin_scope (is_active);
