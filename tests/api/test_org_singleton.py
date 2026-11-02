"""
NSS ERP — API-level organization singleton rules (owner decision 2026-10-30).

KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA, ADVISORY_BOARD and the central
(Kendra-parented) Mahila Sangha are each single. api/helpers.py
require_singleton_slot_free gives a clean 422 before the DB trigger
(database/ddl/02_organization/08_organization_singleton_trigger.sql) fires,
in POST /admin/organizations and PATCH /admin/organizations/{pk} (re-parenting
a Mahila Sangha under a Kendra). Local per-Sakha Mahila Sanghas stay free.

Real-DB integration tests, rolled back with the module SAVEPOINT; written but
NOT yet run against a database — do not claim they pass.
"""

from uuid import uuid4

import pytest

from tests.api.test_correspondence import (
    _create_admin_with_scope,
    _create_test_organization,
    _login_headers,
)
from tests.attendance_support import _with_sevi_pk
from tests.reparent_support import kendra_pks, parent_of, patch_parent

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def admin_h(client, write_conn):
    admin = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None))
    return _login_headers(client, admin["sangha_sevi_id"], admin["password"])


def _sc():
    return "S" + uuid4().hex[:4].upper()


def _ensure_central_mahila(write_conn, kendra_pk):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'MAHILA_SANGHA' AND o.parent_organization_pk = %s AND o.is_active
        LIMIT 1
    """, (kendra_pk,))
    row = cur.fetchone()
    if row:
        return str(row[0])
    return _create_test_organization(
        write_conn, name_prefix="SingletonCentralMahila", type_code="MAHILA_SANGHA",
        parent_pk=kendra_pk, short_code=_sc())


@pytest.mark.parametrize("type_code", ["KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA", "ADVISORY_BOARD"])
def test_create_second_singleton_type_is_422(client, admin_h, type_code):
    r = client.post("/api/v1/admin/organizations", headers=admin_h, json={
        "organization_name": "Second Singleton", "organization_type_code": type_code})
    assert r.status_code == 422, r.text
    assert "unique and already exists" in r.text


def test_create_second_central_mahila_is_422(client, write_conn, admin_h):
    kendra_pk, _ = kendra_pks(write_conn)
    _ensure_central_mahila(write_conn, kendra_pk)
    r = client.post("/api/v1/admin/organizations", headers=admin_h, json={
        "organization_name": "Second Central Mahila", "organization_type_code": "MAHILA_SANGHA",
        "parent_organization_pk": kendra_pk})
    assert r.status_code == 422, r.text
    assert "unique and already exists" in r.text


def test_reparenting_a_local_mahila_under_kendra_is_422_when_central_exists(client, write_conn, admin_h):
    kendra_pk, _ = kendra_pks(write_conn)
    _ensure_central_mahila(write_conn, kendra_pk)
    sakha = _create_test_organization(
        write_conn, name_prefix="SingletonSakha", type_code="SAKHA_SANGHA", parent_pk=None, short_code=_sc())
    local = _create_test_organization(
        write_conn, name_prefix="SingletonLocalMahila", type_code="MAHILA_SANGHA", parent_pk=sakha, short_code=_sc())
    r = patch_parent(client, admin_h, local, kendra_pk)
    assert r.status_code == 422, r.text
    assert "unique and already exists" in r.text
    assert parent_of(write_conn, local) == sakha


def test_moving_a_local_mahila_between_sakhas_is_unrestricted(client, write_conn, admin_h):
    kendra_pk, _ = kendra_pks(write_conn)
    _ensure_central_mahila(write_conn, kendra_pk)
    s1 = _create_test_organization(
        write_conn, name_prefix="SingletonSakhaA", type_code="SAKHA_SANGHA", parent_pk=None, short_code=_sc())
    s2 = _create_test_organization(
        write_conn, name_prefix="SingletonSakhaB", type_code="SAKHA_SANGHA", parent_pk=None, short_code=_sc())
    local = _create_test_organization(
        write_conn, name_prefix="SingletonLocalMahila2", type_code="MAHILA_SANGHA", parent_pk=s1, short_code=_sc())
    r = patch_parent(client, admin_h, local, s2)
    assert r.status_code == 200, r.text
    assert parent_of(write_conn, local) == s2


def test_naming_the_current_kendra_parent_of_the_central_mahila_is_not_a_change(client, write_conn, admin_h):
    kendra_pk, _ = kendra_pks(write_conn)
    central = _ensure_central_mahila(write_conn, kendra_pk)
    r = patch_parent(client, admin_h, central, kendra_pk)
    assert r.status_code == 200, r.text
