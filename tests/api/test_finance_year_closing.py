"""
Closing the financial year Sakha by Sakha and Kendra (owner request 2026-11-25) through the API.

The year stays one calendar record the NSS-wide authority opens and closes; on top of it each Sangha closes ITS OWN books: OPEN -> CLOSING (no new
entries, finish what is in progress) -> CLOSED (nothing unfinished). Its own finance administrators do it. The year closes only when every Sangha with
activity has closed: the NSS-wide "Close" closes the finished ones along with it and names the others; the last Sangha to close closes a CLOSING year.

Real integration tests (nothing mocked); NEVER RUN against a database when this file was written. The DB-free parts are in
tests/api/test_finance_year_closing_service.py.
"""
import itertools

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    admin_h,
    admin_user,
    make_scope,
    make_txn,
    move,
    new_year,
    other_admin,
    other_admin_h,
    other_org_pk,
    post_txn,
    raw_move,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    kendra_admin,
    kendra_h,
    single_approval_levels,
    viewer_h,
    viewer_user,
)

pytestmark = pytest.mark.usefixtures("single_approval_levels")        # the Sakha approval chain is tested elsewhere; here an approver moves entries

# Each test opens a year of its own, in rising order: a new record is made in the CURRENT year (the latest OPEN one), so a later year must be later.
_years = itertools.count(2110)


def _open_year(client, h) -> dict:
    for _ in range(40):
        year = new_year(client, h, next(_years))
        if year is not None:
            return move(client, h, "years", year["financial_year_pk"], "OPEN")
    raise AssertionError("no free financial year")


def _sakha_with_a_draft(client, h, org_pk):
    year = _open_year(client, h)
    scope = make_scope(client, h, org_pk, activate_with=h)
    return year, scope, make_txn(client, h, year, scope, kind="INCOME")


