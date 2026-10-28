-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 02_role_master.sql (seed)
-- Seed: 11 frozen roles (SOL-ADMIN-004 §8.7)
-- Version: 1.4 — added NSS_ERP_ATTENDANCE_MARKER (Tier 6 Attendance,
--          owner-confirmed 2026-10-27): a Sakha may designate MULTIPLE
--          members as attendance markers (role_class ORGANIZATIONAL, so —
--          like NSS_ERP_SAKHA_ADMIN — it is assignable more than once per
--          Sakha, unlike a SYSTEM role). Holds ATTENDANCE_VIEW/MANAGE for
--          marking weekly Sangha Puja attendance only; it does NOT confer
--          Attendance Review authority (close/defer/escalate/approve
--          excused absence) — that is gated separately on the real
--          SAKHA_GOVERNING_BODY Secretary/President governance seat
--          (api/routers/attendance.py's own scope check), not on any RBAC
--          role, per the frozen Attendance Review authority matrix naming
--          actual offices, not admin roles. scope_level SAKHA already
--          existed in chk_role_master_scope_level — no DDL widening
--          needed.
-- Version: 1.3 — added NSS_ERP_ADVISORY_BOARD_ADMIN (Tier 6 governance
--          auto-provisioning, owner-confirmed 2026-10-08): held by the
--          Advisory Board President/Secretary (auto-granted from their
--          governance position) or a third person manually appointed by
--          NSS_ERP_ADMIN. New scope level ADVISORY_BOARD (organization_pk
--          NULL, like NSS-WIDE, but a strictly narrower RBAC footprint).
-- Version: 1.2 — ON CONFLICT DO NOTHING, not DO UPDATE (2026-10-05): a
--          re-run must never overwrite a role's live-edited fields.
--          Insert-if-missing only.
-- Authority: SOL-ARCH-011 §4, SOL-ADMIN-004 §8.7
--
-- NAMING CONVENTION:
--   NSS_ERP_*  = Application RBAC roles (this file)
--   nss_db_*   = PostgreSQL infrastructure roles (00_create_database.sql)
-- =====================================================

INSERT INTO nss.role_master
    (role_code, role_name, role_class, scope_level, description, display_order)
VALUES
    ('NSS_ERP_ADMIN',
     'NSS ERP Administrator',
     'SYSTEM',
     'NSS-WIDE',
     'System-wide ERP administrator with all application permissions',
     1),

    ('NSS_ERP_AUDITOR',
     'Auditor',
     'SYSTEM',
     'NSS-WIDE',
     'System-wide read-only auditor for compliance and review',
     2),

    ('NSS_ERP_REPORT_VIEWER',
     'Report Viewer',
     'SYSTEM',
     'NSS-WIDE',
     'System-wide read-only access to reports and dashboards',
     3),

    ('NSS_ERP_KENDRA_ADMIN',
     'Kendra Administrator',
     'ORGANIZATIONAL',
     'KENDRA',
     'Administrative authority scoped to a specific Kendra',
     4),

    ('NSS_ERP_ANCHALIKA_ADMIN',
     'Anchalika Administrator',
     'ORGANIZATIONAL',
     'ANCHALIKA',
     'Administrative authority scoped to a specific Anchalika',
     5),

    ('NSS_ERP_ZILLA_ADMIN',
     'Zilla Administrator',
     'ORGANIZATIONAL',
     'ZILLA',
     'Administrative authority scoped to a specific Zilla',
     6),

    ('NSS_ERP_SAKHA_ADMIN',
     'Sakha Administrator',
     'ORGANIZATIONAL',
     'SAKHA',
     'Administrative authority scoped to a specific Sakha',
     7),

    ('NSS_ERP_PATHA_CHAKRA_ADMIN',
     'Patha Chakra Administrator',
     'ORGANIZATIONAL',
     'PATHA_CHAKRA',
     'Administrative authority scoped to a specific Patha Chakra',
     8),

    ('NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN',
     'Kendra Mahila Sangha Administrator',
     'ORGANIZATIONAL',
     'KENDRA_MAHILA_SANGHA',
     'Administrative authority scoped to the Kendra Mahila Sangha',
     9),

    ('NSS_ERP_ADVISORY_BOARD_ADMIN',
     'Advisory Board Administrator',
     'ORGANIZATIONAL',
     'ADVISORY_BOARD',
     'Administrative authority scoped to the Advisory Board. Held by the AB President or Secretary (auto-granted from their governance position) or a third person manually appointed by NSS_ERP_ADMIN.',
     10),

    ('NSS_ERP_ATTENDANCE_MARKER',
     'Attendance Marker',
     'ORGANIZATIONAL',
     'SAKHA',
     'A member designated by their Sakha to record Weekly Sangha Puja attendance. A Sakha may designate multiple markers. Does not confer Attendance Review authority — that requires the actual Secretary/President governance seat.',
     11)
ON CONFLICT (role_code) DO NOTHING;
