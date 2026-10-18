"""
NSS ERP — Tier 6 Membership Change Request API tests (MBR-048/MBR-049).

Integration tests for the Sakha Transfer / Apply for Darshak two-step
request/release/accept workflow on nss.membership_change_request:
  1. create_change_request  — self-service vs admin-on-behalf-of, validations
  2. list_change_requests   — self view vs admin (scoped) view, 'requests' key
  3. get_change_request     — self/admin/neither
  4. source_decision         — RELEASE -> PENDING_DESTINATION_ACCEPT, REJECT
  5. destination_decision    — ACCEPT -> COMPLETED (TRANSFER vs DARSHAK), REJECT

Runs against local PostgreSQL. The database must be bootstrapped with
DDL + seed before running (database/ddl/08_governance et al. for
MEMBERSHIP_MANAGE/MEMBERSHIP_VIEW/MEMBERSHIP_APPROVE permissions).
"""

from datetime import date
from uuid import uuid4

import pytest

from api.helpers import insert_sakha_affiliation, next_festival_date_on_or_after

pytestmark = pytest.mark.integration

BASE = "/api/v1/membership/change-requests"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "MbrAdminPass1"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

def _active_sakha_org_pks(write_conn, limit: int = 2):
    """Two distinct active SAKHA_SANGHA organization_pks (source vs destination)."""
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


def _create_member_with_home_affiliation(
    write_conn, label: str, *, organization_pk: str, membership_type_code: str = "REGULAR"
):
    """
    Throwaway person + active sangha_sevi + open membership_sakha_affiliation
    row at *organization_pk* (the "home Sakha"), via the canonical
    insert_sakha_affiliation() helper — _attach_active_membership() alone
    (as used by test_governance.py) does NOT open an affiliation row, and
    create_change_request()'s home-Sakha lookup specifically requires one.

    Returns dict with person_pk, sangha_sevi_pk, sangha_sevi_id, organization_pk.
    """
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute(
        """
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s)
        RETURNING person_pk
        """,
        (f"MCR{suffix}", label, suffix, f"mcr.{suffix.lower()}@example.test"),
    )
    person_pk = cur.fetchone()[0]

    membership_type_pk = _membership_type_pk(write_conn, membership_type_code)
    membership_status_pk = _membership_status_active_pk(write_conn)

    sangha_sevi_id = f"MSS{suffix}"
    cur.execute(
        """
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        RETURNING sangha_sevi_pk
        """,
        (sangha_sevi_id, str(person_pk), str(membership_type_pk),
         str(membership_status_pk), str(organization_pk)),
    )
    sangha_sevi_pk = cur.fetchone()[0]

    insert_sakha_affiliation(
        cur,
        sangha_sevi_pk=str(sangha_sevi_pk),
        organization_pk=str(organization_pk),
        local_number=None,
        effective_from=date(2020, 4, 1),
        is_darshak=False,
        source_event_type="ENROLLMENT",
    )

    return {
        "person_pk": str(person_pk),
        "sangha_sevi_pk": str(sangha_sevi_pk),
        "sangha_sevi_id": sangha_sevi_id,
        "organization_pk": str(organization_pk),
    }


def _create_admin_with_scope(write_conn, *, role_code: str, scope_level: str, organization_pk, home_org_pk: str):
    """Mirrors test_governance.py's helper — dedicated admin person/account/role/scope."""
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    membership_type_pk = _membership_type_pk(write_conn, "REGULAR")
    membership_status_pk = _membership_status_active_pk(write_conn)

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"MADM{suffix}", "MbrAdmin", suffix, f"madm.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"MSSADM{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), home_org_pk))

    password = f"{ADMIN_PASSWORD}{suffix[:4]}"
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
    assert role_row, f"{role_code} role not found in database."
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
def sakha_org_pks(write_conn):
    return _active_sakha_org_pks(write_conn, 2)


@pytest.fixture(scope="module")
def source_org_pk(sakha_org_pks):
    return sakha_org_pks[0]


@pytest.fixture(scope="module")
def dest_org_pk(sakha_org_pks):
    return sakha_org_pks[1]


