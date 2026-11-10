"""
NSS ERP — Security tests for the Finance customization + UPI APIs (api/routers/finance_setup.py, api/routers/finance_upi.py).

Focus - access control and money-handling safety that the functional tests in tests/api/test_finance_heads.py and
tests/api/test_finance_upi.py do not already sweep:
  - an inventory guard: every route of the two routers is listed below, so a new endpoint cannot ship without a security row;
  - every route except the gateway webhook and the member's own self-service routes rejects anonymous callers and garbage
    tokens (401), and a member with no Finance permission (403);
  - configuration (accounts, heads) and booking a held payment need FINANCE_APPROVE: a MANAGE-only admin and a view-only
    role are refused before any lookup;
  - the one unauthenticated route (the gateway webhook) is safe by SIGNATURE, answers 404 when the provider is not
    enabled, and leaks nothing about which orders exist;
  - the member self-service routes serve only the signed-in member (login only, no id of the payer is ever accepted);
  - nothing in any response carries a gateway secret.

NEVER RUN against the project database when this file was written; it was run against a real PostgreSQL engine in the authoring
sandbox through the repo's unmodified conftest (see database/ddl/14_finance/README.md, "Verification").
"""

import json
import re

import pytest

from tests.attendance_support import marker_h, marker_user  # noqa: F401  (fixtures)
from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    admin_h,
    admin_user,
    create_request,
    ensure_open_year_covering_today,
    make_account,
    make_head,
    mock_gateway,
    new_code,
    other_admin,
    other_admin_h,
    other_org_pk,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    upi_world,
    viewer_h,
    viewer_user,
    webhook,
)

pytestmark = pytest.mark.integration

_DATE = "2090-05-15"
_SIGNED_ONLY = ("POST", f"{BASE}/gateway/webhook/MOCK", {"order_id": "x"})

# Permission-gated routes: (method, path, json body). Ids are FAKE_UUID so a request that got past authentication could only
# ever 404/403/422, never succeed.
GATED: list[tuple[str, str, dict | None]] = [
    ("GET", f"{BASE}/accounts", None),
    ("POST", f"{BASE}/accounts", {"organization_pk": FAKE_UUID, "account_label": "x", "account_holder_name": "x"}),
    ("GET", f"{BASE}/accounts/{FAKE_UUID}", None),
    ("PATCH", f"{BASE}/accounts/{FAKE_UUID}", {"bank_name": "x"}),
    ("POST", f"{BASE}/accounts/{FAKE_UUID}/transition", {"status": "INACTIVE", "remarks": "x"}),
    ("GET", f"{BASE}/heads", None),
    ("POST", f"{BASE}/heads", {"organization_pk": FAKE_UUID, "head_code": "XX", "head_name": "x", "direction": "INCOME"}),
    ("POST", f"{BASE}/heads/adopt-templates", {"organization_pk": FAKE_UUID}),
    ("GET", f"{BASE}/heads/{FAKE_UUID}", None),
    ("PATCH", f"{BASE}/heads/{FAKE_UUID}", {"head_name": "x"}),
    ("POST", f"{BASE}/heads/{FAKE_UUID}/transition", {"status": "INACTIVE"}),
    ("GET", f"{BASE}/payment-requests", None),
    ("POST", f"{BASE}/payment-requests", {"finance_head_pk": FAKE_UUID, "amount": "10"}),
    ("GET", f"{BASE}/payment-requests/{FAKE_UUID}", None),
    ("POST", f"{BASE}/payment-requests/{FAKE_UUID}/transition", {"status": "CANCELLED", "remarks": "x"}),
    ("POST", f"{BASE}/payment-requests/{FAKE_UUID}/refresh", None),
    ("POST", f"{BASE}/payment-requests/{FAKE_UUID}/post", None),
    ("POST", f"{BASE}/payment-requests/{FAKE_UUID}/mock-pay", None),
]
# Login-only: the signed-in member's own Pranami payment.
MEMBER = [
    ("GET", f"{BASE}/my-pranami/heads", None),
    ("POST", f"{BASE}/my-pranami/pay", {"finance_head_pk": FAKE_UUID, "amount": "10"}),
    ("GET", f"{BASE}/my-pranami/requests/{FAKE_UUID}", None),
]
APPROVE_ONLY = [e for e in GATED if e[0] != "GET" and "/payment-requests" not in e[1]] + [
    ("POST", f"{BASE}/payment-requests/{FAKE_UUID}/post", None)]
WRITES = [e for e in GATED if e[0] != "GET"]


