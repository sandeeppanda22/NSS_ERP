"""
Live-refresh change feed: GET /api/v1/live/changes (api/routers/live.py).

Owner decision 2026-11-03: data refreshes by itself. The endpoint only says
the latest change number (change_seq) of each whitelisted table - no record
data, no ids. Reads nss.live_change_marker, which statement-level triggers
(database/ddl/12_live_refresh/) bump at COMMIT time; there is no cursor.

Two kinds of test, in one file:
  * DB-FREE (run with `python3 -m pytest tests/api/test_live_changes.py
    --noconftest -k "Whitelist or RouteLimit or JsMapParity or Config or SqlParity"`):
    the whitelist, the per-user limit registration, the JS<->Python table-map
    parity, the SQL-trigger-list<->whitelist parity and the config default.
  * INTEGRATION (need the bootstrapped DB): auth, shape, whitelist
    enforcement, marker bump / per-table change numbers.

Written without a DB available: collection was verified, execution of the
integration classes was not.
"""
import re
from pathlib import Path

import pytest

import api.main  # noqa: F401  (imports every router so their @limiter.limit registrations exist)
from api.config import settings
from api.rate_limit import limiter
from api.routers.live import LIVE_FEED_TABLES

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "frontend" / "assets" / "js"
URL = "/api/v1/live/changes"
ROUTE = "api.routers.live.live_changes"

# A real table that is NOT on the whitelist (credential / session data must never be disclosed).
NON_LISTED_TABLE = "user_session"
LISTED_TABLE = "registration_claim"
TRIGGER_SQL = ROOT / "database" / "ddl" / "12_live_refresh" / "02_live_change_triggers.sql"


def _sql_watched_entries() -> list[tuple[str, list[str]]]:
    """The literal `watched TEXT[] := ARRAY[...]` list of the trigger file (the single SQL source)
    as [(table, ignored_update_columns)]; an entry is 'table' or 'table!col1,col2'."""
    src = TRIGGER_SQL.read_text()
    block = re.search(r"watched TEXT\[\] := ARRAY\[(.*?)\];", src, re.DOTALL).group(1)
    block = "\n".join(line.split("--")[0] for line in block.splitlines())
    return [(m.group(1), m.group(2).split(",") if m.group(2) else [])
            for m in re.finditer(r"'([a-z_]+)(?:!([a-z_,]+))?'", block)]


def _sql_watched_tables() -> set[str]:
    return {t for t, _ in _sql_watched_entries()}


def _js_table_map(filename: str) -> dict[str, list[str]]:
    """Parse the `LIVE_TABLE_TABS:begin/end` block of a page script into {table: [tabs]}."""
    src = (JS / filename).read_text()
    block = re.search(r"// LIVE_TABLE_TABS:begin\n(.*?)// LIVE_TABLE_TABS:end", src, re.DOTALL).group(1)
    return {
        m.group(1): re.findall(r'"([A-Za-z]+)"', m.group(2))
        for m in re.finditer(r"^\s+([a-z_]+): \[(.*?)\],?\s*$", block, re.MULTILINE)
    }


