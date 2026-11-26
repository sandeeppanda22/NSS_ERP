-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 27_finance_year_audit.sql
-- Table: nss.finance_year_audit
-- Depth: 3 (depends on financial_year, organization, correspondence)
-- Version: 1.0
-- Authority: NSS Bye-Law Section G (REF-003-G): "The Accounts of the Kendra Sangha shall be audited every year by appointing a
--            qualified Auditor by the Governing Body and the Audit Report shall be placed first before the Governing Body and then
--            in the combined meeting of the Governing Body and the Advisory Board for their approval only after which the same will
--            be placed before the General Body of the Kendra Sangha by the Secretary."; owner request 2026-11-26.
-- Owner: NSS_ERP_ADMIN
-- Note: ONE audit per Kendra organization per financial year (the Kendra only: no rule is invented for other levels, FIN-BR-044).
--       Five recorded facts, never skipped or reordered:
--         APPOINTED (the Governing Body appointed the Auditor: name, optional firm, date, resolution reference)
--         -> REPORT_RECEIVED (the Audit Report: reference, date, optional https link - the app has no file upload)
--         -> PLACED_BEFORE_GB (placed before the Governing Body: date + resolution / minute reference; a numbered letter to the
--            Advisory Board is filed in Correspondence for the combined meeting)
--         -> APPROVED (the combined meeting of the Governing Body and the Advisory Board approved it: date + reference)
--         -> PLACED_BEFORE_GENERAL_BODY (the Secretary placed it before the General Body: date + reference; final).
--       The financial year's status does not gate any step (owner 2026-11-26: the audit may run while the year is open, closing
--       or closed). Dates keep that order and are never in the future (also checked in the API).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_year_audit
(
    finance_year_audit_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    financial_year_pk UUID NOT NULL,

    organization_pk UUID NOT NULL,

    status VARCHAR(30) NOT NULL
        DEFAULT 'APPOINTED',

    notes TEXT NULL,

    -- 1. The Governing Body's appointment of a qualified Auditor.
    auditor_name VARCHAR(200) NOT NULL,

    auditor_firm VARCHAR(200) NULL,

    appointed_on DATE NOT NULL,

    appointment_reference VARCHAR(100) NOT NULL,

    -- 2. The Audit Report.
    report_reference VARCHAR(100) NULL,

    report_date DATE NULL,

    report_link VARCHAR(500) NULL,

    -- 3. Placed before the Governing Body; the letter filed to the Advisory Board for the combined meeting.
    gb_placed_on DATE NULL,

    gb_reference VARCHAR(100) NULL,

    advisory_correspondence_pk UUID NULL,

    -- 4. The combined meeting of the Governing Body and the Advisory Board approved it.
    approved_on DATE NULL,

    approval_reference VARCHAR(100) NULL,

    -- 5. The Secretary placed it before the General Body.
    general_body_on DATE NULL,

    general_body_reference VARCHAR(100) NULL,

    -- ── Lifecycle / Audit ───────────────────────────────

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_finance_year_audit_year
        FOREIGN KEY (financial_year_pk)
        REFERENCES nss.financial_year (financial_year_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_year_audit_organization
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_finance_year_audit_letter
        FOREIGN KEY (advisory_correspondence_pk)
        REFERENCES nss.correspondence (correspondence_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_finance_year_audit_status
        CHECK (status IN ('APPOINTED', 'REPORT_RECEIVED', 'PLACED_BEFORE_GB', 'APPROVED', 'PLACED_BEFORE_GENERAL_BODY')),

    CONSTRAINT chk_finance_year_audit_appointment
        CHECK (BTRIM(auditor_name) <> '' AND BTRIM(appointment_reference) <> ''),

    -- Each step's facts are present from that step on, and absent before it.
    CONSTRAINT chk_finance_year_audit_report
        CHECK (
            (status <> 'APPOINTED'
             AND report_reference IS NOT NULL AND BTRIM(report_reference) <> '' AND report_date IS NOT NULL)
            OR
            (status = 'APPOINTED'
             AND report_reference IS NULL AND report_date IS NULL AND report_link IS NULL)
        ),

    CONSTRAINT chk_finance_year_audit_gb
        CHECK (
            (status IN ('PLACED_BEFORE_GB', 'APPROVED', 'PLACED_BEFORE_GENERAL_BODY')
             AND gb_placed_on IS NOT NULL AND gb_reference IS NOT NULL AND BTRIM(gb_reference) <> '')
            OR
            (status IN ('APPOINTED', 'REPORT_RECEIVED')
             AND gb_placed_on IS NULL AND gb_reference IS NULL AND advisory_correspondence_pk IS NULL)
        ),

    CONSTRAINT chk_finance_year_audit_approval
        CHECK (
            (status IN ('APPROVED', 'PLACED_BEFORE_GENERAL_BODY')
             AND approved_on IS NOT NULL AND approval_reference IS NOT NULL AND BTRIM(approval_reference) <> '')
            OR
            (status NOT IN ('APPROVED', 'PLACED_BEFORE_GENERAL_BODY')
             AND approved_on IS NULL AND approval_reference IS NULL)
        ),

    CONSTRAINT chk_finance_year_audit_general_body
        CHECK (
            (status = 'PLACED_BEFORE_GENERAL_BODY'
             AND general_body_on IS NOT NULL AND general_body_reference IS NOT NULL AND BTRIM(general_body_reference) <> '')
            OR
            (status <> 'PLACED_BEFORE_GENERAL_BODY' AND general_body_on IS NULL AND general_body_reference IS NULL)
        ),

    -- The order of the facts: appointment, report, Governing Body, combined meeting, General Body.
    CONSTRAINT chk_finance_year_audit_order
        CHECK (
            (report_date IS NULL OR report_date >= appointed_on)
            AND (gb_placed_on IS NULL OR report_date IS NULL OR gb_placed_on >= report_date)
            AND (approved_on IS NULL OR gb_placed_on IS NULL OR approved_on >= gb_placed_on)
            AND (general_body_on IS NULL OR approved_on IS NULL OR general_body_on >= approved_on)
        ),

    CONSTRAINT chk_finance_year_audit_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_year_audit_year_org
    ON nss.finance_year_audit (financial_year_pk, organization_pk) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_year_audit_organization
    ON nss.finance_year_audit (organization_pk);
