"""
Sinking Fund reimbursement (Bye-Law C(i)(2)(xviii), FIN-BR-026; owner request 2026-11-24) through the API.

The road: the Kendra spends from a Sakha's Sinking Fund while it has taken over the Sakha's seva / pujas (an ordinary EXPENSE, posted) ->
the expenditure is REGISTERED as a take-over expenditure (the Sakha now owes the amount) -> the Sakha's payments are recorded (ordinary
INCOME entries in the same fund, linked) -> what is POSTED counts as reimbursed, what is still in progress is reserved.

Real integration tests (nothing mocked); NEVER RUN against a database when this file was written. The DB-free parts are in
tests/api/test_finance_sinking_service.py.
"""
import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    admin_h,
    admin_user,
    make_fund,
    make_scope,
    make_txn,
    make_year,
    other_admin_h,
    plain_sakha_admin_h,
    post_txn,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    viewer_h,
    viewer_user,
)
from tests.reparent_support import kendra_pks

URL = f"{BASE}/sinking-reimbursements"


@pytest.fixture(scope="module")
def kendra_org_pk(write_conn):
    return kendra_pks(write_conn)[0]


def _spend(client, h, kendra_org_pk, sakha_pk, *, amount="1000.00", post=True, fund_type="SINKING_FUND"):
    """A Kendra expense from a fund (the Sakha's Sinking Fund by default); posted unless told not to."""
    year = make_year(client, h)
    scope = make_scope(client, h, kendra_org_pk, activate_with=h)
    extra = {"organization_pk": str(sakha_pk)} if fund_type == "SINKING_FUND" else {}
    fund = make_fund(client, h, scope["financial_scope_pk"], activate_with=h, fund_type=fund_type, **extra)
    txn = make_txn(client, h, year, scope, fund=fund, kind="EXPENSE", amount=amount)
    return (post_txn(client, h, txn) if post else txn), fund, scope


def _register(client, h, txn, *, expect=201, reason="The Kendra took over the daily puja", **over):
    r = client.post(URL, json={"expenditure_transaction_pk": txn["financial_transaction_pk"], "takeover_reason": reason, **over}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _pay(client, h, pk, amount, *, expect=201):
    r = client.post(f"{URL}/{pk}/reimbursements", json={"amount": str(amount)}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


class TestTheRoad:
    def test_register_then_reimburse_in_parts_until_it_is_settled(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, fund, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk, amount="1000.00")
        owed = _register(client, admin_h, txn, resolution_reference="GB/2026/31")
        pk = owed["finance_sinking_reimbursement_pk"]
        assert owed["reimbursement_reference"].startswith("SRB") and owed["status"] == "OPEN"
        assert owed["amount_due"] == "1000.00" and owed["outstanding_amount"] == "1000.00" and owed["reimbursements"] == []
        assert owed["sakha_organization_pk"] == str(register_org_pk) and owed["resolution_reference"] == "GB/2026/31"
        first = _pay(client, admin_h, pk, "400.00")
        assert len(first["reimbursements"]) == 1 and first["reimbursements"][0]["status"] == "DRAFT"
        assert first["reimbursed_amount"] == "0.00" or first["reimbursed_amount"] == "0"       # recorded, not posted: nothing counts yet
        assert first["pending_amount"] in ("400.00", "400") and first["status"] == "OPEN"
        post_txn(client, admin_h, {"financial_transaction_pk": first["reimbursements"][0]["financial_transaction_pk"]})
        part = client.get(f"{URL}/{pk}", headers=admin_h).json()
        assert part["status"] == "PARTLY_REIMBURSED" and float(part["reimbursed_amount"]) == 400 and float(part["outstanding_amount"]) == 600
        second = _pay(client, admin_h, pk, "600.00")
        post_txn(client, admin_h, {"financial_transaction_pk": second["reimbursements"][-1]["financial_transaction_pk"]})
        done = client.get(f"{URL}/{pk}", headers=admin_h).json()
        assert done["status"] == "REIMBURSED" and float(done["outstanding_amount"]) == 0 and done["next_step"] is None
        _pay(client, admin_h, pk, "1.00", expect=422)                                               # nothing more is owed

    def test_it_appears_in_the_list_and_the_filters(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk, amount="250.00")
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        listed = client.get(URL, params={"organization_pk": str(register_org_pk), "status": "OPEN"}, headers=admin_h).json()
        assert pk in [i["finance_sinking_reimbursement_pk"] for i in listed["items"]]
        assert client.get(URL, params={"status": "NOPE"}, headers=admin_h).status_code == 422
        offered = client.get(f"{URL}/expenditures", headers=admin_h).json()["items"]
        assert txn["financial_transaction_pk"] not in [o["financial_transaction_pk"] for o in offered]      # registered: no longer offered

    def test_the_kendras_page_adds_up_sakha_by_sakha(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk, amount="400.00")
        before = {s["sakha_organization_pk"]: s for s in client.get(f"{URL}/summary", headers=admin_h).json()["items"]}[str(register_org_pk)]
        assert before["unregistered_count"] >= 1
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        after = {s["sakha_organization_pk"]: s for s in client.get(f"{URL}/summary", headers=admin_h).json()["items"]}[str(register_org_pk)]
        assert after["unregistered_count"] == before["unregistered_count"] - 1
        assert float(after["owed_amount"]) == float(before["owed_amount"]) + 400 and after["registered_count"] == before["registered_count"] + 1
        assert pk

    def test_an_unregistered_expenditure_is_offered(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk)
        offered = client.get(f"{URL}/expenditures", headers=admin_h).json()["items"]
        assert txn["financial_transaction_pk"] in [o["financial_transaction_pk"] for o in offered]


class TestWhatCanBeRegistered:
    def test_only_a_posted_sinking_fund_expense_can_be_registered(self, client, admin_h, kendra_org_pk, register_org_pk):
        draft, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk, post=False)
        _register(client, admin_h, draft, expect=422)                                              # not posted yet
        general, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk, fund_type="GENERAL")
        _register(client, admin_h, general, expect=422)                                            # not a Sinking Fund

    def test_a_reason_is_required_and_it_cannot_be_registered_twice(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk)
        _register(client, admin_h, txn, expect=422, reason="   ")
        _register(client, admin_h, txn)
        _register(client, admin_h, txn, expect=409)


