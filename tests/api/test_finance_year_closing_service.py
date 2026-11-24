"""
Closing the financial year Sakha by Sakha and Kendra (owner request 2026-11-25) - the parts that need no database (``--noconftest``):

  * the pure rules of api/services/finance_year_closing.py: the steps, what a closing Sangha may still do, which Sanghas the year waits for;
  * the DDL says what the service says; the table is wired into all three build scripts, both validate scripts and the live feed;
  * the router: two routes behind the Finance permissions, every write audited, nothing commits, the year closes by itself through the ONE
    implementation (F.apply_year_status) that the NSS-wide transition also uses;
  * a Sangha that has closed refuses new entries (create) and, once CLOSED, any entry (submit / approve / post).

The end-to-end behaviour is in tests/api/test_finance_year_closing.py (never run against a database when written); the DDL and the service's own
queries were run in a throwaway single-user PostgreSQL 18 (a Sakha with its own transfer counted once, a Kendra, a global scope, the CLOSING and
CLOSED steps).
"""
import inspect
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.schemas import finance as S
from api.services import finance_year_closing as C

ROOT = Path(__file__).resolve().parents[2]
DDL = (ROOT / "database/ddl/14_finance/26_finance_year_closing.sql").read_text(encoding="utf-8")


def _sangha(name, status="OPEN", tx=0, tr=0, pk=None):
    return {"organization_pk": pk or name, "organization_name": name, "status": status, "unfinished_transactions": tx, "unfinished_transfers": tr}


# ── pure rules ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_sangha_goes_open_closing_closed_and_never_skips_or_goes_back():
    C.check_step(C.OPEN, C.CLOSING)
    C.check_step(C.CLOSING, C.CLOSED)
    for current, target in ((C.OPEN, C.CLOSED), (C.CLOSING, C.OPEN), (C.CLOSED, C.OPEN), (C.CLOSED, C.CLOSING), (C.OPEN, C.OPEN)):
        with pytest.raises(HTTPException) as e:
            C.check_step(current, target)
        assert e.value.status_code == 422 and current in e.value.detail


def test_a_sangha_closes_only_while_the_year_is_open_or_closing():
    C.require_year_open_for_closing("2026-27", "OPEN")
    C.require_year_open_for_closing("2026-27", "CLOSING")
    for state in ("PLANNED", "CLOSED"):
        with pytest.raises(HTTPException) as e:
            C.require_year_open_for_closing("2026-27", state)
        assert "2026-27" in e.value.detail and state in e.value.detail


def test_closing_takes_no_new_entry_and_closed_takes_nothing():
    assert [C.refuses_new_entries(s) for s in (C.OPEN, C.CLOSING, C.CLOSED)] == [False, True, True]
    assert [C.refuses_any_entry(s) for s in (C.OPEN, C.CLOSING, C.CLOSED)] == [False, False, True]        # CLOSING may still finish what is in progress


def test_the_refusal_names_the_sangha_the_year_and_what_is_still_possible():
    new = C.refusal("Ekamra Sakha", "2026-27", C.CLOSING, new=True)
    assert new.status_code == 422 and "Ekamra Sakha" in new.detail and "2026-27" in new.detail and "started closing" in new.detail and "finish what is in progress" in new.detail
    shut = C.refusal("Ekamra Sakha", "2026-27", C.CLOSED, new=False)
    assert "closed its books" in shut.detail and "nothing more" in shut.detail


def test_the_year_waits_for_every_sangha_with_unfinished_work():
    plan = C.plan_year_close([_sangha("A", C.CLOSED), _sangha("B", tx=2), _sangha("C"), _sangha("D", C.CLOSING, tr=1)], [])
    assert [s["organization_name"] for s in plan["blocking"]] == ["B", "D"]                  # unfinished: named, never closed for them
    assert [s["organization_name"] for s in plan["closable"]] == ["C"]                       # finished: closed along with the year
    assert plan["global"] == []                                                              # (A is already closed: nothing to do)


