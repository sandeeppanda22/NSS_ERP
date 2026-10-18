-- =====================================================
-- NSS ERP
-- Module: Foundation
-- Seed File: 01_master_category.sql
-- Version: 1.3 — add CORRESPONDENCE_MEDIUM / CORRESPONDENCE_STATUS (Tier 6,
--          2026-10-17): correspondence.medium_master_data_pk / status_master_data_pk
--          reference these categories (01_correspondence.sql); their value
--          lists were already ERP-FROZEN in
--          docs/03_Solution/modules/administration/08_correspondence_register_business_rules.md
--          §6.1 and §10.1 but had not yet been seeded — filling a seed gap,
--          not a new business-rule decision. 16 categories total.
-- Version: 1.2 — ON CONFLICT DO NOTHING, not DO UPDATE (2026-10-05): a
--          re-run must never overwrite a category row an admin has edited.
--          Insert-if-missing only.
-- Authority: SOL-FND-004 §6.4, §29
-- Owner: NSS_ERP_ADMIN
-- =====================================================

INSERT INTO nss.master_category
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
    'STATUS',
    'Status',
    'Unified lifecycle status for all ERP entities (organizations, memberships, governance, etc.)',
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
),
(
    'ORGANIZATION_TYPE',
    'Organization Type',
    'Types of organizations in the NSS hierarchy',
    12
),
(
    'BLOOD_GROUP',
    'Blood Group',
    'Blood group classification for persons',
    13
),
(
    'CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE',
    'Correspondence-Finance Relationship Type',
    'How a correspondence record relates to a referenced financial transaction (SOL-ADMIN-009 §6.5, owner-confirmed 2026-10-17)',
    14
),
(
    'CORRESPONDENCE_MEDIUM',
    'Correspondence Medium',
    'Channel through which a correspondence was transmitted (SOL-ADMIN-009 §4, business rules §10.1)',
    15
),
(
    'CORRESPONDENCE_STATUS',
    'Correspondence Status',
    'Lifecycle state of a correspondence register entry (SOL-ADMIN-009 §4, business rules §6.1)',
    16
)
ON CONFLICT (category_code) DO NOTHING;
