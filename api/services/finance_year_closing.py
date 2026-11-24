"""
NSS ERP — closing the financial year Sangha by Sangha (owner request 2026-11-25: "year closing should be Sakha and Kendra wise").

ONE home for the rules, so the endpoints and the tests share a single implementation:

  The financial year stays ONE calendar record (PLANNED -> OPEN -> CLOSING -> CLOSED, set by the NSS-wide authority). On top of it every
  Sangha - each Sakha, and the Kendra - closes ITS OWN books for the year:

      OPEN ──start closing──▶ CLOSING ──close──▶ CLOSED          (no row in finance_year_closing = the Sangha is still OPEN)

  * CLOSING: the Sangha takes no NEW entries or transfers in that year, but may finish (approve, post, settle, complete) what is in progress.
  * CLOSED: its books are shut. Only possible when the Sangha has nothing unfinished in the year; anything still open is named to it.
  * Who: the Sangha's own finance administrators (a Sakha's seated Treasurer / President / Secretary or an admin given a Finance role, the
    Kendra's finance administrators) - and the NSS ERP Administrator for any - decided in the router (api/routers/finance_closing.py).
  * The YEAR can be CLOSED only when every Sangha with activity in it has closed; the NSS-wide authority's "Close" closes the Sanghas that are
    finished (nothing unfinished) in the same step and refuses, naming each Sangha and what is still open, for the rest. When the year is
    already CLOSING and the last Sangha closes, the year closes by itself.
  * Money on a scope that belongs to no Sangha (global scopes) has no Sangha to close it: unfinished entries there still block the year.
  * "Unfinished" is ALL in-progress work (owner 2026-11-25: "all in-progress work for the FY should be finished before the FY is closed"): transactions
    (DRAFT / PENDING_APPROVAL / APPROVED), transfers (also EXECUTED), draft receipts, payments not yet completed or cancelled, and online payments
    still payable or paid but not yet booked. Closing a scope, a Sangha's books and the year all use the same definition.

Nothing here commits and nothing checks WHO may act.
"""

from fastapi import HTTPException, status

OPEN, CLOSING, CLOSED = "OPEN", "CLOSING", "CLOSED"
STATUSES = (OPEN, CLOSING, CLOSED)
STEPS = {(OPEN, CLOSING), (CLOSING, CLOSED)}
YEAR_STATES_THAT_CAN_CLOSE = ("OPEN", "CLOSING")        # a PLANNED year has nothing to close, a CLOSED one is done

# What "unfinished" means: ONE definition, used by closing a scope, a Sangha and the year (finance.py::_open_work_blockers reads these too).
UNFINISHED_TRANSACTION_STATUSES = ("DRAFT", "PENDING_APPROVAL", "APPROVED")
UNFINISHED_TRANSFER_STATUSES = ("DRAFT", "PENDING_APPROVAL", "APPROVED", "EXECUTED")
# ... and every other piece of in-progress work (owner 2026-11-25: "all in-progress work for the FY should be finished before the FY is closed"):
UNFINISHED_RECEIPT_STATUSES = ("DRAFT",)                                  # not yet ISSUED or CANCELLED
UNFINISHED_PAYMENT_STATUSES = ("DRAFT", "APPROVED", "INITIATED")          # not yet COMPLETED or CANCELLED
# An online (UPI) payment is unfinished while it can still be paid (CREATED / PENDING and not expired) or was paid and has not been booked (PAID, no
# transaction yet: waiting for review). One SQL predicate, used wherever the requests are looked at (alias u):
UNFINISHED_ONLINE_PAYMENT_SQL = ("((u.status IN ('CREATED', 'PENDING') AND u.expires_at > NOW()) "
                                 "OR (u.status = 'PAID' AND u.financial_transaction_pk IS NULL))")


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


# ═══════════════════════════════════════════════════════════════════════
# Pure rules (no database)
# ═══════════════════════════════════════════════════════════════════════

def check_step(current: str, target: str) -> None:
    if (current, target) not in STEPS:
        allowed = ", ".join(sorted(t for f, t in STEPS if f == current)) or "none"
        raise _invalid(f"A Sangha's year goes OPEN -> CLOSING -> CLOSED; it is {current}, so {target} is not possible (allowed from {current}: {allowed}).")


