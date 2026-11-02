# NSS ERP Attendance Module

Status: DRAFT design complete (Review Workflow FROZEN). **Implemented (Tier 6, committed on `feature/tier6-governance`, 2026-10-27/28):**
DDL `database/ddl/10_attendance/` (4 tables, build Phase 11e), API `api/routers/attendance.py`
(21 endpoints under `/api/v1/attendance`) and the shared UI mixin `frontend/assets/js/attendance-register.js`
(admin Attendance group + Sakha dashboard register). API/security tests exist (`tests/api/test_attendance.py`, `tests/security/test_attendance_security.py`, `tests/attendance_support.py`; 261 collected, not yet run against the DB); UI tests `tests/ui/test_ui_attendance.py` (132 collected) also never run.

---

## Live multi-marker register (2026-10-31, owner decision "Option B")

Several markers of the same Sakha open the Mark Attendance register at once. It updates live and one
marker cannot overwrite another's work, without changing any frozen rule (ATT-006..010, the
EXCUSED_ABSENCE authority check, consecutive-absence detection, audit and "not before the puja date"
are untouched):

- **Explicit Save, only changed rows.** The UI sends only the members THIS marker changed (never the
  roster); untouched members stay unmarked (no default status). Each sent row carries
  `expected_version` = the row `version` (last-change timestamp) the marker last saw.
- **409 on a stale overwrite.** If someone else changed that member since, and to a different status,
  `POST /pujas/{pk}/attendance` saves nothing and returns `409 detail.conflicts` naming who changed it
  and when; the UI asks "Overwrite these" (resend with `overwrite_sangha_sevi_pks`) or "Keep theirs".
- **Changing someone else's mark asks first (2026-11-01).** Even when the marker's screen is current,
  tapping a different status on a row another person marked asks "Marked <Status> by <Name> at <time> -
  change it?" (Cancel keeps their mark; OK flags the row so Save sends it in `overwrite_sangha_sevi_pks`).
  Own marks never ask; the bulk P/A/E buttons skip other people's rows unless confirmed once for the batch.
  The server enforces the same rule for requests carrying `expected_version`: a matching version is still a
  409 when the row was last changed by a different member to a different status. Requests without
  `expected_version` keep last-write-wins.
- **Register-screen percentage (2026-11-01).** `present / (roster total - excused)` - unmarked members are
  in the denominator, EXCUSED_ABSENCE members are not. One pure function,
  `registerAttendancePercentage()` in `attendance-register.js`. **Tension with ATT-008** (frozen, not
  edited): ATT-008 defines the percentage over marked present/absent records only; this screen figure
  (8 present, 1 absent, 3 unmarked of 12 = 67%, not 89%) is a deliberate owner-directed display rule.
  The stats endpoints (org, per-member, member leaderboard, dashboard cards) are multi-week figures and
  still use present/(present+absent); aligning them is an open owner decision.
- **Live view.** `GET /pujas/{pk}/live` is polled at a fixed 2 s interval (a "Reconnecting" note shows on
  errors) with an ETag so an unchanged register is a 304. Idle slow-down, hidden-tab pause and error
  back-off were deliberately left out for now (owner decision 2026-10-31). Rows show "by <name>, <time>"; a banner shows "N of M marked";
  a "Not marked" filter chip lists members nobody has marked.
- **Index.** `idx_wspa_puja_last_change` (`database/ddl/10_attendance/05_attendance_live_version_index_patch.sql`,
  idempotent, run by all build scripts) serves the version cursor.
- **Rate limit (fix 1, 2026-11-01):** `GET /pujas/{pk}/live` has its own limit,
  `LIVE_ATTENDANCE_RATE_LIMIT` (default `120/minute`), counted **per signed-in user** (JWT `sub`; client IP when
  there is no valid token) instead of the global per-IP `RATE_LIMIT` — so a whole Sakha polling from one WiFi IP
  no longer shares one budget (`api/rate_limit.py`). Still open: the adaptive cadence (fix 2: idle slow-down,
  hidden-tab pause, error back-off) was left out on purpose; a 429 is retried at the same 2 s.

---

## Documents

01_attendance_module_overview.md — Version 1.0, DRAFT
Purpose: High-level Attendance module overview (Weekly Attendance, Attendance Review,
Attendance Reports).

02_attendance_erd.md — Version 1.0.0, DRAFT
Purpose: Entity relationship design for attendance marking and review.

03_attendance_lifecycle.md — Version 0.1.0, DRAFT, Document ID `SOL-ATT-006`
Purpose: `weekly_sangha_puja` (SCHEDULED/CONDUCTED), `attendance` (PRESENT/ABSENT/
EXCUSED_ABSENCE + correction), `attendance_exception` (ACTIVE/EXPIRED), `attendance_review`
(OPEN/DEFERRED/CLOSED/ESCALATED_TO_PRESIDENT/ESCALATED_TO_PARICHALAK), consecutive-absence
detection, cross-Sakha attendance, Person-death integration.

04_attendance_business_rules.md — Version 1.0.0, DRAFT (was `03_...` before the lifecycle doc
was inserted and file numbers shifted down one slot)
Purpose: Business rules governing who may mark/review attendance and how records are corrected.

05_attendance_table_design.md — Version 1.0.0, DRAFT (was `04_...`)
Purpose: Physical table design for attendance records and review history.

06_attendance_review_workflow.md — Version 1.0.0, **Status: FROZEN** (was `05_...`)
Purpose: Attendance Enforcement + Attendance Review workflow — Secretary as primary operational
authority, President as oversight/appeal authority.

**`DARSHAK_BUSINESS_RULE.md`** — Version 1.1, Status: Approved
An ERP implementation decision (not derived from the Bye-Law): corrects an earlier project Rule
Book's informal "Darshak" tier against the actual Bye-Law (`REF-002`, only
Probationary/Regular/Associate exist) — "Darshak" is a UI display label only (a visiting
Probationary/Regular member from another Sakha), never a `membership_type_master` value.

---

## Current Status

Design Complete

ERD Complete

Lifecycle Documented (SOL-ATT-006 — does not yet cross-reference `SOL-LIFE-001`/`002`, see
`docs/PROJECT_DOCUMENTATION.md` → "Open questions / TODOs")

Business Rules Drafted

Table Design Drafted

Review Workflow Frozen

SQL Implementation Not Started — no `database/ddl/` tables and no API endpoints exist for
Attendance yet
