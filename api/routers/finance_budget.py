"""
NSS ERP — Finance: the Kendra annual budget (Bye-Law, FIN-BR-041).

``/api/v1/finance`` (9 endpoints). The rules live in ``api/services/finance_budget.py`` (one place); this router checks permission +
admin scope, calls them and audits every change.

  GET    /budgets                              list (filters: financial_year_pk, organization_pk, status)  FINANCE_VIEW + scope
  POST   /budgets                              start the Kendra's budget for a financial year              FINANCE_MANAGE + scope
  GET    /budgets/{pk}                         the budget, its lines with actual-so-far, and the flags     FINANCE_VIEW + scope
  PUT    /budgets/{pk}/lines                   set the planned amount of a head (any status; a reason once past DRAFT)  FINANCE_MANAGE + scope
  DELETE /budgets/{pk}/lines/{line_pk}         remove a line (soft; any status; ?reason= once past DRAFT)  FINANCE_MANAGE + scope
  POST   /budgets/{pk}/refer                   refer the draft to the Advisory Board (files a numbered letter)  FINANCE_MANAGE + scope
  POST   /budgets/{pk}/advisory-views          record the Advisory Board's views (files its numbered reply)     FINANCE_MANAGE + scope
  POST   /budgets/{pk}/pass                    record the Governing Body's resolution passing it           FINANCE_MANAGE + scope
  POST   /budgets/{pk}/reopen                  send it back to draft (not once passed), with a reason      FINANCE_MANAGE + scope

Each step records a fact (reference + date). Referring and the Advisory Board's reply FILE A LETTER in the Correspondence register
automatically (api/routers/correspondence.py::register_correspondence, the same code as POST /correspondence; the other organization's
inward copy is minted too and the reply is threaded to it), and the letters' numbers are the budget's references - nobody types one.
The Advisory Board's views must be on file before the budget can pass, and the budget never blocks spending — it only flags it (see the service). Everything written is audited.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.routers import correspondence as C
from api.routers import finance as F
from api.schemas import finance as S
from api.schemas.correspondence import CorrespondenceCreate
from api.services import finance_budget as B
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE = F._VIEW, F._MANAGE
_LETTER_MEDIUM = "HAND_DELIVERY"        # CORRESPONDENCE_MEDIUM: the letter passes between two NSS bodies, there is no postal or e-mail leg


def _detail(cur, budget_pk) -> dict:
    return B.detail(cur, budget_pk, F._COUNTED_TXN_STATUSES)


def _locked(cur, user: UserContext, budget_pk, action: str) -> dict:
    """The budget row (locked), after the caller's admin scope on the Kendra is checked."""
    budget = B.load(cur, budget_pk, lock=True)
    F._require_org_access(cur, user, budget["organization_pk"], action)
    return budget


def _viewable(cur, user: UserContext, budget_pk, action: str) -> dict:
    budget = B.load(cur, budget_pk)
    F._require_org_access(cur, user, budget["organization_pk"], action)
    return budget


