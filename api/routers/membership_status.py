"""
NSS ERP — Membership Status change requests (owner decisions 2026-11-18).

  GET  /api/v1/membership-status/members/{sangha_sevi_pk}            — status, history, pending request, caller's rights
  POST /api/v1/membership-status/members/{sangha_sevi_pk}/requests  — ask for a status change
  GET  /api/v1/membership-status/requests                            — requests I filed / waiting for my decision
  POST /api/v1/membership-status/requests/{pk}/approve               — Parichalak (or acting) / Kendra President
  POST /api/v1/membership-status/requests/{pk}/reject
  POST /api/v1/membership-status/requests/{pk}/cancel                — the requester

Statuses: ACTIVE, SUSPENDED, LAPSED, EXPELLED, DECEASED. A Governing Body member
(the member's Sakha GB or the Kendra GB) or an admin in scope files the request;
the live Parichalak seat (acting cover counts) or the Kendra President decides it.
All endpoints are login-only; authority is the live seat / scope, never a permission
alone. Rules and the one transaction that applies an approval:
api/services/membership_status_service.py. Suspended / Expelled / Deceased members cannot be
marked at Sangha Puja (attendance.py).
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.helpers import get_master_data_pk, log_audit, rows_to_models
from api.schemas.membership_status import (
    MemberStatusOverview,
    StatusChangeCreate,
    StatusChangeRequestListResponse,
    StatusChangeRequestResponse,
    StatusDecision,
    StatusHistoryItem,
    StatusRejection,
)
from api.services import membership_status_service as svc
from api.services.rbac_service import UserContext, org_in_scope

router = APIRouter(prefix="/api/v1/membership-status", tags=["membership-status"])

_REQUEST_SELECT = """
    SELECT r.membership_status_change_request_pk, r.sangha_sevi_pk, ss.sangha_sevi_id,
           CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS member_name,
           o.organization_name,
           fs.value_code AS from_status_code, fs.value_name AS from_status_name,
           ts.value_code AS to_status_code, ts.value_name AS to_status_name,
           r.effective_date, r.reason, r.requested_via, r.request_status,
           (SELECT CONCAT_WS(' ', rp.first_name, rp.last_name)
              FROM nss.sangha_sevi rss JOIN nss.person rp ON rp.person_pk = rss.person_pk
             WHERE rss.sangha_sevi_pk = r.requested_by_sangha_sevi_pk) AS requested_by_name,
           (SELECT CONCAT_WS(' ', dp.first_name, dp.last_name)
              FROM nss.sangha_sevi dss JOIN nss.person dp ON dp.person_pk = dss.person_pk
             WHERE dss.sangha_sevi_pk = r.decided_by_sangha_sevi_pk) AS decided_by_name,
           r.decided_at, r.decision_remarks, r.created_at
    FROM nss.membership_status_change_request r
    JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = r.sangha_sevi_pk
    JOIN nss.person p ON p.person_pk = ss.person_pk
    LEFT JOIN nss.organization o ON o.organization_pk = ss.organization_pk
    JOIN nss.master_data fs ON fs.master_data_pk = r.from_status_master_data_pk
    JOIN nss.master_data ts ON ts.master_data_pk = r.to_status_master_data_pk
