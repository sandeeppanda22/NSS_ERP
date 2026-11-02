-- =====================================================
-- NSS ERP
-- Module: Attendance (Tier 6)
-- File: 03_attendance_exception.sql
-- Table: nss.attendance_exception
-- Depth: 2 (depends on sangha_sevi, master_data)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/attendance/
--            04_attendance_business_rules.md (ATT-023/024/025),
--            05_attendance_table_design.md (§10-11)
-- Owner: NSS_ERP_ADMIN
-- Note: An approved exception's effect (ATT-025 — absence within the
--       exception period is not treated as ordinary ABSENT) is applied by
--       the API when marking/correcting attendance; this table only
--       records the approved exception itself, never a derived
--       attendance row. approved_by_sangha_sevi_pk is the Secretary/
--       President who approved it (Review Authority Matrix) — not
--       restricted to an admin_scope FK since approval authority here is
--       the real governance seat, checked in the API, the same model used
--       for Attendance Review.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.attendance_exception
(
    -- ── Identity ────────────────────────────────────────

    exception_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Core References ─────────────────────────────────

    sangha_sevi_pk UUID NOT NULL,

    exception_type_master_data_pk UUID NOT NULL,

    from_date DATE NOT NULL,

    -- NULL = open-ended exception.
    to_date DATE NULL,

    approved_by_sangha_sevi_pk UUID NOT NULL,

    approved_date DATE NOT NULL,

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

    CONSTRAINT fk_attexc_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_attexc_type
        FOREIGN KEY (exception_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_attexc_approved_by
        FOREIGN KEY (approved_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_attexc_date_range
        CHECK (to_date IS NULL OR to_date >= from_date),

    CONSTRAINT chk_attexc_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_attexc_sevi
    ON nss.attendance_exception (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_attexc_type
    ON nss.attendance_exception (exception_type_master_data_pk);

-- Active-exception lookup (lifecycle doc §24): from_date <= ? AND
-- (to_date IS NULL OR to_date >= ?).
CREATE INDEX IF NOT EXISTS idx_attexc_sevi_dates
    ON nss.attendance_exception (sangha_sevi_pk, from_date, to_date);
