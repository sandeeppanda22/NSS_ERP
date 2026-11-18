"""
NSS ERP — Finance UPI router (Tier 12): collecting money by UPI through a payment gateway.

  GET   /api/v1/finance/payment-requests | POST            list / ask a payer to pay by UPI (treasurer)
  GET   /api/v1/finance/payment-requests/{pk}              detail
  POST  /api/v1/finance/payment-requests/{pk}/transition   cancel an unpaid request
  POST  /api/v1/finance/payment-requests/{pk}/refresh      ask the gateway what happened (a missed webhook)
  POST  /api/v1/finance/payment-requests/{pk}/post         book a PAID request that waited for review
  POST  /api/v1/finance/payment-requests/{pk}/mock-pay     DEV/DEMO ONLY: simulate the gateway (MOCK provider)
  GET   /api/v1/finance/my-pranami/heads                   what the signed-in member can pay by UPI
  POST  /api/v1/finance/my-pranami/pay                     a member pays their OWN Pranami
  GET   /api/v1/finance/my-pranami/requests/{pk}           the member's own request (status polling)
  POST  /api/v1/finance/gateway/webhook/{provider}         the gateway's signed callback (NO login)

How money becomes a posted transaction (the only path):
  1. a payment request is created for a finance head; the HEAD decides the scope, the fund and the Sangha's
     receiving account (and so which gateway credential set is used);
  2. the gateway collects the payment and POSTs a webhook;
  3. the webhook is believed ONLY if its signature verifies with that account's webhook secret (from the server
     environment, never the database). A browser redirect, a status poll by the member or a typed UTR proves nothing;
  4. the event is recorded once (provider event id is unique among signed events - replays are no-ops);
  5. the paid amount must equal the requested amount and the head's usual rules must still hold (open year, active
     scope / fund / head ...); then the transaction is POSTED and the receipt ISSUED automatically (system actor).
     Anything else leaves the request PAID with a review_reason for a treasurer to resolve - money is never lost and
     never booked on a guess.

Security notes:
  - the webhook is the one unauthenticated route; it is rate limited per IP, size capped, answers 404 when the
    provider is not enabled, ignores events for unknown orders WITHOUT storing them (so strangers cannot grow the
    table), logs a bad signature only when it names a real request, and returns 401 (a RESPONSE, not an exception, so
    that forensic row is committed). It commits BEFORE answering, so a failure surfaces as a 5xx the gateway retries.
  - a member can only ever create requests for themselves (the payer is the token), only for Pranami + UPI heads of
    their own Sangha, rate limited per user and capped in number of unpaid requests;
  - member-facing responses expose no review notes, account details or internal ids beyond the request itself.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from psycopg2.extras import Json

from api.config import settings
from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.helpers import get_master_data_pk, log_audit, next_id
from api.rate_limit import limiter, user_or_ip_key
from api.routers import finance as F
from api.routers.finance_setup import account_ready
from api.schemas import finance as S
from api.services import finance_contribution as FC
from api.services import upi_gateway
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE, _APPROVE = F._VIEW, F._MANAGE, F._APPROVE
_MAX_OPEN_REQUESTS_PER_MEMBER = 5
_STORED_PAYLOAD_LIMIT = 16384
_UNPAID = ("CREATED", "PENDING")


# ═══════════════════════════════════════════════════════════════════════
# Reading requests
# ═══════════════════════════════════════════════════════════════════════

_EFFECTIVE_STATUS = "CASE WHEN r.status IN ('CREATED', 'PENDING') AND r.expires_at < NOW() THEN 'EXPIRED' ELSE r.status END"
_REQ_FROM = """
      FROM nss.upi_payment_request r
      JOIN nss.finance_head h ON h.finance_head_pk = r.finance_head_pk
      JOIN nss.financial_account a ON a.financial_account_pk = r.financial_account_pk
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = r.financial_scope_pk
      LEFT JOIN nss.organization o ON o.organization_pk = a.organization_pk
      LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = r.payer_sangha_sevi_pk
      LEFT JOIN nss.financial_transaction t ON t.financial_transaction_pk = r.financial_transaction_pk
      LEFT JOIN nss.financial_receipt rc ON rc.financial_receipt_pk = r.financial_receipt_pk
"""
_REQ_SELECT = f"""
    SELECT r.upi_payment_request_pk, r.request_reference, r.finance_head_pk,
           CASE WHEN (SELECT COUNT(*) FROM nss.upi_payment_request_line l WHERE l.upi_payment_request_pk = r.upi_payment_request_pk AND l.is_active = TRUE) > 0
                THEN 'Several contributions' ELSE h.head_name END AS head_name,
           (SELECT COUNT(*) FROM nss.upi_payment_request_line l WHERE l.upi_payment_request_pk = r.upi_payment_request_pk AND l.is_active = TRUE) AS line_count,
           r.financial_account_pk,
           a.account_label, a.upi_vpa, o.organization_name, r.financial_scope_pk, fs.scope_code, r.amount,
           ss.sangha_sevi_id AS payer_sangha_sevi_id, r.payer_name, r.note, r.provider, r.provider_order_id, r.pay_url, r.upi_uri,
           r.expires_at, {_EFFECTIVE_STATUS} AS status, r.provider_payment_id, r.paid_amount, r.paid_at,
           r.failure_reason, r.review_reason, t.transaction_reference, rc.receipt_number, r.financial_receipt_pk, r.created_at
