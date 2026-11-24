"""
NSS ERP — Sinking Fund reimbursement (Bye-Law C(i)(2)(xviii); business rule FIN-BR-026, owner request 2026-11-24).

ONE home for the rules, so the endpoints and the tests share a single implementation:

  The Kendra Sangha may, as a temporary measure, take over the seva and pujas of a Sakha Sangha / Asana Mandir. "Any expenditure incurred in this
  connection by the Kendra Sangha out of the sinking fund shall be reimbursed by the Sakha Sangha subsequently."

      Sinking Fund (the Sakha's, under the Kendra) ──▶ Kendra expenditure ──▶ reason + beneficiary Sakha ──▶ reimbursement obligation
                                                                                              └──▶ subsequent reimbursement(s)

  * The EXPENDITURE is an ordinary EXPENSE entry (the Bye-Law disbursement controls for Kendra money already apply to it). Registering it as
    a take-over expenditure creates the OBLIGATION: the Sakha owes what was spent, the amount fixed when it is registered. The Sakha, the
    fund and the date come from the expenditure, so they are not stored twice.
  * A REIMBURSEMENT is an ordinary INCOME entry in the same fund (head SINKING_REIMBURSEMENT, the Sakha paying back), linked to the obligation.
    It goes through the ordinary lifecycle and counts as reimbursed only once POSTED / SETTLED - "reimbursed" is read from the books, never stored.
  * Part payments are allowed; the total of what is recorded (posted or still in progress) can never exceed what is owed, and the obligation
    is REIMBURSED when the posted total reaches the amount owed.
  * Nothing is invented beyond the Bye-Law: no interest, no waiver, no due date (the Bye-Law says "subsequently").

Nothing here commits and nothing checks WHO may act: the router does that (permission + admin scope).
"""

from decimal import Decimal

from fastapi import HTTPException, status

OPEN, PARTLY_REIMBURSED, REIMBURSED = "OPEN", "PARTLY_REIMBURSED", "REIMBURSED"
IN_PROGRESS_STATUSES = ("DRAFT", "PENDING_APPROVAL", "APPROVED")          # recorded, not yet posted: reserved against the amount owed
HEAD_CODE = "SINKING_REIMBURSEMENT"                                       # the Kendra template head the Sakha's payment is booked on
SEQUENCE_CODE = "SINKING_REIMBURSEMENT"                                   # id_sequence_master (prefix SRB)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sinking Fund reimbursement not found.")


# ═══════════════════════════════════════════════════════════════════════
# Pure rules (no database)
# ═══════════════════════════════════════════════════════════════════════

def outstanding(due: Decimal, reimbursed: Decimal) -> Decimal:
    return max(Decimal(due) - Decimal(reimbursed), Decimal("0"))


def status_of(due: Decimal, reimbursed: Decimal) -> str:
    if Decimal(reimbursed) <= 0:
        return OPEN
    return REIMBURSED if Decimal(reimbursed) >= Decimal(due) else PARTLY_REIMBURSED


def available_to_record(due: Decimal, reimbursed: Decimal, pending: Decimal) -> Decimal:
    """What may still be recorded: what is owed less what is posted and what is already recorded and on its way."""
    return max(Decimal(due) - Decimal(reimbursed) - Decimal(pending), Decimal("0"))


def next_step(row_status: str, available: Decimal) -> str | None:
    if row_status == REIMBURSED:
        return None
    if available <= 0:
        return "Everything owed has been recorded; post the reimbursement entries that are still in progress."
    return "Record the Sakha's reimbursement when it pays (part payments are fine)."


