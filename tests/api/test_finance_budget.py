"""
Finance — the Kendra annual budget (FIN-BR-041; api/services/finance_budget.py, api/routers/finance_budget.py).

Rules under test:
  * ONE budget per Kendra per financial year; only the Kendra has one (a Sakha's id is refused), never in a CLOSED year;
  * lines (one planned amount per ACTIVE Kendra head) change only while the budget is a DRAFT;
  * the steps cannot be skipped or reordered: DRAFT -> REFERRED (to the Advisory Board) -> VIEWS_RECEIVED -> PASSED, each with its
    reference and date, the dates in that order and never in the future;
  * the Advisory Board's views must be on file before the budget can pass (views, not a veto);
  * a budget goes back to DRAFT with a reason until it has passed; a PASSED budget is final;
  * the budget FLAGS spending (over a line, or on a head with no line) but never blocks it, and "actual" counts only POSTED / SETTLED;
  * a scoped Sakha administrator cannot see or change the Kendra's budget.

Real integration tests (nothing mocked); NEVER RUN against a database when this file was written.
"""

import itertools
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    admin_h,
    admin_user,
    head_pk,
    make_scope,
    make_txn,
    new_year,
    move,
    post_txn,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    viewer_h,
    viewer_user,
)
from tests.reparent_support import kendra_pks

# Each test takes a year of its own (one budget per year), counting DOWN from 2100 so the years other helpers reuse (2040 upwards) stay free.
_years = itertools.count(2100, -1)
_TODAY = date.today()


@pytest.fixture(scope="module")
def kendra_org_pk(write_conn):
    return kendra_pks(write_conn)[0]


def _year(client, h, *, open_: bool = False) -> dict:
    for _ in range(60):
        start = next(_years)
        year = new_year(client, h, start) or next((y for y in client.get(f"{BASE}/years", headers=h).json()["items"] if int(y["year_code"][:4]) == start), None)
        if year is None or year["status"] in ("CLOSING", "CLOSED"):
            continue
        if open_ and year["status"] == "PLANNED":
            year = move(client, h, "years", year["financial_year_pk"], "OPEN")
        if client.get(f"{BASE}/budgets", params={"financial_year_pk": year["financial_year_pk"]}, headers=h).json()["total"] == 0:
            return year
    raise AssertionError("no financial year without a budget could be found")


def _budget(client, h, *, open_year: bool = False) -> tuple[dict, dict]:
    year = _year(client, h, open_=open_year)
    r = client.post(f"{BASE}/budgets", json={"financial_year_pk": year["financial_year_pk"]}, headers=h)
    assert r.status_code == 201, r.text
    return year, r.json()


def _kendra_scope(client, h, kendra_org_pk) -> dict:
    return make_scope(client, h, kendra_org_pk, activate_with=h)


def _head(client, h, scope, code) -> str:
    return head_pk(client, h, scope, code)


