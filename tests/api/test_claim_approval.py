"""
NSS ERP — Claim Approval router coverage (api/routers/claim_approval.py).

This router previously had NO dedicated test file — its GET detail,
PATCH edit, and scope-enforcement paths were entirely untested (only
list/approve/reject happy-paths were covered indirectly via
tests/api/test_registration.py::TestClaimApproval). This file closes
that gap.

Endpoints covered here that were previously untested:
  GET   /api/v1/admin/claims/{pk}            — detail (found, 404, scope-denied)
  PATCH /api/v1/admin/claims/{pk}             — edit (success, non-pending, scope-denied)
  POST  /api/v1/admin/claims/{pk}/approve     — non-Darshaka new-SS path,
                                                 non-Darshaka existing-SS linking,
                                                 Darshak attendance affiliation,
                                                 scope-denied
  POST  /api/v1/admin/claims/{pk}/reject      — scope-denied

Auth-gating (401/unauthenticated) and other pure security assertions for
this router live in tests/security/ — this file focuses on business-logic
and scoping correctness for authenticated, permitted-but-out-of-scope
and in-scope admins.

NOTE: cleanup is automatic via transaction rollback in conftest.py.
"""

import pytest
from uuid import uuid4

from tests.registration_support import (
    create_person_with_sangha_sevi,
    non_darshaka_credential_number,
    registration_address,
)


pytestmark = pytest.mark.integration


# ── Test constants ──────────────────────────────────────────────────────

TEST_PASSWORD = "TestClaim1x"
SCOPED_PASSWORD = "ScopedClaim1x"
TEST_DOB = "2000-01-15"
_RUN_ID = uuid4().hex[:8]
TEST_EMAIL_PREFIX = f"claimtest_{_RUN_ID}_"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_tokens(client, write_conn):
    """NSS-WIDE admin with MEMBERSHIP_APPROVE / ADMIN_USER_MANAGE."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT ua.user_account_pk, ss.sangha_sevi_id
        FROM nss.user_account ua
        JOIN nss.person p ON p.person_pk = ua.person_pk
        JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk AND ss.is_active = TRUE
        JOIN nss.user_role ur ON ur.user_account_pk = ua.user_account_pk AND ur.is_active = TRUE
        JOIN nss.role_permission rp ON rp.role_master_pk = ur.role_master_pk AND rp.is_active = TRUE
        JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
        JOIN nss.admin_scope asc2 ON asc2.user_role_pk = ur.user_role_pk
                                   AND asc2.is_active = TRUE
                                   AND asc2.scope_level = 'NSS-WIDE'
        WHERE ua.is_active = TRUE
          AND ua.account_status = 'ACTIVE'
          AND pm.permission_code IN ('MEMBERSHIP_APPROVE', 'ADMIN_USER_MANAGE')
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No NSS-WIDE admin with MEMBERSHIP_APPROVE. Cannot run claim tests.")
    admin_pk, sevi_id = row

    from api.services.auth_service import hash_password
    cur.execute("""
        UPDATE nss.user_account
        SET password_hash = %s, password_changed_at = NOW(),
            password_expires_at = NOW() + INTERVAL '365 days'
        WHERE user_account_pk = %s
    """, (hash_password(TEST_PASSWORD), str(admin_pk)))

    response = client.post("/api/v1/auth/login", json={
        "login_id": sevi_id, "password": TEST_PASSWORD,
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.json()}")

    return {
        "access_token": response.json()["access_token"],
        "user_account_pk": str(admin_pk),
    }


@pytest.fixture(scope="module")
def sakha_orgs(write_conn):
    """
    Two distinct active SAKHA_SANGHA orgs, for scope-boundary tests.

    Approval of a non-Darshaka claim requires the org to have a
    short_code assigned (compose_local_sakha_erp_id enforces this).
    In this dev DB NONE of the seeded SAKHA_SANGHA orgs have a
    short_code set yet (a real, separate operational gap — every
    non-Darshaka claim approval will 422 until an admin sets one via
    the org short-code endpoint). We assign synthetic short codes here,
    scoped to this test transaction only (rolled back by conftest's
    module SAVEPOINT), so this test doesn't depend on that being fixed.
    """
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk, o.short_code
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.created_at
        LIMIT 2
    """)
    rows = cur.fetchall()
    if len(rows) < 2:
        pytest.skip("Need at least two active SAKHA_SANGHA organizations for scope tests.")

    org_a, sc_a = str(rows[0][0]), rows[0][1]
    org_b, sc_b = str(rows[1][0]), rows[1][1]

    if not sc_a:
        cur.execute("UPDATE nss.organization SET short_code = 'TSTA' WHERE organization_pk = %s", (org_a,))
        sc_a = "TSTA"
    if not sc_b:
        cur.execute("UPDATE nss.organization SET short_code = 'TSTB' WHERE organization_pk = %s", (org_b,))
        sc_b = "TSTB"

    return {"org_a": org_a, "org_b": org_b}