@router.get("/budgets", response_model=S.BudgetListResponse)
def list_budgets(
    financial_year_pk: UUID | None = Query(None),
    organization_pk: UUID | None = Query(None),
    status_code: str | None = Query(None, alias="status"),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    if status_code is not None and status_code not in S.BUDGET_STATUSES:
        raise F._invalid(f"status must be one of {', '.join(S.BUDGET_STATUSES)}.")
    with conn.cursor() as cur:
        visible, params = F._visible(cur, user, "b.organization_pk")
        where = ["b.is_active = TRUE", visible]
        for column, value in (("b.financial_year_pk", financial_year_pk), ("b.organization_pk", organization_pk), ("b.status", status_code)):
            if value is not None:
                where.append(f"{column} = %s")
                params.append(str(value))
        items = B.list_rows(cur, " AND ".join(where), params)
    return {"items": items, "total": len(items)}


@router.post("/budgets", response_model=S.BudgetDetailResponse, status_code=status.HTTP_201_CREATED)
def create_budget(body: S.BudgetCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        org_pk = body.organization_pk or B.kendra_organization_pk(cur)
        if org_pk is None:
            raise F._invalid("There is no active Kendra organization to hold a budget.")
        B.require_budget_holder(cur, org_pk)                                     # the Kendra, or a Sakha (a plain plan)
        F._require_org_access(cur, user, org_pk, "start a budget for this Sangha")
        pk = B.create(cur, user.actor_pk, year_pk=body.financial_year_pk, organization_pk=org_pk, notes=F._clean(body.notes))
        F._audit(cur, user, "CREATE", "finance_budget", pk, "Started the annual budget",
                 {"financial_year_pk": str(body.financial_year_pk), "organization_pk": str(org_pk)})
        return _detail(cur, pk)


@router.get("/budgets/{budget_pk}", response_model=S.BudgetDetailResponse)
def get_budget(budget_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        _viewable(cur, user, budget_pk, "see this budget")
        return _detail(cur, budget_pk)


@router.put("/budgets/{budget_pk}/lines", response_model=S.BudgetDetailResponse)
def put_budget_line(budget_pk: UUID, body: S.BudgetLineWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "change this budget")
        reason = B.require_reason(budget, body.reason)
        line_pk, created, before = B.put_line(cur, user.actor_pk, budget, head_pk=body.finance_head_pk, amount=body.amount, notes=F._clean(body.notes),
                                              reason=reason)
        F._audit(cur, user, "CREATE" if created else "UPDATE", "finance_budget_line", line_pk,
                 f"{'Added' if created else 'Changed'} a budget line of {body.amount}" + (f" ({budget['status']} budget)" if reason else ""),
                 {"finance_budget_pk": str(budget_pk), "finance_head_pk": str(body.finance_head_pk), "amount": str(body.amount),
                  "amount_before": str(before) if before is not None else None, "budget_status": budget["status"], "reason": reason})
        return _detail(cur, budget_pk)


@router.delete("/budgets/{budget_pk}/lines/{line_pk}", response_model=S.BudgetDetailResponse)
def remove_budget_line(budget_pk: UUID, line_pk: UUID, reason: str | None = Query(None, max_length=500, description="Required once the budget has left DRAFT"),
                       user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Soft delete: the row stays for the audit trail, it just stops counting."""
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "change this budget")
        reason = B.require_reason(budget, reason)
        amount = B.remove_line(cur, user.actor_pk, budget, line_pk, reason)
        F._audit(cur, user, "DELETE", "finance_budget_line", line_pk, "Removed a budget line",
                 {"finance_budget_pk": str(budget_pk), "amount_before": str(amount), "budget_status": budget["status"], "reason": reason})
        return _detail(cur, budget_pk)


def _file_letter(cur, user: UserContext, *, register_pk, sender_pk, recipient_pk, on: date, subject: str, remarks: str,
                 in_reply_to=None) -> dict:
    """
    File one letter in the Correspondence register as a SYSTEM action of the budget (the same registration code as
    POST /correspondence; the recipient organization's own INWARD copy is minted by it too). The caller has already been authorised
    for the budget itself (FINANCE_MANAGE + admin scope on the Kendra); the register's own scope is not theirs to hold, so it is not
    asked again. Returns the letter's pk, number and the recipient's inward number.
    """
    return C.register_correspondence(
        cur, user,
        CorrespondenceCreate(
            register_organization_pk=register_pk, direction="OUTWARD", correspondence_date=on, received_or_sent_date=on,
            subject=subject, remarks=remarks,
            sender_type="ORGANIZATION", sender_organization_pk=sender_pk,
            recipient_type="ORGANIZATION", recipient_organization_pk=recipient_pk,
            in_reply_to_correspondence_pk=in_reply_to, medium=_LETTER_MEDIUM,
        ),
        check_scope=False,
    )


@router.post("/budgets/{budget_pk}/refer", response_model=S.BudgetDetailResponse)
def refer_budget(budget_pk: UUID, body: S.BudgetReferWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Refer the draft to the Advisory Board: a numbered letter Kendra -> Advisory Board is filed in Correspondence automatically."""
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "refer this budget")
        B.require_steps(budget)
        referred_on = body.referred_on or date.today()
        B.validate_refer(budget, referred_on)                            # refuse BEFORE anything is filed
        letter = _file_letter(
            cur, user, register_pk=budget["organization_pk"], sender_pk=budget["organization_pk"],
            recipient_pk=B.advisory_board_organization_pk(cur), on=referred_on,
            subject=B.referral_subject(budget["year_code"]), remarks=B.referral_remarks(B.lines(cur, budget_pk, F._COUNTED_TXN_STATUSES)),
        )
        B.refer(cur, user.actor_pk, budget, referred_on, letter["correspondence_pk"])
        F._audit(cur, user, "UPDATE", "finance_budget", budget_pk, "Referred the Kendra budget to the Advisory Board",
                 {"referred_on": str(referred_on), "from": budget["status"], "to": B.REFERRED, "letter": letter["reference_number"],
                  "advisory_board_copy": letter["inward_reference_number"]})
        return _detail(cur, budget_pk)


@router.post("/budgets/{budget_pk}/advisory-views", response_model=S.BudgetDetailResponse)
def record_advisory_views(budget_pk: UUID, body: S.BudgetViewsWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Record the Advisory Board's views: its reply is filed in Correspondence (a reply to its copy of the referral) and numbered automatically."""
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "record the Advisory Board's views on this budget")
        B.require_steps(budget)
        views_date = body.advisory_views_date or date.today()
        summary = B.validate_views(budget, views_date, body.advisory_views_summary)     # refuse BEFORE anything is filed
        board_pk = B.advisory_board_organization_pk(cur)
        letter = _file_letter(
            cur, user, register_pk=board_pk, sender_pk=board_pk, recipient_pk=budget["organization_pk"], on=views_date,
            subject=B.views_subject(budget["year_code"]), remarks=summary,
            in_reply_to=B.inward_copy_pk(cur, budget["referral_correspondence_pk"], board_pk),
        )
        B.record_views(cur, user.actor_pk, budget, reference=letter["reference_number"], views_date=views_date, summary=summary,
                       letter_pk=letter["correspondence_pk"])
        F._audit(cur, user, "UPDATE", "finance_budget", budget_pk, "Recorded the Advisory Board's views on the Kendra budget",
                 {"advisory_reference": letter["reference_number"], "advisory_views_date": str(views_date),
                  "kendra_copy": letter["inward_reference_number"], "from": budget["status"], "to": B.VIEWS_RECEIVED})
        return _detail(cur, budget_pk)


@router.post("/budgets/{budget_pk}/pass", response_model=S.BudgetDetailResponse)
def pass_budget(budget_pk: UUID, body: S.BudgetPassWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "pass this budget")
        B.require_steps(budget)
        B.pass_budget(cur, user.actor_pk, budget, reference=body.resolution_reference, resolution_date=body.resolution_date)
        F._audit(cur, user, "APPROVE", "finance_budget", budget_pk, "The Governing Body passed the Kendra budget",
                 {"resolution_reference": body.resolution_reference, "resolution_date": str(body.resolution_date),
                  "from": budget["status"], "to": B.PASSED})
        return _detail(cur, budget_pk)


@router.post("/budgets/{budget_pk}/reopen", response_model=S.BudgetDetailResponse)
def reopen_budget(budget_pk: UUID, body: S.BudgetReopenWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "send this budget back to draft")
        B.require_steps(budget)
        remarks = B.require_blank(body.remarks, "The reason")
        B.reopen(cur, user.actor_pk, budget)
        F._audit(cur, user, "UPDATE", "finance_budget", budget_pk, "Sent the Kendra budget back to draft",
                 {"remarks": remarks, "from": budget["status"], "to": B.DRAFT, "referred_on": str(budget["referred_on"]),
                  "advisory_reference": budget["advisory_reference"]})
        return _detail(cur, budget_pk)


@router.post("/budgets/{budget_pk}/correct", response_model=S.BudgetDetailResponse)
def correct_budget(budget_pk: UUID, body: S.BudgetCorrectWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """
    Correct the Advisory Board's summary (once its views are on file) or the resolution reference (once the budget has passed), with a reason (owner
    2026-11-24). The status does not move; the audit event keeps the old and new text and the reason.
    """
    with conn.cursor() as cur:
        budget = _locked(cur, user, budget_pk, "correct this budget")
        B.require_steps(budget)
        done = B.correct(cur, user.actor_pk, budget, summary=body.advisory_views_summary, resolution_reference=body.resolution_reference, reason=body.reason)
        F._audit(cur, user, "UPDATE", "finance_budget", budget_pk, "Corrected what was recorded on the Kendra budget",
                 {"reason": done["reason"], "status": budget["status"], "changed": {col: {"from": old, "to": new} for col, (old, new) in done["changed"].items()}})
        return _detail(cur, budget_pk)