class TestWhatCanBeRecorded:
    def test_no_more_than_is_owed_counting_what_is_already_on_its_way(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk, amount="500.00")
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        _pay(client, admin_h, pk, "501.00", expect=422)
        _pay(client, admin_h, pk, "300.00")                                                         # DRAFT: reserved, not yet reimbursed
        _pay(client, admin_h, pk, "201.00", expect=422)                                             # only 200 is left to record
        _pay(client, admin_h, pk, "200.00")

    def test_a_removed_registration_frees_the_expenditure_but_not_once_money_came_back(self, client, admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk)
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        assert client.delete(f"{URL}/{pk}", headers=admin_h).status_code == 422                     # a reason is required
        assert client.delete(f"{URL}/{pk}", params={"reason": "wrong expenditure"}, headers=admin_h).status_code == 200
        assert client.get(f"{URL}/{pk}", headers=admin_h).status_code == 404
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]                    # it can be registered again
        _pay(client, admin_h, pk, "100.00")
        assert client.delete(f"{URL}/{pk}", params={"reason": "too late"}, headers=admin_h).status_code == 422


class TestWhoMayAct:
    def test_a_viewer_reads_but_cannot_write(self, client, admin_h, viewer_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk)
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        assert client.post(URL, json={"expenditure_transaction_pk": txn["financial_transaction_pk"], "takeover_reason": "x"}, headers=viewer_h).status_code == 403
        assert client.post(f"{URL}/{pk}/reimbursements", json={"amount": "1.00"}, headers=viewer_h).status_code == 403
        assert client.delete(f"{URL}/{pk}", params={"reason": "x"}, headers=viewer_h).status_code == 403

    def test_a_sakha_admin_outside_the_kendra_scope_sees_nothing(self, client, admin_h, plain_sakha_admin_h, kendra_org_pk, register_org_pk):
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk)
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        listed = client.get(URL, headers=plain_sakha_admin_h)
        assert listed.status_code in (200, 403) and (listed.status_code == 403 or pk not in [i["finance_sinking_reimbursement_pk"] for i in listed.json()["items"]])
        assert client.get(f"{URL}/{pk}", headers=plain_sakha_admin_h).status_code in (403, 404)

    def test_a_sakhas_admin_or_office_bearer_sees_nothing_of_it(self, client, admin_h, sakha_admin_h, other_admin_h, kendra_org_pk, register_org_pk):
        """Owner 2026-11-24: the Sinking Fund dues are the Kendra's procedure - even the Sakha that owes does not see them."""
        txn, _, _ = _spend(client, admin_h, kendra_org_pk, register_org_pk)
        pk = _register(client, admin_h, txn)["finance_sinking_reimbursement_pk"]
        for headers in (sakha_admin_h, other_admin_h):
            listed = client.get(URL, headers=headers)
            assert listed.status_code in (200, 403)
            if listed.status_code == 200:
                assert pk not in [i["finance_sinking_reimbursement_pk"] for i in listed.json()["items"]]
            summary = client.get(f"{URL}/summary", headers=headers)
            assert summary.status_code in (200, 403)
            if summary.status_code == 200:
                assert str(register_org_pk) not in [i["sakha_organization_pk"] for i in summary.json()["items"]]
            assert client.get(f"{URL}/{pk}", headers=headers).status_code in (403, 404)
            assert client.post(f"{URL}/{pk}/reimbursements", json={"amount": "1.00"}, headers=headers).status_code in (403, 404)
            assert client.delete(f"{URL}/{pk}", params={"reason": "x"}, headers=headers).status_code in (403, 404)
        offered = client.get(f"{BASE}/reference", headers=sakha_admin_h)
        assert offered.status_code == 200 and offered.json()["kendra_side"] is False
        assert client.get(f"{BASE}/reference", headers=admin_h).json()["kendra_side"] is True

    def test_the_login_is_needed(self, client):
        assert client.get(URL).status_code in (401, 403)
