"""
NSS ERP — shared helpers for the forgot/reset-password API and security tests.

Not a test file.

* ``clear_reset_tokens`` resets a user's OTP rate-limit state. The test
  session runs as the ``nss_db_writer`` role, which has no DELETE grant
  (history is never hard-deleted), so tokens are retired with UPDATE:
  marked used and back-dated out of the rate window.
* ``debug_otp_enabled`` forces ``settings.DEBUG_MODE`` on, because
  ``/auth/forgot-password`` only echoes the OTP (``otp_debug``) in debug
  mode and the deployed/local ``api/.env`` normally leaves it off. OTPs are
  never delivered anywhere else.
"""

import pytest

from api.config import settings


def clear_reset_tokens(conn, user_account_pk) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nss.password_reset_token
            SET is_used = TRUE,
                used_at = COALESCE(used_at, NOW()),
                created_at = NOW() - INTERVAL '1 year'
            WHERE user_account_pk = %s
            """,
            (str(user_account_pk),),
        )


@pytest.fixture
def debug_otp_enabled(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG_MODE", True)
