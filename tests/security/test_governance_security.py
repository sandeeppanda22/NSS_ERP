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

3. The full endpoint authentication / permission matrix: every one of the 56
   governance endpoints is exercised anonymously (401), as a member with no
   governance role (403 on the permissioned ones), and as a view-only auditor
   (403 on every write); Sakha-scoped admins are then checked against bodies,
   assignments, acting cover, elections, nominations, votes and results anchored
   to a FOREIGN organization and to the NSS-wide level (403), plus the Advisory
   Board's Sakha-nominated seat authority (GOV-BR item #18).

Exact error strings asserted verbatim against the router source
(api/routers/governance.py).
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
SCOPED_B_PASSWORD = "GovSecScopedBPass1"
AUDITOR_PASSWORD = "GovSecAuditorPass1"
TWO_SAKHA_PASSWORD = "GovSecTwoSakhaPass1"


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


def _fresh_position(client, headers, name="Sec Seat") -> str:
    """
    A brand-new position. An office (non-MEMBER) position holds ONE person per
    body, and one person cannot hold the same position twice while open-ended,
    so every assignment that must succeed gets its own position instead of
    sharing the module-level `position_pk` fixture.
    """
    r = client.post(
        f"{BASE}/positions",
        json={"position_code": f"SEC_SEAT_{uuid4().hex[:10].upper()}", "position_name": name, "display_order": 5},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["position_master_pk"]


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
        self, client, nss_wide_headers, body_a_pk, someone_else,
    ):
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(
                _fresh_position(client, nss_wide_headers), someone_else["person_pk"], someone_else["sangha_sevi_pk"],
            ),
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text

    def test_scoped_admin_can_assign_within_own_scope(
        self, client, nss_wide_headers, scoped_a_headers, body_a_pk, holder,
    ):
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(
                _fresh_position(client, nss_wide_headers), holder["person_pk"], holder["sangha_sevi_pk"],
            ),
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
    def fresh_assignment_pk(self, client, nss_wide_headers, body_a_pk, holder):
        """A fresh, currently-ACTIVE assignment held by `holder`, created anew
        per test (function-scoped) so resign/double-resign tests don't collide.
        Each one gets its OWN position: the active-holder unique index and the
        one-person-per-office rule would otherwise 409 the second creation."""
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(
                _fresh_position(client, nss_wide_headers), holder["person_pk"], holder["sangha_sevi_pk"],
                effective_from=f"2026-01-{uuid4().int % 27 + 1:02d}",
            ),
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text
        return r.json()["body_member_assignment_pk"]

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

    def test_effective_to_before_effective_from_rejected(self, client, nss_wide_headers, holder_headers, body_a_pk, holder):
        """A freshly-created assignment with effective_from set a few days out;
        resigning with an effective_to before that date must 422."""
        future_start = str(date.today() + timedelta(days=10))
        r = client.post(
            f"{BASE}/bodies/{body_a_pk}/assignments",
            json=_assignment_payload(
                _fresh_position(client, nss_wide_headers), holder["person_pk"], holder["sangha_sevi_pk"],
                effective_from=future_start,
            ),
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text
        assignment_pk = r.json()["body_member_assignment_pk"]

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


# ═══════════════════════════════════════════════════════════════════════
# Endpoint authentication / permission matrix (all 56 governance endpoints)
# ═══════════════════════════════════════════════════════════════════════
#
# Path ids are the nil UUID: the auth dependencies run (and raise 401/403)
# before the handler ever looks the record up, so a real row is not needed to
# prove who may call what.

U = FAKE_UUID

# GOVERNANCE_MANAGE-only endpoints (require_permission("GOVERNANCE_MANAGE")).
MANAGE_ENDPOINTS = [
    ("POST", "/body-types", {}),
    ("PATCH", f"/body-types/{U}", {}),
    ("DELETE", f"/body-types/{U}", None),
    ("POST", "/positions", {}),
    ("PATCH", f"/positions/{U}", {}),
    ("DELETE", f"/positions/{U}", None),
    ("GET", f"/bodies/sakha-scope-options?body_type_master_pk={U}", None),
    ("POST", "/bodies", {}),
    ("PATCH", f"/bodies/{U}", {}),
    ("DELETE", f"/bodies/{U}", None),
    ("POST", f"/bodies/{U}/assignments", {}),
    ("POST", f"/assignments/{U}/end", {}),
    ("POST", f"/assignments/{U}/request-removal", {}),
    ("POST", f"/assignments/{U}/approve-removal", {}),
    ("POST", f"/assignments/{U}/reject-removal", {}),
    ("POST", f"/bodies/{U}/acting-assignments", {}),
    ("POST", f"/acting-assignments/{U}/end", {}),
    ("POST", "/elections", {}),
    ("PATCH", f"/elections/{U}/status", {}),
    ("POST", f"/elections/{U}/nominations", {}),
    ("PATCH", f"/nominations/{U}/status", {}),
    ("POST", f"/elections/{U}/votes", {}),
    ("POST", f"/elections/{U}/votes/reset", {}),
    ("POST", f"/elections/{U}/results", {}),
    ("POST", f"/results/{U}/apply", {}),
]

# GOVERNANCE_VIEW-or-MANAGE reads, with the status a VIEW-only NSS-wide admin
# gets for the nil UUID (list endpoints answer 200, id endpoints 404).
VIEW_ENDPOINTS = [
    ("/body-types", 200),
    ("/positions", 200),
    ("/bodies", 200),
    (f"/bodies/{U}", 404),
    (f"/bodies/{U}/assignments", 404),
    (f"/bodies/{U}/allowed-positions", 404),
    (f"/bodies/{U}/inherited-positions", 404),
    ("/advisory-board/missing-nominations", 200),
    ("/advisory-board/dashboard", 200),
    ("/mukhya-pujaka", 200),
    (f"/bodies/{U}/acting-assignments", 404),
    ("/elections", 200),
    (f"/elections/{U}", 404),
    (f"/elections/{U}/nominations", 404),
    (f"/elections/{U}/tally", 404),
    (f"/elections/{U}/results", 404),
]

# Login-only endpoints (get_current_user, no governance permission). Payloads
# are well-formed so the request reaches the handler; the nil UUIDs then 404.
LOGIN_ONLY_ENDPOINTS = [
    ("GET", "/public/national-bodies", None, 200),
    ("GET", "/public/my-sakha-bodies", None, 200),
    ("GET", "/public/sakha-office-bearers", None, 200),
    ("GET", "/me/positions", None, 200),
    ("GET", "/me/acting-delegations", None, 200),
    ("GET", "/me/pending-acting-approvals", None, 200),
    ("GET", "/me/parichalak-status", None, 200),
    ("GET", "/elections/open-for-voting", None, 200),
    ("POST", f"/assignments/{U}/resign",
     {"effective_to": "2026-01-01", "resignation_reason": "Nil."}, 404),
    ("POST", f"/acting-assignments/{U}/approve", {}, 404),
    ("POST", f"/acting-assignments/{U}/reject", {}, 404),
    ("POST", "/me/acting-delegations",
     {"body_master_pk": U, "position_master_pk": U, "person_pk": U, "effective_from": "2026-01-01"}, 404),
    ("POST", "/me/acting-delegations/batch",
     {"items": [{"body_master_pk": U, "position_master_pk": U, "person_pk": U}],
      "effective_from": "2026-01-01"}, 404),
    ("POST", f"/me/acting-delegations/{U}/end", {"effective_to": "2026-01-01"}, 404),
    ("POST", f"/elections/{U}/votes/self", {"election_nomination_pk": U}, 404),
]


def _call(client, method, path, headers=None, payload=None):
    kwargs = {} if payload is None else {"json": payload}
    return client.request(method, f"{BASE}{path}", headers=headers, **kwargs)


def _endpoint_id(*parts) -> str:
    return " ".join(str(p) for p in parts[:2]).replace(U, "{id}")


ALL_ENDPOINTS = (
    [(m, p, body) for m, p, body in MANAGE_ENDPOINTS]
    + [("GET", p, None) for p, _ in VIEW_ENDPOINTS]
    + [(m, p, body) for m, p, body, _ in LOGIN_ONLY_ENDPOINTS]
)


def test_endpoint_matrix_covers_all_fifty_six_governance_routes():
    """Guard: a new governance route must be added to the matrix above."""
    from api.routers.governance import router

    registered = {
        (method, route.path[len("/api/v1/governance"):])
        for route in router.routes
        for method in route.methods
        if method not in ("HEAD", "OPTIONS")
    }
    assert len(registered) == len(ALL_ENDPOINTS) == 56

    def normalise(path):
        # {anything} -> the nil UUID, query string dropped.
        import re
        return re.sub(r"\{[^}]+\}", U, path.split("?")[0])

    covered = {(m, normalise(p)) for m, p, _ in ALL_ENDPOINTS}
    assert {(m, normalise(p)) for m, p in registered} == covered


class TestAuthenticationMatrix:
    @pytest.mark.parametrize(
        "method,path,payload", ALL_ENDPOINTS, ids=[_endpoint_id(m, p) for m, p, _ in ALL_ENDPOINTS],
    )
    def test_anonymous_request_is_rejected(self, anon_client, method, path, payload):
        r = _call(anon_client, method, path, payload=payload)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}: {r.text}"


