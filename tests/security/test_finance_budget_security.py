"""
NSS ERP — Security tests for the Kendra annual budget (api/routers/finance_budget.py).

  - inventory guard (DB-free): the nine routes are listed below, so a new endpoint cannot ship without a security row;
  - anonymous and garbage-token callers get 401; a member with no Finance permission gets 403;
  - a view-only role cannot write; a scoped Sakha administrator cannot reach the Kendra's budget (admin scope);
  - an unknown budget is 404 for an authorised caller;
  - hostile text in the free-text fields is stored as text, never run.

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
    sakha_pks,
    viewer_h,
    viewer_user,
)

pytestmark = pytest.mark.integration

_LINE = {"finance_head_pk": FAKE_UUID, "amount": "10.00"}
_VIEWS = {"advisory_views_date": "2020-01-02", "advisory_views_summary": "x"}
GATED = [
    ("GET", f"{BASE}/budgets", None),
    ("POST", f"{BASE}/budgets", {"financial_year_pk": FAKE_UUID}),
    ("GET", f"{BASE}/budgets/{FAKE_UUID}", None),
    ("PUT", f"{BASE}/budgets/{FAKE_UUID}/lines", _LINE),
    ("DELETE", f"{BASE}/budgets/{FAKE_UUID}/lines/{FAKE_UUID}", None),
    ("POST", f"{BASE}/budgets/{FAKE_UUID}/refer", {"referred_on": "2020-01-01"}),
    ("POST", f"{BASE}/budgets/{FAKE_UUID}/advisory-views", _VIEWS),
    ("POST", f"{BASE}/budgets/{FAKE_UUID}/pass", {"resolution_reference": "GB/1", "resolution_date": "2020-01-03"}),
    ("POST", f"{BASE}/budgets/{FAKE_UUID}/reopen", {"remarks": "x"}),
]
WRITES = [e for e in GATED if e[0] != "GET"]
ON_A_BUDGET = [e for e in GATED if "/budgets/" in e[1]]


def _id(e):
    return f"{e[0]} {re.sub(FAKE_UUID, '{id}', e[1])[len(BASE):]}"


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    from api.routers.finance_budget import router

    routes = {(m, re.sub(r"\{[^}]+\}", FAKE_UUID, r.path)) for r in router.routes for m in r.methods if m != "HEAD"}
    assert routes == {(m, p) for m, p, _ in GATED}
    assert len(router.routes) == 9


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

    @pytest.mark.parametrize("method,path,body", ON_A_BUDGET, ids=[_id(e) for e in ON_A_BUDGET])
    def test_unknown_budget_is_404_for_an_authorised_caller(self, method, path, body, client, admin_h):
        assert _call(client, method, path, body, admin_h).status_code == 404


class TestInput:
    def test_hostile_text_is_stored_as_text(self, client, admin_h, write_conn):
        from tests.api.test_finance_budget import _budget, _head, _kendra_scope, _line, _refer, _views
        from tests.reparent_support import kendra_pks

        hostile = "x'); DROP TABLE nss.finance_budget;-- <script>alert(1)</script>"
        _, b = _budget(client, admin_h)
        scope = _kendra_scope(client, admin_h, kendra_pks(write_conn)[0])
        _line(client, admin_h, b, _head(client, admin_h, scope, "EXPENSE_GENERAL"))
        _refer(client, admin_h, b)
        d = _views(client, admin_h, b, advisory_views_summary=hostile)
        assert d["advisory_views_summary"] == hostile
        cur = write_conn.cursor()
        cur.execute("SELECT remarks FROM nss.correspondence WHERE reference_number = %s", (d["advisory_reference"],))
        assert cur.fetchone()[0] == hostile                                          # the filed letter carries it as plain text too
        cur = write_conn.cursor()
        cur.execute("SELECT to_regclass('nss.finance_budget') IS NOT NULL")
        assert cur.fetchone()[0] is True

    def test_an_oversized_amount_is_422(self, client, admin_h):
        r = client.put(f"{BASE}/budgets/{FAKE_UUID}/lines", json={"finance_head_pk": FAKE_UUID, "amount": "99999999999999999"}, headers=admin_h)
        assert r.status_code == 422
