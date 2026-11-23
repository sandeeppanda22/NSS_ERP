"""
Scopes and funds move to the next financial year on their own (owner 2026-11-23). A scope limited to a year can take entries only in that year, so when a year
opens - or closes after the next one already opened - the scopes still in use (DRAFT / ACTIVE, of a CLOSED earlier year) move on to the year that is OPEN.
A fund has no year: it follows its scope, and its balance is cumulative, so it carries over by itself.

The SQL and the rule's edges are DB-free (a stand-in cursor); the end-to-end behaviour through the year transitions needs the database (never run when this
file was written).
"""
import inspect
import re
from datetime import date
from types import SimpleNamespace

import pytest

from api.routers import finance as F
from api.schemas import finance as S

from tests.finance_support import admin_h, admin_user, make_fund, make_scope, move, new_year, register_org_pk, sakha_pks  # noqa: F401  (fixtures + helpers)


class _Cur:
    """Records the statements and answers: the OPEN year, the scopes the UPDATE moved, the fund count."""

    def __init__(self, open_year=("pk-b", "2027-28", date(2027, 4, 1)), moved=(("pk-s1", "EKM-ORG"), ("pk-s2", "EKM-EVT")), funds=3):
        self.open_year, self.moved, self.funds, self.sql, self._rows = open_year, list(moved), funds, [], []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        self.sql.append((s, params))
        self._rows = []
        if s.startswith("SELECT financial_year_pk, year_code, start_date"):
            self._rows = [self.open_year] if self.open_year else []
        elif s.startswith("UPDATE nss.financial_scope"):
            self._rows = self.moved
        elif s.startswith("SELECT COUNT(*) FROM nss.fund_master"):
            self._rows = [(self.funds,)]

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


USER = SimpleNamespace(actor_pk="actor-1")


def test_nothing_moves_when_no_year_is_open():
    cur = _Cur(open_year=None)
    assert F.carry_scopes_forward(cur, USER) is None and not any(s.startswith("UPDATE") for s, _ in cur.sql)


def test_nothing_is_reported_when_no_scope_needed_to_move():
    assert F.carry_scopes_forward(_Cur(moved=()), USER) is None


def test_the_move_reports_the_scopes_and_the_funds_that_follow_them():
    got = F.carry_scopes_forward(_Cur(), USER)
    assert got == {"to_year_pk": "pk-b", "to_year_code": "2027-28", "scopes": 2, "funds": 3, "scope_codes": ["EKM-EVT", "EKM-ORG"]}      # codes in order


def test_only_the_scopes_still_in_use_of_a_closed_earlier_year_move_to_the_latest_open_year():
    cur = _Cur()
    F.carry_scopes_forward(cur, USER)
    first, update = cur.sql[0], next((s, p) for s, p in cur.sql if s.startswith("UPDATE"))
    assert "status = 'OPEN'" in first[0] and "ORDER BY start_date DESC LIMIT 1" in first[0]               # the latest OPEN year
    sql, params = update
    assert "old.status = 'CLOSED'" in sql and "old.start_date < %s" in sql                                  # a closed, EARLIER year only
    assert "fs.status IN ('DRAFT', 'ACTIVE')" in sql and "fs.is_active = TRUE" in sql                       # not a CLOSING / CLOSED scope
    assert "old.financial_year_pk = fs.financial_year_pk" in sql                                           # a scope with no year (spans years) is never touched
    assert params == ("pk-b", "actor-1", date(2027, 4, 1))
    assert "financial_scope SET" not in sql and "fund_master" not in sql                                    # funds are not rewritten: they follow their scope


def test_the_move_happens_when_a_year_opens_and_when_one_closes_and_is_audited_as_a_whole():
    src = inspect.getsource(F.transition_year)
    assert 'carry_scopes_forward(cur, user) if body.status in ("OPEN", "CLOSED") else None' in src
    assert "moved on to" in src and "after" in src
    assert 'out["carried_over"]' in src


def test_a_fund_has_no_year_and_its_balance_is_not_year_bound():
    assert "financial_year_pk" not in inspect.getsource(F._fund_flows_sql)                                  # cumulative: the fund's balance carries over by itself
    assert "financial_year_pk" not in open("database/ddl/14_finance/03_fund_master.sql", encoding="utf-8").read().split("CREATE TABLE")[1]


def test_the_response_carries_the_report_and_the_page_shows_it():
    assert "carried_over" in S.YearResponse.model_fields and set(S.CarriedOver.model_fields) == {"to_year_code", "scopes", "funds", "scope_codes"}
    assert S.YearResponse.model_fields["carried_over"].default is None                                      # the list and every other transition are unchanged
    js = open("frontend/assets/js/finance.js", encoding="utf-8").read()
    assert "done.carried_over.scopes" in js and "moved on to ${done.carried_over.to_year_code}" in js


# ── through the API (database) ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _scope_row(client, h, pk):
    from tests.finance_support import BASE

    return client.get(f"{BASE}/scopes/{pk}", headers=h).json()


