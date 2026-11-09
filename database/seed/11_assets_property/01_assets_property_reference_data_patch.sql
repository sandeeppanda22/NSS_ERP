-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 01_assets_property_reference_data_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-02)
-- Authority: docs/03_Solution/modules/assets_property/
--            05_assets_property_table_design.md (SOL-AP-005 §7.7, §8.5, §9.5,
--            §10.4, §11.4, §15), 04_assets_property_business_rules.md
--            (AP-005/007/008, AP-030, AP-035..038, AP-058, AP-067),
--            GDR-010 (Proposed - owner approval pending)
-- =====================================================
-- The Foundation seeds (01_master_category / 02_master_data /
-- 03_id_sequence_master) are existence-gated by 02_build.sh / 02_build.ps1 /
-- render_build.sh, so rows added to them never reach an existing database.
-- This module therefore carries its OWN reference data here (single source,
-- not duplicated into the Foundation seed files): applied with run_sql /
-- Invoke-Sql on every build, INSERT ... ON CONFLICT DO NOTHING (a re-run never
-- overwrites a value an admin has since renamed or deactivated).
--
-- Adds:
--   id_sequence_master   PROPERTY (prefix PROP) and ASSET (prefix AST)
--                        -> PROP1, PROP2 ... / AST1, AST2 ...  Unpadded like
--                        P1 / SS1 / SKH1; distinct prefixes keep the two
--                        namespaces from ever colliding (AP-008).
--   master_category      7 categories (below; ACQUISITION_METHOD added 2026-11-03)
--   master_data          only the values the design documents actually list.
--
-- 2026-11-03 additions (owner decisions, GDR-010 §2E/§2F): the category
-- ACQUISITION_METHOD (how a property/asset was acquired, AP-023) and two
-- CUSTODIANSHIP_END_REASON values, DISPOSED and RETIRED, used when a disposal /
-- retirement closes the active custodianship (existing values are never
-- renamed). Acquisition methods: PURCHASE and DONATION are grounded in the
-- source documents (AP-026 'purchase'; REF-001 'special donations';
-- REF-003 VI(B) 'acquisition by purchase'); GIFT, BEQUEST, TRANSFER_IN,
-- CONSTRUCTION and OTHER are CANDIDATES (not named in the source), all
-- admin-extendable.
--
-- PENDING value sets (property type, asset type, custodianship end reason,
-- document relationship type) are seeded with the source-derived CANDIDATE
-- values and stay ADMIN-EXTENDABLE through POST /api/v1/foundation/master-data
-- (FOUNDATION_MANAGE) - they are data, not schema, so nothing is frozen by
-- seeding them. See GDR-010.
-- =====================================================

INSERT INTO nss.id_sequence_master
    (sequence_code, sequence_name, prefix, current_value, padding_length)
VALUES
    ('PROPERTY', 'Property Code', 'PROP', 0, 0),
    ('ASSET',    'Asset Code',    'AST',  0, 0)
ON CONFLICT DO NOTHING;

INSERT INTO nss.master_category (category_code, category_name, description, display_order)
VALUES
    ('PROPERTY_TYPE', 'Property Type',
     'Classification of an immovable property (SOL-AP-005 §7.7 - values PENDING; candidate set, admin-extendable)', 20),
    ('ASSET_TYPE', 'Asset Type',
     'Classification of a movable asset (SOL-AP-005 §8.5 - values PENDING; candidate set, admin-extendable)', 21),
    ('CUSTODIANSHIP_END_REASON', 'Custodianship End Reason',
     'Why a custodianship ended; distinguishes dissolution/vesting from routine transfer (AP-058, SOL-AP-005 §9.5 - values PENDING; candidate set, admin-extendable)', 22),
    ('STATUTORY_OBLIGATION_TYPE', 'Statutory Obligation Type',
     'Type of statutory obligation/record of a property (AP-035..038, SOL-AP-005 §10.4)', 23),
    ('MAINTENANCE_TYPE', 'Maintenance Type',
     'Type of maintenance activity (AP-030, SOL-AP-005 §11.4)', 24),
    ('ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'Asset & Property Document Relationship',
     'Nature of a document attached to a property or asset (AP-067 examples; SOL-AP-005 §15 - values PENDING, admin-extendable)', 25),
    ('ACQUISITION_METHOD', 'Acquisition Method',
     'How a property or asset was acquired (AP-023 "how"; GDR-010 §2E - PURCHASE/DONATION grounded in the source, the rest candidates; admin-extendable)', 26)
