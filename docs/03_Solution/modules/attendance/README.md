# NSS ERP Attendance Module

Status: DRAFT design complete (Review Workflow FROZEN) — `backend/attendance/` remains a pure
Django app stub (empty `models.py`/`views.py`, no `urls.py`, not in `INSTALLED_APPS`), so this
is greenfield design with zero corresponding code yet — a wider code/doc gap than
membership/family, which at least have partial models.

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

SQL Implementation Not Started — `backend/attendance/` has no models at all yet
