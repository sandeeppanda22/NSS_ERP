"""
NSS ERP — Tier 5 Authentication API tests.

Integration tests for the auth endpoints:
  1. POST /api/v1/auth/login       — happy path + failure cases
  2. POST /api/v1/auth/refresh     — token refresh
  3. POST /api/v1/auth/logout      — stateless logout
  4. POST /api/v1/auth/change-password — password change
  5. GET  /api/v1/auth/me          — current user profile

These tests run against local PostgreSQL.
The database must have Tier 0–5 DDL + seed data bootstrapped.

A test user is created in the database at the start of the module
and cleaned up at the end. The test user is linked to an existing
person record (the first active person found in the database).
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

# Fixtures/builders reused by name so the profile tests below build their own
# identity instead of scavenging a pre-existing Sangha Sevi (which skips on a
# freshly-built DB that holds only the bootstrap admin).
from tests.api.test_admin_credentials import (  # noqa: F401
    membership_type_pks, active_status_pk, sakha_org_pk,
    _create_member_without_credential,
)
from tests.registration_support import add_user_account


pytestmark = pytest.mark.integration


# ── Test user constants ─────────────────────────────────────────────────

TEST_PASSWORD = "TestPass1"
TEST_NEW_PASSWORD = "NewPass2x"


# ── Module-scoped fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_user2(write_conn):
    """
    A second, independent test user account (Tier 5 A4 session tests
    need two distinct accounts to prove cross-account session access
    is rejected). Same creation pattern as `test_user`, but explicitly
    excludes any person already claimed by `test_user` in this run.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    cur.execute("""
        SELECT p.person_pk, ss.sangha_sevi_id
        FROM nss.person p
        JOIN nss.sangha_sevi ss ON ss.person_pk = p.person_pk AND ss.is_active = TRUE
        LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
        WHERE p.is_active = TRUE
          AND ua.user_account_pk IS NULL
        LIMIT 1 OFFSET 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No second available person without a user account. Cannot run cross-account session tests.")

    person_pk, sangha_sevi_id = row
    password_hash = hash_password(TEST_PASSWORD)
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), password_hash))
    user_account_pk = cur.fetchone()[0]

    yield {
        "person_pk": person_pk,
        "user_account_pk": user_account_pk,
        "sangha_sevi_id": sangha_sevi_id,
    }


@pytest.fixture(scope="module")
def test_user(write_conn):
    """
    Create a test user account linked to an existing person.

    Finds the first active person without a user_account,
    creates a user_account, and cleans up after the module.
    Returns dict with person_pk, user_account_pk, sangha_sevi_id.

    NOTE: cleanup is automatic via transaction rollback in conftest.py.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()

    # Find an active person with a sangha_sevi record but no user_account
    cur.execute("""
        SELECT p.person_pk, ss.sangha_sevi_id
        FROM nss.person p
        JOIN nss.sangha_sevi ss ON ss.person_pk = p.person_pk AND ss.is_active = TRUE
        LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
        WHERE p.is_active = TRUE
          AND ua.user_account_pk IS NULL
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No available person without a user account. Cannot run auth tests.")

    person_pk, sangha_sevi_id = row

    # Create user_account
    password_hash = hash_password(TEST_PASSWORD)
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), password_hash))
    user_account_pk = cur.fetchone()[0]

    info = {
        "person_pk": person_pk,
        "user_account_pk": user_account_pk,
        "sangha_sevi_id": sangha_sevi_id,
    }

    yield info
    # No manual cleanup needed — conftest SAVEPOINT handles rollback


# ── Login tests ─────────────────────────────────────────────────────────

class TestLogin:
    """POST /api/v1/auth/login"""

    def test_login_success(self, client, test_user):
        """Valid credentials return 200 with access + refresh tokens."""
        response = client.post("/api/v1/auth/login", json={
            "login_id": test_user["sangha_sevi_id"],
            "password": TEST_PASSWORD,
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert isinstance(data["force_password_change"], bool)

    def test_login_wrong_password(self, client, test_user):
        """Wrong password returns 401."""
        response = client.post("/api/v1/auth/login", json={
            "login_id": test_user["sangha_sevi_id"],
            "password": "WrongPassword1",
        })
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_nonexistent_id(self, client):
        """Non-existent login_id returns 401 (no information leak)."""
        response = client.post("/api/v1/auth/login", json={
            "login_id": "NONEXISTENT_ID_99999",
            "password": "SomePass1",
        })
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_missing_fields(self, client):
        """Missing required fields return 422."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    def test_login_empty_password(self, client, test_user):
        """Empty password returns 422 (Pydantic min_length=1)."""
        response = client.post("/api/v1/auth/login", json={
            "login_id": test_user["sangha_sevi_id"],
            "password": "",
        })
        assert response.status_code == 422


# ── Login helper for authenticated tests ────────────────────────────────

def _login(client, test_user, password=TEST_PASSWORD):
    """Helper to login and return tokens."""
    response = client.post("/api/v1/auth/login", json={
        "login_id": test_user["sangha_sevi_id"],
        "password": password,
    })
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return response.json()


# ── Refresh tests ───────────────────────────────────────────────────────

class TestRefresh:
    """POST /api/v1/auth/refresh"""

    def test_refresh_success(self, client, test_user):
        """Valid refresh token returns a new access token."""
        tokens = _login(client, test_user)
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_refresh_invalid_token(self, client):
        """Invalid refresh token returns 401."""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "not.a.valid.token",
        })
        assert response.status_code == 401

    def test_refresh_with_access_token_fails(self, client, test_user):
        """Using an access token as refresh token returns 401."""
        tokens = _login(client, test_user)
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["access_token"],
        })
        assert response.status_code == 401


