-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 02_master_data.sql
-- Version: 1.3 — add CORRESPONDENCE_MEDIUM / CORRESPONDENCE_STATUS values
--          (Tier 6, 2026-10-17): filling a seed gap for value lists already
--          ERP-FROZEN in business rules §10.1 / §6.1 — not a new decision.
-- Version: 1.2 — ON CONFLICT DO NOTHING (2026-10-05): a re-run must never
--          overwrite a row an admin has since edited through the UI
--          (e.g. a renamed master-data label). Insert-if-missing only.
-- Authority: SOL-FND-004 §7, §29
-- Owner: NSS_ERP_ADMIN
-- Note: References master_category by category_code
--       using subquery. Requires 01_master_category.sql
--       to have been executed first.
-- =====================================================

-- -------------------------------------------------
-- GENDER values
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('MALE',   'Male',   1),
    ('FEMALE', 'Female', 2),
    ('OTHER',  'Other',  3)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'GENDER'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- MARITAL_STATUS values
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('UNMARRIED', 'Unmarried', 1),
    ('MARRIED',   'Married',   2),
    ('WIDOWED',   'Widowed',   3),
    ('DIVORCED',  'Divorced',  4),
    ('SEPARATED', 'Separated', 5)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'MARITAL_STATUS'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- ADDRESS_TYPE values
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('PERMANENT', 'Permanent Address', 1),
    ('CURRENT',   'Current Address',   2),
    ('OFFICIAL',  'Official Address',  3)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'ADDRESS_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- DOCUMENT_TYPE values
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('PHOTO',              'Photograph',           1),
    ('ID_PROOF',           'Identity Proof',       2),
    ('ADDRESS_PROOF',      'Address Proof',        3),
    ('CERTIFICATE',        'Certificate',          4),
    ('CORRESPONDENCE',     'Correspondence',       5),
    ('PROPERTY_DOCUMENT',  'Property Document',    6),
    ('MEETING_MINUTES',    'Meeting Minutes',      7)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'DOCUMENT_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- MEMBERSHIP_TYPE values
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('PROBATIONARY', 'Darshaka',            1),
    ('REGULAR',      'Regular Member',      2),
    ('ASSOCIATE',    'Associate Member',    3),
    ('HONORARY',     'Honorary Member',     4)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'MEMBERSHIP_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- STATUS values (unified ERP-wide lifecycle statuses)
-- Replaces per-module MEMBERSHIP_STATUS and
-- ORGANIZATION_STATUS. Each module picks its
-- applicable subset via applicable_modules column.
-- Authority: NSS Bye-Law §D(d), §12, §I, §C
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, description, display_order, applicable_modules)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.description, v.display_order, v.applicable_modules
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('PROPOSED',    'Proposed',    'Entity proposed but not yet approved',                                1, '{ORGANIZATION}'::TEXT[]),
    ('APPROVED',    'Approved',    'Approved by governance, pending activation',                          2, '{ORGANIZATION}'::TEXT[]),
    ('ACTIVE',      'Active',      'Currently operational / active',                                     3, '{ORGANIZATION,MEMBERSHIP,PERSON}'::TEXT[]),
    ('INACTIVE',    'Inactive',    'Temporarily non-operational',                                        4, '{ORGANIZATION,MEMBERSHIP,PERSON}'::TEXT[]),
    ('SUSPENDED',   'Suspended',   'Suspended by governance decision',                                   5, '{ORGANIZATION,MEMBERSHIP}'::TEXT[]),
    ('LAPSED',      'Lapsed',      'Lapsed due to non-renewal or non-attendance (Bye-Law §D(d))',        6, '{MEMBERSHIP}'::TEXT[]),
    ('TRANSFERRED', 'Transferred', 'Transferred to another unit',                                        7, '{MEMBERSHIP}'::TEXT[]),
    ('RESIGNED',    'Resigned',    'Voluntarily departed',                                               8, '{MEMBERSHIP}'::TEXT[]),
    ('EXPELLED',    'Expelled',    'Expelled by governance decision (Bye-Law §D(d)(iii))',                9, '{MEMBERSHIP}'::TEXT[]),
    ('DECEASED',    'Deceased',    'Person is deceased (Bye-Law §D(d)(i))',                              10, '{PERSON}'::TEXT[]),
    ('DISSOLVED',   'Dissolved',   'Organization permanently dissolved (Bye-Law §I)',                    11, '{ORGANIZATION}'::TEXT[]),
    ('ARCHIVED',    'Archived',    'Permanently closed, retained for history',                           12, '{ORGANIZATION,MEMBERSHIP,PERSON}'::TEXT[]),
    ('EXPIRED',          'Expired',          'Credential or document term has expired (Bye-Law §C(1)(c))',            13, '{MEMBERSHIP}'::TEXT[]),
    ('RENEWAL_PENDING',  'Renewal Pending',  'Membership renewal requested, awaiting approval',                    14, '{MEMBERSHIP}'::TEXT[]),
    ('ON_HOLD',          'On Hold',          'Membership temporarily on hold (administrative)',                     15, '{MEMBERSHIP}'::TEXT[]),
    ('DISCIPLINARY_REVIEW', 'Disciplinary Review', 'Under disciplinary review by governance (Bye-Law §D(d)(iii))', 16, '{MEMBERSHIP}'::TEXT[])
) AS v(value_code, value_name, description, display_order, applicable_modules)
WHERE mc.category_code = 'STATUS'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- RELATIONSHIP_TYPE values
-- (Comprehensive for Indian family structure —
--  used by Family module for family_relationship)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
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
    -- Self (family founder / head with no relational context)
    ('SELF',               'Self',                     0),
    -- Other
    ('OTHER',              'Other Relative',          29)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'RELATIONSHIP_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- ORGANIZATION_TYPE values
