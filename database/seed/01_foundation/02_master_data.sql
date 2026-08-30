-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 02_master_data.sql
-- Version: 1.0
-- Authority: SOL-FND-004 §7, §29
-- Owner: NSS_ADMIN
-- Note: References master_category by category_code
--       using subquery. Requires 01_master_category.sql
--       to have been executed first.
-- =====================================================

-- -------------------------------------------------
-- GENDER values
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    ('MALE',   'Male',   1),
    ('FEMALE', 'Female', 2),
    ('OTHER',  'Other',  3)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'GENDER';

-- -------------------------------------------------
-- MARITAL_STATUS values
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    ('UNMARRIED', 'Unmarried', 1),
    ('MARRIED',   'Married',   2),
    ('WIDOWED',   'Widowed',   3),
    ('DIVORCED',  'Divorced',  4),
    ('SEPARATED', 'Separated', 5)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'MARITAL_STATUS';

-- -------------------------------------------------
-- ADDRESS_TYPE values
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    ('PERMANENT', 'Permanent Address', 1),
    ('CURRENT',   'Current Address',   2),
    ('OFFICIAL',  'Official Address',  3)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'ADDRESS_TYPE';

-- -------------------------------------------------
-- DOCUMENT_TYPE values
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    ('PHOTO',              'Photograph',           1),
    ('ID_PROOF',           'Identity Proof',       2),
    ('ADDRESS_PROOF',      'Address Proof',        3),
    ('CERTIFICATE',        'Certificate',          4),
    ('CORRESPONDENCE',     'Correspondence',       5),
    ('PROPERTY_DOCUMENT',  'Property Document',    6),
    ('MEETING_MINUTES',    'Meeting Minutes',      7)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'DOCUMENT_TYPE';

-- -------------------------------------------------
-- MEMBERSHIP_TYPE values
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    ('PROBATIONARY', 'Probationary Member', 1),
    ('REGULAR',      'Regular Member',      2),
    ('ASSOCIATE',    'Associate Member',    3)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'MEMBERSHIP_TYPE';

-- -------------------------------------------------
-- MEMBERSHIP_STATUS values
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    ('ACTIVE',      'Active',      1),
    ('INACTIVE',    'Inactive',    2),
    ('SUSPENDED',   'Suspended',   3),
    ('TRANSFERRED', 'Transferred', 4),
    ('RESIGNED',    'Resigned',    5),
    ('EXPELLED',    'Expelled',    6),
    ('DECEASED',    'Deceased',    7)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'MEMBERSHIP_STATUS';

-- -------------------------------------------------
-- RELATIONSHIP_TYPE values
-- (Comprehensive for Indian family structure —
--  used by Family module for family_relationship)
-- -------------------------------------------------

INSERT INTO master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM master_category mc
CROSS JOIN (VALUES
    -- Immediate family
    ('SPOUSE',             'Spouse',                   1),
    ('FATHER',             'Father',                   2),
    ('MOTHER',             'Mother',                   3),
    ('SON',                'Son',                      4),
    ('DAUGHTER',           'Daughter',                 5),
    ('BROTHER',            'Brother',                  6),
    ('SISTER',             'Sister',                   7),
    -- In-laws
    ('FATHER_IN_LAW',      'Father-in-Law',            8),
    ('MOTHER_IN_LAW',      'Mother-in-Law',            9),
    ('SON_IN_LAW',         'Son-in-Law',              10),
    ('DAUGHTER_IN_LAW',    'Daughter-in-Law',          11),
    ('BROTHER_IN_LAW',     'Brother-in-Law',          12),
    ('SISTER_IN_LAW',      'Sister-in-Law',           13),
    -- Grandparents / Grandchildren
    ('GRANDFATHER',        'Grandfather',             14),
    ('GRANDMOTHER',        'Grandmother',             15),
    ('GRANDSON',           'Grandson',                16),
    ('GRANDDAUGHTER',      'Granddaughter',           17),
    -- Uncle / Aunt / Nephew / Niece
    ('UNCLE',              'Uncle',                   18),
    ('AUNT',               'Aunt',                    19),
    ('NEPHEW',             'Nephew',                  20),
    ('NIECE',              'Niece',                   21),
    -- Cousins
    ('COUSIN',             'Cousin',                  22),
    -- Step relations
    ('STEP_FATHER',        'Step-Father',             23),
    ('STEP_MOTHER',        'Step-Mother',             24),
    ('STEP_SON',           'Step-Son',                25),
    ('STEP_DAUGHTER',      'Step-Daughter',           26),
    -- Guardian / Ward
    ('GUARDIAN',           'Guardian',                27),
    ('WARD',               'Ward',                    28),
    -- Other
    ('OTHER',              'Other Relative',          29)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'RELATIONSHIP_TYPE';
