-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 13_darshak_attendance_registration.sql
-- Table: nss.darshak_attendance_registration
-- Depth: 3 (depends on sangha_sevi, organization)
-- Version: 1.1
-- Authority: SOL-MEM-006 — Darshak Attendance Registration (DAR-009 added)
-- Owner: NSS_ERP_ADMIN
-- Note: Stores cross-Sakha Darshak attendance with
--       three-step approval workflow and local number
--       assigned by the attending Sakha.
--       Separate from membership_sakha_affiliation
--       (which tracks home-Sakha membership affiliation).
--       Darshak local number is persistent per person
--       per Sakha — never reassigned to another person.
--       request_source records whether the member or an
--       admin (on the member's behalf) raised the request;
--       it is record-keeping only and never skips a step of
--       the three-step approval (DAR-009).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.darshak_attendance_registration
(
    -- ── Identity ────────────────────────────────────────

    darshak_attendance_registration_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Core References ─────────────────────────────────

    -- The member attending as Darshak
    sangha_sevi_pk UUID NOT NULL,

    -- Member's home Sakha (where Parichaya Patra resides)
    home_organization_pk UUID NOT NULL,

    -- The Sakha being attended as Darshak
    attending_organization_pk UUID NOT NULL,

    -- ── Request Initiation (DAR-009) ────────────────────

    -- Who raised the request: the member himself, or the admin
    -- acting on his behalf.
    initiated_by_sangha_sevi_pk UUID NOT NULL,

    -- Record-keeping only — does not affect the three-step approval.
    request_source VARCHAR(20) NOT NULL,

    -- ── Darshak Local Number ────────────────────────────

    -- Simple number assigned by attending Sakha on approval.
    -- NULL while approval is pending.
    -- Persistent per person per Sakha — never reassigned.
    darshak_local_number VARCHAR(30) NULL,

    -- ── Approval Workflow ───────────────────────────────

    -- Three-step approval: Home Sakha → Parichalak → Target Sakha
    approval_status VARCHAR(30) NOT NULL,

    -- Step 1: Home Sakha approval
    approved_by_home_sakha_sevi_pk UUID NULL,
    approved_by_home_sakha_at TIMESTAMPTZ NULL,

    -- Step 2: Parichalak approval
    approved_by_parichalak_sevi_pk UUID NULL,
    approved_by_parichalak_at TIMESTAMPTZ NULL,

    -- Step 3: Target Sakha President approval
    approved_by_target_sakha_sevi_pk UUID NULL,
    approved_by_target_sakha_at TIMESTAMPTZ NULL,

    -- Reason for rejection (if REJECTED)
    rejection_reason TEXT NULL,

    -- ── Effective Period ────────────────────────────────

    -- Set when APPROVED; NULL while pending
    effective_from DATE NULL,

    -- NULL = currently active
    effective_to DATE NULL,

    -- ACTIVE or ARCHIVED
    registration_status VARCHAR(20) NOT NULL
        DEFAULT 'ACTIVE',

    remarks TEXT NULL,

    -- ── Lifecycle ───────────────────────────────────────

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT fk_dar_att_reg_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_dar_att_reg_home_org
        FOREIGN KEY (home_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_dar_att_reg_attending_org
        FOREIGN KEY (attending_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_dar_att_reg_initiated_by
        FOREIGN KEY (initiated_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    -- Request source controlled values (DAR-009)
    CONSTRAINT chk_dar_att_reg_request_source
        CHECK (request_source IN ('MEMBER_SELF', 'ADMIN_AUTOMATIC_ENTRY')),

    -- Cannot be Darshak at own home Sakha (DAR-006)
    CONSTRAINT chk_dar_att_reg_different_sakha
        CHECK (home_organization_pk != attending_organization_pk),

    -- Approval status controlled values
    CONSTRAINT chk_dar_att_reg_approval_status
        CHECK (approval_status IN (
            'PENDING_HOME_SAKHA',
            'PENDING_PARICHALAK',
            'PENDING_TARGET_SAKHA',
            'APPROVED',
            'REJECTED',
            'REVOKED'
        )),

    -- Registration status controlled values
    CONSTRAINT chk_dar_att_reg_registration_status
        CHECK (registration_status IN ('ACTIVE', 'ARCHIVED')),

    -- Darshak local number required when APPROVED
    CONSTRAINT chk_dar_att_reg_number_on_approval
        CHECK (
            (approval_status = 'APPROVED' AND darshak_local_number IS NOT NULL)
            OR
            (approval_status != 'APPROVED')
        ),

    -- Effective dates consistency
    CONSTRAINT chk_dar_att_reg_effective_range
        CHECK (
            effective_to IS NULL
            OR effective_to >= effective_from
        ),

    -- Soft delete consistency
    CONSTRAINT chk_dar_att_reg_soft_delete
        CHECK (
            (is_active = TRUE)
            OR
            (is_active = FALSE)
        ),

    -- No two people share the same Darshak number at a Sakha
    CONSTRAINT uq_dar_att_reg_local_number
        UNIQUE (attending_organization_pk, darshak_local_number)
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_dar_att_reg_sevi
    ON nss.darshak_attendance_registration (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_dar_att_reg_home_org
    ON nss.darshak_attendance_registration (home_organization_pk);

CREATE INDEX IF NOT EXISTS idx_dar_att_reg_attending_org
    ON nss.darshak_attendance_registration (attending_organization_pk);

CREATE INDEX IF NOT EXISTS idx_dar_att_reg_initiated_by
    ON nss.darshak_attendance_registration (initiated_by_sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_dar_att_reg_approval_status
    ON nss.darshak_attendance_registration (approval_status);

CREATE INDEX IF NOT EXISTS idx_dar_att_reg_registration_status
    ON nss.darshak_attendance_registration (registration_status);

-- One active Darshak attendance per person at a time (DAR-002)
CREATE UNIQUE INDEX IF NOT EXISTS uq_dar_att_reg_active
    ON nss.darshak_attendance_registration (sangha_sevi_pk)
    WHERE registration_status = 'ACTIVE';
