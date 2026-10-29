"""
NSS ERP — Security tests for GET /organization/organizations/{pk}/stats.

The org-stats endpoint scopes to the *requested* org's subtree (not the
viewer's own scope), so it must enforce ADMIN-BR-076: a scoped admin may
read stats for an org inside their scope subtree, but requesting stats for
an org OUTSIDE that subtree is rejected with 403 (via require_org_in_scope).

The 404-before-403 ordering is deliberate — a non-existent org is reported
as 404 regardless of scope, so scope membership of unknown orgs isn't
leaked. Anonymous callers are rejected by the ORGANIZATION_VIEW gate first.

Runs against local PostgreSQL through the shared TestClient/SAVEPOINT
conftest (like the rest of tests/security/). Self-contained: builds its own
Sakha-scoped admin rather than depending on tests/api fixtures.
"""

from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration

BASE = "/api/v1/organization"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"
SCOPED_ADMIN_PASSWORD = "ScopeAdmin1"


@pytest.fixture(scope="module")
def two_sakhas(write_conn):
    """Two distinct active SAKHA_SANGHA org PKs (in scope vs. out of scope)."""
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
def sakha_admin_headers(client, write_conn, two_sakhas):
    """A NSS_ERP_SAKHA_ADMIN scoped to exactly one Sakha (two_sakhas[0]).

    NSS_ERP_SAKHA_ADMIN carries ORGANIZATION_VIEW, so the permission gate
    passes and the request reaches the scope check — exactly what we want to
    exercise here (permission-403 vs scope-403 would be indistinguishable
    otherwise).
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
    """, (f"TSTA{suffix}", "TestStatsAdmin", suffix, f"tsta.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    ss_id = f"TSSTA{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (ss_id, str(person_pk), str(mtype), str(mstatus), two_sakhas[0]))

    cur.execute("""
        INSERT INTO nss.user_account (person_pk, password_hash, account_status,
            force_password_change, password_expires_at)
        VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), hash_password(SCOPED_ADMIN_PASSWORD)))
    ua_pk = cur.fetchone()[0]

    cur.execute(
        "SELECT role_master_pk FROM nss.role_master "
        "WHERE role_code='NSS_ERP_SAKHA_ADMIN' AND is_active=TRUE"
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

    resp = client.post(
        "/api/v1/auth/login",
        json={"login_id": ss_id, "password": SCOPED_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Sakha admin login failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestOrgStatsScopeEnforcement:
    """ADMIN-BR-076: /stats honours the viewer's scope subtree."""

    def test_in_scope_org_returns_200(self, client, sakha_admin_headers, two_sakhas):
        """The admin's own Sakha (in scope) is readable."""
        r = client.get(
            f"{BASE}/organizations/{two_sakhas[0]}/stats",
            headers=sakha_admin_headers,
        )
        assert r.status_code == 200, r.json()
        assert r.json()["organization_pk"] == two_sakhas[0]

    def test_out_of_scope_org_returns_403(self, client, sakha_admin_headers, two_sakhas):
        """A sibling Sakha outside the admin's scope is rejected."""
        if len(two_sakhas) < 2:
            pytest.skip("Need a second Sakha to test out-of-scope rejection.")
        r = client.get(
            f"{BASE}/organizations/{two_sakhas[1]}/stats",
            headers=sakha_admin_headers,
        )
        assert r.status_code == 403, r.json()

    def test_nonexistent_org_returns_404_not_403(self, client, sakha_admin_headers):
        """Unknown org is 404 (existence checked before scope) — scope
        membership of unknown orgs is not leaked."""
        r = client.get(
            f"{BASE}/organizations/{FAKE_UUID}/stats",
            headers=sakha_admin_headers,
        )
        assert r.status_code == 404, r.json()

    def test_anonymous_is_rejected(self, anon_client, two_sakhas):
        """No token → rejected by the ORGANIZATION_VIEW gate (401/403),
        never reaching the data."""
        if not two_sakhas:
            pytest.skip("No SAKHA_SANGHA org available.")
        r = anon_client.get(f"{BASE}/organizations/{two_sakhas[0]}/stats")
        assert r.status_code in (401, 403)


class TestOrgWingsScopeEnforcement:
    """
    ADMIN-BR-076 for the two wing endpoints, which call the same
    require_org_in_scope() as /stats but were never covered: a scoped admin
    may read wings / the wing roster for an org in scope and gets 403 for a
    sibling Sakha. 404 still precedes 403.
    """

    WING_PATHS = ("wings", "wings/MAHILA_SANGHA/members")

    @pytest.mark.parametrize("suffix", WING_PATHS)
    def test_in_scope_org_returns_200(self, client, sakha_admin_headers, two_sakhas, suffix):
        r = client.get(
            f"{BASE}/organizations/{two_sakhas[0]}/{suffix}",
            headers=sakha_admin_headers,
        )
        assert r.status_code == 200, r.json()

    @pytest.mark.parametrize("suffix", WING_PATHS)
    def test_out_of_scope_org_returns_403(self, client, sakha_admin_headers, two_sakhas, suffix):
        if len(two_sakhas) < 2:
            pytest.skip("Need a second Sakha to test out-of-scope rejection.")
        r = client.get(
            f"{BASE}/organizations/{two_sakhas[1]}/{suffix}",
            headers=sakha_admin_headers,
        )
        assert r.status_code == 403, r.json()

    @pytest.mark.parametrize("suffix", WING_PATHS)
    def test_nonexistent_org_returns_404_not_403(self, client, sakha_admin_headers, suffix):
        r = client.get(
            f"{BASE}/organizations/{FAKE_UUID}/{suffix}",
            headers=sakha_admin_headers,
        )
        assert r.status_code == 404, r.json()
