"""
NSS ERP — Tier 5 Administration API tests.

Integration tests for the admin endpoints:
  1. GET    /api/v1/admin/users               — list users
  2. POST   /api/v1/admin/users               — create user
  3. GET    /api/v1/admin/users/{pk}           — user detail
  4. POST   /api/v1/admin/users/{pk}/reset-password — admin reset
  5. PATCH  /api/v1/admin/users/{pk}/status    — status change
  6. DELETE /api/v1/admin/users/{pk}           — soft-delete user
  7. GET    /api/v1/admin/users/{pk}/roles     — list roles
  8. POST   /api/v1/admin/users/{pk}/roles     — assign role
  9. DELETE /api/v1/admin/users/{pk}/roles/{ur_pk} — revoke role
 10. GET    /api/v1/admin/organizations        — list organizations
 11. PATCH  /api/v1/admin/organizations/{pk}   — update org details
 12. POST   /api/v1/admin/persons              — admin create person
 13. POST   /api/v1/admin/organizations        — create organization
 14. PATCH  /api/v1/admin/organizations/{pk}/short-code — update short code
 15. POST   /api/v1/admin/users (create_sangha_sevi) — create user with SS
 16. POST   /api/v1/admin/users/{pk}/roles     — same-role-different-scope
 17. POST   /api/v1/admin/sangha-sevi          — local Sakha number uniqueness

These tests run against local PostgreSQL.
Requires an admin user with ADMIN_USER_MANAGE, ADMIN_USER_VIEW,
ADMIN_ROLE_MANAGE, and PERSON_MANAGE permissions.
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


pytestmark = pytest.mark.integration


# ── Constants ───────────────────────────────────────────────────────────

ADMIN_PASSWORD = "AdminPass1"
TARGET_PASSWORD = "TargetPass1"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_user(write_conn):
    """
    Create an admin user with full admin permissions.

    Assigns NSS_ERP_ADMIN role with NSS-WIDE scope, which grants
    ADMIN_USER_VIEW, ADMIN_USER_MANAGE, ADMIN_ROLE_MANAGE, etc.

    Builds its own person + sangha_sevi rather than scavenging nss.person
    for someone who happens to lack a user_account. The scavenging version
    silently pytest.skip()'d the WHOLE module the moment live data had no
    such person — indistinguishable from passing in the summary line.
    Anything this fixture inserts is rolled back by conftest's write_conn.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    # Reference data: membership type, ACTIVE membership status, an org.
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE'
          AND md.value_code = 'REGULAR' AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    assert row, "MEMBERSHIP_TYPE/REGULAR master data is missing."
    membership_type_pk = row[0]

    # Membership status: the API resolves this via helpers.get_active_status_pk,
    # which reads category STATUS / value ACTIVE — not a MEMBERSHIP_STATUS
    # category (that category does not exist).
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS'
          AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    assert row, "STATUS/ACTIVE master data is missing."
    membership_status_pk = row[0]

    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md
          ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    assert row, "No active SAKHA_SANGHA organization exists."
    organization_pk = row[0]

    # Dedicated person for the admin actor.
    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s)
        RETURNING person_pk
    """, (
        f"TADM{suffix}",
        "TestAdmin",
        suffix,
        f"tadm.{suffix.lower()}@example.test",
    ))
    person_pk = cur.fetchone()[0]

    # Sangha Sevi record — endpoints resolve user.actor_pk through this.
    sangha_sevi_id = f"TSSADM{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk,
            membership_type_master_data_pk,
            membership_status_master_data_pk,
            organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (
        sangha_sevi_id, str(person_pk),
        str(membership_type_pk), str(membership_status_pk),
        str(organization_pk),
    ))

    # Create user_account
    password_hash = hash_password(ADMIN_PASSWORD)
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), password_hash))
    user_account_pk = cur.fetchone()[0]

    # Find NSS_ERP_ADMIN role
    cur.execute(
        "SELECT role_master_pk FROM nss.role_master WHERE role_code = 'NSS_ERP_ADMIN' AND is_active = TRUE"
    )
    role_row = cur.fetchone()
    assert role_row, "NSS_ERP_ADMIN role not found in database."
    role_master_pk = role_row[0]

    # Assign role
    cur.execute("""
        INSERT INTO nss.user_role (user_account_pk, role_master_pk)
        VALUES (%s, %s)
        RETURNING user_role_pk
    """, (str(user_account_pk), str(role_master_pk)))
    user_role_pk = cur.fetchone()[0]

    # Assign NSS-WIDE scope
    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, 'NSS-WIDE', NULL)
    """, (str(user_role_pk),))

    info = {
        "person_pk": person_pk,
        "user_account_pk": user_account_pk,
        "sangha_sevi_id": sangha_sevi_id,
    }

    yield info
    # No manual cleanup needed — conftest SAVEPOINT handles rollback


@pytest.fixture(scope="module")
def admin_tokens(client, admin_user):
    """Login as admin and return the access token."""
    response = client.post("/api/v1/auth/login", json={
        "login_id": admin_user["sangha_sevi_id"],
        "password": ADMIN_PASSWORD,
    })
    assert response.status_code == 200, f"Admin login failed: {response.json()}"
    return response.json()


@pytest.fixture(scope="module")
def admin_headers(admin_tokens):
    """Authorization header for admin requests."""
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}


@pytest.fixture(scope="module")
def gender_pk(write_conn):
    """
    master_data_pk for an active GENDER value.

    Same convention as tests/api/test_registration.py and
    test_claim_approval.py — GENDER is seeded reference data, so it is
    looked up rather than inserted.
    """
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'GENDER'
          AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No GENDER master data found.")
    return str(row[0])


@pytest.fixture(scope="module")
def india_state_district_pks(write_conn):
    """
    India country_pk + an Odisha state_pk/district_pk triple.

    ANCHALIKA_SANGHA/ZILLA_SANGHA/PATHA_CHAKRA require country/state/
    district (ORG-BR-099 narrowing — administrative jurisdiction, even
    though these types still can't carry a physical premises address).
    Shared here so every org-creation test/fixture that needs a throwaway
    Anchalika doesn't repeat this same India/Odisha lookup.
    """
    cur = write_conn.cursor()
    cur.execute(
        "SELECT country_pk FROM nss.country WHERE country_code = 'IN' AND is_active = TRUE LIMIT 1"
    )
    row = cur.fetchone()
    country_pk = str(row[0]) if row else None

    cur.execute(
        "SELECT state_pk FROM nss.state WHERE LOWER(state_name) LIKE '%odisha%' AND is_active = TRUE LIMIT 1"
    )
    row = cur.fetchone()
    state_pk = str(row[0]) if row else None

    district_pk = None
    if state_pk:
        cur.execute(
            "SELECT district_pk FROM nss.district WHERE state_pk = %s AND is_active = TRUE LIMIT 1",
            (state_pk,),
        )
        row = cur.fetchone()
        district_pk = str(row[0]) if row else None

    if not (country_pk and state_pk and district_pk):
        pytest.skip("India/Odisha country/state/district reference data is missing.")

    return {"country_pk": country_pk, "state_pk": state_pk, "district_pk": district_pk}


@pytest.fixture(scope="module")
def target_person_pk(write_conn):
    """
    Create a dedicated throwaway person (guaranteed no user account)
    to be the target of create-user tests.

    Deliberately does NOT scavenge nss.person for an existing person
    without a user_account — in a fully-onboarded DB every person may
    already have one, which silently pytest.skip()s every test in this
    class without failing the run. Insert a fresh row instead so the
    create-user code path is always actually exercised.
    """
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()
    cur.execute(
        """
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s)
        RETURNING person_pk
        """,
        (f"TCU{suffix}", "TestCreateUser", suffix, f"tcu.{suffix.lower()}@example.test"),
    )
    person_pk = cur.fetchone()[0]
    cur.close()
    return person_pk


# ── Track created test users ──────────────────────────────────────────

_created_user_pks = []


# ── List users tests ────────────────────────────────────────────────────

