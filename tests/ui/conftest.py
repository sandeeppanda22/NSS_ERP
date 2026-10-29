"""
NSS ERP — UI test fixtures (Playwright).

Provides browser, page, and authentication helpers for
end-to-end UI tests running against a live local server.

Requirements (the server is started automatically — see _ui_server):
  - Local PostgreSQL running with nss schema bootstrapped
  - Playwright + Chromium installed:
      pip install pytest-playwright
      playwright install chromium

Usage:
  pytest tests/ui/                       # run all UI tests
  pytest tests/ui/ -m ui                 # explicit marker
  pytest tests/ui/ --headed              # watch the browser
  pytest tests/ui/ --slowmo 500          # slow down for debugging
"""

import base64
import json
import os
import time
import warnings

import pytest
from playwright.sync_api import Page, BrowserContext


# ── Configuration ──────────────────────────────────────────────────────

# By default the suite starts its OWN server (see _ui_server below) on a free
# port, with live reload off and the rate limit relaxed, and stops it when the
# session ends. To test an already-running server instead:
#   NSS_UI_BASE_URL=http://127.0.0.1:8002 python3 -m pytest tests/ui
# or, to use the conventional dev port without spawning anything:
#   NSS_UI_NO_SERVER=1 python3 -m pytest tests/ui     (-> http://127.0.0.1:8001)
# BASE_URL is a module constant other test files import, so the port is
# chosen here at import time rather than inside the fixture.


def _free_port() -> int:
    import socket

    try:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    except OSError:  # e.g. a sandbox that forbids bind(); collection must still work
        return 8001


_EXTERNAL_SERVER = bool(os.environ.get("NSS_UI_BASE_URL") or os.environ.get("NSS_UI_NO_SERVER"))
if _EXTERNAL_SERVER:
    BASE_URL = os.environ.get("NSS_UI_BASE_URL", "http://127.0.0.1:8001")
else:
    BASE_URL = f"http://127.0.0.1:{_free_port()}"

# Test credentials — must exist in the local DB.
# scripts/bootstrap_admin.py seeds SS1 with password Admin@123 and
# force_password_change = FALSE — login goes straight to /dashboard,
# no change-password interstitial. ADMIN_PASSWORD_BOOTSTRAP and
# ADMIN_PASSWORD_NEW are kept as separate names (both currently the same
# value) so _do_login's retry-with-bootstrap-password fallback still
# works unchanged if an environment's account ever drifts from this.
ADMIN_SS_ID = "SS1"
ADMIN_PASSWORD_BOOTSTRAP = "Admin@123"
ADMIN_PASSWORD_NEW = "Admin@123"

# Currently only SS1 (admin) exists.
# Update when a separate member account is bootstrapped.
MEMBER_SS_ID = "SS1"


# ── Apply UI marker to all tests in this directory ─────────────────────

pytestmark = pytest.mark.ui


def pytest_collection_modifyitems(items):
    """Automatically add 'ui' marker to all tests in this package."""
    for item in items:
        if "/ui/" in str(item.fspath):
            item.add_marker(pytest.mark.ui)


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override default browser context settings."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "ignore_https_errors": True,
    }


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SERVER_START_TIMEOUT_S = 60


@pytest.fixture(scope="session", autouse=True)
def _release_api_test_locks(_db_conn):
    """
    Roll back the API tests' shared writer transaction before any UI test runs.

    In a combined `pytest` run the api/db/security tests share ONE
    session-scoped connection (tests/conftest.py::_db_conn) whose transaction
    stays open for the whole process. Session-scoped fixtures such as
    admin_view_token run BEFORE the module-scoped SAVEPOINT, so their
    `UPDATE nss.user_account ... WHERE <admin>` is not undone at module
    teardown and keeps a ROW LOCK on that admin (SS1) until the process ends.
    The separately running UI server then blocks forever on its own
    UPDATE of that row at login (last_login_at etc.) -> every login times out.
    Rolling back here releases those locks (and discards the uncommitted
    password change, which the UI login must not see anyway).
    """
    if not _db_conn.closed:
        _db_conn.rollback()
    yield


