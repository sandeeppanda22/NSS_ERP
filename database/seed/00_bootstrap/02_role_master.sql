-- =====================================================
-- NSS ERP
-- Module: Bootstrap RBAC
-- File: 02_role_master.sql (seed)
-- Seed: 8 frozen roles (SOL-ADMIN-004 §8.7)
-- Authority: SOL-ARCH-011 §4, SOL-ADMIN-004 §8.7
-- =====================================================

INSERT INTO role_master
    (role_code, role_name, role_class, scope_level, description, display_order)
VALUES
    ('NSS_ADMIN',
     'NSS Administrator',
     'SYSTEM',
     NULL,
     'System-wide ERP administrator with all application permissions',
     1),

    ('AUDITOR',
     'Auditor',
     'SYSTEM',
     NULL,
     'System-wide read-only auditor for compliance and review',
     2),

    ('REPORT_VIEWER',
     'Report Viewer',
     'SYSTEM',
     NULL,
     'System-wide read-only access to reports and dashboards',
     3),

    ('KENDRA_ADMIN',
     'Kendra Administrator',
     'ORGANIZATIONAL',
     'KENDRA',
     'Administrative authority scoped to a specific Kendra',
     4),

    ('ANCHALIKA_ADMIN',
     'Anchalika Administrator',
     'ORGANIZATIONAL',
     'ANCHALIKA',
     'Administrative authority scoped to a specific Anchalika',
     5),

    ('ZILLA_ADMIN',
     'Zilla Administrator',
     'ORGANIZATIONAL',
     'ZILLA',
     'Administrative authority scoped to a specific Zilla',
     6),

    ('SAKHA_ADMIN',
     'Sakha Administrator',
     'ORGANIZATIONAL',
     'SAKHA',
     'Administrative authority scoped to a specific Sakha',
     7),

    ('PATHA_CHAKRA_ADMIN',
     'Patha Chakra Administrator',
     'ORGANIZATIONAL',
     'PATHA_CHAKRA',
     'Administrative authority scoped to a specific Patha Chakra',
     8);