@pytest.fixture(scope="module")
def member_user(write_conn, source_org_pk):
    """A self-service member, home Sakha = source_org_pk, with login credentials."""
    from api.services.auth_service import hash_password

    data = _create_member_with_home_affiliation(write_conn, "Member", organization_pk=source_org_pk)
    cur = write_conn.cursor()
    password = "MemberPass1x"
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


@pytest.fixture(scope="module")
def manage_admin(write_conn, source_org_pk, dest_org_pk):
    """NSS-WIDE admin holding MEMBERSHIP_MANAGE/MEMBERSHIP_VIEW/MEMBERSHIP_APPROVE everywhere."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE",
        organization_pk=None, home_org_pk=source_org_pk,
    )


@pytest.fixture(scope="module")
def manage_headers(client, manage_admin):
    return _login_headers(client, manage_admin["sangha_sevi_id"], manage_admin["password"])


@pytest.fixture(scope="module")
def plain_member_user(write_conn, source_org_pk):
    """Second self-service member with NO MEMBERSHIP_MANAGE — for 403 negative tests."""
    from api.services.auth_service import hash_password

    data = _create_member_with_home_affiliation(write_conn, "Plain", organization_pk=source_org_pk)
    cur = write_conn.cursor()
    password = "PlainPass1x"
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
    """, (data["person_pk"], hash_password(password)))
    data["password"] = password
    return data


@pytest.fixture(scope="module")
def plain_headers(client, plain_member_user):
    return _login_headers(client, plain_member_user["sangha_sevi_id"], plain_member_user["password"])


# ═══════════════════════════════════════════════════════════════════════
# create_change_request
# ═══════════════════════════════════════════════════════════════════════

