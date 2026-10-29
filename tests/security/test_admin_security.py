"""
NSS ERP — Tier 5 Administration security tests.

Security-focused subset extracted from tests/api/test_admin.py and
tests/api/test_sakha_branches.py:
  1. Auth-gating checks (401 without token) across admin endpoints
  2. RBAC enforcement (403 for non-admin / under-permissioned users)
  3. Self-protection guards (cannot delete/suspend own account)
  4. Password policy enforcement on admin-created users
  5. Role assignment / same-role-different-scope behaviour

These tests run against local PostgreSQL.
Requires an admin user with ADMIN_USER_MANAGE, ADMIN_USER_VIEW,
ADMIN_ROLE_MANAGE, and PERSON_MANAGE permissions.
"""

import pytest

from tests.registration_support import create_person_with_sangha_sevi


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
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()

    # Find a person with sangha_sevi but no user_account
    cur.execute("""
        SELECT p.person_pk, ss.sangha_sevi_id
        FROM nss.person p
        JOIN nss.sangha_sevi ss ON ss.person_pk = p.person_pk AND ss.is_active = TRUE
        LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
        WHERE p.is_active = TRUE
          AND ua.user_account_pk IS NULL
        ORDER BY p.created_at
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No available person for admin test user.")

    person_pk, sangha_sevi_id = row

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
    if role_row is None:
        pytest.skip("NSS_ERP_ADMIN role not found in database.")
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
def target_person_pk(write_conn):
    """
    Find a second person (without user account) to be the target
    of create-user tests.
    """
    cur = write_conn.cursor()
    cur.execute("""
        SELECT p.person_pk
        FROM nss.person p
        LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
        WHERE p.is_active = TRUE
          AND ua.user_account_pk IS NULL
        ORDER BY p.created_at
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    if row is None:
        pytest.skip("No available person for target user creation.")
    return row[0]


@pytest.fixture(scope="module")
def role_target_user_pk(write_conn):
    """
    Create a standalone user account to exercise role-assignment tests
    against.

    (The original test_admin.py version of these tests reused a user
    created earlier in the same module via a shared `_created_user_pks`
    list. Since these tests now live in their own module, they create
    their own target user instead of depending on cross-class ordering.)
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    cur.execute("""
        SELECT p.person_pk
        FROM nss.person p
        LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
        WHERE p.is_active = TRUE
          AND ua.user_account_pk IS NULL
        ORDER BY p.created_at
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No available person for role assignment test user.")
    person_pk = row[0]

    password_hash = hash_password(TARGET_PASSWORD)
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), password_hash))
    return cur.fetchone()[0]


# ── Auth-gating tests ───────────────────────────────────────────────────

class TestListUsers:
    """GET /api/v1/admin/users"""

    def test_list_users_without_auth_fails(self, client):
        """Listing users without auth returns 401."""
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401


class TestCreateUser:
    """POST /api/v1/admin/users"""

    def test_create_user_bad_password_policy(self, client, admin_headers, target_person_pk):
        """Password that violates policy returns 422."""
        # Use a different person_pk won't matter — policy check runs first
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "person_pk": "00000000-0000-0000-0000-000000000001",
                "password": "short",
            },
        )
        assert response.status_code == 422


class TestStatusChange:
    """PATCH /api/v1/admin/users/{pk}/status"""

    def test_cannot_change_own_status(self, client, admin_headers, admin_user):
        """Admin cannot change their own account status (safety)."""
        response = client.patch(
            f"/api/v1/admin/users/{admin_user['user_account_pk']}/status",
            headers=admin_headers,
            json={"account_status": "SUSPENDED"},
        )
        assert response.status_code == 422


# ── Role assignment tests ──────────────────────────────────────────────

