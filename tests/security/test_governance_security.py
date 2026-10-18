"""
NSS ERP — Security tests for the Governance module (api/routers/governance.py).

Focus: two gaps NOT covered by tests/api/test_governance.py's existing
TestRbac class (which only asserts anonymous-401 on bodies/body-types):

1. `resign_assignment` — a strictly self-service action with NO permission
   dependency and NO admin/scope override of any kind (2026-10-15 design:
   only the office holder named on the assignment may resign it — not even
   an NSS-WIDE GOVERNANCE_MANAGE super-admin can resign on someone else's
   behalf; forced removal is a separate workflow requiring body-President
   approval).
2. `create_assignment` scope negatives — an org-scoped admin creating an
   assignment for a body anchored to a DIFFERENT organization, or for an
   NSS-wide (organization_pk IS NULL) body.

Exact error strings asserted verbatim against the router source
(api/routers/governance.py:151-174, 2296-2366, 2460-2550).
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/governance"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "GovSecAdminPass1"
SCOPED_PASSWORD = "GovSecScopedPass1"
HOLDER_PASSWORD = "GovSecHolderPass1"


# ═══════════════════════════════════════════════════════════════════════
# Fixture-builder helpers (self-contained — mirrors the pattern already
# used in tests/security/test_membership_change_request_security.py).
# ═══════════════════════════════════════════════════════════════════════

def _membership_type_pk(write_conn, value_code: str = "REGULAR"):
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


def _create_person_with_sevi(write_conn, label: str, *, organization_pk: str):
    """Bare person + active sangha_sevi — no user_account yet."""
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"SGOV{suffix}", label, suffix, f"sgov.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    membership_type_pk = _membership_type_pk(write_conn)
    membership_status_pk = _membership_status_active_pk(write_conn)
    sangha_sevi_id = f"SGOVSS{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        RETURNING sangha_sevi_pk
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(organization_pk)))
    sangha_sevi_pk = cur.fetchone()[0]

    return {"person_pk": str(person_pk), "sangha_sevi_pk": str(sangha_sevi_pk),
            "sangha_sevi_id": sangha_sevi_id}


def _attach_user_account(write_conn, person_pk: str, sangha_sevi_id: str, password: str):
    from api.services.auth_service import hash_password
    cur = write_conn.cursor()
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (person_pk, hash_password(password)))
    return str(cur.fetchone()[0])


def _grant_role(write_conn, user_account_pk: str, role_code: str, *, scope_level: str, organization_pk):
    cur = write_conn.cursor()
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
    """, (user_account_pk, str(role_master_pk)))
    user_role_pk = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, %s, %s)
    """, (str(user_role_pk), scope_level,
          str(organization_pk) if (scope_level != "NSS-WIDE" and organization_pk) else None))


def _login_headers(client, login_id: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ═══════════════════════════════════════════════════════════════════════
# Module fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def zone_org_pks(write_conn):
    """zone_a = scoped admin's own Sakha; zone_b = a disjoint Sakha used to
    anchor the 'foreign' body."""
    return _active_sakha_org_pks(write_conn, 2)


@pytest.fixture(scope="module")
def zone_a_org_pk(zone_org_pks):
    return zone_org_pks[0]


@pytest.fixture(scope="module")
def zone_b_org_pk(zone_org_pks):
    return zone_org_pks[1]


@pytest.fixture(scope="module")
def nss_wide_admin(write_conn, zone_a_org_pk):
    data = _create_person_with_sevi(write_conn, "GovSecNssAdmin", organization_pk=zone_a_org_pk)
    uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], ADMIN_PASSWORD)
    _grant_role(write_conn, uap, "NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None)
    return data


@pytest.fixture(scope="module")
def nss_wide_headers(client, nss_wide_admin):
    return _login_headers(client, nss_wide_admin["sangha_sevi_id"], ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def scoped_admin_a(write_conn, zone_a_org_pk):
    """GOVERNANCE_MANAGE scoped strictly to zone_a_org_pk."""
    data = _create_person_with_sevi(write_conn, "GovSecScopedA", organization_pk=zone_a_org_pk)
    uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], SCOPED_PASSWORD)
    _grant_role(write_conn, uap, "NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=zone_a_org_pk)
    return data


@pytest.fixture(scope="module")
def scoped_a_headers(client, scoped_admin_a):
    return _login_headers(client, scoped_admin_a["sangha_sevi_id"], SCOPED_PASSWORD)


@pytest.fixture(scope="module")
def holder(write_conn, zone_a_org_pk):
    """The future office holder — a plain member with login, no governance role."""
    data = _create_person_with_sevi(write_conn, "GovSecHolder", organization_pk=zone_a_org_pk)
    _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], HOLDER_PASSWORD)
    return data


@pytest.fixture(scope="module")
def holder_headers(client, holder):
    return _login_headers(client, holder["sangha_sevi_id"], HOLDER_PASSWORD)


@pytest.fixture(scope="module")
def someone_else(write_conn, zone_a_org_pk):
    """A different member with login — used to prove non-holders are rejected."""
    data = _create_person_with_sevi(write_conn, "GovSecOther", organization_pk=zone_a_org_pk)
    _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], HOLDER_PASSWORD + "x")
    return data


@pytest.fixture(scope="module")
def someone_else_headers(client, someone_else):
    return _login_headers(client, someone_else["sangha_sevi_id"], HOLDER_PASSWORD + "x")


@pytest.fixture(scope="module")
def body_type_pk(client, nss_wide_headers):
    code = f"SEC_BODY_TYPE_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/body-types",
        json={"body_type_code": code, "body_type_name": "Sec Body Type"},
        headers=nss_wide_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_type_master_pk"]


@pytest.fixture(scope="module")
def position_pk(client, nss_wide_headers):
    code = f"SEC_POSITION_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/positions",
        json={"position_code": code, "position_name": "Sec Secretary", "display_order": 1},
        headers=nss_wide_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["position_master_pk"]


@pytest.fixture(scope="module")
def body_a_pk(client, nss_wide_headers, body_type_pk, zone_a_org_pk):
    """A body anchored to zone_a_org_pk — inside scoped_admin_a's scope."""
    code = f"SEC_BODY_A_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": code,
            "body_name": "Sec Body A",
            "organization_pk": zone_a_org_pk,
            "effective_from": "2026-01-01",
        },
        headers=nss_wide_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