""" + _REQ_FROM


def _request_response(cur, pk) -> dict:
    cur.execute(_REQ_SELECT + " WHERE r.upi_payment_request_pk = %s", (str(pk),))
    return F._fetch_one(cur)


def _load_request(cur, pk, *, lock: bool = False) -> dict:
    """The stored request with the pieces the logic needs (account credential ref, scope organization)."""
    cur.execute(
        """
        SELECT r.*, fs.organization_pk AS scope_organization_pk, a.gateway_credential_ref, a.gateway_merchant_ref,
               a.organization_pk AS account_organization_pk
          FROM nss.upi_payment_request r
          JOIN nss.financial_scope fs ON fs.financial_scope_pk = r.financial_scope_pk
          JOIN nss.financial_account a ON a.financial_account_pk = r.financial_account_pk
         WHERE r.upi_payment_request_pk = %s AND r.is_active = TRUE
        """ + (" FOR UPDATE OF r" if lock else ""),
        (str(pk),),
    )
    row = F._fetch_one(cur)
    if row is None:
        raise F._not_found("Payment request")
    return row


def _member_items(cur, request_pk) -> list[dict]:
    """The contributions a multi-item payment covers (empty for an ordinary single-head payment), each with its own receipt once booked."""
    cur.execute(
        """
        SELECT h.head_name, l.amount, rc.receipt_number, l.financial_receipt_pk
          FROM nss.upi_payment_request_line l
          JOIN nss.finance_head h ON h.finance_head_pk = l.finance_head_pk
          LEFT JOIN nss.financial_receipt rc ON rc.financial_receipt_pk = l.financial_receipt_pk
         WHERE l.upi_payment_request_pk = %s AND l.is_active = TRUE ORDER BY l.line_no
        """,
        (str(request_pk),),
    )
    return F._fetch_all(cur)


def _member_view(cur, row: dict) -> dict:
    out = _member_view_fields(row)
    out["items"] = _member_items(cur, row["upi_payment_request_pk"])
    return out


def _member_view_fields(row: dict) -> dict:
    return {k: row[k] for k in ("upi_payment_request_pk", "request_reference", "head_name", "organization_name", "amount", "status",
                                "pay_url", "upi_uri", "expires_at", "paid_at", "receipt_number", "financial_receipt_pk")}


@router.get("/payment-requests", response_model=S.PaymentRequestListResponse)
def list_payment_requests(
    q: str | None = Query(None, description="Matches reference, payee name or member id"),
    status_filter: str | None = Query(None, alias="status"),
    finance_head_pk: UUID | None = Query(None),
    needs_review: bool = Query(False, description="PAID but not yet posted"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = F._visible(cur, user, "fs.organization_pk")
        where = ["r.is_active = TRUE", vis]
        if status_filter:
            where.append(f"({_EFFECTIVE_STATUS}) = %s"); params.append(status_filter)
        if finance_head_pk:
            where.append("r.finance_head_pk = %s"); params.append(str(finance_head_pk))
        if needs_review:
            where.append("r.status = 'PAID' AND r.financial_transaction_pk IS NULL")
        if q and q.strip():
            where.append("(r.request_reference ILIKE %s OR r.payer_name ILIKE %s OR ss.sangha_sevi_id ILIKE %s)")
            params += [f"%{q.strip()}%"] * 3
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_REQ_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_REQ_SELECT + f" WHERE {where_sql} ORDER BY r.created_at DESC LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return F._paged(F._fetch_all(cur), total, page, page_size)


@router.get("/payment-requests/{request_pk}", response_model=S.PaymentRequestResponse)
def get_payment_request(request_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        req = _load_request(cur, request_pk)
        F._require_org_access(cur, user, req["scope_organization_pk"], "view this payment request")
        return _request_response(cur, request_pk)


# ═══════════════════════════════════════════════════════════════════════
# Creating requests
# ═══════════════════════════════════════════════════════════════════════

def _max_amount() -> Decimal:
    return Decimal(settings.UPI_MAX_AMOUNT)


def _min_amount() -> Decimal:
    return Decimal(settings.UPI_MIN_AMOUNT)


def _check_amount_limits(amount: Decimal) -> None:
    """One UPI payment (the TOTAL, for a multi-item payment) must be between the configured minimum and maximum."""
    if amount < _min_amount():
        raise F._invalid(f"A UPI payment must be at least Rs. {_min_amount():,.2f}.")
    if amount > _max_amount():
        raise F._invalid(f"A single UPI payment is limited to {_max_amount():,.2f}.")


def _prepare_collection(cur, head_pk) -> tuple[dict, dict, dict | None, dict]:
    """
    Validate that a head can be collected by UPI right now and return (head, scope, fund, account): an ACTIVE INCOME head of a Sangha
    with an active collection scope / fund and an active receiving account of the same Sangha, obeying its own rules. Every failure is
    a 422 (a mis-configured head).
    """
    head = F._head_row(cur, head_pk)
    if head["status"] != "ACTIVE" or head["direction"] != "INCOME" or not head["allow_upi"] or head["organization_pk"] is None:
        raise F._invalid("This finance head cannot be collected by UPI.")
    if not head["collection_scope_pk"] or not head["collection_account_pk"]:
        raise F._invalid("This finance head has no collection scope or receiving account configured.")
    scope = F._scope_row(cur, head["collection_scope_pk"])
    fund = F._fund_row(cur, head["collection_fund_pk"]) if head["collection_fund_pk"] else None
    if scope["status"] != "ACTIVE" or not F._same_org(scope["organization_pk"], head["organization_pk"]):
        raise F._invalid("The head's collection scope is not active for this organization.")
    if fund is not None and (fund["status"] != "ACTIVE" or str(fund["financial_scope_pk"]) != str(scope["financial_scope_pk"])):
        raise F._invalid("The head's collection fund is not active in its collection scope.")
    F._check_head(head, scope=scope, txn_type="INCOME", fund=fund)           # the head's own rules, at request time
    cur.execute(
        "SELECT financial_account_pk, organization_pk, account_label, upi_vpa, gateway_provider, gateway_credential_ref, "
        "gateway_merchant_ref, status FROM nss.financial_account WHERE financial_account_pk = %s AND is_active = TRUE",
        (str(head["collection_account_pk"]),),
    )
    account = F._fetch_one(cur)
    if account is None or account["status"] != "ACTIVE" or not F._same_org(account["organization_pk"], head["organization_pk"]):
        raise F._invalid("The head's receiving account is not active for this organization.")
    return head, scope, fund, account


def _open_order_and_store(cur, *, account: dict, head: dict, scope: dict, fund: dict | None, amount: Decimal, description: str,
                          payer_person_pk, payer_sevi_pk, payer_name, note, actor_pk) -> str:
    """Ask the gateway for ONE order of *amount* into *account* and store the request (head / scope / fund = the first head's). Returns its pk."""
    _check_amount_limits(amount)                       # the last line of defence: every way of creating a request ends here
    try:
        provider = upi_gateway.get_provider(account["gateway_provider"])
        creds = upi_gateway.credentials_for(account["gateway_credential_ref"])
    except upi_gateway.GatewayUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"UPI collection is not available: {exc}")
    cur.execute("SELECT organization_name FROM nss.organization WHERE organization_pk = %s", (str(head["organization_pk"]),))
    org_name = cur.fetchone()[0]
    reference = next_id(cur, "UPI_PAYMENT_REQUEST")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.UPI_REQUEST_EXPIRY_MINUTES)
    try:
        order = provider.create_order(
            creds=creds, reference=reference, amount=amount, description=f"{description} - {org_name}"[:200],
            payer_name=payer_name, expires_at=expires_at, vpa=account["upi_vpa"], payee_name=org_name[:60],
            merchant_ref=account["gateway_merchant_ref"],
        )
    except upi_gateway.GatewayError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    cur.execute(
        """
        INSERT INTO nss.upi_payment_request
            (request_reference, financial_account_pk, finance_head_pk, financial_scope_pk, fund_master_pk, amount,
             payer_person_pk, payer_sangha_sevi_pk, payer_name, note, provider, provider_order_id, pay_url, upi_uri,
             expires_at, status, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', %s)
        RETURNING upi_payment_request_pk
        """,
        (reference, str(account["financial_account_pk"]), str(head["finance_head_pk"]), str(scope["financial_scope_pk"]),
         str(fund["fund_master_pk"]) if fund else None, amount,
         str(payer_person_pk) if payer_person_pk else None, str(payer_sevi_pk) if payer_sevi_pk else None,
         F._clean(payer_name), F._clean(note), provider.name, order.provider_order_id, order.pay_url, order.upi_uri,
         order.expires_at, actor_pk),
    )
    return cur.fetchone()[0]


