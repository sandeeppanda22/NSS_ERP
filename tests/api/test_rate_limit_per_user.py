"""
Per-user rate limit for the live attendance poll (api/rate_limit.py).

Owner decision 2026-11-01 ("fix 1"): GET /attendance/pujas/{pk}/live is counted
per SIGNED-IN USER, not per IP, because a whole Sakha polls from one WiFi IP.
Adaptive polling (idle slow-down, hidden-tab pause, back-off) is deliberately
NOT part of this.

Most tests here are DB-free (they build a throwaway FastAPI app); they only
sit under tests/api because that is where the suite's conventions live.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request

import api.main  # noqa: F401  (imports every router so their @limiter.limit registrations exist)
from api.config import settings
from api.rate_limit import limiter, user_or_ip_key
from api.services.auth_service import create_access_token

LIVE_ROUTE = "api.routers.attendance.live_attendance"


def _token() -> str:
    return create_access_token(uuid.uuid4(), uuid.uuid4(), "SS-TEST", datetime.now(timezone.utc))


def _request(authorization: str | None, client_host: str = "10.0.0.7") -> Request:
    headers = [(b"authorization", authorization.encode())] if authorization else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (client_host, 1234)})


class TestKeyFunction:
    def test_valid_token_is_keyed_by_user(self):
        token = _token()
        key = user_or_ip_key(_request(f"Bearer {token}"))
        assert key.startswith("user:") and len(key) > len("user:")

    def test_two_tokens_of_one_user_share_a_key_and_two_users_do_not(self):
        user, person = uuid.uuid4(), uuid.uuid4()
        a1 = create_access_token(user, person, "SS-A", datetime.now(timezone.utc))
        a2 = create_access_token(user, person, "SS-A", datetime.now(timezone.utc))
        b = _token()
        assert user_or_ip_key(_request(f"Bearer {a1}")) == user_or_ip_key(_request(f"Bearer {a2}"))
        assert user_or_ip_key(_request(f"Bearer {a1}")) != user_or_ip_key(_request(f"Bearer {b}"))

    @pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer garbage", "Basic abc", "Bearer a.b.c"])
    def test_missing_or_bad_token_falls_back_to_the_client_ip(self, header):
        assert user_or_ip_key(_request(header)) == "10.0.0.7"


class TestRouteLimit:
    def test_live_route_has_its_own_limit_that_replaces_the_global_one(self):
        entries = limiter._route_limits.get(LIVE_ROUTE)
        assert entries, "live_attendance must carry @limiter.limit(...)"
        assert all(lim.override_defaults for lim in entries)
        assert str(entries[0].limit).startswith("120 per 1 minute")  # default of LIVE_ATTENDANCE_RATE_LIMIT

    def test_setting_default_and_global_limit_unchanged(self):
        assert settings.LIVE_ATTENDANCE_RATE_LIMIT == "120/minute"
        assert settings.RATE_LIMIT == "300/minute"

    def test_other_routes_keep_only_the_global_per_ip_limit(self):
        others = [name for name in limiter._route_limits if name != LIVE_ROUTE]
        assert others == []


class TestPerUserCounting:
    @pytest.fixture()
    def tiny_app(self):
        lim = Limiter(key_func=get_remote_address, default_limits=["1000/minute"])
        app = FastAPI()
        app.state.limiter = lim
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

        @app.get("/poll")
        @lim.limit("3/minute", key_func=user_or_ip_key)
        def poll(request: Request):
            return {"ok": True}

        return TestClient(app)

    def test_each_user_gets_their_own_budget_from_one_ip(self, tiny_app):
        a, b = {"Authorization": f"Bearer {_token()}"}, {"Authorization": f"Bearer {_token()}"}
        assert [tiny_app.get("/poll", headers=a).status_code for _ in range(3)] == [200, 200, 200]
        assert tiny_app.get("/poll", headers=a).status_code == 429          # A exhausted
        assert [tiny_app.get("/poll", headers=b).status_code for _ in range(3)] == [200, 200, 200]  # B unaffected
        assert tiny_app.get("/poll", headers=b).status_code == 429

    def test_anonymous_callers_share_the_ip_budget(self, tiny_app):
        assert [tiny_app.get("/poll").status_code for _ in range(3)] == [200, 200, 200]
        assert tiny_app.get("/poll").status_code == 429
