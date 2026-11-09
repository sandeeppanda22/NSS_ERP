-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 02_asset.sql
-- Table: nss.asset
-- Depth: 1 (depends on master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §8),
--            03_assets_property_lifecycle.md (§4),
--            04_assets_property_business_rules.md (AP-001/003/006/007/008/021/023/047/070),
--            GDR-010
-- Owner: NSS_ERP_ADMIN
--
-- Movable asset (equipment, furniture, instruments, articles).
--
-- Design decisions (GDR-010): asset_type is a master_data FK
-- (ASSET_TYPE category; values PENDING, admin-extendable); status is a fixed
-- CHECK (SOL-AP-003 §4.1: REGISTERED / IN_CUSTODY / UNDER_MAINTENANCE /
-- RETIRED); condition is free text because no condition grading system is
-- frozen (SOL-AP-005 §8.6, SOL-AP-004 §21); asset_id is minted by
-- next_id(cur, 'ASSET') -> AST1, AST2 ... (distinct from property ids,
-- AP-008) and is immutable. No financial / valuation columns (AP-060/063).
-- The sacred-article boundary with Heritage (AP-066) is PENDING and adds no
-- column here.
--
-- belongs_to_organization_pk (GDR-010 item 4, 2026-11-02): added to this file
--   for fresh builds; existing databases get it from
--   10_assets_property_belongs_to_patch.sql (this file is existence-gated).
--
-- acquisition_method_master_data_pk (GDR-010 §2E (open question 4), 2026-11-03): added here for
--   fresh builds; existing databases get it from
--   11_assets_property_acquisition_method_patch.sql.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.asset
(
    -- ── Identity ────────────────────────────────────────

    asset_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    asset_id VARCHAR(30) NOT NULL,

    -- ── Core ────────────────────────────────────────────

    asset_name VARCHAR(200) NOT NULL,

    asset_type_master_data_pk UUID NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'REGISTERED',

    location_description TEXT NULL,

    condition TEXT NULL,

    notes TEXT NULL,

    acquired_at DATE NULL,

    -- Optional attribution to an organization DIFFERENT from the physical
    -- custodian (GDR-010 item 4); informational only, no authorization effect.
    belongs_to_organization_pk UUID NULL,

    -- How the asset was acquired (AP-023 "how"); master_data
    -- ACQUISITION_METHOD, optional, informational (owner decision 2026-11-03,
    -- GDR-010 §2E). No authorization effect.
    acquisition_method_master_data_pk UUID NULL,

    -- ── Lifecycle ───────────────────────────────────────

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Audit (AP-070) ──────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT uq_asset_id
        UNIQUE (asset_id),

    CONSTRAINT fk_asset_type
        FOREIGN KEY (asset_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_asset_belongs_to_org
        FOREIGN KEY (belongs_to_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_asset_acquisition_method
        FOREIGN KEY (acquisition_method_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_asset_status
        CHECK (status IN ('REGISTERED', 'IN_CUSTODY', 'UNDER_MAINTENANCE', 'RETIRED')),

    CONSTRAINT chk_asset_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_asset_status
    ON nss.asset (status);

CREATE INDEX IF NOT EXISTS idx_asset_type
    ON nss.asset (asset_type_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_asset_active
    ON nss.asset (is_active);

CREATE INDEX IF NOT EXISTS idx_asset_belongs_to_org
    ON nss.asset (belongs_to_organization_pk) WHERE belongs_to_organization_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_asset_acquisition_method
    ON nss.asset (acquisition_method_master_data_pk) WHERE acquisition_method_master_data_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_asset_name_trgm
    ON nss.asset USING gin (asset_name gin_trgm_ops);
