"""
Sinking Fund reimbursement (Bye-Law C(i)(2)(xviii), FIN-BR-026; owner request 2026-11-24) - the parts that need no database (``--noconftest``):

  * the pure rules of api/services/finance_sinking.py: what is owed, status, what can still be recorded, which expenditure may be registered;
  * the two tables' DDL says what the service says; the tables are wired into all three build scripts, both validate scripts, the live-refresh
    whitelist and its trigger list; the reference-data patch carries the sequence, the head template and the purpose the code names;
  * the route table: seven routes, each behind a Finance permission, writes behind FINANCE_MANAGE, every write audited, nothing commits;
  * a reimbursement is recorded through F.create_transaction (no second implementation of an entry's rules).

The end-to-end behaviour is in tests/api/test_finance_sinking.py (never run against a database when written); the DDL and the service's own queries
were run in a throwaway single-user PostgreSQL 18.
"""
import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.schemas import finance as S
from api.services import finance_sinking as K

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "database" / "ddl" / "14_finance"
SEED = ROOT / "database" / "seed" / "12_finance"
D = Decimal


# ── pure rules ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_what_is_still_owed_never_goes_below_zero():
    assert K.outstanding(D("1000"), D("300")) == D("700")
    assert K.outstanding(D("1000"), D("1000")) == D("0")
    assert K.outstanding(D("1000"), D("1200")) == D("0")


@pytest.mark.parametrize("reimbursed,expected", [("0", K.OPEN), ("0.01", K.PARTLY_REIMBURSED), ("999.99", K.PARTLY_REIMBURSED),
                                                 ("1000", K.REIMBURSED), ("1500", K.REIMBURSED)])
def test_the_status_is_worked_out_from_what_is_posted(reimbursed, expected):
    assert K.status_of(D("1000"), D(reimbursed)) == expected


def test_the_status_values_are_the_schemas_list():
    assert S.SINKING_REIMBURSEMENT_STATUSES == (K.OPEN, K.PARTLY_REIMBURSED, K.REIMBURSED)


def test_what_is_on_its_way_is_reserved_against_the_amount_owed():
    assert K.available_to_record(D("1000"), D("300"), D("200")) == D("500")
    assert K.available_to_record(D("1000"), D("1000"), D("0")) == D("0")
    assert K.available_to_record(D("1000"), D("900"), D("300")) == D("0")


def test_an_amount_is_checked_against_what_can_still_be_recorded():
    K.check_amount(D("500"), D("500"))
    for amount, room, word in ((D("501"), D("500"), "at most 500"), (D("10"), D("0"), "nothing more"), (D("0"), D("500"), "more than zero")):
        with pytest.raises(HTTPException) as e:
            K.check_amount(amount, room)
        assert e.value.status_code == 422 and word in e.value.detail


def test_the_next_step_says_what_to_do():
    assert K.next_step(K.REIMBURSED, D("0")) is None
    assert "Record the Sakha's reimbursement" in K.next_step(K.OPEN, D("100"))
    assert "post" in K.next_step(K.PARTLY_REIMBURSED, D("0")).lower()


def _txn(**over):
    return {"transaction_type": "EXPENSE", "status": "POSTED", **over}


SINKING = {"fund_type": "SINKING_FUND", "organization_pk": "sakha-1"}


def test_a_posted_sinking_fund_expense_by_the_kendra_can_be_registered():
    K.check_registerable(_txn(), SINKING, "kendra-1")
    K.check_registerable(_txn(status="SETTLED"), SINKING, "kendra-1")


@pytest.mark.parametrize("txn,fund,scope_org,word", [
    (_txn(transaction_type="INCOME"), SINKING, "kendra-1", "EXPENSE"),
    (_txn(status="DRAFT"), SINKING, "kendra-1", "POSTED"),
    (_txn(status="APPROVED"), SINKING, "kendra-1", "POSTED"),
    (_txn(), None, "kendra-1", "Sinking Fund"),
    (_txn(), {"fund_type": "GENERAL", "organization_pk": "sakha-1"}, "kendra-1", "Sinking Fund"),
    (_txn(), {"fund_type": "SINKING_FUND", "organization_pk": None}, "kendra-1", "does not name its Sakha"),
    (_txn(), SINKING, "sakha-1", "spent this itself"),
])
def test_everything_else_is_refused(txn, fund, scope_org, word):
    with pytest.raises(HTTPException) as e:
        K.check_registerable(txn, fund, scope_org)
    assert e.value.status_code == 422 and word in e.value.detail