"""


def _require_person(user: UserContext) -> None:
    if not user.person_pk:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No person record for this account.")


def _member_row(cur, sangha_sevi_pk):
    cur.execute(
        """
        SELECT ss.sangha_sevi_pk, ss.person_pk, ss.organization_pk, ss.membership_status_master_data_pk,
               ms.value_code, ms.value_name
        FROM nss.sangha_sevi ss
        JOIN nss.master_data ms ON ms.master_data_pk = ss.membership_status_master_data_pk
        WHERE ss.sangha_sevi_pk = %s AND ss.is_active = TRUE
        """,
        (str(sangha_sevi_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found.")
    return row


def _request_by_pk(cur, request_pk) -> StatusChangeRequestResponse | None:
    cur.execute(_REQUEST_SELECT + " WHERE r.membership_status_change_request_pk = %s AND r.is_active = TRUE",
                (str(request_pk),))
    rows = rows_to_models(cur, StatusChangeRequestResponse)
    return rows[0] if rows else None


@router.get("/members/{sangha_sevi_pk}", response_model=MemberStatusOverview)
def member_status_overview(
    sangha_sevi_pk: UUID,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberStatusOverview:
    """The member's current status, status history, any pending request and what the
    caller may do. Visible to the member, GB members / approvers, and admins with
    MEMBERSHIP_VIEW in scope; anyone else gets 404."""
    with conn.cursor() as cur:
        _, person_pk, org_pk, _, code, name = _member_row(cur, sangha_sevi_pk)
        route = svc.requester_route(cur, user, org_pk)
        decider = svc.can_decide(cur, user)
        is_self = str(person_pk) == str(user.person_pk)
        sees = is_self or route or decider or (user.has_permission("MEMBERSHIP_VIEW") and org_in_scope(cur, user, org_pk))
        if not sees:
            raise HTTPException(status_code=404, detail="Member not found.")
        cur.execute(
            _REQUEST_SELECT + " WHERE r.sangha_sevi_pk = %s AND r.request_status = 'PENDING' AND r.is_active = TRUE",
            (str(sangha_sevi_pk),),
        )
        pending = rows_to_models(cur, StatusChangeRequestResponse)
        cur.execute(
            """
            SELECT md.value_code AS status_code, md.value_name AS status_name,
                   h.effective_from, h.effective_to, h.reason
            FROM nss.membership_status_history h
            JOIN nss.master_data md ON md.master_data_pk = h.membership_status_master_data_pk
            WHERE h.sangha_sevi_pk = %s ORDER BY h.effective_from DESC
            """,
            (str(sangha_sevi_pk),),
        )
        history = rows_to_models(cur, StatusHistoryItem)
    allowed = [] if code in svc.TERMINAL_STATUS_CODES else [c for c in svc.MEMBERSHIP_STATUS_CODES if c != code]
    return MemberStatusOverview(
        sangha_sevi_pk=sangha_sevi_pk, current_status_code=code, current_status_name=name,
        pending_request=pending[0] if pending else None, history=history,
        can_request=bool(route) and not is_self and not pending and bool(allowed),
        can_decide=decider and not is_self, allowed_status_codes=allowed,
    )


@router.post("/members/{sangha_sevi_pk}/requests", response_model=StatusChangeRequestResponse, status_code=201)
def create_status_request(
    sangha_sevi_pk: UUID,
    body: StatusChangeCreate,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> StatusChangeRequestResponse:
    _require_person(user)
    if body.to_status_code not in svc.MEMBERSHIP_STATUS_CODES:
        raise HTTPException(status_code=422, detail=f"Membership status must be one of {', '.join(svc.MEMBERSHIP_STATUS_CODES)}.")
    if body.effective_date > date.today():
        raise HTTPException(status_code=422, detail="The effective date cannot be in the future.")
    with conn.cursor() as cur:
        _, person_pk, org_pk, from_pk, from_code, _ = _member_row(cur, sangha_sevi_pk)
        route = svc.requester_route(cur, user, org_pk)
        if route is None:
            raise HTTPException(status_code=403, detail="Only a Governing Body member (the member's Sakha or the Kendra) "
                                                        "or an admin in scope can request a membership status change.")
        if str(person_pk) == str(user.person_pk):
            raise HTTPException(status_code=403, detail="You cannot request a change to your own membership status.")
        if from_code in svc.TERMINAL_STATUS_CODES:
            raise HTTPException(status_code=422, detail="A deceased member's status cannot be changed.")
        if body.to_status_code == from_code:
            raise HTTPException(status_code=422, detail="The member already has this status.")
        cur.execute(
            "SELECT 1 FROM nss.membership_status_change_request WHERE sangha_sevi_pk = %s "
            "AND request_status = 'PENDING' AND is_active = TRUE", (str(sangha_sevi_pk),))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="A status change for this member is already waiting for approval.")
        to_pk = get_master_data_pk(cur, "STATUS", body.to_status_code)
        cur.execute(
            """
            INSERT INTO nss.membership_status_change_request
                (sangha_sevi_pk, from_status_master_data_pk, to_status_master_data_pk, effective_date, reason,
                 requested_via, requested_by_sangha_sevi_pk, requested_by_user_account_pk, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING membership_status_change_request_pk
            """,
            (str(sangha_sevi_pk), str(from_pk), str(to_pk), body.effective_date, body.reason.strip(), route,
             user.actor_pk, str(user.user_account_pk), user.actor_pk),
        )
        request_pk = cur.fetchone()[0]
        log_audit(cur, action="CREATE", table_name="membership_status_change_request", record_pk=str(request_pk),
                  actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk), module="membership_status",
                  summary=f"Requested membership status {from_code} -> {body.to_status_code} ({route})")
        return _request_by_pk(cur, request_pk)


@router.get("/requests", response_model=StatusChangeRequestListResponse)
def list_status_requests(
    awaiting_my_decision: bool = Query(False, description="Pending requests the caller may approve or reject"),
    request_status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED|CANCELLED)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> StatusChangeRequestListResponse:
    """Without a filter: the requests I filed. With awaiting_my_decision: every PENDING
    request, only if I am the live Parichalak / Kendra President, minus any about my own membership."""
    _require_person(user)
    where = ["r.is_active = TRUE"]
    params: list = []
    with conn.cursor() as cur:
        if awaiting_my_decision:
            if not svc.can_decide(cur, user):
                return StatusChangeRequestListResponse(requests=[], total=0)
            where += ["r.request_status = 'PENDING'", "ss.person_pk <> %s"]
            params.append(str(user.person_pk))
        else:
            where.append("r.requested_by_sangha_sevi_pk = %s")
            params.append(user.actor_pk)
            if request_status:
                where.append("r.request_status = %s")
                params.append(request_status)
        clause = " WHERE " + " AND ".join(where)
        cur.execute("SELECT count(*) FROM nss.membership_status_change_request r "
                    "JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = r.sangha_sevi_pk" + clause, tuple(params))
        total = cur.fetchone()[0]
        cur.execute(_REQUEST_SELECT + clause + " ORDER BY r.created_at DESC LIMIT %s OFFSET %s",
                    tuple(params + [page_size, (page - 1) * page_size]))
        rows = rows_to_models(cur, StatusChangeRequestResponse)
    return StatusChangeRequestListResponse(requests=rows, total=total)


def _pending_for_update(cur, request_pk):
    cur.execute(
        """
        SELECT r.sangha_sevi_pk, r.from_status_master_data_pk, r.to_status_master_data_pk, r.effective_date,
               r.reason, r.requested_by_sangha_sevi_pk, ss.person_pk, ts.value_code
        FROM nss.membership_status_change_request r
        JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = r.sangha_sevi_pk
        JOIN nss.master_data ts ON ts.master_data_pk = r.to_status_master_data_pk
        WHERE r.membership_status_change_request_pk = %s AND r.is_active = TRUE FOR UPDATE OF r
        """,
        (str(request_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Status change request not found.")
    cur.execute("SELECT request_status FROM nss.membership_status_change_request "
                "WHERE membership_status_change_request_pk = %s", (str(request_pk),))
    if cur.fetchone()[0] != "PENDING":
        raise HTTPException(status_code=409, detail="This request has already been decided.")
    return row


def _decide(cur, user: UserContext, request_pk, new_status: str, remarks: str | None) -> None:
    cur.execute(
        """
        UPDATE nss.membership_status_change_request
           SET request_status = %s, decided_at = NOW(), decided_by_sangha_sevi_pk = %s, decision_remarks = %s,
               updated_at = NOW(), updated_by_sangha_sevi_pk = %s
         WHERE membership_status_change_request_pk = %s
        """,
        (new_status, user.actor_pk, remarks, user.actor_pk, str(request_pk)),
    )
    log_audit(cur, action={"APPROVED": "APPROVE", "REJECTED": "REJECT", "CANCELLED": "CANCEL"}[new_status],
              table_name="membership_status_change_request", record_pk=str(request_pk), actor_pk=user.actor_pk,
              actor_user_account_pk=str(user.user_account_pk), module="membership_status",
              summary=f"Membership status change request {new_status.lower()}")


def _require_decider(cur, user: UserContext, member_person_pk, requester_sevi_pk) -> None:
    _require_person(user)
    if not svc.can_decide(cur, user):
        raise HTTPException(status_code=403, detail="Only the Parichalak (or the delegate acting for the seat) or the "
                                                    "Kendra President can decide a membership status change.")
    if str(member_person_pk) == str(user.person_pk):
        raise HTTPException(status_code=403, detail="You cannot decide a change to your own membership status.")
    if requester_sevi_pk and str(requester_sevi_pk) == str(user.actor_pk):
        raise HTTPException(status_code=403, detail="You cannot decide a request you filed yourself.")


@router.post("/requests/{request_pk}/approve", response_model=StatusChangeRequestResponse)
def approve_status_request(
    request_pk: UUID, body: StatusDecision,
    user: UserContext = Depends(get_current_user), conn=Depends(get_write_connection),
) -> StatusChangeRequestResponse:
    with conn.cursor() as cur:
        sevi_pk, from_pk, to_pk, eff, reason, req_by, member_person, to_code = _pending_for_update(cur, request_pk)
        _require_decider(cur, user, member_person, req_by)
        svc.apply_status_change(cur, request_pk=request_pk, sangha_sevi_pk=sevi_pk, from_status_pk=from_pk,
                                to_status_pk=to_pk, effective_date=eff, reason=reason, actor_pk=user.actor_pk,
                                to_status_code=to_code)
        _decide(cur, user, request_pk, "APPROVED", body.remarks)
        return _request_by_pk(cur, request_pk)


@router.post("/requests/{request_pk}/reject", response_model=StatusChangeRequestResponse)
def reject_status_request(
    request_pk: UUID, body: StatusRejection,
    user: UserContext = Depends(get_current_user), conn=Depends(get_write_connection),
) -> StatusChangeRequestResponse:
    with conn.cursor() as cur:
        _, _, _, _, _, req_by, member_person, _ = _pending_for_update(cur, request_pk)
        _require_decider(cur, user, member_person, req_by)
        _decide(cur, user, request_pk, "REJECTED", body.remarks)
        return _request_by_pk(cur, request_pk)


@router.post("/requests/{request_pk}/cancel", response_model=StatusChangeRequestResponse)
def cancel_status_request(
    request_pk: UUID,
    user: UserContext = Depends(get_current_user), conn=Depends(get_write_connection),
) -> StatusChangeRequestResponse:
    _require_person(user)
    with conn.cursor() as cur:
        _, _, _, _, _, req_by, _, _ = _pending_for_update(cur, request_pk)
        if not req_by or str(req_by) != str(user.actor_pk):
            raise HTTPException(status_code=403, detail="Only the person who filed the request can cancel it.")
        _decide(cur, user, request_pk, "CANCELLED", None)
        return _request_by_pk(cur, request_pk)
