-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 11_assets_property_acquisition_method_patch.sql (idempotent patch)
-- Not a table - run with run_sql / Invoke-Sql on every build, after the
-- 7 table DDL files, 08, 09 and 10.
-- Version: 1.0 (2026-11-03)
-- Authority: owner decision 2026-11-03, GDR-010 §2E, open question 4 (acquisition "how",
--            AP-023), SOL-AP-005 amendment (05_assets_property_table_design.md).
--
-- property.acquisition_method_master_data_pk / asset.acquisition_method_master_data_pk
-- - OPTIONAL master_data (category ACQUISITION_METHOD) FK recording HOW the
-- property/asset was acquired (AP-023: "when and how"; `acquired_at` already
-- records when). Informational only: no effect on authorization, admin scope,
-- the custodian rule or the lifecycle; approval stays with Governance
-- (AP-025) and payment with Finance (AP-026).
--
-- 01_property.sql / 02_asset.sql are existence-gated by the build scripts, so
-- the column added to their CREATE TABLE reaches only FRESH databases; this
-- file carries it to existing ones. On a fresh build every statement below is
-- a no-op. Constraint / index names are identical in both places. The
-- ACQUISITION_METHOD category and its values are seeded by
-- seed/11_assets_property/01_assets_property_reference_data_patch.sql.
-- =====================================================

ALTER TABLE nss.property ADD COLUMN IF NOT EXISTS acquisition_method_master_data_pk UUID NULL;
ALTER TABLE nss.asset    ADD COLUMN IF NOT EXISTS acquisition_method_master_data_pk UUID NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_property_acquisition_method'
                   AND conrelid = 'nss.property'::regclass) THEN
        ALTER TABLE nss.property
            ADD CONSTRAINT fk_property_acquisition_method
            FOREIGN KEY (acquisition_method_master_data_pk) REFERENCES nss.master_data (master_data_pk);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_asset_acquisition_method'
                   AND conrelid = 'nss.asset'::regclass) THEN
        ALTER TABLE nss.asset
            ADD CONSTRAINT fk_asset_acquisition_method
            FOREIGN KEY (acquisition_method_master_data_pk) REFERENCES nss.master_data (master_data_pk);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_property_acquisition_method
    ON nss.property (acquisition_method_master_data_pk) WHERE acquisition_method_master_data_pk IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_asset_acquisition_method
    ON nss.asset (acquisition_method_master_data_pk) WHERE acquisition_method_master_data_pk IS NOT NULL;