def _line(client, h, budget, head, amount="1000.00", expect=200):
    r = client.put(f"{BASE}/budgets/{budget['finance_budget_pk']}/lines", json={"finance_head_pk": head, "amount": amount}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _step(client, h, budget, step, body=None, expect=200):
    r = client.post(f"{BASE}/budgets/{budget['finance_budget_pk']}/{step}", json=body or {}, headers=h)
    assert r.status_code == expect, f"{step}: {r.status_code} {r.text}"
    return r.json()


def _days_ago(n: int) -> str:
    return (_TODAY - timedelta(days=n)).isoformat()


def _refer(client, h, budget, days_ago=10, expect=200):
    return _step(client, h, budget, "refer", {"referred_on": _days_ago(days_ago)}, expect)


def _views(client, h, budget, days_ago=6, expect=200, **over):
    body = {"advisory_views_date": _days_ago(days_ago), "advisory_views_summary": "Supports it; asks for a larger Satsiksha line."}
    body.update(over)
    return _step(client, h, budget, "advisory-views", body, expect)


def _pass(client, h, budget, days_ago=2, expect=200, **over):
    body = {"resolution_reference": "GB/2026/118", "resolution_date": _days_ago(days_ago)}
    body.update(over)
    return _step(client, h, budget, "pass", body, expect)


@pytest.fixture
def drafted(client, admin_h, kendra_org_pk):
    """A DRAFT budget with one income and one expense line, and the Kendra scope its heads are used from."""
    scope = _kendra_scope(client, admin_h, kendra_org_pk)
    income, expense = _head(client, admin_h, scope, "PRANAMI_ANNUAL"), _head(client, admin_h, scope, "EXPENSE_GENERAL")
    year, budget = _budget(client, admin_h)
    _line(client, admin_h, budget, income, "8000.00")
    detail = _line(client, admin_h, budget, expense, "2000.00")
    return {"year": year, "budget": detail, "scope": scope, "income": income, "expense": expense}


# ═══════════════════════════════════════════════════════════════════════
# Starting a budget
# ═══════════════════════════════════════════════════════════════════════

class TestStartABudget:
    def test_the_kendra_budget_starts_as_a_draft_with_no_lines(self, client, admin_h, kendra_org_pk):
        year, b = _budget(client, admin_h)
        assert b["status"] == "DRAFT" and b["organization_pk"] == kendra_org_pk and b["lines"] == [] and b["changes_need_reason"] is False
        assert b["year_code"] == year["year_code"] and "Add the budget lines" in b["next_step"]
        assert Decimal(b["totals"]["planned_income"]) == 0

    def test_a_second_budget_for_the_same_year_is_refused(self, client, admin_h):
        year, _ = _budget(client, admin_h)
        r = client.post(f"{BASE}/budgets", json={"financial_year_pk": year["financial_year_pk"]}, headers=admin_h)
        assert r.status_code == 409, r.text

    def test_only_the_kendra_has_a_budget(self, client, admin_h, register_org_pk):
        year = _year(client, admin_h)
        r = client.post(f"{BASE}/budgets", json={"financial_year_pk": year["financial_year_pk"], "organization_pk": register_org_pk}, headers=admin_h)
        assert r.status_code == 422 and "Kendra" in r.text

    def test_an_unknown_year_is_refused(self, client, admin_h):
        r = client.post(f"{BASE}/budgets", json={"financial_year_pk": "00000000-0000-0000-0000-000000000000"}, headers=admin_h)
        assert r.status_code == 422

    def test_a_closed_year_cannot_start_a_budget(self, client, admin_h, write_conn):
        year = _year(client, admin_h)
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.financial_year SET status = 'CLOSED' WHERE financial_year_pk = %s", (year["financial_year_pk"],))
        r = client.post(f"{BASE}/budgets", json={"financial_year_pk": year["financial_year_pk"]}, headers=admin_h)
        assert r.status_code == 422 and "CLOSED" in r.text


# ═══════════════════════════════════════════════════════════════════════
# Lines
# ═══════════════════════════════════════════════════════════════════════

class TestLines:
    def test_a_head_has_one_line_and_writing_it_again_changes_the_amount(self, client, admin_h, drafted):
        d = _line(client, admin_h, drafted["budget"], drafted["expense"], "2500.00")
        assert len(d["lines"]) == 2
        assert {Decimal(l["amount"]) for l in d["lines"] if l["direction"] == "EXPENSE"} == {Decimal("2500.00")}

    def test_income_and_expense_are_totalled_apart(self, drafted):
        t = drafted["budget"]["totals"]
        assert (Decimal(t["planned_income"]), Decimal(t["planned_expense"]), Decimal(t["planned_surplus"])) == (Decimal(8000), Decimal(2000), Decimal(6000))

    def test_a_zero_or_negative_amount_is_refused(self, client, admin_h, drafted):
        for amount in ("0", "-5"):
            _line(client, admin_h, drafted["budget"], drafted["expense"], amount, expect=422)

    def test_a_head_of_another_organization_cannot_be_budgeted(self, client, admin_h, drafted, register_org_pk):
        scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h)
        sakha_head = head_pk(client, admin_h, scope, "EXPENSE_GENERAL")
        r = _line(client, admin_h, drafted["budget"], sakha_head, expect=422)
        assert "Kendra" in str(r)

    def test_a_line_can_be_removed_and_is_kept_for_the_trail(self, client, admin_h, drafted, write_conn):
        line = next(l for l in drafted["budget"]["lines"] if l["direction"] == "EXPENSE")
        r = client.delete(f"{BASE}/budgets/{drafted['budget']['finance_budget_pk']}/lines/{line['finance_budget_line_pk']}", headers=admin_h)
        assert r.status_code == 200 and len(r.json()["lines"]) == 1
        cur = write_conn.cursor()
        cur.execute("SELECT is_active, deleted_at IS NOT NULL FROM nss.finance_budget_line WHERE finance_budget_line_pk = %s", (line["finance_budget_line_pk"],))
        assert cur.fetchone() == (False, True)

    def test_removing_an_unknown_line_is_404(self, client, admin_h, drafted):
        r = client.delete(f"{BASE}/budgets/{drafted['budget']['finance_budget_pk']}/lines/00000000-0000-0000-0000-000000000000", headers=admin_h)
        assert r.status_code == 404

    @pytest.mark.parametrize("state", ["REFERRED", "VIEWS_RECEIVED", "PASSED"])
    def test_a_line_can_be_changed_or_removed_in_every_status_but_needs_a_reason_past_draft(self, client, admin_h, drafted, write_conn, state):
        """Owner 2026-11-22, "edit always"."""
        b = drafted["budget"]; pk = b["finance_budget_pk"]
        _refer(client, admin_h, b)
        if state != "REFERRED":
            _views(client, admin_h, b)
        if state == "PASSED":
            _pass(client, admin_h, b)
        r = client.put(f"{BASE}/budgets/{pk}/lines", json={"finance_head_pk": drafted["expense"], "amount": "2600.00"}, headers=admin_h)
        assert r.status_code == 422 and "say why" in r.text                                   # no reason, no change
        r = client.put(f"{BASE}/budgets/{pk}/lines", json={"finance_head_pk": drafted["expense"], "amount": "2600.00", "reason": "Raised after review"}, headers=admin_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == state and d["changes_need_reason"] is True                    # the status does not move
        assert {Decimal(l["amount"]) for l in d["lines"] if l["direction"] == "EXPENSE"} == {Decimal("2600.00")}
        line = next(l for l in d["lines"] if l["direction"] == "INCOME")["finance_budget_line_pk"]
        assert client.delete(f"{BASE}/budgets/{pk}/lines/{line}", headers=admin_h).status_code == 422
        r = client.delete(f"{BASE}/budgets/{pk}/lines/{line}", params={"reason": "Not needed this year"}, headers=admin_h)
        assert r.status_code == 200 and len(r.json()["lines"]) == 1
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'finance_budget_line' AND detail ? 'reason' ORDER BY event_at")
        details = [row[0] for row in cur.fetchall() if row[0].get("finance_budget_pk") == pk or row[0].get("budget_status") == state]
        assert any(x.get("reason") == "Raised after review" and Decimal(x["amount_before"]) == Decimal("2000.00") and x["budget_status"] == state for x in details)
        assert any(x.get("reason") == "Not needed this year" and Decimal(x["amount_before"]) == Decimal("8000.00") for x in details)


# ═══════════════════════════════════════════════════════════════════════
# The steps
# ═══════════════════════════════════════════════════════════════════════

class TestTheSteps:
    def test_the_whole_road_to_a_passed_budget(self, client, admin_h, drafted):
        b = drafted["budget"]
        r = _refer(client, admin_h, b)
        assert r["status"] == "REFERRED" and r["referred_on"] == _days_ago(10) and "Advisory Board's considered views" in r["next_step"]
        v = _views(client, admin_h, b)
        assert v["status"] == "VIEWS_RECEIVED" and "/OUT/" in v["advisory_reference"] and "resolution" in v["next_step"]
        p = _pass(client, admin_h, b)
        assert p["status"] == "PASSED" and p["resolution_reference"] == "GB/2026/118" and p["next_step"] is None and p["changes_need_reason"] is True

    def test_a_budget_without_lines_cannot_be_referred(self, client, admin_h):
        _, b = _budget(client, admin_h)
        _refer(client, admin_h, b, expect=422)

    def test_the_views_cannot_be_recorded_before_the_referral(self, client, admin_h, drafted):
        _views(client, admin_h, drafted["budget"], expect=422)

    def test_it_cannot_pass_without_the_advisory_boards_views(self, client, admin_h, drafted):
        _pass(client, admin_h, drafted["budget"], expect=422)
        _refer(client, admin_h, drafted["budget"])
        r = _pass(client, admin_h, drafted["budget"], expect=422)
        assert "Advisory Board" in str(r)

    def test_a_step_cannot_be_done_twice(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _refer(client, admin_h, b, expect=422)
        _views(client, admin_h, b)
        _views(client, admin_h, b, expect=422)

    def test_the_dates_keep_their_order(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b, days_ago=10)
        _views(client, admin_h, b, days_ago=12, expect=422)                      # views before the referral
        _views(client, admin_h, b, days_ago=6)
        _pass(client, admin_h, b, days_ago=8, expect=422)                        # resolution before the views

    def test_a_date_in_the_future_is_refused(self, client, admin_h, drafted):
        _step(client, admin_h, drafted["budget"], "refer", {"referred_on": (_TODAY + timedelta(days=3)).isoformat()}, expect=422)

    def test_blank_references_are_refused(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b, expect=422, advisory_views_summary="   ")
        _views(client, admin_h, b)
        _pass(client, admin_h, b, expect=422, resolution_reference="   ")

    def test_the_views_are_views_not_a_veto(self, client, admin_h, drafted):
        """Whatever the Advisory Board said, the Governing Body can pass."""
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b, advisory_views_summary="Does not support this budget.")
        assert _pass(client, admin_h, b)["status"] == "PASSED"

    def test_a_passed_budget_is_final(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b)
        _pass(client, admin_h, b)
        _step(client, admin_h, b, "reopen", {"remarks": "change of mind"}, expect=422)             # it cannot go back to draft ...
        _pass(client, admin_h, b, expect=422)                                                        # ... or pass twice (its lines can still be amended)


class TestSendingItBack:
    def test_a_referred_budget_goes_back_to_draft_and_the_referral_is_cleared(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        d = _step(client, admin_h, b, "reopen", {"remarks": "Satsiksha line to be raised"})
        assert d["status"] == "DRAFT" and d["referred_on"] is None and d["changes_need_reason"] is False

    def test_views_already_received_are_cleared_too_and_it_is_referred_afresh(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b)
        d = _step(client, admin_h, b, "reopen", {"remarks": "changed the lines"})
        assert d["status"] == "DRAFT" and d["advisory_reference"] is None and d["advisory_views_summary"] is None
        _line(client, admin_h, b, drafted["expense"], "3000.00")                   # editable again
        _pass(client, admin_h, b, expect=422)                                       # and the views are no longer on file
        assert _refer(client, admin_h, b)["status"] == "REFERRED"

    def test_a_reason_is_required(self, client, admin_h, drafted):
        _refer(client, admin_h, drafted["budget"])
        _step(client, admin_h, drafted["budget"], "reopen", {"remarks": "  "}, expect=422)
        _step(client, admin_h, drafted["budget"], "reopen", {}, expect=422)

    def test_a_draft_has_nothing_to_send_back(self, client, admin_h, drafted):
        _step(client, admin_h, drafted["budget"], "reopen", {"remarks": "x"}, expect=422)

    def test_what_was_cleared_stays_in_the_audit_trail(self, client, admin_h, drafted, write_conn):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b)
        _step(client, admin_h, b, "reopen", {"remarks": "changed the lines"})
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'finance_budget' AND record_pk::text = %s AND detail ? 'remarks'",
                    (b["finance_budget_pk"],))
        detail = cur.fetchone()[0]
        assert "/OUT/" in detail["advisory_reference"] and detail["remarks"] == "changed the lines"