class TestListUsers:
    """GET /api/v1/admin/users"""

    def test_list_users_as_admin(self, client, admin_headers):
        """Admin can list user accounts."""
        response = client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["users"], list)
        assert data["total"] >= 1  # at least the admin user itself

    def test_list_users_pagination(self, client, admin_headers):
        """Pagination parameters work correctly."""
        response = client.get(
            "/api/v1/admin/users?page=1&page_size=5",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["users"]) <= 5

    def test_list_users_search(self, client, admin_headers, admin_user):
        """Search by sangha_sevi_id returns matching users."""
        response = client.get(
            f"/api/v1/admin/users?search={admin_user['sangha_sevi_id']}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1


# ── Sorting tests ──────────────────────────────────────────────────────

class TestListUsersSorting:
    """
    GET /api/v1/admin/users?sort_by=&sort_dir=

    Sorting is server-side because the list is paginated. Sorting the
    fetched page in the browser would reorder 20 rows and present the
    result as an ordering of all of them.
    """

    SORTABLE = [
        "person_id", "sangha_sevi_id", "person_name", "organization_name",
        "local_sakha_erp_id", "darshak_local_number", "account_status",
        "force_password_change", "last_login_at", "created_at",
    ]

    @pytest.mark.parametrize("column", SORTABLE)
    @pytest.mark.parametrize("direction", ["asc", "desc"])
    def test_every_advertised_column_is_accepted(
        self, client, admin_headers, column, direction
    ):
        """
        Each column the UI renders a clickable header for must actually
        sort. A header that 404s or 500s is worse than no header.
        """
        response = client.get(
            f"/api/v1/admin/users?sort_by={column}&sort_dir={direction}",
            headers=admin_headers,
        )
        assert response.status_code == 200, (
            f"sort_by={column} sort_dir={direction} failed: {response.text}"
        )
        assert isinstance(response.json()["users"], list)

    def test_unknown_column_is_a_readable_422(self, client, admin_headers):
        """Not a 500, and the message names the valid columns."""
        response = client.get(
            "/api/v1/admin/users?sort_by=not_a_column",
            headers=admin_headers,
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert isinstance(detail, str)
        assert "not a sortable column" in detail
        assert "person_id" in detail

    def test_sql_injection_via_sort_by_is_rejected(self, client, admin_headers):
        """
        ORDER BY cannot be a bound parameter, so the whitelist is the only
        thing between this query string and arbitrary SQL. A 200 here
        would mean the payload reached the statement.
        """
        for payload in [
            "created_at; DROP TABLE nss.user_account",
            "(SELECT password_hash FROM nss.user_account LIMIT 1)",
            "created_at--",
        ]:
            response = client.get(
                "/api/v1/admin/users",
                params={"sort_by": payload},
                headers=admin_headers,
            )
            assert response.status_code == 422, (
                f"payload reached SQL: {payload!r} -> {response.status_code}"
            )

        # The table must still be there.
        assert client.get("/api/v1/admin/users", headers=admin_headers).status_code == 200

    def test_asc_and_desc_actually_reverse_the_order(self, client, admin_headers):
        """
        The real assertion: the rows come back in opposite orders. A
        clause that parses but does not order would pass every test
        above and still be broken.
        """
        def ids(direction):
            r = client.get(
                f"/api/v1/admin/users?sort_by=person_id&sort_dir={direction}"
                f"&page_size=100",
                headers=admin_headers,
            )
            assert r.status_code == 200, r.text
            return [u["person_id"] for u in r.json()["users"] if u["person_id"]]

        asc = ids("asc")
        desc = ids("desc")
        if len(asc) < 2:
            pytest.skip("Needs at least 2 users with a person_id to compare order.")
        assert asc == list(reversed(desc)), (
            f"asc and desc are not mirror images.\nasc:  {asc}\ndesc: {desc}"
        )

    def test_blank_values_sort_last_in_both_directions(self, client, admin_headers):
        """
        A missing value is not the smallest value — it sinks to the
        bottom either way. Mirrors the frontend rule so the same column
        behaves identically on every screen.
        """
        for direction in ("asc", "desc"):
            r = client.get(
                f"/api/v1/admin/users?sort_by=sangha_sevi_id&sort_dir={direction}"
                f"&page_size=100",
                headers=admin_headers,
            )
            assert r.status_code == 200, r.text
            values = [u["sangha_sevi_id"] for u in r.json()["users"]]
            present = [i for i, v in enumerate(values) if v]
            blank = [i for i, v in enumerate(values) if not v]
            if not present or not blank:
                continue
            assert max(present) < min(blank), (
                f"{direction}: blanks must come last, got {values}"
            )

    def test_default_order_is_unchanged_when_no_sort_requested(
        self, client, admin_headers
    ):
        """
        Adding sorting must not silently change the list's resting
        order — omitting sort_by keeps the previous newest-first default.
        """
        plain = client.get("/api/v1/admin/users?page_size=100", headers=admin_headers)
        explicit = client.get(
            "/api/v1/admin/users?page_size=100&sort_by=&sort_dir=",
            headers=admin_headers,
        )
        assert plain.status_code == 200 and explicit.status_code == 200
        keys = lambda r: [u["user_account_pk"] for u in r.json()["users"]]
        assert keys(plain) == keys(explicit)

        created = [u["created_at"] for u in plain.json()["users"]]
        assert created == sorted(created, reverse=True), (
            f"default should stay newest-first, got {created}"
        )

    def test_sorted_pages_do_not_repeat_or_drop_rows(self, client, admin_headers):
        """
        Without a deterministic tiebreaker, rows with equal sort keys can
        appear on two pages or on none. account_status has many ties, so
        it is the column that exposes this.
        """
        seen = []
        page = 1
        while page <= 10:
            r = client.get(
                f"/api/v1/admin/users?sort_by=account_status&sort_dir=asc"
                f"&page={page}&page_size=2",
                headers=admin_headers,
            )
            assert r.status_code == 200, r.text
            batch = [u["user_account_pk"] for u in r.json()["users"]]
            if not batch:
                break
            seen.extend(batch)
            if len(batch) < 2:
                break
            page += 1

        assert len(seen) == len(set(seen)), (
            f"a row appeared on more than one page: {seen}"
        )


# ── Create user tests ──────────────────────────────────────────────────

class TestCreateUser:
    """POST /api/v1/admin/users"""

    def test_create_user_success(self, client, admin_headers, target_person_pk):
        """Admin can create a user account for an existing person."""
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "person_pk": str(target_person_pk),
                "password": TARGET_PASSWORD,
                "force_password_change": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "user_account_pk" in data
        assert data["person_pk"] == str(target_person_pk)
        assert data["account_status"] == "ACTIVE"
        assert data["force_password_change"] is True
        assert data["is_active"] is True

        # Track for cleanup
        _created_user_pks.append(data["user_account_pk"])

    def test_create_user_duplicate_person_fails(self, client, admin_headers, target_person_pk):
        """Creating a second account for the same person returns 409."""
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "person_pk": str(target_person_pk),
                "password": TARGET_PASSWORD,
            },
        )
        assert response.status_code == 409

    def test_create_user_nonexistent_person(self, client, admin_headers):
        """Creating account for non-existent person returns 404."""
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "person_pk": "00000000-0000-0000-0000-000000000099",
                "password": TARGET_PASSWORD,
            },
        )
        assert response.status_code == 404


# ── User detail tests ──────────────────────────────────────────────────

