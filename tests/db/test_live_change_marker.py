"""
NSS ERP - DB tests for the live-refresh change marker (owner decision
2026-11-03; database/ddl/12_live_refresh/).

  - nss.live_change_marker + nss.live_change_seq exist, one marker row per
    watched table, a trigger on exactly those tables;
  - the statement-level trigger bumps the table's marker ONCE per statement
    (also for a multi-row or a zero-row statement), only that table's marker,
    with a number taken from the one global sequence;
  - the bump is part of the writing transaction: it disappears on rollback;
  - the API's write role runs the trigger (SECURITY DEFINER) and the read
    role can SELECT the markers;
  - the marker table itself is not audited;
  - user_account's trigger is column-scoped: login bookkeeping columns do not
    bump the marker, an account status / password / soft-delete change does.

The watched list is parsed from the trigger SQL file (the single SQL source),
not repeated here. Every statement runs inside a SAVEPOINT that is rolled
back, so the seed-less test DB is left untouched.

Written without the project DB: executed only against a throwaway PostgreSQL
(see tests/README.md); not run in pytest here.
"""

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.db, pytest.mark.integration]

ROOT = Path(__file__).resolve().parents[2]
TRIGGER_SQL = ROOT / "database" / "ddl" / "12_live_refresh" / "02_live_change_triggers.sql"
# Entries are 'table' or 'table!ignored,update,columns' (routine churn; see the trigger file).
WATCHED = sorted(set(re.findall(
    r"'([a-z_]+)(?:![a-z_,]+)?'",
    "\n".join(l.split("--")[0] for l in re.search(
        r"watched TEXT\[\] := ARRAY\[(.*?)\];", TRIGGER_SQL.read_text(), re.DOTALL).group(1).splitlines()),
)))
TABLE = "registration_claim"
OTHER = "organization"


def _seq(conn, table):
    with conn.cursor() as cur:
        cur.execute("SELECT change_seq FROM nss.live_change_marker WHERE table_name = %s", (table,))
        row = cur.fetchone()
        return row[0] if row else None


