-- =====================================================
-- NSS ERP
-- Module: Attendance (Tier 6)
-- File: 02_weekly_sangha_puja_attendance.sql
-- Table: nss.weekly_sangha_puja_attendance
-- Depth: 2 (depends on weekly_sangha_puja, sangha_sevi, organization,
--           master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/attendance/
--            04_attendance_business_rules.md (ATT-001/002/006-008/026-030),
--            05_attendance_table_design.md (§4-9)
-- Owner: NSS_ERP_ADMIN
-- Note: attendance_sakha_pk is deliberately a SEPARATE FK from the member's
--       home Sakha (resolved via sangha_sevi.organization_pk) — this is the
--       cross-Sakha model (ATT-026/027/028): the record preserves WHERE the
--       member actually attended without ever touching their Membership
--       organization. attendance_sakha_pk may differ from the home Sakha;
--       the API computes "Darshak" labels (ATT-029/030) client-side from
--       that difference — this table never stores a "is_darshak" flag.
--       One attendance row per (puja, member) — Table Design §9.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.weekly_sangha_puja_attendance
(
    -- ── Identity ────────────────────────────────────────

    attendance_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Core References ─────────────────────────────────

    weekly_sangha_puja_pk UUID NOT NULL,

    -- The authoritative Membership identity (ATT-001). Attendance never
    -- creates a second Membership identity (ATT-002).
    sangha_sevi_pk UUID NOT NULL,

    attendance_status_master_data_pk UUID NOT NULL,

    -- The Sakha where this attendance was ACTUALLY recorded — may differ
    -- from the member's home Sakha (cross-Sakha attendance, ATT-026/028).
    attendance_sakha_pk UUID NOT NULL,

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

    CONSTRAINT fk_wspa_puja
        FOREIGN KEY (weekly_sangha_puja_pk)
        REFERENCES nss.weekly_sangha_puja (weekly_sangha_puja_pk),

    CONSTRAINT fk_wspa_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_wspa_status
        FOREIGN KEY (attendance_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_wspa_attendance_sakha
        FOREIGN KEY (attendance_sakha_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_wspa_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        ),

    -- Logical uniqueness (Table Design §9): one attendance record per
    -- Member per Weekly Sangha Puja event. Scoped to active rows so a
    -- soft-deleted correction (chk_wspa_soft_delete) never blocks a
    -- fresh re-record.
    CONSTRAINT uq_wspa_puja_sevi
        UNIQUE (weekly_sangha_puja_pk, sangha_sevi_pk)
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_wspa_puja
    ON nss.weekly_sangha_puja_attendance (weekly_sangha_puja_pk);

CREATE INDEX IF NOT EXISTS idx_wspa_sevi
    ON nss.weekly_sangha_puja_attendance (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_wspa_status
    ON nss.weekly_sangha_puja_attendance (attendance_status_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_wspa_attendance_sakha
    ON nss.weekly_sangha_puja_attendance (attendance_sakha_pk);

-- Consecutive-absence detection (lifecycle doc §24) walks a member's
-- ABSENT history ordered by puja date — this composite index serves that
-- query directly.
CREATE INDEX IF NOT EXISTS idx_wspa_sevi_status
    ON nss.weekly_sangha_puja_attendance (sangha_sevi_pk, attendance_status_master_data_pk);
