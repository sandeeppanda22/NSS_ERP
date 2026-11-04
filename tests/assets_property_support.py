"""
NSS ERP — shared fixtures/helpers for the Assets & Property test modules
(tests/api/test_assets_property.py, tests/security/test_assets_property_security.py).

Builds on the Attendance cast (tests/attendance_support.py: real rows, rolled
back with the module SAVEPOINT) rather than re-implementing the admin/person
builders. Test modules import the fixtures they need by name.

Cast (the "register" Sakha = S1, the "other" Sakha = S2):
  admin_user    NSS_ERP_ADMIN, NSS-WIDE         (global authority: sees/manages custodian-less records)
  sakha_admin   NSS_ERP_SAKHA_ADMIN, scoped S1  (ASSET_VIEW + ASSET_MANAGE for S1's records)
  other_admin   NSS_ERP_SAKHA_ADMIN, scoped S2  (a foreign Sakha)
  viewer_user   NSS_ERP_AUDITOR, scoped S1      (ASSET_VIEW only)
  plain_member  person + login, no role at all  (no ASSET_* permission)

Prerequisites (database build): Phase 11g DDL, the ASSET_* permissions patch
and the Assets & Property reference-data patch.
"""

from datetime import date
from uuid import uuid4

import pytest

from api.helpers import ASSET_CUSTODIAN_ORG_TYPES
from tests.api.test_correspondence import _create_test_organization
from tests.attendance_support import (  # noqa: F401  (re-exported to test modules)
    FAKE_UUID,
    _create_admin_with_scope,
    _login_headers,
    _with_sevi_pk,
    admin_h,
    admin_user,
    other_admin,
    other_admin_h,
    other_org_pk,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
)

BASE = "/api/v1/assets-property"
TODAY = date.today().isoformat()

# Custodian eligibility (owner rule 2026-11-02, GDR-010 §2C). The eligible list
# is the production constant itself (never a second copy); the refused list is
# every OTHER seeded ORGANIZATION_TYPE: the conceptual groupings, the wing
# organizations and the Advisory Board organization.
ELIGIBLE_CUSTODIAN_TYPES = list(ASSET_CUSTODIAN_ORG_TYPES)
INELIGIBLE_CUSTODIAN_TYPES = [
    "ANCHALIKA_SANGHA", "ZILLA_SANGHA", "KUMARI_SANGHA", "SEVAK_SANGHA", "MAHILA_SANGHA",
    "PARIBARIK_ASANA", "PARIBARIK_SANGHA", "ADVISORY_BOARD",
]
# Types capped to a single active organization (singleton trigger): reuse the
# seeded row instead of inserting a second one.
_SINGLETON_TYPES = {"KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA", "ADVISORY_BOARD"}


def org_of_type(write_conn, type_code: str, parent_pk=None) -> str:
    """
    An active organization of *type_code*: the seeded one for the singleton
    types, otherwise a fresh throwaway (rolled back with the module SAVEPOINT).
    """
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = %s AND o.is_active = TRUE
        ORDER BY o.organization_pk LIMIT 1
        """,
        (type_code,),
    )
    row = cur.fetchone()
    if type_code in _SINGLETON_TYPES:
        if row is None:
            pytest.skip(f"No active {type_code} organization is seeded.")
        return str(row[0])
    if row is not None and parent_pk is None:
        return str(row[0])
    return _create_test_organization(
        write_conn, name_prefix=f"AP test {type_code}", type_code=type_code, parent_pk=parent_pk,
        short_code=f"A{uuid4().hex[:4].upper()}"  # nss.organization.short_code is VARCHAR(5),
    )


# ═══════════════════════════════════════════════════════════════════════
# Builders
# ═══════════════════════════════════════════════════════════════════════

def make_property(client, headers, custodian_pk=None, **over) -> dict:
    body = {"property_name": f"AP test property {uuid4().hex[:6]}", "property_type_code": "LAND"}
    if custodian_pk is not None:
        body["custodian_organization_pk"] = str(custodian_pk)
    body.update(over)
    r = client.post(f"{BASE}/properties", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def make_asset(client, headers, custodian_pk=None, **over) -> dict:
    body = {"asset_name": f"AP test asset {uuid4().hex[:6]}", "asset_type_code": "EQUIPMENT"}
    if custodian_pk is not None:
        body["custodian_organization_pk"] = str(custodian_pk)
    body.update(over)
    r = client.post(f"{BASE}/assets", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def transition(client, headers, kind, pk, status_code_, remarks=None):
    return client.post(
        f"{BASE}/{kind}/{pk}/transition", json={"status": status_code_, "remarks": remarks}, headers=headers,
    )


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def viewer_user(write_conn, register_org_pk):
    """ASSET_VIEW only (NSS_ERP_AUDITOR), scoped to the register Sakha."""
    return _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_AUDITOR", scope_level="SAKHA", organization_pk=register_org_pk))


@pytest.fixture(scope="module")
def viewer_h(client, viewer_user):
    return _login_headers(client, viewer_user["sangha_sevi_id"], viewer_user["password"])


@pytest.fixture(scope="module")
def document_pks(write_conn):
    """Two real document_master rows (the document junction FKs are constrained)."""
    cur = write_conn.cursor()
    pks = []
    for i in range(2):
        cur.execute(
            """
            INSERT INTO nss.document_master (document_type_code, document_name, storage_path)
            VALUES ('ASSET_PROPERTY_TEST', %s, %s) RETURNING document_master_pk
            """,
            (f"AP test doc {i} {uuid4().hex[:6]}", f"/tmp/ap-{uuid4().hex[:8]}"),
        )
        pks.append(str(cur.fetchone()[0]))
    return pks
