"""
NSS ERP — Security tests for the Finance API (api/routers/finance.py).

Focus: access control that tests/api/test_finance.py does not already exercise —
  - every route rejects anonymous callers and garbage tokens (401);
  - every route rejects an authenticated user holding no FINANCE_* permission
    (403): a plain member and an Attendance Marker;
  - FINANCE_VIEW alone (NSS_ERP_AUDITOR) reads but can never write or
    transition anything;
  - the approve-class routes (financial years, activation) are closed to a
    scope-bounded admin who only holds FINANCE_MANAGE;
  - records of one Sakha's financial scope are invisible to another Sakha's
    admin (detail 403, lists empty).

NEVER RUN against a database when this file was written (the sandbox blocks
sockets). The 30-route inventory guard below is DB-free.
"""

import re

import pytest

from tests.attendance_support import marker_h, marker_user  # noqa: F401  (fixtures)
from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    admin_h,
    admin_user,
    make_scope,
    make_txn,
    make_world,
    other_admin,
    other_admin_h,
    other_org_pk,
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

_DATE = "2090-05-15"

# (method, path, json body) — one row per route; ids are FAKE_UUID so a request that got past
# authentication could only ever 404/403/422, never succeed.
ENDPOINTS: list[tuple[str, str, dict | None]] = [
    ("GET", f"{BASE}/reference", None),
    ("GET", f"{BASE}/summary", None),
    ("GET", f"{BASE}/years", None),
    ("POST", f"{BASE}/years", {"start_year": 2095}),
    ("POST", f"{BASE}/years/{FAKE_UUID}/transition", {"status": "OPEN"}),
    ("GET", f"{BASE}/scopes", None),
    ("POST", f"{BASE}/scopes", {"scope_code": "X", "scope_name": "x", "scope_type": "EVENT"}),
    ("GET", f"{BASE}/scopes/{FAKE_UUID}", None),
    ("PATCH", f"{BASE}/scopes/{FAKE_UUID}", {"scope_name": "x"}),
    ("POST", f"{BASE}/scopes/{FAKE_UUID}/transition", {"status": "ACTIVE"}),
    ("GET", f"{BASE}/funds", None),
    ("POST", f"{BASE}/funds", {"fund_code": "X", "fund_name": "x", "fund_type": "GENERAL", "financial_scope_pk": FAKE_UUID}),
    ("GET", f"{BASE}/funds/{FAKE_UUID}", None),
    ("PATCH", f"{BASE}/funds/{FAKE_UUID}", {"fund_name": "x"}),
    ("POST", f"{BASE}/funds/{FAKE_UUID}/transition", {"status": "ACTIVE"}),
    ("GET", f"{BASE}/transactions", None),
    ("POST", f"{BASE}/transactions", {
        "financial_year_pk": FAKE_UUID, "financial_scope_pk": FAKE_UUID, "transaction_type": "INCOME",
        "transaction_category": "PRANAMI_ANNUAL", "amount": "10", "transaction_date": _DATE}),
    ("GET", f"{BASE}/transactions/{FAKE_UUID}", None),
    ("PATCH", f"{BASE}/transactions/{FAKE_UUID}", {"description": "x"}),
    ("POST", f"{BASE}/transactions/{FAKE_UUID}/transition", {"status": "PENDING_APPROVAL"}),
    ("POST", f"{BASE}/transactions/{FAKE_UUID}/receipts", {"receipt_date": _DATE, "amount": "10"}),
    ("GET", f"{BASE}/receipts", None),
    ("POST", f"{BASE}/receipts/{FAKE_UUID}/transition", {"status": "ISSUED"}),
    ("POST", f"{BASE}/transactions/{FAKE_UUID}/payments", {"payment_date": _DATE, "amount": "10"}),
    ("GET", f"{BASE}/payments", None),
    ("POST", f"{BASE}/payments/{FAKE_UUID}/transition", {"status": "APPROVED"}),
    ("GET", f"{BASE}/transfers", None),
    ("POST", f"{BASE}/transfers", {
        "financial_year_pk": FAKE_UUID, "source_scope_pk": FAKE_UUID, "destination_scope_pk": FAKE_UUID,
        "amount": "10", "transfer_date": _DATE, "purpose": "x"}),
    ("GET", f"{BASE}/transfers/{FAKE_UUID}", None),
    ("POST", f"{BASE}/transfers/{FAKE_UUID}/transition", {"status": "PENDING_APPROVAL"}),
]
# Login-only (no module permission): the signed-in member's OWN Pranami. No id parameter exists, so there is
# nothing to tamper with; isolation between members is asserted in tests/api/test_finance.py::TestMyPranami.
LOGIN_ONLY = [("GET", f"{BASE}/my-pranami", None)]
IDS = [f"{m} {re.sub(FAKE_UUID, '{id}', p)[len(BASE):]}" for m, p, _ in ENDPOINTS]
WRITES = [e for e in ENDPOINTS if e[0] != "GET"]
WRITE_IDS = [f"{m} {re.sub(FAKE_UUID, '{id}', p)[len(BASE):]}" for m, p, _ in WRITES]
# Routes that need FINANCE_APPROVE itself (a MANAGE-only admin must be refused before anything else).
APPROVE_ONLY = [
    ("POST", f"{BASE}/years", {"start_year": 2095}),
    ("POST", f"{BASE}/years/{FAKE_UUID}/transition", {"status": "OPEN"}),
]


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    """Guard (DB-free): a new Finance route must be added to ENDPOINTS above."""
    from api.routers.finance import router

    routes = set()
    for r in router.routes:
        for m in r.methods:
            if m != "HEAD":
                routes.add((m, re.sub(r"\{[^}]+\}", FAKE_UUID, r.path)))
    assert routes == {(m, p) for m, p, _ in ENDPOINTS + LOGIN_ONLY}
    assert len(router.routes) == 31


