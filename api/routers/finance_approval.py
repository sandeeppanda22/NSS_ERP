"""
NSS ERP — Finance: Sakha approval chain, bills and the Treasurer's default limit (owner decision 2026-11-17).

``/api/v1/finance`` — the rules live in ``api/services/finance_approval.py`` (one place); this router only exposes them.

  GET    /approval-policy?organization_pk            the Sakha's default Treasurer limit            FINANCE_VIEW + scope
  PUT    /approval-policy                            set / clear it                                 FINANCE_CONFIGURE + scope
  GET    /transactions/{pk}/bills                    the bills of a spend                           FINANCE_VIEW + scope
  POST   /transactions/{pk}/bills                    add a bill (entry still DRAFT)                 FINANCE_MANAGE + scope
  DELETE /transactions/{pk}/bills/{bill_pk}          remove a bill (soft; entry still DRAFT)        FINANCE_MANAGE + scope
  GET    /transactions/{pk}/approval                 where the entry stands in the chain            FINANCE_VIEW + scope
  GET    /my-approvals                               entries waiting for MY approval                login only
  POST   /transactions/{pk}/approve | /reject        decide the next step                           login only + the SEAT

The decision endpoints are login-only on purpose: the Treasurer and the President are office-bearers, often with no admin role,
and the authority is the seat they hold at that moment (api/services/seat_service.py), not a permission. A caller who does not
hold the seat that must act now gets 403; an unknown entry is a plain 404. Everything written is audited.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.routers import finance as F
from api.schemas import finance as S
from api.services import finance_approval as A
from api.services import seat_service
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE, _CONFIGURE = F._VIEW, F._MANAGE, F._CONFIGURE
_MAX_MY_APPROVALS = 100


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ═══════════════════════════════════════════════════════════════════════
# The Sakha's default Treasurer limit
# ═══════════════════════════════════════════════════════════════════════

def _policy(cur, org_pk) -> dict:
    cur.execute("SELECT organization_name FROM nss.organization WHERE organization_pk = %s", (str(org_pk),))
    return {"organization_pk": org_pk, "organization_name": cur.fetchone()[0], "default_treasurer_limit": A.default_limit(cur, org_pk)}


@router.get("/approval-policy", response_model=S.ApprovalPolicyResponse)
def get_approval_policy(organization_pk: UUID = Query(...), user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        F._require_org_access(cur, user, organization_pk, "see the approval limit of this organization")
        F._require_active_organization(cur, organization_pk, "Organization")
        return _policy(cur, organization_pk)


@router.put("/approval-policy", response_model=S.ApprovalPolicyResponse)
def put_approval_policy(body: S.ApprovalPolicyWrite, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """Set (or clear) the amount a Sakha's Treasurer may approve alone on a head with no limit of its own."""
    with conn.cursor() as cur:
        F._require_org_access(cur, user, body.organization_pk, "set the approval limit of this organization")
        F._require_active_organization(cur, body.organization_pk, "Organization")
        A.require_not_the_treasurer(cur, user, body.organization_pk, "the Treasurer's approval limit")
        if not A.is_chain_org(cur, body.organization_pk):
            raise F._invalid("The Treasurer's limit applies to a Sakha only.")
        before = A.default_limit(cur, body.organization_pk)
        cur.execute("SELECT finance_approval_policy_pk FROM nss.finance_approval_policy WHERE organization_pk = %s AND is_active = TRUE",
                    (str(body.organization_pk),))
        row = cur.fetchone()
        if row:
            F._update_row(cur, user, "finance_approval_policy", "finance_approval_policy_pk", row[0],
                          {"default_treasurer_limit": body.default_treasurer_limit})
            pk = row[0]
        else:
            cur.execute("INSERT INTO nss.finance_approval_policy (organization_pk, default_treasurer_limit, created_by_sangha_sevi_pk) "
                        "VALUES (%s, %s, %s) RETURNING finance_approval_policy_pk",
                        (str(body.organization_pk), body.default_treasurer_limit, user.actor_pk))
            pk = cur.fetchone()[0]
        F._audit(cur, user, "UPDATE", "finance_approval_policy", pk, "Changed the Treasurer's default approval limit",
                 {"organization_pk": str(body.organization_pk), "from": str(before) if before is not None else None,
                  "to": str(body.default_treasurer_limit) if body.default_treasurer_limit is not None else None})
        return _policy(cur, body.organization_pk)