# ═══════════════════════════════════════════════════════════════════════
# Budget against actual (flags, never blocks)
# ═══════════════════════════════════════════════════════════════════════

class TestAgainstActual:
    def _book(self, client, h, year, scope, head_code, kind, amount, *, post=True):
        txn = make_txn(client, h, year, scope, kind=kind, category=head_code, amount=amount)
        return post_txn(client, h, txn) if post else txn

    def test_actual_counts_only_posted_money_of_that_year_and_flags_the_overspend(self, client, admin_h, kendra_org_pk):
        scope = _kendra_scope(client, admin_h, kendra_org_pk)
        year, budget = _budget(client, admin_h, open_year=True)
        _line(client, admin_h, budget, _head(client, admin_h, scope, "PRANAMI_ANNUAL"), "8000.00")
        d = _line(client, admin_h, budget, _head(client, admin_h, scope, "EXPENSE_GENERAL"), "1000.00")
        self._book(client, admin_h, year, scope, "PRANAMI_ANNUAL", "INCOME", "5000.00")
        self._book(client, admin_h, year, scope, "EXPENSE_GENERAL", "EXPENSE", "700.00")
        self._book(client, admin_h, year, scope, "EXPENSE_GENERAL", "EXPENSE", "500.00")
        self._book(client, admin_h, year, scope, "EXPENSE_GENERAL", "EXPENSE", "9999.00", post=False)          # a DRAFT does not count
        d = client.get(f"{BASE}/budgets/{d['finance_budget_pk']}", headers=admin_h).json()
        by_dir = {l["direction"]: l for l in d["lines"]}
        assert Decimal(by_dir["INCOME"]["actual"]) == 5000 and Decimal(by_dir["INCOME"]["remaining"]) == 3000 and by_dir["INCOME"]["over_budget"] is False
        assert Decimal(by_dir["EXPENSE"]["actual"]) == 1200 and Decimal(by_dir["EXPENSE"]["remaining"]) == -200 and by_dir["EXPENSE"]["over_budget"] is True
        assert Decimal(d["totals"]["actual_expense"]) == 1200 and d["unbudgeted"] == []

    def test_spending_on_a_head_with_no_line_is_flagged_not_blocked(self, client, admin_h, kendra_org_pk):
        scope = _kendra_scope(client, admin_h, kendra_org_pk)
        year, budget = _budget(client, admin_h, open_year=True)
        _line(client, admin_h, budget, _head(client, admin_h, scope, "PRANAMI_ANNUAL"), "100.00")
        self._book(client, admin_h, year, scope, "EXPENSE_GENERAL", "EXPENSE", "250.00")                      # posts: nothing blocks it
        d = client.get(f"{BASE}/budgets/{budget['finance_budget_pk']}", headers=admin_h).json()
        assert [(u["head_code"], Decimal(u["actual"])) for u in d["unbudgeted"]] == [("EXPENSE_GENERAL", Decimal(250))]
        assert Decimal(d["totals"]["actual_expense"]) == 250

    def test_a_passed_budget_still_shows_how_the_year_is_going(self, client, admin_h, drafted):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b)
        _pass(client, admin_h, b)
        d = client.get(f"{BASE}/budgets/{b['finance_budget_pk']}", headers=admin_h).json()
        assert d["status"] == "PASSED" and len(d["lines"]) == 2


