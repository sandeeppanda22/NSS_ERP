"""
Finance UPI collection API (api/routers/finance_upi.py + api/services/upi_gateway.py): payment requests, the signed webhook,
the review queue, the dev 'mock-pay' simulation and member self-service.

Real integration tests (nothing mocked): the MOCK gateway is the project's own adapter - it signs its own webhooks exactly the
way a real provider's callback is verified - so the whole money path is exercised: request -> signed webhook -> booked
transaction + issued receipt -> the member's own Pranami. No money moves. The gateway is OFF unless a test switches it on
(mock_gateway fixture), which is itself asserted.
"""

import json
from contextlib import contextmanager
from datetime import date

import pytest

from api.config import settings
from api.services import upi_gateway
from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    _login_headers,
    admin_h,
    admin_user,
    create_request,
    ensure_open_year_covering_today,
    kendra_admin,
    kendra_h,
    make_account,
    make_fund,
    make_head,
    make_world,
    mock_gateway,
    move,
    new_code,
    new_member,
    other_admin,
    other_admin_h,
    other_org_pk,
    pay_request,
    plain_member,
    plain_member_h,
    raw_move,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    upi_world,
    viewer_h,
    viewer_user,
    webhook,
)


@pytest.fixture
def plain_member(write_conn, register_org_pk):
    """A FRESH member per test (shadows the module-scoped one): the per-member cap on unpaid requests would otherwise carry over."""
    return new_member(write_conn, register_org_pk, "FinPay")


@pytest.fixture
def plain_member_h(client, plain_member):
    return _login_headers(client, plain_member["sangha_sevi_id"], plain_member["password"])


@pytest.fixture(autouse=True)
def _a_financial_year_covers_today(write_conn):
    """UPI payments are booked on the day they are paid."""
    ensure_open_year_covering_today(write_conn)


@contextmanager
def no_open_year_today(write_conn):
    today = date.today()
    cur = write_conn.cursor()
    cur.execute("UPDATE nss.financial_year SET status = 'CLOSING' WHERE status = 'OPEN' AND start_date <= %s AND end_date >= %s RETURNING financial_year_pk", (today, today))
    pks = [str(r[0]) for r in cur.fetchall()]
    try:
        yield
    finally:
        if pks:
            cur.execute("UPDATE nss.financial_year SET status = 'OPEN' WHERE financial_year_pk = ANY(%s::uuid[])", (pks,))


def event_rows(write_conn, request_pk):
    cur = write_conn.cursor()
    cur.execute("SELECT outcome, signature_valid FROM nss.finance_gateway_event WHERE upi_payment_request_pk = %s ORDER BY received_at, finance_gateway_event_pk", (str(request_pk),))
    return cur.fetchall()


def booked_for(write_conn, request_reference):
    cur = write_conn.cursor()
    cur.execute("SELECT financial_transaction_pk, status, amount, created_by_sangha_sevi_pk, finance_head_pk, person_pk FROM nss.financial_transaction "
                "WHERE description LIKE %s", (f"UPI {request_reference}%",))
    return cur.fetchall()


def a_request(client, admin_h_, u, amount="500.00", **over):
    r = create_request(client, admin_h_, u["head"], amount, **over)
    assert r.status_code == 201, r.text
    return r.json()


def fetch(client, headers, pk):
    r = client.get(f"{BASE}/payment-requests/{pk}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════
# Off by default
# ═══════════════════════════════════════════════════════════════════════

class TestOffByDefault:
    def test_nothing_is_collectable_until_a_provider_is_enabled(self, client, admin_h, register_org_pk, mock_gateway, monkeypatch):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "")                       # the production default
        r = create_request(client, admin_h, u["head"])
        assert r.status_code == 503 and "not available" in r.text

    def test_the_webhook_does_not_exist_while_the_provider_is_disabled(self, client, mock_gateway, monkeypatch):
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "")
        assert webhook(client, mock_gateway, "mock_x").status_code == 404

    @pytest.mark.parametrize("provider", ["PAYPAL", "razorpay", "../etc", "mock;drop"])
    def test_unknown_or_disabled_providers_are_404(self, client, mock_gateway, provider):
        assert webhook(client, mock_gateway, "mock_x", provider=provider).status_code == 404

    def test_the_mock_simulator_is_404_unless_the_mock_provider_is_enabled(self, client, admin_h, register_org_pk, mock_gateway, monkeypatch):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "")
        assert client.post(f"{BASE}/payment-requests/{req['upi_payment_request_pk']}/mock-pay", headers=admin_h).status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Creating a request
