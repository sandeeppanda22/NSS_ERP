-- =====================================================
-- NSS ERP
-- Module: Organization
-- Seed File: 03_organization.sql
-- Version: 2.1 — ON CONFLICT DO NOTHING, not DO UPDATE (2026-10-05): a
--          re-run must never overwrite an admin's edit to a Sakha's
--          name/address/contact info. Insert-if-missing only.
-- Authority: SOL-ARCH-010 §8, SOL-ORG-005 §48
-- Owner: NSS_ERP_ADMIN
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
-- v2.0 Migration (2026-09-12):
--       Type/status now resolved via Foundation master_data
--       (categories ORGANIZATION_TYPE / STATUS) instead of
--       standalone organization_type_master /
--       organization_status_master tables.
-- =====================================================

-- -------------------------------------------------
-- Kendra Sangha (apex governing body)
-- -------------------------------------------------

INSERT INTO nss.organization
    (organization_name, organization_type_master_data_pk,
     status_master_data_pk, parent_organization_pk,
     organization_code, short_code,
     address_line_1, address_line_2, postal_code_pk, country_pk,
     phone_number, country_phone_code, mobile_number)
SELECT
    'Nilachala Saraswata Sangha',
    ot.master_data_pk,
    os.master_data_pk,
    NULL,
    'KEN',
    -- short_code seeded (not left for admin UI assignment, unlike other
    -- orgs/Sakhas): correspondence reference numbers (CORR-EXT-001,
    -- SOL-ADMIN-009 §4.9) must read NSS/{IN|OUT}/YYYY-YY/NNN for Kendra
    -- outward/inward letters — owner-confirmed 2026-10-17.
    'NSS',
    'Satsikshya Mandir, A/4, Unit-9',
    'Bhubaneswar',
    pc.postal_code_pk,
    c.country_pk,
    '+91-674-2390055',
    '+91',
    '9238106823'
FROM nss.master_data ot
JOIN nss.master_category mc_type
     ON mc_type.master_category_pk = ot.master_category_pk
CROSS JOIN nss.master_data os
JOIN nss.master_category mc_status
     ON mc_status.master_category_pk = os.master_category_pk
CROSS JOIN nss.country c
CROSS JOIN nss.postal_code pc
JOIN nss.state s ON s.state_pk = pc.state_pk
WHERE mc_type.category_code = 'ORGANIZATION_TYPE'
  AND ot.value_code = 'KENDRA'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '751022'
  AND s.country_pk = c.country_pk
ON CONFLICT (organization_code) DO NOTHING;

-- -------------------------------------------------
-- Nilachala Kutira (Eternal Abode, Puri)
-- -------------------------------------------------

INSERT INTO nss.organization
    (organization_name, organization_type_master_data_pk,
     status_master_data_pk, parent_organization_pk,
     organization_code,
     address_line_1, address_line_2, postal_code_pk, country_pk)
SELECT
    'Nilachala Kutira',
    ot.master_data_pk,
    os.master_data_pk,
    NULL,
    'NKT',
    'Puri',
    NULL,
    pc.postal_code_pk,
    c.country_pk
FROM nss.master_data ot
JOIN nss.master_category mc_type
     ON mc_type.master_category_pk = ot.master_category_pk
CROSS JOIN nss.master_data os
JOIN nss.master_category mc_status
     ON mc_status.master_category_pk = os.master_category_pk
CROSS JOIN nss.country c
CROSS JOIN nss.postal_code pc
JOIN nss.state s ON s.state_pk = pc.state_pk
WHERE mc_type.category_code = 'ORGANIZATION_TYPE'
  AND ot.value_code = 'NILACHALA_KUTIRA'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '752001'
  AND s.country_pk = c.country_pk
ON CONFLICT (organization_code) DO NOTHING;

-- -------------------------------------------------
-- Smruti Mandira (Nigamananda Smruti Mandir — memorial temple)
-- -------------------------------------------------

INSERT INTO nss.organization
    (organization_name, organization_type_master_data_pk,
     status_master_data_pk, parent_organization_pk,
     organization_code,
     address_line_1, address_line_2, postal_code_pk, country_pk,
     phone_number)
SELECT
    'Sri Shri Nigamananda Smruti Mandir',
    ot.master_data_pk,
    os.master_data_pk,
    NULL,
    'SMR',
    'Swargadwar Rd, Bali Sahi',
    'Puri',
    pc.postal_code_pk,
    c.country_pk,
    '+91-6752-230631'
FROM nss.master_data ot
JOIN nss.master_category mc_type
     ON mc_type.master_category_pk = ot.master_category_pk
CROSS JOIN nss.master_data os
JOIN nss.master_category mc_status
     ON mc_status.master_category_pk = os.master_category_pk
CROSS JOIN nss.country c
CROSS JOIN nss.postal_code pc
JOIN nss.state s ON s.state_pk = pc.state_pk
WHERE mc_type.category_code = 'ORGANIZATION_TYPE'
  AND ot.value_code = 'SMRUTI_MANDIRA'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code = 'ACTIVE'
  AND c.country_code = 'IN'
  AND pc.postal_code = '752001'
  AND s.country_pk = c.country_pk
ON CONFLICT (organization_code) DO NOTHING;
