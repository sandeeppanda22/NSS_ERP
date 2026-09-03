-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 04_country.sql
-- Version: 2.0
-- Authority: SOL-FND-004 §30
-- Owner: NSS_ADMIN
-- =====================================================

INSERT INTO nss.country
(
    country_code,
    country_name,
    display_order
)
VALUES
('IN', 'India',          1),
('US', 'United States',  2),
('GB', 'United Kingdom', 3),
('AU', 'Australia',      4),
('CA', 'Canada',         5);
