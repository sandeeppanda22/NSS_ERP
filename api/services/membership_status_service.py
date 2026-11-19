"""
NSS ERP — Membership Status change rules (owner decisions 2026-11-18).

A member's Membership Status is one of ACTIVE, SUSPENDED, LAPSED, EXPELLED,
DECEASED ("Resigned" is a matter of a post, not of membership). A change is
REQUESTED by a Governing Body member (the member's own Sakha GB or the Kendra
GB) or by an admin whose scope covers the member, and APPROVED by the
Parichalak — in the Parichalak's absence the live acting delegate on that seat
(seat_service already counts acting cover) — or the Kendra President.
Authority is the LIVE seat, never a permission or NSS_ERP_ADMIN (same model as
the Sakha re-parent chain); the requester never decides their own request and
nobody requests or decides a change to their own membership.

One home for: the status list, the seat/authority checks, the attendance
block, and the single transaction that applies an approved change (status,
history row, journey event). The router only validates and calls these.
"""

from datetime import date, datetime, time, timezone

from fastapi import HTTPException, status

from api.services.rbac_service import LOGIN_BARRED_STATUS_CODES, UserContext, org_in_scope
from api.services.seat_service import (
    _SUBSTANTIVE_SEAT_SQL,
    find_body_master_pk,
    person_holds_seat,
)

# The statuses a membership can hold, in display order. The Member Directory filter
# reads the same list from the frontend (NSS.MEMBERSHIP_STATUS_FILTER) — keep both in step
# (tests/api/test_membership_status_service.py checks it).
MEMBERSHIP_STATUS_CODES = ("ACTIVE", "SUSPENDED", "LAPSED", "EXPELLED", "DECEASED")

# A member in one of these cannot be marked at Sangha Puja and cannot log in (owner
# 2026-11-18). One list: rbac_service.LOGIN_BARRED_STATUS_CODES.
ATTENDANCE_BLOCKED_STATUS_CODES = LOGIN_BARRED_STATUS_CODES

# Death is final: no further status change once recorded.
TERMINAL_STATUS_CODES = ("DECEASED",)

APPROVER_POSITION_CODES = ("PARICHALAK", "PRESIDENT")


def _kendra_body_pk(cur):
    return find_body_master_pk(cur, "KENDRA_GOVERNING_BODY", None)


def _on_governing_body(cur, person_pk, body_pks) -> bool:
    """True if person_pk holds any substantive seat (any position, MEMBER
    included) on one of body_pks."""
    body_pks = [str(b) for b in body_pks if b]
    if person_pk is None or not body_pks:
        return False
    cur.execute(
        f"""
        SELECT 1 FROM nss.body_member_assignment a
        WHERE a.body_master_pk = ANY(%s::uuid[]) AND a.person_pk = %s AND {_SUBSTANTIVE_SEAT_SQL}
        LIMIT 1
        """,
        (body_pks, str(person_pk)),
    )
    return cur.fetchone() is not None


def requester_route(cur, user: UserContext, home_org_pk) -> str | None:
    """How the caller may START a status change for a member whose home Sakha
    is home_org_pk: 'GOVERNING_BODY' (member of that Sakha's GB or of the Kendra
    GB), 'ADMIN' (MEMBERSHIP_MANAGE with the Sakha inside their admin scope) or
    None. The seat route is tried first so the record shows the stronger basis."""
    bodies = [find_body_master_pk(cur, "SAKHA_GOVERNING_BODY", home_org_pk), _kendra_body_pk(cur)]
    if _on_governing_body(cur, user.person_pk, bodies):
        return "GOVERNING_BODY"
    if user.has_permission("MEMBERSHIP_MANAGE") and org_in_scope(cur, user, home_org_pk):
        return "ADMIN"
    return None


def can_decide(cur, user: UserContext) -> bool:
    """True if the caller is the live Parichalak or Kendra President (acting
    cover counts). No permission and no NSS_ERP_ADMIN override."""
    kendra = _kendra_body_pk(cur)
    if kendra is None:
        return False
    return any(person_holds_seat(cur, user.person_pk, kendra, code) for code in APPROVER_POSITION_CODES)


def attendance_blocked_members(cur, sangha_sevi_pks) -> list[dict]:
    """Of sangha_sevi_pks, the members whose Membership Status bars them from
    Sangha Puja (SUSPENDED / EXPELLED): [{sangha_sevi_pk, sangha_sevi_id, status_code}]."""
    pks = [str(p) for p in sangha_sevi_pks]
    if not pks:
        return []
    cur.execute(
        """
        SELECT ss.sangha_sevi_pk::text, ss.sangha_sevi_id, ms.value_code
        FROM nss.sangha_sevi ss
        JOIN nss.master_data ms ON ms.master_data_pk = ss.membership_status_master_data_pk
        WHERE ss.sangha_sevi_pk = ANY(%s::uuid[]) AND ms.value_code = ANY(%s)
        """,
        (pks, list(ATTENDANCE_BLOCKED_STATUS_CODES)),
    )
    return [{"sangha_sevi_pk": r[0], "sangha_sevi_id": r[1], "status_code": r[2]} for r in cur.fetchall()]


def apply_status_change(cur, *, request_pk, sangha_sevi_pk, from_status_pk, to_status_pk,
                        effective_date: date, reason: str, actor_pk, to_status_code: str) -> None:
    """The single write of an APPROVED change: the member's current status, the
    status-history timeline (close the open row, open the new one) and a journey
    event. Locks the member row and refuses (409) if the status moved since the
    request was filed."""
    cur.execute(
        "SELECT membership_status_master_data_pk FROM nss.sangha_sevi "
        "WHERE sangha_sevi_pk = %s AND is_active = TRUE FOR UPDATE",
        (str(sangha_sevi_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if str(row[0]) != str(from_status_pk):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The member's status changed after this request was filed; reject it and raise a new one.",
        )
    effective_at = datetime.combine(effective_date, time.min, tzinfo=timezone.utc)
    cur.execute(
        "UPDATE nss.membership_status_history SET effective_to = %s "
        "WHERE sangha_sevi_pk = %s AND effective_to IS NULL AND effective_from <= %s",
        (effective_at, str(sangha_sevi_pk), effective_at),
    )
    cur.execute(
        """
        INSERT INTO nss.membership_status_history
            (sangha_sevi_pk, membership_status_master_data_pk, effective_from, reason, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (str(sangha_sevi_pk), str(to_status_pk), effective_at, reason, actor_pk),
    )
    cur.execute(
        """
        UPDATE nss.sangha_sevi
           SET membership_status_master_data_pk = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
         WHERE sangha_sevi_pk = %s
        """,
        (str(to_status_pk), actor_pk, str(sangha_sevi_pk)),
    )
    cur.execute(
        """
        INSERT INTO nss.membership_journey_event
            (sangha_sevi_pk, event_type, event_date, event_reference, remarks, created_by_sangha_sevi_pk)
        VALUES (%s, 'STATUS_CHANGE', %s, %s, %s, %s)
        """,
        (str(sangha_sevi_pk), effective_date, str(request_pk), f"{to_status_code}: {reason}", actor_pk),
    )