class TestWhitelist:
    def test_is_a_nonempty_frozenset_of_plain_table_names(self):
        assert isinstance(LIVE_FEED_TABLES, frozenset) and LIVE_FEED_TABLES
        assert all(re.fullmatch(r"[a-z_]+", t) for t in LIVE_FEED_TABLES)

    @pytest.mark.parametrize("table", [
        "user_session", "password_history", "password_reset_token", "role_permission",
        "system_event_log", "field_change_log", "id_sequence_master", "credential_sequence_counter",
        "correspondence_sequence_counter", "sakha_local_number_counter", "live_change_marker",
    ])
    def test_internal_credential_and_session_tables_are_never_listed(self, table):
        assert table not in LIVE_FEED_TABLES

    @pytest.mark.parametrize("table", ["election_vote", "election_vote_participation"])
    def test_ballot_tables_are_withheld(self, table):
        assert table not in LIVE_FEED_TABLES

    def test_attendance_tables_are_excluded_from_the_feed(self):
        assert not [t for t in LIVE_FEED_TABLES if "attendance" in t and t != "darshak_attendance_registration"]

    def test_first_batch_modules_are_covered(self):
        for table in ("registration_claim", "correspondence", "body_member_assignment", "election", "organization",
                      "property", "asset", "custodianship", "maintenance_record", "property_statutory_record",
                      "property_document", "asset_document", "organization_reparent_request",
                      "organization_reparent_step", "correspondence_approval_step", "membership_change_request"):
            assert table in LIVE_FEED_TABLES, table

    def test_second_batch_tables_are_covered(self):
        for table in ("user_account", "user_role", "admin_scope", "person", "sangha_sevi", "master_data",
                      "country", "postal_code", "system_setting", "festival_calendar_date",
                      "family_relationship", "anumati_patra", "membership_journey_event"):
            assert table in LIVE_FEED_TABLES, table

    def test_live_module_has_no_audit_log_look_back_left(self):
        src = (ROOT / "api" / "routers" / "live.py").read_text()
        assert "LIVE_OVERLAP_SECONDS" not in src and "system_event_log" not in src.split('"""', 2)[2]


class TestSqlParity:
    """Python whitelist == the table list of the SQL trigger file (one list per layer, guarded here)."""

    def test_trigger_list_equals_the_python_whitelist(self):
        sql = _sql_watched_tables()
        assert sql == set(LIVE_FEED_TABLES), (sql ^ set(LIVE_FEED_TABLES))

    def test_trigger_list_has_no_duplicates(self):
        names = [t for t, _ in _sql_watched_entries()]
        assert len(names) == len(set(names))

    def test_only_user_account_ignores_update_columns_and_they_are_the_login_churn_set(self):
        scoped = {t: cols for t, cols in _sql_watched_entries() if cols}
        assert set(scoped) == {"user_account"}
        assert set(scoped["user_account"]) == {
            "failed_login_attempts", "locked_until", "last_failed_login_at", "last_login_at", "updated_at"}

    def test_ignored_columns_are_real_columns_and_never_meaningful_ones(self):
        ddl = (ROOT / "database" / "ddl" / "06_authentication" / "01_user_account.sql").read_text()
        for _, cols in _sql_watched_entries():
            for col in cols:
                assert re.search(rf"^\s+{col}\s", ddl, re.MULTILINE), col
                assert col not in {"account_status", "password_hash", "is_active", "deleted_at",
                                   "force_password_change", "password_expires_at", "person_pk"}

    def test_login_statements_touch_only_ignored_columns(self):
        """The two routine login UPDATEs in auth.py must name ONLY ignored columns; no other
        user_account UPDATE in auth.py may be one (password changes name password_hash)."""
        ignored = set(dict(_sql_watched_entries())["user_account"])
        src = (ROOT / "api" / "routers" / "auth.py").read_text()
        routine = 0
        for m in re.finditer(r"UPDATE nss\.user_account\s+SET(.*?)WHERE", src, re.DOTALL):
            cols = set(re.findall(r"^\s*([a-z_]+)\s*=", m.group(1), re.MULTILINE))
            if cols <= ignored:
                routine += 1
        assert routine == 2  # failed attempt + successful login

    def test_audit_trigger_excludes_the_marker_table(self):
        src = (ROOT / "database" / "ddl" / "01_foundation" / "15_audit_trigger.sql").read_text()
        assert "'live_change_marker'" in src.split("excluded_tables TEXT[] := ARRAY[", 1)[1].split("];", 1)[0]

    def test_marker_ddl_is_one_table_and_one_global_sequence(self):
        src = (ROOT / "database" / "ddl" / "12_live_refresh" / "01_live_change_marker.sql").read_text()
        assert "CREATE SEQUENCE IF NOT EXISTS nss.live_change_seq" in src
        assert len(re.findall(r"CREATE TABLE", src)) == 1 and "nss.live_change_marker" in src

    def test_build_scripts_wire_both_files_identically(self):
        for rel in ("database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"):
            src = (ROOT / rel).read_text()
            assert "12_live_refresh" in src and "01_live_change_marker.sql" in src and "02_live_change_triggers.sql" in src, rel
            # triggers run after Assets & Property (every watched table exists) and before the audit phase
            assert src.index("12_assets_property_terminal_custody_patch") < src.index("02_live_change_triggers.sql"), rel
            assert src.index("02_live_change_triggers.sql") < src.index("15_audit_trigger.sql"), rel