# ═══════════════════════════════════════════════════════════════════════

class TestCreateRequest:
    def test_a_treasurer_asks_for_a_payment(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "500.00", payer_name="A devotee", note="Annual Pranami 2026")
        assert req["request_reference"].startswith("PRQ") and req["status"] == "PENDING" and req["provider"] == "MOCK"
        assert req["provider_order_id"].startswith("mock_") and req["amount"] in ("500.00", 500)
        assert req["head_name"] == "UPI Pranami" and req["financial_account_pk"] == u["account"]["financial_account_pk"]
        assert req["upi_uri"].startswith("upi://pay?") and "pa=sakha%40oksbi" in req["upi_uri"] and "am=500.00" in req["upi_uri"]
        assert req["transaction_reference"] is None and req["receipt_number"] is None and req["payer_name"] == "A devotee"

    def test_the_head_not_the_caller_decides_where_it_is_booked(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        assert req["financial_scope_pk"] == u["world"]["scope"]["financial_scope_pk"]

    @pytest.mark.parametrize("amount", ["0", "-5", "1.234", "abc"])
    def test_bad_amounts_are_422(self, client, admin_h, register_org_pk, mock_gateway, amount):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        assert create_request(client, admin_h, u["head"], amount).status_code == 422

    def test_a_single_payment_is_capped(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        assert create_request(client, admin_h, u["head"], "100000.00").status_code == 201
        assert create_request(client, admin_h, u["head"], "100000.01").status_code == 422

    def test_a_head_that_cannot_collect_by_upi_is_refused(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        plain = make_head(client, admin_h, register_org_pk)
        assert create_request(client, admin_h, plain).status_code == 422
        client.patch(f"{BASE}/heads/{u['head']['finance_head_pk']}", json={"allow_upi": False}, headers=admin_h)
        assert create_request(client, admin_h, u["head"]).status_code == 422

    def test_a_template_or_unknown_head_is_refused(self, client, admin_h, mock_gateway):
        template = client.get(f"{BASE}/heads", params={"templates_only": "true", "q": "PRANAMI_ANNUAL"}, headers=admin_h).json()["items"][0]
        assert create_request(client, admin_h, template).status_code == 422
        assert create_request(client, admin_h, {"finance_head_pk": FAKE_UUID}).status_code == 422

    def test_a_switched_off_head_or_account_or_scope_stops_collecting(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        move(client, admin_h, "heads", u["head"]["finance_head_pk"], "INACTIVE")
        assert create_request(client, admin_h, u["head"]).status_code == 422
        move(client, admin_h, "heads", u["head"]["finance_head_pk"], "ACTIVE")
        move(client, admin_h, "scopes", u["world"]["scope"]["financial_scope_pk"], "CLOSING")
        assert create_request(client, admin_h, u["head"]).status_code == 422

    def test_an_account_whose_credentials_are_missing_is_a_503_not_a_crash(self, client, admin_h, register_org_pk, mock_gateway, monkeypatch):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        monkeypatch.delenv(f"UPI_{mock_gateway.ref}_KEY_SECRET")
        r = create_request(client, admin_h, u["head"])
        assert r.status_code == 503 and mock_gateway.secret not in r.text

    def test_the_payer_can_be_a_member(self, client, admin_h, register_org_pk, mock_gateway, plain_member):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, sangha_sevi_id=plain_member["sangha_sevi_id"])
        assert req["payer_sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        assert create_request(client, admin_h, u["head"], sangha_sevi_id="SS999999999").status_code == 422

    def test_scope_and_permissions(self, client, admin_h, sakha_admin_h, other_admin_h, viewer_h, register_org_pk, other_org_pk, mock_gateway, plain_member):
        mine = upi_world(client, admin_h, register_org_pk, mock_gateway)
        assert create_request(client, sakha_admin_h, mine["head"]).status_code == 201                  # MANAGE in own Sakha
        assert create_request(client, other_admin_h, mine["head"]).status_code == 403                  # a foreign Sakha
        assert create_request(client, viewer_h, mine["head"]).status_code == 403                       # view-only
        theirs = upi_world(client, admin_h, other_org_pk, mock_gateway)
        # a foreign admin may collect for their own Sangha, but not on behalf of a member of another Sangha
        assert create_request(client, other_admin_h, theirs["head"]).status_code == 201
        assert create_request(client, other_admin_h, theirs["head"], sangha_sevi_id=plain_member["sangha_sevi_id"]).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# The signed webhook - the only way money is believed
# ═══════════════════════════════════════════════════════════════════════

class TestWebhookHappyPath:
    def test_a_signed_paid_event_books_the_transaction_and_issues_the_receipt(self, client, admin_h, register_org_pk, mock_gateway, write_conn, plain_member):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "500.00", sangha_sevi_id=plain_member["sangha_sevi_id"], payer_name="Ram")
        before = client.get(f"{BASE}/funds/{u['fund']['fund_master_pk']}", headers=admin_h).json()["balance"]
        r = pay_request(client, mock_gateway, req, payment_id="UTR123456789")
        assert r.status_code == 200 and r.json() == {"outcome": "POSTED"}

        done = fetch(client, admin_h, req["upi_payment_request_pk"])
        assert done["status"] == "PAID" and done["provider_payment_id"] == "UTR123456789" and done["review_reason"] is None
        assert done["transaction_reference"].startswith("FTX") and done["receipt_number"].startswith("RCT")
        assert float(done["paid_amount"]) == 500.0 and done["paid_at"]

        txn = client.get(f"{BASE}/transactions", params={"q": done["transaction_reference"]}, headers=admin_h).json()["items"][0]
        assert (txn["status"], txn["transaction_type"], float(txn["amount"])) == ("POSTED", "INCOME", 500.0)
        assert txn["finance_head_pk"] == u["head"]["finance_head_pk"] and txn["fund_master_pk"] == u["fund"]["fund_master_pk"]
        assert txn["sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        assert float(client.get(f"{BASE}/funds/{u['fund']['fund_master_pk']}", headers=admin_h).json()["balance"]) == float(before) + 500.0

        receipt = client.get(f"{BASE}/receipts", params={"financial_transaction_pk": txn["financial_transaction_pk"]}, headers=admin_h).json()["items"][0]
        assert (receipt["status"], receipt["payment_method_code"], receipt["instrument_reference"]) == ("ISSUED", "UPI", "UTR123456789")

    def test_the_booking_is_a_system_action_not_a_person(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pay_request(client, mock_gateway, req)
        rows = booked_for(write_conn, req["request_reference"])
        assert len(rows) == 1 and rows[0][3] is None, "created_by must be NULL: no person approved this, the signed webhook did"

    def test_the_payer_sees_it_in_their_own_pranami(self, client, admin_h, register_org_pk, mock_gateway, plain_member, plain_member_h):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "250.00", sangha_sevi_id=plain_member["sangha_sevi_id"])
        pay_request(client, mock_gateway, req, payment_id="UTR777")
        item = next(i for i in client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]
                    if i["transaction_reference"] == fetch(client, admin_h, req["upi_payment_request_pk"])["transaction_reference"])
        assert item["finance_head_name"] == "UPI Pranami" and item["receipts"][0]["payment_method_name"] == "UPI"
        assert item["receipts"][0]["instrument_reference"] == "UPI777" or item["receipts"][0]["instrument_reference"] == "UTR777"

    def test_the_provider_name_is_case_insensitive(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        assert pay_request(client, mock_gateway, req, provider="mock").json() == {"outcome": "POSTED"}

    def test_a_restricted_head_books_into_its_restricted_fund(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway, restricted=True)
        req = a_request(client, admin_h, u, "1000.00")
        assert pay_request(client, mock_gateway, req).json() == {"outcome": "POSTED"}
        assert float(client.get(f"{BASE}/funds/{u['fund']['fund_master_pk']}", headers=admin_h).json()["balance"]) == 1000.0

    def test_events_are_logged(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pay_request(client, mock_gateway, req)
        assert event_rows(write_conn, req["upi_payment_request_pk"]) == [("POSTED", True)]


class TestWebhookRejections:
    def test_a_forged_signature_is_401_and_changes_nothing(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        r = pay_request(client, mock_gateway, req, secret="the-attacker-guesses-a-secret")
        assert r.status_code == 401 and r.json() == {"outcome": "REJECTED_SIGNATURE"}
        assert fetch(client, admin_h, req["upi_payment_request_pk"])["status"] == "PENDING"
        assert booked_for(write_conn, req["request_reference"]) == []
        assert event_rows(write_conn, req["upi_payment_request_pk"]) == [("REJECTED_SIGNATURE", False)]

    def test_editing_the_amount_after_signing_is_detected(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "500.00")
        r = webhook(client, mock_gateway, req["provider_order_id"], amount=__import__("decimal").Decimal("5.00"), tamper=(b"5.00", b"500.00"))
        assert r.status_code == 401
        assert booked_for(write_conn, req["request_reference"]) == [] and fetch(client, admin_h, req["upi_payment_request_pk"])["status"] == "PENDING"

    def test_a_missing_signature_is_401(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        raw, _ = upi_gateway.build_mock_event(secret=mock_gateway.secret, order_id=req["provider_order_id"])
        assert client.post(f"{BASE}/gateway/webhook/MOCK", content=raw).status_code == 401

    def test_each_account_has_its_own_secret(self, client, admin_h, register_org_pk, other_org_pk, mock_gateway, monkeypatch):
        """A valid signature from ANOTHER Sangha's credential set must not pay this Sangha's request."""
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        other_ref, other_secret = new_code("O"), "whsec_other_" + new_code()
        for suffix, value in (("KEY_ID", "k"), ("KEY_SECRET", "s"), ("WEBHOOK_SECRET", other_secret)):
            monkeypatch.setenv(f"UPI_{other_ref}_{suffix}", value)
        assert pay_request(client, mock_gateway, req, secret=other_secret).status_code == 401

    def test_a_forged_event_can_never_block_the_real_one(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        assert pay_request(client, mock_gateway, req, secret="forged", event_id="evt-same-id").status_code == 401
        assert pay_request(client, mock_gateway, req, event_id="evt-same-id").json() == {"outcome": "POSTED"}

    def test_an_unknown_order_is_acknowledged_but_not_stored(self, client, mock_gateway, write_conn):
        cur = write_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nss.finance_gateway_event")
        before = cur.fetchone()[0]
        r = webhook(client, mock_gateway, "mock_does_not_exist")
        assert r.status_code == 200 and r.json() == {"outcome": "UNKNOWN_REQUEST"}
        cur.execute("SELECT COUNT(*) FROM nss.finance_gateway_event")
        assert cur.fetchone()[0] == before, "strangers must not be able to grow the event table"

    def test_garbage_bodies(self, client, mock_gateway):
        h = {"X-Mock-Signature": "x", "Content-Type": "application/json"}
        assert client.post(f"{BASE}/gateway/webhook/MOCK", content=b"not json at all", headers=h).status_code == 400
        assert client.post(f"{BASE}/gateway/webhook/MOCK", content=b"[1, 2, 3]", headers=h).status_code == 400
        assert client.post(f"{BASE}/gateway/webhook/MOCK", content=b'{"order_id": 5}', headers=h).json() == {"outcome": "UNKNOWN_REQUEST"}

    def test_an_oversized_body_is_413(self, client, mock_gateway):
        big = b'{"order_id": "' + b"x" * (settings.UPI_WEBHOOK_MAX_BYTES + 10) + b'"}'
        assert client.post(f"{BASE}/gateway/webhook/MOCK", content=big, headers={"X-Mock-Signature": "x"}).status_code == 413

    def test_a_paid_event_without_a_payment_id_is_not_evidence(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        raw = json.dumps({"event_id": "e-nopay", "type": "payment.paid", "order_id": req["provider_order_id"], "amount": "500.00"}).encode()
        r = client.post(f"{BASE}/gateway/webhook/MOCK", content=raw, headers={"X-Mock-Signature": upi_gateway.sign(mock_gateway.secret, raw)})
        assert r.status_code == 200 and r.json() == {"outcome": "IGNORED"}
        assert fetch(client, admin_h, req["upi_payment_request_pk"])["status"] == "PENDING"


class TestIdempotency:
    def test_a_replayed_event_is_acknowledged_and_books_nothing_twice(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        assert pay_request(client, mock_gateway, req, event_id="evt-1").json() == {"outcome": "POSTED"}
        again = pay_request(client, mock_gateway, req, event_id="evt-1")
        assert again.status_code == 200 and again.json() == {"outcome": "DUPLICATE"}
        assert len(booked_for(write_conn, req["request_reference"])) == 1

    def test_a_second_paid_event_with_a_new_id_for_a_paid_request_books_nothing_more(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pay_request(client, mock_gateway, req, event_id="evt-a", payment_id="P1")
        again = pay_request(client, mock_gateway, req, event_id="evt-b", payment_id="P2")
        assert again.json() == {"outcome": "DUPLICATE"}
        assert len(booked_for(write_conn, req["request_reference"])) == 1
        assert fetch(client, admin_h, req["upi_payment_request_pk"])["provider_payment_id"] == "P1"

    def test_failure_and_expiry_events(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        failed, expired = a_request(client, admin_h, u), a_request(client, admin_h, u)
        assert webhook(client, mock_gateway, failed["provider_order_id"], kind="payment.failed").json() == {"outcome": "FAILED"}
        assert webhook(client, mock_gateway, expired["provider_order_id"], kind="order.expired").json() == {"outcome": "EXPIRED"}
        assert fetch(client, admin_h, failed["upi_payment_request_pk"])["status"] == "FAILED"
        assert fetch(client, admin_h, expired["upi_payment_request_pk"])["status"] == "EXPIRED"

    def test_a_late_failure_never_undoes_a_payment(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pay_request(client, mock_gateway, req)
        assert webhook(client, mock_gateway, req["provider_order_id"], kind="payment.failed").json() == {"outcome": "IGNORED"}
        assert fetch(client, admin_h, req["upi_payment_request_pk"])["status"] == "PAID"


# ═══════════════════════════════════════════════════════════════════════
# Money received but not booked: the review queue
# ═══════════════════════════════════════════════════════════════════════

class TestReviewQueue:
    def test_a_different_amount_is_held_never_booked_on_a_guess(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "500.00")
        r = pay_request(client, mock_gateway, req, amount="450.00")
        assert r.status_code == 200 and r.json() == {"outcome": "PAID_NEEDS_REVIEW"}
        held = fetch(client, admin_h, req["upi_payment_request_pk"])
        assert held["status"] == "PAID" and float(held["paid_amount"]) == 450.0 and held["transaction_reference"] is None
        assert held["review_reason"].startswith("AMOUNT_MISMATCH") and "500.00" in held["review_reason"] and "450.00" in held["review_reason"]
        assert booked_for(write_conn, req["request_reference"]) == []
        queue = client.get(f"{BASE}/payment-requests", params={"needs_review": "true"}, headers=admin_h).json()["items"]
        assert req["upi_payment_request_pk"] in {x["upi_payment_request_pk"] for x in queue}

    def test_an_approver_books_the_amount_actually_received(self, client, admin_h, sakha_admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "500.00")
        pay_request(client, mock_gateway, req, amount="450.00")
        pk = req["upi_payment_request_pk"]
        assert client.post(f"{BASE}/payment-requests/{pk}/post", headers=sakha_admin_h).status_code == 403     # booking needs APPROVE
        r = client.post(f"{BASE}/payment-requests/{pk}/post", headers=admin_h)
        assert r.status_code == 200, r.text
        done = r.json()
        assert done["transaction_reference"] and done["review_reason"] is None
        rows = booked_for(write_conn, req["request_reference"])
        assert len(rows) == 1 and float(rows[0][2]) == 450.0 and rows[0][1] == "POSTED"
        assert client.post(f"{BASE}/payment-requests/{pk}/post", headers=admin_h).status_code == 409           # not twice

    def test_no_open_financial_year_holds_the_payment_until_one_is_open(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pk = req["upi_payment_request_pk"]
        with no_open_year_today(write_conn):
            assert pay_request(client, mock_gateway, req).json() == {"outcome": "PAID_NEEDS_REVIEW"}
            held = fetch(client, admin_h, pk)
            assert "No OPEN financial year" in held["review_reason"]
            refused = client.post(f"{BASE}/payment-requests/{pk}/post", headers=admin_h)
            assert refused.status_code == 422 and "Cannot book it yet" in refused.text
            assert "No OPEN financial year" in fetch(client, admin_h, pk)["review_reason"], "the refusal must keep the reason"
        ok = client.post(f"{BASE}/payment-requests/{pk}/post", headers=admin_h)               # the year is open again
        assert ok.status_code == 200 and ok.json()["transaction_reference"]

    def test_a_scope_closed_after_the_request_holds_the_payment(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        move(client, admin_h, "scopes", u["world"]["scope"]["financial_scope_pk"], "CLOSING")
        assert pay_request(client, mock_gateway, req).json() == {"outcome": "PAID_NEEDS_REVIEW"}
        assert "financial scope" in fetch(client, admin_h, req["upi_payment_request_pk"])["review_reason"].lower()

    def test_a_payment_on_a_cancelled_request_is_held(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        move(client, admin_h, "payment-requests", req["upi_payment_request_pk"], "CANCELLED", remarks="Wrong amount asked")
        assert pay_request(client, mock_gateway, req).json() == {"outcome": "PAID_NEEDS_REVIEW"}
        held = fetch(client, admin_h, req["upi_payment_request_pk"])
        assert held["status"] == "PAID" and held["review_reason"].startswith("PAID_AFTER_CANCELLED")
        assert booked_for(write_conn, req["request_reference"]) == []

    def test_booking_only_applies_to_paid_requests(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        assert client.post(f"{BASE}/payment-requests/{req['upi_payment_request_pk']}/post", headers=admin_h).status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Cancelling, expiry, refresh and the dev simulator
# ═══════════════════════════════════════════════════════════════════════

class TestRequestLifecycle:
    def test_cancelling_needs_a_reason_and_only_works_while_unpaid(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pk = req["upi_payment_request_pk"]
        assert raw_move(client, admin_h, "payment-requests", pk, "CANCELLED").status_code == 422
        assert move(client, admin_h, "payment-requests", pk, "CANCELLED", remarks="Asked in error")["status"] == "CANCELLED"
        assert raw_move(client, admin_h, "payment-requests", pk, "CANCELLED", "again").status_code == 422
        paid = a_request(client, admin_h, u)
        pay_request(client, mock_gateway, paid)
        assert raw_move(client, admin_h, "payment-requests", paid["upi_payment_request_pk"], "CANCELLED", "too late").status_code == 422

    def test_paid_failed_and_expired_cannot_be_set_by_a_person(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        for target in ("PAID", "FAILED", "EXPIRED", "PENDING"):
            assert raw_move(client, admin_h, "payment-requests", req["upi_payment_request_pk"], target, "forcing it").status_code == 422, target

    def test_an_unpaid_request_past_its_expiry_reads_as_expired(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        write_conn.cursor().execute("UPDATE nss.upi_payment_request SET expires_at = NOW() - INTERVAL '1 minute' WHERE upi_payment_request_pk = %s", (req["upi_payment_request_pk"],))
        assert fetch(client, admin_h, req["upi_payment_request_pk"])["status"] == "EXPIRED"
        assert req["upi_payment_request_pk"] in {x["upi_payment_request_pk"] for x in client.get(f"{BASE}/payment-requests", params={"status": "EXPIRED"}, headers=admin_h).json()["items"]}

    def test_refresh_on_a_mock_request_changes_nothing(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        r = client.post(f"{BASE}/payment-requests/{req['upi_payment_request_pk']}/refresh", headers=admin_h)
        assert r.status_code == 200 and r.json()["status"] == "PENDING"

    def test_the_simulator_runs_the_same_path_as_the_real_webhook(self, client, admin_h, register_org_pk, mock_gateway, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u, "500.00")
        r = client.post(f"{BASE}/payment-requests/{req['upi_payment_request_pk']}/mock-pay", headers=admin_h)
        assert r.status_code == 200 and r.json()["status"] == "PAID" and r.json()["receipt_number"]
        assert event_rows(write_conn, req["upi_payment_request_pk"]) == [("POSTED", True)]            # a SIGNED event was processed
        assert len(booked_for(write_conn, req["request_reference"])) == 1

    def test_the_simulator_can_rehearse_a_failure_and_a_mismatch(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        bad = a_request(client, admin_h, u, "500.00")
        r = client.post(f"{BASE}/payment-requests/{bad['upi_payment_request_pk']}/mock-pay", params={"outcome": "paid", "amount": "100.00"}, headers=admin_h)
        assert r.json()["status"] == "PAID" and r.json()["review_reason"].startswith("AMOUNT_MISMATCH")
        failing = a_request(client, admin_h, u)
        assert client.post(f"{BASE}/payment-requests/{failing['upi_payment_request_pk']}/mock-pay", params={"outcome": "failed"}, headers=admin_h).json()["status"] == "FAILED"
        assert client.post(f"{BASE}/payment-requests/{failing['upi_payment_request_pk']}/mock-pay", params={"outcome": "nonsense"}, headers=admin_h).status_code == 422

    def test_the_simulator_respects_scope_and_permissions(self, client, admin_h, other_admin_h, viewer_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        for headers in (other_admin_h, viewer_h):
            assert client.post(f"{BASE}/payment-requests/{req['upi_payment_request_pk']}/mock-pay", headers=headers).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Visibility of requests + no secrets
# ═══════════════════════════════════════════════════════════════════════

class TestVisibilityAndSecrets:
    def test_requests_follow_the_sangha(self, client, admin_h, sakha_admin_h, other_admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pk = req["upi_payment_request_pk"]
        assert client.get(f"{BASE}/payment-requests/{pk}", headers=sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/payment-requests/{pk}", headers=other_admin_h).status_code == 403
        # (looked up by reference: inside the shared test transaction every row has the same created_at, so "newest first" is arbitrary)
        by_ref = {"q": req["request_reference"]}
        assert client.get(f"{BASE}/payment-requests", params=by_ref, headers=other_admin_h).json()["total"] == 0
        assert [x["upi_payment_request_pk"] for x in client.get(f"{BASE}/payment-requests", params=by_ref, headers=sakha_admin_h).json()["items"]] == [pk]

    def test_list_filters(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        a, b = a_request(client, admin_h, u, payer_name="Zebra Payer Unique"), a_request(client, admin_h, u)
        pay_request(client, mock_gateway, b)
        assert [x["upi_payment_request_pk"] for x in client.get(f"{BASE}/payment-requests", params={"q": "Zebra Payer Unique"}, headers=admin_h).json()["items"]] == [a["upi_payment_request_pk"]]
        paid = client.get(f"{BASE}/payment-requests", params={"status": "PAID", "finance_head_pk": u["head"]["finance_head_pk"]}, headers=admin_h).json()["items"]
        assert [x["upi_payment_request_pk"] for x in paid] == [b["upi_payment_request_pk"]]

    def test_no_secret_ever_appears_in_a_response(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = a_request(client, admin_h, u)
        pay_request(client, mock_gateway, req)
        secret_values = (mock_gateway.secret, mock_gateway.ref)
        for url in (f"{BASE}/payment-requests/{req['upi_payment_request_pk']}", f"{BASE}/payment-requests",
                    f"{BASE}/accounts/{u['account']['financial_account_pk']}", f"{BASE}/accounts", f"{BASE}/heads"):
            text = client.get(url, headers=admin_h).text
            assert mock_gateway.secret not in text, url
        # the account does name its credential set (a harmless label) but never carries the secret itself
        assert u["account"]["gateway_credential_ref"] == mock_gateway.ref and "secret" not in json.dumps(u["account"]).lower().replace("gateway_credential_ref", "")


# ═══════════════════════════════════════════════════════════════════════
# A member pays their own Pranami
# ═══════════════════════════════════════════════════════════════════════

class TestMemberSelfService:
    def test_the_member_sees_only_the_payable_pranami_heads_of_their_own_sakha(self, client, admin_h, register_org_pk, other_org_pk, mock_gateway, plain_member_h):
        mine = upi_world(client, admin_h, register_org_pk, mock_gateway)
        theirs = upi_world(client, admin_h, other_org_pk, mock_gateway)                                       # another Sakha
        no_upi = make_head(client, admin_h, register_org_pk, is_pranami=True)                                  # Pranami but not UPI
        not_pranami = make_head(client, admin_h, register_org_pk, allow_upi=True, collection_scope_pk=mine["world"]["scope"]["financial_scope_pk"],
                                collection_account_pk=mine["account"]["financial_account_pk"])                 # UPI but not Pranami
        got = {h["finance_head_pk"] for h in client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json()}
        assert mine["head"]["finance_head_pk"] in got
        assert not got & {theirs["head"]["finance_head_pk"], no_upi["finance_head_pk"], not_pranami["finance_head_pk"]}

    def test_nothing_is_offered_while_the_gateway_is_not_ready(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h, monkeypatch):
        upi_world(client, admin_h, register_org_pk, mock_gateway)
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "")
        assert client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json() == []

    def test_a_member_pays_and_the_payment_shows_up_booked(self, client, admin_h, register_org_pk, mock_gateway, plain_member, plain_member_h, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": u["head"]["finance_head_pk"], "amount": "300.00"}, headers=plain_member_h)
        assert r.status_code == 201, r.text
        mine = r.json()
        # the member's view carries no internals
        assert set(mine) == {"upi_payment_request_pk", "request_reference", "head_name", "amount", "status", "pay_url", "upi_uri", "expires_at", "paid_at", "receipt_number"}
        assert mine["status"] == "PENDING" and mine["upi_uri"].startswith("upi://pay?") and mine["receipt_number"] is None
        # the treasurer sees who is paying - the token, not a field the member could choose
        full = fetch(client, admin_h, mine["upi_payment_request_pk"])
        assert full["payer_sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        # the gateway reports the payment
        assert pay_request(client, mock_gateway, full, payment_id="UTR-MEMBER-1").json() == {"outcome": "POSTED"}
        polled = client.get(f"{BASE}/my-pranami/requests/{mine['upi_payment_request_pk']}", headers=plain_member_h).json()
        assert polled["status"] == "PAID" and polled["receipt_number"].startswith("RCT") and polled["paid_at"]
        items = client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]
        item = next(i for i in items if float(i["amount"]) == 300.0 and any(x["instrument_reference"] == "UTR-MEMBER-1" for x in i["receipts"]))
        assert item["status"] == "POSTED" and item["finance_head_name"] == "UPI Pranami"

    def test_a_browser_saying_it_paid_proves_nothing(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        mine = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": u["head"]["finance_head_pk"], "amount": "300.00"}, headers=plain_member_h).json()
        # polling, however often, never turns a request into a booking; only the signed webhook does
        for _ in range(3):
            assert client.get(f"{BASE}/my-pranami/requests/{mine['upi_payment_request_pk']}", headers=plain_member_h).json()["status"] == "PENDING"
        assert client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"] == []

    def test_only_pranami_upi_heads_of_the_members_own_sakha_are_accepted(self, client, admin_h, register_org_pk, other_org_pk, mock_gateway, plain_member_h):
        theirs = upi_world(client, admin_h, other_org_pk, mock_gateway)
        mine = upi_world(client, admin_h, register_org_pk, mock_gateway)
        not_pranami = make_head(client, admin_h, register_org_pk, allow_upi=True, collection_scope_pk=mine["world"]["scope"]["financial_scope_pk"],
                                collection_account_pk=mine["account"]["financial_account_pk"])
        for pk in (theirs["head"]["finance_head_pk"], not_pranami["finance_head_pk"], FAKE_UUID):
            r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": pk, "amount": "10.00"}, headers=plain_member_h)
            assert r.status_code == 422, pk

    def test_the_payer_cannot_be_chosen(self, client, admin_h, register_org_pk, mock_gateway, plain_member, plain_member_h, write_conn):
        """Extra fields (a payer, another member's id) are ignored: the request is always the signed-in member's."""
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        other = new_member(write_conn, register_org_pk, "FinOther")
        r = client.post(f"{BASE}/my-pranami/pay", headers=plain_member_h, json={
            "finance_head_pk": u["head"]["finance_head_pk"], "amount": "10.00", "sangha_sevi_id": other["sangha_sevi_id"],
            "payer_person_pk": other["person_pk"], "payer_name": "Someone else"})
        assert r.status_code == 201
        assert fetch(client, admin_h, r.json()["upi_payment_request_pk"])["payer_sangha_sevi_id"] == plain_member["sangha_sevi_id"]

    def test_a_member_can_only_read_their_own_requests(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h, write_conn):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        mine = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": u["head"]["finance_head_pk"], "amount": "10.00"}, headers=plain_member_h).json()
        other = new_member(write_conn, register_org_pk, "FinOther2")
        other_h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        assert client.get(f"{BASE}/my-pranami/requests/{mine['upi_payment_request_pk']}", headers=other_h).status_code == 404
        assert client.get(f"{BASE}/my-pranami/requests/{FAKE_UUID}", headers=plain_member_h).status_code == 404

    def test_too_many_unpaid_requests_are_refused(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        body = {"finance_head_pk": u["head"]["finance_head_pk"], "amount": "10.00"}
        codes = [client.post(f"{BASE}/my-pranami/pay", json=body, headers=plain_member_h).status_code for _ in range(6)]
        assert codes == [201] * 5 + [429]

    @pytest.mark.parametrize("amount", ["0", "-1", "1.234", "100000.01", "abc"])
    def test_amount_rules(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h, amount):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": u["head"]["finance_head_pk"], "amount": amount}, headers=plain_member_h).status_code == 422

    def test_a_request_the_member_started_shows_to_the_treasurer_but_is_not_a_book_entry(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        mine = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": u["head"]["finance_head_pk"], "amount": "10.00"}, headers=plain_member_h).json()
        assert client.get(f"{BASE}/payment-requests", params={"q": mine["request_reference"]}, headers=admin_h).json()["total"] == 1
        assert client.get(f"{BASE}/transactions", params={"q": mine["request_reference"]}, headers=admin_h).json()["total"] == 0
