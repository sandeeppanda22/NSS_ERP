"""
Paying several contributions in ONE UPI payment (owner request 2026-11-17), end to end against a database: the member ticks several
contributions of their own Sakha, pays once, and the signed MOCK webhook books one transaction + one receipt per contribution, all or
nothing. Real integration tests (nothing mocked); they need Phase 11i plus ddl/14_finance/19_upi_payment_request_line.sql.
"""

import pytest

from api.config import settings
from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    _login_headers,
    admin_h,
    admin_user,
    ensure_open_year_covering_today,
    kendra_admin,
    kendra_h,
    make_account,
    make_head,
    make_world,
    mock_gateway,
    move,
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
    webhook,
)


@pytest.fixture
def plain_member(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "FinMulti")


@pytest.fixture
def plain_member_h(client, plain_member):
    return _login_headers(client, plain_member["sangha_sevi_id"], plain_member["password"])


@pytest.fixture(autouse=True)
def _a_financial_year_covers_today(write_conn):
    ensure_open_year_covering_today(write_conn)


def shared_heads(client, admin_h, org_pk, gw, names=("Annual Pranami", "Special Pranami", "Festival"), **over) -> dict:
    """Several member-payable UPI heads of ONE Sangha, all collecting into the same account and scope."""
    w = make_world(client, admin_h, org_pk)
    account = make_account(client, admin_h, org_pk, gw)
    heads = [make_head(client, admin_h, org_pk, head_name=n, is_pranami=True, allow_upi=True, collection_scope_pk=w["scope"]["financial_scope_pk"],
                       collection_fund_pk=w["fund"]["fund_master_pk"], collection_account_pk=account["financial_account_pk"], **over) for n in names]
    return {"world": w, "account": account, "heads": heads}


def pay_multiple(client, headers, *pairs, expect=201):
    body = {"items": [{"finance_head_pk": h["finance_head_pk"] if isinstance(h, dict) else h, "amount": a} for h, a in pairs]}
    r = client.post(f"{BASE}/my-pranami/pay-multiple", json=body, headers=headers)
    assert r.status_code == expect, r.text
    return r.json()


def full(client, admin_h, pk) -> dict:
    return client.get(f"{BASE}/payment-requests/{pk}", headers=admin_h).json()


def cards(client, headers) -> dict:
    return {c["finance_head_pk"]: c for c in client.get(f"{BASE}/my-pranami/heads", headers=headers).json()}