def test_every_route_declares_a_permission_dependency():
    """Guard (DB-free): no Finance route is reachable by a bare login."""
    from api.routers.finance import router

    login_only = {p for _, p, _ in LOGIN_ONLY}
    for r in router.routes:
        names = {getattr(d.call, "__name__", "") for d in r.dependant.dependencies}
        if r.path in login_only:
            assert "get_current_user" in names, f"{r.path} must at least require a login"
        else:
            assert "_check" in names, f"{r.path} has no permission dependency"


class TestAuthentication:

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_anonymous_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body).status_code == 401

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_garbage_token_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body, {"Authorization": "Bearer not.a.jwt"}).status_code == 401


class TestLoginOnlyMyPranami:
    """GET /finance/my-pranami needs a login and nothing else: every member may read their OWN rows."""

    def test_anonymous_is_401(self, anon_client):
        assert anon_client.get(f"{BASE}/my-pranami").status_code == 401

    def test_garbage_token_is_401(self, anon_client):
        assert anon_client.get(f"{BASE}/my-pranami", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401

    def test_member_without_any_finance_permission_may_read_their_own(self, client, plain_member_h):
        r = client.get(f"{BASE}/my-pranami", headers=plain_member_h)
        assert r.status_code == 200 and r.json()["items"] == []

    def test_there_is_no_way_to_name_another_member(self, client, plain_member_h):
        """Query parameters are ignored: identity comes from the token only."""
        r = client.get(f"{BASE}/my-pranami", params={"sangha_sevi_id": "SS1", "person_pk": FAKE_UUID, "financial_year_pk": FAKE_UUID},
                       headers=plain_member_h)
        assert r.status_code == 200 and r.json()["items"] == []


class TestPermissionGate:

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_member_without_finance_permission_is_403(self, method, path, body, client, plain_member_h):
        assert _call(client, method, path, body, plain_member_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_attendance_marker_has_no_finance_access(self, method, path, body, client, marker_h):
        """NSS_ERP_ATTENDANCE_MARKER is a single-purpose role."""
        assert _call(client, method, path, body, marker_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", WRITES, ids=WRITE_IDS)
    def test_view_only_role_cannot_write(self, method, path, body, client, viewer_h):
        """FINANCE_VIEW alone (the Auditor) reads; every mutating route is 403, before any lookup."""
        assert _call(client, method, path, body, viewer_h).status_code == 403

    @pytest.mark.parametrize("path", ["reference", "summary", "years", "scopes", "funds", "transactions", "receipts", "payments", "transfers"])
    def test_view_only_role_can_read_lists(self, path, client, viewer_h):
        assert client.get(f"{BASE}/{path}", headers=viewer_h).status_code == 200

    @pytest.mark.parametrize("method,path,body", APPROVE_ONLY)
    def test_manage_only_admin_cannot_use_approve_routes(self, method, path, body, client, sakha_admin_h):
        assert _call(client, method, path, body, sakha_admin_h).status_code == 403


class TestAdminScope:

    def test_foreign_admin_cannot_read_a_record_of_another_sakha(self, client, admin_h, other_admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        assert client.get(f"{BASE}/transactions/{pk}", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/funds/{w['fund']['fund_master_pk']}", headers=other_admin_h).status_code == 403
        listed = client.get(f"{BASE}/transactions", params={"financial_scope_pk": w["scope"]["financial_scope_pk"]},
                            headers=other_admin_h)
        assert listed.status_code == 200 and listed.json()["total"] == 0

    def test_foreign_admin_cannot_act_on_a_record_of_another_sakha(self, client, admin_h, other_admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        for method, path, body in (
            ("PATCH", f"{BASE}/transactions/{pk}", {"description": "hijack"}),
            ("POST", f"{BASE}/transactions/{pk}/transition", {"status": "PENDING_APPROVAL"}),
            ("POST", f"{BASE}/transactions/{pk}/receipts", {"receipt_date": _DATE, "amount": "10"}),
            ("POST", f"{BASE}/transactions/{pk}/payments", {"payment_date": _DATE, "amount": "10"}),
        ):
            assert _call(client, method, path, body, other_admin_h).status_code == 403, (method, path)

    def test_scope_without_organization_is_invisible_to_scoped_admins(self, client, admin_h, sakha_admin_h):
        scope = make_scope(client, admin_h)                                                 # no organization
        pk = scope["financial_scope_pk"]
        assert client.get(f"{BASE}/scopes/{pk}", headers=sakha_admin_h).status_code == 403
        assert client.get(f"{BASE}/scopes", params={"q": scope["scope_code"]}, headers=sakha_admin_h).json()["total"] == 0

    def test_scoped_admin_cannot_target_a_foreign_year_scope_pair(self, client, admin_h, sakha_admin_h, other_org_pk):
        w = make_world(client, admin_h, other_org_pk)
        body = {"financial_year_pk": w["year"]["financial_year_pk"], "financial_scope_pk": w["scope"]["financial_scope_pk"],
                "transaction_type": "INCOME", "transaction_category": "PRANAMI_ANNUAL", "amount": "10",
                "transaction_date": w["year"]["start_date"]}
        assert client.post(f"{BASE}/transactions", json=body, headers=sakha_admin_h).status_code == 403
