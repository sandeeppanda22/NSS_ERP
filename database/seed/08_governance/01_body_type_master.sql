-- =====================================================
-- NSS ERP
-- Module: Governance
-- Seed File: 01_body_type_master.sql
-- Version: 1.1 — added ANCHALIKA_GOVERNING_BODY, ZILLA_GOVERNING_BODY,
--          PATHA_CHAKRA_GOVERNING_BODY (§63 composite auto-grant rule,
--          owner-confirmed 2026-10-09): these 3 org-scoped governance
--          bodies were previously unmodeled even though their matching
--          NSS_ERP_ANCHALIKA_ADMIN / NSS_ERP_ZILLA_ADMIN /
--          NSS_ERP_PATHA_CHAKRA_ADMIN roles already existed. Admin-created
--          per organization instance via "Add Body", same pattern as
--          Sakha Governing Body — intentionally NOT seeded as rows in
--          03_body_master.sql.
-- Version: 1.0 — ON CONFLICT DO NOTHING: a re-run must never overwrite a
--          row an admin has since edited through the Governance UI
--          (PATCH /body-types/{pk}). Insert-if-missing only.
-- Authority: GOV-BR-003/006/010/011/023/024/025/031/032, §63,
--            SOL-GOV-002 §4-5, 04_governance_business_rules.md
-- Owner: Governance
--
-- Scope: the 5 body types that are explicitly FROZEN with their own
-- GOV-BR rule(s) describing a distinct, named governance structure, plus
-- the 3 Anchalika/Zilla/Patha Chakra governing bodies added under §63
-- (same org-scoped, admin-created pattern as Sakha Governing Body). This
-- is a starter catalogue, not a closed list — `position_master` and
-- `body_type_master` are caller-extensible via POST /body-types and
-- POST /positions for anything not covered here (e.g. a generic
-- "Committee" instance), per the DDL README's design note #70-77.
--
-- MAHILA_PARICHALANA_MANDALI note: owner-confirmed (2026-10-07) to be the
-- same entity as the Mahila Sangha Bye-Law's own "Governing Body" (p.9,
-- Section 5). The Bye-Law is treated as the higher-authority source for
-- this body's composition; see GOV-BR-032's correction note.
--
-- NOT seeded here: a generic "COMMITTEE" type is mentioned as an example
-- in the DDL header comment but has no FROZEN GOV-BR rule of its own
-- (table design doc §27 describes committees as reusing these same
-- tables, master-data driven, without naming a specific type code) — add
-- it later via the API if/when an actual committee needs one, rather than
-- seeding a speculative row now.
-- =====================================================

INSERT INTO nss.body_type_master (body_type_code, body_type_name, description)
VALUES
    ('KENDRA_GOVERNING_BODY',
     'Kendra Governing Body',
     'The statutorily defined nine-member Kendra-level governing body (GOV-BR-010/011).'),

    ('SAKHA_GOVERNING_BODY',
     'Sakha Governing Body',
     'The governing body of a Sakha Sangha branch.'),

    ('ADVISORY_BOARD',
     'Advisory Board',
     'Advises the Kendra Governing Body; one representative from each Sakha Sangha (GOV-BR-023/024/025).'),

    ('MAHILA_PARICHALANA_MANDALI',
     'Mahila Parichalana Mandali',
     'Nine-member governing body of the Mahila Sangha: President, Vice-President, Parichalak, Secretary, Joint Secretary, Treasurer, and 3 Members (GOV-BR-031/032; Mahila Sangha Bye-Law p.9 Section 5).'),

    ('SEVAK_SANGHA_EXECUTIVE',
     'Sevak Sangha',
     'Executive body of the Sevak Sangha, using the same Unified Body Governance Model.'),

    ('ANCHALIKA_GOVERNING_BODY',
     'Anchalika Governing Body',
     'The governing body of an Anchalika Sangha branch; President, Secretary, and an optional Treasurer (§63; owner decision 2026-10-23 — Treasurer, not Cashier, at every governance tier). Org-scoped, admin-created via "Add Body" — same pattern as Sakha Governing Body.'),

    ('ZILLA_GOVERNING_BODY',
     'Zilla Governing Body',
     'The governing body of a Zilla Sangha branch; President, Secretary, and an optional Treasurer (§63; owner decision 2026-10-23 — Treasurer, not Cashier, at every governance tier). Org-scoped, admin-created via "Add Body" — same pattern as Sakha Governing Body.'),

    ('PATHA_CHAKRA_GOVERNING_BODY',
     'Patha Chakra Governing Body',
     'The governing body of a Patha Chakra; President, Secretary, and an optional Treasurer (§63; owner decision 2026-10-23 — Treasurer, not Cashier, at every governance tier). Org-scoped, admin-created via "Add Body" — same pattern as Sakha Governing Body.')
ON CONFLICT (body_type_code) DO NOTHING;

-- Version: 1.2 (2026-10-21) — DB-level seat-count backstop
-- (nss.fn_enforce_body_seat_limit(), database/ddl/08_governance/
-- 12_governance_seat_limits.sql). max_members is not part of the
-- INSERT above (ON CONFLICT DO NOTHING would silently skip it on a
-- re-run against a pre-existing row), so it is set via a separate,
-- idempotent UPDATE that is safe to re-run — it always converges to
-- the same values regardless of what an admin may have edited via
-- PATCH /body-types/{pk} in the meantime, since max_members is not
-- currently exposed on that endpoint for editing.
--
-- Flat per-type caps only (see 01_body_type_master.sql DDL comment
-- for the full rationale):
--   KENDRA_GOVERNING_BODY        = 9  (GOV-BR-010/011)
--   SAKHA_GOVERNING_BODY         = 9
--   SEVAK_SANGHA_EXECUTIVE       = 3
--   ANCHALIKA_GOVERNING_BODY     = 3  (§63)
--   ZILLA_GOVERNING_BODY         = 3  (§63)
--   PATHA_CHAKRA_GOVERNING_BODY  = 3  (§63)
--
-- Deliberately NOT updated here (left NULL, their default):
--   MAHILA_PARICHALANA_MANDALI — two-tier cap (8 Kendra-level / 3
--     Sakha-level) by body_master.organization_pk-nullness; a single
--     constant on this table cannot express it, so the trigger
--     derives the right limit at write time instead.
--   ADVISORY_BOARD — one seat per active Sakha Sangha (scales with
--     the Sakha count), not a fixed number; the trigger enforces the
--     real "one seat per Sakha" rule instead of a flat count.
UPDATE nss.body_type_master
SET max_members = v.max_members
FROM (VALUES
    ('KENDRA_GOVERNING_BODY',       9),
    ('SAKHA_GOVERNING_BODY',        9),
    ('SEVAK_SANGHA_EXECUTIVE',      3),
    ('ANCHALIKA_GOVERNING_BODY',    3),
    ('ZILLA_GOVERNING_BODY',        3),
    ('PATHA_CHAKRA_GOVERNING_BODY', 3)
) AS v(body_type_code, max_members)
WHERE nss.body_type_master.body_type_code = v.body_type_code;
