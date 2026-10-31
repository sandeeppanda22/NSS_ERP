"""
NSS ERP — DB tests for organization table triggers.

ORG-BR-099 (database/ddl/02_organization/04_organization_address_restriction_trigger.sql):
Anchalika Sangha, Zilla Sangha and Patha Chakra are administrative units
with no premises of their own, so the DB itself must refuse any row of
those types carrying a physical premises address — address_line_1/2,
city_village_pk, postal_code_pk, latitude, longitude. Jurisdiction fields
(country/state/district), contacts and has_own_premises stay allowed, and
SAKHA_SANGHA / KENDRA keep their premises addresses.

The trigger fires BEFORE INSERT and BEFORE UPDATE OF the type or any
premises column, so both a direct write and "re-type a row that already
has an address" are covered. Each attempt runs in its own SAVEPOINT so a
trigger rejection does not abort the surrounding test transaction.
"""

from uuid import uuid4

import psycopg2
import pytest


pytestmark = [pytest.mark.db, pytest.mark.integration]

RESTRICTED = ["ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA"]
# KENDRA is a singleton (trg_enforce_organization_singleton), so a second one cannot be
# inserted; its premises address is covered by the UPDATE test below instead.
UNRESTRICTED = ["SAKHA_SANGHA"]

# column -> value factory (FK columns resolved from live rows by `refs`)
PREMISES_COLUMNS = [
    "address_line_1", "address_line_2", "city_village_pk",
    "postal_code_pk", "latitude", "longitude",
]


@pytest.fixture(scope="module")
def refs(write_conn):
    """Master-data PKs and one row of each referenced geography table."""
    out = {}
    with write_conn.cursor() as cur:
        # KENDRA is a singleton (not parametrized) but test_kendra_keeps_its_premises_address needs its type pk.
        for code in RESTRICTED + UNRESTRICTED + ["KENDRA"]:
            cur.execute(
                """
                SELECT md.master_data_pk FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'ORGANIZATION_TYPE' AND md.value_code = %s
                  AND md.is_active = TRUE
                """,
                (code,),
            )
            row = cur.fetchone()
            if row is None:
                pytest.skip(f"ORGANIZATION_TYPE {code} not seeded.")
            out[code] = str(row[0])
        cur.execute(
            """
            SELECT md.master_data_pk FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' LIMIT 1
            """
        )
        out["status"] = str(cur.fetchone()[0])
        for key, sql in (
            ("city_village_pk", "SELECT city_village_pk FROM nss.city_village LIMIT 1"),
            ("postal_code_pk", "SELECT postal_code_pk FROM nss.postal_code LIMIT 1"),
            ("country_pk", "SELECT country_pk FROM nss.country LIMIT 1"),
            ("state_pk", "SELECT state_pk FROM nss.state LIMIT 1"),
            ("district_pk", "SELECT district_pk FROM nss.district LIMIT 1"),
        ):
            cur.execute(sql)
            row = cur.fetchone()
            out[key] = str(row[0]) if row else None
    return out


def _value(column, refs):
    if column in ("city_village_pk", "postal_code_pk"):
        if refs[column] is None:
            pytest.skip(f"No {column} row available to reference.")
        return refs[column]
    if column in ("latitude", "longitude"):
        return 20.2961
    return "1 Matrix Street"


def _insert(conn, refs, type_code, **cols):
    """INSERT one organization inside a SAVEPOINT; returns (pk | None, error | None)."""
    tag = uuid4().hex[:8].upper()
    names = ["organization_name", "organization_type_master_data_pk", "status_master_data_pk"]
    values = [f"ORG099 {tag}", refs[type_code], refs["status"]]
    for name, val in cols.items():
        names.append(name)
        values.append(val)
    sql = (
        f"INSERT INTO nss.organization ({', '.join(names)}) "
        f"VALUES ({', '.join(['%s'] * len(values))}) RETURNING organization_pk"
    )
    cur = conn.cursor()
    cur.execute("SAVEPOINT sp_org099")
    try:
        cur.execute(sql, values)
        pk = str(cur.fetchone()[0])
        cur.execute("RELEASE SAVEPOINT sp_org099")
        return pk, None
    except psycopg2.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT sp_org099")
        return None, exc
    finally:
        cur.close()


def _update(conn, pk, **cols):
    sets = ", ".join(f"{c} = %s" for c in cols)
    cur = conn.cursor()
    cur.execute("SAVEPOINT sp_org099_upd")
    try:
        cur.execute(f"UPDATE nss.organization SET {sets} WHERE organization_pk = %s",
                    [*cols.values(), pk])
        cur.execute("RELEASE SAVEPOINT sp_org099_upd")
        return None
    except psycopg2.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT sp_org099_upd")
        return exc
    finally:
        cur.close()


