"""
NSS ERP — Finance: downloadable PDF receipts (owner request 2026-11-17).

``/api/v1/finance`` — every payment made in the app ends in an ISSUED receipt (api/routers/finance_upi.py books a paid UPI request and
issues its receipt; administrators issue the others). This router turns a receipt into the PDF of ``api/services/receipt_pdf.py``:

  GET /my-pranami/receipts/{receipt_pk}/pdf   the CALLER's own receipt, any time        login only (own receipts only)
  GET /receipts/{receipt_pk}/pdf              any receipt of the caller's admin scope   FINANCE_VIEW + admin scope
  GET /my-pranami/requests/{request_pk}/summary-pdf   the CALLER's own paid payment: a one-page summary of what it covered (owner 2026-11-20)

A member can only fetch a receipt of a counted (POSTED / SETTLED) income entry that is linked to them by person or Sangha Sevi, and
only while it is ISSUED; anything else - someone else's receipt, a draft, an unknown id - is the same plain 404, so nothing can be
probed. An administrator may also fetch a CANCELLED receipt (it is stamped CANCELLED); a DRAFT is not a receipt yet (422).
"""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from api.database import get_connection
from api.dependencies.auth import get_current_user
from api.routers import finance as F
from api.services import receipt_pdf
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW = F._VIEW

_SELECT = f"""
    SELECT r.financial_receipt_pk, r.receipt_number, r.receipt_date, r.amount, r.status, r.cancellation_reason,
           r.instrument_reference, t.transaction_reference, t.person_pk AS txn_person_pk, t.sangha_sevi_pk AS txn_sangha_sevi_pk,
           t.status AS txn_status, r.person_pk AS receipt_person_pk, fs.organization_pk AS scope_organization_pk,
           COALESCE(r.received_from, {F._PERSON_NAME_SQL.format(a='p')}) AS received_from,
           ss.sangha_sevi_id, home.organization_name AS member_sangha, h.head_name, fy.year_code,
           md.value_name AS payment_method_name,
           COALESCE(o.organization_name, fs.scope_name) AS received_by
      FROM nss.financial_receipt r
      JOIN nss.financial_transaction t ON t.financial_transaction_pk = r.financial_transaction_pk
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
      JOIN nss.financial_year fy ON fy.financial_year_pk = t.financial_year_pk
      LEFT JOIN nss.finance_head h ON h.finance_head_pk = t.finance_head_pk
      LEFT JOIN nss.organization o ON o.organization_pk = fs.organization_pk
      LEFT JOIN nss.master_data md ON md.master_data_pk = r.payment_method_master_data_pk
      LEFT JOIN nss.person p ON p.person_pk = COALESCE(r.person_pk, t.person_pk)
      LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = t.sangha_sevi_pk
      LEFT JOIN nss.organization home ON home.organization_pk = ss.organization_pk
     WHERE r.financial_receipt_pk = %s AND r.is_active = TRUE AND t.is_active = TRUE
"""


