# API Layer — Per-File Code Explanations

| Field       | Value                                    |
|-------------|------------------------------------------|
| Document    | API_CODE_EXPLANATIONS                    |
| Version     | 1.7                                      |
| Scope       | All source files under `api/` (except `api/middleware.py`) |
| Status      | Complete for Tier 0-4 (updated: Tier 4 Family graph/sakha-alignment/membership-summary, first `api/services/` file). **Tier 5 files are not covered** — `routers/auth.py`, `admin.py`, `registration.py`, `claim_approval.py`, `audit.py`, `geo_approval.py`, `schemas/{auth,admin,audit,geo_approval}.py`, `dependencies/`, `services/{auth_service,rbac_service}.py` and the Tier 5 additions to `config.py`/`database.py`/`main.py`/`helpers.py`/`foundation.py`; see `api/README.md` and `docs/03_Solution/api/API_CONTRACT.md` |

---

## 1. Purpose of this document

This document is the authoritative, current, **per-file** reference for the NSS ERP API layer —
every source file under `api/` (FastAPI, raw psycopg2, no ORM) *except* `api/middleware.py`,
which lives in its own dedicated `SECURITY_CODE_EXPLANATIONS.md` alongside the security-relevant
portions of `api/config.py` and `api/main.py`. Likewise, `tests/` has its own dedicated
`TESTING_CODE_EXPLANATIONS.md` rather than being folded in here. `api/services/` is a new
subdirectory (first file: `family_graph.py`) alongside `api/routers/` and `api/schemas/` — it
holds framework-agnostic business logic (graph construction/traversal) that a router calls into,
rather than SQL-adjacent request handling or Pydantic response shapes. For each file this
document covers, it gives:

- **Requirement** — why the file exists: what problem or need it addresses, and what would
  break or be missing without it.
- **Line-by-line** — a walkthrough of the actual code, block by block, naming real functions,
  variables, and line numbers, so that someone unfamiliar with the code could reconstruct its
  behaviour from the explanation alone.

**How the files below fit together** — read this diagram first if you're new to the codebase;
every section after it explains one box in detail:

```
Uvicorn starts api.main:app
        │
        ▼
api/config.py    ── settings = Settings() reads api/.env once, at import time (§2.1)
        │
        ▼
api/main.py      ── builds the FastAPI() app, registers security middleware (see
        │            SECURITY_CODE_EXPLANATIONS.md), includes both routers, mounts the
        │            frontend (§2.3)
        │
        ▼
An HTTP request arrives for e.g. GET /api/v1/foundation/categories
        │
        ▼
api/routers/foundation.py   ── the matching @router.get(...) handler runs (§2.5)
        │                       ├─ Depends(get_connection) borrows a pooled connection
        │                       │  from api/database.py (§2.2)
        │                       ├─ runs a parameterized SELECT against nss.*
        │                       └─ zips (column names, row values) into a dict per row
        ▼
api/schemas/foundation.py   ── that dict is unpacked into a Pydantic response model
        │                       (§2.7), which validates types and becomes the JSON body
        ▼
Response returns to the client (security headers/CORS/rate-limit already applied on the
way — see SECURITY_CODE_EXPLANATIONS.md)
```

Every router handler in `bootstrap.py`/`foundation.py`/`organization.py`/`person.py` follows this
exact same shape: `Depends(get_connection)` → parameterized SQL → zip into dicts → unpack into a
schema class. Once you've read one endpoint in §2.4/§2.5, every other endpoint in the file is the
same pattern with a different table and a different response model — that repetition is
deliberate, not something to search for a shortcut around. `person.py` (§2.11) is the one file
that pulls its zip/dict/unpack step from a shared `api/helpers.py` module (`rows_to_models`/
`row_to_model`) instead of a per-router-local copy of the same two functions — the underlying
shape is unchanged.

**This document replaces three retired docs** that covered the same files but organized by
tier/feature instead of by file: `TIER0_VERTICAL_SLICE.md` (Tier 0 Bootstrap — database through
UI), `TIER1_FOUNDATION.md` (Tier 1 Foundation — schemas through UI), and `SECURITY_HARDENING.md`
(the cross-tier security middleware stack). Those three documents interleaved narration of
`api/config.py`, `api/main.py`, etc. across multiple sections because each was written when a
new tier or cross-cutting concern landed. This document instead gives each core application file
exactly one section, covering its full current behaviour regardless of which tier introduced
which part of it — with security and testing code carved out into their own peer documents (see
above) rather than folded in here. The database DDL/seed narration that lived in
`TIER0_VERTICAL_SLICE.md` (table definitions, roles, grants) is **not** duplicated here — it
belongs to `DATABASE_CODE_EXPLANATIONS.md`, not this document.

---

## 2. Files

### 2.1 `api/config.py`

**Requirement**

The application needs database credentials and a handful of security/runtime toggles
(CORS origins, rate limit, docs visibility, listen port) sourced from the environment rather than
hardcoded, so the same codebase runs unmodified against a local Postgres instance in development
and a Neon.dev instance in production. Without this file, `api/database.py` would have nowhere
to read `DB_NAME`/`DB_USER`/`DB_PASSWORD` from, and `api/main.py` would have no single place to
turn "is `CORS_ORIGINS` configured?" or "is `DISABLE_DOCS` set?" into a Python value. The
`validate()` method exists so that a missing credential fails immediately and legibly (naming
exactly which variables are absent) instead of surfacing later as an opaque `psycopg2` connection
error.

**Line-by-line**

Lines 1–8 — module docstring:

```python
"""
NSS ERP — Application configuration.

Reads database connection parameters from environment variables.
Uses python-dotenv for local development (.env file at api/ level).

No sensitive defaults — all DB parameters are required.
"""
```

States the file reads DB connection parameters from environment variables, uses
`python-dotenv` for local development, and that there are "no sensitive defaults" (i.e.
`DB_NAME`/`DB_USER`/`DB_PASSWORD` have no fallback value).

Line 10:

```python
import os
```

Used to read environment variables via `os.environ.get`.

Line 11:

```python
from pathlib import Path
```

Cross-platform path handling (works identically on macOS/Linux and Windows) to locate the
`.env` file.

Line 13:

```python
from dotenv import load_dotenv
```

Loads a `.env` file's contents into `os.environ` so the rest of the module can read them
uniformly whether they came from a real shell export or a local `.env` file.

Line 16:

```python
_env_path = Path(__file__).resolve().parent / ".env"
```

Resolves to `api/.env` regardless of the current working directory the process was started
from (`__file__` is `api/config.py`, so `.parent` is the `api/` directory).

Line 17:

```python
load_dotenv(_env_path, encoding="utf-8-sig")
```

