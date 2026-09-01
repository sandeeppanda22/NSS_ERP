-- =====================================================
-- NSS ERP
-- Module: Organization
-- Seed File: 01_organization_type_master.sql
-- Version: 1.0
-- Authority: SOL-ORG-005 §48, SOL-ORG-002 §27
-- Owner: NSS_ADMIN
-- Note: 8 frozen organization types (decided 2026-08-28)
-- =====================================================

INSERT INTO organization_type_master
    (organization_type_code, organization_type_name, description, sort_order)
VALUES
    ('KENDRA',           'Kendra Sangha',
     'Central Body — apex organization',                    1),

    ('NILACHALA_KUTIRA', 'Nilachala Kutira',
     'Eternal Abode - Puri',                        2),

    ('SMRUTI_MANDIRA',   'Smruti Mandira',
     'Nigamananda Smruti Mandir',         3),

    ('ANCHALIKA_SANGHA', 'Anchalika Sangha',
     'Administrative unit — intermediate organizational level',     4),

    ('ZILLA_SANGHA',     'Zilla Sangha',
     'Administrative unit — intermediate organizational level',     5),

    ('SAKHA_SANGHA',     'Sakha Sangha',
     'Physical Sangha location — branch with own building',         6),

    ('SAKHA_ASANA',      'Sakha Asana',
     'Approved Sakha without own building',                         7),

    ('PATHA_CHAKRA',     'Patha Chakra',
     'Study Circle',                                                8);