@pytest.fixture(scope="session")
def _ui_server(_release_api_test_locks):

    """Start uvicorn for the session and stop it afterwards.

    The server's output goes to ui_test_server.log in the repo root.
    Skipped when NSS_UI_BASE_URL / NSS_UI_NO_SERVER points the suite at a
    server you run yourself. The spawned server has DEV_LIVE_RELOAD off, no
    --reload and a relaxed RATE_LIMIT — exactly what the guards below demand —
    and reads DB credentials from api/.env like a normal run.
    """
    if _EXTERNAL_SERVER:
        yield None
        return

    import subprocess
    import sys
    import urllib.request

    port = BASE_URL.rsplit(":", 1)[1]
    # Pools are enlarged because Chromium fires a burst of parallel requests
    # per page load; the default write pool (5) was seen exhausted on
    # /auth/refresh ("connection pool exhausted" -> 500 -> forced logout).
    env = {
        **os.environ,
        "DEV_LIVE_RELOAD": "",
        "RATE_LIMIT": "100000/minute",
        "DB_WRITE_POOL_MAX": "20",
        "DB_READ_POOL_MAX": "30",
    }
    # Kept after the run (overwritten each session, *.log is gitignored): its
    # access log is the only record of which request answered 401/403/500 when a
    # test fails with an unexplained bounce to /login or a blank page.
    log = open(os.path.join(_REPO_ROOT, "ui_test_server.log"), "w+")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", port],
        cwd=_REPO_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + _SERVER_START_TIMEOUT_S
        while True:
            if proc.poll() is not None:
                pytest.exit(f"UI test server exited during startup:\n{_tail(log.name)}", returncode=2)
            try:
                urllib.request.urlopen(f"{BASE_URL}/api/v1/bootstrap/health", timeout=2)
                break
            except Exception:
                if time.time() > deadline:
                    pytest.exit(
                        f"UI test server did not become healthy within {_SERVER_START_TIMEOUT_S}s:\n{_tail(log.name)}",
                        returncode=2,
                    )
                time.sleep(0.5)
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()


def _tail(path: str, lines: int = 40) -> str:
    with open(path, errors="replace") as fh:
        return "".join(fh.readlines()[-lines:])


@pytest.fixture(scope="session")
def base_url(_ui_server):
    """Base URL for all page.goto() calls (starts the server first)."""
    return BASE_URL


# ── Rate-limit sanity check ────────────────────────────────────────────

# The API applies slowapi's default_limits (RATE_LIMIT, default "300/minute",
# keyed on client IP) to EVERY endpoint. One admin page load costs several
# requests, so a full UI run (thousands of requests) exceeds that and the server starts
# answering 429. That is what made whole-suite runs fail where each file passed
# alone: the failures looked like "nav item never appeared" or an empty table,
# never like a rate limit. Probe once and say so up front.

RATE_LIMIT_PROBE_REQUESTS = 320  # just over the 300/minute default
RATE_LIMIT_ADVICE = (
    "The API is rate limiting this client (429 after ~300 requests/minute, the "
    "RATE_LIMIT default). A UI suite run exceeds that easily, which shows up as "
    "unrelated-looking UI failures. Restart the dev server with a relaxed limit "
    "for test runs, e.g.:\n"
    "    RATE_LIMIT=100000/minute python3 -m uvicorn api.main:app --port 8001"
)


# ── Dev live-reload guard ──────────────────────────────────────────────
#
# With DEV_LIVE_RELOAD on, every served page polls /__dev/frontend-version
# once a second and calls location.reload() the moment anything under
# frontend/ changes (or after a uvicorn --reload restart). Over a ~10 minute
# run that means (a) a page reload can land in the middle of page.goto(),
# which Playwright reports as "net::ERR_ABORTED" / "Navigation ... interrupted
# by another navigation", and (b) one extra request/second per open page
# counts against the rate limit. Neither points at the real cause, so refuse
# to start and say so.

LIVE_RELOAD_ADVICE = (
    "The server under test has DEV_LIVE_RELOAD enabled "
    "(GET /__dev/frontend-version answered). Its auto-reload aborts in-flight "
    "page.goto() calls (net::ERR_ABORTED / 'Navigation ... interrupted') and "
    "adds a poll per second per page to the rate-limit budget. Restart the "
    "server for test runs WITHOUT it and WITHOUT --reload (editing files "
    "mid-run also restarts uvicorn --reload):\n"
    "    DEV_LIVE_RELOAD= RATE_LIMIT=100000/minute python3 -m uvicorn "
    "api.main:app --port 8001\n"
    "Set NSS_UI_ALLOW_LIVE_RELOAD=1 to run anyway."
)


