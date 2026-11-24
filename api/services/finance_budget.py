"""
NSS ERP — the Kendra annual budget (Bye-Law; business rule FIN-BR-041, owner request 2026-11-22).

ONE home for the rules, so the endpoints and the tests share a single implementation:

  The Kendra Governing Body passes an annual budget; the DRAFT (or any financially consequential resolution) is referred to the
  ADVISORY BOARD for its considered views BEFORE the Governing Body's final consideration.

  DRAFT ──refer──▶ REFERRED ──record the Advisory Board's views──▶ VIEWS_RECEIVED ──Governing Body resolution──▶ PASSED

  * Every step is a recorded FACT with its reference and date; none can be skipped, and the dates keep that order.
  * The Advisory Board's views are REQUIRED on file before the budget can pass, but they are views, not a veto: whatever they
    say, the Governing Body decides (the Bye-Law asks for "considered views", nothing more).
  * A budget can go back to DRAFT (with a reason) until it is PASSED; the referral facts are cleared and the audit trail keeps
    what they were. A PASSED budget is final.
  * Lines (one planned amount per Kendra finance head) can be changed in ANY status (owner 2026-11-22, "edit always"); once the budget
    has left DRAFT a change must give its reason, which is kept in the audit trail with the old and new amounts.
  * The budget GUIDES, it never blocks: money booked on a head with no line, or above its line, is only FLAGGED. "Actual" is
    read from the POSTED / SETTLED transactions, never stored, so it cannot drift from the books.
  * Only the Kendra has a budget rule here. The central Mahila Sangha's "annual budget estimate" (FIN-BR-042) has no referral
    step and every other level is not bound (FIN-BR-044), so nothing is invented for them.

Nothing here commits and nothing checks WHO may act: the router does that (permission + admin scope), like the other Finance
routers. Statuses live in ``api/schemas/finance.py::BUDGET_STATUSES`` (parity-tested against the DDL CHECK).
"""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from api.services import finance_authority as FA

DRAFT, REFERRED, VIEWS_RECEIVED, PASSED = "DRAFT", "REFERRED", "VIEWS_RECEIVED", "PASSED"

# The money counted as "actual" (same statuses as every other balance in Finance): passed in by the router so the list lives once.
_BUDGET_COLUMNS = """
    b.finance_budget_pk, b.financial_year_pk, y.year_code, b.organization_pk, o.organization_name, b.status, b.notes,
    b.referred_on, b.referral_correspondence_pk, rc.reference_number AS referral_reference,
    ric.reference_number AS referral_inward_reference,
    b.advisory_reference, b.views_correspondence_pk, vic.reference_number AS views_inward_reference,
    b.advisory_views_date, b.advisory_views_summary,
    b.resolution_reference, b.resolution_date, b.created_at, b.updated_at
"""
# The two letters are read back from the Correspondence register (the number of each side of the letter), never copied.
_BUDGET_FROM = """
      FROM nss.finance_budget b
      JOIN nss.financial_year y ON y.financial_year_pk = b.financial_year_pk
      JOIN nss.organization o ON o.organization_pk = b.organization_pk
      LEFT JOIN nss.correspondence rc ON rc.correspondence_pk = b.referral_correspondence_pk
      LEFT JOIN nss.correspondence ric ON ric.correspondence_pk = rc.counterpart_correspondence_pk
      LEFT JOIN nss.correspondence vc ON vc.correspondence_pk = b.views_correspondence_pk
      LEFT JOIN nss.correspondence vic ON vic.correspondence_pk = vc.counterpart_correspondence_pk
"""


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found.")


# ═══════════════════════════════════════════════════════════════════════
# Pure rules (no database)
# ═══════════════════════════════════════════════════════════════════════

def changes_need_reason(budget_status: str) -> bool:
    """A line can ALWAYS be changed (owner 2026-11-22: "edit always"); once the draft has gone to the Advisory Board, or has passed, the
    change must say why, and the reason is kept in the audit trail with the old and new amounts."""
    return budget_status != DRAFT


def require_reason(budget: dict, reason: str | None) -> str | None:
    cleaned = (reason or "").strip() or None
    if changes_need_reason(budget["status"]) and cleaned is None:
        raise _invalid(f"The budget is {budget['status']}; say why the line is being changed (the reason is kept in the record).")
    return cleaned


def next_step(budget_status: str, line_count: int) -> str | None:
    """What has to happen next, in words (None once the budget has passed)."""
    if budget_status == DRAFT:
        return "Add the budget lines, then refer the draft to the Advisory Board." if line_count == 0 \
            else "Refer the draft to the Advisory Board."
    if budget_status == REFERRED:
        return "Record the Advisory Board's considered views."
    if budget_status == VIEWS_RECEIVED:
        return "Record the Governing Body's resolution passing the budget."
    return None