def test_a_reason_is_required():
    assert K.clean_reason("  Seva was neglected ") == "Seva was neglected"
    for blank in (None, "", "   "):
        with pytest.raises(HTTPException):
            K.clean_reason(blank)


# ── Sakha by Sakha (owner 2026-11-24) ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _row(sakha, name, due, reimbursed):
    return {"sakha_organization_pk": sakha, "sakha_name": name, "amount_due": D(due), "reimbursed_amount": D(reimbursed),
            "outstanding_amount": K.outstanding(D(due), D(reimbursed))}


def test_the_kendras_page_adds_up_sakha_by_sakha():
    rows = [_row("s2", "Utkal Sakha", "500", "100"), _row("s1", "Ekamra Sakha", "1000", "300"), _row("s1", "Ekamra Sakha", "250", "250")]
    waiting = [{"sakha_organization_pk": "s1", "sakha_name": "Ekamra Sakha", "amount": D("75")},
               {"sakha_organization_pk": "s3", "sakha_name": "Cuttack Sakha", "amount": D("40")},
               {"sakha_organization_pk": "s3", "sakha_name": "Cuttack Sakha", "amount": D("10")}]
    out = K.by_sakha(rows, waiting)
    assert [s["sakha_name"] for s in out] == ["Cuttack Sakha", "Ekamra Sakha", "Utkal Sakha"]                  # by name
    cuttack, ekamra, utkal = out
    assert (cuttack["registered_count"], cuttack["owed_amount"], cuttack["unregistered_count"], cuttack["unregistered_amount"]) == (0, D("0"), 2, D("50"))
    assert (ekamra["registered_count"], ekamra["owed_amount"], ekamra["reimbursed_amount"], ekamra["outstanding_amount"]) == (2, D("1250"), D("550"), D("700"))
    assert (ekamra["unregistered_count"], ekamra["unregistered_amount"]) == (1, D("75"))
    assert (utkal["owed_amount"], utkal["outstanding_amount"], utkal["unregistered_count"]) == (D("500"), D("400"), 0)
    assert K.by_sakha([], []) == []


def test_the_summary_model_and_the_waiting_rows_carry_the_sakha():
    assert set(S.SinkingSakhaSummary.model_fields) >= {"sakha_organization_pk", "sakha_name", "owed_amount", "reimbursed_amount", "outstanding_amount",
                                                       "unregistered_count", "unregistered_amount"}
    assert "sakha_organization_pk" in S.SinkingExpenditureOption.model_fields
    assert "fm.organization_pk AS sakha_organization_pk" in open(ROOT / "api/services/finance_sinking.py", encoding="utf-8").read()


def test_an_entry_on_a_sinking_fund_always_names_its_sakha():
    from api.routers import finance as F

    head = {"head_code": "EXPENSE_GENERAL", "status": "ACTIVE", "organization_pk": "o", "direction": "EXPENSE", "is_restricted": False, "required_fund_type": None}
    scope = {"organization_pk": "o"}
    F._check_head(head, scope=scope, txn_type="EXPENSE", fund={"fund_type": "SINKING_FUND", "organization_pk": "sakha-1", "is_restricted": False})
    with pytest.raises(HTTPException) as e:
        F._check_head(head, scope=scope, txn_type="EXPENSE", fund={"fund_type": "SINKING_FUND", "organization_pk": None, "is_restricted": False})
    assert e.value.status_code == 422 and "name its Sakha" in e.value.detail


# ── the DDL ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
OBLIGATION = (DDL / "24_finance_sinking_reimbursement.sql").read_text(encoding="utf-8")
ENTRY = (DDL / "25_finance_sinking_reimbursement_entry.sql").read_text(encoding="utf-8")
PATCH = (SEED / "07_sinking_reimbursement_patch.sql").read_text(encoding="utf-8")