def _all(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT table_name, change_seq FROM nss.live_change_marker")
        return dict(cur.fetchall())


def _touch(conn, table):
    """Zero-row INSERT..SELECT: writes nothing but fires the statement-level trigger once."""
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO nss.{table} SELECT * FROM nss.{table} WHERE FALSE")


class TestStructure:
    def test_table_and_sequence_exist(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT to_regclass('nss.live_change_marker') IS NOT NULL, to_regclass('nss.live_change_seq') IS NOT NULL")
            assert cur.fetchone() == (True, True)

    def test_every_watched_table_has_exactly_one_trigger_and_one_marker_row(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT c.relname, count(*) FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid "
                        "WHERE g.tgname = 'trg_live_change_marker' AND NOT g.tgisinternal GROUP BY 1")
            triggers = dict(cur.fetchall())
        assert sorted(triggers) == WATCHED
        assert set(triggers.values()) == {1}
        assert set(WATCHED) <= set(_all(write_conn))

    def test_trigger_is_statement_level_after_insert_update_delete(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT tgtype & 1, tgtype & 2, tgtype & 4, tgtype & 8, tgtype & 16 "
                        "FROM pg_trigger WHERE tgname = 'trg_live_change_marker' AND NOT tgisinternal")
            # not ROW (1), not BEFORE (2), INSERT (4), DELETE (8), UPDATE (16)
            assert cur.fetchall() == [(0, 0, 4, 8, 16)]

    def test_ballot_tables_are_not_watched(self, write_conn):
        assert not {"election_vote", "election_vote_participation"} & set(WATCHED)
        with write_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid "
                        "WHERE g.tgname = 'trg_live_change_marker' AND c.relname LIKE 'election_vote%'")
            assert cur.fetchone()[0] == 0

    def test_function_is_security_definer_with_pinned_search_path(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT prosecdef, proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                        "WHERE n.nspname = 'nss' AND p.proname = 'fn_live_change_marker'")
            secdef, config = cur.fetchone()
        assert secdef is True
        assert any(c.startswith("search_path=") for c in (config or []))

    def test_backend_role_can_read_the_markers(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT has_table_privilege('nss_db_backend', 'nss.live_change_marker', 'SELECT')")
            assert cur.fetchone()[0] is True

    def test_marker_table_is_not_audited(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid = 'nss.live_change_marker'::regclass AND NOT tgisinternal")
            assert cur.fetchone()[0] == 0


class TestBehaviour:
    def test_a_statement_raises_only_its_tables_marker(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm1")
        before = _all(write_conn)
        _touch(write_conn, TABLE)
        after = _all(write_conn)
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm1")
        assert after[TABLE] > before[TABLE]
        assert {k: v for k, v in after.items() if k != TABLE} == {k: v for k, v in before.items() if k != TABLE}

    def test_numbers_come_from_one_global_increasing_sequence(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm2")
        _touch(write_conn, TABLE)
        a = _seq(write_conn, TABLE)
        _touch(write_conn, OTHER)
        b = _seq(write_conn, OTHER)
        _touch(write_conn, TABLE)
        c = _seq(write_conn, TABLE)
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm2")
        assert a < b < c

    def test_a_multi_row_statement_bumps_once(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm3")
            cur.execute("SELECT count(*) FROM nss.organization")
            if cur.fetchone()[0] < 3:
                cur.execute("ROLLBACK TO SAVEPOINT lcm3")
                pytest.skip("needs at least 3 organization rows")
        # Marker numbers advance by the same step for a 1-row and a 3-row UPDATE.
        steps = []
        for limit in (1, 3):
            before = _seq(write_conn, "organization")
            with write_conn.cursor() as cur:
                cur.execute("UPDATE nss.organization SET updated_at = updated_at WHERE organization_pk IN "
                            "(SELECT organization_pk FROM nss.organization ORDER BY organization_pk LIMIT %s)", (limit,))
            steps.append(_seq(write_conn, "organization") - before)
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm3")
        assert steps[0] == steps[1] > 0

    def test_a_zero_row_statement_still_bumps(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm4")
        before = _seq(write_conn, TABLE)
        _touch(write_conn, TABLE)
        after = _seq(write_conn, TABLE)
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm4")
        assert after > before

    def test_the_bump_rolls_back_with_the_transaction(self, write_conn):
        before = _all(write_conn)
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm5")
        _touch(write_conn, TABLE)
        assert _seq(write_conn, TABLE) > before[TABLE]
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm5")
        assert _all(write_conn) == before

    def test_a_table_outside_the_list_has_no_marker_effect(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm6")
        before = _all(write_conn)
        _touch(write_conn, "user_session")
        after = _all(write_conn)
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm6")
        assert after == before


class TestColumnScopedTrigger:
    """user_account!failed_login_attempts,locked_until,last_failed_login_at,last_login_at,updated_at"""

    def _account(self, conn):
        with conn.cursor() as cur:
            cur.execute("SELECT user_account_pk FROM nss.user_account ORDER BY created_at LIMIT 1")
            row = cur.fetchone()
        assert row, "needs at least one user_account (the bootstrap admin)"
        return row[0]

    def test_trigger_update_columns_exclude_the_login_churn_set(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SELECT array_agg(a.attname::text) FROM pg_trigger g JOIN pg_attribute a "
                        "ON a.attrelid = g.tgrelid AND a.attnum = ANY (g.tgattr::int2[]) "
                        "WHERE g.tgname = 'trg_live_change_marker' AND g.tgrelid = 'nss.user_account'::regclass")
            cols = set(cur.fetchone()[0])
        assert not cols & {"failed_login_attempts", "locked_until", "last_failed_login_at", "last_login_at", "updated_at"}
        assert {"account_status", "password_hash", "is_active", "force_password_change", "person_pk"} <= cols

    def test_login_bookkeeping_update_does_not_bump(self, write_conn):
        pk = self._account(write_conn)
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm_ua1")
        before = _seq(write_conn, "user_account")
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.user_account SET failed_login_attempts = 0, locked_until = NULL, "
                        "last_login_at = NOW(), last_failed_login_at = NULL, updated_at = NOW() "
                        "WHERE user_account_pk = %s", (pk,))
        after = _seq(write_conn, "user_account")
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm_ua1")
        assert after == before

    @pytest.mark.parametrize("assignment", [
        "account_status = account_status", "force_password_change = force_password_change",
        "password_expires_at = password_expires_at", "is_active = is_active",
    ])
    def test_a_meaningful_column_update_bumps(self, write_conn, assignment):
        pk = self._account(write_conn)
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm_ua2")
        before = _seq(write_conn, "user_account")
        with write_conn.cursor() as cur:
            cur.execute(f"UPDATE nss.user_account SET {assignment}, updated_at = NOW() WHERE user_account_pk = %s", (pk,))
        after = _seq(write_conn, "user_account")
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm_ua2")
        assert after > before

    def test_insert_and_delete_still_bump(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT lcm_ua3")
        before = _seq(write_conn, "user_account")
        _touch(write_conn, "user_account")
        after = _seq(write_conn, "user_account")
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT lcm_ua3")
        assert after > before