@pytest.fixture(scope="module")
def scoped_admin_tokens(write_conn, client, sakha_orgs):
    """
    A SAKHA_ADMIN scoped ONLY to org_b (not org_a) — used to prove
    claim endpoints correctly deny access to out-of-scope organizations.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    # A dedicated, freshly created person + Sangha Sevi in org_b (scavenging an
    # existing member may pick a governing-body seat holder with global reach).
    person_pk, sevi_id = create_person_with_sangha_sevi(write_conn, sakha_orgs["org_b"], "SCA")

    pw_hash = hash_password(SCOPED_PASSWORD)
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), pw_hash))
    ua_pk = cur.fetchone()[0]

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

    # Scope to org_b ONLY — org_a must be out of scope for this admin.
    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, 'SAKHA', %s)
    """, (str(ur_pk), sakha_orgs["org_b"]))

    response = client.post("/api/v1/auth/login", json={
        "login_id": sevi_id, "password": SCOPED_PASSWORD,
    })
    if response.status_code != 200:
        pytest.skip(f"Scoped admin login failed: {response.json()}")

    return {"access_token": response.json()["access_token"]}


@pytest.fixture(scope="module")
def darshaka_type_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'PROBATIONARY'
          AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No PROBATIONARY membership type found.")
    return str(row[0])


@pytest.fixture(scope="module")
def non_darshaka_type_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code != 'PROBATIONARY'
          AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No non-Darshaka membership type found.")
    return str(row[0])


@pytest.fixture(scope="module")
def gender_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'GENDER' AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No GENDER master data found.")
    return str(row[0])


# Mandatory address block for POST /register, resolved once per module by the
# autouse fixture below (the helper functions here take no fixtures).
_REGISTER_ADDRESS: dict = {}


@pytest.fixture(scope="module", autouse=True)
def _register_address(write_conn):
    _REGISTER_ADDRESS.update(registration_address(write_conn.cursor()))


def _register(client, email_suffix, gender_pk, org_pk, membership_type_pk,
              local_sakha_number=None, darshak_org_pk=None, darshak_local_sakha_number=None,
              last_name="Test", credential_number=None):
    payload = {
        **_REGISTER_ADDRESS,
        "first_name": "ClaimApproval",
        "last_name": last_name,
        "date_of_birth": TEST_DOB,
        "gender_master_data_pk": gender_pk,
        "email": f"{TEST_EMAIL_PREFIX}{email_suffix}@test.example",
        "password": TEST_PASSWORD,
        "has_membership": True,
        "membership_type_master_data_pk": membership_type_pk,
        "organization_pk": org_pk,
        # Local Sakha Number is required for every membership type, incl.
        # Darshaka (AUTH-BR-086) — not validated at registration, so any
        # non-empty default is fine for callers that don't care about the
        # exact value. Must still be unique per call: unlike before this
        # requirement existed, every registration now actually composes
        # into nss.membership_sakha_affiliation's local_sakha_erp_id on
        # approval, which is UNIQUE per (organization_pk, local_sakha_erp_id)
        # — a fixed default would collide across the many registrations
        # this module-scoped test class approves against the same org.
        "claimed_local_sakha_number": local_sakha_number or uuid4().hex[:6],
    }
    if credential_number:
        # Required for every membership type except Darshaka (registration.py 3d).
        payload["claimed_credential_document_number"] = credential_number
    if darshak_org_pk:
        payload["is_attending_as_darshak"] = True
        payload["darshak_organization_pk"] = darshak_org_pk
        payload["darshak_local_sakha_number"] = darshak_local_sakha_number or uuid4().hex[:6]
    resp = client.post("/api/v1/register", json=payload)
    assert resp.status_code == 201, f"Registration failed: {resp.json()}"
    return resp.json()


