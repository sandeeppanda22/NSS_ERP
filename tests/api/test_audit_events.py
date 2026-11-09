"""
Audit diagnostics endpoints (api/routers/audit.py), owner request 2026-11-03:

  GET /api/v1/audit/events                — system_event_log explorer (filters, sort, paging)
  GET /api/v1/audit/events/facets         — dropdown values
  GET /api/v1/audit/events/{pk}           — one event incl. JSON detail
  GET /api/v1/audit/live-change-markers   — nss.live_change_marker diagnostics

Two kinds of test, in one file:
  * DB-FREE (`python3 -m pytest tests/api/test_audit_events.py --noconftest -k "Routes or Source"`):
    route table, permission dependency, read-only verbs, whitelist reuse.
  * INTEGRATION (bootstrapped DB; fixtures reused from test_audit.py): behaviour.

Written without a DB available: collection was verified, execution of the
integration classes was not.
"""
import inspect
import re
from uuid import uuid4

import pytest

import api.main  # noqa: F401  (registers every router)
from api.main import app
from api.routers import audit as audit_router
from api.routers.live import LIVE_FEED_TABLES
from tests.api.test_audit import admin_headers, audit_admin  # noqa: F401  (fixtures)

PREFIX = "/api/v1/audit"
EVENTS = f"{PREFIX}/events"
MARKERS = f"{PREFIX}/live-change-markers"


def _audit_routes():
    return [r for r in app.routes if getattr(r, "path", "").startswith(PREFIX)]


# ── DB-free ──────────────────────────────────────────────────────────────

class TestRoutes:
    def test_new_endpoints_are_registered(self):
        paths = {r.path for r in _audit_routes()}
        assert {EVENTS, f"{EVENTS}/facets", f"{EVENTS}/{{system_event_log_pk}}", MARKERS} <= paths

    def test_every_audit_route_is_get_only(self):
        for r in _audit_routes():
            assert r.methods == {"GET"}, (r.path, r.methods)

    def test_every_audit_route_requires_audit_view(self):
        for r in _audit_routes():
            names = [d.call.__qualname__ for d in r.dependant.dependencies]
            assert any("require_permission" in n or "dependency" in n for n in names), r.path
        src = inspect.getsource(audit_router)
        assert src.count('require_permission("AUDIT_VIEW")') == len(_audit_routes())

    def test_facets_is_declared_before_the_pk_route(self):
        paths = [r.path for r in _audit_routes()]
        assert paths.index(f"{EVENTS}/facets") < paths.index(f"{EVENTS}/{{system_event_log_pk}}")

    def test_field_change_log_is_still_not_under_foundation(self):
        assert not [r for r in app.routes if "/foundation" in getattr(r, "path", "") and "change-log" in r.path]


class TestSource:
    def test_router_never_writes(self):
        src = inspect.getsource(audit_router)
        assert not re.search(r"\b(INSERT|UPDATE|DELETE)\s+(INTO|FROM)?\s*nss\.", src.split('"""', 2)[2])
        assert "get_write_connection" not in src and "commit" not in src

    def test_whitelist_is_reused_not_copied(self):
        assert audit_router.LIVE_FEED_TABLES is LIVE_FEED_TABLES

    def test_total_is_capped_and_default_window_is_24h(self):
        assert audit_router.EVENT_TOTAL_CAP == 10_000
        assert audit_router.EVENT_DEFAULT_WINDOW.total_seconds() == 24 * 3600

    def test_limits_reuse_the_shared_page_constants(self):
        from api.helpers import DEFAULT_LIMIT, MAX_LIMIT
        params = inspect.signature(audit_router.list_system_events).parameters
        assert params["limit"].default.default == DEFAULT_LIMIT
        assert params["limit"].default.metadata[-1].le == MAX_LIMIT


# ── Integration ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_events(write_conn):
    """Two deterministic events for one record, one failed, one in the past."""
    record_pk = str(uuid4())
    cur = write_conn.cursor()
    cur.execute("""
        INSERT INTO nss.system_event_log
            (action, table_name, record_pk, module, summary, detail, is_success, event_at)
        VALUES ('AUDIT_TEST_A', 'person', %s, 'audit_events_test', %s, '{"k": 1}'::jsonb, TRUE,
                NOW() - INTERVAL '3 days'),
               ('AUDIT_TEST_B', 'person', %s, 'audit_events_test', 'second event', NULL, FALSE, NOW())
        RETURNING system_event_log_pk
    """, (record_pk, "first 100%_marker", record_pk))
    pks = [str(r[0]) for r in cur.fetchall()]
    return {"record_pk": record_pk, "pks": pks}


