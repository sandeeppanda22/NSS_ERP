-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 07_asset_document.sql
-- Table: nss.asset_document
-- Depth: 2 (depends on asset, document_master, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §13),
--            04_assets_property_business_rules.md (AP-067..069), DOC-ARCH-001,
--            GDR-010
-- Owner: NSS_ERP_ADMIN
--
-- Explicit junction between a asset and the Foundation-owned
-- nss.document_master (no polymorphic entity FK, no module-local document
-- table: AP-067/068/069).
--
-- Design decisions (GDR-010): relationship_type is a nullable master_data FK
-- (ASSET_PROPERTY_DOCUMENT_RELATIONSHIP category; values PENDING,
-- admin-extendable). Uniqueness is one ACTIVE link per (asset, document) - a
-- PARTIAL unique index so that detaching (soft delete) and re-attaching the
-- same document is possible (SOL-AP-005 §12.6 left the exact definition
-- open). ON DELETE CASCADE on the asset FK follows SOL-AP-005 §19 (junction);
-- nss_db_writer has no DELETE privilege so it is never exercised.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.asset_document
(
    -- ── Identity ────────────────────────────────────────

    asset_document_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    asset_pk UUID NOT NULL,

    document_master_pk UUID NOT NULL,

    relationship_type_master_data_pk UUID NULL,

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

    CONSTRAINT fk_asset_document_asset
        FOREIGN KEY (asset_pk)
        REFERENCES nss.asset (asset_pk)
        ON DELETE CASCADE,

    CONSTRAINT fk_asset_document_document
        FOREIGN KEY (document_master_pk)
        REFERENCES nss.document_master (document_master_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_asset_document_relationship
        FOREIGN KEY (relationship_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_asset_document_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_document_active
    ON nss.asset_document (asset_pk, document_master_pk)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_asset_document_asset
    ON nss.asset_document (asset_pk);

CREATE INDEX IF NOT EXISTS idx_asset_document_document
    ON nss.asset_document (document_master_pk);