def _create_request(cur, *, head_pk, amount: Decimal, payer_person_pk, payer_sevi_pk, payer_name, note, actor_pk) -> str:
    """
    Validate the head's collection set-up, ask the gateway for an order, store the request. Every failure is an
    HTTPException: 422 for a mis-configured head, 503 when UPI collection is off / not configured for the account,
    502 when the gateway itself failed. Returns the request pk.
    """
    _check_amount_limits(amount)
    head, scope, fund, account = _prepare_collection(cur, head_pk)
    return _open_order_and_store(cur, account=account, head=head, scope=scope, fund=fund, amount=amount, description=head["head_name"],
                                 payer_person_pk=payer_person_pk, payer_sevi_pk=payer_sevi_pk, payer_name=payer_name, note=note,
                                 actor_pk=actor_pk)


def _create_multi_request(cur, *, items: list[tuple], payer_person_pk, payer_sevi_pk, payer_name, actor_pk) -> str:
    """
    One UPI payment for SEVERAL contributions: ``items`` is [(head_pk, amount), ...]. Every head must collect into the SAME receiving
    account (one payment goes to one account, so one Sangha), each is validated exactly like a single payment, and the request is one
    gateway order for the total with one line per contribution. Returns the request pk.
    """
    if len({str(h) for h, _ in items}) != len(items):
        raise F._invalid("Each contribution can be paid once in a single payment.")
    total = sum((a for _, a in items), Decimal("0"))
    if total > _max_amount():
        raise F._invalid(f"A single UPI payment is limited to {_max_amount():,.2f}; pay fewer items together.")
    _check_amount_limits(total)
    prepared = [_prepare_collection(cur, h) for h, _ in items]
    accounts = {str(p[3]["financial_account_pk"]) for p in prepared}
    if len(accounts) != 1:
        raise F._invalid("These contributions are collected into different accounts (different Sangha): pay each Sangha's contributions separately.")
    head, scope, fund, account = prepared[0]
    request_pk = _open_order_and_store(
        cur, account=account, head=head, scope=scope, fund=fund, amount=total, description=f"{len(items)} contributions",
        payer_person_pk=payer_person_pk, payer_sevi_pk=payer_sevi_pk, payer_name=payer_name,
        note="; ".join(p[0]["head_name"] for p in prepared)[:500], actor_pk=actor_pk)
    for n, ((h, amount), (hd, sc, fd, _acc)) in enumerate(zip(items, prepared), start=1):
        cur.execute(
            "INSERT INTO nss.upi_payment_request_line (upi_payment_request_pk, line_no, finance_head_pk, financial_scope_pk, "
            "fund_master_pk, amount, created_by_sangha_sevi_pk) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (str(request_pk), n, str(hd["finance_head_pk"]), str(sc["financial_scope_pk"]),
             str(fd["fund_master_pk"]) if fd else None, amount, actor_pk),
        )
    return request_pk


@router.post("/payment-requests", response_model=S.PaymentRequestResponse, status_code=status.HTTP_201_CREATED)
def create_payment_request(body: S.PaymentRequestCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """A treasurer asks someone to pay by UPI. FINANCE_MANAGE + admin scope on the head's Sangha."""
    with conn.cursor() as cur:
        head = F._head_row(cur, body.finance_head_pk)
        if head["organization_pk"] is None:
            raise F._invalid("A Kendra template cannot collect money; use the Sangha's own head.")
        F._require_org_access(cur, user, head["organization_pk"], "collect money for this organization")
        person_pk = sevi_pk = None
        if F._clean(body.sangha_sevi_id):
            sevi_pk, person_pk = F._resolve_member(cur, user, body.sangha_sevi_id)
        pk = _create_request(cur, head_pk=body.finance_head_pk, amount=body.amount, payer_person_pk=person_pk,
                             payer_sevi_pk=sevi_pk, payer_name=body.payer_name, note=body.note, actor_pk=user.actor_pk)
        F._audit(cur, user, "CREATE", "upi_payment_request", pk, f"Asked for a UPI payment of {body.amount}",
                 {"head": head["head_code"], "amount": str(body.amount)})
        return _request_response(cur, pk)


@router.post("/payment-requests/{request_pk}/transition", response_model=S.PaymentRequestResponse)
def transition_payment_request(request_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE),
                               conn=Depends(get_write_connection)):
    """Cancel a request that has not been paid. NOTE: the gateway link itself stays payable until it expires; a payment
    that still arrives on a cancelled request is recorded as PAID and held for review (never auto-booked)."""
    with conn.cursor() as cur:
        req = _load_request(cur, request_pk, lock=True)
        F._require_org_access(cur, user, req["scope_organization_pk"], "change this payment request")
        F._guard_transition(user, "payment_request", req["status"], body.status, body.remarks, None)
        F._update_row(cur, user, "upi_payment_request", "upi_payment_request_pk", request_pk,
                      {"status": body.status, "failure_reason": F._clean(body.remarks)})
        F._audit(cur, user, "STATUS_CHANGE", "upi_payment_request", request_pk, f"Request {req['request_reference']} {req['status']} -> {body.status}",
                 {"from": req["status"], "to": body.status, "remarks": F._clean(body.remarks)})
        return _request_response(cur, request_pk)


