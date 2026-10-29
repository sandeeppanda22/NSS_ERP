"""
NSS ERP — Registration & Claim Approval tests.

Integration tests for:
  1. POST /api/v1/register — self-registration (claim-based flow)
  2. GET  /api/v1/admin/claims — list pending claims
  3. POST /api/v1/admin/claims/{pk}/approve — approve a claim
  4. POST /api/v1/admin/claims/{pk}/reject  — reject a claim

These tests run against local PostgreSQL.
The database must have Tier 0–5 DDL + seed data bootstrapped,
including the registration_claim table.

Test flow:
  - Register a new person → account is PENDING_APPROVAL
  - Verify login fails for PENDING_APPROVAL
  - Admin lists claims → sees the new claim
  - Admin approves → account ACTIVE, sangha_sevi created
  - Verify login succeeds after approval
  - Register another person, admin rejects → account stays PENDING

NOTE: cleanup is automatic via transaction rollback in conftest.py.
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from tests.registration_support import (
    registration_address, non_darshaka_credential_number, add_user_account,
)


pytestmark = pytest.mark.integration


# ── Test constants ──────────────────────────────────────────────────────

TEST_PASSWORD = "TestReg1x"
TEST_FIRST_NAME = "RegTest"
TEST_LAST_NAME = "AutoCleanup"
TEST_DOB = "2000-01-15"
# Unique suffix per test run to avoid email collisions from leftover data
_RUN_ID = uuid4().hex[:8]
TEST_EMAIL_PREFIX = f"regtest_{_RUN_ID}_"


# ── Module-scoped fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_tokens(client, write_conn):
    """
    Get auth tokens for an admin user who has MEMBERSHIP_APPROVE
    and ADMIN_USER_MANAGE permissions.

    Finds the first active admin user with appropriate permissions.
    """
    cur = write_conn.cursor()

    # Find an admin with MEMBERSHIP_APPROVE permission
    cur.execute("""
        SELECT ua.user_account_pk, ss.sangha_sevi_id
        FROM nss.user_account ua
        JOIN nss.person p ON p.person_pk = ua.person_pk
        JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk AND ss.is_active = TRUE
        JOIN nss.user_role ur ON ur.user_account_pk = ua.user_account_pk AND ur.is_active = TRUE
        JOIN nss.role_permission rp ON rp.role_master_pk = ur.role_master_pk AND rp.is_active = TRUE
        JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
        WHERE ua.is_active = TRUE
          AND ua.account_status = 'ACTIVE'
          AND pm.permission_code IN ('MEMBERSHIP_APPROVE', 'ADMIN_USER_MANAGE')
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No admin user with MEMBERSHIP_APPROVE permission. Cannot run claim tests.")

    admin_pk, sevi_id = row

    # We need to know the admin's password — set a known one
    from api.services.auth_service import hash_password
    pw_hash = hash_password(TEST_PASSWORD)

    cur.execute("""
        UPDATE nss.user_account
        SET password_hash = %s, password_changed_at = NOW(),
            password_expires_at = NOW() + INTERVAL '365 days'
        WHERE user_account_pk = %s
    """, (pw_hash, str(admin_pk)))

    # Login
    response = client.post("/api/v1/auth/login", json={
        "login_id": sevi_id,
        "password": TEST_PASSWORD,
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.json()}")

    tokens = response.json()
    yield {
        "access_token": tokens["access_token"],
        "user_account_pk": str(admin_pk),
        "sangha_sevi_id": sevi_id,
    }


@pytest.fixture(scope="module")
def test_org_pk(write_conn, admin_tokens):
    """
    Get an organization PK that the admin has scope for.
    Falls back to any SAKHA_SANGHA org.

    Claim approval (compose_local_sakha_erp_id) requires the org to have a
    short_code assigned — the real 175-branch seed leaves short_code NULL
    (admin-assignable via UI), so tests that approve a claim against this
    org would otherwise 422. Assign a synthetic one here if missing, scoped
    to this test transaction only (rolled back by conftest's module
    SAVEPOINT) — mirrors test_claim_approval.py::sakha_orgs.
    """
    cur = write_conn.cursor()

    def _ensure_short_code(org_pk: str) -> str:
        cur.execute("SELECT short_code FROM nss.organization WHERE organization_pk = %s", (org_pk,))
        if not cur.fetchone()[0]:
            cur.execute(
                "UPDATE nss.organization SET short_code = 'TREG' WHERE organization_pk = %s",
                (org_pk,),
            )
        return org_pk

    # Get the admin's scoped org
    cur.execute("""
        SELECT asc2.organization_pk
        FROM nss.admin_scope asc2
        JOIN nss.user_role ur ON ur.user_role_pk = asc2.user_role_pk
        WHERE ur.user_account_pk = %s
          AND ur.is_active = TRUE
          AND asc2.is_active = TRUE
          AND asc2.organization_pk IS NOT NULL
        LIMIT 1
    """, (admin_tokens["user_account_pk"],))
    row = cur.fetchone()
    if row:
        return _ensure_short_code(str(row[0]))

    # Check if admin is NSS-WIDE scoped
    cur.execute("""
        SELECT asc2.scope_level
        FROM nss.admin_scope asc2
        JOIN nss.user_role ur ON ur.user_role_pk = asc2.user_role_pk
        WHERE ur.user_account_pk = %s
          AND ur.is_active = TRUE
          AND asc2.is_active = TRUE
          AND asc2.scope_level = 'NSS-WIDE'
        LIMIT 1
    """, (admin_tokens["user_account_pk"],))
    if cur.fetchone():
        # NSS-WIDE — pick any Sakha org
        cur.execute("""
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA'
              AND o.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return _ensure_short_code(str(row[0]))

    pytest.skip("No suitable organization found for claim tests.")


@pytest.fixture(scope="module")
def darshaka_type_pk(write_conn):
    """Get the master_data_pk for PROBATIONARY (Darshaka) membership type."""
    cur = write_conn.cursor()
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
    if row is None:
        pytest.skip("No PROBATIONARY membership type found.")
    return str(row[0])


@pytest.fixture(scope="module")
def gender_pk(write_conn):
    """Get the master_data_pk for MALE gender (or any active gender)."""
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
def reg_address(write_conn):
    """Mandatory address block for POST /register (see tests/registration_support.py)."""
    return registration_address(write_conn.cursor())


# ── Registration Tests ──────────────────────────────────────────────────

class TestRegistration:
    """POST /api/v1/register — claim-based registration."""

    def test_register_darshaka_success(self, client, test_org_pk, darshaka_type_pk, gender_pk, write_conn, reg_address):
        """Register a new Darshaka member — creates person + PENDING_APPROVAL account + claim."""
        response = client.post("/api/v1/register", json={
            "first_name": TEST_FIRST_NAME,
            "last_name": TEST_LAST_NAME,
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}darshaka@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D1",
        })
        assert response.status_code == 201, f"Registration failed: {response.json()}"
        data = response.json()

        assert "person_pk" in data
        assert "person_id" in data
        assert data["person_id"].startswith("P")
        assert "pending" in data["message"].lower() or "approval" in data["message"].lower()
        # No sangha_sevi_id in response (AUTH-BR-091)
        assert "sangha_sevi_id" not in data

        # Verify DB state via shared test connection
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT user_account_pk, account_status FROM nss.user_account WHERE person_pk = %s",
                (data["person_pk"],),
            )
            ua_row = cur.fetchone()
            assert ua_row is not None
            assert ua_row[1] == "PENDING_APPROVAL"

            cur.execute(
                "SELECT registration_claim_pk, claim_status FROM nss.registration_claim WHERE person_pk = %s",
                (data["person_pk"],),
            )
            claim_row = cur.fetchone()
            assert claim_row is not None
            assert claim_row[1] == "PENDING"

    def test_register_no_membership(self, client, gender_pk, write_conn, reg_address):
        """Register without membership claim — person + address only; NO user_account
        and NO claim (an account with no path to a Sangha Sevi could never log in)."""
        response = client.post("/api/v1/register", json={
            "first_name": TEST_FIRST_NAME,
            "last_name": "NoMembership",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}nomember@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": False,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["person_id"].startswith("P")
        assert "No login account was created" in data["message"]

        with write_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM nss.person WHERE person_pk = %s", (data["person_pk"],))
            assert cur.fetchone() is not None

            cur.execute(
                "SELECT 1 FROM nss.user_account WHERE person_pk = %s", (data["person_pk"],),
            )
            assert cur.fetchone() is None

            cur.execute(
                "SELECT 1 FROM nss.registration_claim WHERE person_pk = %s", (data["person_pk"],),
            )
            assert cur.fetchone() is None

            # The mandatory address block is persisted as the primary PERMANENT address.
            cur.execute(
                "SELECT address_line_1, is_primary FROM nss.person_address WHERE person_pk = %s",
                (data["person_pk"],),
            )
            addr = cur.fetchone()
            assert addr is not None
            assert addr[0] == reg_address["address_line_1"]
            assert addr[1] is True

    def test_register_missing_contact_fails(self, client, gender_pk, reg_address):
        """Registration without mobile or email returns 422 from the contact rule
        (not merely from a missing required field)."""
        response = client.post("/api/v1/register", json={
            "first_name": "NoContact",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "password": TEST_PASSWORD,
            **reg_address,
        })
        assert response.status_code == 422
        assert "mobile_number or email" in response.json()["detail"]

    def test_register_nondarshaka_requires_local_sakha_number(self, client, test_org_pk, gender_pk, write_conn, reg_address):
        """Non-Darshaka registration without Local Sakha Number returns 422."""
        # Get a non-Darshaka membership type
        cur = write_conn.cursor()
        cur.execute("""
            SELECT md.master_data_pk
            FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE'
              AND md.value_code != 'PROBATIONARY'
              AND md.is_active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No non-Darshaka membership type found.")

        response = client.post("/api/v1/register", json={
            "first_name": "NonDarshaka",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}nondark@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": str(row[0]),
            "organization_pk": test_org_pk,
            # Credential number supplied so the Local Sakha Number rule (5b) is
            # the one that fires, not the earlier Parichaya Patra rule (3d).
            "claimed_credential_document_number": non_darshaka_credential_number(),
            # No claimed_local_sakha_number
        })
        assert response.status_code == 422
        assert "Local Sakha Number" in response.json()["detail"]

    def test_register_darshaka_local_sakha_number_optional_at_registration(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, reg_address
    ):
        """A Darshaka applicant has no number to self-report, so registration
        accepts the claim without one (the number is only enforced at approval —
        see test_claim_approval.py::TestApproveRequiresLocalSakhaNumber)."""
        response = client.post("/api/v1/register", json={
            "first_name": "DarshakaNoNumber",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}darkno@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            # No claimed_local_sakha_number
        })
        assert response.status_code == 201, response.json()

    def test_register_attending_as_darshak_requires_darshak_local_sakha_number(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, write_conn, reg_address):
        """is_attending_as_darshak=True without darshak_local_sakha_number returns 422."""
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT organization_pk FROM nss.organization "
                "WHERE organization_pk != %s AND organization_type_master_data_pk = "
                "(SELECT organization_type_master_data_pk FROM nss.organization WHERE organization_pk = %s) "
                "AND is_active = TRUE LIMIT 1",
                (test_org_pk, test_org_pk),
            )
            row = cur.fetchone()
            if row is None:
                pytest.skip("No second Sakha available for darshak attendance test.")
            other_org_pk = str(row[0])

        response = client.post("/api/v1/register", json={
            "first_name": "DarshakAttend",
            "last_name": "NoNumber",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}darkattend@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D2",
            "is_attending_as_darshak": True,
            "darshak_organization_pk": other_org_pk,
            # No darshak_local_sakha_number
        })
        assert response.status_code == 422
        assert "darshak_local_sakha_number" in response.json()["detail"]


