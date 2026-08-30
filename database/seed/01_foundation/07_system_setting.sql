-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 07_system_setting.sql
-- Version: 1.0
-- Authority: SOL-FND-004 §10
-- Owner: NSS_ADMIN
-- Note: Initial system settings. Values are
--       illustrative defaults; actual production
--       values configured during deployment.
-- =====================================================

INSERT INTO system_setting
(
    setting_key,
    setting_value,
    description,
    data_type
)
VALUES
(
    'CURRENT_MEMBERSHIP_YEAR',
    '2026-2027',
    'Active membership year (financial year format)',
    'STRING'
),
(
    'DEFAULT_COUNTRY',
    'IN',
    'Default country code for new records',
    'STRING'
),
(
    'PASSWORD_EXPIRY_DAYS',
    '90',
    'Number of days before password expiry',
    'INTEGER'
),
(
    'MAX_LOGIN_ATTEMPTS',
    '5',
    'Maximum consecutive failed login attempts before lockout',
    'INTEGER'
),
(
    'PRESIDENT_APPROVAL_REQUIRED',
    'true',
    'Whether President approval is required for membership actions',
    'BOOLEAN'
);
