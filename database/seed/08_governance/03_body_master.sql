-- =====================================================
-- NSS ERP
-- Module: Governance
-- Seed File: 03_body_master.sql
-- Version: 1.0 — ON CONFLICT DO NOTHING: a re-run must never overwrite a
--          row an admin has since edited through the Governance UI
--          (PATCH /bodies/{pk}). Insert-if-missing only.
-- Authority: GOV-BR-010/011/023/024/025/031/032, SOL-GOV-002 §4-5,
--            04_governance_business_rules.md
-- Owner: Governance
--
-- Scope: the 3 NSS-wide singleton bodies that are not tied to any one
-- Sakha/Mahila Sangha and therefore cannot be created through the
-- Governance UI's "Add Body" form (which always requires picking an
-- Organization for anything other than these). Owner-confirmed
-- (2026-10-07): admins only ever manually create the per-Sakha Mahila
-- Parichalana Mandali and the Sakha-level Sevak Sangha Executive — both
-- are org-scoped instance data and intentionally have NO seed file.
-- These 3 rows are the exception:
--   - Kendra Governing Body       (GOV-BR-010/011) — one, NSS-wide.
--   - Advisory Board              (GOV-BR-023/024/025) — one, NSS-wide.
--   - Mahila Parichalana Mandali  (GOV-BR-031/032) — the CENTRAL Mahila
--     Sangha's own Governing Body (Nilachala Saraswata Mahila Sangha,
--     Puri; Mahila Sangha Bye-Law p.9 Section 5). Each Sakha-affiliated
--     Mahila Sangha gets its OWN additional, org-scoped row of this same
--     body_type via the normal manual "Add Body" flow — this seed only
--     covers the one central/NSS-wide instance.
--
-- organization_pk is left NULL for all 3 rows above — these bodies are
-- not scoped to any single Sakha/Mahila Sangha organization.
--
-- Owner-confirmed (2026-10-14): a second block below additionally seeds
-- one empty Sakha Governing Body SHELL (body_type SAKHA_GOVERNING_BODY,
-- no office-holders) per active SAKHA_SANGHA organization, so every one
-- of the 175 real Sakha branches has a body to assign members onto from
-- day one. organization_pk is set to that Sakha's own organization_pk
-- (GOV-BR-059 — org-scoped bodies carry the org). Office-holders are
-- never seeded here on a fresh build (per "no demo Person/Family/
-- Membership data" — only the local-dev-only, RUN_DEMO_SEED-gated
-- database/seed/demo/nss_demo_seed.sql assigns demo office-holders onto
-- these shells). The per-Sakha Mahila Parichalana Mandali and the
-- Sakha-level Sevak Sangha Executive remain out of scope here — still
-- manually created, no seed file, as above.
-- =====================================================

INSERT INTO nss.body_master (body_type_master_pk, body_code, body_name, description, organization_pk, effective_from)
SELECT bt.body_type_master_pk, v.body_code, v.body_name, v.description, NULL, CURRENT_DATE
FROM (VALUES
    ('KENDRA_GOVERNING_BODY',
     'KENDRA_GB',
     'Kendra Governing Body',
     'The statutorily defined nine-member Kendra-level governing body (GOV-BR-010/011). NSS-wide; auto-created, not manually creatable.'),

    ('ADVISORY_BOARD',
     'ADVISORY_BOARD',
     'Advisory Board',
     'Advises the Kendra Governing Body; one representative from each Sakha Sangha (GOV-BR-023/024/025). Each Sakha Sangha''s own general body nominates its single representative and is the only authority that may withdraw that nomination — an NSS-wide admin cannot (owner-confirmed 2026-10-08; see one_seat_per_sakha and _require_nominating_sakha_scope in api/routers/governance.py). NSS-wide; auto-created, not manually creatable.'),

    ('MAHILA_PARICHALANA_MANDALI',
     'KENDRA_MAHILA_PM',
     'Nilachala Saraswata Mahila Sangha — Governing Body',
     'The central Mahila Sangha''s own nine-member Governing Body: President, Vice-President, Parichalak, Secretary, Joint Secretary, Treasurer, and 3 Members (GOV-BR-031/032; Mahila Sangha Bye-Law p.9 Section 5). The Parichalak seat is inherited from the Kendra Governing Body rather than independently assigned (owner-confirmed 2026-10-08 — see _COMPOSITION_RULES in api/routers/governance.py). NSS-wide; auto-created, not manually creatable. Per-Sakha Mahila Sanghas get their own separate org-scoped row of this same body type, created manually.')
) AS v(body_type_code, body_code, body_name, description)
JOIN nss.body_type_master bt ON bt.body_type_code = v.body_type_code
ON CONFLICT (body_code) DO NOTHING;

-- One empty Sakha Governing Body shell per active Sakha organization
-- (see header note above, 2026-10-14). No office-holders assigned here.
INSERT INTO nss.body_master (body_type_master_pk, body_code, body_name, description, organization_pk, effective_from)
SELECT
    bt.body_type_master_pk,
    o.organization_code || '_GB',
    o.organization_name || ' — Governing Body',
    'Sakha Governing Body for ' || o.organization_name || ' (GOV-BR per Sakha Sangha By-Law). Org-scoped; auto-created shell, office-holders assigned via election/appointment.',
    o.organization_pk,
    CURRENT_DATE
FROM nss.organization o
JOIN nss.master_data ot
    ON ot.master_data_pk = o.organization_type_master_data_pk
JOIN nss.master_category mc_type
    ON mc_type.master_category_pk = ot.master_category_pk
JOIN nss.master_data os
    ON os.master_data_pk = o.status_master_data_pk
JOIN nss.master_category mc_status
    ON mc_status.master_category_pk = os.master_category_pk
CROSS JOIN nss.body_type_master bt
WHERE mc_type.category_code   = 'ORGANIZATION_TYPE'
  AND ot.value_code           = 'SAKHA_SANGHA'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code           = 'ACTIVE'
  AND bt.body_type_code       = 'SAKHA_GOVERNING_BODY'
ON CONFLICT (body_code) DO NOTHING;