class TestCheckPersonContact:
    """GET /api/v1/admin/persons/check-contact — advisory duplicate lookup."""

    def _make_person(self, write_conn, *, mobile=None, cc=None, email=None):
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()
        cur.execute("""
            INSERT INTO nss.person
                (person_id, first_name, last_name, country_phone_code, mobile_number, email)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING person_pk, person_id
        """, (f"TCC{suffix}", "TestContact", suffix, cc, mobile, email))
        row = cur.fetchone()
        cur.close()
        return str(row[0]), row[1]

    def test_mobile_conflict_reported(self, client, admin_headers, write_conn):
        mobile = f"9{uuid4().int % 1000000000:09d}"
        _, person_id = self._make_person(write_conn, mobile=mobile, cc="+91")
        resp = client.get(
            "/api/v1/admin/persons/check-contact",
            headers=admin_headers,
            params={"mobile_number": mobile, "country_phone_code": "+91"},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["mobile_conflict"] is not None
        assert data["mobile_conflict"]["person_id"] == person_id
        assert data["email_conflict"] is None

    def test_email_conflict_case_insensitive(self, client, admin_headers, write_conn):
        email = f"dup.{uuid4().hex[:8]}@example.test"
        _, person_id = self._make_person(write_conn, email=email)
        resp = client.get(
            "/api/v1/admin/persons/check-contact",
            headers=admin_headers,
            params={"email": email.upper()},
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["email_conflict"]["person_id"] == person_id

    def test_no_conflict_returns_nulls(self, client, admin_headers):
        resp = client.get(
            "/api/v1/admin/persons/check-contact",
            headers=admin_headers,
            params={"mobile_number": "8123456789", "country_phone_code": "+99",
                    "email": "definitely-not-used@example.test"},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["mobile_conflict"] is None
        assert data["email_conflict"] is None


class TestUserDetail:
    """GET /api/v1/admin/users/{pk}"""

    def test_get_user_detail(self, client, admin_headers, admin_user):
        """Admin can retrieve user detail with roles."""
        response = client.get(
            f"/api/v1/admin/users/{admin_user['user_account_pk']}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_account_pk"] == str(admin_user["user_account_pk"])
        assert "roles" in data
        assert isinstance(data["roles"], list)
        # Admin should have at least the NSS_ERP_ADMIN role
        assert len(data["roles"]) >= 1

    def test_get_user_detail_not_found(self, client, admin_headers):
        """Non-existent user PK returns 404."""
        response = client.get(
            "/api/v1/admin/users/00000000-0000-0000-0000-000000000099",
            headers=admin_headers,
        )
        assert response.status_code == 404


# ── Reset password tests ───────────────────────────────────────────────

class TestResetPassword:
    """POST /api/v1/admin/users/{pk}/reset-password"""

    def test_reset_password_success(self, client, admin_headers):
        """Admin can reset a user's password."""
        # Use the first created test user
        if not _created_user_pks:
            pytest.skip("No test user created to reset.")

        target_pk = _created_user_pks[0]
        response = client.post(
            f"/api/v1/admin/users/{target_pk}/reset-password",
            headers=admin_headers,
            json={
                "new_password": "ResetPass1",
                "force_password_change": True,
            },
        )
        assert response.status_code == 200
        assert "message" in response.json()


# ── Status change tests ────────────────────────────────────────────────

class TestStatusChange:
    """PATCH /api/v1/admin/users/{pk}/status"""

    def test_suspend_user(self, client, admin_headers):
        """Admin can suspend a user account.

        NOTE: "SUSPENDED" is not a valid account_status anywhere in the
        schema (Pydantic pattern or DB CHECK constraint only allow
        ACTIVE/LOCKED/INACTIVE/PENDING_APPROVAL). Using "INACTIVE" here
        as the closest existing equivalent — flag to product owner if a
        distinct SUSPENDED status is actually intended.
        """
        if not _created_user_pks:
            pytest.skip("No test user created.")

        target_pk = _created_user_pks[0]
        response = client.patch(
            f"/api/v1/admin/users/{target_pk}/status",
            headers=admin_headers,
            json={"account_status": "INACTIVE"},
        )
        assert response.status_code == 200

        # Verify status changed
        detail = client.get(
            f"/api/v1/admin/users/{target_pk}",
            headers=admin_headers,
        ).json()
        assert detail["account_status"] == "INACTIVE"

    def test_reactivate_user(self, client, admin_headers):
        """Admin can reactivate a suspended user."""
        if not _created_user_pks:
            pytest.skip("No test user created.")

        target_pk = _created_user_pks[0]
        response = client.patch(
            f"/api/v1/admin/users/{target_pk}/status",
            headers=admin_headers,
            json={"account_status": "ACTIVE"},
        )
        assert response.status_code == 200

    def test_invalid_status_value(self, client, admin_headers):
        """Invalid status value returns 422."""
        if not _created_user_pks:
            pytest.skip("No test user created.")

        target_pk = _created_user_pks[0]
        response = client.patch(
            f"/api/v1/admin/users/{target_pk}/status",
            headers=admin_headers,
            json={"account_status": "BOGUS"},
        )
        assert response.status_code == 422


# ── PENDING_APPROVAL + pending claim guard ─────────────────────────────
#
# update_status() used to auto-generate a sangha_sevi record when activating
# a PENDING_APPROVAL account, duplicating (and diverging from — it never
# created the membership_sakha_affiliation row) claim_approval.py::
# approve_claim()'s own logic. That auto-generation was removed: a Sangha
# Sevi is now created in exactly one place. This class covers the new
# behaviour it was replaced with.

class TestUpdateStatusPendingClaimGuard:
    """PATCH /api/v1/admin/users/{pk}/status — PENDING_APPROVAL + claim guard."""

    @pytest.fixture(scope="class")
    @classmethod
    def sakha_org_and_type(cls, write_conn):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No active SAKHA_SANGHA organization exists.")
        org_pk = str(row[0])

        cur.execute("""
            SELECT md.master_data_pk
            FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR'
              AND md.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("MEMBERSHIP_TYPE/REGULAR master data is missing.")
        return {"org_pk": org_pk, "membership_type_pk": str(row[0])}

    def _make_pending_person_with_claim(self, write_conn, sakha_org_and_type, *, with_claim: bool):
        """Direct-SQL setup (not via /api/v1/register) — this class only
        needs the DB state update_status() reacts to, not the registration
        flow itself (already covered by tests/api/test_registration.py)."""
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()
        cur.execute(
            """
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            RETURNING person_pk
            """,
            (f"TPC{suffix}", "TestPendingClaim", suffix, f"tpc.{suffix.lower()}@example.test"),
        )
        person_pk = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO nss.user_account (person_pk, password_hash, account_status)
            VALUES (%s, 'x', 'PENDING_APPROVAL')
            RETURNING user_account_pk
            """,
            (person_pk,),
        )
        user_account_pk = str(cur.fetchone()[0])

        if with_claim:
            cur.execute(
                """
                INSERT INTO nss.registration_claim (
                    user_account_pk, person_pk, claimed_organization_pk,
                    claimed_membership_type_master_data_pk,
                    claimed_local_sakha_number, claim_status
                ) VALUES (%s, %s, %s, %s, %s, 'PENDING')
                """,
                (user_account_pk, person_pk, sakha_org_and_type["org_pk"],
                 sakha_org_and_type["membership_type_pk"], uuid4().hex[:6]),
            )
        return user_account_pk

    def test_activate_pending_approval_with_pending_claim_blocked(
        self, client, admin_headers, write_conn, sakha_org_and_type
    ):
        """Activating a PENDING_APPROVAL account with an outstanding claim
        must be blocked — the Sangha Sevi is created via Registration
        Approvals, not by flipping the account status directly."""
        user_account_pk = self._make_pending_person_with_claim(
            write_conn, sakha_org_and_type, with_claim=True
        )

        response = client.patch(
            f"/api/v1/admin/users/{user_account_pk}/status",
            headers=admin_headers,
            json={"account_status": "ACTIVE"},
        )
        assert response.status_code == 422
        assert "registration claim" in response.json()["detail"].lower()

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT account_status FROM nss.user_account WHERE user_account_pk = %s",
                (user_account_pk,),
            )
            assert cur.fetchone()[0] == "PENDING_APPROVAL", "Blocked activation must not mutate status."

            cur.execute(
                "SELECT COUNT(*) FROM nss.sangha_sevi WHERE person_pk = "
                "(SELECT person_pk FROM nss.user_account WHERE user_account_pk = %s)",
                (user_account_pk,),
            )
            assert cur.fetchone()[0] == 0, "Blocked activation must not create a sangha_sevi."

    def test_activate_pending_approval_without_claim_or_sevi_is_422(
        self, client, admin_headers, write_conn, sakha_org_and_type
    ):
        """An account whose person has no active Sangha Sevi can never log in,
        so activation is refused even with no outstanding claim."""
        user_account_pk = self._make_pending_person_with_claim(
            write_conn, sakha_org_and_type, with_claim=False
        )
        response = client.patch(
            f"/api/v1/admin/users/{user_account_pk}/status",
            headers=admin_headers,
            json={"account_status": "ACTIVE"},
        )
        assert response.status_code == 422
        assert "sangha sevi" in response.json()["detail"].lower()
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT account_status FROM nss.user_account WHERE user_account_pk = %s",
                (user_account_pk,),
            )
            assert cur.fetchone()[0] == "PENDING_APPROVAL"

    def test_activate_pending_approval_without_claim_succeeds(
        self, client, admin_headers, write_conn, sakha_org_and_type
    ):
        """Activating a PENDING_APPROVAL account with NO claim (e.g. an
        admin-created account) but WITH an existing active Sangha Sevi just
        flips the status — update_status() never invents a sangha_sevi."""
        user_account_pk = self._make_pending_person_with_claim(
            write_conn, sakha_org_and_type, with_claim=False
        )
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT md.master_data_pk
                FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE'
                  AND md.is_active = TRUE
                LIMIT 1
                """
            )
            status_pk = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO nss.sangha_sevi (
                    sangha_sevi_id, person_pk, membership_type_master_data_pk,
                    membership_status_master_data_pk, organization_pk, joining_date
                )
                SELECT %s, ua.person_pk, %s, %s, %s, DATE '2020-04-01'
                FROM nss.user_account ua WHERE ua.user_account_pk = %s
                """,
                (f"TSSPC{uuid4().hex[:10].upper()}",
                 sakha_org_and_type["membership_type_pk"], str(status_pk),
                 sakha_org_and_type["org_pk"], user_account_pk),
            )

        response = client.patch(
            f"/api/v1/admin/users/{user_account_pk}/status",
            headers=admin_headers,
            json={"account_status": "ACTIVE"},
        )
        assert response.status_code == 200, f"Activation failed: {response.json()}"

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT account_status FROM nss.user_account WHERE user_account_pk = %s",
                (user_account_pk,),
            )
            assert cur.fetchone()[0] == "ACTIVE"

            cur.execute(
                "SELECT COUNT(*) FROM nss.sangha_sevi WHERE person_pk = "
                "(SELECT person_pk FROM nss.user_account WHERE user_account_pk = %s)",
                (user_account_pk,),
            )
            assert cur.fetchone()[0] == 1, "update_status() must not create a second sangha_sevi."


# ── Delete user tests ─────────────────────────────────────────────────

