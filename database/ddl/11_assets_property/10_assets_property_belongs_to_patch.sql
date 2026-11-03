-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 10_assets_property_belongs_to_patch.sql (idempotent patch)
-- Not a table - run with run_sql / Invoke-Sql on every build, after the
-- 7 table DDL files, 08 and 09.
-- Version: 1.0 (2026-11-02)
-- Authority: owner decision 2026-11-02, GDR-010 item 4 ("belongs to"),
--            SOL-AP-005 amendment (05_assets_property_table_design.md).
--
-- property.belongs_to_organization_pk / asset.belongs_to_organization_pk -
-- an OPTIONAL attribution of a property/asset to an organization that is
-- DIFFERENT from its physical custodian (e.g. an asset that belongs to the
-- Mahila Sangha but is held under the supervision of the Kendra Sangha:
-- custodian = Kendra, belongs-to = Mahila Sangha). Informational only: it has
-- NO effect on authorization, admin scope, the custodian rule or lifecycle.
-- Any organization type is allowed; the API requires only that it be an
-- ACTIVE organization.
--
-- 01_property.sql / 02_asset.sql are existence-gated by the build scripts, so
-- the column added to their CREATE TABLE reaches only FRESH databases; this
-- file carries it to existing ones. On a fresh build every statement below is
-- a no-op. Constraint / index names are identical in both places.
-- =====================================================

ALTER TABLE nss.property ADD COLUMN IF NOT EXISTS belongs_to_organization_pk UUID NULL;
ALTER TABLE nss.asset    ADD COLUMN IF NOT EXISTS belongs_to_organization_pk UUID NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_property_belongs_to_org'
                   AND conrelid = 'nss.property'::regclass) THEN
        ALTER TABLE nss.property
            ADD CONSTRAINT fk_property_belongs_to_org
            FOREIGN KEY (belongs_to_organization_pk) REFERENCES nss.organization (organization_pk);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_asset_belongs_to_org'
                   AND conrelid = 'nss.asset'::regclass) THEN
        ALTER TABLE nss.asset
            ADD CONSTRAINT fk_asset_belongs_to_org
            FOREIGN KEY (belongs_to_organization_pk) REFERENCES nss.organization (organization_pk);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_property_belongs_to_org
    ON nss.property (belongs_to_organization_pk) WHERE belongs_to_organization_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_asset_belongs_to_org
    ON nss.asset (belongs_to_organization_pk) WHERE belongs_to_organization_pk IS NOT NULL;
