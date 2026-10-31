"""
NSS ERP — Registration & Claim Approval security tests.

Security-focused subset extracted from tests/api/test_registration.py:
  1. PENDING_APPROVAL accounts cannot login (AUTH-BR-089)
  2. Unauthenticated requests cannot list registration claims
  3. Weak passwords are rejected at registration

These tests run against local PostgreSQL.
The database must have Tier 0-5 DDL + seed data bootstrapped,
including the registration_claim table.

NOTE: cleanup is automatic via transaction rollback in conftest.py.
"""

import pytest
from uuid import uuid4

from tests.registration_support import registration_address


pytestmark = pytest.mark.integration


# ── Test constants ──────────────────────────────────────────────────────

TEST_PASSWORD = "TestReg1x"
TEST_DOB = "2000-01-15"
# Unique suffix per test run to avoid email collisions from leftover data
_RUN_ID = uuid4().hex[:8]
TEST_EMAIL_PREFIX = f"regtest_{_RUN_ID}_"


# ── Module-scoped fixtures ──────────────────────────────────────────────

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


@pytest.fixture(scope="module")
def membership_claim_pks(write_conn):
    """(Darshaka membership type pk, any Sakha pk) for a registration that creates an account."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'PROBATIONARY'
          AND md.is_active = TRUE
        LIMIT 1
    """)
    type_row = cur.fetchone()
    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        LIMIT 1
    """)
    org_row = cur.fetchone()
    if type_row is None or org_row is None:
        pytest.skip("Need a PROBATIONARY membership type and a Sakha organization.")
    return str(type_row[0]), str(org_row[0])


# ── Registration Tests ──────────────────────────────────────────────────

class TestRegistration:
    """POST /api/v1/register — claim-based registration."""

    def test_register_weak_password_fails(self, client, gender_pk, reg_address):
        """A well-formed registration with a policy-violating password returns 422
        from the password policy itself (not from a missing field)."""
        response = client.post("/api/v1/register", json={
            "first_name": "WeakPw",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}weakpw@test.example",
            "password": "alllowercase1",
            **reg_address,
        })
        assert response.status_code == 422
        assert any("uppercase" in v for v in response.json()["detail"])

    def test_register_is_public_and_needs_no_token(self, client, gender_pk, reg_address):
        """Self-registration is one of the deliberately unauthenticated endpoints."""
        response = client.post("/api/v1/register", json={
            "first_name": "Public",
            "last_name": "Registrant",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}public@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
        })
        assert response.status_code == 201


# ── Login blocked for PENDING_APPROVAL ──────────────────────────────────

class TestPendingLoginBlocked:
    """PENDING_APPROVAL accounts cannot login (AUTH-BR-089)."""

    def test_pending_account_cannot_login(
        self, client, gender_pk, write_conn, reg_address, membership_claim_pks
    ):
        """Login attempt for a PENDING_APPROVAL account is refused."""
        membership_type_pk, org_pk = membership_claim_pks
        response = client.post("/api/v1/register", json={
            "first_name": "LoginBlocked",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}blocked@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": True,
            "membership_type_master_data_pk": membership_type_pk,
            "organization_pk": org_pk,
            "claimed_local_sakha_number": "SEC1",
        })
        assert response.status_code == 201, response.json()
        data = response.json()

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT account_status FROM nss.user_account WHERE person_pk = %s",
                (data["person_pk"],),
            )
            assert cur.fetchone()[0] == "PENDING_APPROVAL"

        # No Sangha Sevi ID exists until approval, so the Person ID is not a valid
        # login. 401 = unknown ID, 403 = known but PENDING_APPROVAL; both block.
        response = client.post("/api/v1/auth/login", json={
            "login_id": data["person_id"],
            "password": TEST_PASSWORD,
        })
        assert response.status_code in (401, 403)

    def test_registration_without_membership_creates_no_account(
        self, client, gender_pk, write_conn, reg_address
    ):
        """A membership-less registrant gets a person only — an account with no path
        to a Sangha Sevi could never log in, and the typed password is not persisted."""
        response = client.post("/api/v1/register", json={
            "first_name": "NoAccount",
            "last_name": "Test",
            "date_of_birth": TEST_DOB,
            "gender_master_data_pk": gender_pk,
            "email": f"{TEST_EMAIL_PREFIX}noaccount@test.example",
            "password": TEST_PASSWORD,
            **reg_address,
            "has_membership": False,
        })
        assert response.status_code == 201
        data = response.json()
        with write_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM nss.user_account WHERE person_pk = %s", (data["person_pk"],))
            assert cur.fetchone() is None
        login = client.post("/api/v1/auth/login", json={
            "login_id": data["person_id"], "password": TEST_PASSWORD,
        })
        assert login.status_code == 401


# ── Claim Approval Tests ───────────────────────────────────────────────

class TestClaimApproval:
    """GET/POST /api/v1/admin/claims — auth gate."""

    def test_unauthenticated_cannot_list_claims(self, client):
        """Unauthenticated request to claims endpoint returns 401."""
        response = client.get("/api/v1/admin/claims")
        assert response.status_code == 401


# ── Previously-registered lookup / claim: public, non-enumerating ───────

def _orphan_person(write_conn, label):
    """Throwaway person with TEST_DOB and no account / claim / Sangha Sevi."""
    suffix = uuid4().hex[:10].upper()
    with write_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO nss.person (person_id, first_name, last_name, email, date_of_birth) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING person_pk, person_id",
            (f"TSL{label}{suffix}", f"Sec{label}", suffix,
             f"tsl.{label.lower()}.{suffix.lower()}@example.test", TEST_DOB),
        )
        person_pk, person_id = cur.fetchone()
    return {"person_pk": str(person_pk), "person_id": person_id}


class TestLookupAndClaimPublicSurface:
    """POST /register/lookup-existing and /register/claim are unauthenticated by design."""

    LOOKUP = "/api/v1/register/lookup-existing"
    CLAIM = "/api/v1/register/claim"

    def test_lookup_needs_no_token_and_ignores_a_bad_one(self, anon_client, write_conn):
        person = _orphan_person(write_conn, "PUB")
        body = {"person_id": person["person_id"], "date_of_birth": TEST_DOB}
        assert anon_client.post(self.LOOKUP, json=body).status_code == 200
        # A garbage Authorization header must not turn a public endpoint into a 401.
        resp = anon_client.post(
            self.LOOKUP, json=body, headers={"Authorization": "Bearer not.a.jwt"}
        )
        assert resp.status_code == 200, resp.text

    def test_claim_needs_no_token(self, anon_client, write_conn, membership_claim_pks):
        type_pk, org_pk = membership_claim_pks
        person = _orphan_person(write_conn, "CLM")
        resp = anon_client.post(self.CLAIM, json={
            "person_id": person["person_id"],
            "date_of_birth": TEST_DOB,
            "membership_type_master_data_pk": type_pk,
            "organization_pk": org_pk,
            "password": TEST_PASSWORD,
        })
        assert resp.status_code == 201, resp.text

    def test_wrong_dob_and_unknown_person_are_indistinguishable(
        self, anon_client, write_conn
    ):
        """No person-id enumeration: both failures return the same 404 and detail."""
        person = _orphan_person(write_conn, "ENUM")
        wrong_dob = anon_client.post(self.LOOKUP, json={
            "person_id": person["person_id"], "date_of_birth": "1990-12-31",
        })
        unknown = anon_client.post(self.LOOKUP, json={
            "person_id": f"NOSUCH{uuid4().hex[:10].upper()}", "date_of_birth": TEST_DOB,
        })
        assert wrong_dob.status_code == unknown.status_code == 404
        assert wrong_dob.json() == unknown.json()

    def test_claim_re_verifies_dob_and_creates_nothing(
        self, anon_client, write_conn, membership_claim_pks
    ):
        type_pk, org_pk = membership_claim_pks
        person = _orphan_person(write_conn, "BADDOB")
        resp = anon_client.post(self.CLAIM, json={
            "person_id": person["person_id"],
            "date_of_birth": "1990-12-31",
            "membership_type_master_data_pk": type_pk,
            "organization_pk": org_pk,
            "password": TEST_PASSWORD,
        })
        assert resp.status_code == 404, resp.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM nss.user_account WHERE person_pk = %s", (person["person_pk"],)
            )
            assert cur.fetchone() is None

    def test_responses_never_leak_credentials(
        self, anon_client, write_conn, membership_claim_pks
    ):
        type_pk, org_pk = membership_claim_pks
        person = _orphan_person(write_conn, "LEAK")
        look = anon_client.post(self.LOOKUP, json={
            "person_id": person["person_id"], "date_of_birth": TEST_DOB,
        })
        claim = anon_client.post(self.CLAIM, json={
            "person_id": person["person_id"],
            "date_of_birth": TEST_DOB,
            "membership_type_master_data_pk": type_pk,
            "organization_pk": org_pk,
            "password": TEST_PASSWORD,
        })
        for resp in (look, claim):
            text = resp.text.lower()
            assert "password" not in text and "argon2" not in text
            assert "access_token" not in text

    def test_claimant_cannot_login_until_approved(
        self, anon_client, write_conn, membership_claim_pks
    ):
        type_pk, org_pk = membership_claim_pks
        person = _orphan_person(write_conn, "NOLOGIN")
        resp = anon_client.post(self.CLAIM, json={
            "person_id": person["person_id"],
            "date_of_birth": TEST_DOB,
            "membership_type_master_data_pk": type_pk,
            "organization_pk": org_pk,
            "password": TEST_PASSWORD,
        })
        assert resp.status_code == 201, resp.text
        login = anon_client.post("/api/v1/auth/login", json={
            "login_id": person["person_id"], "password": TEST_PASSWORD,
        })
        assert login.status_code == 401
