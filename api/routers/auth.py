"""
NSS ERP — Authentication router.

Tier 5 endpoints:
  POST /api/v1/auth/login            — Login with login_id + password
  POST /api/v1/auth/refresh          — Refresh access token
  POST /api/v1/auth/logout           — Logout (revokes the session server-side)
  POST /api/v1/auth/change-password  — Change own password
  POST /api/v1/auth/forgot-password  — Request OTP for password reset
  POST /api/v1/auth/reset-password   — Reset password with OTP
  GET  /api/v1/auth/me               — Current user profile + RBAC
  PATCH /api/v1/auth/profile         — Update own profile fields
  GET  /api/v1/auth/sessions         — List current user's active sessions
  DELETE /api/v1/auth/sessions/{session_pk} — Revoke one of own sessions

Authority: SOL-AUTH-001 through SOL-AUTH-004,
           Tier 5 design decisions (2026-09-15),
           Tier 5.1 self-service reset (2026-09-20),
           Tier 5 security advisory A4 — stateful sessions (2026-10-05)
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.config import settings
from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.auth import get_current_user
from api.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
    ScopeResponse,
    SessionListResponse,
    SessionResponse,
    UpdateProfileRequest,
)
from api.services.auth_service import (
    calculate_lockout_until,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_account_locked,
    verify_password,
)
from api.helpers import apply_person_profile_update, check_duplicate_contact, derive_device_label, log_audit, record_password_history, validate_and_hash_password, validate_mobile, validate_email
from api.services.rbac_service import UserContext, actor_scope_org_pks

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── POST /login ─────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    conn=Depends(get_write_connection),
) -> LoginResponse:
    """
    Authenticate with login_id + password.

    login_id accepts either a Sangha Sevi ID (e.g. SS1) or a
    Person ID (e.g. P1).  Matching is case-insensitive.

    Login chain (Tier 5 design decision #5):
      1. login_id → person_pk (try sangha_sevi_id first, then person_id)
      2. person_pk → user_account (application-level join)
      3. Verify password (Argon2)
      4. Issue JWT tokens

    Lockout: 5 failed attempts → 30-second auto-unlock.
    """
    login_id = body.login_id.strip()
    login_id_upper = login_id.upper()

    # Step 1: Resolve login_id → person_pk + sangha_sevi_id
    # Try Sangha Sevi ID first (case-insensitive), then Person ID.
    resolved_sevi_id = None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ss.person_pk, ss.sangha_sevi_id
            FROM nss.sangha_sevi ss
            WHERE UPPER(ss.sangha_sevi_id) = %s
              AND ss.is_active = TRUE
            """,
            (login_id_upper,),
        )
        sevi_row = cur.fetchone()

    if sevi_row is not None:
        person_pk = sevi_row[0]
        resolved_sevi_id = sevi_row[1]
    else:
        # Fallback: try Person ID (case-insensitive)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.person_pk
                FROM nss.person p
                WHERE UPPER(p.person_id) = %s
                  AND p.is_active = TRUE
                """,
                (login_id_upper,),
            )
            person_row = cur.fetchone()

        if person_row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )
        person_pk = person_row[0]

        # Resolve the person's Sangha Sevi ID (for JWT payload)
        # Only persons with an active SS record can login.
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ss.sangha_sevi_id
                FROM nss.sangha_sevi ss
                WHERE ss.person_pk = %s
                  AND ss.is_active = TRUE
                """,
                (str(person_pk),),
            )
            sevi_lookup = cur.fetchone()
            if sevi_lookup is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No Sangha Sevi membership found. Only registered Sangha Sevis can login.",
                )
            resolved_sevi_id = sevi_lookup[0]

    # Step 2: person_pk → user_account
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ua.user_account_pk,
                   ua.password_hash,
                   ua.account_status,
                   ua.failed_login_attempts,
                   ua.locked_until,
                   ua.force_password_change,
                   ua.password_expires_at
            FROM nss.user_account ua
            WHERE ua.person_pk = %s
              AND ua.is_active = TRUE
            """,
            (str(person_pk),),
        )
        ua_row = cur.fetchone()

    if ua_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    (
        user_account_pk,
        password_hash,
        account_status,
        failed_attempts,
        locked_until,
        force_pw_change,
        password_expires_at,
    ) = ua_row

    # Check account status
    if account_status == "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your registration is pending approval by a Sakha administrator. Please wait for approval before logging in.",
        )
    if account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    # Check lockout
    if is_account_locked(failed_attempts, locked_until):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is temporarily locked. Please try again later.",
        )

    # Step 3: Verify password
    if not verify_password(password_hash, body.password):
        # Increment failed attempts
        new_attempts = failed_attempts + 1
        lockout_until = None
        if new_attempts >= settings.MAX_FAILED_ATTEMPTS:
            lockout_until = calculate_lockout_until()

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nss.user_account
                SET failed_login_attempts = %s,
                    locked_until = %s,
                    updated_at = NOW()
                WHERE user_account_pk = %s
                """,
                (new_attempts, lockout_until, str(user_account_pk)),
            )
            log_audit(cur, action="LOGIN_FAILED", table_name="user_account", record_pk=str(user_account_pk),
                      actor_user_account_pk=str(user_account_pk),
                      module="auth", summary="Failed login attempt", is_success=False)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    # Step 4: Successful login — reset failed attempts, update last_login_at
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nss.user_account
            SET failed_login_attempts = 0,
                locked_until = NULL,
                last_login_at = %s,
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (now, str(user_account_pk)),
        )
        log_audit(cur, action="LOGIN", table_name="user_account", record_pk=str(user_account_pk),
                  actor_user_account_pk=str(user_account_pk),
                  module="auth", summary="Successful login")

    # Step 5: Issue tokens
    session_start = now

    # Tier 5 A4 — create the stateful nss.user_session row this login
    # backs, so it can be listed/revoked later and so refresh/logout can
    # check it hasn't been revoked. Mirrors the forgot-password/reset
    # cursor-per-statement pattern used elsewhere in this file.
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    device_label = derive_device_label(user_agent)
    session_expires_at = now + timedelta(days=settings.JWT_REFRESH_TOKEN_DAYS)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO nss.user_session (
                user_account_pk, issued_at, expires_at,
                user_agent, ip_address, device_label
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_session_pk
            """,
            (
                str(user_account_pk), now, session_expires_at,
                user_agent, ip_address, device_label,
            ),
        )
        session_pk = cur.fetchone()[0]

    access_token = create_access_token(
        user_account_pk=user_account_pk,
        person_pk=person_pk,
        sangha_sevi_id=resolved_sevi_id or "",
        session_start=session_start,
        session_pk=session_pk,
    )
    refresh_token = create_refresh_token(
        user_account_pk=user_account_pk,
        session_start=session_start,
        session_pk=session_pk,
    )

    # Password expiry warning
    password_expiry_warning = False
    if password_expires_at:
        warning_threshold = now + timedelta(
            days=settings.PASSWORD_EXPIRY_WARNING_DAYS
        )
        password_expiry_warning = password_expires_at <= warning_threshold

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_MINUTES * 60,
        force_password_change=force_pw_change,
        password_expiry_warning=password_expiry_warning,
    )


# ── POST /refresh ───────────────────────────────────────────────────────

@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    body: RefreshRequest,
    conn=Depends(get_write_connection),
) -> RefreshResponse:
    """
    Exchange a valid refresh token for a new access token.

    The refresh token itself is NOT rotated (stateless design).
    Absolute session max (30 days) is enforced by decode_token().

    Uses the write connection (not the read pool) because a session
    bearing a session_pk claim (Tier 5 A4) has its last_seen_at bumped
    on every refresh.
    """
    import jwt as pyjwt

    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    if payload.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Refresh token required.",
        )

    user_account_pk = UUID(payload["sub"])

    # Verify user is still active
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ua.person_pk,
                   ss.sangha_sevi_id
            FROM nss.user_account ua
            LEFT JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk
                  AND ss.is_active = TRUE
            WHERE ua.user_account_pk = %s
              AND ua.is_active = TRUE
              AND ua.account_status = 'ACTIVE'
            """,
            (str(user_account_pk),),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )

    person_pk, sangha_sevi_id = row

    # Tier 5 A4 — validate the stateful session, when the refresh token
    # carries one. Older tokens minted before this change have no
    # session_pk claim and skip this check entirely (backward compat).
    session_pk = payload.get("session_pk")
    if session_pk is not None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT revoked_at, expires_at
                FROM nss.user_session
                WHERE user_session_pk = %s
                """,
                (session_pk,),
            )
            session_row = cur.fetchone()
        if (
            session_row is None
            or session_row[0] is not None
            or session_row[1] < datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked. Please log in again.",
            )
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nss.user_session
                SET last_seen_at = NOW()
                WHERE user_session_pk = %s
                """,
                (session_pk,),
            )

    # Preserve original session_start for absolute max enforcement
    session_start_str = payload.get("session_start")
    session_start = (
        datetime.fromisoformat(session_start_str)
        if session_start_str
        else datetime.now(timezone.utc)
    )

    access_token = create_access_token(
        user_account_pk=user_account_pk,
        person_pk=person_pk,
        sangha_sevi_id=sangha_sevi_id or "",
        session_start=session_start,
        session_pk=session_pk,
    )

    return RefreshResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_MINUTES * 60,
    )


