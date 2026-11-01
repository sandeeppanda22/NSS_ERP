"""
NSS ERP — DB tests for the home-affiliation guard and the SQL allocator.

database/ddl/05_membership/20_home_affiliation_guard.sql (owner 2026-11-01):
every ACTIVE, non-system Sangha Sevi must have exactly one open home
membership_sakha_affiliation (with a non-empty Local Sakha ID) at its
organization_pk by COMMIT. The constraint triggers are DEFERRABLE INITIALLY
DEFERRED; the test transaction never commits, so each test flips them to
IMMEDIATE inside a SAVEPOINT to force the check, then restores DEFERRED.

database/ddl/05_membership/19_sakha_local_number_allocator.sql:
nss.fn_next_sakha_local_number().

Written but NOT yet run against a database (collect-only).
"""

from uuid import uuid4

import psycopg2
import pytest

pytestmark = [pytest.mark.db, pytest.mark.integration]

TRIGGERS = ("ctrg_sevi_home_affiliation", "ctrg_affiliation_home_affiliation")


@pytest.fixture(scope="module")
def refs(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT
          (SELECT md.master_data_pk FROM nss.master_data md
             JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR' AND md.is_active LIMIT 1),
          (SELECT md.master_data_pk FROM nss.master_data md
             JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active LIMIT 1)
    """)
    mtype, mstatus = cur.fetchone()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active
        ORDER BY o.organization_name LIMIT 2
    """)
    orgs = [str(r[0]) for r in cur.fetchall()]
    cur.close()
    if mtype is None or mstatus is None or len(orgs) < 2:
        pytest.skip("Need REGULAR/ACTIVE master data and two Sakhas.")
    return {"type": str(mtype), "status": str(mstatus), "org_a": orgs[0], "org_b": orgs[1]}


def _sevi(cur, refs, org):
    suffix = uuid4().hex[:10].upper()
    cur.execute(
        "INSERT INTO nss.person (person_id, first_name, last_name, email) VALUES (%s,%s,%s,%s) RETURNING person_pk",
        (f"HAG{suffix}", "Guard", suffix, f"hag.{suffix.lower()}@example.test"),
    )
    person = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO nss.sangha_sevi (sangha_sevi_id, person_pk, membership_type_master_data_pk,
                                     membership_status_master_data_pk, organization_pk)
        VALUES (%s, %s, %s, %s, %s) RETURNING sangha_sevi_pk
        """,
        (f"HAGS{suffix}", person, refs["type"], refs["status"], org),
    )
    return str(cur.fetchone()[0])


def _aff(cur, sevi, org, local_id, *, status="ACTIVE"):
    closed = status == "ARCHIVED"
    cur.execute(
        """
        INSERT INTO nss.membership_sakha_affiliation
            (sangha_sevi_pk, organization_pk, local_sakha_erp_id, effective_from,
             effective_to, affiliation_status, source_event_type)
        VALUES (%s, %s, %s, DATE '2020-01-01', CASE WHEN %s THEN DATE '2021-01-01' END, %s, 'ENROLLMENT')
        RETURNING membership_sakha_affiliation_pk
        """,
        (sevi, org, local_id, closed, status),
    )
    return str(cur.fetchone()[0])


def _commit_time_check(conn):
    """Force the deferred guard to run now; True if it passes, else the error."""
    cur = conn.cursor()
    cur.execute("SAVEPOINT sp_guard_probe")
    try:
        cur.execute(f"SET CONSTRAINTS {', '.join(TRIGGERS)} IMMEDIATE")
        return None
    except psycopg2.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT sp_guard_probe")
        return exc
    finally:
        try:
            cur.execute(f"SET CONSTRAINTS {', '.join(TRIGGERS)} DEFERRED")
        except psycopg2.Error:
            pass
        cur.close()


def _lid():
    return f"HG{uuid4().hex[:8].upper()}"


class TestGuardDefinition:
    def test_both_triggers_are_deferrable_initially_deferred(self, write_conn):
        cur = write_conn.cursor()
        cur.execute(
            "SELECT tgname, tgdeferrable, tginitdeferred FROM pg_trigger "
            "WHERE tgname = ANY(%s) AND NOT tgisinternal", (list(TRIGGERS),))
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        cur.close()
        assert set(rows) == set(TRIGGERS)
        assert all(v == (True, True) for v in rows.values())

    def test_unrelated_sevi_updates_do_not_fire_the_guard(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgname = 'ctrg_sevi_home_affiliation'")
        definition = cur.fetchone()[0]
        cur.close()
        assert "UPDATE OF organization_pk, is_active, is_system_account" in definition


class TestGuardBehaviour:
    def test_sevi_without_affiliation_is_refused(self, write_conn, refs):
        cur = write_conn.cursor()
        _sevi(cur, refs, refs["org_a"])
        cur.close()
        assert _commit_time_check(write_conn) is not None

    def test_sevi_with_home_affiliation_passes(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        _aff(cur, s, refs["org_a"], _lid())
        cur.close()
        assert _commit_time_check(write_conn) is None

    def test_blank_local_id_does_not_satisfy_the_guard(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        _aff(cur, s, refs["org_a"], " ")
        cur.close()
        assert _commit_time_check(write_conn) is not None

    def test_affiliation_at_a_different_org_does_not_count_as_home(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        _aff(cur, s, refs["org_b"], _lid())  # darshak-style row only
        cur.close()
        assert _commit_time_check(write_conn) is not None

    def test_darshak_row_alongside_home_row_passes(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        _aff(cur, s, refs["org_a"], _lid())
        _aff(cur, s, refs["org_b"], _lid())
        cur.close()
        assert _commit_time_check(write_conn) is None

    def test_closing_home_affiliation_without_replacement_is_refused(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        aff = _aff(cur, s, refs["org_a"], _lid())
        assert _commit_time_check(write_conn) is None
        cur.execute(
            "UPDATE nss.membership_sakha_affiliation SET effective_to = CURRENT_DATE, "
            "affiliation_status = 'ARCHIVED' WHERE membership_sakha_affiliation_pk = %s", (aff,))
        cur.close()
        assert _commit_time_check(write_conn) is not None

    def test_transfer_in_one_transaction_passes(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        aff = _aff(cur, s, refs["org_a"], _lid())
        assert _commit_time_check(write_conn) is None
        cur.execute(
            "UPDATE nss.membership_sakha_affiliation SET effective_to = CURRENT_DATE, "
            "affiliation_status = 'ARCHIVED' WHERE membership_sakha_affiliation_pk = %s", (aff,))
        _aff(cur, s, refs["org_b"], _lid())
        cur.execute("UPDATE nss.sangha_sevi SET organization_pk = %s WHERE sangha_sevi_pk = %s",
                    (refs["org_b"], s))
        cur.close()
        assert _commit_time_check(write_conn) is None

    def test_moving_home_org_without_new_affiliation_is_refused(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        _aff(cur, s, refs["org_a"], _lid())
        assert _commit_time_check(write_conn) is None
        cur.execute("UPDATE nss.sangha_sevi SET organization_pk = %s WHERE sangha_sevi_pk = %s",
                    (refs["org_b"], s))
        cur.close()
        assert _commit_time_check(write_conn) is not None

    def test_soft_deleted_sevi_is_exempt(self, write_conn, refs):
        cur = write_conn.cursor()
        s = _sevi(cur, refs, refs["org_a"])
        cur.execute(
            "UPDATE nss.sangha_sevi SET is_active = FALSE, deleted_at = NOW() WHERE sangha_sevi_pk = %s", (s,))
        cur.close()
        assert _commit_time_check(write_conn) is None


class TestSqlAllocator:
    def _next(self, conn, org, prefix, ns="REGULAR"):
        cur = conn.cursor()
        cur.execute("SELECT nss.fn_next_sakha_local_number(%s, %s, %s)", (org, ns, prefix))
        n = cur.fetchone()[0]
        cur.close()
        return n

    def test_increments_per_call(self, write_conn, refs):
        a = self._next(write_conn, refs["org_a"], "ZZ")
        b = self._next(write_conn, refs["org_a"], "ZZ")
        assert b == a + 1

    def test_skips_existing_ids_including_archived(self, write_conn, refs):
        cur = write_conn.cursor()
        probe = self._next(write_conn, refs["org_b"], "QQ")
        s = _sevi(cur, refs, refs["org_b"])
        _aff(cur, s, refs["org_b"], f"QQ{probe + 1}", status="ARCHIVED")
        cur.close()
        nxt = self._next(write_conn, refs["org_b"], "QQ")
        assert nxt == probe + 2

    def test_namespaces_have_independent_counters(self, write_conn, refs):
        r1 = self._next(write_conn, refs["org_a"], "NS", "REGULAR")
        d1 = self._next(write_conn, refs["org_a"], "NSD", "DARSHAK")
        r2 = self._next(write_conn, refs["org_a"], "NS", "REGULAR")
        assert r2 == r1 + 1
        assert d1 >= 1
