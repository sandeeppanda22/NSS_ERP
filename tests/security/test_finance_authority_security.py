"""
NSS ERP — Security tests for the Bye-Law disbursement controls (api/routers/finance_authority.py).

  - inventory guard (DB-free): the six routes are listed below, so a new endpoint cannot ship without a security row;
    every one declares a permission dependency (no route is reachable by a bare login);
  - anonymous and garbage-token callers get 401; a member with no Finance permission gets 403;
  - a view-only role can read the state but every write is refused;
  - a scoped Sakha administrator cannot see or change the authority of Kendra money (admin scope);
  - the statutory signatures cannot be forged: a permission (even FINANCE_APPROVE) without the Treasurer / Secretary seat
    cannot sign - the super administrator included (covered end to end in tests/api/test_finance_bye_law.py).

NEVER RUN against a database when this file was written.
"""

import re

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    admin_h,
    admin_user,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    viewer_h,
    viewer_user,
)

from tests.api.test_finance_bye_law import _authority_body, _kendra_payment, officers  # noqa: F401  (fixture + builders)

pytestmark = pytest.mark.integration

_BODY = {"resolution_reference": "GB/1", "resolution_date": "2020-01-01", "scheme_description": "x",
         "purpose_code": "KENDRA_MANAGEMENT", "president_order_reference": "P/1", "president_order_date": "2020-01-02"}
GATED = [
    ("GET", f"{BASE}/payments/{FAKE_UUID}/authority", None),
    ("PUT", f"{BASE}/payments/{FAKE_UUID}/authority", _BODY),
    ("POST", f"{BASE}/payments/{FAKE_UUID}/countersign", None),
    ("GET", f"{BASE}/transfers/{FAKE_UUID}/authority", None),
    ("PUT", f"{BASE}/transfers/{FAKE_UUID}/authority", _BODY),
    ("POST", f"{BASE}/transfers/{FAKE_UUID}/countersign", None),
]
WRITES = [e for e in GATED if e[0] != "GET"]


def _id(e):
    return f"{e[0]} {re.sub(FAKE_UUID, '{id}', e[1])[len(BASE):]}"


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    from api.routers.finance_authority import router

    routes = {(m, re.sub(r"\{[^}]+\}", FAKE_UUID, r.path)) for r in router.routes for m in r.methods if m != "HEAD"}
    assert routes == {(m, p) for m, p, _ in GATED}
    assert len(router.routes) == 6


def test_every_route_declares_a_permission_dependency():
    from api.routers.finance_authority import router

    for r in router.routes:
        names = {getattr(d.call, "__name__", "") for d in r.dependant.dependencies}
        assert "_check" in names, f"{r.path} has no permission dependency"


class TestAuthentication:
    @pytest.mark.parametrize("method,path,body", GATED, ids=[_id(e) for e in GATED])
    def test_anonymous_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body).status_code == 401

    @pytest.mark.parametrize("method,path,body", GATED, ids=[_id(e) for e in GATED])
    def test_garbage_token_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body, {"Authorization": "Bearer not.a.token"}).status_code == 401


class TestAuthorization:
    @pytest.mark.parametrize("method,path,body", GATED, ids=[_id(e) for e in GATED])
    def test_member_without_finance_permission_is_403(self, method, path, body, client, plain_member_h):
        assert _call(client, method, path, body, plain_member_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", WRITES, ids=[_id(e) for e in WRITES])
    def test_view_only_role_cannot_write(self, method, path, body, client, viewer_h):
        assert _call(client, method, path, body, viewer_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", GATED, ids=[_id(e) for e in GATED])
    def test_unknown_ids_are_404_for_an_authorised_caller(self, method, path, body, client, admin_h):
        assert _call(client, method, path, body, admin_h).status_code == 404


class TestScope:
    def test_scoped_sakha_admin_cannot_reach_kendra_money(self, client, admin_h, sakha_admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        base = f"{BASE}/payments/{p['pk']}"
        assert client.get(f"{base}/authority", headers=sakha_admin_h).status_code == 403
        assert client.put(f"{base}/authority", json=_authority_body(), headers=sakha_admin_h).status_code == 403
        assert client.post(f"{base}/countersign", headers=sakha_admin_h).status_code == 403

    def test_a_permission_without_the_seat_cannot_sign(self, client, admin_h, officers):
        """FINANCE_APPROVE (and the super administrator) are not the Treasurer / Secretary."""
        p = _kendra_payment(client, admin_h, officers)
        assert client.put(f"{BASE}/payments/{p['pk']}/authority", json=_authority_body(), headers=admin_h).status_code == 200
        assert client.post(f"{BASE}/payments/{p['pk']}/transition", json={"status": "INITIATED"}, headers=admin_h).status_code == 403
        assert client.post(f"{BASE}/payments/{p['pk']}/transition", json={"status": "INITIATED"}, headers=officers["outsider_h"]).status_code == 403