ON CONFLICT (category_code) DO NOTHING;

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
JOIN (VALUES
    ('PROPERTY_TYPE', 'LAND',            'Land',                1),
    ('PROPERTY_TYPE', 'BUILDING',        'Building',            2),
    ('PROPERTY_TYPE', 'PREMISES',        'Premises',            3),
    ('PROPERTY_TYPE', 'OTHER_IMMOVABLE', 'Other Immovable',     4),

    ('ASSET_TYPE', 'EQUIPMENT',     'Equipment',     1),
    ('ASSET_TYPE', 'FURNITURE',     'Furniture',     2),
    ('ASSET_TYPE', 'INSTRUMENT',    'Instrument',    3),
    ('ASSET_TYPE', 'ARTICLE',       'Article',       4),
    ('ASSET_TYPE', 'OTHER_MOVABLE', 'Other Movable', 5),

    ('CUSTODIANSHIP_END_REASON', 'TRANSFER',              'Transfer',               1),
    ('CUSTODIANSHIP_END_REASON', 'DISSOLUTION_VESTING',   'Dissolution / Vesting',  2),
    ('CUSTODIANSHIP_END_REASON', 'ORGANIZATIONAL_CHANGE', 'Organizational Change',  3),
    ('CUSTODIANSHIP_END_REASON', 'OTHER',                 'Other',                  4),
    ('CUSTODIANSHIP_END_REASON', 'DISPOSED',              'Disposed',               5),
    ('CUSTODIANSHIP_END_REASON', 'RETIRED',               'Retired',                6),

    ('STATUTORY_OBLIGATION_TYPE', 'LAND_REVENUE',  'Land Revenue',  1),
    ('STATUTORY_OBLIGATION_TYPE', 'MUNICIPAL_TAX', 'Municipal Tax', 2),
    ('STATUTORY_OBLIGATION_TYPE', 'LAND_RECORD',   'Land Record',   3),
    ('STATUTORY_OBLIGATION_TYPE', 'OTHER',         'Other',         4),

    ('MAINTENANCE_TYPE', 'REPAIR_MINOR', 'Repair (Minor)', 1),
    ('MAINTENANCE_TYPE', 'REPAIR_MAJOR', 'Repair (Major)', 2),
    ('MAINTENANCE_TYPE', 'IMPROVEMENT',  'Improvement',    3),
    ('MAINTENANCE_TYPE', 'ADDITION',     'Addition',       4),
    ('MAINTENANCE_TYPE', 'ALTERATION',   'Alteration',     5),
    ('MAINTENANCE_TYPE', 'UPKEEP',       'Upkeep',         6),
    ('MAINTENANCE_TYPE', 'OTHER',        'Other',          7),

    ('ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'TITLE_DEED',              'Title Deed',              1),
    ('ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'LAND_RECORD',             'Land Record',             2),
    ('ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'MAINTENANCE_CERTIFICATE', 'Maintenance Certificate', 3),
    ('ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'PHOTOGRAPH',              'Photograph',              4),
    ('ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'OTHER',                   'Other',                   5),

    ('ACQUISITION_METHOD', 'PURCHASE',     'Purchase',      1),
    ('ACQUISITION_METHOD', 'DONATION',     'Donation',      2),
    ('ACQUISITION_METHOD', 'GIFT',         'Gift',          3),
    ('ACQUISITION_METHOD', 'BEQUEST',      'Bequest',       4),
    ('ACQUISITION_METHOD', 'TRANSFER_IN',  'Transfer In',   5),
    ('ACQUISITION_METHOD', 'CONSTRUCTION', 'Construction',  6),
    ('ACQUISITION_METHOD', 'OTHER',        'Other',         7)
) AS v (category_code, value_code, value_name, display_order)
  ON v.category_code = mc.category_code
ON CONFLICT (master_category_pk, value_code) DO NOTHING;