class TestRouteLimit:
    def test_live_changes_has_its_own_per_user_limit_that_replaces_the_global_one(self):
        entries = limiter._route_limits.get(ROUTE)
        assert entries, "live_changes must carry @limiter.limit(...)"
        assert all(lim.override_defaults for lim in entries)
        assert str(entries[0].limit).startswith("60 per 1 minute")  # default of LIVE_CHANGES_RATE_LIMIT

    def test_setting_default(self):
        assert settings.LIVE_CHANGES_RATE_LIMIT == "60/minute"


class TestConfig:
    def test_env_example_documents_the_setting(self):
        assert "LIVE_CHANGES_RATE_LIMIT=60/minute" in (ROOT / "api" / ".env.example").read_text()

    def test_router_is_registered_once_with_one_get_route(self):
        from api.main import app

        routes = [r for r in app.routes if getattr(r, "path", "") == URL]
        assert len(routes) == 1 and routes[0].methods == {"GET"}


class TestJsMapParity:
    """The Python whitelist is authoritative: every table a page script maps must be on it."""

    @pytest.mark.parametrize("script", ["admin.js", "dashboard.js"])
    def test_every_mapped_table_is_whitelisted(self, script):
        mapping = _js_table_map(script)
        assert mapping, f"no LIVE_TABLE_TABS block parsed from {script}"
        assert not (set(mapping) - LIVE_FEED_TABLES), set(mapping) - LIVE_FEED_TABLES

    @pytest.mark.parametrize("script", ["admin.js", "dashboard.js"])
    def test_every_mapped_tab_has_a_reload_hook(self, script):
        src = (JS / script).read_text()
        config = re.search(r"const LIVE_REFRESH_CONFIG = \{(.*)", src, re.DOTALL).group(1)
        tabs_block = config[config.index("tabs: {"):]
        for tabs in _js_table_map(script).values():
            for tab in tabs:
                assert re.search(rf"^        {tab}: ", tabs_block, re.MULTILINE), f"{script}: tab {tab} has no LIVE_REFRESH_CONFIG entry"

    def test_whitelisted_tables_are_real_tables(self):
        ddl = "\n".join(p.read_text() for p in (ROOT / "database" / "ddl").rglob("*.sql"))
        for table in LIVE_FEED_TABLES:
            assert re.search(rf"CREATE TABLE (IF NOT EXISTS )?nss\.{table}\b", ddl), table

    def test_no_attendance_or_ballot_table_is_mapped(self):
        for script in ("admin.js", "dashboard.js"):
            for table in _js_table_map(script):
                assert "attendance" not in table.replace("darshak_attendance_registration", "")
                assert not table.startswith("election_vote")


# ── Integration ────────────────────────────────────────────────────────────

def _touch(write_conn, table):
    """A statement-level write that changes no row (zero-row INSERT..SELECT) - the statement trigger still fires once."""
    with write_conn.cursor() as cur:
        cur.execute(f"INSERT INTO nss.{table} SELECT * FROM nss.{table} WHERE FALSE")


def _seqs(resp) -> dict[str, int]:
    assert resp.status_code == 200, resp.text
    return {c["table_name"]: c["change_seq"] for c in resp.json()["changed"]}