class TestPermissionMatrix:
    @pytest.mark.parametrize(
        "method,path,payload", MANAGE_ENDPOINTS,
        ids=[_endpoint_id(m, p) for m, p, _ in MANAGE_ENDPOINTS],
    )
    def test_member_without_a_governance_role_cannot_write(
        self, client, someone_else_headers, method, path, payload,
    ):
        r = _call(client, method, path, someone_else_headers, payload)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text}"
        assert "GOVERNANCE_MANAGE" in r.text

    @pytest.mark.parametrize(
        "path,_expected", VIEW_ENDPOINTS, ids=[_endpoint_id("GET", p) for p, _ in VIEW_ENDPOINTS],
    )
    def test_member_without_a_governance_role_cannot_read(
        self, client, someone_else_headers, path, _expected,
    ):
        r = _call(client, "GET", path, someone_else_headers)
        assert r.status_code == 403, f"GET {path} -> {r.status_code}: {r.text}"
        assert "GOVERNANCE_VIEW" in r.text

    @pytest.mark.parametrize(
        "method,path,payload", MANAGE_ENDPOINTS,
        ids=[_endpoint_id(m, p) for m, p, _ in MANAGE_ENDPOINTS],
    )
    def test_view_only_auditor_cannot_write(self, client, auditor_headers, method, path, payload):
        r = _call(client, method, path, auditor_headers, payload)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text}"
        assert "GOVERNANCE_MANAGE" in r.text

    @pytest.mark.parametrize(
        "path,expected", VIEW_ENDPOINTS, ids=[_endpoint_id("GET", p) for p, _ in VIEW_ENDPOINTS],
    )
    def test_view_only_auditor_can_read(self, client, auditor_headers, path, expected):
        r = _call(client, "GET", path, auditor_headers)
        assert r.status_code == expected, f"GET {path} -> {r.status_code}: {r.text}"

    @pytest.mark.parametrize(
        "method,path,payload,expected", LOGIN_ONLY_ENDPOINTS,
        ids=[_endpoint_id(m, p) for m, p, _, _ in LOGIN_ONLY_ENDPOINTS],
    )
    def test_login_only_endpoints_need_no_governance_permission(
        self, client, someone_else_headers, method, path, payload, expected,
    ):
        """A plain member (no role, no scope) reaches every self-service route."""
        r = _call(client, method, path, someone_else_headers, payload)
        assert r.status_code == expected, f"{method} {path} -> {r.status_code}: {r.text}"