# ── Login blocked for PENDING_APPROVAL ──────────────────────────────────
#
# TestPendingLoginBlocked::test_pending_account_cannot_login moved to
# tests/security/test_registration_security.py


# ── Claim Approval Tests ───────────────────────────────────────────────

class TestClaimApproval:
    """GET/POST /api/v1/admin/claims — list, approve, reject."""

    def test_list_pending_claims(self, client, admin_tokens):
        """Admin can list pending claims."""
        response = client.get(
            "/api/v1/admin/claims?claim_status=PENDING",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert "total" in data

    def test_approve_claim(self, client, admin_tokens, test_org_pk, darshaka_type_pk, gender_pk, write_conn, reg_address):
        """Admin approves a Darshaka claim → account ACTIVE, sangha_sevi + affiliation +
        Anumati Patra credential all created."""
        # 1. Register a new person with claim
        reg_resp = client.post("/api/v1/register", json={
            "first_name": "ApproveMe",
            "last_name": TEST_LAST_NAME,
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}approveme@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D3",
        })
        assert reg_resp.status_code == 201
        person_pk = reg_resp.json()["person_pk"]

        # Find the claim and user_account via shared test connection
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT user_account_pk FROM nss.user_account WHERE person_pk = %s",
                (person_pk,),
            )
            ua_pk = str(cur.fetchone()[0])

            cur.execute(
                "SELECT registration_claim_pk FROM nss.registration_claim WHERE person_pk = %s AND claim_status = 'PENDING'",
                (person_pk,),
            )
            claim_pk = str(cur.fetchone()[0])

        # 2. Approve the claim
        approve_resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={
                "Authorization": f"Bearer {admin_tokens['access_token']}",
                "Content-Type": "application/json",
            },
            json={"admin_remarks": "Test approval"},
        )
        assert approve_resp.status_code == 200, f"Approve failed: {approve_resp.json()}"
        approve_data = approve_resp.json()
        assert "sangha_sevi_id" in approve_data
        assert approve_data["sangha_sevi_id"] is not None

        # 3. Verify: account is now ACTIVE, claim is APPROVED, sangha_sevi exists
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT account_status FROM nss.user_account WHERE user_account_pk = %s",
                (ua_pk,),
            )
            assert cur.fetchone()[0] == "ACTIVE"

            cur.execute(
                "SELECT claim_status FROM nss.registration_claim WHERE registration_claim_pk = %s",
                (claim_pk,),
            )
            assert cur.fetchone()[0] == "APPROVED"

            cur.execute(
                "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
                (person_pk,),
            )
            ss_row = cur.fetchone()
            assert ss_row is not None
            ss_pk = ss_row[0]

            # The home affiliation got a real, short_code-namespaced local
            # ID (MBR-030C) — not the old buggy fallback that just reused
            # the Sangha Sevi ID when no number was given.
            cur.execute(
                "SELECT local_sakha_erp_id FROM nss.membership_sakha_affiliation "
                "WHERE sangha_sevi_pk = %s AND organization_pk = %s",
                (ss_pk, test_org_pk),
            )
            aff_row = cur.fetchone()
            assert aff_row is not None
            assert aff_row[0] != approve_data["sangha_sevi_id"]
            assert aff_row[0].endswith("D3")

            # A mandatory Anumati Patra credential was issued (MBR-010/019A) —
            # claim_approval.py now calls issue_membership_credential(), which
            # it never did before this test was written.
            cur.execute(
                "SELECT document_number FROM nss.anumati_patra WHERE sangha_sevi_pk = %s",
                (ss_pk,),
            )
            credential_row = cur.fetchone()
            assert credential_row is not None
            assert credential_row[0]

    def test_approve_claim_composes_legacy_credential_number_with_current_fy(
        self, client, admin_tokens, test_org_pk, darshaka_type_pk, gender_pk, write_conn, reg_address):
        """A registrant-supplied legacy credential number is a plain sequence
        number (e.g. "789") — the registration form doesn't ask for the FY,
        so approve_claim must compose the full "<no>/<fy_start>/<fy_end>"
        Kendra Number itself, using the current financial year."""
        from datetime import date
        from api.helpers import financial_year_bounds

        reg_resp = client.post("/api/v1/register", json={
            "first_name": "LegacyCred",
            "last_name": TEST_LAST_NAME,
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}legacycred@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D9",
            "claimed_credential_document_number": "789",
        })
        assert reg_resp.status_code == 201
        person_pk = reg_resp.json()["person_pk"]

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT registration_claim_pk FROM nss.registration_claim WHERE person_pk = %s AND claim_status = 'PENDING'",
                (person_pk,),
            )
            claim_pk = str(cur.fetchone()[0])

        approve_resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={},
        )
        assert approve_resp.status_code == 200, f"Approve failed: {approve_resp.json()}"

        fy_start, fy_end, _, _ = financial_year_bounds(date.today())
        expected_document_number = f"789/{fy_start}/{fy_end}"

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT document_number FROM nss.anumati_patra WHERE sangha_sevi_pk = "
                "(SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE)",
                (person_pk,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == expected_document_number, (
                f"Expected the plain number composed with the current FY "
                f"({expected_document_number!r}), got {row[0]!r}"
            )

    def test_reject_claim(self, client, admin_tokens, test_org_pk, darshaka_type_pk, gender_pk, write_conn, reg_address):
        """Admin rejects a claim → claim REJECTED, account stays PENDING_APPROVAL."""
        # 1. Register
        reg_resp = client.post("/api/v1/register", json={
            "first_name": "RejectMe",
            "last_name": TEST_LAST_NAME,
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}rejectme@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D4",
        })
        assert reg_resp.status_code == 201
        person_pk = reg_resp.json()["person_pk"]

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT user_account_pk FROM nss.user_account WHERE person_pk = %s",
                (person_pk,),
            )
            ua_pk = str(cur.fetchone()[0])

            cur.execute(
                "SELECT registration_claim_pk FROM nss.registration_claim WHERE person_pk = %s AND claim_status = 'PENDING'",
                (person_pk,),
            )
            claim_pk = str(cur.fetchone()[0])

        # 2. Reject
        reject_resp = client.post(
            f"/api/v1/admin/claims/{claim_pk}/reject",
            headers={
                "Authorization": f"Bearer {admin_tokens['access_token']}",
                "Content-Type": "application/json",
            },
            json={"admin_remarks": "Test rejection — incorrect details"},
        )
        assert reject_resp.status_code == 200

        # 3. Verify: claim REJECTED, account still PENDING_APPROVAL
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT claim_status FROM nss.registration_claim WHERE registration_claim_pk = %s",
                (claim_pk,),
            )
            assert cur.fetchone()[0] == "REJECTED"

            cur.execute(
                "SELECT account_status FROM nss.user_account WHERE user_account_pk = %s",
                (ua_pk,),
            )
            assert cur.fetchone()[0] == "PENDING_APPROVAL"

    def test_reject_without_remarks_fails(self, client, admin_tokens):
        """Rejection without admin_remarks returns 422."""
        # Use a fake UUID — the 422 should come from Pydantic validation before DB
        response = client.post(
            "/api/v1/admin/claims/00000000-0000-0000-0000-000000000000/reject",
            headers={
                "Authorization": f"Bearer {admin_tokens['access_token']}",
                "Content-Type": "application/json",
            },
            json={"admin_remarks": ""},
        )
        assert response.status_code == 422

    def test_approve_already_approved_fails(self, client, admin_tokens, write_conn):
        """Cannot approve a claim that is already APPROVED."""
        # Find any APPROVED claim in the DB (created by test_approve_claim above)
        with write_conn.cursor() as cur:
            cur.execute("""
                SELECT registration_claim_pk
                FROM nss.registration_claim
                WHERE claim_status = 'APPROVED'
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No APPROVED claim found for double-approve test.")
            claim_pk = str(row[0])

        response = client.post(
            f"/api/v1/admin/claims/{claim_pk}/approve",
            headers={
                "Authorization": f"Bearer {admin_tokens['access_token']}",
                "Content-Type": "application/json",
            },
            json={},
        )
        assert response.status_code == 422
        assert "already" in response.json()["detail"].lower()

# ── Registration with address fields tests ───────────────────────────

class TestRegistrationWithAddress:
    """POST /api/v1/register — the mandatory address block (city_village_name, geography FKs, PIN)."""

    def test_register_with_city_village_name(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, reg_address, write_conn
    ):
        """Registration with city_village_name creates the city_village record."""
        cv_name = f"TestVillage_{_RUN_ID}_addr"
        response = client.post("/api/v1/register", json={
            "first_name": "AddrTest",
            "last_name": "Village",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}addr_cv@test.example",
            "password": TEST_PASSWORD,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D5",
            **{**reg_address, "city_village_name": cv_name},
        })
        assert response.status_code == 201, f"Registration with address failed: {response.json()}"
        data = response.json()
        assert "person_pk" in data

        # Verify the city_village was created in the DB
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT city_village_pk, city_village_name FROM nss.city_village WHERE LOWER(city_village_name) = LOWER(%s)",
                (cv_name,),
            )
            row = cur.fetchone()
            assert row is not None, f"city_village '{cv_name}' was not created."

            # Verify person has the city_village_pk set
            cur.execute(
                "SELECT city_village_pk FROM nss.person WHERE person_pk = %s",
                (data["person_pk"],),
            )
            person_row = cur.fetchone()
            assert person_row is not None
            assert str(person_row[0]) == str(row[0])

    def test_register_with_all_address_fields(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, reg_address, write_conn
    ):
        """Country, state, district and PIN are stored on the person; the PIN is
        resolved/created (PENDING, attributed to the registrant)."""
        response = client.post("/api/v1/register", json={
            "first_name": "FullAddr",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}full_addr@test.example",
            "password": TEST_PASSWORD,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D6",
            **reg_address,
        })
        assert response.status_code == 201, response.json()
        data = response.json()

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT country_pk, state_pk, district_pk, postal_code_pk "
                "FROM nss.person WHERE person_pk = %s",
                (data["person_pk"],),
            )
            country_pk, state_pk, district_pk, postal_code_pk = cur.fetchone()
            assert str(country_pk) == reg_address["country_pk"]
            assert str(state_pk) == reg_address["state_pk"]
            assert str(district_pk) == reg_address["district_pk"]
            assert postal_code_pk is not None

            cur.execute(
                "SELECT postal_code FROM nss.postal_code WHERE postal_code_pk = %s",
                (str(postal_code_pk),),
            )
            assert cur.fetchone()[0] == reg_address["postal_code_value"]

    @pytest.mark.parametrize(
        "missing_field",
        ["country_pk", "state_pk", "district_pk", "city_village_name",
         "postal_code_value", "address_line_1"],
    )
    def test_register_without_address_field_rejected(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, reg_address, missing_field
    ):
        """Every address field is mandatory (user decision 2026-10-03): omitting any
        one is a 422, never a silent address-less person."""
        payload = {
            "first_name": "NoAddr",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}no_addr_{missing_field}@test.example",
            "password": TEST_PASSWORD,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D7",
            **reg_address,
        }
        del payload[missing_field]
        response = client.post("/api/v1/register", json=payload)
        assert response.status_code == 422

    def test_register_blank_address_field_rejected(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, reg_address
    ):
        """Pydantic only guards presence — a blank address_line_1 must be caught by the
        handler's own check and named in the error."""
        response = client.post("/api/v1/register", json={
            "first_name": "BlankAddr",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}blank_addr@test.example",
            "password": TEST_PASSWORD,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D7",
            **{**reg_address, "address_line_1": "   "},
        })
        assert response.status_code == 422
        assert "address_line_1" in response.json()["detail"]

    def test_register_city_village_lookup_existing(
        self, client, test_org_pk, darshaka_type_pk, gender_pk, reg_address, write_conn
    ):
        """If the city_village already exists for (district, PIN, name), it is reused
        (not duplicated)."""
        cv_name = f"LookupVillage_{_RUN_ID}"
        pin = reg_address["postal_code_value"]

        # Pre-create the PIN and the city_village hanging off it. The registration
        # resolves the village on (name, district, PIN), so the fixture row must
        # carry the PIN the registrant is about to type.
        with write_conn.cursor() as cur:
            # Reuse whatever active row the router's resolve_or_create_postal_code
            # would find for this PIN (it matches on postal_code + is_active only,
            # LIMIT 1); only insert when none exists. A blind INSERT could add a
            # second row next to an existing PENDING one and the router might
            # then bind to the other row.
            cur.execute(
                "SELECT postal_code_pk FROM nss.postal_code "
                "WHERE postal_code = %s AND is_active = TRUE "
                "ORDER BY (entry_status = 'APPROVED') DESC LIMIT 1",
                (pin,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO nss.postal_code (state_pk, postal_code, entry_status) "
                    "VALUES (%s, %s, 'APPROVED') RETURNING postal_code_pk",
                    (reg_address["state_pk"], pin),
                )
                row = cur.fetchone()
            postal_code_pk = str(row[0])

            cv_code = cv_name.upper().replace(" ", "_")[:20]
            cur.execute("""
                INSERT INTO nss.city_village
                    (district_pk, postal_code_pk, city_village_code, city_village_name, city_village_type)
                VALUES (%s, %s, %s, %s, 'CITY')
                RETURNING city_village_pk
            """, (reg_address["district_pk"], postal_code_pk, cv_code, cv_name))
            existing_pk = str(cur.fetchone()[0])

        response = client.post("/api/v1/register", json={
            "first_name": "LookupTest",
            "last_name": "Reuse",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}cv_lookup@test.example",
            "password": TEST_PASSWORD,
            "has_membership": True,
            "membership_type_master_data_pk": darshaka_type_pk,
            "organization_pk": test_org_pk,
            "claimed_local_sakha_number": "D8",
            **{**reg_address, "city_village_name": cv_name},
        })
        assert response.status_code == 201, response.json()
        data = response.json()

        # Verify the person points to the existing city_village, not a new one
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT city_village_pk FROM nss.person WHERE person_pk = %s",
                (data["person_pk"],),
            )
            person_cv_pk = str(cur.fetchone()[0])
            assert person_cv_pk == existing_pk, (
                f"Expected reuse of city_village {existing_pk}, got new {person_cv_pk}"
            )


