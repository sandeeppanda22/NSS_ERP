"""
Creating a financial year (owner 2026-11-23: "only a new financial year will be created when the last FY is closed"): only when the LATEST year is CLOSED,
and only the very next one. The rule is the server's (api/routers/finance.py::check_next_year); the Finance page offers just the one year it will accept.

The pure rule and the page's dropdown run DB-free (``--noconftest``); the end-to-end behaviour through POST /years needs the database (never run when this
file was written). Other tests set their years up directly (tests/finance_support.py::new_year), because they are not bound by this rule.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.routers import finance as F

from tests.finance_support import admin_h, admin_user, sakha_admin, sakha_admin_h, register_org_pk, sakha_pks  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


# ── the pure rule ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_first_year_may_be_any_year():
    F.check_next_year(None, 2026)


def test_the_next_year_after_a_closed_one_is_accepted():
    F.check_next_year(("2026-27", "CLOSED", 2026), 2027)


@pytest.mark.parametrize("state", ["PLANNED", "OPEN", "CLOSING"])
def test_no_new_year_while_the_last_one_is_not_closed(state):
    with pytest.raises(HTTPException) as e:
        F.check_next_year(("2026-27", state, 2026), 2027)
    assert e.value.status_code == 422 and "2026-27" in e.value.detail and state in e.value.detail and "CLOSED" in e.value.detail


@pytest.mark.parametrize("start", [2026, 2025, 2028, 2030])
def test_only_the_very_next_year_even_after_a_closed_one(start):
    with pytest.raises(HTTPException) as e:
        F.check_next_year(("2026-27", "CLOSED", 2026), start)
    assert e.value.status_code == 422 and "2027-28" in e.value.detail and "one after another" in e.value.detail


def test_year_codes_roll_over_the_century():
    assert F.year_code_of(2026) == "2026-27" and F.year_code_of(2099) == "2099-00"


def test_the_endpoint_checks_after_the_authority_and_the_duplicate_and_asks_for_the_latest_by_start():
    import inspect

    src = inspect.getsource(F.create_year)
    assert src.index("_require_global(") < src.index("already exists") < src.index("check_next_year(cur.fetchone(), body.start_year)")
    assert "ORDER BY start_date DESC LIMIT 1" in src and "is_active = TRUE" in src


# ── the page offers what the server accepts ───────────────────────────────────────────────────────────────────────────────────────────────────────
FIN_JS = (ROOT / "frontend/assets/js/finance.js").read_text(encoding="utf-8")
ADMIN_HTML = (ROOT / "frontend/admin.html").read_text(encoding="utf-8")


def _panel() -> str:
    start = ADMIN_HTML.index("<!-- Financial years -->")
    return ADMIN_HTML[start:ADMIN_HTML.index("<!-- New scope form -->", start)]


def test_the_form_is_a_dropdown_with_the_next_year_only_and_the_button_hides_when_nothing_is_allowed():
    panel = _panel()
    assert 'x-for="(c, i) in finYearChoices"' in panel and 'x-model="finYearForm.start_year"' in panel
    assert 'x-show="canApproveFinance && !finYearForm.show && finYearChoices.length > 0"' in panel
    assert "finYearBlockedBy" in panel and "can be created once" in panel                              # and says why there is nothing to create
    assert "get finYearChoices()" in FIN_JS and "this.finYearChoices[0]" in FIN_JS


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_choices_run_as_intended():
    start = FIN_JS.index("            get finLatestYear() {")
    end = FIN_JS.index("            async finSubmitYear()")
    script = """
    const newYearForm = () => ({ show: false, saving: false, error: "", start_year: "" });
    const host = { finYears: [], %s };
    const set = (years) => { host.finYears = years.map(([code, status]) => ({ year_code: code, status })); };
    const r = {};
    set([["2026-27", "CLOSED"]]); r.afterClosed = host.finYearChoices.map((c) => c.label); r.blockedClosed = host.finYearBlockedBy;
    set([["2026-27", "OPEN"]]); r.whileOpen = host.finYearChoices.length; r.blockedBy = host.finYearBlockedBy.year_code;
    set([["2026-27", "CLOSED"], ["2027-28", "PLANNED"]]); r.latestWins = [host.finYearChoices.length, host.finYearBlockedBy.year_code];
    set([["2027-28", "CLOSED"], ["2026-27", "CLOSED"]]); r.order = host.finYearChoices.map((c) => c.value);          // the latest by START, whatever the list order
    set([]); r.none = host.finYearChoices.length; r.noneBlocked = host.finYearBlockedBy;
    set([["2100-01", "CLOSED"]]); r.cap = host.finYearChoices.length;                                              // the API accepts up to 2100
    set([["2026-27", "CLOSED"]]); host.finOpenYearForm(); r.preselected = [host.finYearForm.show, host.finYearForm.start_year];
    set([["2026-27", "OPEN"]]); host.finOpenYearForm(); r.noneToSelect = host.finYearForm.start_year;
    console.log(JSON.stringify(r));
    """ % FIN_JS[start:end].replace("%", "%%").rstrip().rstrip(",")
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["afterClosed"] == ["2027-28"] and got["blockedClosed"] is None                       # ONE option: the next
    assert got["whileOpen"] == 0 and got["blockedBy"] == "2026-27"
    assert got["latestWins"] == [0, "2027-28"]
    assert got["order"] == ["2028"]
    assert got["none"] == 1 and got["noneBlocked"] is None                                           # no year yet: the current one is offered
    assert got["cap"] == 0
    assert got["preselected"] == [True, "2027"] and got["noneToSelect"] == ""


# ── through the API (database) ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
class _Years:
    """Helpers over the real endpoints; the years' states are set DIRECTLY (test data), the creation goes through POST /years."""

    def __init__(self, client, headers, conn):
        from tests.finance_support import BASE

        self.client, self.headers, self.conn, self.base = client, headers, conn, BASE

    def all(self):
        return self.client.get(f"{self.base}/years", headers=self.headers).json()["items"]

    def latest(self):
        return max(self.all(), key=lambda y: y["start_date"])

    def latest_start(self) -> int:
        return int(self.latest()["year_code"][:4])

    def set_status(self, year_pk, state):
        self.conn.cursor().execute("UPDATE nss.financial_year SET status = %s WHERE financial_year_pk = %s", (state, str(year_pk)))

    def close_all(self):
        self.conn.cursor().execute("UPDATE nss.financial_year SET status = 'CLOSED'")

    def create(self, start):
        return self.client.post(f"{self.base}/years", json={"start_year": start}, headers=self.headers)