# ── POST /logout ────────────────────────────────────────────────────────

@router.post("/logout", response_model=MessageResponse)
def logout(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Logout the current user.

    Tier 5 security advisory A4 resolution: revokes the nss.user_session
    row backing the caller's own access token (session_pk is populated by
    get_current_user when the token carries that claim), so the session
    can no longer be used to refresh. The client still discards both
    tokens as before. A pre-A4 token with no session_pk claim has nothing
    to revoke — logout is then a client-side no-op, same as before.
    """
    if user.session_pk is not None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nss.user_session
                SET revoked_at = NOW()
                WHERE user_session_pk = %s
                """,
                (str(user.session_pk),),
            )
    return MessageResponse(message="Logged out successfully. Discard tokens on client.")


# ── GET /sessions ───────────────────────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> SessionListResponse:
    """
    List the authenticated user's active (non-revoked, unexpired) login
    sessions (Tier 5 A4) — the "devices logged in" view.

    is_current marks the session backing THIS request's own access
    token (user.session_pk), so the client can label "this device" and
    skip offering a self-revoke button for it (revoking it is allowed —
    it's just same-device logout — but the UI likely wants to call that
    out).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_session_pk, device_label, ip_address,
                   issued_at, last_seen_at
            FROM nss.user_session
            WHERE user_account_pk = %s
              AND revoked_at IS NULL
              AND expires_at > NOW()
            ORDER BY last_seen_at DESC
            """,
            (str(user.user_account_pk),),
        )
        rows = cur.fetchall()

    current = str(user.session_pk) if user.session_pk else None
    return SessionListResponse(
        sessions=[
            SessionResponse(
                user_session_pk=row[0],
                device_label=row[1],
                ip_address=row[2],
                issued_at=row[3],
                last_seen_at=row[4],
                is_current=(str(row[0]) == current),
            )
            for row in rows
        ]
    )


