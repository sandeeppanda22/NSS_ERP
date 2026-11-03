-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 04_property_statutory_record.sql
-- Table: nss.property_statutory_record
-- Depth: 2 (depends on property, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §10),
--            04_assets_property_business_rules.md (AP-034..040), GDR-010
-- Owner: NSS_ERP_ADMIN
--
-- Statutory obligations / records of an immovable property: land revenue,
-- municipal tax, land records. Property ONLY (AP-040): property_pk is
-- NOT NULL and there is deliberately NO asset_pk column.
--
-- NO payment amount / date / transaction columns (AP-039, FIN-ARCH-001):
-- this table identifies the obligation, Finance records the payment.
-- obligation_type is a master_data FK (STATUTORY_OBLIGATION_TYPE, seeded with
-- the four source-established values LAND_REVENUE / MUNICIPAL_TAX /
-- LAND_RECORD / OTHER, admin-extendable).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.property_statutory_record
(
    -- ── Identity ────────────────────────────────────────

    property_statutory_record_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    property_pk UUID NOT NULL,

    obligation_type_master_data_pk UUID NOT NULL,

    description TEXT NULL,

    reference_number VARCHAR(100) NULL,

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

    CONSTRAINT fk_psr_property
        FOREIGN KEY (property_pk)
        REFERENCES nss.property (property_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_psr_obligation_type
        FOREIGN KEY (obligation_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_psr_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ───────────────────────────────────────��─────

CREATE INDEX IF NOT EXISTS idx_psr_property
    ON nss.property_statutory_record (property_pk);

CREATE INDEX IF NOT EXISTS idx_psr_obligation_type
    ON nss.property_statutory_record (obligation_type_master_data_pk);
