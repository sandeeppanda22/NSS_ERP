"""
NSS ERP - DB tests for the audit-actor foreign keys (owner decision 2026-11-04).

database/ddl/13_audit_actor_fk/01_audit_actor_fk_patch.sql (build Phase 13c) gives
EVERY `*_by_sangha_sevi_pk` column of every nss base table a FOREIGN KEY to
nss.sangha_sevi (sangha_sevi_pk) - NOT VALID where dangling historical values
exist, which still enforces every NEW or UPDATED row.

Behavioural probes run inside a SAVEPOINT that is always rolled back.
Written but NOT yet run against a database (collect-only).
"""

from uuid import uuid4

import psycopg2
import pytest

pytestmark = [pytest.mark.db, pytest.mark.integration]

ACTOR_COLUMNS_SQL = """
    SELECT c.relname, a.attname, a.attnum
      FROM pg_attribute a
      JOIN pg_class c     ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'nss' AND c.relkind IN ('r', 'p')
       AND a.attnum > 0 AND NOT a.attisdropped
       AND a.attname LIKE '%\\_by\\_sangha\\_sevi\\_pk'
     ORDER BY 1, 2
"""


def _actor_columns(conn):
    with conn.cursor() as cur:
        cur.execute(ACTOR_COLUMNS_SQL)
        return cur.fetchall()


def _has_fk(conn, table, attnum):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_constraint k
             WHERE k.conrelid = %s::regclass AND k.contype = 'f'
               AND k.confrelid = 'nss.sangha_sevi'::regclass
               AND k.conkey = ARRAY[%s]::smallint[]
            """,
            (f"nss.{table}", attnum),
        )
        return cur.fetchone() is not None


class TestEveryActorColumnHasAnFk:
    def test_actor_columns_exist(self, write_conn):
        # Sanity: the catalog probe must find the audit columns (dozens of tables).
        assert len(_actor_columns(write_conn)) > 100

    def test_every_actor_column_has_a_foreign_key_to_sangha_sevi(self, write_conn):
        # A failure here on a dev DB built before Phase 13c existed means: re-run the build (Phase 13c).
        missing = [f"{t}.{c}" for t, c, num in _actor_columns(write_conn) if not _has_fk(write_conn, t, num)]
        assert missing == [], f"actor columns without an FK to nss.sangha_sevi: {missing}"

    def test_known_columns_are_covered(self, write_conn):
        covered = {(t, c) for t, c, _ in _actor_columns(write_conn)}
        for pair in (
            ("person", "created_by_sangha_sevi_pk"),
            ("sangha_sevi", "updated_by_sangha_sevi_pk"),
            ("district", "submitted_by_sangha_sevi_pk"),
            ("property", "created_by_sangha_sevi_pk"),
            ("membership_change_request", "destination_decided_by_sangha_sevi_pk"),
        ):
            assert pair in covered, pair

    def test_event_log_actor_column_is_out_of_scope(self, write_conn):
        covered = {(t, c) for t, c, _ in _actor_columns(write_conn)}
        assert ("system_event_log", "actor_sangha_sevi_pk") not in covered


@pytest.mark.parametrize("table", ["sangha_sevi", "person", "family_group"])
def test_bogus_actor_is_rejected(write_conn, table):
    """An UPDATE that points an actor column at a non-existent Sangha Sevi must fail (NOT VALID still enforces)."""
    with write_conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM nss.{table}")
        if cur.fetchone()[0] == 0:
            pytest.skip(f"nss.{table} has no rows")
        cur.execute("SAVEPOINT actor_fk_probe")
        try:
            with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                cur.execute(
                    f"UPDATE nss.{table} SET updated_by_sangha_sevi_pk = %s "
                    f"WHERE ctid = (SELECT ctid FROM nss.{table} LIMIT 1)",
                    (str(uuid4()),),
                )
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT actor_fk_probe")
            cur.execute("RELEASE SAVEPOINT actor_fk_probe")


def test_null_actor_is_accepted(write_conn):
    # nss.organization / nss.master_data carry no *_by_sangha_sevi_pk columns, so probe person.
    with write_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM nss.person")
        if cur.fetchone()[0] == 0:
            pytest.skip("no person rows")
        cur.execute("SAVEPOINT actor_fk_null")
        try:
            cur.execute(
                "UPDATE nss.person SET updated_by_sangha_sevi_pk = NULL "
                "WHERE ctid = (SELECT ctid FROM nss.person LIMIT 1)"
            )
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT actor_fk_null")
            cur.execute("RELEASE SAVEPOINT actor_fk_null")


def test_patch_is_wired_in_all_build_scripts():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    needle = "13_audit_actor_fk"
    for rel in ("database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"):
        assert needle in (root / rel).read_text(encoding="utf-8"), rel
    for rel in ("database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "NOT VALID" in text and "_by_sangha_sevi_pk" in text, rel