def require_year_open_for_closing(year_code: str, year_status: str) -> None:
    if year_status not in YEAR_STATES_THAT_CAN_CLOSE:
        raise _invalid(f"Financial year {year_code} is {year_status}; a Sangha closes its books while the year is OPEN or CLOSING.")


def refuses_new_entries(sangha_status: str) -> bool:
    """CLOSING and CLOSED: no new entry or transfer for that Sangha in that year."""
    return sangha_status in (CLOSING, CLOSED)


def refuses_any_entry(sangha_status: str) -> bool:
    """CLOSED: nothing at all (the books are shut)."""
    return sangha_status == CLOSED


def refusal(sangha_name: str, year_code: str, sangha_status: str, *, new: bool) -> HTTPException:
    if new:
        return _invalid(f"{sangha_name} has {'started closing' if sangha_status == CLOSING else 'closed'} its books for financial year {year_code}; "
                        "nothing new can be recorded for it in that year (finish what is in progress, or use the current year).")
    return _invalid(f"{sangha_name} has closed its books for financial year {year_code}; nothing more can be done to its entries in that year.")


def unfinished_total(row: dict) -> int:
    """How many pieces of in-progress work a Sangha row has: transactions, transfers, receipts, payments and online payments."""
    return sum(row.get(k, 0) or 0 for k in ("unfinished_transactions", "unfinished_transfers", "unfinished_receipts", "unfinished_payments",
                                            "unfinished_online_payments"))


def unfinished_text(name: str, transactions: int, transfers: int, receipts: int = 0, payments: int = 0, online: int = 0) -> str:
    parts = [f"{n} {what}" for n, what in ((transactions, "transaction(s)"), (transfers, "transfer(s)"), (receipts, "draft receipt(s)"),
                                           (payments, "unfinished payment(s)"), (online, "online payment(s) not yet booked or finished")) if n]
    return f"{name}: {', '.join(parts)} still unfinished"


def plan_year_close(sanghas: list[dict], global_unfinished: list[str]) -> dict:
    """
    What closing the YEAR needs, from the Sanghas that have activity in it (each: organization_pk, organization_name, status, unfinished_transactions,
    unfinished_transfers). A Sangha already CLOSED needs nothing; one with nothing unfinished is CLOSED along with the year; one with unfinished work
    BLOCKS it. *global_unfinished* are the lines for unfinished work on scopes that belong to no Sangha (they block too). Returns {"blocking": the
    Sangha rows that block, "closable": the rows closed with the year, "global": the global lines}. Pure: no database.
    """
    blocking, closable = [], []
    for s in sanghas:
        if s["status"] == CLOSED:
            continue
        (blocking if unfinished_total(s) else closable).append(s)
    return {"blocking": blocking, "closable": closable, "global": list(global_unfinished)}


def everyone_closed(sanghas: list[dict], global_unfinished: list[str]) -> bool:
    """True when no Sangha with activity is still open and nothing unfinished sits on a global scope (the year may then close by itself)."""
    return not global_unfinished and all(s["status"] == CLOSED for s in sanghas)


# ═══════════════════════════════════════════════════════════════════════
# Reading
# ═══════════════════════════════════════════════════════════════════════

