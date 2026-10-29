"""
NSS ERP — Shared test fixtures.

Provides a FastAPI TestClient backed by the local PostgreSQL database
with **automatic transaction rollback** — every test module's DB
changes (INSERTs, UPDATEs, sequence increments) are rolled back after
the module finishes. No manual cleanup needed.

Architecture:
  - A session-scoped write connection opens a long-lived transaction.
  - Each test module opens a SAVEPOINT at the start and rolls back
    to it at the end, undoing all changes made by that module.
  - Both `get_connection` and `get_write_connection` FastAPI
    dependencies are overridden to yield the same test connection,
    so API endpoints see the same transaction.

Requirements:
  - Local PostgreSQL running with nss schema bootstrapped
  - api/.env configured with DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
  - pytest + httpx installed

Usage:
  pytest                        # run all tests
  pytest -m integration         # run only integration tests
  pytest tests/test_bootstrap.py  # run specific file
"""

from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import app, limiter
from api.database import get_connection, get_write_pool
from api.dependencies.auth import get_write_connection


# ── Session-scoped connection ──────────────────────────────────────────

@pytest.fixture(scope="session")
def _db_conn():
    """
    A single write-pool connection held for the entire test session.

    Starts a top-level transaction. Individual test modules use
    SAVEPOINTs within this transaction. The connection is rolled
    back and returned to the pool at the end of the session.
    """
    pool = get_write_pool()
    conn = pool.getconn()
    conn.autocommit = False
    yield conn
    try:
        if not conn.closed:
            conn.rollback()
        pool.putconn(conn)
    except Exception:
        pass


# ── Module-scoped SAVEPOINT ────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _module_savepoint(_db_conn):
    """
    Wrap each test module in a SAVEPOINT.

    After all tests in the module run, ROLLBACK TO SAVEPOINT undoes
    every INSERT, UPDATE, DELETE, and sequence increment made by
    both the tests and the API endpoints.
    """
    with _db_conn.cursor() as cur:
        cur.execute("SAVEPOINT test_module_sp")
    yield
    if not _db_conn.closed:
        with _db_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT test_module_sp")


# ── FastAPI dependency overrides ───────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _override_deps(_db_conn):
    """
    Override both read and write connection dependencies so API
    endpoints use the test connection (inside the SAVEPOINT).

    The override generators yield the connection but do NOT commit
    or rollback — that's handled by the module-level SAVEPOINT.
    """

    def _test_read_conn():
        yield _db_conn

    def _test_write_conn():
        yield _db_conn

    app.dependency_overrides[get_connection] = _test_read_conn
    app.dependency_overrides[get_write_connection] = _test_write_conn
    yield
    app.dependency_overrides.clear()


# ── TestClient (session-scoped) ────────────────────────────────────────

@pytest.fixture(scope="session")
def client(_override_deps):
    """
    FastAPI TestClient scoped to the test session.

    Uses the real database connection (local PostgreSQL) via
    dependency overrides. The TestClient does not start a server —
    it calls the ASGI app directly.
    """
    with TestClient(app) as c:
        yield c


# ── Write connection for direct DB access in tests ─────────────────────

@pytest.fixture(scope="module")
def write_conn(_db_conn):
    """
    Provides direct DB access for test setup/assertions.

    This is the SAME connection used by the API (via overrides),
    so tests can INSERT seed data and API endpoints will see it
    within the same transaction. Everything rolls back after the
    module finishes.
    """
    return _db_conn


# ── Per-request SAVEPOINT isolation for tests that provoke a DB error ───

@pytest.fixture
def isolated_savepoint(write_conn):
    """
    Context-manager factory: `with isolated_savepoint(): client.post(...)`.

    A request that trips a constraint (unique/FK/CHECK) aborts the shared
    session transaction, because the app's per-request rollback does not run
    under the dependency overrides above. Wrapping that one request in its
    own SAVEPOINT (rolled back on exit, whatever the outcome) keeps the rest
    of the module's tests usable. Everything the request wrote is undone too,
    so only use it around requests that are expected to fail.
    """

    @contextmanager
    def _savepoint():
        name = f"t_sp_{uuid4().hex[:10]}"
        cur = write_conn.cursor()
        cur.execute(f"SAVEPOINT {name}")
        try:
            yield
        finally:
            cur.execute(f"ROLLBACK TO SAVEPOINT {name}")

    return _savepoint