def test_the_obligation_table_keeps_the_audit_columns_and_the_checks():
    for column in ("is_active", "created_at", "created_by_sangha_sevi_pk", "updated_at", "updated_by_sangha_sevi_pk", "deleted_at", "deleted_by_sangha_sevi_pk"):
        assert column in OBLIGATION and column in ENTRY
    assert "CHECK (amount_due > 0)" in OBLIGATION and "BTRIM(takeover_reason) <> ''" in OBLIGATION
    assert "uq_finance_sinking_reimbursement_reference" in OBLIGATION
    # one LIVE obligation per expenditure; one live link per income entry
    assert re.search(r"UNIQUE INDEX IF NOT EXISTS uq_finance_sinking_reimbursement_expenditure\s+ON nss\.finance_sinking_reimbursement \(expenditure_transaction_pk\) WHERE is_active = TRUE", OBLIGATION)
    assert re.search(r"UNIQUE INDEX IF NOT EXISTS uq_finance_sinking_entry_transaction\s+ON nss\.finance_sinking_reimbursement_entry \(financial_transaction_pk\) WHERE is_active = TRUE", ENTRY)


def test_nothing_the_books_know_is_stored_twice():
    # who owes, which fund and when come from the expenditure; what is reimbursed is read from the entries - so no such columns exist
    for forbidden in ("organization_pk", "fund_master_pk", "reimbursed", "status", "outstanding"):
        assert forbidden not in re.sub(r"--[^\n]*", "", OBLIGATION).replace("expenditure_transaction_pk", ""), forbidden


def test_the_service_names_the_tables_and_columns_the_ddl_creates():
    sql = open(ROOT / "api/services/finance_sinking.py", encoding="utf-8").read()
    for table in ("finance_sinking_reimbursement", "finance_sinking_reimbursement_entry"):
        assert f"nss.{table}" in sql
    for column in ("reimbursement_reference", "expenditure_transaction_pk", "takeover_reason", "resolution_reference", "amount_due",
                   "finance_sinking_reimbursement_pk", "financial_transaction_pk"):
        assert column in OBLIGATION + ENTRY, column


# ── the patch and the build wiring ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_patch_carries_what_the_code_names():
    assert f"'{K.SEQUENCE_CODE}'" in PATCH and "'SRB'" in PATCH
    assert f"'{K.HEAD_CODE}'" in PATCH and "'INCOME'" in PATCH and "'SINKING_FUND'" in PATCH            # income, only into a Sinking Fund
    assert "'KENDRA_SAKHA_TAKEOVER'" in PATCH and "'DISBURSEMENT_PURPOSE'" in PATCH
    assert re.sub(r"--[^\n]*", "", PATCH).count("ON CONFLICT") == 3                                                              # a re-run never overwrites an admin's edit


