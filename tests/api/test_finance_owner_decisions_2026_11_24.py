"""
Five owner decisions of 2026-11-24 on Finance, the parts that need no database (run with ``--noconftest``):

  1. the Kendra's Assistant Secretary holds the Kendra finance role by seat (rule in rbac_service, tested in test_finance_admin_rule.py);
  2. a passed budget's Advisory Board summary and resolution reference can be corrected, with a reason (finance_budget.validate_correction);
  3. a new transaction / transfer / scope is made in the CURRENT financial year only, enforced by the API (finance.require_current_year);
  4. the Kendra may start next year's budget in advance (the page's finBudgetNextYear);
  5. a refusal to close a year names the entries in the way (finance.describe_blockers).

The end-to-end behaviour through the API needs the database (not run when this file was written).
"""
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.routers import finance as F
from api.services import finance_budget as B

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


def _y(code, state):
    return {"financial_year_pk": code, "year_code": code, "status": state}


# ── 3. the current year ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
CASES = {
    "open_wins": ([("2026-27", "OPEN"), ("2027-28", "PLANNED"), ("2025-26", "CLOSED")], "2026-27"),
    "latest_open": ([("2026-27", "OPEN"), ("2027-28", "OPEN")], "2027-28"),
    "all_closed_latest": ([("2025-26", "CLOSED"), ("2026-27", "CLOSED")], "2026-27"),
    "closing_before_planned": ([("2026-27", "CLOSING"), ("2027-28", "PLANNED")], "2026-27"),
    "earliest_planned": ([("2027-28", "PLANNED"), ("2028-29", "PLANNED")], "2027-28"),
    "none": ([], None),
}


@pytest.mark.parametrize("name", list(CASES))
def test_the_current_year_rule(name):
    years, expected = CASES[name]
    found = F.pick_current_year([_y(c, s) for c, s in years])
    assert (found["year_code"] if found else None) == expected


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_page_and_the_server_pick_the_same_current_year():
    src = (ROOT / "frontend/assets/js/finance.js").read_text(encoding="utf-8")
    start = src.index("            get finCurrentYear() {")
    end = src.index("            get finOtherLiveYears() {")
    script = f"""
    const host = {{ finYears: [], {src[start:end].rstrip().rstrip(",")} }};
    const cases = {json.dumps({k: v[0] for k, v in CASES.items()})};
    const out = {{}};
    for (const [name, rows] of Object.entries(cases)) {{
        host.finYears = rows.map(([code, status]) => ({{ year_code: code, status, financial_year_pk: code }}));
        out[name] = host.finCurrentYear ? host.finCurrentYear.year_code : null;
    }}
    console.log(JSON.stringify(out));
    """
    run = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {k: v[1] for k, v in CASES.items()}


class _Cursor:
    """Answers the one query require_current_year makes with fixed years."""

    def __init__(self, years):
        self.years = years
        self.description = [("financial_year_pk",), ("year_code",), ("status",)]

    def execute(self, *_a, **_k):
        pass

    def fetchall(self):
        return [(c, c, s) for c, s in self.years]


@pytest.mark.parametrize("what,open_only", [("transaction", True), ("transfer", True), ("financial scope", False)])
def test_only_the_current_year_takes_a_new_record(what, open_only):
    cur = _Cursor([("2026-27", "OPEN"), ("2027-28", "PLANNED")])
    F.require_current_year(cur, "2026-27", what, open_only=open_only)                      # the current one: fine
    with pytest.raises(HTTPException) as e:
        F.require_current_year(cur, "2027-28", what, open_only=open_only)
    assert e.value.status_code == 422 and "2026-27" in e.value.detail and what in e.value.detail


def test_a_scope_may_take_a_year_still_closing_but_an_entry_needs_an_open_one():
    cur = _Cursor([("2026-27", "CLOSING")])
    F.require_current_year(cur, "2026-27", "financial scope")
    with pytest.raises(HTTPException) as e:
        F.require_current_year(cur, "2026-27", "transaction", open_only=True)
    assert "OPEN" in e.value.detail


def test_nothing_is_made_in_a_closed_year_or_when_there_is_no_year():
    with pytest.raises(HTTPException):
        F.require_current_year(_Cursor([("2026-27", "CLOSED")]), "2026-27", "financial scope")
    with pytest.raises(HTTPException) as e:
        F.require_current_year(_Cursor([]), "x", "transaction")
    assert "no financial year" in e.value.detail


def test_every_creation_route_asks_for_the_current_year():
    import inspect

    for fn in (F.create_transaction, F.create_transfer, F.create_scope):
        assert "require_current_year(" in inspect.getsource(fn), fn.__name__
    assert "require_current_year(" in inspect.getsource(F.update_transaction)              # moving a draft to another year is making it there
    assert "require_current_year(" in inspect.getsource(F.update_scope)
    # approving / posting what already exists must NOT ask: an entry made in last year's still-open year has to be able to finish
    assert "require_current_year(" not in inspect.getsource(F._check_transaction)
    assert "require_current_year(" not in inspect.getsource(F._check_transfer)


# ── 5. the refusal names the entries ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_refusal_names_what_is_in_the_way():
    line = F.describe_blockers("transaction", "DRAFT / PENDING_APPROVAL / APPROVED", [("FTX12", "DRAFT", "EKM-ORG"), ("FTX15", "APPROVED", "EKM-EVT")], 2)
    assert line == "2 transaction(s) still DRAFT / PENDING_APPROVAL / APPROVED: FTX12 (DRAFT, EKM-ORG), FTX15 (APPROVED, EKM-EVT)"


