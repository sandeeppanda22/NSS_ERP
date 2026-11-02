-- =====================================================
-- NSS ERP
-- Module: Attendance (Tier 6)
-- File: 05_attendance_live_version_index_patch.sql
-- Table: nss.weekly_sangha_puja_attendance (index only - no table change)
-- Version: 1.0 (live-register follow-up, owner decision "Option B")
-- Purpose: serves GET /api/v1/attendance/pujas/{pk}/live?since=... which
--          returns the rows of ONE puja whose last-change timestamp is newer
--          than a cursor, and mark_attendance()'s optimistic-concurrency
--          check. "Last change" is the single expression
--              GREATEST(created_at, COALESCE(updated_at, created_at))
--          (api/routers/attendance.py::_ATT_VERSION_SQL is the one Python
--          copy; the planner only uses this index when the query repeats the
--          expression verbatim, so keep the two in step).
-- Why a patch: 02_weekly_sangha_puja_attendance.sql is existence-gated by
--          the build scripts and is skipped on any database that already has
--          the table. Not a table: applied with run_sql, idempotent
--          (CREATE INDEX IF NOT EXISTS), a no-op once the index exists.
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_wspa_puja_last_change
    ON nss.weekly_sangha_puja_attendance
       (weekly_sangha_puja_pk, (GREATEST(created_at, COALESCE(updated_at, created_at))));
