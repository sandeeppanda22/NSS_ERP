"""
NSS ERP — Sakha re-parent approval router (owner rule, 2026-10-30).

Re-parenting a Sakha or Sakha Asana (moving it under a different
Anchalika/Zilla Sangha) needs approval unless a Kendra Governing Body member or
the NSS_ERP_ADMIN super administrator does it directly. Any other admin/office
bearer's PATCH /admin/organizations/{pk} with a new
parent files a request here instead (HTTP 202); this router lists, shows,
decides and cancels those requests.

  GET  /api/v1/org-reparent                                 — list (visibility-scoped)
  GET  /api/v1/org-reparent/{pk}                            — detail with steps
  POST /api/v1/org-reparent/{pk}/steps/{step_pk}/decide     — approve / reject one step
  POST /api/v1/org-reparent/{pk}/cancel                     — requester, Kendra GB member or NSS_ERP_ADMIN

Chain: Sakha President -> destination Anchalika/Zilla President -> Kendra
President (final), with Kendra-President fallback + collapse (see
api/services/org_reparent_service.py). Approval authority is the LIVE office
seat only — no permission and no NSS_ERP_ADMIN override when DECIDING a step
(the super-admin exemption is only about re-parenting directly, skipping the
chain). All endpoints are login-only (get_current_user); visibility is
requester, assigned approvers, Kendra GB members / NSS_ERP_ADMIN, and admins
whose scope contains the Sakha.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.schemas.org_reparent import (
    ReparentCancelRequest,
    ReparentDecisionRequest,
    ReparentRequestListResponse,
    ReparentRequestResponse,
)
from api.services import org_reparent_service as svc
from api.services.rbac_service import UserContext
from api.services.seat_service import seat_body_pks_held

router = APIRouter(prefix="/api/v1/org-reparent", tags=["org-reparent"])

def _require_person(user: UserContext) -> None:
    if not user.person_pk:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No person record for this account.")


def _visible_or_404(cur, user: UserContext, request_pk) -> None:
    clause, params = svc.visibility_clause(cur, user)
    cur.execute(
        f"""
        SELECT 1 FROM nss.organization_reparent_request r
        WHERE r.organization_reparent_request_pk = %s AND r.is_active = TRUE AND {clause}
        """,
        (str(request_pk), *params),
    )
    if cur.fetchone() is None:
        # 404, not 403 — existence is not leaked to non-participants.
        raise HTTPException(status_code=404, detail="Re-parent request not found.")


@router.get("", response_model=ReparentRequestListResponse)
def list_reparent_requests(
    mine: bool = Query(False, description="Only requests I filed"),
    awaiting_my_decision: bool = Query(False, description="Only requests with a step I can decide now"),
    sakha_pk: UUID | None = Query(None),
    request_status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED|CANCELLED)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> ReparentRequestListResponse:
    """Re-parent requests visible to the caller, newest first. Filters
    combine with AND."""
    _require_person(user)
    with conn.cursor() as cur:
        clauses, params = svc.visibility_clause(cur, user)
        where = [clauses]
        args: list = list(params)
        if mine:
            where.append("r.requested_by_person_pk = %s")
            args.append(str(user.person_pk))
        if awaiting_my_decision:
            c, p = svc.awaiting_decision_clause(cur, user)
            where.append(c)
            args.extend(p)
        if sakha_pk:
            where.append("r.sakha_organization_pk = %s")
            args.append(str(sakha_pk))
        if request_status:
            where.append("r.request_status = %s")
            args.append(request_status)
        where_sql = " AND ".join(where) + " AND r.is_active = TRUE"

        cur.execute(f"SELECT COUNT(*) FROM nss.organization_reparent_request r WHERE {where_sql}", args)
        total = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT r.organization_reparent_request_pk
            FROM nss.organization_reparent_request r
            WHERE {where_sql}
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*args, page_size, (page - 1) * page_size],
        )
        pks = [r[0] for r in cur.fetchall()]
        held = seat_body_pks_held(cur, user.person_pk, "PRESIDENT")
        items = [svc.build_request_payload(cur, pk, user, held_body_pks=held) for pk in pks]
    return ReparentRequestListResponse(items=items, total=total)


@router.get("/{request_pk:uuid}", response_model=ReparentRequestResponse)
def get_reparent_request(
    request_pk: UUID,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> ReparentRequestResponse:
    _require_person(user)
    with conn.cursor() as cur:
        _visible_or_404(cur, user, request_pk)
        return svc.build_request_payload(cur, request_pk, user)


@router.post("/{request_pk:uuid}/steps/{step_pk:uuid}/decide", response_model=ReparentRequestResponse)
def decide_reparent_step(
    request_pk: UUID,
    step_pk: UUID,
    body: ReparentDecisionRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> ReparentRequestResponse:
    """
    Approve or reject one step. The caller must currently hold the step's
    assigned President seat (substantive or live acting cover) — never a
    permission, never an NSS_ERP_ADMIN override — must not be the requester,
    and every earlier step must already be APPROVED. REJECT (remarks
    required) closes the request REJECTED. APPROVE of the final step
    re-validates and applies the parent change atomically (if re-validation
    fails the request is closed CANCELLED with a system remark and the
    parent is unchanged).
    """
    _require_person(user)
    with conn.cursor() as cur:
        svc.decide_step(cur, user, request_pk, step_pk, body.decision, body.remarks)
        return svc.build_request_payload(cur, request_pk, user)


@router.post("/{request_pk:uuid}/cancel", response_model=ReparentRequestResponse)
def cancel_reparent_request(
    request_pk: UUID,
    body: ReparentCancelRequest | None = None,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> ReparentRequestResponse:
    """Cancel a PENDING request — the requester, a Kendra GB member or the NSS_ERP_ADMIN."""
    _require_person(user)
    with conn.cursor() as cur:
        svc.cancel_request(cur, user, request_pk, body.remarks if body else None)
        return svc.build_request_payload(cur, request_pk, user)
