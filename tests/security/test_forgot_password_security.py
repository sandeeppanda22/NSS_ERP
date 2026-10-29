"""
NSS ERP — Tier 5.1 Forgot Password / Reset Password security tests.

Security-focused subset extracted from tests/api/test_forgot_password.py:
  1. POST /api/v1/auth/forgot-password  — rate limiting
  2. POST /api/v1/auth/reset-password   — OTP/session hardening
     (wrong OTP, expired OTP, bad OTP format, weak password, single-use OTP)

These tests run against local PostgreSQL.
The database must have Tier 0-5 DDL + seed data bootstrapped,
including the password_reset_token table.

A test user is created at the start of the module and cleaned
up via conftest SAVEPOINT rollback.
"""

import pytest

from tests.forgot_password_support import clear_reset_tokens, debug_otp_enabled  # noqa: F401 (fixture)


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

    def test_forgot_password_rate_limiting(self, client, forgot_user):
        """After 3 requests in the rate window, returns 429."""
        login_id = forgot_user["sangha_sevi_id"]

        # Send 3 requests (the config allows max 3)
        for _ in range(3):
            resp = client.post("/api/v1/auth/forgot-password", json={
                "login_id": login_id,
            })
            # First few should succeed (or the 3rd+ might hit limit
            # depending on whether the test_forgot_password_valid_user
            # already consumed one slot)

        # The 4th request should be rate-limited
        response = client.post("/api/v1/auth/forgot-password", json={
            "login_id": login_id,
        })
        assert response.status_code == 429
        assert "too many" in response.json()["detail"].lower()


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

    def test_reset_password_wrong_otp(self, client, forgot_user, write_conn):
        """Wrong OTP returns 400."""
        login_id = forgot_user["sangha_sevi_id"]

        # Clear rate limit tokens
        clear_reset_tokens(write_conn, forgot_user["user_account_pk"])

        otp = self._get_otp(client, login_id)
        assert otp is not None

        response = client.post("/api/v1/auth/reset-password", json={
            "login_id": login_id,
            "otp": "000000",  # wrong OTP
            "new_password": RESET_PASSWORD,
        })
        assert response.status_code == 400

    def test_reset_password_expired_otp(self, client, forgot_user, write_conn):
        """An expired OTP returns 400."""
        login_id = forgot_user["sangha_sevi_id"]

        # Clear tokens and insert an expired one manually
        clear_reset_tokens(write_conn, forgot_user["user_account_pk"])
        from api.services.auth_service import hash_password
        otp_hash = hash_password("123456")
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.password_reset_token (
                    user_account_pk, otp_hash, expires_at
                ) VALUES (%s, %s, NOW() - INTERVAL '1 hour')
            """, (str(forgot_user["user_account_pk"]), otp_hash))

        response = client.post("/api/v1/auth/reset-password", json={
            "login_id": login_id,
            "otp": "123456",
            "new_password": RESET_PASSWORD,
        })
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    def test_reset_password_bad_otp_format(self, client, forgot_user):
        """Non-6-digit OTP returns 422 (Pydantic validation)."""
        response = client.post("/api/v1/auth/reset-password", json={
            "login_id": forgot_user["sangha_sevi_id"],
            "otp": "abc",
            "new_password": RESET_PASSWORD,
        })
        assert response.status_code == 422

    def test_reset_password_weak_password(self, client, forgot_user, write_conn):
        """Password violating policy returns 422."""
        login_id = forgot_user["sangha_sevi_id"]

        # Clear rate limit tokens
        clear_reset_tokens(write_conn, forgot_user["user_account_pk"])

        otp = self._get_otp(client, login_id)
        assert otp is not None

        response = client.post("/api/v1/auth/reset-password", json={
            "login_id": login_id,
            "otp": otp,
            "new_password": "weak",  # too short, no uppercase, no digit
        })
        assert response.status_code == 422

    def test_reset_password_otp_single_use(self, client, forgot_user, write_conn):
        """OTP cannot be reused after successful reset."""
        login_id = forgot_user["sangha_sevi_id"]

        # Clear rate limit tokens
        clear_reset_tokens(write_conn, forgot_user["user_account_pk"])

        otp = self._get_otp(client, login_id)
        assert otp is not None

        # First reset should succeed
        resp1 = client.post("/api/v1/auth/reset-password", json={
            "login_id": login_id,
            "otp": otp,
            "new_password": "SingleUse1",
        })
        assert resp1.status_code == 200

        # Second reset with same OTP should fail
        resp2 = client.post("/api/v1/auth/reset-password", json={
            "login_id": login_id,
            "otp": otp,
            "new_password": "SingleUse2",
        })
        assert resp2.status_code == 400