def _closings(client, h, year):
    r = client.get(f"{BASE}/years/{year['financial_year_pk']}/closings", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _step(client, h, year, org_pk, status, expect=200):
    r = client.post(f"{BASE}/years/{year['financial_year_pk']}/closings", json={"organization_pk": str(org_pk), "status": status}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _mine(listing, org_pk):
    return next(i for i in listing["items"] if i["organization_pk"] == str(org_pk))


class TestASakhaClosesItsOwnBooks:
    def test_the_two_steps_and_what_each_allows(self, client, admin_h, sakha_admin_h, register_org_pk):
        year, scope, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        row = _mine(_closings(client, sakha_admin_h, year), register_org_pk)
        assert row["status"] == "OPEN" and row["unfinished_transactions"] >= 1 and row["can_act"] is True and row["next_status"] == "CLOSING"
        assert _step(client, sakha_admin_h, year, register_org_pk, "CLOSING")["status"] == "CLOSING"
        r = client.post(f"{BASE}/transactions", json={**{k: txn[k] for k in ("financial_year_pk", "financial_scope_pk", "transaction_type", "finance_head_pk", "transaction_date")},
                                                      "amount": "5.00"}, headers=admin_h)
        assert r.status_code == 422 and "started closing" in r.text                                       # no NEW entry once it is closing
        refused = _step(client, sakha_admin_h, year, register_org_pk, "CLOSED", expect=422)
        assert txn["transaction_reference"] in str(refused)                                              # the entry in the way is named
        assert post_txn(client, admin_h, txn)["status"] == "POSTED"                                      # ... and what is in progress can still be finished
        done = _step(client, sakha_admin_h, year, register_org_pk, "CLOSED")
        assert done["status"] == "CLOSED" and done["closed_on"] and done["can_act"] is False

    def test_a_closed_sangha_takes_nothing_in_that_year(self, client, admin_h, sakha_admin_h, register_org_pk):
        year, scope, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        post_txn(client, admin_h, txn)
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSING")
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSED")
        body = {"financial_year_pk": year["financial_year_pk"], "financial_scope_pk": scope["financial_scope_pk"], "transaction_type": "INCOME",
                "finance_head_pk": txn["finance_head_pk"], "amount": "5.00", "transaction_date": txn["transaction_date"]}
        r = client.post(f"{BASE}/transactions", json=body, headers=admin_h)
        assert r.status_code == 422 and "closed its books" in r.text

    def test_the_steps_cannot_be_skipped_or_repeated(self, client, admin_h, sakha_admin_h, register_org_pk):
        year, _, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        post_txn(client, admin_h, txn)
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSED", expect=422)                         # OPEN -> CLOSED is not a step
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSING")
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSING", expect=422)
        _step(client, sakha_admin_h, year, register_org_pk, "OPEN", expect=422)


class TestWhoMayClose:
    def test_only_that_sangha_finance_administrators_and_the_super_administrator(self, client, admin_h, sakha_admin_h, other_admin_h, viewer_h, register_org_pk):
        year, _, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        _step(client, other_admin_h, year, register_org_pk, "CLOSING", expect=403)                       # another Sakha's finance administrator
        _step(client, viewer_h, year, register_org_pk, "CLOSING", expect=403)                            # view only
        assert _mine(_closings(client, sakha_admin_h, year), register_org_pk)["can_act"] is True
        theirs = _closings(client, other_admin_h, year)
        assert str(register_org_pk) not in [i["organization_pk"] for i in theirs["items"]]                # another Sakha does not see this one's row
        assert _step(client, admin_h, year, register_org_pk, "CLOSING")["status"] == "CLOSING"            # the super administrator can for any Sangha

    def test_a_year_that_is_not_open_or_closing_cannot_be_closed_into(self, client, admin_h, sakha_admin_h, register_org_pk):
        planned = new_year(client, admin_h, next(_years))
        _step(client, sakha_admin_h, planned, register_org_pk, "CLOSING", expect=422)


class TestTheYear:
    def test_the_nss_wide_close_names_each_sangha_that_has_not_finished(self, client, admin_h, register_org_pk):
        year, scope, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        move(client, admin_h, "years", year["financial_year_pk"], "CLOSING")
        r = raw_move(client, admin_h, "years", year["financial_year_pk"], "CLOSED")
        assert r.status_code == 422 and "every Sakha and the Kendra must close its own books first" in r.text
        assert txn["transaction_reference"] in r.text

    def test_the_nss_wide_close_closes_the_finished_sanghas_with_the_year(self, client, admin_h, register_org_pk):
        year, scope, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        post_txn(client, admin_h, txn)
        move(client, admin_h, "years", year["financial_year_pk"], "CLOSING")
        assert move(client, admin_h, "years", year["financial_year_pk"], "CLOSED")["status"] == "CLOSED"
        assert _mine(_closings(client, admin_h, year), register_org_pk)["status"] == "CLOSED"

    def test_the_last_sangha_to_close_closes_a_closing_year_by_itself(self, client, admin_h, sakha_admin_h, register_org_pk):
        year, scope, txn = _sakha_with_a_draft(client, admin_h, register_org_pk)
        post_txn(client, admin_h, txn)
        move(client, admin_h, "years", year["financial_year_pk"], "CLOSING")
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSING")
        done = _step(client, sakha_admin_h, year, register_org_pk, "CLOSED")
        listed = client.get(f"{BASE}/years", headers=admin_h).json()["items"]
        closed = next(y for y in listed if y["financial_year_pk"] == year["financial_year_pk"])["status"] == "CLOSED"
        assert closed == done["year_closed"]
        if not done["year_closed"]:                                      # other Sanghas with activity in this year may still be open (a shared database)
            assert any(i["status"] != "CLOSED" for i in _closings(client, admin_h, year)["items"])


class TestAllInProgressWorkMustBeFinished:
    """Owner 2026-11-25: "all in-progress work for the FY should be finished before the FY is closed" - not only transactions and transfers."""

    def test_a_draft_receipt_and_an_unfinished_payment_block_the_sangha_and_are_named(self, client, admin_h, sakha_admin_h, register_org_pk):
        year, scope, _ = _sakha_with_a_draft(client, admin_h, register_org_pk)
        income = post_txn(client, admin_h, make_txn(client, admin_h, year, scope, kind="INCOME", amount="100.00"))
        expense = post_txn(client, admin_h, make_txn(client, admin_h, year, scope, kind="EXPENSE", amount="40.00"))
        receipt = client.post(f"{BASE}/transactions/{income['financial_transaction_pk']}/receipts", json={"receipt_date": year["start_date"], "amount": "100.00"}, headers=admin_h)
        payment = client.post(f"{BASE}/transactions/{expense['financial_transaction_pk']}/payments", json={"payment_date": year["start_date"], "amount": "40.00"}, headers=admin_h)
        assert receipt.status_code == 201 and payment.status_code == 201, (receipt.text, payment.text)
        row = _mine(_closings(client, sakha_admin_h, year), register_org_pk)
        assert row["unfinished_receipts"] == 1 and row["unfinished_payments"] == 1
        _step(client, sakha_admin_h, year, register_org_pk, "CLOSING")
        refused = _step(client, sakha_admin_h, year, register_org_pk, "CLOSED", expect=422)
        text = str(refused)
        assert receipt.json()["receipt_number"] in text and payment.json()["payment_reference"] in text            # each piece of work is named
        r = client.post(f"{BASE}/years/{year['financial_year_pk']}/transition", json={"status": "CLOSING"}, headers=admin_h)
        assert r.status_code == 200
        year_refused = raw_move(client, admin_h, "years", year["financial_year_pk"], "CLOSED")
        assert year_refused.status_code == 422 and receipt.json()["receipt_number"] in year_refused.text            # ... and so does the year


class TestTheKendraDoesNotWaitForTheSakhas:
    """Owner 2026-11-25: "the Kendra's closing should not depend on the Sakha's closing unless they have a mutual transaction"."""

    def _kendra(self, write_conn):
        from tests.reparent_support import kendra_pks

        return kendra_pks(write_conn)[0]

    def test_the_kendra_closes_while_a_sakha_still_has_unfinished_work(self, client, admin_h, kendra_h, register_org_pk, write_conn):
        kendra = self._kendra(write_conn)
        year = _open_year(client, admin_h)
        sakha_scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h)
        make_txn(client, admin_h, year, sakha_scope, kind="INCOME")                                      # the Sakha leaves a DRAFT behind
        kendra_scope = make_scope(client, admin_h, kendra, activate_with=admin_h)
        post_txn(client, admin_h, make_txn(client, admin_h, year, kendra_scope, kind="INCOME", amount="50.00"))
        _step(client, kendra_h, year, kendra, "CLOSING")
        assert _step(client, kendra_h, year, kendra, "CLOSED")["status"] == "CLOSED"                      # nothing of its own is open: it closes
        sakha = _mine(_closings(client, admin_h, year), register_org_pk)
        assert sakha["status"] == "OPEN" and sakha["unfinished_transactions"] >= 1                         # ... and the Sakha is untouched

    def test_a_transfer_between_them_must_be_finished_before_either_closes(self, client, admin_h, kendra_h, sakha_admin_h, register_org_pk, write_conn):
        kendra = self._kendra(write_conn)
        year = _open_year(client, admin_h)
        kendra_scope = make_scope(client, admin_h, kendra, activate_with=admin_h)
        sakha_scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h)
        r = client.post(f"{BASE}/transfers", json={"financial_year_pk": year["financial_year_pk"], "source_scope_pk": kendra_scope["financial_scope_pk"],
                                                   "destination_scope_pk": sakha_scope["financial_scope_pk"], "amount": "10.00",
                                                   "transfer_date": year["start_date"], "purpose": "Grant to the Sakha"}, headers=admin_h)
        assert r.status_code == 201, r.text
        transfer = r.json()
        for headers, org in ((kendra_h, kendra), (sakha_admin_h, register_org_pk)):                         # BOTH ends wait for it
            _step(client, headers, year, org, "CLOSING")
            refused = _step(client, headers, year, org, "CLOSED", expect=422)
            assert transfer["transfer_reference"] in str(refused) and "->" in str(refused)                 # named, source scope -> destination scope
        move(client, admin_h, "transfers", transfer["financial_transfer_pk"], "CANCELLED", remarks="not needed")        # finished (cancelled)
        assert _step(client, kendra_h, year, kendra, "CLOSED")["status"] == "CLOSED"
        assert _step(client, sakha_admin_h, year, register_org_pk, "CLOSED")["status"] == "CLOSED"
