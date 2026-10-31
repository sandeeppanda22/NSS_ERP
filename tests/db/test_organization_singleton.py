"""
NSS ERP — DB tests for the organization singleton trigger.

database/ddl/02_organization/08_organization_singleton_trigger.sql
(owner decision 2026-10-30): at most ONE ACTIVE organization for each of
KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA, ADVISORY_BOARD (by type) and for the
central Mahila Sangha (MAHILA_SANGHA whose parent is a KENDRA). Local per-Sakha
Mahila Sanghas (parent = a Sakha) stay unrestricted. INSERT and UPDATE OF
type / is_active / parent are guarded; unrelated updates never fire it.

Each attempt runs in its own SAVEPOINT so a trigger rejection does not abort
the surrounding test transaction. Written but NOT yet run against a database.
"""

from uuid import uuid4

import psycopg2
import pytest

pytestmark = [pytest.mark.db, pytest.mark.integration]

SINGLETON_TYPES = ["KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA", "ADVISORY_BOARD"]


def _md_pk(cur, category, code):
    cur.execute(
        """
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = %s AND md.value_code = %s AND md.is_active = TRUE
        """,
        (category, code),
    )
    row = cur.fetchone()
    if row is None:
        pytest.skip(f"{category}/{code} not seeded.")
    return str(row[0])


@pytest.fixture(scope="module")
def refs(write_conn):
    with write_conn.cursor() as cur:
        out = {"status": _md_pk(cur, "STATUS", "ACTIVE")}
        for code in SINGLETON_TYPES + ["MAHILA_SANGHA", "SAKHA_SANGHA"]:
            out[code] = _md_pk(cur, "ORGANIZATION_TYPE", code)
    return out


def _insert(conn, refs, type_code, *, parent=None, is_active=True):
    cur = conn.cursor()
    cur.execute("SAVEPOINT sp_org")
    try:
        cur.execute(
            """
            INSERT INTO nss.organization
                (organization_name, organization_type_master_data_pk, status_master_data_pk,
                 parent_organization_pk, is_active)
            VALUES (%s, %s, %s, %s, %s) RETURNING organization_pk
            """,
            (f"ORGSINGLETON {uuid4().hex[:8]}", refs[type_code], refs["status"], parent, is_active),
        )
        pk = str(cur.fetchone()[0])
        cur.execute("RELEASE SAVEPOINT sp_org")
        return pk, None
    except psycopg2.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT sp_org")
        return None, exc
    finally:
        cur.close()


def _update(conn, sql, params):
    cur = conn.cursor()
    cur.execute("SAVEPOINT sp_org_upd")
    try:
        cur.execute(sql, params)
        cur.execute("RELEASE SAVEPOINT sp_org_upd")
        return None
    except psycopg2.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT sp_org_upd")
        return exc
    finally:
        cur.close()