def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def sanghas_of_year(cur, year_pk) -> list[dict]:
    """
    Every Sangha that has activity in the year (a transaction, or a transfer touching one of its scopes - counted once per Sangha even when both
    scopes are its own), has an online payment still unfinished, or has started closing the year: its status (OPEN when it has no closing row), how
    many entries it has and how much of each kind of work is unfinished - transactions, transfers, receipts, payments and online payments. Scopes that
    belong to no Sangha are not here (see global_unfinished).
    """
    cur.execute(
        f"""
        WITH acts AS (
            SELECT fs.organization_pk, 'T' AS kind, ft.status AS status
              FROM nss.financial_transaction ft JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk
             WHERE ft.financial_year_pk = %s AND ft.is_active = TRUE AND fs.organization_pk IS NOT NULL
            UNION ALL
            SELECT d.organization_pk, 'R', d.status
              FROM (SELECT DISTINCT tr.financial_transfer_pk, fs.organization_pk, tr.status
                      FROM nss.financial_transfer tr
                      JOIN nss.financial_scope fs ON fs.financial_scope_pk IN (tr.source_scope_pk, tr.destination_scope_pk)
                     WHERE tr.financial_year_pk = %s AND tr.is_active = TRUE AND fs.organization_pk IS NOT NULL) d
            UNION ALL
            SELECT fs.organization_pk, 'C', rc.status
              FROM nss.financial_receipt rc
              JOIN nss.financial_transaction ft ON ft.financial_transaction_pk = rc.financial_transaction_pk
              JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk
             WHERE ft.financial_year_pk = %s AND rc.is_active = TRUE AND fs.organization_pk IS NOT NULL
            UNION ALL
            SELECT fs.organization_pk, 'P', py.status
              FROM nss.financial_payment py
              JOIN nss.financial_transaction ft ON ft.financial_transaction_pk = py.financial_transaction_pk
              JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk
             WHERE ft.financial_year_pk = %s AND py.is_active = TRUE AND fs.organization_pk IS NOT NULL
            UNION ALL
            SELECT fs.organization_pk, 'U', u.status
              FROM nss.upi_payment_request u JOIN nss.financial_scope fs ON fs.financial_scope_pk = u.financial_scope_pk
             WHERE u.is_active = TRUE AND fs.organization_pk IS NOT NULL AND {UNFINISHED_ONLINE_PAYMENT_SQL}
            UNION ALL
            SELECT c.organization_pk, 'X', NULL FROM nss.finance_year_closing c WHERE c.financial_year_pk = %s AND c.is_active = TRUE
        )
        SELECT a.organization_pk, o.organization_name, md.value_code AS organization_type_code,
               COUNT(*) FILTER (WHERE a.kind = 'T') AS transaction_count, COUNT(*) FILTER (WHERE a.kind = 'R') AS transfer_count,
               COUNT(*) FILTER (WHERE a.kind = 'T' AND a.status = ANY(%s)) AS unfinished_transactions,
               COUNT(*) FILTER (WHERE a.kind = 'R' AND a.status = ANY(%s)) AS unfinished_transfers,
               COUNT(*) FILTER (WHERE a.kind = 'C' AND a.status = ANY(%s)) AS unfinished_receipts,
               COUNT(*) FILTER (WHERE a.kind = 'P' AND a.status = ANY(%s)) AS unfinished_payments,
               COUNT(*) FILTER (WHERE a.kind = 'U') AS unfinished_online_payments,
               COALESCE(MAX(c.status), 'OPEN') AS status, MAX(c.closed_on) AS closed_on
          FROM acts a
          JOIN nss.organization o ON o.organization_pk = a.organization_pk
          LEFT JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
          LEFT JOIN nss.finance_year_closing c
                 ON c.financial_year_pk = %s AND c.organization_pk = a.organization_pk AND c.is_active = TRUE
         GROUP BY a.organization_pk, o.organization_name, md.value_code
         ORDER BY o.organization_name
        """,
        (str(year_pk), str(year_pk), str(year_pk), str(year_pk), str(year_pk), list(UNFINISHED_TRANSACTION_STATUSES), list(UNFINISHED_TRANSFER_STATUSES),
         list(UNFINISHED_RECEIPT_STATUSES), list(UNFINISHED_PAYMENT_STATUSES), str(year_pk)),
    )
    return _rows(cur)