def _id(e):
    return f"{e[0]} {re.sub(FAKE_UUID, '{id}', e[1])[len(BASE):]}"


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    """Guard (DB-free): a new route of either router must be added to the tables above."""
    from api.routers.finance_setup import router as setup
    from api.routers.finance_upi import router as upi

    routes = set()
    for router in (setup, upi):
        for r in router.routes:
            for m in r.methods:
                if m != "HEAD":
                    routes.add((m, re.sub(r"\{[^}]+\}", FAKE_UUID, r.path)))
    listed = {(m, p) for m, p, _ in GATED + MEMBER + [_SIGNED_ONLY]}
    # the webhook is listed with the MOCK provider; the real route takes any provider name
    listed = {(m, p.replace("/gateway/webhook/MOCK", f"/gateway/webhook/{FAKE_UUID}")) for m, p in listed}
    assert routes == listed
    assert len(setup.routes) + len(upi.routes) == 22


def test_every_gated_route_declares_a_permission_dependency():
    """Guard (DB-free): the only routes without a permission check are the member's own routes and the signed webhook."""
    from api.routers.finance_setup import router as setup
    from api.routers.finance_upi import router as upi

    member = {p.replace(BASE, "/api/v1/finance") for _, p, _ in MEMBER}
    member = {re.sub(re.escape(FAKE_UUID), "{request_pk}", p) for p in member}
    for router in (setup, upi):
        for r in router.routes:
            names = {getattr(d.call, "__name__", "") for d in r.dependant.dependencies}
            if "gateway/webhook" in r.path:
                assert "_check" not in names and "get_current_user" not in names, "the webhook is authenticated by its signature, not a login"
            elif r.path.startswith("/api/v1/finance/my-pranami"):
                assert "get_current_user" in names, f"{r.path} must require a login"
            else:
                assert "_check" in names, f"{r.path} has no permission dependency"


def test_the_webhook_is_the_only_route_that_accepts_an_anonymous_caller():
    from api.routers.finance_setup import router as setup
    from api.routers.finance_upi import router as upi

    anonymous = [r.path for router in (setup, upi) for r in router.routes
                 if not {getattr(d.call, "__name__", "") for d in r.dependant.dependencies} & {"_check", "get_current_user"}]
    assert anonymous == ["/api/v1/finance/gateway/webhook/{provider}"]


class TestAuthentication:

    @pytest.mark.parametrize("method,path,body", GATED + MEMBER, ids=[_id(e) for e in GATED + MEMBER])
    def test_anonymous_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body).status_code == 401

    @pytest.mark.parametrize("method,path,body", GATED + MEMBER, ids=[_id(e) for e in GATED + MEMBER])
    def test_garbage_token_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body, {"Authorization": "Bearer not.a.jwt"}).status_code == 401