# ═══════════════════════════════════════════════════════════════════════
# Public pre-registration helpers and the "previously registered" flow
# (all unauthenticated — the registrant has no JWT yet)
# ═══════════════════════════════════════════════════════════════════════

CLAIM_PASSWORD = "ClaimPass1x"


@pytest.fixture(scope="module")
def sakha_pk(write_conn):
    """Any active SAKHA_SANGHA organization (claim submission needs no short_code)."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.created_at
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No active SAKHA_SANGHA organization exists.")
    return str(row[0])


@pytest.fixture(scope="module")
def non_sakha_pk(write_conn):
    """Any active organization that is NOT a Sakha Sangha (e.g. the Kendra)."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code <> 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.created_at
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No non-Sakha organization exists.")
    return str(row[0])


@pytest.fixture(scope="module")
def regular_type_pk(write_conn):
    """A non-Darshaka (non-PROBATIONARY) membership type."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE'
          AND md.value_code <> 'PROBATIONARY' AND md.is_active = TRUE
        ORDER BY md.value_code
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No non-Darshaka membership type found.")
    return str(row[0])


def _make_orphan_person(write_conn, label, dob=TEST_DOB, is_active=True):
    """
    A throwaway person with a known DOB and NO account / claim / Sangha Sevi —
    exactly the "registered without membership" state that /register/lookup-existing
    and /register/claim serve. Built by direct SQL so each test owns its identity.
    """
    suffix = uuid4().hex[:10].upper()
    cur = write_conn.cursor()
    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email, date_of_birth)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING person_pk, person_id
    """, (
        f"TLK{label}{suffix}", f"Lookup{label}", suffix,
        f"tlk.{label.lower()}.{suffix.lower()}@example.test", dob,
    ))
    person_pk, person_id = cur.fetchone()
    if not is_active:
        cur.execute(
            "UPDATE nss.person SET is_active = FALSE, deleted_at = NOW() WHERE person_pk = %s",
            (str(person_pk),),
        )
    return {"person_pk": str(person_pk), "person_id": person_id}