def _pdf_response(row: dict) -> Response:
    data = {k: row.get(k) for k in receipt_pdf.RECEIPT_FIELDS}
    data["transaction_reference"] = row.get("transaction_reference")
    body = receipt_pdf.build_receipt_pdf(data)
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(row["receipt_number"])) or "receipt"
    return Response(content=body, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="NSS-Receipt-{safe}.pdf"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/my-pranami/receipts/{receipt_pk}/pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def my_receipt_pdf(receipt_pk: UUID, user: UserContext = Depends(get_current_user), conn=Depends(get_connection)):
    """The signed-in member's OWN receipt as a PDF - available whenever they want it. Anyone else's, a draft or an unknown id: 404."""
    with conn.cursor() as cur:
        cur.execute(_SELECT, (str(receipt_pk),))
        row = F._fetch_one(cur)
    mine = row is not None and (
        (user.person_pk is not None and str(row["txn_person_pk"] or "") == str(user.person_pk))
        or (user.actor_pk is not None and str(row["txn_sangha_sevi_pk"] or "") == str(user.actor_pk)))
    if not mine or row["status"] != "ISSUED" or row["txn_status"] not in F._COUNTED_TXN_STATUSES:
        raise F._not_found("Receipt")
    return _pdf_response(row)


_SUMMARY_SELECT = f"""
    SELECT r.upi_payment_request_pk, r.request_reference, r.status, r.paid_at, r.paid_amount, r.provider_payment_id, r.payer_person_pk,
           r.financial_receipt_pk, r.financial_transaction_pk, h.head_name,
           COALESCE(r.payer_name, {F._PERSON_NAME_SQL.format(a='p')}) AS received_from,
           ss.sangha_sevi_id, home.organization_name AS member_sangha, COALESCE(o.organization_name, fs.scope_name) AS paid_to
      FROM nss.upi_payment_request r
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = r.financial_scope_pk
      LEFT JOIN nss.organization o ON o.organization_pk = fs.organization_pk
      LEFT JOIN nss.finance_head h ON h.finance_head_pk = r.finance_head_pk
      LEFT JOIN nss.person p ON p.person_pk = r.payer_person_pk
      LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = r.payer_sangha_sevi_pk
      LEFT JOIN nss.organization home ON home.organization_pk = ss.organization_pk
     WHERE r.upi_payment_request_pk = %s AND r.is_active = TRUE
"""

_SUMMARY_LINES = """
    SELECT h.head_name, l.amount, rc.receipt_number, md.value_name AS payment_method_name
      FROM nss.upi_payment_request_line l
      JOIN nss.finance_head h ON h.finance_head_pk = l.finance_head_pk
      LEFT JOIN nss.financial_receipt rc ON rc.financial_receipt_pk = l.financial_receipt_pk
      LEFT JOIN nss.master_data md ON md.master_data_pk = rc.payment_method_master_data_pk
     WHERE l.upi_payment_request_pk = %s AND l.is_active = TRUE ORDER BY l.line_no
"""

_SUMMARY_SINGLE = """
    SELECT rc.receipt_number, md.value_name AS payment_method_name
      FROM nss.financial_receipt rc
      LEFT JOIN nss.master_data md ON md.master_data_pk = rc.payment_method_master_data_pk
     WHERE rc.financial_receipt_pk = %s
"""


@router.get("/my-pranami/requests/{request_pk}/summary-pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def my_payment_summary_pdf(request_pk: UUID, user: UserContext = Depends(get_current_user), conn=Depends(get_connection)):
    """
    The signed-in member's OWN paid payment as a one-page summary: every contribution it covered with that contribution's own receipt number
    and the total (a printout only - no receipt number of its own, the books are untouched). Someone else's payment, one that is not paid and
    booked yet, or an unknown id: the same plain 404.
    """
    with conn.cursor() as cur:
        cur.execute(_SUMMARY_SELECT, (str(request_pk),))
        row = F._fetch_one(cur)
        booked = row is not None and row["status"] == "PAID" and row["financial_transaction_pk"] is not None
        if not booked or user.person_pk is None or str(row["payer_person_pk"] or "") != str(user.person_pk):
            raise F._not_found("Payment")
        cur.execute(_SUMMARY_LINES, (str(request_pk),))
        items = F._fetch_all(cur)
        method = items[0]["payment_method_name"] if items else None
        if not items:                                              # an ordinary single-head payment: one item, its one receipt
            single = {"receipt_number": None, "payment_method_name": None}
            if row["financial_receipt_pk"]:
                cur.execute(_SUMMARY_SINGLE, (str(row["financial_receipt_pk"]),))
                single = F._fetch_one(cur) or single
            items = [{"head_name": row["head_name"], "amount": row["paid_amount"], "receipt_number": single["receipt_number"]}]
            method = single["payment_method_name"]
    data = {k: row.get(k) for k in receipt_pdf.SUMMARY_FIELDS}
    data["payment_method_name"] = method
    body = receipt_pdf.build_payment_summary_pdf(data, items)
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(row["request_reference"])) or "payment"
    return Response(content=body, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="NSS-Payment-{safe}.pdf"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/receipts/{receipt_pk}/pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def receipt_pdf_for_admin(receipt_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    """Any receipt inside the caller's admin scope as a PDF. A CANCELLED one is stamped; a DRAFT is not a receipt yet."""
    with conn.cursor() as cur:
        cur.execute(_SELECT, (str(receipt_pk),))
        row = F._fetch_one(cur)
        if row is None:
            raise F._not_found("Receipt")
        F._require_org_access(cur, user, row["scope_organization_pk"], "download this receipt")
    if row["status"] not in ("ISSUED", "CANCELLED"):
        raise F._invalid("A draft receipt has not been issued yet; issue it first to download the PDF.")
    return _pdf_response(row)