def by_sakha(rows: list[dict], unregistered: list[dict]) -> list[dict]:
    """
    The Kendra's page, Sakha by Sakha (owner 2026-11-24): for each Sakha with a Sinking Fund expenditure, what is registered as owed, what has been
    reimbursed, what is still owed, and what has been spent but not registered yet. *rows* are the obligations (present()), *unregistered* the
    expenditures waiting to be registered. Pure: no database. Sorted by Sakha name.
    """
    sakhas: dict[str, dict] = {}

    def slot(pk, name):
        return sakhas.setdefault(str(pk), {"sakha_organization_pk": pk, "sakha_name": name, "registered_count": 0, "owed_amount": Decimal("0"),
                                           "reimbursed_amount": Decimal("0"), "outstanding_amount": Decimal("0"),
                                           "unregistered_count": 0, "unregistered_amount": Decimal("0")})

    for r in rows:
        s = slot(r["sakha_organization_pk"], r["sakha_name"])
        s["registered_count"] += 1
        s["owed_amount"] += Decimal(r["amount_due"])
        s["reimbursed_amount"] += Decimal(r["reimbursed_amount"])
        s["outstanding_amount"] += Decimal(r["outstanding_amount"])
    for u in unregistered:
        s = slot(u["sakha_organization_pk"], u["sakha_name"])
        s["unregistered_count"] += 1
        s["unregistered_amount"] += Decimal(u["amount"])
    return sorted(sakhas.values(), key=lambda s: s["sakha_name"].lower())


def check_registerable(expenditure: dict, fund: dict | None, scope_organization_pk) -> None:
    """
    May this entry be registered as a take-over expenditure? *expenditure* is the stored transaction (transaction_type, status, ...), *fund* its fund
    row (fund_type, organization_pk = the Sakha) or None. The Kendra's money spent in a Sakha's name: an EXPENSE already POSTED / SETTLED, from a
    SINKING_FUND that names its Sakha, spent by someone other than that Sakha.
    """
    if expenditure["transaction_type"] != "EXPENSE":
        raise _invalid("Only an expenditure (an EXPENSE entry) can be registered as a take-over expenditure.")
    if expenditure["status"] not in ("POSTED", "SETTLED"):
        raise _invalid(f"The expenditure is {expenditure['status']}; register it once it has been POSTED (the money has really been spent).")
    if fund is None or fund["fund_type"] != "SINKING_FUND":
        raise _invalid("Only an expenditure from a Sinking Fund is reimbursed by the Sakha (Bye-Law C(i)(2)(xviii)).")
    if fund["organization_pk"] is None:
        raise _invalid("This Sinking Fund does not name its Sakha, so there is no Sakha to reimburse it (FIN-BR-023/024).")
    if str(fund["organization_pk"]) == str(scope_organization_pk):
        raise _invalid("The Sakha spent this itself; only what the Kendra spends on its behalf is reimbursed.")


def clean_reason(reason: str | None) -> str:
    cleaned = (reason or "").strip()
    if not cleaned:
        raise _invalid("Say why the Kendra took over the Sakha's seva / pujas (the reason is kept in the record).")
    return cleaned


def check_amount(amount: Decimal, available: Decimal) -> None:
    if amount <= 0:
        raise _invalid("The amount must be more than zero.")
    if available <= 0:
        raise _invalid("Everything owed is already recorded as reimbursed (or on its way); nothing more can be recorded.")
    if amount > available:
        raise _invalid(f"The Sakha owes at most {available} more (what is owed, less what is reimbursed or already recorded).")


# ═══════════════════════════════════════════════════════════════════════
# Reading
# ═══════════════════════════════════════════════════════════════════════

