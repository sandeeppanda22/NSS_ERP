"""
The Razorpay adapter (real httpx client) against the local rehearsal server's handler (scripts/fake_razorpay.py) - DB-free, no account and
no network permission needed (the handler is called in-process; run the script itself for the click-through rehearsal).

It proves the adapter speaks HTTP correctly (auth, JSON, paise, UPI-link flags, the 15-minute rule, error handling) and that the signed webhook
the rehearsal server sends is accepted and parsed by the adapter exactly as the app's webhook handler would. It is NOT proof that Razorpay
itself behaves like this: the rehearsal server was written from the same public API reference as the adapter.
"""

import importlib.util
import io
import json
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from api.config import settings
from api.services import upi_gateway as gw

pytestmark = pytest.mark.integration  # lives with the API tests; needs no database

httpx = pytest.importorskip("httpx")

_spec = importlib.util.spec_from_file_location("fake_razorpay", Path(__file__).resolve().parents[2] / "scripts" / "fake_razorpay.py")
fake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake)

WEBHOOK_SECRET = "local-webhook-secret"
CREDS = gw.Credentials("rzp_test_local", "local-secret", WEBHOOK_SECRET)


class _Receiver:
    """Stands in for the app's webhook endpoint: records what the rehearsal server POSTs (urllib is replaced, so no port is opened)."""

    got: list = []


class _Resp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"ok"


class _Sock:
    """The least a socket must do for BaseHTTPRequestHandler: lets the handler run in-process, so the tests need no network permission."""

    def __init__(self, data: bytes):
        self.rfile, self.out = io.BytesIO(data), io.BytesIO()

    def makefile(self, mode, *a, **k):
        return self.rfile

    def sendall(self, b):
        self.out.write(b)


def _call(srv, method: str, path: str, body: bytes = b"", headers: dict | None = None) -> tuple[int, bytes]:
    head = f"{method} {path} HTTP/1.0\r\nHost: 127.0.0.1\r\nContent-Length: {len(body)}\r\n"
    head += "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items()) + "\r\n"
    sock = _Sock(head.encode() + body)
    fake._Handler(sock, ("127.0.0.1", 0), srv)
    raw = sock.out.getvalue()
    status = int(raw.split(b" ", 2)[1])
    return status, raw.split(b"\r\n\r\n", 1)[1]


@pytest.fixture
def world(monkeypatch):
    srv = fake.FakeRazorpay.__new__(fake.FakeRazorpay)              # no listening socket: requests are handed to the handler directly
    srv.webhook_url, srv.webhook_secret = "http://app.invalid/hook", WEBHOOK_SECRET
    srv.links, srv.sent_webhooks, srv.lock, srv.server_address = {}, [], threading.Lock(), ("127.0.0.1", 8099)
    _Receiver.got = []

    def deliver(req, timeout=None):
        _Receiver.got.append((dict(req.header_items()), req.data))
        return _Resp()

    monkeypatch.setattr(fake.urllib.request, "urlopen", deliver)

    def route(request: httpx.Request) -> httpx.Response:            # the adapter's REAL httpx client, answered by the rehearsal handler
        status, body = _call(srv, request.method, request.url.raw_path.decode(), request.content,
                             {k: v for k, v in request.headers.items() if k.lower() == "authorization"})
        return httpx.Response(status, content=body, headers={"Content-Type": "application/json"})

    # the INSTANCE, not the class: another test file patches the instance, which would otherwise shadow a class-level patch
    monkeypatch.setattr(gw.PROVIDERS["RAZORPAY"], "_client", lambda: httpx.Client(transport=httpx.MockTransport(route)))
    monkeypatch.setenv("RAZORPAY_API_BASE", "http://127.0.0.1:8099/v1")
    monkeypatch.setattr(settings, "DB_HOST", "localhost")                       # the override is honoured on a development install only
    monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "RAZORPAY")
    return srv


def _order(expires_in=timedelta(minutes=30), amount=Decimal("500.50")):
    p = gw.get_provider("RAZORPAY")
    return p.create_order(creds=CREDS, reference="PRQ7", amount=amount, description="Annual Pranami", payer_name="Ram",
                          expires_at=datetime.now(timezone.utc) + expires_in, vpa=None, payee_name="Sakha", merchant_ref=None)