def test_the_refusal_counts_what_it_does_not_name():
    rows = [(f"FTX{i}", "DRAFT", "S") for i in range(F.BLOCKER_LIST_LIMIT)]
    assert F.describe_blockers("transaction", "x", rows, F.BLOCKER_LIST_LIMIT + 3).endswith("and 3 more")


def test_nothing_in_the_way_says_nothing():
    assert F.describe_blockers("transfer", "x", [], 0) is None


def test_both_closings_use_the_one_helper_with_the_names():
    import inspect

    src = inspect.getsource(F._open_work_blockers)
    assert "transaction_reference" in src and "transfer_reference" in src and "LIMIT" in src
    assert "_open_work_blockers(" in inspect.getsource(F.transition_year) and "_open_work_blockers(" in inspect.getsource(F.transition_scope)


# ── 2. correcting a passed budget ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _budget(status, **kw):
    base = {"finance_budget_pk": "b", "status": status, "advisory_views_summary": "Agreed.", "resolution_reference": "GB/9"}
    return {**base, **kw}


def test_a_summary_can_be_corrected_once_the_views_are_on_file_and_after_passing():
    for status in (B.VIEWS_RECEIVED, B.PASSED):
        got = B.validate_correction(_budget(status), summary="Agreed, with a note.", resolution_reference=None, reason="typo")
        assert got == {"advisory_views_summary": "Agreed, with a note.", "_reason": "typo"}


def test_the_resolution_reference_can_be_corrected_only_once_passed():
    got = B.validate_correction(_budget(B.PASSED), summary=None, resolution_reference="GB/9A", reason="wrong number")
    assert got["resolution_reference"] == "GB/9A"
    with pytest.raises(HTTPException) as e:
        B.validate_correction(_budget(B.VIEWS_RECEIVED), summary=None, resolution_reference="GB/9A", reason="x")
    assert "not passed" in e.value.detail


@pytest.mark.parametrize("status", [B.DRAFT, B.REFERRED])
def test_nothing_to_correct_before_the_views_are_on_file(status):
    with pytest.raises(HTTPException):
        B.validate_correction(_budget(status), summary="x", resolution_reference=None, reason="y")


def test_a_correction_needs_a_reason_and_a_real_change():
    for reason in (None, "", "   "):
        with pytest.raises(HTTPException):
            B.validate_correction(_budget(B.PASSED), summary="New", resolution_reference=None, reason=reason)
    with pytest.raises(HTTPException) as e:
        B.validate_correction(_budget(B.PASSED), summary="Agreed.", resolution_reference="GB/9", reason="same")      # identical: nothing changes
    assert "Nothing to correct" in e.value.detail
    with pytest.raises(HTTPException):
        B.validate_correction(_budget(B.PASSED), summary="   ", resolution_reference=None, reason="blank")


def test_a_correction_keeps_the_status_and_the_old_text():
    class Cur:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params=None):
            self.sql.append((sql, params))

    cur = Cur()
    done = B.correct(cur, "actor", _budget(B.PASSED), summary="New", resolution_reference=None, reason="typo")
    assert done == {"reason": "typo", "changed": {"advisory_views_summary": ("Agreed.", "New")}}
    sql = cur.sql[0][0]
    assert "status" not in sql.split("WHERE")[0].replace("updated_by", "") and "advisory_views_summary = %s" in sql


# ── 4. the budget in advance (page) ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_page_offers_next_year_in_advance():
    src = (ROOT / "frontend/assets/js/finance-budget.js").read_text(encoding="utf-8")
    start = src.index("            get finBudgetNextYear() {")
    end = src.index("            get finBudgetCanStart()")
    script = f"""
    const host = {{ finYears: [], finBudgets: [], finScopeYear: null, {src[start:end].rstrip().rstrip(",")} }};
    const yr = (code, status) => ({{ year_code: code, status, financial_year_pk: code }});
    const r = {{}};
    host.finYears = [yr("2026-27", "OPEN"), yr("2027-28", "PLANNED"), yr("2025-26", "CLOSED")]; host.finScopeYear = host.finYears[0];
    r.next = host.finBudgetNextYear && host.finBudgetNextYear.year_code;
    host.finBudgets = [{{ financial_year_pk: "2027-28" }}]; r.taken = host.finBudgetNextYear;
    host.finBudgets = []; host.finYears = [yr("2026-27", "OPEN")]; r.none = host.finBudgetNextYear;
    host.finYears = [yr("2026-27", "OPEN"), yr("2027-28", "PLANNED"), yr("2028-29", "PLANNED")]; r.nearest = host.finBudgetNextYear.year_code;
    host.finScopeYear = null; r.noCurrent = host.finBudgetNextYear;
    console.log(JSON.stringify(r));
    """
    run = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {"next": "2027-28", "taken": None, "none": None, "nearest": "2027-28", "noCurrent": None}


def test_the_budget_api_accepts_any_year_that_is_not_closed_so_next_year_is_possible():
    import inspect

    src = inspect.getsource(B.create)
    assert '"CLOSED"' in src and "PLANNED" not in src         # only a closed year is refused: the next (PLANNED) one is allowed
