"""
NSS ERP — Database connection pools.

Two pools:
  - Read pool (nss_db_backend): SELECT-only, used by all read endpoints.
  - Write pool (nss_db_writer): INSERT/UPDATE/DELETE on auth + admin tables,
    used by Tier 5 authentication and administration endpoints.

No ORM — raw SQL queries against nss.* tables.

Connection hygiene (2026-11-09, after `PoolError: connection pool exhausted`
500s on Render + Neon):
  - Each pool is fronted by a BoundedSemaphore of its size, so a request that
    arrives while every connection is checked out WAITS (up to
    DB_POOL_WAIT_SECONDS) instead of failing; past that it raises
    PoolBusyError, which the API turns into a 503 + Retry-After.
  - A connection that is closed, or that has sat idle longer than
    DB_POOL_PING_AFTER_SECONDS and no longer answers `SELECT 1` (Neon pauses
    an idle compute and drops connections), is discarded and replaced
    instead of being handed to a request.
  - New connections use TCP keepalives and a connect timeout.
"""

import threading
import time

import psycopg2
import psycopg2.pool

from api.config import settings


class PoolBusyError(Exception):
    """Every pooled connection stayed checked out for DB_POOL_WAIT_SECONDS."""


# libpq options for every pooled connection: detect a dead peer within ~60 s
# and never hang forever on connect (Neon waking from suspend can take seconds).
_CONNECT_OPTIONS = dict(
    connect_timeout=10,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=3,
)

# How many dead connections one checkout will discard before giving up.
_MAX_CHECKOUT_ATTEMPTS = 3

# id(connection) -> time.monotonic() when it was last returned to its pool.
# A connection with no entry is brand new and is not pinged.
_last_returned: dict[int, float] = {}

_pool_lock = threading.Lock()


def _checkout(pool, slots, *, now=time.monotonic):
    """Wait for a free slot, then return a connection that works."""
    if not slots.acquire(timeout=settings.DB_POOL_WAIT_SECONDS):
        raise PoolBusyError(
            f"no database connection became free within {settings.DB_POOL_WAIT_SECONDS}s"
        )
    try:
        return _healthy_connection(pool, now=now)
    except BaseException:
        slots.release()
        raise


def _healthy_connection(pool, *, now=time.monotonic):
    for _ in range(_MAX_CHECKOUT_ATTEMPTS):
        conn = pool.getconn()
        if conn.closed:
            _last_returned.pop(id(conn), None)
            pool.putconn(conn, close=True)
            continue
        returned_at = _last_returned.get(id(conn))
        if returned_at is not None and now() - returned_at > settings.DB_POOL_PING_AFTER_SECONDS:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()  # leave no open transaction behind the ping
            except psycopg2.Error:
                _last_returned.pop(id(conn), None)
                pool.putconn(conn, close=True)
                continue
        return conn
    raise psycopg2.OperationalError("could not obtain a working database connection")


def _release(pool, slots, conn, *, now=time.monotonic):
    """Give the connection back and free its slot, whatever happens."""
    try:
        if conn.closed:
            _last_returned.pop(id(conn), None)
        else:
            _last_returned[id(conn)] = now()
        pool.putconn(conn)
    finally:
        slots.release()

# ── Read pool (nss_db_backend — SELECT-only) ────────────────────────────

_read_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_read_slots: threading.BoundedSemaphore | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the shared read connection pool, creating it on first use."""
    global _read_pool, _read_slots
    if _read_pool is None or _read_pool.closed:
        with _pool_lock:
            if _read_pool is None or _read_pool.closed:
                settings.validate()
                _read_slots = threading.BoundedSemaphore(settings.DB_READ_POOL_MAX)
                _read_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=settings.DB_READ_POOL_MIN,
                    maxconn=settings.DB_READ_POOL_MAX,
                    dbname=settings.DB_NAME,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD,
                    host=settings.DB_HOST,
                    port=settings.DB_PORT,
                    **_CONNECT_OPTIONS,
                )
    return _read_pool


# ── Write pool (nss_db_writer — Tier 5) ─────────────────────────────────

_write_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_write_slots: threading.BoundedSemaphore | None = None


def get_write_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the shared write connection pool, creating it on first use."""
    global _write_pool, _write_slots
    if _write_pool is None or _write_pool.closed:
        with _pool_lock:
            if _write_pool is None or _write_pool.closed:
                settings.validate()
                settings.validate_auth()
                _write_slots = threading.BoundedSemaphore(settings.DB_WRITE_POOL_MAX)
                _write_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=settings.DB_WRITE_POOL_MIN,
                    maxconn=settings.DB_WRITE_POOL_MAX,
                    dbname=settings.DB_NAME,
                    user=settings.DB_WRITE_USER,
                    password=settings.DB_WRITE_PASSWORD,
                    host=settings.DB_HOST,
                    port=settings.DB_PORT,
                    **_CONNECT_OPTIONS,
                )
    return _write_pool


# ── Pool lifecycle ───────────────────────────────────────────────────────

def close_pool() -> None:
    """Close all connections in both pools."""
    global _read_pool, _write_pool
    _last_returned.clear()
    if _read_pool is not None and not _read_pool.closed:
        _read_pool.closeall()
        _read_pool = None
    if _write_pool is not None and not _write_pool.closed:
        _write_pool.closeall()
        _write_pool = None


def checkout_write() -> "psycopg2.extensions.connection":
    """A working writer connection (waits for a free slot). Always pair with
    release_write(); api.dependencies.auth.get_write_connection is the other
    caller, so ALL writes share one slot count and one health check."""
    pool = get_write_pool()
    return _checkout(pool, _write_slots)


def release_write(conn) -> None:
    _release(get_write_pool(), _write_slots, conn)


# ── Connection generators (FastAPI dependencies) ────────────────────────

def get_connection():
    """
    Read connection (nss_db_backend — SELECT-only).

    Usage as a FastAPI dependency:
        def endpoint(conn=Depends(get_connection)): ...
    """
    pool = get_pool()
    conn = _checkout(pool, _read_slots)
    try:
        yield conn
    finally:
        _release(pool, _read_slots, conn)


def get_write_connection():
    """
    Write connection (nss_db_writer — INSERT/UPDATE/DELETE).

    Low-level primitive — routers should NOT depend on this directly.
    Use api.dependencies.auth.get_write_connection instead: it wraps
    this and also sets the nss.actor_* session variables so the DB
    audit trigger records WHO made each change. Depending on this one
    produces audit/change-log rows with a NULL actor.

    Auto-commits on success, rolls back on exception.
    """
    conn = checkout_write()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_write(conn)


# ── Health check ─────────────────────────────────────────────────────────

def check_connection() -> bool:
    """
    Test whether the database is reachable via the read pool.

    Returns True if a simple query succeeds, False otherwise.
    Does not leak connection details on failure.
    """
    try:
        pool = get_pool()
        conn = _checkout(pool, _read_slots)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        finally:
            _release(pool, _read_slots, conn)
    except Exception:
        return False
