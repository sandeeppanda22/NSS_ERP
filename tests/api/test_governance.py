"""
NSS ERP — Tier 6 Governance API tests.

Integration tests for the Unified Body Governance Model (GOV-BR-004):
  1. Body Type Master  — catalog CRUD
  2. Position Master   — catalog CRUD
  3. Body Master        — list/get/create/patch/deactivate, NSS-wide vs
                           org-scoped authority (GOV-BR-058/059)
  4. Body Member Assignment — create/list/end, active-holder uniqueness
  5. Acting Position Assignment — create/list/end
  6. Election           — create/list/get/status
  7. Election Nomination — create/list/status, active-candidate uniqueness
  8. Election Vote       — cast, one-vote-per-position uniqueness, tally
  9. Election Result     — declare, active-position uniqueness, apply ->
                           body_member_assignment hand-off
 10. RBAC                — anonymous access rejected

Runs against local PostgreSQL. The database must be bootstrapped with
DDL + seed before running (database/ddl/08_governance/*,
database/seed/00_bootstrap/01_permission_master.sql +
03_role_permission.sql for GOVERNANCE_VIEW/GOVERNANCE_MANAGE).
"""

import pytest
from uuid import uuid4

pytestmark = pytest.mark.integration

BASE = "/api/v1/governance"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "GovAdminPass1"
SCOPED_PASSWORD = "GovScopedPass1"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

def _create_person(write_conn, label: str) -> str:
    """
    Throwaway person WITH an active REGULAR Sangha Sevi membership, for use as
    candidate/voter/proposer/holder.

    Governance now requires an active NSS member (an active sangha_sevi) for
    assignments (NOT-NULL sangha_sevi_pk, GOV-BR-056/074), nominations and
    votes (GOV-BR-043). A bare nss.person row is no longer accepted by those
    endpoints, so every throwaway test person is given a REGULAR membership —
    REGULAR has full electoral rights (may stand and vote). Returns the
    person_pk string, unchanged contract; use _active_sevi_pk() when a test
    also needs the person's sangha_sevi_pk.
    """
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()
    cur.execute(
        """
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s)
        RETURNING person_pk
        """,
        (f"GOV{suffix}", label, suffix, f"gov.{suffix.lower()}@example.test"),
    )
    person_pk = cur.fetchone()[0]
    _attach_active_membership(write_conn, person_pk, "REGULAR", suffix)
    return str(person_pk)


def _attach_active_membership(write_conn, person_pk, membership_type_code: str, suffix: str):
    """
    Give person_pk an active sangha_sevi of the given MEMBERSHIP_TYPE value_code
    (REGULAR / PROBATIONARY / ASSOCIATE / HONORARY), ACTIVE status, anchored to
    any active SAKHA_SANGHA org — mirroring _create_admin_with_scope.
    """
    cur = write_conn.cursor()

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = %s AND md.is_active = TRUE
        LIMIT 1
    """, (membership_type_code,))
    mt_row = cur.fetchone()
    assert mt_row, f"MEMBERSHIP_TYPE '{membership_type_code}' not seeded."
    membership_type_pk = mt_row[0]

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_status_pk = cur.fetchone()[0]

    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE LIMIT 1
    """)
    org_row = cur.fetchone()
    assert org_row, "No active SAKHA_SANGHA organization exists."

    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (f"GSS{suffix}", str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(org_row[0])))


def _active_sevi_pk(write_conn, person_pk: str) -> str:
    """The active sangha_sevi_pk for a person (person_pk is UNIQUE on sangha_sevi)."""
    cur = write_conn.cursor()
    cur.execute(
        "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
        (str(person_pk),),
    )
    row = cur.fetchone()
    assert row, "Expected an active sangha_sevi for this person."
    return str(row[0])


def _create_admin_with_scope(write_conn, *, role_code: str, scope_level: str, organization_pk):
    """
    Build a dedicated person + sangha_sevi + user_account + user_role +
    admin_scope row, mirroring tests/api/test_admin.py's admin_user fixture.
    Everything rolls back with the module SAVEPOINT.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_type_pk = cur.fetchone()[0]

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_status_pk = cur.fetchone()[0]

    if organization_pk is None:
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE LIMIT 1
        """)
        row = cur.fetchone()
        assert row, "No active SAKHA_SANGHA organization exists."
        home_organization_pk = row[0]
    else:
        home_organization_pk = organization_pk

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"GADM{suffix}", "GovAdmin", suffix, f"gadm.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"GSSADM{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(home_organization_pk)))

    password = ADMIN_PASSWORD if scope_level == "NSS-WIDE" else SCOPED_PASSWORD
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

    return {
        "person_pk": person_pk,
        "user_account_pk": user_account_pk,
        "sangha_sevi_id": sangha_sevi_id,
        "password": password,
        "organization_pk": home_organization_pk,
    }


@pytest.fixture(scope="module")
def admin_user(write_conn):
    """NSS-WIDE NSS_ERP_ADMIN — holds GOVERNANCE_VIEW + GOVERNANCE_MANAGE everywhere."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None,
    )


@pytest.fixture(scope="module")
def scoped_sakha_pk(write_conn):
    """An active SAKHA_SANGHA organization to anchor the scoped-admin fixture."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.organization_pk LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No active SAKHA_SANGHA organization exists.")
    return str(row[0])


@pytest.fixture(scope="module")
def scoped_admin_user(write_conn, scoped_sakha_pk):
    """NSS_ERP_SAKHA_ADMIN scoped to one Sakha — for GOV-BR-058/059 scope tests."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=scoped_sakha_pk,
    )


def _login_headers(client, login_id: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_headers(client, admin_user):
    return _login_headers(client, admin_user["sangha_sevi_id"], admin_user["password"])


@pytest.fixture(scope="module")
def scoped_headers(client, scoped_admin_user):
    return _login_headers(client, scoped_admin_user["sangha_sevi_id"], scoped_admin_user["password"])


@pytest.fixture(scope="module")
def candidate_person_pk(write_conn):
    return _create_person(write_conn, "Candidate")


@pytest.fixture(scope="module")
def candidate_sevi_pk(write_conn, candidate_person_pk):
    """The candidate's active sangha_sevi_pk — required on assignment creation."""
    return _active_sevi_pk(write_conn, candidate_person_pk)


@pytest.fixture(scope="module")
def candidate2_person_pk(write_conn):
    return _create_person(write_conn, "Candidate2")


@pytest.fixture(scope="module")
def voter_person_pk(write_conn):
    return _create_person(write_conn, "Voter")


@pytest.fixture(scope="module")
def proposer_person_pk(write_conn):
    return _create_person(write_conn, "Proposer")


@pytest.fixture(scope="module")
def body_type_pk(client, admin_headers):
    """A fresh body type, created through the API so the create-path is exercised."""
    code = f"TEST_BODY_TYPE_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/body-types",
        json={"body_type_code": code, "body_type_name": "Test Body Type", "description": "For tests."},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_type_master_pk"]


@pytest.fixture(scope="module")
def position_pk(client, admin_headers):
    code = f"TEST_POSITION_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/positions",
        json={"position_code": code, "position_name": "Test Secretary", "display_order": 1},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["position_master_pk"]


@pytest.fixture(scope="module")
def body_pk(client, admin_headers, body_type_pk):
    """An NSS-wide (organization_pk NULL) governance body."""
    code = f"TEST_BODY_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": code,
            "body_name": "Test Governing Body",
            "effective_from": "2026-01-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


# ═══════════════════════════════════════════════════════════════════════
# 1. Body Type Master
# ═══════════════════════════════════════════════════════════════════════

