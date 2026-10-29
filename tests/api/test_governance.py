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
from datetime import date
from uuid import uuid4

pytestmark = pytest.mark.integration

BASE = "/api/v1/governance"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "GovAdminPass1"
SCOPED_PASSWORD = "GovScopedPass1"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

def _create_bare_person(write_conn, label: str):
    """Throwaway nss.person row with NO membership. Returns (person_pk, suffix)."""
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
    return str(cur.fetchone()[0]), suffix


def _create_person_of_type(write_conn, label: str, membership_type_code: str) -> str:
    """Throwaway person with an active Sangha Sevi of the given MEMBERSHIP_TYPE."""
    person_pk, suffix = _create_bare_person(write_conn, label)
    _attach_active_membership(write_conn, person_pk, membership_type_code, suffix)
    return person_pk


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
    return _create_person_of_type(write_conn, label, "REGULAR")


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


def _force_end_assignment(write_conn, assignment_pk: str, effective_to: str) -> None:
    """
    Close an assignment straight in the table (status ENDED + effective_to).

    POST /assignments/{pk}/end is no longer a general admin action — outside
    the Sakha-nominated Advisory Board MEMBER seat it answers 409 and points
    at /request-removal (GOV-BR item #18, generalized 2026-10-15) — so tests
    that merely need a seat vacated again (to free the single-holder slot for
    a later step) vacate it with SQL, on the same connection the API reads.
    """
    cur = write_conn.cursor()
    cur.execute(
        "UPDATE nss.body_member_assignment "
        "SET assignment_status = 'ENDED', effective_to = %s "
        "WHERE body_member_assignment_pk = %s",
        (effective_to, str(assignment_pk)),
    )


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
        # Page 1 (20 rows, ORDER BY body_code) of a populated dev DB need not
        # contain a TEST_BODY_* row, so narrow by its (unique) code.
        code = client.get(f"{BASE}/bodies/{body_pk}", headers=admin_headers).json()["body_code"]
        r = client.get(f"{BASE}/bodies", params={"search": code}, headers=admin_headers)
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

    def test_end_assignment(self, client, admin_headers, write_conn, body_pk, position_pk, candidate_person_pk, candidate_sevi_pk):
        """
        POST /assignments/{pk}/end is no longer an admin shortcut: for any
        seat other than a Sakha-nominated Advisory Board MEMBER, even an
        in-scope super-admin gets a 409 pointing at /request-removal (a forced
        removal needs the body's own GB resolution + President approval).
        """
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
        assert r2.status_code == 409, r2.text
        assert "request-removal" in r2.json()["detail"]

        # The refused call must not have touched the seat.
        r_after = client.get(f"{BASE}/bodies/{body_pk}/assignments", headers=admin_headers)
        row = next(a for a in r_after.json()["items"] if a["body_member_assignment_pk"] == assignment_pk)
        assert row["assignment_status"] in ("ASSIGNED", "ACTIVE")
        assert row["effective_to"] is None

        # Vacate the seat directly; the active-holder slot is then free again.
        _force_end_assignment(write_conn, assignment_pk, "2026-03-01")
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
        _force_end_assignment(write_conn, r3.json()["body_member_assignment_pk"], "2026-10-01")

    def test_end_unknown_assignment_returns_404(self, client, admin_headers):
        r = client.post(
            f"{BASE}/assignments/{FAKE_UUID}/end",
            json={"effective_to": "2026-03-01"}, headers=admin_headers,
        )
        assert r.status_code == 404, r.text

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
        _force_end_assignment(write_conn, member_assignment_pk, "2026-10-01")


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
    @classmethod
    def nominee(cls, write_conn):
        return _create_member_login(write_conn, "ActingNominee")

    @pytest.fixture(scope="class")
    @classmethod
    def other_person(cls, write_conn):
        return _create_member_login(write_conn, "ActingOther")

    @pytest.fixture(scope="class")
    @classmethod
    def nominee_headers(cls, client, nominee):
        return _login_headers(client, nominee["sangha_sevi_id"], nominee["password"])

    @pytest.fixture(scope="class")
    @classmethod
    def other_headers(cls, client, other_person):
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
    return _advance_election(client, admin_headers, r.json()["election_pk"], "NOMINATION")


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
    return _create_person_of_type(write_conn, label, "PROBATIONARY")


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
    return _advance_election(client, admin_headers, r.json()["election_pk"], "NOMINATION")


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

    # A populated dev DB already has a real Parichalak and a Kendra GB that
    # sits at its DB seat cap (fn_enforce_body_seat_limit, max_members=9), so
    # a 10th row would raise RestrictViolation. Vacate any sitting Parichalak
    # first (it also keeps this fixture's holder the ONLY current Parichalak:
    # _resolve_current_parichalak_sangha_sevi_pk is LIMIT 1), then — only if
    # the body is still full — one more seat. Rolled back with the module
    # SAVEPOINT.
    cur.execute(
        """
        UPDATE nss.body_member_assignment a
        SET assignment_status = 'ENDED', effective_to = a.effective_from
        FROM nss.position_master pm
        WHERE pm.position_master_pk = a.position_master_pk
          AND pm.position_code = 'PARICHALAK' AND a.is_active = TRUE
          AND a.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
        """
    )
    cur.execute(
        """
        SELECT COUNT(*), MAX(bt.max_members)
        FROM nss.body_member_assignment a
        JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE a.body_master_pk = %s AND a.is_active = TRUE
          AND a.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
        """,
        (kendra_gb_pk,),
    )
    seated, cap = cur.fetchone()
    if cap is not None and seated >= cap:
        cur.execute(
            """
            UPDATE nss.body_member_assignment
            SET assignment_status = 'ENDED', effective_to = effective_from
            WHERE body_member_assignment_pk = (
                SELECT body_member_assignment_pk FROM nss.body_member_assignment
                WHERE body_master_pk = %s AND is_active = TRUE
                  AND assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
                ORDER BY created_at DESC LIMIT 1
            )
            """,
            (kendra_gb_pk,),
        )

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


    def test_parichalak_status_true_for_the_seat_holder(
        self, client, parichalak_headers, parichalak_sevi_pk,
    ):
        """GET /me/parichalak-status is a login-only self-check (GOV-BR-043-A)."""
        r = client.get(f"{BASE}/me/parichalak-status", headers=parichalak_headers)
        assert r.status_code == 200, r.text
        assert r.json()["is_parichalak"] is True
        assert r.json()["sangha_sevi_pk"] == parichalak_sevi_pk

    def test_parichalak_status_false_for_everyone_else(
        self, client, admin_headers, parichalak_identity,
    ):
        """A governance super-admin is not the Parichalak merely by being an admin."""
        r = client.get(f"{BASE}/me/parichalak-status", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json() == {"is_parichalak": False, "sangha_sevi_pk": None}


class TestNominationOnlyCycle:
    """GOV-BR-042: in some years posts are filled by consensus, not a ballot."""

    @pytest.fixture(scope="class")
    @classmethod
    def nomination_cycle_pk(cls, client, admin_headers, body_pk):
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
        return _advance_election(client, admin_headers, r.json()["election_pk"], "NOMINATION")

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


def _create_member_login(write_conn, label: str, membership_type_code: str = "REGULAR") -> dict:
    """
    A person + active sangha_sevi + ACTIVE user_account and NOTHING else —
    no user_role, no admin_scope. Exactly the "plain logged-in member" these
    endpoints must serve, so the tests prove the self-role gate (not a
    permission) is what authorizes them.
    """
    from api.services.auth_service import hash_password

    person_pk = _create_person_of_type(write_conn, label, membership_type_code)
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


# ═══════════════════════════════════════════════════════════════════════
# 13. Endpoint-coverage matrix additions
#     (validation 422 / 404 / business-rule edges for every endpoint whose
#      happy path was previously the only thing exercised — 401/403/org-scope
#      negatives live in tests/security/test_governance_security.py)
# ═══════════════════════════════════════════════════════════════════════

def _body_type_pk_by_code(write_conn, body_type_code: str) -> str:
    """The pk of a SEEDED body type (skips the test if the seed lacks it)."""
    cur = write_conn.cursor()
    cur.execute(
        "SELECT body_type_master_pk FROM nss.body_type_master WHERE body_type_code = %s",
        (body_type_code,),
    )
    row = cur.fetchone()
    if row is None:
        pytest.skip(f"{body_type_code} body type is not seeded.")
    return str(row[0])


def _position_pks_by_code(write_conn) -> dict:
    """{position_code: position_master_pk} for every seeded position."""
    cur = write_conn.cursor()
    cur.execute("SELECT position_code, position_master_pk FROM nss.position_master")
    return {code: str(pk) for code, pk in cur.fetchall()}


def _make_body(client, headers, body_type_master_pk, *, name="Matrix Body",
               organization_pk=None, effective_from="2026-01-01") -> str:
    payload = {
        "body_type_master_pk": body_type_master_pk,
        "body_code": f"TB_{uuid4().hex[:10].upper()}",
        "body_name": name,
        "effective_from": effective_from,
    }
    if organization_pk:
        payload["organization_pk"] = organization_pk
    r = client.post(f"{BASE}/bodies", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


def _post_assignment(client, headers, body_pk, position_pk, person_pk, sevi_pk,
                     effective_from="2026-01-01"):
    """POST an assignment and hand back the raw response (callers assert)."""
    return client.post(
        f"{BASE}/bodies/{body_pk}/assignments",
        json={
            "position_master_pk": position_pk, "person_pk": person_pk,
            "sangha_sevi_pk": sevi_pk, "effective_from": effective_from,
        },
        headers=headers,
    )


def _make_election(client, headers, body_pk, **extra) -> str:
    payload = {
        "election_code": f"TEST_MX_{uuid4().hex[:8].upper()}",
        "body_master_pk": body_pk,
        "election_name": "Matrix Election",
        "election_date": "2026-11-01",
    }
    payload.update(extra)
    r = client.post(f"{BASE}/elections", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["election_pk"]


def _declare_result(client, headers, election_pk, position_pk, **extra):
    payload = {"position_master_pk": position_pk, "result_status": "DECLARED"}
    payload.update(extra)
    return client.post(f"{BASE}/elections/{election_pk}/results", json=payload, headers=headers)


def _advance_election(client, headers, election_pk, *statuses) -> str:
    """PATCH the election through each status in turn (each must succeed); returns election_pk."""
    for status in statuses:
        adv = client.patch(
            f"{BASE}/elections/{election_pk}/status",
            json={"election_status": status}, headers=headers,
        )
        assert adv.status_code == 200, adv.text
    return election_pk


def _seated_admin(client, admin_headers, write_conn, body_pk, position_pk) -> dict:
    """An NSS_ERP_ADMIN login who also holds `position_pk` on `body_pk`."""
    admin = _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None,
    )
    person = str(admin["person_pk"])
    sevi = _active_sevi_pk(write_conn, person)
    r = _post_assignment(client, admin_headers, body_pk, position_pk, person, sevi)
    assert r.status_code == 201, r.text
    return {
        "headers": _login_headers(client, admin["sangha_sevi_id"], admin["password"]),
        "person_pk": person, "sangha_sevi_pk": sevi,
    }


def _open_ballot(client, headers, write_conn, body_pk, position_pk, *,
                 secret=False, candidate_sakha_pk=None) -> dict:
    """
    An ELECTION cycle taken all the way to VOTING with one ACCEPTED candidate:
    schedule -> NOMINATION -> nominate -> accept -> VOTING. Returns the pks a
    ballot test needs.
    """
    election_pk = _make_election(client, headers, body_pk, is_secret_ballot=secret)
    _advance_election(client, headers, election_pk, "NOMINATION")
    candidate = _create_person(write_conn, "BallotCandidate")
    if candidate_sakha_pk:
        _reanchor_membership(write_conn, candidate, candidate_sakha_pk)
    nom = client.post(
        f"{BASE}/elections/{election_pk}/nominations",
        json={"position_master_pk": position_pk, "candidate_person_pk": candidate},
        headers=headers,
    )
    assert nom.status_code == 201, nom.text
    nomination_pk = nom.json()["election_nomination_pk"]
    acc = client.patch(
        f"{BASE}/nominations/{nomination_pk}/status",
        json={"nomination_status": "ACCEPTED"}, headers=headers,
    )
    assert acc.status_code == 200, acc.text
    _advance_election(client, headers, election_pk, "VOTING")
    return {"election_pk": election_pk, "nomination_pk": nomination_pk,
            "candidate_pk": candidate, "position_pk": position_pk}


# ── 13a. Catalogs: validation / 404 / reservation of retired codes ────────

class TestCatalogValidation:
    def test_body_type_code_is_trimmed_and_upper_cased(self, client, admin_headers):
        raw = f"tbt_case_{uuid4().hex[:8]}"
        r = client.post(
            f"{BASE}/body-types",
            json={"body_type_code": f"  {raw}  ", "body_type_name": "  Padded Name  "},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["body_type_code"] == raw.upper()
        assert r.json()["body_type_name"] == "Padded Name"

    def test_body_type_requires_a_name(self, client, admin_headers):
        r = client.post(f"{BASE}/body-types", json={"body_type_code": "ONLY_CODE"}, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_body_type_code_over_max_length_rejected(self, client, admin_headers):
        r = client.post(
            f"{BASE}/body-types",
            json={"body_type_code": "A" * 51, "body_type_name": "Too long"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_update_body_type_keeps_its_code(self, client, admin_headers, body_type_pk):
        """body_type_code is identity — a code in the PATCH body is ignored."""
        before = next(
            t for t in client.get(f"{BASE}/body-types", headers=admin_headers).json()
            if t["body_type_master_pk"] == body_type_pk
        )
        r = client.patch(
            f"{BASE}/body-types/{body_type_pk}",
            json={"description": "Updated description.", "body_type_code": "HIJACK"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["description"] == "Updated description."
        assert r.json()["body_type_code"] == before["body_type_code"]

    def test_update_unknown_body_type_returns_404(self, client, admin_headers):
        r = client.patch(f"{BASE}/body-types/{FAKE_UUID}", json={"body_type_name": "x"}, headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_deactivate_unknown_body_type_returns_404(self, client, admin_headers):
        assert client.delete(f"{BASE}/body-types/{FAKE_UUID}", headers=admin_headers).status_code == 404

    def test_deactivated_body_type_code_stays_reserved(self, client, admin_headers):
        """History is never deleted (GOV-BR-063): a retired code cannot be re-minted."""
        code = f"TBT_RES_{uuid4().hex[:8].upper()}"
        pk = client.post(
            f"{BASE}/body-types", json={"body_type_code": code, "body_type_name": "Retired"},
            headers=admin_headers,
        ).json()["body_type_master_pk"]
        assert client.delete(f"{BASE}/body-types/{pk}", headers=admin_headers).status_code == 200
        again = client.post(
            f"{BASE}/body-types", json={"body_type_code": code, "body_type_name": "Reborn"},
            headers=admin_headers,
        )
        assert again.status_code == 409, again.text

    def test_deactivated_body_type_cannot_anchor_a_new_body(self, client, admin_headers):
        code = f"TBT_DEAD_{uuid4().hex[:8].upper()}"
        pk = client.post(
            f"{BASE}/body-types", json={"body_type_code": code, "body_type_name": "Dead"},
            headers=admin_headers,
        ).json()["body_type_master_pk"]
        client.delete(f"{BASE}/body-types/{pk}", headers=admin_headers)
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": pk, "body_code": f"TB_DEAD_{uuid4().hex[:8].upper()}",
                "body_name": "Should not exist", "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_position_code_is_trimmed_and_upper_cased(self, client, admin_headers):
        raw = f"tp_case_{uuid4().hex[:8]}"
        r = client.post(
            f"{BASE}/positions",
            json={"position_code": f" {raw} ", "position_name": " Padded "},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["position_code"] == raw.upper()
        assert r.json()["position_name"] == "Padded"
        assert r.json()["display_order"] == 0

    def test_position_requires_a_name(self, client, admin_headers):
        r = client.post(f"{BASE}/positions", json={"position_code": "ONLY_CODE"}, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_update_position_name_and_description(self, client, admin_headers, position_pk):
        r = client.patch(
            f"{BASE}/positions/{position_pk}",
            json={"position_name": "Renamed Position", "description": "Now described."},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["position_name"] == "Renamed Position"
        assert r.json()["description"] == "Now described."

    def test_update_unknown_position_returns_404(self, client, admin_headers):
        r = client.patch(f"{BASE}/positions/{FAKE_UUID}", json={"position_name": "x"}, headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_deactivate_position_hides_it_unless_requested(self, client, admin_headers):
        code = f"TP_DEL_{uuid4().hex[:8].upper()}"
        pk = client.post(
            f"{BASE}/positions", json={"position_code": code, "position_name": "To Retire"},
            headers=admin_headers,
        ).json()["position_master_pk"]
        assert client.delete(f"{BASE}/positions/{pk}", headers=admin_headers).status_code == 200
        active = client.get(f"{BASE}/positions", headers=admin_headers).json()
        assert all(p["position_master_pk"] != pk for p in active)
        everything = client.get(f"{BASE}/positions?include_inactive=true", headers=admin_headers).json()
        assert any(p["position_master_pk"] == pk and p["is_active"] is False for p in everything)
        # The retired code stays reserved.
        again = client.post(
            f"{BASE}/positions", json={"position_code": code, "position_name": "Reborn"},
            headers=admin_headers,
        )
        assert again.status_code == 409, again.text

    def test_deactivate_unknown_position_returns_404(self, client, admin_headers):
        assert client.delete(f"{BASE}/positions/{FAKE_UUID}", headers=admin_headers).status_code == 404


# ── 13b. Bodies: listing filters, detail, create/update validation ───────

class TestBodyListingAndEdits:
    def test_search_matches_code_or_name(self, client, admin_headers, body_type_pk):
        tag = uuid4().hex[:10]
        pk = _make_body(client, admin_headers, body_type_pk, name=f"Zeta-{tag} Council")
        r = client.get(f"{BASE}/bodies", params={"search": tag}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert [b["body_master_pk"] for b in r.json()["items"]] == [pk]
        assert r.json()["total"] == 1

    def test_body_status_filter(self, client, admin_headers, body_type_pk):
        tag = uuid4().hex[:10]
        pk = _make_body(client, admin_headers, body_type_pk, name=f"Status-{tag}")
        client.patch(f"{BASE}/bodies/{pk}", json={"body_status": "INACTIVE"}, headers=admin_headers)
        inactive = client.get(
            f"{BASE}/bodies", params={"search": tag, "body_status": "INACTIVE"}, headers=admin_headers,
        ).json()
        assert [b["body_master_pk"] for b in inactive["items"]] == [pk]
        active = client.get(
            f"{BASE}/bodies", params={"search": tag, "body_status": "ACTIVE"}, headers=admin_headers,
        ).json()
        assert active["items"] == []

    def test_organization_filter(self, client, admin_headers, sakha_body_pk, two_sakha_pks):
        home, _ = two_sakha_pks
        r = client.get(
            f"{BASE}/bodies", params={"organization_pk": home, "page_size": 100}, headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert sakha_body_pk in [b["body_master_pk"] for b in items]
        assert all(b["organization_pk"] == home for b in items)

    def test_deactivated_body_hidden_unless_include_inactive(self, client, admin_headers, body_type_pk):
        tag = uuid4().hex[:10]
        pk = _make_body(client, admin_headers, body_type_pk, name=f"Gone-{tag}")
        assert client.delete(f"{BASE}/bodies/{pk}", headers=admin_headers).status_code == 200
        hidden = client.get(f"{BASE}/bodies", params={"search": tag}, headers=admin_headers).json()
        assert hidden["items"] == []
        shown = client.get(
            f"{BASE}/bodies", params={"search": tag, "include_inactive": "true"}, headers=admin_headers,
        ).json()
        assert [b["body_master_pk"] for b in shown["items"]] == [pk]
        assert shown["items"][0]["is_active"] is False

    def test_pagination_bounds(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies?page_size=101", headers=admin_headers).status_code == 422
        assert client.get(f"{BASE}/bodies?page=0", headers=admin_headers).status_code == 422
        r = client.get(f"{BASE}/bodies?page=1&page_size=1", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert len(r.json()["items"]) == 1
        assert r.json()["page_size"] == 1

    def test_unknown_sort_field_rejected(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies?sort_by=not_a_column", headers=admin_headers).status_code == 422

    def test_known_sort_field_accepted(self, client, admin_headers):
        r = client.get(f"{BASE}/bodies?sort_by=body_name&sort_dir=desc", headers=admin_headers)
        assert r.status_code == 200, r.text

    def test_include_members_attaches_composition(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        tag = uuid4().hex[:10]
        pk = _make_body(client, admin_headers, body_type_pk, name=f"Members-{tag}")
        person = _create_person(write_conn, "ListedMember")
        position = _new_position(client, admin_headers, "Listed Chair", 1)
        r = _post_assignment(client, admin_headers, pk, position, person, _active_sevi_pk(write_conn, person))
        assert r.status_code == 201, r.text

        plain = client.get(f"{BASE}/bodies", params={"search": tag}, headers=admin_headers).json()["items"][0]
        assert plain["members"] is None and plain["member_count"] is None

        rich = client.get(
            f"{BASE}/bodies", params={"search": tag, "include_members": "true"}, headers=admin_headers,
        ).json()["items"][0]
        assert rich["member_count"] == 1
        assert rich["scope_label"] == "NSS-wide"
        assert [m["person_pk"] for m in rich["members"]] == [person]
        assert rich["members"][0]["position_name"] == "Listed Chair"

    def test_get_unknown_body_returns_404(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies/{FAKE_UUID}", headers=admin_headers).status_code == 404

    def test_create_with_unknown_organization_returns_404(self, client, admin_headers, body_type_pk):
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"TB_NOORG_{uuid4().hex[:8].upper()}",
                "body_name": "Orphan", "organization_pk": FAKE_UUID, "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_create_with_end_before_start_rejected(self, client, admin_headers, body_type_pk):
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"TB_BADTERM_{uuid4().hex[:8].upper()}",
                "body_name": "Backwards term", "effective_from": "2026-05-01", "effective_to": "2026-04-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "Effective To cannot be before Effective From" in r.json()["detail"]

    def test_create_with_malformed_date_rejected(self, client, admin_headers, body_type_pk):
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"TB_BADDATE_{uuid4().hex[:8].upper()}",
                "body_name": "Bad date", "effective_from": "01/05/2026",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "YYYY-MM-DD" in r.json()["detail"]

    def test_create_requires_a_name(self, client, admin_headers, body_type_pk):
        r = client.post(
            f"{BASE}/bodies",
            json={"body_type_master_pk": body_type_pk, "body_code": f"TB_NONAME_{uuid4().hex[:8].upper()}"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_body_code_is_upper_cased(self, client, admin_headers, body_type_pk):
        raw = f"tb_lower_{uuid4().hex[:8]}"
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": raw,
                "body_name": "Lower code", "effective_from": "2026-01-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["body_code"] == raw.upper()

    def test_update_edits_name_description_and_start(self, client, admin_headers, body_type_pk):
        pk = _make_body(client, admin_headers, body_type_pk)
        r = client.patch(
            f"{BASE}/bodies/{pk}",
            json={"body_name": "  Renamed Body  ", "description": "Described.", "effective_from": "2026-02-01"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["body_name"] == "Renamed Body"
        assert data["description"] == "Described."
        assert data["effective_from"] == "2026-02-01"

    def test_update_with_empty_payload_changes_nothing(self, client, admin_headers, body_type_pk):
        pk = _make_body(client, admin_headers, body_type_pk, name="Untouched")
        r = client.patch(f"{BASE}/bodies/{pk}", json={}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["body_name"] == "Untouched"

    def test_update_unknown_body_returns_404(self, client, admin_headers):
        r = client.patch(f"{BASE}/bodies/{FAKE_UUID}", json={"body_name": "x"}, headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_update_rejects_unknown_status(self, client, admin_headers, body_pk):
        r = client.patch(f"{BASE}/bodies/{body_pk}", json={"body_status": "BOGUS"}, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_update_rejects_malformed_date(self, client, admin_headers, body_pk):
        r = client.patch(f"{BASE}/bodies/{body_pk}", json={"effective_to": "not-a-date"}, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_deactivate_unknown_body_returns_404(self, client, admin_headers):
        assert client.delete(f"{BASE}/bodies/{FAKE_UUID}", headers=admin_headers).status_code == 404


class TestSakhaScopeOptions:
    """GET /bodies/sakha-scope-options — parent-Sakha picker for Sakha-anchored bodies."""

    def test_nss_wide_admin_may_choose_any_active_sakha(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        r = client.get(
            f"{BASE}/bodies/sakha-scope-options",
            params={"body_type_master_pk": body_type_pk}, headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mode"] == "choose"
        assert data["auto_select_pk"] is None
        cur = write_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        """)
        assert len(data["sakhas"]) == cur.fetchone()[0]
        assert {"organization_pk", "organization_name", "organization_code"} <= data["sakhas"][0].keys()

    def test_single_sakha_admin_is_locked_to_that_sakha(
        self, client, scoped_headers, scoped_sakha_pk, body_type_pk,
    ):
        r = client.get(
            f"{BASE}/bodies/sakha-scope-options",
            params={"body_type_master_pk": body_type_pk}, headers=scoped_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mode"] == "locked"
        assert data["auto_select_pk"] == scoped_sakha_pk
        assert [s["organization_pk"] for s in data["sakhas"]] == [scoped_sakha_pk]

    def test_unknown_body_type_returns_404(self, client, admin_headers):
        r = client.get(
            f"{BASE}/bodies/sakha-scope-options",
            params={"body_type_master_pk": FAKE_UUID}, headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_body_type_parameter_is_required(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies/sakha-scope-options", headers=admin_headers).status_code == 422


# ── 13c. Login-only public panels (dashboard Governance tab) ──────────────

class TestPublicGovernancePanels:
    @pytest.fixture(scope="class")
    @classmethod
    def home_sakha(cls, two_sakha_pks):
        return two_sakha_pks[0]

    @pytest.fixture(scope="class")
    @classmethod
    def home_headers(cls, client, write_conn, home_sakha):
        member = _create_member_login(write_conn, "PanelHome")
        _reanchor_membership(write_conn, member["person_pk"], home_sakha)
        return _login_headers(client, member["sangha_sevi_id"], member["password"])

    @pytest.fixture(scope="class")
    @classmethod
    def other_headers(cls, client, write_conn, two_sakha_pks):
        member = _create_member_login(write_conn, "PanelOther")
        _reanchor_membership(write_conn, member["person_pk"], two_sakha_pks[1])
        return _login_headers(client, member["sangha_sevi_id"], member["password"])

    @pytest.fixture(scope="class")
    @classmethod
    def president(cls, write_conn, home_sakha):
        person = _create_person(write_conn, "PanelPresident")
        _reanchor_membership(write_conn, person, home_sakha)
        return person

    @pytest.fixture(scope="class")
    @classmethod
    def own_sakha_gb_pk(cls, client, admin_headers, write_conn, home_sakha, president):
        """A REAL-type Sakha Governing Body for the home Sakha with a seated President."""
        pk = _make_body(
            client, admin_headers, _body_type_pk_by_code(write_conn, "SAKHA_GOVERNING_BODY"),
            name="Panel Sakha GB", organization_pk=home_sakha,
        )
        r = _post_assignment(
            client, admin_headers, pk, _position_pks_by_code(write_conn)["PRESIDENT"],
            president, _active_sevi_pk(write_conn, president),
        )
        assert r.status_code == 201, r.text
        return pk

    def test_national_bodies_lists_nss_wide_and_own_sakha_gb_only(
        self, client, home_headers, body_pk, own_sakha_gb_pk, sakha_body_pk,
    ):
        r = client.get(f"{BASE}/public/national-bodies", headers=home_headers)
        assert r.status_code == 200, r.text
        bodies = r.json()["bodies"]
        by_pk = {b["body_master_pk"]: b for b in bodies}
        assert by_pk[body_pk]["scope_label"] == "NSS-wide"
        assert by_pk[own_sakha_gb_pk]["scope_label"] == "Your Sakha"
        # A Sakha-anchored body of any OTHER type is not part of this panel.
        assert sakha_body_pk not in by_pk
        # NSS-wide bodies sort ahead of the viewer's own Sakha body.
        order = [b["body_master_pk"] for b in bodies]
        assert order.index(own_sakha_gb_pk) > order.index(body_pk)
        assert {"members", "member_count", "body_type_code", "body_name"} <= by_pk[body_pk].keys()

    def test_national_bodies_hides_another_sakhas_governing_body(
        self, client, other_headers, own_sakha_gb_pk,
    ):
        r = client.get(f"{BASE}/public/national-bodies", headers=other_headers)
        assert r.status_code == 200, r.text
        assert own_sakha_gb_pk not in [b["body_master_pk"] for b in r.json()["bodies"]]

    def test_my_sakha_bodies_returns_only_the_viewers_sakha_bodies(
        self, client, home_headers, other_headers, home_sakha, body_pk, own_sakha_gb_pk, sakha_body_pk,
    ):
        r = client.get(f"{BASE}/public/my-sakha-bodies", headers=home_headers)
        assert r.status_code == 200, r.text
        bodies = r.json()["bodies"]
        pks = [b["body_master_pk"] for b in bodies]
        assert own_sakha_gb_pk in pks
        assert body_pk not in pks            # NSS-wide bodies belong to national-bodies
        assert sakha_body_pk not in pks      # a non-Sakha-level body type
        assert all(b["organization_pk"] == home_sakha for b in bodies)

        theirs = client.get(f"{BASE}/public/my-sakha-bodies", headers=other_headers).json()["bodies"]
        assert own_sakha_gb_pk not in [b["body_master_pk"] for b in theirs]

    def test_composition_carries_seated_member_details(
        self, client, home_headers, own_sakha_gb_pk, president,
    ):
        bodies = client.get(f"{BASE}/public/my-sakha-bodies", headers=home_headers).json()["bodies"]
        body = next(b for b in bodies if b["body_master_pk"] == own_sakha_gb_pk)
        assert body["member_count"] == 1
        member = body["members"][0]
        assert member["person_pk"] == president
        assert member["position_code"] == "PRESIDENT"
        assert member["sangha_sevi_id"]
        assert member["sakha_name"]
        assert member["acting_person_pk"] is None

    def test_sakha_office_bearers_directory_lists_the_president(
        self, client, home_headers, home_sakha, own_sakha_gb_pk,
    ):
        r = client.get(f"{BASE}/public/sakha-office-bearers", headers=home_headers)
        assert r.status_code == 200, r.text
        entry = r.json()["office_bearers"][home_sakha]
        assert entry["president"] is not None
        assert entry["president"]["name"]
        assert "mobile" in entry["president"]
        assert "secretary" in entry


# ── 13d. allowed-positions / inherited-positions / Mukhya Pujaka ──────────

class TestAllowedAndInheritedPositions:
    def test_unruled_body_offers_every_catalogue_position(
        self, client, admin_headers, body_type_pk,
    ):
        pk = _make_body(client, admin_headers, body_type_pk)
        r = client.get(f"{BASE}/bodies/{pk}/allowed-positions", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        codes = {p["position_code"] for p in data["positions"]}
        active = {p["position_code"] for p in client.get(f"{BASE}/positions", headers=admin_headers).json()}
        assert "MEMBER" in codes
        assert codes <= active
        assert data["seat_limit"] is None
        assert data["seats_filled"] == 0
        assert data["officers_from_members"] is False
        assert data["organization_pk"] is None

    def test_filled_office_position_is_hidden_unless_requested(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        pk = _make_body(client, admin_headers, body_type_pk)
        position = _new_position(client, admin_headers, "Matrix Filled Chair", 1)
        person = _create_person(write_conn, "ChairHolder")
        r = _post_assignment(client, admin_headers, pk, position, person, _active_sevi_pk(write_conn, person))
        assert r.status_code == 201, r.text

        default = client.get(f"{BASE}/bodies/{pk}/allowed-positions", headers=admin_headers).json()
        assert position not in [p["position_master_pk"] for p in default["positions"]]
        assert default["seats_filled"] == 1

        for_acting = client.get(
            f"{BASE}/bodies/{pk}/allowed-positions", params={"exclude_filled": "false"}, headers=admin_headers,
        ).json()
        assert position in [p["position_master_pk"] for p in for_acting["positions"]]

    def test_member_position_is_never_filtered_out(self, client, admin_headers, write_conn, body_type_pk):
        pk = _make_body(client, admin_headers, body_type_pk)
        member_position = _position_pks_by_code(write_conn)["MEMBER"]
        person = _create_person(write_conn, "PlainMember")
        r = _post_assignment(client, admin_headers, pk, member_position, person, _active_sevi_pk(write_conn, person))
        assert r.status_code == 201, r.text
        data = client.get(f"{BASE}/bodies/{pk}/allowed-positions", headers=admin_headers).json()
        assert member_position in [p["position_master_pk"] for p in data["positions"]]

    def test_ruled_body_offers_only_its_own_positions(
        self, client, admin_headers, write_conn, two_sakha_pks,
    ):
        home, _ = two_sakha_pks
        pk = _make_body(
            client, admin_headers, _body_type_pk_by_code(write_conn, "SEVAK_SANGHA_EXECUTIVE"),
            name="Matrix Sevak Executive", organization_pk=home,
        )
        data = client.get(f"{BASE}/bodies/{pk}/allowed-positions", headers=admin_headers).json()
        assert {p["position_code"] for p in data["positions"]} <= {"PRESIDENT", "SECRETARY", "TREASURER"}
        assert data["seat_limit"] == 3
        assert data["organization_pk"] == home

    def test_allowed_positions_unknown_body_returns_404(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies/{FAKE_UUID}/allowed-positions", headers=admin_headers).status_code == 404

    def test_inherited_positions_empty_for_a_body_that_inherits_nothing(self, client, admin_headers, body_pk):
        r = client.get(f"{BASE}/bodies/{body_pk}/inherited-positions", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json() == {"inherited": []}

    def test_mahila_body_surfaces_the_inherited_parichalak_seat(self, client, admin_headers, write_conn):
        pk = _make_body(
            client, admin_headers, _body_type_pk_by_code(write_conn, "MAHILA_PARICHALANA_MANDALI"),
            name="Matrix Mahila Mandali",
        )
        r = client.get(f"{BASE}/bodies/{pk}/inherited-positions", headers=admin_headers)
        assert r.status_code == 200, r.text
        inherited = r.json()["inherited"]
        assert len(inherited) == 1
        assert inherited[0]["position_code"] == "PARICHALAK"
        assert inherited[0]["source_body_type_code"] == "KENDRA_GOVERNING_BODY"
        # Null while the Kendra seat is vacant, a name once somebody holds it.
        assert inherited[0]["person_name"] is None or isinstance(inherited[0]["person_name"], str)

    def test_mahila_body_does_not_accept_a_direct_parichalak_assignment(
        self, client, admin_headers, write_conn,
    ):
        """PARICHALAK is inherited, never assigned directly, on the Mahila body (2026-10-08)."""
        pk = _make_body(
            client, admin_headers, _body_type_pk_by_code(write_conn, "MAHILA_PARICHALANA_MANDALI"),
            name="Matrix Mahila Direct",
        )
        person = _create_person(write_conn, "NotParichalak")
        r = _post_assignment(
            client, admin_headers, pk, _position_pks_by_code(write_conn)["PARICHALAK"],
            person, _active_sevi_pk(write_conn, person),
        )
        assert r.status_code == 422, r.text
        assert "not a position on this type" in r.json()["detail"]

    def test_inherited_positions_unknown_body_returns_404(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies/{FAKE_UUID}/inherited-positions", headers=admin_headers).status_code == 404


class TestMukhyaPujaka:
    def test_response_shape(self, client, admin_headers):
        r = client.get(f"{BASE}/mukhya-pujaka", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert {"position_master_pk", "position_name", "body_master_pk", "body_name", "holder"} <= data.keys()
        assert data["position_name"] == "Mukhya Pujaka"

    def test_post_is_a_single_nss_wide_seat(self, client, admin_headers, write_conn):
        positions = _position_pks_by_code(write_conn)
        kendra_type = _body_type_pk_by_code(write_conn, "KENDRA_GOVERNING_BODY")
        first_body = _make_body(client, admin_headers, kendra_type, name="Matrix Kendra One")
        second_body = _make_body(client, admin_headers, kendra_type, name="Matrix Kendra Two")

        holder = _create_person(write_conn, "MukhyaPujaka")
        r1 = _post_assignment(
            client, admin_headers, first_body, positions["MUKHYA_PUJAKA"],
            holder, _active_sevi_pk(write_conn, holder),
        )
        if r1.status_code == 409:
            pytest.skip("The Mukhya Pujaka seat is already held in this database.")
        assert r1.status_code == 201, r1.text

        current = client.get(f"{BASE}/mukhya-pujaka", headers=admin_headers).json()["holder"]
        assert current["person_pk"] == holder
        assert current["body_master_pk"] == first_body

        # A second person cannot take the post on ANOTHER body either.
        rival = _create_person(write_conn, "MukhyaRival")
        r2 = _post_assignment(
            client, admin_headers, second_body, positions["MUKHYA_PUJAKA"],
            rival, _active_sevi_pk(write_conn, rival),
        )
        assert r2.status_code == 409, r2.text
        assert "single NSS-wide post" in r2.json()["detail"]


# ── 13e. Assignment creation: validation + composition rules ──────────────

class TestAssignmentValidation:
    @pytest.fixture(scope="class")
    @classmethod
    def plain_body_pk(cls, client, admin_headers, body_type_pk):
        return _make_body(client, admin_headers, body_type_pk, name="Assignment Validation Body")

    def test_unknown_body_returns_404(self, client, admin_headers, write_conn, position_pk):
        person = _create_person(write_conn, "NoBody")
        r = _post_assignment(client, admin_headers, FAKE_UUID, position_pk, person, _active_sevi_pk(write_conn, person))
        assert r.status_code == 404, r.text

    def test_unknown_position_returns_404(self, client, admin_headers, write_conn, plain_body_pk):
        person = _create_person(write_conn, "NoPosition")
        r = _post_assignment(client, admin_headers, plain_body_pk, FAKE_UUID, person, _active_sevi_pk(write_conn, person))
        assert r.status_code == 404, r.text

    def test_unknown_person_returns_404(self, client, admin_headers, write_conn, plain_body_pk, position_pk):
        member = _create_person(write_conn, "SevisOwner")
        r = _post_assignment(
            client, admin_headers, plain_body_pk, position_pk, FAKE_UUID, _active_sevi_pk(write_conn, member),
        )
        assert r.status_code == 404, r.text

    def test_unknown_sangha_sevi_returns_404(self, client, admin_headers, write_conn, plain_body_pk, position_pk):
        person = _create_person(write_conn, "NoSevi")
        r = _post_assignment(client, admin_headers, plain_body_pk, position_pk, person, FAKE_UUID)
        assert r.status_code == 404, r.text
        assert "Sangha Sevi not found" in r.json()["detail"]

    def test_sangha_sevi_of_another_person_rejected(
        self, client, admin_headers, write_conn, plain_body_pk, position_pk,
    ):
        """GOV-BR-056: the supplied membership must belong to the person being seated."""
        person = _create_person(write_conn, "Seated")
        stranger = _create_person(write_conn, "Stranger")
        r = _post_assignment(
            client, admin_headers, plain_body_pk, position_pk, person, _active_sevi_pk(write_conn, stranger),
        )
        assert r.status_code == 422, r.text
        assert "does not belong to this person" in r.json()["detail"]

    def test_sangha_sevi_is_mandatory(self, client, admin_headers, write_conn, plain_body_pk, position_pk):
        person = _create_person(write_conn, "NoMembershipField")
        r = client.post(
            f"{BASE}/bodies/{plain_body_pk}/assignments",
            json={"position_master_pk": position_pk, "person_pk": person, "effective_from": "2026-01-01"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_end_before_start_rejected(self, client, admin_headers, write_conn, plain_body_pk):
        person = _create_person(write_conn, "BackwardsTerm")
        position = _new_position(client, admin_headers, "Backwards Chair", 1)
        r = client.post(
            f"{BASE}/bodies/{plain_body_pk}/assignments",
            json={
                "position_master_pk": position, "person_pk": person,
                "sangha_sevi_pk": _active_sevi_pk(write_conn, person),
                "effective_from": "2026-05-01", "effective_to": "2026-04-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "Effective To cannot be before Effective From" in r.json()["detail"]

    def test_malformed_date_rejected(self, client, admin_headers, write_conn, plain_body_pk, position_pk):
        person = _create_person(write_conn, "BadDate")
        r = _post_assignment(
            client, admin_headers, plain_body_pk, position_pk, person,
            _active_sevi_pk(write_conn, person), effective_from="2026/05/01",
        )
        assert r.status_code == 422, r.text

    def test_office_position_has_one_holder_per_body(self, client, admin_headers, write_conn, plain_body_pk):
        position = _new_position(client, admin_headers, "Single Holder Chair", 1)
        first = _create_person(write_conn, "FirstHolder")
        second = _create_person(write_conn, "SecondHolder")
        assert _post_assignment(
            client, admin_headers, plain_body_pk, position, first, _active_sevi_pk(write_conn, first),
        ).status_code == 201
        r = _post_assignment(
            client, admin_headers, plain_body_pk, position, second, _active_sevi_pk(write_conn, second),
        )
        assert r.status_code == 409, r.text
        assert "already has" in r.json()["detail"]

    def test_one_person_may_hold_two_offices_on_one_body(self, client, admin_headers, write_conn, plain_body_pk):
        chair = _new_position(client, admin_headers, "Dual Chair", 1)
        clerk = _new_position(client, admin_headers, "Dual Clerk", 2)
        person = _create_person(write_conn, "DualHolder")
        sevi = _active_sevi_pk(write_conn, person)
        assert _post_assignment(client, admin_headers, plain_body_pk, chair, person, sevi).status_code == 201
        assert _post_assignment(client, admin_headers, plain_body_pk, clerk, person, sevi).status_code == 201

    def test_position_outside_the_body_types_composition_rejected(
        self, client, admin_headers, write_conn, two_sakha_pks,
    ):
        home, _ = two_sakha_pks
        body = _make_body(
            client, admin_headers, _body_type_pk_by_code(write_conn, "SEVAK_SANGHA_EXECUTIVE"),
            name="Matrix Sevak Rules", organization_pk=home,
        )
        person = _create_person(write_conn, "WrongSeat")
        r = _post_assignment(
            client, admin_headers, body, _position_pks_by_code(write_conn)["MEMBER"],
            person, _active_sevi_pk(write_conn, person),
        )
        assert r.status_code == 422, r.text
        assert "is not a position on this type of governing body" in r.json()["detail"]

    def test_full_body_rejects_a_new_person(self, client, admin_headers, write_conn, two_sakha_pks):
        """GOV-BR-011 style seat cap: a Sakha Governing Body seats at most nine people."""
        home, _ = two_sakha_pks
        body = _make_body(
            client, admin_headers, _body_type_pk_by_code(write_conn, "SAKHA_GOVERNING_BODY"),
            name="Matrix Full Sakha GB", organization_pk=home,
        )
        member_position = _position_pks_by_code(write_conn)["MEMBER"]
        for n in range(9):
            person = _create_person(write_conn, f"Seat{n}")
            r = _post_assignment(
                client, admin_headers, body, member_position, person, _active_sevi_pk(write_conn, person),
            )
            assert r.status_code == 201, r.text
        tenth = _create_person(write_conn, "Seat9")
        r = _post_assignment(
            client, admin_headers, body, member_position, tenth, _active_sevi_pk(write_conn, tenth),
        )
        assert r.status_code == 422, r.text
        assert "This body is full (9 of 9 seats)" in r.json()["detail"]


# ── 13f. Forced-removal workflow (request / approve / reject, GOV-BR #18) ─

class TestForcedRemovalWorkflow:
    """
    A seat is only vacated by the body's own sitting President (or, while the
    Presidency is vacant, another of its own sitting office bearers) after a
    GB-resolution-backed request. The President/Treasurer fixtures are real
    NSS-wide admins who ALSO hold the seat — the endpoints need
    GOVERNANCE_MANAGE *and* the seat.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def removal_body_pk(cls, client, admin_headers, body_type_pk):
        return _make_body(client, admin_headers, body_type_pk, name="Removal Test Body")

    @pytest.fixture(scope="class")
    @classmethod
    def president(cls, client, admin_headers, write_conn, removal_body_pk):
        return _seated_admin(
            client, admin_headers, write_conn, removal_body_pk, _position_pks_by_code(write_conn)["PRESIDENT"],
        )

    @pytest.fixture(scope="class")
    @classmethod
    def treasurer(cls, client, admin_headers, write_conn, removal_body_pk, president):
        return _seated_admin(
            client, admin_headers, write_conn, removal_body_pk, _position_pks_by_code(write_conn)["TREASURER"],
        )

    def _new_seat(self, client, admin_headers, write_conn, body_pk) -> dict:
        person = _create_person(write_conn, "Removable")
        position = _new_position(client, admin_headers, "Removable Chair", 1)
        r = _post_assignment(client, admin_headers, body_pk, position, person, _active_sevi_pk(write_conn, person))
        assert r.status_code == 201, r.text
        return {"assignment_pk": r.json()["body_member_assignment_pk"], "position_pk": position, "person_pk": person}

    def _request(self, client, headers, assignment_pk, reason="Conduct unbecoming.", ref="GB/2026/12"):
        return client.post(
            f"{BASE}/assignments/{assignment_pk}/request-removal",
            json={"reason": reason, "gb_resolution_reference": ref}, headers=headers,
        )

    def test_request_marks_pending_but_the_seat_stays_held(
        self, client, admin_headers, write_conn, removal_body_pk, president,
    ):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        r = self._request(client, admin_headers, seat["assignment_pk"])
        assert r.status_code == 200, r.text
        assert r.json()["assignment_status"] == "PENDING_REMOVAL"
        assert r.json()["remarks"] == "Conduct unbecoming."
        assert r.json()["assignment_reference"] == "GB/2026/12"

        # The holder keeps serving until the President approves: nobody else
        # can take the single-holder position yet.
        rival = _create_person(write_conn, "Rival")
        again = _post_assignment(
            client, admin_headers, removal_body_pk, seat["position_pk"], rival, _active_sevi_pk(write_conn, rival),
        )
        assert again.status_code == 409, again.text

    def test_second_request_conflicts(self, client, admin_headers, write_conn, removal_body_pk, president):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        assert self._request(client, admin_headers, seat["assignment_pk"]).status_code == 200
        r = self._request(client, admin_headers, seat["assignment_pk"])
        assert r.status_code == 409, r.text
        assert "already PENDING_REMOVAL" in r.json()["detail"]

    def test_request_validation_and_404(self, client, admin_headers, write_conn, removal_body_pk, president):
        assert self._request(client, admin_headers, FAKE_UUID).status_code == 404
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        no_ref = client.post(
            f"{BASE}/assignments/{seat['assignment_pk']}/request-removal",
            json={"reason": "Missing resolution reference."}, headers=admin_headers,
        )
        assert no_ref.status_code == 422, no_ref.text
        empty_reason = client.post(
            f"{BASE}/assignments/{seat['assignment_pk']}/request-removal",
            json={"reason": "", "gb_resolution_reference": "GB/1"}, headers=admin_headers,
        )
        assert empty_reason.status_code == 422, empty_reason.text

    def test_requester_must_be_admin_or_own_office_bearer(
        self, client, admin_headers, scoped_headers, write_conn, removal_body_pk, president,
    ):
        """A Sakha-scoped admin has GOVERNANCE_MANAGE but no standing over an NSS-wide body's seats."""
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        r = self._request(client, scoped_headers, seat["assignment_pk"])
        assert r.status_code == 403, r.text
        assert "own admin or one of its own office bearers" in r.json()["detail"]

    def test_only_the_sitting_president_decides(
        self, client, admin_headers, write_conn, removal_body_pk, president, treasurer,
    ):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        assert self._request(client, admin_headers, seat["assignment_pk"]).status_code == 200
        pk = seat["assignment_pk"]
        # A super-admin with no seat, and a sitting non-President office bearer
        # while a President sits, are both refused — on approve and on reject.
        for headers in (admin_headers, treasurer["headers"]):
            approve = client.post(
                f"{BASE}/assignments/{pk}/approve-removal", json={"effective_to": "2026-06-01"}, headers=headers,
            )
            assert approve.status_code == 403, approve.text
            assert "sitting President" in approve.json()["detail"]
            reject = client.post(f"{BASE}/assignments/{pk}/reject-removal", json={}, headers=headers)
            assert reject.status_code == 403, reject.text

    def test_approval_needs_a_valid_effective_to(
        self, client, admin_headers, write_conn, removal_body_pk, president,
    ):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        pk = seat["assignment_pk"]
        assert self._request(client, admin_headers, pk).status_code == 200
        missing = client.post(f"{BASE}/assignments/{pk}/approve-removal", json={}, headers=president["headers"])
        assert missing.status_code == 422, missing.text
        assert "Effective To is required" in missing.json()["detail"]
        backwards = client.post(
            f"{BASE}/assignments/{pk}/approve-removal",
            json={"effective_to": "2025-12-31"}, headers=president["headers"],
        )
        assert backwards.status_code == 422, backwards.text
        assert "Effective To cannot be before Effective From" in backwards.json()["detail"]

    def test_president_approval_ends_the_seat_and_frees_the_position(
        self, client, admin_headers, write_conn, removal_body_pk, president,
    ):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        pk = seat["assignment_pk"]
        assert self._request(client, admin_headers, pk).status_code == 200
        r = client.post(
            f"{BASE}/assignments/{pk}/approve-removal",
            json={"effective_to": "2026-06-01", "remarks": "GB resolution carried."},
            headers=president["headers"],
        )
        assert r.status_code == 200, r.text
        assert r.json()["assignment_status"] == "ENDED"
        assert r.json()["effective_to"] == "2026-06-01"
        assert r.json()["remarks"] == "GB resolution carried."

        successor = _create_person(write_conn, "Successor")
        taken = _post_assignment(
            client, admin_headers, removal_body_pk, seat["position_pk"], successor,
            _active_sevi_pk(write_conn, successor), effective_from="2026-06-02",
        )
        assert taken.status_code == 201, taken.text

    def test_president_rejection_restores_the_seat(
        self, client, admin_headers, write_conn, removal_body_pk, president,
    ):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        pk = seat["assignment_pk"]
        assert self._request(client, admin_headers, pk).status_code == 200
        r = client.post(
            f"{BASE}/assignments/{pk}/reject-removal",
            json={"remarks": "Resolution not carried."}, headers=president["headers"],
        )
        assert r.status_code == 200, r.text
        assert r.json()["assignment_status"] == "ACTIVE"
        assert r.json()["effective_to"] is None
        assert r.json()["remarks"] == "Resolution not carried."

    def test_deciding_without_a_pending_request_conflicts(
        self, client, admin_headers, write_conn, removal_body_pk, president,
    ):
        seat = self._new_seat(client, admin_headers, write_conn, removal_body_pk)
        pk = seat["assignment_pk"]
        approve = client.post(
            f"{BASE}/assignments/{pk}/approve-removal",
            json={"effective_to": "2026-06-01"}, headers=president["headers"],
        )
        assert approve.status_code == 409, approve.text
        assert "no pending removal request" in approve.json()["detail"]
        reject = client.post(f"{BASE}/assignments/{pk}/reject-removal", json={}, headers=president["headers"])
        assert reject.status_code == 409, reject.text

    def test_decide_unknown_assignment_returns_404(self, client, president):
        for action in ("approve-removal", "reject-removal"):
            r = client.post(
                f"{BASE}/assignments/{FAKE_UUID}/{action}",
                json={"effective_to": "2026-06-01"}, headers=president["headers"],
            )
            assert r.status_code == 404, r.text

    def test_vacant_presidency_lets_another_office_bearer_decide(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        body = _make_body(client, admin_headers, body_type_pk, name="No-President Body")
        treasurer = _seated_admin(
            client, admin_headers, write_conn, body, _position_pks_by_code(write_conn)["TREASURER"],
        )
        seat = self._new_seat(client, admin_headers, write_conn, body)
        pk = seat["assignment_pk"]
        assert self._request(client, admin_headers, pk).status_code == 200

        # Still refused for a super-admin who holds no seat on THIS body ...
        refused = client.post(
            f"{BASE}/assignments/{pk}/approve-removal", json={"effective_to": "2026-06-01"}, headers=admin_headers,
        )
        assert refused.status_code == 403, refused.text
        # ... but the sitting Treasurer may stand in while the Presidency is vacant.
        r = client.post(
            f"{BASE}/assignments/{pk}/approve-removal",
            json={"effective_to": "2026-06-01"}, headers=treasurer["headers"],
        )
        assert r.status_code == 200, r.text
        assert r.json()["assignment_status"] == "ENDED"


# ── 13g. Acting assignments: validation + 404 edges ───────────────────────

class TestActingAssignmentValidation:
    def _create(self, client, headers, body_pk, position_pk, person_pk, **extra):
        payload = {
            "position_master_pk": position_pk, "person_pk": person_pk,
            "effective_from": "2026-05-01", "reason": "Matrix.",
        }
        payload.update(extra)
        return client.post(f"{BASE}/bodies/{body_pk}/acting-assignments", json=payload, headers=headers)

    def test_unknown_body_returns_404(self, client, admin_headers, position_pk, voter_person_pk):
        r = self._create(client, admin_headers, FAKE_UUID, position_pk, voter_person_pk)
        assert r.status_code == 404, r.text

    def test_unknown_position_and_person_return_404(
        self, client, admin_headers, body_pk, position_pk, voter_person_pk,
    ):
        assert self._create(client, admin_headers, body_pk, FAKE_UUID, voter_person_pk).status_code == 404
        assert self._create(client, admin_headers, body_pk, position_pk, FAKE_UUID).status_code == 404

    def test_end_before_start_rejected(self, client, admin_headers, body_pk, position_pk, voter_person_pk):
        r = self._create(
            client, admin_headers, body_pk, position_pk, voter_person_pk,
            effective_from="2026-05-01", effective_to="2026-04-01",
        )
        assert r.status_code == 422, r.text
        assert "Effective To cannot be before Effective From" in r.json()["detail"]

    def test_duplicate_open_ended_cover_conflicts(self, client, admin_headers, write_conn, body_type_pk):
        body = _make_body(client, admin_headers, body_type_pk, name="Acting Duplicate Body")
        position = _new_position(client, admin_headers, "Acting Dup Chair", 1)
        person = _create_person(write_conn, "ActingDup")
        assert self._create(client, admin_headers, body, position, person).status_code == 201
        r = self._create(client, admin_headers, body, position, person)
        assert r.status_code == 409, r.text
        assert "active, open-ended" in r.json()["detail"]

    def test_list_for_unknown_body_returns_404(self, client, admin_headers):
        assert client.get(f"{BASE}/bodies/{FAKE_UUID}/acting-assignments", headers=admin_headers).status_code == 404

    def test_end_unknown_acting_assignment_returns_404(self, client, admin_headers):
        r = client.post(
            f"{BASE}/acting-assignments/{FAKE_UUID}/end", json={"effective_to": "2026-06-01"}, headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_end_before_start_rejected_on_end(self, client, admin_headers, write_conn, body_type_pk):
        body = _make_body(client, admin_headers, body_type_pk, name="Acting End Body")
        position = _new_position(client, admin_headers, "Acting End Chair", 1)
        person = _create_person(write_conn, "ActingEnd")
        pk = self._create(client, admin_headers, body, position, person).json()["acting_position_assignment_pk"]
        r = client.post(
            f"{BASE}/acting-assignments/{pk}/end", json={"effective_to": "2026-04-01"}, headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_approve_and_reject_unknown_return_404(self, client, deleg_plain_headers):
        for action in ("approve", "reject"):
            r = client.post(f"{BASE}/acting-assignments/{FAKE_UUID}/{action}", json={}, headers=deleg_plain_headers)
            assert r.status_code == 404, r.text

    def test_my_delegation_end_unknown_returns_404(self, client, deleg_plain_headers):
        r = client.post(
            f"{BASE}/me/acting-delegations/{FAKE_UUID}/end",
            json={"effective_to": "2026-06-01"}, headers=deleg_plain_headers,
        )
        assert r.status_code == 404, r.text

    def test_my_delegation_unknown_position_or_body_returns_404(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk, deleg_nominee,
    ):
        nominee = str(deleg_nominee["person_pk"])
        no_position = client.post(
            f"{BASE}/me/acting-delegations",
            json={"body_master_pk": deleg_body_pk, "position_master_pk": FAKE_UUID,
                  "person_pk": nominee, "effective_from": "2026-02-01"},
            headers=deleg_bearer_headers,
        )
        assert no_position.status_code == 404, no_position.text
        no_body = client.post(
            f"{BASE}/me/acting-delegations",
            json={"body_master_pk": FAKE_UUID, "position_master_pk": deleg_held_position_pk,
                  "person_pk": nominee, "effective_from": "2026-02-01"},
            headers=deleg_bearer_headers,
        )
        assert no_body.status_code == 404, no_body.text

    def test_batch_with_reversed_dates_rejected(
        self, client, deleg_bearer_headers, deleg_body_pk, deleg_held_position_pk, deleg_nominee,
    ):
        r = client.post(
            f"{BASE}/me/acting-delegations/batch",
            json={
                "items": [{
                    "body_master_pk": deleg_body_pk, "position_master_pk": deleg_held_position_pk,
                    "person_pk": str(deleg_nominee["person_pk"]),
                }],
                "effective_from": "2026-09-01", "effective_to": "2026-08-01",
            },
            headers=deleg_bearer_headers,
        )
        assert r.status_code == 422, r.text
        assert "Effective To cannot be before Effective From" in r.json()["detail"]


# ── 13h. Elections: create/list validation and the status state machine ───

class TestElectionValidationAndLifecycle:
    def test_create_with_unknown_body_returns_404(self, client, admin_headers):
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_NOBODY_{uuid4().hex[:8].upper()}", "body_master_pk": FAKE_UUID,
                "election_name": "No such body", "election_date": "2026-11-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_create_with_reversed_nomination_window_rejected(self, client, admin_headers, body_pk):
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_BADNOM_{uuid4().hex[:8].upper()}", "body_master_pk": body_pk,
                "election_name": "Bad nomination window", "election_date": "2026-11-01",
                "nomination_start_date": "2026-10-15", "nomination_end_date": "2026-10-01",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "Nomination End Date" in r.json()["detail"]

    def test_create_with_reversed_voting_window_rejected(self, client, admin_headers, body_pk):
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_BADVOTE_{uuid4().hex[:8].upper()}", "body_master_pk": body_pk,
                "election_name": "Bad voting window", "election_date": "2026-11-01",
                "voting_start_date": "2026-10-25", "voting_end_date": "2026-10-20",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "Voting End Date" in r.json()["detail"]

    def test_create_rejects_unknown_election_type(self, client, admin_headers, body_pk):
        r = client.post(
            f"{BASE}/elections",
            json={
                "election_code": f"TEST_BADTYPE_{uuid4().hex[:8].upper()}", "body_master_pk": body_pk,
                "election_name": "Bad type", "election_date": "2026-11-01", "election_type": "BALLOT",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_create_requires_election_date_and_valid_format(self, client, admin_headers, body_pk):
        missing = client.post(
            f"{BASE}/elections",
            json={"election_code": f"TEST_NODATE_{uuid4().hex[:8].upper()}", "body_master_pk": body_pk,
                  "election_name": "No date"},
            headers=admin_headers,
        )
        assert missing.status_code == 422, missing.text
        malformed = client.post(
            f"{BASE}/elections",
            json={"election_code": f"TEST_BADDATE_{uuid4().hex[:8].upper()}", "body_master_pk": body_pk,
                  "election_name": "Bad date", "election_date": "01-11-2026"},
            headers=admin_headers,
        )
        assert malformed.status_code == 422, malformed.text

    def test_election_code_is_upper_cased(self, client, admin_headers, body_pk):
        raw = f"test_lower_{uuid4().hex[:8]}"
        r = client.post(
            f"{BASE}/elections",
            json={"election_code": raw, "body_master_pk": body_pk,
                  "election_name": "Lower code", "election_date": "2026-11-01"},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["election_code"] == raw.upper()

    def test_get_unknown_election_returns_404(self, client, admin_headers):
        assert client.get(f"{BASE}/elections/{FAKE_UUID}", headers=admin_headers).status_code == 404

    def test_list_filters(self, client, admin_headers, body_type_pk):
        body = _make_body(client, admin_headers, body_type_pk, name="Election Filter Body")
        tag = uuid4().hex[:8].upper()
        pk = _make_election(client, admin_headers, body, election_code=f"TEST_FLT_{tag}")
        by_search = client.get(f"{BASE}/elections", params={"search": tag}, headers=admin_headers).json()
        assert [e["election_pk"] for e in by_search["items"]] == [pk]
        by_body = client.get(f"{BASE}/elections", params={"body_master_pk": body}, headers=admin_headers).json()
        assert [e["election_pk"] for e in by_body["items"]] == [pk]
        scheduled = client.get(
            f"{BASE}/elections", params={"body_master_pk": body, "election_status": "SCHEDULED"},
            headers=admin_headers,
        ).json()
        assert scheduled["total"] == 1
        voting = client.get(
            f"{BASE}/elections", params={"body_master_pk": body, "election_status": "VOTING"},
            headers=admin_headers,
        ).json()
        assert voting["items"] == []

    def test_list_page_size_is_capped_and_sort_validated(self, client, admin_headers):
        assert client.get(f"{BASE}/elections?page_size=501", headers=admin_headers).status_code == 422
        assert client.get(f"{BASE}/elections?sort_by=not_a_column", headers=admin_headers).status_code == 422
        assert client.get(f"{BASE}/elections?sort_by=election_name&sort_dir=asc", headers=admin_headers).status_code == 200

    def _patch_status(self, client, headers, election_pk, status):
        return client.patch(
            f"{BASE}/elections/{election_pk}/status", json={"election_status": status}, headers=headers,
        )

    def test_cannot_jump_from_scheduled_to_voting(self, client, admin_headers, body_pk):
        pk = _make_election(client, admin_headers, body_pk)
        r = self._patch_status(client, admin_headers, pk, "VOTING")
        assert r.status_code == 422, r.text
        assert "Allowed next" in r.json()["detail"]

    def test_setting_the_current_status_is_a_noop(self, client, admin_headers, body_pk):
        pk = _make_election(client, admin_headers, body_pk)
        r = self._patch_status(client, admin_headers, pk, "SCHEDULED")
        assert r.status_code == 200, r.text
        assert r.json()["election_status"] == "SCHEDULED"

    def test_cancelled_is_terminal(self, client, admin_headers, body_pk):
        pk = _make_election(client, admin_headers, body_pk)
        assert self._patch_status(client, admin_headers, pk, "CANCELLED").status_code == 200
        r = self._patch_status(client, admin_headers, pk, "NOMINATION")
        assert r.status_code == 422, r.text
        assert "Allowed next: none" in r.json()["detail"]

    def test_completed_is_terminal(self, client, admin_headers, body_pk):
        pk = _make_election(client, admin_headers, body_pk)
        for status in ("NOMINATION", "VOTING", "COMPLETED"):
            assert self._patch_status(client, admin_headers, pk, status).status_code == 200
        r = self._patch_status(client, admin_headers, pk, "VOTING")
        assert r.status_code == 422, r.text
        assert "Allowed next: none" in r.json()["detail"]

    def test_nomination_cycle_cannot_complete_from_scheduled(self, client, admin_headers, body_pk):
        pk = _make_election(client, admin_headers, body_pk, election_type="NOMINATION")
        r = self._patch_status(client, admin_headers, pk, "COMPLETED")
        assert r.status_code == 422, r.text

    def test_unknown_status_value_rejected(self, client, admin_headers, body_pk):
        pk = _make_election(client, admin_headers, body_pk)
        assert self._patch_status(client, admin_headers, pk, "BOGUS").status_code == 422

    def test_status_change_on_unknown_election_returns_404(self, client, admin_headers):
        assert self._patch_status(client, admin_headers, FAKE_UUID, "NOMINATION").status_code == 404


# ── 13i. Nominations: validation, eligibility, status edits ───────────────

class TestNominationValidation:
    @pytest.fixture(scope="class")
    @classmethod
    def nomination_election_pk(cls, client, admin_headers, body_pk):
        return _advance_election(client, admin_headers, _make_election(client, admin_headers, body_pk), "NOMINATION")

    def _nominate(self, client, headers, election_pk, position_pk, candidate_pk, **extra):
        payload = {"position_master_pk": position_pk, "candidate_person_pk": candidate_pk}
        payload.update(extra)
        return client.post(f"{BASE}/elections/{election_pk}/nominations", json=payload, headers=headers)

    def test_unknown_election_returns_404(self, client, admin_headers, position_pk, candidate_person_pk):
        assert client.get(f"{BASE}/elections/{FAKE_UUID}/nominations", headers=admin_headers).status_code == 404
        assert self._nominate(client, admin_headers, FAKE_UUID, position_pk, candidate_person_pk).status_code == 404

    def test_unknown_position_candidate_and_proposer_return_404(
        self, client, admin_headers, write_conn, nomination_election_pk, position_pk,
    ):
        candidate = _create_person(write_conn, "NomCandidate")
        assert self._nominate(client, admin_headers, nomination_election_pk, FAKE_UUID, candidate).status_code == 404
        assert self._nominate(client, admin_headers, nomination_election_pk, position_pk, FAKE_UUID).status_code == 404
        r = self._nominate(
            client, admin_headers, nomination_election_pk, position_pk, candidate, proposer_person_pk=FAKE_UUID,
        )
        assert r.status_code == 404, r.text

    def test_candidate_without_membership_rejected(
        self, client, admin_headers, write_conn, nomination_election_pk, position_pk,
    ):
        bare, _ = _create_bare_person(write_conn, "NonMember")
        r = self._nominate(client, admin_headers, nomination_election_pk, position_pk, bare)
        assert r.status_code == 422, r.text
        assert "not an active NSS member" in r.json()["detail"]

    def test_associate_member_may_not_stand(
        self, client, admin_headers, write_conn, nomination_election_pk, position_pk,
    ):
        """GOV-BR-043: Associate members hold no electoral rights."""
        associate = _create_person_of_type(write_conn, "AssociateCandidate", "ASSOCIATE")
        r = self._nominate(client, admin_headers, nomination_election_pk, position_pk, associate)
        assert r.status_code == 422, r.text
        assert "may not stand for any elected post" in r.json()["detail"]

    def test_malformed_nomination_date_rejected(
        self, client, admin_headers, write_conn, nomination_election_pk, position_pk,
    ):
        candidate = _create_person(write_conn, "BadNomDate")
        r = self._nominate(
            client, admin_headers, nomination_election_pk, position_pk, candidate, nomination_date="5th Oct",
        )
        assert r.status_code == 422, r.text

    def test_status_edit_validation_and_404(
        self, client, admin_headers, write_conn, nomination_election_pk, position_pk,
    ):
        assert client.patch(
            f"{BASE}/nominations/{FAKE_UUID}/status", json={"nomination_status": "ACCEPTED"}, headers=admin_headers,
        ).status_code == 404
        candidate = _create_person(write_conn, "StatusEdit")
        pk = self._nominate(client, admin_headers, nomination_election_pk, position_pk, candidate).json()[
            "election_nomination_pk"
        ]
        bad = client.patch(
            f"{BASE}/nominations/{pk}/status", json={"nomination_status": "ELECTED"}, headers=admin_headers,
        )
        assert bad.status_code == 422, bad.text
        withdrawn = client.patch(
            f"{BASE}/nominations/{pk}/status", json={"nomination_status": "WITHDRAWN"}, headers=admin_headers,
        )
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["nomination_status"] == "WITHDRAWN"


# ── 13j. Ballots: officer-recorded votes, secrecy, reset ──────────────────

class TestBallots:
    @pytest.fixture(scope="class")
    @classmethod
    def ballot_scope(cls, client, admin_headers, body_type_pk):
        return {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Ballot Body"),
            "position_pk": _new_position(client, admin_headers, "Ballot Chair", 1),
        }

    def _cast(self, client, headers, ballot, voter_pk, remarks=None):
        payload = {"election_nomination_pk": ballot["nomination_pk"], "voter_person_pk": voter_pk}
        if remarks:
            payload["remarks"] = remarks
        return client.post(f"{BASE}/elections/{ballot['election_pk']}/votes", json=payload, headers=headers)

    def test_ineligible_voters_rejected(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        associate = _create_person_of_type(write_conn, "AssociateVoter", "ASSOCIATE")
        r = self._cast(client, admin_headers, ballot, associate)
        assert r.status_code == 422, r.text
        assert "may not vote" in r.json()["detail"]

        bare, _ = _create_bare_person(write_conn, "NonMemberVoter")
        r = self._cast(client, admin_headers, ballot, bare)
        assert r.status_code == 422, r.text
        assert "not an active NSS member" in r.json()["detail"]

        assert self._cast(client, admin_headers, ballot, FAKE_UUID).status_code == 404

    def test_vote_in_unknown_election_returns_404(self, client, admin_headers, accepted_nomination_pk, voter_person_pk):
        r = client.post(
            f"{BASE}/elections/{FAKE_UUID}/votes",
            json={"election_nomination_pk": accepted_nomination_pk, "voter_person_pk": voter_person_pk},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_secret_ballot_never_stores_or_returns_the_voter(
        self, client, admin_headers, write_conn, ballot_scope,
    ):
        ballot = _open_ballot(client, admin_headers, write_conn, secret=True, **ballot_scope)
        voter = _create_person(write_conn, "SecretVoter")
        r = self._cast(client, admin_headers, ballot, voter)
        assert r.status_code == 201, r.text
        assert r.json()["is_secret_ballot"] is True
        assert r.json()["voter_person_pk"] is None

        cur = write_conn.cursor()
        cur.execute(
            "SELECT voter_person_pk FROM nss.election_vote WHERE election_vote_pk = %s",
            (r.json()["election_vote_pk"],),
        )
        assert cur.fetchone()[0] is None
        cur.execute(
            "SELECT COUNT(*) FROM nss.election_vote_participation "
            "WHERE election_pk = %s AND voter_person_pk = %s",
            (ballot["election_pk"], voter),
        )
        assert cur.fetchone()[0] == 1

        # The participation ledger still enforces one vote per position.
        again = self._cast(client, admin_headers, ballot, voter)
        assert again.status_code == 409, again.text
        tally = client.get(f"{BASE}/elections/{ballot['election_pk']}/tally", headers=admin_headers).json()
        assert next(t for t in tally["items"] if t["election_nomination_pk"] == ballot["nomination_pk"])[
            "vote_count"
        ] == 1

    def test_reset_request_validation(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        url = f"{BASE}/elections/{ballot['election_pk']}/votes/reset"
        no_president = client.post(
            url, json={"reset_mode": "ADMIN_WITH_PRESIDENT_APPROVAL", "reason": "Recount ordered"},
            headers=admin_headers,
        )
        assert no_president.status_code == 422, no_president.text
        assert "president_person_pk is required" in no_president.json()["detail"]
        short_reason = client.post(
            url, json={"reset_mode": "PRESIDENT_UNILATERAL", "reason": "x"}, headers=admin_headers,
        )
        assert short_reason.status_code == 422, short_reason.text
        bad_mode = client.post(
            url, json={"reset_mode": "ANYONE", "reason": "Recount ordered"}, headers=admin_headers,
        )
        assert bad_mode.status_code == 422, bad_mode.text
        unknown_president = client.post(
            url,
            json={"reset_mode": "ADMIN_WITH_PRESIDENT_APPROVAL", "reason": "Recount ordered",
                  "president_person_pk": FAKE_UUID},
            headers=admin_headers,
        )
        assert unknown_president.status_code == 404, unknown_president.text
        unknown_election = client.post(
            f"{BASE}/elections/{FAKE_UUID}/votes/reset",
            json={"reset_mode": "PRESIDENT_UNILATERAL", "reason": "Recount ordered"}, headers=admin_headers,
        )
        assert unknown_election.status_code == 404, unknown_election.text

    def _president_ballot(self, client, admin_headers, write_conn, body_type_pk, **kw):
        """A VOTING ballot on a fresh body whose sitting PRESIDENT is a freshly created person."""
        scope = {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Reset Body"),
            "position_pk": _new_position(client, admin_headers, "Reset Chair", 1),
        }
        president = _create_person(write_conn, "ResetPresident")
        seated = _post_assignment(
            client, admin_headers, scope["body_pk"], _position_pks_by_code(write_conn)["PRESIDENT"],
            president, _active_sevi_pk(write_conn, president),
        )
        assert seated.status_code == 201, seated.text
        return _open_ballot(client, admin_headers, write_conn, **scope, **kw), president

    def _reset(self, client, headers, ballot, **extra):
        payload = {"reset_mode": "ADMIN_WITH_PRESIDENT_APPROVAL", "reason": "Recount ordered by the GB."}
        payload.update(extra)
        return client.post(f"{BASE}/elections/{ballot['election_pk']}/votes/reset", json=payload, headers=headers)

    def test_reset_soft_deletes_ballots_and_lets_members_vote_again(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        """History is never hard-deleted and nss_db_writer has no DELETE grant: reset flips is_active."""
        ballot, president = self._president_ballot(client, admin_headers, write_conn, body_type_pk)
        voters = [_create_person(write_conn, f"ResetVoter{n}") for n in range(2)]
        for voter in voters:
            assert self._cast(client, admin_headers, ballot, voter).status_code == 201

        r = self._reset(client, admin_headers, ballot, president_person_pk=president)
        assert r.status_code == 200, r.text
        assert r.json()["votes_deleted"] == 2
        assert r.json()["participation_deleted"] == 2

        cur = write_conn.cursor()
        for table in ("election_vote", "election_vote_participation"):
            cur.execute(
                f"SELECT COUNT(*) FILTER (WHERE is_active), COUNT(*) FILTER (WHERE NOT is_active "
                f"AND deleted_at IS NOT NULL) FROM nss.{table} WHERE election_pk = %s",
                (ballot["election_pk"],),
            )
            assert cur.fetchone() == (0, 2), table
        tally = client.get(f"{BASE}/elections/{ballot['election_pk']}/tally", headers=admin_headers).json()
        assert all(t["vote_count"] == 0 for t in tally["items"])
        # Participation was retired too, so the same voter can vote again (partial unique index).
        assert self._cast(client, admin_headers, ballot, voters[0]).status_code == 201
        # Reset ballots no longer count as "already voted" on the member's open-for-voting view.
        cur.execute(
            "SELECT COUNT(*) FROM nss.election_vote_participation WHERE election_pk = %s AND is_active",
            (ballot["election_pk"],),
        )
        assert cur.fetchone()[0] == 1

    def test_reset_single_position_leaves_other_positions(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        ballot, president = self._president_ballot(client, admin_headers, write_conn, body_type_pk)
        voter = _create_person(write_conn, "ResetPosVoter")
        assert self._cast(client, admin_headers, ballot, voter).status_code == 201
        other_position = _new_position(client, admin_headers, "Untouched Chair", 2)
        r = self._reset(
            client, admin_headers, ballot, president_person_pk=president, position_master_pk=other_position,
        )
        assert r.status_code == 200, r.text
        assert r.json()["votes_deleted"] == 0
        assert self._cast(client, admin_headers, ballot, voter).status_code == 409

    def test_president_unilateral_requires_the_sitting_president(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        """PRESIDENT_UNILATERAL is verified against the live seat, not taken as a bare claim."""
        ballot, _ = self._president_ballot(client, admin_headers, write_conn, body_type_pk)
        voter = _create_person(write_conn, "UnilateralVoter")
        assert self._cast(client, admin_headers, ballot, voter).status_code == 201
        # The global admin is not this body's President.
        refused = self._reset(client, admin_headers, ballot, reset_mode="PRESIDENT_UNILATERAL")
        assert refused.status_code == 403, refused.text
        assert "sitting President" in refused.json()["detail"]
        assert self._cast(client, admin_headers, ballot, voter).status_code == 409  # ballot untouched

    def test_president_unilateral_by_the_sitting_president_succeeds(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        scope = {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Unilateral Body"),
            "position_pk": _new_position(client, admin_headers, "Unilateral Chair", 1),
        }
        president = _seated_admin(
            client, admin_headers, write_conn, scope["body_pk"], _position_pks_by_code(write_conn)["PRESIDENT"],
        )
        ballot = _open_ballot(client, admin_headers, write_conn, **scope)
        voter = _create_person(write_conn, "UnilateralOkVoter")
        assert self._cast(client, admin_headers, ballot, voter).status_code == 201
        r = self._reset(client, president["headers"], ballot, reset_mode="PRESIDENT_UNILATERAL")
        assert r.status_code == 200, r.text
        assert r.json()["votes_deleted"] == 1

    def test_approving_president_must_be_the_sitting_president(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        ballot, _ = self._president_ballot(client, admin_headers, write_conn, body_type_pk)
        impostor = _create_person(write_conn, "NotThePresident")
        r = self._reset(client, admin_headers, ballot, president_person_pk=impostor)
        assert r.status_code == 422, r.text
        assert "not the sitting President" in r.json()["detail"]

    def test_completed_election_ballots_cannot_be_reset(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        ballot, president = self._president_ballot(client, admin_headers, write_conn, body_type_pk)
        voter = _create_person(write_conn, "CompletedVoter")
        assert self._cast(client, admin_headers, ballot, voter).status_code == 201
        _advance_election(client, admin_headers, ballot["election_pk"], "COMPLETED")
        r = self._reset(client, admin_headers, ballot, president_person_pk=president)
        assert r.status_code == 409, r.text
        assert "COMPLETED" in r.json()["detail"]
        cur = write_conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM nss.election_vote WHERE election_pk = %s AND is_active",
            (ballot["election_pk"],),
        )
        assert cur.fetchone()[0] == 1

    def test_ballot_rows_remain_immutable_apart_from_soft_delete(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        """The trigger now permits ONLY the is_active/deleted_at bookkeeping change."""
        import psycopg2.errors

        ballot, _ = self._president_ballot(client, admin_headers, write_conn, body_type_pk)
        assert self._cast(
            client, admin_headers, ballot, _create_person(write_conn, "ImmutableVoter"),
        ).status_code == 201
        cur = write_conn.cursor()
        cur.execute("SAVEPOINT immutable_probe")
        with pytest.raises(psycopg2.errors.RestrictViolation):
            cur.execute(
                "UPDATE nss.election_vote SET remarks = 'tampered' WHERE election_pk = %s",
                (ballot["election_pk"],),
            )
        cur.execute("ROLLBACK TO SAVEPOINT immutable_probe")
        cur.execute("RELEASE SAVEPOINT immutable_probe")

    def test_officer_vote_requires_voting_status(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        _advance_election(client, admin_headers, ballot["election_pk"], "COMPLETED")
        r = self._cast(client, admin_headers, ballot, _create_person(write_conn, "LateOfficerVoter"))
        assert r.status_code == 422, r.text
        assert "Voting is not open" in r.json()["detail"]

    def test_vote_requires_an_accepted_nomination(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        voter = _create_person(write_conn, "WithdrawnVoter")
        withdrawn = client.patch(
            f"{BASE}/nominations/{ballot['nomination_pk']}/status",
            json={"nomination_status": "WITHDRAWN"}, headers=admin_headers,
        )
        # Nomination status is frozen once voting opened, so retire the nomination directly.
        assert withdrawn.status_code == 422, withdrawn.text
        cur = write_conn.cursor()
        cur.execute(
            "UPDATE nss.election_nomination SET nomination_status = 'WITHDRAWN' "
            "WHERE election_nomination_pk = %s", (ballot["nomination_pk"],),
        )
        r = self._cast(client, admin_headers, ballot, voter)
        assert r.status_code == 422, r.text
        assert "ACCEPTED nomination" in r.json()["detail"]

    def test_unaccepted_nomination_cannot_be_voted_for(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        merely_nominated = _create_person(write_conn, "NominatedOnly")
        cur = write_conn.cursor()
        cur.execute(
            """
            INSERT INTO nss.election_nomination (election_pk, position_master_pk, candidate_person_pk)
            VALUES (%s, %s, %s) RETURNING election_nomination_pk
            """,
            (ballot["election_pk"], ballot["position_pk"], merely_nominated),
        )
        pending_pk = str(cur.fetchone()[0])
        r = self._cast(
            client, admin_headers, {**ballot, "nomination_pk": pending_pk},
            _create_person(write_conn, "PendingNomVoter"),
        )
        assert r.status_code == 422, r.text
        assert "ACCEPTED nomination" in r.json()["detail"]


class TestSelfServiceVoting:
    """POST /elections/{pk}/votes/self + GET /elections/open-for-voting (GOV-BR-045)."""

    @pytest.fixture(scope="class")
    @classmethod
    def ballot_scope(cls, client, admin_headers, body_type_pk):
        return {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Self Vote Body"),
            "position_pk": _new_position(client, admin_headers, "Self Vote Chair", 1),
        }

    def _member(self, client, write_conn, label, membership_type_code="REGULAR", sakha_pk=None):
        member = _create_member_login(write_conn, label, membership_type_code)
        if sakha_pk:
            _reanchor_membership(write_conn, member["person_pk"], sakha_pk)
        return member, _login_headers(client, member["sangha_sevi_id"], member["password"])

    def _vote(self, client, headers, election_pk, nomination_pk, **extra):
        return client.post(
            f"{BASE}/elections/{election_pk}/votes/self",
            json={"election_nomination_pk": nomination_pk, **extra}, headers=headers,
        )

    def test_member_casts_their_own_open_ballot_once(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        member, headers = self._member(client, write_conn, "SelfVoter")
        r = self._vote(client, headers, ballot["election_pk"], ballot["nomination_pk"], remarks="Mine.")
        assert r.status_code == 201, r.text
        assert r.json()["voter_person_pk"] == member["person_pk"]
        assert r.json()["is_secret_ballot"] is False
        dup = self._vote(client, headers, ballot["election_pk"], ballot["nomination_pk"])
        assert dup.status_code == 409, dup.text

    def test_open_for_voting_lists_the_ballot_and_remembers_the_vote(
        self, client, admin_headers, write_conn, ballot_scope,
    ):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        _, headers = self._member(client, write_conn, "OpenListVoter")

        def mine():
            items = client.get(f"{BASE}/elections/open-for-voting", headers=headers).json()["items"]
            return next(e for e in items if e["election_pk"] == ballot["election_pk"])

        before = mine()
        assert [n["election_nomination_pk"] for n in before["nominations"]] == [ballot["nomination_pk"]]
        assert before["voted_position_pks"] == []
        assert self._vote(client, headers, ballot["election_pk"], ballot["nomination_pk"]).status_code == 201
        assert mine()["voted_position_pks"] == [ballot["position_pk"]]

    def test_ballot_must_be_open(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        scheduled = _make_election(client, admin_headers, ballot_scope["body_pk"])
        _, headers = self._member(client, write_conn, "EarlyVoter")
        r = self._vote(client, headers, scheduled, ballot["nomination_pk"])
        assert r.status_code == 422, r.text
        assert "Voting is not open" in r.json()["detail"]
        # ... and a SCHEDULED election is not offered for voting at all.
        items = client.get(f"{BASE}/elections/open-for-voting", headers=headers).json()["items"]
        assert scheduled not in [e["election_pk"] for e in items]

    def test_unknown_election_and_nomination(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        _, headers = self._member(client, write_conn, "LostVoter")
        assert self._vote(client, headers, FAKE_UUID, ballot["nomination_pk"]).status_code == 404
        assert self._vote(client, headers, ballot["election_pk"], FAKE_UUID).status_code == 404

    def test_nomination_from_another_election_rejected(self, client, admin_headers, write_conn, ballot_scope):
        first = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        second = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        _, headers = self._member(client, write_conn, "CrossVoter")
        r = self._vote(client, headers, first["election_pk"], second["nomination_pk"])
        assert r.status_code == 422, r.text
        assert "does not belong to this election" in r.json()["detail"]

    def test_associate_member_may_not_vote(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **ballot_scope)
        _, headers = self._member(client, write_conn, "AssociateSelf", "ASSOCIATE")
        r = self._vote(client, headers, ballot["election_pk"], ballot["nomination_pk"])
        assert r.status_code == 422, r.text
        assert "may not vote" in r.json()["detail"]

    def test_secret_ballot_is_anonymous_but_recorded(self, client, admin_headers, write_conn, ballot_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, secret=True, **ballot_scope)
        member, headers = self._member(client, write_conn, "SecretSelf")
        r = self._vote(client, headers, ballot["election_pk"], ballot["nomination_pk"])
        assert r.status_code == 201, r.text
        assert r.json()["voter_person_pk"] is None
        assert r.json()["is_secret_ballot"] is True
        cur = write_conn.cursor()
        cur.execute(
            "SELECT voter_person_pk FROM nss.election_vote WHERE election_vote_pk = %s",
            (r.json()["election_vote_pk"],),
        )
        assert cur.fetchone()[0] is None
        cur.execute(
            "SELECT COUNT(*) FROM nss.election_vote_participation "
            "WHERE election_pk = %s AND voter_person_pk = %s",
            (ballot["election_pk"], member["person_pk"]),
        )
        assert cur.fetchone()[0] == 1

    def test_sakha_ballot_is_only_for_that_sakhas_electorate(
        self, client, admin_headers, write_conn, sakha_body_pk, position_pk, two_sakha_pks,
    ):
        """GOV-BR-094: a sibling Sakha's member neither sees nor may cast the ballot."""
        home, other = two_sakha_pks
        ballot = _open_ballot(
            client, admin_headers, write_conn, sakha_body_pk, position_pk, candidate_sakha_pk=home,
        )
        _, home_headers = self._member(client, write_conn, "HomeElector", sakha_pk=home)
        _, other_headers = self._member(client, write_conn, "OtherElector", sakha_pk=other)

        home_items = client.get(f"{BASE}/elections/open-for-voting", headers=home_headers).json()["items"]
        assert ballot["election_pk"] in [e["election_pk"] for e in home_items]
        other_items = client.get(f"{BASE}/elections/open-for-voting", headers=other_headers).json()["items"]
        assert ballot["election_pk"] not in [e["election_pk"] for e in other_items]

        refused = self._vote(client, other_headers, ballot["election_pk"], ballot["nomination_pk"])
        assert refused.status_code == 422, refused.text
        assert "not part of the electorate" in refused.json()["detail"]
        accepted = self._vote(client, home_headers, ballot["election_pk"], ballot["nomination_pk"])
        assert accepted.status_code == 201, accepted.text


# ── 13k. Results: declare validation and the explicit apply hand-off ──────

class TestResultDeclarationAndApply:
    @pytest.fixture(scope="class")
    @classmethod
    def result_scope(cls, client, admin_headers, body_type_pk):
        return {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Result Body"),
            "position_pk": _new_position(client, admin_headers, "Result Chair", 1),
        }

    def _declared_winner(self, client, admin_headers, write_conn, body_type_pk) -> dict:
        """
        A DECLARED result for a fresh winner on a fresh body + position. A fresh
        scope per call matters: an office position holds one person per body, so
        applying two different winners to one shared (body, position) would 409.
        """
        scope = {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Apply Body"),
            "position_pk": _new_position(client, admin_headers, "Apply Chair", 1),
        }
        ballot = _open_ballot(client, admin_headers, write_conn, **scope)
        r = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"],
            winning_nomination_pk=ballot["nomination_pk"], winner_person_pk=ballot["candidate_pk"], vote_count=0,
        )
        assert r.status_code == 201, r.text
        return {**ballot, "body_pk": scope["body_pk"], "result_pk": r.json()["election_result_pk"]}

    def test_declare_in_unknown_election_returns_404(self, client, admin_headers, position_pk):
        assert _declare_result(client, admin_headers, FAKE_UUID, position_pk).status_code == 404

    def test_unknown_winning_nomination_returns_404(self, client, admin_headers, write_conn, result_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **result_scope)
        r = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"], winning_nomination_pk=FAKE_UUID,
        )
        assert r.status_code == 404, r.text

    def test_malformed_declared_at_rejected(self, client, admin_headers, write_conn, result_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **result_scope)
        r = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"],
            result_status="VACANT", declared_at="yesterday",
        )
        assert r.status_code == 422, r.text
        assert "valid ISO datetime" in r.json()["detail"]

    def test_negative_vote_count_and_unknown_status_rejected(
        self, client, admin_headers, write_conn, result_scope,
    ):
        ballot = _open_ballot(client, admin_headers, write_conn, **result_scope)
        negative = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"], vote_count=-1,
        )
        assert negative.status_code == 422, negative.text
        bogus = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"], result_status="WON",
        )
        assert bogus.status_code == 422, bogus.text

    def test_nomination_cycle_cannot_carry_a_vote_count(self, client, admin_headers, result_scope):
        pk = _make_election(client, admin_headers, result_scope["body_pk"], election_type="NOMINATION")
        client.patch(
            f"{BASE}/elections/{pk}/status", json={"election_status": "NOMINATION"}, headers=admin_headers,
        )
        r = _declare_result(
            client, admin_headers, pk, result_scope["position_pk"], result_status="VACANT", vote_count=3,
        )
        assert r.status_code == 422, r.text
        assert "cannot carry a vote count" in r.json()["detail"]

    def test_apply_unknown_result_returns_404(self, client, admin_headers):
        r = client.post(f"{BASE}/results/{FAKE_UUID}/apply", json={}, headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_apply_vacant_result_has_nothing_to_assign(self, client, admin_headers, write_conn, result_scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **result_scope)
        declared = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"], result_status="VACANT",
        )
        assert declared.status_code == 201, declared.text
        r = client.post(
            f"{BASE}/results/{declared.json()['election_result_pk']}/apply", json={}, headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "has no winner to assign" in r.json()["detail"]

    def test_apply_seats_the_winner_with_default_reference_and_date(
        self, client, admin_headers, write_conn, body_type_pk,
    ):
        won = self._declared_winner(client, admin_headers, write_conn, body_type_pk)
        r = client.post(f"{BASE}/results/{won['result_pk']}/apply", json={}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["election_result_pk"] == won["result_pk"]
        seat = next(
            a for a in client.get(
                f"{BASE}/bodies/{won['body_pk']}/assignments", headers=admin_headers,
            ).json()["items"]
            if a["body_member_assignment_pk"] == r.json()["body_member_assignment_pk"]
        )
        assert seat["person_pk"] == won["candidate_pk"]
        assert seat["assignment_reference"] == f"ELECTION_RESULT:{won['result_pk']}"
        assert seat["effective_from"] == date.today().isoformat()

    def test_applying_twice_conflicts(self, client, admin_headers, write_conn, body_type_pk):
        won = self._declared_winner(client, admin_headers, write_conn, body_type_pk)
        assert client.post(f"{BASE}/results/{won['result_pk']}/apply", json={}, headers=admin_headers).status_code == 200
        again = client.post(f"{BASE}/results/{won['result_pk']}/apply", json={}, headers=admin_headers)
        assert again.status_code == 409, again.text
        assert "already holds this position" in again.json()["detail"]

    def test_apply_rejects_someone_elses_sangha_sevi(self, client, admin_headers, write_conn, body_type_pk):
        won = self._declared_winner(client, admin_headers, write_conn, body_type_pk)
        stranger = _create_person(write_conn, "NotTheWinner")
        r = client.post(
            f"{BASE}/results/{won['result_pk']}/apply",
            json={"sangha_sevi_pk": _active_sevi_pk(write_conn, stranger)}, headers=admin_headers,
        )
        assert r.status_code == 422, r.text
        assert "does not belong to this person" in r.json()["detail"]


# ── 13l. Hardening regressions (2026-10-28 governance bug sweep) ──────────

class TestHardeningRegressions:
    @pytest.fixture(scope="class")
    @classmethod
    def scope(cls, client, admin_headers, body_type_pk):
        return {
            "body_pk": _make_body(client, admin_headers, body_type_pk, name="Hardening Body"),
            "position_pk": _new_position(client, admin_headers, "Hardening Chair", 1),
        }

    def _nominate(self, client, headers, election_pk, position_pk, candidate_pk):
        return client.post(
            f"{BASE}/elections/{election_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": candidate_pk}, headers=headers,
        )

    def _set_nomination(self, client, headers, nomination_pk, status):
        return client.patch(
            f"{BASE}/nominations/{nomination_pk}/status", json={"nomination_status": status}, headers=headers,
        )

    # -- bug 2: PATCH /bodies effective window --------------------------------
    def test_patch_body_rejects_reversed_window(self, client, admin_headers, body_type_pk):
        pk = _make_body(client, admin_headers, body_type_pk, name="Window Body")
        before = client.patch(
            f"{BASE}/bodies/{pk}", json={"effective_to": "2025-12-31"}, headers=admin_headers,
        )
        assert before.status_code == 422, before.text  # against stored effective_from 2026-01-01
        ok = client.patch(f"{BASE}/bodies/{pk}", json={"effective_to": "2026-12-31"}, headers=admin_headers)
        assert ok.status_code == 200, ok.text
        after = client.patch(f"{BASE}/bodies/{pk}", json={"effective_from": "2027-01-01"}, headers=admin_headers)
        assert after.status_code == 422, after.text
        both = client.patch(
            f"{BASE}/bodies/{pk}",
            json={"effective_from": "2026-06-01", "effective_to": "2026-05-01"}, headers=admin_headers,
        )
        assert both.status_code == 422, both.text

    # -- bug 5: nominations gated on election status --------------------------
    def test_nomination_requires_nomination_status(self, client, admin_headers, write_conn, scope):
        election = _make_election(client, admin_headers, scope["body_pk"])  # SCHEDULED
        r = self._nominate(client, admin_headers, election, scope["position_pk"], _create_person(write_conn, "Early"))
        assert r.status_code == 422, r.text
        assert "Nominations are not open" in r.json()["detail"]

    def test_nomination_status_edit_frozen_once_voting_opens(self, client, admin_headers, write_conn, scope):
        ballot = _open_ballot(client, admin_headers, write_conn, **scope)
        r = self._set_nomination(client, admin_headers, ballot["nomination_pk"], "WITHDRAWN")
        assert r.status_code == 422, r.text
        assert "nominations are open" in r.json()["detail"]
        late = self._nominate(
            client, admin_headers, ballot["election_pk"], scope["position_pk"], _create_person(write_conn, "Late"),
        )
        assert late.status_code == 422, late.text

    # -- bug 6: withdrawn / rejected nominations can be re-filed --------------
    @pytest.mark.parametrize("terminal", ["WITHDRAWN", "REJECTED"])
    def test_terminal_nomination_can_be_refiled(self, client, admin_headers, write_conn, scope, terminal):
        election = _advance_election(client, admin_headers, _make_election(client, admin_headers, scope["body_pk"]), "NOMINATION")
        candidate = _create_person(write_conn, "Refile")
        first = self._nominate(client, admin_headers, election, scope["position_pk"], candidate)
        assert first.status_code == 201, first.text
        old_pk = first.json()["election_nomination_pk"]
        assert self._nominate(client, admin_headers, election, scope["position_pk"], candidate).status_code == 409
        assert self._set_nomination(client, admin_headers, old_pk, terminal).status_code == 200
        again = self._nominate(client, admin_headers, election, scope["position_pk"], candidate)
        assert again.status_code == 201, again.text
        # Reviving the old row would now duplicate the live one -> 409, not a 500.
        revive = self._set_nomination(client, admin_headers, old_pk, "ACCEPTED")
        assert revive.status_code == 409, revive.text

    # -- bug 7: declare_result validates winning_nomination_pk ----------------
    def test_winning_nomination_must_belong_to_this_election_and_position(
        self, client, admin_headers, write_conn, scope,
    ):
        ballot = _open_ballot(client, admin_headers, write_conn, **scope)
        other = _open_ballot(client, admin_headers, write_conn, **scope)
        elsewhere = _declare_result(
            client, admin_headers, ballot["election_pk"], ballot["position_pk"],
            winning_nomination_pk=other["nomination_pk"],
        )
        assert elsewhere.status_code == 422, elsewhere.text
        assert "not a nomination for this position in this election" in elsewhere.json()["detail"]
        wrong_position = _declare_result(
            client, admin_headers, ballot["election_pk"],
            _new_position(client, admin_headers, "Other Chair", 2),
            winning_nomination_pk=ballot["nomination_pk"],
        )
        assert wrong_position.status_code == 422, wrong_position.text

    def test_winning_nomination_must_be_accepted_and_match_winner(
        self, client, admin_headers, write_conn, scope,
    ):
        ballot = _open_ballot(client, admin_headers, write_conn, **scope)
        declare = lambda **kw: _declare_result(  # noqa: E731
            client, admin_headers, ballot["election_pk"], ballot["position_pk"], **kw,
        )
        mismatch = declare(
            winning_nomination_pk=ballot["nomination_pk"], winner_person_pk=_create_person(write_conn, "Mismatch"),
        )
        assert mismatch.status_code == 422, mismatch.text
        assert "does not match" in mismatch.json()["detail"]

        pending = write_conn.cursor()
        pending.execute(
            "INSERT INTO nss.election_nomination (election_pk, position_master_pk, candidate_person_pk) "
            "VALUES (%s, %s, %s) RETURNING election_nomination_pk",
            (ballot["election_pk"], ballot["position_pk"], _create_person(write_conn, "StillNominated")),
        )
        unaccepted = declare(winning_nomination_pk=str(pending.fetchone()[0]))
        assert unaccepted.status_code == 422, unaccepted.text
        assert "ACCEPTED" in unaccepted.json()["detail"]

        derived = declare(winning_nomination_pk=ballot["nomination_pk"], vote_count=0)
        assert derived.status_code == 201, derived.text
        assert derived.json()["winner_person_pk"] == ballot["candidate_pk"]

    # -- bug 8: terminal acting cover cannot be ended again -------------------
    def test_ended_or_rejected_acting_cover_cannot_be_ended(self, client, admin_headers, write_conn, scope):
        def new_cover(label):
            r = client.post(
                f"{BASE}/bodies/{scope['body_pk']}/acting-assignments",
                json={"position_master_pk": scope["position_pk"], "person_pk": _create_person(write_conn, label),
                      "effective_from": "2026-05-01"},
                headers=admin_headers,
            )
            assert r.status_code == 201, r.text
            return r.json()["acting_position_assignment_pk"]

        end = lambda pk: client.post(  # noqa: E731
            f"{BASE}/acting-assignments/{pk}/end", json={"effective_to": "2026-06-01"}, headers=admin_headers,
        )
        ended = new_cover("EndTwice")
        assert end(ended).status_code == 200
        again = end(ended)
        assert again.status_code == 409, again.text
        assert "already ENDED" in again.json()["detail"]

        rejected = new_cover("RejectedCover")
        write_conn.cursor().execute(
            "UPDATE nss.acting_position_assignment SET acting_status = 'REJECTED' "
            "WHERE acting_position_assignment_pk = %s", (rejected,),
        )
        refused = end(rejected)
        assert refused.status_code == 409, refused.text
        assert "already REJECTED" in refused.json()["detail"]

    # -- bug 10: no new seats / cover on a deactivated body -------------------
    def test_deactivated_body_takes_no_assignments_or_acting_cover(
        self, client, admin_headers, write_conn, body_type_pk, scope,
    ):
        body = _make_body(client, admin_headers, body_type_pk, name="Soon Deactivated")
        assert client.delete(f"{BASE}/bodies/{body}", headers=admin_headers).status_code == 200
        person = _create_person(write_conn, "DeactivatedSeat")
        seat = _post_assignment(
            client, admin_headers, body, scope["position_pk"], person, _active_sevi_pk(write_conn, person),
        )
        assert seat.status_code == 409, seat.text
        assert "deactivated" in seat.json()["detail"]
        cover = client.post(
            f"{BASE}/bodies/{body}/acting-assignments",
            json={"position_master_pk": scope["position_pk"], "person_pk": person, "effective_from": "2026-05-01"},
            headers=admin_headers,
        )
        assert cover.status_code == 409, cover.text

    # -- bug 9: open-for-voting walks the election org's subtree --------------
    def test_open_for_voting_lists_subtree_elections(
        self, client, admin_headers, write_conn, body_type_pk, position_pk, two_sakha_pks,
    ):
        home, _ = two_sakha_pks
        cur = write_conn.cursor()
        cur.execute("SELECT parent_organization_pk FROM nss.organization WHERE organization_pk = %s", (home,))
        parent = cur.fetchone()[0]
        if parent is None:
            pytest.skip("The test Sakha has no parent (Anchalika/Zilla) organization.")
        body = _make_body(client, admin_headers, body_type_pk, name="Anchalika Body", organization_pk=str(parent))
        ballot = _open_ballot(client, admin_headers, write_conn, body, position_pk, candidate_sakha_pk=home)
        member = _create_member_login(write_conn, "SubtreeElector")
        _reanchor_membership(write_conn, member["person_pk"], home)
        headers = _login_headers(client, member["sangha_sevi_id"], member["password"])
        items = client.get(f"{BASE}/elections/open-for-voting", headers=headers).json()["items"]
        assert ballot["election_pk"] in [e["election_pk"] for e in items]
        # ...and the listing agrees with the eligibility check: the same member can cast the ballot.
        cast = client.post(
            f"{BASE}/elections/{ballot['election_pk']}/votes/self",
            json={"election_nomination_pk": ballot["nomination_pk"]}, headers=headers,
        )
        assert cast.status_code == 201, cast.text
