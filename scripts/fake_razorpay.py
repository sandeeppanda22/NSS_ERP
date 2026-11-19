"""
A LOCAL stand-in for the part of Razorpay's Payment Links API that NSS ERP uses - for rehearsing the whole Razorpay flow
before a Razorpay account exists. NOT Razorpay: it was written from Razorpay's public API reference, accepts any API key,
and moves no money. It lets you click through exactly what a real payer would do:

  1. the app creates a payment link here        POST /v1/payment_links       (what RazorpayProvider.create_order calls)
  2. you open the link and press "Pay"          GET  /pay/<id>  ->  POST /pay/<id>
  3. this server POSTs the signed webhook to the app, in Razorpay's shape (event payment_link.paid, header X-Razorpay-Signature
     = hex HMAC-SHA256 of the raw body with the webhook secret, header X-Razorpay-Event-Id)
  4. the app books the payment and issues the receipt.

Run (three environment lines the app also needs; any values work, the webhook secret must match on both sides):

    # api/.env (a development install only - the override is ignored anywhere else)
    RAZORPAY_API_BASE=http://127.0.0.1:8099/v1
    UPI_RAZORPAY_MAIN_KEY_ID=rzp_test_local
    UPI_RAZORPAY_MAIN_KEY_SECRET=local-secret
    UPI_RAZORPAY_MAIN_WEBHOOK_SECRET=local-webhook-secret

    python3 scripts/fake_razorpay.py --webhook-secret local-webhook-secret

then add a receiving account with provider RAZORPAY and credential set name RAZORPAY_MAIN.

Standard library only. Binds to 127.0.0.1.
"""

import argparse
import hashlib
import hmac
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

MIN_EXPIRY_SECONDS = 15 * 60          # Razorpay refuses a link that expires in under 15 minutes


def razorpay_error(description: str, field: str | None = None) -> dict:
    """Razorpay's error body shape."""
    err = {"code": "BAD_REQUEST_ERROR", "description": description, "source": "business", "step": "payment_initiation", "reason": "input_validation_failed"}
    if field:
        err["field"] = field
    return {"error": err}