class TestDeleteUser:
    """DELETE /api/v1/admin/users/{pk}"""

    def test_delete_user_success(self, client, admin_headers):
        """Admin can soft-delete a user account."""
        if not _created_user_pks:
            pytest.skip("No test user created to delete.")

        target_pk = _created_user_pks[0]
        response = client.delete(
            f"/api/v1/admin/users/{target_pk}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    def test_delete_user_not_found(self, client, admin_headers):
        """Deleting a non-existent user returns 404."""
        response = client.delete(
            "/api/v1/admin/users/00000000-0000-0000-0000-000000000099",
            headers=admin_headers,
        )
        assert response.status_code == 404


# ── Self-protection guards ────────────────────────────────────────────

class TestSelfProtection:
    """A user must not be able to revoke or disable their own access."""

    def test_cannot_change_own_status(self, client, admin_headers, admin_user):
        """Admin cannot change their own account status (422).

        Uses "INACTIVE" (a real status) so the guard being tested is the
        app's own-account check, not an incidental Pydantic pattern
        rejection of an invalid value like "SUSPENDED".
        """
        own_pk = admin_user["user_account_pk"]
        r = client.patch(
            f"/api/v1/admin/users/{own_pk}/status",
            headers=admin_headers,
            json={"account_status": "INACTIVE"},
        )
        assert r.status_code == 422
        assert "own account" in r.json()["detail"].lower()

    def test_cannot_delete_own_account(self, client, admin_headers, admin_user):
        """Admin cannot soft-delete their own account (422)."""
        own_pk = admin_user["user_account_pk"]
        r = client.delete(
            f"/api/v1/admin/users/{own_pk}",
            headers=admin_headers,
        )
        assert r.status_code == 422
        assert "own account" in r.json()["detail"].lower()

    def test_cannot_revoke_own_role(self, client, admin_headers, admin_user):
        """Admin cannot revoke their own role assignment (422).

        This is the guard that would otherwise let an admin strip their
        own access and lock themselves out of the system.
        """
        own_pk = admin_user["user_account_pk"]
        roles = client.get(
            f"/api/v1/admin/users/{own_pk}/roles",
            headers=admin_headers,
        ).json()
        active = [r for r in roles if r.get("is_active", True)]
        if not active:
            pytest.skip("Admin has no active role assignment to revoke.")
        user_role_pk = active[0]["user_role_pk"]
        r = client.delete(
            f"/api/v1/admin/users/{own_pk}/roles/{user_role_pk}",
            headers=admin_headers,
        )
        assert r.status_code == 422
        assert "own role" in r.json()["detail"].lower()


# ── Organization listing tests ────────────────────────────────────────

class TestListOrganizations:
    """GET /api/v1/admin/organizations"""

    def test_list_organizations(self, client, admin_headers):
        """Admin can list organizations."""
        response = client.get(
            "/api/v1/admin/organizations",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "organizations" in data
        assert "total" in data
        assert isinstance(data["organizations"], list)
        assert data["total"] >= 1

    def test_list_organizations_returns_extended_fields(self, client, admin_headers):
        """Organization listing includes phone, email, website fields."""
        response = client.get(
            "/api/v1/admin/organizations?page_size=1",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        if data["organizations"]:
            org = data["organizations"][0]
            # Verify all expected keys exist (values may be null)
            for key in [
                "organization_pk", "organization_code", "organization_name",
                "short_code", "type_code", "type_name",
                "phone_number", "mobile_number", "org_email",
                "org_website_url", "org_youtube_channel_url",
            ]:
                assert key in org, f"Missing key: {key}"

    def test_list_organizations_search(self, client, admin_headers):
        """Search filter works on org name/code."""
        response = client.get(
            "/api/v1/admin/organizations?search=NSS",
            headers=admin_headers,
        )
        assert response.status_code == 200

    def test_list_organizations_pagination(self, client, admin_headers):
        """Pagination parameters are respected."""
        response = client.get(
            "/api/v1/admin/organizations?page=1&page_size=5",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["organizations"]) <= 5

    def test_list_organizations_without_auth_fails(self, client):
        """Listing organizations without auth returns 401."""
        response = client.get("/api/v1/admin/organizations")
        assert response.status_code == 401


# ── Organization editing tests ────────────────────────────────────────

class TestUpdateOrganization:
    """PATCH /api/v1/admin/organizations/{pk}"""

    def _get_first_org_pk(self, client, admin_headers):
        """Helper: get the PK of the first organization."""
        resp = client.get(
            "/api/v1/admin/organizations?page_size=1",
            headers=admin_headers,
        )
        orgs = resp.json().get("organizations", [])
        if not orgs:
            pytest.skip("No organizations in database.")
        return orgs[0]["organization_pk"]

    def test_update_org_name(self, client, admin_headers):
        """Admin can update an organization name."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}",
            headers=admin_headers,
            json={"organization_name": "Test Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "updated_fields" in data
        assert "organization_name" in data["updated_fields"]

    def test_update_org_contact_fields(self, client, admin_headers):
        """Admin can update phone, email, website fields."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}",
            headers=admin_headers,
            json={
                "phone_number": "0674-1234567",
                "org_email": "test@example.org",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "phone_number" in data["updated_fields"]
        assert "org_email" in data["updated_fields"]

    def test_update_org_no_fields_returns_422(self, client, admin_headers):
        """Sending empty body returns 422."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}",
            headers=admin_headers,
            json={},
        )
        assert response.status_code == 422

    def test_update_org_not_found(self, client, admin_headers):
        """Updating a non-existent org returns 404."""
        response = client.patch(
            "/api/v1/admin/organizations/00000000-0000-0000-0000-000000000099",
            headers=admin_headers,
            json={"organization_name": "Ghost Org"},
        )
        assert response.status_code == 404


# ── Admin create person tests ────────────────────────────────────────

_RUN_ID = uuid4().hex[:8]
# Digits-only run id: nss.person.chk_person_mobile_number_format requires
# mobile_number to match ^[0-9]{7,15}$, so the hex _RUN_ID cannot be used
# inside a phone number.
#
# 7 digits, not 8: callers wrap this in a 2-digit prefix + 1-digit suffix to
# build a 10-digit number, which is what MBR-CONTACT-01's +91 rule demands
# (exactly 10 digits, leading 6–9). Widening this breaks validate_mobile().
_RUN_DIGITS = f"{uuid4().int % 10**7:07d}"


class TestAdminCreatePerson:
    """POST /api/v1/admin/persons"""

    def test_create_person_success(self, client, admin_headers, gender_pk):
        """Admin can create a new person with mobile + email."""
        response = client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "Test",
                "middle_name": "Kumar",
                "last_name": "Panda",
                "date_of_birth": "1990-01-15",
                "gender_master_data_pk": gender_pk,
                "country_phone_code": "+91",
                "mobile_number": f"99{_RUN_DIGITS}1",
                "email": f"test_person_{_RUN_ID}@test.example",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "person_pk" in data
        assert "person_id" in data
        assert data["person_id"].startswith("P")
        assert data["person_name"] == "Test Kumar Panda"

    def test_create_person_email_only(self, client, admin_headers, gender_pk):
        """Person can be created with only email (no mobile)."""
        response = client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "EmailOnly",
                "last_name": "Person",
                "date_of_birth": "1985-06-30",
                "gender_master_data_pk": gender_pk,
                "email": f"emailonly_{_RUN_ID}@test.example",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["person_name"] == "Emailonly Person"

    def test_create_person_no_contact_fails(self, client, admin_headers):
        """Creating a person without mobile or email returns 422."""
        response = client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "NoContact",
            },
        )
        assert response.status_code == 422

    def test_create_person_duplicate_mobile_fails(self, client, admin_headers, gender_pk):
        """Duplicate mobile number returns 409."""
        mobile = f"88{_RUN_DIGITS}2"
        # Create first
        client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "First",
                "last_name": "DupMobile",
                "date_of_birth": "1991-02-02",
                "gender_master_data_pk": gender_pk,
                "country_phone_code": "+91",
                "mobile_number": mobile,
                "email": f"dup_mob1_{_RUN_ID}@test.example",
            },
        )
        # Create second with same mobile
        response = client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "Second",
                "last_name": "DupMobile",
                "date_of_birth": "1992-03-03",
                "gender_master_data_pk": gender_pk,
                "country_phone_code": "+91",
                "mobile_number": mobile,
                "email": f"dup_mob2_{_RUN_ID}@test.example",
            },
        )
        assert response.status_code == 409

    def test_create_person_duplicate_email_fails(self, client, admin_headers, gender_pk):
        """Duplicate email returns 409."""
        email = f"dup_email_{_RUN_ID}@test.example"
        # Create first
        client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "First",
                "last_name": "DupEmail",
                "date_of_birth": "1993-04-04",
                "gender_master_data_pk": gender_pk,
                "email": email,
            },
        )
        # Create second with same email
        response = client.post(
            "/api/v1/admin/persons",
            headers=admin_headers,
            json={
                "first_name": "Second",
                "last_name": "DupEmail",
                "date_of_birth": "1994-05-05",
                "gender_master_data_pk": gender_pk,
                "email": email,
            },
        )
        assert response.status_code == 409

    def test_create_person_without_auth_fails(self, client):
        """Creating a person without auth returns 401."""
        response = client.post(
            "/api/v1/admin/persons",
            json={
                "first_name": "NoAuth",
                "email": "noauth@test.example",
            },
        )
        assert response.status_code == 401


# ── Create organization tests ────────────────────────────────────────

class TestCreateOrganization:
    """POST /api/v1/admin/organizations"""

    @pytest.fixture(scope="class")
    @classmethod
    def org_helpers(cls, write_conn):
        """Get master data PKs needed for org creation."""
        cur = write_conn.cursor()
        # Get India country_pk
        cur.execute(
            "SELECT country_pk FROM nss.country WHERE country_code = 'IN' AND is_active = TRUE LIMIT 1"
        )
        row = cur.fetchone()
        country_pk = str(row[0]) if row else None

        # Get a state_pk (Odisha)
        cur.execute(
            "SELECT state_pk FROM nss.state WHERE LOWER(state_name) LIKE '%odisha%' AND is_active = TRUE LIMIT 1"
        )
        row = cur.fetchone()
        state_pk = str(row[0]) if row else None

        # Get a district_pk (any in Odisha)
        if state_pk:
            cur.execute(
                "SELECT district_pk FROM nss.district WHERE state_pk = %s AND is_active = TRUE LIMIT 1",
                (state_pk,),
            )
            row = cur.fetchone()
            district_pk = str(row[0]) if row else None
        else:
            district_pk = None

        return {
            "country_pk": country_pk,
            "state_pk": state_pk,
            "district_pk": district_pk,
        }

    @pytest.fixture(scope="class")
    @classmethod
    def parent_anchalika_pk(cls, client, admin_headers, write_conn, org_helpers):
        """
        Throwaway ANCHALIKA_SANGHA to act as the parent of the SAKHA_SANGHA
        under test.

        The hierarchy rules in create_organization require SAKHA_SANGHA to
        have a parent of type ANCHALIKA_SANGHA or ZILLA_SANGHA, and
        ANCHALIKA_SANGHA in turn must hang off KENDRA (a unique, seeded
        apex org — looked up, never created). Rather than scavenging an
        existing Anchalika, create a fresh one through the same endpoint so
        the parent is known-good; conftest's write_conn rolls it back.

        ANCHALIKA_SANGHA/ZILLA_SANGHA/PATHA_CHAKRA now require
        country/state/district (ORG-BR-099 narrowing — administrative
        jurisdiction, even though they still can't carry a physical
        premises address) — reuses org_helpers rather than a second copy
        of the India/Odisha lookup.
        """
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN nss.master_data md
              ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'KENDRA' AND o.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        assert row, "No active KENDRA organization exists (seeded reference data)."
        kendra_pk = str(row[0])

        resp = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": f"Test Anchalika {_RUN_ID}",
                "organization_type_code": "ANCHALIKA_SANGHA",
                "parent_organization_pk": kendra_pk,
                "organization_code": f"AN{_RUN_ID[:6].upper()}",
                "country_pk": org_helpers["country_pk"],
                "state_pk": org_helpers["state_pk"],
                "district_pk": org_helpers["district_pk"],
            },
        )
        assert resp.status_code == 201, f"Parent Anchalika setup failed: {resp.json()}"
        return resp.json()["organization_pk"]

    def test_create_org_sakha_success(self, client, admin_headers, org_helpers,
                                      parent_anchalika_pk, write_conn):
        """NSS_ERP_ADMIN can create a SAKHA_SANGHA organization."""
        response = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": f"Test Sakha {_RUN_ID}",
                "organization_type_code": "SAKHA_SANGHA",
                "parent_organization_pk": parent_anchalika_pk,
                "country_pk": org_helpers["country_pk"],
                "state_pk": org_helpers["state_pk"],
                "district_pk": org_helpers["district_pk"],
                "city_village_name": f"TestVillage{_RUN_ID}",
                "phone_number": "0674-9999999",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "organization_pk" in data
        assert "organization_code" in data
        assert data["organization_name"] == f"Test Sakha {_RUN_ID}"
        # The create response carries identifiers only (no type_code), so the
        # persisted type + parent edge are verified against the row itself.
        cur = write_conn.cursor()
        cur.execute("""
            SELECT md.value_code, o.parent_organization_pk
            FROM nss.organization o
            JOIN nss.master_data md
              ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.organization_pk = %s
        """, (data["organization_pk"],))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "SAKHA_SANGHA"
        assert str(row[1]) == str(parent_anchalika_pk)

    def test_create_org_unknown_type_fails(self, client, admin_headers):
        """Unknown organization type returns 422."""
        response = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": "Bad Type Org",
                "organization_type_code": "NONEXISTENT_TYPE",
            },
        )
        assert response.status_code == 422

    def test_create_org_missing_name_fails(self, client, admin_headers):
        """Missing organization_name returns 422."""
        response = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_type_code": "SAKHA_SANGHA",
            },
        )
        assert response.status_code == 422


# ── Auto-generated org code + non-consuming preview (ORG-BR-105) ─────

class TestOrgCodeSequencePreview:
    """
    GET /api/v1/admin/organizations/next-code and the sequence-driven
    organization_code it previews (ORG-BR-105).

    For non-wing types the org code is the org-type sequence value
    (organization.organization_id): the code auto-generates on submit and
    equals organization_id. The next-code endpoint shows that value live
    WITHOUT consuming the sequence, so opening the form never burns a number.
    """

    _NEXT_CODE = "/api/v1/admin/organizations/next-code"

    def test_preview_is_non_consuming_and_matches_created_code(
        self, client, admin_headers, india_state_district_pks
    ):
        t = "ANCHALIKA_SANGHA"  # parent auto-resolves to the seeded Kendra
        # Two previews in a row return the SAME value — peeked, not minted.
        p1 = client.get(f"{self._NEXT_CODE}?organization_type_code={t}",
                        headers=admin_headers)
        assert p1.status_code == 200, p1.json()
        d1 = p1.json()
        assert d1["organization_type_code"] == t
        assert d1["sequence_code"] == "ANCHALIKA"
        assert d1["next_code"], "expected a previewed code for a non-wing type"

        p2 = client.get(f"{self._NEXT_CODE}?organization_type_code={t}",
                        headers=admin_headers).json()
        assert p2["next_code"] == d1["next_code"], \
            "preview must not consume the sequence"

        # Creating without a code mints exactly the previewed value, and the
        # org code IS the sequence-based organization_id (one number).
        resp = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": f"Preview Anchalika {_RUN_ID}",
                "organization_type_code": t,
                "country_pk": india_state_district_pks["country_pk"],
                "state_pk": india_state_district_pks["state_pk"],
                "district_pk": india_state_district_pks["district_pk"],
            },
        )
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["organization_code"] == d1["next_code"]
        # ORG-BR-105: the sequence value is materialised as organization_code;
        # organization_id is a legacy identifier not minted by this flow.
        assert data["organization_id"] is None

        # After the create, the next preview has advanced by exactly one.
        p3 = client.get(f"{self._NEXT_CODE}?organization_type_code={t}",
                        headers=admin_headers).json()
        assert p3["next_code"] != d1["next_code"]

    @pytest.mark.parametrize("type_code", ["KUMARI_SANGHA", "SEVAK_SANGHA"])
    def test_preview_is_null_for_wing_types(self, client, admin_headers, type_code):
        # Wings carry no code of their own (ORG-BR-104), so there is nothing
        # to preview — next_code and sequence_code are both null.
        r = client.get(f"{self._NEXT_CODE}?organization_type_code={type_code}",
                       headers=admin_headers)
        assert r.status_code == 200, r.json()
        data = r.json()
        assert data["next_code"] is None
        assert data["sequence_code"] is None


# ── Kumari/Sevak wing inheritance tests ──────────────────────────────

class TestKumariSevakInheritsFromParent:
    """
    POST /api/v1/admin/organizations — KUMARI_SANGHA / SEVAK_SANGHA carry NO
    organization_code and NO short_code of their own (they are wings of a
    Sakha Sangha, which already holds those), and inherit ALL location/contact
    detail from that parent Sakha. Client-supplied code / short_code / address
    / contact values for these two types are ignored (ORG-BR-092/104,
    wing-shares-the-Sakha's-identity, MBR-046).
    """

    @pytest.fixture(scope="class")
    @classmethod
    def parent_sakha(cls, client, admin_headers, write_conn, india_state_district_pks):
        """A Sakha with a known code and a full location/contact detail set,
        so the wing's inheritance can be asserted field-by-field."""
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN nss.master_data md
              ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'KENDRA' AND o.is_active = TRUE
            LIMIT 1
        """)
        kendra_pk = str(cur.fetchone()[0])
        country_pk = india_state_district_pks["country_pk"]
        state_pk = india_state_district_pks["state_pk"]
        district_pk = india_state_district_pks["district_pk"]

        an = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": f"Wing Anchalika {_RUN_ID}",
                "organization_type_code": "ANCHALIKA_SANGHA",
                "parent_organization_pk": kendra_pk,
                "organization_code": f"WA{_RUN_ID[:6].upper()}",
                "country_pk": country_pk,
                "state_pk": state_pk,
                "district_pk": district_pk,
            },
        )
        assert an.status_code == 201, f"Anchalika setup failed: {an.json()}"

        sk = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": f"Wing Parent Sakha {_RUN_ID}",
                "organization_type_code": "SAKHA_SANGHA",
                "parent_organization_pk": an.json()["organization_pk"],
                "organization_code": f"WP{_RUN_ID[:5].upper()}",
                "country_pk": country_pk,
                "state_pk": state_pk,
                "district_pk": district_pk,
                "city_village_name": f"WingVillage{_RUN_ID}",
                "postal_code_value": "751024",
                "phone_number": "0674-1112222",
                "country_phone_code": "+91",
                "mobile_number": "9800011122",
                "org_email": "wingparent@example.org",
                "org_website_url": "https://wingparent.example.org",
                "org_youtube_channel_url": "https://youtube.com/@wingparent",
            },
        )
        assert sk.status_code == 201, f"Parent Sakha setup failed: {sk.json()}"
        return sk.json()["organization_pk"], sk.json()["organization_code"]

    @pytest.mark.parametrize("type_code", [
        "KUMARI_SANGHA",
        "SEVAK_SANGHA",
    ])
    def test_wing_has_no_code_and_inherits_detail_from_parent(
        self, client, admin_headers, write_conn, parent_sakha, type_code
    ):
        parent_pk, parent_code = parent_sakha
        resp = client.post(
            "/api/v1/admin/organizations",
            headers=admin_headers,
            json={
                "organization_name": f"{type_code} {_RUN_ID}",
                "organization_type_code": type_code,
                "parent_organization_pk": parent_pk,
                # Deliberately-wrong values that MUST be ignored for wings:
                "organization_code": "WRONGXX",
                "short_code": "WRNG",
                "address_line_1": "Should Be Ignored",
                "phone_number": "0000000",
                "org_email": "ignored@example.org",
            },
        )
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        # A wing carries no organization_code of its own.
        assert data["organization_code"] is None

        cols = """organization_code, address_line_1, country_pk, state_pk,
                  district_pk, city_village_pk, postal_code_pk, phone_number,
                  mobile_number, org_email, org_website_url,
                  org_youtube_channel_url, short_code"""
        cur = write_conn.cursor()
        cur.execute(f"SELECT {cols} FROM nss.organization WHERE organization_pk = %s", (data["organization_pk"],))
        wing = cur.fetchone()
        cur.execute(f"SELECT {cols} FROM nss.organization WHERE organization_pk = %s", (parent_pk,))
        parent = cur.fetchone()

        # No code / short_code of its own, regardless of client input.
        assert wing[0] is None
        assert wing[12] is None
        # Every inheritable detail column (1..11) equals the parent's.
        for i in range(1, 12):
            assert wing[i] == parent[i], f"inherited column index {i} mismatch"


# ── Short-code update tests ──────────────────────────────────────────

class TestUpdateShortCode:
    """PATCH /api/v1/admin/organizations/{pk}/short-code"""

    def _get_first_org_pk(self, client, admin_headers):
        """Helper: get the PK of the first organization."""
        resp = client.get(
            "/api/v1/admin/organizations?page_size=1",
            headers=admin_headers,
        )
        orgs = resp.json().get("organizations", [])
        if not orgs:
            pytest.skip("No organizations in database.")
        return orgs[0]["organization_pk"]

    def test_set_short_code_success(self, client, admin_headers):
        """Admin can set a short_code on an organization."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        code = f"T{_RUN_ID[:4].upper()}"[:5]
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}/short-code",
            headers=admin_headers,
            json={"short_code": code},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["short_code"] == code

    def test_clear_short_code(self, client, admin_headers):
        """Admin can clear a short_code by sending null."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}/short-code",
            headers=admin_headers,
            json={"short_code": None},
        )
        assert response.status_code == 200
        assert response.json()["short_code"] is None

    def test_invalid_short_code_format(self, client, admin_headers):
        """Short code with invalid format returns 422."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}/short-code",
            headers=admin_headers,
            json={"short_code": "AB"},  # too short (min 3)
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [123, True, ["ABC"], {"a": 1}])
    def test_non_string_short_code_is_422(self, client, admin_headers, value):
        """The body is a Pydantic schema: a non-string is a 422, not a crash/coercion."""
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}/short-code",
            headers=admin_headers,
            json={"short_code": value},
        )
        assert response.status_code == 422

    def test_non_object_body_is_422(self, client, admin_headers):
        org_pk = self._get_first_org_pk(client, admin_headers)
        response = client.patch(
            f"/api/v1/admin/organizations/{org_pk}/short-code",
            headers=admin_headers,
            json=["ABC"],
        )
        assert response.status_code == 422

    def test_short_code_nonexistent_org(self, client, admin_headers):
        """Updating short_code on non-existent org returns 404."""
        response = client.patch(
            "/api/v1/admin/organizations/00000000-0000-0000-0000-000000000099/short-code",
            headers=admin_headers,
            json={"short_code": "XYZ"},
        )
        assert response.status_code == 404


# ── Create user with Sangha Sevi tests ───────────────────────────────

class TestCreateUserWithSanghaSevi:
    """POST /api/v1/admin/users with create_sangha_sevi=True"""

    @pytest.fixture(scope="class")
    @classmethod
    def ss_helpers(cls, write_conn):
        """Get master data PKs needed for sangha sevi creation."""
        cur = write_conn.cursor()

        # Get PROBATIONARY membership type
        cur.execute("""
            SELECT md.master_data_pk
            FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE'
              AND md.value_code = 'PROBATIONARY'
              AND md.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        membership_type_pk = str(row[0]) if row else None

        # Get a SAKHA_SANGHA org
        cur.execute("""
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA'
              AND o.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        org_pk = str(row[0]) if row else None

        return {
            "membership_type_pk": membership_type_pk,
            "organization_pk": org_pk,
        }

    @pytest.fixture(scope="class")
    @classmethod
    def ss_target_person_pk(cls, write_conn):
        """
        Create a dedicated throwaway person (guaranteed no user account)
        for the create-user-with-sangha-sevi test. See target_person_pk
        above for why this must not scavenge nss.person for an existing
        unassigned person.
        """
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()
        cur.execute(
            """
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s)
            RETURNING person_pk
            """,
            (f"TSS{suffix}", "TestCreateUserSS", suffix, f"tss.{suffix.lower()}@example.test"),
        )
        person_pk = cur.fetchone()[0]
        cur.close()
        return person_pk

    def test_create_user_with_sangha_sevi(
        self, client, admin_headers, ss_target_person_pk, ss_helpers
    ):
        """Admin can create user + sangha sevi in one call."""
        if not ss_helpers["membership_type_pk"] or not ss_helpers["organization_pk"]:
            pytest.skip("Missing membership_type or organization for SS test.")

        response = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "person_pk": str(ss_target_person_pk),
                "password": TARGET_PASSWORD,
                "force_password_change": True,
                "create_sangha_sevi": True,
                "membership_type_pk": ss_helpers["membership_type_pk"],
                "organization_pk": ss_helpers["organization_pk"],
                "joining_date": "2024-01-15",
            },
        )
        assert response.status_code == 201, f"Failed: {response.json()}"
        data = response.json()
        assert "user_account_pk" in data
        assert data["account_status"] == "ACTIVE"

    def test_create_user_with_ss_missing_fields(self, client, admin_headers):
        """Requesting sangha sevi without required fields returns 422."""
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "person_pk": "00000000-0000-0000-0000-000000000001",
                "password": TARGET_PASSWORD,
                "create_sangha_sevi": True,
                # Missing: membership_type_pk, organization_pk, joining_date
            },
        )
        assert response.status_code == 422
        assert "sangha sevi" in response.json()["detail"].lower()