# ── DELETE /sessions/{session_pk} ────────────────────────────────────────

@router.delete("/sessions/{session_pk}", response_model=MessageResponse)
def revoke_session(
    session_pk: UUID,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Revoke one of the authenticated user's own sessions (Tier 5 A4) —
    e.g. "log out this device" from a device list.

    Returns a generic 404 whether the session_pk does not exist at all or
    belongs to someone else, so the response never discloses that a given
    session_pk belongs to another account. Revoking the caller's own
    current session is allowed with no special-casing — that's just
    same-device logout.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_account_pk
            FROM nss.user_session
            WHERE user_session_pk = %s
            """,
            (str(session_pk),),
        )
        row = cur.fetchone()

    if row is None or str(row[0]) != str(user.user_account_pk):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nss.user_session
            SET revoked_at = NOW()
            WHERE user_session_pk = %s
            """,
            (str(session_pk),),
        )

    return MessageResponse(message="Device logged out.")


# ── POST /change-password ───────────────────────────────────────────────

@router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Change the current user's own password.

    Validates:
      1. Current password is correct
      2. New password meets policy (8–128, 1 upper, 1 digit)
      3. New password differs from current (reuse prevention)
    """
    # Fetch current password hash
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT password_hash
            FROM nss.user_account
            WHERE user_account_pk = %s
              AND is_active = TRUE
            """,
            (str(user.user_account_pk),),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    current_hash = row[0]

    # Verify current password
    if not verify_password(current_hash, body.current_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    # Check reuse: new password must not match current
    if verify_password(current_hash, body.new_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="New password must differ from the current password.",
        )

    # Validate new password policy, hash, and compute expiry
    new_hash, new_expiry = validate_and_hash_password(body.new_password)

    with conn.cursor() as cur:
        # Update user_account
        actor = user.actor_pk
        cur.execute(
            """
            UPDATE nss.user_account
            SET password_hash = %s,
                password_expires_at = %s,
                force_password_change = FALSE,
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (new_hash, new_expiry, str(user.user_account_pk)),
        )

        # Record in password_history
        record_password_history(cur, str(user.user_account_pk), new_hash, "USER_CHANGE", actor_pk=actor)
        log_audit(cur, action="PASSWORD_CHANGE", table_name="user_account", record_pk=str(user.user_account_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="auth", summary="User changed own password")

    return MessageResponse(message="Password changed successfully.")


# ── POST /forgot-password ──────────────────────────────────────────────

def _resolve_login_id(login_id: str, conn):
    """
    Resolve a login_id to (person_pk, user_account_pk, masked_contact).

    Returns None if not found.
    """
    login_id_upper = login_id.strip().upper()

    with conn.cursor() as cur:
        # Try Sangha Sevi ID first
        cur.execute(
            """
            SELECT ss.person_pk, ss.sangha_sevi_id
            FROM nss.sangha_sevi ss
            WHERE UPPER(ss.sangha_sevi_id) = %s
              AND ss.is_active = TRUE
            """,
            (login_id_upper,),
        )
        sevi_row = cur.fetchone()

    if sevi_row is not None:
        person_pk = sevi_row[0]
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.person_pk
                FROM nss.person p
                WHERE UPPER(p.person_id) = %s
                  AND p.is_active = TRUE
                """,
                (login_id_upper,),
            )
            person_row = cur.fetchone()
        if person_row is None:
            return None
        person_pk = person_row[0]

    # Get user_account + contact info for masking
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ua.user_account_pk,
                   p.email,
                   p.mobile_number,
                   p.country_phone_code
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            WHERE ua.person_pk = %s
              AND ua.is_active = TRUE
              AND ua.account_status = 'ACTIVE'
            """,
            (str(person_pk),),
        )
        ua_row = cur.fetchone()

    if ua_row is None:
        return None

    user_account_pk, email, mobile, phone_code = ua_row

    # Build masked contact string
    masked = None
    if email:
        parts = email.split("@")
        if len(parts) == 2:
            local = parts[0]
            show = local[:2] if len(local) > 2 else local[:1]
            masked = f"{show}{'*' * (len(local) - len(show))}@{parts[1]}"
    elif mobile:
        show = mobile[-3:] if len(mobile) > 3 else mobile
        masked = f"{'*' * (len(mobile) - len(show))}{show}"
        if phone_code:
            masked = f"{phone_code} {masked}"

    return person_pk, user_account_pk, masked


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    conn=Depends(get_write_connection),
) -> ForgotPasswordResponse:
    """
    Request a password reset OTP.

    Generates a 6-digit OTP valid for 15 minutes.
    Rate-limited to 3 requests per hour per user.

    NOTE: OTP is returned in the response under `otp_debug` ONLY when
    DEBUG_MODE=true (env var). In production, otp_debug is always None.
    Remove the `otp_debug` field entirely once email/SMS delivery is integrated.
    """
    result = _resolve_login_id(body.login_id, conn)

    # Always return a generic success message to prevent user enumeration
    generic_response = ForgotPasswordResponse(
        message="If an account exists with that ID, a reset OTP has been generated.",
        masked_contact=None,
        otp_debug=None,
    )

    if result is None:
        return generic_response

    person_pk, user_account_pk, masked_contact = result

    # Rate limit: count active (unused, unexpired) tokens in the last hour
    now = datetime.now(timezone.utc)
    rate_window = now - timedelta(minutes=settings.RESET_OTP_RATE_LIMIT_MINUTES)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM nss.password_reset_token
            WHERE user_account_pk = %s
              AND created_at >= %s
            """,
            (str(user_account_pk), rate_window),
        )
        recent_count = cur.fetchone()[0]

    if recent_count >= settings.RESET_OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset requests. Please try again later.",
        )

    # Invalidate any existing unused tokens for this user
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nss.password_reset_token
            SET is_used = TRUE, used_at = %s
            WHERE user_account_pk = %s
              AND is_used = FALSE
            """,
            (now, str(user_account_pk)),
        )

    # Generate OTP
    otp_plain = "".join(
        [str(secrets.randbelow(10)) for _ in range(settings.RESET_OTP_LENGTH)]
    )
    otp_hash = hash_password(otp_plain)
    expires_at = now + timedelta(minutes=settings.RESET_OTP_EXPIRY_MINUTES)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO nss.password_reset_token (
                user_account_pk, otp_hash, expires_at
            ) VALUES (%s, %s, %s)
            """,
            (str(user_account_pk), otp_hash, expires_at),
        )

    # TODO: Send OTP via email/SMS when service is available.
    # For now, return in response for development/testing.

    return ForgotPasswordResponse(
        message="If an account exists with that ID, a reset OTP has been generated.",
        masked_contact=masked_contact,
        otp_debug=otp_plain if settings.DEBUG_MODE else None,
    )