# ── Logout tests ────────────────────────────────────────────────────────

class TestLogout:
    """POST /api/v1/auth/logout"""

    def test_logout_success(self, client, test_user):
        """Authenticated logout returns success message."""
        tokens = _login(client, test_user)
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 200
        assert "message" in response.json()

    def test_logout_without_token_fails(self, client):
        """Logout without Authorization header returns 401."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 401


# ── Me tests ────────────────────────────────────────────────────────────

class TestMe:
    """GET /api/v1/auth/me"""

    def test_me_returns_profile(self, client, test_user):
        """Authenticated user gets their profile with RBAC context."""
        tokens = _login(client, test_user)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_account_pk"] == str(test_user["user_account_pk"])
        assert data["person_pk"] == str(test_user["person_pk"])
        assert data["sangha_sevi_id"] == test_user["sangha_sevi_id"]
        assert "permissions" in data
        assert "scopes" in data
        assert isinstance(data["permissions"], list)
        assert isinstance(data["scopes"], list)

    def test_me_without_token_fails(self, client):
        """GET /me without token returns 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


# ── Change password tests ───────────────────────────────────────────────

class TestChangePassword:
    """POST /api/v1/auth/change-password"""

    def test_change_password_success(self, client, test_user):
        """Valid password change returns success and new password works."""
        tokens = _login(client, test_user)

        # Change password
        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "current_password": TEST_PASSWORD,
                "new_password": TEST_NEW_PASSWORD,
            },
        )
        assert response.status_code == 200
        assert "message" in response.json()

        # Verify new password works
        response2 = client.post("/api/v1/auth/login", json={
            "login_id": test_user["sangha_sevi_id"],
            "password": TEST_NEW_PASSWORD,
        })
        assert response2.status_code == 200

        # Restore original password for other tests
        tokens2 = response2.json()
        client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {tokens2['access_token']}"},
            json={
                "current_password": TEST_NEW_PASSWORD,
                "new_password": TEST_PASSWORD,
            },
        )

    def test_change_password_wrong_current(self, client, test_user):
        """Wrong current password returns 401."""
        tokens = _login(client, test_user)
        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "current_password": "WrongCurrent1",
                "new_password": TEST_NEW_PASSWORD,
            },
        )
        assert response.status_code == 401

    def test_change_password_same_as_current(self, client, test_user):
        """New password same as current returns 422."""
        tokens = _login(client, test_user)
        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "current_password": TEST_PASSWORD,
                "new_password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 422


# ── Sessions tests (Tier 5 A4 — stateful session table) ────────────────

