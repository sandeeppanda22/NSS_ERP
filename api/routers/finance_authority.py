"""
NSS ERP — Finance: Bye-Law disbursement authority (Kendra / central Mahila Sangha).

``/api/v1/finance`` (6 endpoints). A payment, or a transfer OUT of a Kendra or central Mahila
Sangha scope, may only move money on the Bye-Law's terms (see ``api/services/finance_authority.py``,
the one place the rules live):

  GET  /payments/{pk}/authority      \\  whether the controls apply, what is recorded, the next step
  PUT  /payments/{pk}/authority       |  record the Governing Body resolution, purpose, (Kendra) the President's order
  POST /payments/{pk}/countersign    /   the Secretary's countersignature after the Treasurer has disbursed
  GET / PUT / POST  /transfers/{pk}/authority | /countersign   the same for transfers

The Treasurer's signature is not an endpoint: it is stamped when the Treasurer moves the payment to
INITIATED (transfer: EXECUTED) through the ordinary ``/transition``. Auth: FINANCE_VIEW to read,
FINANCE_MANAGE (or APPROVE) to write, admin scope on the scope's organization — and, for the signatures,
the live Treasurer / Secretary seat (a permission alone cannot sign).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.routers import finance as F
from api.schemas import finance as S
from api.services import finance_authority as FA
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE = F._VIEW, F._MANAGE


def _payment_context(cur, user: UserContext, payment_pk, action: str, *, lock: bool = False) -> tuple[dict, object]:
    cur.execute(
        "SELECT financial_payment_pk, payment_reference, financial_transaction_pk, status "
        "FROM nss.financial_payment WHERE financial_payment_pk = %s AND is_active = TRUE" + (" FOR UPDATE" if lock else ""),
        (str(payment_pk),),
    )
    payment = F._fetch_one(cur)
    if payment is None:
        raise F._not_found("Payment")
    txn = F._txn_row(cur, user, payment["financial_transaction_pk"], action)
    return payment, txn["scope_organization_pk"]


def _transfer_context(cur, user: UserContext, transfer_pk, action: str, *, lock: bool = False) -> tuple[dict, object]:
    transfer = F._transfer_row(cur, user, transfer_pk, action, lock=lock)
    return transfer, F._scope_row(cur, transfer["source_scope_pk"])["organization_pk"]


def _state(cur, kind: str, row: dict, org_pk) -> dict:
    pk = row["financial_payment_pk" if kind == "payment" else "financial_transfer_pk"]
    return FA.describe(cur, kind, pk, FA.basis_for_org(cur, org_pk), row["status"])


def _write(cur, user: UserContext, kind: str, row: dict, org_pk, body: S.AuthorityWrite) -> dict:
    basis = FA.basis_for_org(cur, org_pk)
    if basis is None:
        raise F._invalid("No Bye-Law disbursement rule applies to this level; there is no authority to record (FIN-BR-044).")
    pk = row["financial_payment_pk" if kind == "payment" else "financial_transfer_pk"]
    FA.record(cur, user.actor_pk, kind, pk, basis, row["status"], body.model_dump())
    table = "financial_payment" if kind == "payment" else "financial_transfer"
    F._audit(cur, user, "UPDATE", table, pk, f"Recorded the Bye-Law disbursement authority ({basis}) for {kind} {pk}",
             {"resolution_reference": body.resolution_reference, "purpose": body.purpose_code,
              "president_order_reference": body.president_order_reference})
    return _state(cur, kind, row, org_pk)


def _countersign(cur, user: UserContext, kind: str, row: dict, org_pk) -> dict:
    pk = row["financial_payment_pk" if kind == "payment" else "financial_transfer_pk"]
    FA.countersign(cur, user.person_pk, kind, pk, org_pk, row["status"])
    table = "financial_payment" if kind == "payment" else "financial_transfer"
    F._audit(cur, user, "APPROVE", table, pk, f"Secretary countersigned {kind} {pk} (joint operation, Bye-Law F[b])")
    return _state(cur, kind, row, org_pk)


@router.get("/payments/{payment_pk}/authority", response_model=S.AuthorityState)
def get_payment_authority(payment_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        payment, org_pk = _payment_context(cur, user, payment_pk, "view this payment")
        return _state(cur, "payment", payment, org_pk)


@router.put("/payments/{payment_pk}/authority", response_model=S.AuthorityState)
def put_payment_authority(payment_pk: UUID, body: S.AuthorityWrite, user: UserContext = Depends(_MANAGE),
                          conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        payment, org_pk = _payment_context(cur, user, payment_pk, "record the authority for this payment", lock=True)
        return _write(cur, user, "payment", payment, org_pk, body)


@router.post("/payments/{payment_pk}/countersign", response_model=S.AuthorityState)
def countersign_payment(payment_pk: UUID, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        payment, org_pk = _payment_context(cur, user, payment_pk, "countersign this payment", lock=True)
        return _countersign(cur, user, "payment", payment, org_pk)


@router.get("/transfers/{transfer_pk}/authority", response_model=S.AuthorityState)
def get_transfer_authority(transfer_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        transfer, org_pk = _transfer_context(cur, user, transfer_pk, "view this transfer")
        return _state(cur, "transfer", transfer, org_pk)


@router.put("/transfers/{transfer_pk}/authority", response_model=S.AuthorityState)
def put_transfer_authority(transfer_pk: UUID, body: S.AuthorityWrite, user: UserContext = Depends(_MANAGE),
                           conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        transfer, org_pk = _transfer_context(cur, user, transfer_pk, "record the authority for this transfer", lock=True)
        return _write(cur, user, "transfer", transfer, org_pk, body)


@router.post("/transfers/{transfer_pk}/countersign", response_model=S.AuthorityState)
def countersign_transfer(transfer_pk: UUID, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        transfer, org_pk = _transfer_context(cur, user, transfer_pk, "countersign this transfer", lock=True)
        return _countersign(cur, user, "transfer", transfer, org_pk)