# ═══════════════════════════════════════════════════════════════════════
# Turning a paid request into a posted transaction + receipt
# ═══════════════════════════════════════════════════════════════════════

def _book_one(cur, req: dict, year_pk, txn_date, *, head_pk, scope_pk, fund_pk, amount: Decimal, actor_pk, label: str = "") -> tuple:
    """
    Book ONE amount of a paid request: the books' own rules (open year, active scope, the head's rules), the POSTED transaction and its
    ISSUED receipt. Returns (txn_pk, receipt_pk, transaction_reference, receipt_number). Raises HTTPException when the rules refuse it.
    """
    _, head = F._check_transaction(
        cur, year_pk=year_pk, scope_pk=scope_pk, fund_pk=fund_pk, txn_date=txn_date, txn_type="INCOME", head_pk=head_pk, amount=amount,
    )
    reference = next_id(cur, "FINANCIAL_TRANSACTION")
    description = f"UPI {req['request_reference']}{label}" + (f" - {req['note']}" if req["note"] else "")
    cur.execute(
        """
        INSERT INTO nss.financial_transaction
            (transaction_reference, financial_year_pk, financial_scope_pk, fund_master_pk, transaction_type,
             finance_head_pk, transaction_category, amount, transaction_date, description, person_pk, sangha_sevi_pk,
             status, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, 'INCOME', %s, %s, %s, %s, %s, %s, %s, 'POSTED', %s) RETURNING financial_transaction_pk
        """,
        (reference, str(year_pk), str(scope_pk), str(fund_pk) if fund_pk else None,
         str(head["finance_head_pk"]), head["head_code"], amount, txn_date, description[:2000],
         str(req["payer_person_pk"]) if req["payer_person_pk"] else None,
         str(req["payer_sangha_sevi_pk"]) if req["payer_sangha_sevi_pk"] else None, actor_pk),
    )
    txn_pk = cur.fetchone()[0]
    receipt_number = next_id(cur, "FINANCIAL_RECEIPT")
    cur.execute(
        """
        INSERT INTO nss.financial_receipt
            (receipt_number, financial_transaction_pk, receipt_date, amount, received_from,
             payment_method_master_data_pk, instrument_reference, person_pk, status, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ISSUED', %s) RETURNING financial_receipt_pk
        """,
        (receipt_number, str(txn_pk), txn_date, amount, req["payer_name"], get_master_data_pk(cur, "PAYMENT_METHOD", "UPI"),
         req["provider_payment_id"], str(req["payer_person_pk"]) if req["payer_person_pk"] else None, actor_pk),
    )
    receipt_pk = cur.fetchone()[0]
    log_audit(cur, action="UPI_PAYMENT_POSTED", table_name="financial_transaction", record_pk=str(txn_pk), actor_pk=actor_pk,
              module="finance", summary=f"UPI payment {req['request_reference']}{label} booked as {reference} / {receipt_number}",
              detail={"request": req["request_reference"], "amount": str(amount), "system": actor_pk is None})
    return txn_pk, receipt_pk, reference, receipt_number


def _request_lines(cur, request_pk) -> list[dict]:
    cur.execute(
        "SELECT upi_payment_request_line_pk, line_no, finance_head_pk, financial_scope_pk, fund_master_pk, amount, financial_transaction_pk, "
        "financial_receipt_pk FROM nss.upi_payment_request_line WHERE upi_payment_request_pk = %s AND is_active = TRUE ORDER BY line_no",
        (str(request_pk),),
    )
    return F._fetch_all(cur)


def _post_paid_request(cur, request_pk, *, actor_pk) -> str | None:
    """
    Book a PAID request: the transaction (POSTED) and the ISSUED receipt, for the amount that was ACTUALLY received. A request that
    pays several contributions books one transaction + receipt per line, all or nothing (a savepoint), and only for exactly the
    amount asked. Returns None on success (or if already booked) and the reason text when the books' rules refuse it - the caller
    then keeps the request PAID with that review_reason. Genuine defects (a missing PAYMENT_METHOD seed) still raise.
    """
    req = _load_request(cur, request_pk, lock=True)
    if req["status"] != "PAID":
        return "The request is not paid."
    if req["financial_transaction_pk"]:
        return None
    cur.execute("SELECT (%s AT TIME ZONE 'Asia/Kolkata')::date", (req["paid_at"],))
    txn_date = cur.fetchone()[0]
    cur.execute(
        "SELECT financial_year_pk FROM nss.financial_year WHERE is_active = TRUE AND status = 'OPEN' "
        "AND start_date <= %s AND end_date >= %s ORDER BY start_date DESC LIMIT 1", (txn_date, txn_date),
    )
    year = cur.fetchone()
    if year is None:
        return f"No OPEN financial year covers the payment date {txn_date}."
    amount = req["paid_amount"]
    lines = _request_lines(cur, request_pk)
    if not lines:
        try:
            txn_pk, receipt_pk, _ref, _num = _book_one(cur, req, year[0], txn_date, head_pk=req["finance_head_pk"], scope_pk=req["financial_scope_pk"],
                                                    fund_pk=req["fund_master_pk"], amount=amount, actor_pk=actor_pk)
        except HTTPException as exc:
            return str(exc.detail)[:300]
    else:
        if amount != sum((l["amount"] for l in lines), Decimal("0")):
            return ("AMOUNT_MISMATCH: this payment covers several contributions and can only be booked for exactly the amount asked; "
                    "the difference has to be settled with the payer outside the app.")
        cur.execute("SAVEPOINT upi_multi_post")
        booked = []
        try:
            for l in lines:
                booked.append(_book_one(cur, req, year[0], txn_date, head_pk=l["finance_head_pk"], scope_pk=l["financial_scope_pk"],
                                        fund_pk=l["fund_master_pk"], amount=l["amount"], actor_pk=actor_pk,
                                        label=f" ({l['line_no']} of {len(lines)})"))
        except HTTPException as exc:
            cur.execute("ROLLBACK TO SAVEPOINT upi_multi_post")
            return str(exc.detail)[:300]
        cur.execute("RELEASE SAVEPOINT upi_multi_post")
        for l, (t_pk, r_pk, _ref, _num) in zip(lines, booked):
            cur.execute("UPDATE nss.upi_payment_request_line SET financial_transaction_pk = %s, financial_receipt_pk = %s, updated_at = NOW() "
                        "WHERE upi_payment_request_line_pk = %s", (str(t_pk), str(r_pk), str(l["upi_payment_request_line_pk"])))
        txn_pk, receipt_pk = booked[0][0], booked[0][1]
    cur.execute("UPDATE nss.upi_payment_request SET financial_transaction_pk = %s, financial_receipt_pk = %s, review_reason = NULL, "
                "updated_at = NOW() WHERE upi_payment_request_pk = %s", (str(txn_pk), str(receipt_pk), str(request_pk)))
    return None