# ── POST /register/check-duplicate ──────────────────────────────────────

class TestCheckDuplicate:

    def test_unknown_contact_reports_no_duplicates(self, client, write_conn):
        # A hard-coded mobile can already belong to a real person on a populated
        # dev DB; pick one that is genuinely unused.
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT m FROM (SELECT '9' || lpad(g::text, 9, '0') AS m "
                "FROM generate_series(1, 200000) g) c "
                "WHERE NOT EXISTS (SELECT 1 FROM nss.person p "
                "WHERE p.country_phone_code = '+91' AND p.mobile_number = c.m) LIMIT 1"
            )
            mobile = cur.fetchone()[0]
        resp = client.post("/api/v1/register/check-duplicate", json={
            "email": f"{TEST_EMAIL_PREFIX}nobody@test.example",
            "country_phone_code": "+91",
            "mobile_number": mobile,
        })
        assert resp.status_code == 200
        assert resp.json() == {"mobile_exists": False, "email_exists": False}

    def test_empty_body_is_a_noop(self, client):
        resp = client.post("/api/v1/register/check-duplicate", json={})
        assert resp.status_code == 200
        assert resp.json() == {"mobile_exists": False, "email_exists": False}

    def test_existing_email_matches_case_insensitively(self, client, write_conn):
        person = _make_orphan_person(write_conn, "DUPE")
        with write_conn.cursor() as cur:
            cur.execute("SELECT email FROM nss.person WHERE person_pk = %s", (person["person_pk"],))
            email = cur.fetchone()[0]
        resp = client.post("/api/v1/register/check-duplicate", json={"email": email.upper()})
        assert resp.status_code == 200
        assert resp.json()["email_exists"] is True
        assert resp.json()["mobile_exists"] is False

    def test_existing_mobile_needs_phone_code(self, client, write_conn):
        person = _make_orphan_person(write_conn, "DUPM")
        mobile = f"9{uuid4().int % 10**9:09d}"
        with write_conn.cursor() as cur:
            cur.execute(
                "UPDATE nss.person SET country_phone_code = '+91', mobile_number = %s "
                "WHERE person_pk = %s", (mobile, person["person_pk"]),
            )
        hit = client.post("/api/v1/register/check-duplicate", json={
            "country_phone_code": "+91", "mobile_number": mobile,
        })
        assert hit.json()["mobile_exists"] is True

        # The check is keyed on (code, number): a number alone is not looked up.
        bare = client.post("/api/v1/register/check-duplicate", json={"mobile_number": mobile})
        assert bare.status_code == 200
        assert bare.json()["mobile_exists"] is False

    def test_soft_deleted_person_is_not_a_duplicate(self, client, write_conn):
        person = _make_orphan_person(write_conn, "DUPX", is_active=False)
        with write_conn.cursor() as cur:
            cur.execute("SELECT email FROM nss.person WHERE person_pk = %s", (person["person_pk"],))
            email = cur.fetchone()[0]
        resp = client.post("/api/v1/register/check-duplicate", json={"email": email})
        assert resp.json()["email_exists"] is False

    def test_non_object_body_is_422(self, client):
        resp = client.post("/api/v1/register/check-duplicate", json=["x"])
        assert resp.status_code == 422


