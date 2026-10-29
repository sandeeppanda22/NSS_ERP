"""
Attendance API router — Tier 6.

Weekly Sangha Puja attendance marking, attendance exceptions, and the
Attendance Review workflow (3 consecutive ABSENT -> OPEN review ->
Secretary/President action). Authority: docs/03_Solution/modules/
attendance/01_attendance_module_overview.md through
06_attendance_review_workflow.md (all FROZEN 2026-10-27).

Operational authority split (ATT-041..044, 2026-10-27 amendment):
  - Marking attendance (create puja, mark PRESENT/ABSENT/EXCUSED_ABSENCE):
    ATTENDANCE_MANAGE permission + admin scope (Sakha admin or the new
    per-Sakha NSS_ERP_ATTENDANCE_MARKER role — both just need the
    permission + scope, no governance-seat check).
  - Acting on an Attendance Review (close/defer/escalate/reopen/override/
    approve excused absence) and creating an Attendance Exception:
    the REAL Secretary/President seat on the member's home Sakha's
    SAKHA_GOVERNING_BODY, checked live against body_member_assignment
    (_require_review_authority below) — not a permission at all, per the
    frozen Review Authority Matrix naming actual offices. NSS_ERP_ADMIN
    retains global oversight (ATT-044) and may also act, consistent with
    every other module's NSS-wide override.

Three-tier identity model (unchanged from Membership): all attendance is
keyed on sangha_sevi_pk, never a second identity (ATT-001/002).
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.dependencies.rbac import require_permission
from api.helpers import MAX_LIMIT, get_master_data_pk, log_audit, require_entity, require_sakha_organization
from api.routers.governance import _CURRENT_ASSIGNMENT_SQL, _person_name_sql
from api.schemas.attendance import (
    AttendanceRecordListResponse,
    AttendanceRecordResponse,
    CorrectAttendanceRequest,
    CreateExceptionRequest,
    CreatePujaRequest,
    ExceptionListResponse,
    ExceptionResponse,
    MarkAttendanceRequest,
    MemberAttendanceStatsResponse,
    OrgAttendanceStatsResponse,
    OrgMemberAttendanceListResponse,
    OrgMemberAttendanceResponse,
    PujaListResponse,
    PujaResponse,
    ReviewActionRequest,
    ReviewListResponse,
    ReviewOverrideRequest,
    ReviewResponse,
    WatchListItem,
    WatchListResponse,
)
from api.services.rbac_service import UserContext, actor_scope_org_pks, require_org_in_scope

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════

# Only ABSENT counts toward consecutive-absence monitoring (ATT-007);
# EXCUSED_ABSENCE breaks the chain just like PRESENT (ATT-008/025).
_CONSECUTIVE_ABSENCE_THRESHOLD = 3

# ATT-025: an ABSENT that falls inside one of the member's approved
# attendance exceptions (from_date <= puja_date AND (to_date IS NULL OR
# to_date >= puja_date)) is not an ordinary ABSENT — it breaks the
# consecutive-absence chain exactly like EXCUSED_ABSENCE. Shared by review
# detection, the watch list and the member streak so the three never
# disagree. Expects aliases: a = weekly_sangha_puja_attendance,
# w = weekly_sangha_puja, md = the status master_data row.
_EFFECTIVE_STATUS_SQL = """(
    CASE WHEN md.value_code = 'ABSENT' AND EXISTS (
        SELECT 1 FROM nss.attendance_exception ex
        WHERE  ex.sangha_sevi_pk = a.sangha_sevi_pk AND ex.is_active = TRUE
          AND  ex.from_date <= w.puja_date
          AND  (ex.to_date IS NULL OR ex.to_date >= w.puja_date)
    ) THEN 'EXCEPTED' ELSE md.value_code END
)"""


# A member with any non-CLOSED Attendance Review (OPEN/DEFERRED/ESCALATED_*)
# already has one in flight (ATT-014). %s = SQL expression for the member pk.
_HAS_OPEN_REVIEW_SQL = """EXISTS (
    SELECT 1 FROM nss.attendance_review r
    JOIN nss.master_data rmd ON rmd.master_data_pk = r.review_status_master_data_pk
    WHERE r.sangha_sevi_pk = %s AND r.is_active = TRUE AND rmd.value_code != 'CLOSED'
)"""


def _require_view_or_self(user: UserContext, sangha_sevi_pk) -> None:
    """
    A member may always read their own attendance data; anyone else's needs
    ATTENDANCE_VIEW (plus admin scope, checked by the caller). Used instead
    of a blanket require_permission so the self-access promised by the
    endpoint docstrings is real.
    """
    if sangha_sevi_pk is not None and user.sangha_sevi_pk and str(sangha_sevi_pk) == str(user.sangha_sevi_pk):
        return
    if not user.has_permission("ATTENDANCE_VIEW"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission required: ATTENDANCE_VIEW")


def _require_review_authority(
    cur, user: UserContext, organization_pk, action: str, *, president_only: bool = False
) -> None:
    """
    Attendance Review / Exception approval authority (ATT-042): the real
    Secretary or President seat on *organization_pk*'s SAKHA_GOVERNING_BODY
    — not an admin permission. NSS_ERP_ADMIN keeps global oversight
    (ATT-044) and may act anywhere. Raises 403 otherwise.

    Mirrors the lookup used for the Member Directory's President/
    Secretary badge (api/routers/membership.py's position_join) — same
    "currently seated" definition (_CURRENT_ASSIGNMENT_SQL).
    """
    if user.is_super_admin():
        return
    position_codes = ("PRESIDENT",) if president_only else ("PRESIDENT", "SECRETARY")
    placeholders = ",".join(["%s"] * len(position_codes))
    cur.execute(
        f"""
        SELECT 1
        FROM   nss.body_member_assignment a
        JOIN   nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        JOIN   nss.body_master bm ON bm.body_master_pk = a.body_master_pk
        JOIN   nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE  a.person_pk = %s
          AND  bm.organization_pk = %s
          AND  bt.body_type_code = 'SAKHA_GOVERNING_BODY'
          AND  pm.position_code IN ({placeholders})
          AND  {_CURRENT_ASSIGNMENT_SQL}
        """,
        (str(user.person_pk), str(organization_pk), *position_codes),
    )
    if cur.fetchone() is not None:
        return
    office = "President" if president_only else "Secretary or President"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Only the Sakha's {office} may {action}.",
    )


def _member_home_org(cur, sangha_sevi_pk) -> str:
    """Resolve a member's current home Sakha (sangha_sevi.organization_pk)."""
    cur.execute(
        "SELECT organization_pk FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s AND is_active = TRUE",
        (str(sangha_sevi_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found.")
    return str(row[0])


def _check_and_open_review(cur, sangha_sevi_pk, trigger_date: date, actor_pk) -> None:
    """
    ATT-009/010/014: after recording an ABSENT, check the member's last 3
    Weekly Sangha Puja records; if all 3 are ABSENT and no review is
    already OPEN/DEFERRED/ESCALATED_* for them, open one (detection at
    write-time per the 2026-10-27 lifecycle amendment — no scheduled job).
    """
    cur.execute(
        f"""
        SELECT {_EFFECTIVE_STATUS_SQL}
        FROM   nss.weekly_sangha_puja_attendance a
        JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
        JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
        WHERE  a.sangha_sevi_pk = %s AND a.is_active = TRUE
        ORDER BY w.puja_date DESC
        LIMIT %s
        """,
        (str(sangha_sevi_pk), _CONSECUTIVE_ABSENCE_THRESHOLD),
    )
    rows = cur.fetchall()
    if len(rows) < _CONSECUTIVE_ABSENCE_THRESHOLD or any(r[0] != "ABSENT" for r in rows):
        return

    # An existing non-terminal review already covers this member — don't
    # open a duplicate (DB can't express this as a constraint; see
    # 05_attendance_table_design.md's 2026-10-27 amendment).
    cur.execute(f"SELECT {_HAS_OPEN_REVIEW_SQL % '%s'}", (str(sangha_sevi_pk),))
    if cur.fetchone()[0]:
        return

    organization_pk = _member_home_org(cur, sangha_sevi_pk)
    open_pk = get_master_data_pk(cur, "ATTENDANCE_REVIEW_STATUS", "OPEN")
    cur.execute(
        """
        INSERT INTO nss.attendance_review
            (sangha_sevi_pk, organization_pk, trigger_date, consecutive_absences,
             review_status_master_data_pk, assigned_to_role, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s, 'SECRETARY', %s)
        RETURNING review_pk
        """,
        (str(sangha_sevi_pk), organization_pk, trigger_date,
         _CONSECUTIVE_ABSENCE_THRESHOLD, open_pk, actor_pk),
    )
    review_pk = cur.fetchone()[0]
    log_audit(cur, action="CREATE", table_name="attendance_review", record_pk=str(review_pk),
              actor_pk=actor_pk, module="attendance",
              summary=f"Attendance Review opened — 3 consecutive absences (ATT-010)")


_REVIEW_SELECT_SQL = f"""
    SELECT r.review_pk, r.sangha_sevi_pk, s.sangha_sevi_id, {_person_name_sql('p')},
           r.organization_pk, o.organization_name, r.trigger_date, r.consecutive_absences,
           md.value_code, md.value_name, r.assigned_to_role,
           r.closed_by_sangha_sevi_pk, NULLIF({_person_name_sql('cp')}, ''),
           r.deferred_by_sangha_sevi_pk, NULLIF({_person_name_sql('dp')}, ''),
           r.escalated_by_sangha_sevi_pk, NULLIF({_person_name_sql('ep')}, ''),
           r.remarks, r.created_at, r.updated_at
    FROM   nss.attendance_review r
    JOIN   nss.sangha_sevi s ON s.sangha_sevi_pk = r.sangha_sevi_pk
    JOIN   nss.person p ON p.person_pk = s.person_pk
    JOIN   nss.organization o ON o.organization_pk = r.organization_pk
    JOIN   nss.master_data md ON md.master_data_pk = r.review_status_master_data_pk
    LEFT JOIN nss.sangha_sevi cs ON cs.sangha_sevi_pk = r.closed_by_sangha_sevi_pk
    LEFT JOIN nss.person cp ON cp.person_pk = cs.person_pk
    LEFT JOIN nss.sangha_sevi ds ON ds.sangha_sevi_pk = r.deferred_by_sangha_sevi_pk
    LEFT JOIN nss.person dp ON dp.person_pk = ds.person_pk
    LEFT JOIN nss.sangha_sevi es ON es.sangha_sevi_pk = r.escalated_by_sangha_sevi_pk
    LEFT JOIN nss.person ep ON ep.person_pk = es.person_pk
"""


def _row_to_review(r) -> ReviewResponse:
    return ReviewResponse(
        review_pk=r[0], sangha_sevi_pk=r[1], sangha_sevi_id=r[2], person_name=r[3],
        organization_pk=r[4], organization_name=r[5], trigger_date=r[6],
        consecutive_absences=r[7], review_status_code=r[8], review_status_name=r[9],
        assigned_to_role=r[10], closed_by_sangha_sevi_pk=r[11], closed_by_name=r[12],
        deferred_by_sangha_sevi_pk=r[13], deferred_by_name=r[14],
        escalated_by_sangha_sevi_pk=r[15], escalated_by_name=r[16],
        remarks=r[17], created_at=r[18], updated_at=r[19],
    )


def _set_review_status(cur, review_pk, status_code: str, *, actor_pk, remarks: str | None,
                        by_column: str | None = None) -> None:
    status_pk = get_master_data_pk(cur, "ATTENDANCE_REVIEW_STATUS", status_code)
    sets = ["review_status_master_data_pk = %s", "updated_at = NOW()", "updated_by_sangha_sevi_pk = %s"]
    params: list = [status_pk, actor_pk]
    if by_column:
        sets.append(f"{by_column} = %s")
        params.append(actor_pk)
    if remarks is not None:
        sets.append("remarks = %s")
        params.append(remarks)
    params.append(str(review_pk))
    cur.execute(
        f"UPDATE nss.attendance_review SET {', '.join(sets)} WHERE review_pk = %s",
        params,
    )
    log_audit(cur, action="UPDATE", table_name="attendance_review", record_pk=str(review_pk),
              actor_pk=actor_pk, module="attendance", summary=f"Review status -> {status_code}")


# ═══════════════════════════════════════════════════════════════════════
# 1. Weekly Sangha Puja
# ═══════════════════════════════════════════════════════════════════════

@router.post("/pujas", response_model=PujaResponse, status_code=201)
def create_puja(
    body: CreatePujaRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> PujaResponse:
    """Create a Weekly Sangha Puja event for a Sakha (ATT-003/004/005)."""
    with conn.cursor() as cur:
        require_org_in_scope(cur, user, body.sakha_pk, "create a Weekly Sangha Puja event")
        require_entity(cur, "organization", str(body.sakha_pk), label="Sakha")
        require_sakha_organization(cur, str(body.sakha_pk))  # ATT-004: a puja is held at a Sakha
        try:
            cur.execute(
                """
                INSERT INTO nss.weekly_sangha_puja (sakha_pk, puja_date, remarks, created_by_sangha_sevi_pk)
                VALUES (%s, %s, %s, %s)
                RETURNING weekly_sangha_puja_pk
                """,
                (str(body.sakha_pk), body.puja_date, body.remarks, user.sangha_sevi_pk),
            )
        except Exception as exc:
            if "uq_wsp_sakha_date" in str(exc):
                raise HTTPException(
                    status_code=409,
                    detail="A Weekly Sangha Puja event already exists for this Sakha on this date.",
                )
            raise
        pk = cur.fetchone()[0]
        log_audit(cur, action="CREATE", table_name="weekly_sangha_puja", record_pk=str(pk),
                  actor_pk=user.sangha_sevi_pk, module="attendance", summary="Created Weekly Sangha Puja event")
        cur.execute(
            "SELECT organization_name FROM nss.organization WHERE organization_pk = %s",
            (str(body.sakha_pk),),
        )
        sakha_name = cur.fetchone()[0]
    return PujaResponse(
        weekly_sangha_puja_pk=pk, sakha_pk=body.sakha_pk, sakha_name=sakha_name,
        puja_date=body.puja_date, remarks=body.remarks,
        puja_status="SCHEDULED" if body.puja_date >= date.today() else "CONDUCTED",
        marked_count=0, present_count=0, absent_count=0, excused_count=0,
    )


@router.get("/pujas", response_model=PujaListResponse)
def list_pujas(
    organization_pk: UUID | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_connection),
) -> PujaListResponse:
    """List Weekly Sangha Puja events, scoped to the caller's admin scope."""
    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)
        conditions = ["w.is_active = TRUE"]
        params: list = []
        if allowed is not None:
            if not allowed:
                return PujaListResponse(pujas=[], total=0)
            placeholders = ",".join(["%s"] * len(allowed))
            conditions.append(f"w.sakha_pk IN ({placeholders})")
            params.extend(allowed)
        if organization_pk:
            require_org_in_scope(cur, user, organization_pk, "view this Sakha's puja events")
            conditions.append("w.sakha_pk = %s")
            params.append(str(organization_pk))
        if from_date:
            conditions.append("w.puja_date >= %s")
            params.append(from_date)
        if to_date:
            conditions.append("w.puja_date <= %s")
            params.append(to_date)
        where = "WHERE " + " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) FROM nss.weekly_sangha_puja w {where}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT w.weekly_sangha_puja_pk, w.sakha_pk, o.organization_name, w.puja_date, w.remarks,
                   COUNT(a.attendance_pk) AS marked,
                   COUNT(*) FILTER (WHERE md.value_code = 'PRESENT') AS present_c,
                   COUNT(*) FILTER (WHERE md.value_code = 'ABSENT') AS absent_c,
                   COUNT(*) FILTER (WHERE md.value_code = 'EXCUSED_ABSENCE') AS excused_c
            FROM   nss.weekly_sangha_puja w
            JOIN   nss.organization o ON o.organization_pk = w.sakha_pk
            LEFT JOIN nss.weekly_sangha_puja_attendance a
                   ON a.weekly_sangha_puja_pk = w.weekly_sangha_puja_pk AND a.is_active = TRUE
            LEFT JOIN nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            {where}
            GROUP BY w.weekly_sangha_puja_pk, w.sakha_pk, o.organization_name, w.puja_date, w.remarks
            ORDER BY w.puja_date DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, (page - 1) * page_size],
        )
        today = date.today()
        pujas = [
            PujaResponse(
                weekly_sangha_puja_pk=r[0], sakha_pk=r[1], sakha_name=r[2], puja_date=r[3],
                remarks=r[4], puja_status="SCHEDULED" if r[3] >= today else "CONDUCTED",
                marked_count=r[5], present_count=r[6], absent_count=r[7], excused_count=r[8],
            )
            for r in cur.fetchall()
        ]
    return PujaListResponse(pujas=pujas, total=total)


# ═══════════════════════════════════════════════════════════════════════
# 2. Attendance Marking
# ═══════════════════════════════════════════════════════════════════════

@router.post("/pujas/{weekly_sangha_puja_pk}/attendance", response_model=AttendanceRecordListResponse, status_code=201)
def mark_attendance(
    weekly_sangha_puja_pk: UUID,
    body: MarkAttendanceRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AttendanceRecordListResponse:
    """
    Bulk-mark attendance for one Weekly Sangha Puja (ATT-006/007/008).

    Each item upserts (one row per member per puja, Table Design §9); an
    ABSENT mark immediately runs consecutive-absence detection
    (ATT-009/010/014).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sakha_pk, puja_date FROM nss.weekly_sangha_puja WHERE weekly_sangha_puja_pk = %s AND is_active = TRUE",
            (str(weekly_sangha_puja_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Weekly Sangha Puja event not found.")
        puja_sakha_pk, puja_date = row
        require_org_in_scope(cur, user, puja_sakha_pk, "mark attendance for this Sakha")
        if puja_date > date.today():
            raise HTTPException(
                status_code=422,
                detail="Attendance cannot be marked before the puja date (the event is still SCHEDULED).",
            )

        status_pks = {
            code: get_master_data_pk(cur, "ATTENDANCE_STATUS", code)
            for code in ("PRESENT", "ABSENT", "EXCUSED_ABSENCE")
        }
        result_pks: list[str] = []
        for item in body.records:
            require_entity(cur, "sangha_sevi", str(item.sangha_sevi_pk), label="Member")
            if item.attendance_status_code not in status_pks:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown attendance status: {item.attendance_status_code}",
                )
            # Re-marking an already-EXCUSED record to anything else revokes an
            # approval — same seat requirement as correct_attendance().
            if item.attendance_status_code != "EXCUSED_ABSENCE":
                cur.execute(
                    """
                    SELECT 1 FROM nss.weekly_sangha_puja_attendance a
                    JOIN nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
                    WHERE a.weekly_sangha_puja_pk = %s AND a.sangha_sevi_pk = %s
                      AND a.is_active = TRUE AND md.value_code = 'EXCUSED_ABSENCE'
                    """,
                    (str(weekly_sangha_puja_pk), str(item.sangha_sevi_pk)),
                )
                if cur.fetchone() is not None:
                    _require_review_authority(cur, user, puja_sakha_pk, "approve or revoke an Excused Absence")
            attendance_sakha_pk = str(item.attendance_sakha_pk or puja_sakha_pk)
            if item.attendance_sakha_pk is not None:
                require_sakha_organization(cur, attendance_sakha_pk)  # ATT-028
            cur.execute(
                """
                INSERT INTO nss.weekly_sangha_puja_attendance
                    (weekly_sangha_puja_pk, sangha_sevi_pk, attendance_status_master_data_pk,
                     attendance_sakha_pk, remarks, created_by_sangha_sevi_pk)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (weekly_sangha_puja_pk, sangha_sevi_pk) DO UPDATE SET
                    attendance_status_master_data_pk = EXCLUDED.attendance_status_master_data_pk,
                    attendance_sakha_pk = EXCLUDED.attendance_sakha_pk,
                    remarks = EXCLUDED.remarks,
                    is_active = TRUE, deleted_at = NULL, deleted_by_sangha_sevi_pk = NULL,
                    updated_at = NOW(),
                    updated_by_sangha_sevi_pk = %s
                RETURNING attendance_pk
                """,
                (str(weekly_sangha_puja_pk), str(item.sangha_sevi_pk),
                 status_pks[item.attendance_status_code], attendance_sakha_pk,
                 item.remarks, user.sangha_sevi_pk, user.sangha_sevi_pk),
            )
            attendance_pk = cur.fetchone()[0]
            result_pks.append(str(attendance_pk))
            log_audit(cur, action="CREATE", table_name="weekly_sangha_puja_attendance",
                      record_pk=str(attendance_pk), actor_pk=user.sangha_sevi_pk, module="attendance",
                      summary=f"Marked {item.attendance_status_code}")
            if item.attendance_status_code == "ABSENT":
                _check_and_open_review(cur, item.sangha_sevi_pk, puja_date, user.sangha_sevi_pk)

        records = _fetch_records(cur, attendance_pks=result_pks)
    return AttendanceRecordListResponse(records=records, total=len(records))


@router.patch("/records/{attendance_pk}", response_model=AttendanceRecordResponse)
def correct_attendance(
    attendance_pk: UUID,
    body: CorrectAttendanceRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AttendanceRecordResponse:
    """
    Correct a previously-marked attendance record (Lifecycle §6, "Status
    Correction"). Setting the new status to EXCUSED_ABSENCE is an
    approval action (ATT-008/025) — gated on the real Secretary/President
    seat, same as creating an Exception — and so is changing a record AWAY
    from EXCUSED_ABSENCE (otherwise a marker could silently undo an
    approval); PRESENT<->ABSENT corrections only need ATTENDANCE_MANAGE in
    scope. Original row never deleted (ATT-039).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.sangha_sevi_pk, w.sakha_pk, w.puja_date, cmd.value_code
            FROM   nss.weekly_sangha_puja_attendance a
            JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
            JOIN   nss.master_data cmd ON cmd.master_data_pk = a.attendance_status_master_data_pk
            WHERE  a.attendance_pk = %s AND a.is_active = TRUE
            """,
            (str(attendance_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Attendance record not found.")
        sangha_sevi_pk, sakha_pk, puja_date, current_code = row
        require_org_in_scope(cur, user, sakha_pk, "correct attendance for this Sakha")
        status_pk = get_master_data_pk(cur, "ATTENDANCE_STATUS", body.attendance_status_code, client_supplied=True)
        if "EXCUSED_ABSENCE" in (body.attendance_status_code, current_code):
            _require_review_authority(cur, user, sakha_pk, "approve or revoke an Excused Absence")
        cur.execute(
            """
            UPDATE nss.weekly_sangha_puja_attendance
            SET attendance_status_master_data_pk = %s, remarks = COALESCE(%s, remarks),
                updated_at = NOW(), updated_by_sangha_sevi_pk = %s
            WHERE attendance_pk = %s
            """,
            (status_pk, body.remarks, user.sangha_sevi_pk, str(attendance_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="weekly_sangha_puja_attendance",
                  record_pk=str(attendance_pk), actor_pk=user.sangha_sevi_pk, module="attendance",
                  summary=f"Corrected attendance -> {body.attendance_status_code}")
        if body.attendance_status_code == "ABSENT":
            _check_and_open_review(cur, sangha_sevi_pk, puja_date, user.sangha_sevi_pk)
        records = _fetch_records(cur, attendance_pks=[str(attendance_pk)])
    return records[0]


_RECORD_SELECT_SQL = f"""
    SELECT a.attendance_pk, a.weekly_sangha_puja_pk, w.puja_date, w.sakha_pk,
           a.sangha_sevi_pk, s.sangha_sevi_id, {_person_name_sql('p')},
           md.value_code, md.value_name,
           a.attendance_sakha_pk, aso.organization_name,
           a.remarks, s.organization_pk AS home_organization_pk, ho.organization_name AS home_organization_name,
           mt.value_code AS membership_type_code,
           EXISTS (
               SELECT 1 FROM nss.darshak_attendance_registration dar
               WHERE  dar.sangha_sevi_pk = a.sangha_sevi_pk
                 AND  dar.attending_organization_pk = w.sakha_pk
                 AND  dar.approval_status = 'APPROVED'
                 AND  dar.registration_status = 'ACTIVE'
           ) AS has_approved_darshak_registration,
           aff.local_sakha_erp_id
    FROM   nss.weekly_sangha_puja_attendance a
    JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
    JOIN   nss.sangha_sevi s ON s.sangha_sevi_pk = a.sangha_sevi_pk
    JOIN   nss.person p ON p.person_pk = s.person_pk
    JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
    JOIN   nss.master_data mt ON mt.master_data_pk = s.membership_type_master_data_pk
    JOIN   nss.organization aso ON aso.organization_pk = a.attendance_sakha_pk
    JOIN   nss.organization ho ON ho.organization_pk = s.organization_pk
    -- Mirrors MEMBER_JOINS_SQL's own `aff` join (api/helpers.py) — the
    -- member's current ACTIVE affiliation at their HOME org, for its
    -- local_sakha_erp_id. Written inline rather than importing that
    -- helper wholesale: MEMBER_JOINS_SQL hardcodes alias `ss` for
    -- sangha_sevi, this file uses `s` throughout, and re-aliasing every
    -- existing query here to adopt it would be a much bigger, riskier
    -- change than mirroring one 4-line join.
    LEFT JOIN nss.membership_sakha_affiliation aff
           ON aff.sangha_sevi_pk = s.sangha_sevi_pk
          AND aff.organization_pk = s.organization_pk
          AND aff.effective_to IS NULL
"""


def _fetch_records(cur, *, attendance_pks: list[str]) -> list[AttendanceRecordResponse]:
    if not attendance_pks:
        return []
    placeholders = ",".join(["%s"] * len(attendance_pks))
    cur.execute(f"{_RECORD_SELECT_SQL} WHERE a.attendance_pk IN ({placeholders})", attendance_pks)
    return [_row_to_record(r) for r in cur.fetchall()]


def _row_to_record(r) -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        attendance_pk=r[0], weekly_sangha_puja_pk=r[1], puja_date=r[2], sakha_pk=r[3],
        sangha_sevi_pk=r[4], sangha_sevi_id=r[5], person_name=r[6],
        attendance_status_code=r[7], attendance_status_name=r[8],
        attendance_sakha_pk=r[9], attendance_sakha_name=r[10],
        remarks=r[11],
        home_organization_pk=r[12], home_organization_name=r[13],
        membership_type_code=r[14],
        has_approved_darshak_registration=bool(r[15]),
        local_sakha_erp_id=r[16],
        # Cross-Sakha when the member's HOME Sakha differs from the
        # puja's own Sakha (ATT-026/029/030) — NOT when attendance_sakha_pk
        # differs from the puja's sakha_pk, which are definitionally the
        # same thing (a puja happens at one physical place).
        is_darshak=(str(r[12]) != str(r[3])),
    )


@router.get("/records", response_model=AttendanceRecordListResponse)
def list_records(
    sangha_sevi_pk: UUID | None = Query(None),
    organization_pk: UUID | None = Query(None),
    weekly_sangha_puja_pk: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> AttendanceRecordListResponse:
    """
    Attendance history — for a member, a Sakha, or (self-access) the
    caller's own record. ATTENDANCE_VIEW is required for everything except
    ``sangha_sevi_pk`` equal to the caller's own.
    """
    _require_view_or_self(user, sangha_sevi_pk)
    with conn.cursor() as cur:
        conditions = ["a.is_active = TRUE"]
        params: list = []
        if sangha_sevi_pk:
            # A member may always see their own attendance history even
            # without ATTENDANCE_VIEW's admin scope covering them.
            if str(sangha_sevi_pk) != str(user.sangha_sevi_pk):
                home_org = _member_home_org(cur, sangha_sevi_pk)
                require_org_in_scope(cur, user, home_org, "view this member's attendance")
            conditions.append("a.sangha_sevi_pk = %s")
            params.append(str(sangha_sevi_pk))
        else:
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None:
                if not allowed:
                    return AttendanceRecordListResponse(records=[], total=0)
                placeholders = ",".join(["%s"] * len(allowed))
                conditions.append(f"w.sakha_pk IN ({placeholders})")
                params.extend(allowed)
        if organization_pk:
            require_org_in_scope(cur, user, organization_pk, "view this Sakha's attendance")
            conditions.append("a.attendance_sakha_pk = %s")
            params.append(str(organization_pk))
        if weekly_sangha_puja_pk:
            conditions.append("a.weekly_sangha_puja_pk = %s")
            params.append(str(weekly_sangha_puja_pk))
        where = "WHERE " + " AND ".join(conditions)

        cur.execute(
            f"SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a "
            f"JOIN nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk {where}",
            params,
        )
        total = cur.fetchone()[0]
        cur.execute(
            f"{_RECORD_SELECT_SQL} {where} ORDER BY w.puja_date DESC, a.attendance_pk LIMIT %s OFFSET %s",
            params + [page_size, (page - 1) * page_size],
        )
        records = [_row_to_record(r) for r in cur.fetchall()]
    return AttendanceRecordListResponse(records=records, total=total)


# ═══════════════════════════════════════════════════════════════════════
# 3. Attendance Exceptions
# ═══════════════════════════════════════════════════════════════════════

_EXCEPTION_SELECT_SQL = f"""
    SELECT e.exception_pk, e.sangha_sevi_pk, s.sangha_sevi_id, {_person_name_sql('p')},
           md.value_code, md.value_name, e.from_date, e.to_date,
           e.approved_by_sangha_sevi_pk, {_person_name_sql('ap')}, e.approved_date, e.remarks
    FROM   nss.attendance_exception e
    JOIN   nss.sangha_sevi s ON s.sangha_sevi_pk = e.sangha_sevi_pk
    JOIN   nss.person p ON p.person_pk = s.person_pk
    JOIN   nss.master_data md ON md.master_data_pk = e.exception_type_master_data_pk
    JOIN   nss.sangha_sevi aps ON aps.sangha_sevi_pk = e.approved_by_sangha_sevi_pk
    JOIN   nss.person ap ON ap.person_pk = aps.person_pk
"""


def _row_to_exception(r) -> ExceptionResponse:
    return ExceptionResponse(
        exception_pk=r[0], sangha_sevi_pk=r[1], sangha_sevi_id=r[2], person_name=r[3],
        exception_type_code=r[4], exception_type_name=r[5], from_date=r[6], to_date=r[7],
        approved_by_sangha_sevi_pk=r[8], approved_by_name=r[9], approved_date=r[10], remarks=r[11],
    )


@router.post("/exceptions", response_model=ExceptionResponse, status_code=201)
def create_exception(
    body: CreateExceptionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ExceptionResponse:
    """
    Record an approved attendance exception (ATT-023/024). Approval
    authority is the real Secretary/President seat (ATT-042), not an
    admin permission — ATTENDANCE_VIEW above is only the entry gate so a
    non-attendance role 403s cleanly before the real check runs.
    """
    with conn.cursor() as cur:
        home_org = _member_home_org(cur, body.sangha_sevi_pk)
        _require_review_authority(cur, user, home_org, "approve an attendance exception")
        type_pk = get_master_data_pk(cur, "ATTENDANCE_EXCEPTION_TYPE", body.exception_type_code, client_supplied=True)
        if not user.sangha_sevi_pk:
            raise HTTPException(status_code=403, detail="Only a seated Secretary/President (with their own Sangha Sevi ID) may approve an exception.")
        cur.execute(
            """
            INSERT INTO nss.attendance_exception
                (sangha_sevi_pk, exception_type_master_data_pk, from_date, to_date,
                 approved_by_sangha_sevi_pk, approved_date, remarks, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, CURRENT_DATE, %s, %s)
            RETURNING exception_pk
            """,
            (str(body.sangha_sevi_pk), type_pk, body.from_date, body.to_date,
             user.sangha_sevi_pk, body.remarks, user.sangha_sevi_pk),
        )
        pk = cur.fetchone()[0]
        log_audit(cur, action="CREATE", table_name="attendance_exception", record_pk=str(pk),
                  actor_pk=user.sangha_sevi_pk, module="attendance", summary="Approved attendance exception")
        cur.execute(f"{_EXCEPTION_SELECT_SQL} WHERE e.exception_pk = %s", (str(pk),))
        row = cur.fetchone()
    return _row_to_exception(row)


@router.get("/exceptions", response_model=ExceptionListResponse)
def list_exceptions(
    sangha_sevi_pk: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> ExceptionListResponse:
    """Approved exceptions; ATTENDANCE_VIEW required except for the caller's own (``sangha_sevi_pk`` = self)."""
    _require_view_or_self(user, sangha_sevi_pk)
    with conn.cursor() as cur:
        conditions = ["e.is_active = TRUE"]
        params: list = []
        if sangha_sevi_pk:
            if str(sangha_sevi_pk) != str(user.sangha_sevi_pk):
                home_org = _member_home_org(cur, sangha_sevi_pk)
                require_org_in_scope(cur, user, home_org, "view this member's exceptions")
            conditions.append("e.sangha_sevi_pk = %s")
            params.append(str(sangha_sevi_pk))
        else:
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None:
                if not allowed:
                    return ExceptionListResponse(exceptions=[], total=0)
                placeholders = ",".join(["%s"] * len(allowed))
                conditions.append(
                    f"e.sangha_sevi_pk IN (SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE organization_pk IN ({placeholders}))"
                )
                params.extend(allowed)
        where = "WHERE " + " AND ".join(conditions)
        cur.execute(f"SELECT COUNT(*) FROM nss.attendance_exception e {where}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"{_EXCEPTION_SELECT_SQL} {where} ORDER BY e.from_date DESC LIMIT %s OFFSET %s",
            params + [page_size, (page - 1) * page_size],
        )
        exceptions = [_row_to_exception(r) for r in cur.fetchall()]
    return ExceptionListResponse(exceptions=exceptions, total=total)


# ═══════════════════════════════════════════════════════════════════════
# 4. Attendance Review
# ═══════════════════════════════════════════════════════════════════════

@router.get("/reviews", response_model=ReviewListResponse)
def list_reviews(
    review_status: str | None = Query(None),
    organization_pk: UUID | None = Query(None),
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    conn=Depends(get_connection),
) -> ReviewListResponse:
    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)
        conditions = ["r.is_active = TRUE"]
        params: list = []
        if allowed is not None:
            if not allowed:
                return ReviewListResponse(reviews=[], total=0)
            placeholders = ",".join(["%s"] * len(allowed))
            conditions.append(f"r.organization_pk IN ({placeholders})")
            params.extend(allowed)
        if organization_pk:
            require_org_in_scope(cur, user, organization_pk, "view this Sakha's reviews")
            conditions.append("r.organization_pk = %s")
            params.append(str(organization_pk))
        if review_status:
            conditions.append("md.value_code = %s")
            params.append(review_status)
        where = "WHERE " + " AND ".join(conditions)

        cur.execute(
            f"SELECT COUNT(*) FROM nss.attendance_review r "
            f"JOIN nss.master_data md ON md.master_data_pk = r.review_status_master_data_pk {where}",
            params,
        )
        total = cur.fetchone()[0]
        cur.execute(
            f"{_REVIEW_SELECT_SQL} {where} ORDER BY r.trigger_date DESC LIMIT %s OFFSET %s",
            params + [page_size, (page - 1) * page_size],
        )
        reviews = [_row_to_review(r) for r in cur.fetchall()]
    return ReviewListResponse(reviews=reviews, total=total)


@router.get("/reviews/{review_pk}", response_model=ReviewResponse)
def get_review(
    review_pk: UUID,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_connection),
) -> ReviewResponse:
    with conn.cursor() as cur:
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Attendance Review not found.")
        require_org_in_scope(cur, user, row[4], "view this Attendance Review")
    return _row_to_review(row)


def _load_review_for_action(cur, review_pk) -> tuple[str, str]:
    """Returns (organization_pk, current_status_code) or 404s."""
    cur.execute(
        """
        SELECT r.organization_pk, md.value_code
        FROM   nss.attendance_review r
        JOIN   nss.master_data md ON md.master_data_pk = r.review_status_master_data_pk
        WHERE  r.review_pk = %s AND r.is_active = TRUE
        """,
        (str(review_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Attendance Review not found.")
    return row[0], row[1]


@router.post("/reviews/{review_pk}/close", response_model=ReviewResponse)
def close_review(
    review_pk: UUID, body: ReviewActionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """OPEN -> CLOSED (Secretary), or ESCALATED_TO_PRESIDENT -> CLOSED (President)."""
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        if current not in ("OPEN", "ESCALATED_TO_PRESIDENT"):
            raise HTTPException(status_code=422, detail=f"Cannot close a review in {current} status.")
        president_only = current == "ESCALATED_TO_PRESIDENT"
        _require_review_authority(cur, user, org_pk, "close this review", president_only=president_only)
        _set_review_status(cur, review_pk, "CLOSED", actor_pk=user.sangha_sevi_pk,
                            remarks=body.remarks, by_column="closed_by_sangha_sevi_pk")
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


@router.post("/reviews/{review_pk}/defer", response_model=ReviewResponse)
def defer_review(
    review_pk: UUID, body: ReviewActionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """OPEN -> DEFERRED (Secretary or President)."""
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        if current != "OPEN":
            raise HTTPException(status_code=422, detail=f"Cannot defer a review in {current} status.")
        _require_review_authority(cur, user, org_pk, "defer this review")
        _set_review_status(cur, review_pk, "DEFERRED", actor_pk=user.sangha_sevi_pk,
                            remarks=body.remarks, by_column="deferred_by_sangha_sevi_pk")
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


@router.post("/reviews/{review_pk}/revisit", response_model=ReviewResponse)
def revisit_review(
    review_pk: UUID, body: ReviewActionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """DEFERRED -> OPEN (Secretary or President)."""
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        if current != "DEFERRED":
            raise HTTPException(status_code=422, detail=f"Cannot revisit a review in {current} status.")
        _require_review_authority(cur, user, org_pk, "revisit this review")
        _set_review_status(cur, review_pk, "OPEN", actor_pk=user.sangha_sevi_pk, remarks=body.remarks)
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


@router.post("/reviews/{review_pk}/escalate-to-president", response_model=ReviewResponse)
def escalate_to_president(
    review_pk: UUID, body: ReviewActionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """OPEN -> ESCALATED_TO_PRESIDENT (Secretary only, per the frozen authority matrix)."""
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        if current != "OPEN":
            raise HTTPException(status_code=422, detail=f"Cannot escalate a review in {current} status.")
        # Secretary escalates (ATT-015); the matrix also lets President
        # act everywhere a Secretary can, so this is NOT president_only.
        _require_review_authority(cur, user, org_pk, "escalate this review to the President")
        _set_review_status(cur, review_pk, "ESCALATED_TO_PRESIDENT", actor_pk=user.sangha_sevi_pk,
                            remarks=body.remarks, by_column="escalated_by_sangha_sevi_pk")
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


@router.post("/reviews/{review_pk}/escalate-to-parichalak", response_model=ReviewResponse)
def escalate_to_parichalak(
    review_pk: UUID, body: ReviewActionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """ESCALATED_TO_PRESIDENT -> ESCALATED_TO_PARICHALAK (President only — ATT-016/017)."""
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        if current != "ESCALATED_TO_PRESIDENT":
            raise HTTPException(status_code=422, detail=f"Cannot escalate a review in {current} status.")
        _require_review_authority(cur, user, org_pk, "escalate this review to the Parichalak", president_only=True)
        _set_review_status(cur, review_pk, "ESCALATED_TO_PARICHALAK", actor_pk=user.sangha_sevi_pk,
                            remarks=body.remarks, by_column="escalated_by_sangha_sevi_pk")
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


@router.post("/reviews/{review_pk}/reopen", response_model=ReviewResponse)
def reopen_review(
    review_pk: UUID, body: ReviewActionRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """CLOSED -> OPEN (President only — Secretary cannot reopen, Review Workflow §13)."""
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        if current != "CLOSED":
            raise HTTPException(status_code=422, detail=f"Cannot reopen a review in {current} status.")
        _require_review_authority(cur, user, org_pk, "reopen this review", president_only=True)
        _set_review_status(cur, review_pk, "OPEN", actor_pk=user.sangha_sevi_pk, remarks=body.remarks)
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


@router.post("/reviews/{review_pk}/override", response_model=ReviewResponse)
def override_review(
    review_pk: UUID, body: ReviewOverrideRequest,
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_write_connection),
) -> ReviewResponse:
    """
    President overrides a Secretary decision to any status (Review
    Workflow §12 — President only). The previous status is preserved in
    the audit log detail, and remarks record the reason, per §12's
    "Previous Decision / President Decision / Reason" requirement.
    """
    with conn.cursor() as cur:
        org_pk, current = _load_review_for_action(cur, review_pk)
        _require_review_authority(cur, user, org_pk, "override this review", president_only=True)
        status_pk = get_master_data_pk(cur, "ATTENDANCE_REVIEW_STATUS", body.new_status_code, client_supplied=True)
        cur.execute(
            """
            UPDATE nss.attendance_review
            SET review_status_master_data_pk = %s, remarks = %s,
                updated_at = NOW(), updated_by_sangha_sevi_pk = %s
            WHERE review_pk = %s
            """,
            (status_pk, body.reason, user.sangha_sevi_pk, str(review_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="attendance_review", record_pk=str(review_pk),
                  actor_pk=user.sangha_sevi_pk, module="attendance",
                  summary=f"President override: {current} -> {body.new_status_code}",
                  detail={"previous_status": current, "new_status": body.new_status_code, "reason": body.reason})
        cur.execute(f"{_REVIEW_SELECT_SQL} WHERE r.review_pk = %s", (str(review_pk),))
        row = cur.fetchone()
    return _row_to_review(row)


# ═══════════════════════════════════════════════════════════════════════
# 5. Watch List (Review Workflow §21/§22/§23) and Stats (owner ask, 2026-10-27)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/watch-list", response_model=WatchListResponse)
def watch_list(
    organization_pk: UUID | None = Query(None),
    threshold: int = Query(2, ge=1, le=2, description="Consecutive ABSENT count (lifecycle doc §24: fixed at 2, not configurable past that)"),
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_connection),
) -> WatchListResponse:
    """
    Members with >= *threshold* (default 2) consecutive ordinary ABSENT
    records (absences covered by an approved exception don't count,
    ATT-025), most recent puja first. Members who already have a
    non-CLOSED Attendance Review are excluded — they are past the
    3-absence trigger and tracked in the review queue instead.
    """
    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)
        conditions = ["ss.is_active = TRUE"]
        params: list = []
        if allowed is not None:
            if not allowed:
                return WatchListResponse(items=[], total=0)
            placeholders = ",".join(["%s"] * len(allowed))
            conditions.append(f"ss.organization_pk IN ({placeholders})")
            params.extend(allowed)
        if organization_pk:
            require_org_in_scope(cur, user, organization_pk, "view this Sakha's watch list")
            conditions.append("ss.organization_pk = %s")
            params.append(str(organization_pk))
        where = "WHERE " + " AND ".join(conditions)

        # Per member: their last `threshold` puja records, all ABSENT.
        cur.execute(
            f"""
            WITH ranked AS (
                SELECT a.sangha_sevi_pk, w.puja_date, {_EFFECTIVE_STATUS_SQL} AS status_code,
                       ROW_NUMBER() OVER (PARTITION BY a.sangha_sevi_pk ORDER BY w.puja_date DESC) AS rn
                FROM   nss.weekly_sangha_puja_attendance a
                JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
                JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
                JOIN   nss.sangha_sevi ss ON ss.sangha_sevi_pk = a.sangha_sevi_pk
                {where}
                AND a.is_active = TRUE
                AND NOT {_HAS_OPEN_REVIEW_SQL % 'a.sangha_sevi_pk'}
            ),
            consecutive AS (
                SELECT sangha_sevi_pk, MAX(puja_date) AS last_puja_date
                FROM   ranked
                WHERE  rn <= %s
                GROUP BY sangha_sevi_pk
                HAVING COUNT(*) = %s AND COUNT(*) FILTER (WHERE status_code = 'ABSENT') = %s
            )
            SELECT c.sangha_sevi_pk, s.sangha_sevi_id, {_person_name_sql('p')},
                   s.organization_pk, o.organization_name, c.last_puja_date
            FROM   consecutive c
            JOIN   nss.sangha_sevi s ON s.sangha_sevi_pk = c.sangha_sevi_pk
            JOIN   nss.person p ON p.person_pk = s.person_pk
            JOIN   nss.organization o ON o.organization_pk = s.organization_pk
            ORDER BY c.last_puja_date DESC
            """,
            params + [threshold, threshold, threshold],
        )
        items = [
            WatchListItem(
                sangha_sevi_pk=r[0], sangha_sevi_id=r[1], person_name=r[2],
                organization_pk=r[3], organization_name=r[4], current_consecutive_absences=threshold,
                last_puja_date=r[5],
            )
            for r in cur.fetchall()
        ]
    return WatchListResponse(items=items, total=len(items))


@router.get("/stats/organizations/{organization_pk}", response_model=OrgAttendanceStatsResponse)
def organization_stats(
    organization_pk: UUID,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_connection),
) -> OrgAttendanceStatsResponse:
    """Attendance percentage for a Sakha (owner ask 2026-10-27, i)."""
    with conn.cursor() as cur:
        require_org_in_scope(cur, user, organization_pk, "view this Sakha's attendance statistics")
        require_entity(cur, "organization", str(organization_pk), label="Organization")
        cur.execute(
            "SELECT organization_name FROM nss.organization WHERE organization_pk = %s",
            (str(organization_pk),),
        )
        org_name = cur.fetchone()[0]

        conditions = ["w.sakha_pk = %s", "a.is_active = TRUE"]
        params: list = [str(organization_pk)]
        if from_date:
            conditions.append("w.puja_date >= %s")
            params.append(from_date)
        if to_date:
            conditions.append("w.puja_date <= %s")
            params.append(to_date)
        where = "WHERE " + " AND ".join(conditions)

        cur.execute(
            f"""
            SELECT COUNT(DISTINCT w.weekly_sangha_puja_pk),
                   COUNT(*),
                   COUNT(*) FILTER (WHERE md.value_code = 'PRESENT'),
                   COUNT(*) FILTER (WHERE md.value_code = 'ABSENT'),
                   COUNT(*) FILTER (WHERE md.value_code = 'EXCUSED_ABSENCE')
            FROM   nss.weekly_sangha_puja_attendance a
            JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
            JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            {where}
            """,
            params,
        )
        total_pujas, total_records, present_c, absent_c, excused_c = cur.fetchone()
        denom = present_c + absent_c
        pct = round(present_c / denom * 100, 1) if denom else None
    return OrgAttendanceStatsResponse(
        organization_pk=organization_pk, organization_name=org_name,
        period_from=from_date, period_to=to_date, total_puja_events=total_pujas,
        total_records=total_records, present_count=present_c, absent_count=absent_c,
        excused_count=excused_c, attendance_percentage=pct,
    )


def _member_recent_statuses(cur, organization_pk: UUID, *, n: int = 3) -> dict:
    """
    Per-member most recent *n* puja statuses at *organization_pk*'s own
    Weekly Sangha Puja history, plus the single most recent record's
    remark — the shape the Top/Full Attendance tables render (owner
    correction 2026-10-28: "status is last 3 attendance, remarks is for
    [the] latest ... attendance remark [only]"). Same ranked-CTE pattern
    as list_watch_list above, scoped to one Sakha instead of ABSENT runs.

    Returns {str(sangha_sevi_pk): {"recent": [{"puja_date", "attendance_
    status_code"}, ...] (most-recent-first, <= n items), "latest_remarks":
    str | None}}.
    """
    cur.execute(
        """
        WITH ranked AS (
            SELECT a.sangha_sevi_pk, w.puja_date, md.value_code AS status_code, a.remarks,
                   ROW_NUMBER() OVER (PARTITION BY a.sangha_sevi_pk ORDER BY w.puja_date DESC) AS rn
            FROM   nss.weekly_sangha_puja_attendance a
            JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
            JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            WHERE  w.sakha_pk = %s AND w.is_active = TRUE AND a.is_active = TRUE
        )
        SELECT sangha_sevi_pk, puja_date, status_code, remarks, rn
        FROM   ranked
        WHERE  rn <= %s
        ORDER BY sangha_sevi_pk, rn
        """,
        (str(organization_pk), n),
    )
    out: dict = {}
    for sangha_sevi_pk, puja_date, status_code, remarks, rn in cur.fetchall():
        entry = out.setdefault(str(sangha_sevi_pk), {"recent": [], "latest_remarks": None})
        entry["recent"].append({"puja_date": puja_date, "attendance_status_code": status_code})
        if rn == 1:
            entry["latest_remarks"] = remarks
    return out


@router.get("/stats/organizations/{organization_pk}/members", response_model=OrgMemberAttendanceListResponse)
def organization_member_attendance(
    organization_pk: UUID,
    sort: str = Query("desc", pattern="^(asc|desc)$", description="'desc' (highest % first, the leaderboard default) or 'asc'"),
    limit: int = Query(5, ge=1, le=MAX_LIMIT, description="Max rows — 5 for the dashboard card, omit/raise for the full list page"),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(require_permission("ATTENDANCE_VIEW")),
    conn=Depends(get_connection),
) -> OrgMemberAttendanceListResponse:
    """
    Per-member attendance leaderboard for one Sakha (owner ask 2026-10-28):
    every active HOME member of *organization_pk*, with their own
    present/(present+absent) percentage at THIS Sakha's own Weekly Sangha
    Puja history — same denominator convention as organization_stats
    (EXCUSED_ABSENCE excluded, ATT-008). Backs both the Sakha dashboard's
    "Top Attendance" card (limit=5) and its "View Full Attendance" page
    (same endpoint, no limit) — one query, two presentations, identical
    columns (owner correction 2026-10-28): ID/Name/Type/Status(last 3
    puja attendances)/Remarks(latest puja only)/Attendance %.

    A member with zero attendance records still appears (attendance_
    percentage=None, sorted last) — "all Sangha Sevis" per the owner's ask,
    not just those who have ever been marked.
    """
    with conn.cursor() as cur:
        require_org_in_scope(cur, user, organization_pk, "view this Sakha's member attendance")
        require_entity(cur, "organization", str(organization_pk), label="Organization")

        count_sql = "SELECT COUNT(*) FROM nss.sangha_sevi s WHERE s.organization_pk = %s AND s.is_active = TRUE"
        cur.execute(count_sql, (str(organization_pk),))
        total = cur.fetchone()[0]

        order_dir = "ASC" if sort == "asc" else "DESC"
        cur.execute(
            f"""
            SELECT s.sangha_sevi_pk, s.sangha_sevi_id, {_person_name_sql('p')}, aff.local_sakha_erp_id,
                   mt.value_code AS membership_type_code,
                   COUNT(a.attendance_pk) AS total_records,
                   COUNT(*) FILTER (WHERE md.value_code = 'PRESENT') AS present_c,
                   COUNT(*) FILTER (WHERE md.value_code = 'ABSENT') AS absent_c,
                   COUNT(*) FILTER (WHERE md.value_code = 'EXCUSED_ABSENCE') AS excused_c
            FROM   nss.sangha_sevi s
            JOIN   nss.person p ON p.person_pk = s.person_pk
            JOIN   nss.master_data mt ON mt.master_data_pk = s.membership_type_master_data_pk
            LEFT JOIN nss.membership_sakha_affiliation aff
                   ON aff.sangha_sevi_pk = s.sangha_sevi_pk
                  AND aff.organization_pk = s.organization_pk
                  AND aff.effective_to IS NULL
            LEFT JOIN nss.weekly_sangha_puja_attendance a
                   ON a.sangha_sevi_pk = s.sangha_sevi_pk AND a.is_active = TRUE
            LEFT JOIN nss.weekly_sangha_puja w
                   ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
                  AND w.sakha_pk = s.organization_pk AND w.is_active = TRUE
            LEFT JOIN nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            WHERE  s.organization_pk = %s AND s.is_active = TRUE
            GROUP BY s.sangha_sevi_pk, s.sangha_sevi_id, p.first_name, p.middle_name, p.last_name,
                     aff.local_sakha_erp_id, mt.value_code
            ORDER BY
                CASE WHEN COUNT(*) FILTER (WHERE md.value_code IN ('PRESENT', 'ABSENT')) > 0
                     THEN 100.0 * COUNT(*) FILTER (WHERE md.value_code = 'PRESENT')
                          / COUNT(*) FILTER (WHERE md.value_code IN ('PRESENT', 'ABSENT'))
                     ELSE NULL END {order_dir} NULLS LAST,
                {_person_name_sql('p')}
            LIMIT %s OFFSET %s
            """,
            (str(organization_pk), limit, offset),
        )
        rows = cur.fetchall()
        recent_map = _member_recent_statuses(cur, organization_pk, n=3)
        members = []
        for r in rows:
            present_c, absent_c = r[6], r[7]
            denom = present_c + absent_c
            pct = round(present_c / denom * 100, 1) if denom else None
            recent = recent_map.get(str(r[0]), {})
            members.append(OrgMemberAttendanceResponse(
                sangha_sevi_pk=r[0], sangha_sevi_id=r[1], person_name=r[2], local_sakha_erp_id=r[3],
                membership_type_code=r[4],
                total_records=r[5], present_count=present_c, absent_count=absent_c,
                excused_count=r[8], attendance_percentage=pct,
                recent_statuses=recent.get("recent", []),
                latest_remarks=recent.get("latest_remarks"),
            ))
    return OrgMemberAttendanceListResponse(members=members, total=total)


@router.get("/stats/members/{sangha_sevi_pk}", response_model=MemberAttendanceStatsResponse)
def member_stats(
    sangha_sevi_pk: UUID,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberAttendanceStatsResponse:
    """Attendance percentage for a member (owner ask 2026-10-27, ii); a member may read their own."""
    _require_view_or_self(user, sangha_sevi_pk)
    with conn.cursor() as cur:
        if str(sangha_sevi_pk) != str(user.sangha_sevi_pk):
            home_org = _member_home_org(cur, sangha_sevi_pk)
            require_org_in_scope(cur, user, home_org, "view this member's attendance statistics")
        cur.execute(
            f"SELECT s.sangha_sevi_id, {_person_name_sql('p')} "
            f"FROM nss.sangha_sevi s JOIN nss.person p ON p.person_pk = s.person_pk "
            f"WHERE s.sangha_sevi_pk = %s",
            (str(sangha_sevi_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Member not found.")
        sangha_sevi_id, person_name = row

        conditions = ["a.sangha_sevi_pk = %s", "a.is_active = TRUE"]
        params: list = [str(sangha_sevi_pk)]
        if from_date:
            conditions.append("w.puja_date >= %s")
            params.append(from_date)
        if to_date:
            conditions.append("w.puja_date <= %s")
            params.append(to_date)
        where = "WHERE " + " AND ".join(conditions)
        cur.execute(
            f"""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE md.value_code = 'PRESENT'),
                   COUNT(*) FILTER (WHERE md.value_code = 'ABSENT'),
                   COUNT(*) FILTER (WHERE md.value_code = 'EXCUSED_ABSENCE')
            FROM   nss.weekly_sangha_puja_attendance a
            JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
            JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            {where}
            """,
            params,
        )
        total_records, present_c, absent_c, excused_c = cur.fetchone()
        denom = present_c + absent_c
        pct = round(present_c / denom * 100, 1) if denom else None

        # Current consecutive ABSENT streak, most recent first.
        cur.execute(
            f"""
            SELECT {_EFFECTIVE_STATUS_SQL}
            FROM   nss.weekly_sangha_puja_attendance a
            JOIN   nss.weekly_sangha_puja w ON w.weekly_sangha_puja_pk = a.weekly_sangha_puja_pk
            JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
            WHERE  a.sangha_sevi_pk = %s AND a.is_active = TRUE
            ORDER BY w.puja_date DESC
            """,
            (str(sangha_sevi_pk),),
        )
        streak = 0
        for (code,) in cur.fetchall():
            if code == "ABSENT":
                streak += 1
            else:
                break
    return MemberAttendanceStatsResponse(
        sangha_sevi_pk=sangha_sevi_pk, sangha_sevi_id=sangha_sevi_id, person_name=person_name,
        period_from=from_date, period_to=to_date, total_records=total_records,
        present_count=present_c, absent_count=absent_c, excused_count=excused_c,
        attendance_percentage=pct, current_consecutive_absences=streak,
    )
