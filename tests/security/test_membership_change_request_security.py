"""
NSS ERP — Security tests for the Membership Change Request workflow
(api/routers/membership_change_request.py).

Focus: permission negatives (MEMBERSHIP_MANAGE / MEMBERSHIP_APPROVE) and
admin-scope negatives (require_org_in_scope) that are NOT already covered
by the happy-path assertions in tests/api/test_membership_change_request.py.
Exact error strings asserted verbatim against the router source.
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/membership/change-requests"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — two disjoint Sakha "zones" with their own scoped admins,
# so a decision in zone A can be attempted by an admin scoped only to zone B.
# ═══════════════════════════════════════════════════════════════════════

def _active_sakha_org_pks(write_conn, limit: int = 2):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.organization_pk LIMIT %s
    """, (limit,))
    rows = [str(r[0]) for r in cur.fetchall()]
    if len(rows) < limit:
        pytest.skip(f"Need at least {limit} active SAKHA_SANGHA organizations.")
    return rows


def _membership_type_pk(write_conn, value_code: str):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = %s AND md.is_active = TRUE
        LIMIT 1
    """, (value_code,))
    row = cur.fetchone()
    assert row, f"MEMBERSHIP_TYPE '{value_code}' not seeded."
    return row[0]


def _membership_status_active_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    return cur.fetchone()[0]


def _create_member_with_home_affiliation(write_conn, label: str, *, organization_pk: str):
    from datetime import date
    from api.helpers import insert_sakha_affiliation

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"SMCR{suffix}", label, suffix, f"smcr.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    membership_type_pk = _membership_type_pk(write_conn, "REGULAR")
    membership_status_pk = _membership_status_active_pk(write_conn)

    sangha_sevi_id = f"SMSS{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        RETURNING sangha_sevi_pk
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(organization_pk)))
    sangha_sevi_pk = cur.fetchone()[0]

    insert_sakha_affiliation(
        cur, sangha_sevi_pk=str(sangha_sevi_pk), organization_pk=str(organization_pk),
        local_number=None, effective_from=date(2020, 4, 1), is_darshak=False,
        source_event_type="ENROLLMENT",
    )
    return {"person_pk": str(person_pk), "sangha_sevi_pk": str(sangha_sevi_pk),
            "sangha_sevi_id": sangha_sevi_id, "organization_pk": str(organization_pk)}


def _create_admin_with_scope(write_conn, *, role_code: str, scope_level: str, organization_pk, home_org_pk: str):
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    membership_type_pk = _membership_type_pk(write_conn, "REGULAR")
    membership_status_pk = _membership_status_active_pk(write_conn)

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"SADM{suffix}", "SecAdmin", suffix, f"sadm.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"SADMSS{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), home_org_pk))

    password = f"SecPass1{suffix[:4]}"
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), hash_password(password)))
    user_account_pk = cur.fetchone()[0]

    cur.execute(
        "SELECT role_master_pk FROM nss.role_master WHERE role_code = %s AND is_active = TRUE",
        (role_code,),
    )
    role_row = cur.fetchone()
    assert role_row, f"{role_code} role not found."
    role_master_pk = role_row[0]

    cur.execute("""
        INSERT INTO nss.user_role (user_account_pk, role_master_pk)
        VALUES (%s, %s) RETURNING user_role_pk
    """, (str(user_account_pk), str(role_master_pk)))
    user_role_pk = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, %s, %s)
    """, (str(user_role_pk), scope_level,
          str(organization_pk) if (scope_level != "NSS-WIDE" and organization_pk) else None))

    return {"sangha_sevi_id": sangha_sevi_id, "password": password, "person_pk": str(person_pk)}


def _login_headers(client, login_id: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def zone_org_pks(write_conn):
    """zone_a = [source, dest]; zone_b_org is a third, disjoint Sakha."""
    return _active_sakha_org_pks(write_conn, 3)


@pytest.fixture(scope="module")
def source_org_pk(zone_org_pks):
    return zone_org_pks[0]


@pytest.fixture(scope="module")
def dest_org_pk(zone_org_pks):
    return zone_org_pks[1]


@pytest.fixture(scope="module")
def outside_org_pk(zone_org_pks):
    """Scoped admin's own zone — disjoint from source/dest."""
    return zone_org_pks[2]


@pytest.fixture(scope="module")
def nss_wide_admin(write_conn, source_org_pk):
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE",
        organization_pk=None, home_org_pk=source_org_pk,
    )


@pytest.fixture(scope="module")
def nss_wide_headers(client, nss_wide_admin):
    return _login_headers(client, nss_wide_admin["sangha_sevi_id"], nss_wide_admin["password"])