# ═══════════════════════════════════════════════════════════════════════
# Organization-scope matrix: a Sakha-scoped admin vs FOREIGN and NSS-WIDE records
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def scoped_admin_b(write_conn, zone_b_org_pk):
    """GOVERNANCE_MANAGE scoped strictly to zone_b_org_pk (the OTHER Sakha)."""
    data = _create_person_with_sevi(write_conn, "GovSecScopedB", organization_pk=zone_b_org_pk)
    uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], SCOPED_B_PASSWORD)
    _grant_role(write_conn, uap, "NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=zone_b_org_pk)
    return data


@pytest.fixture(scope="module")
def scoped_b_headers(client, scoped_admin_b):
    return _login_headers(client, scoped_admin_b["sangha_sevi_id"], SCOPED_B_PASSWORD)


@pytest.fixture(scope="module")
def auditor_headers(client, write_conn, zone_a_org_pk):
    """NSS-wide AUDITOR: holds GOVERNANCE_VIEW but not GOVERNANCE_MANAGE."""
    data = _create_person_with_sevi(write_conn, "GovSecAuditor", organization_pk=zone_a_org_pk)
    uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], AUDITOR_PASSWORD)
    _grant_role(write_conn, uap, "NSS_ERP_AUDITOR", scope_level="NSS-WIDE", organization_pk=None)
    return _login_headers(client, data["sangha_sevi_id"], AUDITOR_PASSWORD)


@pytest.fixture(scope="module")
def zone_a_member(write_conn, zone_a_org_pk):
    return _create_person_with_sevi(write_conn, "GovSecMemberA", organization_pk=zone_a_org_pk)


@pytest.fixture(scope="module")
def zone_b_member(write_conn, zone_b_org_pk):
    return _create_person_with_sevi(write_conn, "GovSecMemberB", organization_pk=zone_b_org_pk)


@pytest.fixture(scope="module")
def real_positions(write_conn):
    cur = write_conn.cursor()
    cur.execute("SELECT position_code, position_master_pk FROM nss.position_master")
    return {code: str(pk) for code, pk in cur.fetchall()}


@pytest.fixture(scope="module")
def real_body_type_pks(write_conn):
    cur = write_conn.cursor()
    cur.execute("SELECT body_type_code, body_type_master_pk FROM nss.body_type_master")
    return {code: str(pk) for code, pk in cur.fetchall()}


