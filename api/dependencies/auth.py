"""
NSS ERP — Authentication dependency.

Extracts and validates JWT from the Authorization header.
Returns a UserContext with full RBAC information.

Usage in endpoints:
    @router.get("/protected")
    def protected(user: UserContext = Depends(get_current_user)):
        ...

    @router.get("/optional")
    def optional(user: UserContext | None = Depends(get_optional_user)):
        ...
"""

from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.database import checkout_write, get_connection, release_write
from api.services.auth_service import decode_token
from api.services.rbac_service import UserContext, load_user_context

# HTTPBearer extracts "Bearer <token>" from the Authorization header
_bearer_scheme = HTTPBearer(auto_error=True)
_bearer_scheme_optional = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    conn=Depends(get_connection),
) -> UserContext:
    """
    Mandatory auth dependency.

    Extracts JWT from Authorization header, validates it, loads
    the user's RBAC context from the database.

    Raises 401 if:
      - No token / invalid format
      - Token expired or invalid
      - Absolute session max exceeded
      - Token is not an access token
      - User account not found or inactive
    """
    token = credentials.credentials

    # Decode and validate JWT
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Must be an access token (not refresh)
    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load full RBAC context from database
    user_account_pk = UUID(payload["sub"])
    user_ctx = load_user_context(conn, user_account_pk)

    if user_ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate the stateful session (Tier 5 A4), when the token carries one.
    # Older tokens minted before this change have no session_pk claim and
    # skip this check entirely — backward compatible until they expire.
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
            row = cur.fetchone()
        if (
            row is None
            or row[0] is not None
            or row[1] < datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_ctx.session_pk = UUID(session_pk)

    # Set session variables for the DB audit trigger.
    # nss.fn_audit_trigger() reads these to identify the actor.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('nss.actor_user_account_pk', %s, TRUE)",
            (str(user_ctx.user_account_pk),),
        )
        if user_ctx.sangha_sevi_pk:
            cur.execute(
                "SELECT set_config('nss.actor_sangha_sevi_pk', %s, TRUE)",
                (str(user_ctx.sangha_sevi_pk),),
            )

    return user_ctx


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme_optional),
    conn=Depends(get_connection),
) -> UserContext | None:
    """
    Optional auth dependency.

    Returns UserContext if a valid token is present, None otherwise.
    Does not raise 401 — useful for endpoints that behave differently
    for authenticated vs anonymous users.
    """
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

    if payload.get("token_type") != "access":
        return None

    try:
        user_account_pk = UUID(payload["sub"])
    except (ValueError, KeyError):
        return None

    user_ctx = load_user_context(conn, user_account_pk)

    # Set session variables for the DB audit trigger
    if user_ctx is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('nss.actor_user_account_pk', %s, TRUE)",
                (str(user_ctx.user_account_pk),),
            )
            if user_ctx.sangha_sevi_pk:
                cur.execute(
                    "SELECT set_config('nss.actor_sangha_sevi_pk', %s, TRUE)",
                    (str(user_ctx.sangha_sevi_pk),),
                )

    return user_ctx


def get_write_connection(
    user: UserContext | None = Depends(get_optional_user),
):
    """
    Write connection (nss_db_writer) with the audit actor set.

    The DB audit trigger (nss.fn_audit_trigger) reads the nss.actor_*
    session GUCs to record WHO made each change — in both
    system_event_log and field_change_log. Those GUCs must be set on
    the SAME connection the writes (and therefore the trigger) run on,
    i.e. the write connection — not the read connection used by
    get_current_user. This dependency resolves the caller from the
    bearer token (if present) and sets the GUCs here, so the actor is
    captured without touching any endpoint body.

    Public endpoints (no token) write with a NULL actor, as before.

    Auto-commits on success, rolls back on exception. The GUCs are
    transaction-local (set_config(..., TRUE)) and live for the whole
    handler transaction, which commits only after the handler returns.

    Usage as a FastAPI dependency:
        def endpoint(conn=Depends(get_write_connection)): ...
    """
    conn = checkout_write()
    try:
        conn.autocommit = False
        if user is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('nss.actor_user_account_pk', %s, TRUE)",
                    (str(user.user_account_pk),),
                )
                if user.sangha_sevi_pk:
                    cur.execute(
                        "SELECT set_config('nss.actor_sangha_sevi_pk', %s, TRUE)",
                        (str(user.sangha_sevi_pk),),
                    )
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_write(conn)