# ═══════════════════════════════════════════════════════════════════════
# List and scope
# ═══════════════════════════════════════════════════════════════════════

class TestListAndScope:
    def test_the_list_filters_by_year_and_status(self, client, admin_h):
        year, b = _budget(client, admin_h)
        r = client.get(f"{BASE}/budgets", params={"financial_year_pk": year["financial_year_pk"]}, headers=admin_h)
        assert r.status_code == 200 and [i["finance_budget_pk"] for i in r.json()["items"]] == [b["finance_budget_pk"]]
        assert client.get(f"{BASE}/budgets", params={"financial_year_pk": year["financial_year_pk"], "status": "PASSED"}, headers=admin_h).json()["total"] == 0
        assert client.get(f"{BASE}/budgets", params={"status": "NOPE"}, headers=admin_h).status_code == 422

    def test_a_view_only_role_cannot_start_a_budget(self, client, admin_h, viewer_h):
        year = _year(client, admin_h)
        assert client.post(f"{BASE}/budgets", json={"financial_year_pk": year["financial_year_pk"]}, headers=viewer_h).status_code == 403

    def test_a_scoped_sakha_admin_cannot_see_or_change_the_kendra_budget(self, client, admin_h, sakha_admin_h):
        year, b = _budget(client, admin_h)
        pk = b["finance_budget_pk"]
        assert client.get(f"{BASE}/budgets/{pk}", headers=sakha_admin_h).status_code == 403
        assert client.put(f"{BASE}/budgets/{pk}/lines", json={"finance_head_pk": "00000000-0000-0000-0000-000000000000", "amount": "1"},
                          headers=sakha_admin_h).status_code == 403
        assert client.post(f"{BASE}/budgets/{pk}/refer", json={"referred_on": _days_ago(1)}, headers=sakha_admin_h).status_code == 403
        assert client.get(f"{BASE}/budgets", headers=sakha_admin_h).json()["total"] == 0                    # not even listed