def check_not_future(value: date, label: str, today: date | None = None) -> None:
    if value > (today or date.today()):
        raise _invalid(f"{label} cannot be in the future; record it when it has happened.")


def check_dates_in_order(*, referred_on: date | None, views_date: date | None, resolution_date: date | None) -> None:
    """Referral, then the Advisory Board's views, then the resolution — never the other way round."""
    if referred_on and views_date and views_date < referred_on:
        raise _invalid("The Advisory Board's views cannot be dated before the draft was referred to it.")
    if views_date and resolution_date and resolution_date < views_date:
        raise _invalid("The Governing Body's resolution cannot be dated before the Advisory Board's views.")


def require_status(budget: dict, allowed: tuple[str, ...], what: str) -> None:
    if budget["status"] not in allowed:
        raise _invalid(f"The budget is {budget['status']}; {what} is possible only while it is {' or '.join(allowed)}.")


def require_blank(value: str | None, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise _invalid(f"{label} cannot be blank.")
    return cleaned


LETTER_REMARKS_MAX = 2000        # nss.correspondence remarks limit


def referral_subject(year_code: str) -> str:
    return f"Draft Kendra annual budget {year_code} - for the Advisory Board's considered views"


def views_subject(year_code: str) -> str:
    return f"Advisory Board's considered views on the draft Kendra annual budget {year_code}"


def referral_remarks(budget_lines: list[dict]) -> str:
    """The body of the referral letter: every planned line and the totals, cut to what a register remark can hold."""
    def money(v):
        return f"{Decimal(v):,.2f}"

    income = [l for l in budget_lines if l["direction"] == "INCOME"]
    spend = [l for l in budget_lines if l["direction"] == "EXPENSE"]
    out = []
    for title, rows in (("Planned income", income), ("Planned spending", spend)):
        if rows:
            out.append(f"{title}: " + "; ".join(f"{l['head_name']} {money(l['amount'])}" for l in rows) + f". Total {money(sum((l['amount'] for l in rows), start=Decimal(0)))}.")
    text = " ".join(out)
    return text if len(text) <= LETTER_REMARKS_MAX else text[: LETTER_REMARKS_MAX - 1].rstrip() + "…"


# ═══════════════════════════════════════════════════════════════════════
# Which organization holds the budget
# ═══════════════════════════════════════════════════════════════════════

def kendra_organization_pk(cur):
    """The one active Kendra organization (a singleton), else None."""
    cur.execute(
        """
        SELECT o.organization_pk
          FROM nss.organization o
          JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
         WHERE md.value_code = 'KENDRA' AND o.is_active = TRUE
         ORDER BY o.created_at LIMIT 1
        """
    )
    row = cur.fetchone()
    return row[0] if row else None


def advisory_board_organization_pk(cur):
    """The Advisory Board organization (a singleton, seeded with its own register and short code)."""
    cur.execute(
        """
        SELECT o.organization_pk
          FROM nss.organization o
          JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
         WHERE md.value_code = 'ADVISORY_BOARD' AND o.is_active = TRUE
         ORDER BY o.created_at LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        raise _invalid("There is no active Advisory Board organization to refer the budget to.")
    return row[0]


def inward_copy_pk(cur, correspondence_pk, register_organization_pk):
    """The other side of a letter (the recipient's INWARD copy), only when it sits in *register_organization_pk*'s register."""
    if not correspondence_pk:
        return None
    cur.execute(
        "SELECT c2.correspondence_pk FROM nss.correspondence c1 JOIN nss.correspondence c2 ON c2.correspondence_pk = c1.counterpart_correspondence_pk "
        "WHERE c1.correspondence_pk = %s AND c2.register_organization_pk = %s AND c2.is_active = TRUE",
        (str(correspondence_pk), str(register_organization_pk)),
    )
    row = cur.fetchone()
    return row[0] if row else None


def require_kendra(cur, organization_pk) -> None:
    if FA.basis_for_org(cur, organization_pk) != FA.KENDRA:
        raise _invalid("Only the Kendra Sangha has an annual budget to be passed by its Governing Body (FIN-BR-041).")


# ═══════════════════════════════════════════════════════════════════════
# Reading
# ═══════════════════════════════════════════════════════════════════════

def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load(cur, budget_pk, *, lock: bool = False) -> dict:
    cur.execute(
        f"SELECT {_BUDGET_COLUMNS}, (SELECT COUNT(*) FROM nss.finance_budget_line l "
        f"WHERE l.finance_budget_pk = b.finance_budget_pk AND l.is_active = TRUE) AS line_count "
        f"{_BUDGET_FROM} WHERE b.finance_budget_pk = %s AND b.is_active = TRUE" + (" FOR UPDATE OF b" if lock else ""),
        (str(budget_pk),),
    )
    rows = _rows(cur)
    if not rows:
        raise _not_found()
    return rows[0]


def present(budget: dict) -> dict:
    """The response fields every budget carries, computed from the row."""
    shown = {k: v for k, v in budget.items() if k != "line_count"}
    shown["next_step"] = next_step(budget["status"], budget.get("line_count", 0))
    shown["changes_need_reason"] = changes_need_reason(budget["status"])
    return shown


def list_rows(cur, where_sql: str, params: list) -> list[dict]:
    """Budgets matching a WHERE built by the caller from fixed predicates (never input text), newest year first."""
    cur.execute(
        f"SELECT {_BUDGET_COLUMNS}, (SELECT COUNT(*) FROM nss.finance_budget_line l "
        f"WHERE l.finance_budget_pk = b.finance_budget_pk AND l.is_active = TRUE) AS line_count "
        f"{_BUDGET_FROM} WHERE {where_sql} ORDER BY y.start_date DESC, o.organization_name",
        params,
    )
    return [present(r) for r in _rows(cur)]


_ACTUAL_SQL = """
    SELECT COALESCE(SUM(t.amount), 0)
      FROM nss.financial_transaction t
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
     WHERE t.finance_head_pk = h.finance_head_pk AND t.financial_year_pk = b.financial_year_pk
       AND fs.organization_pk = b.organization_pk AND t.is_active = TRUE
       AND t.transaction_type = h.direction AND t.status = ANY(%s)
"""


def lines(cur, budget_pk, counted_statuses) -> list[dict]:
    cur.execute(
        f"""
        SELECT l.finance_budget_line_pk, l.finance_head_pk, h.head_code, h.head_name, h.direction, l.amount, l.notes,
               ({_ACTUAL_SQL}) AS actual
          FROM nss.finance_budget_line l
          JOIN nss.finance_budget b ON b.finance_budget_pk = l.finance_budget_pk
          JOIN nss.finance_head h ON h.finance_head_pk = l.finance_head_pk
         WHERE l.finance_budget_pk = %s AND l.is_active = TRUE
         ORDER BY h.direction DESC, h.head_name
        """,
        (list(counted_statuses), str(budget_pk)),
    )
    out = _rows(cur)
    for r in out:
        r["remaining"] = r["amount"] - r["actual"]
        r["over_budget"] = r["direction"] == "EXPENSE" and r["actual"] > r["amount"]
    return out


def unbudgeted(cur, budget: dict, counted_statuses) -> list[dict]:
    """Heads with money booked this year that have no line in the budget (flag only)."""
    cur.execute(
        """
        SELECT h.finance_head_pk, h.head_code, h.head_name, h.direction, SUM(t.amount) AS actual
          FROM nss.financial_transaction t
          JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
          JOIN nss.finance_head h ON h.finance_head_pk = t.finance_head_pk
         WHERE t.financial_year_pk = %s AND fs.organization_pk = %s AND t.is_active = TRUE
           AND t.transaction_type = h.direction AND t.status = ANY(%s)
           AND NOT EXISTS (SELECT 1 FROM nss.finance_budget_line l
                            WHERE l.finance_budget_pk = %s AND l.finance_head_pk = h.finance_head_pk AND l.is_active = TRUE)
         GROUP BY h.finance_head_pk, h.head_code, h.head_name, h.direction
         ORDER BY h.direction DESC, h.head_name
        """,
        (str(budget["financial_year_pk"]), str(budget["organization_pk"]), list(counted_statuses), str(budget["finance_budget_pk"])),
    )
    return _rows(cur)


def totals(budget_lines: list[dict], flagged: list[dict]) -> dict:
    """Planned and actual, income and expense. Actual includes money on heads with no line (it is real money)."""
    def planned(direction):
        return sum((r["amount"] for r in budget_lines if r["direction"] == direction), start=Decimal(0))

    def actual(direction):
        return sum((r["actual"] for r in [*budget_lines, *flagged] if r["direction"] == direction), start=Decimal(0))

    return {"planned_income": planned("INCOME"), "planned_expense": planned("EXPENSE"),
            "actual_income": actual("INCOME"), "actual_expense": actual("EXPENSE"),
            "planned_surplus": planned("INCOME") - planned("EXPENSE")}


def detail(cur, budget_pk, counted_statuses) -> dict:
    budget = load(cur, budget_pk)
    budget_lines = lines(cur, budget_pk, counted_statuses)
    flagged = unbudgeted(cur, budget, counted_statuses)
    out = present(budget)
    out.update({"lines": budget_lines, "unbudgeted": flagged, "totals": totals(budget_lines, flagged)})
    return out


# ═══════════════════════════════════════════════════════════════════════
# Writing (the caller has already checked permission + scope and holds the row lock)
# ═══════════════════════════════════════════════════════════════════════

def _set(cur, actor_pk, budget_pk, values: dict) -> None:
    sets = [f"{col} = %s" for col in values] + ["updated_at = NOW()", "updated_by_sangha_sevi_pk = %s"]
    cur.execute(f"UPDATE nss.finance_budget SET {', '.join(sets)} WHERE finance_budget_pk = %s", [*values.values(), actor_pk, str(budget_pk)])


def create(cur, actor_pk, *, year_pk, organization_pk, notes) -> str:
    cur.execute("SELECT status FROM nss.financial_year WHERE financial_year_pk = %s AND is_active = TRUE", (str(year_pk),))
    year = cur.fetchone()
    if year is None:
        raise _invalid("Financial year not found.")
    if year[0] == "CLOSED":
        raise _invalid("That financial year is CLOSED; a budget cannot be started for it.")
    cur.execute("SELECT 1 FROM nss.finance_budget WHERE financial_year_pk = %s AND organization_pk = %s AND is_active = TRUE",
                (str(year_pk), str(organization_pk)))
    if cur.fetchone():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This financial year already has a budget for the Kendra.")
    cur.execute(
        "INSERT INTO nss.finance_budget (financial_year_pk, organization_pk, notes, created_by_sangha_sevi_pk) "
        "VALUES (%s, %s, %s, %s) RETURNING finance_budget_pk",
        (str(year_pk), str(organization_pk), notes, actor_pk),
    )
    return cur.fetchone()[0]


def put_line(cur, actor_pk, budget: dict, *, head_pk, amount, notes, reason=None) -> tuple[str, bool, Decimal | None]:
    """Add the planned amount for a head, or change it if the head already has a line, in ANY status (a reason is required once the
    budget has left DRAFT). Returns (line pk, created, the amount before - None for a new line)."""
    require_reason(budget, reason)
    cur.execute(
        "SELECT organization_pk, status, head_name FROM nss.finance_head WHERE finance_head_pk = %s AND is_active = TRUE",
        (str(head_pk),),
    )
    head = cur.fetchone()
    if head is None:
        raise _invalid("Finance head not found.")
    if str(head[0]) != str(budget["organization_pk"]):
        raise _invalid("Only a finance head of the Kendra can have a budget line.")
    if head[1] != "ACTIVE":
        raise _invalid(f"Finance head {head[2]} is {head[1]}; only an ACTIVE head can be budgeted.")
    cur.execute("SELECT finance_budget_line_pk, amount FROM nss.finance_budget_line WHERE finance_budget_pk = %s AND finance_head_pk = %s AND is_active = TRUE",
                (str(budget["finance_budget_pk"]), str(head_pk)))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE nss.finance_budget_line SET amount = %s, notes = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s "
                    "WHERE finance_budget_line_pk = %s", (amount, notes, actor_pk, str(row[0])))
        return row[0], False, row[1]
    cur.execute("INSERT INTO nss.finance_budget_line (finance_budget_pk, finance_head_pk, amount, notes, created_by_sangha_sevi_pk) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING finance_budget_line_pk",
                (str(budget["finance_budget_pk"]), str(head_pk), amount, notes, actor_pk))
    return cur.fetchone()[0], True, None


def remove_line(cur, actor_pk, budget: dict, line_pk, reason=None) -> Decimal:
    """Remove a line in ANY status (a reason is required once the budget has left DRAFT). Returns the amount it had."""
    require_reason(budget, reason)
    cur.execute("SELECT amount FROM nss.finance_budget_line WHERE finance_budget_line_pk = %s AND finance_budget_pk = %s AND is_active = TRUE",
                (str(line_pk), str(budget["finance_budget_pk"])))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget line not found.")
    cur.execute("UPDATE nss.finance_budget_line SET is_active = FALSE, deleted_at = NOW(), deleted_by_sangha_sevi_pk = %s, "
                "updated_at = NOW(), updated_by_sangha_sevi_pk = %s WHERE finance_budget_line_pk = %s", (actor_pk, actor_pk, str(line_pk)))
    return row[0]


def validate_refer(budget: dict, referred_on: date) -> None:
    """Every rule of referring, with nothing written - the caller runs it BEFORE filing the letter, so a refused step leaves no letter."""
    require_status(budget, (DRAFT,), "referring it to the Advisory Board")
    if budget["line_count"] == 0:
        raise _invalid("Add at least one budget line before referring the draft to the Advisory Board.")
    check_not_future(referred_on, "The referral date")


def refer(cur, actor_pk, budget: dict, referred_on: date, letter_pk) -> None:
    validate_refer(budget, referred_on)
    _set(cur, actor_pk, budget["finance_budget_pk"], {"status": REFERRED, "referred_on": referred_on, "referral_correspondence_pk": str(letter_pk)})


def validate_views(budget: dict, views_date: date, summary: str) -> str:
    """Every rule of recording the views, nothing written; returns the cleaned summary."""
    require_status(budget, (REFERRED,), "recording the Advisory Board's views")
    summary = require_blank(summary, "The summary of the views")
    check_not_future(views_date, "The date of the Advisory Board's views")
    check_dates_in_order(referred_on=budget["referred_on"], views_date=views_date, resolution_date=None)
    return summary


def record_views(cur, actor_pk, budget: dict, *, reference: str, views_date: date, summary: str, letter_pk) -> None:
    """*reference* is the number of the Advisory Board's reply in the Correspondence register (minted, never typed)."""
    summary = validate_views(budget, views_date, summary)
    reference = require_blank(reference, "The Advisory Board's reference")
    _set(cur, actor_pk, budget["finance_budget_pk"], {"status": VIEWS_RECEIVED, "advisory_reference": reference, "advisory_views_date": views_date,
                                                       "advisory_views_summary": summary, "views_correspondence_pk": str(letter_pk)})


def pass_budget(cur, actor_pk, budget: dict, *, reference: str, resolution_date: date) -> None:
    require_status(budget, (VIEWS_RECEIVED,), "passing it (the Advisory Board's views must be on file first)")
    reference = require_blank(reference, "The resolution reference")
    check_not_future(resolution_date, "The resolution date")
    check_dates_in_order(referred_on=budget["referred_on"], views_date=budget["advisory_views_date"], resolution_date=resolution_date)
    _set(cur, actor_pk, budget["finance_budget_pk"], {"status": PASSED, "resolution_reference": reference, "resolution_date": resolution_date})


def reopen(cur, actor_pk, budget: dict) -> None:
    """Back to DRAFT: the referral and the views are cleared (the audit trail keeps them; the letters stay in Correspondence, which
    never deletes) so a changed draft is referred afresh with a new letter."""
    require_status(budget, (REFERRED, VIEWS_RECEIVED), "sending it back to draft")
    _set(cur, actor_pk, budget["finance_budget_pk"], {"status": DRAFT, "referred_on": None, "advisory_reference": None,
                                                       "advisory_views_date": None, "advisory_views_summary": None,
                                                       "referral_correspondence_pk": None, "views_correspondence_pk": None})


def validate_correction(budget: dict, *, summary: str | None, resolution_reference: str | None, reason: str | None) -> dict:
    """
    Correcting what was recorded (owner 2026-11-24): the Advisory Board's summary from VIEWS_RECEIVED on, the resolution reference once PASSED, always with
    a reason. Returns the columns that really change ({} is refused: nothing to correct). Nothing is written.
    """
    require_status(budget, (VIEWS_RECEIVED, PASSED), "correcting what was recorded")
    why = require_blank(reason, "The reason for the correction")
    changes: dict = {}
    if summary is not None:
        new_summary = require_blank(summary, "The summary of the views")
        if new_summary != budget["advisory_views_summary"]:
            changes["advisory_views_summary"] = new_summary
    if resolution_reference is not None:
        if budget["status"] != PASSED:
            raise _invalid("There is no resolution to correct yet; the budget has not passed.")
        new_reference = require_blank(resolution_reference, "The resolution reference")
        if new_reference != budget["resolution_reference"]:
            changes["resolution_reference"] = new_reference
    if not changes:
        raise _invalid("Nothing to correct: send a summary or a resolution reference that differs from what is recorded.")
    changes["_reason"] = why
    return changes


def correct(cur, actor_pk, budget: dict, *, summary: str | None, resolution_reference: str | None, reason: str | None) -> dict:
    """Apply a correction; returns {"reason", "changed": {column: (old, new)}} for the audit event. The status does not move."""
    changes = validate_correction(budget, summary=summary, resolution_reference=resolution_reference, reason=reason)
    why = changes.pop("_reason")
    _set(cur, actor_pk, budget["finance_budget_pk"], changes)
    return {"reason": why, "changed": {col: (budget[col], new) for col, new in changes.items()}}