@pytest.mark.integration
class TestThroughTheYearTransitions:
    def test_the_scopes_in_use_and_their_funds_move_on_when_the_next_year_opens(self, client, admin_h, register_org_pk, write_conn):
        from tests.finance_support import BASE

        year_a, year_b = new_year(client, admin_h, 2081), new_year(client, admin_h, 2082)
        move(client, admin_h, "years", year_a["financial_year_pk"], "OPEN")
        scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h, financial_year_pk=year_a["financial_year_pk"])
        fund = make_fund(client, admin_h, scope["financial_scope_pk"], activate_with=admin_h)
        spans = make_scope(client, admin_h, register_org_pk, activate_with=admin_h)                         # no year: spans years
        draft = make_scope(client, admin_h, register_org_pk, financial_year_pk=year_a["financial_year_pk"])  # a DRAFT scope of the year
        for step in ("CLOSING", "CLOSED"):
            move(client, admin_h, "years", year_a["financial_year_pk"], step)
        opened = client.post(f"{BASE}/years/{year_b['financial_year_pk']}/transition", json={"status": "OPEN"}, headers=admin_h)
        assert opened.status_code == 200, opened.text
        report = opened.json()["carried_over"]
        assert report["to_year_code"] == year_b["year_code"] and report["scopes"] >= 2 and report["funds"] >= 1
        assert scope["scope_code"] in report["scope_codes"] and draft["scope_code"] in report["scope_codes"]
        assert _scope_row(client, admin_h, scope["financial_scope_pk"])["financial_year_pk"] == year_b["financial_year_pk"]
        assert _scope_row(client, admin_h, draft["financial_scope_pk"])["financial_year_pk"] == year_b["financial_year_pk"]
        assert _scope_row(client, admin_h, spans["financial_scope_pk"])["financial_year_pk"] is None       # untouched
        fund_after = client.get(f"{BASE}/funds/{fund['fund_master_pk']}", headers=admin_h).json()
        assert fund_after["financial_scope_pk"] == scope["financial_scope_pk"]                           # the fund follows its scope, unchanged itself

    def test_a_scope_that_moved_takes_entries_in_the_new_year(self, client, admin_h, register_org_pk, write_conn):
        from tests.finance_support import make_txn, post_txn

        year_a, year_b = new_year(client, admin_h, 2083), new_year(client, admin_h, 2084)
        move(client, admin_h, "years", year_a["financial_year_pk"], "OPEN")
        scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h, financial_year_pk=year_a["financial_year_pk"])
        for step in ("CLOSING", "CLOSED"):
            move(client, admin_h, "years", year_a["financial_year_pk"], step)
        year_b = move(client, admin_h, "years", year_b["financial_year_pk"], "OPEN")
        txn = make_txn(client, admin_h, year_b, scope, kind="INCOME")                                       # would be refused: "belongs to a different financial year"
        assert post_txn(client, admin_h, txn)["status"] == "POSTED"

    def test_a_scope_of_a_year_that_is_not_closed_stays_put(self, client, admin_h, register_org_pk):
        from tests.finance_support import BASE

        year_a, year_b = new_year(client, admin_h, 2085), new_year(client, admin_h, 2086)
        move(client, admin_h, "years", year_a["financial_year_pk"], "OPEN")
        scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h, financial_year_pk=year_a["financial_year_pk"])
        r = client.post(f"{BASE}/years/{year_b['financial_year_pk']}/transition", json={"status": "OPEN"}, headers=admin_h)     # a is still OPEN
        assert r.status_code == 200 and scope["scope_code"] not in ((r.json().get("carried_over") or {}).get("scope_codes") or [])
        assert _scope_row(client, admin_h, scope["financial_scope_pk"])["financial_year_pk"] == year_a["financial_year_pk"]
        # ... and moves when that year finally closes, because the next one is already open
        for step in ("CLOSING", "CLOSED"):
            closed = client.post(f"{BASE}/years/{year_a['financial_year_pk']}/transition", json={"status": step}, headers=admin_h)
        assert closed.status_code == 200 and scope["scope_code"] in closed.json()["carried_over"]["scope_codes"]
        assert _scope_row(client, admin_h, scope["financial_scope_pk"])["financial_year_pk"] == year_b["financial_year_pk"]

    def test_a_closed_scope_does_not_move_and_the_move_is_audited(self, client, admin_h, register_org_pk, write_conn):
        from tests.finance_support import BASE

        year_a, year_b = new_year(client, admin_h, 2087), new_year(client, admin_h, 2088)
        move(client, admin_h, "years", year_a["financial_year_pk"], "OPEN")
        done = make_scope(client, admin_h, register_org_pk, activate_with=admin_h, financial_year_pk=year_a["financial_year_pk"])
        move(client, admin_h, "scopes", done["financial_scope_pk"], "CLOSING")
        move(client, admin_h, "scopes", done["financial_scope_pk"], "CLOSED")
        for step in ("CLOSING", "CLOSED"):
            move(client, admin_h, "years", year_a["financial_year_pk"], step)
        client.post(f"{BASE}/years/{year_b['financial_year_pk']}/transition", json={"status": "OPEN"}, headers=admin_h)
        assert _scope_row(client, admin_h, done["financial_scope_pk"])["financial_year_pk"] == year_a["financial_year_pk"]       # history stays with its year
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'financial_year' AND record_pk::text = %s AND detail ? 'scopes'", (year_b["financial_year_pk"],))
        rows = cur.fetchall()
        assert rows and rows[-1][0]["to_year"] == year_b["year_code"] and isinstance(rows[-1][0]["scopes"], list)
