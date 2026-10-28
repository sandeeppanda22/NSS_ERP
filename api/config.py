"""
NSS ERP — Application configuration.

Reads database connection parameters from environment variables.
Uses python-dotenv for local development (.env file at api/ level).

No sensitive defaults — all DB parameters are required.
JWT secret has no default — must be set explicitly.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the api/ directory if present
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, encoding="utf-8-sig")


class Settings:
    """Application settings sourced from environment variables."""

    # ── Database (read-only pool) ────────────────────────────────────────
    DB_NAME: str = os.environ.get("DB_NAME", "")
    DB_USER: str = os.environ.get("DB_USER", "")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")
    DB_HOST: str = os.environ.get("DB_HOST", "localhost")
    DB_PORT: str = os.environ.get("DB_PORT", "5432")

    # ── Database (write pool — Tier 5) ───────────────────────────────────
    DB_WRITE_USER: str = os.environ.get("DB_WRITE_USER", "")
    DB_WRITE_PASSWORD: str = os.environ.get("DB_WRITE_PASSWORD", "")

    # ── API ──────────────────────────────────────────────────────────────
    API_PORT: int = int(os.environ.get("API_PORT", "8001"))
    DISABLE_DOCS: bool = os.environ.get("DISABLE_DOCS", "").lower() in ("1", "true", "yes")

    # ── Security ─────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "").split(",")
        if o.strip()
    ]
    # Global per-IP rate limit applied to EVERY endpoint (api/main.py's
    # Limiter default_limits). Raised 60->300/minute 2026-10-27: a single
    # authenticated dashboard load legitimately fans out to 20-30 calls
    # (org children-stats + subtree stats + governance's per-body election
    # lookups + correspondence + attendance), so 60/min 429'd real users
    # after a refresh or two. Login brute-force is NOT weakened by this:
    # it is throttled at the ACCOUNT level (MAX_FAILED_ATTEMPTS ->
    # lockout in auth.py), not by this IP limit; the forgot-password OTP
    # has its own app-level 3/hour throttle (RESET_OTP_RATE_LIMIT_MINUTES).
    # 300/min is the IP-velocity backstop. Override per environment via
    # the RATE_LIMIT env var.
    RATE_LIMIT: str = os.environ.get("RATE_LIMIT", "300/minute")

    # ── Content-Security-Policy (Tier 5 — advisory A2) ───────────────────
    # CSP_ENABLED      — emit the header at all (default on).
    # CSP_REPORT_ONLY  — emit as Content-Security-Policy-Report-Only, which
    #                    reports violations without blocking. Use this when
    #                    rolling out a tightened policy to a live deployment.
    # CSP_SCRIPT_SRC_EXTRA / CSP_STYLE_SRC_EXTRA — comma-separated extra
    #                    origins, so adding a CDN never needs a code change.
    CSP_ENABLED: bool = os.environ.get("CSP_ENABLED", "true").lower() in ("1", "true", "yes")
    CSP_REPORT_ONLY: bool = os.environ.get("CSP_REPORT_ONLY", "").lower() in ("1", "true", "yes")
    CSP_SCRIPT_SRC_EXTRA: list[str] = [
        o.strip()
        for o in os.environ.get("CSP_SCRIPT_SRC_EXTRA", "").split(",")
        if o.strip()
    ]
    CSP_STYLE_SRC_EXTRA: list[str] = [
        o.strip()
        for o in os.environ.get("CSP_STYLE_SRC_EXTRA", "").split(",")
        if o.strip()
    ]

    # ── Debug / Development ─────────────────────────────────────────────
    DEBUG_MODE: bool = os.environ.get("DEBUG_MODE", "").lower() in ("1", "true", "yes")

    # DEV_LIVE_RELOAD — development-only browser auto-reload. When truthy,
    # api/main.py registers GET /__dev/frontend-version (an mtime fingerprint
    # of frontend/) and injects frontend/assets/js/dev-reload.js into every
    # page served by _serve_page(), so saving a frontend file reloads the open
    # tab. Off by default; must never be set in a deployed environment.
    DEV_LIVE_RELOAD: bool = os.environ.get("DEV_LIVE_RELOAD", "").lower() in ("1", "true", "yes")

    # ── Connection Pools ────────────────────────────────────────────────
    DB_READ_POOL_MIN: int = int(os.environ.get("DB_READ_POOL_MIN", "2"))
    DB_READ_POOL_MAX: int = int(os.environ.get("DB_READ_POOL_MAX", "15"))
    DB_WRITE_POOL_MIN: int = int(os.environ.get("DB_WRITE_POOL_MIN", "1"))
    DB_WRITE_POOL_MAX: int = int(os.environ.get("DB_WRITE_POOL_MAX", "5"))

    # ── JWT (Tier 5 — Authentication) ────────────────────────────────────
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_MINUTES: int = int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "30"))
    JWT_REFRESH_TOKEN_DAYS: int = int(os.environ.get("JWT_REFRESH_TOKEN_DAYS", "7"))
    JWT_ABSOLUTE_SESSION_DAYS: int = int(os.environ.get("JWT_ABSOLUTE_SESSION_DAYS", "30"))

    # ── Lockout Policy ───────────────────────────────────────────────────
    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_DURATION_SECONDS: int = 30

    # ── Password Policy ──────────────────────────────────────────────────
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_EXPIRY_DAYS: int = 365
    PASSWORD_EXPIRY_WARNING_DAYS: int = 30

    # ── Password Reset (Forgot Password) ────────────────────────────────
    RESET_OTP_LENGTH: int = 6
    RESET_OTP_EXPIRY_MINUTES: int = 15
    RESET_OTP_MAX_ATTEMPTS: int = 3        # max active OTPs per user
    RESET_OTP_RATE_LIMIT_MINUTES: int = 60 # rate window (max 3 requests per hour)

    def validate(self) -> None:
        """Raise if required settings are missing."""
        missing = []
        if not self.DB_NAME:
            missing.append("DB_NAME")
        if not self.DB_USER:
            missing.append("DB_USER")
        if not self.DB_PASSWORD:
            missing.append("DB_PASSWORD")
        if missing:
            raise RuntimeError(
                f"Required environment variables not set: {', '.join(missing)}. "
                f"Create api/.env or export them before starting the server."
            )

    def validate_auth(self) -> None:
        """Raise if auth-required settings are missing."""
        missing = []
        if not self.JWT_SECRET_KEY:
            missing.append("JWT_SECRET_KEY")
        if not self.DB_WRITE_USER:
            missing.append("DB_WRITE_USER")
        if not self.DB_WRITE_PASSWORD:
            missing.append("DB_WRITE_PASSWORD")
        if missing:
            raise RuntimeError(
                f"Auth-required environment variables not set: {', '.join(missing)}. "
                f"These are required for Tier 5 authentication endpoints."
            )


settings = Settings()
