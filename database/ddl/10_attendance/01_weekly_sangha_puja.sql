-- =====================================================
-- NSS ERP
-- Module: Attendance (Tier 6)
-- File: 01_weekly_sangha_puja.sql
-- Table: nss.weekly_sangha_puja
-- Depth: 1 (depends on organization)
-- Version: 1.0
-- Authority: docs/03_Solution/modules/attendance/
--            01_attendance_module_overview.md (§7),
--            04_attendance_business_rules.md (ATT-003..005),
--            05_attendance_table_design.md (§3),
--            03_attendance_lifecycle.md (§3-4)
-- Owner: NSS_ERP_ADMIN
-- Note: One Weekly Sangha Puja attendance event per Sakha per date.
--       sakha_pk is a generic FK to nss.organization (not CHECK-restricted
--       to SAKHA_SANGHA at the DDL level, matching the project convention
--       of validating org-type constraints in the API, not the schema —
--       see ORG-BR-099's own precedent); the business rule (ATT-004: the
--       event is Sakha-level only) is enforced in api/routers/attendance.py.
--       No separate SCHEDULED/CONDUCTED status column: per the Attendance
--       Lifecycle doc (§3-4), that state is DERIVED from puja_date vs.
--       CURRENT_DATE, not stored — storing it would drift out of sync.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.weekly_sangha_puja
(
    -- ── Identity ────────────────────────────────────────

    weekly_sangha_puja_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Core References ─────────────────────────────────

    -- The Sakha conducting this Weekly Sangha Puja (ATT-004).
    sakha_pk UUID NOT NULL,

    puja_date DATE NOT NULL,

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

    CONSTRAINT fk_wsp_sakha
        FOREIGN KEY (sakha_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_wsp_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        ),

    -- One Weekly Sangha Puja event per Sakha per date.
    CONSTRAINT uq_wsp_sakha_date
        UNIQUE (sakha_pk, puja_date)
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_wsp_sakha
    ON nss.weekly_sangha_puja (sakha_pk);

CREATE INDEX IF NOT EXISTS idx_wsp_puja_date
    ON nss.weekly_sangha_puja (puja_date);

CREATE INDEX IF NOT EXISTS idx_wsp_active
    ON nss.weekly_sangha_puja (is_active);