def test_unfinished_work_on_a_scope_of_no_sangha_blocks_the_year_too():
    plan = C.plan_year_close([_sangha("A", C.CLOSED)], ["Scopes that belong to no Sangha: 1 transaction(s) still unfinished"])
    assert plan["blocking"] == [] and plan["global"] and not C.everyone_closed([_sangha("A", C.CLOSED)], plan["global"])


def test_the_year_closes_by_itself_only_when_everyone_has_closed():
    assert C.everyone_closed([_sangha("A", C.CLOSED), _sangha("B", C.CLOSED)], [])
    assert not C.everyone_closed([_sangha("A", C.CLOSED), _sangha("B", C.CLOSING)], [])
    assert not C.everyone_closed([_sangha("A", C.OPEN)], [])
    assert C.everyone_closed([], [])                                                          # nobody had any activity


def test_unfinished_text_counts_what_is_there():
    assert C.unfinished_text("Ekamra Sakha", 2, 1) == "Ekamra Sakha: 2 transaction(s), 1 transfer(s) still unfinished"
    assert C.unfinished_text("Kendra", 0, 3) == "Kendra: 3 transfer(s) still unfinished"
    assert C.unfinished_text("Utkal Sakha", 0, 0, 1, 2, 3) == ("Utkal Sakha: 1 draft receipt(s), 2 unfinished payment(s), "
                                                              "3 online payment(s) not yet booked or finished still unfinished")


def test_the_status_lists_are_the_schemas_and_one_definition_of_unfinished():
    assert S.YEAR_CLOSING_STATUSES == C.STATUSES == (C.OPEN, C.CLOSING, C.CLOSED)
    from api.routers import finance as F

    src = inspect.getsource(F._open_work_blockers)
    assert "closing_service.UNFINISHED_TRANSACTION_STATUSES" in src and "closing_service.UNFINISHED_TRANSFER_STATUSES" in src
    assert "'DRAFT','PENDING_APPROVAL','APPROVED'" not in src                                 # no second list


# ── the DDL ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_table_keeps_the_audit_columns_and_the_checks():
    for column in ("is_active", "created_at", "created_by_sangha_sevi_pk", "updated_at", "updated_by_sangha_sevi_pk", "deleted_at", "deleted_by_sangha_sevi_pk"):
        assert column in DDL
    assert "CHECK (status IN ('CLOSING', 'CLOSED'))" in DDL                                    # OPEN is the absence of a row
    assert "status = 'CLOSED' AND closed_on IS NOT NULL AND closed_on >= closing_started_on" in DDL
    assert re.search(r"UNIQUE INDEX IF NOT EXISTS uq_finance_year_closing_year_organization\s+ON nss\.finance_year_closing \(financial_year_pk, organization_pk\) WHERE is_active = TRUE", DDL)


def test_the_service_names_the_table_and_columns_the_ddl_creates():
    sql = (ROOT / "api/services/finance_year_closing.py").read_text(encoding="utf-8")
    assert "nss.finance_year_closing" in sql
    for column in ("financial_year_pk", "organization_pk", "status", "closed_on", "remarks"):
        assert column in DDL and column in sql


