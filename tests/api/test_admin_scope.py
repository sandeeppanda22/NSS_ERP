"""
NSS ERP — Admin router: admin-scope (ADMIN-BR-076/077) and previously-uncovered endpoints.

tests/api/test_admin.py covers the admin CRUD happy paths and a few scope
cases (Sakha auto-select); this file closes the rest of the endpoint x test
matrix for api/routers/admin.py:

  Previously UNTESTED endpoints
    GET   /admin/sangha-sevi/without-account
    GET   /admin/sangha-sevi/check/{person_pk}
    POST  /admin/sangha-sevi/check-batch
    GET   /admin/users/check-account/{person_pk}
    GET   /admin/persons/{pk}                 PATCH /admin/persons/{pk}
    GET   /admin/organizations/code-availability
    GET   /admin/dashboard-stats
    PATCH /admin/patra/{patra_type}/{patra_pk}/document-number

  Scope-subtree violations (a Sakha-scoped admin reaching a DIFFERENT Sakha's
  data) for endpoints whose scope gate had no test:
    users list / detail / roles list / reset-password / status / delete,
    POST /users, organizations list / PATCH / short-code,
    credentials list / timeline / issue / promote, patra correction.

Identities: the NSS-wide admin comes from tests.api.test_admin (`admin_user`
-> NSS_ERP_ADMIN + NSS-WIDE); the scoped admin is that module's
`sakha_admin_headers` (NSS_ERP_SAKHA_ADMIN scoped to ONE Sakha, two_sakhas[0],
holding PERSON_MANAGE / MEMBERSHIP_APPROVE / MEMBERSHIP_MANAGE /
ORGANIZATION_VIEW but none of ADMIN_USER_* / ADMIN_ROLE_MANAGE). two_sakhas[1]
is the out-of-scope Sakha. 401/403 permission gating lives in
tests/security/test_admin_surface_security.py.

Everything rolls back with the module SAVEPOINT (tests/conftest.py).
"""

import pytest
from uuid import uuid4

# Fixtures reused by name (pytest resolves them from this module's namespace).
from tests.api.test_admin import (  # noqa: F401
    admin_user, admin_tokens, admin_headers, gender_pk, two_sakhas,
    regular_membership_type_pk, sakha_admin_headers, target_person_pk,
)
from tests.api.test_admin_credentials import (  # noqa: F401
    membership_type_pks, active_status_pk,
    _create_person, _create_darshaka_member, _create_member_without_credential,
)
from tests.registration_support import add_user_account


pytestmark = pytest.mark.integration

MEMBER_PASSWORD = "ScopeMember1x"
RANDOM_UUID = "00000000-0000-0000-0000-0000000000aa"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sakha_a(write_conn, two_sakhas):
    """The Sakha the scoped admin administers (short_code ensured for member creation)."""
    return _with_short_code(write_conn, two_sakhas[0])


@pytest.fixture(scope="module")
def sakha_b(write_conn, two_sakhas):
    """A second Sakha that is OUTSIDE the scoped admin's scope."""
    if len(two_sakhas) < 2:
        pytest.skip("Need two active SAKHA_SANGHA organizations.")
    return _with_short_code(write_conn, two_sakhas[1])


def _with_short_code(write_conn, org_pk):
    cur = write_conn.cursor()
    cur.execute("SELECT short_code FROM nss.organization WHERE organization_pk = %s", (org_pk,))
    if not cur.fetchone()[0]:
        cur.execute(
            "UPDATE nss.organization SET short_code = %s WHERE organization_pk = %s",
            (f"Z{uuid4().hex[:3].upper()}", org_pk),
        )
    return org_pk


def _member_with_account(write_conn, org_pk, type_pk, status_pk, label):
    """Sangha Sevi in *org_pk* with an ACTIVE login account (direct SQL, no credential)."""
    member = _create_member_without_credential(write_conn, org_pk, type_pk, status_pk, label)
    member["user_account_pk"] = add_user_account(
        write_conn, member["person_pk"], MEMBER_PASSWORD, status="ACTIVE",
    )
    return member


@pytest.fixture(scope="module")
def regular_type(membership_type_pks):
    return membership_type_pks["REGULAR"]


@pytest.fixture
def in_scope_member(write_conn, sakha_a, regular_type, active_status_pk):
    return _member_with_account(write_conn, sakha_a, regular_type, active_status_pk, "INS")


@pytest.fixture
def out_of_scope_member(write_conn, sakha_b, regular_type, active_status_pk):
    return _member_with_account(write_conn, sakha_b, regular_type, active_status_pk, "OUT")


def _person_row(write_conn, person_pk):
    cur = write_conn.cursor()
    cur.execute(
        "SELECT first_name, remarks, is_active FROM nss.person WHERE person_pk = %s",
        (person_pk,),
    )
    return cur.fetchone()


def _account_status(write_conn, user_account_pk):
    cur = write_conn.cursor()
    cur.execute(
        "SELECT account_status, is_active FROM nss.user_account WHERE user_account_pk = %s",
        (user_account_pk,),
    )
    return cur.fetchone()


# ═══════════════════════════════════════════════════════════════════════
# GET /sangha-sevi/without-account
# ═══════════════════════════════════════════════════════════════════════