class TestRoleAssignment:
    """POST/GET/DELETE /api/v1/admin/users/{pk}/roles"""

    def test_list_roles_for_user(self, client, admin_headers, admin_user):
        """Admin can list role assignments for a user."""
        response = client.get(
            f"/api/v1/admin/users/{admin_user['user_account_pk']}/roles",
            headers=admin_headers,
        )
        assert response.status_code == 200
        roles = response.json()
        assert isinstance(roles, list)
        assert len(roles) >= 1

    def test_assign_and_revoke_role(self, client, admin_headers, write_conn, role_target_user_pk):
        """Admin can assign a role then revoke it."""
        target_pk = role_target_user_pk

        # Find an available role (NSS_ERP_REPORT_VIEWER — lowest privilege)
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT role_code FROM nss.role_master WHERE role_code = 'NSS_ERP_REPORT_VIEWER' AND is_active = TRUE"
            )
            row = cur.fetchone()

        if row is None:
            pytest.skip("NSS_ERP_REPORT_VIEWER role not found.")

        role_code = row[0]

        # Assign role
        assign_resp = client.post(
            f"/api/v1/admin/users/{target_pk}/roles",
            headers=admin_headers,
            json={
                "role_code": role_code,
                "scope_level": "NSS-WIDE",
                "organization_pk": None,
            },
        )
        assert assign_resp.status_code == 201
        assign_data = assign_resp.json()
        assert assign_data["role_code"] == role_code
        assert assign_data["scope_level"] == "NSS-WIDE"
        assert assign_data["is_active"] is True

        user_role_pk = assign_data["user_role_pk"]

        # Verify in role list
        list_resp = client.get(
            f"/api/v1/admin/users/{target_pk}/roles",
            headers=admin_headers,
        )
        assert list_resp.status_code == 200
        active_roles = [r for r in list_resp.json() if r["is_active"]]
        assert any(r["user_role_pk"] == user_role_pk for r in active_roles)

        # Revoke role
        revoke_resp = client.delete(
            f"/api/v1/admin/users/{target_pk}/roles/{user_role_pk}",
            headers=admin_headers,
        )
        assert revoke_resp.status_code == 200

        # Verify revoked
        list_resp2 = client.get(
            f"/api/v1/admin/users/{target_pk}/roles",
            headers=admin_headers,
        )
        revoked = [r for r in list_resp2.json() if r["user_role_pk"] == user_role_pk]
        assert len(revoked) == 1
        assert revoked[0]["is_active"] is False

    def test_assign_duplicate_role_fails(self, client, admin_headers, admin_user):
        """Assigning the same role twice returns 409."""
        # Admin already has NSS_ERP_ADMIN — try assigning it again
        response = client.post(
            f"/api/v1/admin/users/{admin_user['user_account_pk']}/roles",
            headers=admin_headers,
            json={
                "role_code": "NSS_ERP_ADMIN",
                "scope_level": "NSS-WIDE",
                "organization_pk": None,
            },
        )
        assert response.status_code == 409

    def test_assign_nonexistent_role_fails(self, client, admin_headers, role_target_user_pk):
        """Assigning a role that doesn't exist returns 404."""
        target_pk = role_target_user_pk
        response = client.post(
            f"/api/v1/admin/users/{target_pk}/roles",
            headers=admin_headers,
            json={
                "role_code": "NONEXISTENT_ROLE",
                "scope_level": "NSS-WIDE",
            },
        )
        assert response.status_code == 404

    def test_non_nss_wide_requires_organization(self, client, admin_headers, role_target_user_pk):
        """Non-NSS-WIDE scope without organization_pk returns 422."""
        target_pk = role_target_user_pk
        response = client.post(
            f"/api/v1/admin/users/{target_pk}/roles",
            headers=admin_headers,
            json={
                "role_code": "NSS_ERP_SAKHA_ADMIN",
                "scope_level": "SAKHA",
                "organization_pk": None,
            },
        )
        assert response.status_code == 422


# ── RBAC enforcement tests ─────────────────────────────────────────────