# ═══════════════════════════════════════════════════════════════════════
# Bills
# ═══════════════════════════════════════════════════════════════════════

_BILL_SELECT = ("SELECT finance_transaction_bill_pk, vendor_name, bill_number, bill_date, amount, document_url, description, created_at "
                "FROM nss.finance_transaction_bill WHERE financial_transaction_pk = %s AND is_active = TRUE ORDER BY bill_date, created_at")


def _bills(cur, txn_pk) -> dict:
    cur.execute(_BILL_SELECT, (str(txn_pk),))
    items = F._fetch_all(cur)
    return {"items": items, "total_amount": sum((b["amount"] for b in items), start=0) or 0, "count": len(items)}


def _draft_expense(txn: dict) -> None:
    if txn["transaction_type"] != "EXPENSE":
        raise F._invalid("Bills are recorded for spending only.")
    if txn["status"] != "DRAFT":
        raise F._invalid(f"The entry is {txn['status']}; bills can only change while it is a DRAFT.")


@router.get("/transactions/{txn_pk}/bills", response_model=S.BillListResponse)
def list_bills(txn_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        F._txn_row(cur, user, txn_pk, "see the bills of this transaction")
        return _bills(cur, txn_pk)


@router.post("/transactions/{txn_pk}/bills", response_model=S.BillResponse, status_code=status.HTTP_201_CREATED)
def add_bill(txn_pk: UUID, body: S.BillCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        txn = F._txn_row(cur, user, txn_pk, "add a bill to this transaction", lock=True)
        _draft_expense(txn)
        vendor = F._clean(body.vendor_name)
        if not vendor:
            raise F._invalid("vendor_name cannot be blank.")
        cur.execute(
            """
            INSERT INTO nss.finance_transaction_bill
                (financial_transaction_pk, vendor_name, bill_number, bill_date, amount, document_url, description, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_transaction_bill_pk
            """,
            (str(txn_pk), vendor, F._clean(body.bill_number), body.bill_date, body.amount, body.document_url,
             F._clean(body.description), user.actor_pk),
        )
        pk = cur.fetchone()[0]
        F._audit(cur, user, "CREATE", "finance_transaction_bill", pk, f"Added a bill of {body.amount} from {vendor} to {txn['transaction_reference']}",
                 {"financial_transaction_pk": str(txn_pk), "amount": str(body.amount), "bill_number": F._clean(body.bill_number)})
        cur.execute(_BILL_SELECT.replace("WHERE financial_transaction_pk = %s", "WHERE finance_transaction_bill_pk = %s"), (str(pk),))
        return F._fetch_one(cur)


@router.delete("/transactions/{txn_pk}/bills/{bill_pk}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bill(txn_pk: UUID, bill_pk: UUID, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Soft delete: the row stays for the audit trail, it just stops counting."""
    with conn.cursor() as cur:
        txn = F._txn_row(cur, user, txn_pk, "remove a bill of this transaction", lock=True)
        _draft_expense(txn)
        cur.execute("SELECT 1 FROM nss.finance_transaction_bill WHERE finance_transaction_bill_pk = %s AND financial_transaction_pk = %s AND is_active = TRUE",
                    (str(bill_pk), str(txn_pk)))
        if cur.fetchone() is None:
            raise F._not_found("Bill")
        cur.execute("UPDATE nss.finance_transaction_bill SET is_active = FALSE, deleted_at = NOW(), deleted_by_sangha_sevi_pk = %s, "
                    "updated_at = NOW(), updated_by_sangha_sevi_pk = %s WHERE finance_transaction_bill_pk = %s",
                    (user.actor_pk, user.actor_pk, str(bill_pk)))
        F._audit(cur, user, "DELETE", "finance_transaction_bill", bill_pk, f"Removed a bill from {txn['transaction_reference']}",
                 {"financial_transaction_pk": str(txn_pk)})


# ═══════════════════════════════════════════════════════════════════════
# Where an entry stands
# ═══════════════════════════════════════════════════════════════════════

def _state_response(cur, txn: dict, org_pk) -> dict:
    st = A.state(cur, txn, org_pk)
    total, count = A.bills_summary(cur, txn["financial_transaction_pk"])
    problem = A.submit_problems(cur, txn, org_pk) if st["applies"] and txn["status"] == "DRAFT" else None
    return {
        "applies": st["applies"], "requires": st["requires"], "limit": st["limit"], "steps": st["steps"],
        "next_stage": st["next_stage"], "next_position": st["next_position"], "next_cover_reason": st["next_cover_reason"],
        "complete": st["complete"], "blocked_reason": st["blocked_reason"], "bills_total": total, "bill_count": count,
        "submit_problem": problem,
    }


@router.get("/transactions/{txn_pk}/approval", response_model=S.ApprovalState)
def get_approval_state(txn_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        txn = F._txn_row(cur, user, txn_pk, "see the approval of this transaction")
        return _state_response(cur, txn, txn["scope_organization_pk"])


# ═══════════════════════════════════════════════════════════════════════
# The approver's side (login only; the SEAT is the authority)
# ═══════════════════════════════════════════════════════════════════════

_TXN_COLUMNS = """
           t.financial_transaction_pk, t.transaction_reference, t.financial_year_pk, t.financial_scope_pk, t.fund_master_pk,
           t.transaction_type, t.finance_head_pk, t.amount, t.transaction_date, t.description, t.person_pk, t.sangha_sevi_pk,
           t.status, t.created_by_sangha_sevi_pk, fs.organization_pk AS scope_organization_pk
"""
_TXN_FROM = """
      FROM nss.financial_transaction t
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
"""


def _locked_txn(cur, txn_pk) -> dict:
    cur.execute("SELECT" + _TXN_COLUMNS + _TXN_FROM + " WHERE t.financial_transaction_pk = %s AND t.is_active = TRUE FOR UPDATE OF t", (str(txn_pk),))
    row = F._fetch_one(cur)
    if row is None:
        raise F._not_found("Transaction")
    return row


def _decide(txn_pk: UUID, user: UserContext, conn, decision: str, remarks: str | None) -> dict:
    if user.person_pk is None:
        raise _forbidden("Only an office-bearer of the Sakha can approve its entries.")
    with conn.cursor() as cur:
        txn = _locked_txn(cur, txn_pk)
        org = txn["scope_organization_pk"]
        if not A.is_chain_org(cur, org):
            raise F._not_found("Transaction")                    # not a Sakha entry: nothing for this endpoint to reveal
        result = A.decide(cur, user, txn, org, decision, remarks)
        final = result["final"]
        who = f"{result['position'].title()}"
        if final == "APPROVED":
            # The last required approval: the entry is approved and posted in one go (an office-bearer holds no FINANCE permission).
            extra = {"chain": True, "last_step": result["stage"], "last_position": result["position"]}
            F._move_transaction(cur, user, txn, "APPROVED", extra=extra)
            F._move_transaction(cur, user, txn, "POSTED", extra={**extra, "posted_by_chain": True})
            message = f"Approved by the {who}. The entry is approved and posted."
        elif final == "REJECTED":
            F._move_transaction(cur, user, txn, "REJECTED", remarks=remarks, extra={"chain": True, "position": result["position"]})
            message = f"Rejected by the {who}."
        else:
            message = f"Approved by the {who}. It now waits for the President (or the Secretary when no President is seated)."
        return {"financial_transaction_pk": txn["financial_transaction_pk"], "transaction_reference": txn["transaction_reference"],
                "status": txn["status"], "final": final, "message": message}


@router.post("/transactions/{txn_pk}/approve", response_model=S.ApprovalResult)
def approve_transaction(txn_pk: UUID, body: S.ApprovalDecision | None = None, user: UserContext = Depends(get_current_user),
                        conn=Depends(get_write_connection)):
    return _decide(txn_pk, user, conn, "APPROVED", body.remarks if body else None)


@router.post("/transactions/{txn_pk}/reject", response_model=S.ApprovalResult)
def reject_transaction(txn_pk: UUID, body: S.ApprovalDecision, user: UserContext = Depends(get_current_user),
                       conn=Depends(get_write_connection)):
    return _decide(txn_pk, user, conn, "REJECTED", body.remarks)


def _seat_orgs(cur, person_pk) -> set[str]:
    """The Sakha whose Governing Body seat (Treasurer / President / Secretary) the person holds right now."""
    bodies: set[str] = set()
    for position in (A.TREASURER, A.PRESIDENT, A.SECRETARY):
        bodies |= seat_service.seat_body_pks_held(cur, person_pk, position)
    if not bodies:
        return set()
    cur.execute(
        "SELECT bm.organization_pk FROM nss.body_master bm JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk "
        "WHERE bm.body_master_pk = ANY(%s::uuid[]) AND bt.body_type_code = %s AND bm.organization_pk IS NOT NULL AND bm.is_active = TRUE",
        (sorted(bodies), A.BODY_TYPE),
    )
    return {str(r[0]) for r in cur.fetchall()}


@router.get("/my-approvals", response_model=S.MyApprovals)
def my_approvals(user: UserContext = Depends(get_current_user), conn=Depends(get_connection)):
    """The entries waiting for the CALLER to act now: their seat is the one the next step needs. Login only; nothing else is shown."""
    with conn.cursor() as cur:
        if user.person_pk is None:
            return {"items": [], "total": 0}
        orgs = _seat_orgs(cur, user.person_pk)
        if not orgs:
            return {"items": [], "total": 0}
        cur.execute(
            f"""
            SELECT h.head_name, o.organization_name,
                   {F._PERSON_NAME_SQL.format(a='cp')} AS recorded_by_name, {F._PERSON_NAME_SQL.format(a='mp')} AS member_name,
                   {_TXN_COLUMNS}
            {_TXN_FROM}
              JOIN nss.finance_head h ON h.finance_head_pk = t.finance_head_pk
              JOIN nss.organization o ON o.organization_pk = fs.organization_pk
              LEFT JOIN nss.sangha_sevi cs ON cs.sangha_sevi_pk = t.created_by_sangha_sevi_pk
              LEFT JOIN nss.person cp ON cp.person_pk = cs.person_pk
              LEFT JOIN nss.person mp ON mp.person_pk = t.person_pk
             WHERE t.is_active = TRUE AND t.status = 'PENDING_APPROVAL' AND fs.organization_pk = ANY(%s::uuid[])
             ORDER BY t.transaction_date, t.created_at LIMIT {_MAX_MY_APPROVALS}
            """,
            (sorted(orgs),),
        )
        rows = F._fetch_all(cur)
        items = []
        for txn in rows:
            st = A.state(cur, txn, txn["scope_organization_pk"])
            if not st["applies"] or st["requires"] == A.REQUIRES_NONE or str(st["next_person_pk"]) != str(user.person_pk):
                continue
            total, _ = A.bills_summary(cur, txn["financial_transaction_pk"])
            bills = _bills(cur, txn["financial_transaction_pk"])["items"]
            items.append({
                "financial_transaction_pk": txn["financial_transaction_pk"], "transaction_reference": txn["transaction_reference"],
                "transaction_type": txn["transaction_type"], "transaction_date": txn["transaction_date"], "head_name": txn["head_name"],
                "amount": txn["amount"], "description": txn["description"], "organization_name": txn["organization_name"],
                "recorded_by_name": txn["recorded_by_name"], "member_name": txn["member_name"], "stage": st["next_stage"],
                "position_code": st["next_position"], "cover_reason": st["next_cover_reason"], "requires": st["requires"],
                "limit": st["limit"], "steps": st["steps"], "bills": bills, "bills_total": total,
            })
        return {"items": items, "total": len(items)}
