-- =====================================================
-- NSS ERP
-- Module: Organization
-- Seed File: 02_organization_status_master.sql
-- Version: 1.0
-- Authority: SOL-ORG-005 §15–§16, SOL-ORG-003
-- Owner: NSS_ADMIN
-- Note: 6 lifecycle statuses per GOV-002
-- =====================================================

INSERT INTO organization_status_master
    (organization_status_code, organization_status_name, description, sort_order)
VALUES
    ('PROPOSED',  'Proposed',
     'Organization has been proposed but not yet approved',         1),

    ('APPROVED',  'Approved',
     'Organization approved by governance, pending activation',     2),

    ('ACTIVE',    'Active',
     'Organization is currently operational',                       3),

    ('INACTIVE',  'Inactive',
     'Organization is temporarily non-operational',                 4),

    ('SUSPENDED', 'Suspended',
     'Organization activities suspended by governance decision',    5),

    ('ARCHIVED',  'Archived',
     'Organization is permanently closed, retained for history',    6);
