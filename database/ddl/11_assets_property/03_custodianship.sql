-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 03_custodianship.sql
-- Table: nss.custodianship
-- Depth: 2 (depends on property, asset, organization, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §9),
--            03_assets_property_lifecycle.md (§5, AP-LIF-001..005),
--            04_assets_property_business_rules.md (AP-014..020, AP-041/042,
--            AP-057..059, AP-072), GDR-010
-- Owner: NSS_ERP_ADMIN
--
-- Historical record of which organization has operational custody of a
-- property or asset. The custodian is ALWAYS an organization (AP-015), never
-- a person, and is distinct from the recorded/legal holder (AP-009).
--
-- Design decisions:
--   - Exactly one of property_pk / asset_pk (AP-019) - XOR CHECK.
--   - One ACTIVE custodianship per property and per asset (AP-017 /
--     AP-LIF-005) - two partial UNIQUE indexes (the mechanism SOL-AP-005
--     §9.7 left open). ASSIGNED rows are transient (the API writes ASSIGNED
--     then ACTIVE in one transaction, AP-042) and are not counted.
--   - History (AP-018/072): a transfer UPDATEs the current row to ENDED and
--     INSERTs a new one; ENDED rows are immutable (trigger,
--     08_assets_property_guards.sql). No delete endpoint exists.
--   - end_reason is a master_data FK (CUSTODIANSHIP_END_REASON, values
--     PENDING per SOL-AP-005 §9.5 -> admin-extendable) so dissolution /
--     vesting is distinguishable from a routine TRANSFER (AP-058/059).
--     Required exactly when status = ENDED.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.custodianship
(
    -- ── Identity ────────────────────────────────────────

    custodianship_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Target (exactly one) ────────────────────────────

    property_pk UUID NULL,

    asset_pk UUID NULL,

    -- ── Custody ─────────────────────────────────────────

    custodian_organization_pk UUID NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'ASSIGNED',

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    end_reason_master_data_pk UUID NULL,

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

    CONSTRAINT fk_custodianship_property
        FOREIGN KEY (property_pk)
        REFERENCES nss.property (property_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_custodianship_asset
        FOREIGN KEY (asset_pk)
        REFERENCES nss.asset (asset_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_custodianship_organization
        FOREIGN KEY (custodian_organization_pk)
        REFERENCES nss.organization (organization_pk)
        ON DELETE RESTRICT,

    CONSTRAINT fk_custodianship_end_reason
        FOREIGN KEY (end_reason_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    -- AP-019: a custodianship belongs to a property OR an asset.
    CONSTRAINT chk_custodianship_target_xor
        CHECK (
            (property_pk IS NOT NULL AND asset_pk IS NULL)
            OR
            (property_pk IS NULL AND asset_pk IS NOT NULL)
        ),

    CONSTRAINT chk_custodianship_status
        CHECK (status IN ('ASSIGNED', 'ACTIVE', 'ENDED')),

    CONSTRAINT chk_custodianship_dates
        CHECK (effective_to IS NULL OR effective_to >= effective_from),

    -- ENDED <=> effective_to and end_reason both present (AP-058).
    CONSTRAINT chk_custodianship_ended_consistency
        CHECK (
            (status = 'ENDED' AND effective_to IS NOT NULL AND end_reason_master_data_pk IS NOT NULL)
            OR
            (status <> 'ENDED' AND effective_to IS NULL AND end_reason_master_data_pk IS NULL)
        ),

    CONSTRAINT chk_custodianship_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

-- AP-017 / AP-LIF-005: one ACTIVE custodian per property / per asset.
CREATE UNIQUE INDEX IF NOT EXISTS uq_custodianship_active_property
    ON nss.custodianship (property_pk)
    WHERE status = 'ACTIVE' AND is_active = TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_custodianship_active_asset
    ON nss.custodianship (asset_pk)
    WHERE status = 'ACTIVE' AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_custodianship_property_status
    ON nss.custodianship (property_pk, status);

CREATE INDEX IF NOT EXISTS idx_custodianship_asset_status
    ON nss.custodianship (asset_pk, status);

CREATE INDEX IF NOT EXISTS idx_custodianship_organization
    ON nss.custodianship (custodian_organization_pk);