class TestSessions:
    """
    GET /api/v1/auth/sessions, DELETE /api/v1/auth/sessions/{session_pk}

    Covers the A4 resolution: login creates a nss.user_session row,
    logout/revoke actually invalidate the backing access token (no
    longer the Tier 5 no-op), and a session cannot be revoked by any
    account other than the one that owns it.
    """

    def test_login_creates_listable_session(self, client, test_user):
        """After login, GET /sessions shows exactly the new session,
        flagged as the caller's current one."""
        tokens = _login(client, test_user)
        response = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 200
        data = response.json()
        sessions = data["sessions"] if isinstance(data, dict) else data
        assert len(sessions) >= 1
        current = [s for s in sessions if s["is_current"]]
        assert len(current) == 1
        assert "user_session_pk" in current[0]

    def test_sessions_without_token_fails(self, client):
        """GET /sessions without a token returns 401."""
        response = client.get("/api/v1/auth/sessions")
        assert response.status_code == 401

    def test_logout_revokes_current_session(self, client, test_user):
        """After logout, the access token that was just logged out
        with is rejected on the next authenticated call — this is
        the behavior A4 explicitly closes (logout was previously a
        client-side-only no-op)."""
        tokens = _login(client, test_user)
        access_token = tokens["access_token"]

        logout_resp = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_resp.status_code == 200

        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 401
        assert "revoked" in me_resp.json()["detail"].lower()

    def test_revoke_own_session_rejects_its_token(self, client, test_user):
        """DELETE /sessions/{own session_pk} invalidates that session;
        the access token tied to it is rejected afterward."""
        tokens = _login(client, test_user)
        access_token = tokens["access_token"]

        sessions_resp = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = sessions_resp.json()
        sessions = data["sessions"] if isinstance(data, dict) else data
        current_session_pk = next(s["user_session_pk"] for s in sessions if s["is_current"])

        delete_resp = client.delete(
            f"/api/v1/auth/sessions/{current_session_pk}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert delete_resp.status_code == 200

        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 401

    def test_cannot_revoke_another_users_session(self, client, test_user, test_user2):
        """DELETE on a session_pk belonging to a different account
        returns 404 — existence of someone else's session must not
        be confirmed or denied via a 403."""
        tokens_a = _login(client, test_user)
        tokens_b = _login(client, test_user2)

        sessions_resp = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
        )
        data = sessions_resp.json()
        sessions = data["sessions"] if isinstance(data, dict) else data
        user_b_session_pk = next(s["user_session_pk"] for s in sessions if s["is_current"])

        response = client.delete(
            f"/api/v1/auth/sessions/{user_b_session_pk}",
            headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
        )
        assert response.status_code == 404

        # Confirm it genuinely wasn't revoked — user B's token still works.
        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
        )
        assert me_resp.status_code == 200

    def test_revoke_nonexistent_session_404(self, client, test_user):
        """DELETE on a syntactically valid but nonexistent session_pk
        returns 404 (not 500/422)."""
        tokens = _login(client, test_user)
        fake_pk = "00000000-0000-0000-0000-000000000000"
        response = client.delete(
            f"/api/v1/auth/sessions/{fake_pk}",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 404

    # NOTE: backward compatibility for pre-A4 tokens (no `session_pk` claim)
    # is enforced by `get_current_user`/`refresh` simply skipping the
    # revocation check when the claim is absent — see
    # api/dependencies/auth.py and api/routers/auth.py. There is no
    # practical way to mint a "pre-A4" token through the public API
    # surface (every token issued by this codebase now carries the
    # claim), so this path is covered by code inspection rather than
    # an integration test here.


# ── Profile update tests (PATCH /auth/profile) ──────────────────────────

PROFILE_PASSWORD = "ProfilePass1x"


@pytest.fixture(scope="module")
def profile_user(write_conn, sakha_org_pk, membership_type_pks, active_status_pk):
    """A self-built ACTIVE member + login (nothing scavenged)."""
    member = _create_member_without_credential(
        write_conn, sakha_org_pk, membership_type_pks["REGULAR"], active_status_pk, "PROF",
    )
    add_user_account(write_conn, member["person_pk"], PROFILE_PASSWORD, status="ACTIVE")
    return member


@pytest.fixture(scope="module")
def profile_headers(client, profile_user):
    resp = client.post("/api/v1/auth/login", json={
        "login_id": profile_user["sangha_sevi_id"], "password": PROFILE_PASSWORD,
    })
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _person(write_conn, person_pk):
    cur = write_conn.cursor()
    cur.execute(
        "SELECT first_name, middle_name, remarks, emergency_contact_name, date_of_birth "
        "FROM nss.person WHERE person_pk = %s", (person_pk,),
    )
    return cur.fetchone()


class TestUpdateProfile:
    """PATCH /api/v1/auth/profile — self-service personal-info edit."""

    URL = "/api/v1/auth/profile"

    def test_update_own_fields(self, client, write_conn, profile_user, profile_headers):
        response = client.patch(self.URL, headers=profile_headers, json={
            "first_name": "  selfedited ",
            "middle_name": "mid dle",
            "remarks": "updated by owner",
            "emergency_contact_name": "ec person",
            "date_of_birth": "1990-05-17",
        })
        assert response.status_code == 200, response.json()
        assert response.json()["message"] == "Profile updated."
        first, middle, remarks, ec_name, dob = _person(write_conn, profile_user["person_pk"])
        assert first == "Selfedited"
        assert middle == "Mid Dle"
        assert remarks == "updated by owner"
        assert ec_name == "Ec Person"
        assert str(dob) == "1990-05-17"

    def test_free_text_field_clears_when_sent_blank(self, client, write_conn, profile_user, profile_headers):
        client.patch(self.URL, headers=profile_headers, json={"remarks": "to be cleared"})
        response = client.patch(self.URL, headers=profile_headers, json={"remarks": "   "})
        assert response.status_code == 200
        assert _person(write_conn, profile_user["person_pk"])[2] is None

    def test_me_reflects_the_edit(self, client, profile_headers):
        client.patch(self.URL, headers=profile_headers, json={"first_name": "Reflected"})
        me = client.get("/api/v1/auth/me", headers=profile_headers)
        assert me.status_code == 200
        assert "Reflected" in me.json()["person_name"]

    def test_empty_body_is_422(self, client, profile_headers):
        response = client.patch(self.URL, headers=profile_headers, json={})
        assert response.status_code == 422
        assert "No fields to update" in response.json()["detail"]

    def test_blank_first_name_is_422(self, client, profile_headers):
        response = client.patch(self.URL, headers=profile_headers, json={"first_name": "   "})
        assert response.status_code == 422

    @pytest.mark.parametrize("dob", ["not-a-date", "2020-13-45", "15/01/2000"])
    def test_bad_date_of_birth_is_422(self, client, profile_headers, dob):
        response = client.patch(self.URL, headers=profile_headers, json={"date_of_birth": dob})
        assert response.status_code == 422

    def test_invalid_email_is_422(self, client, profile_headers):
        response = client.patch(self.URL, headers=profile_headers, json={"email": "nope"})
        assert response.status_code == 422

    def test_email_already_used_by_someone_else_is_409(
        self, client, write_conn, sakha_org_pk, membership_type_pks, active_status_pk, profile_headers
    ):
        other = _create_member_without_credential(
            write_conn, sakha_org_pk, membership_type_pks["REGULAR"], active_status_pk, "PROFB",
        )
        cur = write_conn.cursor()
        cur.execute("SELECT email FROM nss.person WHERE person_pk = %s", (other["person_pk"],))
        taken = cur.fetchone()[0]
        response = client.patch(self.URL, headers=profile_headers, json={"email": taken})
        assert response.status_code == 409

    def test_keeping_own_email_is_not_a_duplicate(self, client, write_conn, profile_user, profile_headers):
        cur = write_conn.cursor()
        cur.execute("SELECT email FROM nss.person WHERE person_pk = %s", (profile_user["person_pk"],))
        own = cur.fetchone()[0]
        response = client.patch(self.URL, headers=profile_headers, json={"email": own})
        assert response.status_code == 200

    def test_master_data_fk_must_be_in_the_right_category(
        self, client, membership_type_pks, profile_headers
    ):
        """A MEMBERSHIP_TYPE pk is not a valid gender."""
        response = client.patch(self.URL, headers=profile_headers, json={
            "gender_master_data_pk": membership_type_pks["REGULAR"],
        })
        assert response.status_code == 422

    def test_malformed_uuid_is_422(self, client, profile_headers):
        response = client.patch(self.URL, headers=profile_headers, json={
            "gender_master_data_pk": "not-a-uuid",
        })
        assert response.status_code == 422

    def test_overlong_field_is_422(self, client, profile_headers):
        response = client.patch(self.URL, headers=profile_headers, json={"first_name": "x" * 101})
        assert response.status_code == 422

    def test_without_token_is_401(self, client):
        assert client.patch(self.URL, json={"remarks": "x"}).status_code == 401


class TestChangePasswordPolicy:
    """POST /api/v1/auth/change-password — rules the happy-path tests above don't reach."""

    URL = "/api/v1/auth/change-password"

    @pytest.mark.parametrize("weak", ["alllowercase1", "NoDigitsHere", "Sh0rt"])
    def test_new_password_must_meet_policy(self, client, profile_headers, weak):
        response = client.post(self.URL, headers=profile_headers, json={
            "current_password": PROFILE_PASSWORD, "new_password": weak,
        })
        assert response.status_code == 422

    @pytest.mark.parametrize("body", [
        {"current_password": PROFILE_PASSWORD},
        {"new_password": "Another1Pass"},
        {},
    ])
    def test_missing_fields_are_422(self, client, profile_headers, body):
        assert client.post(self.URL, headers=profile_headers, json=body).status_code == 422

    def test_without_token_is_401(self, client):
        response = client.post(self.URL, json={
            "current_password": PROFILE_PASSWORD, "new_password": "Another1Pass",
        })
        assert response.status_code == 401