# ═══════════════════════════════════════════════════════════════════════
# The letters filed in Correspondence by the referral and by the Advisory Board's reply (owner request 2026-11-22)
# ═══════════════════════════════════════════════════════════════════════

def _letter(write_conn, pk):
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT c.reference_number, c.direction, c.register_organization_pk::text, c.subject, c.remarks, st.value_code,
               c.counterpart_correspondence_pk::text, c.in_reply_to_correspondence_pk::text,
               c.sender_organization_pk::text, c.recipient_organization_pk::text
          FROM nss.correspondence c JOIN nss.master_data st ON st.master_data_pk = c.status_master_data_pk
         WHERE c.correspondence_pk = %s
        """, (str(pk),))
    keys = ("reference", "direction", "register", "subject", "remarks", "status", "counterpart", "in_reply_to", "sender", "recipient")
    row = cur.fetchone()
    return dict(zip(keys, row)) if row else None


def _letters_of(write_conn, budget_pk):
    cur = write_conn.cursor()
    cur.execute("SELECT referral_correspondence_pk::text, views_correspondence_pk::text FROM nss.finance_budget WHERE finance_budget_pk = %s", (budget_pk,))
    return cur.fetchone()


def _count_letters(write_conn, like):
    cur = write_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM nss.correspondence WHERE subject LIKE %s", (like,))
    return cur.fetchone()[0]


@pytest.fixture(scope="module")
def board_org_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""SELECT o.organization_pk::text FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                    WHERE md.value_code = 'ADVISORY_BOARD' AND o.is_active = TRUE LIMIT 1""")
    return cur.fetchone()[0]


