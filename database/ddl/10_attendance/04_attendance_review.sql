-- =====================================================
-- NSS ERP
-- Module: Attendance (Tier 6)
-- File: 04_attendance_review.sql
-- Table: nss.attendance_review
-- Depth: 3 (depends on sangha_sevi, organization, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/attendance/
--            01_attendance_module_overview.md (§11-15),
--            04_attendance_business_rules.md (ATT-009/010/014-022),
--            05_attendance_table_design.md (§12-16),
--            06_attendance_review_workflow.md (FROZEN)
-- Owner: NSS_ERP_ADMIN
-- Note: assigned_to_role names the OPERATIONAL OFFICE responsible (the
--       frozen Review Authority Matrix speaks of Secretary/President/
--       Parichalak, not an admin_scope row) — api/routers/attendance.py
--       resolves the real office-holder at action time via
--       body_member_assignment on the Sakha's SAKHA_GOVERNING_BODY, the
--       same lookup used for the Member Directory's President/Secretary
--       badge. organization_pk is the Sakha this review belongs to
--       (ERD §3: ORGANIZATION relates_to ATTENDANCE_REVIEW) — captured at
--       trigger time from the member's home Sakha, so the review stays
--       addressed to the correct Sakha even if the member later
--       transfers. "One OPEN review per member" (implied by ATT-010's
--       trigger semantics) is enforced in the API, not a DB constraint —
--       review_status is master-data driven (FK, not a literal code), so
--       a partial unique index keyed to a specific status value can't be
--       expressed in pure DDL without hardcoding a seed-time PK.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.attendance_review
(
    -- ── Identity ────────────────────────────────────────

    review_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Core References ─────────────────────────────────

    sangha_sevi_pk UUID NOT NULL,

    -- The Sakha this review belongs to (member's home Sakha at trigger
    -- time).
    organization_pk UUID NOT NULL,

    trigger_date DATE NOT NULL,

    consecutive_absences INTEGER NOT NULL
        DEFAULT 3,

    review_status_master_data_pk UUID NOT NULL,

    -- Operational office responsible right now (ATT-015/016/017).
    assigned_to_role VARCHAR(20) NOT NULL
        DEFAULT 'SECRETARY',

    closed_by_sangha_sevi_pk UUID NULL,

    deferred_by_sangha_sevi_pk UUID NULL,

    escalated_by_sangha_sevi_pk UUID NULL,

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

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT fk_attrev_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_attrev_org
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_attrev_status
        FOREIGN KEY (review_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_attrev_closed_by
        FOREIGN KEY (closed_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_attrev_deferred_by
        FOREIGN KEY (deferred_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_attrev_escalated_by
        FOREIGN KEY (escalated_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_attrev_assigned_role
        CHECK (assigned_to_role IN ('SECRETARY', 'PRESIDENT', 'PARICHALAK')),

    CONSTRAINT chk_attrev_consecutive_absences
        CHECK (consecutive_absences >= 3),

    CONSTRAINT chk_attrev_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_attrev_sevi
    ON nss.attendance_review (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_attrev_org
    ON nss.attendance_review (organization_pk);

CREATE INDEX IF NOT EXISTS idx_attrev_status
    ON nss.attendance_review (review_status_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_attrev_assigned_role
    ON nss.attendance_review (assigned_to_role);