def _assert_org_br_099(error):
    assert error is not None, "trigger did not reject the premises address"
    assert isinstance(error, psycopg2.errors.CheckViolation), repr(error)
    assert "ORG-BR-099" in str(error)


def test_trigger_exists_on_insert_and_relevant_updates(write_conn):
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'nss' AND c.relname = 'organization'
              AND t.tgname = 'trg_enforce_organization_address_restriction'
            """
        )
        row = cur.fetchone()
    assert row, "ORG-BR-099 trigger is missing"
    definition = row[0]
    assert "BEFORE INSERT OR UPDATE OF" in definition
    for column in ["organization_type_master_data_pk", *PREMISES_COLUMNS]:
        assert column in definition


@pytest.mark.parametrize("type_code", RESTRICTED)
@pytest.mark.parametrize("column", PREMISES_COLUMNS)
def test_restricted_type_rejects_each_premises_column_on_insert(write_conn, refs, type_code, column):
    _, error = _insert(write_conn, refs, type_code, **{column: _value(column, refs)})
    _assert_org_br_099(error)


@pytest.mark.parametrize("type_code", RESTRICTED)
def test_restricted_type_rejects_a_full_address_on_insert(write_conn, refs, type_code):
    cols = {c: _value(c, refs) for c in PREMISES_COLUMNS}
    _, error = _insert(write_conn, refs, type_code, **cols)
    _assert_org_br_099(error)


@pytest.mark.parametrize("type_code", RESTRICTED)
def test_restricted_type_allows_jurisdiction_contacts_and_flag(write_conn, refs, type_code):
    """country/state/district are jurisdiction, not premises (ORG-BR-099)."""
    cols = {k: refs[k] for k in ("country_pk", "state_pk", "district_pk") if refs[k]}
    cols.update(mobile_number="9876543210", has_own_premises=True)
    pk, error = _insert(write_conn, refs, type_code, **cols)
    assert error is None, error
    assert pk


@pytest.mark.parametrize("type_code", RESTRICTED)
def test_restricted_type_with_no_premises_is_allowed(write_conn, refs, type_code):
    pk, error = _insert(write_conn, refs, type_code)
    assert error is None, error
    assert pk


@pytest.mark.parametrize("type_code", RESTRICTED)
@pytest.mark.parametrize("column", ["address_line_1", "latitude"])
def test_restricted_type_rejects_adding_premises_by_update(write_conn, refs, type_code, column):
    pk, error = _insert(write_conn, refs, type_code)
    assert error is None, error
    _assert_org_br_099(_update(write_conn, pk, **{column: _value(column, refs)}))


@pytest.mark.parametrize("type_code", UNRESTRICTED)
def test_unrestricted_types_keep_their_premises_address(write_conn, refs, type_code):
    cols = {c: _value(c, refs) for c in PREMISES_COLUMNS}
    pk, error = _insert(write_conn, refs, type_code, **cols)
    assert error is None, error
    assert pk


def test_kendra_keeps_its_premises_address(write_conn, refs):
    """KENDRA is unrestricted; it is a singleton, so update the existing row (rolled back)."""
    cols = {c: _value(c, refs) for c in PREMISES_COLUMNS}
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT organization_pk FROM nss.organization "
            "WHERE organization_type_master_data_pk = %s AND is_active LIMIT 1",
            (refs["KENDRA"],),
        )
        row = cur.fetchone()
    if row is None:
        pk, error = _insert(write_conn, refs, "KENDRA", **cols)
        assert error is None, error
        return
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_kendra_addr")
    try:
        assert _update(write_conn, str(row[0]), **cols) is None
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT sp_kendra_addr")
        cur.close()


@pytest.mark.parametrize("restricted", RESTRICTED)
def test_retyping_an_addressed_sakha_into_a_restricted_type_is_rejected(write_conn, refs, restricted):
    """The trigger also fires on UPDATE OF organization_type_master_data_pk."""
    pk, error = _insert(write_conn, refs, "SAKHA_SANGHA", address_line_1="1 Matrix Street")
    assert error is None, error
    _assert_org_br_099(_update(write_conn, pk, organization_type_master_data_pk=refs[restricted]))


def test_retyping_an_address_free_org_into_a_restricted_type_is_allowed(write_conn, refs):
    pk, error = _insert(write_conn, refs, "SAKHA_SANGHA")
    assert error is None, error
    assert _update(write_conn, pk, organization_type_master_data_pk=refs["ZILLA_SANGHA"]) is None