@pytest.mark.integration
class TestEventList:
    def test_shape(self, client, admin_headers, sample_events):
        r = client.get(EVENTS, params={"record_pk": sample_events["record_pk"]}, headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"items", "total", "total_capped", "event_from", "limit", "offset"}
        assert body["total"] == 2 and body["total_capped"] is False

    def test_record_filter_has_no_default_window(self, client, admin_headers, sample_events):
        body = client.get(EVENTS, params={"record_pk": sample_events["record_pk"]}, headers=admin_headers).json()
        assert body["event_from"] is None
        assert {i["action"] for i in body["items"]} == {"AUDIT_TEST_A", "AUDIT_TEST_B"}

    def test_default_window_is_last_24h(self, client, admin_headers, sample_events):
        body = client.get(EVENTS, params={"module": "audit_events_test"}, headers=admin_headers).json()
        assert body["event_from"] is not None
        assert [i["action"] for i in body["items"]] == ["AUDIT_TEST_B"]

    def test_explicit_event_from_widens_the_window(self, client, admin_headers, sample_events):
        body = client.get(EVENTS, params={"module": "audit_events_test", "event_from": "2000-01-01T00:00:00Z"},
                          headers=admin_headers).json()
        assert body["total"] == 2

    def test_sort_asc_and_desc(self, client, admin_headers, sample_events):
        p = {"record_pk": sample_events["record_pk"]}
        desc = [i["action"] for i in client.get(EVENTS, params={**p, "sort": "desc"}, headers=admin_headers).json()["items"]]
        asc = [i["action"] for i in client.get(EVENTS, params={**p, "sort": "asc"}, headers=admin_headers).json()["items"]]
        assert desc == ["AUDIT_TEST_B", "AUDIT_TEST_A"] and asc == list(reversed(desc))

    def test_bad_sort_is_422(self, client, admin_headers):
        assert client.get(EVENTS, params={"sort": "sideways"}, headers=admin_headers).status_code == 422

    def test_filters_action_success_table(self, client, admin_headers, sample_events):
        p = {"record_pk": sample_events["record_pk"]}
        assert client.get(EVENTS, params={**p, "action": "AUDIT_TEST_A"}, headers=admin_headers).json()["total"] == 1
        assert client.get(EVENTS, params={**p, "is_success": "false"}, headers=admin_headers).json()["total"] == 1
        assert client.get(EVENTS, params={**p, "table_name": "organization"}, headers=admin_headers).json()["total"] == 0

    def test_free_text_matches_literally(self, client, admin_headers, sample_events):
        p = {"record_pk": sample_events["record_pk"]}
        assert client.get(EVENTS, params={**p, "q": "100%_marker"}, headers=admin_headers).json()["total"] == 1
        # an unescaped % or _ would match everything
        assert client.get(EVENTS, params={**p, "q": "%"}, headers=admin_headers).json()["total"] == 1
        assert client.get(EVENTS, params={**p, "q": "SECOND"}, headers=admin_headers).json()["total"] == 1

    def test_actor_filter_unknown_id_matches_nothing(self, client, admin_headers, sample_events):
        r = client.get(EVENTS, params={"actor_sangha_sevi_id": "SS999999999"}, headers=admin_headers)
        assert r.status_code == 200 and r.json()["total"] == 0

    def test_paging(self, client, admin_headers, sample_events):
        p = {"record_pk": sample_events["record_pk"], "limit": 1}
        first = client.get(EVENTS, params=p, headers=admin_headers).json()
        second = client.get(EVENTS, params={**p, "offset": 1}, headers=admin_headers).json()
        assert first["total"] == second["total"] == 2
        assert first["items"][0]["system_event_log_pk"] != second["items"][0]["system_event_log_pk"]

    def test_limit_bounds(self, client, admin_headers):
        assert client.get(EVENTS, params={"limit": 0}, headers=admin_headers).status_code == 422
        assert client.get(EVENTS, params={"limit": 501}, headers=admin_headers).status_code == 422

    def test_list_rows_carry_no_json_payload(self, client, admin_headers, sample_events):
        item = client.get(EVENTS, params={"record_pk": sample_events["record_pk"]}, headers=admin_headers).json()["items"][0]
        assert "detail" not in item


@pytest.mark.integration
class TestEventDetailAndFacets:
    def test_detail_includes_json_payload(self, client, admin_headers, sample_events):
        a = client.get(f"{EVENTS}/{sample_events['pks'][0]}", headers=admin_headers)
        assert a.status_code == 200 and a.json()["detail"] == {"k": 1}

    def test_unknown_event_is_404(self, client, admin_headers):
        assert client.get(f"{EVENTS}/{uuid4()}", headers=admin_headers).status_code == 404

    def test_bad_pk_is_422(self, client, admin_headers):
        assert client.get(f"{EVENTS}/not-a-uuid", headers=admin_headers).status_code == 422

    def test_facets_list_recent_values(self, client, admin_headers, sample_events):
        body = client.get(f"{EVENTS}/facets", headers=admin_headers).json()
        assert set(body) == {"tables", "actions", "modules"}
        assert "AUDIT_TEST_B" in body["actions"] and "audit_events_test" in body["modules"]
        assert "AUDIT_TEST_A" in body["actions"]   # 3 days old, inside the 30-day facet window
        assert body["tables"] == sorted(body["tables"])


@pytest.mark.integration
class TestLiveChangeMarkers:
    def test_shape_and_order(self, client, admin_headers):
        body = client.get(MARKERS, headers=admin_headers).json()
        assert set(body) == {"server_time", "markers", "latest_change_seq", "latest_table_name",
                             "whitelist_size", "whitelist_without_marker"}
        seqs = [m["change_seq"] for m in body["markers"]]
        assert seqs == sorted(seqs, reverse=True)
        assert body["whitelist_size"] == len(LIVE_FEED_TABLES)
        if body["markers"]:
            assert body["latest_change_seq"] == seqs[0] == max(seqs)
            assert body["latest_table_name"] == body["markers"][0]["table_name"]
            assert set(body["markers"][0]) == {"table_name", "change_seq", "changed_at", "on_live_whitelist"}

    def test_whitelist_flag_matches_the_live_feed_list(self, client, admin_headers):
        body = client.get(MARKERS, headers=admin_headers).json()
        for m in body["markers"]:
            assert m["on_live_whitelist"] == (m["table_name"] in LIVE_FEED_TABLES)
        present = {m["table_name"] for m in body["markers"]}
        assert set(body["whitelist_without_marker"]) == LIVE_FEED_TABLES - present
