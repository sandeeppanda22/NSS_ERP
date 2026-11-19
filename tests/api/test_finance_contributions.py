"""
Finance contributions (owner decision 2026-11-15): the simple "add a contribution" form, a Kendra head that every Sakha receives
as its own copy, and the member's contribution cards with paid / due. Real integration tests (nothing mocked; the MOCK gateway
is the project's own adapter): they need the Phase 11i DDL AND ddl/14_finance/14_finance_head_fixed_amount_patch.sql applied.

The register Sakha / the other Sakha are shared by the whole module, so every test that depends on WHICH account a copy collects
into creates its own default account first (the newest default is the one a new copy is linked to).
"""

from uuid import uuid4

import pytest

from api.services import finance_contribution as FC
from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    _login_headers,
    admin_h,
    admin_user,
    ensure_open_year_covering_today,
    kendra_admin,
    kendra_h,
    make_account,
    mock_gateway,
    new_member,
    other_admin,
    other_admin_h,
    other_org_pk,
    pay_request,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    upi_world,
)


@pytest.fixture
def plain_member(write_conn, register_org_pk):
    """A FRESH member per test: the per-member cap on unpaid requests and the paid totals must not carry over."""
    return new_member(write_conn, register_org_pk, "FinCon")


@pytest.fixture
def plain_member_h(client, plain_member):
    return _login_headers(client, plain_member["sangha_sevi_id"], plain_member["password"])


@pytest.fixture(autouse=True)
def _a_financial_year_covers_today(write_conn):
    ensure_open_year_covering_today(write_conn)


def _kendra_pk(write_conn) -> str:
    from tests.reparent_support import kendra_pks

    return kendra_pks(write_conn)[0]


def contribution(client, headers, org_pk, expect=201, **over) -> dict:
    body = {"organization_pk": str(org_pk), "head_name": f"Contribution {uuid4().hex[:6]}"}
    body.update(over)
    r = client.post(f"{BASE}/contributions", json=body, headers=headers)
    assert r.status_code == expect, r.text
    return r.json()