# ── POST /reset-password ──────────────────────────────────────────────

@router.post("/reset-password", response_model=MessageResponse)
def reset_password_with_otp(
    body: ResetPasswordRequest,
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Reset password using the OTP from forgot-password.

    Validates:
      1. login_id resolves to an active user
      2. OTP matches an unused, unexpired token for that user
      3. New password meets policy
    """
    result = _resolve_login_id(body.login_id, conn)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid login ID or OTP.",
        )

    person_pk, user_account_pk, _ = result
    now = datetime.now(timezone.utc)

    # Find active (unused, unexpired) tokens for this user
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT password_reset_token_pk, otp_hash
            FROM nss.password_reset_token
            WHERE user_account_pk = %s
              AND is_used = FALSE
              AND expires_at > %s
            ORDER BY created_at DESC
            """,
            (str(user_account_pk), now),
        )
        tokens = cur.fetchall()

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    # Verify OTP against each active token (should be at most 1 due to invalidation)
    matched_token_pk = None
    for token_pk, otp_hash in tokens:
        if verify_password(otp_hash, body.otp):
            matched_token_pk = token_pk
            break

    if matched_token_pk is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    # Validate new password
    new_hash, new_expiry = validate_and_hash_password(body.new_password)

    # Mark token as used
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nss.password_reset_token
            SET is_used = TRUE, used_at = %s
            WHERE password_reset_token_pk = %s
            """,
            (now, str(matched_token_pk)),
        )

    # Reset the password
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nss.user_account
            SET password_hash = %s,
                password_expires_at = %s,
                force_password_change = FALSE,
                failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = NOW()
            WHERE user_account_pk = %s
            """,
            (new_hash, new_expiry, str(user_account_pk)),
        )

        # Record in password_history
        record_password_history(cur, str(user_account_pk), new_hash, "SELF_RESET")
        log_audit(cur, action="PASSWORD_RESET", table_name="user_account", record_pk=str(user_account_pk),
                  module="auth", summary="Password reset via OTP")

    return MessageResponse(message="Password has been reset. You can now sign in.")


