-- =====================================================
-- NSS ERP
-- Module: Organization
-- Seed File: 03_organization.sql
-- Version: 1.0
-- Authority: SOL-ARCH-010 §8, SOL-ORG-005 §48
-- Owner: NSS_ADMIN
-- Note: Seeds the three unique organizations of NSS.
--       All three are unique entities — no organization_id
--       (sequence-generated IDs are for multi-instance types
--       like Sakha, Anchalika, etc.).
--       All three are peers (parent = NULL).
--
--       Kendra Sangha — apex governing body.
--         Representative Office: Satsikshya Mandir, A/4,
--         Unit-9, Bhubaneswar - 751022, Odisha, India.
--       Nilachala Kutira — Eternal Abode, Puri.
--       Smruti Mandira — Nigamananda Smruti Mandir
--         (memorial temple), Swargadwar, Puri.
--
--       All addresses are editable at runtime — seed values
--       are initial state only.
--
-- Note: city_village_pk is NULL because Foundation
--       city_village seed data is not yet implemented.
--       postal_code_pk references Foundation postal_code
--       seed (08_postal_code.sql).
--
--       Requires 01_organization_type_master.sql and
--       02_organization_status_master.sql to have been
--       executed first.
--       Uses subqueries to resolve type/status/postal PKs.
-- =====================================================

-- -------------------------------------------------
-- Kendra Sangha (apex governing body)
-- -------------------------------------------------

INSERT INTO organization
    (organization_name, organization_type_pk,
     organization_status_pk, parent_organization_pk,
     organization_code,
     address_line_1, address_line_2, postal_code_pk, country_pk)
SELECT
    'Nilachala Saraswata Sangha',
    ot.organization_type_pk,
    os.organization_status_pk,
    NULL,
    'KEN',
    'Satsikshya Mandir, A/4, Unit-9',
    'Bhubaneswar',
    pc.postal_code_pk,
    c.country_pk
FROM organization_type_master ot
CROSS JOIN organization_status_master os
CROSS JOIN country c
CROSS JOIN postal_code pc
WHERE ot.organization_type_code = 'KENDRA'
  AND os.organization_status_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '751022'
  AND pc.country_pk = c.country_pk;

-- -------------------------------------------------
-- Nilachala Kutira (Eternal Abode, Puri)
-- -------------------------------------------------

INSERT INTO organization
    (organization_name, organization_type_pk,
     organization_status_pk, parent_organization_pk,
     organization_code,
     address_line_1, address_line_2, postal_code_pk, country_pk)
SELECT
    'Nilachala Kutira',
    ot.organization_type_pk,
    os.organization_status_pk,
    NULL,
    'NKT',
    'Puri',
    NULL,
    pc.postal_code_pk,
    c.country_pk
FROM organization_type_master ot
CROSS JOIN organization_status_master os
CROSS JOIN country c
CROSS JOIN postal_code pc
WHERE ot.organization_type_code = 'NILACHALA_KUTIRA'
  AND os.organization_status_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '752001'
  AND pc.country_pk = c.country_pk;

-- -------------------------------------------------
-- Smruti Mandira (Nigamananda Smruti Mandir — memorial temple)
-- -------------------------------------------------

INSERT INTO organization
    (organization_name, organization_type_pk,
     organization_status_pk, parent_organization_pk,
     organization_code,
     address_line_1, address_line_2, postal_code_pk, country_pk)
SELECT
    'Sri Shri Nigamananda Smruti Mandir',
    ot.organization_type_pk,
    os.organization_status_pk,
    NULL,
    'SMR',
    'Swargadwar',
    'Puri',
    pc.postal_code_pk,
    c.country_pk
FROM organization_type_master ot
CROSS JOIN organization_status_master os
CROSS JOIN country c
CROSS JOIN postal_code pc
WHERE ot.organization_type_code = 'SMRUTI_MANDIRA'
  AND os.organization_status_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '752001'
  AND pc.country_pk = c.country_pk;