@pytest.mark.parametrize("script", ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"])
def test_every_build_script_creates_the_table_after_the_ones_it_depends_on(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    assert text.index("26_finance_year_closing.sql") > text.index("25_finance_sinking_reimbursement_entry.sql")


@pytest.mark.parametrize("script", ["database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"])
def test_both_validate_scripts_check_it(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    assert text.count("finance_year_closing") >= 2


def test_it_is_on_the_live_feed():
    assert '"finance_year_closing"' in (ROOT / "api/routers/live.py").read_text(encoding="utf-8")
    assert "'finance_year_closing'" in (ROOT / "database/ddl/12_live_refresh/02_live_change_triggers.sql").read_text(encoding="utf-8")


# ── the routes and the wiring in finance.py ───────────────────────────────────────────────────────────────────────────────────────────────────────
class TestRoutes:
    def test_two_routes_behind_the_finance_permissions(self):
        from api.routers import finance as F
        from api.routers.finance_closing import router

        got = {(m, r.path): [d.call for d in r.dependant.dependencies] for r in router.routes for m in r.methods if m != "HEAD"}
        assert set(got) == {("GET", "/api/v1/finance/years/{year_pk}/closings"), ("POST", "/api/v1/finance/years/{year_pk}/closings")}
        assert F._VIEW in got[("GET", "/api/v1/finance/years/{year_pk}/closings")] and F._MANAGE in got[("POST", "/api/v1/finance/years/{year_pk}/closings")]

    def test_the_app_serves_them_once_each(self):
        from api.main import app

        served = [(m, r.path) for r in app.routes for m in getattr(r, "methods", ()) if m != "HEAD" and getattr(r, "path", "").endswith("/closings")]
        assert len(served) == 2 and len(set(served)) == 2

    def test_the_write_is_audited_does_not_commit_and_only_a_finance_administrator_of_the_sangha_may(self):
        text = (ROOT / "api/routers/finance_closing.py").read_text(encoding="utf-8")
        assert text.count("F._audit(") == 1 and ".commit()" not in text
        post = inspect.getsource(__import__("api.routers.finance_closing", fromlist=["x"]).close_a_sangha_year)
        assert "F._require_finance_admin(cur, user, " in post and "F._require_org_access(cur, user, org," in post
        assert post.index("F._require_org_access") < post.index("C.check_step") < post.index("C.set_status")

    def test_closing_names_what_is_unfinished_and_the_last_sangha_closes_the_year_through_the_one_implementation(self):
        from api.routers import finance_closing as R

        post = inspect.getsource(R.close_a_sangha_year)
        assert "F._open_work_blockers(cur, year_pk=year_pk, organization_pk=org)" in post
        assert 'F.apply_year_status(cur, user, year, "CLOSED"' in post and "C.everyone_closed(" in post
        from api.routers import finance as F

        assert "apply_year_status(" in inspect.getsource(F.transition_year)

    def test_the_year_check_is_the_one_in_finance_py_and_it_closes_the_finished_sanghas_with_the_year(self):
        from api.routers import finance as F

        check = inspect.getsource(F.close_year_check)
        assert "closing_service.plan_year_close(" in check and "every Sakha and the Kendra must close its own books first" in check
        apply = inspect.getsource(F.apply_year_status)
        assert "closing_service.set_status(" in apply and "closed their books with the year" in apply


class TestEntriesAreRefusedForAClosingSangha:
    def test_the_check_is_called_by_every_way_in(self):
        from api.routers import finance as F

        assert "check_sangha_year_open(cur, body.financial_year_pk, scope[\"organization_pk\"], new=True)" in inspect.getsource(F.create_transaction)
        assert "check_sangha_year_open(cur, year_pk, scope[\"organization_pk\"], new=False)" in inspect.getsource(F._check_transaction)      # submit / approve / post
        assert "new=True" in inspect.getsource(F.create_transfer) and "new=False" in inspect.getsource(F._check_transfer)

    def test_the_check_refuses_by_state_and_a_scope_of_no_sangha_is_never_bound(self, monkeypatch):
        from api.routers import finance as F

        class Cur:
            def execute(self, *_a, **_k):
                pass

            def fetchone(self):
                return ("Ekamra Sakha", "2026-27")

        original = C.status_of
        for state, new, refused in ((C.OPEN, True, False), (C.CLOSING, True, True), (C.CLOSING, False, False), (C.CLOSED, True, True), (C.CLOSED, False, True)):
            monkeypatch.setattr(F.closing_service, "status_of", lambda cur, y, o, s=state: s)
            if refused:
                with pytest.raises(HTTPException) as e:
                    F.check_sangha_year_open(Cur(), "y", "o", new=new)
                assert e.value.status_code == 422 and "Ekamra Sakha" in e.value.detail
            else:
                F.check_sangha_year_open(Cur(), "y", "o", new=new)
        assert original(Cur(), "y", None) == C.OPEN                                              # no Sangha: nothing to close


# ── ALL in-progress work must be finished before a year closes (owner 2026-11-25) ───────────────────────────────────────────────────────────────────
class TestAllInProgressWorkBlocksTheClose:
    def test_each_kind_of_work_counts(self):
        row = {"unfinished_transactions": 0, "unfinished_transfers": 0, "unfinished_receipts": 0, "unfinished_payments": 0, "unfinished_online_payments": 0}
        assert C.unfinished_total(row) == 0
        for key in row:
            assert C.unfinished_total({**row, key: 2}) == 2, key
        assert C.unfinished_total({"unfinished_transactions": 1, "unfinished_receipts": 2, "unfinished_payments": 3, "unfinished_online_payments": 4}) == 10
        assert C.unfinished_total({}) == 0

    def test_a_sangha_with_only_a_draft_receipt_a_payment_or_an_online_payment_in_flight_still_blocks_the_year(self):
        base = {"organization_pk": "p", "organization_name": "Utkal Sakha", "status": C.OPEN, "unfinished_transactions": 0, "unfinished_transfers": 0,
                "unfinished_receipts": 0, "unfinished_payments": 0, "unfinished_online_payments": 0}
        for key in ("unfinished_receipts", "unfinished_payments", "unfinished_online_payments"):
            plan = C.plan_year_close([{**base, key: 1}], [])
            assert [s["organization_name"] for s in plan["blocking"]] == ["Utkal Sakha"] and plan["closable"] == [], key
        assert C.plan_year_close([base], [])["closable"] == [base]                                      # nothing in progress: closed with the year

    def test_the_statuses_that_count_as_unfinished(self):
        assert C.UNFINISHED_RECEIPT_STATUSES == ("DRAFT",)                                                # ISSUED and CANCELLED are done
        assert C.UNFINISHED_PAYMENT_STATUSES == ("DRAFT", "APPROVED", "INITIATED")                        # COMPLETED and CANCELLED are done
        assert set(C.UNFINISHED_RECEIPT_STATUSES) <= set(S.RECEIPT_STATUSES) and set(C.UNFINISHED_PAYMENT_STATUSES) <= set(S.PAYMENT_STATUSES)
        assert set(C.UNFINISHED_TRANSACTION_STATUSES) < set(S.TRANSACTION_STATUSES) and set(C.UNFINISHED_TRANSFER_STATUSES) < set(S.TRANSFER_STATUSES)
        assert "'CREATED', 'PENDING'" in C.UNFINISHED_ONLINE_PAYMENT_SQL and "u.expires_at > NOW()" in C.UNFINISHED_ONLINE_PAYMENT_SQL
        assert "u.status = 'PAID' AND u.financial_transaction_pk IS NULL" in C.UNFINISHED_ONLINE_PAYMENT_SQL        # paid but not booked

    def test_the_one_definition_is_what_every_query_uses(self):
        from api.routers import finance as F

        blockers = inspect.getsource(F._open_work_blockers)
        for name in ("UNFINISHED_TRANSACTION_STATUSES", "UNFINISHED_TRANSFER_STATUSES", "UNFINISHED_RECEIPT_STATUSES", "UNFINISHED_PAYMENT_STATUSES",
                     "UNFINISHED_ONLINE_PAYMENT_SQL"):
            assert f"closing_service.{name}" in blockers, name
        for fn in (C.sanghas_of_year, C.global_unfinished):
            src = inspect.getsource(fn)
            assert "UNFINISHED_ONLINE_PAYMENT_SQL" in src and "UNFINISHED_RECEIPT_STATUSES" in src and "UNFINISHED_PAYMENT_STATUSES" in src, fn.__name__
        assert "'DRAFT','PENDING_APPROVAL','APPROVED'" not in blockers                                  # no second list

    def test_closing_a_scope_a_sangha_and_the_year_all_name_every_kind(self):
        from api.routers import finance as F

        src = inspect.getsource(F._open_work_blockers)
        for noun in ("transaction", "transfer", "receipt", "payment", "online payment"):
            assert f'line("{noun}"' in src, noun
        for fn in (F.close_year_check, F.transition_scope):
            assert "_open_work_blockers(" in inspect.getsource(fn), fn.__name__

    def test_the_card_and_the_model_carry_the_new_counts(self):
        for field in ("unfinished_receipts", "unfinished_payments", "unfinished_online_payments"):
            assert field in S.YearClosingRow.model_fields and S.YearClosingRow.model_fields[field].default == 0


# ── one Sangha's closing does not wait for another's, except through a transfer between them (owner 2026-11-25) ─────────────────────────────────────
class TestOneSanghaDoesNotWaitForAnother:
    """Owner 2026-11-25: "the Kendra's closing should not depend on the Sakha's closing unless they have a mutual transaction"."""

    def test_a_sangha_closes_on_its_own_work_only_the_router_never_looks_at_the_others(self):
        from api.routers import finance_closing as R

        post = inspect.getsource(R.close_a_sangha_year)
        assert "F._open_work_blockers(cur, year_pk=year_pk, organization_pk=org)" in post
        # the other Sanghas are looked at ONLY to decide whether the YEAR may now close by itself, never to let this Sangha close
        closing_branch = post[post.index("if body.status == C.CLOSED:"):post.index("remarks = F._clean(body.remarks)")]
        assert "sanghas_of_year" not in closing_branch and "everyone_closed" not in closing_branch
        assert "C.everyone_closed(" in post[post.index("sanghas = C.sanghas_of_year"):]

    def test_the_only_thing_two_sanghas_share_is_a_transfer_between_their_scopes(self):
        from api.routers import finance as F

        src = inspect.getsource(F._open_work_blockers)
        # a Sangha's entries: its OWN scopes (organization_pk on the scope of the entry)
        assert '"ft.financial_year_pk = %s AND fs.organization_pk = %s"' in src
        # a transfer counts for BOTH ends: the Sangha owning the source scope or the one owning the destination scope
        assert '(fs.organization_pk = %s OR fd.organization_pk = %s)' in src
        # ... and is shown "source scope -> destination scope" so both can see what it is
        assert "fs.scope_code || ' -> ' || fd.scope_code" in src
        # receipts, payments and online payments are entries of the Sangha that owns the scope, nobody else's
        assert src.count("fs.organization_pk = %s") >= 2

    def test_the_sangha_listing_counts_a_shared_transfer_for_each_end_once(self):
        src = inspect.getsource(C.sanghas_of_year)
        assert "SELECT DISTINCT tr.financial_transfer_pk, fs.organization_pk, tr.status" in src          # once per Sangha, even when both scopes are its own
        assert "fs.financial_scope_pk IN (tr.source_scope_pk, tr.destination_scope_pk)" in src            # ... and for BOTH ends of the transfer

    def test_a_year_check_does_not_make_one_sangha_wait_for_another(self):
        # the year waits for everyone; a Sangha does not: a Sangha with nothing unfinished is "closable" whatever the others are doing
        kendra = _sangha("Kendra")
        sakha = _sangha("Ekamra Sakha", tx=3)
        plan = C.plan_year_close([kendra, sakha], [])
        assert [s["organization_name"] for s in plan["closable"]] == ["Kendra"] and [s["organization_name"] for s in plan["blocking"]] == ["Ekamra Sakha"]
        assert C.unfinished_total(kendra) == 0                                                           # the Kendra's own work is what decides its closing