def _pending_claim_pk(write_conn, person_pk):
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT registration_claim_pk FROM nss.registration_claim "
            "WHERE person_pk = %s AND claim_status = 'PENDING'",
            (person_pk,),
        )
        return str(cur.fetchone()[0])


# ── GET /api/v1/admin/claims/{pk} — detail ──────────────────────────────

class TestClaimDetail:

    def test_get_claim_detail_success(self, client, admin_tokens, sakha_orgs,
                                       darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "detailok", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.get(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["registration_claim_pk"] == claim_pk
        assert data["person_pk"] == person["person_pk"]
        assert data["claim_status"] == "PENDING"
        assert data["claimed_organization_pk"] == sakha_orgs["org_a"]

    def test_get_claim_detail_not_found(self, client, admin_tokens):
        resp = client.get(
            "/api/v1/admin/claims/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        )
        assert resp.status_code == 404

    def test_get_claim_detail_scope_denied(self, client, scoped_admin_tokens, sakha_orgs,
                                            darshaka_type_pk, gender_pk, write_conn):
        """Admin scoped to org_b cannot view a claim filed against org_a."""
        person = _register(client, "detailscope", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.get(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {scoped_admin_tokens['access_token']}"},
        )
        assert resp.status_code == 403


# ── PATCH /api/v1/admin/claims/{pk} — edit ──────────────────────────────

class TestUpdateClaim:

    def test_update_claim_success(self, client, admin_tokens, sakha_orgs,
                                   darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "editok", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.patch(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={"first_name": "Edited", "admin_remarks_ignored": "n/a"},
        )
        assert resp.status_code == 200, f"Update failed: {resp.json()}"

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT first_name FROM nss.person WHERE person_pk = %s",
                (person["person_pk"],),
            )
            # helper title-cases input
            assert cur.fetchone()[0] == "Edited"

    def test_update_claim_not_pending_fails(self, client, admin_tokens, sakha_orgs,
                                             darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "editnotpending", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        # Approve it first so it's no longer PENDING
        approve_resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert approve_resp.status_code == 200

        resp = client.patch(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={"first_name": "ShouldFail"},
        )
        assert resp.status_code == 422
        assert "cannot edit" in resp.json()["detail"].lower()

    def test_update_claim_scope_denied(self, client, scoped_admin_tokens, sakha_orgs,
                                        darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "editscope", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.patch(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {scoped_admin_tokens['access_token']}"},
            json={"first_name": "ShouldBeDenied"},
        )
        assert resp.status_code == 403


# ── POST .../approve — non-Darshaka + Darshak-affiliation paths ────────

class TestApproveNonDarshakaAndDarshak:

    def test_approve_non_darshaka_creates_new_sangha_sevi(
        self, client, admin_tokens, sakha_orgs, non_darshaka_type_pk, gender_pk, write_conn
    ):
        """Non-Darshaka claim with a local sakha number and no prior SS record
        creates a brand-new sangha_sevi row on approval."""
        local_number = f"LN{uuid4().hex[:6]}"
        person = _register(
            client, "nondarshnew", gender_pk, sakha_orgs["org_a"], non_darshaka_type_pk,
            local_sakha_number=local_number,
            credential_number=non_darshaka_credential_number(),
        )
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert resp.status_code == 200, f"Approve failed: {resp.json()}"
        data = resp.json()
        assert data["sangha_sevi_id"] is not None

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
                (person["person_pk"],),
            )
            ss_row = cur.fetchone()
            assert ss_row is not None

            cur.execute(
                "SELECT membership_sakha_affiliation_pk FROM nss.membership_sakha_affiliation "
                "WHERE sangha_sevi_pk = %s AND organization_pk = %s",
                (str(ss_row[0]), sakha_orgs["org_a"]),
            )
            assert cur.fetchone() is not None

    def test_approve_non_darshaka_links_existing_sangha_sevi(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, non_darshaka_type_pk,
        gender_pk, write_conn
    ):
        """If the claimant already has an active sangha_sevi record (e.g. from
        a prior Darshaka approval), a second non-Darshaka claim links to it
        instead of creating a duplicate SS row."""
        # First: approve a Darshaka claim to give this person an active SS record.
        person = _register(client, "existingss", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        first_claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        first_approve = client.post(
            f"/api/v1/admin/claims/{first_claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert first_approve.status_code == 200
        original_ss_id = first_approve.json()["sangha_sevi_id"]

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
                (person["person_pk"],),
            )
            ss_pk_before = str(cur.fetchone()[0])

            # Manually create a second PENDING claim for the SAME person against
            # a non-Darshaka membership type, to exercise the "existing SS" branch
            # of approve_claim without going through a second /register call
            # (registration doesn't allow re-registering the same active user).
            cur.execute(
                "SELECT user_account_pk FROM nss.user_account WHERE person_pk = %s",
                (person["person_pk"],),
            )
            ua_pk = str(cur.fetchone()[0])
            local_number = f"LN{uuid4().hex[:6]}"
            cur.execute(
                """
                INSERT INTO nss.registration_claim (
                    user_account_pk, person_pk, claimed_organization_pk,
                    claimed_membership_type_master_data_pk,
                    claimed_local_sakha_number, claim_status
                ) VALUES (%s, %s, %s, %s, %s, 'PENDING')
                RETURNING registration_claim_pk
                """,
                (ua_pk, person["person_pk"], sakha_orgs["org_a"], non_darshaka_type_pk, local_number),
            )
            second_claim_pk = str(cur.fetchone()[0])

        second_approve = client.post(
            f"/api/v1/admin/claims/{second_claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert second_approve.status_code == 200, f"Second approve failed: {second_approve.json()}"
        assert second_approve.json()["sangha_sevi_id"] == original_ss_id, (
            "Approving a second claim for a person who already has an active "
            "sangha_sevi record must link to the existing record, not create a new one."
        )

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
                (person["person_pk"],),
            )
            assert cur.fetchone()[0] == 1, "Must not create a duplicate active sangha_sevi row."

    def test_approve_darshak_creates_attendance_affiliation(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        """Approving a claim with darshak_organization_pk set must create a
        SECOND membership_sakha_affiliation row at the darshak org, in
        addition to the primary affiliation at the claimed org.

        Previously always failed silently: uq_mem_sakha_aff_active was
        (sangha_sevi_pk) alone, so this INSERT's ON CONFLICT DO NOTHING
        always matched the primary affiliation's slot for the same
        sangha_sevi_pk and the darshak row never persisted. Narrowed to
        (sangha_sevi_pk, organization_pk) in
        database/ddl/05_membership/06_membership_sakha_affiliation.sql —
        a member's home affiliation and a darshak attendance affiliation
        at a different org are no longer mutually exclusive."""
        person = _register(
            client, "darshakatt", gender_pk, sakha_orgs["org_a"], darshaka_type_pk,
            darshak_org_pk=sakha_orgs["org_b"],
        )
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert resp.status_code == 200, f"Approve failed: {resp.json()}"

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
                (person["person_pk"],),
            )
            ss_pk = str(cur.fetchone()[0])

            cur.execute(
                "SELECT organization_pk FROM nss.membership_sakha_affiliation WHERE sangha_sevi_pk = %s",
                (ss_pk,),
            )
            org_pks = {str(r[0]) for r in cur.fetchall()}
            assert sakha_orgs["org_a"] in org_pks, "Primary affiliation at claimed org missing."
            assert sakha_orgs["org_b"] in org_pks, "Darshak attendance affiliation at darshak org missing."


class TestApproveRequiresLocalSakhaNumber:
    """AUTH-BR-086: the Local Sakha Number is required for non-Darshaka claims and
    optional for Darshaka. A PENDING claim's number can be blanked via PATCH before
    approval, so approve_claim must handle both cases: reject for non-Darshaka,
    mint the next Darshak-namespace number (MBR-030C / MBR-048) for Darshaka."""

    def test_approve_darshaka_without_local_number_auto_generates_it(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "darkblank", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        patch_resp = client.patch(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={"claimed_local_sakha_number": ""},
        )
        assert patch_resp.status_code == 200, f"Blanking number failed: {patch_resp.json()}"

        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert resp.status_code == 200, resp.json()

        with write_conn.cursor() as cur:
            cur.execute("""
                SELECT msa.local_sakha_erp_id, o.short_code
                FROM nss.membership_sakha_affiliation msa
                JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = msa.sangha_sevi_pk
                JOIN nss.organization o ON o.organization_pk = msa.organization_pk
                WHERE ss.person_pk = %s AND msa.organization_pk = %s
            """, (person["person_pk"], sakha_orgs["org_a"]))
            local_id, short_code = cur.fetchone()
        # <short_code><Darshak marker><sequence> — never the bare Regular namespace.
        assert local_id.startswith(short_code) and local_id[len(short_code):].strip("0123456789") != ""
        assert local_id[-1].isdigit()

    def test_approve_non_darshaka_without_local_number_fails(
        self, client, admin_tokens, sakha_orgs, non_darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(
            client, "regblank", gender_pk, sakha_orgs["org_a"], non_darshaka_type_pk,
            credential_number=non_darshaka_credential_number(),
        )
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        client.patch(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={"claimed_local_sakha_number": ""},
        )
        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert resp.status_code == 422
        assert "Local Sakha Number" in resp.json()["detail"]

    def test_approve_darshak_attendance_without_darshak_local_number_fails(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(
            client, "darkattblank", gender_pk, sakha_orgs["org_a"], darshaka_type_pk,
            darshak_org_pk=sakha_orgs["org_b"],
        )
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        patch_resp = client.patch(
            f"/api/v1/admin/claims/{claim_pk}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={"darshak_local_sakha_number": ""},
        )
        assert patch_resp.status_code == 200, f"Blanking darshak number failed: {patch_resp.json()}"

        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert resp.status_code == 422
        assert "darshak_local_sakha_number" in resp.json()["detail"] or "Darshak Sakha" in resp.json()["detail"]


# ── Scope enforcement on approve/reject ─────────────────────────────────

class TestApproveRejectScopeDenied:

    def test_approve_scope_denied(self, client, scoped_admin_tokens, sakha_orgs,
                                   darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "approvescope", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {scoped_admin_tokens['access_token']}"},
            json={},
        )
        assert resp.status_code == 403

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT claim_status FROM nss.registration_claim WHERE registration_claim_pk = %s",
                (claim_pk,),
            )
            assert cur.fetchone()[0] == "PENDING", "Denied approval must not mutate claim status."

    def test_reject_scope_denied(self, client, scoped_admin_tokens, sakha_orgs,
                                  darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "rejectscope", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])

        resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/reject",
            headers={"Authorization": f"Bearer {scoped_admin_tokens['access_token']}"},
            json={"admin_remarks": "Attempted denial"},
        )
        assert resp.status_code == 403

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT claim_status FROM nss.registration_claim WHERE registration_claim_pk = %s",
                (claim_pk,),
            )
            assert cur.fetchone()[0] == "PENDING", "Denied rejection must not mutate claim status."


# ── Remaining endpoint x edge-case matrix (list / 404 / state guards) ────

def _auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


class TestClaimList:
    """GET /api/v1/admin/claims"""

    URL = "/api/v1/admin/claims"

    def test_list_shape_and_default_is_pending(self, client, admin_tokens, sakha_orgs,
                                                darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "listshape", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        resp = client.get(self.URL, headers=_auth(admin_tokens), params={"page_size": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert {"claims", "total", "page", "page_size"} <= data.keys()
        assert all(c["claim_status"] == "PENDING" for c in data["claims"])
        assert person["person_pk"] in {c["person_pk"] for c in data["claims"]} or data["total"] > 100

    def test_status_filter_separates_pending_and_rejected(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "listrej", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        assert client.post(f"{self.URL}/{claim_pk}/reject", headers=_auth(admin_tokens),
                           json={"admin_remarks": "list filter test"}).status_code == 200

        rejected = client.get(self.URL, headers=_auth(admin_tokens),
                              params={"claim_status": "REJECTED", "page_size": 100}).json()
        pending = client.get(self.URL, headers=_auth(admin_tokens),
                             params={"claim_status": "PENDING", "page_size": 100}).json()
        assert claim_pk in {c["registration_claim_pk"] for c in rejected["claims"]}
        assert claim_pk not in {c["registration_claim_pk"] for c in pending["claims"]}

    @pytest.mark.parametrize("params", [
        {"claim_status": "BOGUS"}, {"claim_status": "pending"},
        {"page": 0}, {"page_size": 0}, {"page_size": 101},
    ])
    def test_invalid_query_is_422(self, client, admin_tokens, params):
        assert client.get(self.URL, headers=_auth(admin_tokens), params=params).status_code == 422

    @pytest.mark.parametrize("sort_by", ["person_name", "organization_name", "created_at"])
    def test_whitelisted_sort_columns_work(self, client, admin_tokens, sort_by):
        resp = client.get(self.URL, headers=_auth(admin_tokens),
                          params={"sort_by": sort_by, "sort_dir": "desc"})
        assert resp.status_code == 200

    def test_scoped_admin_list_is_bounded_to_scope(
        self, client, scoped_admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        """ADMIN-BR-076: a Sakha admin scoped to org_b lists org_b's claims, never org_a's."""
        mine = _register(client, "listscope_b", gender_pk, sakha_orgs["org_b"], darshaka_type_pk)
        theirs = _register(client, "listscope_a", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        data = client.get(self.URL, headers=_auth(scoped_admin_tokens),
                          params={"page_size": 100}).json()
        listed = {c["person_pk"] for c in data["claims"]}
        assert mine["person_pk"] in listed
        assert theirs["person_pk"] not in listed
        assert all(c["claimed_organization_pk"] == sakha_orgs["org_b"] for c in data["claims"])


class TestClaimNotFoundAndStateGuards:

    UNKNOWN = "00000000-0000-0000-0000-0000000000cc"

    def test_update_unknown_claim_is_404(self, client, admin_tokens):
        resp = client.patch(f"/api/v1/admin/claims/{self.UNKNOWN}", headers=_auth(admin_tokens),
                            json={"claimed_local_sakha_number": "X1"})
        assert resp.status_code == 404

    def test_approve_unknown_claim_is_404(self, client, admin_tokens):
        resp = client.post(f"/api/v1/admin/claims/{self.UNKNOWN}/approve",
                           headers=_auth(admin_tokens), json={})
        assert resp.status_code == 404

    def test_reject_unknown_claim_is_404(self, client, admin_tokens):
        resp = client.post(f"/api/v1/admin/claims/{self.UNKNOWN}/reject",
                           headers=_auth(admin_tokens), json={"admin_remarks": "nope"})
        assert resp.status_code == 404

    @pytest.mark.parametrize("method,suffix", [("get", ""), ("patch", ""),
                                               ("post", "/approve"), ("post", "/reject")])
    def test_malformed_claim_pk_is_422(self, client, admin_tokens, method, suffix):
        kwargs = {"headers": _auth(admin_tokens)}
        if method != "get":
            kwargs["json"] = {"admin_remarks": "x"} if suffix == "/reject" else {}
        resp = getattr(client, method)(f"/api/v1/admin/claims/not-a-uuid{suffix}", **kwargs)
        assert resp.status_code == 422

    def test_reject_twice_is_422(self, client, admin_tokens, sakha_orgs, darshaka_type_pk,
                                  gender_pk, write_conn):
        person = _register(client, "rejtwice", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        url = f"/api/v1/admin/claims/{claim_pk}/reject"
        assert client.post(url, headers=_auth(admin_tokens), json={"admin_remarks": "first"}).status_code == 200
        again = client.post(url, headers=_auth(admin_tokens), json={"admin_remarks": "second"})
        assert again.status_code == 422
        assert "already REJECTED" in again.json()["detail"]

    def test_approve_rejected_claim_is_422(self, client, admin_tokens, sakha_orgs, darshaka_type_pk,
                                            gender_pk, write_conn):
        person = _register(client, "apprejected", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        client.post(f"/api/v1/admin/claims/{claim_pk}/reject", headers=_auth(admin_tokens),
                    json={"admin_remarks": "no"})
        resp = client.post(f"/api/v1/admin/claims/{claim_pk}/approve", headers=_auth(admin_tokens), json={})
        assert resp.status_code == 422
        assert "already REJECTED" in resp.json()["detail"]

    def test_reject_requires_non_empty_remarks(self, client, admin_tokens, sakha_orgs,
                                                darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "rejblank", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        resp = client.post(f"/api/v1/admin/claims/{claim_pk}/reject", headers=_auth(admin_tokens),
                           json={"admin_remarks": ""})
        assert resp.status_code == 422
        assert _claim_status(write_conn, claim_pk) == "PENDING"

    def test_approve_marks_claim_and_activates_account(self, client, admin_tokens, sakha_orgs,
                                                        darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "apprflow", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        resp = client.post(f"/api/v1/admin/claims/{claim_pk}/approve", headers=_auth(admin_tokens),
                           json={"admin_remarks": "verified"})
        assert resp.status_code == 200, resp.json()
        assert _claim_status(write_conn, claim_pk) == "APPROVED"
        # The approved member can now log in with the Sangha Sevi ID the approval minted.
        login = client.post("/api/v1/auth/login", json={
            "login_id": resp.json()["sangha_sevi_id"], "password": TEST_PASSWORD,
        })
        assert login.status_code == 200, login.json()

    def test_update_claim_edits_person_contact_and_validates_email(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "editcontact", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        url = f"/api/v1/admin/claims/{claim_pk}"

        bad = client.patch(url, headers=_auth(admin_tokens), json={"email": "not-an-email"})
        assert bad.status_code == 422

        new_email = f"{TEST_EMAIL_PREFIX}edited@test.example"
        ok = client.patch(url, headers=_auth(admin_tokens),
                          json={"email": new_email.upper(), "first_name": "  fixedname "})
        assert ok.status_code == 200
        with write_conn.cursor() as cur:
            cur.execute("SELECT email, first_name FROM nss.person WHERE person_pk = %s",
                        (person["person_pk"],))
            assert cur.fetchone() == (new_email, "Fixedname")

    def test_update_claim_empty_body_is_a_harmless_noop(self, client, admin_tokens, sakha_orgs,
                                                         darshaka_type_pk, gender_pk, write_conn):
        person = _register(client, "editnoop", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        resp = client.patch(f"/api/v1/admin/claims/{claim_pk}", headers=_auth(admin_tokens), json={})
        assert resp.status_code == 200
        assert _claim_status(write_conn, claim_pk) == "PENDING"


def _claim_status(write_conn, claim_pk):
    with write_conn.cursor() as cur:
        cur.execute("SELECT claim_status FROM nss.registration_claim WHERE registration_claim_pk = %s",
                    (claim_pk,))
        return cur.fetchone()[0]


class TestClaimRepointAndResubmit:
    """ADMIN-BR-076 / MBR-038A on claim edits, and AUTH-BR-093 resubmission."""

    def test_scoped_admin_cannot_repoint_claim_to_out_of_scope_org(
        self, client, scoped_admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "repoint", gender_pk, sakha_orgs["org_b"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        resp = client.patch(f"/api/v1/admin/claims/{claim_pk}", headers=_auth(scoped_admin_tokens),
                            json={"claimed_organization_pk": sakha_orgs["org_a"]})
        assert resp.status_code == 403
        with write_conn.cursor() as cur:
            cur.execute("SELECT claimed_organization_pk FROM nss.registration_claim "
                        "WHERE registration_claim_pk = %s", (claim_pk,))
            assert str(cur.fetchone()[0]) == sakha_orgs["org_b"]

    def test_claim_cannot_be_repointed_to_a_non_sakha_org(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "repointns", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        with write_conn.cursor() as cur:
            cur.execute("""
                SELECT o.organization_pk FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE md.value_code NOT IN ('SAKHA_SANGHA', 'SAKHA_ASANA') AND o.is_active = TRUE LIMIT 1
            """)
            non_sakha = str(cur.fetchone()[0])
        resp = client.patch(f"/api/v1/admin/claims/{claim_pk}", headers=_auth(admin_tokens),
                            json={"claimed_organization_pk": non_sakha})
        assert resp.status_code == 422

    def test_in_scope_repoint_to_another_sakha_in_scope_is_allowed(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "repointok", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        resp = client.patch(f"/api/v1/admin/claims/{claim_pk}", headers=_auth(admin_tokens),
                            json={"claimed_organization_pk": sakha_orgs["org_b"]})
        assert resp.status_code == 200, resp.json()

    def _reject(self, client, admin_tokens, write_conn, person):
        claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        resp = client.post(f"/api/v1/admin/claims/{claim_pk}/reject", headers=_auth(admin_tokens),
                           json={"admin_remarks": "wrong Sakha"})
        assert resp.status_code == 200, resp.json()
        return claim_pk

    def test_rejected_claimant_can_resubmit_via_lookup_existing(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "resubmit", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        self._reject(client, admin_tokens, write_conn, person)
        resp = client.post("/api/v1/register/lookup-existing", json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 200, resp.json()

    def test_rejected_claimant_resubmits_a_new_claim_on_the_same_account(
        self, client, admin_tokens, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        person = _register(client, "resubclaim", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        old_claim_pk = self._reject(client, admin_tokens, write_conn, person)

        resp = client.post("/api/v1/register/claim", json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": sakha_orgs["org_b"],
            "claimed_local_sakha_number": uuid4().hex[:6],
            "password": TEST_PASSWORD,
        })
        assert resp.status_code == 201, resp.json()

        with write_conn.cursor() as cur:
            cur.execute("SELECT count(*), min(account_status) FROM nss.user_account WHERE person_pk = %s",
                        (person["person_pk"],))
            assert cur.fetchone() == (1, "PENDING_APPROVAL")
        new_claim_pk = _pending_claim_pk(write_conn, person["person_pk"])
        assert new_claim_pk != old_claim_pk
        assert _claim_status(write_conn, old_claim_pk) == "REJECTED"
        # ...and the new claim is approvable.
        ok = client.post(f"/api/v1/admin/claims/{new_claim_pk}/approve",
                         headers=_auth(admin_tokens), json={})
        assert ok.status_code == 200, ok.json()

    def test_pending_claim_blocks_a_second_submission(
        self, client, sakha_orgs, darshaka_type_pk, gender_pk
    ):
        person = _register(client, "stillpending", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        resp = client.post("/api/v1/register/lookup-existing", json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 409

    def test_soft_deleted_account_is_reactivated_by_claim(
        self, client, sakha_orgs, darshaka_type_pk, gender_pk, write_conn
    ):
        """uq_user_account_person is a plain UNIQUE: a person whose only account was
        soft-deleted must have that row reactivated, not get an INSERT 500."""
        person = _register(client, "softdel", gender_pk, sakha_orgs["org_a"], darshaka_type_pk)
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.registration_claim SET claim_status = 'REJECTED' WHERE person_pk = %s",
                        (person["person_pk"],))
            cur.execute("UPDATE nss.user_account SET is_active = FALSE, deleted_at = NOW() "
                        "WHERE person_pk = %s", (person["person_pk"],))
        resp = client.post("/api/v1/register/claim", json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": sakha_orgs["org_a"],
            "claimed_local_sakha_number": uuid4().hex[:6],
            "password": TEST_PASSWORD,
        })
        assert resp.status_code == 201, resp.json()
        with write_conn.cursor() as cur:
            cur.execute("SELECT count(*), bool_and(is_active), min(account_status) "
                        "FROM nss.user_account WHERE person_pk = %s", (person["person_pk"],))
            assert cur.fetchone() == (1, True, "PENDING_APPROVAL")
