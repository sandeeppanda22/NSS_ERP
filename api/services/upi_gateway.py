"""
UPI payment-gateway adapters for Finance (Tier 12).

One small, provider-agnostic interface so the rest of the app (api/routers/
finance_upi.py) never knows which gateway collected the money:

  create_order()       ask the gateway for a payable order / link
  verify_signature()   check that a webhook really came from the gateway
  peek_order_id()      read the order id out of an UNTRUSTED payload (only to
                       find which request - and therefore which credential set -
                       the webhook claims to be about; nothing is believed until
                       the signature has been verified with THAT set's secret)
  parse_event()        turn a verified payload into a GatewayEvent
  fetch_order_status() poll the gateway when a webhook was missed

Security model (the reason this module exists):
  * SECRETS NEVER LIVE IN THE DATABASE. A financial_account names a credential
    set (gateway_credential_ref, e.g. SAKHA_A); the key id / key secret /
    webhook secret are read from the server environment:
        UPI_<REF>_KEY_ID, UPI_<REF>_KEY_SECRET, UPI_<REF>_WEBHOOK_SECRET
  * A provider can only be used when listed in UPI_GATEWAY_ENABLED_PROVIDERS
    (default empty = OFF), so a fresh deployment exposes no payment surface.
  * Webhook signatures are compared in constant time (hmac.compare_digest).
  * Money is Decimal; providers that count in paise are converted here, once.

Providers:
  MOCK       development / demo / tests. Its "gateway" is this module: it signs
             its own webhooks (build_mock_event) so the whole flow can be driven
             without any money or network. NEVER enable on a production database.
  RAZORPAY   Payment Links API (UPI-only links) written from Razorpay's public
             API reference. **NOT YET EXERCISED against Razorpay's sandbox or
             live API** - it has had no credentials and no network access. Treat
             it as unverified until it has been tried end to end in their test
             mode.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode

from api.config import settings

# Gateway call timeout (seconds) - a hung provider must not hold a pool connection for long.
HTTP_TIMEOUT = 10.0
_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")


class GatewayError(Exception):
    """The gateway refused or failed a call (shown to the caller as a 502)."""


class GatewayUnavailable(GatewayError):
    """UPI collection is switched off or not configured for this account (503)."""


@dataclass(frozen=True)
class Credentials:
    key_id: str
    key_secret: str
    webhook_secret: str


@dataclass(frozen=True)
class GatewayOrder:
    provider_order_id: str
    pay_url: str | None          # hosted payment page / short link
    upi_uri: str | None          # upi://pay?... deep link for UPI apps
    expires_at: datetime


@dataclass(frozen=True)
class GatewayEvent:
    event_id: str
    event_type: str
    provider_order_id: str | None
    provider_payment_id: str | None
    amount: Decimal | None       # rupees, two places; None when the event carries no amount
    status: str                  # PAID | FAILED | EXPIRED | IGNORED
    method: str | None = None


# ═══════════════════════════════════════════════════════════════════════
# Credentials + provider registry
# ═══════════════════════════════════════════════════════════════════════

def credentials_for(ref: str | None) -> Credentials:
    """Read a credential set from the environment; raise GatewayUnavailable when it is not fully configured."""
    if not ref or not _REF_RE.match(ref):
        raise GatewayUnavailable("This account has no valid gateway credential reference.")
    prefix = f"UPI_{ref}_"
    key_id = os.environ.get(prefix + "KEY_ID", "")
    key_secret = os.environ.get(prefix + "KEY_SECRET", "")
    webhook_secret = os.environ.get(prefix + "WEBHOOK_SECRET", "")
    if not (key_id and key_secret and webhook_secret):
        raise GatewayUnavailable(f"Gateway credential set {ref} is not configured on this server.")
    return Credentials(key_id, key_secret, webhook_secret)


def enabled_providers() -> frozenset[str]:
    return frozenset(p.strip().upper() for p in settings.UPI_GATEWAY_ENABLED_PROVIDERS.split(",") if p.strip())


def to_paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


def from_paise(value) -> Decimal | None:
    try:
        return (Decimal(str(value)) / 100).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def build_upi_uri(*, vpa: str, payee_name: str, amount: Decimal, reference: str, note: str | None = None) -> str:
    """The standard UPI deep link (NPCI): opens any UPI app pre-filled."""
    params = {"pa": vpa, "pn": payee_name, "am": f"{amount:.2f}", "cu": "INR", "tr": reference, "tn": (note or reference)[:80]}
    return "upi://pay?" + urlencode(params, quote_via=quote)


def sign(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _same_signature(expected: str, supplied: str | None) -> bool:
    return bool(supplied) and hmac.compare_digest(expected.encode("utf-8"), supplied.strip().encode("utf-8"))


class Provider(ABC):
    name: str = ""
    signature_header: str = ""

    @abstractmethod
    def create_order(self, *, creds: Credentials, reference: str, amount: Decimal, description: str,
                     payer_name: str | None, expires_at: datetime, vpa: str | None, payee_name: str,
                     merchant_ref: str | None) -> GatewayOrder: ...

    def verify_signature(self, *, secret: str, headers: dict, raw_body: bytes) -> bool:
        supplied = {k.lower(): v for k, v in headers.items()}.get(self.signature_header.lower())
        return _same_signature(sign(secret, raw_body), supplied)

    @abstractmethod
    def peek_order_id(self, payload: dict) -> str | None: ...

    @abstractmethod
    def parse_event(self, headers: dict, payload: dict, raw_body: bytes) -> GatewayEvent: ...

    def fetch_order_status(self, *, creds: Credentials, provider_order_id: str, merchant_ref: str | None) -> GatewayEvent | None:
        return None


# ═══════════════════════════════════════════════════════════════════════
# MOCK - development / demo / tests
# ═══════════════════════════════════════════════════════════════════════

class MockProvider(Provider):
    """
    A pretend gateway. create_order() returns a UPI deep link and no hosted page;
    the "payment" is simulated by build_mock_event(), which produces exactly what a
    real gateway would POST to the webhook (a signed JSON body). No money moves.
    """

    name = "MOCK"
    signature_header = "X-Mock-Signature"

    def create_order(self, *, creds, reference, amount, description, payer_name, expires_at, vpa, payee_name, merchant_ref):
        order_id = "mock_" + secrets.token_hex(8)
        uri = build_upi_uri(vpa=vpa, payee_name=payee_name, amount=amount, reference=reference, note=description) if vpa else None
        return GatewayOrder(order_id, None, uri, expires_at)

    def peek_order_id(self, payload):
        v = payload.get("order_id") if isinstance(payload, dict) else None
        return v if isinstance(v, str) else None

    def parse_event(self, headers, payload, raw_body):
        kind = str(payload.get("type", ""))
        status = {"payment.paid": "PAID", "payment.failed": "FAILED", "order.expired": "EXPIRED"}.get(kind, "IGNORED")
        try:
            amount = Decimal(str(payload["amount"])).quantize(Decimal("0.01")) if payload.get("amount") is not None else None
        except (InvalidOperation, ValueError):
            amount = None
        return GatewayEvent(
            event_id=str(payload.get("event_id") or hashlib.sha256(raw_body).hexdigest()),
            event_type=kind, provider_order_id=self.peek_order_id(payload),
            provider_payment_id=payload.get("payment_id"), amount=amount, status=status, method="UPI",
        )


def build_mock_event(*, secret: str, order_id: str, kind: str = "payment.paid", amount: Decimal | None = None,
                     payment_id: str | None = None, event_id: str | None = None) -> tuple[bytes, dict]:
    """(raw body, headers) of a MOCK webhook, signed with *secret* - for the dev 'mock-pay' action and the tests."""
    body = {
        "event_id": event_id or "evt_" + secrets.token_hex(8), "type": kind, "order_id": order_id,
        "payment_id": payment_id or "mockpay_" + secrets.token_hex(6),
        "amount": None if amount is None else f"{amount:.2f}", "currency": "INR",
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return raw, {"X-Mock-Signature": sign(secret, raw), "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════════════
# RAZORPAY - Payment Links (UPI-only). UNVERIFIED against the live/sandbox API.
# ═══════════════════════════════════════════════════════════════════════

class RazorpayProvider(Provider):
    name = "RAZORPAY"
    signature_header = "X-Razorpay-Signature"
    API = "https://api.razorpay.com/v1"           # fixed: never built from input

    def _client(self):
        import httpx                                # imported lazily: only live use needs it
        return httpx.Client(timeout=HTTP_TIMEOUT)

    def create_order(self, *, creds, reference, amount, description, payer_name, expires_at, vpa, payee_name, merchant_ref):
        body = {
            "amount": to_paise(amount), "currency": "INR", "accept_partial": False, "reference_id": reference,
            "description": description[:2000], "upi_link": True,
            "expire_by": int(expires_at.timestamp()),
            "notify": {"sms": False, "email": False}, "reminder_enable": False,
        }
        if payer_name:
            body["customer"] = {"name": payer_name[:100]}
        headers = {"X-Razorpay-Account": merchant_ref} if merchant_ref else {}
        try:
            with self._client() as http:
                r = http.post(f"{self.API}/payment_links", json=body, auth=(creds.key_id, creds.key_secret), headers=headers)
        except Exception as exc:                     # network / TLS / timeout
            raise GatewayError("The payment gateway could not be reached.") from exc
        if r.status_code >= 400:
            raise GatewayError(f"The payment gateway refused the request (HTTP {r.status_code}).")
        data = r.json()
        if not data.get("id") or not data.get("short_url"):
            raise GatewayError("The payment gateway returned an unexpected response.")
        return GatewayOrder(data["id"], data["short_url"], None, expires_at)

    def peek_order_id(self, payload):
        try:
            return payload["payload"]["payment_link"]["entity"]["id"]
        except (KeyError, TypeError):
            return None

    def parse_event(self, headers, payload, raw_body):
        h = {k.lower(): v for k, v in headers.items()}
        event = str(payload.get("event", ""))
        status = {"payment_link.paid": "PAID", "payment_link.expired": "EXPIRED", "payment_link.cancelled": "EXPIRED"}.get(event, "IGNORED")
        link = (payload.get("payload", {}).get("payment_link", {}) or {}).get("entity", {}) or {}
        pay = (payload.get("payload", {}).get("payment", {}) or {}).get("entity", {}) or {}
        return GatewayEvent(
            event_id=h.get("x-razorpay-event-id") or hashlib.sha256(raw_body).hexdigest(),
            event_type=event, provider_order_id=link.get("id"), provider_payment_id=pay.get("id"),
            amount=from_paise(link.get("amount_paid")) if status == "PAID" else None,
            status=status, method=pay.get("method"),
        )

    def fetch_order_status(self, *, creds, provider_order_id, merchant_ref):
        headers = {"X-Razorpay-Account": merchant_ref} if merchant_ref else {}
        try:
            with self._client() as http:
                r = http.get(f"{self.API}/payment_links/{quote(provider_order_id, safe='')}", auth=(creds.key_id, creds.key_secret), headers=headers)
        except Exception as exc:
            raise GatewayError("The payment gateway could not be reached.") from exc
        if r.status_code >= 400:
            raise GatewayError(f"The payment gateway refused the request (HTTP {r.status_code}).")
        data = r.json()
        status = {"paid": "PAID", "expired": "EXPIRED", "cancelled": "EXPIRED"}.get(str(data.get("status")), "IGNORED")
        if status == "IGNORED":
            return None
        payments = data.get("payments") or []
        payment_id = (payments[0].get("payment_id") if payments and isinstance(payments[0], dict) else None)
        return GatewayEvent(
            event_id=f"poll:{provider_order_id}:{status}", event_type="poll." + str(data.get("status")),
            provider_order_id=provider_order_id, provider_payment_id=payment_id,
            amount=from_paise(data.get("amount_paid")) if status == "PAID" else None, status=status, method="UPI",
        )


PROVIDERS: dict[str, Provider] = {p.name: p for p in (MockProvider(), RazorpayProvider())}


def get_provider(name: str | None) -> Provider:
    """The adapter for *name*, only if it is registered AND enabled on this server."""
    key = (name or "").upper()
    if key not in PROVIDERS:
        raise GatewayUnavailable(f"Unknown payment gateway {name!r}.")
    if key not in enabled_providers():
        raise GatewayUnavailable(f"The {key} payment gateway is not enabled on this server.")
    return PROVIDERS[key]