class TestARealRoundTrip:
    def test_a_link_is_created_in_paise_and_can_be_polled(self, world):
        order = _order()
        assert order.provider_order_id.startswith("plink_") and order.pay_url.startswith("http://127.0.0.1:8099/pay/")
        assert world.links[order.provider_order_id]["amount"] == 50050
        assert gw.get_provider("RAZORPAY").fetch_order_status(creds=CREDS, provider_order_id=order.provider_order_id, merchant_ref=None) is None   # unpaid

    def test_paying_sends_a_signed_webhook_the_adapter_accepts_and_parses(self, world):
        order = _order()
        link = world.links[order.provider_order_id]
        link["status"], link["amount_paid"] = "paid", link["amount"]
        code, _ = world.announce(link, "payment_link.paid")
        assert code == 200
        headers, raw = _Receiver.got[0]
        provider = gw.get_provider("RAZORPAY")
        assert provider.verify_signature(secret=WEBHOOK_SECRET, headers=headers, raw_body=raw)
        assert not provider.verify_signature(secret="another-secret", headers=headers, raw_body=raw)
        assert not provider.verify_signature(secret=WEBHOOK_SECRET, headers=headers, raw_body=raw + b" ")           # one changed byte
        event = provider.parse_event(headers, json.loads(raw), raw)
        assert (event.status, event.provider_order_id, event.amount) == ("PAID", order.provider_order_id, Decimal("500.50"))
        assert event.provider_payment_id and event.event_id.startswith("evt_")

    def test_polling_a_paid_link_reports_it_paid(self, world):
        order = _order()
        link = world.links[order.provider_order_id]
        link["status"], link["amount_paid"] = "paid", link["amount"]
        ev = gw.get_provider("RAZORPAY").fetch_order_status(creds=CREDS, provider_order_id=order.provider_order_id, merchant_ref=None)
        assert (ev.status, ev.amount) == ("PAID", Decimal("500.50"))

    def test_an_expired_link_webhook_is_parsed_as_expired(self, world):
        order = _order()
        link = world.links[order.provider_order_id]
        link["status"] = "expired"
        world.announce(link, "payment_link.expired")
        headers, raw = _Receiver.got[0]
        assert gw.get_provider("RAZORPAY").parse_event(headers, json.loads(raw), raw).status == "EXPIRED"


class TestTheRulesRazorpayEnforcesAreRespected:
    def test_a_window_under_fifteen_minutes_is_refused_by_the_server_as_it_would_be_by_razorpay(self, world):
        with pytest.raises(gw.GatewayError):
            _order(expires_in=timedelta(minutes=10))

    def test_a_refusal_never_leaks_the_response_body(self, world):
        with pytest.raises(gw.GatewayError) as exc:
            _order(amount=Decimal("0.50"))                                                                         # under the 1 rupee minimum
        assert "HTTP 400" in str(exc.value) and "amount" not in str(exc.value)


class TestTheOverrideIsDevelopmentOnly:
    def test_a_remote_database_ignores_it(self, world, monkeypatch):
        monkeypatch.setattr(settings, "DB_HOST", "ep-cool-123.neon.tech")
        assert gw.get_provider("RAZORPAY")._api() == "https://api.razorpay.com/v1"

    def test_a_non_local_target_is_ignored_even_on_a_development_install(self, monkeypatch):
        monkeypatch.setattr(settings, "DB_HOST", "localhost")
        for target in ("https://evil.example/v1", "http://10.0.0.5:8099/v1", "http://127.0.0.1.evil.example/v1"):
            monkeypatch.setenv("RAZORPAY_API_BASE", target)
            assert gw.get_provider("RAZORPAY")._api() == "https://api.razorpay.com/v1", target


class TestTheRehearsalPages:
    def test_the_pay_page_and_the_pay_button_book_the_link_and_announce_it(self, world):
        order = _order()
        status, html = _call(world, "GET", f"/pay/{order.provider_order_id}")
        assert status == 200 and b"Pay (success)" in html
        status, html = _call(world, "POST", f"/pay/{order.provider_order_id}")
        assert status == 200 and b"Webhook to the app: <b>200</b>" in html
        assert world.links[order.provider_order_id]["status"] == "paid" and len(_Receiver.got) == 1
        status, html = _call(world, "GET", f"/pay/{order.provider_order_id}")
        assert b"Pay (success)" not in html                                          # a paid link offers no second payment

    def test_requests_without_credentials_are_refused_like_razorpay_does(self, world):
        assert _call(world, "POST", "/v1/payment_links", b"{}")[0] == 401
        assert _call(world, "GET", "/v1/payment_links/plink_x")[0] == 401