def _ensure_one_active(conn, refs, type_code, *, parent=None):
    """Seeded singletons exist already; on a bare DB create the one allowed row."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT organization_pk FROM nss.organization "
            "WHERE organization_type_master_data_pk = %s AND is_active",
            (refs[type_code],),
        )
        row = cur.fetchone()
    if row is not None:
        return str(row[0])
    pk, err = _insert(conn, refs, type_code, parent=parent)
    assert err is None, err
    return pk


def _kendra(conn, refs):
    return _ensure_one_active(conn, refs, "KENDRA")


def _central_mahila(conn, refs):
    """The one active MAHILA_SANGHA under the Kendra (created if none)."""
    kendra = _kendra(conn, refs)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT organization_pk FROM nss.organization "
            "WHERE organization_type_master_data_pk = %s AND parent_organization_pk = %s AND is_active",
            (refs["MAHILA_SANGHA"], kendra),
        )
        row = cur.fetchone()
    if row is not None:
        return str(row[0]), kendra
    pk, err = _insert(conn, refs, "MAHILA_SANGHA", parent=kendra)
    assert err is None, err
    return pk, kendra


def test_trigger_exists_and_old_one_is_gone(write_conn):
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
            "WHERE t.tgname = 'trg_enforce_organization_singleton' AND NOT t.tgisinternal"
        )
        row = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) FROM pg_trigger WHERE tgname = 'trg_enforce_advisory_board_singleton' "
            "AND NOT tgisinternal"
        )
        old = cur.fetchone()[0]
    assert row, "organization singleton trigger is missing"
    assert "INSERT" in row[0] and "UPDATE" in row[0] and "parent_organization_pk" in row[0]
    assert old == 0, "the v1.0 ADVISORY_BOARD-only trigger must have been dropped"


@pytest.mark.parametrize("type_code", SINGLETON_TYPES)
def test_second_active_organization_of_a_singleton_type_is_rejected(write_conn, refs, type_code):
    _ensure_one_active(write_conn, refs, type_code, parent=_kendra(write_conn, refs) if type_code != "KENDRA" else None)
    pk, error = _insert(write_conn, refs, type_code)
    assert pk is None
    assert isinstance(error, psycopg2.errors.UniqueViolation), repr(error)
    assert "singleton violation" in str(error)


@pytest.mark.parametrize("type_code", SINGLETON_TYPES)
def test_inactive_second_row_is_allowed_but_cannot_be_activated(write_conn, refs, type_code):
    _ensure_one_active(write_conn, refs, type_code, parent=_kendra(write_conn, refs) if type_code != "KENDRA" else None)
    pk, error = _insert(write_conn, refs, type_code, is_active=False)
    assert error is None, error
    err = _update(write_conn, "UPDATE nss.organization SET is_active = TRUE WHERE organization_pk = %s", (pk,))
    assert isinstance(err, psycopg2.errors.UniqueViolation), repr(err)


def test_unrelated_update_of_a_singleton_row_is_not_blocked(write_conn, refs):
    pk = _ensure_one_active(write_conn, refs, "ADVISORY_BOARD", parent=_kendra(write_conn, refs))
    err = _update(write_conn, "UPDATE nss.organization SET phone_number = %s WHERE organization_pk = %s",
                  ("0674-1234567", pk))
    assert err is None, err


def test_second_central_mahila_under_kendra_is_rejected(write_conn, refs):
    _, kendra = _central_mahila(write_conn, refs)
    pk, error = _insert(write_conn, refs, "MAHILA_SANGHA", parent=kendra)
    assert pk is None
    assert isinstance(error, psycopg2.errors.UniqueViolation), repr(error)
    assert "CENTRAL_MAHILA_SANGHA" in str(error)


def test_local_mahila_sanghas_under_sakhas_are_unrestricted(write_conn, refs):
    _central_mahila(write_conn, refs)
    for _ in range(2):
        sakha, err = _insert(write_conn, refs, "SAKHA_SANGHA")
        assert err is None, err
        local, err = _insert(write_conn, refs, "MAHILA_SANGHA", parent=sakha)
        assert err is None, err
    # A Mahila Sangha with no parent at all is not the Kendra-parented slot either.
    pk, err = _insert(write_conn, refs, "MAHILA_SANGHA", parent=None)
    assert err is None, err


def test_reparenting_a_local_mahila_under_kendra_is_rejected_when_central_exists(write_conn, refs):
    _, kendra = _central_mahila(write_conn, refs)
    sakha, err = _insert(write_conn, refs, "SAKHA_SANGHA")
    assert err is None, err
    local, err = _insert(write_conn, refs, "MAHILA_SANGHA", parent=sakha)
    assert err is None, err
    err = _update(write_conn, "UPDATE nss.organization SET parent_organization_pk = %s WHERE organization_pk = %s",
                  (kendra, local))
    assert isinstance(err, psycopg2.errors.UniqueViolation), repr(err)
