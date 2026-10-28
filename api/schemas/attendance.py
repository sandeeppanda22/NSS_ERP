"""
Pydantic response models for the Attendance API (Tier 6).

Authority: docs/03_Solution/modules/attendance/01_attendance_module_overview.md
through 06_attendance_review_workflow.md (all FROZEN as of 2026-10-27).

All models exclude audit columns (created_at/updated_at/deleted_at) per
the project's API convention, except where the timestamp itself is the
business fact (e.g. a review's created_at as its "opened" date).
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


# ═══════════════════════════════════════════════════════════════════════
# Weekly Sangha Puja
# ═══════════════════════════════════════════════════════════════════════

class CreatePujaRequest(BaseModel):
    sakha_pk: UUID
    puja_date: date
    remarks: str | None = None


class PujaResponse(BaseModel):
    weekly_sangha_puja_pk: UUID
    sakha_pk: UUID
    sakha_name: str
    puja_date: date
    remarks: str | None

    # Derived, never stored (Attendance Lifecycle §3-4): SCHEDULED while
    # puja_date is today or in the future, CONDUCTED once it has passed.
    puja_status: str

    marked_count: int
    present_count: int
    absent_count: int
    excused_count: int


class PujaListResponse(BaseModel):
    pujas: list[PujaResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════
# Attendance Records
# ═══════════════════════════════════════════════════════════════════════

class MarkAttendanceItem(BaseModel):
    sangha_sevi_pk: UUID
    attendance_status_code: str  # PRESENT / ABSENT / EXCUSED_ABSENCE
    # Defaults to the puja's own sakha_pk when omitted — only needed when
    # this specific member attended cross-Sakha (ATT-026/028).
    attendance_sakha_pk: UUID | None = None
    remarks: str | None = None


class MarkAttendanceRequest(BaseModel):
    records: list[MarkAttendanceItem]


class AttendanceRecordResponse(BaseModel):
    attendance_pk: UUID
    weekly_sangha_puja_pk: UUID
    puja_date: date
    sakha_pk: UUID  # the puja's own Sakha

    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str

    attendance_status_code: str
    attendance_status_name: str

    attendance_sakha_pk: UUID
    attendance_sakha_name: str

    # Member's home Sakha (sangha_sevi.organization_pk) — added 2026-10-27
    # alongside the is_darshak bug fix (see attendance.py::_row_to_record):
    # home Sakha vs. the puja's own Sakha is what actually makes someone a
    # Darshak, not attendance_sakha_pk (which always equals the puja's
    # Sakha in practice — a puja happens at one physical place).
    home_organization_pk: UUID
    home_organization_name: str

    # Member's membership type (REGULAR / PROBATIONARY / ASSOCIATE /
    # HONORARY) — added 2026-10-27 for the demo-style Darshak card, which
    # classifies a home PROBATIONARY attendee as a "New Visitor" vs. a
    # cross-Sakha attendee as "Other Sakha".
    membership_type_code: str

    # Owner-confirmed classification (2026-10-27), replacing the earlier
    # "is_darshak alone decides Other Sakha" rule:
    #   - Darshak (home):  home Sakha == puja Sakha AND PROBATIONARY.
    #   - Other Sakha:     an ACTIVE + APPROVED nss.darshak_attendance_
    #     registration exists for (this member, this puja's Sakha) — the
    #     formal three-step-approved arrangement (DAR-002/006/009), not a
    #     bare home-Sakha-mismatch guess.
    #   - New Visitor:     anything else that still shows in the Darshak
    #     card (cross-Sakha without an approved registration, or any
    #     other darshak-worthy row not covered above).
    has_approved_darshak_registration: bool

    # The member's current local Sakha ERP number at their HOME Sakha
    # (membership_sakha_affiliation.local_sakha_erp_id) — added 2026-10-27
    # for the Darshak card's "SSID/LocalSakhaID" identity format. None
    # when no active home affiliation exists yet.
    local_sakha_erp_id: str | None

    # Home Sakha != Puja Sakha (ATT-026/029/030) — computed, not stored;
    # kept for backward compatibility / the plain cross-Sakha signal.
    is_darshak: bool

    remarks: str | None


class AttendanceRecordListResponse(BaseModel):
    records: list[AttendanceRecordResponse]
    total: int


class CorrectAttendanceRequest(BaseModel):
    attendance_status_code: str
    remarks: str | None = None


# ═══════════════════════════════════════════════════════════════════════
# Attendance Exceptions
# ═══════════════════════════════════════════════════════════════════════

class CreateExceptionRequest(BaseModel):
    sangha_sevi_pk: UUID
    exception_type_code: str
    from_date: date
    to_date: date | None = None
    remarks: str | None = None


class ExceptionResponse(BaseModel):
    exception_pk: UUID
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str

    exception_type_code: str
    exception_type_name: str

    from_date: date
    to_date: date | None

    approved_by_sangha_sevi_pk: UUID
    approved_by_name: str
    approved_date: date

    remarks: str | None


class ExceptionListResponse(BaseModel):
    exceptions: list[ExceptionResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════
# Attendance Review
# ═══════════════════════════════════════════════════════════════════════

class ReviewResponse(BaseModel):
    review_pk: UUID

    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str

    organization_pk: UUID
    organization_name: str

    trigger_date: date
    consecutive_absences: int

    review_status_code: str
    review_status_name: str

    assigned_to_role: str

    closed_by_sangha_sevi_pk: UUID | None
    closed_by_name: str | None
    deferred_by_sangha_sevi_pk: UUID | None
    deferred_by_name: str | None
    escalated_by_sangha_sevi_pk: UUID | None
    escalated_by_name: str | None

    remarks: str | None
    created_at: datetime
    updated_at: datetime | None


class ReviewListResponse(BaseModel):
    reviews: list[ReviewResponse]
    total: int


class ReviewActionRequest(BaseModel):
    remarks: str | None = None


class ReviewOverrideRequest(BaseModel):
    # New review_status code to apply (President override, ATT-016 /
    # Review Workflow §12) — e.g. overriding a Secretary CLOSED back to
    # OPEN, or an OPEN straight to CLOSED.
    new_status_code: str
    reason: str


# ═══════════════════════════════════════════════════════════════════════
# Watch List
# ═══════════════════════════════════════════════════════════════════════

class WatchListItem(BaseModel):
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str
    organization_pk: UUID
    organization_name: str
    current_consecutive_absences: int
    last_puja_date: date


class WatchListResponse(BaseModel):
    items: list[WatchListItem]
    total: int


# ═══════════════════════════════════════════════════════════════════════
# Stats (owner ask 2026-10-27: attendance % per Sakha, attendance % per
# member)
# ═══════════════════════════════════════════════════════════════════════

class OrgAttendanceStatsResponse(BaseModel):
    organization_pk: UUID
    organization_name: str
    period_from: date | None
    period_to: date | None
    total_puja_events: int
    total_records: int
    present_count: int
    absent_count: int
    excused_count: int
    # present_count / (present_count + absent_count) * 100 — EXCUSED_ABSENCE
    # is deliberately excluded from the denominator (ATT-008: it is not an
    # ordinary absence), rounded to 1 decimal. None when the denominator
    # is 0 (no PRESENT/ABSENT history yet).
    attendance_percentage: float | None


class MemberAttendanceStatsResponse(BaseModel):
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str
    period_from: date | None
    period_to: date | None
    total_records: int
    present_count: int
    absent_count: int
    excused_count: int
    attendance_percentage: float | None
    current_consecutive_absences: int


# ═══════════════════════════════════════════════════════════════════════
# Per-org Member Attendance Leaderboard (owner ask 2026-10-28) — every
# HOME member of a Sakha with their own attendance % at that Sakha's
# puja, for the Sakha dashboard's "Top Attendance" card (top 5) and its
# "View Full Attendance" page (same endpoint, no limit). Both render the
# SAME columns (owner correction 2026-10-28): ID / Name / Type / Status
# (the member's last 3 puja attendances) / Remarks (the latest puja's
# remark only) / Attendance %.
# ═══════════════════════════════════════════════════════════════════════

class RecentAttendanceStatus(BaseModel):
    puja_date: date
    attendance_status_code: str


class OrgMemberAttendanceResponse(BaseModel):
    sangha_sevi_pk: UUID
    sangha_sevi_id: str
    person_name: str
    local_sakha_erp_id: str | None
    membership_type_code: str
    total_records: int
    present_count: int
    absent_count: int
    excused_count: int
    attendance_percentage: float | None

    # Last 3 puja attendances, most recent first (owner correction
    # 2026-10-28: "the status is last 3 attendance") — never more than 3,
    # fewer when the member has less history.
    recent_statuses: list[RecentAttendanceStatus]

    # The latest puja's own remark only (owner correction 2026-10-28:
    # "remarks is for latest sangha puja attendance remark") — not every
    # remark across the 3 statuses above.
    latest_remarks: str | None


class OrgMemberAttendanceListResponse(BaseModel):
    members: list[OrgMemberAttendanceResponse]
    total: int