class TestOnePaymentForSeveralContributions:
    def test_one_order_for_the_total_with_the_items_listed(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        s = shared_heads(client, admin_h, register_org_pk, mock_gateway)
        a, b, c = s["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "120.50"), (c, "50.00"))
        assert r["amount"] == "470.50" and r["status"] == "PENDING" and r["upi_uri"].startswith("upi://pay?")
        assert r["head_name"] == "Several contributions" and r["receipt_number"] is None
        assert [(i["head_name"], i["amount"]) for i in r["items"]] == [("Annual Pranami", "300.00"), ("Special Pranami", "120.50"), ("Festival", "50.00")]
        admin_view = full(client, admin_h, r["upi_payment_request_pk"])
        assert admin_view["line_count"] == 3 and admin_view["amount"] == "470.50" and admin_view["head_name"] == "Several contributions"

    def test_the_signed_webhook_books_one_transaction_and_receipt_per_item(self, client, admin_h, register_org_pk, mock_gateway, plain_member, plain_member_h):
        s = shared_heads(client, admin_h, register_org_pk, mock_gateway)
        a, b, c = s["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "120.50"))
        assert pay_request(client, mock_gateway, full(client, admin_h, r["upi_payment_request_pk"])).status_code == 200
        done = client.get(f"{BASE}/my-pranami/requests/{r['upi_payment_request_pk']}", headers=plain_member_h).json()
        assert done["status"] == "PAID" and len(done["items"]) == 2
        assert all(i["receipt_number"] and i["financial_receipt_pk"] for i in done["items"])
        assert len({i["receipt_number"] for i in done["items"]}) == 2                      # a receipt for EACH contribution
        history = client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]
        by_head = {h["finance_head_name"]: h for h in history}
        assert by_head["Annual Pranami"]["amount"] == "300.00" and by_head["Special Pranami"]["amount"] == "120.50"
        assert all(h["status"] == "POSTED" and len(h["receipts"]) == 1 for h in by_head.values())

    def test_every_receipt_downloads_as_its_own_pdf(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        s = shared_heads(client, admin_h, register_org_pk, mock_gateway)
        a, b, _ = s["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "120.50"))
        pay_request(client, mock_gateway, full(client, admin_h, r["upi_payment_request_pk"]))
        done = client.get(f"{BASE}/my-pranami/requests/{r['upi_payment_request_pk']}", headers=plain_member_h).json()
        texts = []
        for item in done["items"]:
            pdf = client.get(f"{BASE}/my-pranami/receipts/{item['financial_receipt_pk']}/pdf", headers=plain_member_h)
            assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
            texts.append(item["receipt_number"])
        assert len(set(texts)) == 2

    def test_the_cards_follow_each_contribution_separately(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        s = shared_heads(client, admin_h, register_org_pk, mock_gateway)
        a, b, c = s["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "120.50"))
        pay_request(client, mock_gateway, full(client, admin_h, r["upi_payment_request_pk"]))
        after = cards(client, plain_member_h)
        assert after[a["finance_head_pk"]]["paid_amount"] == "300.00" and after[b["finance_head_pk"]]["paid_amount"] == "120.50"
        assert after[c["finance_head_pk"]]["paid_amount"] == "0.00"

    def test_a_single_item_is_accepted_as_a_one_line_payment(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"][0]
        r = pay_multiple(client, plain_member_h, (a, "10.00"))
        assert r["amount"] == "10.00" and len(r["items"]) == 1

    def test_the_payment_and_the_booking_are_audited(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h, write_conn):
        s = shared_heads(client, admin_h, register_org_pk, mock_gateway)
        a, b, _ = s["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "120.50"))
        pay_request(client, mock_gateway, full(client, admin_h, r["upi_payment_request_pk"]))
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'upi_payment_request' AND action = 'CREATE' AND record_pk::text = %s", (r["upi_payment_request_pk"],))
        detail = cur.fetchone()[0]
        assert detail["multiple"] is True and len(detail["items"]) == 2
        cur.execute("SELECT COUNT(*) FROM nss.system_event_log WHERE action = 'UPI_PAYMENT_POSTED' AND detail->>'request' = %s", (full(client, admin_h, r["upi_payment_request_pk"])["request_reference"],))
        assert cur.fetchone()[0] == 2


class TestTheRules:
    def test_the_same_contribution_twice_is_refused(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"][0]
        pay_multiple(client, plain_member_h, (a, "10.00"), (a, "20.00"), expect=422)

    def test_one_unavailable_item_stops_the_whole_payment_and_creates_nothing(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        no_upi = make_head(client, admin_h, register_org_pk, is_pranami=True)                  # a Pranami head that has no payment set up
        before = client.get(f"{BASE}/payment-requests", params={"page_size": 100}, headers=admin_h).json()["total"]
        pay_multiple(client, plain_member_h, (a, "10.00"), (no_upi, "10.00"), expect=422)
        pay_multiple(client, plain_member_h, (a, "10.00"), (FAKE_UUID, "10.00"), expect=422)
        assert client.get(f"{BASE}/payment-requests", params={"page_size": 100}, headers=admin_h).json()["total"] == before

    def test_own_sakha_and_the_kendra_cannot_be_paid_in_one_payment(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        from tests.reparent_support import kendra_pks

        mine = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"][0]
        kendra = shared_heads(client, admin_h, kendra_pks(write_conn)[0], mock_gateway, names=("Kendra Pranami",))["heads"][0]
        r = pay_multiple(client, plain_member_h, (mine, "10.00"), (kendra, "10.00"), expect=422)
        assert "separately" in r["detail"]

    def test_another_sakhas_contribution_is_refused(self, client, admin_h, register_org_pk, other_org_pk, mock_gateway, plain_member_h):
        mine = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"][0]
        theirs = shared_heads(client, admin_h, other_org_pk, mock_gateway)["heads"][0]
        pay_multiple(client, plain_member_h, (mine, "10.00"), (theirs, "10.00"), expect=422)

    def test_each_fixed_contribution_must_be_paid_in_full(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        s = shared_heads(client, admin_h, register_org_pk, mock_gateway)
        a, b, _ = s["heads"]
        client.patch(f"{BASE}/heads/{a['finance_head_pk']}", json={"fixed_amount": "500", "due_period": "YEARLY"}, headers=admin_h)
        r = pay_multiple(client, plain_member_h, (a, "200.00"), (b, "10.00"), expect=422)
        assert "Annual Pranami" in r["detail"] and "in full" in r["detail"]                 # it names the offending item
        pay_multiple(client, plain_member_h, (a, "500.00"), (b, "10.00"))

    def test_a_part_payment_item_takes_any_part(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        client.patch(f"{BASE}/heads/{a['finance_head_pk']}", json={"fixed_amount": "500", "due_period": "YEARLY", "allow_part_payment": True}, headers=admin_h)
        pay_multiple(client, plain_member_h, (a, "125.00"), (b, "10.00"))

    def test_the_total_cannot_pass_the_single_payment_cap(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h, monkeypatch):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        monkeypatch.setattr(settings, "UPI_MAX_AMOUNT", "1000")
        pay_multiple(client, plain_member_h, (a, "600.00"), (b, "400.01"), expect=422)
        pay_multiple(client, plain_member_h, (a, "600.00"), (b, "400.00"))

    def test_the_total_must_reach_the_minimum_payment(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        r = pay_multiple(client, plain_member_h, (a, "0.40"), (b, "0.40"), expect=422)
        assert "at least Rs. 1.00" in r["detail"]
        pay_multiple(client, plain_member_h, (a, "0.60"), (b, "0.60"))                  # Rs. 1.20 in total is fine, even if each item is below Rs. 1

    def test_waiting_money_blocks_a_second_payment_of_the_same_full_payment_head(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a, b, c = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        client.patch(f"{BASE}/heads/{a['finance_head_pk']}", json={"fixed_amount": "500", "due_period": "YEARLY"}, headers=admin_h)
        pay_multiple(client, plain_member_h, (a, "500.00"), (b, "10.00"))
        assert cards(client, plain_member_h)[a["finance_head_pk"]]["pending_amount"] == "500.00"       # counted from the line
        pay_multiple(client, plain_member_h, (a, "500.00"), (c, "10.00"), expect=409)
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": a["finance_head_pk"], "amount": "500.00"}, headers=plain_member_h).status_code == 409

    def test_the_payer_cannot_be_named_and_nobody_else_can_read_the_payment(self, client, admin_h, register_org_pk, mock_gateway, plain_member, plain_member_h, write_conn):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        other = new_member(write_conn, register_org_pk, "FinMultiOther")
        r = client.post(f"{BASE}/my-pranami/pay-multiple", headers=plain_member_h, json={
            "items": [{"finance_head_pk": a["finance_head_pk"], "amount": "10.00", "payer_person_pk": other["person_pk"]}],
            "payer_person_pk": other["person_pk"], "sangha_sevi_id": other["sangha_sevi_id"]})
        assert r.status_code == 201
        pk = r.json()["upi_payment_request_pk"]
        assert full(client, admin_h, pk)["payer_sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        other_h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        assert client.get(f"{BASE}/my-pranami/requests/{pk}", headers=other_h).status_code == 404

    @pytest.mark.parametrize("body", [{"items": []}, {"items": [{"finance_head_pk": "not-a-uuid", "amount": "1"}]}, {}, {"items": [{"finance_head_pk": FAKE_UUID, "amount": "0"}]}])
    def test_malformed_bodies_are_422(self, client, plain_member_h, body):
        assert client.post(f"{BASE}/my-pranami/pay-multiple", json=body, headers=plain_member_h).status_code == 422

    def test_no_login_is_401(self, client):
        assert client.post(f"{BASE}/my-pranami/pay-multiple", json={"items": [{"finance_head_pk": FAKE_UUID, "amount": "1"}]}).status_code == 401


class TestBookingIsAllOrNothing:
    def test_a_different_amount_paid_is_held_and_nothing_is_booked(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "100.00"))
        pay_request(client, mock_gateway, full(client, admin_h, r["upi_payment_request_pk"]), amount="350.00")
        held = full(client, admin_h, r["upi_payment_request_pk"])
        assert held["status"] == "PAID" and held["transaction_reference"] is None and "AMOUNT_MISMATCH" in held["review_reason"]
        assert client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"] == []
        refused = client.post(f"{BASE}/payment-requests/{r['upi_payment_request_pk']}/post", headers=admin_h)
        assert refused.status_code == 422 and "exactly the amount asked" in refused.json()["detail"]

    def test_if_one_item_cannot_be_booked_none_is_and_the_payment_waits_for_review(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h, write_conn):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        other_scope = make_world(client, admin_h, register_org_pk)["scope"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "100.00"))
        # the second contribution's scope is closed AFTER the member started paying
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.upi_payment_request_line SET financial_scope_pk = %s WHERE upi_payment_request_pk = %s AND line_no = 2", (other_scope["financial_scope_pk"], r["upi_payment_request_pk"]))
        move(client, admin_h, "scopes", other_scope["financial_scope_pk"], "CLOSING")
        pay_request(client, mock_gateway, full(client, admin_h, r["upi_payment_request_pk"]))
        held = full(client, admin_h, r["upi_payment_request_pk"])
        assert held["status"] == "PAID" and held["transaction_reference"] is None and held["review_reason"]
        assert client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"] == []        # not even the first item was booked
        cur.execute("SELECT COUNT(*) FROM nss.upi_payment_request_line WHERE upi_payment_request_pk = %s AND financial_transaction_pk IS NOT NULL", (r["upi_payment_request_pk"],))
        assert cur.fetchone()[0] == 0

    def test_a_replayed_webhook_books_nothing_twice(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        a, b, _ = shared_heads(client, admin_h, register_org_pk, mock_gateway)["heads"]
        r = pay_multiple(client, plain_member_h, (a, "300.00"), (b, "100.00"))
        request = full(client, admin_h, r["upi_payment_request_pk"])
        assert pay_request(client, mock_gateway, request, event_id="evt-fixed").status_code == 200
        assert pay_request(client, mock_gateway, request, event_id="evt-fixed").status_code == 200
        assert len(client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]) == 2