@pytest.mark.integration
class TestAuth:
    def test_anonymous_gets_401(self, anon_client):
        assert anon_client.get(URL).status_code == 401

    def test_garbage_token_gets_401(self, anon_client):
        assert anon_client.get(URL, headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401

    def test_any_logged_in_user_is_admitted_no_module_permission_needed(self, authed_client):
        assert authed_client.get(URL).status_code == 200


@pytest.mark.integration
class TestResponseShape:
    def test_body_is_a_list_of_table_name_and_change_seq_only(self, authed_client):
        body = authed_client.get(URL).json()
        assert set(body) == {"changed"}
        assert body["changed"], "seeded markers must exist for every watched table"
        for entry in body["changed"]:
            assert set(entry) == {"table_name", "change_seq"}
            assert isinstance(entry["change_seq"], int)

    def test_every_watched_table_has_a_marker_after_a_build(self, authed_client):
        assert set(_seqs(authed_client.get(URL))) == set(LIVE_FEED_TABLES)

    def test_a_legacy_since_parameter_is_ignored(self, authed_client):
        assert authed_client.get(URL, params={"since": "yesterday-ish"}).status_code == 200


@pytest.mark.integration
class TestChangeNumbers:
    def test_a_write_raises_that_tables_change_seq_and_only_that_one(self, authed_client, write_conn):
        before = _seqs(authed_client.get(URL))
        _touch(write_conn, LISTED_TABLE)
        after = _seqs(authed_client.get(URL))
        assert after[LISTED_TABLE] > before[LISTED_TABLE]
        assert {t: v for t, v in after.items() if t != LISTED_TABLE} == {t: v for t, v in before.items() if t != LISTED_TABLE}

    def test_change_numbers_are_unique_across_tables(self, authed_client, write_conn):
        _touch(write_conn, LISTED_TABLE)
        _touch(write_conn, "organization")
        seqs = _seqs(authed_client.get(URL))
        assert len(set(seqs.values())) == len(seqs)

    def test_a_non_watched_table_write_changes_nothing(self, authed_client, write_conn):
        before = _seqs(authed_client.get(URL))
        _touch(write_conn, NON_LISTED_TABLE)
        assert _seqs(authed_client.get(URL)) == before


@pytest.mark.integration
class TestWhitelistEnforced:
    def test_a_marker_row_outside_the_whitelist_is_never_returned(self, authed_client, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("INSERT INTO nss.live_change_marker (table_name, change_seq) VALUES (%s, 0)"
                        " ON CONFLICT (table_name) DO NOTHING", ("election_vote",))
        names = set(_seqs(authed_client.get(URL)))
        assert "election_vote" not in names and names <= LIVE_FEED_TABLES

    def test_installed_triggers_match_the_whitelist(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT c.relname FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid "
                        "WHERE g.tgname = 'trg_live_change_marker' AND NOT g.tgisinternal")
            assert {r[0] for r in cur.fetchall()} == set(LIVE_FEED_TABLES)

    def test_user_account_trigger_is_column_scoped_and_skips_login_churn(self, write_conn):
        ignored = set(dict(_sql_watched_entries())["user_account"])
        with write_conn.cursor() as cur:
            cur.execute("SELECT a.attname FROM pg_trigger g JOIN pg_attribute a ON a.attrelid = g.tgrelid "
                        "AND a.attnum = ANY (g.tgattr::int2[]) "
                        "WHERE g.tgname = 'trg_live_change_marker' AND g.tgrelid = 'nss.user_account'::regclass")
            cols = {r[0] for r in cur.fetchall()}
        assert cols and not (cols & ignored) and {"account_status", "password_hash", "is_active"} <= cols


@pytest.mark.integration
class TestUserAccountChurn:
    """Login bookkeeping must not bump the marker; admin-visible changes must."""

    def _one_account(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT user_account_pk FROM nss.user_account LIMIT 1")
            return cur.fetchone()[0]

    def test_login_columns_do_not_bump_but_status_does(self, authed_client, write_conn):
        pk = self._one_account(write_conn)
        before = _seqs(authed_client.get(URL))["user_account"]
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.user_account SET failed_login_attempts = failed_login_attempts, "
                        "locked_until = locked_until, last_login_at = last_login_at, updated_at = NOW() "
                        "WHERE user_account_pk = %s", (pk,))
        assert _seqs(authed_client.get(URL))["user_account"] == before
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.user_account SET account_status = account_status, updated_at = NOW() "
                        "WHERE user_account_pk = %s", (pk,))
        assert _seqs(authed_client.get(URL))["user_account"] > before
