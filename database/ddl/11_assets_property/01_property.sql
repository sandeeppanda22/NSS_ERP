-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 01_property.sql
-- Table: nss.property
-- Depth: 1 (depends on master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §7),
--            03_assets_property_lifecycle.md (§3),
--            04_assets_property_business_rules.md (AP-001/002/004/005/008/021/023/046/070),
--            GDR-010 (implementation decisions on the PENDING items)
-- Owner: NSS_ERP_ADMIN
--
-- Immovable property (land, buildings, premises). Separate entity from
-- nss.asset (AP-001).
--
-- Design decisions (GDR-010):
--   - property_type is a master_data FK (PROPERTY_TYPE category), NOT a
--     CHECK: the controlled values are PENDING (SOL-AP-005 §7.7, §15), so
--     the set stays admin-extendable (Master Data Driven). The Bye-Law
--     candidate values LAND/BUILDING/PREMISES/OTHER_IMMOVABLE are only
--     seeded data, never schema.
--   - status is a fixed CHECK: the four-state lifecycle is frozen
--     (SOL-AP-003 §3.1). Valid transitions are enforced by the API and, as a
--     backstop, by trigger nss.fn_ap_entity_guard()
--     (08_assets_property_guards.sql).
--   - location_description / holding_arrangement stay free text: AP-022 and
--     AP-013 (normalisation) are PENDING; the recorded holder is distinct
--     from the custodian (AP-009) and is NOT a FK to anything.
--   - property_id is the human-readable business identifier (AP-005),
--     minted by api/helpers.py::next_id(cur, 'PROPERTY') -> PROP1, PROP2 ...
--     (distinct prefix from asset ids, AP-008). Immutable (trigger).
--   - No financial columns of any kind (AP-060/061/063).
--
-- belongs_to_organization_pk (GDR-010 item 4, 2026-11-02): added to this file
--   for fresh builds; existing databases get it from
--   10_assets_property_belongs_to_patch.sql (this file is existence-gated).
--
-- acquisition_method_master_data_pk (GDR-010 §2E (open question 4), 2026-11-03): added here for
--   fresh builds; existing databases get it from
--   11_assets_property_acquisition_method_patch.sql.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE columns; their FK
--       constraints are deferred to Pass 2 per the project-wide convention.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.property
(
    -- ── Identity ────────────────────────────────────────

    property_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    property_id VARCHAR(30) NOT NULL,

    -- ── Core ────────────────────────────────────────────

    property_name VARCHAR(200) NOT NULL,

    property_type_master_data_pk UUID NOT NULL,

    status VARCHAR(20) NOT NULL
        DEFAULT 'REGISTERED',

    location_description TEXT NULL,

    holding_arrangement TEXT NULL,

    notes TEXT NULL,

    acquired_at DATE NULL,

    -- Optional attribution to an organization DIFFERENT from the physical
    -- custodian (GDR-010 item 4); informational only, no authorization effect.
    belongs_to_organization_pk UUID NULL,

    -- How the property was acquired (AP-023 "how"); master_data
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

    CONSTRAINT uq_property_id
        UNIQUE (property_id),

    CONSTRAINT fk_property_type
        FOREIGN KEY (property_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_property_belongs_to_org
        FOREIGN KEY (belongs_to_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_property_acquisition_method
        FOREIGN KEY (acquisition_method_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT chk_property_status
        CHECK (status IN ('REGISTERED', 'ACTIVE', 'UNDER_MAINTENANCE', 'DISPOSED')),

    CONSTRAINT chk_property_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_property_status
    ON nss.property (status);

CREATE INDEX IF NOT EXISTS idx_property_type
    ON nss.property (property_type_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_property_active
    ON nss.property (is_active);

CREATE INDEX IF NOT EXISTS idx_property_belongs_to_org
    ON nss.property (belongs_to_organization_pk) WHERE belongs_to_organization_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_property_acquisition_method
    ON nss.property (acquisition_method_master_data_pk) WHERE acquisition_method_master_data_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_property_name_trgm
    ON nss.property USING gin (property_name gin_trgm_ops);
