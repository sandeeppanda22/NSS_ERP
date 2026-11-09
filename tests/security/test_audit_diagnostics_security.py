"""
Security tests for the audit diagnostics endpoints (api/routers/audit.py):
/audit/events, /audit/events/facets, /audit/events/{pk}, /audit/live-change-markers.

  * authentication (401) and the AUDIT_VIEW gate (403) on every one of them;
  * no write verbs (405) and no unauthenticated twin under another prefix;
  * system_event_log / live_change_marker are not exposed under /foundation or
    /live (the live feed keeps returning change numbers only);
  * the free-text filter is parameterised (SQL metacharacters are inert).

DB-free part: `--noconftest -k Source`. The rest needs the bootstrapped DB
(fixtures reused from test_audit_security.py); written without one, so only
collection was verified.
"""
import inspect
from uuid import uuid4

import pytest

import api.main  # noqa: F401
from api.main import app
from api.routers import audit as audit_router
from tests.security.test_audit_security import admin_headers, audit_admin, norole_headers  # noqa: F401  (fixtures)

PREFIX = "/api/v1/audit"
READ_PATHS = [
    f"{PREFIX}/events",
    f"{PREFIX}/events/facets",
    f"{PREFIX}/events/{uuid4()}",
    f"{PREFIX}/live-change-markers",
]


class TestSource:
    def test_every_new_handler_is_gated_by_audit_view_and_uses_the_read_pool(self):
        src = inspect.getsource(audit_router)
        assert "get_write_connection" not in src
        for fn in (audit_router.list_system_events, audit_router.system_event_facets,
                   audit_router.get_system_event, audit_router.list_live_change_markers):
            code = inspect.getsource(fn)
            assert 'require_permission("AUDIT_VIEW")' in code, fn.__name__
            assert "conn=Depends(get_connection)" in code, fn.__name__

    def test_free_text_and_filters_are_bound_parameters(self):
        code = inspect.getsource(audit_router.list_system_events)
        # the only f-string before the ORDER BY builds the LIKE *value*, never SQL text
        assert [ln.strip() for ln in code.split("direction =")[0].splitlines() if 'f"' in ln] == [
            'like = f"%{_like_escape(q.strip())}%"']
        assert "params.append(" in code and "%s" in code

    def test_no_audit_route_accepts_a_write_verb(self):
        for r in app.routes:
            if getattr(r, "path", "").startswith(PREFIX):
                assert r.methods == {"GET"}, r.path


@pytest.mark.integration
class TestGate:
    @pytest.mark.parametrize("path", READ_PATHS)
    def test_anonymous_gets_401(self, client, path):
        assert client.get(path).status_code == 401

    @pytest.mark.parametrize("path", READ_PATHS)
    def test_garbage_token_gets_401(self, client, path):
        assert client.get(path, headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401

    @pytest.mark.parametrize("path", READ_PATHS)
    def test_user_without_audit_view_gets_403(self, client, norole_headers, path):
        assert client.get(path, headers=norole_headers).status_code == 403

    @pytest.mark.parametrize("path", READ_PATHS[:2] + READ_PATHS[3:])
    def test_audit_view_holder_is_admitted(self, client, admin_headers, path):
        assert client.get(path, headers=admin_headers).status_code == 200


@pytest.mark.integration
class TestNoWrites:
    @pytest.mark.parametrize("path", READ_PATHS)
    @pytest.mark.parametrize("verb", ["post", "put", "patch", "delete"])
    def test_write_verbs_are_rejected(self, client, admin_headers, path, verb):
        assert getattr(client, verb)(path, headers=admin_headers).status_code in (404, 405)


@pytest.mark.integration
class TestExposure:
    @pytest.mark.parametrize("path", [
        "/api/v1/foundation/events", "/api/v1/foundation/system-event-log",
        "/api/v1/foundation/live-change-markers", "/api/v1/live/markers",
    ])
    def test_not_exposed_elsewhere(self, client, admin_headers, path):
        assert client.get(path, headers=admin_headers).status_code in (404, 405)

    def test_live_feed_still_returns_only_change_numbers(self, client, admin_headers):
        for entry in client.get("/api/v1/live/changes", headers=admin_headers).json()["changed"]:
            assert set(entry) == {"table_name", "change_seq"}

    def test_sql_metacharacters_in_free_text_are_inert(self, client, admin_headers):
        for q in ("'; DROP TABLE nss.person; --", "\" OR 1=1 --", "\\", "%"):
            r = client.get(f"{PREFIX}/events", params={"q": q}, headers=admin_headers)
            assert r.status_code == 200, q
        assert client.get(f"{PREFIX}/events", params={"actor_sangha_sevi_id": "x' OR '1'='1"},
                          headers=admin_headers).json()["total"] == 0
