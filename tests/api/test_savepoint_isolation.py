"""
NSS ERP — tests for the SAVEPOINT isolation architecture itself (tests/conftest.py).

conftest.py holds ONE session-scoped writer connection, wraps every test module
in `SAVEPOINT test_module_sp` (rolled back at module teardown) and overrides
both `get_connection` and `get_write_connection` to yield that same connection.

What is proven here, without depending on any other module or on run order:
  - both dependency overrides yield the very connection `write_conn` hands out;
  - a row written inside a module savepoint is invisible after ROLLBACK TO
    SAVEPOINT (mechanism, exercised on a nested savepoint so the real module
    savepoint of THIS module is never touched);
  - the connection is non-autocommit;
  - the API reads through the same connection, so uncommitted test rows are
    visible to it and vanish after the rollback;
  - the autouse per-test savepoint (`_test_savepoint`): a test that leaves the
    transaction ABORTED is rolled back to its own savepoint (its writes vanish,
    the connection works again for the next test), while a test that passes
    keeps its rows for later tests/fixtures of the module.

NOTE: nothing here commits. Cleanup is the very mechanism under test.
"""

import inspect
from uuid import uuid4

import pytest

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.main import app


pytestmark = pytest.mark.integration


def _count_persons(conn, person_id):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nss.person WHERE person_id = %s", (person_id,))
        return cur.fetchone()[0]


def _insert_person(conn, person_id):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO nss.person (person_id, first_name, last_name, email) "
            "VALUES (%s, 'Isolation', 'Probe', %s)",
            (person_id, f"{person_id.lower()}@example.test"),
        )


class TestDependencyOverrides:
    """Both connection dependencies resolve to the one shared test connection."""

    @staticmethod
    def _yielded(dependency):
        override = app.dependency_overrides[dependency]
        gen = override()
        assert inspect.isgenerator(gen)
        conn = next(gen)
        gen.close()  # the overrides neither commit nor roll back
        return conn

    def test_read_override_yields_the_session_connection(self, write_conn):
        assert self._yielded(get_connection) is write_conn

    def test_write_override_yields_the_session_connection(self, write_conn):
        assert self._yielded(get_write_connection) is write_conn

    def test_read_and_write_overrides_share_one_connection(self):
        assert self._yielded(get_connection) is self._yielded(get_write_connection)

    def test_closing_an_override_generator_does_not_close_the_connection(self, write_conn):
        self._yielded(get_write_connection)
        assert not write_conn.closed
        with write_conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)

    def test_connection_is_non_autocommit(self, write_conn):
        """Autocommit would make SAVEPOINT rollback impossible."""
        assert write_conn.autocommit is False


class TestSavepointRollback:
    """Rolling back to a savepoint undoes writes made after it."""

    def test_module_savepoint_exists_and_is_rollbackable(self, write_conn):
        """The autouse module fixture opened `test_module_sp`; a nested savepoint
        on top of it can be created and released without error."""
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT iso_probe_sp")
            cur.execute("RELEASE SAVEPOINT iso_probe_sp")

    def test_row_is_gone_after_rollback_to_savepoint(self, write_conn):
        person_id = f"TISO{uuid4().hex[:12].upper()}"
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT iso_rollback_sp")
        _insert_person(write_conn, person_id)
        assert _count_persons(write_conn, person_id) == 1
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT iso_rollback_sp")
        assert _count_persons(write_conn, person_id) == 0

    def test_per_test_savepoint_rollback_statement_undoes_writes(self, write_conn):
        """The exact statement the per-test fixture runs for a failed test. It is valid
        mid-test because ROLLBACK TO keeps the savepoint alive (the fixture RELEASEs it
        afterwards). The module savepoint itself is deliberately not touched here."""
        person_id = f"TISO{uuid4().hex[:12].upper()}"
        _insert_person(write_conn, person_id)
        assert _count_persons(write_conn, person_id) == 1
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT test_fn_sp")
        assert _count_persons(write_conn, person_id) == 0

    def test_released_savepoint_keeps_the_row_until_an_outer_rollback(self, write_conn):
        person_id = f"TISO{uuid4().hex[:12].upper()}"
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT iso_outer_sp")
            cur.execute("SAVEPOINT iso_inner_sp")
        _insert_person(write_conn, person_id)
        with write_conn.cursor() as cur:
            cur.execute("RELEASE SAVEPOINT iso_inner_sp")
        assert _count_persons(write_conn, person_id) == 1
        with write_conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT iso_outer_sp")
        assert _count_persons(write_conn, person_id) == 0

    def test_sequence_counter_increments_roll_back_too(self, write_conn):
        """Counter churn (id_sequence_master) made through next_id() is undone,
        which is what keeps business IDs from drifting across test modules."""
        with write_conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(current_value), 0) FROM nss.id_sequence_master")
            before = cur.fetchone()[0]
            cur.execute("SAVEPOINT iso_seq_sp")
            cur.execute("UPDATE nss.id_sequence_master SET current_value = current_value + 1")
            cur.execute("ROLLBACK TO SAVEPOINT iso_seq_sp")
            cur.execute("SELECT COALESCE(SUM(current_value), 0) FROM nss.id_sequence_master")
            assert cur.fetchone()[0] == before


class TestApiSeesTestWrites:
    """The API reads through the same connection, so uncommitted test rows are visible to it."""

    def test_api_sees_uncommitted_row_then_not_after_rollback(self, client, write_conn):
        person_id = f"TISOAPI{uuid4().hex[:10].upper()}"
        email = f"{person_id.lower()}@example.test"
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT iso_api_sp")
        try:
            _insert_person(write_conn, person_id)
            seen = client.post("/api/v1/register/check-duplicate", json={"email": email})
            assert seen.status_code == 200, seen.text
            assert seen.json()["email_exists"] is True
        finally:
            with write_conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT iso_api_sp")
        gone = client.post("/api/v1/register/check-duplicate", json={"email": email})
        assert gone.json()["email_exists"] is False


_CONTAINMENT = {}


class TestPerTestSavepointContainsDbErrors:
    """tests/conftest.py::_test_savepoint — run in order (the 2nd/4th depend on the 1st/3rd)."""

    def test_1_a_db_error_leaves_the_transaction_aborted_inside_this_test(self, write_conn):
        person_id = f"TISOERR{uuid4().hex[:9].upper()}"
        _CONTAINMENT["aborted_person"] = person_id
        _insert_person(write_conn, person_id)
        with pytest.raises(Exception):
            _insert_person(write_conn, person_id)  # duplicate person_id/email -> unique violation
        # Deliberately NOT cleaned up: the fixture must recover the connection.

    def test_2_the_next_test_gets_a_working_connection_and_the_aborted_tests_rows_are_gone(self, write_conn):
        assert _CONTAINMENT.get("aborted_person"), "test 1 did not run before this one"
        assert _count_persons(write_conn, _CONTAINMENT["aborted_person"]) == 0

    def test_3_a_passing_test_keeps_its_rows(self, write_conn):
        person_id = f"TISOKEEP{uuid4().hex[:8].upper()}"
        _CONTAINMENT["kept_person"] = person_id
        _insert_person(write_conn, person_id)

    def test_4_rows_of_an_earlier_passing_test_survive_until_the_module_ends(self, write_conn):
        assert _CONTAINMENT.get("kept_person"), "test 3 did not run before this one"
        assert _count_persons(write_conn, _CONTAINMENT["kept_person"]) == 1