# ── Authenticated client (admin with all _VIEW permissions) ────────────

# Password we force onto the chosen admin so we can log in and mint a token.
_ADMIN_VIEW_PASSWORD = "ViewAdmin1x"


@pytest.fixture(scope="session")
def admin_view_token(_override_deps, _db_conn):
    """
    Session-scoped admin JWT carrying FOUNDATION_VIEW / ORGANIZATION_VIEW /
    PERSON_VIEW / MEMBERSHIP_VIEW.

    The Tier-5 RBAC hardening gated the foundation/organization/person/
    membership read endpoints behind these permissions. The standalone
    read-only pages that used to call them anonymously are being retired
    in favour of the authenticated admin.html directory tabs, so the
    surviving *functional* tests for those endpoints authenticate through
    this token instead of calling anonymously.

    The token is minted once. It stays valid for the whole session because
    it is a stateless JWT and the underlying role/permission rows are
    permanent seed data — only the transient password reset (rolled back
    with the module savepoint) is needed, and only at login time.
    """
    from api.services.auth_service import hash_password

    with _db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ua.user_account_pk, ss.sangha_sevi_id
            FROM nss.user_account ua
            JOIN nss.sangha_sevi ss
              ON ss.person_pk = ua.person_pk AND ss.is_active = TRUE
            JOIN nss.user_role ur
              ON ur.user_account_pk = ua.user_account_pk AND ur.is_active = TRUE
            JOIN nss.role_permission rp
              ON rp.role_master_pk = ur.role_master_pk AND rp.is_active = TRUE
            JOIN nss.permission_master pm
              ON pm.permission_master_pk = rp.permission_master_pk
            WHERE ua.is_active = TRUE
              AND ua.account_status = 'ACTIVE'
              AND pm.permission_code IN (
                  'FOUNDATION_VIEW', 'ORGANIZATION_VIEW',
                  'PERSON_VIEW', 'MEMBERSHIP_VIEW'
              )
            GROUP BY ua.user_account_pk, ss.sangha_sevi_id
            HAVING COUNT(DISTINCT pm.permission_code) = 4
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            pytest.skip(
                "No active admin holds all four _VIEW permissions; "
                "cannot authenticate the read-endpoint functional tests."
            )
        admin_pk, sevi_id = row

        cur.execute(
            """
            UPDATE nss.user_account
            SET password_hash = %s,
                password_changed_at = NOW(),
                password_expires_at = NOW() + INTERVAL '365 days'
            WHERE user_account_pk = %s
            """,
            (hash_password(_ADMIN_VIEW_PASSWORD), str(admin_pk)),
        )

    # Plain TestClient (no `with`) so we never fire lifespan shutdown /
    # close_pool() on exit, which would close the shared session connection.
    login_client = TestClient(app)
    resp = login_client.post(
        "/api/v1/auth/login",
        json={"login_id": sevi_id, "password": _ADMIN_VIEW_PASSWORD},
    )
    if resp.status_code != 200:
        pytest.skip(f"View-admin login failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def authed_client(_override_deps, admin_view_token):
    """
    A TestClient that sends an admin Bearer token on every request.

    Deliberately a plain TestClient(app) — NOT a `with` context manager —
    so it never fires the app's lifespan shutdown (close_pool()), which
    would close the shared session connection. The API routers are
    registered at import time, so all /api/v1/* routes are available
    without running startup.
    """
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {admin_view_token}"})
    return c


@pytest.fixture(scope="session")
def anon_client(_override_deps):
    """
    An explicitly UNauthenticated TestClient.

    For the small number of negative tests that assert an endpoint rejects
    anonymous access (401), used in modules whose `client` fixture has been
    overridden to send an admin token.
    """
    return TestClient(app)


# ── Rate limiter reset ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """
    Reset the rate limiter's in-memory storage before every test.

    slowapi's Limiter is a module-level singleton shared across
    the entire pytest process. Without this reset, request counts
    accumulate across test files and cause spurious 429s.
    """
    limiter.reset()
    yield