def _seat_new_member(client, headers, write_conn, body_pk, org_pk) -> str:
    """Seat a brand-new member of `org_pk` in `body_pk` on a brand-new position."""
    member = _create_person_with_sevi(write_conn, "GovSecSeat", organization_pk=org_pk)
    r = client.post(
        f"{BASE}/bodies/{body_pk}/assignments",
        json=_assignment_payload(_fresh_position(client, headers), member["person_pk"], member["sangha_sevi_pk"]),
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_member_assignment_pk"]


def _new_election(client, headers, body_pk) -> str:
    r = client.post(
        f"{BASE}/elections",
        json={
            "election_code": f"SEC_EL_{uuid4().hex[:10].upper()}",
            "body_master_pk": body_pk,
            "election_name": "Sec Election",
            "election_date": "2026-11-01",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["election_pk"]


@pytest.fixture(scope="module")
def election_a_pk(client, nss_wide_headers, body_a_pk):
    return _new_election(client, nss_wide_headers, body_a_pk)


@pytest.fixture(scope="module")
def election_b_pk(client, nss_wide_headers, body_b_pk):
    return _new_election(client, nss_wide_headers, body_b_pk)


@pytest.fixture(scope="module")
def election_nss_pk(client, nss_wide_headers, body_nss_wide_pk):
    return _new_election(client, nss_wide_headers, body_nss_wide_pk)


class TestBodyScope:
    def test_foreign_body_detail_is_forbidden(self, client, scoped_a_headers, body_b_pk):
        r = client.get(f"{BASE}/bodies/{body_b_pk}", headers=scoped_a_headers)
        assert r.status_code == 403
        assert "This governance body is outside your admin scope." in r.text

    def test_own_and_nss_wide_bodies_are_visible(self, client, scoped_a_headers, body_a_pk, body_nss_wide_pk):
        assert client.get(f"{BASE}/bodies/{body_a_pk}", headers=scoped_a_headers).status_code == 200
        assert client.get(f"{BASE}/bodies/{body_nss_wide_pk}", headers=scoped_a_headers).status_code == 200

    def test_list_is_filtered_to_visible_bodies(
        self, client, scoped_a_headers, body_a_pk, body_b_pk, body_nss_wide_pk,
    ):
        r = client.get(
            f"{BASE}/bodies", params={"search": "SEC_BODY_", "page_size": 100}, headers=scoped_a_headers,
        )
        assert r.status_code == 200, r.text
        pks = {b["body_master_pk"] for b in r.json()["items"]}
        assert {body_a_pk, body_nss_wide_pk} <= pks
        assert body_b_pk not in pks

    def test_foreign_and_nss_wide_bodies_cannot_be_edited_or_deactivated(
        self, client, scoped_a_headers, body_b_pk, body_nss_wide_pk,
    ):
        for pk in (body_b_pk, body_nss_wide_pk):
            patch = client.patch(f"{BASE}/bodies/{pk}", json={"description": "hijack"}, headers=scoped_a_headers)
            assert patch.status_code == 403, patch.text
            delete = client.delete(f"{BASE}/bodies/{pk}", headers=scoped_a_headers)
            assert delete.status_code == 403, delete.text

    def test_own_body_can_be_edited(self, client, scoped_a_headers, body_a_pk):
        r = client.patch(f"{BASE}/bodies/{body_a_pk}", json={"description": "Edited by its own Sakha."},
                         headers=scoped_a_headers)
        assert r.status_code == 200, r.text
        assert r.json()["description"] == "Edited by its own Sakha."

    def test_cannot_create_a_body_in_a_foreign_org(self, client, scoped_a_headers, body_type_pk, zone_b_org_pk):
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"SEC_FOREIGN_{uuid4().hex[:8].upper()}",
                "body_name": "Foreign", "organization_pk": zone_b_org_pk, "effective_from": "2026-01-01",
            },
            headers=scoped_a_headers,
        )
        assert r.status_code == 403
        assert "You can only create governance bodies within your admin scope." in r.text

    def test_can_create_and_deactivate_a_body_in_its_own_org(
        self, client, scoped_a_headers, body_type_pk, zone_a_org_pk,
    ):
        r = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": body_type_pk, "body_code": f"SEC_OWN_{uuid4().hex[:8].upper()}",
                "body_name": "Own", "organization_pk": zone_a_org_pk, "effective_from": "2026-01-01",
            },
            headers=scoped_a_headers,
        )
        assert r.status_code == 201, r.text
        assert client.delete(f"{BASE}/bodies/{r.json()['body_master_pk']}", headers=scoped_a_headers).status_code == 200

    def test_catalogs_are_nss_wide_only(self, client, scoped_a_headers, body_type_pk, position_pk):
        """Body types and positions are NSS-wide catalogues (organization_pk NULL)."""
        calls = [
            ("POST", "/body-types", {"body_type_code": "SEC_SCOPED", "body_type_name": "x"}),
            ("PATCH", f"/body-types/{body_type_pk}", {"body_type_name": "x"}),
            ("DELETE", f"/body-types/{body_type_pk}", None),
            ("POST", "/positions", {"position_code": "SEC_SCOPED", "position_name": "x"}),
            ("PATCH", f"/positions/{position_pk}", {"position_name": "x"}),
            ("DELETE", f"/positions/{position_pk}", None),
        ]
        for method, path, payload in calls:
            r = _call(client, method, path, scoped_a_headers, payload)
            assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text}"
            assert "Only an NSS-wide admin may" in r.text


class TestBodySubresourceScope:
    @pytest.mark.parametrize("suffix", ["assignments", "allowed-positions", "inherited-positions", "acting-assignments"])
    def test_foreign_body_subresources_are_forbidden(self, client, scoped_a_headers, body_b_pk, suffix):
        r = client.get(f"{BASE}/bodies/{body_b_pk}/{suffix}", headers=scoped_a_headers)
        assert r.status_code == 403, r.text
        assert "This governance body is outside your admin scope." in r.text

    @pytest.mark.parametrize("suffix", ["assignments", "allowed-positions", "inherited-positions", "acting-assignments"])
    def test_own_and_nss_wide_body_subresources_are_readable(
        self, client, scoped_a_headers, body_a_pk, body_nss_wide_pk, suffix,
    ):
        for pk in (body_a_pk, body_nss_wide_pk):
            r = client.get(f"{BASE}/bodies/{pk}/{suffix}", headers=scoped_a_headers)
            assert r.status_code == 200, r.text

    def test_sakha_scope_options_lock_a_sakha_admin_to_their_own_sakha(
        self, client, scoped_a_headers, zone_a_org_pk, body_type_pk,
    ):
        r = client.get(
            f"{BASE}/bodies/sakha-scope-options", params={"body_type_master_pk": body_type_pk},
            headers=scoped_a_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["mode"] == "locked"
        assert r.json()["auto_select_pk"] == zone_a_org_pk

    def test_sakha_scope_options_auto_selects_the_only_sakha_without_a_body(
        self, client, write_conn, nss_wide_headers, zone_a_org_pk, zone_b_org_pk,
    ):
        """
        An admin scoped to TWO Sakhas: while both lack a body of the type the
        picker is a free "choose"; once one has one, the other is auto-selected
        and the picker locks.
        """
        data = _create_person_with_sevi(write_conn, "GovSecTwoSakha", organization_pk=zone_a_org_pk)
        uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], TWO_SAKHA_PASSWORD)
        _grant_role(write_conn, uap, "NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=zone_a_org_pk)
        _grant_role(write_conn, uap, "NSS_ERP_AUDITOR", scope_level="SAKHA", organization_pk=zone_b_org_pk)
        headers = _login_headers(client, data["sangha_sevi_id"], TWO_SAKHA_PASSWORD)

        # A body type no Sakha has a body of yet.
        type_r = client.post(
            f"{BASE}/body-types",
            json={"body_type_code": f"SEC_PICKER_{uuid4().hex[:8].upper()}", "body_type_name": "Picker Type"},
            headers=nss_wide_headers,
        )
        assert type_r.status_code == 201, type_r.text
        type_pk = type_r.json()["body_type_master_pk"]

        def options():
            r = client.get(
                f"{BASE}/bodies/sakha-scope-options", params={"body_type_master_pk": type_pk}, headers=headers,
            )
            assert r.status_code == 200, r.text
            return r.json()

        free = options()
        assert free["mode"] == "choose"
        assert free["auto_select_pk"] is None
        assert {s["organization_pk"] for s in free["sakhas"]} == {zone_a_org_pk, zone_b_org_pk}

        created = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": type_pk, "body_code": f"SEC_PICKER_BODY_{uuid4().hex[:8].upper()}",
                "body_name": "Picker Body", "organization_pk": zone_a_org_pk, "effective_from": "2026-01-01",
            },
            headers=nss_wide_headers,
        )
        assert created.status_code == 201, created.text
        locked = options()
        assert locked["mode"] == "locked"
        assert locked["auto_select_pk"] == zone_b_org_pk


