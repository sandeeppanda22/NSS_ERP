-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 01_master_category.sql
-- Version: 1.0
-- Authority: SOL-FND-004 §6.4, §29
-- Owner: NSS_ADMIN
-- =====================================================

INSERT INTO master_category
(
    category_code,
    category_name,
    description,
    display_order
)
VALUES
(
    'GENDER',
    'Gender',
    'Gender classification for persons',
    1
),
(
    'RELATIONSHIP_TYPE',
    'Relationship Type',
    'Family relationship types',
    2
),
(
    'MEMBERSHIP_TYPE',
    'Membership Type',
    'Types of NSS membership',
    3
),
(
    'MEMBERSHIP_STATUS',
    'Membership Status',
    'Lifecycle status of membership',
    4
),
(
    'LOGIN_ROLE',
    'Login Role',
    'Application login role classification',
    5
),
(
    'STATUS_REASON',
    'Status Reason',
    'Reason codes for status changes',
    6
),
(
    'WORKFLOW_STATUS',
    'Workflow Status',
    'Generic workflow state values',
    7
),
(
    'DOCUMENT_TYPE',
    'Document Type',
    'Classification of stored documents',
    8
),
(
    'APPLICATION_TYPE',
    'Application Type',
    'Types of member applications',
    9
),
(
    'MARITAL_STATUS',
    'Marital Status',
    'Marital status for persons',
    10
),
(
    'ADDRESS_TYPE',
    'Address Type',
    'Types of addresses',
    11
);
