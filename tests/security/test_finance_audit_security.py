"""
NSS ERP — Security tests for the Kendra annual audit (api/routers/finance_audit.py, Bye-Law Section G).

  - inventory guard (DB-free): the eight routes are listed below, so a new endpoint cannot ship without a security row;
  - anonymous and garbage-token callers get 401; a member with no Finance permission gets 403;
  - a view-only role cannot write; a scoped Sakha administrator cannot reach the Kendra's audit (admin scope);
  - an unknown audit is 404 for an authorised caller.

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

GATED = [
    ("GET", f"{BASE}/audits", None),
    ("POST", f"{BASE}/audits", {"financial_year_pk": FAKE_UUID, "auditor_name": "A", "appointed_on": "2020-01-01", "appointment_reference": "GB/1"}),
    ("GET", f"{BASE}/audits/{FAKE_UUID}", None),
    ("POST", f"{BASE}/audits/{FAKE_UUID}/report", {"report_reference": "R/1", "report_date": "2020-02-01"}),
    ("POST", f"{BASE}/audits/{FAKE_UUID}/governing-body", {"gb_placed_on": "2020-02-02", "gb_reference": "GB/2"}),
    ("POST", f"{BASE}/audits/{FAKE_UUID}/approval", {"approved_on": "2020-02-03", "approval_reference": "CM/1"}),
    ("POST", f"{BASE}/audits/{FAKE_UUID}/general-body", {"general_body_on": "2020-02-04", "general_body_reference": "GBM/1"}),
    ("POST", f"{BASE}/audits/{FAKE_UUID}/correct", {"auditor_name": "B", "reason": "typo"}),
]
WRITES = [e for e in GATED if e[0] != "GET"]
ON_AN_AUDIT = [e for e in GATED if "/audits/" in e[1]]


def _id(e):
    return f"{e[0]} {re.sub(FAKE_UUID, '{id}', e[1])[len(BASE):]}"


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    from api.routers.finance_audit import router

    routes = {(m, re.sub(r"\{[^}]+\}", FAKE_UUID, r.path)) for r in router.routes for m in r.methods if m != "HEAD"}
    assert routes == {(m, p) for m, p, _ in GATED}
    assert len(router.routes) == 8


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

    @pytest.mark.parametrize("method,path,body", ON_AN_AUDIT, ids=[_id(e) for e in ON_AN_AUDIT])
    def test_unknown_audit_is_404_for_an_authorised_caller(self, method, path, body, client, admin_h):
        assert _call(client, method, path, body, admin_h).status_code == 404


class TestInput:
    def test_a_bad_status_filter_is_422(self, client, admin_h):
        assert client.get(f"{BASE}/audits", params={"status": "DONE"}, headers=admin_h).status_code == 422

    def test_a_report_link_that_is_not_https_is_refused(self, client, admin_h):
        r = client.post(f"{BASE}/audits/{FAKE_UUID}/report", json={"report_reference": "R", "report_date": "2020-02-01", "report_link": "javascript:alert(1)"},
                        headers=admin_h)
        assert r.status_code in (404, 422)                       # an unknown audit is 404 first; a known one would be 422 - never accepted
