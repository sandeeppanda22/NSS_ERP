"""
NSS ERP — Rate limiter (shared).

One ``Limiter`` for the whole app. It lives here, not in api/main.py, so a
router can attach a route-specific limit with ``@limiter.limit(...)``
without importing the application module (which imports the routers).

* Default: ``settings.RATE_LIMIT`` per client IP, applied to every route by
  ``SlowAPIMiddleware`` (api/main.py).
* Per-user routes: ``user_or_ip_key`` counts a request against the SIGNED-IN
  USER (JWT ``sub``), falling back to the client IP when there is no valid
  token. Needed where many members legitimately share one IP (a Sakha's WiFi)
  — e.g. the live attendance register poll — so one person's polling can
  neither exhaust the IP's shared budget nor be throttled by the others.
  A route decorated with ``@limiter.limit(...)`` REPLACES the global per-IP
  limit for that route (slowapi override_defaults).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from api.config import settings
from api.services.auth_service import decode_token


def user_or_ip_key(request: Request) -> str:
    """Rate-limit key: ``user:<user_account_pk>`` from a valid Bearer token, else the client IP."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        try:
            sub = decode_token(header[7:].strip()).get("sub")
        except Exception:  # expired / malformed / bad signature: auth will 401 the request itself
            sub = None
        if sub:
            return f"user:{sub}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT],
)
