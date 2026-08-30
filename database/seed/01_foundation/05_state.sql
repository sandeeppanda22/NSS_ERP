-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 05_state.sql
-- Version: 3.0
-- Authority: SOL-FND-004 §14, SOL-ARCH-010 §8
-- Owner: NSS_ADMIN
-- Note: All states/provinces/territories for all
--       seeded countries.
-- =====================================================

-- =========================================================
-- INDIA — 28 States + 8 Union Territories
-- =========================================================

INSERT INTO state (country_pk, state_code, state_name, display_order)
SELECT c.country_pk, v.state_code, v.state_name, v.display_order
FROM country c
CROSS JOIN (VALUES
    -- States (28)
    ('AP', 'Andhra Pradesh',       1),
    ('AR', 'Arunachal Pradesh',    2),
    ('AS', 'Assam',                3),
    ('BR', 'Bihar',                4),
    ('CG', 'Chhattisgarh',        5),
    ('GA', 'Goa',                  6),
    ('GJ', 'Gujarat',             7),
    ('HR', 'Haryana',             8),
    ('HP', 'Himachal Pradesh',    9),
    ('JH', 'Jharkhand',          10),
    ('KA', 'Karnataka',          11),
    ('KL', 'Kerala',             12),
    ('MP', 'Madhya Pradesh',     13),
    ('MH', 'Maharashtra',        14),
    ('MN', 'Manipur',            15),
    ('ML', 'Meghalaya',          16),
    ('MZ', 'Mizoram',            17),
    ('NL', 'Nagaland',           18),
    ('OD', 'Odisha',             19),
    ('PB', 'Punjab',             20),
    ('RJ', 'Rajasthan',          21),
    ('SK', 'Sikkim',             22),
    ('TN', 'Tamil Nadu',         23),
    ('TS', 'Telangana',          24),
    ('TR', 'Tripura',            25),
    ('UP', 'Uttar Pradesh',      26),
    ('UK', 'Uttarakhand',        27),
    ('WB', 'West Bengal',        28),
    -- Union Territories (8)
    ('AN', 'Andaman and Nicobar Islands', 29),
    ('CH', 'Chandigarh',                  30),
    ('DN', 'Dadra and Nagar Haveli and Daman and Diu', 31),
    ('DL', 'Delhi',                       32),
    ('JK', 'Jammu and Kashmir',           33),
    ('LA', 'Ladakh',                      34),
    ('LD', 'Lakshadweep',                 35),
    ('PY', 'Puducherry',                  36)
) AS v(state_code, state_name, display_order)
WHERE c.country_code = 'IN';

-- =========================================================
-- UNITED STATES — 50 States + DC
-- =========================================================

INSERT INTO state (country_pk, state_code, state_name, display_order)
SELECT c.country_pk, v.state_code, v.state_name, v.display_order
FROM country c
CROSS JOIN (VALUES
    ('AL', 'Alabama',        1),
    ('AK', 'Alaska',         2),
    ('AZ', 'Arizona',        3),
    ('AR', 'Arkansas',       4),
    ('CA', 'California',     5),
    ('CO', 'Colorado',       6),
    ('CT', 'Connecticut',    7),
    ('DE', 'Delaware',       8),
    ('FL', 'Florida',        9),
    ('GA', 'Georgia',       10),
    ('HI', 'Hawaii',        11),
    ('ID', 'Idaho',         12),
    ('IL', 'Illinois',      13),
    ('IN', 'Indiana',       14),
    ('IA', 'Iowa',          15),
    ('KS', 'Kansas',        16),
    ('KY', 'Kentucky',      17),
    ('LA', 'Louisiana',     18),
    ('ME', 'Maine',         19),
    ('MD', 'Maryland',      20),
    ('MA', 'Massachusetts', 21),
    ('MI', 'Michigan',      22),
    ('MN', 'Minnesota',     23),
    ('MS', 'Mississippi',   24),
    ('MO', 'Missouri',      25),
    ('MT', 'Montana',       26),
    ('NE', 'Nebraska',      27),
    ('NV', 'Nevada',        28),
    ('NH', 'New Hampshire', 29),
    ('NJ', 'New Jersey',    30),
    ('NM', 'New Mexico',    31),
    ('NY', 'New York',      32),
    ('NC', 'North Carolina', 33),
    ('ND', 'North Dakota',  34),
    ('OH', 'Ohio',          35),
    ('OK', 'Oklahoma',      36),
    ('OR', 'Oregon',        37),
    ('PA', 'Pennsylvania',  38),
    ('RI', 'Rhode Island',  39),
    ('SC', 'South Carolina', 40),
    ('SD', 'South Dakota',  41),
    ('TN', 'Tennessee',     42),
    ('TX', 'Texas',         43),
    ('UT', 'Utah',          44),
    ('VT', 'Vermont',       45),
    ('VA', 'Virginia',      46),
    ('WA', 'Washington',    47),
    ('WV', 'West Virginia', 48),
    ('WI', 'Wisconsin',     49),
    ('WY', 'Wyoming',       50),
    ('DC', 'District of Columbia', 51)
) AS v(state_code, state_name, display_order)
WHERE c.country_code = 'US';

-- =========================================================
-- UNITED KINGDOM — Countries/Regions
-- =========================================================

INSERT INTO state (country_pk, state_code, state_name, display_order)
SELECT c.country_pk, v.state_code, v.state_name, v.display_order
FROM country c
CROSS JOIN (VALUES
    ('ENG', 'England',          1),
    ('SCO', 'Scotland',         2),
    ('WLS', 'Wales',            3),
    ('NIR', 'Northern Ireland', 4)
) AS v(state_code, state_name, display_order)
WHERE c.country_code = 'GB';

-- =========================================================
-- AUSTRALIA — States and Territories
-- =========================================================

INSERT INTO state (country_pk, state_code, state_name, display_order)
SELECT c.country_pk, v.state_code, v.state_name, v.display_order
FROM country c
CROSS JOIN (VALUES
    ('NSW', 'New South Wales',              1),
    ('VIC', 'Victoria',                     2),
    ('QLD', 'Queensland',                   3),
    ('WA',  'Western Australia',            4),
    ('SA',  'South Australia',              5),
    ('TAS', 'Tasmania',                     6),
    ('ACT', 'Australian Capital Territory', 7),
    ('NT',  'Northern Territory',           8)
) AS v(state_code, state_name, display_order)
WHERE c.country_code = 'AU';

-- =========================================================
-- CANADA — Provinces and Territories
-- =========================================================

INSERT INTO state (country_pk, state_code, state_name, display_order)
SELECT c.country_pk, v.state_code, v.state_name, v.display_order
FROM country c
CROSS JOIN (VALUES
    ('ON', 'Ontario',                    1),
    ('QC', 'Quebec',                     2),
    ('BC', 'British Columbia',           3),
    ('AB', 'Alberta',                    4),
    ('MB', 'Manitoba',                   5),
    ('SK', 'Saskatchewan',              6),
    ('NS', 'Nova Scotia',               7),
    ('NB', 'New Brunswick',             8),
    ('NL', 'Newfoundland and Labrador', 9),
    ('PE', 'Prince Edward Island',      10),
    ('NT', 'Northwest Territories',     11),
    ('YT', 'Yukon',                     12),
    ('NU', 'Nunavut',                   13)
) AS v(state_code, state_name, display_order)
WHERE c.country_code = 'CA';