@pytest.fixture(scope="module")
def body_b_pk(client, nss_wide_headers, body_type_pk, zone_b_org_pk):
    """A body anchored to zone_b_org_pk — OUTSIDE scoped_admin_a's scope."""
    code = f"SEC_BODY_B_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": code,
            "body_name": "Sec Body B",
            "organization_pk": zone_b_org_pk,
            "effective_from": "2026-01-01",
        },
        headers=nss_wide_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


@pytest.fixture(scope="module")
def body_nss_wide_pk(client, nss_wide_headers, body_type_pk):
    """An NSS-wide body (organization_pk NULL)."""
    code = f"SEC_BODY_NW_{uuid4().hex[:8].upper()}"
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": body_type_pk,
            "body_code": code,
            "body_name": "Sec Body NSS-Wide",
            "effective_from": "2026-01-01",
        },
        headers=nss_wide_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


def _assignment_payload(position_pk, person_pk, sangha_sevi_pk, effective_from="2026-01-02"):
    return {
        "position_master_pk": position_pk,
        "person_pk": person_pk,
        "sangha_sevi_pk": sangha_sevi_pk,
        "effective_from": effective_from,
    }


# ═══════════════════════════════════════════════════════════════════════
# create_assignment — scope negatives
# ═══════════════════════════════════════════════════════════════════════

class TestCreateAssignmentScope:
    def test_scoped_admin_cannot_assign_in_foreign_org_body(
        self, client, scoped_a_headers, body_b_pk, position_pk, holder,
    ):
        """scoped_admin_a is scoped to zone_a; body_b is anchored to zone_b."""
        r = client.post(
            f"{BASE}/bodies/{body_b_pk}/assignments",
            json=_assignment_payload(position_pk, holder["person_pk"], holder["sangha_sevi_pk"]),
            headers=scoped_a_headers,
        )
        assert r.status_code == 403
        assert "You can only manage body member assignments within your admin scope." in r.text

    def test_scoped_admin_cannot_assign_on_nss_wide_body(
        self, client, scoped_a_headers, body_nss_wide_pk, position_pk, holder,
    ):
        r = client.post(
            f"{BASE}/bodies/{body_nss_wide_pk}/assignments",
            json=_assignment_payload(position_pk, holder["person_pk"], holder["sangha_sevi_pk"]),
            headers=scoped_a_headers,
        )
        assert r.status_code == 403
        assert "Only an NSS-wide admin may manage body member assignments" in r.text

    def test_nss_wide_admin_can_assign_anywhere(
        self, client, nss_wide_headers, body_a_pk, position_pk, holder,
    ):
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(position_pk, holder["person_pk"], holder["sangha_sevi_pk"]),
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text

    def test_scoped_admin_can_assign_within_own_scope(
        self, client, scoped_a_headers, body_a_pk, position_pk, someone_else,
    ):
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(position_pk, someone_else["person_pk"], someone_else["sangha_sevi_pk"]),
            headers=scoped_a_headers,
        )
        assert r.status_code == 201, r.text

    def test_create_assignment_requires_auth(self, anon_client, body_a_pk, position_pk, holder):
        r = anon_client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(position_pk, holder["person_pk"], holder["sangha_sevi_pk"]),
        )
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# resign_assignment — strictly self-service, NO admin/scope override
# ═══════════════════════════════════════════════════════════════════════

