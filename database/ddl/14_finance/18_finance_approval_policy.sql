-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 18_finance_approval_policy.sql
-- Table: nss.finance_approval_policy
-- Depth: 2 (depends on organization)
-- Version: 1.0
-- Authority: owner decision 2026-11-17 (per-head Treasurer limit with a Sakha default).
-- Owner: NSS_ERP_ADMIN
-- Note: One row per Sakha: the DEFAULT amount its Treasurer may approve alone, used by an expense head that has no limit
--       of its own. No row / NULL = no default: such a spend needs the President (or Secretary in cover) as well. Changing
--       it is a FINANCE_CONFIGURE decision (it widens the Treasurer's power); the Treasurer's own approval never sets it.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_approval_policy
(
    finance_approval_policy_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_pk UUID NOT NULL,

    default_treasurer_limit NUMERIC(14, 2) NULL,

    -- ── Lifecycle / Audit ───────────────────────────────

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_fap_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_fap_limit
        CHECK (default_treasurer_limit IS NULL OR default_treasurer_limit > 0),

    CONSTRAINT chk_fap_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fap_organization
    ON nss.finance_approval_policy (organization_pk) WHERE is_active = TRUE;