@pytest.fixture(scope="session", autouse=True)
def _live_reload_guard(base_url):
    """Abort the session early if the target server auto-reloads pages."""
    import urllib.request

    if os.environ.get("NSS_UI_ALLOW_LIVE_RELOAD"):
        return
    try:
        urllib.request.urlopen(f"{base_url}/__dev/frontend-version", timeout=5)
    except Exception:
        # 404 (flag off), 429, or unreachable: nothing to guard against here.
        return
    pytest.exit(LIVE_RELOAD_ADVICE, returncode=2)


@pytest.fixture(scope="session", autouse=True)
def _rate_limit_warning(base_url):
    """Warn once per session if the production rate limit is still in force."""
    import urllib.error
    import urllib.request

    limited = False
    for _ in range(RATE_LIMIT_PROBE_REQUESTS):
        try:
            urllib.request.urlopen(f"{base_url}/api/v1/auth/me", timeout=5)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                limited = True
                break
        except Exception:
            # Server not reachable — the individual tests report that far
            # better than a probe can.
            return
    if limited:
        warnings.warn(UserWarning(RATE_LIMIT_ADVICE))
        # The window is per minute; let it roll over so the suite does not
        # start already throttled.
        time.sleep(61)


# ── Test-data cleanup ───────────────────────────────────────────────────
#
# UI tests drive a real running uvicorn server over HTTP (see module
# docstring) — unlike tests/api|db|security, their writes are NOT wrapped
# in a SAVEPOINT (tests/conftest.py's rollback mechanism only applies
# inside the pytest process's own TestClient calls). Every person/
# user_account/sangha_sevi/claim a UI test creates by clicking through
# the real form is a real, permanent commit.
#
# Only two files create that kind of data: test_ui_06_register_submit.py
# (person + user_account + registration_claim via a real /register
# submission) and test_ui_07_admin_write.py (approves that claim, which
# additionally creates sangha_sevi + membership_sakha_affiliation +
# anumati_patra/parichaya_patra). Both tag every person they create with
# a `@example.com` email (see _unique_suffix() in those files) — that is
# the one marker this fixture relies on to find rows safely, without
# touching anything a real member created.
#
# Cleanup runs once, at the end of the whole UI session (not per-test),
# so test_ui_07's dependency on claims from test_ui_06 still sees that
# data for the full run. It is a hard DELETE, not a soft-delete/archive —
# deliberately, since this is throwaway test fixture data, not real
# membership history (the "History Never Deleted" principle governs
# production domain data, not test scaffolding).

UI_TEST_EMAIL_PATTERN = "%@example.com"

# Tables with a sangha_sevi_pk FK that the register→approve flow can
# populate (per api/routers/claim_approval.py::approve_claim()). Deleted
# before sangha_sevi itself, since every FK in this schema is plain
# NO ACTION (no ON DELETE CASCADE anywhere — see database/ddl/).
_SANGHA_SEVI_DEPENDENT_TABLES = (
    "anumati_patra",
    "parichaya_patra",
    "membership_sakha_affiliation",
)

# Tables with a user_account_pk FK, deleted before user_account itself.
_USER_ACCOUNT_DEPENDENT_TABLES = (
    "user_role",
    "user_session",
    "password_history",
    "password_reset_token",
)