@pytest.fixture(scope="module")
def outside_scoped_admin(write_conn, outside_org_pk):
    """A SAKHA-scoped admin whose scope is the THIRD org — outside source/dest."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA",
        organization_pk=outside_org_pk, home_org_pk=outside_org_pk,
    )


@pytest.fixture(scope="module")
def outside_scoped_headers(client, outside_scoped_admin):
    return _login_headers(client, outside_scoped_admin["sangha_sevi_id"], outside_scoped_admin["password"])


@pytest.fixture(scope="module")
def member_user(write_conn, source_org_pk):
    from api.services.auth_service import hash_password
    data = _create_member_with_home_affiliation(write_conn, "SecMember", organization_pk=source_org_pk)
    cur = write_conn.cursor()
    password = "SecMemberPass1x"
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
    """, (data["person_pk"], hash_password(password)))
    data["password"] = password
    return data


@pytest.fixture(scope="module")
def member_headers(client, member_user):
    return _login_headers(client, member_user["sangha_sevi_id"], member_user["password"])


def _create_request_pk(client, member_headers, member_user, dest_org_pk, request_type="TRANSFER"):
    resp = client.post(BASE, headers=member_headers, json={
        "sangha_sevi_pk": member_user["sangha_sevi_pk"],
        "request_type": request_type,
        "new_organization_pk": dest_org_pk,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["membership_change_request_pk"]


# ═══════════════════════════════════════════════════════════════════════
# source_decision — admin-scope negative
# ═══════════════════════════════════════════════════════════════════════

class TestSourceDecisionScope:
    def test_out_of_scope_admin_cannot_release(
        self, client, outside_scoped_headers, member_headers, member_user, dest_org_pk,
    ):
        pk = _create_request_pk(client, member_headers, member_user, dest_org_pk)
        resp = client.post(f"{BASE}/{pk}/source-decision", headers=outside_scoped_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 403
        assert "You can only release this member's affiliation within your admin scope." in resp.text

    def test_nss_wide_admin_can_release_anywhere(
        self, client, nss_wide_headers, member_headers, member_user, dest_org_pk,
    ):
        pk = _create_request_pk(client, member_headers, member_user, dest_org_pk)
        resp = client.post(f"{BASE}/{pk}/source-decision", headers=nss_wide_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 200, resp.text


# ═══════════════════════════════════════════════════════════════════════
# destination_decision — admin-scope negative
# ═══════════════════════════════════════════════════════════════════════

class TestDestinationDecisionScope:
    def _pending_destination(self, client, nss_wide_headers, member_headers, member_user, dest_org_pk):
        pk = _create_request_pk(client, member_headers, member_user, dest_org_pk)
        resp = client.post(f"{BASE}/{pk}/source-decision", headers=nss_wide_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 200, resp.text
        return pk

    def test_out_of_scope_admin_cannot_accept(
        self, client, nss_wide_headers, outside_scoped_headers, member_headers, member_user, dest_org_pk,
    ):
        pk = self._pending_destination(client, nss_wide_headers, member_headers, member_user, dest_org_pk)
        resp = client.post(f"{BASE}/{pk}/destination-decision", headers=outside_scoped_headers, json={
            "decision": "ACCEPT",
        })
        assert resp.status_code == 403
        assert "You can only accept this member into this Sakha within your admin scope." in resp.text

    def test_out_of_scope_admin_cannot_reject(
        self, client, nss_wide_headers, outside_scoped_headers, member_headers, member_user, dest_org_pk,
    ):
        pk = self._pending_destination(client, nss_wide_headers, member_headers, member_user, dest_org_pk)
        resp = client.post(f"{BASE}/{pk}/destination-decision", headers=outside_scoped_headers, json={
            "decision": "REJECT",
        })
        assert resp.status_code == 403
        assert "You can only accept this member into this Sakha within your admin scope." in resp.text


# ═══════════════════════════════════════════════════════════════════════
# Permission negatives (no MEMBERSHIP_APPROVE at all)
# ═══════════════════════════════════════════════════════════════════════

class TestNoMembershipApprovePermission:
    def test_source_decision_requires_membership_approve(self, client, member_headers):
        """member_headers holds no MEMBERSHIP_APPROVE at all — dependency-level 403."""
        resp = client.post(f"{BASE}/{FAKE_UUID}/source-decision", headers=member_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 403

    def test_destination_decision_requires_membership_approve(self, client, member_headers):
        resp = client.post(f"{BASE}/{FAKE_UUID}/destination-decision", headers=member_headers, json={
            "decision": "ACCEPT",
        })
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Anonymous access
# ═══════════════════════════════════════════════════════════════════════

class TestAnonymousAccess:
    def test_create_requires_auth(self, anon_client, source_org_pk, dest_org_pk):
        resp = anon_client.post(BASE, json={
            "sangha_sevi_pk": FAKE_UUID,
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code in (401, 403)

    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_get_requires_auth(self, anon_client):
        resp = anon_client.get(f"{BASE}/{FAKE_UUID}")
        assert resp.status_code in (401, 403)

    def test_source_decision_requires_auth(self, anon_client):
        resp = anon_client.post(f"{BASE}/{FAKE_UUID}/source-decision", json={"decision": "RELEASE"})
        assert resp.status_code in (401, 403)

    def test_destination_decision_requires_auth(self, anon_client):
        resp = anon_client.post(f"{BASE}/{FAKE_UUID}/destination-decision", json={"decision": "ACCEPT"})
        assert resp.status_code in (401, 403)