class TestResignAssignment:
    @pytest.fixture()
    def fresh_assignment_pk(self, client, nss_wide_headers, body_a_pk, position_pk, holder):
        """A fresh, currently-ACTIVE assignment held by `holder`, created anew
        per test (function-scoped) so resign/double-resign tests don't collide."""
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(
                position_pk, holder["person_pk"], holder["sangha_sevi_pk"],
                effective_from=f"2026-01-{uuid4().int % 27 + 1:02d}",
            ),
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text
        return r.json()["assignment_pk"]

    def test_not_found_returns_404(self, client, holder_headers):
        r = client.post(
            f"{BASE}/assignments/{FAKE_UUID}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "No longer available."},
            headers=holder_headers,
        )
        assert r.status_code == 404
        assert "Assignment not found." in r.text

    def test_non_holder_forbidden(self, client, someone_else_headers, fresh_assignment_pk):
        r = client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "Not mine."},
            headers=someone_else_headers,
        )
        assert r.status_code == 403
        assert "Only the office holder may resign this assignment." in r.text

    def test_nss_wide_admin_has_no_override(self, client, nss_wide_headers, fresh_assignment_pk):
        """Deliberate design (2026-10-15): even an NSS-wide GOVERNANCE_MANAGE
        super-admin cannot resign on someone else's behalf — forced removal
        is a separate, body-President-approved workflow."""
        r = client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "Admin override attempt."},
            headers=nss_wide_headers,
        )
        assert r.status_code == 403
        assert "Only the office holder may resign this assignment." in r.text

    def test_holder_can_resign_self(self, client, holder_headers, fresh_assignment_pk):
        r = client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "Stepping down."},
            headers=holder_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["assignment_status"] == "RESIGNED"

    def test_double_resign_returns_409(self, client, holder_headers, fresh_assignment_pk):
        r1 = client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "First resignation."},
            headers=holder_headers,
        )
        assert r1.status_code == 200, r1.text

        r2 = client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "Second attempt."},
            headers=holder_headers,
        )
        assert r2.status_code == 409
        assert "Cannot resign — this assignment is already RESIGNED." in r2.text

    def test_effective_to_before_effective_from_rejected(self, client, nss_wide_headers, holder_headers, body_a_pk, position_pk, holder):
        """A freshly-created assignment with effective_from set a few days out;
        resigning with an effective_to before that date must 422."""
        future_start = str(date.today() + timedelta(days=10))
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(position_pk, holder["person_pk"], holder["sangha_sevi_pk"], effective_from=future_start),
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text
        assignment_pk = r.json()["assignment_pk"]

        r2 = client.post(
            f"{BASE}/assignments/{assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "Backdated before start."},
            headers=holder_headers,
        )
        assert r2.status_code == 422
        assert "Effective To cannot be before Effective From." in r2.text

    def test_future_effective_to_rejected(self, client, holder_headers, fresh_assignment_pk):
        future = str(date.today() + timedelta(days=5))
        r = client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": future, "resignation_reason": "Trying to backdate... forward."},
            headers=holder_headers,
        )
        assert r.status_code == 422
        assert "Resignation takes effect immediately" in r.text

    def test_resign_requires_auth(self, anon_client, fresh_assignment_pk):
        r = anon_client.post(
            f"{BASE}/assignments/{fresh_assignment_pk}/resign",
            json={"effective_to": str(date.today()), "resignation_reason": "Anon."},
        )
        assert r.status_code in (401, 403)