def _store_event(cur, *, provider, event: upi_gateway.GatewayEvent, payload: dict, request_pk, valid: bool, outcome: str, detail=None):
    """Insert the event row. Returns its pk, or None when a SIGNED event with this id was already recorded (a replay)."""
    stored = payload if len(json.dumps(payload, default=str)) <= _STORED_PAYLOAD_LIMIT else {"truncated": True}
    cur.execute(
        """
        INSERT INTO nss.finance_gateway_event
            (provider, event_id, event_type, upi_payment_request_pk, signature_valid, payload, outcome, detail)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (provider, event_id) WHERE signature_valid = TRUE DO NOTHING
        RETURNING finance_gateway_event_pk
        """,
        (provider, event.event_id[:150], (event.event_type or "")[:80] or None, str(request_pk) if request_pk else None,
         valid, Json(stored, dumps=lambda o: json.dumps(o, default=str)), outcome, detail),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _apply_event(cur, req: dict, event: upi_gateway.GatewayEvent) -> tuple[str, str | None]:
    """Apply a VERIFIED event to a locked request. Returns (outcome, detail)."""
    pk = req["upi_payment_request_pk"]
    if event.status == "PAID":
        if req["status"] == "PAID":
            return "DUPLICATE", "already paid"
        if not event.provider_payment_id:
            # a paid event without a payment id is not evidence we can book against
            return "IGNORED", "paid event carried no payment id"
        received = event.amount if event.amount is not None else req["amount"]
        review = None
        if req["status"] == "CANCELLED":
            review = "PAID_AFTER_CANCELLED: the request had been cancelled but the payer paid through the link."
        elif req["status"] == "EXPIRED":
            review = "PAID_AFTER_EXPIRED: the request had expired."
        elif event.amount is None:
            review = "AMOUNT_NOT_REPORTED: the gateway did not report the amount paid."
        elif event.amount != req["amount"]:
            review = f"AMOUNT_MISMATCH: requested {req['amount']}, received {event.amount}."
        cur.execute(
            "UPDATE nss.upi_payment_request SET status = 'PAID', provider_payment_id = %s, paid_amount = %s, paid_at = NOW(), "
            "failure_reason = NULL, review_reason = %s, updated_at = NOW() WHERE upi_payment_request_pk = %s",
            (event.provider_payment_id, received, review, str(pk)),
        )
        if review is None:
            review = _post_paid_request(cur, pk, actor_pk=None)
            if review is not None:
                cur.execute("UPDATE nss.upi_payment_request SET review_reason = %s WHERE upi_payment_request_pk = %s", (review, str(pk)))
        return ("POSTED", None) if review is None else ("PAID_NEEDS_REVIEW", review)
    if event.status in ("FAILED", "EXPIRED"):
        if req["status"] in _UNPAID:
            cur.execute("UPDATE nss.upi_payment_request SET status = %s, failure_reason = %s, updated_at = NOW() WHERE upi_payment_request_pk = %s",
                        (event.status, f"Reported {event.status.lower()} by the gateway.", str(pk)))
            return event.status, None
        return "IGNORED", f"request already {req['status']}"
    return "IGNORED", "event type needs no action"


def handle_webhook(cur, provider_name: str, headers: dict, raw_body: bytes) -> tuple[int, str]:
    """
    The one place a gateway callback is believed (shared by the real endpoint and the dev 'mock-pay'). Returns
    (HTTP status, outcome). Raises GatewayUnavailable for a provider that is not enabled (-> 404).
    """
    provider = upi_gateway.get_provider(provider_name)
    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        return 400, "BAD_REQUEST"
    if not isinstance(payload, dict):
        return 400, "BAD_REQUEST"
    order_id = provider.peek_order_id(payload)
    req_pk = None
    if order_id:
        cur.execute("SELECT upi_payment_request_pk FROM nss.upi_payment_request WHERE provider = %s AND provider_order_id = %s",
                    (provider.name, order_id[:100]))
        row = cur.fetchone()
        req_pk = row[0] if row else None
    if req_pk is None:
        return 200, "UNKNOWN_REQUEST"              # not stored: strangers must not be able to grow our tables
    req = _load_request(cur, req_pk, lock=True)
    creds = upi_gateway.credentials_for(req["gateway_credential_ref"])      # GatewayUnavailable -> 503, gateway retries later
    try:
        event = provider.parse_event(headers, payload, raw_body)
    except (KeyError, TypeError, AttributeError, ValueError):
        return 400, "BAD_REQUEST"
    valid = provider.verify_signature(secret=creds.webhook_secret, headers=headers, raw_body=raw_body)
    if not valid:
        _store_event(cur, provider=provider.name, event=event, payload=payload, request_pk=req_pk, valid=False,
                     outcome="REJECTED_SIGNATURE", detail="signature did not verify")
        return 401, "REJECTED_SIGNATURE"
    event_pk = _store_event(cur, provider=provider.name, event=event, payload=payload, request_pk=req_pk, valid=True, outcome="IGNORED")
    if event_pk is None:
        return 200, "DUPLICATE"
    outcome, detail = _apply_event(cur, req, event)
    cur.execute("UPDATE nss.finance_gateway_event SET outcome = %s, detail = %s WHERE finance_gateway_event_pk = %s",
                (outcome, (detail or "")[:500] or None, str(event_pk)))
    return 200, outcome


@router.post("/gateway/webhook/{provider}")
@limiter.limit(settings.UPI_WEBHOOK_RATE_LIMIT)
async def gateway_webhook(provider: str, request: Request, conn=Depends(get_write_connection, scope="function")):
    """
    The payment gateway's callback. NO login (the shared write-connection dependency accepts an anonymous caller and
    leaves the audit actor NULL, i.e. a system action): authenticity is the HMAC signature, checked against the receiving
    account's webhook secret (api/services/upi_gateway.py). Answers 404 for a provider that is not enabled.

    The connection dependency has scope="function": it commits when this handler returns but BEFORE the response is
    sent, so a commit failure is a 5xx the gateway retries (never a 200 for work that was lost) - without an explicit
    conn.commit() here, which would escape the test suite's rollback savepoint and leak test rows into a real database.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.UPI_WEBHOOK_MAX_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Payload too large."})
    raw = await request.body()
    if len(raw) > settings.UPI_WEBHOOK_MAX_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Payload too large."})

    def run() -> tuple[int, str]:
        with conn.cursor() as cur:
            return handle_webhook(cur, provider, dict(request.headers), raw)

    try:
        code, outcome = await run_in_threadpool(run)
    except upi_gateway.GatewayUnavailable as exc:      # raised before anything was written
        if provider.upper() not in upi_gateway.enabled_providers() or provider.upper() not in upi_gateway.PROVIDERS:
            return JSONResponse(status_code=404, content={"detail": "Not found."})
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    return JSONResponse(status_code=code, content={"outcome": outcome})


# ═══════════════════════════════════════════════════════════════════════
# Treasurer actions on a request
# ═══════════════════════════════════════════════════════════════════════

@router.post("/payment-requests/{request_pk}/refresh", response_model=S.PaymentRequestResponse)
def refresh_payment_request(request_pk: UUID, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Ask the gateway what happened to an unpaid request (a webhook may have been missed). Idempotent."""
    with conn.cursor() as cur:
        req = _load_request(cur, request_pk, lock=True)
        F._require_org_access(cur, user, req["scope_organization_pk"], "refresh this payment request")
        if req["status"] not in _UNPAID:
            return _request_response(cur, request_pk)
        try:
            provider = upi_gateway.get_provider(req["provider"])
            creds = upi_gateway.credentials_for(req["gateway_credential_ref"])
            event = provider.fetch_order_status(creds=creds, provider_order_id=req["provider_order_id"], merchant_ref=req["gateway_merchant_ref"])
        except upi_gateway.GatewayUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        except upi_gateway.GatewayError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        if event is not None and event.provider_order_id == req["provider_order_id"]:
            event_pk = _store_event(cur, provider=provider.name, event=event, payload={"source": "poll", "status": event.status},
                                    request_pk=request_pk, valid=True, outcome="IGNORED")
            if event_pk is not None:
                outcome, detail = _apply_event(cur, req, event)
                cur.execute("UPDATE nss.finance_gateway_event SET outcome = %s, detail = %s WHERE finance_gateway_event_pk = %s",
                            (outcome, (detail or "")[:500] or None, str(event_pk)))
                F._audit(cur, user, "STATUS_CHANGE", "upi_payment_request", request_pk, f"Refreshed {req['request_reference']}: {outcome}")
        return _request_response(cur, request_pk)


@router.post("/payment-requests/{request_pk}/post", response_model=S.PaymentRequestResponse)
def post_paid_request(request_pk: UUID, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
    """
    Book a PAID request that waited for review (after fixing the cause: opening the year, reactivating the scope ...).
    FINANCE_APPROVE. It books the amount that was ACTUALLY received. A request the books' rules still refuse stays
    unbooked and the reason is returned.
    """
    with conn.cursor() as cur:
        req = _load_request(cur, request_pk, lock=True)
        F._require_org_access(cur, user, req["scope_organization_pk"], "book this payment")
        if req["status"] != "PAID":
            raise F._invalid("Only a PAID request can be booked.")
        if req["financial_transaction_pk"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This payment is already booked.")
        reason = _post_paid_request(cur, request_pk, actor_pk=user.actor_pk)
        if reason is not None:
            cur.execute("UPDATE nss.upi_payment_request SET review_reason = %s WHERE upi_payment_request_pk = %s", (reason, str(request_pk)))
            # a RESPONSE, not an exception: raising would roll back the refreshed review_reason we just stored
            return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": f"Cannot book it yet: {reason}"})
        F._audit(cur, user, "APPROVE", "upi_payment_request", request_pk, f"Booked held UPI payment {req['request_reference']}")
        return _request_response(cur, request_pk)


@router.post("/payment-requests/{request_pk}/mock-pay", response_model=S.PaymentRequestResponse)
def mock_pay(request_pk: UUID, outcome: str = Query("paid", pattern="^(paid|failed|expired)$"),
             amount: Decimal | None = Query(None, gt=0, description="Pay a DIFFERENT amount (to rehearse a mismatch)"),
             user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """
    DEVELOPMENT / DEMO ONLY. Plays the part of the MOCK gateway: builds a webhook, signs it with the account's real
    webhook secret and feeds it through exactly the same handle_webhook() the live endpoint uses. 404 unless the MOCK
    provider is enabled on this server; refuses any request that is not a MOCK request. No money moves.
    """
    if "MOCK" not in upi_gateway.enabled_providers():
        raise F._not_found("Not found")
    with conn.cursor() as cur:
        req = _load_request(cur, request_pk, lock=True)
        F._require_org_access(cur, user, req["scope_organization_pk"], "simulate a payment for this request")
        if req["provider"] != "MOCK":
            raise F._invalid("Only a request created through the MOCK gateway can be simulated.")
        try:
            creds = upi_gateway.credentials_for(req["gateway_credential_ref"])
        except upi_gateway.GatewayUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        kind = {"paid": "payment.paid", "failed": "payment.failed", "expired": "order.expired"}[outcome]
        raw, headers = upi_gateway.build_mock_event(secret=creds.webhook_secret, order_id=req["provider_order_id"], kind=kind,
                                                    amount=amount if amount is not None else req["amount"])
        code, result = handle_webhook(cur, "MOCK", headers, raw)
        if code >= 400:
            raise HTTPException(status_code=code, detail=result)
        F._audit(cur, user, "STATUS_CHANGE", "upi_payment_request", request_pk, f"Simulated {outcome} for {req['request_reference']}: {result}")
        return _request_response(cur, request_pk)


# ═══════════════════════════════════════════════════════════════════════
# Member self-service: pay my own Pranami
# ═══════════════════════════════════════════════════════════════════════

def _member_org(cur, user: UserContext):
    if user.sangha_sevi_pk is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only members of a Sakha can pay Pranami.")
    cur.execute("SELECT organization_pk FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s AND is_active = TRUE", (str(user.sangha_sevi_pk),))
    row = cur.fetchone()
    if row is None or row[0] is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only members of a Sakha can pay Pranami.")
    return row[0]


def _member_destinations(cur, user: UserContext) -> list[str]:
    """The Sangha a member may pay: their OWN Sakha and the Kendra (owner decision 2026-11-10) - never another Sakha."""
    home = str(_member_org(cur, user))
    cur.execute(
        """
        SELECT o.organization_pk FROM nss.organization o
          JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
         WHERE md.value_code = 'KENDRA' AND o.is_active = TRUE
        """
    )
    return [home] + [str(r[0]) for r in cur.fetchall() if str(r[0]) != home]


# The member's contribution cards: every ACTIVE member-visible INCOME head of their OWN Sakha and of the Kendra (the source of an
# all-Sakhas head collects nothing and is never shown - the member sees their own Sakha's copy). Accounts / scopes are LEFT joined
# so a head whose Sangha has not set up payment still shows (as "not available yet") with what the member has already paid.
_CARDS_SQL = """
    SELECT h.finance_head_pk, h.head_name, h.description, h.organization_pk, o.organization_name,
           (mdo.value_code = 'KENDRA') AS is_kendra,
           CASE WHEN cs.scope_type = 'EVENT' THEN cs.scope_name END AS event_name,
           h.fixed_amount, h.due_period, h.allow_part_payment, h.allow_upi,
           (cs.financial_scope_pk IS NOT NULL) AS scope_active,
           a.financial_account_pk, a.upi_vpa, a.gateway_provider, a.gateway_credential_ref
      FROM nss.finance_head h
      JOIN nss.organization o ON o.organization_pk = h.organization_pk
      JOIN nss.master_data mdo ON mdo.master_data_pk = o.organization_type_master_data_pk
      LEFT JOIN nss.financial_account a ON a.financial_account_pk = h.collection_account_pk
                                       AND a.is_active = TRUE AND a.status = 'ACTIVE'
      LEFT JOIN nss.financial_scope cs ON cs.financial_scope_pk = h.collection_scope_pk
                                      AND cs.is_active = TRUE AND cs.status = 'ACTIVE'
     WHERE h.is_active = TRUE AND h.status = 'ACTIVE' AND h.is_pranami = TRUE AND h.direction = 'INCOME'
       AND h.applies_to_all_sakhas = FALSE AND h.organization_pk = ANY(%s::uuid[])
       AND (h.collection_scope_pk IS NULL OR cs.financial_scope_pk IS NOT NULL)      -- a closed event / scope is hidden, not shown as unavailable
     ORDER BY (h.organization_pk = %s::uuid) DESC, o.organization_name, h.display_order, h.head_name
"""
_CARD_FIELDS = ("finance_head_pk", "head_name", "description", "organization_pk", "organization_name", "is_kendra", "event_name",
                "upi_vpa", "fixed_amount", "due_period", "allow_part_payment")


def _member_cards(cur, user: UserContext) -> list[dict]:
    """
    The single source for what a member sees AND may pay: one dict per contribution with its fixed amount, what they paid in the
    current period (POSTED / SETTLED income linked to them), what is waiting in an unexpired UPI request, the paid / due state
    and whether it can be paid right now. The pay endpoint validates against this same list.
    """
    destinations = _member_destinations(cur, user)
    cur.execute(_CARDS_SQL, (destinations, destinations[0]))
    heads = F._fetch_all(cur)
    cur.execute("SELECT (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
    today = cur.fetchone()[0]
    paid: dict = {}
    pending: dict = {}
    if heads:
        pks = [str(h["finance_head_pk"]) for h in heads]
        cur.execute(
            f"""
            SELECT t.finance_head_pk, t.transaction_date, t.amount FROM nss.financial_transaction t
             WHERE t.finance_head_pk = ANY(%s::uuid[]) AND t.is_active = TRUE AND t.transaction_type = 'INCOME'
               AND t.status IN {F._in(F._COUNTED_TXN_STATUSES)}
               AND (t.person_pk = %s OR (%s::uuid IS NOT NULL AND t.sangha_sevi_pk = %s::uuid))
            """,
            (pks, str(user.person_pk), user.actor_pk, user.actor_pk),
        )
        txns = cur.fetchall()
        cur.execute(
            """
            SELECT head_pk, SUM(amt) FROM (
                SELECT r.finance_head_pk AS head_pk, r.amount AS amt FROM nss.upi_payment_request r
                 WHERE r.finance_head_pk = ANY(%s::uuid[]) AND r.payer_person_pk = %s AND r.status IN ('CREATED', 'PENDING')
                   AND r.expires_at > NOW() AND r.is_active = TRUE
                   AND NOT EXISTS (SELECT 1 FROM nss.upi_payment_request_line x WHERE x.upi_payment_request_pk = r.upi_payment_request_pk AND x.is_active = TRUE)
                UNION ALL
                SELECT l.finance_head_pk, l.amount FROM nss.upi_payment_request_line l
                  JOIN nss.upi_payment_request r ON r.upi_payment_request_pk = l.upi_payment_request_pk
                 WHERE l.finance_head_pk = ANY(%s::uuid[]) AND l.is_active = TRUE AND r.payer_person_pk = %s
                   AND r.status IN ('CREATED', 'PENDING') AND r.expires_at > NOW() AND r.is_active = TRUE
            ) pending GROUP BY 1
            """,
            (pks, str(user.person_pk), pks, str(user.person_pk)),
        )
        pending = {str(r[0]): r[1] for r in cur.fetchall()}
        for head in heads:
            window = FC.period_window(head["due_period"], today)
            total = sum((amt for pk, d, amt in txns if str(pk) == str(head["finance_head_pk"])
                         and (window is None or window[0] <= d <= window[1])), Decimal("0"))
            paid[str(head["finance_head_pk"])] = total
    cards = []
    for h in heads:
        key = str(h["finance_head_pk"])
        card = {k: h[k] for k in _CARD_FIELDS}
        card.update(FC.card_state(h["fixed_amount"], paid.get(key, Decimal("0")), pending.get(key, Decimal("0"))))
        card["period_label"] = FC.period_label(h["due_period"], today)
        ready = bool(h["allow_upi"] and h["scope_active"] and h["financial_account_pk"] and account_ready(h))
        card["payable"] = ready
        card["unavailable_reason"] = None if ready else (
            "Online payment is not set up for this contribution yet." if not (h["allow_upi"] and h["financial_account_pk"])
            else "Online payment is temporarily unavailable.")
        cards.append(card)
    return cards


@router.get("/my-pranami/heads", response_model=list[S.MyPayableHead])
def my_payable_heads(user: UserContext = Depends(get_current_user), conn=Depends(get_connection)):
    """The signed-in member's contribution cards: the heads of their OWN Sakha and of the Kendra, each with amount and paid / due."""
    with conn.cursor() as cur:
        return _member_cards(cur, user)


def _check_card_amount(card: dict | None, amount: Decimal) -> None:
    """The rules a member's payment of *amount* towards one contribution card must pass (shared by a single and a multi-item payment)."""
    if card is None or not card["payable"]:
        raise F._invalid("This payment is not available for UPI.")
    if card["fixed_amount"] is None:
        return
    if card["pending_amount"] > 0 and not card["allow_part_payment"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"You already have an unpaid request for {card['head_name']}. Pay it or wait for it to expire.")
    remaining = (card["due_amount"] or Decimal("0")) - (card["pending_amount"] if card["allow_part_payment"] else Decimal("0"))
    if card["allow_part_payment"] and card["due_amount"] and remaining <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Your pending payments already cover what is due for {card['head_name']}. Wait for the bank to confirm them.")
    problem = FC.amount_problem(card, amount, remaining)
    if problem:
        raise F._invalid(f"{card['head_name']}: {problem}" if card.get("head_name") else problem)


def _check_open_request_cap(cur, user: UserContext) -> None:
    cur.execute("SELECT COUNT(*) FROM nss.upi_payment_request WHERE payer_person_pk = %s AND status IN ('CREATED','PENDING') "
                "AND expires_at > NOW() AND is_active = TRUE", (str(user.person_pk),))
    if cur.fetchone()[0] >= _MAX_OPEN_REQUESTS_PER_MEMBER:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="You already have several unpaid UPI requests. Pay or wait for them to expire first.")


@router.post("/my-pranami/pay", response_model=S.MyPayment, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.UPI_PAY_RATE_LIMIT, key_func=user_or_ip_key)
def pay_my_pranami(request: Request, body: S.MyPayRequest, user: UserContext = Depends(get_current_user),
                   conn=Depends(get_write_connection)):
    """
    A member starts a UPI payment to their OWN Sakha or to the Kendra (a Pranami, a card, an event contribution...). The payer
    is the token, never a field, and only member-visible UPI heads of those two Sangha are accepted. A head with a fixed amount
    is checked against what is still due (exact amount, or any part up to it when part payment is allowed). The money is booked
    only when the gateway's signed webhook says it was paid - never because the member's browser says so. The request, and the
    booking that follows, are audited.
    """
    with conn.cursor() as cur:
        # One payment decision per member and head at a time, so two quick taps cannot both pass the "still due" check.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"upi-pay:{user.person_pk}:{body.finance_head_pk}",))
        card = next((c for c in _member_cards(cur, user) if str(c["finance_head_pk"]) == str(body.finance_head_pk)), None)
        _check_card_amount(card, body.amount)
        _check_open_request_cap(cur, user)
        pk = _create_request(cur, head_pk=body.finance_head_pk, amount=body.amount, payer_person_pk=user.person_pk,
                             payer_sevi_pk=user.sangha_sevi_pk, payer_name=None, note=None, actor_pk=user.actor_pk)
        log_audit(cur, action="CREATE", table_name="upi_payment_request", record_pk=str(pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk), module="finance",
                  summary=f"Member started a UPI payment of {body.amount}",
                  detail={"amount": str(body.amount), "self_service": True, "finance_head_pk": str(body.finance_head_pk),
                          "fixed_amount": str(card["fixed_amount"]) if card["fixed_amount"] is not None else None})
        return _member_view(cur, _request_response(cur, pk))


@router.post("/my-pranami/pay-multiple", response_model=S.MyPayment, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.UPI_PAY_RATE_LIMIT, key_func=user_or_ip_key)
def pay_my_pranami_multiple(request: Request, body: S.MyPayMultipleRequest, user: UserContext = Depends(get_current_user),
                            conn=Depends(get_write_connection)):
    """
    A member pays SEVERAL of their own contributions in ONE UPI payment (owner request 2026-11-17). Each item passes exactly the
    checks of a single payment (visible, payable, amount against what is due), the items must all collect into the same receiving
    account (one Sangha: the member's own Sakha, or the Kendra, never both in one payment), and the gateway gets one order for the
    total. When the signed webhook says it is paid, every item is booked as its own transaction with its own ISSUED receipt - all or
    nothing - and the member can download each receipt. The payer is the token, never a field.
    """
    heads = [str(i.finance_head_pk) for i in body.items]
    if len(set(heads)) != len(heads):
        raise F._invalid("Each contribution can be paid once in a single payment.")
    with conn.cursor() as cur:
        for head in sorted(heads):                                    # sorted: two overlapping payments can never lock in opposite order
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"upi-pay:{user.person_pk}:{head}",))
        cards = {str(c["finance_head_pk"]): c for c in _member_cards(cur, user)}
        for item in body.items:
            _check_card_amount(cards.get(str(item.finance_head_pk)), item.amount)
        _check_open_request_cap(cur, user)
        total = sum((i.amount for i in body.items), Decimal("0"))
        pk = _create_multi_request(cur, items=[(i.finance_head_pk, i.amount) for i in body.items], payer_person_pk=user.person_pk,
                                   payer_sevi_pk=user.sangha_sevi_pk, payer_name=None, actor_pk=user.actor_pk)
        log_audit(cur, action="CREATE", table_name="upi_payment_request", record_pk=str(pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk), module="finance",
                  summary=f"Member started one UPI payment of {total} for {len(body.items)} contributions",
                  detail={"amount": str(total), "self_service": True, "multiple": True,
                          "items": [{"finance_head_pk": str(i.finance_head_pk), "amount": str(i.amount)} for i in body.items]})
        return _member_view(cur, _request_response(cur, pk))


@router.get("/my-pranami/requests/{request_pk}", response_model=S.MyPayment)
def my_payment_status(request_pk: UUID, user: UserContext = Depends(get_current_user), conn=Depends(get_connection)):
    """Poll the status of one of the signed-in member's OWN payment requests (anyone else's is a plain 404)."""
    with conn.cursor() as cur:
        req = _load_request(cur, request_pk)
        if str(req["payer_person_pk"] or "") != str(user.person_pk):
            raise F._not_found("Payment request")
        return _member_view(cur, _request_response(cur, request_pk))