class TestRBACEnforcement:
    """Verify that non-admin users cannot access admin endpoints."""

    def test_unpermissioned_user_cannot_list_users(self, client, write_conn):
        """A user without ADMIN_USER_VIEW cannot list users."""
        from api.services.auth_service import hash_password

        cur = write_conn.cursor()

        # A fresh member with no role assignments. Do not scavenge an existing
        # member: a governing-body seat holder is auto-granted admin roles.
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE LIMIT 1
        """)
        org_row = cur.fetchone()
        if org_row is None:
            pytest.skip("No active SAKHA_SANGHA organization.")
        person_pk, sangha_sevi_id = create_person_with_sangha_sevi(write_conn, org_row[0], "UNP")
        password_hash = hash_password("UnpermPass1")

        cur.execute("""
            INSERT INTO nss.user_account (
                person_pk, password_hash, account_status,
                force_password_change, password_expires_at
            ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
            RETURNING user_account_pk
        """, (str(person_pk), password_hash))
        user_pk = cur.fetchone()[0]

        # Login as unpermissioned user (no roles assigned)
        login_resp = client.post("/api/v1/auth/login", json={
            "login_id": sangha_sevi_id,
            "password": "UnpermPass1",
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Try to list users — should be 403
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        # No manual cleanup — conftest SAVEPOINT handles rollback


# ── Delete user tests ─────────────────────────────────────────────────

class TestDeleteUser:
    """DELETE /api/v1/admin/users/{pk}"""

    def test_cannot_delete_self(self, client, admin_headers, admin_user):
        """Admin cannot delete their own account (safety)."""
        response = client.delete(
            f"/api/v1/admin/users/{admin_user['user_account_pk']}",
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert "own" in response.json()["detail"].lower()

    def test_delete_user_without_auth_fails(self, client):
        """Deleting without auth returns 401."""
        response = client.delete(
            "/api/v1/admin/users/00000000-0000-0000-0000-000000000001",
        )
        assert response.status_code == 401


# ── Organization editing tests ────────────────────────────────────────

class TestCreateOrganization:
    """POST /api/v1/admin/organizations"""

    def test_create_org_without_auth_fails(self, client):
        """Creating org without auth returns 401."""
        response = client.post(
            "/api/v1/admin/organizations",
            json={
                "organization_name": "No Auth Org",
                "organization_type_code": "SAKHA_SANGHA",
            },
        )
        assert response.status_code == 401

    def test_create_org_non_admin_fails(self, client, write_conn):
        """A user without NSS_ERP_ADMIN role cannot create organizations."""
        from api.services.auth_service import hash_password

        cur = write_conn.cursor()

        # Find a person with sangha_sevi but no user_account
        cur.execute("""
            SELECT p.person_pk, ss.sangha_sevi_id
            FROM nss.person p
            JOIN nss.sangha_sevi ss ON ss.person_pk = p.person_pk AND ss.is_active = TRUE
            LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
            WHERE p.is_active = TRUE
              AND ua.user_account_pk IS NULL
            ORDER BY p.created_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No available person for non-admin org creation test.")

        person_pk, sangha_sevi_id = row
        pw = "NonAdminPass1"
        password_hash = hash_password(pw)

        cur.execute("""
            INSERT INTO nss.user_account (
                person_pk, password_hash, account_status,
                force_password_change, password_expires_at
            ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
            RETURNING user_account_pk
        """, (str(person_pk), password_hash))
        ua_pk = cur.fetchone()[0]

        # Assign SAKHA_ADMIN role (not NSS_ERP_ADMIN)
        cur.execute(
            "SELECT role_master_pk FROM nss.role_master WHERE role_code = 'NSS_ERP_SAKHA_ADMIN' AND is_active = TRUE"
        )
        role_row = cur.fetchone()
        if role_row is None:
            pytest.skip("NSS_ERP_SAKHA_ADMIN role not found.")

        cur.execute("""
            INSERT INTO nss.user_role (user_account_pk, role_master_pk)
            VALUES (%s, %s) RETURNING user_role_pk
        """, (str(ua_pk), str(role_row[0])))
        ur_pk = cur.fetchone()[0]

        # Give NSS-WIDE scope so they pass permission checks
        cur.execute("""
            INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
            VALUES (%s, 'NSS-WIDE', NULL)
        """, (str(ur_pk),))

        # Login
        login_resp = client.post("/api/v1/auth/login", json={
            "login_id": sangha_sevi_id,
            "password": pw,
        })
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed for non-admin: {login_resp.json()}")
        token = login_resp.json()["access_token"]

        # Try to create org — should be 403
        response = client.post(
            "/api/v1/admin/organizations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "organization_name": "Non Admin Org",
                "organization_type_code": "SAKHA_SANGHA",
            },
        )
        assert response.status_code == 403


class TestUpdateOrganization:
    """PATCH /api/v1/admin/organizations/{pk}"""

    def test_update_org_without_auth_fails(self, client):
        """Updating org without auth returns 401."""
        response = client.patch(
            "/api/v1/admin/organizations/00000000-0000-0000-0000-000000000001",
            json={"organization_name": "No Auth"},
        )
        assert response.status_code == 401