def _columns(counted_placeholders: str) -> str:
    return f"""
    r.finance_sinking_reimbursement_pk, r.reimbursement_reference, r.takeover_reason, r.resolution_reference, r.amount_due,
    r.expenditure_transaction_pk, t.transaction_reference AS expenditure_reference, t.transaction_date AS expenditure_date,
    t.description AS expenditure_description, fm.fund_master_pk, fm.fund_code, fm.fund_name,
    fm.organization_pk AS sakha_organization_pk, so.organization_name AS sakha_name,
    fs.organization_pk AS scope_organization_pk, fs.financial_scope_pk, t.financial_year_pk, r.created_at,
    COALESCE((SELECT SUM(et.amount) FROM nss.finance_sinking_reimbursement_entry e
                JOIN nss.financial_transaction et ON et.financial_transaction_pk = e.financial_transaction_pk
               WHERE e.finance_sinking_reimbursement_pk = r.finance_sinking_reimbursement_pk AND e.is_active = TRUE
                 AND et.is_active = TRUE AND et.status = ANY({counted_placeholders})), 0) AS reimbursed_amount,
    COALESCE((SELECT SUM(et.amount) FROM nss.finance_sinking_reimbursement_entry e
                JOIN nss.financial_transaction et ON et.financial_transaction_pk = e.financial_transaction_pk
               WHERE e.finance_sinking_reimbursement_pk = r.finance_sinking_reimbursement_pk AND e.is_active = TRUE
                 AND et.is_active = TRUE AND et.status = ANY(%s)), 0) AS pending_amount
"""


_FROM = """
      FROM nss.finance_sinking_reimbursement r
      JOIN nss.financial_transaction t ON t.financial_transaction_pk = r.expenditure_transaction_pk
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
      JOIN nss.fund_master fm ON fm.fund_master_pk = t.fund_master_pk
      JOIN nss.organization so ON so.organization_pk = fm.organization_pk
"""


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def present(row: dict) -> dict:
    """The fields every obligation carries, worked out from the stored row and the books."""
    shown = dict(row)
    shown["outstanding_amount"] = outstanding(row["amount_due"], row["reimbursed_amount"])
    shown["status"] = status_of(row["amount_due"], row["reimbursed_amount"])
    return shown


def list_rows(cur, where_sql: str, params: list, counted) -> list[dict]:
    """Obligations matching a WHERE built by the caller from fixed predicates (never input text), newest first."""
    cur.execute(
        f"SELECT {_columns('%s')} {_FROM} WHERE r.is_active = TRUE AND {where_sql} ORDER BY t.transaction_date DESC, r.created_at DESC",
        [list(counted), list(IN_PROGRESS_STATUSES), *params],
    )
    return [present(r) for r in _rows(cur)]


def load(cur, pk, counted, *, lock: bool = False) -> dict:
    cur.execute(
        f"SELECT {_columns('%s')} {_FROM} WHERE r.finance_sinking_reimbursement_pk = %s AND r.is_active = TRUE"
        + (" FOR UPDATE OF r" if lock else ""),
        [list(counted), list(IN_PROGRESS_STATUSES), str(pk)],
    )
    rows = _rows(cur)
    if not rows:
        raise _not_found()
    return present(rows[0])


def entries(cur, pk) -> list[dict]:
    cur.execute(
        """
        SELECT et.financial_transaction_pk, et.transaction_reference, et.transaction_date, et.amount, et.status, et.description
          FROM nss.finance_sinking_reimbursement_entry e
          JOIN nss.financial_transaction et ON et.financial_transaction_pk = e.financial_transaction_pk
         WHERE e.finance_sinking_reimbursement_pk = %s AND e.is_active = TRUE AND et.is_active = TRUE
         ORDER BY et.transaction_date, et.created_at
        """,
        (str(pk),),
    )
    return _rows(cur)


def detail(cur, pk, counted) -> dict:
    row = load(cur, pk, counted)
    row["reimbursements"] = entries(cur, pk)
    row["next_step"] = next_step(row["status"], available_to_record(row["amount_due"], row["reimbursed_amount"], row["pending_amount"]))
    return row