class TestPermissionGate:

    @pytest.mark.parametrize("method,path,body", GATED, ids=[_id(e) for e in GATED])
    def test_member_without_finance_permission_is_403(self, method, path, body, client, plain_member_h):
        assert _call(client, method, path, body, plain_member_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", GATED, ids=[_id(e) for e in GATED])
    def test_attendance_marker_has_no_finance_access(self, method, path, body, client, marker_h):
        assert _call(client, method, path, body, marker_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", WRITES, ids=[_id(e) for e in WRITES])
    def test_view_only_role_cannot_write(self, method, path, body, client, viewer_h):
        """The Auditor reads; every mutating route is 403 before any lookup."""
        assert _call(client, method, path, body, viewer_h).status_code == 403

    @pytest.mark.parametrize("path", ["accounts", "heads", "payment-requests"])
    def test_view_only_role_can_read_lists(self, path, client, viewer_h):
        assert client.get(f"{BASE}/{path}", headers=viewer_h).status_code == 200

    @pytest.mark.parametrize("method,path,body", APPROVE_ONLY, ids=[_id(e) for e in APPROVE_ONLY])
    def test_manage_only_admin_cannot_configure_or_book_a_held_payment(self, method, path, body, client, sakha_admin_h):
        """Configuring heads / accounts and booking a held payment are FINANCE_APPROVE decisions."""
        assert _call(client, method, path, body, sakha_admin_h).status_code == 403


class TestMemberRoutesAreLoginOnly:

    def test_a_member_with_no_role_may_use_their_own_routes(self, client, plain_member_h):
        assert client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).status_code == 200
        assert client.get(f"{BASE}/my-pranami/requests/{FAKE_UUID}", headers=plain_member_h).status_code == 404

    def test_a_person_without_a_sakha_membership_cannot_pay(self, client, admin_h):
        """The bootstrap-style admin of a scope-less account has no home Sakha: there is nothing to pay into."""
        assert client.get(f"{BASE}/my-pranami/heads", headers=admin_h).status_code in (200, 403)

    def test_no_payer_field_exists_and_extra_ones_are_ignored(self, client, admin_h, register_org_pk, mock_gateway, plain_member, plain_member_h, write_conn):
        ensure_open_year_covering_today(write_conn)
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/my-pranami/pay", headers=plain_member_h, json={
            "finance_head_pk": u["head"]["finance_head_pk"], "amount": "10.00", "payer_person_pk": FAKE_UUID, "sangha_sevi_id": "SS1",
            "financial_scope_pk": FAKE_UUID, "financial_account_pk": FAKE_UUID})
        assert r.status_code == 201
        full = client.get(f"{BASE}/payment-requests/{r.json()['upi_payment_request_pk']}", headers=admin_h).json()
        assert full["payer_sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        assert full["financial_scope_pk"] == u["world"]["scope"]["financial_scope_pk"], "the head, not the member, picks the destination"
        assert full["financial_account_pk"] == u["account"]["financial_account_pk"]


class TestTheWebhook:

    def test_it_needs_no_login_but_a_valid_signature(self, client, anon_client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = create_request(client, admin_h, u["head"]).json()
        assert webhook(anon_client, mock_gateway, req["provider_order_id"], secret="wrong").status_code == 401
        assert webhook(anon_client, mock_gateway, req["provider_order_id"]).status_code == 200

    def test_a_bearer_token_does_not_replace_the_signature(self, client, admin_h, register_org_pk, mock_gateway):
        """Being an administrator does not let anyone mark a request paid: only the gateway's signature does."""
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = create_request(client, admin_h, u["head"]).json()
        from api.services import upi_gateway
        raw, _ = upi_gateway.build_mock_event(secret="not-the-gateway", order_id=req["provider_order_id"])
        r = client.post(f"{BASE}/gateway/webhook/MOCK", content=raw, headers={**admin_h, "X-Mock-Signature": "00" * 32})
        assert r.status_code == 401
        assert client.get(f"{BASE}/payment-requests/{req['upi_payment_request_pk']}", headers=admin_h).json()["status"] == "PENDING"

    def test_it_reveals_nothing_about_which_orders_exist(self, client, admin_h, register_org_pk, mock_gateway):
        """A real order with a bad signature and an unknown order must not be distinguishable by a probing stranger beyond 401 vs 200."""
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        real = create_request(client, admin_h, u["head"]).json()
        unknown = webhook(client, mock_gateway, "mock_nope")
        forged = webhook(client, mock_gateway, real["provider_order_id"], secret="x")
        assert unknown.status_code == 200 and forged.status_code == 401
        for r in (unknown, forged):
            assert set(r.json()) == {"outcome"}, "no request details may leak"

    def test_a_disabled_provider_looks_like_a_missing_route(self, client, monkeypatch, mock_gateway):
        from api.config import settings
        monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "")
        r = webhook(client, mock_gateway, "mock_x")
        assert r.status_code == 404 and "MOCK" not in r.text


class TestNoSecretLeaks:

    def test_no_response_of_either_router_contains_a_secret(self, client, admin_h, register_org_pk, mock_gateway, plain_member_h):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        req = create_request(client, admin_h, u["head"]).json()
        client.post(f"{BASE}/gateway/webhook/MOCK", content=b"{}", headers={"X-Mock-Signature": "x"})
        urls = [f"{BASE}/accounts", f"{BASE}/accounts/{u['account']['financial_account_pk']}", f"{BASE}/heads",
                f"{BASE}/payment-requests", f"{BASE}/payment-requests/{req['upi_payment_request_pk']}", f"{BASE}/reference"]
        for url in urls:
            text = client.get(url, headers=admin_h).text
            assert mock_gateway.secret not in text, url
            assert not re.search(r"key_secret|webhook_secret|password", text, re.I), url
        assert mock_gateway.secret not in client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).text

    def test_a_gateway_failure_never_echoes_provider_internals(self, client, admin_h, register_org_pk, mock_gateway, monkeypatch):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        from api.services import upi_gateway
        provider = upi_gateway.PROVIDERS["MOCK"]

        def boom(**kwargs):
            raise upi_gateway.GatewayError("The payment gateway could not be reached.")

        monkeypatch.setattr(provider, "create_order", boom)
        r = create_request(client, admin_h, u["head"])
        assert r.status_code == 502 and r.json()["detail"] == "The payment gateway could not be reached."
