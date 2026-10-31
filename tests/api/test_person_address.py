"""
NSS ERP — Person address write endpoints (api/routers/person.py).

POST/PATCH/DELETE /api/v1/person/persons/{person_pk}/addresses[...]:
self-service plus PERSON_MANAGE-in-scope, ADDRESS_TYPE validation, the
APPROVED-or-own-PENDING geography rule, the single-primary invariant and
soft delete. Real rows, rolled back with the module SAVEPOINT.

Admin-scope / 401 / cross-member negatives live in
tests/security/test_person_address_security.py.
"""

from uuid import uuid4

import pytest

from tests.attendance_support import (  # noqa: F401  (fixtures)
    FAKE_UUID, _login_headers, new_member, other_org_pk, register_org_pk, sakha_pks,
)

pytestmark = pytest.mark.integration

BASE = "/api/v1/person/persons"


def _md_pk(write_conn, category: str, value_code: str | None = None) -> str:
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = %s AND md.is_active = TRUE
          AND (%s::text IS NULL OR md.value_code = %s)
        ORDER BY md.value_code LIMIT 1
        """,
        (category, value_code, value_code),
    )
    row = cur.fetchone()
    if row is None:
        pytest.skip(f"No {category} master data seeded.")
    return str(row[0])


def _insert_city_village(write_conn, *, status: str, person_pk: str | None = None) -> str:
    suffix = uuid4().hex[:8].upper()
    cur = write_conn.cursor()
    cur.execute(
        """
        INSERT INTO nss.city_village (
            city_village_code, city_village_name, city_village_type,
            entry_status, submitted_by_person_pk
        ) VALUES (%s, %s, 'VILLAGE', %s, %s)
        RETURNING city_village_pk
        """,
        (f"T{suffix}", f"Testville {suffix}", status, person_pk),
    )
    return str(cur.fetchone()[0])


@pytest.fixture(scope="module")
def address_type_pk(write_conn):
    return _md_pk(write_conn, "ADDRESS_TYPE")


@pytest.fixture(scope="module")
def second_address_type_pk(write_conn, address_type_pk):
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'ADDRESS_TYPE' AND md.is_active = TRUE
          AND md.master_data_pk <> %s LIMIT 1
        """,
        (address_type_pk,),
    )
    row = cur.fetchone()
    return str(row[0]) if row else address_type_pk


@pytest.fixture
def member(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "AddrMember")


@pytest.fixture
def member_h(client, member):
    return _login_headers(client, member["sangha_sevi_id"], member["password"])


def _body(address_type_pk, **over):
    return {"address_type_master_data_pk": address_type_pk, "address_line_1": "12 Temple Road", **over}


