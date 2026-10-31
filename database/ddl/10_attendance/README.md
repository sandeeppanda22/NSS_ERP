# database/ddl/10_attendance/

Attendance module DDL — 4 tables (Tier 6, committed on `feature/tier6-governance`). Weekly Sangha Puja attendance, attendance
exceptions and the Attendance Review workflow. Built as Phase 11e of `02_build.sh`/`.ps1` and
`render_build.sh` (after Governance/Correspondence, before the Phase 12 writer grant and Phase 14
audit trigger, so both cover these tables). Design authority: `docs/03_Solution/modules/attendance/`
(frozen 2026-10-27).

| File | Table | Notes |
|---|---|---|
| `01_weekly_sangha_puja.sql` | `weekly_sangha_puja` | One event per Sakha per date (`UNIQUE (sakha_pk, puja_date)`). `sakha_pk` is a generic FK to `organization`; "Sakha only" (ATT-004) is enforced in the API, not the schema. SCHEDULED/CONDUCTED is derived from `puja_date`, never stored. |
| `02_weekly_sangha_puja_attendance.sql` | `weekly_sangha_puja_attendance` | One row per (puja, member), keyed on `sangha_sevi_pk`. `attendance_sakha_pk` is separate from the member's home Sakha (cross-Sakha / Darshak attendance); no `is_darshak` flag is stored. Status is a `master_data` FK (`ATTENDANCE_STATUS`). |
| `03_attendance_exception.sql` | `attendance_exception` | Date-ranged exception per member; type is a `master_data` FK (`ATTENDANCE_EXCEPTION_TYPE`); `to_date >= from_date` CHECK. |
| `04_attendance_review.sql` | `attendance_review` | Opened after 3 consecutive ABSENT; `assigned_to_role` CHECK (SECRETARY/PRESIDENT/PARICHALAK); status is a `master_data` FK. "One OPEN review per member" is enforced in the API, not by an index. |

Reference data (`ATTENDANCE_STATUS`, `ATTENDANCE_EXCEPTION_TYPE`, review statuses) is seeded in
`database/seed/01_foundation/02_master_data.sql`; RBAC (`ATTENDANCE_VIEW`/`ATTENDANCE_MANAGE`,
`NSS_ERP_ATTENDANCE_MARKER`) in `database/seed/00_bootstrap/`.

API: `api/routers/attendance.py` + `api/schemas/attendance.py`. `03_validate.sh`/`.ps1` run
existence checks for these tables (no seed). API/security pytest coverage: `tests/api/test_attendance.py`, `tests/security/test_attendance_security.py` (fixtures in `tests/attendance_support.py`; written but not yet run against the DB). There is no `tests/db` schema test for these tables.

Folder index: [`../README.md`](../README.md). Deep doc: `docs/PROJECT_DOCUMENTATION.md`.
