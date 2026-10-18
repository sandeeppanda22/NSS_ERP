-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 03_role_permission.sql (seed)
-- Seed: Role-to-permission mappings (~111 rows)
-- Version: 1.5 — added CORRESPONDENCE_VIEW / CORRESPONDENCE_MANAGE
--          (Tier 6, 2026-10-17): granted on the same footprint as
--          PERSON_MANAGE / MEMBERSHIP_MANAGE (every org-scoped admin role
--          down to PATHA_CHAKRA/KENDRA_MAHILA_SANGHA manages its own
--          register, admin-scope bounded) rather than GOVERNANCE_MANAGE's
--          ADMIN+KENDRA(+SAKHA exception) footprint — correspondence
--          registration is routine per-org administration, not a
--          structural/governance action. CORRESPONDENCE_VIEW also granted
--          to AUDITOR and REPORT_VIEWER (mirrors MEMBERSHIP_VIEW).
-- Version: 1.4 — GOVERNANCE_MANAGE also granted to NSS_ERP_SAKHA_ADMIN
--          (owner-confirmed 2026-10-08). That role is also held by the
--          Sakha's own President / Secretary / Treasurer-Cashier, who must
--          run their own Sakha's bodies. The grant carries NO Kendra reach:
--          it stays scope-bounded, and NSS-wide bodies (organization_pk IS
--          NULL) remain refused by _require_scope_for_org_or_nss_wide() —
--          view-only for this role — except for nominating/withdrawing the
--          Sakha's own Advisory Board representative.
-- Version: 1.3 — added GOVERNANCE_VIEW / GOVERNANCE_MANAGE (Tier 6,
--          2026-10-06): GOVERNANCE_MANAGE mirrored the ORGANIZATION_MANAGE
--          footprint (ADMIN + KENDRA only — body/election creation is a
--          structural action); GOVERNANCE_VIEW mirrors ORGANIZATION_VIEW
--          (all org-scoped admins + AUDITOR).
-- Version: 1.2 — added FOUNDATION_CALENDAR_MANAGE for NSS_ERP_ADMIN only
--          (SOL-ARCH-013 OPEN-FC-03, 2026-10-01); v1.1 added
--          NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN (12 rows, same
--          set as SAKHA/ZILLA/ANCHALIKA/PATHA_CHAKRA)
-- Authority: SOL-ARCH-011 §4, SOL-ADMIN-004 §10,
--            Tier 5 design decisions (2026-09-15), SOL-ARCH-013
--
-- DEPENDS ON: 01_permission_master.sql (seed),
--             02_role_master.sql (seed)
--
-- Matrix: 25 permissions x 9 roles (FOUNDATION_CALENDAR_MANAGE granted to
-- NSS_ERP_ADMIN only; GOVERNANCE_MANAGE to NSS_ERP_ADMIN /
-- NSS_ERP_KENDRA_ADMIN / NSS_ERP_SAKHA_ADMIN; CORRESPONDENCE_MANAGE to
-- every org-scoped admin role, same footprint as MEMBERSHIP_MANAGE).
-- Idempotent: ON CONFLICT ... DO NOTHING (mapping is
-- immutable once created; deactivate via is_active).
-- =====================================================

-- Helper: use a CTE to look up PKs by code, then insert
-- all mappings in a single statement.