def _add(client, headers, person_pk, address_type_pk, **over):
    r = client.post(f"{BASE}/{person_pk}/addresses", json=_body(address_type_pk, **over), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _list(client, headers, person_pk):
    r = client.get(f"{BASE}/{person_pk}/addresses", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


class TestCreate:
    def test_first_address_is_auto_primary_and_trimmed(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk,
                 address_line_1="  12 Temple Road  ", landmark="Near temple")
        assert a["person_pk"] == member["person_pk"]
        assert a["address_line_1"] == "12 Temple Road"
        assert a["landmark"] == "Near temple"
        assert a["is_primary"] is True and a["is_active"] is True
        assert a["address_type_code"]

    def test_second_address_defaults_non_primary(self, client, member, member_h, address_type_pk):
        _add(client, member_h, member["person_pk"], address_type_pk)
        b = _add(client, member_h, member["person_pk"], address_type_pk, address_line_1="B")
        assert b["is_primary"] is False

    def test_is_primary_true_demotes_previous_primary(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        b = _add(client, member_h, member["person_pk"], address_type_pk, address_line_1="B", is_primary=True)
        assert b["is_primary"] is True
        rows = {r["person_address_pk"]: r for r in _list(client, member_h, member["person_pk"])}
        assert rows[a["person_address_pk"]]["is_primary"] is False
        assert sum(r["is_primary"] for r in rows.values()) == 1

    def test_blank_address_line_422(self, client, member, member_h, address_type_pk):
        r = client.post(f"{BASE}/{member['person_pk']}/addresses",
                        json=_body(address_type_pk, address_line_1="   "), headers=member_h)
        assert r.status_code == 422

    def test_address_line_too_long_422(self, client, member, member_h, address_type_pk):
        r = client.post(f"{BASE}/{member['person_pk']}/addresses",
                        json=_body(address_type_pk, address_line_1="x" * 256), headers=member_h)
        assert r.status_code == 422

    def test_non_address_type_master_data_422(self, client, write_conn, member, member_h):
        wrong = _md_pk(write_conn, "MEMBERSHIP_TYPE")
        r = client.post(f"{BASE}/{member['person_pk']}/addresses",
                        json=_body(wrong), headers=member_h)
        assert r.status_code == 422

    def test_unknown_geography_404(self, client, member, member_h, address_type_pk):
        r = client.post(f"{BASE}/{member['person_pk']}/addresses",
                        json=_body(address_type_pk, city_village_pk=FAKE_UUID), headers=member_h)
        assert r.status_code == 404

    def test_approved_geography_allowed(self, client, write_conn, member, member_h, address_type_pk):
        cv = _insert_city_village(write_conn, status="APPROVED")
        a = _add(client, member_h, member["person_pk"], address_type_pk, city_village_pk=cv)
        assert a["city_village_pk"] == cv

    def test_own_pending_geography_allowed(self, client, write_conn, member, member_h, address_type_pk):
        cv = _insert_city_village(write_conn, status="PENDING", person_pk=member["person_pk"])
        a = _add(client, member_h, member["person_pk"], address_type_pk, city_village_pk=cv)
        assert a["city_village_pk"] == cv

    def test_own_pending_via_sangha_sevi_allowed(self, client, write_conn, member, member_h, address_type_pk):
        cv = _insert_city_village(write_conn, status="PENDING")
        cur = write_conn.cursor()
        cur.execute(
            "UPDATE nss.city_village SET submitted_by_sangha_sevi_pk = "
            "(SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE) "
            "WHERE city_village_pk = %s",
            (member["person_pk"], cv),
        )
        a = _add(client, member_h, member["person_pk"], address_type_pk, city_village_pk=cv)
        assert a["city_village_pk"] == cv

    def test_someone_elses_pending_geography_422(self, client, write_conn, member, member_h, address_type_pk,
                                                 register_org_pk):
        other = new_member(write_conn, register_org_pk, "AddrOther")
        cv = _insert_city_village(write_conn, status="PENDING", person_pk=other["person_pk"])
        r = client.post(f"{BASE}/{member['person_pk']}/addresses",
                        json=_body(address_type_pk, city_village_pk=cv), headers=member_h)
        assert r.status_code == 422

    def test_member_addressing_a_stranger_403(self, client, member_h, address_type_pk):
        # A member addressing a stranger is refused before existence is revealed.
        r = client.post(f"{BASE}/{FAKE_UUID}/addresses", json=_body(address_type_pk), headers=member_h)
        assert r.status_code == 403


class TestUpdate:
    def test_partial_update_changes_only_sent_fields(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk, landmark="Keep me")
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}",
                         json={"address_line_1": " New Line "}, headers=member_h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["address_line_1"] == "New Line"
        assert j["landmark"] == "Keep me"
        assert j["is_primary"] is True

    def test_explicit_null_clears_optional_field(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk, landmark="Gone")
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}",
                         json={"landmark": None}, headers=member_h)
        assert r.status_code == 200 and r.json()["landmark"] is None

    def test_change_address_type(self, client, member, member_h, address_type_pk, second_address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}",
                         json={"address_type_master_data_pk": second_address_type_pk}, headers=member_h)
        assert r.status_code == 200
        assert r.json()["address_type_master_data_pk"] == second_address_type_pk

    def test_empty_body_422(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}",
                         json={}, headers=member_h)
        assert r.status_code == 422

    def test_null_required_field_422(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}",
                         json={"address_line_1": None}, headers=member_h)
        assert r.status_code == 422

    def test_promote_demotes_previous_primary(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        b = _add(client, member_h, member["person_pk"], address_type_pk, address_line_1="B")
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{b['person_address_pk']}",
                         json={"is_primary": True}, headers=member_h)
        assert r.status_code == 200 and r.json()["is_primary"] is True
        rows = {x["person_address_pk"]: x for x in _list(client, member_h, member["person_pk"])}
        assert rows[a["person_address_pk"]]["is_primary"] is False
        assert sum(x["is_primary"] for x in rows.values()) == 1

    def test_unprimary_the_primary_409(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}",
                         json={"is_primary": False}, headers=member_h)
        assert r.status_code == 409

    def test_unknown_address_404(self, client, member, member_h):
        r = client.patch(f"{BASE}/{member['person_pk']}/addresses/{FAKE_UUID}",
                         json={"landmark": "x"}, headers=member_h)
        assert r.status_code == 404

    def test_other_persons_address_via_my_url_404(self, client, write_conn, member, member_h,
                                                  address_type_pk, register_org_pk):
        other = new_member(write_conn, register_org_pk, "AddrOther")
        other_h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        theirs = _add(client, other_h, other["person_pk"], address_type_pk)
        for method, kw in (("patch", {"json": {"landmark": "x"}}), ("delete", {})):
            r = getattr(client, method)(
                f"{BASE}/{member['person_pk']}/addresses/{theirs['person_address_pk']}",
                headers=member_h, **kw)
            assert r.status_code == 404
        assert _list(client, other_h, other["person_pk"])[0]["landmark"] is None


class TestDelete:
    def test_soft_delete_hides_row_but_keeps_it(self, client, write_conn, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        r = client.delete(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}", headers=member_h)
        assert r.status_code == 200 and r.json()["message"]
        assert _list(client, member_h, member["person_pk"]) == []
        cur = write_conn.cursor()
        cur.execute("SELECT is_active, deleted_at, is_primary FROM nss.person_address "
                    "WHERE person_address_pk = %s", (a["person_address_pk"],))
        is_active, deleted_at, is_primary = cur.fetchone()
        assert is_active is False and deleted_at is not None and is_primary is False

    def test_delete_twice_404(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        url = f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}"
        assert client.delete(url, headers=member_h).status_code == 200
        assert client.delete(url, headers=member_h).status_code == 404

    def test_primary_with_siblings_409_then_ok_after_promote(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        b = _add(client, member_h, member["person_pk"], address_type_pk, address_line_1="B")
        url_a = f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}"
        assert client.delete(url_a, headers=member_h).status_code == 409
        assert client.patch(f"{BASE}/{member['person_pk']}/addresses/{b['person_address_pk']}",
                            json={"is_primary": True}, headers=member_h).status_code == 200
        assert client.delete(url_a, headers=member_h).status_code == 200
        rows = _list(client, member_h, member["person_pk"])
        assert len(rows) == 1 and rows[0]["is_primary"] is True

    def test_new_primary_allowed_after_last_address_removed(self, client, member, member_h, address_type_pk):
        a = _add(client, member_h, member["person_pk"], address_type_pk)
        client.delete(f"{BASE}/{member['person_pk']}/addresses/{a['person_address_pk']}", headers=member_h)
        b = _add(client, member_h, member["person_pk"], address_type_pk)
        assert b["is_primary"] is True