class TestCreateChangeRequest:
    def test_self_service_create_succeeds(self, client, member_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "PENDING_SOURCE_RELEASE"
        assert body["request_type"] == "TRANSFER"
        assert body["old_organization_pk"] == member_user["organization_pk"]
        assert body["new_organization_pk"] == dest_org_pk

    def test_admin_on_behalf_of_succeeds(self, client, manage_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=manage_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "DARSHAK",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        assert resp.json()["request_type"] == "DARSHAK"

    def test_neither_self_nor_manage_rejected(self, client, plain_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=plain_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 403
        assert "You may only file a change request for yourself unless you hold MEMBERSHIP_MANAGE." in resp.text

    def test_same_source_and_destination_rejected(self, client, member_headers, member_user):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": member_user["organization_pk"],
        })
        assert resp.status_code == 422
        assert "The destination Sakha must be different from the current Sakha." in resp.text

    def test_no_active_home_affiliation_rejected(self, client, manage_headers, write_conn, dest_org_pk, source_org_pk):
        """A member with a sangha_sevi row but no open membership_sakha_affiliation."""
        from uuid import uuid4 as _u
        suffix = _u().hex[:10].upper()
        cur = write_conn.cursor()
        cur.execute("""
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) RETURNING person_pk
        """, (f"NOAFF{suffix}", "NoAff", suffix, f"noaff.{suffix.lower()}@example.test"))
        person_pk = cur.fetchone()[0]
        membership_type_pk = _membership_type_pk(write_conn, "REGULAR")
        membership_status_pk = _membership_status_active_pk(write_conn)
        cur.execute("""
            INSERT INTO nss.sangha_sevi (
                sangha_sevi_id, person_pk, membership_type_master_data_pk,
                membership_status_master_data_pk, organization_pk, joining_date
            ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
            RETURNING sangha_sevi_pk
        """, (f"NOAFFSS{suffix}", str(person_pk), str(membership_type_pk),
              str(membership_status_pk), source_org_pk))
        sangha_sevi_pk = cur.fetchone()[0]

        resp = client.post(BASE, headers=manage_headers, json={
            "sangha_sevi_pk": str(sangha_sevi_pk),
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 422
        assert "This member has no active Sakha affiliation to transfer or attend from." in resp.text

    def test_anonymous_rejected(self, anon_client, member_user, dest_org_pk):
        resp = anon_client.post(BASE, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# list_change_requests
# ═══════════════════════════════════════════════════════════════════════

class TestListChangeRequests:
    def test_response_uses_requests_key(self, client, manage_headers):
        resp = client.get(BASE, headers=manage_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "requests" in body
        assert "items" not in body
        assert "total" in body

    def test_self_view_filters_to_own_requests(self, client, member_headers, member_user):
        resp = client.get(BASE, headers=member_headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json()["requests"]
        for row in rows:
            assert row["sangha_sevi_pk"] == member_user["sangha_sevi_pk"]

    def test_neither_admin_view_nor_own_sevi_rejected(self, client, write_conn):
        """A logged-in user with no sangha_sevi_pk and no MEMBERSHIP_VIEW/APPROVE."""
        from api.services.auth_service import hash_password
        from uuid import uuid4 as _u
        suffix = _u().hex[:10].upper()
        cur = write_conn.cursor()
        cur.execute("""
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) RETURNING person_pk
        """, (f"BARE{suffix}", "Bare", suffix, f"bare.{suffix.lower()}@example.test"))
        person_pk = cur.fetchone()[0]
        password = "BarePass1x"
        cur.execute("""
            INSERT INTO nss.user_account (
                person_pk, password_hash, account_status, force_password_change, password_expires_at
            ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        """, (str(person_pk), hash_password(password)))

        headers = _login_headers(client, f"BARE{suffix}", password)
        resp = client.get(BASE, headers=headers)
        assert resp.status_code == 403
        assert "You do not have permission to view change requests." in resp.text

    def test_anonymous_rejected(self, anon_client):
        resp = anon_client.get(BASE)
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# get_change_request
# ═══════════════════════════════════════════════════════════════════════

class TestGetChangeRequest:
    @pytest.fixture(scope="class")
    def created_request_pk(self, client, member_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        return resp.json()["membership_change_request_pk"]

    def test_not_found(self, client, manage_headers):
        resp = client.get(f"{BASE}/{FAKE_UUID}", headers=manage_headers)
        assert resp.status_code == 404
        assert "Change request not found." in resp.text

    def test_self_can_view_own(self, client, member_headers, created_request_pk):
        resp = client.get(f"{BASE}/{created_request_pk}", headers=member_headers)
        assert resp.status_code == 200, resp.text

    def test_admin_can_view(self, client, manage_headers, created_request_pk):
        resp = client.get(f"{BASE}/{created_request_pk}", headers=manage_headers)
        assert resp.status_code == 200, resp.text

    def test_neither_self_nor_admin_rejected(self, client, plain_headers, created_request_pk):
        resp = client.get(f"{BASE}/{created_request_pk}", headers=plain_headers)
        assert resp.status_code == 403
        assert "You do not have access to this change request." in resp.text


# ═══════════════════════════════════════════════════════════════════════
# source_decision
# ═══════════════════════════════════════════════════════════════════════

class TestSourceDecision:
    @pytest.fixture()
    def fresh_request_pk(self, client, member_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        return resp.json()["membership_change_request_pk"]

    def test_not_found(self, client, manage_headers):
        resp = client.post(f"{BASE}/{FAKE_UUID}/source-decision", headers=manage_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 404
        assert "Change request not found." in resp.text

    def test_release_moves_to_pending_destination_accept(self, client, manage_headers, fresh_request_pk):
        resp = client.post(f"{BASE}/{fresh_request_pk}/source-decision", headers=manage_headers, json={
            "decision": "RELEASE", "remarks": "ok to go",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "PENDING_DESTINATION_ACCEPT"

    def test_wrong_status_rejected(self, client, manage_headers, fresh_request_pk):
        # First call already moved it to PENDING_DESTINATION_ACCEPT.
        client.post(f"{BASE}/{fresh_request_pk}/source-decision", headers=manage_headers, json={
            "decision": "RELEASE",
        })
        resp = client.post(f"{BASE}/{fresh_request_pk}/source-decision", headers=manage_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 422
        assert "a source decision is no longer applicable." in resp.text

    def test_reject_sets_rejected_by_source(self, client, manage_headers, member_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        pk = resp.json()["membership_change_request_pk"]

        resp = client.post(f"{BASE}/{pk}/source-decision", headers=manage_headers, json={
            "decision": "REJECT", "remarks": "no",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "REJECTED_BY_SOURCE"

    def test_no_membership_approve_rejected(self, client, plain_headers, fresh_request_pk):
        resp = client.post(f"{BASE}/{fresh_request_pk}/source-decision", headers=plain_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 403

    def test_anonymous_rejected(self, anon_client, fresh_request_pk):
        resp = anon_client.post(f"{BASE}/{fresh_request_pk}/source-decision", json={
            "decision": "RELEASE",
        })
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# destination_decision
# ═══════════════════════════════════════════════════════════════════════

class TestDestinationDecision:
    @pytest.fixture()
    def pending_destination_request(self, client, manage_headers, member_headers, member_user, dest_org_pk, request_type="TRANSFER"):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        pk = resp.json()["membership_change_request_pk"]
        resp = client.post(f"{BASE}/{pk}/source-decision", headers=manage_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 200, resp.text
        return pk

    def _make_pending_destination(self, client, manage_headers, member_headers, sangha_sevi_pk, dest_org_pk, request_type):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": sangha_sevi_pk,
            "request_type": request_type,
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        pk = resp.json()["membership_change_request_pk"]
        resp = client.post(f"{BASE}/{pk}/source-decision", headers=manage_headers, json={
            "decision": "RELEASE",
        })
        assert resp.status_code == 200, resp.text
        return pk

    def test_not_found(self, client, manage_headers):
        resp = client.post(f"{BASE}/{FAKE_UUID}/destination-decision", headers=manage_headers, json={
            "decision": "ACCEPT",
        })
        assert resp.status_code == 404
        assert "Change request not found." in resp.text

    def test_new_local_number_without_legacy_import_rejected_before_lookup(self, client, manage_headers):
        """
        The is_legacy_import/new_local_number pairing check runs BEFORE the
        DB lookup — testable even against a nonexistent PK.
        """
        resp = client.post(f"{BASE}/{FAKE_UUID}/destination-decision", headers=manage_headers, json={
            "decision": "ACCEPT", "new_local_number": "123",
        })
        assert resp.status_code == 422
        assert "new_local_number may only be set together with is_legacy_import=true." in resp.text

    def test_wrong_status_rejected(self, client, manage_headers, member_headers, member_user, dest_org_pk):
        resp = client.post(BASE, headers=member_headers, json={
            "sangha_sevi_pk": member_user["sangha_sevi_pk"],
            "request_type": "TRANSFER",
            "new_organization_pk": dest_org_pk,
        })
        assert resp.status_code == 201, resp.text
        pk = resp.json()["membership_change_request_pk"]
        # Still PENDING_SOURCE_RELEASE — destination decision not yet applicable.
        resp = client.post(f"{BASE}/{pk}/destination-decision", headers=manage_headers, json={
            "decision": "ACCEPT",
        })
        assert resp.status_code == 422
        assert "a destination decision is no longer applicable." in resp.text

    def test_reject_sets_rejected_by_destination(self, client, manage_headers, member_headers, member_user, dest_org_pk):
        pk = self._make_pending_destination(
            client, manage_headers, member_headers, member_user["sangha_sevi_pk"], dest_org_pk, "TRANSFER",
        )
        resp = client.post(f"{BASE}/{pk}/destination-decision", headers=manage_headers, json={
            "decision": "REJECT", "remarks": "not now",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "REJECTED_BY_DESTINATION"

    def test_accept_transfer_completes_and_closes_old_affiliation(
        self, client, manage_headers, member_headers, write_conn, source_org_pk, dest_org_pk,
    ):
        festival_date = next_festival_date_on_or_after(write_conn.cursor(), "DOLA_PURNIMA", date.today())
        if festival_date is None:
            pytest.skip("No confirmed DOLA_PURNIMA festival date on/after today — cannot exercise ACCEPT.")

        member = _create_member_with_home_affiliation(write_conn, "XferAccept", organization_pk=source_org_pk)

        pk = self._make_pending_destination(
            client, manage_headers, member_headers, member["sangha_sevi_pk"], dest_org_pk, "TRANSFER",
        )
        resp = client.post(f"{BASE}/{pk}/destination-decision", headers=manage_headers, json={
            "decision": "ACCEPT", "remarks": "welcome",
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert body["effective_date"] == str(festival_date)

        cur = write_conn.cursor()
        cur.execute("""
            SELECT effective_to, affiliation_status FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = %s AND organization_pk = %s
        """, (member["sangha_sevi_pk"], source_org_pk))
        old_row = cur.fetchone()
        assert old_row is not None
        assert old_row[0] is not None  # closed
        assert old_row[1] == "ARCHIVED"

        cur.execute("""
            SELECT effective_to FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = %s AND organization_pk = %s
        """, (member["sangha_sevi_pk"], dest_org_pk))
        new_row = cur.fetchone()
        assert new_row is not None
        assert new_row[0] is None  # still open

        cur.execute("""
            SELECT transfer_type, transfer_reason FROM nss.membership_transfer_history
            WHERE sangha_sevi_pk = %s
        """, (member["sangha_sevi_pk"],))
        hist_row = cur.fetchone()
        assert hist_row is not None
        assert hist_row[0] == "SAKHA_TRANSFER"
        assert hist_row[1] is None

        cur.execute("""
            SELECT event_type FROM nss.membership_journey_event WHERE sangha_sevi_pk = %s
        """, (member["sangha_sevi_pk"],))
        event_row = cur.fetchone()
        assert event_row is not None
        assert event_row[0] == "TRANSFER"

    def test_accept_darshak_keeps_old_affiliation_open(
        self, client, manage_headers, member_headers, write_conn, source_org_pk, dest_org_pk,
    ):
        festival_date = next_festival_date_on_or_after(write_conn.cursor(), "DOLA_PURNIMA", date.today())
        if festival_date is None:
            pytest.skip("No confirmed DOLA_PURNIMA festival date on/after today — cannot exercise ACCEPT.")

        member = _create_member_with_home_affiliation(write_conn, "DarshakAccept", organization_pk=source_org_pk)

        pk = self._make_pending_destination(
            client, manage_headers, member_headers, member["sangha_sevi_pk"], dest_org_pk, "DARSHAK",
        )
        resp = client.post(f"{BASE}/{pk}/destination-decision", headers=manage_headers, json={
            "decision": "ACCEPT",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "COMPLETED"

        cur = write_conn.cursor()
        cur.execute("""
            SELECT effective_to FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = %s AND organization_pk = %s
        """, (member["sangha_sevi_pk"], source_org_pk))
        old_row = cur.fetchone()
        assert old_row is not None
        assert old_row[0] is None  # still open — DARSHAK never closes the home affiliation

        cur.execute("""
            SELECT event_type FROM nss.membership_journey_event WHERE sangha_sevi_pk = %s
        """, (member["sangha_sevi_pk"],))
        event_row = cur.fetchone()
        assert event_row is not None
        assert event_row[0] == "DARSHAK_ATTENDANCE_STARTED"

        cur.execute("""
            SELECT COUNT(*) FROM nss.membership_transfer_history WHERE sangha_sevi_pk = %s
        """, (member["sangha_sevi_pk"],))
        assert cur.fetchone()[0] == 0  # DARSHAK never writes transfer history

    def test_no_membership_approve_rejected(self, client, plain_headers):
        resp = client.post(f"{BASE}/{FAKE_UUID}/destination-decision", headers=plain_headers, json={
            "decision": "ACCEPT",
        })
        assert resp.status_code == 403

    def test_anonymous_rejected(self, anon_client):
        resp = anon_client.post(f"{BASE}/{FAKE_UUID}/destination-decision", json={
            "decision": "ACCEPT",
        })
        assert resp.status_code in (401, 403)
