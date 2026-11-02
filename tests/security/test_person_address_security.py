"""
NSS ERP — Security tests for the Person address write endpoints
(POST/PATCH/DELETE /api/v1/person/persons/{pk}/addresses, api/routers/person.py).

401 anonymous, 403 for another member, PERSON_MANAGE admin-scope in/out.
"""

import pytest

from tests.api.test_person_address import BASE, _add, _body, _md_pk  # noqa: F401
from tests.attendance_support import (  # noqa: F401  (fixtures)
    FAKE_UUID, _login_headers, new_member, other_admin, other_admin_h, other_org_pk,
    plain_member, plain_member_h, register_org_pk, sakha_admin, sakha_admin_h, sakha_pks,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def address_type_pk(write_conn):
    return _md_pk(write_conn, "ADDRESS_TYPE")


@pytest.fixture(scope="module")
def victim(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "AddrVictim")


@pytest.fixture(scope="module")
def victim_h(client, victim):
    return _login_headers(client, victim["sangha_sevi_id"], victim["password"])


@pytest.fixture(scope="module")
def victim_address(client, victim, victim_h, address_type_pk):
    return _add(client, victim_h, victim["person_pk"], address_type_pk)


def _url(person_pk, address_pk=FAKE_UUID):
    return f"{BASE}/{person_pk}/addresses/{address_pk}"


class TestAnonymous:
    def test_post_401(self, anon_client, address_type_pk):
        r = anon_client.post(f"{BASE}/{FAKE_UUID}/addresses", json=_body(address_type_pk))
        assert r.status_code == 401

    def test_patch_401(self, anon_client):
        assert anon_client.patch(_url(FAKE_UUID), json={"landmark": "x"}).status_code == 401

    def test_delete_401(self, anon_client):
        assert anon_client.delete(_url(FAKE_UUID)).status_code == 401


class TestAnotherMember:
    def test_post_403(self, client, victim, plain_member_h, address_type_pk):
        r = client.post(f"{BASE}/{victim['person_pk']}/addresses",
                        json=_body(address_type_pk), headers=plain_member_h)
        assert r.status_code == 403

    def test_patch_403(self, client, victim, victim_address, plain_member_h):
        r = client.patch(_url(victim["person_pk"], victim_address["person_address_pk"]),
                         json={"landmark": "hax"}, headers=plain_member_h)
        assert r.status_code == 403

    def test_delete_403(self, client, victim, victim_address, plain_member_h):
        r = client.delete(_url(victim["person_pk"], victim_address["person_address_pk"]),
                          headers=plain_member_h)
        assert r.status_code == 403


class TestAdminScope:
    def test_in_scope_admin_can_add_edit_delete(self, client, victim, sakha_admin_h, address_type_pk):
        a = _add(client, sakha_admin_h, victim["person_pk"], address_type_pk, address_line_1="By admin")
        u = _url(victim["person_pk"], a["person_address_pk"])
        assert client.patch(u, json={"landmark": "ok"}, headers=sakha_admin_h).status_code == 200
        assert client.delete(u, headers=sakha_admin_h).status_code == 200

    def test_out_of_scope_admin_post_403(self, client, victim, other_admin_h, address_type_pk):
        r = client.post(f"{BASE}/{victim['person_pk']}/addresses",
                        json=_body(address_type_pk), headers=other_admin_h)
        assert r.status_code == 403

    def test_out_of_scope_admin_patch_403(self, client, victim, victim_address, other_admin_h):
        r = client.patch(_url(victim["person_pk"], victim_address["person_address_pk"]),
                         json={"landmark": "hax"}, headers=other_admin_h)
        assert r.status_code == 403

    def test_out_of_scope_admin_delete_403(self, client, victim, victim_address, other_admin_h):
        r = client.delete(_url(victim["person_pk"], victim_address["person_address_pk"]),
                          headers=other_admin_h)
        assert r.status_code == 403