def unregistered_expenditures(cur, where_sql: str, params: list, counted) -> list[dict]:
    """POSTED / SETTLED expenditures from a Sakha's Sinking Fund that nobody has registered as owed yet (what the page offers)."""
    cur.execute(
        f"""
        SELECT t.financial_transaction_pk, t.transaction_reference, t.transaction_date, t.amount, t.description,
               fm.fund_code, fm.fund_name, fm.organization_pk AS sakha_organization_pk, so.organization_name AS sakha_name
          FROM nss.financial_transaction t
          JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
          JOIN nss.fund_master fm ON fm.fund_master_pk = t.fund_master_pk
          JOIN nss.organization so ON so.organization_pk = fm.organization_pk
         WHERE t.is_active = TRUE AND t.transaction_type = 'EXPENSE' AND t.status = ANY(%s)
           AND fm.fund_type = 'SINKING_FUND' AND fm.organization_pk IS NOT NULL
           AND fs.organization_pk IS DISTINCT FROM fm.organization_pk
           AND NOT EXISTS (SELECT 1 FROM nss.finance_sinking_reimbursement r
                            WHERE r.expenditure_transaction_pk = t.financial_transaction_pk AND r.is_active = TRUE)
           AND {where_sql}
         ORDER BY t.transaction_date DESC, t.transaction_reference
        """,
        [list(counted), *params],
    )
    return _rows(cur)


# ═══════════════════════════════════════════════════════════════════════
# Writing
# ═══════════════════════════════════════════════════════════════════════

def is_registered(cur, expenditure_pk) -> bool:
    cur.execute("SELECT 1 FROM nss.finance_sinking_reimbursement WHERE expenditure_transaction_pk = %s AND is_active = TRUE", (str(expenditure_pk),))
    return cur.fetchone() is not None


def register(cur, actor_pk, *, reference: str, expenditure_pk, amount_due: Decimal, reason: str, resolution_reference: str | None):
    cur.execute(
        """
        INSERT INTO nss.finance_sinking_reimbursement
            (reimbursement_reference, expenditure_transaction_pk, takeover_reason, resolution_reference, amount_due, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING finance_sinking_reimbursement_pk
        """,
        (reference, str(expenditure_pk), reason, resolution_reference, amount_due, actor_pk),
    )
    return cur.fetchone()[0]


def link_entry(cur, actor_pk, reimbursement_pk, transaction_pk) -> None:
    cur.execute(
        "INSERT INTO nss.finance_sinking_reimbursement_entry (finance_sinking_reimbursement_pk, financial_transaction_pk, created_by_sangha_sevi_pk) "
        "VALUES (%s, %s, %s)",
        (str(reimbursement_pk), str(transaction_pk), actor_pk),
    )


def has_entries(cur, pk) -> bool:
    cur.execute("SELECT 1 FROM nss.finance_sinking_reimbursement_entry WHERE finance_sinking_reimbursement_pk = %s AND is_active = TRUE", (str(pk),))
    return cur.fetchone() is not None


def remove(cur, actor_pk, pk) -> None:
    """Soft delete (history is never deleted); the expenditure can then be registered again."""
    cur.execute(
        "UPDATE nss.finance_sinking_reimbursement SET is_active = FALSE, deleted_at = NOW(), deleted_by_sangha_sevi_pk = %s, "
        "updated_at = NOW(), updated_by_sangha_sevi_pk = %s WHERE finance_sinking_reimbursement_pk = %s",
        (actor_pk, actor_pk, str(pk)),
    )


def head_for(cur, organization_pk):
    """The ACTIVE SINKING_REIMBURSEMENT head the organization owns, or None."""
    cur.execute(
        "SELECT finance_head_pk FROM nss.finance_head WHERE organization_pk = %s AND head_code = %s AND is_active = TRUE AND status = 'ACTIVE'",
        (str(organization_pk), HEAD_CODE),
    )
    row = cur.fetchone()
    return row[0] if row else None


def template_head_pk(cur):
    cur.execute("SELECT finance_head_pk FROM nss.finance_head WHERE organization_pk IS NULL AND head_code = %s AND is_active = TRUE", (HEAD_CODE,))
    row = cur.fetchone()
    return row[0] if row else None