class TestSanghaSeviWithoutAccount:
    URL = "/api/v1/admin/sangha-sevi/without-account"

    @pytest.fixture
    def accountless(self, write_conn, sakha_a, regular_type, active_status_pk):
        return _create_member_without_credential(
            write_conn, sakha_a, regular_type, active_status_pk, "NOACC",
        )

    def test_lists_member_without_any_account(self, client, admin_headers, accountless):
        resp = client.get(self.URL, headers=admin_headers,
                          params={"search": accountless["sangha_sevi_id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert {"members", "total", "page", "page_size"} <= data.keys()
        ids = {m["sangha_sevi_id"]: m for m in data["members"]}
        assert accountless["sangha_sevi_id"] in ids
        assert ids[accountless["sangha_sevi_id"]]["has_deleted_account"] is False

    def test_member_with_live_account_is_excluded(
        self, client, admin_headers, in_scope_member
    ):
        resp = client.get(self.URL, headers=admin_headers,
                          params={"search": in_scope_member["sangha_sevi_id"]})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_soft_deleted_account_is_reported_not_hidden(
        self, client, admin_headers, write_conn, sakha_a, regular_type, active_status_pk
    ):
        """uq_user_account_person occupies the slot, so the row is flagged — the
        'Create Account' picker reactivates it in place."""
        member = _create_member_without_credential(
            write_conn, sakha_a, regular_type, active_status_pk, "DELACC",
        )
        add_user_account(write_conn, member["person_pk"], MEMBER_PASSWORD, is_active=False)
        resp = client.get(self.URL, headers=admin_headers,
                          params={"search": member["sangha_sevi_id"]})
        assert resp.status_code == 200
        rows = resp.json()["members"]
        assert [r["sangha_sevi_id"] for r in rows] == [member["sangha_sevi_id"]]
        assert rows[0]["has_deleted_account"] is True

    def test_scoped_admin_sees_only_in_scope_members(
        self, client, sakha_admin_headers, write_conn, sakha_a, sakha_b,
        regular_type, active_status_pk
    ):
        mine = _create_member_without_credential(write_conn, sakha_a, regular_type, active_status_pk, "SCA")
        theirs = _create_member_without_credential(write_conn, sakha_b, regular_type, active_status_pk, "SCB")
        seen_mine = client.get(self.URL, headers=sakha_admin_headers,
                               params={"search": mine["sangha_sevi_id"]}).json()
        seen_theirs = client.get(self.URL, headers=sakha_admin_headers,
                                 params={"search": theirs["sangha_sevi_id"]}).json()
        assert [m["sangha_sevi_id"] for m in seen_mine["members"]] == [mine["sangha_sevi_id"]]
        assert seen_theirs["total"] == 0 and seen_theirs["members"] == []

    @pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
    def test_pagination_bounds_are_422(self, client, admin_headers, params):
        assert client.get(self.URL, headers=admin_headers, params=params).status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /sangha-sevi/check/{person_pk}  ·  POST /sangha-sevi/check-batch
# GET /users/check-account/{person_pk}
# ═══════════════════════════════════════════════════════════════════════

class TestSanghaSeviChecks:

    def test_check_person_with_sangha_sevi(self, client, admin_headers, in_scope_member):
        resp = client.get(
            f"/api/v1/admin/sangha-sevi/check/{in_scope_member['person_pk']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "has_sangha_sevi": True, "sangha_sevi_id": in_scope_member["sangha_sevi_id"],
        }

    def test_check_person_without_sangha_sevi(self, client, admin_headers, target_person_pk):
        resp = client.get(
            f"/api/v1/admin/sangha-sevi/check/{target_person_pk}", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"has_sangha_sevi": False, "sangha_sevi_id": None}

    def test_check_malformed_person_pk_is_422(self, client, admin_headers):
        resp = client.get("/api/v1/admin/sangha-sevi/check/not-a-uuid", headers=admin_headers)
        assert resp.status_code == 422

    def test_batch_reports_sangha_sevi_and_pending_claim(
        self, client, admin_headers, write_conn, in_scope_member, target_person_pk,
        sakha_a, regular_type
    ):
        # A person whose only link is a PENDING registration claim.
        claimant = _create_person(write_conn, "BATCH")
        ua_pk = add_user_account(write_conn, str(claimant), MEMBER_PASSWORD)
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.registration_claim (
                    user_account_pk, person_pk, claimed_organization_pk,
                    claimed_membership_type_master_data_pk,
                    claimed_local_sakha_number, claim_status
                ) VALUES (%s, %s, %s, %s, 'B1', 'PENDING') RETURNING registration_claim_pk
            """, (ua_pk, str(claimant), sakha_a, regular_type))
            claim_pk = str(cur.fetchone()[0])

        resp = client.post("/api/v1/admin/sangha-sevi/check-batch", headers=admin_headers, json={
            "person_pks": [in_scope_member["person_pk"], str(claimant), str(target_person_pk)],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data[in_scope_member["person_pk"]] == {"sangha_sevi_id": in_scope_member["sangha_sevi_id"]}
        assert data[str(claimant)]["pending_claim_pk"] == claim_pk
        assert "pending_claim_org" in data[str(claimant)]
        # Persons with neither are simply absent from the map.
        assert str(target_person_pk) not in data

    @pytest.mark.parametrize("body", [{}, {"person_pks": []}])
    def test_batch_empty_input_returns_empty_map(self, client, admin_headers, body):
        resp = client.post("/api/v1/admin/sangha-sevi/check-batch", headers=admin_headers, json=body)
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_batch_over_100_returns_empty_map(self, client, admin_headers):
        resp = client.post("/api/v1/admin/sangha-sevi/check-batch", headers=admin_headers, json={
            "person_pks": [str(uuid4()) for _ in range(101)],
        })
        assert resp.status_code == 200
        assert resp.json() == {}

    @pytest.mark.parametrize("body", [
        {"person_pks": "not-a-list"}, {"person_pks": ["not-a-uuid"]},
        {"person_pks": [123]}, {"person_pks": None},
    ])
    def test_batch_malformed_person_pks_is_422(self, client, admin_headers, body):
        resp = client.post("/api/v1/admin/sangha-sevi/check-batch", headers=admin_headers, json=body)
        assert resp.status_code == 422

    def test_batch_non_object_body_is_422(self, client, admin_headers):
        resp = client.post("/api/v1/admin/sangha-sevi/check-batch", headers=admin_headers,
                           json=[RANDOM_UUID])
        assert resp.status_code == 422

    def test_check_account_states(self, client, admin_headers, write_conn, target_person_pk):
        url = "/api/v1/admin/users/check-account/{}"
        person = _create_person(write_conn, "CHKACC")

        none = client.get(url.format(person), headers=admin_headers)
        assert none.status_code == 200
        assert none.json() == {"has_account": False, "is_active": None}

        add_user_account(write_conn, str(person), MEMBER_PASSWORD, status="ACTIVE")
        live = client.get(url.format(person), headers=admin_headers)
        assert live.json() == {"has_account": True, "is_active": True}

        deleted_person = _create_person(write_conn, "CHKDEL")
        add_user_account(write_conn, str(deleted_person), MEMBER_PASSWORD, is_active=False)
        gone = client.get(url.format(deleted_person), headers=admin_headers)
        assert gone.json() == {"has_account": True, "is_active": False}

    def test_check_account_malformed_pk_is_422(self, client, admin_headers):
        resp = client.get("/api/v1/admin/users/check-account/not-a-uuid", headers=admin_headers)
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET / PATCH /persons/{pk}
# ═══════════════════════════════════════════════════════════════════════

class TestPersonProfile:

    def test_get_profile(self, client, admin_headers, in_scope_member):
        resp = client.get(f"/api/v1/admin/persons/{in_scope_member['person_pk']}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["person_pk"] == in_scope_member["person_pk"]
        assert data["first_name"].startswith("Test")
        assert {"middle_name", "last_name", "date_of_birth", "email", "remarks"} <= data.keys()

    def test_get_unknown_person_is_404(self, client, admin_headers):
        resp = client.get(f"/api/v1/admin/persons/{RANDOM_UUID}", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_malformed_pk_is_422(self, client, admin_headers):
        assert client.get("/api/v1/admin/persons/nope", headers=admin_headers).status_code == 422

    def test_patch_updates_and_persists(self, client, admin_headers, write_conn, in_scope_member):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers,
            json={"remarks": "corrected by scope test", "reason": "typo in registration"},
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["message"] == "Profile updated."
        assert _person_row(write_conn, in_scope_member["person_pk"])[1] == "corrected by scope test"
        # GET reflects the PATCH 1:1 (the edit form pre-fill contract).
        got = client.get(f"/api/v1/admin/persons/{in_scope_member['person_pk']}", headers=admin_headers)
        assert got.json()["remarks"] == "corrected by scope test"

    def test_patch_name_is_title_cased(self, client, admin_headers, write_conn, in_scope_member):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"first_name": "  renamed person "},
        )
        assert resp.status_code == 200
        assert _person_row(write_conn, in_scope_member["person_pk"])[0] == "Renamed Person"

    def test_patch_empty_body_is_422(self, client, admin_headers, in_scope_member):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}", headers=admin_headers, json={},
        )
        assert resp.status_code == 422
        assert "No fields to update" in resp.json()["detail"]

    def test_patch_blank_first_name_is_422(self, client, admin_headers, in_scope_member):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"first_name": "   "},
        )
        assert resp.status_code == 422
        assert "blank" in resp.json()["detail"].lower()

    def test_patch_invalid_email_is_422(self, client, admin_headers, in_scope_member):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_patch_duplicate_email_is_409(self, client, admin_headers, write_conn, in_scope_member):
        other = _create_person(write_conn, "DUPEM")
        with write_conn.cursor() as cur:
            cur.execute("SELECT email FROM nss.person WHERE person_pk = %s", (str(other),))
            taken = cur.fetchone()[0]
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"email": taken},
        )
        assert resp.status_code == 409

    def test_patch_wrong_master_data_category_is_422(
        self, client, admin_headers, in_scope_member, regular_membership_type_pk
    ):
        """A MEMBERSHIP_TYPE pk may not be stored in the gender column."""
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"gender_master_data_pk": regular_membership_type_pk},
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("dob", ["not-a-date", "2020-13-45", "15/01/2000"])
    def test_patch_bad_date_of_birth_is_422(self, client, admin_headers, in_scope_member, dob):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"date_of_birth": dob},
        )
        assert resp.status_code == 422

    def test_patch_valid_date_of_birth_is_applied(self, client, admin_headers, in_scope_member):
        resp = client.patch(
            f"/api/v1/admin/persons/{in_scope_member['person_pk']}",
            headers=admin_headers, json={"date_of_birth": "1990-05-17"},
        )
        assert resp.status_code == 200, resp.json()

    def test_patch_unknown_person_is_404(self, client, admin_headers):
        resp = client.patch(
            f"/api/v1/admin/persons/{RANDOM_UUID}", headers=admin_headers, json={"remarks": "x"},
        )
        assert resp.status_code == 404

    # ── ADMIN-BR-076/077 ────────────────────────────────────────────────

    def test_scoped_admin_reads_and_edits_in_scope_person(
        self, client, sakha_admin_headers, write_conn, in_scope_member
    ):
        url = f"/api/v1/admin/persons/{in_scope_member['person_pk']}"
        assert client.get(url, headers=sakha_admin_headers).status_code == 200
        assert client.patch(url, headers=sakha_admin_headers, json={"remarks": "in scope"}).status_code == 200

    def test_scoped_admin_cannot_read_or_edit_out_of_scope_person(
        self, client, sakha_admin_headers, write_conn, out_of_scope_member
    ):
        url = f"/api/v1/admin/persons/{out_of_scope_member['person_pk']}"
        assert client.get(url, headers=sakha_admin_headers).status_code == 403
        denied = client.patch(url, headers=sakha_admin_headers, json={"remarks": "tamper"})
        assert denied.status_code == 403
        assert _person_row(write_conn, out_of_scope_member["person_pk"])[1] != "tamper"

    def test_person_without_sangha_sevi_is_global_authority_only(
        self, client, admin_headers, sakha_admin_headers, target_person_pk
    ):
        """ADMIN-BR-077: a person with no organizational anchor is reachable only by
        the global authority; permission alone never confers global reach."""
        url = f"/api/v1/admin/persons/{target_person_pk}"
        assert client.get(url, headers=admin_headers).status_code == 200
        assert client.get(url, headers=sakha_admin_headers).status_code == 403
        assert client.patch(url, headers=sakha_admin_headers, json={"remarks": "x"}).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# GET /organizations/code-availability
# ═══════════════════════════════════════════════════════════════════════

class TestOrganizationCodeAvailability:
    URL = "/api/v1/admin/organizations/code-availability"

    @pytest.fixture
    def org_with_codes(self, write_conn, sakha_a):
        code = f"Q{uuid4().hex[:4].upper()}"
        with write_conn.cursor() as cur:
            cur.execute(
                "UPDATE nss.organization SET short_code = %s WHERE organization_pk = %s "
                "RETURNING organization_code",
                (code, sakha_a),
            )
            org_code = cur.fetchone()[0]
        if not org_code:
            pytest.skip("Sakha has no organization_code to probe.")
        return {"organization_pk": sakha_a, "short_code": code, "organization_code": org_code}

    def test_taken_short_code_reports_conflict(self, client, admin_headers, org_with_codes):
        resp = client.get(self.URL, headers=admin_headers,
                          params={"field": "short_code", "value": org_with_codes["short_code"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["conflict"]["organization_pk"] == org_with_codes["organization_pk"]
        assert data["conflict"]["is_active"] is True

    def test_short_code_comparison_is_case_insensitive(self, client, admin_headers, org_with_codes):
        resp = client.get(self.URL, headers=admin_headers, params={
            "field": "short_code", "value": f"  {org_with_codes['short_code'].lower()} ",
        })
        data = resp.json()
        assert data["available"] is False
        assert data["value"] == org_with_codes["short_code"]

    def test_taken_organization_code_reports_conflict(self, client, admin_headers, org_with_codes):
        resp = client.get(self.URL, headers=admin_headers, params={
            "field": "organization_code", "value": org_with_codes["organization_code"],
        })
        assert resp.json()["available"] is False

    def test_free_value_is_available(self, client, admin_headers):
        resp = client.get(self.URL, headers=admin_headers, params={
            "field": "short_code", "value": f"F{uuid4().hex[:4].upper()}",
        })
        assert resp.status_code == 200
        assert resp.json()["available"] is True
        assert resp.json()["conflict"] is None

    def test_exclude_pk_ignores_the_row_being_edited(self, client, admin_headers, org_with_codes):
        resp = client.get(self.URL, headers=admin_headers, params={
            "field": "short_code", "value": org_with_codes["short_code"],
            "exclude_pk": org_with_codes["organization_pk"],
        })
        assert resp.json()["available"] is True

    def test_blank_value_is_available(self, client, admin_headers):
        resp = client.get(self.URL, headers=admin_headers, params={"field": "short_code", "value": "   "})
        assert resp.status_code == 200
        assert resp.json()["available"] is True

    def test_unknown_field_is_422(self, client, admin_headers):
        resp = client.get(self.URL, headers=admin_headers, params={"field": "org_name", "value": "x"})
        assert resp.status_code == 422

    @pytest.mark.parametrize("params", [{"field": "short_code"}, {"value": "ABC"}])
    def test_missing_param_is_422(self, client, admin_headers, params):
        assert client.get(self.URL, headers=admin_headers, params=params).status_code == 422

    def test_scoped_admin_with_person_manage_may_call_it(self, client, sakha_admin_headers):
        resp = client.get(self.URL, headers=sakha_admin_headers,
                          params={"field": "short_code", "value": "ZZZZ9"})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# GET /dashboard-stats
# ═══════════════════════════════════════════════════════════════════════

class TestDashboardStats:
    URL = "/api/v1/admin/dashboard-stats"
    KEYS = {
        "members", "families", "renewals_due", "anchalika_sanghas", "zilla_sanghas",
        "patha_chakras", "paribarik_sanghas", "sakha_sanghas", "mahila_sanghas",
        "attendance_pct", "attendance_tracked",
    }

    def test_nss_wide_shape(self, client, admin_headers):
        resp = client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data) == self.KEYS
        assert isinstance(data["members"], int) and data["members"] >= 1
        assert isinstance(data["attendance_tracked"], bool)

    def test_scoped_admin_is_bounded_by_global_totals(
        self, client, admin_headers, sakha_admin_headers
    ):
        total = client.get(self.URL, headers=admin_headers).json()
        mine = client.get(self.URL, headers=sakha_admin_headers).json()
        assert set(mine) == self.KEYS
        assert 1 <= mine["members"] <= total["members"]
        assert mine["sakha_sanghas"] <= total["sakha_sanghas"]

    def test_org_pk_inside_scope_is_allowed(self, client, sakha_admin_headers, sakha_a):
        resp = client.get(self.URL, headers=sakha_admin_headers, params={"org_pk": sakha_a})
        assert resp.status_code == 200
        assert resp.json()["members"] >= 1

    def test_org_pk_outside_scope_is_403(self, client, sakha_admin_headers, sakha_b):
        resp = client.get(self.URL, headers=sakha_admin_headers, params={"org_pk": sakha_b})
        assert resp.status_code == 403

    def test_garbage_org_pk_is_403_for_scoped_admin(self, client, sakha_admin_headers):
        resp = client.get(self.URL, headers=sakha_admin_headers, params={"org_pk": "not-a-uuid"})
        assert resp.status_code == 403

    def test_nss_wide_may_scope_to_any_org(self, client, admin_headers, sakha_b):
        resp = client.get(self.URL, headers=admin_headers, params={"org_pk": sakha_b})
        assert resp.status_code == 200
        assert set(resp.json()) == self.KEYS


# ═══════════════════════════════════════════════════════════════════════
# PATCH /patra/{patra_type}/{patra_pk}/document-number
# ═══════════════════════════════════════════════════════════════════════

def _anumati_for(write_conn, sangha_sevi_pk):
    cur = write_conn.cursor()
    cur.execute(
        "SELECT anumati_patra_pk, document_number, issue_date FROM nss.anumati_patra "
        "WHERE sangha_sevi_pk = %s",
        (sangha_sevi_pk,),
    )
    pk, number, issue_date = cur.fetchone()
    return {"pk": str(pk), "document_number": number, "issue_date": issue_date}


class TestCorrectPatraNumber:

    @pytest.fixture(scope="class")
    @classmethod
    def patras(cls, client, admin_headers, write_conn, sakha_a, sakha_b, membership_type_pks):
        in_member = _create_darshaka_member(client, admin_headers, write_conn, sakha_a, membership_type_pks)
        out_member = _create_darshaka_member(client, admin_headers, write_conn, sakha_b, membership_type_pks)
        # Anumati numbers are unique only WITHIN an issuing Sakha
        # (uq_ap_document_number), so a collision needs a second Patra in
        # the SAME Sakha as "in".
        twin_member = _create_darshaka_member(client, admin_headers, write_conn, sakha_a, membership_type_pks)
        return {
            "in": _anumati_for(write_conn, in_member["sangha_sevi_pk"]),
            "out": _anumati_for(write_conn, out_member["sangha_sevi_pk"]),
            "twin": _anumati_for(write_conn, twin_member["sangha_sevi_pk"]),
        }

    @staticmethod
    def _url(patra_type, pk):
        return f"/api/v1/admin/patra/{patra_type}/{pk}/document-number"

    @staticmethod
    def _expected(number, issue_date):
        from api.helpers import patra_year_pair
        start, end = patra_year_pair(issue_date)
        return f"{number}/{start}/{end}"

    def test_bare_number_gets_issue_year_appended(self, client, admin_headers, write_conn, patras):
        number = str(500000 + uuid4().int % 400000)
        resp = client.patch(
            self._url("anumati", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": number, "reason": "mis-keyed at approval"},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        expected = self._expected(number, patras["in"]["issue_date"])
        assert data["document_number"] == expected
        assert data["previous_document_number"] == patras["in"]["document_number"]
        assert data["patra_type"] == "anumati"
        assert _anumati_for(write_conn, _sevi_of(write_conn, patras["in"]["pk"]))["document_number"] == expected
        patras["in"]["document_number"] = expected  # chain later tests off the new value

    def test_same_number_is_a_noop_200(self, client, admin_headers, patras):
        resp = client.patch(
            self._url("anumati", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": patras["in"]["document_number"]},
        )
        assert resp.status_code == 200
        assert resp.json()["document_number"] == resp.json()["previous_document_number"]

    def test_patra_type_is_case_and_space_insensitive(self, client, admin_headers, patras):
        resp = client.patch(
            self._url("%20ANUMATI%20", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": patras["in"]["document_number"]},
        )
        assert resp.status_code == 200
        assert resp.json()["patra_type"] == "anumati"

    def test_full_number_with_wrong_year_is_422(self, client, admin_headers, patras):
        resp = client.patch(
            self._url("anumati", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": "7/1990/1991"},
        )
        assert resp.status_code == 422
        assert "wrong year" in resp.json()["detail"]

    @pytest.mark.parametrize("bad", ["abc", "12/xx/yy", "1/2/3/4"])
    def test_malformed_number_is_422(self, client, admin_headers, patras, bad):
        resp = client.patch(
            self._url("anumati", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": bad},
        )
        assert resp.status_code == 422

    def test_blank_number_is_422(self, client, admin_headers, patras):
        resp = client.patch(
            self._url("anumati", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": "  "},
        )
        assert resp.status_code == 422
        assert "required" in resp.json()["detail"]

    def test_missing_number_and_overlong_number_are_422(self, client, admin_headers, patras):
        url = self._url("anumati", patras["in"]["pk"])
        assert client.patch(url, headers=admin_headers, json={}).status_code == 422
        assert client.patch(url, headers=admin_headers,
                            json={"document_number": "1" * 31}).status_code == 422

    def test_unknown_patra_type_is_422(self, client, admin_headers, patras):
        resp = client.patch(
            self._url("aadhaar", patras["in"]["pk"]), headers=admin_headers,
            json={"document_number": "1"},
        )
        assert resp.status_code == 422
        assert "parichaya" in resp.json()["detail"]

    def test_unknown_patra_is_404(self, client, admin_headers):
        resp = client.patch(self._url("anumati", RANDOM_UUID), headers=admin_headers,
                            json={"document_number": "1"})
        assert resp.status_code == 404

    def test_wrong_table_for_pk_is_404(self, client, admin_headers, patras):
        """An Anumati pk looked up as a Parichaya Patra does not exist there."""
        resp = client.patch(self._url("parichaya", patras["in"]["pk"]), headers=admin_headers,
                            json={"document_number": "1"})
        assert resp.status_code == 404

    def test_malformed_pk_is_422(self, client, admin_headers):
        resp = client.patch(self._url("anumati", "nope"), headers=admin_headers,
                            json={"document_number": "1"})
        assert resp.status_code == 422

    def test_number_already_in_use_is_409(self, client, admin_headers, write_conn, patras):
        """Anumati document_number is UNIQUE per issuing Sakha; a collision inside
        one Sakha is a clean 409 and the transaction survives (SAVEPOINT)."""
        resp = client.patch(
            self._url("anumati", patras["twin"]["pk"]), headers=admin_headers,
            json={"document_number": patras["in"]["document_number"]},
        )
        assert resp.status_code == 409
        assert "already in use" in resp.json()["detail"]
        # the transaction is still usable afterwards
        assert client.get(f"/api/v1/admin/persons/{RANDOM_UUID}", headers=admin_headers).status_code == 404

    def test_scoped_admin_corrects_in_scope_patra(self, client, sakha_admin_headers, patras):
        number = str(500000 + uuid4().int % 400000)
        resp = client.patch(
            self._url("anumati", patras["in"]["pk"]), headers=sakha_admin_headers,
            json={"document_number": number},
        )
        assert resp.status_code == 200, resp.json()

    def test_scoped_admin_cannot_correct_out_of_scope_patra(
        self, client, sakha_admin_headers, write_conn, patras
    ):
        before = patras["out"]["document_number"]
        resp = client.patch(
            self._url("anumati", patras["out"]["pk"]), headers=sakha_admin_headers,
            json={"document_number": str(500000 + uuid4().int % 400000)},
        )
        assert resp.status_code == 403
        cur = write_conn.cursor()
        cur.execute("SELECT document_number FROM nss.anumati_patra WHERE anumati_patra_pk = %s",
                    (patras["out"]["pk"],))
        assert cur.fetchone()[0] == before


def _sevi_of(write_conn, anumati_patra_pk):
    cur = write_conn.cursor()
    cur.execute("SELECT sangha_sevi_pk FROM nss.anumati_patra WHERE anumati_patra_pk = %s",
                (anumati_patra_pk,))
    return str(cur.fetchone()[0])


# ═══════════════════════════════════════════════════════════════════════
# Scope-subtree violations — users and roles
# ═══════════════════════════════════════════════════════════════════════

class TestUserEndpointsAdminScope:

    def test_list_users_filters_to_scope(
        self, client, admin_headers, sakha_admin_headers, in_scope_member, out_of_scope_member
    ):
        def ids(headers, member):
            body = client.get("/api/v1/admin/users", headers=headers,
                              params={"search": member["sangha_sevi_id"]}).json()
            return [u["sangha_sevi_id"] for u in body["users"]]

        assert ids(admin_headers, in_scope_member) == [in_scope_member["sangha_sevi_id"]]
        assert ids(admin_headers, out_of_scope_member) == [out_of_scope_member["sangha_sevi_id"]]
        assert ids(sakha_admin_headers, in_scope_member) == [in_scope_member["sangha_sevi_id"]]
        assert ids(sakha_admin_headers, out_of_scope_member) == []

    def test_get_user_detail(self, client, sakha_admin_headers, in_scope_member, out_of_scope_member):
        ok = client.get(f"/api/v1/admin/users/{in_scope_member['user_account_pk']}",
                        headers=sakha_admin_headers)
        assert ok.status_code == 200
        assert ok.json()["sangha_sevi_id"] == in_scope_member["sangha_sevi_id"]
        denied = client.get(f"/api/v1/admin/users/{out_of_scope_member['user_account_pk']}",
                            headers=sakha_admin_headers)
        assert denied.status_code == 403
        assert "outside your admin scope" in denied.json()["detail"]

    def test_list_roles_for_account(
        self, client, sakha_admin_headers, in_scope_member, out_of_scope_member
    ):
        ok = client.get(f"/api/v1/admin/users/{in_scope_member['user_account_pk']}/roles",
                        headers=sakha_admin_headers)
        assert ok.status_code == 200 and ok.json() == []
        denied = client.get(f"/api/v1/admin/users/{out_of_scope_member['user_account_pk']}/roles",
                            headers=sakha_admin_headers)
        assert denied.status_code == 403

    def test_reset_password(
        self, client, sakha_admin_headers, write_conn, in_scope_member, out_of_scope_member
    ):
        body = {"new_password": "ResetByScope9x", "force_password_change": False}
        denied = client.post(
            f"/api/v1/admin/users/{out_of_scope_member['user_account_pk']}/reset-password",
            headers=sakha_admin_headers, json=body,
        )
        assert denied.status_code == 403
        ok = client.post(
            f"/api/v1/admin/users/{in_scope_member['user_account_pk']}/reset-password",
            headers=sakha_admin_headers, json=body,
        )
        assert ok.status_code == 200
        # The reset password actually works for login (Sangha Sevi ID + new password).
        login = client.post("/api/v1/auth/login", json={
            "login_id": in_scope_member["sangha_sevi_id"], "password": "ResetByScope9x",
        })
        assert login.status_code == 200

    def test_reset_password_unknown_account_is_404(self, client, admin_headers):
        resp = client.post(f"/api/v1/admin/users/{RANDOM_UUID}/reset-password",
                           headers=admin_headers, json={"new_password": "ResetByScope9x"})
        assert resp.status_code == 404

    def test_reset_password_policy_violation_is_422(self, client, admin_headers, in_scope_member):
        resp = client.post(
            f"/api/v1/admin/users/{in_scope_member['user_account_pk']}/reset-password",
            headers=admin_headers, json={"new_password": "alllowercase1"},
        )
        assert resp.status_code == 422

    def test_status_change(
        self, client, sakha_admin_headers, write_conn, in_scope_member, out_of_scope_member
    ):
        denied = client.patch(
            f"/api/v1/admin/users/{out_of_scope_member['user_account_pk']}/status",
            headers=sakha_admin_headers, json={"account_status": "LOCKED"},
        )
        assert denied.status_code == 403
        assert _account_status(write_conn, out_of_scope_member["user_account_pk"]) == ("ACTIVE", True)

        ok = client.patch(
            f"/api/v1/admin/users/{in_scope_member['user_account_pk']}/status",
            headers=sakha_admin_headers, json={"account_status": "LOCKED"},
        )
        assert ok.status_code == 200
        assert _account_status(write_conn, in_scope_member["user_account_pk"]) == ("LOCKED", True)

    def test_status_change_invalid_value_and_unknown_account(self, client, admin_headers, in_scope_member):
        bad = client.patch(f"/api/v1/admin/users/{in_scope_member['user_account_pk']}/status",
                           headers=admin_headers, json={"account_status": "PENDING_APPROVAL"})
        assert bad.status_code == 422
        missing = client.patch(f"/api/v1/admin/users/{RANDOM_UUID}/status",
                               headers=admin_headers, json={"account_status": "LOCKED"})
        assert missing.status_code == 404

    def test_delete(
        self, client, sakha_admin_headers, write_conn, in_scope_member, out_of_scope_member
    ):
        denied = client.delete(f"/api/v1/admin/users/{out_of_scope_member['user_account_pk']}",
                               headers=sakha_admin_headers)
        assert denied.status_code == 403
        assert _account_status(write_conn, out_of_scope_member["user_account_pk"]) == ("ACTIVE", True)

        ok = client.delete(f"/api/v1/admin/users/{in_scope_member['user_account_pk']}",
                           headers=sakha_admin_headers)
        assert ok.status_code == 200
        assert _account_status(write_conn, in_scope_member["user_account_pk"]) == ("INACTIVE", False)

    def test_delete_unknown_account_is_404(self, client, admin_headers):
        assert client.delete(f"/api/v1/admin/users/{RANDOM_UUID}", headers=admin_headers).status_code == 404

    def test_create_user_for_out_of_scope_person_is_403(
        self, client, sakha_admin_headers, write_conn, sakha_b, regular_type, active_status_pk
    ):
        """POST /users without create_sangha_sevi needs the person to already sit in scope."""
        theirs = _create_member_without_credential(write_conn, sakha_b, regular_type, active_status_pk, "NEWU")
        resp = client.post("/api/v1/admin/users", headers=sakha_admin_headers, json={
            "person_pk": theirs["person_pk"], "password": "NewUserPass1x",
        })
        assert resp.status_code == 403

    def test_create_user_for_person_without_anchor_is_global_only(
        self, client, admin_headers, sakha_admin_headers, write_conn
    ):
        loner = _create_person(write_conn, "LONER")
        body = {"person_pk": str(loner), "password": "NewUserPass1x"}
        assert client.post("/api/v1/admin/users", headers=sakha_admin_headers, json=body).status_code == 403
        assert client.post("/api/v1/admin/users", headers=admin_headers, json=body).status_code == 201

    def test_create_user_in_scope_person_succeeds(
        self, client, sakha_admin_headers, write_conn, sakha_a, regular_type, active_status_pk
    ):
        mine = _create_member_without_credential(write_conn, sakha_a, regular_type, active_status_pk, "NEWI")
        resp = client.post("/api/v1/admin/users", headers=sakha_admin_headers, json={
            "person_pk": mine["person_pk"], "password": "NewUserPass1x",
        })
        assert resp.status_code == 201, resp.json()

    def test_role_assignment_requires_role_manage_not_just_scope(
        self, client, sakha_admin_headers, in_scope_member
    ):
        """Being in scope is not enough: ADMIN_ROLE_MANAGE is a separate permission the
        Sakha admin role does not hold."""
        resp = client.post(
            f"/api/v1/admin/users/{in_scope_member['user_account_pk']}/roles",
            headers=sakha_admin_headers,
            json={"role_code": "NSS_ERP_ADMIN", "scope_level": "NSS-WIDE"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Scope-subtree violations — organizations
# ═══════════════════════════════════════════════════════════════════════

class TestOrganizationEndpointsAdminScope:

    def test_list_organizations_is_subtree_bounded(
        self, client, admin_headers, sakha_admin_headers, sakha_a, sakha_b
    ):
        def pks(headers):
            body = client.get("/api/v1/admin/organizations", headers=headers,
                              params={"page_size": 200}).json()
            return {o["organization_pk"] for o in body["organizations"]}, body["total"]

        scoped, scoped_total = pks(sakha_admin_headers)
        assert sakha_a in scoped
        assert sakha_b not in scoped
        assert scoped_total == len(scoped) or scoped_total > 200
        # The global authority sees both.
        search = client.get("/api/v1/admin/organizations", headers=admin_headers,
                            params={"page_size": 200, "type_code": "SAKHA_SANGHA"}).json()
        assert {sakha_a, sakha_b} <= {o["organization_pk"] for o in search["organizations"]} \
            or search["total"] > 200

    def test_update_out_of_scope_organization_is_403(
        self, client, sakha_admin_headers, write_conn, sakha_b
    ):
        resp = client.patch(f"/api/v1/admin/organizations/{sakha_b}",
                            headers=sakha_admin_headers, json={"phone_number": "0674-000111"})
        assert resp.status_code == 403
        cur = write_conn.cursor()
        cur.execute("SELECT phone_number FROM nss.organization WHERE organization_pk = %s", (sakha_b,))
        assert cur.fetchone()[0] != "0674-000111"

    def test_update_in_scope_organization_succeeds(self, client, sakha_admin_headers, sakha_a):
        resp = client.patch(f"/api/v1/admin/organizations/{sakha_a}",
                            headers=sakha_admin_headers, json={"phone_number": "0674-000222"})
        assert resp.status_code == 200, resp.json()

    def test_short_code_out_of_scope_is_403(self, client, sakha_admin_headers, write_conn, sakha_b):
        cur = write_conn.cursor()
        cur.execute("SELECT short_code FROM nss.organization WHERE organization_pk = %s", (sakha_b,))
        before = cur.fetchone()[0]
        resp = client.patch(f"/api/v1/admin/organizations/{sakha_b}/short-code",
                            headers=sakha_admin_headers, json={"short_code": "NOPE1"})
        assert resp.status_code == 403
        cur.execute("SELECT short_code FROM nss.organization WHERE organization_pk = %s", (sakha_b,))
        assert cur.fetchone()[0] == before

    def test_short_code_in_scope_succeeds(self, client, sakha_admin_headers, sakha_a):
        resp = client.patch(f"/api/v1/admin/organizations/{sakha_a}/short-code",
                            headers=sakha_admin_headers,
                            json={"short_code": f"S{uuid4().hex[:4].upper()}"})
        assert resp.status_code == 200, resp.json()

    @pytest.mark.parametrize("bad", ["ab", "TOOLONGCODE", "A-B-C", ""])
    def test_short_code_format_is_422(self, client, admin_headers, sakha_a, bad):
        resp = client.patch(f"/api/v1/admin/organizations/{sakha_a}/short-code",
                            headers=admin_headers, json={"short_code": bad})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Scope-subtree violations — member credentials
# ═══════════════════════════════════════════════════════════════════════

class TestCredentialEndpointsAdminScope:

    @pytest.fixture
    def foreign_member(self, write_conn, sakha_b, membership_type_pks, active_status_pk):
        return _create_member_without_credential(
            write_conn, sakha_b, membership_type_pks["PROBATIONARY"], active_status_pk, "CRED",
        )

    @pytest.fixture
    def own_member(self, write_conn, sakha_a, membership_type_pks, active_status_pk):
        return _create_member_without_credential(
            write_conn, sakha_a, membership_type_pks["PROBATIONARY"], active_status_pk, "CRDI",
        )

    def test_list_excludes_out_of_scope_members(
        self, client, admin_headers, sakha_admin_headers, own_member, foreign_member
    ):
        def ids(headers, member):
            body = client.get("/api/v1/admin/credentials/members", headers=headers,
                              params={"search": member["sangha_sevi_id"]}).json()
            return [m["sangha_sevi_id"] for m in body["members"]]

        assert ids(admin_headers, foreign_member) == [foreign_member["sangha_sevi_id"]]
        assert ids(sakha_admin_headers, own_member) == [own_member["sangha_sevi_id"]]
        assert ids(sakha_admin_headers, foreign_member) == []

    def test_timeline_out_of_scope_is_403(self, client, sakha_admin_headers, own_member, foreign_member):
        assert client.get(
            f"/api/v1/admin/credentials/members/{own_member['sangha_sevi_pk']}/timeline",
            headers=sakha_admin_headers).status_code == 200
        assert client.get(
            f"/api/v1/admin/credentials/members/{foreign_member['sangha_sevi_pk']}/timeline",
            headers=sakha_admin_headers).status_code == 403

    def test_issue_out_of_scope_is_403_and_mints_nothing(
        self, client, sakha_admin_headers, write_conn, foreign_member
    ):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{foreign_member['sangha_sevi_pk']}/issue",
            headers=sakha_admin_headers,
            json={"issue_date": "2026-10-12", "valid_from": "2026-10-12", "valid_to": "2030-01-01"},
        )
        assert resp.status_code == 403
        cur = write_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nss.anumati_patra WHERE sangha_sevi_pk = %s",
                    (foreign_member["sangha_sevi_pk"],))
        assert cur.fetchone()[0] == 0

    def test_promote_out_of_scope_is_403_before_any_state_change(
        self, client, sakha_admin_headers, write_conn, foreign_member
    ):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{foreign_member['sangha_sevi_pk']}/promote",
            headers=sakha_admin_headers, json={"effective_date": "2026-03-01"},
        )
        assert resp.status_code == 403
        cur = write_conn.cursor()
        cur.execute(
            "SELECT md.value_code FROM nss.sangha_sevi ss "
            "JOIN nss.master_data md ON md.master_data_pk = ss.membership_type_master_data_pk "
            "WHERE ss.sangha_sevi_pk = %s", (foreign_member["sangha_sevi_pk"],),
        )
        assert cur.fetchone()[0] == "PROBATIONARY"

    def test_credential_list_invalid_filters_and_bounds(self, client, admin_headers):
        assert client.get("/api/v1/admin/credentials/members", headers=admin_headers,
                          params={"page_size": 201}).status_code == 422
        assert client.get("/api/v1/admin/credentials/members", headers=admin_headers,
                          params={"page": 0}).status_code == 422