# ── POST /register/lookup-existing ──────────────────────────────────────

class TestLookupExisting:

    URL = "/api/v1/register/lookup-existing"

    def test_lookup_success(self, client, write_conn):
        person = _make_orphan_person(write_conn, "OK")
        resp = client.post(self.URL, json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["person_pk"] == person["person_pk"]
        assert data["person_id"] == person["person_id"]
        assert data["person_name"].startswith("LookupOK")

    def test_person_id_is_whitespace_trimmed(self, client, write_conn):
        person = _make_orphan_person(write_conn, "TRIM")
        resp = client.post(self.URL, json={
            "person_id": f"  {person['person_id']}  ", "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 200

    def test_wrong_dob_is_404(self, client, write_conn):
        person = _make_orphan_person(write_conn, "DOB")
        resp = client.post(self.URL, json={
            "person_id": person["person_id"], "date_of_birth": "1999-12-31",
        })
        assert resp.status_code == 404

    def test_unknown_person_id_is_404(self, client):
        resp = client.post(self.URL, json={
            "person_id": f"NOPE{uuid4().hex[:8]}", "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 404

    def test_inactive_person_is_404(self, client, write_conn):
        person = _make_orphan_person(write_conn, "GONE", is_active=False)
        resp = client.post(self.URL, json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 404

    @pytest.mark.parametrize("body", [
        {"date_of_birth": TEST_DOB},
        {"person_id": "P1"},
        {"person_id": "", "date_of_birth": TEST_DOB},
        {"person_id": "P1", "date_of_birth": "not-a-date"},
    ])
    def test_invalid_body_is_422(self, client, body):
        assert client.post(self.URL, json=body).status_code == 422

    def test_person_with_account_is_409(self, client, write_conn):
        person = _make_orphan_person(write_conn, "HASACC")
        add_user_account(write_conn, person["person_pk"], CLAIM_PASSWORD)
        resp = client.post(self.URL, json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 409
        assert "already has a registered account" in resp.json()["detail"]

    def test_person_with_pending_claim_is_409(
        self, client, write_conn, sakha_pk, regular_type_pk
    ):
        """The pending-claim guard only fires when no live account trips the earlier
        guard first, so build the claim against a soft-deleted account."""
        person = _make_orphan_person(write_conn, "PENDCL")
        ua_pk = add_user_account(write_conn, person["person_pk"], CLAIM_PASSWORD, is_active=False)
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.registration_claim (
                    user_account_pk, person_pk, claimed_organization_pk,
                    claimed_membership_type_master_data_pk,
                    claimed_local_sakha_number, claim_status
                ) VALUES (%s, %s, %s, %s, %s, 'PENDING')
            """, (ua_pk, person["person_pk"], sakha_pk, regular_type_pk, "L1"))
        resp = client.post(self.URL, json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 409
        assert "already pending" in resp.json()["detail"]

    def test_person_who_is_already_sangha_sevi_is_409(
        self, client, write_conn, sakha_pk, regular_type_pk
    ):
        person = _make_orphan_person(write_conn, "ISSS")
        with write_conn.cursor() as cur:
            cur.execute("""
                SELECT md.master_data_pk FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE'
                  AND md.is_active = TRUE LIMIT 1
            """)
            active_status_pk = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO nss.sangha_sevi (
                    sangha_sevi_id, person_pk, membership_type_master_data_pk,
                    membership_status_master_data_pk, organization_pk, joining_date
                ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
            """, (f"TSSLK{uuid4().hex[:8].upper()}", person["person_pk"],
                  regular_type_pk, str(active_status_pk), sakha_pk))
        resp = client.post(self.URL, json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert resp.status_code == 409
        assert "already a Sangha Sevi" in resp.json()["detail"]


# ── POST /register/claim ────────────────────────────────────────────────

class TestClaimExisting:

    URL = "/api/v1/register/claim"

    def _body(self, person, sakha_pk, type_pk, **overrides):
        body = {
            "person_id": person["person_id"],
            "date_of_birth": TEST_DOB,
            "membership_type_master_data_pk": type_pk,
            "organization_pk": sakha_pk,
            "claimed_local_sakha_number": "L7",
            "password": CLAIM_PASSWORD,
        }
        body.update(overrides)
        return body

    def test_darshaka_claim_creates_pending_account_and_claim(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLDK")
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, joining_date="2024-04-01",
        ))
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["person_pk"] == person["person_pk"]
        assert data["person_id"] == person["person_id"]
        assert "pending approval" in data["message"].lower()

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT account_status, force_password_change FROM nss.user_account "
                "WHERE person_pk = %s", (person["person_pk"],),
            )
            assert cur.fetchone() == ("PENDING_APPROVAL", False)

            cur.execute("""
                SELECT claim_status, claimed_organization_pk, claimed_local_sakha_number,
                       claimed_joining_date
                FROM nss.registration_claim WHERE person_pk = %s
            """, (person["person_pk"],))
            status_val, org_pk, local_no, joining = cur.fetchone()
            assert status_val == "PENDING"
            assert str(org_pk) == sakha_pk
            assert local_no == "L7"
            assert str(joining) == "2024-04-01"

            # No Sangha Sevi until an admin approves (AUTH-BR-091).
            cur.execute("SELECT 1 FROM nss.sangha_sevi WHERE person_pk = %s", (person["person_pk"],))
            assert cur.fetchone() is None

    def test_second_claim_is_refused_after_first(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        """After a successful claim the person has an account, so both lookup and a
        repeat claim are now 409 — the flow cannot be replayed."""
        person = _make_orphan_person(write_conn, "CLTWICE")
        body = self._body(person, sakha_pk, darshaka_type_pk)
        assert client.post(self.URL, json=body).status_code == 201
        again = client.post(self.URL, json=body)
        assert again.status_code == 409
        look = client.post("/api/v1/register/lookup-existing", json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        assert look.status_code == 409

    def test_non_darshaka_requires_local_sakha_number(
        self, client, write_conn, sakha_pk, regular_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLNL")
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, regular_type_pk,
            claimed_local_sakha_number=None,
            claimed_credential_document_number=non_darshaka_credential_number(),
        ))
        assert resp.status_code == 422
        assert "Local Sakha Number" in resp.json()["detail"]

    def test_non_darshaka_requires_credential_number(
        self, client, write_conn, sakha_pk, regular_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLNC")
        resp = client.post(self.URL, json=self._body(person, sakha_pk, regular_type_pk))
        assert resp.status_code == 422
        assert "claimed_credential_document_number" in resp.json()["detail"]

    def test_non_darshaka_with_both_numbers_succeeds(
        self, client, write_conn, sakha_pk, regular_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLNOK")
        number = non_darshaka_credential_number()
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, regular_type_pk, claimed_credential_document_number=number,
        ))
        assert resp.status_code == 201, resp.json()
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT claimed_credential_document_number FROM nss.registration_claim "
                "WHERE person_pk = %s", (person["person_pk"],),
            )
            assert cur.fetchone()[0] == number

    def test_weak_password_is_422_and_creates_nothing(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLPW")
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, password="weakpassword1",
        ))
        assert resp.status_code == 422
        with write_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM nss.user_account WHERE person_pk = %s", (person["person_pk"],))
            assert cur.fetchone() is None

    def test_short_password_is_422(self, client, write_conn, sakha_pk, darshaka_type_pk):
        person = _make_orphan_person(write_conn, "CLSP")
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, password="Ab1",
        ))
        assert resp.status_code == 422

    def test_wrong_dob_is_404_and_creates_nothing(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLDOB")
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, date_of_birth="1999-12-31",
        ))
        assert resp.status_code == 404
        with write_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM nss.user_account WHERE person_pk = %s", (person["person_pk"],))
            assert cur.fetchone() is None

    def test_non_sakha_organization_is_422(
        self, client, write_conn, non_sakha_pk, darshaka_type_pk
    ):
        """MBR-038A: a claim must target a Sakha Sangha."""
        person = _make_orphan_person(write_conn, "CLNS")
        resp = client.post(self.URL, json=self._body(person, non_sakha_pk, darshaka_type_pk))
        assert resp.status_code == 422
        assert "SAKHA_SANGHA" in resp.json()["detail"]

    def test_unknown_organization_is_422(self, client, write_conn, darshaka_type_pk):
        person = _make_orphan_person(write_conn, "CLNO")
        resp = client.post(self.URL, json=self._body(
            person, "00000000-0000-0000-0000-000000000099", darshaka_type_pk,
        ))
        assert resp.status_code == 422

    def test_darshak_attendance_requires_org_and_number(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLDA")
        no_org = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, is_attending_as_darshak=True,
        ))
        assert no_org.status_code == 422
        assert "darshak_organization_pk" in no_org.json()["detail"]

        no_number = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, is_attending_as_darshak=True,
            darshak_organization_pk=sakha_pk,
        ))
        assert no_number.status_code == 422
        assert "darshak_local_sakha_number" in no_number.json()["detail"]

    def test_darshak_attendance_fields_are_stored(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        person = _make_orphan_person(write_conn, "CLDS")
        resp = client.post(self.URL, json=self._body(
            person, sakha_pk, darshaka_type_pk, is_attending_as_darshak=True,
            darshak_organization_pk=sakha_pk, darshak_local_sakha_number="DK3",
        ))
        assert resp.status_code == 201, resp.json()
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT darshak_organization_pk, darshak_local_sakha_number "
                "FROM nss.registration_claim WHERE person_pk = %s", (person["person_pk"],),
            )
            org_pk, number = cur.fetchone()
            assert str(org_pk) == sakha_pk
            assert number == "DK3"

    @pytest.mark.parametrize("missing", [
        "person_id", "date_of_birth", "membership_type_master_data_pk",
        "organization_pk", "password",
    ])
    def test_missing_required_field_is_422(
        self, client, write_conn, sakha_pk, darshaka_type_pk, missing
    ):
        person = _make_orphan_person(write_conn, "CLMF")
        body = self._body(person, sakha_pk, darshaka_type_pk)
        del body[missing]
        assert client.post(self.URL, json=body).status_code == 422

    def test_claimed_account_cannot_log_in_until_approved(
        self, client, write_conn, sakha_pk, darshaka_type_pk
    ):
        """No Sangha Sevi ID exists yet, so the Person ID is not a valid login."""
        person = _make_orphan_person(write_conn, "CLLG")
        assert client.post(self.URL, json=self._body(person, sakha_pk, darshaka_type_pk)).status_code == 201
        login = client.post("/api/v1/auth/login", json={
            "login_id": person["person_id"], "password": CLAIM_PASSWORD,
        })
        assert login.status_code in (401, 403)