WITH
roles AS (
    SELECT role_master_pk, role_code
    FROM nss.role_master
    WHERE is_active = TRUE
),
perms AS (
    SELECT permission_master_pk, permission_code
    FROM nss.permission_master
    WHERE is_active = TRUE
),
mappings (role_code, permission_code) AS (
    VALUES
    -- ── NSS_ERP_ADMIN (21 permissions — full access, including
    --    FOUNDATION_CALENDAR_MANAGE which NO OTHER ROLE receives —
    --    SOL-ARCH-013 OPEN-FC-03) ──────────────────────────────
    ('NSS_ERP_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_ADMIN', 'FOUNDATION_MANAGE'),
    ('NSS_ERP_ADMIN', 'FOUNDATION_CALENDAR_MANAGE'),
    ('NSS_ERP_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_ADMIN', 'ORGANIZATION_MANAGE'),
    ('NSS_ERP_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_ADMIN', 'PERSON_VIEW_SENSITIVE'),
    ('NSS_ERP_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_ADMIN', 'ADMIN_USER_VIEW'),
    ('NSS_ERP_ADMIN', 'ADMIN_USER_MANAGE'),
    ('NSS_ERP_ADMIN', 'ADMIN_ROLE_MANAGE'),
    ('NSS_ERP_ADMIN', 'ADMIN_SCOPE_MANAGE'),
    ('NSS_ERP_ADMIN', 'ADMIN_PERMISSION_VIEW'),
    ('NSS_ERP_ADMIN', 'AUDIT_VIEW'),
    ('NSS_ERP_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_ADMIN', 'GOVERNANCE_MANAGE'),
    ('NSS_ERP_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_KENDRA_ADMIN (20 — identical to ADMIN except
    --    FOUNDATION_CALENDAR_MANAGE, which ADMIN alone holds) ─
    ('NSS_ERP_KENDRA_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'FOUNDATION_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'ORGANIZATION_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'PERSON_VIEW_SENSITIVE'),
    ('NSS_ERP_KENDRA_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ADMIN_USER_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'ADMIN_USER_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ADMIN_ROLE_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ADMIN_SCOPE_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ADMIN_PERMISSION_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'AUDIT_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'GOVERNANCE_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_ANCHALIKA_ADMIN (12 permissions) ────────
    ('NSS_ERP_ANCHALIKA_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_ZILLA_ADMIN (12 permissions — same as ANCHALIKA)
    ('NSS_ERP_ZILLA_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_ZILLA_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_ZILLA_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_ZILLA_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_ZILLA_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_SAKHA_ADMIN (13 permissions)
    -- GOVERNANCE_MANAGE added 2026-10-08 (owner-confirmed): this role is also
    -- held by the Sakha's own President / Secretary / Treasurer-Cashier, who
    -- must be able to run their own Sakha's bodies. It grants NO Kendra reach —
    -- the permission is scope-bounded and _require_scope_for_org_or_nss_wide()
    -- still refuses every NSS-wide body (organization_pk IS NULL: Kendra
    -- Governing Body, Advisory Board, Kendra Mahila Parichalana Mandali), which
    -- remain view-only for this role. The one deliberate exception is
    -- nominating / withdrawing this Sakha's OWN Advisory Board representative
    -- (_require_nominating_sakha_scope in api/routers/governance.py).
    ('NSS_ERP_SAKHA_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_SAKHA_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_SAKHA_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_SAKHA_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_SAKHA_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'GOVERNANCE_MANAGE'),
    ('NSS_ERP_SAKHA_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_PATHA_CHAKRA_ADMIN (12 permissions — same as SAKHA)
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN (12 — same as SAKHA)
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'PERSON_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'PERSON_MANAGE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'FAMILY_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'FAMILY_MANAGE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'MEMBERSHIP_MANAGE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'MEMBERSHIP_APPROVE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'REPORT_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'CORRESPONDENCE_MANAGE'),

    -- ── NSS_ERP_AUDITOR (8 permissions — read + sensitive + audit)
    ('NSS_ERP_AUDITOR', 'BOOTSTRAP_VIEW'),
    ('NSS_ERP_AUDITOR', 'FOUNDATION_VIEW'),
    ('NSS_ERP_AUDITOR', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_AUDITOR', 'PERSON_VIEW'),
    ('NSS_ERP_AUDITOR', 'PERSON_VIEW_SENSITIVE'),
    ('NSS_ERP_AUDITOR', 'FAMILY_VIEW'),
    ('NSS_ERP_AUDITOR', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_AUDITOR', 'ADMIN_USER_VIEW'),
    ('NSS_ERP_AUDITOR', 'ADMIN_PERMISSION_VIEW'),
    ('NSS_ERP_AUDITOR', 'AUDIT_VIEW'),
    ('NSS_ERP_AUDITOR', 'REPORT_VIEW'),
    ('NSS_ERP_AUDITOR', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_AUDITOR', 'CORRESPONDENCE_VIEW'),

    -- ── NSS_ERP_REPORT_VIEWER (4 permissions — minimal read)
    ('NSS_ERP_REPORT_VIEWER', 'FOUNDATION_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'PERSON_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'FAMILY_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'REPORT_VIEW')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN roles r ON r.role_code = m.role_code
JOIN perms p ON p.permission_code = m.permission_code
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
