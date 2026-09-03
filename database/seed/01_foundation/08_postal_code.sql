-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 08_postal_code.sql
-- Version: 1.0
-- Authority: SOL-FND-004, SOL-ARCH-010 §8
-- Owner: NSS_ADMIN
-- Note: Seed postal codes referenced by Organization
--       seed data. This is a minimal bootstrap set —
--       full postal code data loading is a future task.
-- =====================================================

-- Bhubaneswar — Kendra (Satsikshya Mandir, Unit-9)
INSERT INTO postal_code (country_pk, state_pk, postal_code, post_office_name)
SELECT c.country_pk, s.state_pk, '751022', 'Unit 9 SO'
FROM country c
JOIN state s ON s.country_pk = c.country_pk
WHERE c.country_code = 'IN'
  AND s.state_code = 'OD';

-- Puri — Nilachala Kutira, Smruti Mandira (Swargadwar area)
INSERT INTO postal_code (country_pk, state_pk, postal_code, post_office_name)
SELECT c.country_pk, s.state_pk, '752001', 'Puri HO'
FROM country c
JOIN state s ON s.country_pk = c.country_pk
WHERE c.country_code = 'IN'
  AND s.state_code = 'OD';
