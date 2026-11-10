"""
UPI gateway adapters (api/services/upi_gateway.py) - DB-free, network-free.

Run with --noconftest. These pin the security properties everything else relies on:
secrets only from the environment, providers off unless enabled, constant-time
signature checks that reject tampering, and exact money conversion.

The RAZORPAY adapter is exercised only against a FAKE http client built from the shape
of Razorpay's public API reference - it has never been run against Razorpay itself.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from api.config import settings
from api.services import upi_gateway as gw

pytestmark = pytest.mark.integration  # file lives with the API tests; needs no database

SECRET = "whsec_test_secret"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "MOCK,RAZORPAY")


@pytest.fixture
def creds_env(monkeypatch):
    monkeypatch.setenv("UPI_SAKHA_A_KEY_ID", "key_id")
    monkeypatch.setenv("UPI_SAKHA_A_KEY_SECRET", "key_secret")
    monkeypatch.setenv("UPI_SAKHA_A_WEBHOOK_SECRET", SECRET)


class TestCredentials:
    def test_read_from_the_environment_only(self, creds_env):
        c = gw.credentials_for("SAKHA_A")
        assert (c.key_id, c.key_secret, c.webhook_secret) == ("key_id", "key_secret", SECRET)

    @pytest.mark.parametrize("missing", ["KEY_ID", "KEY_SECRET", "WEBHOOK_SECRET"])
    def test_a_partial_set_is_unavailable(self, creds_env, monkeypatch, missing):
        monkeypatch.delenv(f"UPI_SAKHA_A_{missing}")
        with pytest.raises(gw.GatewayUnavailable):
            gw.credentials_for("SAKHA_A")

    @pytest.mark.parametrize("ref", [None, "", "lower", "HAS SPACE", "A" * 41, "1START", "A;B", "../X"])
    def test_a_malformed_reference_is_rejected_before_any_lookup(self, ref):
        with pytest.raises(gw.GatewayUnavailable):
            gw.credentials_for(ref)

    def test_an_unconfigured_set_is_unavailable(self):
        with pytest.raises(gw.GatewayUnavailable):
            gw.credentials_for("NEVER_CONFIGURED_SET")


class TestProviderGate:
    def test_everything_is_off_by_default(self, monkeypatch):
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "")
        assert gw.enabled_providers() == frozenset()
        for name in ("MOCK", "RAZORPAY"):
            with pytest.raises(gw.GatewayUnavailable):
                gw.get_provider(name)

    def test_only_listed_providers_are_usable(self, monkeypatch):
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", " mock ")
        assert gw.get_provider("MOCK").name == "MOCK"
        assert gw.get_provider("mock").name == "MOCK"
        with pytest.raises(gw.GatewayUnavailable):
            gw.get_provider("RAZORPAY")

    @pytest.mark.parametrize("name", [None, "", "PAYPAL", "mock; drop"])
    def test_unknown_providers_are_unavailable(self, enabled, name):
        with pytest.raises(gw.GatewayUnavailable):
            gw.get_provider(name)


class TestSignatures:
    def _provider(self):
        return gw.PROVIDERS["MOCK"]

    def test_a_correct_signature_verifies(self):
        raw, headers = gw.build_mock_event(secret=SECRET, order_id="o1", amount=Decimal("500"))
        assert self._provider().verify_signature(secret=SECRET, headers=headers, raw_body=raw)

    def test_header_name_is_case_insensitive(self):
        raw, headers = gw.build_mock_event(secret=SECRET, order_id="o1")
        lowered = {k.lower(): v for k, v in headers.items()}
        assert self._provider().verify_signature(secret=SECRET, headers=lowered, raw_body=raw)

    def test_tampering_with_the_body_is_detected(self):
        raw, headers = gw.build_mock_event(secret=SECRET, order_id="o1", amount=Decimal("500"))
        forged = raw.replace(b"500.00", b"5000.00")
        assert forged != raw
        assert not self._provider().verify_signature(secret=SECRET, headers=headers, raw_body=forged)

    def test_the_wrong_secret_is_rejected(self):
        raw, headers = gw.build_mock_event(secret="another-secret", order_id="o1")
        assert not self._provider().verify_signature(secret=SECRET, headers=headers, raw_body=raw)

    @pytest.mark.parametrize("headers", [{}, {"X-Mock-Signature": ""}, {"X-Mock-Signature": "   "}, {"X-Other": "x"}])
    def test_a_missing_or_empty_signature_is_rejected(self, headers):
        raw, _ = gw.build_mock_event(secret=SECRET, order_id="o1")
        assert not self._provider().verify_signature(secret=SECRET, headers=headers, raw_body=raw)

    def test_comparison_is_constant_time(self, monkeypatch):
        calls = []
        real = gw.hmac.compare_digest
        monkeypatch.setattr(gw.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
        raw, headers = gw.build_mock_event(secret=SECRET, order_id="o1")
        self._provider().verify_signature(secret=SECRET, headers=headers, raw_body=raw)
        assert calls, "signatures must be compared with hmac.compare_digest"

    def test_razorpay_signature_is_hmac_sha256_of_the_raw_body(self):
        raw = b'{"event":"payment_link.paid"}'
        p = gw.PROVIDERS["RAZORPAY"]
        assert p.verify_signature(secret=SECRET, headers={"X-Razorpay-Signature": gw.sign(SECRET, raw)}, raw_body=raw)
        assert not p.verify_signature(secret=SECRET, headers={"X-Razorpay-Signature": gw.sign(SECRET, raw + b" ")}, raw_body=raw)


class TestMockEvents:
    def test_paid_event_is_parsed(self):
        raw, headers = gw.build_mock_event(secret=SECRET, order_id="mock_1", amount=Decimal("250.5"), payment_id="p9", event_id="e9")
        ev = gw.PROVIDERS["MOCK"].parse_event(headers, json.loads(raw), raw)
        assert (ev.event_id, ev.status, ev.provider_order_id, ev.provider_payment_id, ev.amount) == ("e9", "PAID", "mock_1", "p9", Decimal("250.50"))

    @pytest.mark.parametrize("kind,status", [("payment.failed", "FAILED"), ("order.expired", "EXPIRED"), ("something.else", "IGNORED")])
    def test_other_event_kinds(self, kind, status):
        raw, headers = gw.build_mock_event(secret=SECRET, order_id="mock_1", kind=kind)
        assert gw.PROVIDERS["MOCK"].parse_event(headers, json.loads(raw), raw).status == status

    def test_a_garbage_amount_becomes_none_not_a_crash(self):
        p = gw.PROVIDERS["MOCK"]
        ev = p.parse_event({}, {"type": "payment.paid", "order_id": "x", "amount": "not-money"}, b"{}")
        assert ev.amount is None

    def test_peek_ignores_non_string_order_ids(self):
        p = gw.PROVIDERS["MOCK"]
        assert p.peek_order_id({"order_id": 5}) is None and p.peek_order_id({}) is None and p.peek_order_id("x") is None

    def test_mock_create_order_has_a_upi_link_and_no_hosted_page(self):
        order = gw.PROVIDERS["MOCK"].create_order(
            creds=None, reference="PRQ1", amount=Decimal("500"), description="Annual Pranami", payer_name=None,
            expires_at=NOW + timedelta(minutes=30), vpa="sakha@okbank", payee_name="Sakha Sangha", merchant_ref=None)
        assert order.provider_order_id.startswith("mock_") and order.pay_url is None
        assert order.upi_uri.startswith("upi://pay?") and "pa=sakha%40okbank" in order.upi_uri and "am=500.00" in order.upi_uri


class TestMoney:
    @pytest.mark.parametrize("rupees,paise", [("500", 50000), ("0.01", 1), ("1234.56", 123456), ("99999999999.99", 9999999999999)])
    def test_rupees_to_paise_is_exact(self, rupees, paise):
        assert gw.to_paise(Decimal(rupees)) == paise

    @pytest.mark.parametrize("paise,rupees", [(50000, "500.00"), (1, "0.01"), ("123456", "1234.56")])
    def test_paise_to_rupees_is_exact(self, paise, rupees):
        assert gw.from_paise(paise) == Decimal(rupees)

    @pytest.mark.parametrize("bad", [None, "abc", "", object()])
    def test_unparseable_paise_is_none(self, bad):
        assert gw.from_paise(bad) is None


class TestUpiUri:
    def test_special_characters_are_percent_encoded(self):
        uri = gw.build_upi_uri(vpa="a.b@bank", payee_name="Ram & Sons", amount=Decimal("10"), reference="PRQ 1", note="x&y=z")
        assert "&pn=Ram%20%26%20Sons" in uri and "tn=x%26y%3Dz" in uri and "tr=PRQ%201" in uri
        assert uri.count("?") == 1


class _FakeResponse:
    def __init__(self, status_code, data):
        self.status_code, self._d = status_code, data

    def json(self):
        return self._d


class _FakeHttp:
    """Stands in for httpx.Client: records the call, returns a canned response."""

    calls: list = []

    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, auth=None, headers=None):
        _FakeHttp.calls.append(("POST", url, json, auth, headers))
        return self.response

    def get(self, url, auth=None, headers=None):
        _FakeHttp.calls.append(("GET", url, None, auth, headers))
        return self.response


class TestRazorpayAdapterAgainstAFake:
    """Shape checks only - NOT proof the live API behaves like this."""

    def _p(self, monkeypatch, response):
        _FakeHttp.calls = []
        p = gw.PROVIDERS["RAZORPAY"]
        monkeypatch.setattr(p, "_client", lambda: _FakeHttp(response))
        return p

    def _order(self, p, merchant_ref=None):
        return p.create_order(creds=gw.Credentials("kid", "ksec", SECRET), reference="PRQ7", amount=Decimal("500.50"),
                              description="Annual Pranami", payer_name="Ram", expires_at=NOW + timedelta(minutes=30),
                              vpa=None, payee_name="Sakha", merchant_ref=merchant_ref)

    def test_create_sends_paise_a_upi_only_link_and_basic_auth(self, monkeypatch):
        p = self._p(monkeypatch, _FakeResponse(200, {"id": "plink_1", "short_url": "https://rzp.io/i/abc"}))
        order = self._order(p)
        method, url, body, auth, headers = _FakeHttp.calls[0]
        assert url == "https://api.razorpay.com/v1/payment_links" and auth == ("kid", "ksec")
        assert body["amount"] == 50050 and body["currency"] == "INR" and body["upi_link"] is True and body["accept_partial"] is False
        assert body["reference_id"] == "PRQ7" and body["expire_by"] == int((NOW + timedelta(minutes=30)).timestamp())
        assert (order.provider_order_id, order.pay_url) == ("plink_1", "https://rzp.io/i/abc")
        assert headers == {}

    def test_merchant_ref_is_sent_as_the_account_header(self, monkeypatch):
        p = self._p(monkeypatch, _FakeResponse(200, {"id": "plink_1", "short_url": "https://rzp.io/i/abc"}))
        self._order(p, merchant_ref="acc_123")
        assert _FakeHttp.calls[0][4] == {"X-Razorpay-Account": "acc_123"}

    @pytest.mark.parametrize("status,data", [(400, {}), (500, {}), (200, {}), (200, {"id": "x"})])
    def test_refusals_and_odd_responses_become_gateway_errors(self, monkeypatch, status, data):
        p = self._p(monkeypatch, _FakeResponse(status, data))
        with pytest.raises(gw.GatewayError):
            self._order(p)

    def test_network_failure_becomes_a_gateway_error_without_leaking_details(self, monkeypatch):
        p = gw.PROVIDERS["RAZORPAY"]

        class Boom(_FakeHttp):
            def post(self, *a, **k):
                raise OSError("secret.internal.host: connection refused")

        monkeypatch.setattr(p, "_client", lambda: Boom(None))
        with pytest.raises(gw.GatewayError) as exc:
            self._order(p)
        assert "secret.internal.host" not in str(exc.value)

    def test_paid_webhook_is_parsed(self):
        payload = {"event": "payment_link.paid", "payload": {
            "payment_link": {"entity": {"id": "plink_1", "amount_paid": 50050, "status": "paid"}},
            "payment": {"entity": {"id": "pay_9", "method": "upi"}}}}
        raw = json.dumps(payload).encode()
        p = gw.PROVIDERS["RAZORPAY"]
        assert p.peek_order_id(payload) == "plink_1"
        ev = p.parse_event({"X-Razorpay-Event-Id": "evt_1"}, payload, raw)
        assert (ev.event_id, ev.status, ev.provider_order_id, ev.provider_payment_id, ev.amount) == ("evt_1", "PAID", "plink_1", "pay_9", Decimal("500.50"))

    def test_expired_and_unknown_events(self):
        p = gw.PROVIDERS["RAZORPAY"]
        base = {"payload": {"payment_link": {"entity": {"id": "plink_1"}}}}
        assert p.parse_event({}, {"event": "payment_link.expired", **base}, b"{}").status == "EXPIRED"
        assert p.parse_event({}, {"event": "payment.failed", **base}, b"{}").status == "IGNORED"

    def test_event_id_falls_back_to_a_body_hash(self):
        ev = gw.PROVIDERS["RAZORPAY"].parse_event({}, {"event": "x"}, b"abc")
        assert len(ev.event_id) == 64

    def test_poll_maps_status_and_never_trusts_a_non_paid_link(self, monkeypatch):
        p = self._p(monkeypatch, _FakeResponse(200, {"status": "paid", "amount_paid": 50050, "payments": [{"payment_id": "pay_9"}]}))
        ev = p.fetch_order_status(creds=gw.Credentials("k", "s", SECRET), provider_order_id="plink_1", merchant_ref=None)
        assert (ev.status, ev.amount, ev.provider_payment_id) == ("PAID", Decimal("500.50"), "pay_9")
        p = self._p(monkeypatch, _FakeResponse(200, {"status": "created"}))
        assert p.fetch_order_status(creds=gw.Credentials("k", "s", SECRET), provider_order_id="plink_1", merchant_ref=None) is None

    def test_poll_url_encodes_the_order_id(self, monkeypatch):
        p = self._p(monkeypatch, _FakeResponse(200, {"status": "created"}))
        p.fetch_order_status(creds=gw.Credentials("k", "s", SECRET), provider_order_id="../../x?y", merchant_ref=None)
        assert _FakeHttp.calls[0][1] == "https://api.razorpay.com/v1/payment_links/..%2F..%2Fx%3Fy"