@pytest.fixture(scope="session")
def _ui_cleanup_conn():
    """
    Direct psycopg2 connection used only to delete throwaway UI-test rows.

    It must be the schema OWNER (DB_OWNER_USER / DB_OWNER_PASSWORD in
    api/.env): the app's own roles cannot DELETE anything — nss_db_writer is
    SELECT/INSERT/UPDATE only by design (database/scripts/05_create_writer_role.sql),
    so cleaning up with it fails with "permission denied" the moment there is a
    row to remove. Without owner credentials this yields None and cleanup is
    skipped with a warning (the rows are tagged @example.com and harmless).
    """
    import psycopg2
    from api.config import settings

    user = os.environ.get("DB_OWNER_USER")
    password = os.environ.get("DB_OWNER_PASSWORD")
    if not (user and password):
        yield None
        return

    settings.validate()
    conn = psycopg2.connect(
        dbname=settings.DB_NAME,
        user=user,
        password=password,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    conn.autocommit = True
    yield conn
    conn.close()


def _purge_ui_test_rows(conn) -> int:
    """
    Hard-delete every person (and its dependent rows) tagged with the
    `@example.com` marker, in FK order (no ON DELETE CASCADE anywhere).

    Returns the number of marked person rows found (0 if the DB was
    already clean). Raises on SQL failure — the caller decides whether a
    failure is fatal (pre-session) or a warning (post-session).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT person_pk FROM nss.person WHERE email ILIKE %s",
            (UI_TEST_EMAIL_PATTERN,),
        )
        person_pks = [row[0] for row in cur.fetchall()]
        if not person_pks:
            return 0

        cur.execute(
            "SELECT sangha_sevi_pk FROM nss.sangha_sevi "
            "WHERE person_pk = ANY(%s::uuid[])",
            (person_pks,),
        )
        sevi_pks = [row[0] for row in cur.fetchall()]

        cur.execute(
            "SELECT user_account_pk FROM nss.user_account "
            "WHERE person_pk = ANY(%s::uuid[])",
            (person_pks,),
        )
        account_pks = [row[0] for row in cur.fetchall()]

        if sevi_pks:
            for table in _SANGHA_SEVI_DEPENDENT_TABLES:
                cur.execute(
                    f"DELETE FROM nss.{table} WHERE sangha_sevi_pk = ANY(%s::uuid[])",
                    (sevi_pks,),
                )
            cur.execute(
                "DELETE FROM nss.sangha_sevi WHERE sangha_sevi_pk = ANY(%s::uuid[])",
                (sevi_pks,),
            )

        cur.execute(
            "DELETE FROM nss.registration_claim "
            "WHERE person_pk = ANY(%s::uuid[]) OR user_account_pk = ANY(%s::uuid[])",
            (person_pks, account_pks),
        )

        if account_pks:
            for table in _USER_ACCOUNT_DEPENDENT_TABLES:
                cur.execute(
                    f"DELETE FROM nss.{table} WHERE user_account_pk = ANY(%s::uuid[])",
                    (account_pks,),
                )
            cur.execute(
                "DELETE FROM nss.user_account WHERE user_account_pk = ANY(%s::uuid[])",
                (account_pks,),
            )

        cur.execute(
            "DELETE FROM nss.person_address WHERE person_pk = ANY(%s::uuid[])",
            (person_pks,),
        )
        # /register creates genuinely new city/village, PIN and post-office rows
        # as PENDING with submitted_by_person_pk = the registrant (immediate FK
        # to person), while the person row points back at them. Break that cycle:
        # detach the person first, drop the geography they submitted, then the
        # person.
        cur.execute(
            "UPDATE nss.person SET city_village_pk = NULL, postal_code_pk = NULL "
            "WHERE person_pk = ANY(%s::uuid[])",
            (person_pks,),
        )
        for table in ("post_office", "city_village", "postal_code"):
            cur.execute(
                f"DELETE FROM nss.{table} "
                "WHERE submitted_by_person_pk = ANY(%s::uuid[])",
                (person_pks,),
            )
        cur.execute(
            "DELETE FROM nss.person WHERE person_pk = ANY(%s::uuid[])",
            (person_pks,),
        )
    return len(person_pks)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_ui_test_data(_ui_cleanup_conn):
    """
    Guarantee the UI suite neither inherits nor leaves `@example.com`
    throwaway rows — even when the previous run died abnormally.

    Runs the purge TWICE:
      * Before the session (pre-yield): clears anything a prior run left
        behind after a crash / Ctrl-C / `kill` — the case the post-yield
        delete alone can never cover, because an interrupted process never
        reaches its teardown. A pre-session failure is fatal (raised): a
        dirty DB would make the register/claim tests collide on unique
        contacts and fail for a misleading reason.
      * After the session (post-yield): the normal happy-path cleanup. A
        post-session failure only warns — the tests already passed, and the
        next run's pre-yield pass will clear whatever remains.
    """
    if _ui_cleanup_conn is None:
        warnings.warn(
            UserWarning(
                "UI test-data cleanup skipped: set DB_OWNER_USER and "
                "DB_OWNER_PASSWORD (nss_db_owner) in api/.env to delete the "
                f"'{UI_TEST_EMAIL_PATTERN}' rows these tests create — "
                "nss_db_writer has no DELETE privilege."
            )
        )
        yield
        return

    leftover = _purge_ui_test_rows(_ui_cleanup_conn)
    if leftover:
        warnings.warn(
            UserWarning(
                f"Pre-session cleanup removed {leftover} leftover "
                f"'{UI_TEST_EMAIL_PATTERN}' person row(s) from a previous "
                "UI run that did not exit cleanly."
            )
        )

    yield

    try:
        _purge_ui_test_rows(_ui_cleanup_conn)
    except Exception as exc:
        warnings.warn(
            UserWarning(
                f"UI test-data cleanup failed ({exc}) — rows tagged "
                f"'{UI_TEST_EMAIL_PATTERN}' may remain in the DB; the next "
                "run's pre-session pass will clear them."
            )
        )


@pytest.fixture
def page(context: BrowserContext, base_url: str) -> Page:
    """
    Fresh page per test with base_url set.

    Each test gets a clean page (no cookies/storage from prior tests).
    """
    pg = context.new_page()
    pg.set_default_timeout(10000)  # 10s default timeout
    pg.set_default_navigation_timeout(15000)  # 15s for navigation
    yield pg
    pg.close()


# ── Login helpers ──────────────────────────────────────────────────────

def _do_login(page: Page, base_url: str, login_id: str, password: str):
    """
    Perform login via the login page, handling force_password_change.

    Flow:
      1. Navigate to /login, fill credentials, click Sign In.
      2. If force_password_change is active, the page stays on /login
         and shows the "Change Your Password" form. We fill in
         ADMIN_PASSWORD_NEW and submit.
      3. After success, wait for redirect to /dashboard.

    If the bootstrap password has already been changed (prior test run),
    the method tries ADMIN_PASSWORD_NEW first, falling back to the
    bootstrap default.
    """
    page.goto(f"{base_url}/login")
    page.wait_for_selector('[x-model="login_id"]', state="visible")

    change_form = page.locator('[x-model="newPassword"]')
    error_el = page.locator('[x-text="error"]')

    # Try the post-change password first (works on subsequent runs)
    _attempt_login(page, login_id, password)
    outcome = _wait_for_login_outcome(page, change_form, error_el)

    # Case 1: Already redirected — password was accepted, no force change.
    if outcome == "redirected":
        return

    # Case 2: Force password change form appeared
    if outcome == "change_form":
        _handle_force_password_change(page)
        return

    # Case 3: Error (wrong password) or nothing detected in time — retry
    # with the bootstrap default, unless we already used it.
    if password != ADMIN_PASSWORD_BOOTSTRAP:
        page.fill('[x-model="login_id"]', "")
        page.wait_for_timeout(200)
        page.fill('[x-model="login_id"]', login_id)
        page.fill('[x-model="password"]', ADMIN_PASSWORD_BOOTSTRAP)
        page.click("button:has-text('Sign In')")
        outcome = _wait_for_login_outcome(page, change_form, error_el)

        if outcome == "redirected":
            return
        if outcome == "change_form":
            _handle_force_password_change(page)
            return

    # Final fallback: wait for redirect (might just be slow)
    page.wait_for_url(lambda url: "/login" not in url, timeout=10000)


def _wait_for_login_outcome(page: Page, change_form, error_el, timeout_ms: int = 8000):
    """
    Poll for the first observable outcome of a submitted login attempt:
    redirect away from /login, the force-password-change form, or a
    rendered error message. Avoids a fixed wait_for_timeout() racing
    Alpine's re-render (which silently drops the bootstrap-password retry
    and causes a plain, unexplained 10s hang further down).

    Returns "redirected", "change_form", "error", or "timeout".
    """
    start = time.monotonic()
    while (time.monotonic() - start) * 1000 < timeout_ms:
        if "/login" not in page.url:
            return "redirected"
        if change_form.is_visible():
            return "change_form"
        if error_el.is_visible() and (error_el.text_content() or "").strip():
            return "error"
        page.wait_for_timeout(150)
    return "timeout"


def _attempt_login(page: Page, login_id: str, password: str):
    """Fill login form and click Sign In."""
    page.fill('[x-model="login_id"]', login_id)
    page.fill('[x-model="password"]', password)
    page.click("button:has-text('Sign In')")


def _handle_force_password_change(page: Page):
    """
    Handle the force_password_change form on the login page.

    Fills ADMIN_PASSWORD_NEW into both fields, clicks Change Password,
    and waits for redirect to /dashboard (1.5s delay built into the UI).
    """
    page.fill('[x-model="newPassword"]', ADMIN_PASSWORD_NEW)
    page.fill('[x-model="confirmPassword"]', ADMIN_PASSWORD_NEW)
    page.wait_for_timeout(300)
    page.click("button:has-text('Change Password')")

    # The UI shows "Password changed. Redirecting..." then waits 1.5s
    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)


# ── Session reuse ──────────────────────────────────────────────────────
#
# NSSAuth keeps the whole session in localStorage (nss_access_token /
# nss_refresh_token / nss_user) — no cookies — so a session can be captured
# once and replayed into any later page on the same origin.
#
# This matters for more than speed. pytest-playwright gives each test a fresh
# context, so a per-test login meant ~220 bcrypt verifications per suite run
# against the single-worker dev server. Under that load logins started timing
# out, and the failure surfaced further down the test as "nav item never
# appeared" — the source of the whole-suite-only failures that every file
# passed cleanly in isolation. One login per session removes the contention
# instead of papering over it with longer timeouts.

SESSION_KEYS = ("nss_access_token", "nss_refresh_token", "nss_user")

# Re-login rather than replay a token this close to (or past) its expiry.
# Replaying a stale one makes the page refresh it on load, and if the server
# rotates refresh tokens only the first page to do so wins — every later test
# gets a 401, bounces to /login, and fails with a misleading "nav item never
# appeared". Cheaper and far more stable to notice the clock here.
SESSION_MIN_REMAINING_SECONDS = 120


@pytest.fixture(scope="session")
def _session_cache():
    """login_id → captured localStorage session, filled on first use."""
    return {}


def _capture_session(page: Page) -> dict:
    return page.evaluate(
        "(keys) => Object.fromEntries(keys.map(k => [k, localStorage.getItem(k)]))",
        list(SESSION_KEYS),
    )


def _token_seconds_left(token: str | None) -> float:
    """
    Seconds until a JWT's `exp`, or -1 if it cannot be read. Signature is not
    checked — this only decides whether to reuse or re-login.
    """
    if not token:
        return -1
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload))["exp"]
        return float(exp) - time.time()
    except Exception:
        return -1


def _token_accepted(base_url: str, token: str | None) -> bool:
    """True if the API currently accepts this access token (GET /auth/me)."""
    import urllib.request

    if not token:
        return False
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _restore_session(page: Page, base_url: str, session: dict) -> bool:
    """
    Replay a captured session and confirm it is still accepted.

    /login is a static page on the right origin, so it is the cheapest place
    to seed localStorage. Returns False if the token no longer holds (aged out,
    revoked, server restarted), in which case the caller logs in again.
    """
    if _token_seconds_left(session.get("nss_access_token")) < \
            SESSION_MIN_REMAINING_SECONDS:
        return False

    # Ask the server first. The browser-side check below cannot tell a live
    # session from a revoked one in time: dashboard.html ships static
    # .nav-item markup, so the selector matches before /auth/me has answered
    # and a session revoked by an earlier logout would be accepted — every later
    # test then bounced to /login.
    if not _token_accepted(base_url, session.get("nss_access_token")):
        return False

    page.goto(f"{base_url}/login")
    page.evaluate(
        "(s) => { for (const [k, v] of Object.entries(s)) "
        "if (v !== null) localStorage.setItem(k, v); }",
        session,
    )
    page.goto(f"{base_url}/dashboard")
    try:
        # Not "did the URL stay put" — the redirect to /login only happens once
        # /auth/me has answered, so checking too early passes for the wrong
        # reason. Wait for the authenticated layout to actually render.
        page.wait_for_selector(".nav-item", state="attached", timeout=10_000)
    except Exception:
        return False
    return "/login" not in page.url


def _authenticated_page(context, base_url, cache, login_id) -> Page:
    pg = context.new_page()
    pg.set_default_timeout(10000)
    pg.set_default_navigation_timeout(15000)

    cached = cache.get(login_id)
    if cached and _restore_session(pg, base_url, cached):
        # Carry forward anything the page rotated while loading.
        cache[login_id] = _capture_session(pg)
        return pg

    _do_login(pg, base_url, login_id, ADMIN_PASSWORD_NEW)
    cache[login_id] = _capture_session(pg)
    return pg


@pytest.fixture
def admin_page(context: BrowserContext, base_url: str, _session_cache) -> Page:
    """
    Page pre-authenticated as admin (SS1).

    Logs in for real once per test session (handling force_password_change),
    then replays the stored tokens for every later test. Yields the page on
    /dashboard; tests can navigate from there.
    """
    pg = _authenticated_page(context, base_url, _session_cache, ADMIN_SS_ID)
    yield pg
    pg.close()


@pytest.fixture
def member_page(context: BrowserContext, base_url: str, _session_cache) -> Page:
    """
    Page pre-authenticated as a regular member.

    Currently uses SS1 (same as admin). Update MEMBER_SS_ID
    when a separate member account exists.
    """
    pg = _authenticated_page(context, base_url, _session_cache, MEMBER_SS_ID)
    yield pg
    pg.close()


# ── Utility helpers ────────────────────────────────────────────────────

def wait_for_alpine(page: Page, timeout: int = 5000):
    """Wait until Alpine.js has initialized on the page."""
    page.wait_for_function(
        "() => typeof Alpine !== 'undefined' && Alpine.version !== undefined",
        timeout=timeout,
    )


def wait_for_toast(page: Page, text: str = None, timeout: int = 5000):
    """
    Wait for a toast/notification to appear.

    If text is provided, waits for a toast containing that text.
    """
    if text:
        page.wait_for_selector(f"text={text}", state="visible", timeout=timeout)
    else:
        # Generic toast — look for common toast containers
        page.wait_for_selector(
            ".toast, .notification, .alert-success, [x-show*='toast']",
            state="visible",
            timeout=timeout,
        )


def get_table_rows(page: Page, table_selector: str = ".admin-table tbody tr"):
    """Count visible table rows."""
    return page.locator(table_selector).count()


def click_nav_item(page: Page, tab_name: str, timeout: int = 10000):
    """
    Click a sidebar navigation item by its display text.

    Two things this has to cope with:

    * Nav items live inside `<template x-if="!isNavGroupCollapsed('...')">`
      (admin.html / dashboard.html), so an item in a collapsed group is not
      hidden — it is absent from the DOM. The collapsed set is persisted in
      localStorage under `nss_nav_groups_collapsed`, so a test that folds a
      group (or a seeded session that carries one) makes every later
      click_nav_item in that page time out. Expand everything first, then look.
    * A bare page.click() on a missing item fails with nothing but the
      selector, which is what made the whole-suite failures unreadable. Report
      the current URL and the nav items that *are* present instead.
    """
    page.evaluate(
        "() => { try { localStorage.removeItem('nss_nav_groups_collapsed'); } "
        "catch {} }"
    )
    nav_item = page.locator(f".nav-item:has-text('{tab_name}')")
    try:
        nav_item.first.wait_for(state="visible", timeout=2000)
    except Exception:
        # Expand any collapsed group in place (no reload — that would discard
        # whatever the test has already set up on this page).
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.nav-section-label')) {
                const chev = el.querySelector('.nav-chevron');
                if (chev && chev.classList.contains('collapsed')) el.click();
            }
        }""")
        try:
            nav_item.first.wait_for(state="visible", timeout=timeout)
        except Exception as exc:
            present = page.locator(".nav-item").all_text_contents()
            raise AssertionError(
                f"nav item '{tab_name}' never appeared (url={page.url}). "
                f"Nav items present: {[t.strip() for t in present]}. "
                "An empty list usually means the page bounced to /login — the "
                "session was not accepted — rather than a selector problem."
            ) from exc
    nav_item.first.click()
    page.wait_for_timeout(300)  # Allow Alpine.js reactivity
