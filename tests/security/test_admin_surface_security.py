"""
NSS ERP — Auth/permission gating matrix for the admin, claim-approval,
geo-approval and auth routers.

One parametrized table drives two assertions per endpoint:

  * anonymous request          -> 401 (nothing leaks without a token)
  * authenticated, NO roles    -> 403 (a valid login alone confers no admin reach)

plus a handful of token-hygiene cases (garbage token, refresh token used as an
access token). Before this file only a few admin endpoints had a 401/403
assertion; claim_approval and geo_approval had none (their API test modules
defer to tests/security/, which did not cover them).

Permission gates are evaluated as FastAPI dependencies, so they fire before the
body is validated — an empty `{}` body is therefore enough to reach the gate.
The business-logic and admin-scope (ADMIN-BR-076/077) assertions live in
tests/api/test_admin_scope.py, test_claim_approval.py and test_geo_approval.py.

Not covered here (separately tested): /audit/change-log (test_audit_security.py),
/bootstrap/* and /register/* (deliberately public).

Everything rolls back with the module SAVEPOINT (tests/conftest.py).
"""

import pytest
from uuid import uuid4

from tests.api.test_admin_credentials import (  # noqa: F401  (fixtures reused by name)
    membership_type_pks, active_status_pk, sakha_org_pk,
    _create_member_without_credential,
)
from tests.registration_support import add_user_account


pytestmark = pytest.mark.integration

NOROLE_PASSWORD = "NoRolePass1x"
U = "00000000-0000-0000-0000-0000000000bb"   # syntactically valid, non-existent pk

# (method, path) — every endpoint guarded by a permission dependency.
PERMISSION_GATED = [
    # api/routers/admin.py (32 endpoints)
    ("GET",    "/api/v1/admin/users"),
    ("GET",    "/api/v1/admin/sangha-sevi/without-account"),
    ("POST",   "/api/v1/admin/persons"),
    ("GET",    "/api/v1/admin/persons/check-contact"),
    ("POST",   "/api/v1/admin/users"),
    ("POST",   "/api/v1/admin/sangha-sevi"),
    ("GET",    f"/api/v1/admin/sangha-sevi/check/{U}"),
    ("POST",   "/api/v1/admin/sangha-sevi/check-batch"),
    ("GET",    f"/api/v1/admin/users/check-account/{U}"),
    ("GET",    f"/api/v1/admin/users/{U}"),
    ("POST",   f"/api/v1/admin/users/{U}/reset-password"),
    ("PATCH",  f"/api/v1/admin/users/{U}/status"),
    ("GET",    f"/api/v1/admin/persons/{U}"),
    ("PATCH",  f"/api/v1/admin/persons/{U}"),
    ("DELETE", f"/api/v1/admin/users/{U}"),
    ("GET",    f"/api/v1/admin/users/{U}/roles"),
    ("POST",   f"/api/v1/admin/users/{U}/roles"),
    ("DELETE", f"/api/v1/admin/users/{U}/roles/{U}"),
    ("GET",    "/api/v1/admin/organizations"),
    ("GET",    "/api/v1/admin/organizations/kumari-sevak-sakha-options"),
    ("GET",    "/api/v1/admin/sakha-scope-options"),
    ("GET",    "/api/v1/admin/organizations/code-availability?field=short_code&value=ABC"),
    ("PATCH",  f"/api/v1/admin/organizations/{U}/short-code"),
    ("PATCH",  f"/api/v1/admin/organizations/{U}"),
    ("POST",   "/api/v1/admin/organizations"),
    ("GET",    "/api/v1/admin/organizations/next-code"),
    ("GET",    "/api/v1/admin/dashboard-stats"),
    ("PATCH",  f"/api/v1/admin/patra/anumati/{U}/document-number"),
    ("GET",    "/api/v1/admin/credentials/members"),
    ("GET",    f"/api/v1/admin/credentials/members/{U}/timeline"),
    ("POST",   f"/api/v1/admin/credentials/members/{U}/issue"),
    ("POST",   f"/api/v1/admin/credentials/members/{U}/promote"),
    # api/routers/claim_approval.py (5)
    ("GET",    "/api/v1/admin/claims"),
    ("GET",    f"/api/v1/admin/claims/{U}"),
    ("PATCH",  f"/api/v1/admin/claims/{U}"),
    ("POST",   f"/api/v1/admin/claims/{U}/approve"),
    ("POST",   f"/api/v1/admin/claims/{U}/reject"),
    # api/routers/geo_approval.py (4)
    ("GET",    "/api/v1/admin/geo-entries/district"),
    ("GET",    f"/api/v1/admin/geo-entries/district/{U}"),
    ("POST",   f"/api/v1/admin/geo-entries/district/{U}/approve"),
    ("POST",   f"/api/v1/admin/geo-entries/district/{U}/correct"),
]

