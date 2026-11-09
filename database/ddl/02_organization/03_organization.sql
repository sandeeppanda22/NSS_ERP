-- =====================================================
-- NSS ERP
-- Module: Organization
-- File: 03_organization.sql
-- Table: organization
-- Depth: 1 (depends on master_data, country,
--           state, district, city_village, postal_code)
-- Sequence: #33 of 87
-- Version: 2.1
-- Authority: SOL-ARCH-010, SOL-ORG-005 §19–§52, ORG-BR-098/099/100
-- Owner: NSS_ERP_ADMIN
--
-- v2.1 (2026-09-26):
--   has_own_premises added (ORG-BR-098). Records whether a
--   SAKHA_SANGHA has secured its own permanent premises WITHOUT
--   storing a distinct organization_type. "Sakha Asana" is the
--   day-to-day label for has_own_premises = FALSE; the standard
--   Create Organization flow never writes organization_type =
--   SAKHA_ASANA. Meaningless (always FALSE, ignored) for every
--   other organization type.
--
-- v2.0 Migration (2026-09-12):
--   organization_type_pk    → organization_type_master_data_pk (FK → master_data)
--   organization_status_pk  → status_master_data_pk (FK → master_data)
--   Standalone organization_type_master and organization_status_master
--   tables are retired — type/status values now live in Foundation
--   master_data under categories ORGANIZATION_TYPE / STATUS.
--
-- Note: Self-referencing FK (parent_organization_pk)
--       is included in CREATE TABLE since the table
--       already exists at that point.
--
-- Note: hierarchical_level is NOT a stored column.
--       Organizational level = organization type.
--       Hierarchy depth = derived from parent chain.
--       See SOL-ORG-005 §33 (decided 2026-09-01).
--
-- Note: Address is inline per frozen design (no
--       separate organization_address table).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.organization
(
    organization_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- Business identifier (system-generated for multi-instance
    -- org types; NULL for unique organizations identified by
    -- organization_code alone)
    organization_id VARCHAR(20) NULL,

    organization_name VARCHAR(200) NOT NULL,

    -- Classification (FK → master_data, category ORGANIZATION_TYPE)
    organization_type_master_data_pk UUID NOT NULL,

    -- Current lifecycle status (FK → master_data, category STATUS)
    status_master_data_pk UUID NOT NULL,

    -- Hierarchy: immediate parent (NULL = apex)
    parent_organization_pk UUID NULL,

    -- Organization short code (3-5 chars, unique)
    organization_code VARCHAR(10) NULL,

    -- Admin-assigned short code (3-5 uppercase alphanumeric)
    -- Used for local ERP references (e.g. "EKM" for Ekamra)
    -- NULL by default — assigned via admin panel
    short_code VARCHAR(5) NULL,

    -- Inline address (current address, v1 design)
    address_line_1 VARCHAR(200) NULL,

    address_line_2 VARCHAR(200) NULL,

    -- Sakha premises attribute (ORG-BR-098). Only meaningful for
    -- SAKHA_SANGHA rows; the "Sakha Asana" day-to-day label refers
    -- to has_own_premises = FALSE, never a distinct type.
    has_own_premises BOOLEAN NOT NULL
        DEFAULT FALSE,

    -- Contact information (operational requirement)
    phone_number VARCHAR(20) NULL,

    country_phone_code VARCHAR(10) NULL,

    mobile_number VARCHAR(20) NULL,

    email VARCHAR(254) NOT NULL
        DEFAULT 'info@nsspuri.org',

    org_email VARCHAR(254) NULL,

    -- Online presence
    website_url VARCHAR(500) NOT NULL
        DEFAULT 'https://www.nsspuri.org',

    org_website_url VARCHAR(500) NULL,

    youtube_channel_url VARCHAR(500) NOT NULL
        DEFAULT 'https://www.youtube.com/@NilachalaSaraswataSangha',

    org_youtube_channel_url VARCHAR(500) NULL,

    district_pk UUID NULL,

    state_pk UUID NULL,

    country_pk UUID NULL,

    city_village_pk UUID NULL,

    postal_code_pk UUID NULL,

    -- Physical coordinates of this organization
    latitude NUMERIC(10,7) NULL,

    longitude NUMERIC(10,7) NULL,

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

    -- short_code format: 3-5 uppercase alphanumeric only
    CONSTRAINT chk_organization_short_code
        CHECK (short_code IS NULL OR short_code ~ '^[A-Z0-9]{3,5}$'),

    -- MBR-CONTACT-02: email format (both the mandatory default contact
    -- email and the optional org-specific email). Mirrors api.helpers
    -- EMAIL_PATTERN and NSS.EMAIL_PATTERN (nss-config.js).
    CONSTRAINT chk_organization_email_format
        CHECK (email ~ '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'),

    CONSTRAINT chk_organization_org_email_format
        CHECK (org_email IS NULL OR org_email ~ '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'),

    -- MBR-CONTACT-01: organization dial code format (e.g. +91). The
    -- country-wise mobile DIGIT-LENGTH rule is enforced in the app layer
    -- (api.helpers.validate_mobile / NSS.validateMobile) since the DB does
    -- not pair digit length to a dial code; here we only guard the shape.
    CONSTRAINT chk_organization_country_phone_code_format
        CHECK (country_phone_code IS NULL OR country_phone_code ~ '^\+[0-9]{1,4}$'),

    CONSTRAINT chk_organization_mobile_number_format
        CHECK (mobile_number IS NULL OR mobile_number ~ '^[0-9]{7,15}$'),

    -- Foreign keys: classification + lifecycle (now via master_data)
    CONSTRAINT fk_organization_type
        FOREIGN KEY (organization_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_organization_status
        FOREIGN KEY (status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    -- Self-referencing FK: hierarchy
    CONSTRAINT fk_organization_parent
        FOREIGN KEY (parent_organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- Location FKs (Foundation tables)
    CONSTRAINT fk_organization_district
        FOREIGN KEY (district_pk)
        REFERENCES nss.district (district_pk),

    CONSTRAINT fk_organization_state
        FOREIGN KEY (state_pk)
        REFERENCES nss.state (state_pk),

    CONSTRAINT fk_organization_country
        FOREIGN KEY (country_pk)
        REFERENCES nss.country (country_pk),

    CONSTRAINT fk_organization_city_village
        FOREIGN KEY (city_village_pk)
        REFERENCES nss.city_village (city_village_pk),

    CONSTRAINT fk_organization_postal_code
        FOREIGN KEY (postal_code_pk)
        REFERENCES nss.postal_code (postal_code_pk),

    -- Coordinate range validation
    CONSTRAINT chk_organization_latitude
        CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),

    CONSTRAINT chk_organization_longitude
        CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),

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
CREATE INDEX IF NOT EXISTS idx_organization_type
    ON nss.organization (organization_type_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_organization_status
    ON nss.organization (status_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_organization_parent
    ON nss.organization (parent_organization_pk);

CREATE INDEX IF NOT EXISTS idx_organization_country
    ON nss.organization (country_pk);

CREATE INDEX IF NOT EXISTS idx_organization_state
    ON nss.organization (state_pk);

CREATE INDEX IF NOT EXISTS idx_organization_district
    ON nss.organization (district_pk);

CREATE INDEX IF NOT EXISTS idx_organization_city_village
    ON nss.organization (city_village_pk);

CREATE INDEX IF NOT EXISTS idx_organization_postal_code
    ON nss.organization (postal_code_pk);

CREATE INDEX IF NOT EXISTS idx_organization_active
    ON nss.organization (is_active);

-- Unique partial index: only non-NULL short_codes must be unique
CREATE UNIQUE INDEX IF NOT EXISTS uq_organization_short_code
    ON nss.organization (short_code)
    WHERE short_code IS NOT NULL;

-- Performance: recursive CTE joins on parent with is_active filter
CREATE INDEX IF NOT EXISTS idx_organization_parent_active
    ON nss.organization (parent_organization_pk)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_organization_name
    ON nss.organization USING gin (organization_name gin_trgm_ops);
