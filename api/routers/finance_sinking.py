"""
NSS ERP — Finance: Sinking Fund reimbursement (Bye-Law C(i)(2)(xviii), FIN-BR-026).

``/api/v1/finance`` (7 endpoints). The rules live in ``api/services/finance_sinking.py`` (one place); this router checks permission +
admin scope, calls them and audits every change.

  GET    /sinking-reimbursements                       list the obligations (filters: organization_pk = the Sakha, status)   FINANCE_VIEW + scope (the Kendra's)
  GET    /sinking-reimbursements/expenditures          Sinking Fund expenditures not yet registered as owed                  FINANCE_VIEW + scope
  GET    /sinking-reimbursements/summary               the Kendra's page Sakha by Sakha: owed, reimbursed, still owed, not yet registered  FINANCE_VIEW + scope
  POST   /sinking-reimbursements                       register an expenditure as a take-over expenditure (the Sakha owes it) FINANCE_MANAGE + scope
  GET    /sinking-reimbursements/{pk}                  the obligation with its reimbursements                                FINANCE_VIEW + scope (the Kendra's)
  POST   /sinking-reimbursements/{pk}/reimbursements   record a reimbursement (an income entry in the same fund, linked)     FINANCE_MANAGE + scope
  DELETE /sinking-reimbursements/{pk}                  remove one registered by mistake (soft; not once a reimbursement exists)  FINANCE_MANAGE + scope

Everything here is the KENDRA's procedure (owner 2026-11-24: "Sakha admins or office bearers should not see this"): reading and writing both need
admin scope on the organization of the financial scope the money was spent in. A Sakha's admin or office bearer sees nothing - not the list, not the
summary, not a single obligation - and the page does not show them the tab (``GET /reference`` -> ``kendra_side``).
A reimbursement is recorded through the ordinary ``POST /transactions`` code (F.create_transaction), so every rule of an entry - the open
current year, an ACTIVE scope and fund, the head's own rules - applies unchanged and no second implementation exists. Everything written is audited.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.helpers import next_id
from api.routers import finance as F
from api.routers import finance_setup as FS
from api.schemas import finance as S
from api.services import finance_sinking as K
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE = F._VIEW, F._MANAGE


def _detail(cur, pk) -> dict:
    return K.detail(cur, pk, F._COUNTED_TXN_STATUSES)


def _locked(cur, user: UserContext, pk, action: str) -> dict:
    row = K.load(cur, pk, F._COUNTED_TXN_STATUSES, lock=True)
    F._require_org_access(cur, user, row["scope_organization_pk"], action)
    return row


@router.get("/sinking-reimbursements", response_model=S.SinkingReimbursementListResponse)
def list_sinking_reimbursements(
    organization_pk: UUID | None = Query(None, description="The Sakha that owes"),
    status_filter: str | None = Query(None, alias="status", description="OPEN / PARTLY_REIMBURSED / REIMBURSED"),
    user: UserContext = Depends(_VIEW), conn=Depends(get_connection),
):
    if status_filter is not None and status_filter not in S.SINKING_REIMBURSEMENT_STATUSES:
        raise F._invalid(f"status must be one of: {', '.join(S.SINKING_REIMBURSEMENT_STATUSES)}.")
    with conn.cursor() as cur:
        where, params = F._visible(cur, user, "fs.organization_pk")      # the Kendra's side only
        if organization_pk is not None:
            where += " AND fm.organization_pk = %s"
            params.append(str(organization_pk))
        items = K.list_rows(cur, where, params, F._COUNTED_TXN_STATUSES)
    if status_filter:
        items = [i for i in items if i["status"] == status_filter]
    return {"items": items, "total": len(items)}


@router.get("/sinking-reimbursements/expenditures", response_model=S.SinkingExpenditureListResponse)
def list_unregistered_expenditures(user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    """What the page offers when registering: posted Sinking Fund spending by someone other than the Sakha, not registered yet."""
    with conn.cursor() as cur:
        where, params = F._visible(cur, user, "fs.organization_pk")
        items = K.unregistered_expenditures(cur, where, params, F._COUNTED_TXN_STATUSES)
    return {"items": items, "total": len(items)}


@router.post("/sinking-reimbursements", response_model=S.SinkingReimbursementDetail, status_code=status.HTTP_201_CREATED)
def register_sinking_reimbursement(body: S.SinkingReimbursementCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Register a Sinking Fund expenditure as a take-over expenditure: the Sakha now owes the amount (Bye-Law C(i)(2)(xviii))."""
    with conn.cursor() as cur:
        txn = F._txn_row(cur, user, body.expenditure_transaction_pk, "register this expenditure", lock=True)       # scope check on the Kendra's side
        fund = F._fund_row(cur, txn["fund_master_pk"]) if txn["fund_master_pk"] is not None else None
        K.check_registerable(txn, fund, txn["scope_organization_pk"])
        reason = K.clean_reason(body.takeover_reason)
        if K.is_registered(cur, txn["financial_transaction_pk"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This expenditure is already registered as a take-over expenditure.")
        reference = next_id(cur, K.SEQUENCE_CODE)
        pk = K.register(cur, user.actor_pk, reference=reference, expenditure_pk=txn["financial_transaction_pk"], amount_due=txn["amount"],
                        reason=reason, resolution_reference=F._clean(body.resolution_reference))
        F._audit(cur, user, "CREATE", "finance_sinking_reimbursement", pk, f"Registered take-over expenditure {txn['transaction_reference']} as owed by the Sakha",
                 {"reference": reference, "expenditure": txn["transaction_reference"], "sakha_organization_pk": str(fund["organization_pk"]),
                  "amount_due": str(txn["amount"]), "reason": reason, "resolution_reference": F._clean(body.resolution_reference)})
        return _detail(cur, pk)


@router.get("/sinking-reimbursements/summary", response_model=S.SinkingSummaryResponse)
def sinking_summary_by_sakha(user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    """The Kendra's page Sakha by Sakha: owed, reimbursed, still owed and spent-but-not-registered."""
    with conn.cursor() as cur:
        where, params = F._visible(cur, user, "fs.organization_pk")
        rows = K.list_rows(cur, where, params, F._COUNTED_TXN_STATUSES)
        waiting = K.unregistered_expenditures(cur, where, params, F._COUNTED_TXN_STATUSES)
    items = K.by_sakha(rows, waiting)
    return {"items": items, "total": len(items)}


@router.get("/sinking-reimbursements/{pk}", response_model=S.SinkingReimbursementDetail)
def get_sinking_reimbursement(pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        row = K.load(cur, pk, F._COUNTED_TXN_STATUSES)
        F._require_org_access(cur, user, row["scope_organization_pk"], "view this reimbursement")
        return _detail(cur, pk)


def _reimbursement_head(cur, user: UserContext, conn, organization_pk):
    """The SINKING_REIMBURSEMENT head of the organization that holds the fund; copied from the Kendra template the first time (a standard, automatic step)."""
    if organization_pk is None:                                                  # a scope that belongs to no Sangha uses the global templates
        head = K.template_head_pk(cur)
        if head is None:
            raise F._invalid("The Sinking Fund reimbursement head is not set up yet; run the database build (02_build.sh) to add it.")
        return head
    head = K.head_for(cur, organization_pk)
    if head is None:
        template = K.template_head_pk(cur)
        if template is None:
            raise F._invalid("The Sinking Fund reimbursement head is not set up yet; run the database build (02_build.sh) to add it.")
        FS.adopt_templates(S.AdoptTemplates(organization_pk=organization_pk, template_pks=[template]), user, conn)
        head = K.head_for(cur, organization_pk)
    if head is None:
        raise F._invalid("The Sinking Fund reimbursement head is switched off for this Sangha; switch it on under Finance > Heads first.")
    return head


@router.post("/sinking-reimbursements/{pk}/reimbursements", response_model=S.SinkingReimbursementDetail, status_code=status.HTTP_201_CREATED)
def record_reimbursement(pk: UUID, body: S.SinkingReimbursementPay, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """
    The Sakha pays back (part of) what the Kendra spent: an INCOME entry in the same Sinking Fund, DRAFT, in the current year - then posted
    like any other entry. It counts as reimbursed only once POSTED / SETTLED; what is recorded but not posted is reserved so nobody records more
    than is owed.
    """
    with conn.cursor() as cur:
        row = _locked(cur, user, pk, "record a reimbursement")
        K.check_amount(body.amount, K.available_to_record(row["amount_due"], row["reimbursed_amount"], row["pending_amount"]))
        year = F.current_year(cur)
        if year is None:
            raise F._invalid("There is no financial year yet; create one first.")
        head = _reimbursement_head(cur, user, conn, row["scope_organization_pk"])
        txn = F.create_transaction(
            S.TransactionCreate(
                financial_year_pk=year["financial_year_pk"], financial_scope_pk=row["financial_scope_pk"], fund_master_pk=row["fund_master_pk"],
                transaction_type="INCOME", finance_head_pk=head, amount=body.amount, transaction_date=body.transaction_date or date.today(),
                description=F._clean(body.description) or f"Reimbursement by {row['sakha_name']} of {row['expenditure_reference']} ({row['reimbursement_reference']})",
            ),
            user, conn,
        )
        K.link_entry(cur, user.actor_pk, pk, txn["financial_transaction_pk"])
        F._audit(cur, user, "CREATE", "finance_sinking_reimbursement_entry", pk, f"Recorded a reimbursement of {body.amount} against {row['reimbursement_reference']}",
                 {"reference": row["reimbursement_reference"], "entry": txn["transaction_reference"], "amount": str(body.amount),
                  "owed_before": str(row["outstanding_amount"])})
        return _detail(cur, pk)


@router.delete("/sinking-reimbursements/{pk}", response_model=S.SinkingReimbursementDetail)
def remove_sinking_reimbursement(pk: UUID, reason: str = Query(..., min_length=1, max_length=500, description="Why it was registered by mistake"),
                                 user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Remove an obligation registered by mistake (soft delete, audited). Not once a reimbursement has been recorded against it."""
    with conn.cursor() as cur:
        row = _locked(cur, user, pk, "remove this registration")
        if K.has_entries(cur, pk):
            raise F._invalid("A reimbursement has already been recorded against this; it can no longer be removed.")
        shown = _detail(cur, pk)
        K.remove(cur, user.actor_pk, pk)
        F._audit(cur, user, "DELETE", "finance_sinking_reimbursement", pk, f"Removed registration {row['reimbursement_reference']}",
                 {"reason": reason.strip(), "reference": row["reimbursement_reference"], "amount_due": str(row["amount_due"])})
        return shown
