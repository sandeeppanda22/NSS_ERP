-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 03_role_permission.sql (seed)
-- Seed: Role-to-permission mappings (~130 rows)
-- Version: 1.8 — owner decisions 2026-10-30 (existing databases receive the
--          same rows through the idempotent 04_role_permission_mahila_advisory_board_patch.sql,
--          because this file is existence-gated and never re-runs):
--          (a) NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN is "similar to
--          NSS_ERP_KENDRA_ADMIN but only related to Mahila Sangha": Kendra's
--          operational set = its 26 permissions minus the 8 system/admin ones
--          (ADMIN_PERMISSION_VIEW, ADMIN_ROLE_MANAGE, ADMIN_SCOPE_MANAGE,
--          ADMIN_USER_MANAGE, ADMIN_USER_VIEW, AUDIT_VIEW, FOUNDATION_MANAGE,
--          PERSON_VIEW_SENSITIVE) = 18; i.e. the old 15 plus ORGANIZATION_MANAGE,
--          GOVERNANCE_MANAGE and ATTENDANCE_MANAGE. Reach is NOT global: the
--          role's scope resolves (rbac_service.actor_scope_org_pks) to every
--          MAHILA_SANGHA organization + subtree, so each *_MANAGE grant is
--          bounded to Mahila Sanghas server-side.
--          (b) NSS_ERP_ADVISORY_BOARD_ADMIN (previously zero rows) gets
--          GOVERNANCE_VIEW, GOVERNANCE_MANAGE and MEMBERSHIP_VIEW (3 rows).
--          GOVERNANCE_MANAGE is confined server-side to ADVISORY_BOARD-type
--          bodies (seat assignments, acting cover, removal requests) by
--          governance.py _require_scope_for_org_or_nss_wide(body_type_code=);
--          MEMBERSHIP_VIEW is the member search used to seat officers.
--          (c) The Advisory Board also became an organization type with its
--          own correspondence register (same day): NSS_ERP_ADVISORY_BOARD_ADMIN
--          additionally gets CORRESPONDENCE_VIEW, CORRESPONDENCE_MANAGE,
--          ORGANIZATION_VIEW and FOUNDATION_VIEW (3 -> 7 rows), all bounded to
--          the Advisory Board organization by admin scope.
-- Version: 1.7 — added ATTENDANCE_VIEW / ATTENDANCE_MANAGE (Tier 6,
--          2026-10-27) and the new NSS_ERP_ATTENDANCE_MARKER role. See the
--          inline block near the end of the mappings list for the exact
--          footprint and rationale.
-- Version: 1.6 — added GEO_ENTRY_APPROVE to NSS_ERP_SAKHA_ADMIN only
--          (2026-10-21, owner-confirmed): lets a Sakha admin approve/
--          correct geography proposals scoped to their own Sakha without
--          the broad FOUNDATION_MANAGE (also gates global NSS/Kendra-only
--          master-data editing). NOT granted to NSS_ERP_ADMIN /
--          NSS_ERP_KENDRA_ADMIN (they already satisfy geo_approval.py's
--          require_any_permission via FOUNDATION_MANAGE) nor to any other
--          org-scoped admin role (Anchalika/Zilla/Patha Chakra/etc.).
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
-- Matrix: 28 permissions x 12 roles (FOUNDATION_CALENDAR_MANAGE granted to
-- NSS_ERP_ADMIN only; GOVERNANCE_MANAGE to NSS_ERP_ADMIN /
-- NSS_ERP_KENDRA_ADMIN / NSS_ERP_SAKHA_ADMIN / NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN
-- / NSS_ERP_ADVISORY_BOARD_ADMIN (the last confined to Advisory Board bodies);
-- CORRESPONDENCE_MANAGE to every org-scoped admin role, same footprint as
-- MEMBERSHIP_MANAGE; GEO_ENTRY_APPROVE to NSS_ERP_SAKHA_ADMIN only;
-- ORGANIZATION_MANAGE to ADMIN / KENDRA_ADMIN / KENDRA_MAHILA_SANGHA_ADMIN).
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

    -- ── NSS_ERP_SAKHA_ADMIN (16 permissions)
    -- GEO_ENTRY_APPROVE added 2026-10-21 (owner-confirmed): lets this role
    -- approve/correct geography proposals scoped to its own Sakha without
    -- the broad FOUNDATION_MANAGE (also gates global NSS/Kendra-only
    -- master-data editing).
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
    ('NSS_ERP_SAKHA_ADMIN', 'GEO_ENTRY_APPROVE'),

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

    -- ── NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN (18 — Kendra's operational set
    --    minus the 8 ADMIN_*/AUDIT_VIEW/FOUNDATION_MANAGE/PERSON_VIEW_SENSITIVE
    --    system permissions; owner decision 2026-10-30. Reach = every
    --    MAHILA_SANGHA org + subtree only. The 15 rows below were seeded
    --    earlier; ORGANIZATION_MANAGE / GOVERNANCE_MANAGE / ATTENDANCE_MANAGE
    --    are the 2026-10-30 additions.) ──
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
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ORGANIZATION_MANAGE'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'GOVERNANCE_MANAGE'),

    -- ── NSS_ERP_ADVISORY_BOARD_ADMIN (8 — owner decisions 2026-10-30) ──
    -- Least-privilege footprint. Governance BODY side (3): GOVERNANCE_MANAGE is
    -- confined server-side to ADVISORY_BOARD-type bodies' seat assignments,
    -- acting cover and forced-removal requests; the Sakha-nominated MEMBER
    -- seat stays with the nominating Sakha. MEMBERSHIP_VIEW is the member
    -- search used to seat officers.
    -- Organization/correspondence side (4) — "Advisory Board should be an org
    -- type / needs a correspondence register": the ADVISORY_BOARD scope level
    -- now resolves to the singleton ADVISORY_BOARD organization
    -- (rbac_service.NULL_ORG_SCOPE_ORG_TYPE), so these are bounded to that
    -- organization's own register by admin scope.
    --   CORRESPONDENCE_VIEW / CORRESPONDENCE_MANAGE — read/file/transition its
    --     own register; ORGANIZATION_VIEW — the org list the register switcher
    --     and recipient picker are built from; FOUNDATION_VIEW — the
    --     CORRESPONDENCE_MEDIUM / ORGANIZATION_TYPE catalogues the create form
    --     needs (Medium is mandatory).
    -- PERSON_VIEW (owner decision, 2026-10-30, the 8th): person search for the
    -- correspondence person pickers / seating officers. NOT scope-narrowed by
    -- the endpoints themselves (see docs: PERSON_VIEW exposure note).
    -- Deliberately NOT granted: BOOTSTRAP_VIEW, REPORT_VIEW, ORGANIZATION_MANAGE, every ADMIN_* / AUDIT_VIEW /
    -- FOUNDATION_MANAGE / PERSON_VIEW_SENSITIVE, and the other org-scoped *_MANAGE.
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'GOVERNANCE_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'GOVERNANCE_MANAGE'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'MEMBERSHIP_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'CORRESPONDENCE_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'CORRESPONDENCE_MANAGE'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'ORGANIZATION_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'FOUNDATION_VIEW'),
    ('NSS_ERP_ADVISORY_BOARD_ADMIN', 'PERSON_VIEW'),

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
    ('NSS_ERP_REPORT_VIEWER', 'REPORT_VIEW'),

    -- ── Attendance (Tier 6, 2026-10-27, owner-confirmed) ──
    -- ATTENDANCE_MANAGE (mark PRESENT/ABSENT/EXCUSED_ABSENCE, create puja
    -- events) goes ONLY to roles that actually run a Sakha's own puja:
    -- ADMIN/KENDRA (global), SAKHA_ADMIN, KENDRA_MAHILA_SANGHA_ADMIN (added
-- 2026-10-30 as part of Kendra's operational set; its scope covers only
-- MAHILA_SANGHA orgs, so in practice it cannot mark a Sakha's puja), and the new per-Sakha
    -- ATTENDANCE_MARKER (owner: "sakha admin, designated members by
    -- sakha (multiple members)"). ATTENDANCE_VIEW is broader — every
    -- org-scoped admin role down the hierarchy plus AUDITOR/REPORT_VIEWER,
    -- mirroring MEMBERSHIP_VIEW/GOVERNANCE_VIEW's footprint, for roll-up
    -- reporting (Anchalika/Zilla/Patha Chakra/Kendra Mahila Sangha see
    -- their subtree's attendance but do not mark it — Weekly Sangha Puja
    -- is Sakha-level only, ATT-004). Attendance Review authority
    -- (close/defer/escalate/approve excused absence) is NOT a permission
    -- at all — it is checked against the real SAKHA_GOVERNING_BODY
    -- Secretary/President seat in api/routers/attendance.py, per the
    -- frozen Review Authority Matrix naming actual offices.
    ('NSS_ERP_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_ADMIN', 'ATTENDANCE_MANAGE'),
    ('NSS_ERP_KENDRA_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_KENDRA_ADMIN', 'ATTENDANCE_MANAGE'),
    ('NSS_ERP_ANCHALIKA_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_ZILLA_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_SAKHA_ADMIN', 'ATTENDANCE_MANAGE'),
    ('NSS_ERP_PATHA_CHAKRA_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'ATTENDANCE_MANAGE'),
    ('NSS_ERP_AUDITOR', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_REPORT_VIEWER', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_ATTENDANCE_MARKER', 'ATTENDANCE_VIEW'),
    ('NSS_ERP_ATTENDANCE_MARKER', 'ATTENDANCE_MANAGE')
)
INSERT INTO nss.role_permission (role_master_pk, permission_master_pk)
SELECT r.role_master_pk, p.permission_master_pk
FROM mappings m
JOIN roles r ON r.role_code = m.role_code
JOIN perms p ON p.permission_code = m.permission_code
ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING;
