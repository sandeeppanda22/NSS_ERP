"""
Pool hygiene in api/database.py (2026-11-09: `PoolError: connection pool
exhausted` 500s on Render + Neon). DB-free: the pool and connections are fakes.
"""
import threading
import time

import psycopg2
import pytest

from api import database as db
from api.config import settings


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.conn.executed.append(sql)
        if not self.conn.alive:
            raise psycopg2.OperationalError("SSL connection has been closed unexpectedly")


class FakeConn:
    def __init__(self, alive=True, closed=False):
        self.alive, self.closed = alive, closed
        self.executed, self.rollbacks = [], 0

    def cursor(self):
        return FakeCursor(self)

    def rollback(self):
        self.rollbacks += 1


class FakePool:
    def __init__(self, conns):
        self.idle, self.put = list(conns), []

    def getconn(self):
        return self.idle.pop(0)

    def putconn(self, conn, close=False):
        self.put.append((conn, close))
        if not close:
            self.idle.append(conn)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    db._last_returned.clear()
    monkeypatch.setattr(settings, "DB_POOL_WAIT_SECONDS", 0.2)
    monkeypatch.setattr(settings, "DB_POOL_PING_AFTER_SECONDS", 30)
    yield
    db._last_returned.clear()


def slots(n=2):
    return threading.BoundedSemaphore(n)


def test_a_closed_connection_is_discarded_and_the_next_one_used():
    dead, good = FakeConn(closed=True), FakeConn()
    pool = FakePool([dead, good])
    assert db._checkout(pool, slots()) is good
    assert (dead, True) in pool.put


def test_a_new_connection_is_not_pinged():
    c = FakeConn()
    assert db._checkout(FakePool([c]), slots()) is c
    assert c.executed == []


def test_a_recently_used_connection_is_not_pinged():
    c = FakeConn()
    db._last_returned[id(c)] = 100.0
    assert db._checkout(FakePool([c]), slots(), now=lambda: 110.0) is c
    assert c.executed == []


def test_an_idle_connection_is_pinged_and_kept_when_it_answers():
    c = FakeConn()
    db._last_returned[id(c)] = 100.0
    assert db._checkout(FakePool([c]), slots(), now=lambda: 200.0) is c
    assert c.executed == ["SELECT 1"] and c.rollbacks == 1   # no transaction left open


def test_an_idle_connection_that_no_longer_answers_is_replaced():
    stale, fresh = FakeConn(alive=False), FakeConn()
    db._last_returned[id(stale)] = 100.0
    pool = FakePool([stale, fresh])
    assert db._checkout(pool, slots(), now=lambda: 200.0) is fresh
    assert (stale, True) in pool.put


def test_gives_up_after_three_bad_connections_and_frees_the_slot():
    bad = [FakeConn(closed=True) for _ in range(3)]
    s = slots(1)
    with pytest.raises(psycopg2.OperationalError):
        db._checkout(FakePool(bad), s)
    assert s.acquire(timeout=0.01)   # the slot was released, not leaked


def test_waits_for_a_free_connection_instead_of_failing():
    s = slots(1)
    first = db._checkout(FakePool([FakeConn()]), s)
    pool = FakePool([FakeConn()])
    got = []
    t = threading.Thread(target=lambda: got.append(db._checkout(pool, s)))
    t.start()
    time.sleep(0.05)
    assert got == []                      # still waiting: the only slot is taken
    db._release(FakePool([]), s, first)   # the first request finishes
    t.join(1)
    assert len(got) == 1


def test_raises_pool_busy_when_nothing_frees_up():
    s = slots(1)
    db._checkout(FakePool([FakeConn()]), s)
    with pytest.raises(db.PoolBusyError):
        db._checkout(FakePool([FakeConn()]), s)


def test_release_frees_the_slot_even_if_putconn_fails():
    class Boom(FakePool):
        def putconn(self, conn, close=False):
            raise RuntimeError("pool gone")
    s = slots(1)
    c = db._checkout(FakePool([FakeConn()]), s)
    with pytest.raises(RuntimeError):
        db._release(Boom([]), s, c)
    assert s.acquire(timeout=0.01)


def test_pool_busy_is_reported_as_503_with_retry_after():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from api.error_handlers import pool_busy_handler

    app = FastAPI()
    app.add_exception_handler(db.PoolBusyError, pool_busy_handler)

    @app.get("/x")
    def x():
        raise db.PoolBusyError("busy")

    r = TestClient(app).get("/x")
    assert r.status_code == 503 and r.headers["retry-after"] == "2"
    assert "try again" in r.json()["detail"].lower()