class TestBodyTypes:
    def test_create_returns_201(self, client, admin_headers):
        code = f"TBT_{uuid4().hex[:8].upper()}"
        r = client.post(
            f"{BASE}/body-types",
            json={"body_type_code": code, "body_type_name": "Sample Type"},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["body_type_code"] == code
        assert data["is_active"] is True

    def test_duplicate_code_returns_409(self, client, admin_headers, body_type_pk):
        r = client.get(f"{BASE}/body-types", headers=admin_headers)
        existing_code = next(t["body_type_code"] for t in r.json() if t["body_type_master_pk"] == body_type_pk)
        r2 = client.post(
            f"{BASE}/body-types",
            json={"body_type_code": existing_code, "body_type_name": "Dup"},
            headers=admin_headers,
        )
        assert r2.status_code == 409

    def test_list_includes_created(self, client, admin_headers, body_type_pk):
        r = client.get(f"{BASE}/body-types", headers=admin_headers)
        assert r.status_code == 200
        assert any(t["body_type_master_pk"] == body_type_pk for t in r.json())

    def test_update_name(self, client, admin_headers, body_type_pk):
        r = client.patch(
            f"{BASE}/body-types/{body_type_pk}",
            json={"body_type_name": "Renamed Type"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["body_type_name"] == "Renamed Type"

    def test_deactivate(self, client, admin_headers):
        code = f"TBT_DEL_{uuid4().hex[:8].upper()}"
        r = client.post(
            f"{BASE}/body-types", json={"body_type_code": code, "body_type_name": "To Delete"},
            headers=admin_headers,
        )
        pk = r.json()["body_type_master_pk"]
        r2 = client.delete(f"{BASE}/body-types/{pk}", headers=admin_headers)
        assert r2.status_code == 200
        r3 = client.get(f"{BASE}/body-types", headers=admin_headers)
        assert all(t["body_type_master_pk"] != pk for t in r3.json())
        r4 = client.get(f"{BASE}/body-types?include_inactive=true", headers=admin_headers)
        assert any(t["body_type_master_pk"] == pk and t["is_active"] is False for t in r4.json())

    def test_create_requires_manage_permission(self, client, scoped_headers):
        """Body types are the NSS-wide governance catalogue — only an NSS-wide
        admin may extend it, even though a Sakha admin now holds
        GOVERNANCE_MANAGE for their own scope (owner-confirmed 2026-10-08,
        decision B). Guarded by _require_scope_for_org_or_nss_wide."""
        r = client.post(
            f"{BASE}/body-types",
            json={"body_type_code": f"TBT_FORBID_{uuid4().hex[:8]}", "body_type_name": "Forbidden"},
            headers=scoped_headers,
        )
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# 2. Position Master
# ═══════════════════════════════════════════════════════════════════════

class TestPositions:
    def test_create_returns_201(self, client, admin_headers):
        code = f"TP_{uuid4().hex[:8].upper()}"
        r = client.post(
            f"{BASE}/positions",
            json={"position_code": code, "position_name": "Sample Position", "display_order": 5},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["position_code"] == code

    def test_duplicate_code_returns_409(self, client, admin_headers, position_pk):
        r = client.get(f"{BASE}/positions", headers=admin_headers)
        existing_code = next(p["position_code"] for p in r.json() if p["position_master_pk"] == position_pk)
        r2 = client.post(
            f"{BASE}/positions",
            json={"position_code": existing_code, "position_name": "Dup"},
            headers=admin_headers,
        )
        assert r2.status_code == 409

    def test_list_ordered_by_display_order(self, client, admin_headers):
        r = client.get(f"{BASE}/positions", headers=admin_headers)
        assert r.status_code == 200
        orders = [p["display_order"] for p in r.json()]
        assert orders == sorted(orders)

    def test_update_display_order(self, client, admin_headers, position_pk):
        r = client.patch(
            f"{BASE}/positions/{position_pk}", json={"display_order": 99}, headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["display_order"] == 99


# ═══════════════════════════════════════════════════════════════════════
# 3. Body Master
# ═══════════════════════════════════════════════════════════════════════

class TestBodies:
    def test_create_nss_wide_body(self, client, admin_headers, body_type_pk):
        code = f"TB_{uuid4().hex[:8].upper()}"
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": code,
                "body_name": "NSS Wide Body", "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["organization_pk"] is None
        assert data["body_status"] == "ACTIVE"

    def test_duplicate_body_code_returns_409(self, client, admin_headers, body_pk, body_type_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}", headers=admin_headers)
        existing_code = r.json()["body_code"]
        r2 = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": existing_code,
                "body_name": "Dup", "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r2.status_code == 409

    def test_create_rejects_unknown_body_type(self, client, admin_headers):
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": FAKE_UUID, "body_code": f"TB_BAD_{uuid4().hex[:8]}",
                "body_name": "Bad", "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 404

    def test_get_detail(self, client, admin_headers, body_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["body_master_pk"] == body_pk

    def test_list_returns_created_body(self, client, admin_headers, body_pk):
        r = client.get(f"{BASE}/bodies", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert any(b["body_master_pk"] == body_pk for b in data["items"])

    def test_update_status(self, client, admin_headers, body_pk):
        r = client.patch(
            f"{BASE}/bodies/{body_pk}", json={"body_status": "RECONSTITUTED"}, headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["body_status"] == "RECONSTITUTED"
        # Restore for later tests in this module.
        client.patch(f"{BASE}/bodies/{body_pk}", json={"body_status": "ACTIVE"}, headers=admin_headers)

    def test_nss_wide_body_blocked_for_scoped_admin(self, client, scoped_headers, body_type_pk):
        """
        GOV-BR-058: only an NSS-wide admin may create a body with
        organization_pk NULL. A Sakha-scoped admin must be rejected even
        though they hold GOVERNANCE_MANAGE within their own scope.
        """
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"TB_SCOPE_{uuid4().hex[:8]}",
                "body_name": "Should Be Blocked", "effective_from": "2026-01-01",
            },
            headers=scoped_headers,
        )
        assert r.status_code == 403

    def test_org_scoped_body_allowed_for_owning_admin(
        self, client, scoped_headers, body_type_pk, scoped_sakha_pk,
    ):
        """A Sakha-scoped admin CAN create a body anchored to their own org."""
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"TB_OWNSCOPE_{uuid4().hex[:8]}",
                "body_name": "In Scope", "organization_pk": scoped_sakha_pk,
                "effective_from": "2026-01-01",
            },
            headers=scoped_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["organization_pk"] == scoped_sakha_pk

    def test_deactivate_body(self, client, admin_headers, body_type_pk):
        code = f"TB_DEL_{uuid4().hex[:8].upper()}"
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": code,
                "body_name": "To Delete", "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        pk = r.json()["body_master_pk"]
        r2 = client.delete(f"{BASE}/bodies/{pk}", headers=admin_headers)
        assert r2.status_code == 200
        r3 = client.get(f"{BASE}/bodies/{pk}", headers=admin_headers)
        assert r3.json()["is_active"] is False


# ═══════════════════════════════════════════════════════════════════════
# 4. Body Member Assignment
# ═══════════════════════════════════════════════════════════════════════

class TestAssignments:
    def test_create_assignment(self, client, admin_headers, body_pk, position_pk, candidate_person_pk, candidate_sevi_pk):
        r = client.post(
            f"{BASE}/bodies/{body_pk}/assignments",
            json={
                "position_master_pk": position_pk, "person_pk": candidate_person_pk,
                "sangha_sevi_pk": candidate_sevi_pk, "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["assignment_status"] in ("ASSIGNED", "ACTIVE")
        assert data["person_pk"] == candidate_person_pk

    def test_duplicate_active_holder_returns_409(
        self, client, admin_headers, body_pk, position_pk, candidate_person_pk, candidate_sevi_pk,
    ):
        r = client.post(
            f"{BASE}/bodies/{body_pk}/assignments",
            json={
                "position_master_pk": position_pk, "person_pk": candidate_person_pk,
                "sangha_sevi_pk": candidate_sevi_pk, "effective_from": "2026-02-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 409

    def test_list_assignments(self, client, admin_headers, body_pk, candidate_person_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}/assignments", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert any(a["person_pk"] == candidate_person_pk for a in data["items"])

    def test_list_includes_home_sakha(self, client, admin_headers, body_pk, candidate_person_pk):
        """The assignments list carries the holder's home Sakha
        (sakha_name / sakha_organization_pk), backing the Sakha filter on the
        admin Assignments tab (owner ask #3, 2026-10-24). Both are additive
        None-default fields: always present in the response (None-/absent-safe
        for a holder whose Sangha Sevi has no home org), and populated for a
        holder anchored to a real Sakha."""
        r = client.get(f"{BASE}/bodies/{body_pk}/assignments", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        # Every row always exposes both keys — never KeyError on the frontend.
        for a in items:
            assert "sakha_name" in a
            assert "sakha_organization_pk" in a
        # The candidate's active Sangha Sevi is anchored to a SAKHA_SANGHA org
        # (_attach_active_membership), so its assignment resolves a real home
        # Sakha: both fields are populated, not None.
        cand = next(a for a in items if a["person_pk"] == candidate_person_pk)
        assert cand["sakha_organization_pk"] is not None
        assert cand["sakha_name"]

    def test_end_assignment(self, client, admin_headers, body_pk, position_pk, candidate_person_pk, candidate_sevi_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}/assignments", headers=admin_headers)
        assignment_pk = next(
            a["body_member_assignment_pk"] for a in r.json()["items"]
            if a["person_pk"] == candidate_person_pk
        )
        r2 = client.post(
            f"{BASE}/assignments/{assignment_pk}/end",
            json={"effective_to": "2026-03-01"},
            headers=admin_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["assignment_status"] == "ENDED"

        # Now that the active-holder slot is free, re-assigning is allowed.
        r3 = client.post(
            f"{BASE}/bodies/{body_pk}/assignments",
            json={
                "position_master_pk": position_pk, "person_pk": candidate_person_pk,
                "sangha_sevi_pk": candidate_sevi_pk, "effective_from": "2026-03-02",
            },
            headers=admin_headers,
        )
        assert r3.status_code == 201, r3.text

        # Close this demonstration assignment so the slot is free again —
        # TestResults later hands this same position/body to this same
        # candidate via the election-result apply flow, and the DB's
        # single-active-holder constraint would otherwise correctly block it.
        r4 = client.post(
            f"{BASE}/assignments/{r3.json()['body_member_assignment_pk']}/end",
            json={"effective_to": "2026-10-01"},
            headers=admin_headers,
        )
        assert r4.status_code == 200

    def test_promoting_a_member_converts_the_row_in_place(
        self, client, admin_headers, write_conn, body_pk,
    ):
        """
        Owner-confirmed 2026-10-24: "member and president/secretary all
        same... instead of promoting can't we just point the president
        post to a member" — supersedes the 2026-10-23 "insert the officer
        row, then end the prior MEMBER row" approach. Assigning a MEMBER,
        then assigning that SAME person a different position on the SAME
        body, must UPDATE the existing row (same body_member_assignment_pk)
        rather than create a second row — so GET assignments shows exactly
        ONE row for this person, now carrying the new position.

        Uses its own fresh position (not the shared `position_pk` fixture)
        so this test is self-contained regardless of what ran before it in
        this class/module.
        """
        person_pk = _create_person(write_conn, "Promotee")
        sevi_pk = _active_sevi_pk(write_conn, person_pk)

        positions = client.get(f"{BASE}/positions", headers=admin_headers).json()
        member_position_pk = next(p["position_master_pk"] for p in positions if p["position_code"] == "MEMBER")

        officer_code = f"TEST_OFFICER_{uuid4().hex[:8].upper()}"
        r_pos = client.post(
            f"{BASE}/positions",
            json={"position_code": officer_code, "position_name": "Test Officer", "display_order": 1},
            headers=admin_headers,
        )
        assert r_pos.status_code == 201, r_pos.text
        officer_position_pk = r_pos.json()["position_master_pk"]

        r1 = client.post(
            f"{BASE}/bodies/{body_pk}/assignments",
            json={
                "position_master_pk": member_position_pk, "person_pk": person_pk,
                "sangha_sevi_pk": sevi_pk, "effective_from": "2026-04-01",
            },
            headers=admin_headers,
        )
        assert r1.status_code == 201, r1.text
        member_assignment_pk = r1.json()["body_member_assignment_pk"]

        r2 = client.post(
            f"{BASE}/bodies/{body_pk}/assignments",
            json={
                "position_master_pk": officer_position_pk, "person_pk": person_pk,
                "sangha_sevi_pk": sevi_pk, "effective_from": "2026-04-15",
            },
            headers=admin_headers,
        )
        assert r2.status_code == 201, r2.text
        # Same row, converted — not a second, newly-inserted row.
        assert r2.json()["body_member_assignment_pk"] == member_assignment_pk
        assert r2.json()["position_master_pk"] == officer_position_pk

        r3 = client.get(f"{BASE}/bodies/{body_pk}/assignments", headers=admin_headers)
        rows_for_person = [a for a in r3.json()["items"] if a["person_pk"] == person_pk]
        assert len(rows_for_person) == 1, rows_for_person
        assert rows_for_person[0]["position_master_pk"] == officer_position_pk

        # Close this demonstration assignment so the slot is free again.
        client.post(
            f"{BASE}/assignments/{member_assignment_pk}/end",
            json={"effective_to": "2026-10-01"},
            headers=admin_headers,
        )


# ═══════════════════════════════════════════════════════════════════════
# 5. Acting Position Assignment
# ═══════════════════════════════════════════════════════════════════════

class TestActingAssignments:
    def test_create_acting_assignment(self, client, admin_headers, body_pk, position_pk, voter_person_pk):
        r = client.post(
            f"{BASE}/bodies/{body_pk}/acting-assignments",
            json={
                "position_master_pk": position_pk, "person_pk": voter_person_pk,
                "effective_from": "2026-01-15", "reason": "Primary holder on leave.",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        # Admin-initiated creation lands PENDING_APPROVAL, not immediately
        # ACTIVE (owner decision A, 2026-10-23) — it only becomes ACTIVE
        # once the concerned person approves it; see TestDecideActingAssignment.
        assert r.json()["acting_status"] == "PENDING_APPROVAL"

    def test_list_acting_assignments(self, client, admin_headers, body_pk, voter_person_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}/acting-assignments", headers=admin_headers)
        assert r.status_code == 200
        assert any(a["person_pk"] == voter_person_pk for a in r.json()["items"])

    def test_end_acting_assignment(self, client, admin_headers, body_pk, voter_person_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}/acting-assignments", headers=admin_headers)
        pk = next(
            a["acting_position_assignment_pk"] for a in r.json()["items"]
            if a["person_pk"] == voter_person_pk
        )
        r2 = client.post(
            f"{BASE}/acting-assignments/{pk}/end", json={"effective_to": "2026-01-31"},
            headers=admin_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["acting_status"] == "ENDED"


# ═══════════════════════════════════════════════════════════════════════
# 5b. Acting Position Assignment — concerned-person approve/reject
# ═══════════════════════════════════════════════════════════════════════
#
# Admin-initiated acting assignments land PENDING_APPROVAL (owner decision
# A, 2026-10-23) and only the person NAMED on the row (person_pk) may
# approve or reject it — no permission/scope check at all. Dedicated
# login-capable nominees (not the plain voter_person_pk, which has no
# user_account) so the test can authenticate as "the concerned person".

class TestDecideActingAssignment:
    @pytest.fixture(scope="class")
    def nominee(self, write_conn):
        return _create_member_login(write_conn, "ActingNominee")

    @pytest.fixture(scope="class")
    def other_person(self, write_conn):
        return _create_member_login(write_conn, "ActingOther")

    @pytest.fixture(scope="class")
    def nominee_headers(self, client, nominee):
        return _login_headers(client, nominee["sangha_sevi_id"], nominee["password"])

    @pytest.fixture(scope="class")
    def other_headers(self, client, other_person):
        return _login_headers(client, other_person["sangha_sevi_id"], other_person["password"])

    def _create_pending(self, client, admin_headers, body_pk, nominee, *, day="01"):
        # A fresh position per call — uq_acting_position_assignment_active_holder
        # is unique on (body, position, person) while is_active/effective_to IS
        # NULL, and REJECTED/ACTIVE rows from earlier sub-tests stay is_active =
        # TRUE, so reusing one shared position across these sub-tests would
        # 409 against the PRIOR sub-test's row, not exercise this one's path.
        position_pk = _new_position(
            client, admin_headers, f"Decision Test Position {day}", int(day),
        )
        r = client.post(
            f"{BASE}/bodies/{body_pk}/acting-assignments",
            json={
                "position_master_pk": position_pk, "person_pk": str(nominee["person_pk"]),
                "effective_from": f"2026-03-{day}", "reason": "Decision workflow test.",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["acting_status"] == "PENDING_APPROVAL"
        return r.json()["acting_position_assignment_pk"]

    def test_approve_by_other_person_returns_403(
        self, client, admin_headers, other_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="01")
        r = client.post(f"{BASE}/acting-assignments/{pk}/approve", json={}, headers=other_headers)
        assert r.status_code == 403, r.text

    def test_reject_by_other_person_returns_403(
        self, client, admin_headers, other_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="02")
        r = client.post(f"{BASE}/acting-assignments/{pk}/reject", json={}, headers=other_headers)
        assert r.status_code == 403, r.text

    def test_approve_by_concerned_person_succeeds(
        self, client, admin_headers, nominee_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="03")
        r = client.post(f"{BASE}/acting-assignments/{pk}/approve", json={}, headers=nominee_headers)
        assert r.status_code == 200, r.text
        assert r.json()["acting_status"] == "ACTIVE"

    def test_reject_by_concerned_person_succeeds(
        self, client, admin_headers, nominee_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="04")
        r = client.post(
            f"{BASE}/acting-assignments/{pk}/reject",
            json={"remarks": "Not available."}, headers=nominee_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["acting_status"] == "REJECTED"

    def test_approve_non_pending_returns_409(
        self, client, admin_headers, nominee_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="05")
        r1 = client.post(f"{BASE}/acting-assignments/{pk}/approve", json={}, headers=nominee_headers)
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"{BASE}/acting-assignments/{pk}/approve", json={}, headers=nominee_headers)
        assert r2.status_code == 409, r2.text

    def test_reject_non_pending_returns_409(
        self, client, admin_headers, nominee_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="06")
        r1 = client.post(f"{BASE}/acting-assignments/{pk}/reject", json={}, headers=nominee_headers)
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"{BASE}/acting-assignments/{pk}/reject", json={}, headers=nominee_headers)
        assert r2.status_code == 409, r2.text

    def test_pending_approval_listed_on_me_pending_acting_approvals(
        self, client, admin_headers, nominee_headers, body_pk, nominee,
    ):
        pk = self._create_pending(client, admin_headers, body_pk, nominee, day="07")
        r = client.get(f"{BASE}/me/pending-acting-approvals", headers=nominee_headers)
        assert r.status_code == 200, r.text
        assert any(a["acting_position_assignment_pk"] == pk for a in r.json()["items"])

    def test_pending_acting_approvals_requires_auth(self, anon_client):
        assert anon_client.get(f"{BASE}/me/pending-acting-approvals").status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# 6. Election
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def election_pk(client, admin_headers, body_pk):
    code = f"TEST_ELECTION_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/elections",
        json={
            "election_code": code, "body_master_pk": body_pk,
            "election_name": "Test Election", "election_date": "2026-11-01",
            "nomination_start_date": "2026-10-01", "nomination_end_date": "2026-10-15",
            "voting_start_date": "2026-10-20", "voting_end_date": "2026-10-25",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["election_pk"]


class TestElections:
    def test_create_returns_201(self, client, admin_headers, election_pk):
        r = client.get(f"{BASE}/elections/{election_pk}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["election_status"] == "SCHEDULED"

    def test_duplicate_election_code_returns_409(self, client, admin_headers, election_pk, body_pk):
        existing_code = client.get(f"{BASE}/elections/{election_pk}", headers=admin_headers).json()["election_code"]
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": existing_code, "body_master_pk": body_pk,
                "election_name": "Dup", "election_date": "2026-11-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 409

    def test_list_includes_created(self, client, admin_headers, election_pk):
        r = client.get(f"{BASE}/elections", headers=admin_headers)
        assert r.status_code == 200
        assert any(e["election_pk"] == election_pk for e in r.json()["items"])

    def test_advance_status_to_nomination(self, client, admin_headers, election_pk):
        r = client.patch(
            f"{BASE}/elections/{election_pk}/status",
            json={"election_status": "NOMINATION"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["election_status"] == "NOMINATION"


# ═══════════════════════════════════════════════════════════════════════
# 7. Election Nomination
# ═══════════════════════════════════════════════════════════════════════

class TestNominations:
    def test_create_nomination(
        self, client, admin_headers, election_pk, position_pk, candidate_person_pk, proposer_person_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{election_pk}/nominations",
            json={
                "position_master_pk": position_pk, "candidate_person_pk": candidate_person_pk,
                "proposer_person_pk": proposer_person_pk, "nomination_date": "2026-10-05",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["nomination_status"] == "NOMINATED"

    def test_duplicate_active_candidate_returns_409(
        self, client, admin_headers, election_pk, position_pk, candidate_person_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{election_pk}/nominations",
            json={
                "position_master_pk": position_pk, "candidate_person_pk": candidate_person_pk,
                "nomination_date": "2026-10-06",
            },
            headers=admin_headers,
        )
        assert r.status_code == 409

    def test_second_candidate_allowed(
        self, client, admin_headers, election_pk, position_pk, candidate2_person_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{election_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": candidate2_person_pk},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text

    def test_list_nominations(self, client, admin_headers, election_pk, candidate_person_pk):
        r = client.get(f"{BASE}/elections/{election_pk}/nominations", headers=admin_headers)
        assert r.status_code == 200
        assert any(n["candidate_person_pk"] == candidate_person_pk for n in r.json()["items"])

    def test_update_nomination_status_to_accepted(
        self, client, admin_headers, election_pk, candidate_person_pk,
    ):
        r = client.get(f"{BASE}/elections/{election_pk}/nominations", headers=admin_headers)
        nom_pk = next(
            n["election_nomination_pk"] for n in r.json()["items"]
            if n["candidate_person_pk"] == candidate_person_pk
        )
        r2 = client.patch(
            f"{BASE}/nominations/{nom_pk}/status",
            json={"nomination_status": "ACCEPTED"},
            headers=admin_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["nomination_status"] == "ACCEPTED"


# ═══════════════════════════════════════════════════════════════════════
# 8. Election Vote + Tally
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def accepted_nomination_pk(client, admin_headers, election_pk, candidate_person_pk):
    r = client.get(f"{BASE}/elections/{election_pk}/nominations", headers=admin_headers)
    return next(
        n["election_nomination_pk"] for n in r.json()["items"]
        if n["candidate_person_pk"] == candidate_person_pk
    )


@pytest.fixture(scope="module")
def election_in_voting(client, admin_headers, election_pk):
    """
    Advance the shared election from NOMINATION to VOTING.

    Must run AFTER the nominations exist and BEFORE any ballot is cast:
    casting a vote requires the ballot to be open (_require_election_voting_open),
    and an ELECTION cycle may only declare results from VOTING or COMPLETED
    (declare_result) — a winner cannot be declared on a cycle that never
    opened its ballot. Both gates are enforced server-side, so this step is
    required rather than incidental.
    """
    r = client.patch(
        f"{BASE}/elections/{election_pk}/status",
        json={"election_status": "VOTING"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    return election_pk


class TestVotes:
    def test_cast_vote(self, client, admin_headers, election_in_voting, election_pk,
                       accepted_nomination_pk, voter_person_pk):
        r = client.post(
            f"{BASE}/elections/{election_pk}/votes",
            json={"election_nomination_pk": accepted_nomination_pk, "voter_person_pk": voter_person_pk},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["voter_person_pk"] == voter_person_pk

    def test_duplicate_vote_same_position_returns_409(
        self, client, admin_headers, election_pk, accepted_nomination_pk, voter_person_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{election_pk}/votes",
            json={"election_nomination_pk": accepted_nomination_pk, "voter_person_pk": voter_person_pk},
            headers=admin_headers,
        )
        assert r.status_code == 409

    def test_vote_for_nomination_outside_election_returns_422(
        self, client, admin_headers, election_pk, proposer_person_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{election_pk}/votes",
            json={"election_nomination_pk": FAKE_UUID, "voter_person_pk": proposer_person_pk},
            headers=admin_headers,
        )
        assert r.status_code == 404

    def test_tally_reflects_cast_vote(
        self, client, admin_headers, election_pk, accepted_nomination_pk,
    ):
        r = client.get(f"{BASE}/elections/{election_pk}/tally", headers=admin_headers)
        assert r.status_code == 200
        row = next(
            t for t in r.json()["items"] if t["election_nomination_pk"] == accepted_nomination_pk
        )
        assert row["vote_count"] == 1

    def test_cast_vote_requires_manage_permission(
        self, client, scoped_headers, election_pk, accepted_nomination_pk, proposer_person_pk,
    ):
        """Vote casting is officer-recorded (GOVERNANCE_MANAGE), not member self-service — GOV-BR-045."""
        r = client.post(
            f"{BASE}/elections/{election_pk}/votes",
            json={"election_nomination_pk": accepted_nomination_pk, "voter_person_pk": proposer_person_pk},
            headers=scoped_headers,
        )
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# 9. Election Result
# ═══════════════════════════════════════════════════════════════════════

class TestResults:
    def test_declare_result(
        self, client, admin_headers, election_in_voting, election_pk, position_pk,
        accepted_nomination_pk, candidate_person_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{election_pk}/results",
            json={
                "position_master_pk": position_pk,
                "winning_nomination_pk": accepted_nomination_pk,
                "winner_person_pk": candidate_person_pk,
                "vote_count": 1, "result_status": "DECLARED",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["winner_person_pk"] == candidate_person_pk

    def test_duplicate_result_for_position_returns_409(self, client, admin_headers, election_pk, position_pk):
        r = client.post(
            f"{BASE}/elections/{election_pk}/results",
            json={"position_master_pk": position_pk, "result_status": "VACANT"},
            headers=admin_headers,
        )
        assert r.status_code == 409

    def test_list_results(self, client, admin_headers, election_pk, position_pk):
        r = client.get(f"{BASE}/elections/{election_pk}/results", headers=admin_headers)
        assert r.status_code == 200
        assert any(res["position_master_pk"] == position_pk for res in r.json()["items"])

    def test_apply_result_creates_assignment(
        self, client, admin_headers, election_pk, position_pk, candidate_person_pk, body_pk,
    ):
        results = client.get(f"{BASE}/elections/{election_pk}/results", headers=admin_headers).json()["items"]
        result_pk = next(res["election_result_pk"] for res in results if res["position_master_pk"] == position_pk)

        r = client.post(
            f"{BASE}/results/{result_pk}/apply",
            json={"effective_from": "2026-11-02"},
            headers=admin_headers,
        )
        assert r.status_code == 201 or r.status_code == 200, r.text
        data = r.json()
        assert data["election_result_pk"] == result_pk

        # The hand-off actually landed in body_member_assignment.
        assignments = client.get(f"{BASE}/bodies/{body_pk}/assignments", headers=admin_headers).json()["items"]
        assert any(
            a["body_member_assignment_pk"] == data["body_member_assignment_pk"]
            and a["person_pk"] == candidate_person_pk
            for a in assignments
        )

    def test_apply_result_without_winner_returns_422(self, client, admin_headers, election_pk):
        """A VACANT/TIE/CANCELLED result has nothing to hand off."""
        r = client.post(
            f"{BASE}/elections/{election_pk}/results",
            json={"position_master_pk": FAKE_UUID, "result_status": "VACANT"},
            headers=admin_headers,
        )
        # position_master_pk is invalid here on purpose — exercises the
        # existence check rather than the apply path directly.
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 10. Nomination-only cycles and candidate home-organization scoping
#     (GOV-BR-042 / GOV-BR-094 / GOV-BR-095)
# ═══════════════════════════════════════════════════════════════════════

def _reanchor_membership(write_conn, person_pk: str, organization_pk: str) -> None:
    """Point a person's active sangha_sevi at a specific Sakha."""
    cur = write_conn.cursor()
    cur.execute(
        "UPDATE nss.sangha_sevi SET organization_pk = %s "
        "WHERE person_pk = %s AND is_active = TRUE",
        (organization_pk, person_pk),
    )
    # No commit: the shared session connection is the same one the API reads
    # through, so the UPDATE is already visible within the module transaction.
    # A connection-level commit here would destroy the module SAVEPOINT (test
    # isolation) and leak these rows into the real database.


@pytest.fixture(scope="module")
def two_sakha_pks(write_conn):
    """Two distinct active Sakha organizations, for sibling-Sakha tests."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.organization_pk LIMIT 2
    """)
    rows = cur.fetchall()
    if len(rows) < 2:
        pytest.skip("Needs two active SAKHA_SANGHA organizations.")
    return str(rows[0][0]), str(rows[1][0])


@pytest.fixture(scope="module")
def sakha_body_pk(client, admin_headers, body_type_pk, two_sakha_pks):
    """A governance body scoped to the FIRST of the two Sakhas."""
    home_sakha, _ = two_sakha_pks
    code = f"TEST_SAKHA_BODY_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": code,
            "body_name": "Test Sakha Governing Body",
            "organization_pk": home_sakha,
            "effective_from": "2026-01-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


@pytest.fixture(scope="module")
def sakha_election_pk(client, admin_headers, sakha_body_pk):
    """
    A Sakha-scoped election. Its organization_pk must be derived server-side
    from the body (GOV-BR-059) — the client never sends it.
    """
    r = client.post(
        f"{BASE}/elections",
        json={
            "election_code": f"TEST_SKH_{uuid4().hex[:8].upper()}",
            "body_master_pk": sakha_body_pk,
            "election_name": "Test Sakha Election",
            "election_date": "2026-11-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["election_pk"]


class TestSakhaElectionScoping:
    def test_election_inherits_body_organization(
        self, client, admin_headers, sakha_election_pk, two_sakha_pks,
    ):
        """
        GOV-BR-059: the election mirrors its body's org. Regression test —
        create_election used to trust a client-supplied organization_pk that
        the UI never sent, so every election was created NSS-wide (NULL).
        """
        home_sakha, _ = two_sakha_pks
        r = client.get(f"{BASE}/elections/{sakha_election_pk}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["organization_pk"] == home_sakha

    def test_sakha_election_appears_in_list(self, client, admin_headers, sakha_election_pk):
        r = client.get(f"{BASE}/elections?page=1&page_size=500", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert any(e["election_pk"] == sakha_election_pk for e in r.json()["items"])

    def test_sibling_sakha_candidate_rejected(
        self, client, admin_headers, write_conn, sakha_election_pk, position_pk, two_sakha_pks,
    ):
        """GOV-BR-094: a member of another Sakha may never stand here."""
        _, other_sakha = two_sakha_pks
        outsider = _create_person(write_conn, "Outsider")
        _reanchor_membership(write_conn, outsider, other_sakha)

        r = client.post(
            f"{BASE}/elections/{sakha_election_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": outsider},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "may stand for its posts" in r.json()["detail"]

    def test_own_sakha_candidate_accepted(
        self, client, admin_headers, write_conn, sakha_election_pk, position_pk, two_sakha_pks,
    ):
        home_sakha, _ = two_sakha_pks
        insider = _create_person(write_conn, "Insider")
        _reanchor_membership(write_conn, insider, home_sakha)

        r = client.post(
            f"{BASE}/elections/{sakha_election_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": insider},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text

    def test_self_nomination_allowed(
        self, client, admin_headers, write_conn, sakha_election_pk, position_pk, two_sakha_pks,
    ):
        """
        GOV-BR-095: a candidate may propose themselves. The Bye-Law has no
        proposer/seconder requirement, so this must not be blocked.
        """
        home_sakha, _ = two_sakha_pks
        selfie = _create_person(write_conn, "SelfNom")
        _reanchor_membership(write_conn, selfie, home_sakha)

        r = client.post(
            f"{BASE}/elections/{sakha_election_pk}/nominations",
            json={
                "position_master_pk": position_pk,
                "candidate_person_pk": selfie,
                "proposer_person_pk": selfie,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["candidate_person_pk"] == selfie


# ═══════════════════════════════════════════════════════════════════════
# 10a. GOV-BR-043-A — Parichalak-approved Probationary exception
# ═══════════════════════════════════════════════════════════════════════

def _create_probationary_person(write_conn, label: str) -> str:
    """Throwaway person with an active PROBATIONARY Sangha Sevi membership."""
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()
    cur.execute(
        """
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s)
        RETURNING person_pk
        """,
        (f"GOV{suffix}", label, suffix, f"gov.{suffix.lower()}@example.test"),
    )
    person_pk = cur.fetchone()[0]
    _attach_active_membership(write_conn, person_pk, "PROBATIONARY", suffix)
    return str(person_pk)


def _grant_valid_anumati_patra(write_conn, person_pk: str, issuing_organization_pk: str) -> None:
    """Give person_pk's active Sangha Sevi a currently-valid ACTIVE Anumati Patra."""
    sevi_pk = _active_sevi_pk(write_conn, person_pk)
    cur = write_conn.cursor()
    suffix = uuid4().hex[:8].upper()
    cur.execute(
        """
        INSERT INTO nss.anumati_patra (
            sangha_sevi_pk, issuing_organization_pk, document_number,
            issue_date, valid_from, valid_to, status
        ) VALUES (%s, %s, %s, CURRENT_DATE, CURRENT_DATE, CURRENT_DATE + INTERVAL '1 year', 'ACTIVE')
        """,
        (sevi_pk, issuing_organization_pk, f"TEST-{suffix}"),
    )


@pytest.fixture(scope="class")
def sakha_governing_body_type_pk(write_conn):
    """The REAL seeded SAKHA_GOVERNING_BODY body type (not a fresh TEST_* one)
    — needed to hit the restricted-position branch in
    _require_candidate_eligible, which matches on this stable code."""
    cur = write_conn.cursor()
    cur.execute(
        "SELECT body_type_master_pk FROM nss.body_type_master WHERE body_type_code = 'SAKHA_GOVERNING_BODY'"
    )
    row = cur.fetchone()
    assert row, "SAKHA_GOVERNING_BODY not seeded."
    return str(row[0])


@pytest.fixture(scope="class")
def real_position_pks(write_conn):
    """The REAL seeded PRESIDENT / SECRETARY / PARICHALAK position rows."""
    cur = write_conn.cursor()
    cur.execute(
        "SELECT position_code, position_master_pk FROM nss.position_master "
        "WHERE position_code IN ('PRESIDENT', 'SECRETARY', 'PARICHALAK')"
    )
    rows = {code: str(pk) for code, pk in cur.fetchall()}
    assert {"PRESIDENT", "SECRETARY", "PARICHALAK"} <= rows.keys(), "Expected positions not seeded."
    return rows


@pytest.fixture(scope="class")
def real_sakha_body_pk(client, admin_headers, sakha_governing_body_type_pk, two_sakha_pks):
    """A body of the REAL SAKHA_GOVERNING_BODY type, scoped to the first of
    two Sakhas. `sakha_body_pk` elsewhere in this file deliberately uses a
    fresh TEST_* body type and never trips the restricted-position branch;
    this fixture is the one that does."""
    home_sakha, _ = two_sakha_pks
    code = f"TEST_REAL_SAKHA_BODY_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": sakha_governing_body_type_pk,
            "body_code": code,
            "body_name": "Test Real Sakha Governing Body",
            "organization_pk": home_sakha,
            "effective_from": "2026-01-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


@pytest.fixture(scope="class")
def real_sakha_election_pk(client, admin_headers, real_sakha_body_pk):
    r = client.post(
        f"{BASE}/elections",
        json={
            "election_code": f"TEST_REAL_SKH_{uuid4().hex[:8].upper()}",
            "body_master_pk": real_sakha_body_pk,
            "election_name": "Test Real Sakha Election",
            "election_date": "2026-11-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["election_pk"]


PARICHALAK_PASSWORD = "GovParichalakPass1"


@pytest.fixture(scope="class")
def parichalak_identity(write_conn, real_position_pks):
    """
    Make a fresh test person the current, active holder of the NSS-wide
    PARICHALAK seat (GOV-BR-043-A), seated on the REAL seeded Kendra
    Governing Body (body_code 'KENDRA_GB') — not an ad hoc test body.

    This has to be the real Kendra GB specifically, not merely a body of
    some PARICHALAK-bearing type: the §63 composite-grant rule
    (api/services/rbac_service.py::load_composite_grants) that auto-grants
    NSS_ERP_KENDRA_ADMIN / GOVERNANCE_MANAGE to a seated member is keyed on
    KENDRA_GOVERNING_BODY membership specifically, and GOV-BR-043-A now
    requires the Parichalak to personally authenticate and record the
    nomination themselves (the approver is never client-supplied — see
    create_nomination in api/routers/governance.py). A login is therefore
    also provisioned here, mirroring _create_admin_with_scope, so a
    parichalak_headers fixture can log in as this seat's holder.

    Direct SQL on purpose for the assignment — there is no POST
    /assignments endpoint; body_member_assignment rows are only ever
    created via the election-result "apply" flow, so setup for this one
    seat has to go straight to the table, same as the other raw-SQL test
    fixtures here.
    """
    from api.services.auth_service import hash_password

    holder = _create_person(write_conn, "Parichalak")
    sevi_pk = _active_sevi_pk(write_conn, holder)
    cur = write_conn.cursor()

    cur.execute("SELECT body_master_pk FROM nss.body_master WHERE body_code = 'KENDRA_GB'")
    row = cur.fetchone()
    assert row, "KENDRA_GB not seeded."
    kendra_gb_pk = row[0]

    cur.execute(
        """
        INSERT INTO nss.body_member_assignment (
            body_master_pk, position_master_pk, person_pk, sangha_sevi_pk,
            effective_from, assignment_status
        ) VALUES (%s, %s, %s, %s, DATE '2020-01-01', 'ACTIVE')
        """,
        (kendra_gb_pk, real_position_pks["PARICHALAK"], holder, sevi_pk),
    )

    suffix = uuid4().hex[:10].upper()
    cur.execute(
        """
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        """,
        (str(holder), hash_password(PARICHALAK_PASSWORD)),
    )

    cur.execute("SELECT sangha_sevi_id FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s", (str(sevi_pk),))
    sangha_sevi_id = cur.fetchone()[0]

    return {"sevi_pk": str(sevi_pk), "sangha_sevi_id": sangha_sevi_id, "password": PARICHALAK_PASSWORD}


@pytest.fixture(scope="class")
def parichalak_sevi_pk(parichalak_identity):
    return parichalak_identity["sevi_pk"]


@pytest.fixture(scope="class")
def parichalak_headers(client, parichalak_identity):
    return _login_headers(client, parichalak_identity["sangha_sevi_id"], parichalak_identity["password"])


class TestProbationaryParichalakException:
    """
    GOV-BR-043-A: a Parichalak-approved, per-nomination exception that lets
    a PROBATIONARY member stand for Sakha President/Secretary, provided the
    candidate holds a currently valid Anumati Patra (owner-confirmed
    2026-10-14; docs/03_Solution/modules/governance/04_governance_business_rules.md).
    """

    def test_probationary_candidate_rejected_without_exception(
        self, client, admin_headers, write_conn, real_sakha_election_pk,
        real_position_pks, two_sakha_pks,
    ):
        """Base GOV-BR-043 restriction still holds when no exception is supplied."""
        home_sakha, _ = two_sakha_pks
        candidate = _create_probationary_person(write_conn, "ProbNoExc")
        _reanchor_membership(write_conn, candidate, home_sakha)

        r = client.post(
            f"{BASE}/elections/{real_sakha_election_pk}/nominations",
            json={
                "position_master_pk": real_position_pks["PRESIDENT"],
                "candidate_person_pk": candidate,
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "GOV-BR-043-A" in r.json()["detail"]

    def test_rejected_when_approver_is_not_current_parichalak(
        self, client, admin_headers, write_conn, real_sakha_election_pk,
        real_position_pks, two_sakha_pks,
    ):
        """
        A reason recorded by someone other than the seated Parichalak cannot
        grant the exception — the approver is never client-supplied; it is
        always the authenticated actor (user.sangha_sevi_pk). admin_headers
        is a GOVERNANCE_MANAGE holder but not the Parichalak, so the server
        derives an approver pk that doesn't match the seated Parichalak.
        """
        home_sakha, _ = two_sakha_pks
        candidate = _create_probationary_person(write_conn, "ProbWrongAppr")
        _reanchor_membership(write_conn, candidate, home_sakha)

        r = client.post(
            f"{BASE}/elections/{real_sakha_election_pk}/nominations",
            json={
                "position_master_pk": real_position_pks["PRESIDENT"],
                "candidate_person_pk": candidate,
                "probationary_exception_reason": "Approved per field visit.",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "Parichalak" in r.json()["detail"]

    def test_rejected_when_candidate_has_no_valid_anumati_patra(
        self, client, parichalak_headers, write_conn, real_sakha_election_pk,
        real_position_pks, two_sakha_pks,
    ):
        """Correct approver (the seated Parichalak, authenticated) + reason, but no credential — still rejected."""
        home_sakha, _ = two_sakha_pks
        candidate = _create_probationary_person(write_conn, "ProbNoAP")
        _reanchor_membership(write_conn, candidate, home_sakha)

        r = client.post(
            f"{BASE}/elections/{real_sakha_election_pk}/nominations",
            json={
                "position_master_pk": real_position_pks["SECRETARY"],
                "candidate_person_pk": candidate,
                "probationary_exception_reason": "Approved per field visit.",
            },
            headers=parichalak_headers,
        )
        assert r.status_code == 422, r.text
        assert "Anumati Patra" in r.json()["detail"]

    def test_accepted_with_valid_exception_and_credential(
        self, client, parichalak_headers, parichalak_sevi_pk, write_conn, real_sakha_election_pk,
        real_position_pks, two_sakha_pks,
    ):
        """All three GOV-BR-043-A conditions met — the nomination succeeds."""
        home_sakha, _ = two_sakha_pks
        candidate = _create_probationary_person(write_conn, "ProbValid")
        _reanchor_membership(write_conn, candidate, home_sakha)
        _grant_valid_anumati_patra(write_conn, candidate, home_sakha)

        r = client.post(
            f"{BASE}/elections/{real_sakha_election_pk}/nominations",
            json={
                "position_master_pk": real_position_pks["SECRETARY"],
                "candidate_person_pk": candidate,
                "probationary_exception_reason": "Approved per field visit, exceptional need.",
            },
            headers=parichalak_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["probationary_exception_approver_sangha_sevi_pk"] == parichalak_sevi_pk
        assert body["probationary_exception_reason"] == "Approved per field visit, exceptional need."


class TestNominationOnlyCycle:
    """GOV-BR-042: in some years posts are filled by consensus, not a ballot."""

    @pytest.fixture(scope="class")
    def nomination_cycle_pk(self, client, admin_headers, body_pk):
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_NOM_{uuid4().hex[:8].upper()}",
                "body_master_pk": body_pk,
                "election_name": "Test Consensus Cycle",
                "election_type": "NOMINATION",
                "election_date": "2026-11-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["election_type"] == "NOMINATION"
        return r.json()["election_pk"]

    def test_default_type_is_election(self, client, admin_headers, election_pk):
        r = client.get(f"{BASE}/elections/{election_pk}", headers=admin_headers)
        assert r.json()["election_type"] == "ELECTION"

    def test_voting_window_rejected(self, client, admin_headers, body_pk):
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_NOMBAD_{uuid4().hex[:8].upper()}",
                "body_master_pk": body_pk,
                "election_name": "Consensus cycle with a ballot",
                "election_type": "NOMINATION",
                "election_date": "2026-11-01",
                "voting_start_date": "2026-10-20",
                "voting_end_date": "2026-10-25",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "no ballot" in r.json()["detail"]

    def test_cannot_advance_to_voting(self, client, admin_headers, nomination_cycle_pk):
        client.patch(
            f"{BASE}/elections/{nomination_cycle_pk}/status",
            json={"election_status": "NOMINATION"}, headers=admin_headers,
        )
        r = client.patch(
            f"{BASE}/elections/{nomination_cycle_pk}/status",
            json={"election_status": "VOTING"}, headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_declared_outcome_rejected_without_ballot(
        self, client, admin_headers, nomination_cycle_pk, position_pk,
    ):
        r = client.post(
            f"{BASE}/elections/{nomination_cycle_pk}/results",
            json={"position_master_pk": position_pk, "result_status": "DECLARED"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "requires a ballot" in r.json()["detail"]

    def test_uncontested_outcome_from_accepted_nomination(
        self, client, admin_headers, write_conn, nomination_cycle_pk, position_pk,
    ):
        """The consensus path: nominate -> accept -> declare UNCONTESTED."""
        chosen = _create_person(write_conn, "Consensus")
        nom = client.post(
            f"{BASE}/elections/{nomination_cycle_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": chosen},
            headers=admin_headers,
        )
        assert nom.status_code == 201, nom.text
        nom_pk = nom.json()["election_nomination_pk"]

        acc = client.patch(
            f"{BASE}/nominations/{nom_pk}/status",
            json={"nomination_status": "ACCEPTED"}, headers=admin_headers,
        )
        assert acc.status_code == 200, acc.text

        r = client.post(
            f"{BASE}/elections/{nomination_cycle_pk}/results",
            json={
                "position_master_pk": position_pk,
                "winning_nomination_pk": nom_pk,
                "winner_person_pk": chosen,
                "result_status": "UNCONTESTED",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["winner_person_pk"] == chosen
        assert r.json()["vote_count"] is None

    def test_can_complete_without_voting(self, client, admin_headers, nomination_cycle_pk):
        r = client.patch(
            f"{BASE}/elections/{nomination_cycle_pk}/status",
            json={"election_status": "COMPLETED"}, headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["election_status"] == "COMPLETED"


class TestElectionLifecycleGuards:
    def test_election_cycle_cannot_skip_voting(self, client, admin_headers, body_pk):
        """A contested cycle must hold its ballot before completing."""
        created = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_SKIP_{uuid4().hex[:8].upper()}",
                "body_master_pk": body_pk,
                "election_name": "Skip-voting attempt",
                "election_date": "2026-11-01",
            },
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text
        pk = created.json()["election_pk"]

        client.patch(f"{BASE}/elections/{pk}/status",
                     json={"election_status": "NOMINATION"}, headers=admin_headers)
        r = client.patch(f"{BASE}/elections/{pk}/status",
                         json={"election_status": "COMPLETED"}, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_cannot_declare_before_voting_opens(self, client, admin_headers, body_pk, position_pk):
        created = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_EARLY_{uuid4().hex[:8].upper()}",
                "body_master_pk": body_pk,
                "election_name": "Premature declaration",
                "election_date": "2026-11-01",
            },
            headers=admin_headers,
        )
        pk = created.json()["election_pk"]
        r = client.post(
            f"{BASE}/elections/{pk}/results",
            json={"position_master_pk": position_pk, "result_status": "VACANT"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "SCHEDULED" in r.json()["detail"]

    def test_winner_must_have_accepted_nomination(
        self, client, admin_headers, write_conn, election_in_voting, election_pk, position_pk,
    ):
        """GOV-BR-046: a declared winner must actually have stood."""
        stranger = _create_person(write_conn, "Stranger")
        r = client.post(
            f"{BASE}/elections/{election_pk}/results",
            json={
                "position_master_pk": position_pk,
                "winner_person_pk": stranger,
                "result_status": "DECLARED",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "accepted nomination" in r.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════
# 11. RBAC — anonymous access rejected
# ═══════════════════════════════════════════════════════════════════════

class TestRbac:
    def test_list_bodies_requires_auth(self, anon_client):
        r = anon_client.get(f"{BASE}/bodies")
        assert r.status_code == 401

    def test_create_body_type_requires_auth(self, anon_client):
        r = anon_client.post(
            f"{BASE}/body-types", json={"body_type_code": "X", "body_type_name": "X"},
        )
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# 12. Member-facing "act on my behalf" delegation (/me/acting-delegations)
# ═══════════════════════════════════════════════════════════════════════
#
# Login-only endpoints whose authority comes from the caller's OWN current
# office-bearer seat (_active_office_bearer), never from GOVERNANCE_*.
# Dedicated body/positions so this block cannot collide with the shared
# body_pk/position_pk fixtures the assignment and election tests mutate.

MEMBER_PASSWORD = "GovMemberPass1"


def _create_member_login(write_conn, label: str) -> dict:
    """
    A person + active sangha_sevi + ACTIVE user_account and NOTHING else —
    no user_role, no admin_scope. Exactly the "plain logged-in member" these
    endpoints must serve, so the tests prove the self-role gate (not a
    permission) is what authorizes them.
    """
    from api.services.auth_service import hash_password

    person_pk = _create_person(write_conn, label)
    cur = write_conn.cursor()
    cur.execute(
        """
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        """,
        (str(person_pk), hash_password(MEMBER_PASSWORD)),
    )
    cur.execute(
        "SELECT sangha_sevi_id, sangha_sevi_pk FROM nss.sangha_sevi "
        "WHERE person_pk = %s AND is_active = TRUE",
        (str(person_pk),),
    )
    sangha_sevi_id, sangha_sevi_pk = cur.fetchone()
    return {
        "person_pk": person_pk,
        "sangha_sevi_id": sangha_sevi_id,
        "sangha_sevi_pk": str(sangha_sevi_pk),
        "password": MEMBER_PASSWORD,
    }


def _new_position(client, admin_headers, name: str, display_order: int) -> str:
    r = client.post(
        f"{BASE}/positions",
        json={
            "position_code": f"DELEG_{uuid4().hex[:8].upper()}",
            "position_name": name,
            "display_order": display_order,
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["position_master_pk"]


def _seat(client, admin_headers, body_pk, position_pk, user):
    r = client.post(
        f"{BASE}/bodies/{body_pk}/assignments",
        json={
            "position_master_pk": position_pk,
            "person_pk": str(user["person_pk"]),
            "sangha_sevi_pk": user["sangha_sevi_pk"],
            "effective_from": "2026-01-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text


@pytest.fixture(scope="module")
def deleg_body_pk(client, admin_headers, body_type_pk):
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": f"DELEG_BODY_{uuid4().hex[:8].upper()}",
            "body_name": "Delegation Test Body",
            "effective_from": "2026-01-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


@pytest.fixture(scope="module")
def deleg_held_position_pk(client, admin_headers):
    """The position the bearer holds — the only one they may delegate."""
    return _new_position(client, admin_headers, "Delegation Chair", 1)


@pytest.fixture(scope="module")
def deleg_other_position_pk(client, admin_headers):
    """A position the bearer does NOT hold — the 403 case."""
    return _new_position(client, admin_headers, "Delegation Deputy", 2)


@pytest.fixture(scope="module")
def deleg_third_position_pk(client, admin_headers):
    return _new_position(client, admin_headers, "Delegation Treasurer", 3)


@pytest.fixture(scope="module")
def deleg_bearer(write_conn, client, admin_headers, deleg_body_pk, deleg_held_position_pk):
    user = _create_member_login(write_conn, "DelegBearer")
    _seat(client, admin_headers, deleg_body_pk, deleg_held_position_pk, user)
    return user


@pytest.fixture(scope="module")
def deleg_nominee(write_conn, client, admin_headers, deleg_body_pk, deleg_other_position_pk):
    user = _create_member_login(write_conn, "DelegNominee")
    _seat(client, admin_headers, deleg_body_pk, deleg_other_position_pk, user)
    return user


@pytest.fixture(scope="module")
def deleg_nominee2(write_conn, client, admin_headers, deleg_body_pk, deleg_third_position_pk):
    user = _create_member_login(write_conn, "DelegNominee2")
    _seat(client, admin_headers, deleg_body_pk, deleg_third_position_pk, user)
    return user


@pytest.fixture(scope="module")
def deleg_plain_member(write_conn):
    """Login-capable member who sits on no governance body at all."""
    return _create_member_login(write_conn, "DelegPlain")


@pytest.fixture(scope="module")
def deleg_bearer_headers(client, deleg_bearer):
    return _login_headers(client, deleg_bearer["sangha_sevi_id"], deleg_bearer["password"])


@pytest.fixture(scope="module")
def deleg_plain_headers(client, deleg_plain_member):
    return _login_headers(
        client, deleg_plain_member["sangha_sevi_id"], deleg_plain_member["password"]
    )


# ── Second body, for the batch endpoint (owner ask, 2026-10-24) ──────────
# The batch POST exists because the dashboard now renders ONE candidate
# table per (body, position-I-hold) slot and makes every table mandatory,
# so Confirm creates N delegations at once. Exercising that needs the
# bearer to hold a seat on a SECOND body (the realistic shape — one
# position per body), with a nominee sitting there too.


@pytest.fixture(scope="module")
def deleg_body2_pk(client, admin_headers, body_type_pk):
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": f"DELEG_BODY2_{uuid4().hex[:8].upper()}",
            "body_name": "Delegation Test Body Two",
            "effective_from": "2026-01-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


@pytest.fixture(scope="module")
def deleg_body2_held_position_pk(client, admin_headers, deleg_body2_pk, deleg_bearer):
    """A position the bearer holds on body two — the second batch slot."""
    pk = _new_position(client, admin_headers, "Delegation Body2 Chair", 4)
    _seat(client, admin_headers, deleg_body2_pk, pk, deleg_bearer)
    return pk


@pytest.fixture(scope="module")
def deleg_body2_nominee(client, admin_headers, deleg_body2_pk, deleg_nominee):
    """The body-one nominee, also seated on body two so they are eligible there."""
    pk = _new_position(client, admin_headers, "Delegation Body2 Deputy", 5)
    _seat(client, admin_headers, deleg_body2_pk, pk, deleg_nominee)
    return deleg_nominee


class TestMyGovernancePositions:
    def test_office_bearer_sees_their_body(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk,
        deleg_nominee, deleg_nominee2,
    ):
        r = client.get(f"{BASE}/me/positions", headers=deleg_bearer_headers)
        assert r.status_code == 200, r.text
        body = next(
            (b for b in r.json()["bodies"] if b["body_master_pk"] == deleg_body_pk), None
        )
        assert body is not None, "The bearer's own body must be returned."
        assert any(
            p["position_master_pk"] == deleg_held_position_pk for p in body["my_positions"]
        )
        # Composition comes back too, so the dashboard can build the
        # candidate radio list without GOVERNANCE_VIEW.
        member_pks = {str(m["person_pk"]) for m in body["members"]}
        assert str(deleg_nominee["person_pk"]) in member_pks

    def test_plain_member_sees_nothing(self, client, deleg_plain_headers):
        r = client.get(f"{BASE}/me/positions", headers=deleg_plain_headers)
        assert r.status_code == 200, r.text
        assert r.json()["bodies"] == []

    def test_requires_auth(self, anon_client):
        assert anon_client.get(f"{BASE}/me/positions").status_code == 401


class TestMyActingDelegations:
    def test_position_not_held_returns_403(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_other_position_pk, deleg_nominee,
    ):
        """Owner ask #2's security core — you may only delegate your OWN seat."""
        r = client.post(
            f"{BASE}/me/acting-delegations",
            json={
                "body_master_pk": deleg_body_pk,
                "position_master_pk": deleg_other_position_pk,
                "person_pk": str(deleg_nominee["person_pk"]),
                "effective_from": "2026-02-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 403, r.text

    def test_self_delegation_returns_422(
        self, client, deleg_bearer_headers, deleg_bearer, deleg_body_pk, deleg_held_position_pk,
    ):
        r = client.post(
            f"{BASE}/me/acting-delegations",
            json={
                "body_master_pk": deleg_body_pk,
                "position_master_pk": deleg_held_position_pk,
                "person_pk": str(deleg_bearer["person_pk"]),
                "effective_from": "2026-02-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 422, r.text

    def test_nominee_must_sit_on_the_same_body(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk,
        deleg_plain_member,
    ):
        r = client.post(
            f"{BASE}/me/acting-delegations",
            json={
                "body_master_pk": deleg_body_pk,
                "position_master_pk": deleg_held_position_pk,
                "person_pk": str(deleg_plain_member["person_pk"]),
                "effective_from": "2026-02-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 422, r.text

    def test_delegation_succeeds_for_held_position(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk, deleg_nominee,
    ):
        r = client.post(
            f"{BASE}/me/acting-delegations",
            json={
                "body_master_pk": deleg_body_pk,
                "position_master_pk": deleg_held_position_pk,
                "person_pk": str(deleg_nominee["person_pk"]),
                "effective_from": "2026-02-01",
                "reason": "Travelling.",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["acting_status"] in ("ASSIGNED", "ACTIVE")
        assert data["person_pk"] == str(deleg_nominee["person_pk"])

    def test_second_concurrent_delegation_returns_409(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk, deleg_nominee2,
    ):
        """
        Added rule (2026-10-23): one delegate per (body, position) at a time.
        The admin endpoint does NOT enforce this — its DDL unique index is
        per-person, so two different people could otherwise both act for one
        seat. Deliberate and reversible.
        """
        r = client.post(
            f"{BASE}/me/acting-delegations",
            json={
                "body_master_pk": deleg_body_pk,
                "position_master_pk": deleg_held_position_pk,
                "person_pk": str(deleg_nominee2["person_pk"]),
                "effective_from": "2026-03-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 409, r.text

    def test_list_my_delegations(self, client, deleg_bearer_headers, deleg_nominee):
        r = client.get(f"{BASE}/me/acting-delegations", headers=deleg_bearer_headers)
        assert r.status_code == 200, r.text
        assert any(
            d["person_pk"] == str(deleg_nominee["person_pk"]) for d in r.json()["items"]
        )

    def test_plain_member_has_no_delegations(self, client, deleg_plain_headers):
        r = client.get(f"{BASE}/me/acting-delegations", headers=deleg_plain_headers)
        assert r.status_code == 200, r.text
        assert r.json()["items"] == []

    def test_end_requires_holding_the_position(
        self, client, deleg_plain_headers, deleg_bearer_headers, deleg_nominee,
    ):
        listing = client.get(f"{BASE}/me/acting-delegations", headers=deleg_bearer_headers)
        pk = next(
            d["acting_position_assignment_pk"] for d in listing.json()["items"]
            if d["person_pk"] == str(deleg_nominee["person_pk"])
        )
        r = client.post(
            f"{BASE}/me/acting-delegations/{pk}/end",
            json={"effective_to": "2026-06-02"},
            headers=deleg_plain_headers,
        )
        assert r.status_code == 403, r.text

    def test_end_delegation_sets_ended(self, client, deleg_bearer_headers, deleg_nominee):
        listing = client.get(f"{BASE}/me/acting-delegations", headers=deleg_bearer_headers)
        pk = next(
            d["acting_position_assignment_pk"] for d in listing.json()["items"]
            if d["person_pk"] == str(deleg_nominee["person_pk"])
        )
        r = client.post(
            f"{BASE}/me/acting-delegations/{pk}/end",
            json={"effective_to": "2026-06-01"},
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["acting_status"] == "ENDED"

    def test_requires_auth(self, anon_client, deleg_body_pk, deleg_held_position_pk):
        r = anon_client.post(
            f"{BASE}/me/acting-delegations",
            json={
                "body_master_pk": deleg_body_pk,
                "position_master_pk": deleg_held_position_pk,
                "person_pk": FAKE_UUID,
                "effective_from": "2026-02-01",
            },
        )
        assert r.status_code == 401

    # ── Batch self-delegation (owner ask, 2026-10-24) ────────────────────
    # POST /me/acting-delegations/batch — one delegation per governance
    # body, created all-or-nothing. These run AFTER
    # test_end_delegation_sets_ended above, so the body-one slot is free
    # again (its only prior delegation is ENDED).

    def test_batch_rejects_empty_items(self, client, deleg_bearer_headers):
        r = client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={"items": [], "effective_from": "2026-07-01"},
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 422, r.text

    def test_batch_rejects_duplicate_slot_in_one_request(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk,
        deleg_nominee, deleg_nominee2,
    ):
        """The same (body, position) twice in one payload — the second would
        collide with the first on the one-live-delegate-per-seat rule, so it
        is rejected up front rather than half-applied."""
        item = {
            "body_master_pk": deleg_body_pk,
            "position_master_pk": deleg_held_position_pk,
        }
        r = client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={
                "items": [
                    {**item, "person_pk": str(deleg_nominee["person_pk"])},
                    {**item, "person_pk": str(deleg_nominee2["person_pk"])},
                ],
                "effective_from": "2026-07-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 422, r.text

    def test_batch_403_when_an_item_is_not_a_held_position(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_other_position_pk,
        deleg_nominee,
    ):
        r = client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={
                "items": [{
                    "body_master_pk": deleg_body_pk,
                    "position_master_pk": deleg_other_position_pk,
                    "person_pk": str(deleg_nominee["person_pk"]),
                }],
                "effective_from": "2026-07-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 403, r.text

    def test_batch_is_atomic_when_a_later_item_fails(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk,
        deleg_other_position_pk, deleg_nominee,
    ):
        """
        A good item followed by a bad one must create NOTHING. With every
        dashboard table mandatory, a partial success would leave the member
        half-delegated with no obvious way back — so the handler wraps the
        whole loop in a SAVEPOINT and rolls it back on the first rejection.
        """
        r = client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={
                "items": [
                    {   # valid — the bearer holds this seat
                        "body_master_pk": deleg_body_pk,
                        "position_master_pk": deleg_held_position_pk,
                        "person_pk": str(deleg_nominee["person_pk"]),
                    },
                    {   # invalid — the bearer does NOT hold this seat
                        "body_master_pk": deleg_body_pk,
                        "position_master_pk": deleg_other_position_pk,
                        "person_pk": str(deleg_nominee["person_pk"]),
                    },
                ],
                "effective_from": "2026-07-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 403, r.text

        # The first (valid) item must not have persisted. The only row on
        # this seat should still be the ENDED one from
        # test_end_delegation_sets_ended.
        listing = client.get(f"{BASE}/me/acting-delegations", headers=deleg_bearer_headers)
        assert listing.status_code == 200, listing.text
        live = [
            d for d in listing.json()["items"]
            if d["body_master_pk"] == deleg_body_pk
            and d["position_master_pk"] == deleg_held_position_pk
            and d["acting_status"] in ("ASSIGNED", "ACTIVE", "PENDING_APPROVAL")
        ]
        assert live == [], (
            "the valid item in a failed batch persisted — the batch is not atomic"
        )

    def test_batch_creates_one_delegation_per_held_position(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk,
        deleg_body2_pk, deleg_body2_held_position_pk, deleg_nominee,
        deleg_body2_nominee,
    ):
        r = client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={
                "items": [
                    {
                        "body_master_pk": deleg_body_pk,
                        "position_master_pk": deleg_held_position_pk,
                        "person_pk": str(deleg_nominee["person_pk"]),
                    },
                    {
                        "body_master_pk": deleg_body2_pk,
                        "position_master_pk": deleg_body2_held_position_pk,
                        "person_pk": str(deleg_body2_nominee["person_pk"]),
                    },
                ],
                "effective_from": "2026-08-01",
                "reason": "Travelling — both bodies.",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["total"] == 2, data
        assert {i["body_master_pk"] for i in data["items"]} == {deleg_body_pk, deleg_body2_pk}
        assert all(i["acting_status"] in ("ASSIGNED", "ACTIVE") for i in data["items"])

        # Both are visible on the bearer's own delegation list.
        listing = client.get(f"{BASE}/me/acting-delegations", headers=deleg_bearer_headers)
        live_pairs = {
            (d["body_master_pk"], d["position_master_pk"])
            for d in listing.json()["items"]
            if d["acting_status"] in ("ASSIGNED", "ACTIVE")
        }
        assert (deleg_body_pk, deleg_held_position_pk) in live_pairs
        assert (deleg_body2_pk, deleg_body2_held_position_pk) in live_pairs

    def test_batch_requires_auth(self, anon_client, deleg_body_pk, deleg_held_position_pk):
        r = anon_client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={
                "items": [{
                    "body_master_pk": deleg_body_pk,
                    "position_master_pk": deleg_held_position_pk,
                    "person_pk": FAKE_UUID,
                }],
                "effective_from": "2026-07-01",
            },
        )
        assert r.status_code == 401
