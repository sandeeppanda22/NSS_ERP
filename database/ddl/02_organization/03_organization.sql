-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 03_organization.sql
-- Table: organization
-- Depth: 4 (depends on organization_type_master,
--           organization_status_master, country,
--           state, district)
-- Sequence: #33 of 87
-- Version: 1.0
-- Authority: SOL-ARCH-010, SOL-ORG-005 §19–§52
-- Owner: NSS_ADMIN
--
-- Note: Self-referencing FK (parent_organization_pk)
--       is included in CREATE TABLE since the table
--       already exists at that point.
--
-- Note: hierarchical_level is NOT a stored column.
--       Organizational level = organization_type_pk.
--       Hierarchy depth = derived from parent chain.
--       See SOL-ORG-005 §33 (decided 2026-09-01).
--
-- Note: Address is inline per frozen design (no
--       separate organization_address table).
-- =====================================================

CREATE TABLE organization
(
    organization_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- Business identifier (system-generated for multi-instance
    -- org types; NULL for unique organizations identified by
    -- organization_code alone)
    organization_id VARCHAR(20) NULL,

    organization_name VARCHAR(200) NOT NULL,

    -- Classification
    organization_type_pk UUID NOT NULL,

    -- Current lifecycle status
    organization_status_pk UUID NOT NULL,

    -- Hierarchy: immediate parent (NULL = apex)
    parent_organization_pk UUID NULL,

    -- Organization short code (3-5 chars, unique)
    organization_code VARCHAR(10) NULL,

    -- Inline address (current address, v1 design)
    address_line_1 VARCHAR(200) NULL,

    address_line_2 VARCHAR(200) NULL,

    district_pk UUID NULL,

    state_pk UUID NULL,

    country_pk UUID NULL,

    postal_code VARCHAR(20) NULL,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- Unique constraints
    CONSTRAINT uq_organization_id
        UNIQUE (organization_id),

    CONSTRAINT uq_organization_code
        UNIQUE (organization_code),

    -- Foreign keys: classification + lifecycle
    CONSTRAINT fk_organization_type
        FOREIGN KEY (organization_type_pk)
        REFERENCES organization_type_master (organization_type_pk),

    CONSTRAINT fk_organization_status
        FOREIGN KEY (organization_status_pk)
        REFERENCES organization_status_master (organization_status_pk),

    -- Self-referencing FK: hierarchy
    CONSTRAINT fk_organization_parent
        FOREIGN KEY (parent_organization_pk)
        REFERENCES organization (organization_pk),

    -- Location FKs (Foundation tables)
    CONSTRAINT fk_organization_district
        FOREIGN KEY (district_pk)
        REFERENCES district (district_pk),

    CONSTRAINT fk_organization_state
        FOREIGN KEY (state_pk)
        REFERENCES state (state_pk),

    CONSTRAINT fk_organization_country
        FOREIGN KEY (country_pk)
        REFERENCES country (country_pk),

    -- Soft-delete consistency
    CONSTRAINT chk_organization_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- Indexes
CREATE INDEX idx_organization_type
    ON organization (organization_type_pk);

CREATE INDEX idx_organization_status
    ON organization (organization_status_pk);

CREATE INDEX idx_organization_parent
    ON organization (parent_organization_pk);

CREATE INDEX idx_organization_country
    ON organization (country_pk);

CREATE INDEX idx_organization_state
    ON organization (state_pk);

CREATE INDEX idx_organization_district
    ON organization (district_pk);

CREATE INDEX idx_organization_active
    ON organization (is_active);

CREATE INDEX idx_organization_name
    ON organization USING gin (organization_name gin_trgm_ops);