# ── Sakha auto-select/lock for member-attach flows ────────────────────

# ── Shared module-scope fixtures for Sakha-scope tests ─────────────────
# Moved out of TestSakhaScopeAutoSelect (class-scoped fixtures aren't
# visible to other classes) so TestKumariSevakSakhaOptions can reuse them
# too — same two_sakhas / sakha_admin_headers, one Sakha-scoped test user.

@pytest.fixture(scope="module")
def two_sakhas(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md
          ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.organization_name
        LIMIT 2
    """)
    rows = [str(r[0]) for r in cur.fetchall()]
    cur.close()
    return rows


@pytest.fixture(scope="module")
def regular_membership_type_pk(write_conn):
    """REGULAR membership_type master_data_pk (module-shared)."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE'
          AND md.value_code = 'REGULAR' AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row else None


@pytest.fixture(scope="module")
def sakha_admin_headers(client, write_conn, two_sakhas):
    """A NSS_ERP_SAKHA_ADMIN scoped to exactly one Sakha (two_sakhas[0])."""
    if not two_sakhas:
        pytest.skip("No SAKHA_SANGHA org available.")
    from api.services.auth_service import hash_password
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR'
          AND md.is_active = TRUE LIMIT 1
    """)
    mtype = cur.fetchone()[0]
    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE'
          AND md.is_active = TRUE LIMIT 1
    """)
    mstatus = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"TSKA{suffix}", "TestSakhaAdmin", suffix, f"tska.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    ss_id = f"TSSSKA{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (ss_id, str(person_pk), str(mtype), str(mstatus), two_sakhas[0]))

    password_hash = hash_password(ADMIN_PASSWORD)
    cur.execute("""
        INSERT INTO nss.user_account (person_pk, password_hash, account_status,
            force_password_change, password_expires_at)
        VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), password_hash))
    ua_pk = cur.fetchone()[0]

    cur.execute(
        "SELECT role_master_pk FROM nss.role_master WHERE role_code='NSS_ERP_SAKHA_ADMIN' AND is_active=TRUE"
    )
    role_pk = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO nss.user_role (user_account_pk, role_master_pk)
        VALUES (%s, %s) RETURNING user_role_pk
    """, (str(ua_pk), str(role_pk)))
    ur_pk = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, 'SAKHA', %s)
    """, (str(ur_pk), two_sakhas[0]))
    cur.close()

    resp = client.post("/api/v1/auth/login", json={"login_id": ss_id, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Sakha admin login failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestSakhaScopeAutoSelect:
    """
    The parent-Sakha auto-select/lock pattern (from Kumari/Sevak creation)
    extended to member-attach flows: GET /admin/sakha-scope-options and the
    auto-fill in POST /admin/sangha-sevi.

      - NSS-wide admin: mode "choose", no auto-select, must pick a Sakha.
      - Admin scoped to exactly one Sakha: mode "locked", that Sakha
        auto-selected, and omitting organization_pk on create still works.
      - A scoped admin may not attach to a Sakha outside their scope.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def regular_type_pk(cls, write_conn):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT md.master_data_pk
            FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE'
              AND md.value_code = 'REGULAR' AND md.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        return str(row[0]) if row else None

    def _make_person(self, write_conn):
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()
        cur.execute("""
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) RETURNING person_pk
        """, (f"TSAP{suffix}", "TestScopePerson", suffix, f"tsap.{suffix.lower()}@example.test"))
        person_pk = str(cur.fetchone()[0])
        cur.close()
        return person_pk

    def test_options_nss_wide_is_choose(self, client, admin_headers):
        resp = client.get("/api/v1/admin/sakha-scope-options", headers=admin_headers)
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["mode"] == "choose"
        assert data["auto_select_pk"] is None
        assert len(data["sakhas"]) >= 1

    def test_options_single_sakha_is_locked(self, client, sakha_admin_headers, two_sakhas):
        resp = client.get("/api/v1/admin/sakha-scope-options", headers=sakha_admin_headers)
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["mode"] == "locked"
        assert data["auto_select_pk"] == two_sakhas[0]
        assert len(data["sakhas"]) == 1

    def test_nss_wide_must_pick_sakha(self, client, admin_headers, regular_type_pk, write_conn):
        if not regular_type_pk:
            pytest.skip("REGULAR membership type missing.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_type_pk,
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 422
        assert "sakha" in resp.json()["detail"].lower()

    def test_single_sakha_admin_auto_fills(
        self, client, sakha_admin_headers, regular_type_pk, two_sakhas, write_conn
    ):
        if not regular_type_pk:
            pytest.skip("REGULAR membership type missing.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=sakha_admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_type_pk,
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 201, resp.json()

    def test_scoped_admin_rejected_out_of_scope(
        self, client, sakha_admin_headers, regular_type_pk, two_sakhas, write_conn
    ):
        if not regular_type_pk:
            pytest.skip("REGULAR membership type missing.")
        if len(two_sakhas) < 2:
            pytest.skip("Need a second Sakha to test out-of-scope rejection.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=sakha_admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_type_pk,
            "organization_pk": two_sakhas[1],
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 403


class TestKumariSevakSakhaOptions:
    """
    GET /admin/organizations/kumari-sevak-sakha-options (ORG-BR-101/102).

    Regression coverage for the permission-gate bug where this endpoint
    (and create_organization) required ADMIN_USER_MANAGE outright, making
    the Sakha-admin branch below unreachable since NSS_ERP_SAKHA_ADMIN only
    holds PERSON_MANAGE. Now gated on require_any_permission of the two,
    matching the ORG-BR-103 sibling /admin/sakha-scope-options.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def report_viewer_headers(cls, client, write_conn, two_sakhas):
        """A role with neither ADMIN_USER_MANAGE nor PERSON_MANAGE.

        Login is via sangha_sevi_id (there is no user_account.login_id
        column) — mirrors the admin_user / sakha_admin_headers fixtures.
        """
        if not two_sakhas:
            pytest.skip("No SAKHA_SANGHA org available.")
        from api.services.auth_service import hash_password
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()

        cur.execute("""
            SELECT md.master_data_pk FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR'
              AND md.is_active = TRUE LIMIT 1
        """)
        mtype = cur.fetchone()[0]
        cur.execute("""
            SELECT md.master_data_pk FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE'
              AND md.is_active = TRUE LIMIT 1
        """)
        mstatus = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) RETURNING person_pk
        """, (f"TRVW{suffix}", "TestReportViewer", suffix, f"trvw.{suffix.lower()}@example.test"))
        person_pk = cur.fetchone()[0]

        ss_id = f"TSSRVW{suffix}"
        cur.execute("""
            INSERT INTO nss.sangha_sevi (
                sangha_sevi_id, person_pk, membership_type_master_data_pk,
                membership_status_master_data_pk, organization_pk, joining_date
            ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        """, (ss_id, str(person_pk), str(mtype), str(mstatus), two_sakhas[0]))

        password_hash = hash_password(ADMIN_PASSWORD)
        cur.execute("""
            INSERT INTO nss.user_account (person_pk, password_hash, account_status,
                force_password_change, password_expires_at)
            VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
            RETURNING user_account_pk
        """, (str(person_pk), password_hash))
        ua_pk = cur.fetchone()[0]

        cur.execute(
            "SELECT role_master_pk FROM nss.role_master WHERE role_code='NSS_ERP_REPORT_VIEWER' AND is_active=TRUE"
        )
        role_pk = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO nss.user_role (user_account_pk, role_master_pk)
            VALUES (%s, %s)
        """, (str(ua_pk), str(role_pk)))
        cur.close()

        resp = client.post("/api/v1/auth/login", json={"login_id": ss_id, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200, f"Report-viewer login failed: {resp.json()}"
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_nss_wide_admin_is_choose(self, client, admin_headers):
        resp = client.get(
            "/api/v1/admin/organizations/kumari-sevak-sakha-options",
            headers=admin_headers, params={"type_code": "KUMARI_SANGHA"},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["mode"] == "choose"
        assert data["auto_select_pk"] is None
        assert len(data["sakhas"]) >= 1

    def test_single_sakha_admin_is_locked(self, client, sakha_admin_headers, two_sakhas):
        resp = client.get(
            "/api/v1/admin/organizations/kumari-sevak-sakha-options",
            headers=sakha_admin_headers, params={"type_code": "SEVAK_SANGHA"},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["mode"] == "locked"
        assert data["auto_select_pk"] == two_sakhas[0]
        assert len(data["sakhas"]) == 1
        assert data["sakhas"][0]["organization_pk"] == two_sakhas[0]

    def test_invalid_type_code_is_422(self, client, admin_headers):
        resp = client.get(
            "/api/v1/admin/organizations/kumari-sevak-sakha-options",
            headers=admin_headers, params={"type_code": "SAKHA_SANGHA"},
        )
        assert resp.status_code == 422

    def test_neither_permission_is_403(self, client, report_viewer_headers):
        resp = client.get(
            "/api/v1/admin/organizations/kumari-sevak-sakha-options",
            headers=report_viewer_headers, params={"type_code": "KUMARI_SANGHA"},
        )
        assert resp.status_code == 403


class TestCreateSanghaSeviWithAccount:
    """
    POST /admin/sangha-sevi with create_user_account=true bundles a login
    account onto the newly created Sangha Sevi. Login is by sangha_sevi_id,
    so this is the correct home for account creation. Per ADMIN-BR-078,
    account provisioning is a scoped operation: any admin authorized to
    create the Sangha Sevi within scope (ADMIN_USER_MANAGE or PERSON_MANAGE)
    may also bundle its login, but only within their scope (ADMIN-BR-076).
    """

    def _make_person(self, write_conn):
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()
        cur.execute("""
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) RETURNING person_pk
        """, (f"TSSA{suffix}", "TestSSAcct", suffix, f"tssa.{suffix.lower()}@example.test"))
        person_pk = str(cur.fetchone()[0])
        cur.close()
        return person_pk

    def test_bundles_account_and_can_login(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
            "create_user_account": True,
            "password": ADMIN_PASSWORD,
            "force_password_change": True,
        })
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["user_account_pk"] is not None
        # The bundled account is usable immediately — login by sangha_sevi_id.
        login = client.post("/api/v1/auth/login", json={
            "login_id": data["sangha_sevi_id"], "password": ADMIN_PASSWORD,
        })
        assert login.status_code == 200, login.json()

    def test_account_requested_without_password_is_422(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
            "create_user_account": True,
        })
        assert resp.status_code == 422

    def test_scoped_admin_can_bundle_account_in_scope(
        self, client, sakha_admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        # ADMIN-BR-078: a PERSON_MANAGE-only Sakha admin MAY bundle a login
        # account, provided the Sangha Sevi is created within their scope.
        # organization_pk is omitted, so it auto-resolves to their own Sakha.
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=sakha_admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "joining_date": "2024-04-01",
            "create_user_account": True,
            "password": ADMIN_PASSWORD,
            "force_password_change": True,
        })
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["user_account_pk"] is not None
        # The bundled account is usable immediately — login by sangha_sevi_id.
        login = client.post("/api/v1/auth/login", json={
            "login_id": data["sangha_sevi_id"], "password": ADMIN_PASSWORD,
        })
        assert login.status_code == 200, login.json()

    def test_scoped_admin_cannot_bundle_out_of_scope(
        self, client, sakha_admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        # ADMIN-BR-076: bundling for a Sakha OUTSIDE the admin's scope is
        # rejected. sakha_admin is scoped to two_sakhas[0]; target [1].
        if not regular_membership_type_pk or len(two_sakhas) < 2:
            pytest.skip("Need two SAKHA_SANGHA orgs.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=sakha_admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[1],
            "joining_date": "2024-04-01",
            "create_user_account": True,
            "password": ADMIN_PASSWORD,
        })
        assert resp.status_code == 403, resp.json()

    def test_plain_ss_creation_returns_no_account(
        self, client, sakha_admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        # Plain SS creation (no account) still works and returns no account pk.
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk2 = self._make_person(write_conn)
        resp2 = client.post("/api/v1/admin/sangha-sevi", headers=sakha_admin_headers, json={
            "person_pk": person_pk2,
            "membership_type_pk": regular_membership_type_pk,
            "joining_date": "2024-04-01",
        })
        assert resp2.status_code == 201, resp2.json()
        assert resp2.json()["user_account_pk"] is None


class TestCreateSanghaSeviCredentialNumber:
    """
    POST /admin/sangha-sevi — legacy credential document_number handling.

    MBR-030H (2026-10-03, supersedes the 2026-10-01 verbatim-storage note):
    the shared credential writer issue_membership_credential() normalises a
    caller-supplied document_number via normalize_patra_document_number() —
    a bare number gets the issue-date year pair appended, a number with a
    year must match it (else 422). The auto-generate path (no
    document_number) is unaffected and still mints a well-formed FY
    composite.
    """

    def _make_person(self, write_conn):
        cur = write_conn.cursor()
        suffix = uuid4().hex[:10].upper()
        cur.execute("""
            INSERT INTO nss.person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) RETURNING person_pk
        """, (f"TCDN{suffix}", "TestCredDoc", suffix, f"tcdn.{suffix.lower()}@example.test"))
        person_pk = str(cur.fetchone()[0])
        cur.close()
        return person_pk

    def _parichaya_document_number(self, write_conn, person_pk):
        """The document_number of the Parichaya Patra issued for this person."""
        cur = write_conn.cursor()
        cur.execute("""
            SELECT pp.document_number
            FROM nss.parichaya_patra pp
            JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = pp.sangha_sevi_pk
            WHERE ss.person_pk = %s
        """, (person_pk,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def _issue_year(self, write_conn, person_pk):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT pp.issue_date
            FROM nss.parichaya_patra pp
            JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = pp.sangha_sevi_pk
            WHERE ss.person_pk = %s
        """, (person_pk,))
        row = cur.fetchone()
        cur.close()
        return row[0].year

    def _create(self, client, admin_headers, regular_membership_type_pk, two_sakhas, number):
        return client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": number["person_pk"],
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
            "credential_document_number": number["value"],
        })

    # MBR-030H (supersedes the retired verbatim-storage note, 2026-10-03):
    # a supplied number is normalised — a bare number gets the issue-date
    # year pair appended, a number with a year must match it. The sequence is
    # trusted as typed (int-normalised). parichaya_patra.document_number is
    # globally UNIQUE and rows persist, so every case gets a run-scoped,
    # per-case sequence.
    @pytest.mark.parametrize("shape,offset", [
        ("{s}", 0),             # bare number -> year pair appended
        (" {s} ", 1),           # surrounding whitespace is stripped
    ])
    def test_bare_legacy_number_gets_issue_year_appended(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn, shape, offset
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        seq = int(_RUN_DIGITS) + 10 + offset
        person_pk = self._make_person(write_conn)
        resp = self._create(client, admin_headers, regular_membership_type_pk, two_sakhas,
                            {"person_pk": person_pk, "value": shape.format(s=seq)})
        assert resp.status_code == 201, resp.json()
        year = self._issue_year(write_conn, person_pk)
        assert self._parichaya_document_number(write_conn, person_pk) == f"{seq}/{year}/{year + 1}"

    def test_legacy_number_with_matching_year_is_kept(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        # Learn the issue year the Parichaya Patra will carry from a bare issue.
        probe = self._make_person(write_conn)
        seq0 = int(_RUN_DIGITS) + 20
        resp = self._create(client, admin_headers, regular_membership_type_pk, two_sakhas,
                            {"person_pk": probe, "value": str(seq0)})
        assert resp.status_code == 201, resp.json()
        year = self._issue_year(write_conn, probe)

        seq = int(_RUN_DIGITS) + 21
        person_pk = self._make_person(write_conn)
        resp = self._create(client, admin_headers, regular_membership_type_pk, two_sakhas,
                            {"person_pk": person_pk, "value": f" {seq}/{year}/{year + 1} "})
        assert resp.status_code == 201, resp.json()
        assert self._parichaya_document_number(write_conn, person_pk) == f"{seq}/{year}/{year + 1}"

    @pytest.mark.parametrize("bad_shape,fragment", [
        ("{s}/2026", "Use the form"),             # partial year
        ("abc{s}", "not valid"),                  # non-numeric
        ("{s}/25/26", "wrong year"),              # two-digit years
        ("{s}/2026/2027/2028", "Use the form"),   # extra segment
        ("{s}/1990/1991", "wrong year"),          # well-formed but wrong year
    ])
    def test_malformed_legacy_number_is_422(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn,
        bad_shape, fragment
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        resp = self._create(client, admin_headers, regular_membership_type_pk, two_sakhas,
                            {"person_pk": person_pk, "value": bad_shape.format(s=int(_RUN_DIGITS) + 30)})
        assert resp.status_code == 422, resp.json()
        assert fragment in resp.json()["detail"]

    def test_valid_legacy_number_accepted_and_stored_verbatim(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        # No year requirement (MBR-030D retired, 2026-10-01) — any FY-shaped
        # number, past, present, or future, is accepted and stored as-is.
        from datetime import date

        from api.helpers import financial_year_bounds

        fy_start, fy_end, fy_valid_from, fy_valid_to = financial_year_bounds(date.today())
        # Unique 6-digit sequence so the composite can't collide (409) with
        # seed data or a sibling test's credential in the same transaction.
        seq = str(uuid4().int % 900000 + 100000)
        doc = f"{seq}/{fy_start}/{fy_end}"
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
            "credential_document_number": doc,
            "credential_valid_from": fy_valid_from.isoformat(),
            "credential_valid_to": fy_valid_to.isoformat(),
        })
        assert resp.status_code == 201, resp.json()
        # REGULAR membership => Parichaya Patra; the number is stored verbatim.
        assert self._parichaya_document_number(write_conn, person_pk) == doc

    def test_omitted_number_autogenerates_valid_composite(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        """No document_number => a well-formed FY composite is auto-generated."""
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 201, resp.json()
        stored = self._parichaya_document_number(write_conn, person_pk)
        assert stored is not None, "Parichaya Patra should have been issued"
        parts = stored.split("/")
        assert len(parts) == 3, stored
        assert parts[0].isdigit(), stored
        assert len(parts[1]) == 4 and parts[1].isdigit(), stored
        assert len(parts[2]) == 4 and parts[2].isdigit(), stored

    def test_autogenerated_validity_window_follows_dola_purnima(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        """
        SOL-ARCH-013 FC-DECISION-01: valid_from/valid_to are decoupled from
        the FY-based document_number — they must land on confirmed Dola
        Purnima dates (the "Dola Purnima membership year"), not on the
        1 April/31 March financial-year bounds that still govern the
        document_number itself.
        """
        from datetime import date

        from api.helpers import festival_date_for_year, financial_year_bounds

        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        person_pk = self._make_person(write_conn)
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": person_pk,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 201, resp.json()

        cur = write_conn.cursor()
        cur.execute("""
            SELECT pp.document_number, pp.valid_from, pp.valid_to
            FROM nss.parichaya_patra pp
            JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = pp.sangha_sevi_pk
            WHERE ss.person_pk = %s
        """, (person_pk,))
        document_number, valid_from, valid_to = cur.fetchone()

        # document_number is still FY-based (MBR-030A) ...
        seq_str, fy_start_str, fy_end_str = document_number.split("/")
        assert int(fy_end_str) == int(fy_start_str) + 1

        # ... and valid_from/valid_to (and issue_date, implicitly) are the
        # Dola Purnima dates of that SAME financial year — the document
        # number's fy_start year to fy_start+1 — not whatever Dola Purnima
        # happens to fall next after today's raw date (2026-10-03 refinement:
        # no credential is ever anchored on today(), only on a Dola Purnima
        # tied to the membership year being issued).
        anchor_year = financial_year_bounds(date.today())[0]
        assert int(fy_start_str) == anchor_year
        expected_from = festival_date_for_year(cur, "DOLA_PURNIMA", anchor_year)
        expected_to = festival_date_for_year(cur, "DOLA_PURNIMA", anchor_year + 1)
        cur.close()

        assert valid_from == expected_from
        assert valid_to == expected_to
        assert valid_to.year == valid_from.year + 1


# ── Local Sakha number uniqueness / numbering-space tests ─────────────

class TestLocalSakhaNumberUniqueness:
    """
    POST /api/v1/admin/sangha-sevi — local Sakha number rules.

    Two distinct rules are asserted here:

      1. Per MBR-030C, the Tier 2 local Sakha identifier is namespace-separated
         by membership state. A Regular composes as <short_code><number> and a
         Darshaka (MEMBERSHIP_TYPE 'PROBATIONARY') as <short_code><marker>
         <number>. The same raw number given to one of each is therefore not a
         collision at all — it materialises as two DIFFERENT identifiers, and
         both enrolments succeed.
      2. A genuine duplicate — same raw number, same namespace, same Sakha —
         must surface as a readable 409 conflict, never as an unhandled 500
         from the underlying UniqueViolation.

    Note the scope. This is Tier 2 only. The no-reuse guarantee the Bye-Law
    makes (MBR-004) is a Tier 1 statement about the Sangha Sevi ID, which is
    permanent and never reissued; it says nothing about Tier 2 local numbers
    and must not be read as forbidding what rule 1 asserts.

    Authority for the numbering spaces:
      - MBR-030C (membership business rules) — namespace separation, the
        configured marker, and archival-not-reuse on progression
      - nss.membership_sakha_affiliation.uq_mem_sakha_aff_local_id
        UNIQUE (organization_pk, local_sakha_erp_id)
      - nss.darshak_attendance_registration
        UNIQUE (attending_organization_pk, darshak_local_number)

    Because the marker is part of the identifier STRING, both constraints
    above remain correct unmodified — no type discriminator is needed.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def num_helpers(cls, write_conn):
        """
        Resolve the REGULAR and PROBATIONARY (Darshaka) membership types and
        a Sakha org that has a short_code — compose_local_sakha_erp_id raises
        422 when short_code is NULL, which would mask the behaviour under
        test. The real 175-branch seed leaves short_code NULL by design
        (admin-assignable via UI), so a fresh build has none set — assign a
        synthetic one here if needed, scoped to this test transaction only
        (rolled back by conftest's module SAVEPOINT). Same pattern as
        test_claim_approval.py::sakha_orgs / test_registration.py::test_org_pk.
        """
        cur = write_conn.cursor()

        cur.execute("""
            SELECT md.value_code, md.master_data_pk
            FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE'
              AND md.value_code IN ('REGULAR', 'PROBATIONARY')
              AND md.is_active = TRUE
        """)
        types = {row[0]: str(row[1]) for row in cur.fetchall()}

        cur.execute("""
            SELECT o.organization_pk, o.short_code
            FROM nss.organization o
            JOIN nss.master_data md
              ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA'
              AND o.is_active = TRUE
            ORDER BY o.short_code IS NOT NULL DESC, o.created_at
            LIMIT 1
        """)
        row = cur.fetchone()
        org_pk = str(row[0]) if row else None
        if org_pk and not row[1]:
            cur.execute(
                "UPDATE nss.organization SET short_code = 'TLSN' WHERE organization_pk = %s",
                (org_pk,),
            )
        cur.close()

        return {
            "regular_pk": types.get("REGULAR"),
            "darshaka_pk": types.get("PROBATIONARY"),
            "organization_pk": org_pk,
        }

    @pytest.fixture
    def make_person(self, write_conn):
        """Factory for throwaway nss.person rows (never scavenges)."""
        def _make():
            cur = write_conn.cursor()
            suffix = uuid4().hex[:10].upper()
            cur.execute(
                """
                INSERT INTO nss.person (person_id, first_name, last_name, email)
                VALUES (%s, %s, %s, %s)
                RETURNING person_pk
                """,
                (
                    f"TNM{suffix}",
                    "TestLocalNum",
                    suffix,
                    f"tnm.{suffix.lower()}@example.test",
                ),
            )
            person_pk = cur.fetchone()[0]
            cur.close()
            return str(person_pk)
        return _make

    @staticmethod
    def _fresh_number():
        """A local number wide enough that it cannot collide with live data."""
        return str(9_000_000 + int(uuid4().int % 900_000))

    def _create_ss(self, client, admin_headers, helpers, person_pk,
                   membership_type_pk, local_number):
        return client.post(
            "/api/v1/admin/sangha-sevi",
            headers=admin_headers,
            json={
                "person_pk": person_pk,
                "membership_type_pk": membership_type_pk,
                "organization_pk": helpers["organization_pk"],
                "joining_date": "2024-04-01",
                "local_sakha_erp_id": local_number,
            },
        )

    @pytest.fixture(autouse=True)
    def _require_helpers(self, num_helpers):
        missing = [k for k, v in num_helpers.items() if not v]
        if missing:
            pytest.fail(
                "Cannot run local-number tests — missing reference data: "
                f"{missing}. A Sakha org with a short_code and both the "
                "REGULAR and PROBATIONARY membership types must exist."
            )

    def test_regular_number_is_accepted(
        self, client, admin_headers, num_helpers, make_person
    ):
        """Baseline: a Regular member with an unused local number is created."""
        response = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["regular_pk"], self._fresh_number(),
        )
        assert response.status_code == 201, f"Failed: {response.json()}"

    def test_regular_and_darshaka_numbers_occupy_separate_namespaces(
        self, client, admin_headers, num_helpers, make_person, write_conn
    ):
        """
        MBR-030C — the same raw local number is not a collision across
        membership states, because it composes into two different identifiers.

        Given raw number N in Sakha with short code ESS:
            Regular  -> ESS<N>
            Darshaka -> ESS<marker><N>

        Both enrolments must succeed, and the two STORED identifiers must
        differ — which is the actual guarantee. Asserting only two 201s would
        pass even if both rows stored the same string, so the stored values
        are read back.
        """
        number = self._fresh_number()

        first = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["regular_pk"], number,
        )
        assert first.status_code == 201, f"Regular setup failed: {first.json()}"

        second = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["darshaka_pk"], number,
        )
        assert second.status_code == 201, (
            "A Darshaka must be enrollable on the same raw local number as a "
            "Regular member — the marker places it in a separate namespace "
            f"(MBR-030C). Got {second.status_code}: {second.text}"
        )

        # The marker is read from configuration, never hardcoded here — the
        # rule is "the namespaces are separated", not "the letter is D".
        cur = write_conn.cursor()
        cur.execute(
            """
            SELECT setting_value
            FROM   nss.system_setting
            WHERE  setting_key = 'MEMBERSHIP_DARSHAK_LOCAL_ID_MARKER'
              AND  is_active = TRUE
            """
        )
        row = cur.fetchone()
        assert row and row[0].strip(), (
            "MEMBERSHIP_DARSHAK_LOCAL_ID_MARKER is not configured. "
            "Darshaka enrolment is designed to fail loudly without it, so "
            "this test cannot be meaningful until the setting is seeded."
        )
        marker = row[0].strip()

        stored = {}
        for label, response in (("regular", first), ("darshaka", second)):
            cur.execute(
                """
                SELECT local_sakha_erp_id
                FROM   nss.membership_sakha_affiliation
                WHERE  sangha_sevi_pk = %s
                  AND  organization_pk = %s
                """,
                (response.json()["sangha_sevi_pk"], num_helpers["organization_pk"]),
            )
            found = cur.fetchone()
            assert found, f"No affiliation row persisted for the {label} member."
            stored[label] = found[0]
        cur.close()

        assert stored["regular"] != stored["darshaka"], (
            "Both members stored the identical Tier 2 identifier "
            f"{stored['regular']!r}. The namespace marker was not applied, so "
            "the two states are sharing one numbering space."
        )
        assert stored["regular"].endswith(number), (
            f"Regular identifier {stored['regular']!r} should end with the raw "
            f"number {number!r} and carry no marker."
        )
        assert stored["darshaka"].endswith(f"{marker}{number}"), (
            f"Darshaka identifier {stored['darshaka']!r} should end with the "
            f"configured marker + raw number ({marker}{number})."
        )

    def test_duplicate_number_same_type_returns_409(
        self, client, admin_headers, num_helpers, make_person
    ):
        """
        Two Regular members cannot share a local number in the same Sakha —
        and the refusal must be a readable 409, not a 500.
        """
        number = self._fresh_number()

        first = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["regular_pk"], number,
        )
        assert first.status_code == 201, f"Regular setup failed: {first.json()}"

        second = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["regular_pk"], number,
        )
        assert second.status_code == 409, (
            f"Expected 409, got {second.status_code}: {second.text}"
        )
        detail = second.json()["detail"]
        assert isinstance(detail, str), f"detail must be a string, got {detail!r}"
        assert number in detail, f"Message should name the number: {detail!r}"

    def test_duplicate_darshaka_number_returns_409(
        self, client, admin_headers, num_helpers, make_person
    ):
        """
        Two Darshaka members cannot share a local number either — namespace
        separation (MBR-030C) applies BETWEEN states, not within one. The
        Darshaka namespace is uniqueness-constrained exactly like the Regular
        one, so the marker must not be mistaken for a licence to duplicate.
        """
        number = self._fresh_number()

        first = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["darshaka_pk"], number,
        )
        assert first.status_code == 201, f"Darshaka setup failed: {first.json()}"

        second = self._create_ss(
            client, admin_headers, num_helpers,
            make_person(), num_helpers["darshaka_pk"], number,
        )
        assert second.status_code == 409, (
            f"Expected 409, got {second.status_code}: {second.text}"
        )
        assert isinstance(second.json()["detail"], str)