@pytest.mark.parametrize("script", ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"])
def test_every_build_script_creates_the_tables_and_runs_the_patch(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    order = [text.index(n) for n in ("24_finance_sinking_reimbursement.sql", "25_finance_sinking_reimbursement_entry.sql", "07_sinking_reimbursement_patch.sql")]
    assert order == sorted(order)
    assert text.index("22_finance_budget_line.sql") < order[0]                                          # after the tables they depend on


@pytest.mark.parametrize("script", ["database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"])
def test_both_validate_scripts_check_the_tables(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    assert text.count("finance_sinking_reimbursement") >= 4 and "finance_sinking_reimbursement_entry" in text


def test_both_tables_are_on_the_live_feed():
    live = (ROOT / "api/routers/live.py").read_text(encoding="utf-8")
    triggers = (ROOT / "database/ddl/12_live_refresh/02_live_change_triggers.sql").read_text(encoding="utf-8")
    for table in ("finance_sinking_reimbursement", "finance_sinking_reimbursement_entry"):
        assert f'"{table}"' in live and f"'{table}'" in triggers


# ── the Kendra's procedure: a Sakha's admin or office bearer does not see it (owner 2026-11-24) ────────────────────────────────────────────────────
class _Cur:
    def __init__(self, kendra):
        self.kendra = kendra

    def execute(self, *_a, **_k):
        pass

    def fetchone(self):
        return (self.kendra,) if self.kendra else None


def test_only_someone_whose_scope_reaches_the_kendra_is_on_the_kendras_side(monkeypatch):
    from api.routers import finance as F

    def reach(value):
        monkeypatch.setattr(F, "actor_scope_org_pks", lambda cur, user: value)

    reach(None)
    assert F.kendra_side_of(_Cur("kendra-1"), object()) is True                                # global authority
    reach({"kendra-1", "sakha-9"})
    assert F.kendra_side_of(_Cur("kendra-1"), object()) is True                                # the Kendra is in reach
    reach({"sakha-1"})
    assert F.kendra_side_of(_Cur("kendra-1"), object()) is False                               # a Sakha's admin or office bearer
    reach(set())
    assert F.kendra_side_of(_Cur("kendra-1"), object()) is False
    reach({"sakha-1"})
    assert F.kendra_side_of(_Cur(None), object()) is False                                     # no Kendra organization at all


def test_the_reference_tells_the_page_which_side_the_caller_is_on():
    from api.schemas.finance import FinanceReference

    assert "kendra_side" in FinanceReference.model_fields and FinanceReference.model_fields["kendra_side"].default is False
    import inspect

    from api.routers import finance as F

    assert '"kendra_side": kendra_side' in inspect.getsource(F.reference)


def test_every_read_and_write_is_the_kendras_scope_nothing_opens_it_to_the_sakha():
    text = (ROOT / "api/routers/finance_sinking.py").read_text(encoding="utf-8")
    assert "_visible_either" not in text and "can_manage" not in text and "actor_scope_org_pks" not in text
    assert text.count('F._visible(cur, user, "fs.organization_pk")') >= 3                          # list, expenditures, summary
    assert "can_manage" not in S.SinkingReimbursementResponse.model_fields


# ── the routes ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
EXPECTED = {
    ("GET", "/api/v1/finance/sinking-reimbursements"), ("GET", "/api/v1/finance/sinking-reimbursements/expenditures"),
    ("GET", "/api/v1/finance/sinking-reimbursements/summary"),
    ("POST", "/api/v1/finance/sinking-reimbursements"), ("GET", "/api/v1/finance/sinking-reimbursements/{pk}"),
    ("POST", "/api/v1/finance/sinking-reimbursements/{pk}/reimbursements"), ("DELETE", "/api/v1/finance/sinking-reimbursements/{pk}"),
}


class TestRoutes:
    def test_the_seven_routes_and_only_those(self):
        from api.routers.finance_sinking import router

        assert {(m, r.path) for r in router.routes for m in r.methods if m != "HEAD"} == EXPECTED
        assert len(router.routes) == 7

    def test_the_fixed_paths_are_registered_before_the_pk_path(self):
        from api.routers.finance_sinking import router

        paths = [r.path for r in router.routes if "GET" in r.methods]
        for fixed in ("expenditures", "summary"):
            assert paths.index(f"/api/v1/finance/sinking-reimbursements/{fixed}") < paths.index("/api/v1/finance/sinking-reimbursements/{pk}")

    def test_the_app_serves_them_once_each(self):
        from api.main import app

        served = [(m, r.path) for r in app.routes for m in getattr(r, "methods", ()) if m != "HEAD" and "sinking-reimbursements" in getattr(r, "path", "")]
        assert sorted(served) == sorted(EXPECTED)

    def test_every_route_needs_a_finance_permission_and_every_write_the_manage_one(self):
        from api.routers import finance as F
        from api.routers.finance_sinking import router

        calls = {(m, r.path): [d.call for d in r.dependant.dependencies] for r in router.routes for m in r.methods if m != "HEAD"}
        for key, deps in calls.items():
            assert (F._VIEW if key[0] == "GET" else F._MANAGE) in deps, key

    def test_every_write_is_audited_and_the_router_does_not_commit(self):
        text = (ROOT / "api/routers/finance_sinking.py").read_text(encoding="utf-8")
        writes = len(re.findall(r"@router\.(?:post|delete)\(", text))
        assert writes == 3 and text.count("F._audit(") == writes
        assert ".commit()" not in text and "f\"SELECT" not in text and "f'SELECT" not in text

    def test_a_reimbursement_is_an_ordinary_entry_made_by_the_one_implementation(self):
        import inspect

        from api.routers import finance_sinking as R

        src = inspect.getsource(R.record_reimbursement)
        assert "F.create_transaction(" in src and "INSERT INTO nss.financial_transaction" not in src
        assert '"INCOME"' in src and "K.check_amount(" in src