# ── Public reference-data / location-cascade lookups ────────────────────

class TestPublicRegistrationLookups:
    """GET /register/{reference-data,countries,states,districts,cities,postal-codes,
    post-offices,sakhas} — all unauthenticated (the registrant has no JWT)."""

    BASE = "/api/v1/register"

    def test_reference_data_bundle(self, client):
        resp = client.get(f"{self.BASE}/reference-data")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data) == {
            "countries", "genders", "marital_statuses", "blood_groups",
            "membership_types", "sakhas",
        }
        assert data["genders"], "GENDER master data should be seeded"
        assert {m["category_code"] for m in data["genders"]} == {"GENDER"}
        assert {m["category_code"] for m in data["membership_types"]} == {"MEMBERSHIP_TYPE"}
        assert all(s["organization_type_code"] == "SAKHA_SANGHA" for s in data["sakhas"])

    def test_countries_are_active_and_public(self, client):
        resp = client.get(f"{self.BASE}/countries")
        assert resp.status_code == 200
        countries = resp.json()
        assert countries and all(c["is_active"] for c in countries)
        assert {"country_pk", "country_code", "country_name"} <= countries[0].keys()

    def test_states_filter_by_country(self, client):
        countries = client.get(f"{self.BASE}/countries").json()
        country_pk = countries[0]["country_pk"]
        resp = client.get(f"{self.BASE}/states", params={"country_pk": country_pk})
        assert resp.status_code == 200
        assert all(s["country_pk"] == country_pk for s in resp.json())

    def test_states_without_filter_is_superset_of_filtered(self, client):
        everything = client.get(f"{self.BASE}/states").json()
        country_pk = client.get(f"{self.BASE}/countries").json()[0]["country_pk"]
        filtered = client.get(f"{self.BASE}/states", params={"country_pk": country_pk}).json()
        assert len(everything) >= len(filtered)

    def test_districts_filter_by_state(self, client, reg_address):
        resp = client.get(f"{self.BASE}/districts", params={"state_pk": reg_address["state_pk"]})
        assert resp.status_code == 200
        districts = resp.json()
        assert reg_address["district_pk"] in {d["district_pk"] for d in districts}
        assert all(d["state_pk"] == reg_address["state_pk"] for d in districts)

    def test_cities_filter_by_district(self, client, reg_address, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.city_village
                    (district_pk, city_village_code, city_village_name, city_village_type)
                VALUES (%s, %s, %s, 'CITY') RETURNING city_village_pk
            """, (reg_address["district_pk"], f"LKC{uuid4().hex[:8].upper()}",
                  f"LookupCity{uuid4().hex[:6]}"))
            cv_pk = str(cur.fetchone()[0])
        resp = client.get(f"{self.BASE}/cities", params={"district_pk": reg_address["district_pk"]})
        assert resp.status_code == 200
        cities = resp.json()
        assert cv_pk in {c["city_village_pk"] for c in cities}
        assert all(c["district_pk"] == reg_address["district_pk"] for c in cities)

    def test_cities_hide_pending_entries(self, client, reg_address, write_conn):
        """A member-typed (PENDING) village is quarantined from the shared dropdown."""
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.city_village
                    (district_pk, city_village_code, city_village_name, city_village_type,
                     entry_status)
                VALUES (%s, %s, %s, 'CITY', 'PENDING') RETURNING city_village_pk
            """, (reg_address["district_pk"], f"LKP{uuid4().hex[:8].upper()}",
                  f"PendingCity{uuid4().hex[:6]}"))
            pending_pk = str(cur.fetchone()[0])
        cities = client.get(
            f"{self.BASE}/cities", params={"district_pk": reg_address["district_pk"]},
        ).json()
        assert pending_pk not in {c["city_village_pk"] for c in cities}

    def test_postal_codes_filter_by_state(self, client, reg_address, write_conn):
        pin = str(900000 + uuid4().int % 99999)
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.postal_code (state_pk, postal_code, entry_status)
                VALUES (%s, %s, 'APPROVED') RETURNING postal_code_pk
            """, (reg_address["state_pk"], pin))
            pc_pk = str(cur.fetchone()[0])
        resp = client.get(f"{self.BASE}/postal-codes", params={"state_pk": reg_address["state_pk"]})
        assert resp.status_code == 200
        codes = resp.json()
        assert pc_pk in {p["postal_code_pk"] for p in codes}
        assert all(p["state_pk"] == reg_address["state_pk"] for p in codes)

    def test_post_offices_for_pin_list_only_approved(self, client, reg_address, write_conn):
        pin = str(800000 + uuid4().int % 99999)
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.postal_code (state_pk, postal_code, entry_status)
                VALUES (%s, %s, 'APPROVED') RETURNING postal_code_pk
            """, (reg_address["state_pk"], pin))
            pc_pk = str(cur.fetchone()[0])
            cur.execute("""
                INSERT INTO nss.post_office (postal_code_pk, post_office_name, entry_status)
                VALUES (%s, 'Approved PO', 'APPROVED'), (%s, 'Pending PO', 'PENDING')
            """, (pc_pk, pc_pk))
        resp = client.get(f"{self.BASE}/post-offices", params={"postal_code_pk": pc_pk})
        assert resp.status_code == 200
        names = [p["post_office_name"] for p in resp.json()]
        assert names == ["Approved PO"]

    def test_post_offices_unknown_pin_is_empty_list(self, client):
        resp = client.get(
            f"{self.BASE}/post-offices",
            params={"postal_code_pk": "00000000-0000-0000-0000-000000000099"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_post_offices_requires_postal_code_pk(self, client):
        assert client.get(f"{self.BASE}/post-offices").status_code == 422

    def test_sakhas_are_all_sakha_sangha(self, client):
        resp = client.get(f"{self.BASE}/sakhas")
        assert resp.status_code == 200
        sakhas = resp.json()
        assert sakhas and all(s["organization_type_code"] == "SAKHA_SANGHA" for s in sakhas)

    def test_sakhas_geographic_filter_narrows(self, client):
        everything = client.get(f"{self.BASE}/sakhas").json()
        country_pk = next((s["country_pk"] for s in everything if s.get("country_pk")), None)
        if country_pk is None:
            pytest.skip("No Sakha carries a country_pk to filter on.")
        narrowed = client.get(f"{self.BASE}/sakhas", params={"country_pk": country_pk}).json()
        assert narrowed
        assert len(narrowed) <= len(everything)
        assert all(s["country_pk"] == country_pk for s in narrowed)

    def test_sakhas_unmatched_geography_is_empty(self, client):
        resp = client.get(
            f"{self.BASE}/sakhas",
            params={"postal_code_pk": "00000000-0000-0000-0000-000000000099"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize("path,param", [
        ("states", "country_pk"), ("districts", "state_pk"), ("cities", "district_pk"),
        ("postal-codes", "state_pk"), ("post-offices", "postal_code_pk"),
        ("sakhas", "state_pk"),
    ])
    def test_malformed_uuid_filter_is_422(self, client, path, param):
        assert client.get(f"{self.BASE}/{path}", params={param: "not-a-uuid"}).status_code == 422