Loads that file into `os.environ`. `encoding="utf-8-sig"` strips a UTF-8 byte-order-mark,
which some Windows editors write into `.env` files and which would otherwise corrupt the first
variable name. If the file doesn't exist, `load_dotenv` silently does nothing — the app still
works if env vars are set some other way (e.g. Render's dashboard).

Line 20:

```python
class Settings:
```

A plain class (not a Pydantic `BaseSettings`) used as a module-level configuration object.

Lines 23–27:

```python
    DB_NAME: str = os.environ.get("DB_NAME", "")
    DB_USER: str = os.environ.get("DB_USER", "")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")
    DB_HOST: str = os.environ.get("DB_HOST", "localhost")
    DB_PORT: str = os.environ.get("DB_PORT", "5432")
```

`DB_NAME`, `DB_USER`, `DB_PASSWORD` default to `""` (empty string — deliberately no real
default, since these are required); `DB_HOST` defaults to `"localhost"`; `DB_PORT` defaults to
`"5432"` (the standard PostgreSQL port). All are read via `os.environ.get(name, default)` at
class-body evaluation time, i.e. at import time.

Line 30:

```python
    API_PORT: int = int(os.environ.get("API_PORT", "8001"))
```

The Uvicorn listen port, cast from string to `int`.

Line 31:

```python
    DISABLE_DOCS: bool = os.environ.get("DISABLE_DOCS", "").lower() in ("1", "true", "yes")
```

Reads the raw string, lowercases it, and checks membership in a small set of truthy spellings.
Anything else (including an unset variable, which reads as `""`) evaluates to `False`, so docs
are enabled by default.

Lines 34–38:

```python
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "").split(",")
        if o.strip()
    ]
```

A list comprehension that splits the `CORS_ORIGINS` env var on commas, strips whitespace from
each entry, and drops empty strings. An unset `CORS_ORIGINS` produces `[]` (empty list) — this
is the "CORS inactive" sentinel that `api/main.py` checks with `if settings.CORS_ORIGINS:`.

Line 39:

```python
    RATE_LIMIT: str = os.environ.get("RATE_LIMIT", "60/minute")
```

A rate-limit string in the `limits` library's `<count>/<period>` syntax, consumed directly by
`slowapi.Limiter`.

Lines 41–54:

```python
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
```

Builds a `missing` list by checking `DB_NAME`, `DB_USER`, `DB_PASSWORD` (only these three —
`DB_HOST`/`DB_PORT` have safe defaults so they're never "missing"). If `missing` is non-empty,
raises `RuntimeError` with a message naming every missing variable and pointing at `api/.env`
as the fix. This is called by `api/database.py::get_pool()` before the connection pool is
created — the first thing that happens on the first real database access, not at import time
(import-time validation would make it impossible to import `api.main` for tooling, e.g.
generating an OpenAPI schema, without a database configured).

Line 57:

```python
settings = Settings()
```

A module-level singleton instantiated once. Every other file that needs configuration does
`from api.config import settings` and reads its attributes; there is exactly one `Settings`
instance in the process.

---

### 2.2 `api/database.py`

**Requirement**

Every router handler needs a database connection, but opening and closing a raw TCP connection
to PostgreSQL per request would be slow and would exhaust connections under load. This file
supplies a small, dependency-injectable connection pool so FastAPI's `Depends(get_connection)`
mechanism can hand each request a pooled connection and reliably return it afterward, and a
`check_connection()` helper the `/health` endpoint uses to report liveness without leaking
internal error detail. Without this file there is no connection strategy at all — `api/main.py`
would have nothing to call on shutdown, and every router would have to invent its own
`psycopg2.connect(...)` boilerplate.

**Line-by-line**

Lines 1–8 — module docstring:

```python
"""
NSS ERP — Database connection pool.

Uses psycopg2 with a simple connection-pool pattern.
The FastAPI application connects as nss_db_backend (read-only in Tier 0).

No ORM — raw SQL queries against nss.* tables.
"""
```

States psycopg2 is used with a "simple connection-pool pattern," the app connects as
`nss_db_backend` (read-only in Tier 0/1), and there is no ORM — raw SQL against `nss.*` tables.

Line 10:

```python
import psycopg2
```

The PostgreSQL driver.

Line 11:

```python
import psycopg2.pool
```

The pooling submodule, used for `SimpleConnectionPool`.

Line 13:

```python
from api.config import settings
```

The singleton from `config.py`, read for `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`
and for calling `.validate()`.

Line 16:

```python
_pool: psycopg2.pool.SimpleConnectionPool | None = None
```

A module-level variable holding the shared pool, initialized to `None`. The `| None` union
(Python 3.10+ syntax) documents that the pool doesn't exist until first use — **lazy
initialization**.

Lines 19–33:

```python
def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    """Return the shared connection pool, creating it on first use."""
    global _pool
    if _pool is None or _pool.closed:
        settings.validate()
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=2,
            maxconn=5,
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
        )
    return _pool
```

Declares `global _pool` so it can rebind the module-level variable; if `_pool is None or
_pool.closed` (i.e. never created, or previously closed), it calls `settings.validate()` (fail
fast if credentials are missing) and then constructs `psycopg2.pool.SimpleConnectionPool(...)`.
`minconn=2` keeps two connections warm at all times (v0.10.4 —
pre-warms enough connections so a 2-worker Uvicorn deployment has no
cold-start latency on first request; see `docs/03_Solution/architecture/PERFORMANCE_TUNING.md`);
`maxconn=5` caps concurrent connections to PostgreSQL at 5. Either way, the function returns
`_pool` — callers never construct a pool themselves.

Lines 36–41:

```python
def close_pool() -> None:
    """Close all connections in the pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.closeall()
        _pool = None
```

Declares `global _pool`; if a pool exists and isn't already closed, calls `_pool.closeall()`
(closes every connection cleanly) and sets `_pool = None` so a later `get_pool()` call would
recreate it from scratch. Called from `api/main.py`'s `lifespan` shutdown handler.

Lines 44–60:

```python
def get_connection():
    """
    Context-manager-compatible connection getter.

    Usage as a FastAPI dependency:
        conn = get_pool().getconn()
        try:
            yield conn
        finally:
            get_pool().putconn(conn)
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
```

A generator function used as a FastAPI dependency. Calls `get_pool()` to obtain the shared
pool, then `pool.getconn()` to borrow one connection. `yield conn` is the point where FastAPI
hands the connection to the route handler; the `finally: pool.putconn(conn)` block runs after
the request completes (successfully or with an exception), returning the connection to the
pool rather than closing it — the connection is reused across requests. The docstring (lines
45–54) spells out this exact usage pattern for anyone reading the dependency without tracing
FastAPI's internals.

Lines 63–80:

```python
def check_connection() -> bool:
    """
    Test whether the database is reachable.

    Returns True if a simple query succeeds, False otherwise.
    Does not leak connection details on failure.
    """
    try:
        pool = get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        finally:
            pool.putconn(conn)
    except Exception:
        return False
```

Used exclusively by the `/health` endpoint. Wrapped in a `try/except Exception: return False`
so any failure (network, auth, pool exhaustion) collapses to a boolean rather than leaking a
stack trace or connection string to the caller. Inside the `try`, it borrows a connection
(`pool.getconn()`), opens a cursor with `with conn.cursor() as cur:`, executes the simplest
possible query `SELECT 1`, and returns `True` if that succeeds. The `finally:
pool.putconn(conn)` ensures the connection is returned to the pool even if the query raises —
this `try/finally` is nested *inside* the outer `try`, so a failure to even obtain a connection
(e.g. `get_pool()` itself raising because credentials are missing) is caught by the outer
`except` without ever reaching the `finally`.

---

### 2.3 `api/main.py`

**Requirement**

Something has to be the single object Uvicorn imports and serves (`api.main:app`), the place
that wires together the connection pool lifecycle, both routers, the security middleware stack
(rate limiting, CORS, security headers), the Swagger/ReDoc/OpenAPI docs toggle, and the static
frontend. Every other API file is a component that does nothing on its own until this file
assembles it into one FastAPI application. Without it there is no running server at all — just
a collection of importable modules.

**Line-by-line**

Lines 1–34 — module docstring:

```python
"""
NSS ERP — FastAPI application entry point.

Tier 0 Bootstrap + Tier 1 Foundation + Tier 2 Organization + Tier 3 Person
+ Tier 4 Family + Membership
API + Frontend:
  - Read-only endpoints for RBAC, Foundation, Organization, Person,
    Family, and Membership data verification
  - Serves frontend/ static files (Verification UIs)
  - No authentication (Tier 5)
  - No ORM — raw psycopg2 against nss.* schema
  - Connects as nss_db_backend (SELECT-only privileges)

Security middleware:
  - CORS: configurable origins via CORS_ORIGINS env var
  - Rate limiting: configurable via RATE_LIMIT env var (default 60/minute)
  - Security headers: X-Content-Type-Options, X-Frame-Options, etc.
  - Docs toggle: DISABLE_DOCS=true hides /docs, /redoc, /openapi.json

Start with:
    python3 -m uvicorn api.main:app --reload --port 8001   (macOS/Linux)
    py -m uvicorn api.main:app --reload --port 8001         (Windows)
    (run from the repository root)

URLs:
    http://localhost:8001/              -> Bootstrap Verification UI
    http://localhost:8001/foundation    -> Foundation Verification UI
    http://localhost:8001/organization  -> Organization Verification UI
    http://localhost:8001/person        -> Person Verification UI
    http://localhost:8001/family        -> Family Verification UI
    http://localhost:8001/membership    -> Membership Verification UI
    http://localhost:8001/docs          -> Swagger UI (OpenAPI)
    http://localhost:8001/api/v1/       -> API endpoints
"""
```

Summarizes the file as covering all six tiers (Bootstrap through Family + Membership), lists what
it doesn't do (no auth, no ORM), names the security middleware present, gives the exact `uvicorn`
start commands for macOS/Linux and Windows (must be run from the repository root), and all eight
URLs served (`/`, `/foundation`, `/organization`, `/person`, `/family`, `/membership`, `/docs`,
`/api/v1/...`).

Line 28:

```python
from contextlib import asynccontextmanager
```

Decorator used to build the FastAPI `lifespan` handler.

Line 29:

```python
from pathlib import Path
```

Used below to locate `frontend/` cross-platform.

Lines 31–34:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
```

The FastAPI application class, CORS middleware, a response type for serving a single file
(at the time `index.html`/`foundation.html`; now `login.html`/`register.html`/`dashboard.html`/
`admin.html`), and a mountable static-file server for `frontend/assets/`.

Lines 35–38:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
```

The rate-limiting engine (`Limiter`), the exception type it raises on breach, the ASGI
middleware that actually enforces limits on every request, and the key function that
identifies a client by IP address.

Lines 40–43:

```python
from api.config import settings
from api.database import close_pool
from api.middleware import add_security_headers
from api.routers import bootstrap, foundation, organization, person, family, membership
```

Pulls in configuration, the pool-shutdown function, the security-headers middleware function,
and all six routers.

Line 45:

```python
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
```

Resolves to the repository's `frontend/` directory (`api/main.py`'s parent is `api/`, whose
parent is the repo root), independent of platform path separators.

Lines 49–52:

```python
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT],
)
```

A module-level `Limiter` instance keyed by client IP, with the default rate (e.g.
`"60/minute"`) taken from configuration. This same `limiter` object is imported directly by
`tests/conftest.py`, which resets it via an autouse fixture before **every** test in the whole
suite (not just `tests/test_security.py`) — it's a shared, process-wide singleton, so without a
global reset, request-heavy test files accumulate against the same budget and can trip spurious
429s in unrelated, later-running tests.

Lines 55–59:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — clean up DB pool on shutdown."""
    yield
    close_pool()
```

The FastAPI lifespan context manager. Code before `yield` would run at startup (there is none
— the pool is created lazily on first DB access, not eagerly at startup); code after `yield`
runs at shutdown, here calling `close_pool()` to cleanly close every pooled connection.

Lines 62–74:

```python
app = FastAPI(
    title="NSS ERP API",
    version="0.1.0",
    description=(
        "Nilachala Saraswata Sangha ERP — "
        "Tier 0 Bootstrap + Tier 1 Foundation + Tier 2 Organization "
        "+ Tier 3 Person + Tier 4 Family + Membership API. "
        "Read-only verification endpoints."
    ),
    lifespan=lifespan,
    docs_url=None if settings.DISABLE_DOCS else "/docs",
    redoc_url=None if settings.DISABLE_DOCS else "/redoc",
    openapi_url=None if settings.DISABLE_DOCS else "/openapi.json",
)
```

Constructs the application. The three doc-related URLs each independently collapse to `None`
when `DISABLE_DOCS` is true, which makes FastAPI return 404 for `/docs`, `/redoc`, and
`/openapi.json` — hiding endpoint paths, parameter schemas, and response models from anyone
probing an unauthenticated production deployment, while leaving the actual API routes fully
functional.

Lines 78–81 (under the comment "1. Rate limiting"):

```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

`app.state.limiter = limiter` makes the limiter reachable from `SlowAPIMiddleware` via the
request's `app` reference; `app.add_exception_handler(RateLimitExceeded,
_rate_limit_exceeded_handler)` converts a `RateLimitExceeded` exception into an HTTP 429
response with a `Retry-After` header; `app.add_middleware(SlowAPIMiddleware)` is the actual
enforcement — without this call the limiter is configured but never consulted on incoming
requests (this exact omission was caught by `test_rate_limit_returns_429` during development).
Full rationale in `SECURITY_CODE_EXPLANATIONS.md` §2.3.

Lines 84–91 (under the comment "2. CORS"):

```python
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
```

CORS middleware is added **only if** at least one origin is configured; with the default
empty list, it's never added at all, so cross-origin requests get no CORS headers regardless
of what `Origin` header they send (verified by `tests/test_security.py::TestCORS`).
`allow_methods=["GET"]` matches the read-only nature of every current endpoint.

Line 94 (under the comment "3. Security headers on every response"):

```python
app.middleware("http")(add_security_headers)
```

Registers the function from `api/middleware.py` as HTTP middleware, called with function-call
syntax (rather than the `@app.middleware("http")` decorator form) because the function is
defined in a separate module. The comments above (lines 76, 93) explain middleware execution
order: middleware added later wraps middleware added earlier, so the effective request path is
Security Headers → CORS → Rate Limiting → endpoint, and the response path unwinds in reverse —
security headers see every outgoing response, including 429s and CORS preflights. Full
walkthrough of `api/middleware.py` itself: `SECURITY_CODE_EXPLANATIONS.md` §2.1.

Lines 98–99:

```python
app.include_router(bootstrap.router)
app.include_router(foundation.router)
app.include_router(organization.router)
app.include_router(person.router)
app.include_router(family.router)
app.include_router(membership.router)
```

Mounts all 46 endpoints across all six routers onto the app: 4 Bootstrap, 17 Foundation, 7
Organization, 4 Person, 7 Family, 7 Membership.

Lines 118–169 (**superseded — see the note after this block**):

```python
if _FRONTEND_DIR.is_dir():
    _index_path = _FRONTEND_DIR / "index.html"
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIR / "assets")),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the Bootstrap Verification UI."""
        return FileResponse(str(_index_path))

    _foundation_path = _FRONTEND_DIR / "foundation.html"
    if _foundation_path.is_file():

        @app.get("/foundation", include_in_schema=False)
        async def serve_foundation():
            """Serve the Foundation Verification UI."""
            return FileResponse(str(_foundation_path))

    _organization_path = _FRONTEND_DIR / "organization.html"
    if _organization_path.is_file():

        @app.get("/organization", include_in_schema=False)
        async def serve_organization():
            """Serve the Organization Verification UI."""
            return FileResponse(str(_organization_path))

    _person_path = _FRONTEND_DIR / "person.html"
    if _person_path.is_file():

        @app.get("/person", include_in_schema=False)
        async def serve_person():
            """Serve the Person Verification UI."""
            return FileResponse(str(_person_path))

    _family_path = _FRONTEND_DIR / "family.html"
    if _family_path.is_file():

        @app.get("/family", include_in_schema=False)
        async def serve_family():
            """Serve the Family Verification UI."""
            return FileResponse(str(_family_path))

    _membership_path = _FRONTEND_DIR / "membership.html"
    if _membership_path.is_file():

        @app.get("/membership", include_in_schema=False)
        async def serve_membership():
            """Serve the Membership Verification UI."""
            return FileResponse(str(_membership_path))
```

The entire frontend-serving block is conditional on the `frontend/` directory existing, so the
API still runs (e.g. in a test environment without a frontend checkout) if it's absent.
Inside: `app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")),
name="frontend-assets")` serves CSS/JS/images under `/assets/*` — deliberately mounted at
`/assets` rather than `/` so it can't shadow `/docs` or `/openapi.json`. `@app.get("/",
include_in_schema=False) async def serve_frontend(): return FileResponse(str(_index_path))`
serves `frontend/index.html` at the root; `include_in_schema=False` keeps this page route out
of the OpenAPI schema (it's a UI page, not an API contract). The same
`_x_path = _FRONTEND_DIR / "x.html"; if _x_path.is_file():` pattern then repeats four more times
— `foundation.html` at `/foundation`, `organization.html` at `/organization`, `person.html` at
`/person`, `family.html` at `/family`, and `membership.html` at `/membership` — each gated
independently on that specific HTML file's existence, so a partial frontend checkout (e.g. only
some tier pages present) still serves whichever pages do exist.

> **⚠ Superseded.** The six page routes quoted above no longer exist in `api/main.py`. All six
> Tier 0-4 verification pages (`index.html`, `foundation.html`, `organization.html`,
> `person.html`, `family.html`, `membership.html`) were deleted from `frontend/`, and their
> routes were removed with them — see the "Retired standalone verification pages" comment in
> `api/main.py`. What the file does now, using the same
> `_x_path = _FRONTEND_DIR / "x.html"; if _x_path.is_file():` pattern: `GET /` is registered
> unconditionally (whenever `frontend/` is a directory) and returns
> `RedirectResponse(url="/login", status_code=302)`; then `login.html` at `/login`,
> `dashboard.html` at `/dashboard`, `admin.html` at `/admin`, and `register.html` at
> `/register`. There is no `/forgot-password` page route — that flow is inline on the Login
> page. The
> `app.mount("/assets", ...)` line and the surrounding `if _FRONTEND_DIR.is_dir():` guard are
> unchanged. The retired pages' functionality now lives in tabs of `admin.html` (Bootstrap RBAC
> → System Settings, Foundation → Reference Data + Geography, Organization → Organizations +
> Organization Hierarchy, Person → Person Directory, Membership → Member Directory) and
> `dashboard.html` (Family, Membership).

---

### 2.4 `api/routers/bootstrap.py`

**Requirement**

Tier 0 needs 4 concrete, callable HTTP endpoints — a liveness probe and read access to the 3
Bootstrap RBAC tables (`role_master`, `permission_master`, `role_permission`) — expressed as raw
SQL against `nss.*`, translated into the Pydantic response models from `api/schemas/bootstrap.py`.
Without this file, `api/main.py` would have nothing to mount at `/api/v1/bootstrap/*`, and there
would be no way for the frontend Bootstrap Verification UI or any consumer to see the 8 frozen
roles.

**Line-by-line**

Lines 1–11 — module docstring:

```python
"""
NSS ERP — Bootstrap RBAC endpoints.

Tier 0 read-only API:
  GET /api/v1/bootstrap/health
  GET /api/v1/bootstrap/roles
  GET /api/v1/bootstrap/permissions
  GET /api/v1/bootstrap/roles/{role_pk}/permissions

No authentication. No CRUD. No speculative permissions.
"""
```

Lists the exact 4 endpoint paths and states "No authentication. No CRUD. No speculative
permissions" as an explicit design constraint.

Line 13:

```python
from uuid import UUID
```

Used to type the `role_pk` path parameter so FastAPI validates it's a well-formed UUID before
the handler runs.

Line 15:

```python
from fastapi import APIRouter, Depends, HTTPException
```

`APIRouter` groups these endpoints; `Depends` injects the pooled connection; `HTTPException`
raises 404 responses.

Lines 17–22:

```python
from api.database import check_connection, get_connection
from api.schemas.bootstrap import (
    HealthResponse,
    PermissionResponse,
    RoleResponse,
)
```

The DB helpers and the three response models this router returns.

Line 24:

```python
router = APIRouter(prefix="/api/v1/bootstrap", tags=["bootstrap"])
```

Every route declared below is automatically prefixed with `/api/v1/bootstrap` and grouped
under the "bootstrap" tag in Swagger UI.

Lines 27–39:

```python
@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Liveness/readiness probe.

    Returns database connectivity status.
    Never exposes connection details, credentials, or error messages.
    """
    db_ok = check_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "unreachable",
    )
```

Note this handler takes **no** `conn=Depends(get_connection)` parameter, unlike every other
endpoint in the file; it calls `check_connection()` directly, which manages its own connection
borrow/return internally. Returns a fixed two-value vocabulary (`"ok"`/`"degraded"`,
`"connected"`/`"unreachable"`) that never echoes an underlying exception message.

Lines 42–68:

```python
@router.get("/roles", response_model=list[RoleResponse])
def list_roles(conn=Depends(get_connection)) -> list[RoleResponse]:
    """
    Return all active roles from nss.role_master.

    Tier 0 state: 10 frozen roles.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT role_master_pk,
                   role_code,
                   role_name,
                   role_class,
                   scope_level,
                   description,
                   display_order,
                   is_active
              FROM nss.role_master
             WHERE is_active = TRUE
             ORDER BY display_order
            """
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return [RoleResponse(**dict(zip(columns, row))) for row in rows]
```

Opens a cursor with `with conn.cursor() as cur:`, executes the `SELECT` above against
`nss.role_master` — the `WHERE is_active = TRUE` clause is the sole soft-delete filter; there
is no `include_inactive` parameter. `columns = [desc[0] for desc in cur.description]` pulls
column names from psycopg2's cursor metadata, and `rows = cur.fetchall()` pulls the data.
`return [RoleResponse(**dict(zip(columns, row))) for row in rows]` zips column names with each
row's values into a dict, then unpacks that dict as keyword arguments into `RoleResponse`,
which validates types and produces the JSON the client sees.

Lines 71–97:

```python
@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(conn=Depends(get_connection)) -> list[PermissionResponse]:
    """
    Return all active permissions from nss.permission_master.

    Tier 0 state: empty by design — permissions are populated
    progressively with each module's vertical-slice implementation.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT permission_master_pk,
                   permission_code,
                   permission_name,
                   module_code,
                   description,
                   display_order,
                   is_active
              FROM nss.permission_master
             WHERE is_active = TRUE
             ORDER BY module_code, display_order
            """
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return [PermissionResponse(**dict(zip(columns, row))) for row in rows]
```

Identical structure to `list_roles`, querying `nss.permission_master` with `ORDER BY
module_code, display_order`. In Tier 0 this always returns an empty list, because the
permission catalogue seed is intentionally empty — permissions are populated progressively per
module, not pre-seeded.

Lines 100–152:

```python
@router.get(
    "/roles/{role_pk}/permissions",
    response_model=list[PermissionResponse],
)
def list_role_permissions(
    role_pk: UUID,
    conn=Depends(get_connection),
) -> list[PermissionResponse]:
    """
    Return permissions assigned to a specific role via nss.role_permission.

    Tier 0 state: empty — no role-permission mappings exist yet.
    Returns 404 if the role_pk does not exist.
    """
    # Verify the role exists
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
              FROM nss.role_master
             WHERE role_master_pk = %s
               AND is_active = TRUE
            """,
            (str(role_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Role not found")

    # Fetch permissions via the junction table
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pm.permission_master_pk,
                   pm.permission_code,
                   pm.permission_name,
                   pm.module_code,
                   pm.description,
                   pm.display_order,
                   pm.is_active
              FROM nss.role_permission rp
              JOIN nss.permission_master pm
                ON pm.permission_master_pk = rp.permission_master_pk
             WHERE rp.role_master_pk = %s
               AND rp.is_active = TRUE
               AND pm.is_active = TRUE
             ORDER BY pm.module_code, pm.display_order
            """,
            (str(role_pk),),
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return [PermissionResponse(**dict(zip(columns, row))) for row in rows]
```

`role_pk: UUID` means an unparseable path segment (e.g. `"not-a-uuid"`) is rejected by FastAPI
with 422 before this function body ever runs. The first cursor checks existence with `SELECT 1
FROM nss.role_master WHERE role_master_pk = %s AND is_active = TRUE`, parameterized with
`(str(role_pk),)` (psycopg2 requires the UUID as a string); if `cur.fetchone() is None`, it
raises `HTTPException(status_code=404, detail="Role not found")`. The second cursor, only
reached if the role exists, runs a `JOIN` — filtering `is_active` on *both* sides of the join,
so a soft-deleted permission or a soft-deleted mapping row is excluded even if the other side
is still active. The final return builds the response list the same zip/dict/unpack way as the
other two endpoints. In Tier 0 this always returns an empty list — no role-permission mappings
exist yet — but a 404 is still possible and is tested (`test_role_permissions_invalid_role`).

---

### 2.5 `api/routers/foundation.py`

**Requirement**

Tier 1 exposes 17 read-only GET endpoints across 11 of the 12 Foundation tables (Master Data,
System Configuration, Geographic, and one Runtime table) so downstream modules and the
Foundation Verification UI can browse master data, settings, ID-sequence definitions, and the
geographic hierarchy (country → state → district → city/village → postal code). The 12th table,
`field_change_log`, is intentionally not given an endpoint here — audit data requires
authentication, deferred to Tier 5 — and `TestChangeLogNotExposed` in the test suite guards
against that boundary being accidentally crossed. Without this file, none of the 12 Foundation
DDL tables built in the database layer would be reachable over HTTP at all.

**Line-by-line**

Lines 1–16 — module docstring:

```python
"""
Foundation API router — Tier 1 read-only endpoints.

17 GET endpoints across 11 Foundation tables. No authentication.
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Master Data:      categories, master-data
  - System Config:    settings, sequences
  - Geographic:       countries, states, districts, cities, postal-codes,
                      postal-code-mappings
  - Runtime:          documents

field_change_log is intentionally excluded from Tier 1 — audit data
requires authentication. Deferred to Tier 5.
"""
```

States "17 GET endpoints across 11 Foundation tables," lists the four endpoint groups (Master
Data / System Config / Geographic / Runtime), and states the `field_change_log` exclusion and
its rationale explicitly.

Line 18:

```python
from uuid import UUID
```

Types every PK path/query parameter.

Line 20:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

`Query` is new relative to `bootstrap.py`: it declares optional filter query parameters with
Swagger-UI descriptions.

Lines 22–35:

```python
from api.database import get_connection
from api.schemas.foundation import (
    CategoryResponse,
    CityVillageResponse,
    CountryResponse,
    DistrictResponse,
    DocumentResponse,
    MasterDataResponse,
    PostalCodeMappingResponse,
    PostalCodeResponse,
    SequenceResponse,
    SettingResponse,
    StateResponse,
)
```

All 11 response models used by this router.

Line 37:

```python
router = APIRouter(prefix="/api/v1/foundation", tags=["foundation"])
```

Separate prefix and Swagger tag from the bootstrap router, so both mount independently in
`main.py`.

Lines 42–45:

```python
def _rows_to_models(cur, model_class):
    """Convert cursor results to a list of Pydantic models."""
    columns = [desc[0] for desc in cur.description]
    return [model_class(**dict(zip(columns, row))) for row in cur.fetchall()]
```

The "cursor → Pydantic" bridge shared by every list endpoint in this file. `columns = [desc[0]
for desc in cur.description]` reads column names from cursor metadata (never hardcoded
positions); the return line converts every returned row the same zip/dict/unpack way seen in
`bootstrap.py`, but factored into a helper so it isn't repeated 15 times. If the SQL SELECT
column list doesn't exactly match the model's field names, Pydantic raises a validation error
immediately — there is no silent truncation or renaming.

Lines 48–54:

```python
def _row_to_model(cur, model_class):
    """Convert a single cursor result to a Pydantic model, or None."""
    columns = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    if row is None:
        return None
    return model_class(**dict(zip(columns, row)))
```

The single-row counterpart, used by every detail (`/…/{pk}`) endpoint. Returning `None`
(rather than raising) lets each calling endpoint decide how to turn "not found" into an
`HTTPException(404)` at its own call site.

**Master Data group (lines 57–159, 4 endpoints):**

Lines 62–73 — `GET /categories`:

```python
@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(conn=Depends(get_connection)) -> list[CategoryResponse]:
    """List all active master categories."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT master_category_pk, category_code, category_name,
                   description, display_order, is_active
            FROM   nss.master_category
            WHERE  is_active = TRUE
            ORDER BY display_order, category_name
        """)
        return _rows_to_models(cur, CategoryResponse)
```

`list_categories(conn=Depends(get_connection))` runs the `SELECT` above and returns
`_rows_to_models(cur, CategoryResponse)`.

Lines 76–92 — `GET /categories/{master_category_pk}`:

```python
@router.get("/categories/{master_category_pk}", response_model=CategoryResponse)
def get_category(
    master_category_pk: UUID,
    conn=Depends(get_connection),
) -> CategoryResponse:
    """Get a single master category by PK."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT master_category_pk, category_code, category_name,
                   description, display_order, is_active
            FROM   nss.master_category
            WHERE  master_category_pk = %s AND is_active = TRUE
        """, (str(master_category_pk),))
        result = _row_to_model(cur, CategoryResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Category not found")
        return result
```

Runs the same column list as `list_categories` with `WHERE master_category_pk = %s AND
is_active = TRUE`, parameterized with `(str(master_category_pk),)`; if `_row_to_model` returns
`None`, raises `HTTPException(404, "Category not found")`.

Lines 95–134 — `GET /master-data`:

```python
@router.get("/master-data", response_model=list[MasterDataResponse])
def list_master_data(
    category_code: str | None = Query(None, description="Filter by category code"),
    category_pk: UUID | None = Query(None, description="Filter by category PK"),
    conn=Depends(get_connection),
) -> list[MasterDataResponse]:
    """
    List all active master data values.

    Optionally filter by category_code or category_pk.
    If both are provided, category_pk takes precedence.
    """
    base_sql = """
        SELECT md.master_data_pk, md.master_category_pk,
               mc.category_code, mc.category_name,
               md.value_code, md.value_name,
               md.description, md.display_order, md.is_active
        FROM   nss.master_data md
        JOIN   nss.master_category mc
               ON mc.master_category_pk = md.master_category_pk
        WHERE  md.is_active = TRUE
          AND  mc.is_active = TRUE
    """
    params: list = []

    if category_pk is not None:
        base_sql += " AND md.master_category_pk = %s"
        params.append(str(category_pk))
    elif category_code is not None:
        base_sql += " AND mc.category_code = %s"
        params.append(category_code)

    base_sql += """
        ORDER BY mc.display_order, mc.category_name,
                 md.display_order, md.value_name
    """

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, MasterDataResponse)
```

`list_master_data(category_code: str | None = Query(...), category_pk: UUID | None =
Query(...), conn=...)` builds `base_sql` with a `JOIN nss.master_category mc ON
mc.master_category_pk = md.master_category_pk` so `category_code`/`category_name` come from
the parent row — the "JOINed parent context" pattern used throughout this file so the UI never
needs a second round-trip to resolve a parent's display name. It filters both `md.is_active`
and `mc.is_active`. The `if category_pk is not None: ... elif category_code is not None: ...`
block is dynamic WHERE-clause building — `category_pk` takes precedence when both are
supplied, and only one extra condition is ever added. All values are appended to a `params`
list and passed as `tuple(params)` to `cur.execute`, never string-interpolated — no
SQL-injection surface regardless of what a caller supplies.

Lines 137–159 — `GET /master-data/{master_data_pk}`:

```python
@router.get("/master-data/{master_data_pk}", response_model=MasterDataResponse)
def get_master_data(
    master_data_pk: UUID,
    conn=Depends(get_connection),
) -> MasterDataResponse:
    """Get a single master data value by PK (with category context)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT md.master_data_pk, md.master_category_pk,
                   mc.category_code, mc.category_name,
                   md.value_code, md.value_name,
                   md.description, md.display_order, md.is_active
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  md.master_data_pk = %s
              AND  md.is_active = TRUE
              AND  mc.is_active = TRUE
        """, (str(master_data_pk),))
        result = _row_to_model(cur, MasterDataResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Master data value not found")
        return result
```

Same JOIN and both-sides-active filter as the list endpoint, keyed by `md.master_data_pk =
%s`; 404 if `_row_to_model` returns `None`.

**System Configuration group (lines 162–222, 3 endpoints):**

Lines 167–178 — `GET /settings`:

```python
@router.get("/settings", response_model=list[SettingResponse])
def list_settings(conn=Depends(get_connection)) -> list[SettingResponse]:
    """List all active system settings."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT system_setting_pk, setting_key, setting_value,
                   description, data_type, is_active
            FROM   nss.system_setting
            WHERE  is_active = TRUE
            ORDER BY setting_key
        """)
        return _rows_to_models(cur, SettingResponse)
```

Flat query (no JOIN) against `nss.system_setting`, `ORDER BY setting_key`.

Lines 181–202 — `GET /settings/{setting_key}`:

```python
@router.get("/settings/{setting_key}", response_model=SettingResponse)
def get_setting_by_key(
    setting_key: str,
    conn=Depends(get_connection),
) -> SettingResponse:
    """
    Get a single system setting by its business key.

    Settings are consumed by code using their key name
    (e.g., CURRENT_MEMBERSHIP_YEAR), not their UUID.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT system_setting_pk, setting_key, setting_value,
                   description, data_type, is_active
            FROM   nss.system_setting
            WHERE  setting_key = %s AND is_active = TRUE
        """, (setting_key,))
        result = _row_to_model(cur, SettingResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Setting not found")
        return result
```

`setting_key: str`, not `UUID` — settings are looked up by their **business key** (e.g.
`CURRENT_MEMBERSHIP_YEAR`), which is how consuming code actually references them; FastAPI does
not validate the string's format, any value is accepted and simply may or may not match a row.
404 if no match.

Lines 205–222 — `GET /sequences`:

```python
@router.get("/sequences", response_model=list[SequenceResponse])
def list_sequences(conn=Depends(get_connection)) -> list[SequenceResponse]:
    """
    List all active ID sequence configurations.

    Infrastructure/verification endpoint. current_value is excluded —
    it's infrastructure state, not consumer data.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id_sequence_master_pk, sequence_code, sequence_name,
                   prefix, padding_length,
                   description, is_active
            FROM   nss.id_sequence_master
            WHERE  is_active = TRUE
            ORDER BY sequence_code
        """)
        return _rows_to_models(cur, SequenceResponse)
```

Queries `nss.id_sequence_master` selecting `id_sequence_master_pk, sequence_code,
sequence_name, prefix, padding_length, description, is_active`. The docstring and the SELECT
column list both make explicit that `current_value` — a real column in the table — is **not**
selected: it is infrastructure state (the next number to be allocated), not consumer data, and
`test_current_value_not_exposed` enforces this at the response-shape level.

**Geographic group (lines 225–486, 9 endpoints):** all parent-child relationships (country →
state → district → city/village; state/country → postal code; city/village ↔ postal code) are
expressed as **flat routes with optional query-parameter filters**, not nested paths like
`/countries/{pk}/states` — chosen so the frontend can compose filters freely and so endpoint
paths aren't coupled to the data hierarchy.

Lines 230–260 — `GET /countries` and `GET /countries/{country_pk}`:

```python
@router.get("/countries", response_model=list[CountryResponse])
def list_countries(conn=Depends(get_connection)) -> list[CountryResponse]:
    """List all active countries."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT country_pk, country_code, country_name,
                   display_order, is_active
            FROM   nss.country
            WHERE  is_active = TRUE
            ORDER BY display_order, country_name
        """)
        return _rows_to_models(cur, CountryResponse)


@router.get("/countries/{country_pk}", response_model=CountryResponse)
def get_country(
    country_pk: UUID,
    conn=Depends(get_connection),
) -> CountryResponse:
    """Get a single country by PK."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT country_pk, country_code, country_name,
                   display_order, is_active
            FROM   nss.country
            WHERE  country_pk = %s AND is_active = TRUE
        """, (str(country_pk),))
        result = _row_to_model(cur, CountryResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Country not found")
        return result
```

Top of the hierarchy, no JOIN needed.

Lines 263–317 — `GET /states` and `GET /states/{state_pk}`:

```python
@router.get("/states", response_model=list[StateResponse])
def list_states(
    country_pk: UUID | None = Query(None, description="Filter by parent country"),
    conn=Depends(get_connection),
) -> list[StateResponse]:
    """
    List all active states/provinces.

    Optionally filter by parent country PK.
    """
    base_sql = """
        SELECT s.state_pk, s.country_pk,
               c.country_code, c.country_name,
               s.state_code, s.state_name,
               s.display_order, s.is_active
        FROM   nss.state s
        JOIN   nss.country c ON c.country_pk = s.country_pk
        WHERE  s.is_active = TRUE
          AND  c.is_active = TRUE
    """
    params: list = []

    if country_pk is not None:
        base_sql += " AND s.country_pk = %s"
        params.append(str(country_pk))

    base_sql += " ORDER BY c.display_order, s.display_order, s.state_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, StateResponse)


@router.get("/states/{state_pk}", response_model=StateResponse)
def get_state(
    state_pk: UUID,
    conn=Depends(get_connection),
) -> StateResponse:
    """Get a single state by PK (with country context)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.state_pk, s.country_pk,
                   c.country_code, c.country_name,
                   s.state_code, s.state_name,
                   s.display_order, s.is_active
            FROM   nss.state s
            JOIN   nss.country c ON c.country_pk = s.country_pk
            WHERE  s.state_pk = %s
              AND  s.is_active = TRUE
              AND  c.is_active = TRUE
        """, (str(state_pk),))
        result = _row_to_model(cur, StateResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="State not found")
        return result
```

`list_states(country_pk: UUID | None = Query(None, ...), ...)` joins `nss.state s` to
`nss.country c`; if `country_pk` is supplied, appends `AND s.country_pk = %s`; `ORDER BY
c.display_order, s.display_order, s.state_name`. `GET /states/{state_pk}` mirrors this with a
PK filter and 404-on-missing.

Lines 320–375 — `GET /districts` and `GET /districts/{district_pk}`:

```python
@router.get("/districts", response_model=list[DistrictResponse])
def list_districts(
    state_pk: UUID | None = Query(None, description="Filter by parent state"),
    conn=Depends(get_connection),
) -> list[DistrictResponse]:
    """
    List all active districts.

    Optionally filter by parent state PK. Without filter, returns all
    active districts (~700+ for India alone).
    """
    base_sql = """
        SELECT d.district_pk, d.state_pk,
               s.state_name,
               d.district_code, d.district_name,
               d.display_order, d.is_active
        FROM   nss.district d
        JOIN   nss.state s ON s.state_pk = d.state_pk
        WHERE  d.is_active = TRUE
          AND  s.is_active = TRUE
    """
    params: list = []

    if state_pk is not None:
        base_sql += " AND d.state_pk = %s"
        params.append(str(state_pk))

    base_sql += " ORDER BY s.state_name, d.display_order, d.district_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, DistrictResponse)


@router.get("/districts/{district_pk}", response_model=DistrictResponse)
def get_district(
    district_pk: UUID,
    conn=Depends(get_connection),
) -> DistrictResponse:
    """Get a single district by PK (with state context)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.district_pk, d.state_pk,
                   s.state_name,
                   d.district_code, d.district_name,
                   d.display_order, d.is_active
            FROM   nss.district d
            JOIN   nss.state s ON s.state_pk = d.state_pk
            WHERE  d.district_pk = %s
              AND  d.is_active = TRUE
              AND  s.is_active = TRUE
        """, (str(district_pk),))
        result = _row_to_model(cur, DistrictResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="District not found")
        return result
```

Same filter pattern joined to `nss.state` for `state_name` only (not the state's parent
country fields — the UI already has the country from the previous drill-down step). Optional
`state_pk` filter. `GET /districts/{district_pk}` mirrors it.

Lines 378–410 — `GET /cities`:

```python
@router.get("/cities", response_model=list[CityVillageResponse])
def list_cities(
    district_pk: UUID | None = Query(None, description="Filter by parent district"),
    conn=Depends(get_connection),
) -> list[CityVillageResponse]:
    """
    List all active cities/villages.

    Optionally filter by parent district PK.
    Currently returns empty — no seed data by design.
    """
    base_sql = """
        SELECT cv.city_village_pk, cv.district_pk,
               d.district_name,
               cv.city_village_code, cv.city_village_name,
               cv.city_village_type,
               cv.display_order, cv.is_active
        FROM   nss.city_village cv
        JOIN   nss.district d ON d.district_pk = cv.district_pk
        WHERE  cv.is_active = TRUE
          AND  d.is_active = TRUE
    """
    params: list = []

    if district_pk is not None:
        base_sql += " AND cv.district_pk = %s"
        params.append(str(district_pk))

    base_sql += " ORDER BY d.district_name, cv.display_order, cv.city_village_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, CityVillageResponse)
```

`list_cities(district_pk: UUID | None = Query(None, ...), ...)` joined to `nss.district` for
`district_name`; the docstring notes it "currently returns empty — no seed data by design."
There is deliberately **no** `/cities/{pk}` detail endpoint in this file.

Lines 413–445 — `GET /postal-codes`:

```python
@router.get("/postal-codes", response_model=list[PostalCodeResponse])
def list_postal_codes(
    state_pk: UUID | None = Query(None, description="Filter by state"),
    country_pk: UUID | None = Query(None, description="Filter by country"),
    conn=Depends(get_connection),
) -> list[PostalCodeResponse]:
    """
    List all active postal codes.

    Optionally filter by state or country.
    """
    base_sql = """
        SELECT pc.postal_code_pk, pc.state_pk,
               s.state_name, s.country_pk,
               pc.postal_code, pc.is_active
        FROM   nss.postal_code pc
        JOIN   nss.state s ON s.state_pk = pc.state_pk
        WHERE  pc.is_active = TRUE
    """
    params: list = []

    if state_pk is not None:
        base_sql += " AND pc.state_pk = %s"
        params.append(str(state_pk))
    elif country_pk is not None:
        base_sql += " AND s.country_pk = %s"
        params.append(str(country_pk))

    base_sql += " ORDER BY pc.postal_code"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, PostalCodeResponse)
```

`list_postal_codes(state_pk: UUID | None = Query(None, ...), country_pk: UUID | None =
Query(None, ...), ...)` joined to `nss.state` for `state_name`; if `state_pk` is given it takes
precedence over `country_pk` (the `elif`) — the two filters are mutually exclusive
alternatives, not combinable. Under the Simplified Geography Model (2026-10-02)
`nss.postal_code` no longer stores a `country_pk` of its own, so the country filter is applied
to the joined `s.country_pk` and the returned `country_pk` is re-derived from the parent state.
Each PIN is a single globally-unique, state-scoped row, so there is no office-level column to
select. No detail endpoint.

Lines 448–485 — `GET /postal-code-mappings`:

```python
@router.get("/postal-code-mappings", response_model=list[PostalCodeMappingResponse])
def list_postal_code_mappings(
    city_village_pk: UUID | None = Query(None, description="Filter by city/village"),
    postal_code_pk: UUID | None = Query(None, description="Filter by postal code"),
    conn=Depends(get_connection),
) -> list[PostalCodeMappingResponse]:
    """
    List city/village to postal code mappings.

    Pure junction table — no is_active, no soft-delete.
    Currently returns empty — no seed data by design.
    """
    base_sql = """
        SELECT m.city_village_postal_code_map_pk,
               m.city_village_pk, cv.city_village_name,
               m.postal_code_pk, pc.postal_code
        FROM   nss.city_village_postal_code_map m
        JOIN   nss.city_village cv ON cv.city_village_pk = m.city_village_pk
        JOIN   nss.postal_code pc ON pc.postal_code_pk = m.postal_code_pk
    """
    conditions: list[str] = []
    params: list = []

    if city_village_pk is not None:
        conditions.append("m.city_village_pk = %s")
        params.append(str(city_village_pk))
    if postal_code_pk is not None:
        conditions.append("m.postal_code_pk = %s")
        params.append(str(postal_code_pk))

    if conditions:
        base_sql += " WHERE " + " AND ".join(conditions)

    base_sql += " ORDER BY cv.city_village_name, pc.postal_code"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, PostalCodeMappingResponse)
```

`list_postal_code_mappings(city_village_pk: UUID | None = Query(None, ...), postal_code_pk:
UUID | None = Query(None, ...), ...)` double joins `nss.city_village_postal_code_map m` to
both `nss.city_village cv` and `nss.postal_code pc`. Unlike `postal-codes`, this builds both
filters into a `conditions` list joined with `AND` — the two filters here are **independent
and combinable** ("mappings for city X AND postal code Y"), appropriate for a junction table
lookup. No `is_active` filter anywhere in this query — the docstring and the schema both state
this table has no soft-delete. No detail endpoint.

**Runtime group (lines 489–525, 1 endpoint):**

`GET /documents`:

```python
@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    document_type_code: str | None = Query(None, description="Filter by document type code"),
    conn=Depends(get_connection),
) -> list[DocumentResponse]:
    """
    List all active documents.

    Tier 1 exposes only currently useful fields. FK fields
    (person_pk, uploaded_by_sangha_sevi_pk) excluded — targets
    don't exist yet. Response shape revisited when consuming
    modules arrive.
    Currently returns empty — documents are runtime data.
    """
    base_sql = """
        SELECT document_master_pk, document_type_code,
               document_number, document_name, storage_path,
               file_size_bytes, mime_type, version, checksum,
               description, is_active
        FROM   nss.document_master
        WHERE  is_active = TRUE
    """
    params: list = []

    if document_type_code is not None:
        base_sql += " AND document_type_code = %s"
        params.append(document_type_code)

    base_sql += " ORDER BY document_type_code, document_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return _rows_to_models(cur, DocumentResponse)
```

`list_documents(document_type_code: str | None = Query(None, ...), ...)` against
`nss.document_master`, optionally filtered by the business-key `document_type_code` (e.g.
`"PHOTO"`). No JOINs; FK columns `person_pk` and `uploaded_by_sangha_sevi_pk` exist in the
table but are excluded from the SELECT because their target tables (Person module) don't exist
yet. The docstring states the response shape "will be revisited when consuming modules
arrive." Currently always returns an empty list — documents are runtime data, not seed data.

---

### 2.6 `api/schemas/bootstrap.py`

**Requirement**

`api/routers/bootstrap.py` needs a typed, validated shape for every JSON response it returns, and
that shape must deliberately hide internal audit columns (`created_at`,
`created_by_sangha_sevi_pk`, `updated_at`, `updated_by_sangha_sevi_pk`, `deleted_at`,
`deleted_by_sangha_sevi_pk`) that exist in the underlying `nss.role_master` /
`nss.permission_master` tables but are not consumer-facing data. Without this file the router
would either return raw dict/tuple data with no validation or type coercion, or would leak audit
metadata to any anonymous caller.

**Line-by-line**

Lines 1–9 — module docstring:

```python
"""
NSS ERP — Pydantic response schemas for Bootstrap RBAC endpoints.

These schemas define the API contract. They deliberately exclude
audit columns (created_at, *_by_sangha_sevi_pk) — those are internal.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""
```

States the schemas "define the API contract," "deliberately exclude audit columns... those are
internal," and that `ConfigDict(from_attributes=True)` is unnecessary because raw psycopg2
returns dictionaries, not ORM objects.

Line 11:

```python
from uuid import UUID
```

Pydantic serializes this as a string in JSON.

Line 13:

```python
from pydantic import BaseModel
```

Pydantic v2 base class.

Lines 16–26:

```python
class RoleResponse(BaseModel):
    """Single role from nss.role_master."""

    role_master_pk: UUID
    role_code: str
    role_name: str
    role_class: str
    scope_level: str | None
    description: str | None
    display_order: int
    is_active: bool
```

One field per non-audit column of `nss.role_master`; `str | None` (Python 3.10+ union syntax)
marks the two genuinely nullable columns.

Lines 29–38:

```python
class PermissionResponse(BaseModel):
    """Single permission from nss.permission_master."""

    permission_master_pk: UUID
    permission_code: str
    permission_name: str
    module_code: str
    description: str | None
    display_order: int
    is_active: bool
```

Same pattern, mapped to `nss.permission_master`.

Lines 41–46:

```python
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
```

The minimal two-field contract `health_check()` returns, deliberately not including anything
that could reveal connection internals.

---

### 2.7 `api/schemas/foundation.py`

**Requirement**

`api/routers/foundation.py` needs 11 typed response models — one per queried shape — covering
Master Data, System Configuration, Geographic, and Runtime data, several of which must include
fields pulled in via SQL `JOIN` (e.g. a state's parent `country_code`/`country_name`) so the
frontend can render parent context without a second API call. Without this file the router's
17 endpoints would have no `response_model=` to validate against, and there would be no single
place documenting, for instance, that `current_value` and `person_pk` are deliberately excluded
from their respective responses.

**Line-by-line**

Lines 1–9 — module docstring:

```python
"""
Pydantic response models for the Foundation API (Tier 1).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""
```

States audit columns are excluded per the Tier 0 convention, and that
`ConfigDict(from_attributes=True)` is unnecessary for the same reason as `schemas/bootstrap.py`.

Lines 11–13:

```python
from uuid import UUID

from pydantic import BaseModel
```

Same imports as `schemas/bootstrap.py`.

**Master Data Subsystem (lines 16–47, 2 models):**

Lines 20–28 — `CategoryResponse`:

```python
class CategoryResponse(BaseModel):
    """Master category — a logical group of related master values."""

    master_category_pk: UUID
    category_code: str
    category_name: str
    description: str | None
    display_order: int
    is_active: bool
```

Maps 1:1 to `nss.master_category`.

Lines 31–47 — `MasterDataResponse`:

```python
class MasterDataResponse(BaseModel):
    """
    Master data value with parent category context.

    Includes category_code and category_name via JOIN so the UI can
    display master data with its category context in a single API call.
    """

    master_data_pk: UUID
    master_category_pk: UUID
    category_code: str
    category_name: str
    value_code: str
    value_name: str
    description: str | None
    display_order: int
    is_active: bool
```

The docstring explains `category_code`/`category_name` are included "via JOIN so the UI can
display master data with its category context in a single API call."

**System Configuration Subsystem (lines 50–79, 2 models):**

Lines 54–62 — `SettingResponse`:

```python
class SettingResponse(BaseModel):
    """System-wide configurable setting."""

    system_setting_pk: UUID
    setting_key: str
    setting_value: str
    description: str | None
    data_type: str
    is_active: bool
```

`setting_value` is always a string in the API regardless of the setting's logical type;
`data_type` tells the consumer how to interpret it.

Lines 65–79 — `SequenceResponse`:

```python
class SequenceResponse(BaseModel):
    """
    ID sequence configuration for generating business identifiers.

    Infrastructure/verification endpoint. current_value is excluded —
    it's infrastructure state, not consumer data.
    """

    id_sequence_master_pk: UUID
    sequence_code: str
    sequence_name: str
    prefix: str
    padding_length: int
    description: str | None
    is_active: bool
```

The docstring states this is an "Infrastructure/verification endpoint. `current_value` is
excluded — it's infrastructure state, not consumer data." No `current_value` field at all,
matching the router's SELECT column list.

**Geographic Subsystem (lines 82–167, 6 models):**

Lines 86–93 — `CountryResponse`:

```python
class CountryResponse(BaseModel):
    """Country reference record."""

    country_pk: UUID
    country_code: str
    country_name: str
    display_order: int
    is_active: bool
```

Standalone, no JOINed fields.

Lines 96–110 — `StateResponse`:

```python
class StateResponse(BaseModel):
    """
    State/province with parent country context.

    Includes country_code and country_name via JOIN.
    """

    state_pk: UUID
    country_pk: UUID
    country_code: str
    country_name: str
    state_code: str
    state_name: str
    display_order: int
    is_active: bool
```

The docstring notes it "Includes country_code and country_name via JOIN."

Lines 113–127 — `DistrictResponse`:

```python
class DistrictResponse(BaseModel):
    """
    District with parent state context.

    Includes state_name via JOIN. Does not include country fields —
    resolve via the state's country_pk if needed.
    """

    district_pk: UUID
    state_pk: UUID
    state_name: str
    district_code: str
    district_name: str
    display_order: int
    is_active: bool
```

The docstring notes it "Includes state_name via JOIN. Does not include country fields —
resolve via the state's country_pk if needed."

Lines 130–140 — `CityVillageResponse`:

```python
class CityVillageResponse(BaseModel):
    """City/village with parent district context."""

    city_village_pk: UUID
    district_pk: UUID
    district_name: str
    city_village_code: str
    city_village_name: str
    city_village_type: str
    display_order: int
    is_active: bool
```

`city_village_type` distinguishes `CITY` from `VILLAGE`.

Lines 143–152 — `PostalCodeResponse`:

```python
class PostalCodeResponse(BaseModel):
    """Postal code with parent state context."""

    postal_code_pk: UUID
    country_pk: UUID
    state_pk: UUID
    state_name: str
    postal_code: str
    is_active: bool
```

`country_pk` is still returned for the frontend's country → state → PIN cascade, but it is
sourced from the joined `state.country_pk` rather than stored on `nss.postal_code`. There are
no office-level fields: under the Simplified Geography Model (2026-10-02) a PIN is one
globally-unique, state-scoped row carrying its pre-resolved dominant state, so
`post_office_name` and `office_count` no longer exist.

Lines 155–167 — `PostalCodeMappingResponse`:

```python
class PostalCodeMappingResponse(BaseModel):
    """
    City/village to postal code mapping (M:N junction).

    Pure junction table — no is_active, no soft-delete.
    Includes display fields from both sides via JOIN.
    """

    city_village_postal_code_map_pk: UUID
    city_village_pk: UUID
    city_village_name: str
    postal_code_pk: UUID
    postal_code: str
```

The docstring notes "Pure junction table — no is_active, no soft-delete. Includes display
fields from both sides via JOIN." — deliberately no `is_active` or `display_order` field,
unlike every other model in this file.

**Runtime Tables (lines 170–196, 1 model):**

Lines 174–196 — `DocumentResponse`:

```python
class DocumentResponse(BaseModel):
    """
    Document master record.

    Tier 1 exposes only the currently useful fields. FK fields
    (person_pk, uploaded_by_sangha_sevi_pk) are excluded — their
    targets don't exist yet. The response shape will be revisited
    when consuming modules arrive; no assumption is made here about
    the final representation.
    """

    document_master_pk: UUID
    document_type_code: str
    document_number: str | None
    document_name: str
    storage_path: str
    file_size_bytes: int | None
    mime_type: str | None
    version: int
    checksum: str | None
    description: str | None
    is_active: bool
```

The docstring states the model is intentionally shape-agnostic: "Tier 1 exposes only the
currently useful fields. FK fields (person_pk, uploaded_by_sangha_sevi_pk) are excluded — their
targets don't exist yet. ... no assumption is made here about the final representation."

---

### 2.8 `api/__init__.py`, `api/routers/__init__.py`, `api/schemas/__init__.py`

**Requirement**

Python needs each of `api/`, `api/routers/`, and `api/schemas/` to be an importable package so
statements like `from api.database import get_connection`, `from api.routers import bootstrap,
foundation`, and `from api.schemas.foundation import CategoryResponse` resolve correctly, both
when running `uvicorn api.main:app` from the repository root and when pytest imports `api.main`
in `tests/conftest.py`. Without these three files, none of those imports would work.

**Line-by-line**

All three are package markers, not code.

`api/__init__.py` has one line of content:

```python
# NSS ERP — FastAPI API Layer
```

A comment identifying the package; it defines no names and has no runtime effect beyond
marking `api/` as a package.

`api/routers/__init__.py` and `api/schemas/__init__.py` are both completely empty files —
there is no code to show for either. Their mere presence is what makes `api.routers` and
`api.schemas` importable as packages; they contribute no code, re-exports, or `__all__`
declarations. Everything imported from these packages elsewhere in the codebase is imported by
its explicit submodule path (e.g. `from api.routers import bootstrap, foundation, organization`,
not `from api.routers import router`), so there was never a need to populate these files with
re-exports.

---

### 2.9 `api/routers/organization.py`

> **v2.0 (2026-09-12):** `organization_type_master`/`organization_status_master` retired.
> `/types` and `/statuses` (and the `_ORG_SELECT` fragment and `/hierarchy` CTE) now query
> Foundation's shared `nss.master_data` JOINed to `nss.master_category`, filtered by
> `category_code = 'ORGANIZATION_TYPE'` / `'STATUS'`. `organization`'s FK columns are renamed to
> `organization_type_master_data_pk` / `status_master_data_pk`. `OrganizationStatusResponse` is
> renamed to `StatusResponse` throughout.

> **v2.1 (Tier 4, on top of Family + Membership):** New endpoint
> `GET /organizations/{organization_pk}/children-stats` (`OrgChildStatsResponse`) — 6 endpoints
> becomes 7. Computes per-direct-child family/member/person counts by recursively walking every
> descendant Sakha and applying the same "family's effective Sakha is whichever Sakha holds a
> majority of the family's active member affiliations" rule (FAM-036) that
> `api/routers/family.py`'s `/families/{pk}/sakha-alignment` endpoint (see §2.13)
> implements independently. **The module docstring below (lines 1–16) was not updated when this
> endpoint was added** — it still says "6 GET endpoints" and still lists only
> Reference/Core/Navigation as the endpoint groups, with no "Stats" group; this is a known
> docstring/code drift, not a documentation error in this file.

**Requirement**

Tier 2 exposes 7 read-only GET endpoints across `organization` plus Foundation's shared
`master_data`/`master_category` tables (for type/status) so the Organization Verification UI
and any consumer can browse type/status catalogues, list and detail organizations with full
resolved context (type name, status name, parent name, geographic names), view an
organization's direct children, fetch aggregate family/member/person counts per direct child
(`/children-stats`), and traverse the complete organizational hierarchy as a flat list with
depth. The `organization` table FKs into 5 Foundation geographic tables (country, state,
district, city_village, postal_code) — all nullable, so every geographic column is resolved via
`LEFT JOIN` rather than `JOIN`. Without this file, the `organization` DDL table would have no
HTTP surface at all.

**Line-by-line**

Lines 1–16 — module docstring:

```python
"""
Organization API router — Tier 2 read-only endpoints.

6 GET endpoints across the organization table plus Foundation
master_data (for type/status). No authentication.
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Reference:   types, statuses (from master_data)
  - Core:        organizations (list, detail, children)
  - Navigation:  hierarchy (recursive CTE tree)

Organization type values are stored in Foundation master_data
under category ORGANIZATION_TYPE. Status values use the unified
ERP-wide STATUS category (shared across all modules).
"""
```

States "6 GET endpoints across the organization table plus Foundation master_data," names the
three endpoint groups (Reference / Core / Navigation), and — new in v2.0 — explicitly documents
that type/status values now live in Foundation's `master_data` rather than dedicated
Organization tables (categories `ORGANIZATION_TYPE` and the unified, cross-module `STATUS`).

Lines 18–20:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
```

Same imports as `foundation.py`: `UUID` for path parameters, `APIRouter` for grouping,
`Depends` for connection injection, `HTTPException` for 404 responses, `Query` for optional
filter parameters.

Lines 22–28:

```python
from api.database import get_connection
from api.schemas.organization import (
    OrganizationHierarchyNodeResponse,
    OrganizationResponse,
    OrganizationTypeResponse,
    StatusResponse,
)
```

All 4 response models used by this router. `StatusResponse` (renamed from
`OrganizationStatusResponse`) reflects that lifecycle status is no longer Organization-owned —
it's the shared, unified `STATUS` category from Foundation.

Line 30:

```python
router = APIRouter(prefix="/api/v1/organization", tags=["organization"])
```

Separate prefix and Swagger tag from the bootstrap and foundation routers.

Lines 35–47 — helpers:

```python
def _rows_to_models(cur, model_class):
    """Convert cursor results to a list of Pydantic models."""
    columns = [desc[0] for desc in cur.description]
    return [model_class(**dict(zip(columns, row))) for row in cur.fetchall()]


def _row_to_model(cur, model_class):
    """Convert a single cursor result to a Pydantic model, or None."""
    columns = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    if row is None:
        return None
    return model_class(**dict(zip(columns, row)))
```

Identical to the helpers in `foundation.py` — the same "cursor → Pydantic" bridge. These
are **not** imported from `foundation.py`; each router file owns its own copy, keeping the
modules independently self-contained (no cross-router import dependency).

Lines 52–105 — shared SQL fragment:

```python
_ORG_SELECT = """
    SELECT o.organization_pk,
           o.organization_id,
           o.organization_name,
           o.organization_code,
           ot.master_data_pk   AS organization_type_pk,
           ot.value_code       AS organization_type_code,
           ot.value_name       AS organization_type_name,
           os.master_data_pk   AS status_pk,
           os.value_code       AS status_code,
           os.value_name       AS status_name,
           o.parent_organization_pk,
           p.organization_name AS parent_organization_name,
           o.address_line_1,
           o.address_line_2,
           o.phone_number,
           o.mobile_number,
           o.email,
           o.org_email,
           o.website_url,
           o.org_website_url,
           o.youtube_channel_url,
           o.org_youtube_channel_url,
           o.district_pk,
           d.district_name,
           o.state_pk,
           s.state_name,
           o.country_pk,
           c.country_name,
           o.city_village_pk,
           cv.city_village_name,
           o.postal_code_pk,
           pc.postal_code,
           o.latitude,
           o.longitude,
           o.is_active
    FROM   nss.organization o
    JOIN   nss.master_data ot
           ON ot.master_data_pk = o.organization_type_master_data_pk
    JOIN   nss.master_data os
           ON os.master_data_pk = o.status_master_data_pk
    LEFT JOIN nss.organization p
           ON p.organization_pk = o.parent_organization_pk
    LEFT JOIN nss.district d
           ON d.district_pk = o.district_pk
    LEFT JOIN nss.state s
           ON s.state_pk = o.state_pk
    LEFT JOIN nss.country c
           ON c.country_pk = o.country_pk
    LEFT JOIN nss.city_village cv
           ON cv.city_village_pk = o.city_village_pk
    LEFT JOIN nss.postal_code pc
           ON pc.postal_code_pk = o.postal_code_pk
"""
```

A module-level constant holding the reusable SELECT + FROM + JOIN block shared by the list,
detail, and children endpoints. This is the Organization router's equivalent of
`foundation.py`'s inline `base_sql` fragments, but factored into a single constant because
all three endpoints use the exact same 35-column, 8-join query shape and only differ in
their WHERE clause.

The 8 JOINs:
- 2 × `JOIN` (inner) — both against `nss.master_data`, aliased `ot` (type) and `os` (status):
  every organization row has exactly one type and one status, so inner joins are correct. Unlike
  the retired dedicated tables, both joins now target the *same* `master_data` table — the
  distinction between "type" and "status" comes entirely from which FK column
  (`organization_type_master_data_pk` vs `status_master_data_pk`) drives the join, not from
  which table is joined. Note `_ORG_SELECT` does **not** itself filter `ot`/`os` by
  `category_code` — it relies on each `organization` row's FK already pointing at the correct
  category's `master_data` row (enforced at data-entry time, not by this query or by the FK
  constraint itself, which only guarantees the row exists in `master_data`, not which category
  it belongs to).
- 6 × `LEFT JOIN` — `organization p` (parent, nullable self-FK), `district`, `state`,
  `country`, `city_village`, `postal_code`: all nullable FK columns, so a `LEFT JOIN`
  ensures rows with no address or no parent still appear in results.

The aliased column `p.organization_name AS parent_organization_name` resolves the parent's
display name in the same query, so the UI never needs a separate call to look up a parent.
`ot.master_data_pk AS organization_type_pk` and `os.master_data_pk AS status_pk` (plus the
matching `value_code`/`value_name` aliases) keep the response field names stable
(`organization_type_pk/code/name`, `status_pk/code/name`) even though the underlying columns are
now `master_data`'s generic `master_data_pk`/`value_code`/`value_name` — the aliasing is what
lets `OrganizationResponse` stay decoupled from the physical schema.

**Reference Data endpoints (lines 113–156):**

Lines 113–133 — `GET /types`:

```python
@router.get("/types", response_model=list[OrganizationTypeResponse])
def list_organization_types(
    conn=Depends(get_connection),
) -> list[OrganizationTypeResponse]:
    """List all active organization types (10 frozen types from master_data)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT md.master_data_pk  AS organization_type_pk,
                   md.value_code      AS organization_type_code,
                   md.value_name      AS organization_type_name,
                   md.description,
                   md.display_order   AS sort_order,
                   md.is_active
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  mc.category_code = 'ORGANIZATION_TYPE'
              AND  md.is_active = TRUE
            ORDER BY md.display_order
        """)
        return _rows_to_models(cur, OrganizationTypeResponse)
```

Queries Foundation's `nss.master_data` JOINed to `nss.master_category`, filtered to
`category_code = 'ORGANIZATION_TYPE'`, `ORDER BY md.display_order`. This replaces the
pre-migration flat query against the now-retired `nss.organization_type_master`. Returns the 10
frozen organization types (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA, ANCHALIKA_SANGHA,
ZILLA_SANGHA, SAKHA_SANGHA, SAKHA_ASANA, PARIBARIK_ASANA, PARIBARIK_SANGHA, PATHA_CHAKRA) — two
more than the pre-migration 8, since `PARIBARIK_ASANA` and `PARIBARIK_SANGHA` were added to the
`ORGANIZATION_TYPE` category during the same migration. `md.display_order` (Foundation's generic
column name) is aliased `AS sort_order` so `OrganizationTypeResponse`'s field name is unaffected
by the underlying schema change.

Lines 136–156 — `GET /statuses`:

```python
@router.get("/statuses", response_model=list[StatusResponse])
def list_statuses(
    conn=Depends(get_connection),
) -> list[StatusResponse]:
    """List active lifecycle statuses applicable to the Organization module."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT md.master_data_pk  AS status_pk,
                   md.value_code      AS status_code,
                   md.value_name      AS status_name,
                   md.description,
                   md.display_order   AS sort_order,
                   md.is_active
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  mc.category_code = 'STATUS'
              AND  md.is_active = TRUE
              AND  ('ORGANIZATION' = ANY(md.applicable_modules)
                    OR md.applicable_modules IS NULL)
            ORDER BY md.display_order
        """)
        return _rows_to_models(cur, StatusResponse)
```

Identical shape to `/types`, filtered to `category_code = 'STATUS'` instead. This is the same
handler name change as the schema rename — `list_organization_statuses` became `list_statuses`,
and the docstring/route now says "lifecycle statuses" rather than "organization lifecycle
statuses," since `STATUS` is a unified category shared across modules, not owned by
Organization. **As of Tier 4**, `master_data` gained an `applicable_modules TEXT[]` column so
each module sees only its own applicable subset of the now-16-value `STATUS` category — this
query's `WHERE` clause gained the `'ORGANIZATION' = ANY(...)  OR ... IS NULL` predicate, and the
docstring was reworded from "(13 unified statuses from master_data)" to the module-scoped
description above. Returns 7 lifecycle statuses for Organization (PROPOSED, APPROVED, ACTIVE, INACTIVE,
SUSPENDED, DISSOLVED, ARCHIVED) — the other 9 values are filtered out: Membership-only
(LAPSED, TRANSFERRED, RESIGNED, EXPELLED, EXPIRED, plus the 3 new `RENEWAL_PENDING`/`ON_HOLD`/
`DISCIPLINARY_REVIEW`) and Person-only (DECEASED). `EXPIRED` is tagged `{MEMBERSHIP}` (not a
separate "Credential" scope, despite `parichaya_patra.status`/`anumati_patra.status` each being
their own inline `VARCHAR` + `CHECK` column rather than an FK into `master_data` — credential
expiry from non-renewal of a Parichaya Patra/Anumati Patra is exactly how a membership actually
lapses in practice, so `{MEMBERSHIP}` is the correct tag).
**Known test gap:** `tests/test_organization.py::test_list_returns_13_statuses` still asserts
the old unfiltered count of 13 and was not updated for this filter — it now fails.

**Core CRUD-read endpoints (lines 164–244):**

Lines 164–189 — `GET /organizations`:

```python
@router.get("/organizations", response_model=list[OrganizationResponse])
def list_organizations(
    type_code: str | None = Query(None, description="Filter by organization type code"),
    status_code: str | None = Query(None, description="Filter by status code"),
    conn=Depends(get_connection),
) -> list[OrganizationResponse]:
```

Builds the query by appending `WHERE o.is_active = TRUE` to `_ORG_SELECT`, then optionally
appending `AND ot.value_code = %s` and/or `AND os.value_code = %s` (renamed from
`ot.organization_type_code`/`os.organization_status_code`, since the joined table is now
`master_data` whose value column is generically named `value_code`). Unlike Foundation's
`master-data` (which uses `elif` — mutually exclusive filters), here both filters are
**independently combinable** with `if`/`if` (not `if`/`elif`) — filtering by both type and
status simultaneously is valid. The final `ORDER BY ot.display_order, o.organization_name` also
switched from `ot.sort_order` to `ot.display_order` to match `master_data`'s column name.

Lines 192–208 — `GET /organizations/{organization_pk}`:

Same `_ORG_SELECT` with a PK filter and `AND o.is_active = TRUE`, 404 if `_row_to_model`
returns `None`.

Lines 211–244 — `GET /organizations/{organization_pk}/children`:

Two-cursor pattern (same as `bootstrap.py`'s `list_role_permissions`): the first cursor
verifies the parent organization exists with `SELECT 1 FROM nss.organization WHERE
organization_pk = %s AND is_active = TRUE`; 404 if missing. The second cursor fetches
direct children via `WHERE o.parent_organization_pk = %s AND o.is_active = TRUE`, ordered by
`ot.display_order, o.organization_name`. In the current seed state (3 root organizations, no
children), this always returns an empty list for valid parents.

**Children Stats endpoint (`_CHILDREN_STATS_SQL`, `list_children_stats`):**

New in Tier 4, on top of Family + Membership. `GET
/organizations/{organization_pk}/children-stats` answers "for each direct child of this org,
how many families/members/persons live under it" — the docstring says it is "used by the org
admin sidebar to display inline counts on each drill-down card," though no UI wiring exists:
neither the original `frontend/organization.html`/`frontend/assets/js/organization.js` (both
since deleted) nor their successor, `frontend/admin.html`'s Organization Hierarchy tab, calls it
— see `UI_CODE_EXPLANATIONS.md`.

Same two-cursor shape as `/children`: a first cursor 404s if the parent doesn't exist
(`is_active = TRUE`), then a second cursor runs `_CHILDREN_STATS_SQL` and maps rows to
`OrgChildStatsResponse` via the shared `rows_to_models` helper.

`_CHILDREN_STATS_SQL` is a seven-CTE query, parameterized on the single `organization_pk` of
the requested parent:

```sql
WITH RECURSIVE org_tree AS (
    -- Anchor: direct children of the requested parent
    SELECT o.organization_pk, o.organization_pk AS root_child_pk, ...
    FROM   nss.organization o JOIN nss.master_data ot ON ...
    WHERE  o.parent_organization_pk = %s AND o.is_active = TRUE
    UNION ALL
    -- Recursive: descendants
    SELECT o.organization_pk, t.root_child_pk, ...
    FROM   nss.organization o JOIN nss.master_data ot ON ...
    JOIN   org_tree t ON t.organization_pk = o.parent_organization_pk
    WHERE  o.is_active = TRUE
),
sakha_pks AS ( ... ),
family_majority AS ( ... ),
family_effective AS ( ... ),
family_counts AS ( ... ),
member_counts AS ( ... ),
person_counts AS ( ... )
SELECT ... FROM org_tree ot LEFT JOIN family_counts fc ... LEFT JOIN member_counts mc ...
LEFT JOIN person_counts pc ... WHERE ot.organization_pk = ot.root_child_pk
ORDER BY ot.organization_name
```

- **`org_tree`** — a `WITH RECURSIVE` CTE identical in shape to the `/hierarchy` CTE, but
  anchored on the requested parent's direct children (not global roots) and carrying a second
  column, `root_child_pk`, that every descendant row copies forward unchanged from its anchor
  row. This is the mechanism that lets a Kendra-level call attribute a great-grandchild Sakha's
  counts back up to the correct Anchalika-level direct child — every row in the CTE, no matter
  how deep, still knows which of the parent's *direct* children it descends from. Unlike
  `/hierarchy`'s CTE there is no explicit `depth` column or `depth < 10` guard written into this
  particular CTE text — the code comment says "capped depth via the existing `WITH RECURSIVE`
  pattern," but the depth cap itself is not present in this query (it relies on the
  data actually terminating — Sakha/Patha Chakra are leaf types with no further children —
  rather than an explicit numeric guard the way `/hierarchy` has one).
- **`sakha_pks`** — filters `org_tree` down to rows where `organization_type_code =
  'SAKHA_SANGHA'`, keeping only `(root_child_pk, sakha_pk)` pairs. Every count below is
  ultimately computed per-Sakha and then rolled up to `root_child_pk` — non-Sakha organization
  types (Anchalika, Zilla, Patha Chakra, Sakha Asana, etc.) contribute zero rows here and,
  transitively, zero stats unless they have a Sakha descendant.
- **`family_majority`** (FAM-036) — for every family (`family_relationship fr`, `is_current =
  TRUE`) joined to its members' active Sakha affiliations (`sangha_sevi` `is_active = TRUE` →
  `membership_sakha_affiliation` `effective_to IS NULL`), counts affiliations per
  `(family_group_pk, sakha_pk)` pair and ranks them per family with `ROW_NUMBER() OVER
  (PARTITION BY family_group_pk ORDER BY COUNT(*) DESC)`. This CTE's SQL text is **line-for-line
  identical** to the `family_majority` CTE inside `_FAMILY_SELECT` in `api/routers/family.py`
  (§2.13) — the same FAM-036 majority computation is implemented twice, independently, rather
  than factored into one shared SQL fragment or helper. See the maintainability note at the end
  of this endpoint's write-up.
- **`family_effective`** — for every active `family_group`, resolves its *effective* Sakha as
  `COALESCE(fm.sakha_pk, fg.sakha_organization_pk)`: the `rn = 1` majority Sakha from
  `family_majority` if one exists, else the family's stored `sakha_organization_pk` (the
  registration/fallback Sakha) — the same fallback logic as `family.py`'s `_FAMILY_SELECT`.
- **`family_counts`** — joins `sakha_pks` to `family_effective` on `effective_sakha_pk =
  sakha_pk` and counts `DISTINCT family_group_pk` per `root_child_pk`. A family counts toward
  a direct child once, no matter how many of its members are affiliated with Sakhas under that
  child (the `DISTINCT` absorbs that).
- **`member_counts`** — joins `sakha_pks` directly to `membership_sakha_affiliation`
  (`effective_to IS NULL`) and `sangha_sevi` (`is_active = TRUE`), counting `DISTINCT
  sangha_sevi_pk` per `root_child_pk`. This is **not** derived from `family_effective` — it
  counts every active member whose *own* current affiliation points at one of the descendant
  Sakhas, independent of which Sakha the member's family was assigned to by the majority rule.
  A member whose personal affiliation disagrees with their family's majority Sakha (the exact
  "mismatch" scenario `family.py`'s `/sakha-alignment` endpoint flags) is still counted here
  under their own affiliated Sakha's `root_child_pk`, not their family's.
- **`person_counts`** — joins `sakha_pks` to `family_effective` (same as `family_counts`) and
  then to `family_relationship` (`is_current = TRUE`) to count `DISTINCT person_pk` per
  `root_child_pk` — every current member of every family whose *effective* Sakha falls under
  that child, whether or not that person individually holds a Sangha Sevi membership. This is
  why `member_count <= person_count` is a documented test invariant (`tests/test_organization.py
  ::test_children_stats_members_lte_persons`, see `TESTING_CODE_EXPLANATIONS.md`) — not every
  family member is a member.
- **Final `SELECT`** — restricts `org_tree` back down to `ot.organization_pk =
  ot.root_child_pk` (i.e. only the direct children themselves, not their descendants) and
  `LEFT JOIN`s the three count CTEs, `COALESCE`-ing each to `0` so a direct child with no Sakha
  descendants (or no families/members yet) still appears with zero counts rather than being
  dropped. Ordered by `organization_name`.

**Maintainability observation (not fixed here per scope):** the `family_majority` CTE text is
duplicated verbatim between this file's `_CHILDREN_STATS_SQL` and `family.py`'s
`_FAMILY_SELECT` — two independent copies of the same FAM-036 majority-rule SQL, not a shared
constant or helper. A schema or business-rule change to FAM-036 (e.g. tie-breaking on equal
counts, or excluding a new affiliation state) would need to be made in both places by hand.

**Hierarchy endpoint (lines 252–309):**

```python
@router.get("/hierarchy", response_model=list[OrganizationHierarchyNodeResponse])
def get_organization_hierarchy(
    conn=Depends(get_connection),
) -> list[OrganizationHierarchyNodeResponse]:
```

The most complex query in the codebase. `WITH RECURSIVE org_tree AS (...)` defines a
recursive CTE with two parts:

- **Anchor member** — selects root organizations (`WHERE o.parent_organization_pk IS NULL
  AND o.is_active = TRUE`), joining to `nss.master_data` (aliased `ot`/`os`) via
  `organization_type_master_data_pk`/`status_master_data_pk` for display names — the same
  master_data-based join pattern as `_ORG_SELECT`, not a separate dedicated-table join — and
  hardcoding `0 AS depth`.
- **Recursive member** — selects children by joining `nss.organization o` to `org_tree t ON
  t.organization_pk = o.parent_organization_pk` (plus the same two `master_data` joins),
  computing `t.depth + 1` for each child level. PostgreSQL executes this recursively until no
  new rows are produced.

The final `SELECT * FROM org_tree ORDER BY depth, organization_name` returns the flat list
sorted breadth-first (all depth-0 roots first, then depth-1 children, etc.). This is
deliberately a **flat** representation — the UI uses `depthIndent(depth)` (see
`UI_CODE_EXPLANATIONS.md`) to visually indent nodes, rather than receiving nested JSON.

The recursive CTE uses a **leaner column set** than `_ORG_SELECT` (10 columns vs 35) — no
address fields, no contact/online-presence fields, no geographic LEFT JOINs, no parent name resolution — because the hierarchy
view shows only the organizational structure (name, type, status, depth), not full detail.
This maps to the dedicated `OrganizationHierarchyNodeResponse` schema (§2.10), whose
`status_code`/`status_name` fields (renamed from `organization_status_code`/
`organization_status_name`) are resolved the same `os.value_code`/`os.value_name` way as
everywhere else in this router.

---

### 2.10 `api/schemas/organization.py`

> **v2.0 (2026-09-12):** `OrganizationStatusResponse` renamed to `StatusResponse` — its fields
> renamed `organization_status_pk/code/name` → `status_pk/code/name` — reflecting that status is
> now sourced from Foundation's shared, unified `STATUS` category rather than an
> Organization-owned table. `OrganizationResponse` and `OrganizationHierarchyNodeResponse`'s
> status fields are renamed to match; their `organization_type_*` fields are unchanged.

**Requirement**

`api/routers/organization.py` needs 5 typed response models: one for each reference-data
catalogue (types, statuses), one for the full organization detail (35 fields including 8
JOINed context fields and 9 contact/online-presence fields), one for the `/children-stats`
aggregate shape (`OrgChildStatsResponse`, new in Tier 4), and one for the hierarchy tree's
leaner node shape (10 fields). Without this file the Organization router would have no
`response_model=` to validate against.

**Line-by-line**

Lines 1–13 — module docstring:

```python
"""
Pydantic response models for the Organization API (Tier 2).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Organization type is sourced from Foundation master_data (category
ORGANIZATION_TYPE). Status is sourced from the unified ERP-wide
STATUS category — a single shared category used by all modules.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""
```

Same audit-column exclusion and ConfigDict note as `schemas/bootstrap.py` and
`schemas/foundation.py`, plus a new paragraph (v2.0) documenting where type/status values now
come from — Foundation's shared `master_data`, not dedicated Organization tables.

Lines 20–28 — `OrganizationTypeResponse` (6 fields):

```python
class OrganizationTypeResponse(BaseModel):
    """Organization type from nss.master_data (category: ORGANIZATION_TYPE)."""

    organization_type_pk: UUID
    organization_type_code: str
    organization_type_name: str
    description: str | None
    sort_order: int
    is_active: bool
```

Field names (`organization_type_pk/code/name`) are unchanged from before the migration — only
the docstring changed, to say the values come "from `nss.master_data` (category:
`ORGANIZATION_TYPE`)" instead of from a dedicated `organization_type_master` table. The router's
`AS organization_type_pk` / `AS organization_type_code` / `AS organization_type_name` aliasing
(§2.9) is what keeps this schema's field names stable across the underlying table swap.

Lines 31–39 — `StatusResponse` (6 fields, renamed from `OrganizationStatusResponse`):

```python
class StatusResponse(BaseModel):
    """Lifecycle status from nss.master_data (category: STATUS)."""

    status_pk: UUID
    status_code: str
    status_name: str
    description: str | None
    sort_order: int
    is_active: bool
```

Both the class name and its three identity fields (`status_pk`, `status_code`, `status_name` —
previously `organization_status_pk`, `organization_status_code`, `organization_status_name`)
dropped the `organization_` prefix, since this is no longer an Organization-specific concept: it's
the unified, ERP-wide `STATUS` category from Foundation, shared by memberships, governance, and
any future module.

Lines 42–107 — `OrganizationResponse` (35 fields):

The largest response model in the codebase. Field groups match the `_ORG_SELECT` column list:
- 4 core fields (`organization_pk`, `organization_id`, `organization_name`,
  `organization_code`).
- 3 classification fields (`organization_type_pk/code/name`) resolved from `nss.master_data`
  (category `ORGANIZATION_TYPE`) via JOIN — field names unchanged from before the migration.
- 3 lifecycle fields (`status_pk/code/name`, renamed from `organization_status_pk/code/name`)
  resolved from the same `nss.master_data` table (category `STATUS`) via a second JOIN.
- 2 hierarchy fields (`parent_organization_pk` + `parent_organization_name` via self-LEFT
  JOIN).
- 2 inline address fields (`address_line_1`, `address_line_2`).
- 4 contact fields (`phone_number`, `mobile_number`, `email` NOT NULL DEFAULT,
  `org_email` nullable).
- 4 online presence fields (`website_url` NOT NULL DEFAULT, `org_website_url` nullable,
  `youtube_channel_url` NOT NULL DEFAULT, `org_youtube_channel_url` nullable).
- 10 geographic context fields (5 FK PKs + 5 resolved names via LEFT JOINs).
- 2 coordinate fields (`latitude`, `longitude`).
- 1 `is_active`.

Every nullable field uses `UUID | None`, `str | None`, or `float | None` — matching the
LEFT JOIN / nullable-FK reality. The docstring's closing paragraph spells out the rename
explicitly: "Type fields are aliased from master_data columns for the ORGANIZATION_TYPE
category. Status fields use the unified ERP-wide STATUS category."

`OrgChildStatsResponse` (7 fields, new in Tier 4, inserted between `OrganizationResponse` and
`OrganizationHierarchyNodeResponse` in the file):

```python
class OrgChildStatsResponse(BaseModel):
    organization_pk: UUID
    organization_name: str
    organization_code: str | None
    organization_type_code: str
    family_count: int = 0
    member_count: int = 0
    person_count: int = 0
```

Backs the `/organizations/{organization_pk}/children-stats` endpoint (§2.9). The four identity
fields (`organization_pk/name/code/type_code`) describe the direct child itself; the three
`_count` fields all default to `0` — matching `_CHILDREN_STATS_SQL`'s `COALESCE(..., 0)` on
each of the three `LEFT JOIN`ed aggregate CTEs, so a child with no descendant Sakhas (or no
families/members under them) still validates rather than raising on a missing field. The
docstring documents the FAM-036 majority-rule dependency directly: "Counts are computed
dynamically — families use the majority-rule CTE (FAM-036), members use active affiliations.
For non-Sakha orgs the stats aggregate across all descendant Sakhas."

Lines 109–127 — `OrganizationHierarchyNodeResponse` (10 fields):

The leaner shape used by the `/hierarchy` endpoint's recursive CTE. Includes `depth: int`
(computed by the CTE as `0` for roots, `depth + 1` for children) and the type/status
display names — `organization_type_code`/`organization_type_name` plus `status_code`/
`status_name` (the latter two renamed from `organization_status_code`/
`organization_status_name`) — but no address/geographic fields. The docstring explicitly notes
"Children are not nested — the tree is returned flat."

---

### 2.11 `api/routers/person.py`

**Requirement**

Tier 3 exposes 4 read-only GET endpoints across `nss.person` and `nss.person_address` so the
Person Verification UI and any consumer can list/filter persons, view a single person's full
resolved detail, list a person's addresses, and fuzzy-search persons by name/ID/mobile number.
Person carries the ERP's first genuinely sensitive column — an encrypted Aadhaar number — so
this router's defining constraint isn't a new query shape but a security boundary: `person`'s
`aadhaar_encrypted` (BYTEA) and `aadhaar_hash` columns must never appear in any response, no
matter which endpoint or SELECT list is involved, and only the pre-truncated `aadhaar_last4` is
fit to expose for masked display (PER-BR-081). Without this file, `nss.person` and
`nss.person_address` — the two Person DDL tables — would have no HTTP surface at all, and the
Foundation-style JOIN-resolution pattern (gender/marital-status/blood-group/emergency-relationship
master data, and the full geographic chain for addresses) would have nowhere to live.

**Line-by-line**

Lines 1–16 — module docstring:

```python
"""
Person API router — Tier 3 read-only endpoints.

4 GET endpoints across 2 Person tables. No authentication.
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Core:       persons (list with filters, detail)
  - Addresses:  person addresses (per person)
  - Search:     trigram-based name/ID search

Security:
  - aadhaar_encrypted and aadhaar_hash are NEVER returned (PER-BR-081)
  - Only aadhaar_last4 is exposed for masked display
  - Audit actor FKs excluded per API convention
"""
```

States "4 GET endpoints across 2 Person tables," lists the three endpoint groups (Core /
Addresses / Search), and — unlike any prior router's docstring — dedicates an explicit
"Security:" block naming the exact business rule (PER-BR-081), the exact two forbidden columns,
and the one substitute column that is safe to expose. This is the same governance-frozen
constraint documented in `docs/01_Authoritative_References/` and enforced again in
`api/schemas/person.py` (§2.12) — belt-and-suspenders: neither the SQL nor the schema selects
the sensitive columns, so there is no single point of failure.

Lines 18–28:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, row_to_model, rows_to_models
from api.schemas.person import (
    PersonAddressResponse,
    PersonResponse,
    PersonSummaryResponse,
)
```

Same FastAPI/UUID imports as `organization.py`. The notable difference: `row_to_model`/
`rows_to_models` are imported **from `api/helpers.py`** rather than redefined locally. Every
prior router (`bootstrap.py`, `foundation.py`, `organization.py`) carries its own private copy of
these two "cursor → Pydantic" functions; `person.py` is the first to consume the shared module
instead, per `api/helpers.py`'s own docstring rationale — "a single point of maintenance for any
future security hardening (e.g. column sanitisation)," which matters more here than anywhere
else given the Aadhaar-masking constraint above. `DEFAULT_LIMIT` (100) and `MAX_LIMIT` (500) are
likewise the same pagination constants centralized in `api/helpers.py`, used below by
`list_persons` instead of hardcoded literals.

Line 30:

```python
router = APIRouter(prefix="/api/v1/person", tags=["person"])
```

Separate prefix and Swagger tag from the other three routers.

**Shared SQL fragments (lines 33–143):**

```python
_PERSON_DETAIL_SELECT = """
    SELECT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           p.date_of_birth,
           p.date_of_death,
           p.gender_master_data_pk,
           g.value_code   AS gender_code,
           g.value_name   AS gender_name,
           p.marital_status_master_data_pk,
           ms.value_code  AS marital_status_code,
           ms.value_name  AS marital_status_name,
           p.blood_group_master_data_pk,
           bg.value_code  AS blood_group_code,
           bg.value_name  AS blood_group_name,
           p.country_phone_code,
           p.mobile_number,
           p.email,
           p.aadhaar_last4,
           p.photo_document_master_pk,
           p.emergency_contact_name,
           p.emergency_contact_phone,
           p.emergency_relationship_master_data_pk,
           er.value_code  AS emergency_relationship_code,
           er.value_name  AS emergency_relationship_name,
           p.remarks,
           p.is_active
    FROM   nss.person p
    LEFT JOIN nss.master_data g
           ON g.master_data_pk = p.gender_master_data_pk
    LEFT JOIN nss.master_data ms
           ON ms.master_data_pk = p.marital_status_master_data_pk
    LEFT JOIN nss.master_data bg
           ON bg.master_data_pk = p.blood_group_master_data_pk
    LEFT JOIN nss.master_data er
           ON er.master_data_pk = p.emergency_relationship_master_data_pk
"""
```

Unlike `organization.py`'s single `_ORG_SELECT` reused by all three core endpoints, `person.py`
defines **two** person SELECT fragments plus one address fragment — a deliberate split, not an
oversight. `_PERSON_DETAIL_SELECT` is the full 27-column shape used only by `get_person`
(single-record detail): it includes `p.aadhaar_last4` (masked, safe), `p.photo_document_master_pk`,
and the full emergency-contact block. Every master-data lookup — gender, marital status, blood
group, emergency relationship — is a `LEFT JOIN` against the same `nss.master_data` table
(aliased `g`/`ms`/`bg`/`er`), because all four of `person`'s corresponding FK columns are
nullable: a person record can exist with gender/marital-status/blood-group/emergency-relationship
left unset, and a `LEFT JOIN` (not `JOIN`) is what keeps such a row from being silently dropped.
Critically, `_PERSON_DETAIL_SELECT` never lists `p.aadhaar_encrypted` or `p.aadhaar_hash` — the
two columns the module docstring forbids — so even a future maintainer copy-pasting this SELECT
wholesale cannot accidentally leak them; the enforcement is structural, not a runtime check.

```python
_PERSON_SUMMARY_SELECT = """
    SELECT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           p.date_of_birth,
           p.date_of_death,
           g.value_code   AS gender_code,
           g.value_name   AS gender_name,
           ms.value_code  AS marital_status_code,
           ms.value_name  AS marital_status_name,
           bg.value_code  AS blood_group_code,
           bg.value_name  AS blood_group_name,
           p.country_phone_code,
           p.mobile_number,
           p.email,
           p.is_active
    FROM   nss.person p
    LEFT JOIN nss.master_data g
           ON g.master_data_pk = p.gender_master_data_pk
    LEFT JOIN nss.master_data ms
           ON ms.master_data_pk = p.marital_status_master_data_pk
    LEFT JOIN nss.master_data bg
           ON bg.master_data_pk = p.blood_group_master_data_pk
"""
```

`_PERSON_SUMMARY_SELECT` is the compact 17-column shape shared by `list_persons` and
`search_persons` — both multi-row endpoints where payload size matters. It drops
`aadhaar_last4`, the emergency-contact block, and `photo_document_master_pk` entirely (not just
the two forbidden Aadhaar columns — the whole sensitive/heavy block), and correspondingly has one
fewer `LEFT JOIN` (no `emergency_relationship` join, since none of its fields are selected).

```python
_ADDRESS_SELECT = """
    SELECT pa.person_address_pk,
           pa.person_pk,
           pa.address_type_master_data_pk,
           at.value_code  AS address_type_code,
           at.value_name  AS address_type_name,
           pa.address_line_1,
           pa.address_line_2,
           pa.landmark,
           pa.city_village_postal_code_map_pk,
           cv.city_village_name,
           pc.postal_code,
           d.district_name,
           s.state_name,
           c.country_name,
           pa.is_primary,
           pa.remarks,
           pa.is_active
    FROM   nss.person_address pa
    JOIN   nss.master_data at
           ON at.master_data_pk = pa.address_type_master_data_pk
    JOIN   nss.city_village_postal_code_map cvm
           ON cvm.city_village_postal_code_map_pk
              = pa.city_village_postal_code_map_pk
    LEFT JOIN nss.city_village cv
           ON cv.city_village_pk = cvm.city_village_pk
    LEFT JOIN nss.postal_code pc
           ON pc.postal_code_pk = cvm.postal_code_pk
    LEFT JOIN nss.district d
           ON d.district_pk = cv.district_pk
    LEFT JOIN nss.state s
           ON s.state_pk = d.state_pk
    LEFT JOIN nss.country c
           ON c.country_pk = s.country_pk
"""
```

`_ADDRESS_SELECT` resolves location context through a six-table JOIN chain, mixing `JOIN` and
`LEFT JOIN` deliberately rather than uniformly: `at` (address type via `master_data`) and `cvm`
(the `city_village_postal_code_map` junction row itself) use plain `JOIN`, because
`address_type_master_data_pk` and `city_village_postal_code_map_pk` are both `NOT NULL` FKs on
`person_address` — every address row is required to have a type and a location mapping, so an
inner join can't drop a valid row. From `cvm` onward, though, the chain switches to `LEFT JOIN`
for `city_village`, `postal_code`, `district`, `state`, `country` — each of those is reached by
walking the map row's own two FKs (`cvm.city_village_pk`, `cvm.postal_code_pk`) and then further
geographic parent FKs, any of which could in principle be null or point at an inactive/missing
row; a `LEFT JOIN` here means a broken or partial geographic chain degrades gracefully to `NULL`
display names rather than making the whole address disappear from the endpoint's response.

**1. PERSONS — core read (lines 146–218, 2 endpoints):**

Lines 151–193 — `GET /persons`:

```python
@router.get("/persons", response_model=list[PersonSummaryResponse])
def list_persons(
    gender_code: str | None = Query(
        None, description="Filter by gender value_code (e.g. MALE, FEMALE)"
    ),
    marital_status_code: str | None = Query(
        None, description="Filter by marital status value_code"
    ),
    blood_group_code: str | None = Query(
        None, description="Filter by blood group value_code"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
) -> list[PersonSummaryResponse]:
    """
    List all active persons with resolved master-data context.

    Optionally filter by gender_code, marital_status_code, or
    blood_group_code. Returns a compact summary (no Aadhaar,
    emergency, or photo fields). Supports pagination via limit/offset
    (default 100, max 500).
    """
    sql = _PERSON_SUMMARY_SELECT + " WHERE p.is_active = TRUE"
    params: list = []

    if gender_code is not None:
        sql += " AND g.value_code = %s"
        params.append(gender_code)
    if marital_status_code is not None:
        sql += " AND ms.value_code = %s"
        params.append(marital_status_code)
    if blood_group_code is not None:
        sql += " AND bg.value_code = %s"
        params.append(blood_group_code)

    sql += " ORDER BY p.first_name, p.last_name"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return rows_to_models(cur, PersonSummaryResponse)
```

`list_persons` is `person.py`'s only endpoint with query-parameter pagination in the whole API
layer — no Bootstrap, Foundation, or Organization list endpoint accepts `limit`/`offset` at all;
they return their (small, fully-seeded) tables in full. `limit: int = Query(DEFAULT_LIMIT, ge=1,
le=MAX_LIMIT, ...)` and `offset: int = Query(0, ge=0, ...)` mean an out-of-range value (e.g.
`limit=0` or `limit=10000`) is rejected by FastAPI with 422 before the handler body runs, rather
than silently clamped. All three filters (`gender_code`, `marital_status_code`,
`blood_group_code`) use `if` — not `elif` — exactly like `organization.py`'s
`type_code`/`status_code`: they are independently combinable, so a caller can filter by gender
*and* blood group in the same request. `sql += " LIMIT %s OFFSET %s"` with `params.extend([limit,
offset])` appends the pagination clause last, after all WHERE conditions and the `ORDER BY` —
`ORDER BY p.first_name, p.last_name` runs before pagination is applied, so `limit`/`offset`
paginate a *stable, name-sorted* sequence rather than an arbitrary one.

Lines 196–217 — `GET /persons/{person_pk}`:

```python
@router.get(
    "/persons/{person_pk}",
    response_model=PersonResponse,
)
def get_person(
    person_pk: UUID,
    conn=Depends(get_connection),
) -> PersonResponse:
    """
    Get a single person by PK with full resolved context.

    Includes Aadhaar last-4 (masked), emergency contact, and photo
    FK. Never returns aadhaar_encrypted or aadhaar_hash.
    """
    sql = _PERSON_DETAIL_SELECT + " WHERE p.person_pk = %s AND p.is_active = TRUE"

    with conn.cursor() as cur:
        cur.execute(sql, (str(person_pk),))
        result = row_to_model(cur, PersonResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Person not found")
        return result
```

The one endpoint that uses `_PERSON_DETAIL_SELECT`. Same PK-filter-plus-`is_active`/404 pattern
as every other detail endpoint in the codebase (`get_category`, `get_country`, `get_state`, …):
append `WHERE p.person_pk = %s AND p.is_active = TRUE`, parameterize with `(str(person_pk),)`,
and raise `HTTPException(status_code=404, detail="Person not found")` if `row_to_model` returns
`None`. The docstring repeats the security guarantee inline ("Never returns aadhaar_encrypted or
aadhaar_hash") even though it's already stated once in the module docstring — deliberate
redundancy on the one field group in the entire API surface where a silent regression would be a
data-protection incident, not just a contract mismatch.

**2. ADDRESSES (lines 220–257, 1 endpoint):**

Lines 225–257 — `GET /persons/{person_pk}/addresses`:

```python
@router.get(
    "/persons/{person_pk}/addresses",
    response_model=list[PersonAddressResponse],
)
def list_person_addresses(
    person_pk: UUID,
    conn=Depends(get_connection),
) -> list[PersonAddressResponse]:
    """
    List all active addresses for a given person.

    Resolves address type, city/village, postal code, district,
    state, and country names via JOINs. Returns 404 if the person
    does not exist.
    """
    # Verify the person exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.person
            WHERE  person_pk = %s AND is_active = TRUE
        """, (str(person_pk),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Person not found")

    sql = (
        _ADDRESS_SELECT
        + " WHERE pa.person_pk = %s AND pa.is_active = TRUE"
        + " ORDER BY pa.is_primary DESC, at.value_name"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(person_pk),))
        return rows_to_models(cur, PersonAddressResponse)
```

The same two-cursor "verify parent exists, then fetch children" pattern as
`bootstrap.py::list_role_permissions` and `organization.py`'s `/organizations/{pk}/children`: the
first cursor's `SELECT 1 FROM nss.person WHERE person_pk = %s AND is_active = TRUE` exists purely
to distinguish "person exists but has zero addresses" (empty list, 200) from "person doesn't
exist" (`HTTPException(404, "Person not found")`) — `_ADDRESS_SELECT` alone can't make that
distinction, since a `WHERE pa.person_pk = %s` with no matching rows looks identical either way.
The second cursor's `ORDER BY pa.is_primary DESC, at.value_name` puts the primary address first
(PostgreSQL sorts `TRUE` before `FALSE` under `DESC`), then breaks ties alphabetically by
resolved address-type name.

**3. SEARCH (lines 260–304, 1 endpoint):**

Lines 265–304 — `GET /search`:

```python
@router.get("/search", response_model=list[PersonSummaryResponse])
def search_persons(
    q: str = Query(
        ...,
        min_length=2,
        max_length=100,
        description="Search term — matches against first_name (trigram), "
        "last_name (trigram), person_id, or mobile_number",
    ),
    conn=Depends(get_connection),
) -> list[PersonSummaryResponse]:
    """
    Search active persons by name, person_id, or mobile number.

    Uses PostgreSQL trigram similarity (pg_trgm) on first_name for
    fuzzy matching. Also matches exact prefix on person_id and
    mobile_number. Results ordered by trigram similarity (best match
    first), limited to 50 results.
    """
    sql = (
        _PERSON_SUMMARY_SELECT
        + """
        WHERE p.is_active = TRUE
          AND (
              p.first_name %% %s
              OR p.last_name %% %s
              OR p.person_id ILIKE %s
              OR p.mobile_number ILIKE %s
          )
        ORDER BY similarity(p.first_name, %s) DESC,
                 p.first_name, p.last_name
        LIMIT 50
    """
    )

    prefix_pattern = f"{q}%"

    with conn.cursor() as cur:
        cur.execute(sql, (q, q, prefix_pattern, prefix_pattern, q))
        return rows_to_models(cur, PersonSummaryResponse)
```

The only fuzzy-matching endpoint in the API layer. `q: str = Query(..., min_length=2,
max_length=100, ...)` — the `...` (Ellipsis) makes `q` required (unlike every optional filter
elsewhere, which defaults to `None`), and the length bounds mean a 1-character or absurdly long
query is rejected by FastAPI with 422 before touching the database, which also caps how expensive
a single trigram scan can be.

The WHERE clause ORs together four independent match strategies:
- `p.first_name %% %s` and `p.last_name %% %s` — the `%%` in the Python triple-quoted string is
  an *escaped* literal `%`, because this same string later goes through `cur.execute(sql,
  params)`, and psycopg2 treats a bare `%` as the start of a `%s` placeholder; the actual SQL sent
  to PostgreSQL contains a single `%`, which is `pg_trgm`'s **similarity operator** — it matches
  when the trigram similarity between the column and the bound parameter exceeds PostgreSQL's
  configured `pg_trgm.similarity_threshold` (default `0.3`). This is what makes the search
  tolerant of typos/partial names, and it requires the `pg_trgm` extension, installed by
  `database/ddl/01_extensions.sql` per `CLAUDE.md`'s bootstrap sequence.
- `p.person_id ILIKE %s` and `p.mobile_number ILIKE %s` — bound to `prefix_pattern = f"{q}%"`
  (built in Python, then passed as an ordinary bind parameter — not string-interpolated into the
  SQL, so this is not a SQL-injection surface despite the `%` wildcard living inside the bound
  value rather than the query text). This is a **prefix** match (`ILIKE 'abc%'`), not a
  substring or trigram match — appropriate for structured identifiers like `person_id` and
  `mobile_number`, where fuzzy matching would produce noise, not signal.

`ORDER BY similarity(p.first_name, %s) DESC, p.first_name, p.last_name` ranks by first-name
similarity only, even though `last_name` also participates in the WHERE-clause matching — a
result that matched purely on `last_name` trigram similarity, `person_id` prefix, or
`mobile_number` prefix is still ordered by how similar its `first_name` happens to be to `q`
(likely a low or zero score), with the two plain-alphabetical columns breaking ties. `LIMIT 50` is
hardcoded — unlike `list_persons`, this endpoint takes no `limit`/`offset` query parameters at
all. `params = (q, q, prefix_pattern, prefix_pattern, q)` is a 5-tuple whose order maps
positionally to the five `%s` placeholders in the SQL, in this order: first_name trigram,
last_name trigram, person_id prefix, mobile_number prefix, and the `similarity(...)`
`ORDER BY` argument — `q` deliberately appears three times because it's rebound at each of its
three distinct placeholder positions.

---

### 2.12 `api/schemas/person.py`

**Requirement**

`api/routers/person.py` needs three typed response models: a lean summary shape for list/search
results, a full detail shape for the single-person endpoint, and an address shape with resolved
geographic context. All three must structurally exclude `aadhaar_encrypted`/`aadhaar_hash` — the
same PER-BR-081 constraint from the router (§2.11) — so that even if a future SELECT accidentally
widened to include those columns, Pydantic's `response_model=` validation would still only pass
through the fields these classes declare; anything not declared here is silently dropped rather
than serialized. Without this file, `person.py`'s three response-model list types would have
nothing to validate against.

**Line-by-line**

Lines 1–14 — module docstring:

```python
"""
Pydantic response models for the Person API (Tier 3).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Sensitive fields excluded per PER-BR-081:
  - aadhaar_encrypted (BYTEA)  — never exposed
  - aadhaar_hash (VARCHAR)     — never exposed
Only aadhaar_last4 is returned for masked display.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""
```

Same audit-column-exclusion and `ConfigDict` notes as `schemas/bootstrap.py`/
`schemas/foundation.py`/`schemas/organization.py`, plus — new here — an explicit "Sensitive
fields excluded per PER-BR-081" block naming both forbidden columns and their BYTEA/VARCHAR
underlying types, and confirming `aadhaar_last4` is the one substitute field that is safe.

Lines 16–19:

```python
from datetime import date
from uuid import UUID

from pydantic import BaseModel
```

The first schema file in the codebase to import `date` — `person.date_of_birth` and
`person.date_of_death` are the first genuine date-typed columns exposed by any router; Pydantic
validates/serializes them as ISO-8601 date strings (`YYYY-MM-DD`) in JSON.

Lines 22–79 — `PersonResponse` (27 fields):

```python
class PersonResponse(BaseModel):
    """
    Person with resolved master-data context.

    Includes gender_name, marital_status_name, blood_group_name, and
    emergency_relationship_name via JOINs so the UI can display full
    context in a single API call.
    """

    # Identity
    person_pk: UUID
    person_id: str

    # Demographics
    first_name: str
    middle_name: str | None
    last_name: str | None
    date_of_birth: date | None
    date_of_death: date | None

    # Gender (resolved)
    gender_master_data_pk: UUID | None
    gender_code: str | None
    gender_name: str | None

    # Marital status (resolved)
    marital_status_master_data_pk: UUID | None
    marital_status_code: str | None
    marital_status_name: str | None

    # Blood group (resolved)
    blood_group_master_data_pk: UUID | None
    blood_group_code: str | None
    blood_group_name: str | None

    # Contact
    country_phone_code: str | None
    mobile_number: str | None
    email: str | None

    # Sensitive identity — masked display only
    aadhaar_last4: str | None

    # Photo
    photo_document_master_pk: UUID | None

    # Emergency contact (resolved)
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_relationship_master_data_pk: UUID | None
    emergency_relationship_code: str | None
    emergency_relationship_name: str | None

    # Other
    remarks: str | None

    # Lifecycle
    is_active: bool
```

The largest model this router needs, mapping field-for-field onto `_PERSON_DETAIL_SELECT`'s
column list, grouped by inline comments into Identity / Demographics / Gender / Marital status /
Blood group / Contact / sensitive identity / Photo / Emergency contact / Other / Lifecycle. Every
field that comes from a `LEFT JOIN` in the router (all three master-data groups, plus
`emergency_relationship`) is `UUID | None` / `str | None` — matching the nullable-FK reality —
while `person_pk`, `person_id`, `first_name`, and `is_active` (`person`'s own `NOT NULL` columns)
are unqualified. The comment `# Sensitive identity — masked display only` sits directly above the
one field (`aadhaar_last4: str | None`) that survived the PER-BR-081 filter — there is no field
named `aadhaar_encrypted` or `aadhaar_hash` anywhere in this class, which is what makes the
exclusion structural rather than a convention someone has to remember to follow.

Lines 82–106 — `PersonSummaryResponse` (16 fields):

```python
class PersonSummaryResponse(BaseModel):
    """
    Lightweight Person summary for list/search results.

    Omits Aadhaar, emergency contact, and photo details to keep
    list payloads compact.
    """

    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    date_of_birth: date | None
    date_of_death: date | None
    gender_code: str | None
    gender_name: str | None
    marital_status_code: str | None
    marital_status_name: str | None
    blood_group_code: str | None
    blood_group_name: str | None
    country_phone_code: str | None
    mobile_number: str | None
    email: str | None
    is_active: bool
```

Maps onto `_PERSON_SUMMARY_SELECT` and is used by both `list_persons` and `search_persons`. It
drops the three `_master_data_pk` FK fields that `PersonResponse` carries for gender/marital
status/blood group (the summary exposes only the resolved `_code`/`_name` pair, not the raw FK),
and — per the docstring — omits Aadhaar, emergency contact, and photo entirely, not just the
sensitive Aadhaar columns; this is a payload-size decision as much as a security one, since
`list_persons`/`search_persons` can return up to `MAX_LIMIT` (500) or 50 rows respectively.

Lines 109–141 — `PersonAddressResponse` (16 fields):

```python
class PersonAddressResponse(BaseModel):
    """
    Person address with resolved location context.

    Resolves address_type via master_data and location via the
    city_village_postal_code_map junction → city_village + postal_code
    + district + state + country chain.
    """

    person_address_pk: UUID
    person_pk: UUID

    # Address type (resolved)
    address_type_master_data_pk: UUID
    address_type_code: str
    address_type_name: str

    # Address fields
    address_line_1: str
    address_line_2: str | None
    landmark: str | None

    # Location (resolved through junction and geographic chain)
    city_village_postal_code_map_pk: UUID
    city_village_name: str | None
    postal_code: str | None
    district_name: str | None
    state_name: str | None
    country_name: str | None

    is_primary: bool
    remarks: str | None
    is_active: bool
```

Maps onto `_ADDRESS_SELECT`. `address_type_master_data_pk`, `address_type_code`, and
`address_type_name` are all non-nullable (`UUID`/`str`, no `| None`) — matching the router's plain
`JOIN` (not `LEFT JOIN`) against `master_data` for address type, since `person_address`'s FK there
is `NOT NULL`. By contrast, every field resolved through the `city_village_postal_code_map` →
`city_village`/`postal_code`/`district`/`state`/`country` chain (`city_village_name`,
`postal_code`, `district_name`, `state_name`, `country_name`) is `str | None` — matching the
router's `LEFT JOIN`s for that half of the chain, so a broken or partial geographic link degrades
to `None` fields rather than a validation error.

---

### 2.13 `api/routers/family.py`

**Requirement**

Tier 4's Family module exposes 7 read-only GET endpoints across all 4 of the module's DDL tables
(`family_group`, `family_relationship`, `family_head_history`, `family_link` —
`family_transition_history` has no endpoint yet, since it's purely an append-only log with
nothing to verify against in Tier 4's seed data) so the Family Verification UI can list families,
view a single family's resolved detail, list a family's current members, view a family's
head-of-household history, render a dynamically-computed relationship graph relative to any
viewer, compute a family's FAM-036 majority-rule Sakha alignment, and bridge a `person_pk` to its
membership snapshot for the family tree's Selected Person panel. The last three endpoints (§4/§5/§6
below) also read from Tier 4 Membership tables (`sangha_sevi`, `membership_sakha_affiliation`,
`parichaya_patra`, `anumati_patra`) and from `api/services/family_graph.py` (§2.15) — the first
cross-module and first cross-layer (`routers/` → `services/`) reads in this router. Without this
file, `nss.family_group` and friends would have no HTTP surface at all, and the
"Family First Model" principle — a family exists independently of membership — would have no way
to be demonstrated end-to-end (DB → API → UI) the way Bootstrap/Foundation/Organization/Person
each were for their own tiers.

**Line-by-line**

Lines 1–14 — module docstring:

```python
"""
Family API router — Tier 4 read-only endpoints.

4 GET endpoints across 3 Family tables. No authentication.
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Core:     families (list with filters, detail)
  - Members:  family members (relationships per family)
  - History:  family head history (per family)

Security:
  - Audit actor FKs excluded per API convention
"""
```

Same shape as `person.py`'s docstring (§2.11): endpoint count, table count, the logical endpoint
groups, and a "Security:" note — here just the standard audit-actor-FK exclusion, since Family
carries no Aadhaar-grade sensitive column of its own. This module docstring has not been revised
alongside the code: it still says "4 GET endpoints across 3 Family tables" and lists only the
three original endpoint groups (Core/Members/History), even though the file now implements 7
endpoints across 4 tables plus the 3 new groups documented in §4/§5/§6 below (Graph/Sakha
Alignment/Membership Summary). This is a stale header comment, not a functional issue — every
endpoint below is live and reachable regardless of what the docstring claims.

Lines 16–32:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, row_to_model, rows_to_models
from api.schemas.family import (
    FamilyGraphMemberResponse,
    FamilyGroupResponse,
    FamilyHeadHistoryResponse,
    FamilyMemberResponse,
    FamilySakhaAlignmentResponse,
    MemberSakhaInfo,
    PersonMembershipSummaryResponse,
    SakhaAffiliationCount,
)
from api.services.family_graph import Step, build_family_graph

router = APIRouter(prefix="/api/v1/family", tags=["family"])
```

Imports `row_to_model`/`rows_to_models`/`DEFAULT_LIMIT`/`MAX_LIMIT` from the shared
`api/helpers.py` module — same pattern `person.py` and `organization.py` already follow, not a
locally-redefined pair. The `api.schemas.family` import now pulls in the 4 new response models
(`FamilyGraphMemberResponse`, `FamilySakhaAlignmentResponse`, `MemberSakhaInfo`,
`SakhaAffiliationCount`, `PersonMembershipSummaryResponse`) alongside the 3 original ones — see
§2.14. `from api.services.family_graph import Step, build_family_graph` is this router's only
import from the new `api/services/` layer (§2.15): `build_family_graph` turns raw DB rows into an
in-memory graph, and the `Step` enum is re-used directly in `get_family_graph` (§4 below) to walk
each member's adjacency list. `router = APIRouter(prefix="/api/v1/family", tags=["family"])` gives
Family its own prefix and Swagger tag, parallel to every other tier's router.

**Shared SQL fragments (lines 39–126):**

```python
_FAMILY_SELECT = """
    WITH family_majority AS (
        SELECT fr.family_group_pk,
               aff.organization_pk        AS sakha_pk,
               COUNT(*)                    AS cnt,
               ROW_NUMBER() OVER (
                   PARTITION BY fr.family_group_pk
                   ORDER BY COUNT(*) DESC
               ) AS rn
        FROM   nss.family_relationship fr
        JOIN   nss.sangha_sevi ss
               ON ss.person_pk = fr.person_pk AND ss.is_active = TRUE
        JOIN   nss.membership_sakha_affiliation aff
               ON aff.sangha_sevi_pk = ss.sangha_sevi_pk
              AND aff.effective_to IS NULL
        WHERE  fr.is_current = TRUE
        GROUP BY fr.family_group_pk, aff.organization_pk
    )
    SELECT fg.family_group_pk,
           fg.family_id,
           fg.family_name,
           fg.family_status_master_data_pk,
           st.value_code  AS status_code,
           st.value_name  AS status_name,
           COALESCE(fmj.sakha_pk, fg.sakha_organization_pk)
               AS sakha_organization_pk,
           COALESCE(eo.organization_name, o.organization_name)
               AS sakha_name,
           COALESCE(eo.organization_code, o.organization_code)
               AS sakha_code,
           fg.formed_date,
           fg.remarks,
           fg.is_active
    FROM   nss.family_group fg
    JOIN   nss.master_data st
           ON st.master_data_pk = fg.family_status_master_data_pk
    JOIN   nss.organization o
           ON o.organization_pk = fg.sakha_organization_pk
    LEFT JOIN family_majority fmj
           ON fmj.family_group_pk = fg.family_group_pk AND fmj.rn = 1
    LEFT JOIN nss.organization eo
           ON eo.organization_pk = fmj.sakha_pk
"""
```

`_FAMILY_SELECT` now leads with a `family_majority` CTE that computes, per family, the Sakha with
the most current-member affiliations (`COUNT(*)` per `(family_group_pk, sakha organization_pk)`,
ranked via `ROW_NUMBER() OVER (PARTITION BY fr.family_group_pk ORDER BY COUNT(*) DESC)` so `rn = 1`
is the majority Sakha) — this is FAM-036's "effective Sakha" rule (see §5 below) computed once
here so **every** endpoint built on `_FAMILY_SELECT` (`list_families`, `get_family`, and the Sakha
Alignment endpoint's own family lookup) reports the *effective*, not merely the *registered*,
Sakha. The final `SELECT`'s `sakha_organization_pk`/`sakha_name`/`sakha_code` columns use
`COALESCE(fmj.sakha_pk, fg.sakha_organization_pk)` (and the matching `eo`/`o` aliases for
name/code) so a family with at least one affiliated member reports the majority Sakha, falling
back to the stored `family_group.sakha_organization_pk` registration when no member has an active
affiliation (`fmj` is `NULL` via the `LEFT JOIN`). `st`'s status resolution is unchanged — a plain
`JOIN` against `master_data`, since `family_status_master_data_pk` is `NOT NULL`. This
`family_majority` CTE is **structurally identical** to the one inside `organization.py`'s
`_CHILDREN_STATS_SQL` (§2.9) — the same FAM-036 majority computation is implemented twice,
independently, as already noted from the other side in §2.9/§2.10.

```python
_MEMBER_SELECT = """
    SELECT fr.family_relationship_pk,
           fr.family_group_pk,
           fr.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           fr.relationship_type_master_data_pk,
           rt.value_code  AS relationship_type_code,
           rt.value_name  AS relationship_type_name,
           fr.effective_from,
           fr.effective_to,
           fr.is_current,
           CASE WHEN fhh.family_head_history_pk IS NOT NULL
                THEN TRUE ELSE FALSE
           END AS is_head,
           fr.remarks
    FROM   nss.family_relationship fr
    JOIN   nss.person p
           ON p.person_pk = fr.person_pk
    JOIN   nss.master_data rt
           ON rt.master_data_pk = fr.relationship_type_master_data_pk
    LEFT JOIN nss.family_head_history fhh
           ON fhh.family_group_pk = fr.family_group_pk
          AND fhh.person_pk = fr.person_pk
          AND fhh.effective_to IS NULL
"""
```

`_MEMBER_SELECT` joins `person` (for display name and `person_id`) and `master_data` (for
relationship type, category `RELATIONSHIP_TYPE`) — both plain `JOIN`s, since
`family_relationship.person_pk` and `.relationship_type_master_data_pk` are both `NOT NULL`. It
now also `LEFT JOIN`s `family_head_history fhh` on the same `(family_group_pk, person_pk)` pair
plus `fhh.effective_to IS NULL` (the DDL's own "current head" marker), and derives
`is_head` with a `CASE WHEN fhh.family_head_history_pk IS NOT NULL THEN TRUE ELSE FALSE END` —
so a member row can report whether that person is the family's *current* head without a second
round-trip or client-side cross-referencing against `/head-history`. It's a `LEFT JOIN` (not a
plain `JOIN`) because most members are **not** the head — an inner join would drop every
non-head member row. Notably `_MEMBER_SELECT` still does **not** join anything from Person's
sensitive block (`aadhaar_last4`, emergency contact, etc.) — only `person_id`/`first_name`/
`middle_name`/`last_name` are pulled across, the minimum needed to display a member's name in the
Family UI.

```python
_HEAD_SELECT = """
    SELECT fh.family_head_history_pk,
           fh.family_group_pk,
           fh.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           fh.effective_from,
           fh.effective_to,
           fh.remarks
    FROM   nss.family_head_history fh
    JOIN   nss.person p
           ON p.person_pk = fh.person_pk
"""
```

`_HEAD_SELECT` is the same shape again, one JOIN against `person` for display fields, applied to
`family_head_history` instead of `family_relationship`. All three fragments share the identical
"resolve the person's name, resolve the classification via master_data" pattern already
established by Foundation/Organization/Person's routers — Family introduces no new SQL idiom,
just applies the existing one to three of the module's tables (the fourth, `family_link`, is
queried separately in §4 below via its own two dedicated fragments, since the graph endpoint
needs raw person/edge rows rather than a resolved display row).

**1. FAMILIES — core read (lines 129–187, 2 endpoints):**

Lines 134–168 — `GET /families`:

```python
@router.get("/families", response_model=list[FamilyGroupResponse])
def list_families(
    sakha_code: str | None = Query(
        None, description="Filter by Sakha organization_code (e.g. SKH1)"
    ),
    status_code: str | None = Query(
        None, description="Filter by status value_code"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    conn=Depends(get_connection),
) -> list[FamilyGroupResponse]:
    ...
    sql = _FAMILY_SELECT + " WHERE fg.is_active = TRUE"
    params: list = []

    if sakha_code is not None:
        sql += " AND o.organization_code = %s"
        params.append(sakha_code)
    if status_code is not None:
        sql += " AND st.value_code = %s"
        params.append(status_code)

    sql += " ORDER BY fg.family_name"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return rows_to_models(cur, FamilyGroupResponse)
```

Same `if`-not-`elif` independently-combinable filter pattern as `organization.py`'s
`type_code`/`status_code` and `person.py`'s three filters: `sakha_code` and `status_code` can be
applied together in one request. `limit`/`offset` use the same `Query(DEFAULT_LIMIT, ge=1,
le=MAX_LIMIT, ...)`/`Query(0, ge=0, ...)` pagination contract as `person.py`'s `list_persons` —
out-of-range values 422 before the handler body runs. `ORDER BY fg.family_name` sorts
alphabetically before pagination is applied, giving a stable paginated sequence.

Lines 171–187 — `GET /families/{family_group_pk}`:

```python
@router.get(
    "/families/{family_group_pk}",
    response_model=FamilyGroupResponse,
)
def get_family(
    family_group_pk: UUID,
    conn=Depends(get_connection),
) -> FamilyGroupResponse:
    """Get a single family by PK with resolved context."""
    sql = _FAMILY_SELECT + " WHERE fg.family_group_pk = %s AND fg.is_active = TRUE"

    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk),))
        result = row_to_model(cur, FamilyGroupResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Family not found")
        return result
```

The standard PK-filter-plus-`is_active`/404 detail pattern shared by every detail endpoint in the
codebase (`get_person`, `get_organization`, `get_category`, etc.): filter by PK and
`is_active = TRUE`, parameterize with `(str(family_group_pk),)`, and raise
`HTTPException(status_code=404, detail="Family not found")` if `row_to_model` returns `None`.

**2. FAMILY MEMBERS — relationships (lines 190–223, 1 endpoint):**

```python
@router.get(
    "/families/{family_group_pk}/members",
    response_model=list[FamilyMemberResponse],
)
def list_family_members(
    family_group_pk: UUID,
    conn=Depends(get_connection),
) -> list[FamilyMemberResponse]:
    ...
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.family_group
            WHERE  family_group_pk = %s AND is_active = TRUE
        """, (str(family_group_pk),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Family not found")

    sql = (
        _MEMBER_SELECT
        + " WHERE fr.family_group_pk = %s AND fr.is_current = TRUE"
        + " ORDER BY rt.display_order, p.first_name"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk),))
        return rows_to_models(cur, FamilyMemberResponse)
```

The same two-cursor "verify parent exists, then fetch children" pattern used by
`person.py::list_person_addresses` and `organization.py`'s `/organizations/{pk}/children`: the
first cursor's `SELECT 1 ... WHERE family_group_pk = %s AND is_active = TRUE` distinguishes
"family exists but has zero current members" (empty list, 200) from "family doesn't exist" (404)
— `_MEMBER_SELECT` alone can't tell the two apart. The second cursor filters
`fr.is_current = TRUE` — only the family's **present-day** membership roster is returned, not its
full historical relationship log — and orders by `rt.display_order` (the relationship type's
sort order from `master_data`, e.g. HEAD/FATHER before SON/DAUGHTER) then alphabetically by first
name, so the head/parents surface before children in the UI's members table.

**3. FAMILY HEAD HISTORY (lines 226–259, 1 endpoint):**

```python
@router.get(
    "/families/{family_group_pk}/head-history",
    response_model=list[FamilyHeadHistoryResponse],
)
def list_family_head_history(
    family_group_pk: UUID,
    conn=Depends(get_connection),
) -> list[FamilyHeadHistoryResponse]:
    ...
    sql = (
        _HEAD_SELECT
        + " WHERE fh.family_group_pk = %s"
        + " ORDER BY fh.effective_from DESC"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk),))
        return rows_to_models(cur, FamilyHeadHistoryResponse)
```

Same existence-check-then-fetch shape as the members endpoint above, but the final SELECT has no
`is_current`-style filter at all — `family_head_history` has no such column; instead, the
row with `effective_to IS NULL` (enforced unique per family by the DDL's
`uq_family_head_current` partial index) is understood to be the current head, and
`ORDER BY fh.effective_from DESC` puts it — and every past head — in most-recent-first order,
so a caller can distinguish "current" from "past" purely by checking `effective_to === null` on
the first row, without any special-casing in the SQL itself.

**4. FAMILY GRAPH — dynamic relationship computation (lines 262–374, 1 endpoint):**

Lines 266–289 — the graph's own two SQL fragments:

```python
_GRAPH_PERSONS_SQL = """
    SELECT DISTINCT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           g.value_code AS gender_code
    FROM   nss.family_link fl
    JOIN   nss.person p
           ON p.person_pk IN (fl.person_a_pk, fl.person_b_pk)
    LEFT JOIN nss.master_data g
           ON g.master_data_pk = p.gender_master_data_pk
    WHERE  fl.family_group_pk = %s
      AND  fl.is_current = TRUE
"""

_GRAPH_LINKS_SQL = """
    SELECT fl.person_a_pk,
           fl.person_b_pk,
           fl.link_type
    FROM   nss.family_link fl
    WHERE  fl.family_group_pk = %s
      AND  fl.is_current = TRUE
"""
```

Unlike `_FAMILY_SELECT`/`_MEMBER_SELECT`/`_HEAD_SELECT`, these two fragments deliberately return
**raw** rows, not a UI-ready resolved shape — they're the input contract for
`api/services/family_graph.py`'s `build_family_graph()` (§2.15), which expects plain dicts with
exactly the keys these `SELECT`s produce (`person_pk`/`person_id`/`first_name`/`middle_name`/
`last_name`/`gender_code` for persons; `person_a_pk`/`person_b_pk`/`link_type` for links).
`_GRAPH_PERSONS_SQL` uses `p.person_pk IN (fl.person_a_pk, fl.person_b_pk)` — a person qualifies
if they appear on *either* side of any current `family_link` row in the family — and `DISTINCT`
because the same person can appear across multiple link rows (e.g. as both someone's child and
someone else's spouse). `gender_code` is resolved via a `LEFT JOIN` (not plain `JOIN`) against
`master_data` because `person.gender_master_data_pk` is nullable at the DDL level; a `NULL`
`gender_code` is handled later by `FamilyGraph._path_to_label` (§2.15) defaulting to the male
label form. Both fragments filter `fl.family_group_pk = %s AND fl.is_current = TRUE` — only the
family's present-day edges participate in the graph, mirroring `_MEMBER_SELECT`'s
`fr.is_current = TRUE` filter one section up.

Lines 292–374 — `GET /families/{family_group_pk}/graph`:

```python
@router.get(
    "/families/{family_group_pk}/graph",
    response_model=list[FamilyGraphMemberResponse],
)
def get_family_graph(
    family_group_pk: UUID,
    viewer_person_pk: UUID = Query(
        ..., description="Person PK of the logged-in viewer"
    ),
    conn=Depends(get_connection),
) -> list[FamilyGraphMemberResponse]:
    ...
    # Verify family exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.family_group
            WHERE  family_group_pk = %s AND is_active = TRUE
        """, (str(family_group_pk),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Family not found")

    # Fetch graph data
    with conn.cursor() as cur:
        cur.execute(_GRAPH_PERSONS_SQL, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        person_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute(_GRAPH_LINKS_SQL, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        link_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    if not person_rows or not link_rows:
        return []

    # Build graph and compute
    graph = build_family_graph(person_rows, link_rows)
    computed = graph.compute_relationships(viewer_person_pk)

    # Look up current head
    with conn.cursor() as cur:
        cur.execute("""
            SELECT person_pk FROM nss.family_head_history
            WHERE  family_group_pk = %s AND effective_to IS NULL
        """, (str(family_group_pk),))
        head_row = cur.fetchone()
        head_pk = str(head_row[0]) if head_row else None

    # Build response — include spouse_person_pk and parent_person_pks from graph adjacency
    results = []
    for member in computed:
        member_pk = UUID(member["person_pk"])
        spouse_pk = None
        parent_pks = []
        for neighbor_pk, step in graph.adjacency.get(member_pk, []):
            if step == Step.SPOUSE:
                spouse_pk = neighbor_pk
            elif step == Step.UP:
                parent_pks.append(str(neighbor_pk))

        results.append(FamilyGraphMemberResponse(
            person_pk=member["person_pk"],
            ...
            is_head=(member["person_pk"] == head_pk),
            spouse_person_pk=str(spouse_pk) if spouse_pk else None,
            parent_person_pks=parent_pks,
        ))

    return results
```

`viewer_person_pk: UUID = Query(..., description=...)` — the `...` (Ellipsis) default makes this
a **required** query parameter, unlike every optional `str | None = Query(None, ...)` filter
elsewhere in this router; without a viewer there is nothing to compute relationship labels
relative to. The handler runs in five steps. (1) The same existence-check cursor as §2/§3 above —
404 if the family doesn't exist or is soft-deleted. (2) and (3) Two more cursors run
`_GRAPH_PERSONS_SQL`/`_GRAPH_LINKS_SQL` and hand-roll the "zip column names with row values into a
dict per row" step (`cols = [desc[0] for desc in cur.description]` then
`dict(zip(cols, row))`) — this is the one place in the file that does **not** go through
`row_to_model`/`rows_to_models`, because the output here is raw graph input, not a Pydantic
response row; `if not person_rows or not link_rows: return []` short-circuits to an empty list
(200, not 404) for a family that exists but has no `family_link` rows yet — an existing family
that predates the graph feature or simply has no recorded edges is a valid, empty state, not an
error. (4) `build_family_graph(person_rows, link_rows)` (§2.15) constructs the in-memory graph,
and `graph.compute_relationships(viewer_person_pk)` (§2.15) runs the BFS and returns one dict per
reachable member with a computed `relationship_label`/`generation`. A separate cursor then looks
up the family's current head the same way `list_family_head_history`'s underlying data does
(`family_head_history` row with `effective_to IS NULL`), so the response can flag `is_head`
without re-deriving it from `family_link` edges. (5) The final loop re-derives each member's
`spouse_person_pk`/`parent_person_pks` directly from `graph.adjacency` (not from
`compute_relationships`'s output, which only carries the viewer-relative label/generation/path) —
scanning that member's own adjacency list for a `Step.SPOUSE` neighbor and collecting every
`Step.UP` neighbor (a person can have up to two parents, hence a list not a single field) — and
assembles the `FamilyGraphMemberResponse` (§2.14). Note this endpoint is built directly with
`FamilyGraphMemberResponse(...)` constructor calls, not `rows_to_models`, since its input is a
Python list of dicts assembled in-process rather than a fresh DB cursor.

**5. SAKHA ALIGNMENT — FAM-036 majority rule (lines 377–541, 1 endpoint):**

Lines 382–541 — `GET /families/{family_group_pk}/sakha-alignment`:

```python
@router.get(
    "/families/{family_group_pk}/sakha-alignment",
    response_model=FamilySakhaAlignmentResponse,
)
def get_family_sakha_alignment(
    family_group_pk: UUID,
    conn=Depends(get_connection),
) -> FamilySakhaAlignmentResponse:
    ...
```

This endpoint independently re-derives the same FAM-036 majority-Sakha computation that
`_FAMILY_SELECT`'s `family_majority` CTE already performs in SQL (see the Shared SQL fragments
section above), but in Python, over a wider result set: it needs per-member affiliation detail
(name, code, "is this member's Sakha the family's home Sakha") that a single aggregated CTE
row can't carry. Five steps: (1) Re-run `_FAMILY_SELECT` filtered by PK to get the family's own
`assigned_sakha_*` fields (already the *effective*, majority-or-fallback Sakha, per the CTE) — 404
via `row_to_model` returning `None` if the family doesn't exist. (2) Query every current
`family_relationship` member (`fr.is_current = TRUE`) joined to `person` — a plain hand-rolled
`cols`/`dict(zip(...))` pass again, not `rows_to_models`, because the raw rows feed further
Python-side computation rather than becoming the response directly. If there are zero members
(`if not member_rows`), the endpoint returns a `FamilySakhaAlignmentResponse` early with only the
`assigned_sakha_*` fields populated and every majority/member field left at its Pydantic default
(§2.14) — a family with no current members has nothing to compute a majority over. (3) For every
member found, a single `IN (...)` query against `sangha_sevi`/`membership_sakha_affiliation`/
`organization` (built with a `placeholders = ",".join(["%s"] * len(person_pks))` string, one
round trip instead of N) fetches each member's *current* Sakha affiliation
(`aff.effective_to IS NULL`), keyed into a dict by `str(person_pk)` for O(1) lookup in the next
step. (4) The per-member loop builds a `MemberSakhaInfo` (§2.14) for every member — `has_membership`
is `aff is not None`, `is_home_sakha` compares the member's affiliated Sakha to the *family's*
already-effective `sakha_organization_pk` — and simultaneously accumulates `sakha_counts`, a
`dict[str, dict]` keyed by organization PK that tallies `member_count` per Sakha as it iterates
(the in-Python equivalent of the SQL CTE's `GROUP BY`/`COUNT(*)`). (5) `affiliations = sorted(
sakha_counts.values(), key=lambda x: x["member_count"], reverse=True)` reproduces the CTE's
`ORDER BY COUNT(*) DESC`/`rn = 1` ranking as a plain list sort; `affiliations[0]` (if any) is the
computed majority, assigned to `majority_sakha_*`. `is_aligned = True` is set unconditionally
before this block and **only reassigned inside `if affiliations:`** — meaning `is_aligned` always
ends up comparing the majority Sakha against `family.sakha_organization_pk`, which — because that
field is itself already the CTE's majority-or-fallback value — is definitionally always equal to
`majority_sakha_pk` whenever both exist. This is exactly the "`is_aligned` is hardcoded `True` by
design" behaviour `FamilySakhaAlignmentResponse`'s own docstring (§2.14) calls out: the family's
stored/reported Sakha *is* the majority by construction, so a mismatch at the family level cannot
occur — only `MemberSakhaInfo.is_home_sakha` can ever flag `False` for an individual member.

**6. PERSON MEMBERSHIP SUMMARY — person-to-membership bridge (lines 544–653, 1 endpoint):**

Lines 549–653 — `GET /person/{person_pk}/membership-summary`:

```python
@router.get(
    "/person/{person_pk}/membership-summary",
    response_model=PersonMembershipSummaryResponse,
)
def get_person_membership_summary(
    person_pk: UUID,
    conn=Depends(get_connection),
) -> PersonMembershipSummaryResponse:
    ...
    if not row:
        return PersonMembershipSummaryResponse()
    ...
```

This is the router's only endpoint under the `/api/v1/family/person/...` path (every other
endpoint is `/api/v1/family/families/...`) — it belongs to Family because it's consumed by the
Family tree UI's Selected Person panel, even though its data lives entirely in Tier 4 Membership
tables (`sangha_sevi`, `membership_sakha_affiliation`, `parichaya_patra`, `anumati_patra`), none of
which are Family-module tables. It bridges the two identity spaces the docstring for
`api/schemas/family.py`'s `PersonMembershipSummaryResponse` (§2.14) describes: `person_pk` (the
Family/Person identity) to `sangha_sevi_pk` (the Membership identity) — a person can exist in a
family with no membership at all, consistent with the "Person ≠ Member" project-wide principle.
Four steps: (1) Look up `sangha_sevi` by `ss.person_pk = %s AND ss.is_active = TRUE`, joined to
`master_data` twice (membership type, membership status) and `organization`, with a `LEFT JOIN`
to `membership_sakha_affiliation` (`aff.effective_to IS NULL`) for the current Sakha — `LIMIT 1`
since a person has at most one active `sangha_sevi` row (one-person-one-membership). If `row` is
falsy — no matching `sangha_sevi` at all — the function returns `PersonMembershipSummaryResponse()`
with every field at its `None`/default, and **explicitly not a 404**: the docstring and the
"Returns empty fields (not 404) if the person has no membership record" note make this a
deliberate contract choice, since "this person has a family record but no membership" is an
expected, valid state, not an error condition. (2) If a `sangha_sevi` row was found, a second
query fetches the most recent `parichaya_patra` (`ORDER BY pp.valid_from DESC LIMIT 1`) — the
latest Parichaya Patra regardless of its `status`, i.e. even an expired/superseded one is
returned if it's the most recent by `valid_from`. (3) A third query does the same for
`anumati_patra`, but **only if** `member["membership_type_code"] != "ASSOCIATE"` — a direct
reflection of MBR-019A/B (per this function's own docstring): Associate members are not eligible
for an Anumati Patra, so the query is skipped entirely for them rather than running and finding no
rows. (4) The final `PersonMembershipSummaryResponse(...)` construction assembles all three
lookups' results into one flat response — again a direct constructor call rather than
`row_to_model`, since the values are drawn from three separate cursors merged in Python, not from
a single result row.

---

### 2.14 `api/schemas/family.py`

**Requirement**

`api/routers/family.py` needs eight typed response models — one per resolved query/computation
shape across its 7 endpoints (`_FAMILY_SELECT`, `_MEMBER_SELECT`, `_HEAD_SELECT`, the graph
endpoint's per-member result, the Sakha Alignment endpoint's family/per-member/per-Sakha-count
shapes, and the Person Membership Summary bridge) — so FastAPI can validate, serialize, and
document (via `/docs`) exactly what each endpoint returns, and so audit columns
(`created_at`/`updated_at`/`deleted_at`/`*_by_sangha_sevi_pk`) are structurally excluded from every
response the same way they are for every other tier.

**Line-by-line**

Lines 1–14 — module docstring:

```python
"""
Pydantic response models for the Family API (Tier 4).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""
```

Same "raw dicts, no ORM, no `ConfigDict(from_attributes=True)`" note carried forward verbatim
from Organization's and Person's schema modules — a reminder that `row_to_model`/`rows_to_models`
(in `api/helpers.py`) construct these models from plain dict rows returned by psycopg2's
`RealDictCursor`-style access, not from mapped ORM instances.

```python
class FamilyGroupResponse(BaseModel):
    family_group_pk: UUID
    family_id: str
    family_name: str

    family_status_master_data_pk: UUID
    status_code: str
    status_name: str

    sakha_organization_pk: UUID
    sakha_name: str
    sakha_code: str | None

    formed_date: date | None
    remarks: str | None
    is_active: bool
```

Maps onto `_FAMILY_SELECT`. `status_code`/`status_name` and `sakha_name` are plain `str` (not
`| None`) — matching the router's plain `JOIN`s against `master_data` and `organization`, both of
which are `NOT NULL` FKs on `family_group`. `sakha_code` is `str | None` even though
`organization_code` is resolved via the same non-nullable join — reflecting that `organization
.organization_code` itself is nullable at the DDL level for some organization types (per
`database/ddl/02_organization/README.md`'s note that `organization_id`/codes aren't universally
populated), not a gap in the join. `family_id` is a plain `str`, following the project-wide
unpadded business-ID convention (`F1`, not `F00000001`).

```python
class FamilyMemberResponse(BaseModel):
    family_relationship_pk: UUID
    family_group_pk: UUID

    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None

    relationship_type_master_data_pk: UUID
    relationship_type_code: str
    relationship_type_name: str

    effective_from: date
    effective_to: date | None
    is_current: bool
    is_head: bool
    remarks: str | None
```

Maps onto `_MEMBER_SELECT`. `middle_name`/`last_name` are `str | None` (Person's own nullable
columns), while `relationship_type_code`/`relationship_type_name` are non-nullable `str` — the
router's plain `JOIN` against `master_data` for relationship type guarantees a match, since
`family_relationship.relationship_type_master_data_pk` is `NOT NULL`. `effective_to` is
`date | None`: `None` for a current relationship (`is_current = True`), populated once the
relationship ends — mirroring the DDL's `chk_family_rel_current_consistency` CHECK constraint one
layer up in the schema. `is_head: bool` (not `| None`) is the model-side counterpart of
`_MEMBER_SELECT`'s `CASE WHEN fhh.family_head_history_pk IS NOT NULL THEN TRUE ELSE FALSE END` —
the SQL's `CASE`/`ELSE FALSE` already guarantees a non-null boolean for every row, so the field
carries no `| None`.

```python
class FamilyHeadHistoryResponse(BaseModel):
    family_head_history_pk: UUID
    family_group_pk: UUID

    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None

    effective_from: date
    effective_to: date | None
    remarks: str | None
```

Maps onto `_HEAD_SELECT`. Structurally almost identical to `FamilyMemberResponse` minus the
relationship-type fields and `is_current` (this table has no such column — see §2.13's note on
how "current head" is derived from `effective_to IS NULL` rather than a boolean flag). The
absence of an `is_current` field here, present on `FamilyMemberResponse`, is a direct
one-to-one reflection of the two underlying tables' different DDL shapes, not an inconsistency.

```python
class FamilyGraphMemberResponse(BaseModel):
    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    gender_code: str | None
    relationship_label: str
    generation: int
    is_head: bool
    spouse_person_pk: UUID | None = None
    parent_person_pks: list[str] = []
```

Backs `GET /families/{family_group_pk}/graph` (§2.13 §4). `relationship_label` and `generation`
are the two fields `FamilyGraph.compute_relationships` (§2.15) computes via BFS — everything else
is either passed through from the person row (`person_id`/name fields/`gender_code`, the latter
`str | None` since `person.gender_master_data_pk` is nullable) or re-derived from graph adjacency
in the router (`is_head`, `spouse_person_pk`, `parent_person_pks`). `spouse_person_pk: UUID | None
= None` and `parent_person_pks: list[str] = []` both carry defaults because a member without a
recorded spouse/parent edge in `family_link` simply omits them, rather than the router needing to
special-case the response construction. `parent_person_pks` is `list[str]`, not `list[UUID]` —
the router builds it by appending `str(neighbor_pk)` for each `Step.UP` neighbor (§2.13), so the
model's field type matches what's actually assembled rather than requiring an extra per-item
`UUID` coercion at construction time.

```python
class PersonMembershipSummaryResponse(BaseModel):
    sangha_sevi_id: str | None = None
    sangha_sevi_pk: UUID | None = None
    membership_type_code: str | None = None
    membership_type_name: str | None = None
    status_code: str | None = None
    status_name: str | None = None
    organization_name: str | None = None
    local_sakha_erp_id: str | None = None
    parichaya_patra_number: str | None = None
    parichaya_patra_status: str | None = None
    parichaya_patra_valid_to: date | None = None
    anumati_patra_number: str | None = None
    anumati_patra_status: str | None = None
    anumati_patra_valid_to: date | None = None
```

Backs `GET /person/{person_pk}/membership-summary` (§2.13 §6). **Every** field is `| None` with a
default — an unusually all-optional shape compared to every other response model in this file —
because the model has to represent three genuinely different "nothing found" states with the same
type: (1) the person has no `sangha_sevi` row at all (the router returns
`PersonMembershipSummaryResponse()` with every field at its default), (2) they have a
`sangha_sevi` but no Parichaya Patra yet (`parichaya_patra_*` fields stay `None`), and (3) they're
an `ASSOCIATE` member, for whom the router skips the Anumati Patra query entirely per MBR-019A/B
(`anumati_patra_*` fields stay `None`). Modeling this as one flat, all-optional shape — rather
than three response models or a nested optional sub-object — matches the router's own "bridge,
don't 404" contract: the caller always gets a `200` with a `PersonMembershipSummaryResponse`
shape, and reads presence/absence off individual fields.

```python
class SakhaAffiliationCount(BaseModel):
    organization_pk: UUID
    organization_name: str
    organization_code: str
    member_count: int


class MemberSakhaInfo(BaseModel):
    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    affiliated_sakha_pk: UUID | None = None
    affiliated_sakha_name: str | None = None
    affiliated_sakha_code: str | None = None
    is_home_sakha: bool | None = None      # matches family's effective (majority) Sakha?
    has_membership: bool = False


class FamilySakhaAlignmentResponse(BaseModel):
    family_group_pk: UUID
    family_name: str

    assigned_sakha_pk: UUID
    assigned_sakha_name: str
    assigned_sakha_code: str

    majority_sakha_pk: UUID | None = None
    majority_sakha_name: str | None = None
    majority_sakha_code: str | None = None

    is_aligned: bool = True   # always True — family follows majority
    total_members: int = 0
    members_with_affiliation: int = 0

    affiliations: list[SakhaAffiliationCount] = []
    members: list[MemberSakhaInfo] = []
```

These three models together back `GET /families/{family_group_pk}/sakha-alignment` (§2.13 §5).
`SakhaAffiliationCount` is the per-Sakha tally (one row per distinct Sakha found among the
family's members, `member_count` matching the router's `sakha_counts` dict). `MemberSakhaInfo` is
the per-member detail row — `affiliated_sakha_*` and `is_home_sakha` are all `| None` because a
member with no active `sangha_sevi`/affiliation contributes nothing to compare (`has_membership`
distinguishes "no membership" from "membership but no affiliation record" at a glance).
`FamilySakhaAlignmentResponse` is the envelope: `assigned_sakha_*` fields are non-nullable
`UUID`/`str` (the family always has *some* effective Sakha, per `_FAMILY_SELECT`'s CTE fallback),
while `majority_sakha_*` stay `| None` for the zero-members early-return case. Its own docstring
(reproduced in the source) states plainly that **`is_aligned` is hardcoded to `True` by design**
— "the family follows the majority automatically" — with `MemberSakhaInfo.is_home_sakha` left as
the only field that can actually flag an individual mismatch; see §2.13 §5 for why the router-side
computation can never actually set `is_aligned = False`.

---

### 2.15 `api/services/family_graph.py`

**Requirement**

`api/routers/family.py`'s graph endpoint (§2.13 §4) needs to turn a flat table of direct
`family_link` edges (`PARENT_OF`/`SPOUSE_OF`) into every *extended* kinship label a viewer would
recognize (Grandfather, Sister-in-Law, Cousin, ...) without storing a single one of those labels
in the database. Per the "History Never Deleted"/"Master Data Driven" principles this project
already applies elsewhere, storing a denormalized `relationship_type` for every possible pair of
family members would mean re-deriving and rewriting O(n²) rows every time a marriage, birth, or
change of Family Head occurs. This file is the first source file under a brand-new `api/services/`
directory (see this document's Purpose section) — a layer for framework-agnostic business logic
(pure Python graph construction and BFS traversal, no FastAPI/psycopg2 imports at all) that a
router calls into, sitting between `api/routers/` (HTTP + SQL) and `api/schemas/` (response
shape). Without this file, `family.py`'s graph endpoint would have no way to compute a
relationship label at all — the DDL comment atop `05_family_link.sql` itself states the design
intent this module implements: "All extended relationships ... are computed dynamically via
graph traversal relative to the viewer."

**Line-by-line**

Lines 1–24 — module docstring:

```python
"""
Family Graph — dynamic relationship computation.

Builds an in-memory graph from ``nss.family_link`` rows and computes
relationship labels relative to any viewer via BFS traversal.

Edge types stored in the DB:
    PARENT_OF  — person_a is parent of person_b (directed)
    SPOUSE_OF  — person_a and person_b are spouses (bidirectional)

Traversal step types (internal):
    UP      — move to a parent   (reverse of PARENT_OF)
    DOWN    — move to a child    (forward  PARENT_OF)
    SPOUSE  — move to a spouse   (either direction of SPOUSE_OF)

The path from viewer → target is a tuple of step types.  A lookup table
maps each path pattern to a gendered relationship label pair
(male_label, female_label).  The target person's gender_code selects
which label to use.

Design decision:  Only direct edges are stored.  Every other kinship
term is derived.  When the Family Head changes, zero data re-entry
is required — the graph is the same, only the viewer changes.
"""
```

States the module's whole design up front: two DB-level edge types (`PARENT_OF`/`SPOUSE_OF`)
expand into three traversal-level step types (`UP`/`DOWN`/`SPOUSE`), a path is a tuple of those
steps, and a lookup table maps path-shape → gendered label pair. The closing "Design decision"
paragraph is the module's own restatement of why `family_link` (§2.13/DDL) stores only direct
edges: changing who the Family Head is (i.e. who the viewer is) requires zero data migration,
since the same stored graph simply gets walked from a different starting node.

Lines 37–40 — the `Step` enum:

```python
class Step(Enum):
    UP = "UP"          # to parent
    DOWN = "DOWN"      # to child
    SPOUSE = "SPOUSE"  # to spouse
```

The three traversal primitives named in the docstring, as a proper `Enum` (not bare strings) so
`FamilyGraph.adjacency`'s step values are type-checked and so `family.py`'s router (§2.13 §4) can
import `Step` and compare `step == Step.SPOUSE`/`step == Step.UP` directly rather than matching
on string literals.

Lines 47–149 — `PATH_LABELS`, the path → label lookup table:

```python
PATH_LABELS: dict[tuple[Step, ...], tuple[str, str]] = {
    (Step.SPOUSE,): ("Husband", "Wife"),
    (Step.UP, Step.DOWN): ("Brother", "Sister"),
    (Step.UP,): ("Father", "Mother"),
    (Step.UP, Step.UP): ("Grandfather", "Grandmother"),
    (Step.DOWN,): ("Son", "Daughter"),
    (Step.DOWN, Step.DOWN): ("Grandson", "Granddaughter"),
    (Step.UP, Step.UP, Step.DOWN): ("Uncle", "Aunt"),
    (Step.UP, Step.DOWN, Step.DOWN): ("Nephew", "Niece"),
    (Step.UP, Step.UP, Step.DOWN, Step.DOWN): ("Cousin", "Cousin"),
    (Step.UP, Step.UP, Step.UP): ("Great-Grandfather", "Great-Grandmother"),
    (Step.DOWN, Step.DOWN, Step.DOWN): ("Great-Grandson", "Great-Granddaughter"),
    # ... 27 entries total, grouped by generation with a comment header per group
}
```

A `dict` keyed by an exact tuple of `Step` values (the shortest BFS path from viewer to target),
valued as `(male_label, female_label)`. 27 entries total, organized by the module's own comment
headers into Generation 0 (spouse, siblings, siblings'-spouses), Generation −1/−2 (parents,
parents-in-law, step-parents, grandparents), Generation +1/+2 (children, step-children,
children-in-law, grandchildren), and "Extended family" (uncle/aunt, nephew/niece, cousin,
great-grandparent/child, grandchild-in-law, grand-nephew/niece). In-law and step-relation entries
are their own explicit dict keys (e.g. `(Step.SPOUSE, Step.UP): ("Father-in-Law",
"Mother-in-Law")` vs. `(Step.UP, Step.SPOUSE): ("Step-Father", "Step-Mother")`) rather than being
derived by a rule — the exact sequence of `UP`/`DOWN`/`SPOUSE` steps, not just which steps appear,
determines the label. Any path shape not present as a key (an exact-match `dict.get`, not a
pattern match) falls through to `"Relative"` in `_path_to_label` below — the table is intentionally
finite; very distant or unusual paths (e.g. great-great-grandparent) are not modeled and degrade
to a generic label rather than raising.

Lines 154–176 — `PersonNode` and the `FamilyGraph` dataclass shell:

```python
@dataclass
class PersonNode:
    """Minimal person info needed for graph traversal."""
    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: Optional[str]
    last_name: Optional[str]
    gender_code: Optional[str]  # MALE / FEMALE


@dataclass
class FamilyGraph:
    persons: dict[UUID, PersonNode] = field(default_factory=dict)
    adjacency: dict[UUID, list[tuple[UUID, Step]]] = field(default_factory=dict)
```

`PersonNode` is a plain display-data carrier (no graph logic) — a typed counterpart to the raw
dicts `_GRAPH_PERSONS_SQL` (§2.13 §4) returns. `FamilyGraph.adjacency` is the graph itself: a
`dict` from a person's PK to a list of `(neighbor_pk, Step)` pairs — an adjacency-list
representation, not a matrix, appropriate since a family graph is sparse (each person has at most
a handful of parents/children/spouses, never a connection to every other member).

Lines 175–194 — `add_person`/`add_link`:

```python
def add_person(self, node: PersonNode) -> None:
    self.persons[node.person_pk] = node
    if node.person_pk not in self.adjacency:
        self.adjacency[node.person_pk] = []

def add_link(self, person_a_pk: UUID, person_b_pk: UUID, link_type: str) -> None:
    """Add a directed link and its reverse."""
    if person_a_pk not in self.adjacency:
        self.adjacency[person_a_pk] = []
    if person_b_pk not in self.adjacency:
        self.adjacency[person_b_pk] = []

    if link_type == "PARENT_OF":
        self.adjacency[person_a_pk].append((person_b_pk, Step.DOWN))
        self.adjacency[person_b_pk].append((person_a_pk, Step.UP))
    elif link_type == "SPOUSE_OF":
        self.adjacency[person_a_pk].append((person_b_pk, Step.SPOUSE))
        self.adjacency[person_b_pk].append((person_a_pk, Step.SPOUSE))
```

This is where the DB's two directed/bidirectional edge semantics become a symmetric adjacency
list: a single `PARENT_OF` row from A to B is stored as **two** adjacency entries — `DOWN` from
A's list (A → B, A is the parent) and `UP` from B's list (B → A, B is the child) — so BFS can walk
the graph in either direction from any starting viewer. `SPOUSE_OF` similarly becomes two
`SPOUSE`-tagged entries, one on each side, since a spouse relationship has no direction. Both
methods guard `if pk not in self.adjacency: self.adjacency[pk] = []` before appending, defending
against a link row referencing a person not yet added via `add_person` (defensive, though
`build_family_graph`'s row shapes make this unlikely in practice since `_GRAPH_PERSONS_SQL`
already selects every person appearing in any `family_link` row for the family).

Lines 196–258 — `compute_relationships`, the BFS:

```python
def compute_relationships(
    self,
    viewer_pk: UUID,
    max_depth: int = 6,
) -> list[dict]:
    if viewer_pk not in self.adjacency:
        return []

    visited: dict[UUID, tuple[Step, ...]] = {viewer_pk: ()}
    queue: deque[UUID] = deque([viewer_pk])

    while queue:
        current = queue.popleft()
        current_path = visited[current]

        if len(current_path) >= max_depth:
            continue

        for neighbor_pk, step in self.adjacency[current]:
            if neighbor_pk in visited:
                continue
            new_path = current_path + (step,)
            visited[neighbor_pk] = new_path
            queue.append(neighbor_pk)

    results: list[dict] = []
    for person_pk, path in visited.items():
        if person_pk == viewer_pk:
            continue

        person = self.persons.get(person_pk)
        if person is None:
            continue

        label = self._path_to_label(path, person.gender_code)
        generation = self._path_to_generation(path)

        results.append({
            "person_pk": str(person.person_pk),
            ...
            "relationship_label": label,
            "generation": generation,
            "path": [s.value for s in path],
        })

    results.sort(key=lambda r: (r["generation"], r["first_name"] or ""))
    return results
```

Standard BFS with a `deque`, tracking the **shortest path** (as a tuple of `Step`s, not a
distance count) to each newly-discovered node in `visited`. `if viewer_pk not in self.adjacency:
return []` — a viewer with zero recorded links (an isolated family member, or a bad PK) has no
computable relationships; this is a graceful empty result, not an error, matching the router's
own `if not person_rows or not link_rows: return []` short-circuit one layer up (§2.13 §4).
`max_depth: int = 6` caps how many steps BFS will extend a path (`if len(current_path) >=
max_depth: continue` skips expanding further from that node, though already-visited neighbors
within depth are still recorded) — a safety net against runaway traversal in a malformed or
unusually large/cyclic graph, not expected to bind in a real family. BFS naturally finds the
*shortest* path first because it explores level-by-level and `if neighbor_pk in visited: continue`
never overwrites a path once set — so if a person is reachable both as a "sibling" (2 steps) and,
via a longer route, as something else, the 2-step path wins, matching real-world kinship
convention (the closest relationship label is the correct one). The results loop skips the viewer
themself (`if person_pk == viewer_pk: continue`) and any `person_pk` in `visited` that has no
matching `PersonNode` (a defensive `person is None` guard — shouldn't occur given
`build_family_graph`'s inputs, but avoids a `KeyError`-shaped crash if it ever did), then computes
`relationship_label`/`generation` per node and sorts the final list by `(generation, first_name)`
— older generations (negative `generation`, e.g. parents/grandparents) sort before the viewer's
own generation, which sorts before descendants, and ties within a generation sort alphabetically.

Lines 260–290 — `_path_to_label`/`_path_to_generation`:

```python
@staticmethod
def _path_to_label(path: tuple[Step, ...], gender_code: Optional[str]) -> str:
    labels = PATH_LABELS.get(path)
    if labels is None:
        return "Relative"

    male_label, female_label = labels
    if gender_code == "MALE":
        return male_label
    elif gender_code == "FEMALE":
        return female_label
    else:
        return male_label  # Unknown gender — return male form (conventional default)

@staticmethod
def _path_to_generation(path: tuple[Step, ...]) -> int:
    gen = 0
    for step in path:
        if step == Step.UP:
            gen -= 1
        elif step == Step.DOWN:
            gen += 1
        # SPOUSE: no generation change
    return gen
```

`_path_to_label` is a direct `PATH_LABELS.get(path)` lookup (exact tuple match, per the note
above) with a `"Relative"` fallback for any unmodeled path shape, then picks the gendered label
form; an unknown/`None` `gender_code` (nullable at the DDL level, per §2.13 §4's note on
`_GRAPH_PERSONS_SQL`'s `LEFT JOIN`) falls back to the male label form as a documented, explicit
convention rather than an accidental default. `_path_to_generation` reduces a path to a single
signed integer purely from `UP`/`DOWN` counts (`SPOUSE` steps contribute 0) — this is what the
router's/UI's "sort/group by generation" behaviour is built on (§2.13 §4's BFS results sort by
this exact value).

Lines 295–327 — `build_family_graph`, the DB-rows-to-graph constructor:

```python
def build_family_graph(
    person_rows: list[dict],
    link_rows: list[dict],
) -> FamilyGraph:
    graph = FamilyGraph()

    for row in person_rows:
        node = PersonNode(
            person_pk=UUID(str(row["person_pk"])),
            person_id=row["person_id"],
            first_name=row["first_name"],
            middle_name=row.get("middle_name"),
            last_name=row.get("last_name"),
            gender_code=row.get("gender_code"),
        )
        graph.add_person(node)

    for row in link_rows:
        graph.add_link(
            person_a_pk=UUID(str(row["person_a_pk"])),
            person_b_pk=UUID(str(row["person_b_pk"])),
            link_type=row["link_type"],
        )

    return graph
```

The module-level entry point `family.py`'s router (§2.13 §4) actually calls. Takes exactly the two
raw-dict row lists `_GRAPH_PERSONS_SQL`/`_GRAPH_LINKS_SQL` produce, wraps every PK with
`UUID(str(row[...]))` (defensive against psycopg2 returning either a `str` or an already-typed
`UUID` depending on column/driver configuration — `str()` first makes the `UUID(...)` call
uniform either way), and calls `add_person`/`add_link` in a fixed order — every person is added
before any link is processed, so `add_link`'s "person not yet in adjacency" guard (see above) is
belt-and-suspenders rather than the common path. Returns the fully-built `FamilyGraph`, ready for
`compute_relationships`.

---

### 2.16 `api/routers/membership.py`

**Requirement**

Tier 4 Membership exposes 7 read-only GET endpoints across 5 tables (`sangha_sevi`,
`membership_sakha_affiliation`, `parichaya_patra`, `anumati_patra`,
`membership_journey_event`) — the largest router in the API layer by table count. Its defining
constraint is the **three-tier member identity model**: a Sangha Sevi ID (permanent, NSS-wide),
a Local Sakha ERP Number / "Sakha Sangha ID" (Sakha-scoped, changes on transfer), and a Kendra
Number (annual, printed on the Parichaya Patra) live on three different tables, so almost every
endpoint has to reach across a JOIN or a sub-resource fetch to assemble a complete picture of "who
this member is" rather than reading one row off `sangha_sevi` alone. Without this file,
`nss.sangha_sevi` and its four dependent tables would have no HTTP surface, and the module's
central non-obvious design decision (identity split across three tables, not three columns on one
table) would have no place where a consumer could actually observe it.

**Line-by-line**

Lines 1–23 — module docstring:

```python
"""
Membership API router — Tier 4 read-only endpoints.

7 GET endpoints across 5 Membership tables. No authentication.
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Core:          members (list with filters, detail)
  - Search:        trigram + prefix across all 3 identity tiers + name
  - Affiliations:  sakha affiliation history (per member)
  - Credentials:   parichaya patra, anumati patra (per member)
  - Timeline:      journey events (per member)

Three-tier identity model:
  - Sangha Sevi ID (SS1) — permanent NSS-wide (sangha_sevi)
  - ERP Number / Local Sakha Number (ESS1192) — Sakha-scoped,
    auto-generated (membership_sakha_affiliation)
  - Kendra Number (345/2026/2027) — annual per FY
    (parichaya_patra.document_number)

Security:
  - Audit actor FKs excluded per API convention
"""
```

States "7 GET endpoints across 5 Membership tables," lists five endpoint groups (one more than
Person's three — Affiliations, Credentials, and Timeline are each their own group, reflecting
the module's larger table count), and spells out the three-tier identity model with concrete
examples (`SS1`, `ESS1192`, `345/2026/2027`) and which table each tier lives on — the same three
lines repeated verbatim in `api/schemas/membership.py`, `tests/test_membership.py`, and
`API_CONTRACT.md` §8, so a reader who lands on any one of the four files gets the identical
mental model.

Lines 25–40:

```python
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, row_to_model, rows_to_models
from api.schemas.membership import (
    AnumatiPatraResponse,
    JourneyEventResponse,
    MemberResponse,
    ParichayaPatraResponse,
    SakhaAffiliationResponse,
)

router = APIRouter(prefix="/api/v1/membership", tags=["membership"])
```

Same shared-helper pattern as `organization.py`/`person.py`/`family.py` (`row_to_model`/
`rows_to_models`/`DEFAULT_LIMIT`/`MAX_LIMIT` from `api/helpers.py`, not redefined locally). The
one new import is `re` (Python's standard-library regex module) — used exactly once, in
`search_members`, to split an email-like query string. `router = APIRouter(prefix=
"/api/v1/membership", tags=["membership"])` gives this module its own prefix and Swagger tag,
same as every other tier.

**Shared SQL fragment (lines 43–84):**

```python
_MEMBER_SELECT = """
    SELECT ss.sangha_sevi_pk,
           ss.sangha_sevi_id,
           ss.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           p.country_phone_code,
           p.mobile_number,
           p.email,
           ss.membership_type_master_data_pk,
           mt.value_code  AS membership_type_code,
           mt.value_name  AS membership_type_name,
           ss.membership_status_master_data_pk,
           ms.value_code  AS status_code,
           ms.value_name  AS status_name,
           ss.organization_pk,
           o.organization_name,
           o.organization_code,
           aff.local_sakha_erp_id,
           ss.joining_date,
           ss.renewal_due_date,
           ss.remarks,
           ss.is_active
    FROM   nss.sangha_sevi ss
    JOIN   nss.person p
           ON p.person_pk = ss.person_pk
    JOIN   nss.master_data mt
           ON mt.master_data_pk = ss.membership_type_master_data_pk
    JOIN   nss.master_data ms
           ON ms.master_data_pk = ss.membership_status_master_data_pk
    JOIN   nss.organization o
           ON o.organization_pk = ss.organization_pk
    LEFT JOIN nss.membership_sakha_affiliation aff
           ON aff.sangha_sevi_pk = ss.sangha_sevi_pk
          AND aff.effective_to IS NULL
"""
```

`_MEMBER_SELECT` is the single SQL fragment reused by all three "core" endpoints
(`list_members`, `get_member`, `search_members`) — the same one-fragment-many-callers pattern as
`organization.py`'s `_ORG_SELECT`. Five JOINs resolve the full picture: `p` (person — name,
contact), `mt`/`ms` (two separate aliases into the *same* `nss.master_data` table, for
membership type and status respectively — the same "one physical table, multiple semantic
roles via aliasing" pattern used throughout the Foundation-derived master-data design), `o`
(current organization/Sakha), and — the one JOIN unique to this fragment —
`LEFT JOIN nss.membership_sakha_affiliation aff ON aff.sangha_sevi_pk = ss.sangha_sevi_pk AND
aff.effective_to IS NULL`. That `effective_to IS NULL` condition *inside* the JOIN (not in a
later `WHERE`) is what selects specifically the member's **currently active** affiliation row —
the one the partial unique index `uq_mem_sakha_aff_active` guarantees is unique per member — and
it must be a `LEFT JOIN`, not a plain `JOIN`, because a member can theoretically have zero active
affiliations (e.g. mid-transfer, between closing the old row and opening the new one), in which
case `aff.local_sakha_erp_id` simply resolves to `NULL` rather than dropping the member from the
result set entirely. The four core JOINs (`p`, `mt`, `ms`, `o`) are all plain `JOIN`s because
their corresponding FK columns on `sangha_sevi` are all `NOT NULL`.

**1. MEMBERS — core read (lines 92–152, 2 endpoints):**

```python
@router.get("/members", response_model=list[MemberResponse])
def list_members(
    type_code: str | None = Query(
        None, description="Filter by membership type (REGULAR, PROBATIONARY, etc.)"
    ),
    status_code: str | None = Query(
        None, description="Filter by status value_code"
    ),
    org_code: str | None = Query(
        None, description="Filter by organization_code (e.g. SKH1)"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    conn=Depends(get_connection),
) -> list[MemberResponse]:
    sql = _MEMBER_SELECT + " WHERE ss.is_active = TRUE"
    params: list = []

    if type_code is not None:
        sql += " AND mt.value_code = %s"
        params.append(type_code)
    if status_code is not None:
        sql += " AND ms.value_code = %s"
        params.append(status_code)
    if org_code is not None:
        sql += " AND o.organization_code = %s"
        params.append(org_code)

    sql += " ORDER BY p.first_name, p.last_name"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return rows_to_models(cur, MemberResponse)
```

Three independent, `AND`-composable filters (`type_code` against `mt.value_code`, `status_code`
against `ms.value_code`, `org_code` against `o.organization_code` — note `org_code` filters on
the resolved organization's business code, not a raw FK), the same `if`-not-`elif` pattern as
every other filterable list endpoint, plus the standard `limit`/`offset` pagination
(`DEFAULT_LIMIT`/`MAX_LIMIT` shared from `api/helpers.py`) appended last, after `ORDER BY`. `GET
/members/{sangha_sevi_pk}` (lines 136–152) is the standard PK-filter-plus-`is_active`/404 detail
pattern (`_MEMBER_SELECT + " WHERE ss.sangha_sevi_pk = %s AND ss.is_active = TRUE"`,
`row_to_model`, `HTTPException(404, "Member not found")` if `None`) seen in every other tier's
detail endpoint.

**2. SEARCH (lines 160–223, 1 endpoint):**

```python
@router.get("/search", response_model=list[MemberResponse])
def search_members(
    q: str = Query(
        ...,
        min_length=2,
        max_length=100,
        description="Search term — matches against Sangha Sevi ID (prefix), "
        "Person ID (prefix), ERP Number (prefix), name (trigram), "
        "mobile number (prefix), email (prefix), "
        "or Kendra Number (prefix)",
    ),
    conn=Depends(get_connection),
) -> list[MemberResponse]:
    # For trigram: strip email-like suffix so "aniket.mishra" → "aniket"
    name_q = re.split(r'[.@]', q)[0] if ('.' in q or '@' in q) else q

    sql = (
        _MEMBER_SELECT
        + """
        WHERE ss.is_active = TRUE
          AND (
              ss.sangha_sevi_id ILIKE %s
              OR p.person_id ILIKE %s
              OR aff.local_sakha_erp_id ILIKE %s
              OR similarity(p.first_name, %s) > 0.45
              OR similarity(p.last_name, %s) > 0.45
              OR p.mobile_number ILIKE %s
              OR p.email ILIKE %s
              OR EXISTS (
                  SELECT 1 FROM nss.parichaya_patra pp
                  WHERE  pp.sangha_sevi_pk = ss.sangha_sevi_pk
                    AND  pp.document_number ILIKE %s
              )
          )
        ORDER BY similarity(p.first_name, %s) DESC,
                 p.first_name, p.last_name
        LIMIT 50
    """
    )

    prefix_pattern = f"{q}%"

    with conn.cursor() as cur:
        cur.execute(sql, (
            prefix_pattern, prefix_pattern, prefix_pattern,
            name_q, name_q,
            prefix_pattern, prefix_pattern, prefix_pattern,
            name_q,
        ))
        return rows_to_models(cur, MemberResponse)
```

The most elaborate WHERE clause in the API layer — seven OR-ed match strategies covering all
three identity tiers plus name/mobile/email. `ss.sangha_sevi_id ILIKE %s` (Tier 1 prefix),
`aff.local_sakha_erp_id ILIKE %s` (Tier 2 prefix, against the same active-affiliation alias
`_MEMBER_SELECT` already joins), and the `EXISTS (SELECT 1 FROM nss.parichaya_patra pp WHERE
pp.sangha_sevi_pk = ss.sangha_sevi_pk AND pp.document_number ILIKE %s)` subquery (Tier 3 prefix)
are the three tier-specific paths; `p.person_id ILIKE %s`, `p.mobile_number ILIKE %s`, `p.email
ILIKE %s` are prefix matches on identifying/contact fields (identical rationale to
`person.py::search_persons`); `similarity(p.first_name, %s) > 0.45` / `similarity(p.last_name,
%s) > 0.45` are explicit `similarity()` function calls with a **named threshold** (`0.45`) —
unlike `person.py`'s bare `%%` trigram operator, which relies on PostgreSQL's session-level
`pg_trgm.similarity_threshold` (default `0.3`); Membership's search hardcodes a higher bar in the
query itself, independent of that session setting. Notably the Parichaya Patra `EXISTS` subquery
has **no** `is_active`-style status filter — it matches `document_number` regardless of whether
that particular card is `ACTIVE`, `EXPIRED`, `CANCELLED`, or `REPLACED`, so a member can be found
by an old, superseded Kendra Number.

The `name_q = re.split(r'[.@]', q)[0] if ('.' in q or '@' in q) else q` line is this router's one
piece of custom pre-processing logic with no equivalent in `person.py`: an email-like query
(containing `.` or `@`) would otherwise trigram-match nonsensically against `first_name`/
`last_name` (e.g. `"aniket.mishra"` could spuriously score against a *different* person's
surname `"Mishra"`), so the trigram comparison parameters use only the substring before the
first `.`/`@` separator, while the full, unsplit `q` still drives every `ILIKE`-prefix branch via
`prefix_pattern = f"{q}%"`. The 9-tuple of bind parameters maps positionally to the SQL's nine
`%s` placeholders in written order: three ID/ERP-number prefixes, two name-similarity
comparisons, mobile prefix, email prefix, Kendra-number prefix, and the `ORDER BY`
similarity argument — `prefix_pattern` appears three times and `name_q` three times, each
rebound at its respective placeholder position. `LIMIT 50` is hardcoded, same as `person.py`'s
search — no `offset` parameter on this endpoint.

**3. SAKHA AFFILIATIONS (lines 231–270, 1 endpoint):**

```python
@router.get(
    "/members/{sangha_sevi_pk}/affiliations",
    response_model=list[SakhaAffiliationResponse],
)
def list_member_affiliations(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
) -> list[SakhaAffiliationResponse]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.sangha_sevi
            WHERE  sangha_sevi_pk = %s AND is_active = TRUE
        """, (str(sangha_sevi_pk),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Member not found")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT msa.membership_sakha_affiliation_pk,
                   msa.sangha_sevi_pk,
                   msa.organization_pk,
                   o.organization_name,
                   o.organization_code,
                   msa.local_sakha_erp_id,
                   msa.effective_from,
                   msa.effective_to,
                   msa.affiliation_status,
                   msa.source_event_type,
                   msa.legacy_sakha_number
            FROM   nss.membership_sakha_affiliation msa
            JOIN   nss.organization o
                   ON o.organization_pk = msa.organization_pk
            WHERE  msa.sangha_sevi_pk = %s
            ORDER BY msa.effective_from DESC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, SakhaAffiliationResponse)
```

This is the first of four near-identical "sub-resource" endpoints (Affiliations, Parichaya
Patra, Anumati Patra, Journey Events) that all share one structural template: a first cursor
verifies `sangha_sevi_pk` exists and `is_active = TRUE`, raising `HTTPException(404, "Member not
found")` if not, then a second cursor fetches the child rows unconditionally — the same
two-cursor "distinguish parent-missing from parent-has-no-children" pattern as
`person.py::list_person_addresses`. Unlike `_MEMBER_SELECT`, this endpoint's query is inlined
directly in the function rather than factored into a module-level constant, because — unlike the
Members group's three callers — each of these four sub-resource endpoints has exactly one
caller, so there's no duplication to factor out. `ORDER BY msa.effective_from DESC` returns the
most recent affiliation first (current/active affiliation before historical/archived ones for a
transferred member).

**4. PARICHAYA PATRA (lines 278–320, 1 endpoint) and 5. ANUMATI PATRA (lines 328–363, 1
endpoint):**

```python
@router.get(
    "/members/{sangha_sevi_pk}/parichaya-patra",
    response_model=list[ParichayaPatraResponse],
)
def list_member_parichaya_patra(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
) -> list[ParichayaPatraResponse]:
    ...
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pp.parichaya_patra_pk,
                   ...
                   pp.affiliated_organization_pk,
                   o.organization_name  AS affiliated_organization_name,
                   o.organization_code  AS affiliated_organization_code,
                   pp.local_sakha_erp_id,
                   ...
            FROM   nss.parichaya_patra pp
            LEFT JOIN nss.organization o
                   ON o.organization_pk = pp.affiliated_organization_pk
            WHERE  pp.sangha_sevi_pk = %s
            ORDER BY pp.valid_from DESC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, ParichayaPatraResponse)
```

Same verify-then-fetch two-cursor template as Affiliations. The one structural difference: the
JOIN to `nss.organization o` is a `LEFT JOIN`, not a plain `JOIN`, because
`parichaya_patra.affiliated_organization_pk` is nullable in the DDL — a card snapshot could in
principle be recorded without a resolved Sakha. `local_sakha_erp_id` here is the **snapshot**
value stored directly on the `parichaya_patra` row (what was printed on that year's card), not a
live JOIN to the current affiliation — deliberately distinct from `_MEMBER_SELECT`'s
`aff.local_sakha_erp_id`, which always reflects the *current* affiliation regardless of card
history. `list_member_anumati_patra` (lines 328–363) is structurally identical minus the
`affiliated_organization`/`local_sakha_erp_id` snapshot columns entirely — `anumati_patra` has no
Sakha-snapshot columns in its DDL, since (per `database/ddl/05_membership/README.md`) it isn't
tied to a specific Sakha the way the Identity Card is. Both endpoints order by `valid_from DESC`
(most recent document first), and neither filters by `status` — a member's full document
history, including `EXPIRED`/`CANCELLED`/`REPLACED` records, is always returned.

**6. JOURNEY EVENTS (lines 371–404, 1 endpoint):**

```python
@router.get(
    "/members/{sangha_sevi_pk}/journey",
    response_model=list[JourneyEventResponse],
)
def list_member_journey(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
) -> list[JourneyEventResponse]:
    ...
    with conn.cursor() as cur:
        cur.execute("""
            SELECT mje.membership_journey_event_pk,
                   mje.sangha_sevi_pk,
                   mje.event_type,
                   mje.event_date,
                   mje.event_reference,
                   mje.remarks
            FROM   nss.membership_journey_event mje
            WHERE  mje.sangha_sevi_pk = %s
            ORDER BY mje.event_date ASC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, JourneyEventResponse)
```

The fourth and final sub-resource endpoint, and the simplest query in the router — no JOINs at
all, since `membership_journey_event.event_type` is a plain `VARCHAR` rather than an FK (the
event catalogue is application-controlled, not `master_data`-driven — see
`database/ddl/05_membership/README.md`). The one notable difference from the other three
sub-resource endpoints: `ORDER BY mje.event_date ASC` (oldest first), not `DESC` — Affiliations,
Parichaya Patra, and Anumati Patra all sort most-recent-first, but a lifecycle *timeline* reads
naturally in chronological order, which is also how the DaisyUI vertical-steps component renders
it (originally in `membership.html`, now in `dashboard.html`'s Membership tab).

---

### 2.17 `api/schemas/membership.py`

**Requirement**

`api/routers/membership.py` needs five typed response models — one per endpoint-group shape
(`MemberResponse`, `SakhaAffiliationResponse`, `ParichayaPatraResponse`, `AnumatiPatraResponse`,
`JourneyEventResponse`) — so FastAPI can validate/serialize each cursor row and so the three-tier
identity model has a single, precise, typed definition of exactly which tier's identifier
appears on which response shape, rather than that fact living only in prose.

**Line-by-line**

Lines 1–21 — module docstring and imports:

```python
"""
Pydantic response models for the Membership API (Tier 4).

All models exclude audit columns (created_at, updated_at, deleted_at)
per the project's API convention established in Tier 0.

Three-tier identity model:
  - Sangha Sevi ID (SS1) — NSS-wide, permanent, on sangha_sevi
  - ERP Number / Local Sakha Number (ESS1192) — Sakha-scoped,
    auto-generated, on membership_sakha_affiliation
  - Kendra Number (345/2026/2027) — Kendra-wide, annual,
    on parichaya_patra.document_number

Raw psycopg2 returns dictionaries — no ORM objects — so
ConfigDict(from_attributes=True) is unnecessary.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel
```

Restates the three-tier model one more time, now pinned to the exact table each tier's column
lives on — `sangha_sevi_id` on `sangha_sevi`, `local_sakha_erp_id` on
`membership_sakha_affiliation`, `document_number` on `parichaya_patra`. The
`ConfigDict(from_attributes=True)` remark is the same boilerplate note carried over from every
prior schema file, following the Tier 0 audit finding that it's unnecessary against raw
dict-returning psycopg2 cursors.

```python
class MemberResponse(BaseModel):
    # Identity
    sangha_sevi_pk: UUID
    sangha_sevi_id: str

    # Person (resolved)
    person_pk: UUID
    person_id: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    country_phone_code: str | None
    mobile_number: str | None
    email: str | None

    # Membership type (resolved from master_data)
    membership_type_master_data_pk: UUID
    membership_type_code: str
    membership_type_name: str

    # Status (resolved from master_data — unified STATUS)
    membership_status_master_data_pk: UUID
    status_code: str
    status_name: str

    # Current organization (resolved)
    organization_pk: UUID
    organization_name: str
    organization_code: str | None

    # Current Local Sakha ERP ID (from active affiliation)
    local_sakha_erp_id: str | None

    # Dates
    joining_date: date
    renewal_due_date: date | None

    remarks: str | None
    is_active: bool
```

`MemberResponse` is the widest model in the file, mirroring `_MEMBER_SELECT`'s 24 columns
field-for-field, grouped by inline comments into Identity / Person / Type / Status /
Organization / dates — the same "comment-delimited logical grouping within one flat model" style
`OrganizationResponse` and `PersonResponse` use. `local_sakha_erp_id: str | None` is nullable
specifically because `_MEMBER_SELECT`'s `LEFT JOIN` to the active-affiliation row can legitimately
produce no match; every other identity field (`sangha_sevi_id`, `person_id`) is non-optional
because their source JOINs are all plain `JOIN`s guaranteed to match.

```python
class SakhaAffiliationResponse(BaseModel):
    membership_sakha_affiliation_pk: UUID
    sangha_sevi_pk: UUID

    organization_pk: UUID
    organization_name: str
    organization_code: str | None

    local_sakha_erp_id: str
    effective_from: date
    effective_to: date | None
    affiliation_status: str
    source_event_type: str
    legacy_sakha_number: str | None
```

Unlike `MemberResponse.local_sakha_erp_id` (nullable), `SakhaAffiliationResponse.local_sakha_erp_id:
str` is non-optional — every row in `membership_sakha_affiliation` has a `NOT NULL`
`local_sakha_erp_id` in the DDL by definition (it's *the* authoritative source for this field);
the nullability lives only on the derived, JOIN-dependent copy in `MemberResponse`, not on the
source table's own shape.

```python
class ParichayaPatraResponse(BaseModel):
    parichaya_patra_pk: UUID
    sangha_sevi_pk: UUID
    document_number: str
    issue_date: date
    valid_from: date
    valid_to: date
    status: str

    # Snapshot: Sakha at issuance (resolved)
    affiliated_organization_pk: UUID | None
    affiliated_organization_name: str | None
    affiliated_organization_code: str | None

    # Snapshot: Local Sakha number at issuance
    local_sakha_erp_id: str | None

    document_reference: str | None
    remarks: str | None


class AnumatiPatraResponse(BaseModel):
    anumati_patra_pk: UUID
    sangha_sevi_pk: UUID
    document_number: str
    issue_date: date
    valid_from: date
    valid_to: date
    status: str
    document_reference: str | None
    remarks: str | None


class JourneyEventResponse(BaseModel):
    membership_journey_event_pk: UUID
    sangha_sevi_pk: UUID
    event_type: str
    event_date: date
    event_reference: str | None
    remarks: str | None
```

`ParichayaPatraResponse.document_number: str` carries the Kendra Number (Tier 3) — the docstring
explicitly calls out that its inline comments label `affiliated_organization_*` and
`local_sakha_erp_id` as "Snapshot" fields, reinforcing at the type level (not just in the
router's SQL comments) that these are point-in-time copies, not live references.
`AnumatiPatraResponse` is `ParichayaPatraResponse` minus the three Sakha-snapshot fields — a
direct, field-for-field reflection of `anumati_patra`'s DDL lacking those columns entirely (see
§2.16's note on why). `JourneyEventResponse` is the narrowest model in the file, mirroring
`membership_journey_event`'s six columns exactly, with `event_type: str` left as a plain string
(not an enum) — consistent with the DDL's deliberate choice not to constrain the event catalogue
to `master_data`.

---

## 3. Cross-references

- **`docs/03_Solution/code_explanations/SECURITY_CODE_EXPLANATIONS.md`** —
  `api/middleware.py` in full, plus the security-relevant portions of `api/config.py` and
  `api/main.py` this document deliberately doesn't duplicate.
- **`docs/03_Solution/code_explanations/TESTING_CODE_EXPLANATIONS.md`** — the
  `tests/` integration suite that exercises every router/schema documented above.
- **`docs/03_Solution/api/FOUNDATION_API_CONTRACT.md`** — the Tier 1 Foundation API
  contract: the authoritative specification of what each of the 17 endpoints in
  `api/routers/foundation.py` must return, independent of this document's implementation-level
  walkthrough.
- **`docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md`** — the Tier 2 Organization API
  contract: the authoritative specification of what each of the 6 endpoints in
  `api/routers/organization.py` must return, independent of this document's implementation-level
  walkthrough.
- **`docs/03_Solution/api/PERSON_API_CONTRACT.md`** — the Tier 3 Person API contract: the
  authoritative specification of what each of the 4 endpoints in `api/routers/person.py` must
  return, independent of this document's implementation-level walkthrough.
- **`docs/03_Solution/api/API_CONTRACT.md`** §8 — the Tier 4 Membership API contract: the
  authoritative specification of what each of the 7 endpoints in `api/routers/membership.py`
  must return, including the three-tier identity model and the full search-fields table
  (Family §7 and Membership §8 share this one cross-module contract document rather than each
  having its own `*_API_CONTRACT.md`).
- **`database/ddl/05_membership/README.md`** — the table design (12 tables, the
  "current + history" pairing pattern, and the three-tier identity split across
  `sangha_sevi`/`membership_sakha_affiliation`/`parichaya_patra`) that
  `api/routers/membership.py`'s SQL directly reflects.
- **`docs/03_Solution/code_explanations/TIER0_SECURITY_AUDIT.md`** and
  **`TIER1_SECURITY_AUDIT.md`** — the security audit verdicts for the Bootstrap and Foundation
  API surfaces respectively. These are *not* retired by this document — they record findings and
  remediation status, which is a different concern from this document's per-file code narration,
  and continue to live alongside it in this same `code_explanations/` folder.
