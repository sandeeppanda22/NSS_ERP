-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 05_maintenance_record.sql
-- Table: nss.maintenance_record
-- Depth: 2 (depends on property, asset, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §11),
--            04_assets_property_business_rules.md (AP-027..033), GDR-010
-- Owner: NSS_ERP_ADMIN
--
-- Historical record of maintenance performed on a property OR an asset
-- (XOR CHECK, same pattern as custodianship). Records what WAS done, not a
-- schedule (AP-029/032); NO cost / payment columns (AP-031, FIN-ARCH-001).
-- maintenance_type is a master_data FK (MAINTENANCE_TYPE, seeded with the
-- seven source-established AP-030 values, admin-extendable).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.maintenance_record
(
    -- ── Identity ────────────────────────────────────────

    maintenance_record_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    property_pk UUID NULL,

    asset_pk UUID NULL,

    maintenance_type_master_data_pk UUID NOT NULL,

    description TEXT NULL,

    performed_at DATE NULL,

    notes TEXT NULL,

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

    CONSTRAINT fk_maintenance_property
        FOREIGN KEY (property_pk)
        REFERENCES nss.property (property_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_maintenance_asset
        FOREIGN KEY (asset_pk)
        REFERENCES nss.asset (asset_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_maintenance_type
        FOREIGN KEY (maintenance_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_maintenance_target_xor
        CHECK (
            (property_pk IS NOT NULL AND asset_pk IS NULL)
            OR
            (property_pk IS NULL AND asset_pk IS NOT NULL)
        ),

    CONSTRAINT chk_maintenance_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_maintenance_property
    ON nss.maintenance_record (property_pk);

CREATE INDEX IF NOT EXISTS idx_maintenance_asset
    ON nss.maintenance_record (asset_pk);

CREATE INDEX IF NOT EXISTS idx_maintenance_type
    ON nss.maintenance_record (maintenance_type_master_data_pk);