# Endpoints that need only a valid login (get_current_user) — 401 anonymous, but
# deliberately NOT 403 for a role-less member (they act on the caller's own data).
LOGIN_ONLY = [
    ("POST",   "/api/v1/auth/logout"),
    ("GET",    "/api/v1/auth/sessions"),
    ("DELETE", f"/api/v1/auth/sessions/{U}"),
    ("POST",   "/api/v1/auth/change-password"),
    ("GET",    "/api/v1/auth/me"),
    ("PATCH",  "/api/v1/auth/profile"),
]


def _id(case):
    return f"{case[0]} {case[1].split('/api/v1/')[-1].replace(U, '{pk}')}"


def _call(client, method, path, headers=None):
    return client.request(method, path, headers=headers or {}, json={} if method != "GET" else None)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def norole_user(write_conn, sakha_org_pk, membership_type_pks, active_status_pk):
    """An ACTIVE, loginable Sangha Sevi who holds NO role -> no permission at all."""
    member = _create_member_without_credential(
        write_conn, sakha_org_pk, membership_type_pks["REGULAR"], active_status_pk, "NOROLE",
    )
    add_user_account(write_conn, member["person_pk"], NOROLE_PASSWORD, status="ACTIVE")
    return member


@pytest.fixture(scope="module")
def norole_tokens(client, norole_user):
    resp = client.post("/api/v1/auth/login", json={
        "login_id": norole_user["sangha_sevi_id"], "password": NOROLE_PASSWORD,
    })
    assert resp.status_code == 200, f"No-role login failed: {resp.json()}"
    return resp.json()


@pytest.fixture(scope="module")
def norole_headers(norole_tokens):
    return {"Authorization": f"Bearer {norole_tokens['access_token']}"}


# ── 401: anonymous ──────────────────────────────────────────────────────

class TestAnonymousIsRejected:

    @pytest.mark.parametrize("method,path", PERMISSION_GATED + LOGIN_ONLY,
                             ids=[_id(c) for c in PERMISSION_GATED + LOGIN_ONLY])
    def test_no_token_is_401(self, client, method, path):
        resp = _call(client, method, path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code} {resp.text[:200]}"

    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/claims"),
        ("POST", f"/api/v1/admin/geo-entries/district/{U}/correct"),
    ], ids=["users", "claims", "geo-correct"])
    def test_garbage_token_is_401(self, client, method, path):
        resp = _call(client, method, path, headers={"Authorization": "Bearer not.a.jwt"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("scheme", ["Basic dXNlcjpwYXNz", "Token abc", "Bearer"])
    def test_wrong_auth_scheme_is_rejected(self, client, scheme):
        resp = client.get("/api/v1/admin/users", headers={"Authorization": scheme})
        assert resp.status_code in (401, 403)
        assert resp.status_code != 200


# ── 403: authenticated but unpermissioned ───────────────────────────────

class TestRolelessUserIsForbidden:

    @pytest.mark.parametrize("method,path", PERMISSION_GATED, ids=[_id(c) for c in PERMISSION_GATED])
    def test_login_without_a_role_is_403(self, client, norole_headers, method, path):
        resp = _call(client, method, path, headers=norole_headers)
        assert resp.status_code == 403, f"{method} {path} -> {resp.status_code} {resp.text[:200]}"

    def test_login_only_endpoints_remain_available_to_a_roleless_member(self, client, norole_headers):
        """/auth/me is the member's own view — no permission required."""
        resp = client.get("/api/v1/auth/me", headers=norole_headers)
        assert resp.status_code == 200
        assert resp.json()["sangha_sevi_id"]

    def test_refresh_token_is_not_an_access_token(self, client, norole_tokens):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {norole_tokens['refresh_token']}",
        })
        assert resp.status_code == 401
        assert "access token" in resp.json()["detail"].lower()
        admin = client.get("/api/v1/admin/users", headers={
            "Authorization": f"Bearer {norole_tokens['refresh_token']}",
        })
        assert admin.status_code == 401

    def test_deleted_account_token_stops_working(self, client, write_conn, norole_user, norole_headers):
        """A soft-deleted account must lose access even with a not-yet-expired JWT
        (get_current_user reloads the account on every request)."""
        assert client.get("/api/v1/auth/me", headers=norole_headers).status_code == 200
        with write_conn.cursor() as cur:
            cur.execute(
                "UPDATE nss.user_account SET is_active = FALSE, deleted_at = NOW(), "
                "account_status = 'INACTIVE' WHERE person_pk = %s",
                (norole_user["person_pk"],),
            )
        try:
            resp = client.get("/api/v1/auth/me", headers=norole_headers)
            assert resp.status_code in (401, 403)
        finally:
            with write_conn.cursor() as cur:
                cur.execute(
                    "UPDATE nss.user_account SET is_active = TRUE, deleted_at = NULL, "
                    "account_status = 'ACTIVE' WHERE person_pk = %s",
                    (norole_user["person_pk"],),
                )