@pytest.fixture
def years(client, admin_h, write_conn):
    return _Years(client, admin_h, write_conn)


@pytest.mark.integration
class TestThroughTheApi:
    def test_no_new_year_while_the_last_is_not_closed(self, years):
        years.close_all()
        latest, start = years.latest(), years.latest_start()
        assert start < 2099
        for state in ("PLANNED", "OPEN", "CLOSING"):
            years.set_status(latest["financial_year_pk"], state)
            r = years.create(start + 1)
            assert r.status_code == 422 and state in r.text and "CLOSED" in r.text and latest["year_code"] in r.text, (state, r.text)

    def test_the_next_year_is_created_once_the_last_is_closed_and_then_the_door_shuts_again(self, years):
        years.close_all()
        start = years.latest_start()
        assert start < 2098
        r = years.create(start + 1)
        assert r.status_code == 201 and r.json()["status"] == "PLANNED" and r.json()["year_code"] == f"{start + 1}-{(start + 2) % 100:02d}"
        again = years.create(start + 2)                                              # the year just created is PLANNED, not closed
        assert again.status_code == 422 and "CLOSED" in again.text

    def test_only_the_very_next_year(self, years):
        years.close_all()
        start = years.latest_start()
        assert start < 2098
        too_far = years.create(start + 2)
        assert too_far.status_code == 422 and "one after another" in too_far.text
        assert years.create(start).status_code == 409                                # an existing year is still a duplicate, not a rule message
        assert years.create(start + 1).status_code == 201

    def test_a_scoped_admin_is_still_refused_before_the_rule(self, client, sakha_admin_h):
        from tests.finance_support import BASE

        assert client.post(f"{BASE}/years", json={"start_year": 2095}, headers=sakha_admin_h).status_code == 403

    def test_tests_that_need_years_of_their_own_are_not_bound_by_the_rule(self, client, admin_h):
        from tests.finance_support import make_year

        assert make_year(client, admin_h, open_=False)["status"] == "PLANNED"        # set up directly, whatever the latest year's state