# ── GET /me ─────────────────────────────────────────────────────────────

@router.get("/me", response_model=MeResponse)
def me(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MeResponse:
    """
    Return the authenticated user's profile and RBAC context.

    Includes: person name, account status, permissions, scopes.
    """
    # Get person name and account details
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.first_name,
                   p.middle_name,
                   p.last_name,
                   ua.account_status,
                   ua.force_password_change,
                   ua.password_expires_at,
                   ua.last_login_at
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            WHERE ua.user_account_pk = %s
            """,
            (str(user.user_account_pk),),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    first, middle, last, acct_status, force_pw, pw_expires, last_login = row

    # Build display name
    name_parts = [p for p in (first, middle, last) if p]
    person_name = " ".join(name_parts) if name_parts else None

    # Resolve organization names for scoped roles
    org_info = {}  # organization_pk → {name, type_code}
    scoped_org_pks = [
        str(s.organization_pk) for s in user.scopes if s.organization_pk is not None
    ]
    if scoped_org_pks:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(scoped_org_pks))
            cur.execute(
                f"""
                SELECT o.organization_pk,
                       o.organization_name,
                       md.value_code
                FROM nss.organization o
                JOIN nss.master_data md
                    ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE o.organization_pk IN ({placeholders})
                """,
                scoped_org_pks,
            )
            for org_pk, org_name, type_code in cur.fetchall():
                org_info[str(org_pk)] = {"name": org_name, "type_code": type_code}

    # Resolve role names from role_master
    role_names = {}  # role_code → role_name
    role_codes = list({s.role_code for s in user.scopes})
    if role_codes:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(role_codes))
            cur.execute(
                f"SELECT role_code, role_name FROM nss.role_master WHERE role_code IN ({placeholders})",
                role_codes,
            )
            for rc, rn in cur.fetchall():
                role_names[rc] = rn

    # Fetch active sakha affiliation (local_sakha_erp_id + sakha name)
    local_sakha_erp_id = None
    sakha_name = None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT msa.local_sakha_erp_id,
                   o.organization_name
            FROM nss.sangha_sevi ss
            JOIN nss.membership_sakha_affiliation msa
                ON msa.sangha_sevi_pk = ss.sangha_sevi_pk
               AND msa.affiliation_status IN ('ACTIVE', 'REACTIVATED')
               AND msa.effective_to IS NULL
            JOIN nss.organization o
                ON o.organization_pk = msa.organization_pk
            WHERE ss.person_pk = %s
              AND ss.is_active = TRUE
            LIMIT 1
            """,
            (str(user.person_pk),),
        )
        aff_row = cur.fetchone()
        if aff_row:
            local_sakha_erp_id = aff_row[0]
            sakha_name = aff_row[1]

    # ADMIN-BR-076/077: full recursive scope subtree, for frontend
    # scope-aware filtering (e.g. admin.js's govAssignableBodies). None
    # means global reach — see schemas.auth.MeResponse.admin_scope_org_pks.
    with conn.cursor() as cur:
        admin_scope_org_pks = actor_scope_org_pks(cur, user)

    return MeResponse(
        user_account_pk=user.user_account_pk,
        person_pk=user.person_pk,
        sangha_sevi_pk=user.sangha_sevi_pk,
        sangha_sevi_id=user.sangha_sevi_id,
        person_name=person_name,
        local_sakha_erp_id=local_sakha_erp_id,
        sakha_name=sakha_name,
        account_status=acct_status,
        force_password_change=force_pw,
        password_expires_at=pw_expires,
        last_login_at=last_login,
        permissions=sorted(user.permissions),
        scopes=[
            ScopeResponse(
                role_code=s.role_code,
                role_name=role_names.get(s.role_code),
                scope_level=s.scope_level,
                organization_pk=s.organization_pk,
                organization_name=(
                    org_info.get(str(s.organization_pk), {}).get("name")
                    if s.organization_pk else None
                ),
                organization_type_code=(
                    org_info.get(str(s.organization_pk), {}).get("type_code")
                    if s.organization_pk else None
                ),
            )
            for s in user.scopes
        ],
        admin_scope_org_pks=(
            [UUID(pk) for pk in sorted(admin_scope_org_pks)]
            if admin_scope_org_pks is not None else None
        ),
    )