def global_unfinished(cur, year_pk) -> list[str]:
    """Lines for unfinished work on scopes that belong to no Sangha (only the NSS-wide authority can finish those)."""
    cur.execute(
        f"""
        SELECT COUNT(*) FILTER (WHERE kind = 'T'), COUNT(*) FILTER (WHERE kind = 'R'), COUNT(*) FILTER (WHERE kind = 'C'),
               COUNT(*) FILTER (WHERE kind = 'P'), COUNT(*) FILTER (WHERE kind = 'U')
          FROM (
            SELECT 'T' AS kind FROM nss.financial_transaction ft JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk
             WHERE ft.financial_year_pk = %s AND ft.is_active = TRUE AND fs.organization_pk IS NULL AND ft.status = ANY(%s)
            UNION ALL
            SELECT 'R' FROM nss.financial_transfer tr
             WHERE tr.financial_year_pk = %s AND tr.is_active = TRUE AND tr.status = ANY(%s)
               AND EXISTS (SELECT 1 FROM nss.financial_scope fs WHERE fs.financial_scope_pk IN (tr.source_scope_pk, tr.destination_scope_pk)
                              AND fs.organization_pk IS NULL)
            UNION ALL
            SELECT 'C' FROM nss.financial_receipt rc
              JOIN nss.financial_transaction ft ON ft.financial_transaction_pk = rc.financial_transaction_pk
              JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk
             WHERE ft.financial_year_pk = %s AND rc.is_active = TRUE AND fs.organization_pk IS NULL AND rc.status = ANY(%s)
            UNION ALL
            SELECT 'P' FROM nss.financial_payment py
              JOIN nss.financial_transaction ft ON ft.financial_transaction_pk = py.financial_transaction_pk
              JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk
             WHERE ft.financial_year_pk = %s AND py.is_active = TRUE AND fs.organization_pk IS NULL AND py.status = ANY(%s)
            UNION ALL
            SELECT 'U' FROM nss.upi_payment_request u JOIN nss.financial_scope fs ON fs.financial_scope_pk = u.financial_scope_pk
             WHERE u.is_active = TRUE AND fs.organization_pk IS NULL AND {UNFINISHED_ONLINE_PAYMENT_SQL}
          ) u
        """,
        (str(year_pk), list(UNFINISHED_TRANSACTION_STATUSES), str(year_pk), list(UNFINISHED_TRANSFER_STATUSES), str(year_pk), list(UNFINISHED_RECEIPT_STATUSES),
         str(year_pk), list(UNFINISHED_PAYMENT_STATUSES)),
    )
    transactions, transfers, receipts, payments, online = cur.fetchone()
    return ([unfinished_text("Scopes that belong to no Sangha", transactions, transfers, receipts, payments, online)]
            if (transactions or transfers or receipts or payments or online) else [])


def status_of(cur, year_pk, organization_pk) -> str:
    """OPEN / CLOSING / CLOSED of one Sangha in one year (a Sangha with no closing row is OPEN)."""
    if organization_pk is None:
        return OPEN
    cur.execute("SELECT status FROM nss.finance_year_closing WHERE financial_year_pk = %s AND organization_pk = %s AND is_active = TRUE",
                (str(year_pk), str(organization_pk)))
    row = cur.fetchone()
    return row[0] if row else OPEN


# ═══════════════════════════════════════════════════════════════════════
# Writing
# ═══════════════════════════════════════════════════════════════════════

def set_status(cur, actor_pk, year_pk, organization_pk, target: str, remarks: str | None) -> None:
    """Move one Sangha's year to *target* (CLOSING creates the row, CLOSED completes it; a Sangha closed with the year goes straight to CLOSED)."""
    cur.execute("SELECT finance_year_closing_pk FROM nss.finance_year_closing WHERE financial_year_pk = %s AND organization_pk = %s AND is_active = TRUE",
                (str(year_pk), str(organization_pk)))
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO nss.finance_year_closing (financial_year_pk, organization_pk, status, closed_on, remarks, created_by_sangha_sevi_pk) "
            "VALUES (%s, %s, %s, CASE WHEN %s = 'CLOSED' THEN CURRENT_DATE END, %s, %s)",
            (str(year_pk), str(organization_pk), target, target, remarks, actor_pk),
        )
        return
    cur.execute(
        "UPDATE nss.finance_year_closing SET status = %s, closed_on = CASE WHEN %s = 'CLOSED' THEN CURRENT_DATE END, "
        "remarks = COALESCE(%s, remarks), updated_at = NOW(), updated_by_sangha_sevi_pk = %s WHERE finance_year_closing_pk = %s",
        (target, target, remarks, actor_pk, str(row[0])),
    )