-- (13 types per NSS Bye-Law hierarchy + preamble)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, description, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.description, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('KENDRA',           'Kendra Sangha',     'Central Body — Apex Organization',                                    1),
    ('NILACHALA_KUTIRA', 'Nilachala Kutira',   'Eternal Abode - Puri',                                               2),
    ('SMRUTI_MANDIRA',   'Smruti Mandira',     'Nigamananda Smruti Mandir',                                          3),
    ('ANCHALIKA_SANGHA', 'Anchalika Sangha',   'Administrative unit — intermediate organizational level',             4),
    ('ZILLA_SANGHA',     'Zilla Sangha',       'Administrative unit — intermediate organizational level',             5),
    ('SAKHA_SANGHA',     'Sakha Sangha',       'Physical Sangha location — branch with own building',                 6),
    ('SAKHA_ASANA',      'Sakha Asana',        'Approved Sakha without own building',                                 7),
    ('PARIBARIK_ASANA',  'Paribarik Asana',    'Family-level Asana — per Parichay Patra holder; renewed with Parichay Patra — Bye-Law §C(2)(iii)', 8),
    ('PARIBARIK_SANGHA', 'Paribarik Sangha',   'Family organisation attached to Kendra — Bye-Law Preamble',             9),
    ('PATHA_CHAKRA',     'Patha Chakra',       'Study Circle',                                                        10),
    ('KUMARI_SANGHA',    'Kumari Sangha',      'Kumari Sangha — unmarried female participants organization (Kumari Module §24)', 11),
    ('SEVAK_SANGHA',     'Sevak Sangha',       'Sevak Sangha — service-oriented wing organization',                     12),
    ('MAHILA_SANGHA',    'Mahila Sangha',      'Mahila Sangha — women''s wing organization (NSS Mahila Sangha Bye-Law)', 13)
) AS v(value_code, value_name, description, display_order)
WHERE mc.category_code = 'ORGANIZATION_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- (STATUS values are above — unified ERP-wide category
--  replaces the former per-module ORGANIZATION_STATUS)
-- -------------------------------------------------

-- -------------------------------------------------
-- BLOOD_GROUP values
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('A_POSITIVE',  'A+',  1),
    ('A_NEGATIVE',  'A-',  2),
    ('B_POSITIVE',  'B+',  3),
    ('B_NEGATIVE',  'B-',  4),
    ('AB_POSITIVE', 'AB+', 5),
    ('AB_NEGATIVE', 'AB-', 6),
    ('O_POSITIVE',  'O+',  7),
    ('O_NEGATIVE',  'O-',  8)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'BLOOD_GROUP'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE values
-- (correspondence_finance_reference.relationship_type_master_data_pk —
--  SOL-ADMIN-009 §6.5, owner-confirmed 2026-10-17)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('PAYMENT',    'Payment',    1),
    ('RECEIPT',    'Receipt',    2),
    ('REFUND',     'Refund',     3),
    ('TAX',        'Tax',        4),
    ('ADJUSTMENT', 'Adjustment', 5),
    ('OTHER',      'Other',      6)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- CORRESPONDENCE_MEDIUM values
-- (correspondence.medium_master_data_pk — business rules §10.1, ERP-FROZEN)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('POST',          'Post',          1),
    ('EMAIL',         'Email',         2),
    ('HAND_DELIVERY', 'Hand Delivery', 3),
    ('CIRCULAR',      'Circular',      4),
    ('FAX',           'Fax',           5),
    ('COURIER',       'Courier',       6)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'CORRESPONDENCE_MEDIUM'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- CORRESPONDENCE_STATUS values
-- (correspondence.status_master_data_pk — business rules §6.1, ERP-FROZEN)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('REGISTERED',      'Registered',      1),
    ('PENDING_ACTION',  'Pending Action',  2),
    ('ACTIONED',        'Actioned',        3),
    ('CLOSED',          'Closed',          4)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'CORRESPONDENCE_STATUS'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- ATTENDANCE_STATUS values
-- (weekly_sangha_puja_attendance.attendance_status_master_data_pk —
--  frozen set, SOL-ATT-004 §5 / §17, business rules ATT-006/007/008)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('PRESENT',          'Present',          1),
    ('ABSENT',           'Absent',           2),
    ('EXCUSED_ABSENCE',  'Excused Absence',  3)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'ATTENDANCE_STATUS'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- ATTENDANCE_REVIEW_STATUS values
-- (attendance_review.review_status_master_data_pk — frozen set,
--  SOL-ATT-005 §15 / §18, business rules ATT-018)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('OPEN',                     'Open',                      1),
    ('DEFERRED',                 'Deferred',                  2),
    ('CLOSED',                   'Closed',                    3),
    ('ESCALATED_TO_PRESIDENT',   'Escalated to President',    4),
    ('ESCALATED_TO_PARICHALAK',  'Escalated to Parichalak',   5)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'ATTENDANCE_REVIEW_STATUS'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;

-- -------------------------------------------------
-- ATTENDANCE_EXCEPTION_TYPE values
-- (attendance_exception.exception_type_master_data_pk — NOT frozen to this
--  exact list, SOL-ATT-004 §11: "catalogue may be extended through approved
--  project governance." These four are sensible defaults, editable/
--  extensible like any other master-data category via Reference Data.)
-- -------------------------------------------------

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
CROSS JOIN (VALUES
    ('MEDICAL',          'Medical',          1),
    ('TRAVEL',           'Travel',           2),
    ('FAMILY_EMERGENCY', 'Family Emergency', 3),
    ('OTHER',            'Other',            4)
) AS v(value_code, value_name, display_order)
WHERE mc.category_code = 'ATTENDANCE_EXCEPTION_TYPE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;