class TestAssignmentAuthority:
    """end / request-removal / approve-removal / reject-removal across scopes."""

    def test_ending_a_foreign_seat_is_forbidden(
        self, client, write_conn, nss_wide_headers, scoped_a_headers, body_b_pk, zone_b_org_pk,
    ):
        pk = _seat_new_member(client, nss_wide_headers, write_conn, body_b_pk, zone_b_org_pk)
        r = client.post(f"{BASE}/assignments/{pk}/end", json={"effective_to": "2026-02-01"}, headers=scoped_a_headers)
        assert r.status_code == 403, r.text
        assert "You can only end body member assignments within your admin scope." in r.text

    def test_in_scope_end_is_redirected_to_request_removal_for_everyone(
        self, client, write_conn, nss_wide_headers, scoped_a_headers, body_a_pk, zone_a_org_pk,
    ):
        """Even the super-admin and the owning Sakha admin cannot end an ordinary seat directly."""
        pk = _seat_new_member(client, nss_wide_headers, write_conn, body_a_pk, zone_a_org_pk)
        for headers in (scoped_a_headers, nss_wide_headers):
            r = client.post(f"{BASE}/assignments/{pk}/end", json={"effective_to": "2026-02-01"}, headers=headers)
            assert r.status_code == 409, r.text
            assert "request-removal" in r.json()["detail"]

    def test_requesting_removal_of_a_foreign_seat_is_forbidden(
        self, client, write_conn, nss_wide_headers, scoped_a_headers, body_b_pk, zone_b_org_pk,
    ):
        pk = _seat_new_member(client, nss_wide_headers, write_conn, body_b_pk, zone_b_org_pk)
        r = client.post(
            f"{BASE}/assignments/{pk}/request-removal",
            json={"reason": "Not ours.", "gb_resolution_reference": "GB/1"}, headers=scoped_a_headers,
        )
        assert r.status_code == 403, r.text
        assert "own admin or one of its own office bearers" in r.text

    def test_owning_sakha_admin_may_request_but_nobody_without_a_seat_may_decide(
        self, client, write_conn, nss_wide_headers, scoped_a_headers, body_a_pk, zone_a_org_pk,
    ):
        pk = _seat_new_member(client, nss_wide_headers, write_conn, body_a_pk, zone_a_org_pk)
        requested = client.post(
            f"{BASE}/assignments/{pk}/request-removal",
            json={"reason": "Inactive.", "gb_resolution_reference": "GB/2026/7"}, headers=scoped_a_headers,
        )
        assert requested.status_code == 200, requested.text
        assert requested.json()["assignment_status"] == "PENDING_REMOVAL"

        # Approval/rejection belong to the BODY'S OWN President — an admin
        # (scoped OR the NSS_ERP_ADMIN super-admin) with no seat has no override.
        for headers in (scoped_a_headers, nss_wide_headers):
            for action in ("approve-removal", "reject-removal"):
                r = client.post(
                    f"{BASE}/assignments/{pk}/{action}", json={"effective_to": "2026-06-01"}, headers=headers,
                )
                assert r.status_code == 403, f"{action}: {r.text}"
                assert "sitting President" in r.json()["detail"]


class TestActingScope:
    def _acting_payload(self, client, headers, person):
        return {
            "position_master_pk": _fresh_position(client, headers),
            "person_pk": person["person_pk"], "effective_from": "2026-05-01",
        }

    def test_acting_cover_only_within_own_org(
        self, client, nss_wide_headers, scoped_a_headers, body_a_pk, body_b_pk, body_nss_wide_pk, zone_a_member,
    ):
        for foreign in (body_b_pk, body_nss_wide_pk):
            r = client.post(
                f"{BASE}/bodies/{foreign}/acting-assignments",
                json=self._acting_payload(client, nss_wide_headers, zone_a_member), headers=scoped_a_headers,
            )
            assert r.status_code == 403, r.text
        own = client.post(
            f"{BASE}/bodies/{body_a_pk}/acting-assignments",
            json=self._acting_payload(client, nss_wide_headers, zone_a_member), headers=scoped_a_headers,
        )
        assert own.status_code == 201, own.text
        assert own.json()["acting_status"] == "PENDING_APPROVAL"

    def test_ending_acting_cover_follows_the_same_scope(
        self, client, nss_wide_headers, scoped_a_headers, body_a_pk, body_b_pk, zone_a_member, zone_b_member,
    ):
        foreign = client.post(
            f"{BASE}/bodies/{body_b_pk}/acting-assignments",
            json=self._acting_payload(client, nss_wide_headers, zone_b_member), headers=nss_wide_headers,
        ).json()["acting_position_assignment_pk"]
        refused = client.post(
            f"{BASE}/acting-assignments/{foreign}/end", json={"effective_to": "2026-06-01"}, headers=scoped_a_headers,
        )
        assert refused.status_code == 403, refused.text

        own = client.post(
            f"{BASE}/bodies/{body_a_pk}/acting-assignments",
            json=self._acting_payload(client, nss_wide_headers, zone_a_member), headers=nss_wide_headers,
        ).json()["acting_position_assignment_pk"]
        ended = client.post(
            f"{BASE}/acting-assignments/{own}/end", json={"effective_to": "2026-06-01"}, headers=scoped_a_headers,
        )
        assert ended.status_code == 200, ended.text
        assert ended.json()["acting_status"] == "ENDED"


