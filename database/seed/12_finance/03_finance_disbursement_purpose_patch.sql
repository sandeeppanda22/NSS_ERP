-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 03_finance_disbursement_purpose_patch.sql (idempotent patch)
-- Version: 1.0
-- Authority: NSS Bye-Law F[A](vi), F[c](ii)(iii)(iv)(v); Mahila Sangha Bye-Law
--            7(iii)(b)-(h)(j)(k); business rules FIN-BR-029, FIN-BR-048..050.
-- =====================================================
-- The purposes for which Kendra / central Mahila Sangha money may be paid out.
-- Run with run_sql / Invoke-Sql on every build (ON CONFLICT DO NOTHING: a re-run
-- never overwrites a value an admin has renamed or deactivated). Values are
-- admin-extendable; the prefix decides which Bye-Law the purpose belongs to
-- (KENDRA_* for the Kendra Sangha, MAHILA_* for the Mahila Sangha) and is
-- enforced by the API. Must run AFTER the Finance tables (master_category).
-- =====================================================

INSERT INTO nss.master_category (category_code, category_name, description, display_order)
VALUES
    ('DISBURSEMENT_PURPOSE', 'Disbursement Purpose',
     'Bye-Law-permitted purposes for paying out Kendra / Mahila Sangha funds (NSS F[c], F[A](vi); Mahila 7(iii)). KENDRA_* and MAHILA_* prefixes select the Bye-Law; admin-extendable.', 28)
ON CONFLICT (category_code) DO NOTHING;

INSERT INTO nss.master_data (master_category_pk, value_code, value_name, display_order)
SELECT mc.master_category_pk, v.value_code, v.value_name, v.display_order
FROM nss.master_category mc
JOIN (VALUES
    -- NSS Bye-Law F[c](ii): management and institutions
    ('KENDRA_MANAGEMENT',          'Management of the Kendra Sangha (F[c](ii))',                     10),
    ('KENDRA_NILACHALA_KUTIR',     'Nilachala Kutir (F[c](ii))',                                     20),
    ('KENDRA_SMRUTI_MANDIR',       'Smruti Mandir at Puri (F[c](ii))',                               30),
    ('KENDRA_SIKSHYA_KENDRA',      'Sikshya Kendra at Biratung (F[c](ii))',                          40),
    ('KENDRA_AFFILIATED_SAKHA',    'Affiliated Sakha Sangha (F[c](ii))',                             50),
    ('KENDRA_SPONSORED_INSTITUTION','Institution run or sponsored by the Kendra Sangha (F[c](ii))',  60),
    ('KENDRA_PANCHA_YAGNA',        'Pancha Yagna / Atithi Satkar (F[c](iii))',                       70),
    ('KENDRA_SPECIFIC_PURPOSE',    'Specific-purpose fund, spent for that purpose only (F[c](iv))',  80),
    ('KENDRA_MATHA_GURU_DHAMA_DONATION','Donation to the Saraswata Matha / Guru Dhama (F[c](v))',    90),
    ('KENDRA_SATSIKSHYA_BISTAR',   'Satsikshya Bistar, in consultation with the Parichalak (F[A](vi))', 100),
    ('KENDRA_PARICHALAK_EXPENDITURE','Personal expenditure of the Parichalak (F[A](vi))',           110),
    -- Mahila Sangha Bye-Law 7(iii)
    ('MAHILA_BIRTHDAY_CEREMONY',   'Annual Birth Day Ceremony of Shri Shri Thakura at Nilachala Kutir (7(iii)(b))', 210),
    ('MAHILA_NILACHALA_KUTIR',     'Day-to-day expenditure of Nilachala Kutir, Puri (7(iii)(c))',    220),
    ('MAHILA_TRAINING_EDUCATION',  'Training centres and educational institutions (7(iii)(d))',      230),
    ('MAHILA_PUBLICATION',         'Publication of books on Shri Shri Thakur (7(iii)(e))',           240),
    ('MAHILA_CLEANLINESS_PEACE',   'Cleanliness, peace and serenity of the compound (7(iii)(f))',    250),
    ('MAHILA_KUTIR_REPAIR_TAXES',  'Repairs of the Kutir, land revenue, municipal tax (7(iii)(g))',  260),
    ('MAHILA_SPONSORED_ACTIVITIES','Activities sponsored by Nilachala Saraswata Sangha (7(iii)(h))', 270),
    ('MAHILA_SPECIFIC_PURPOSE',    'Specific-purpose donation, spent for that purpose only (7(iii)(j))', 280),
    ('MAHILA_PRESIDENT_VP_EXPENSES','Expenses of the President and Vice-President (7(iii)(k))',      290)
) AS v (value_code, value_name, display_order)
  ON mc.category_code = 'DISBURSEMENT_PURPOSE'
ON CONFLICT (master_category_pk, value_code) DO NOTHING;