def head(client, headers, pk) -> dict:
    r = client.get(f"{BASE}/heads/{pk}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def copy_in(client, headers, source_pk, org_pk) -> dict:
    """The Sakha's own copy of a Kendra head (found through the Sakha's heads list)."""
    items = client.get(f"{BASE}/heads", params={"organization_pk": str(org_pk), "page_size": 200, "with_templates": "false"}, headers=headers).json()["items"]
    found = [h for h in items if h["template_head_pk"] == source_pk]
    assert len(found) == 1, (source_pk, [h["head_code"] for h in items])
    return found[0]


def card(client, headers, head_pk) -> dict:
    cards = {c["finance_head_pk"]: c for c in client.get(f"{BASE}/my-pranami/heads", headers=headers).json()}
    assert head_pk in cards, "the member is not offered this contribution"
    return cards[head_pk]


def audit_rows(write_conn, table, pk) -> list[tuple]:
    cur = write_conn.cursor()
    cur.execute("SELECT action, summary FROM nss.system_event_log WHERE table_name = %s AND record_pk::text = %s", (table, str(pk)))
    return cur.fetchall()


def member_pays(client, admin_h, mock_gateway, member_h, head_pk, amount) -> dict:
    """Start a payment as the member, then simulate the bank confirming it (the signed webhook)."""
    r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": head_pk, "amount": amount}, headers=member_h)
    assert r.status_code == 201, r.text
    full = client.get(f"{BASE}/payment-requests/{r.json()['upi_payment_request_pk']}", headers=admin_h).json()
    assert pay_request(client, mock_gateway, full).status_code == 200
    return client.get(f"{BASE}/payment-requests/{full['upi_payment_request_pk']}", headers=admin_h).json()      # now carries the booked transaction


# ═══════════════════════════════════════════════════════════════════════
# The simple form
# ═══════════════════════════════════════════════════════════════════════

class TestSimpleContribution:
    def test_four_fields_make_a_head_that_collects(self, client, admin_h, register_org_pk, mock_gateway):
        account = make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        r = contribution(client, admin_h, register_org_pk, head_name="Annual Pranami", fixed_amount="500", due_period="YEARLY")
        h = r["head"]
        assert r["needs_account"] is False and r["copies_created"] == 0
        assert (h["direction"], h["is_pranami"], h["allow_upi"], h["applies_to_all_sakhas"]) == ("INCOME", True, True, False)
        assert (h["fixed_amount"], h["due_period"], h["allow_part_payment"]) == ("500.00", "YEARLY", False)
        assert h["collection_account_pk"] == account["financial_account_pk"] and h["collection_scope_pk"]
        assert h["head_code"].startswith("CONTRIB_")                               # the code is the server's business

    def test_a_free_amount_contribution_needs_no_amount_or_period(self, client, admin_h, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        h = contribution(client, admin_h, register_org_pk, head_name="Donation")["head"]
        assert h["fixed_amount"] is None and h["due_period"] is None

    def test_it_collects_into_the_account_that_was_chosen(self, client, admin_h, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        other = make_account(client, admin_h, register_org_pk, mock_gateway)
        h = contribution(client, admin_h, register_org_pk, collection_account_pk=other["financial_account_pk"])["head"]
        assert h["collection_account_pk"] == other["financial_account_pk"]

    def test_with_no_account_it_is_saved_but_cannot_collect_yet(self, client, admin_h, register_org_pk, monkeypatch):
        monkeypatch.setattr(FC, "default_account", lambda cur, org: None)
        r = contribution(client, admin_h, register_org_pk, fixed_amount="100", due_period="MONTHLY")
        assert r["needs_account"] is True and r["head"]["allow_upi"] is False and r["head"]["collection_account_pk"] is None

    @pytest.mark.parametrize("over", [
        {"fixed_amount": "500"},                                          # an amount needs a period
        {"due_period": "YEARLY"},                                         # a period needs an amount
        {"allow_part_payment": True},                                     # part payment needs an amount
        {"fixed_amount": "0", "due_period": "YEARLY"},
        {"fixed_amount": "-5", "due_period": "YEARLY"},
        {"fixed_amount": "5", "due_period": "WEEKLY"},
        {"applies_to": "EVERYONE"},
        {"head_name": "   "},
    ])
    def test_bad_input_is_refused(self, client, admin_h, register_org_pk, over):
        contribution(client, admin_h, register_org_pk, expect=422, **over)

    def test_all_sakhas_is_for_the_kendra_only(self, client, admin_h, register_org_pk):
        contribution(client, admin_h, register_org_pk, expect=422, applies_to="ALL_SAKHAS")

    def test_only_an_administrator_with_scope_over_the_sangha_may_add_one(self, client, admin_h, kendra_h, register_org_pk, sakha_admin_h, other_admin_h, plain_member_h):
        # Configuring is FINANCE_CONFIGURE (owner 2026-11-17), which a Sakha admin holds for ITS OWN Sakha only.
        for headers in (other_admin_h, plain_member_h):                            # a foreign Sakha's admin / no permission
            contribution(client, headers, register_org_pk, expect=403)
        contribution(client, sakha_admin_h, register_org_pk)
        contribution(client, kendra_h, register_org_pk)

    def test_the_creation_is_audited(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        h = contribution(client, admin_h, register_org_pk, fixed_amount="300", due_period="ONE_TIME")["head"]
        assert any(action == "CREATE" for action, _ in audit_rows(write_conn, "finance_head", h["finance_head_pk"]))


# ═══════════════════════════════════════════════════════════════════════
# A Kendra head every Sakha receives
# ═══════════════════════════════════════════════════════════════════════

def _all_sakhas(client, admin_h, write_conn, **over) -> dict:
    return contribution(client, admin_h, _kendra_pk(write_conn), applies_to="ALL_SAKHAS", **{"fixed_amount": "500", "due_period": "YEARLY", **over})


class TestKendraHeadForAllSakhas:
    def test_every_sakha_gets_its_own_copy_and_the_source_collects_nothing(self, client, admin_h, write_conn, register_org_pk, other_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        r = _all_sakhas(client, admin_h, write_conn, head_name="Kendra Pranami")
        source = r["head"]
        assert r["copies_created"] >= 2 and source["applies_to_all_sakhas"] is True and source["allow_upi"] is False
        assert source["collection_account_pk"] is None and source["copy_count"] == r["copies_created"]
        mine = copy_in(client, admin_h, source["finance_head_pk"], register_org_pk)
        theirs = copy_in(client, admin_h, source["finance_head_pk"], other_org_pk)
        assert mine["organization_pk"] == str(register_org_pk) and theirs["organization_pk"] == str(other_org_pk)
        for c in (mine, theirs):
            assert c["is_kendra_copy"] is True and (c["head_name"], c["fixed_amount"], c["due_period"]) == ("Kendra Pranami", "500.00", "YEARLY")
            assert c["head_code"] == source["head_code"] and c["applies_to_all_sakhas"] is False
        assert mine["allow_upi"] is True and mine["needs_account"] is False        # it already had an account: collecting at once

    def test_adding_an_account_never_switches_an_adopted_template_onto_upi(self, client, admin_h, register_org_pk, mock_gateway):
        """Regression: adopted Kendra templates (EXPENSE ones too) carry template_head_pk but are not all-Sakhas copies."""
        adopted = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(register_org_pk)}, headers=admin_h)
        assert adopted.status_code == 200, adopted.text
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)          # used to fail with a CHECK violation
        heads = client.get(f"{BASE}/heads", params={"organization_pk": str(register_org_pk), "page_size": 200, "with_templates": "false"}, headers=admin_h).json()["items"]
        for h in heads:
            if h["template_head_pk"] and not h["is_kendra_copy"]:
                assert h["allow_upi"] is False and h["collection_account_pk"] is None, h["head_code"]

    def test_a_sakha_without_an_account_is_flagged_and_linked_when_it_adds_one(self, client, admin_h, write_conn, register_org_pk, mock_gateway, monkeypatch):
        with monkeypatch.context() as m:
            m.setattr(FC, "default_account", lambda cur, org: None)
            source = _all_sakhas(client, admin_h, write_conn)["head"]
        c = copy_in(client, admin_h, source["finance_head_pk"], register_org_pk)
        assert c["needs_account"] is True and c["allow_upi"] is False
        account = make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)       # the Sakha adds its account
        c = head(client, admin_h, c["finance_head_pk"])
        assert c["needs_account"] is False and c["allow_upi"] is True and c["collection_account_pk"] == account["financial_account_pk"]

    def test_the_kendras_edit_reaches_every_copy(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)["head"]
        r = client.patch(f"{BASE}/heads/{source['finance_head_pk']}", json={"head_name": "Renamed", "fixed_amount": "750", "due_period": "MONTHLY",
                                                                            "allow_part_payment": True}, headers=admin_h)
        assert r.status_code == 200, r.text
        c = copy_in(client, admin_h, source["finance_head_pk"], register_org_pk)
        assert (c["head_name"], c["fixed_amount"], c["due_period"], c["allow_part_payment"]) == ("Renamed", "750.00", "MONTHLY", True)

    def test_a_sakha_may_only_choose_the_account_of_its_copy(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)["head"]
        c = copy_in(client, admin_h, source["finance_head_pk"], register_org_pk)
        for body in ({"head_name": "Mine"}, {"fixed_amount": "1", "due_period": "YEARLY"}, {"allow_part_payment": True}, {"is_pranami": False}, {"display_order": 5}):
            assert client.patch(f"{BASE}/heads/{c['finance_head_pk']}", json=body, headers=admin_h).status_code == 403, body
        second = make_account(client, admin_h, register_org_pk, mock_gateway)
        r = client.patch(f"{BASE}/heads/{c['finance_head_pk']}", json={"collection_account_pk": second["financial_account_pk"]}, headers=admin_h)
        assert r.status_code == 200 and r.json()["collection_account_label"] == second["account_label"]
        # the account must be the Sakha's own
        foreign = make_account(client, admin_h, _kendra_pk(write_conn), mock_gateway)
        assert client.patch(f"{BASE}/heads/{c['finance_head_pk']}", json={"collection_account_pk": foreign["financial_account_pk"]}, headers=admin_h).status_code == 422

    def test_the_source_itself_never_collects(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        source = _all_sakhas(client, admin_h, write_conn)["head"]
        account = make_account(client, admin_h, _kendra_pk(write_conn), mock_gateway)
        r = client.patch(f"{BASE}/heads/{source['finance_head_pk']}", json={"collection_account_pk": account["financial_account_pk"]}, headers=admin_h)
        assert r.status_code == 422

    def test_switching_the_kendra_head_off_and_on_moves_every_copy(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)["head"]
        pk = source["finance_head_pk"]
        assert client.post(f"{BASE}/heads/{pk}/transition", json={"status": "INACTIVE"}, headers=admin_h).status_code == 200
        assert copy_in(client, admin_h, pk, register_org_pk)["status"] == "INACTIVE"
        assert client.post(f"{BASE}/heads/{pk}/transition", json={"status": "ACTIVE"}, headers=admin_h).status_code == 200
        assert copy_in(client, admin_h, pk, register_org_pk)["status"] == "ACTIVE"

    def test_a_sakha_can_switch_its_own_copy_off_without_touching_the_others(self, client, admin_h, write_conn, register_org_pk, other_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)["head"]["finance_head_pk"]
        mine, theirs = copy_in(client, admin_h, source, register_org_pk), copy_in(client, admin_h, source, other_org_pk)
        assert client.post(f"{BASE}/heads/{mine['finance_head_pk']}/transition", json={"status": "INACTIVE"}, headers=admin_h).status_code == 200
        assert head(client, admin_h, mine["finance_head_pk"])["status"] == "INACTIVE" and head(client, admin_h, theirs["finance_head_pk"])["status"] == "ACTIVE"

    def test_syncing_again_creates_nothing_and_every_step_is_audited(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)["head"]
        cur = write_conn.cursor()
        assert FC.sync_copies(cur, None, source["finance_head_pk"]) == {"created": 0, "updated": 0}
        c = copy_in(client, admin_h, source["finance_head_pk"], register_org_pk)
        assert any(a == "CREATE" for a, _ in audit_rows(write_conn, "finance_head", c["finance_head_pk"]))
        assert any(a == "CREATE" for a, _ in audit_rows(write_conn, "finance_head", source["finance_head_pk"]))
        client.post(f"{BASE}/heads/{source['finance_head_pk']}/transition", json={"status": "INACTIVE"}, headers=admin_h)
        assert any(a == "STATUS_CHANGE" for a, _ in audit_rows(write_conn, "finance_head", c["finance_head_pk"]))

    def test_a_new_sakha_receives_the_copy_too(self, client, admin_h, write_conn, register_org_pk, mock_gateway, monkeypatch):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        with monkeypatch.context() as m:                                     # the head exists BEFORE this Sakha does
            m.setattr(FC, "_active_sakhas", lambda cur: [])
            r = _all_sakhas(client, admin_h, write_conn)
        assert r["copies_created"] == 0
        source = r["head"]["finance_head_pk"]
        cur = write_conn.cursor()
        assert FC.sync_sakha(cur, None, register_org_pk) >= 1               # what creating the Sakha does
        assert copy_in(client, admin_h, source, register_org_pk)["is_kendra_copy"] is True
        assert FC.sync_sakha(cur, None, register_org_pk) == 0               # and it is idempotent


# ═══════════════════════════════════════════════════════════════════════
# The member's cards: amount, paid, due
# ═══════════════════════════════════════════════════════════════════════

class TestMemberCards:
    def _own_copy(self, client, admin_h, write_conn, register_org_pk, mock_gateway, **over):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn, **over)["head"]["finance_head_pk"]
        return copy_in(client, admin_h, source, register_org_pk), source

    def test_the_member_sees_their_own_sakhas_copy_and_never_the_source_or_another_sakhas(self, client, admin_h, write_conn, register_org_pk, other_org_pk, mock_gateway, plain_member_h):
        mine, source = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        theirs = copy_in(client, admin_h, source, other_org_pk)
        cards = {c["finance_head_pk"] for c in client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json()}
        assert mine["finance_head_pk"] in cards
        assert source not in cards and theirs["finance_head_pk"] not in cards

    def test_an_unpaid_fixed_contribution_is_due_and_must_be_paid_in_full(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        c = card(client, plain_member_h, mine["finance_head_pk"])
        assert (c["state"], c["fixed_amount"], c["paid_amount"], c["due_amount"], c["payable"]) == ("DUE", "500.00", "0.00", "500.00", True)
        for amount in ("100.00", "500.01"):
            assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": amount}, headers=plain_member_h).status_code == 422

    def test_paying_in_full_turns_the_card_green_and_a_second_payment_is_refused(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        member_pays(client, admin_h, mock_gateway, plain_member_h, mine["finance_head_pk"], "500.00")
        c = card(client, plain_member_h, mine["finance_head_pk"])
        assert (c["state"], c["paid_amount"], c["due_amount"]) == ("PAID", "500.00", "0.00")
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": "500.00"}, headers=plain_member_h).status_code == 422

    def test_a_second_unpaid_request_for_a_full_payment_head_is_a_conflict(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        body = {"finance_head_pk": mine["finance_head_pk"], "amount": "500.00"}
        assert client.post(f"{BASE}/my-pranami/pay", json=body, headers=plain_member_h).status_code == 201
        assert client.post(f"{BASE}/my-pranami/pay", json=body, headers=plain_member_h).status_code == 409
        c = card(client, plain_member_h, mine["finance_head_pk"])
        assert c["state"] == "DUE" and c["pending_amount"] == "500.00"             # waiting money is shown, never counted as paid

    def test_part_payment_adds_up(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway, allow_part_payment=True)
        member_pays(client, admin_h, mock_gateway, plain_member_h, mine["finance_head_pk"], "200.00")
        c = card(client, plain_member_h, mine["finance_head_pk"])
        assert (c["state"], c["paid_amount"], c["due_amount"]) == ("PART", "200.00", "300.00")
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": "300.01"}, headers=plain_member_h).status_code == 422
        member_pays(client, admin_h, mock_gateway, plain_member_h, mine["finance_head_pk"], "300.00")
        assert card(client, plain_member_h, mine["finance_head_pk"])["state"] == "PAID"

    def test_pending_part_payments_cannot_overshoot_what_is_due(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway, allow_part_payment=True)
        pk = mine["finance_head_pk"]
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": pk, "amount": "400.00"}, headers=plain_member_h).status_code == 201
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": pk, "amount": "200.00"}, headers=plain_member_h).status_code == 422   # only 100 left
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": pk, "amount": "100.00"}, headers=plain_member_h).status_code == 201

    def test_a_free_amount_head_has_nothing_due_but_shows_what_was_paid(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        h = contribution(client, admin_h, register_org_pk, head_name="Donation")["head"]
        member_pays(client, admin_h, mock_gateway, plain_member_h, h["finance_head_pk"], "75.00")
        c = card(client, plain_member_h, h["finance_head_pk"])
        assert (c["state"], c["fixed_amount"], c["due_amount"], c["paid_amount"]) == ("OPEN", None, None, "75.00")

    def test_a_one_sakha_payment_does_not_settle_another_members_card(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        member_pays(client, admin_h, mock_gateway, plain_member_h, mine["finance_head_pk"], "500.00")
        other = new_member(write_conn, register_org_pk, "FinConB")
        other_h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        assert card(client, other_h, mine["finance_head_pk"])["state"] == "DUE"

    def test_the_money_lands_with_the_sakha_that_owns_the_copy(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        full = member_pays(client, admin_h, mock_gateway, plain_member_h, mine["finance_head_pk"], "500.00")
        assert full["status"] == "PAID" and full["transaction_reference"] and full["financial_account_pk"] == mine["collection_account_pk"]
        txn = client.get(f"{BASE}/transactions", params={"q": full["transaction_reference"]}, headers=admin_h).json()["items"][0]
        assert txn["finance_head_pk"] == mine["finance_head_pk"] and txn["scope_organization_name"] == mine["organization_name"]
        assert any(a == "UPI_PAYMENT_POSTED" for a, _ in audit_rows(write_conn, "financial_transaction", txn["financial_transaction_pk"]))

    def test_the_payment_request_is_audited(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        mine, _ = self._own_copy(client, admin_h, write_conn, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": "500.00"}, headers=plain_member_h).json()
        assert any(a == "CREATE" for a, _ in audit_rows(write_conn, "upi_payment_request", r["upi_payment_request_pk"]))