class TestElectionScope:
    def test_election_detail_visibility(self, client, scoped_a_headers, election_a_pk, election_b_pk, election_nss_pk):
        assert client.get(f"{BASE}/elections/{election_a_pk}", headers=scoped_a_headers).status_code == 200
        assert client.get(f"{BASE}/elections/{election_nss_pk}", headers=scoped_a_headers).status_code == 200
        r = client.get(f"{BASE}/elections/{election_b_pk}", headers=scoped_a_headers)
        assert r.status_code == 403
        assert "This election is outside your admin scope." in r.text

    def test_election_list_is_filtered(self, client, scoped_a_headers, election_a_pk, election_b_pk, election_nss_pk):
        r = client.get(
            f"{BASE}/elections", params={"search": "SEC_EL_", "page_size": 500}, headers=scoped_a_headers,
        )
        assert r.status_code == 200, r.text
        pks = {e["election_pk"] for e in r.json()["items"]}
        assert {election_a_pk, election_nss_pk} <= pks
        assert election_b_pk not in pks

    @pytest.mark.parametrize("suffix", ["nominations", "tally", "results"])
    def test_foreign_election_subresources_are_forbidden(self, client, scoped_a_headers, election_b_pk, suffix):
        r = client.get(f"{BASE}/elections/{election_b_pk}/{suffix}", headers=scoped_a_headers)
        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("suffix", ["nominations", "tally", "results"])
    def test_own_and_nss_wide_election_subresources_are_readable(
        self, client, scoped_a_headers, election_a_pk, election_nss_pk, suffix,
    ):
        for pk in (election_a_pk, election_nss_pk):
            assert client.get(f"{BASE}/elections/{pk}/{suffix}", headers=scoped_a_headers).status_code == 200

    def test_writes_on_foreign_and_nss_wide_elections_are_forbidden(
        self, client, scoped_a_headers, election_b_pk, election_nss_pk, position_pk, zone_a_member,
    ):
        for election in (election_b_pk, election_nss_pk):
            calls = [
                ("POST", f"/elections/{election}/nominations",
                 {"position_master_pk": position_pk, "candidate_person_pk": zone_a_member["person_pk"]}),
                ("PATCH", f"/elections/{election}/status", {"election_status": "NOMINATION"}),
                ("POST", f"/elections/{election}/votes",
                 {"election_nomination_pk": FAKE_UUID, "voter_person_pk": zone_a_member["person_pk"]}),
                ("POST", f"/elections/{election}/votes/reset",
                 {"reset_mode": "PRESIDENT_UNILATERAL", "reason": "Not allowed."}),
                ("POST", f"/elections/{election}/results", {"position_master_pk": position_pk}),
            ]
            for method, path, payload in calls:
                r = _call(client, method, path, scoped_a_headers, payload)
                assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text}"

    def test_creating_an_election_follows_the_body_scope(
        self, client, scoped_a_headers, body_a_pk, body_b_pk, body_nss_wide_pk,
    ):
        def payload(body_pk):
            return {
                "election_code": f"SEC_EL_{uuid4().hex[:10].upper()}", "body_master_pk": body_pk,
                "election_name": "Scoped create", "election_date": "2026-11-01",
            }
        for foreign in (body_b_pk, body_nss_wide_pk):
            r = client.post(f"{BASE}/elections", json=payload(foreign), headers=scoped_a_headers)
            assert r.status_code == 403, r.text
        own = client.post(f"{BASE}/elections", json=payload(body_a_pk), headers=scoped_a_headers)
        assert own.status_code == 201, own.text
        assert own.json()["organization_pk"] is not None

    def test_owning_sakha_admin_runs_its_own_election(
        self, client, scoped_a_headers, election_a_pk, position_pk, zone_a_member,
    ):
        advanced = client.patch(
            f"{BASE}/elections/{election_a_pk}/status",
            json={"election_status": "NOMINATION"}, headers=scoped_a_headers,
        )
        assert advanced.status_code == 200, advanced.text
        nom = client.post(
            f"{BASE}/elections/{election_a_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": zone_a_member["person_pk"]},
            headers=scoped_a_headers,
        )
        assert nom.status_code == 201, nom.text
        accepted = client.patch(
            f"{BASE}/nominations/{nom.json()['election_nomination_pk']}/status",
            json={"nomination_status": "ACCEPTED"}, headers=scoped_a_headers,
        )
        assert accepted.status_code == 200, accepted.text

    def test_foreign_nomination_status_is_forbidden(
        self, client, nss_wide_headers, scoped_a_headers, election_b_pk, position_pk, zone_b_member,
    ):
        client.patch(
            f"{BASE}/elections/{election_b_pk}/status",
            json={"election_status": "NOMINATION"}, headers=nss_wide_headers,
        )
        nom = client.post(
            f"{BASE}/elections/{election_b_pk}/nominations",
            json={"position_master_pk": position_pk, "candidate_person_pk": zone_b_member["person_pk"]},
            headers=nss_wide_headers,
        )
        assert nom.status_code == 201, nom.text
        r = client.patch(
            f"{BASE}/nominations/{nom.json()['election_nomination_pk']}/status",
            json={"nomination_status": "ACCEPTED"}, headers=scoped_a_headers,
        )
        assert r.status_code == 403, r.text

    def test_applying_a_foreign_result_is_forbidden(
        self, client, write_conn, scoped_a_headers, election_b_pk, position_pk, zone_b_member,
    ):
        cur = write_conn.cursor()
        cur.execute(
            """
            INSERT INTO nss.election_result (election_pk, position_master_pk, winner_person_pk, result_status)
            VALUES (%s, %s, %s, 'DECLARED') RETURNING election_result_pk
            """,
            (election_b_pk, position_pk, zone_b_member["person_pk"]),
        )
        result_pk = str(cur.fetchone()[0])
        r = client.post(f"{BASE}/results/{result_pk}/apply", json={}, headers=scoped_a_headers)
        assert r.status_code == 403, r.text
        assert "You can only apply election results within your admin scope." in r.text


