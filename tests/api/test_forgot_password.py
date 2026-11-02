"""
NSS ERP — Tier 5.1 Forgot Password / Reset Password API tests.

Integration tests for the self-service password reset flow:
  1. POST /api/v1/auth/forgot-password  — request OTP
  2. POST /api/v1/auth/reset-password   — reset password with OTP

These tests run against local PostgreSQL.
The database must have Tier 0–5 DDL + seed data bootstrapped,
including the password_reset_token table.

A test user is created at the start of the module and cleaned
up via conftest SAVEPOINT rollback.
"""

import pytest

from tests.forgot_password_support import clear_reset_tokens, debug_otp_enabled  # noqa: F401 (fixture)
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("debug_otp_enabled")]


# ── Constants ───────────────────────────────────────────────────────────

TEST_PASSWORD = "ForgotTest1"
RESET_PASSWORD = "ResetNew2x"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def forgot_user(write_conn):
    """
    Create a test user account for forgot/reset password tests.

    Returns dict with person_pk, user_account_pk, sangha_sevi_id.
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
        pytest.skip("No available person for forgot password tests.")

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


# ── Forgot Password tests ──────────────────────────────────────────────

class TestForgotPassword:
    """POST /api/v1/auth/forgot-password"""

    def test_forgot_password_valid_user(self, client, forgot_user):
        """Valid login_id returns success with otp_debug (dev mode)."""
        response = client.post("/api/v1/auth/forgot-password", json={
            "login_id": forgot_user["sangha_sevi_id"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # Dev mode returns the OTP
        assert data.get("otp_debug") is not None
        assert len(data["otp_debug"]) == 6
        assert data["otp_debug"].isdigit()

    def test_forgot_password_nonexistent_user(self, client):
        """Non-existent login_id still returns 200 (no user enumeration)."""
        response = client.post("/api/v1/auth/forgot-password", json={
            "login_id": "NONEXISTENT_99999",
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # Should NOT include otp_debug for non-existent users
        assert data.get("otp_debug") is None

    def test_forgot_password_empty_login_id(self, client):
        """Empty login_id returns 422."""
        response = client.post("/api/v1/auth/forgot-password", json={
            "login_id": "",
        })
        assert response.status_code == 422

    def test_forgot_password_missing_field(self, client):
        """Missing login_id field returns 422."""
        response = client.post("/api/v1/auth/forgot-password", json={})
        assert response.status_code == 422


# ── Reset Password tests ───────────────────────────────────────────────

class TestResetPassword:
    """POST /api/v1/auth/reset-password"""

    def _get_otp(self, client, login_id):
        """Helper: request a forgot-password OTP and return it."""
        resp = client.post("/api/v1/auth/forgot-password", json={
            "login_id": login_id,
        })
        if resp.status_code == 429:
            pytest.skip("Rate limited — cannot generate OTP for reset test.")
        assert resp.status_code == 200
        return resp.json().get("otp_debug")

    def test_reset_password_success(self, client, forgot_user, write_conn):
        """Valid OTP + new password resets the password."""
        login_id = forgot_user["sangha_sevi_id"]

        # Clear rate limit tokens so we can generate a fresh OTP
        clear_reset_tokens(write_conn, forgot_user["user_account_pk"])

        otp = self._get_otp(client, login_id)
        assert otp is not None, "No OTP returned in dev mode"

        response = client.post("/api/v1/auth/reset-password", json={
            "login_id": login_id,
            "otp": otp,
            "new_password": RESET_PASSWORD,
        })
        assert response.status_code == 200
        assert "reset" in response.json()["message"].lower()

        # Verify new password works for login
        login_resp = client.post("/api/v1/auth/login", json={
            "login_id": login_id,
            "password": RESET_PASSWORD,
        })
        assert login_resp.status_code == 200

    def test_reset_password_invalid_login_id(self, client):
        """Non-existent login_id returns 400."""
        response = client.post("/api/v1/auth/reset-password", json={
            "login_id": "NONEXISTENT_99999",
            "otp": "123456",
            "new_password": RESET_PASSWORD,
        })
        assert response.status_code == 400