# ── PATCH /profile ─────────────────────────────────────────────────────

@router.patch("/profile", response_model=MessageResponse)
def update_profile(
    body: UpdateProfileRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Update the authenticated user's own person record.

    Full self-service personal-info edit (SOL-PERSON, 2026-10-03): name
    (first/middle/last), date of birth, demographics (gender / marital
    status / blood group), contact (mobile / country code / email),
    emergency contact, and remarks. Aadhaar and photo are deliberately
    excluded — they are sensitive and have dedicated flows.

    All field validation, category-checking of the master-data FKs,
    effective-value contact validation, and the duplicate-contact guard
    are delegated to helpers.apply_person_profile_update() — the single
    shared code path, so this self-service surface and any future admin
    person-edit surface enforce byte-identical rules.
    """
    with conn.cursor() as cur:
        changed = apply_person_profile_update(
            cur,
            person_pk=str(user.person_pk),
            body=body,
            updated_by_sangha_sevi_pk=(
                str(user.sangha_sevi_pk) if user.sangha_sevi_pk else None
            ),
        )
        if not changed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No fields to update.",
            )

        log_audit(
            cur,
            action="UPDATE",
            table_name="person",
            record_pk=str(user.person_pk),
            actor_pk=user.actor_pk,
            actor_user_account_pk=str(user.user_account_pk),
            module="auth",
            summary="Updated own profile",
        )

    return MessageResponse(message="Profile updated.")