# ═══════════════════════════════════════════════════════════════════════
# Advisory Board — the Sakha-nominated seat (GOV-BR item #18)
# ═══════════════════════════════════════════════════════════════════════
#
# The Advisory Board is NSS-wide, but each Sakha's own general body nominates
# (and alone may withdraw) its single MEMBER representative. A Kendra / NSS-wide
# admin therefore may not end that seat directly; the platform super-admin may
# nominate as break-glass but must route a removal through request-removal.

@pytest.fixture(scope="module")
def advisory_board_pk(client, nss_wide_headers, real_body_type_pks):
    """
    A REAL-type Advisory Board with the earliest effective_from, so
    /advisory-board/missing-nominations (which reads the earliest active board)
    resolves to THIS one rather than the seeded board.
    """
    if "ADVISORY_BOARD" not in real_body_type_pks:
        pytest.skip("ADVISORY_BOARD body type is not seeded.")
    r = client.post(
        f"{BASE}/bodies",
        json={
            "body_type_master_pk": real_body_type_pks["ADVISORY_BOARD"],
            "body_code": f"SEC_ADVISORY_{uuid4().hex[:8].upper()}",
            "body_name": "Sec Advisory Board",
            "effective_from": "1900-01-01",
        },
        headers=nss_wide_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["body_master_pk"]


class TestAdvisoryBoardAuthority:
    @pytest.fixture(scope="class")
    @classmethod
    def rep_a(cls, write_conn, zone_a_org_pk):
        return _create_person_with_sevi(write_conn, "GovSecRepA", organization_pk=zone_a_org_pk)

    @pytest.fixture(scope="class")
    @classmethod
    def rep_a_rival(cls, write_conn, zone_a_org_pk):
        return _create_person_with_sevi(write_conn, "GovSecRepARival", organization_pk=zone_a_org_pk)

    @pytest.fixture(scope="class")
    @classmethod
    def rep_b(cls, write_conn, zone_b_org_pk):
        return _create_person_with_sevi(write_conn, "GovSecRepB", organization_pk=zone_b_org_pk)

    @classmethod
    def _nominate(cls, client, headers, board_pk, position_pk, member):
        return client.post(
            f"{BASE}/bodies/{board_pk}/assignments",
            json=_assignment_payload(position_pk, member["person_pk"], member["sangha_sevi_pk"]),
            headers=headers,
        )

    @pytest.fixture(scope="class")
    @classmethod
    def nominee_a_assignment(cls, client, scoped_a_headers, advisory_board_pk, real_positions, rep_a):
        r = cls._nominate(client, scoped_a_headers, advisory_board_pk, real_positions["MEMBER"], rep_a)
        assert r.status_code == 201, r.text
        return r.json()["body_member_assignment_pk"]

    @pytest.fixture(scope="class")
    @classmethod
    def nominee_b_assignment(cls, client, nss_wide_headers, advisory_board_pk, real_positions, rep_b):
        r = cls._nominate(client, nss_wide_headers, advisory_board_pk, real_positions["MEMBER"], rep_b)
        assert r.status_code == 201, r.text
        return r.json()["body_member_assignment_pk"]

    def test_a_sakha_admin_cannot_nominate_for_another_sakha(
        self, client, scoped_a_headers, advisory_board_pk, real_positions, rep_b,
    ):
        r = self._nominate(client, scoped_a_headers, advisory_board_pk, real_positions["MEMBER"], rep_b)
        assert r.status_code == 403, r.text
        assert "own admin may nominate an Advisory Board representative" in r.json()["detail"]

    def test_a_sakha_has_at_most_one_representative(
        self, client, scoped_a_headers, advisory_board_pk, real_positions, rep_a_rival, nominee_a_assignment,
    ):
        r = self._nominate(client, scoped_a_headers, advisory_board_pk, real_positions["MEMBER"], rep_a_rival)
        assert r.status_code == 409, r.text
        assert "already represented on the Advisory Board" in r.json()["detail"]

    def test_super_admin_cannot_end_a_nomination_directly(self, client, nss_wide_headers, nominee_b_assignment):
        """Break-glass may nominate, but a removal must go through request-removal (President approval)."""
        r = client.post(
            f"{BASE}/assignments/{nominee_b_assignment}/end",
            json={"effective_to": "2026-02-01"}, headers=nss_wide_headers,
        )
        assert r.status_code == 409, r.text
        assert "request-removal" in r.json()["detail"]

    def test_another_sakhas_admin_cannot_withdraw_a_nomination(
        self, client, scoped_b_headers, nominee_a_assignment,
    ):
        r = client.post(
            f"{BASE}/assignments/{nominee_a_assignment}/end",
            json={"effective_to": "2026-02-01"}, headers=scoped_b_headers,
        )
        assert r.status_code == 403, r.text
        assert "own admin may withdraw this Advisory Board nomination" in r.json()["detail"]

    def test_officer_must_be_chosen_from_among_the_members(
        self, client, nss_wide_headers, advisory_board_pk, real_positions, rep_a_rival,
    ):
        r = self._nominate(client, nss_wide_headers, advisory_board_pk, real_positions["PRESIDENT"], rep_a_rival)
        assert r.status_code == 422, r.text
        assert "chosen from among its members" in r.json()["detail"]

    def test_promoting_a_representative_converts_the_seat_in_place(
        self, client, nss_wide_headers, advisory_board_pk, real_positions, rep_b, nominee_b_assignment,
    ):
        r = self._nominate(client, nss_wide_headers, advisory_board_pk, real_positions["PRESIDENT"], rep_b)
        assert r.status_code == 201, r.text
        assert r.json()["body_member_assignment_pk"] == nominee_b_assignment
        assert r.json()["position_master_pk"] == real_positions["PRESIDENT"]

    def test_missing_nominations_is_nss_wide_only_and_counts_converted_seats(
        self, client, scoped_a_headers, nss_wide_headers, advisory_board_pk, zone_b_org_pk, nominee_b_assignment,
    ):
        denied = client.get(f"{BASE}/advisory-board/missing-nominations", headers=scoped_a_headers)
        assert denied.status_code == 403, denied.text
        assert "Only an NSS-wide admin may view Advisory Board nomination status" in denied.text

        r = client.get(f"{BASE}/advisory-board/missing-nominations", headers=nss_wide_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        if data["advisory_board_body_master_pk"] != advisory_board_pk:
            pytest.skip("A seeded Advisory Board with an earlier effective_from is being read instead.")
        assert data["total"] == len(data["items"])
        # zone_b's representative now sits as PRESIDENT (a converted MEMBER seat):
        # that Sakha is still represented.
        assert zone_b_org_pk not in {i["organization_pk"] for i in data["items"]}

    def test_allowed_positions_hide_the_sakha_nominated_seat_from_nss_wide_admins(
        self, write_conn, client, nss_wide_headers, scoped_a_headers, advisory_board_pk,
    ):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        """)
        sakha_count = cur.fetchone()[0]

        nss = client.get(f"{BASE}/bodies/{advisory_board_pk}/allowed-positions", headers=nss_wide_headers).json()
        assert "MEMBER" not in {p["position_code"] for p in nss["positions"]}
        assert nss["seat_limit"] == sakha_count
        assert nss["officers_from_members"] is True

        sakha = client.get(f"{BASE}/bodies/{advisory_board_pk}/allowed-positions", headers=scoped_a_headers).json()
        assert "MEMBER" in {p["position_code"] for p in sakha["positions"]}

    def test_a_kendra_governing_body_member_cannot_sit_on_the_advisory_board(
        self, client, write_conn, nss_wide_headers, advisory_board_pk, real_positions, real_body_type_pks,
        zone_a_org_pk,
    ):
        kendra = client.post(
            f"{BASE}/bodies",
            json={
                "body_type_master_pk": real_body_type_pks["KENDRA_GOVERNING_BODY"],
                "body_code": f"SEC_KENDRA_{uuid4().hex[:8].upper()}",
                "body_name": "Sec Kendra GB", "effective_from": "2026-01-01",
            },
            headers=nss_wide_headers,
        )
        assert kendra.status_code == 201, kendra.text
        member = _create_person_with_sevi(write_conn, "GovSecBoth", organization_pk=zone_a_org_pk)
        seated = self._nominate(client, nss_wide_headers, kendra.json()["body_master_pk"], real_positions["MEMBER"], member)
        assert seated.status_code == 201, seated.text

        r = self._nominate(client, nss_wide_headers, advisory_board_pk, real_positions["MEMBER"], member)
        assert r.status_code == 409, r.text
        assert "cannot sit on both the Kendra Governing Body and the Advisory Board" in r.json()["detail"]

    def test_the_owning_sakha_admin_can_withdraw_its_own_nomination(
        self, client, scoped_a_headers, nominee_a_assignment,
    ):
        r = client.post(
            f"{BASE}/assignments/{nominee_a_assignment}/end",
            json={"effective_to": "2026-02-01"}, headers=scoped_a_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["assignment_status"] == "ENDED"
        assert r.json()["effective_to"] == "2026-02-01"

    def test_an_already_ended_nomination_cannot_be_ended_again(
        self, client, scoped_a_headers, nominee_a_assignment,
    ):
        """Runs after the withdrawal above: the terminal ENDED row must not be rewritten."""
        r = client.post(
            f"{BASE}/assignments/{nominee_a_assignment}/end",
            json={"effective_to": "2026-03-01"}, headers=scoped_a_headers,
        )
        assert r.status_code == 409, r.text
        assert "already ENDED" in r.json()["detail"]
