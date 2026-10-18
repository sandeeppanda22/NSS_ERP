-- =====================================================
-- NSS ERP
-- Module: Governance
-- Seed File: 02_position_master.sql
-- Version: 1.0 — ON CONFLICT DO NOTHING: a re-run must never overwrite a
--          row an admin has since edited through the Governance UI
--          (PATCH /positions/{pk}). Insert-if-missing only.
-- Authority: GOV-BR-010/012/013/014/032, SOL-GOV-002 §9-11,
--            04_governance_business_rules.md
-- Owner: Governance
--
-- Scope: positions explicitly named in a FROZEN GOV-BR rule, plus
-- MUKHYA_PUJAKA (owner-confirmed 2026-10-07 — see note below). A
-- position is reusable across body types (GOV-BR-013); which positions a
-- given body actually fills is a body/business composition concern, not
-- enforced by this catalogue. Caller-extensible via POST /positions for
-- anything not covered here.
--
-- JOINT_SECRETARY vs ASSISTANT_SECRETARY: both are real, distinct
-- positions used by different body types — ASSISTANT_SECRETARY is the
-- Kendra Governing Body's position (GOV-BR-010); JOINT_SECRETARY is the
-- Mahila Parichalana Mandali's position per the Mahila Sangha Bye-Law
-- (p.9), which superseded this project's earlier "Assistant Secretary"
-- wording for that body (GOV-BR-032 correction, 2026-10-07).
--
-- MUKHYA_PUJAKA: owner-confirmed (2026-10-07) as an ERP-operational
-- position, NOT named in any Bye-Law — same non-Bye-Law status as the
-- HONORARY membership type. It is a single NSS-wide post (one person at a
-- time across all of NSS).
--
-- Owner-confirmed 2026-10-08: Mukhya Pujaka is a POSITION, never a body
-- type — the post always exists irrespective of whether its holder also
-- sits on the Kendra Governing Body. The seat is stored in exactly ONE
-- place: a MUKHYA_PUJAKA body_member_assignment on the Kendra Governing
-- Body. When the holder is seated there he DOES count as one of that
-- body's nine members (no seat exemption). The ERP offers a dedicated
-- "Mukhya Pujaka" entry point in addition to the normal GB position-
-- assignment flow, but both write that same single row
-- (GET /mukhya-pujaka resolves it — see api/routers/governance.py).
--
-- Which positions each body type may hold (and its seat limit) is
-- enforced at the API layer — see _COMPOSITION_RULES in
-- api/routers/governance.py and GOV-BR-011A.
--
-- PARICHALAK: also a single NSS-wide seat (one person holds the title at
-- a time), owner-confirmed (2026-10-07). The same person is also the
-- Mahila Parichalana Mandali's Parichalak, but owner-confirmed 2026-10-08:
-- that is NOT a second body_member_assignment row. The Mahila Parichalana
-- Mandali inherits the Kendra Governing Body's Parichalak instead of
-- taking an independent assignment — PARICHALAK is deliberately excluded
-- from that body's assignable positions in _COMPOSITION_RULES
-- (api/routers/governance.py).
--
-- Both MUKHYA_PUJAKA's and PARICHALAK's singleton/scope constraints are
-- NOT a DDL cap — they are enforced at the API/business layer, same
-- pattern as other occupancy limits (DDL README design note #4,
-- SOL-GOV-004 §25/§8.9).
-- =====================================================

INSERT INTO nss.position_master (position_code, position_name, description, display_order)
VALUES
    ('PRESIDENT',            'President',            'Presiding office-bearer.', 1),
    ('VICE_PRESIDENT',       'Vice-President',        'Deputises for the President.', 2),
    ('PARICHALAK',           'Parichalak',            'Guiding/supervisory office-bearer (Kendra and Mahila bodies).', 3),
    ('SECRETARY',            'Secretary',             'Principal administrative office-bearer.', 4),
    ('ASSISTANT_SECRETARY',  'Assistant Secretary',   'Assists the Secretary — Kendra Governing Body (GOV-BR-010).', 5),
    ('JOINT_SECRETARY',      'Joint Secretary',       'Assists the Secretary — Mahila Parichalana Mandali, per Mahila Sangha Bye-Law p.9 (GOV-BR-032).', 6),
    ('TREASURER',            'Treasurer',             'Custodian of funds and accounts — Kendra Governing Body and Kendra Mahila Parichalana Mandali.', 7),
    ('CASHIER',              'Cashier',               'Custodian of funds — Sakha Governing Body, Sakha Mahila Parichalana Mandali (optional), Sevak Sangha Executive (owner-confirmed 2026-10-07).', 8),
    ('MUKHYA_PUJAKA',        'Mukhya Pujaka',         'ERP-operational, non-Bye-Law seat; single NSS-wide post. May sit on the Kendra Governing Body (optional).', 9),
    ('MEMBER',               'Member',                'Generic member seat (non office-bearer).', 10)
ON CONFLICT (position_code) DO NOTHING;