class FakeRazorpay(ThreadingHTTPServer):
    """State: payment links by id. ``webhook_url`` / ``webhook_secret`` say where and how a "payment" is announced."""

    daemon_threads = True

    def __init__(self, address, webhook_url: str | None, webhook_secret: str):
        super().__init__(address, _Handler)
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.links: dict[str, dict] = {}
        self.sent_webhooks: list[dict] = []
        self.lock = threading.Lock()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def sign(self, raw: bytes) -> str:
        return hmac.new(self.webhook_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()

    def announce(self, link: dict, event: str) -> tuple[int | None, str]:
        """POST the webhook for *link* to the app, signed like Razorpay does. Returns (HTTP status or None, detail)."""
        payload = {
            "entity": "event", "account_id": "acc_FAKE", "event": event, "contains": ["payment_link"],
            "payload": {"payment_link": {"entity": {"id": link["id"], "amount": link["amount"], "amount_paid": link["amount_paid"], "status": link["status"],
                                                    "reference_id": link["reference_id"], "currency": "INR"}}},
            "created_at": int(time.time()),
        }
        if event == "payment_link.paid":
            payload["contains"].append("payment")
            payload["payload"]["payment"] = {"entity": {"id": link["payment_id"], "amount": link["amount"], "method": "upi", "status": "captured"}}
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        record = {"event": event, "link": link["id"], "event_id": "evt_" + secrets.token_hex(8)}
        self.sent_webhooks.append(record)
        if not self.webhook_url:
            return None, "no webhook url configured"
        req = urllib.request.Request(self.webhook_url, data=raw, method="POST", headers={
            "Content-Type": "application/json", "X-Razorpay-Signature": self.sign(raw), "X-Razorpay-Event-Id": record["event_id"]})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")[:300]
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")[:300]
        except Exception as exc:                                           # the app is not running / unreachable
            return None, f"{type(exc).__name__}: {exc}"


class _Handler(BaseHTTPRequestHandler):
    server: FakeRazorpay

    def log_message(self, fmt, *args):                                     # quiet: one line per request is enough
        print("[fake razorpay]", fmt % args)

    # ── helpers ──────────────────────────────────────────────────────
    def _send(self, code: int, body, content_type: str = "application/json"):
        raw = (json.dumps(body) if content_type == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _authed(self) -> bool:
        return (self.headers.get("Authorization") or "").startswith("Basic ")

    # ── routes ───────────────────────────────────────────────────────
    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/v1/payment_links":
            return self._create()
        if path.startswith("/pay/"):
            return self._pay(path.split("/")[2], "payment_link.paid")
        if path.startswith("/expire/"):
            return self._pay(path.split("/")[2], "payment_link.expired")
        self._send(404, razorpay_error("The requested URL was not found on the server."))

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/v1/payment_links/"):
            link = self.server.links.get(path.split("/")[3])
            if not self._authed():
                return self._send(401, razorpay_error("Authentication failed"))
            return self._send(200, self._public(link)) if link else self._send(400, razorpay_error("The id provided does not exist"))
        if path.startswith("/pay/"):
            return self._page(path.split("/")[2])
        self._send(404, razorpay_error("The requested URL was not found on the server."))

    def _public(self, link: dict) -> dict:
        out = {k: link[k] for k in ("id", "amount", "amount_paid", "currency", "status", "reference_id", "description", "short_url", "expire_by", "upi_link", "accept_partial")}
        out["payments"] = [{"payment_id": link["payment_id"], "amount": link["amount"], "status": "captured"}] if link["status"] == "paid" else None
        return out

    def _create(self):
        if not self._authed():
            return self._send(401, razorpay_error("Authentication failed"))
        b = self._body()
        amount = b.get("amount")
        if not isinstance(amount, int) or amount < 100:
            return self._send(400, razorpay_error("amount must be at least 100 paise", "amount"))
        if b.get("currency") != "INR":
            return self._send(400, razorpay_error("Only INR is supported here", "currency"))
        if b.get("upi_link") and b.get("accept_partial"):
            return self._send(400, razorpay_error("accept_partial cannot be true for a UPI payment link", "accept_partial"))
        expire_by = b.get("expire_by")
        if expire_by is not None and (not isinstance(expire_by, int) or expire_by < time.time() + MIN_EXPIRY_SECONDS - 5):
            return self._send(400, razorpay_error("expire_by should be at least 15 minutes after the current time", "expire_by"))
        ref = b.get("reference_id")
        if ref is not None and (not isinstance(ref, str) or len(ref) > 40):
            return self._send(400, razorpay_error("reference_id must be at most 40 characters", "reference_id"))
        link_id = "plink_" + secrets.token_hex(7)
        link = {"id": link_id, "amount": amount, "amount_paid": 0, "currency": "INR", "status": "created", "reference_id": ref,
                "description": b.get("description"), "short_url": f"{self.server.base}/pay/{link_id}", "expire_by": expire_by,
                "upi_link": bool(b.get("upi_link")), "accept_partial": bool(b.get("accept_partial")), "payment_id": "pay_" + secrets.token_hex(7)}
        with self.server.lock:
            self.server.links[link_id] = link
        self._send(200, self._public(link))

    def _page(self, link_id: str):
        link = self.server.links.get(link_id)
        if not link:
            return self._send(404, "<h1>Unknown link</h1>", "text/html")
        paid = link["status"] != "created"
        html = (f"<html><body style='font-family:sans-serif;max-width:30rem;margin:3rem auto'><h2>Fake Razorpay (local rehearsal)</h2>"
                f"<p>{link['description'] or ''}</p><p style='font-size:1.6rem'>₹{link['amount'] / 100:.2f}</p><p>Status: <b>{link['status']}</b></p>"
                + ("" if paid else f"<form method='post' action='/pay/{link_id}' style='display:inline'><button>Pay (success)</button></form> "
                                   f"<form method='post' action='/expire/{link_id}' style='display:inline'><button>Let the link expire</button></form>")
                + "<p style='color:#666'>No money moves. This page exists only on your machine.</p></body></html>")
        self._send(200, html, "text/html")

    def _pay(self, link_id: str, event: str):
        link = self.server.links.get(link_id)
        if not link:
            return self._send(404, "<h1>Unknown link</h1>", "text/html")
        if link["status"] == "created":
            link["status"] = "paid" if event == "payment_link.paid" else "expired"
            link["amount_paid"] = link["amount"] if link["status"] == "paid" else 0
        code, detail = self.server.announce(link, event)
        self._send(200, f"<html><body style='font-family:sans-serif;max-width:30rem;margin:3rem auto'><h2>{'Payment' if link['status'] == 'paid' else 'Link'} {link['status']}</h2>"
                        f"<p>Webhook to the app: <b>{code if code is not None else 'not delivered'}</b><br><small>{detail}</small></p>"
                        f"<p>You can close this page and go back to the app.</p></body></html>", "text/html")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--webhook-url", default="http://127.0.0.1:8001/api/v1/finance/gateway/webhook/razorpay")
    ap.add_argument("--webhook-secret", required=True, help="must equal UPI_<REF>_WEBHOOK_SECRET in api/.env")
    args = ap.parse_args()
    srv = FakeRazorpay(("127.0.0.1", args.port), args.webhook_url, args.webhook_secret)
    print(f"Fake Razorpay on {srv.base}/v1 - webhooks go to {args.webhook_url}\nSet RAZORPAY_API_BASE={srv.base}/v1 in api/.env (development install only). Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