# ── Short-code update tests ──────────────────────────────────────────

class TestUpdateShortCode:
    """PATCH /api/v1/admin/organizations/{pk}/short-code"""

    def test_short_code_without_auth(self, client):
        """Updating short_code without auth returns 401."""
        response = client.patch(
            "/api/v1/admin/organizations/00000000-0000-0000-0000-000000000001/short-code",
            json={"short_code": "ABC"},
        )
        assert response.status_code == 401


# ── Same-role-different-scope tests ──────────────────────────────────

class TestSameRoleDifferentScope:
    """Assign the same role to a user with different org scopes."""

    def test_same_role_different_org_scope(self, client, admin_headers, write_conn):
        """User can hold SAKHA_ADMIN for two different organizations."""
        from api.services.auth_service import hash_password

        cur = write_conn.cursor()

        # Find a person with sangha_sevi but no user_account
        cur.execute("""
            SELECT p.person_pk, ss.sangha_sevi_id
            FROM nss.person p
            JOIN nss.sangha_sevi ss ON ss.person_pk = p.person_pk AND ss.is_active = TRUE
            LEFT JOIN nss.user_account ua ON ua.person_pk = p.person_pk AND ua.is_active = TRUE
            WHERE p.is_active = TRUE
              AND ua.user_account_pk IS NULL
            ORDER BY p.created_at
            LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No available person for same-role-different-scope test.")

        person_pk = row[0]

        # Create user account
        pw_hash = hash_password(TARGET_PASSWORD)
        cur.execute("""
            INSERT INTO nss.user_account (
                person_pk, password_hash, account_status,
                force_password_change, password_expires_at
            ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
            RETURNING user_account_pk
        """, (str(person_pk), pw_hash))
        ua_pk = str(cur.fetchone()[0])

        # Find two different SAKHA_SANGHA organizations
        cur.execute("""
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA'
              AND o.is_active = TRUE
            ORDER BY o.created_at
            LIMIT 2
        """)
        org_rows = cur.fetchall()
        if len(org_rows) < 2:
            pytest.skip("Need at least 2 SAKHA_SANGHA orgs for this test.")

        org1_pk = str(org_rows[0][0])
        org2_pk = str(org_rows[1][0])

        # Assign SAKHA_ADMIN for org1
        resp1 = client.post(
            f"/api/v1/admin/users/{ua_pk}/roles",
            headers=admin_headers,
            json={
                "role_code": "NSS_ERP_SAKHA_ADMIN",
                "scope_level": "SAKHA",
                "organization_pk": org1_pk,
            },
        )
        assert resp1.status_code == 201, f"First assignment failed: {resp1.json()}"

        # Assign same role for org2 (different scope)
        resp2 = client.post(
            f"/api/v1/admin/users/{ua_pk}/roles",
            headers=admin_headers,
            json={
                "role_code": "NSS_ERP_SAKHA_ADMIN",
                "scope_level": "SAKHA",
                "organization_pk": org2_pk,
            },
        )
        assert resp2.status_code == 201, f"Second assignment failed: {resp2.json()}"

        # Verify both roles are active
        list_resp = client.get(
            f"/api/v1/admin/users/{ua_pk}/roles",
            headers=admin_headers,
        )
        assert list_resp.status_code == 200
        active_sakha = [
            r for r in list_resp.json()
            if r["is_active"] and r["role_code"] == "NSS_ERP_SAKHA_ADMIN"
        ]
        assert len(active_sakha) >= 2, (
            f"Expected at least 2 SAKHA_ADMIN roles, got {len(active_sakha)}"
        )

        # Verify the two assignments have different org scopes
        org_pks = {r.get("organization_pk") for r in active_sakha}
        assert org1_pk in org_pks
        assert org2_pk in org_pks

    def test_same_role_same_scope_duplicate_fails(self, client, admin_headers, admin_user):
        """Assigning identical role + scope combo returns 409."""
        # Admin already has NSS_ERP_ADMIN + NSS-WIDE — try the exact same combo
        response = client.post(
            f"/api/v1/admin/users/{admin_user['user_account_pk']}/roles",
            headers=admin_headers,
            json={
                "role_code": "NSS_ERP_ADMIN",
                "scope_level": "NSS-WIDE",
                "organization_pk": None,
            },
        )
        assert response.status_code == 409
