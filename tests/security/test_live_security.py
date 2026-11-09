"""
Security matrix for the live-refresh change feed: GET /api/v1/live/changes
(api/routers/live.py, 1 endpoint).

The one gate: login only (any signed-in user, no module permission). The
reply must never disclose record data or ids, and never name a table outside
the LIVE_FEED_TABLES whitelist.

Written without a DB available: collection was verified, execution was not.
"""
import pytest

from api.routers.live import LIVE_FEED_TABLES
from tests.api.test_family_ownership import (  # noqa: F401  (fixtures)
    make_roleless_member,
    sakha_pk,
)

pytestmark = pytest.mark.integration

URL = "/api/v1/live/changes"


def test_matrix_covers_every_endpoint():
    """The live router has exactly one route; a new one must get a gate assertion here."""
    from api.main import app

    routes = {(m, r.path) for r in app.routes if getattr(r, "path", "").startswith("/api/v1/live")
              for m in r.methods if m != "HEAD"}
    assert routes == {("GET", URL)}


def test_anonymous_is_401(anon_client):
    assert anon_client.get(URL).status_code == 401


@pytest.mark.parametrize("header", ["Bearer", "Bearer garbage", "Basic abc", "Bearer a.b.c"])
def test_bad_credentials_are_401(anon_client, header):
    assert anon_client.get(URL, headers={"Authorization": header}).status_code in (401, 403)


def test_roleless_member_is_admitted(make_roleless_member, sakha_pk):
    member = make_roleless_member(sakha_pk)
    r = member["client"].get(URL)
    assert r.status_code == 200
    assert set(r.json()) == {"changed"}


def test_reply_never_discloses_ids_or_non_whitelisted_tables(make_roleless_member, sakha_pk, write_conn):
    member = make_roleless_member(sakha_pk)
    with write_conn.cursor() as cur:
        # A stray marker row for a table that is not on the whitelist (ballots, credentials) must stay invisible.
        for table in ("election_vote", "user_session", "password_history"):
            cur.execute("INSERT INTO nss.live_change_marker (table_name, change_seq) VALUES (%s, 0) "
                        "ON CONFLICT (table_name) DO NOTHING", (table,))
    r = member["client"].get(URL)
    assert r.status_code == 200
    assert r.json()["changed"]
    for entry in r.json()["changed"]:
        assert set(entry) == {"table_name", "change_seq"}
        assert entry["table_name"] in LIVE_FEED_TABLES
        assert isinstance(entry["change_seq"], int)


def test_scope_does_not_change_what_is_disclosed(authed_client, make_roleless_member, sakha_pk):
    """The reply is table-level and identical in shape for an admin and a role-less member."""
    member = make_roleless_member(sakha_pk)
    a = authed_client.get(URL).json()
    b = member["client"].get(URL).json()
    assert a == b


def test_reply_carries_no_record_text_only_table_names_and_numbers(authed_client):
    body = authed_client.get(URL).json()
    assert set(body) == {"changed"}
    assert all(set(c) == {"table_name", "change_seq"} for c in body["changed"])


def test_no_route_exposes_the_marker_table():
    """There is no API surface that writes the marker: only the SECURITY DEFINER trigger function does."""
    from api.main import app

    assert not [r for r in app.routes if "live_change_marker" in getattr(r, "path", "")]


@pytest.mark.parametrize("method", ["post", "patch", "delete", "put"])
def test_feed_is_read_only(authed_client, method):
    assert getattr(authed_client, method)(URL).status_code == 405
