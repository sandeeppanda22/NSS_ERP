"""
NSS ERP — Finance: closing the financial year Sakha by Sakha and Kendra (owner request 2026-11-25).

``/api/v1/finance`` (2 endpoints). The rules live in ``api/services/finance_year_closing.py`` (one place); this router checks permission and who may act,
calls them and audits every change.

  GET  /years/{year_pk}/closings   every Sangha with activity in the year: its status, what it has and what is unfinished   FINANCE_VIEW + scope
  POST /years/{year_pk}/closings   a Sangha starts closing / closes its books for the year                                   FINANCE_MANAGE + the Sangha's finance administrator

The year stays one calendar record the NSS-wide authority opens and closes (``POST /years/{pk}/transition``). On top of it every Sangha closes its own
books: OPEN -> CLOSING (no new entries or transfers, finish what is in progress) -> CLOSED (nothing unfinished may remain). Who: the Sangha's own finance
administrators (a Sakha's seated Treasurer / President / Secretary, an admin given a Finance role) and the NSS ERP Administrator - the same people who
set up its scopes and funds. The year itself closes only when every Sangha with activity has closed (the transition closes the finished ones with it);
when the year is already CLOSING and the last Sangha closes, the year closes by itself. Everything written is audited.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.routers import finance as F
from api.schemas import finance as S
from api.services import finance_year_closing as C
from api.services.rbac_service import UserContext, actor_scope_org_pks

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE = F._VIEW, F._MANAGE


def _row(cur, user: UserContext, year: dict, sangha: dict) -> dict:
    """One Sangha's line, with what the caller may do about it."""
    state = sangha["status"]
    nxt = {C.OPEN: C.CLOSING, C.CLOSING: C.CLOSED}.get(state)
    can = (nxt is not None and year["status"] in C.YEAR_STATES_THAT_CAN_CLOSE and user.has_any_permission("FINANCE_MANAGE", "FINANCE_APPROVE")
           and F._is_finance_admin(cur, user, sangha["organization_pk"]))
    return {**sangha, "next_status": nxt if can else None, "can_act": bool(can)}


@router.get("/years/{year_pk}/closings", response_model=S.YearClosingListResponse)
def list_year_closings(year_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    """Sangha by Sangha: where each stands in closing this year. A caller sees the Sanghas their admin scope reaches (the Kendra's people all of them)."""
    with conn.cursor() as cur:
        year = F._year_row(cur, year_pk)
        reach = actor_scope_org_pks(cur, user)
        sanghas = [s for s in C.sanghas_of_year(cur, year_pk) if reach is None or str(s["organization_pk"]) in reach]
        items = [_row(cur, user, year, s) for s in sanghas]
    return {"financial_year_pk": year["financial_year_pk"], "year_code": year["year_code"], "year_status": year["status"], "items": items, "total": len(items)}


@router.post("/years/{year_pk}/closings", response_model=S.YearClosingResult)
def close_a_sangha_year(year_pk: UUID, body: S.YearClosingWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """A Sakha or the Kendra starts closing, or closes, its own books for the year. CLOSED needs nothing unfinished; what is in the way is named."""
    with conn.cursor() as cur:
        year = F._year_row(cur, year_pk, lock=True)
        C.require_year_open_for_closing(year["year_code"], year["status"])
        if body.status not in (C.CLOSING, C.CLOSED):
            raise F._invalid("status must be CLOSING or CLOSED.")
        org = body.organization_pk
        F._require_active_organization(cur, org, "Organization")
        F._require_org_access(cur, user, org, "close this Sangha's financial year")
        F._require_finance_admin(cur, user, "close this Sangha's financial year", org)
        current = C.status_of(cur, year_pk, org)
        C.check_step(current, body.status)
        if body.status == C.CLOSED:
            entries = F._open_work_blockers(cur, year_pk=year_pk, organization_pk=org)
            if entries:
                cur.execute("SELECT organization_name FROM nss.organization WHERE organization_pk = %s", (str(org),))
                raise F._invalid(f"{cur.fetchone()[0]} cannot close its books for {year['year_code']} yet: " + "; ".join(entries) + ".")
        remarks = F._clean(body.remarks)
        C.set_status(cur, user.actor_pk, year_pk, org, body.status, remarks)
        F._audit(cur, user, "STATUS_CHANGE", "finance_year_closing", year_pk, f"A Sangha's books for {year['year_code']}: {current} -> {body.status}",
                 {"organization_pk": str(org), "year": year["year_code"], "from": current, "to": body.status, "remarks": remarks})
        sanghas = C.sanghas_of_year(cur, year_pk)
        year_closed = False
        if body.status == C.CLOSED and year["status"] == "CLOSING" and C.everyone_closed(sanghas, C.global_unfinished(cur, year_pk)):
            F.apply_year_status(cur, user, year, "CLOSED", "Every Sakha and the Kendra have closed their books")          # the last one closes the year
            year_closed = True
            year = {**year, "status": "CLOSED"}
        mine = next(s for s in sanghas if str(s["organization_pk"]) == str(org))
        return {**_row(cur, user, year, mine), "year_closed": year_closed}