class TestLettersInCorrespondence:
    def test_referring_files_a_numbered_letter_to_the_advisory_board_and_it_gets_its_own_copy(self, client, admin_h, drafted, write_conn, kendra_org_pk, board_org_pk):
        b = drafted["budget"]
        d = _refer(client, admin_h, b)
        referral, _ = _letters_of(write_conn, b["finance_budget_pk"])
        out = _letter(write_conn, referral)
        assert out["direction"] == "OUTWARD" and out["register"] == kendra_org_pk and out["recipient"] == board_org_pk and out["sender"] == kendra_org_pk
        assert out["reference"] == d["referral_reference"] and "/OUT/" in out["reference"]
        assert drafted["year"]["year_code"] in out["subject"] and "Planned income" in out["remarks"] and "Planned spending" in out["remarks"]
        copy = _letter(write_conn, out["counterpart"])                                  # the Advisory Board's own INWARD number
        assert copy["direction"] == "INWARD" and copy["register"] == board_org_pk and copy["reference"] == d["referral_inward_reference"]
        assert "/IN/" in copy["reference"] and copy["status"] == "REGISTERED"

    def test_the_advisory_boards_reply_is_filed_in_its_register_threaded_to_its_copy_and_numbered_for_the_kendra(
            self, client, admin_h, drafted, write_conn, kendra_org_pk, board_org_pk):
        b = drafted["budget"]
        d = _refer(client, admin_h, b)
        v = _views(client, admin_h, b, advisory_views_summary="Supports the budget.")
        _, views = _letters_of(write_conn, b["finance_budget_pk"])
        reply = _letter(write_conn, views)
        assert reply["direction"] == "OUTWARD" and reply["register"] == board_org_pk and reply["sender"] == board_org_pk and reply["recipient"] == kendra_org_pk
        assert reply["reference"] == v["advisory_reference"] and "/OUT/" in reply["reference"] and reply["remarks"] == "Supports the budget."
        kendra_copy = _letter(write_conn, reply["counterpart"])
        assert kendra_copy["direction"] == "INWARD" and kendra_copy["register"] == kendra_org_pk and kendra_copy["reference"] == v["views_inward_reference"]
        # a reply to ITS copy of the referral: threaded, and that copy is acted on (the event-driven lifecycle of Correspondence)
        board_copy_pk = _letter(write_conn, _letters_of(write_conn, b["finance_budget_pk"])[0])["counterpart"]
        assert reply["in_reply_to"] == board_copy_pk and _letter(write_conn, board_copy_pk)["status"] == "ACTIONED"

    def test_the_numbers_are_the_registers_own_next_numbers(self, client, admin_h, drafted, write_conn):
        d = _refer(client, admin_h, drafted["budget"])
        n = int(d["referral_reference"].rsplit("/", 1)[1])
        second_year, second = _budget(client, admin_h)
        _line(client, admin_h, second, drafted["income"])
        assert int(_refer(client, admin_h, second)["referral_reference"].rsplit("/", 1)[1]) == n + 1

    def test_a_refused_step_files_no_letter(self, client, admin_h, write_conn):
        _, b = _budget(client, admin_h)                                                   # no lines: refusing to refer
        before = _count_letters(write_conn, "Draft Kendra annual budget%")
        _refer(client, admin_h, b, expect=422)
        assert _count_letters(write_conn, "Draft Kendra annual budget%") == before
        assert _letters_of(write_conn, b["finance_budget_pk"]) == (None, None)

    def test_a_refused_reply_files_no_letter(self, client, admin_h, drafted, write_conn):
        before = _count_letters(write_conn, "Advisory Board's considered views%")
        _views(client, admin_h, drafted["budget"], expect=422)                           # not referred yet
        assert _count_letters(write_conn, "Advisory Board's considered views%") == before

    def test_sending_it_back_clears_the_links_but_the_letters_stay_in_correspondence(self, client, admin_h, drafted, write_conn):
        b = drafted["budget"]
        _refer(client, admin_h, b)
        _views(client, admin_h, b)
        first = _letters_of(write_conn, b["finance_budget_pk"])
        d = _step(client, admin_h, b, "reopen", {"remarks": "changed the lines"})
        assert _letters_of(write_conn, b["finance_budget_pk"]) == (None, None) and d["referral_reference"] is None and d["advisory_reference"] is None
        assert all(_letter(write_conn, pk) is not None for pk in first)                   # history is never deleted
        again = _refer(client, admin_h, b)
        assert again["referral_reference"] != _letter(write_conn, first[0])["reference"]    # a new letter, a new number

    def test_the_audit_trail_names_the_letters(self, client, admin_h, drafted, write_conn):
        b = drafted["budget"]
        d = _refer(client, admin_h, b)
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'finance_budget' AND record_pk::text = %s AND detail ? 'letter'", (b["finance_budget_pk"],))
        detail = cur.fetchone()[0]
        assert detail["letter"] == d["referral_reference"] and detail["advisory_board_copy"] == d["referral_inward_reference"]
