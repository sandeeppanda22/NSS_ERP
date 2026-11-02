"""
NSS ERP — shared builders for the Sakha re-parent approval tests
(tests/api/test_org_reparent.py, tests/ui is source-parsing only).

Builds on the person/seat builders from tests/api/test_correspondence.py and
tests/attendance_support.py (real rows, rolled back with the module
SAVEPOINT). Every Sakha/Anchalika here is created fresh through the admin API
so no seeded org is ever re-parented, and the one-open-request-per-Sakha rule
never leaks between tests.

Cast (see `world` fixture in the test module):
  admin_user        NSS_ERP_ADMIN, NSS-WIDE (real user_role; NOT a GB member, but
                    EXEMPT from approval by role — owner 2026-10-30)
  kendra_admin      NSS_ERP_KENDRA_ADMIN via a real user_role (NOT a GB member)
  gb_member         seated SECRETARY on the Kendra Governing Body (GB member,
                    §63 composite NSS_ERP_KENDRA_ADMIN with user_role_pk None)
  kendra_president  seated PRESIDENT on the Kendra Governing Body
"""

from uuid import uuid4

from tests.api.test_correspondence import (  # noqa: F401  (re-exported)
    _create_admin_with_scope,
    _create_person_with_login,
    _create_test_organization as create_test_organization,
    _login_headers,
    _seat_office_bearer,
)
from tests.attendance_support import _scoped_user, _seat_exclusive, _with_sevi_pk  # noqa: F401

BASE = "/api/v1/org-reparent"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


def kendra_pks(write_conn) -> tuple[str, str]:
    """(kendra organization_pk, KENDRA_GOVERNING_BODY body_master_pk)."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'KENDRA' AND o.is_active = TRUE LIMIT 1
    """)
    kendra_pk = str(cur.fetchone()[0])
    cur.execute("""
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'KENDRA_GOVERNING_BODY' AND bm.organization_pk IS NULL
          AND bm.is_active = TRUE LIMIT 1
    """)
    row = cur.fetchone()
    assert row, "No KENDRA_GOVERNING_BODY shell is seeded."
    return kendra_pk, str(row[0])


def vacate_seat(write_conn, body_pk: str, position_code: str) -> None:
    """Deactivate every current holder of position_code on the body (rolled
    back with the module SAVEPOINT) so a negative test is never masked by a
    demo-seeded office bearer."""
    cur = write_conn.cursor()
    cur.execute(
        """
        UPDATE nss.body_member_assignment a
        SET is_active = FALSE, effective_to = CURRENT_DATE - 1, deleted_at = NOW()
        FROM nss.position_master pm
        WHERE a.position_master_pk = pm.position_master_pk
          AND a.body_master_pk = %s AND pm.position_code = %s
          AND a.is_active = TRUE AND a.effective_to IS NULL
        """,
        (str(body_pk), position_code),
    )


def seat(write_conn, body_pk: str, position_code: str, person: dict) -> None:
    vacate_seat(write_conn, body_pk, position_code)
    _seat_office_bearer(
        write_conn, body_master_pk=body_pk, position_code=position_code,
        person_pk=person["person_pk"], sangha_sevi_pk=person["sangha_sevi_pk"],
    )


def ensure_gb_body(write_conn, org_pk: str, body_type_code: str) -> str:
    """The org's governing body of body_type_code, inserting an empty shell
    if the org has none (a fresh Anchalika/Zilla has no auto-created GB;
    a fresh Sakha already gets one from create_organization)."""
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = %s AND bm.organization_pk = %s AND bm.is_active = TRUE LIMIT 1
        """,
        (body_type_code, str(org_pk)),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])
    cur.execute("SELECT body_type_master_pk FROM nss.body_type_master WHERE body_type_code = %s", (body_type_code,))
    type_pk = cur.fetchone()[0]
    suffix = uuid4().hex[:8].upper()
    cur.execute(
        """
        INSERT INTO nss.body_master (body_type_master_pk, body_code, body_name, organization_pk,
                                     body_status, effective_from)
        VALUES (%s, %s, %s, %s, 'ACTIVE', DATE '2020-01-01') RETURNING body_master_pk
        """,
        (str(type_pk), f"RPT_{suffix}", f"Reparent test body {suffix}", str(org_pk)),
    )
    return str(cur.fetchone()[0])


def location_pks(write_conn) -> dict:
    cur = write_conn.cursor()
    cur.execute("SELECT country_pk FROM nss.country WHERE country_code = 'IN' AND is_active = TRUE LIMIT 1")
    country_pk = str(cur.fetchone()[0])
    cur.execute("SELECT state_pk FROM nss.state WHERE LOWER(state_name) LIKE '%%odisha%%' AND is_active = TRUE LIMIT 1")
    state_pk = str(cur.fetchone()[0])
    cur.execute("SELECT district_pk FROM nss.district WHERE state_pk = %s AND is_active = TRUE LIMIT 1", (state_pk,))
    return {"country_pk": country_pk, "state_pk": state_pk, "district_pk": str(cur.fetchone()[0])}


def create_org(client, admin_h, loc: dict, type_code: str, parent_pk: str, label: str) -> str:
    """Fresh Anchalika/Zilla/Sakha through the admin API (NSS_ERP_ADMIN)."""
    suffix = uuid4().hex[:6].upper()
    payload = {
        "organization_name": f"{label} {suffix}",
        "organization_type_code": type_code,
        "parent_organization_pk": parent_pk,
        **loc,
    }
    if type_code in ("ANCHALIKA_SANGHA", "ZILLA_SANGHA"):
        payload["organization_code"] = f"RP{suffix}"
    if type_code == "SAKHA_SANGHA":
        payload.update({"city_village_name": f"RptVillage{suffix}", "phone_number": "0674-9999999"})
    r = client.post("/api/v1/admin/organizations", headers=admin_h, json=payload)
    assert r.status_code == 201, r.text
    return r.json()["organization_pk"]


def parent_of(write_conn, org_pk: str) -> str | None:
    cur = write_conn.cursor()
    cur.execute("SELECT parent_organization_pk FROM nss.organization WHERE organization_pk = %s", (str(org_pk),))
    row = cur.fetchone()
    return str(row[0]) if row and row[0] else None


def patch_parent(client, headers, org_pk: str, parent_pk: str, **extra):
    return client.patch(
        f"/api/v1/admin/organizations/{org_pk}", headers=headers,
        json={"parent_organization_pk": parent_pk, **extra},
    )


def decide(client, headers, request: dict, step_order: int, decision: str = "APPROVE", remarks: str | None = None):
    step = next(s for s in request["steps"] if s["step_order"] == step_order)
    return client.post(
        f"{BASE}/{request['organization_reparent_request_pk']}/steps/{step['organization_reparent_step_pk']}/decide",
        json={"decision": decision, "remarks": remarks}, headers=headers,
    )


def get_request(client, headers, request_pk: str) -> dict:
    r = client.get(f"{BASE}/{request_pk}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
