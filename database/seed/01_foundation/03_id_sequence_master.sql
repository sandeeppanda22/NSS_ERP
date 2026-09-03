-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 03_id_sequence_master.sql
-- Version: 2.0
-- Authority: SOL-FND-004 §11
-- Owner: NSS_ADMIN
-- =====================================================

INSERT INTO nss.id_sequence_master
(
    sequence_code,
    sequence_name,
    prefix,
    current_value,
    padding_length
)
VALUES
(
    'PERSON',
    'Person Code',
    'P',
    0,
    10
),
(
    'SANGHA_SEVI',
    'Sangha Sevi Code',
    'SS',
    0,
    8
),
(
    'ANCHALIKA',
    'Anchalika Code',
    'ANC',
    0,
    8
),
(
    'ZILLA',
    'Zilla Code',
    'ZL',
    0,
    8
),
(
    'SAKHA',
    'Sakha Code',
    'SKH',
    0,
    8
),
(
    'SAKHA_ASANA',
    'Sakha Asana Code',
    'SA',
    0,
    8
),
(
    'PATHA_CHAKRA',
    'Patha Chakra Code',
    'PC',
    0,
    8
),
(
    'FAMILY',
    'Family Code',
    'F',
    0,
    8
),
(
    'DOCUMENT',
    'Document Code',
    'DOC',
    0,
    8
);
