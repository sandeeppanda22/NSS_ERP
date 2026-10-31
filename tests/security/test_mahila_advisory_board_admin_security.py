"""
NSS ERP — Security tests for NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN and
NSS_ERP_ADVISORY_BOARD_ADMIN (owner decisions 2026-10-30).

Mahila admin (Kendra's 18 operational permissions, reach = every MAHILA_SANGHA
org + subtree):
  - acts inside a Mahila Sangha, is refused (403) in a Sakha and other orgs;
  - never reaches admin user / role / scope / audit / foundation-write endpoints.

Advisory Board admin (8 permissions, PERSON_VIEW added 2026-10-30; reach = the singleton ADVISORY_BOARD
organization only, 2026-10-30 "Advisory Board should be an org type"):
  - may manage seats / acting cover of ADVISORY_BOARD-type bodies only;
  - refused on KENDRA_GB, Sakha bodies, body CRUD, catalogues, person/family/
    attendance/admin/audit endpoints; the Sakha-nominated MEMBER seat stays with
    the Sakha;
  - files and numbers correspondence under its own register, refused on others.

Scope-resolution unit assertions live in tests/api/test_null_org_scope.py.
Helpers are reused from tests/security/test_governance_security.py (no
duplicates). Everything rolls back with the module SAVEPOINT.
"""

from uuid import uuid4

import pytest

from tests.api.test_correspondence import _create_test_organization
from tests.security.test_governance_security import (
    _active_sakha_org_pks,
    _attach_user_account,
    _create_person_with_sevi,
    _grant_role,
    _login_headers,
)

pytestmark = pytest.mark.integration

GOV = "/api/v1/governance"
MAHILA_PASSWORD = "MahilaSecPass1x"
AB_PASSWORD = "AdvBoardSecPass1x"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


def _sc():
    return f"S{uuid4().hex[:3].upper()}"


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def home_sakha_pk(write_conn):
    """A real Sakha used as the admins' own home (sangha_sevi is Sakha-only)."""
    return _active_sakha_org_pks(write_conn, 1)[0]


@pytest.fixture(scope="module")
def mahila_org_pk(write_conn):
    return _create_test_organization(
        write_conn, name_prefix="SecMahila", type_code="MAHILA_SANGHA", parent_pk=None, short_code=_sc())


@pytest.fixture(scope="module")
def foreign_sakha_org_pk(write_conn):
    return _create_test_organization(
        write_conn, name_prefix="SecForeignSakha", type_code="SAKHA_SANGHA", parent_pk=None, short_code=_sc())


@pytest.fixture(scope="module")
def mahila_admin_headers(write_conn, client, home_sakha_pk):
    data = _create_person_with_sevi(write_conn, "MahilaSecAdmin", organization_pk=home_sakha_pk)
    uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], MAHILA_PASSWORD)
    _grant_role(write_conn, uap, "NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN",
                scope_level="KENDRA_MAHILA_SANGHA", organization_pk=None)
    return _login_headers(client, data["sangha_sevi_id"], MAHILA_PASSWORD)


@pytest.fixture(scope="module")
def ab_holder(write_conn, home_sakha_pk):
    """Person used as the target of seat/acting-cover requests."""
    return _create_person_with_sevi(write_conn, "AdvBoardSecHolder", organization_pk=home_sakha_pk)


@pytest.fixture(scope="module")
def ab_admin_headers(write_conn, client, home_sakha_pk):
    data = _create_person_with_sevi(write_conn, "AdvBoardSecAdmin", organization_pk=home_sakha_pk)
    uap = _attach_user_account(write_conn, data["person_pk"], data["sangha_sevi_id"], AB_PASSWORD)
    _grant_role(write_conn, uap, "NSS_ERP_ADVISORY_BOARD_ADMIN",
                scope_level="ADVISORY_BOARD", organization_pk=None)
    return _login_headers(client, data["sangha_sevi_id"], AB_PASSWORD)


@pytest.fixture(scope="module")
def nss_admin_headers(write_conn, client):
    from tests.api.test_correspondence import _create_admin_with_scope
    from tests.attendance_support import _with_sevi_pk

    admin = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None))
    return _login_headers(client, admin["sangha_sevi_id"], admin["password"])


def _body_pk(write_conn, body_code):
    cur = write_conn.cursor()
    cur.execute("SELECT body_master_pk FROM nss.body_master WHERE body_code = %s", (body_code,))
    row = cur.fetchone()
    if not row:
        pytest.skip(f"Seeded body {body_code} not present.")
    return str(row[0])


def _first_sakha_body_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk IS NOT NULL
        LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        pytest.skip("No Sakha Governing Body shell seeded.")
    return str(row[0])


def _position_pk(write_conn, code):
    cur = write_conn.cursor()
    cur.execute("SELECT position_master_pk FROM nss.position_master WHERE position_code = %s", (code,))
    row = cur.fetchone()
    if not row:
        pytest.skip(f"Seeded position {code} not present.")
    return str(row[0])


def _body_type_pk(write_conn, code):
    cur = write_conn.cursor()
    cur.execute("SELECT body_type_master_pk FROM nss.body_type_master WHERE body_type_code = %s", (code,))
    row = cur.fetchone()
    if not row:
        pytest.skip(f"Seeded body type {code} not present.")
    return str(row[0])


# ═══════════════════════════════════════════════════════════════════════
# Mahila admin
# ═══════════════════════════════════════════════════════════════════════

class TestMahilaAdminReach:

    def test_org_list_contains_mahila_org_and_no_sakha(self, client, mahila_admin_headers,
                                                       mahila_org_pk, foreign_sakha_org_pk):
        r = client.get("/api/v1/admin/organizations",
                       params={"type_code": "MAHILA_SANGHA", "page_size": 200}, headers=mahila_admin_headers)
        assert r.status_code == 200, r.text
        assert mahila_org_pk in {o["organization_pk"] for o in r.json()["organizations"]}
        r = client.get("/api/v1/admin/organizations",
                       params={"type_code": "SAKHA_SANGHA", "page_size": 200}, headers=mahila_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["organizations"] == [], "a Mahila admin must not see Sakha organizations"
        assert foreign_sakha_org_pk not in {o["organization_pk"] for o in r.json()["organizations"]}

    def test_can_edit_a_mahila_org_but_not_a_sakha(self, client, mahila_admin_headers,
                                                   mahila_org_pk, foreign_sakha_org_pk):
        ok = client.patch(f"/api/v1/admin/organizations/{mahila_org_pk}",
                          json={"organization_name": "SecMahila Renamed"}, headers=mahila_admin_headers)
        assert ok.status_code != 403, ok.text
        denied = client.patch(f"/api/v1/admin/organizations/{foreign_sakha_org_pk}",
                              json={"organization_name": "Hijacked"}, headers=mahila_admin_headers)
        assert denied.status_code == 403, denied.text
        assert "admin scope" in denied.json()["detail"]

    def test_short_code_edit_is_scoped(self, client, mahila_admin_headers, foreign_sakha_org_pk):
        r = client.patch(f"/api/v1/admin/organizations/{foreign_sakha_org_pk}/short-code",
                         json={"short_code": "ZZZ"}, headers=mahila_admin_headers)
        assert r.status_code == 403, r.text

    def test_dashboard_stats_scoped(self, client, mahila_admin_headers, mahila_org_pk, foreign_sakha_org_pk):
        assert client.get("/api/v1/admin/dashboard-stats", headers=mahila_admin_headers).status_code == 200
        assert client.get("/api/v1/admin/dashboard-stats", params={"org_pk": mahila_org_pk},
                          headers=mahila_admin_headers).status_code == 200
        assert client.get("/api/v1/admin/dashboard-stats", params={"org_pk": foreign_sakha_org_pk},
                          headers=mahila_admin_headers).status_code == 403

    def test_hierarchy_is_rooted_at_mahila_orgs(self, client, mahila_admin_headers,
                                                mahila_org_pk, foreign_sakha_org_pk):
        r = client.get("/api/v1/organization/hierarchy", params={"limit": 500}, headers=mahila_admin_headers)
        assert r.status_code == 200, r.text
        pks = {n["organization_pk"] for n in r.json()}
        assert mahila_org_pk in pks
        assert foreign_sakha_org_pk not in pks
        assert "KENDRA" not in {n["organization_type_code"] for n in r.json()}

    def test_attendance_is_scope_bounded(self, client, mahila_admin_headers, foreign_sakha_org_pk):
        r = client.get("/api/v1/attendance/pujas", params={"organization_pk": foreign_sakha_org_pk},
                       headers=mahila_admin_headers)
        assert r.status_code == 403, r.text

    def test_governance_body_create_is_scope_bounded(self, client, write_conn, mahila_admin_headers,
                                                     mahila_org_pk, foreign_sakha_org_pk):
        type_pk = _body_type_pk(write_conn, "MAHILA_PARICHALANA_MANDALI")

        def payload(org_pk):
            body = {"body_type_master_pk": type_pk, "body_code": f"SECM_{uuid4().hex[:8].upper()}",
                    "body_name": "Sec Mahila Mandali", "effective_from": "2026-01-01"}
            if org_pk:
                body["organization_pk"] = org_pk
            return body

        inside = client.post(f"{GOV}/bodies", json=payload(mahila_org_pk), headers=mahila_admin_headers)
        assert inside.status_code != 403, inside.text
        sakha = client.post(f"{GOV}/bodies", json=payload(foreign_sakha_org_pk), headers=mahila_admin_headers)
        assert sakha.status_code == 403, sakha.text
        nss_wide = client.post(f"{GOV}/bodies", json=payload(None), headers=mahila_admin_headers)
        assert nss_wide.status_code == 403, nss_wide.text
        assert "NSS-wide" in nss_wide.json()["detail"]

    def test_cannot_edit_catalogues_or_nss_wide_bodies(self, client, write_conn, mahila_admin_headers):
        r = client.post(f"{GOV}/body-types", json={"body_type_code": "X_MAHILA_SEC", "body_type_name": "x"},
                        headers=mahila_admin_headers)
        assert r.status_code == 403, r.text
        r = client.patch(f"{GOV}/bodies/{_body_pk(write_conn, 'KENDRA_GB')}", json={"body_name": "x"},
                         headers=mahila_admin_headers)
        assert r.status_code == 403, r.text


class TestMahilaAdminCannotReachAdminSurface:

    def test_role_assignment_and_revocation_refused(self, client, mahila_admin_headers):
        r = client.post(f"/api/v1/admin/users/{FAKE_UUID}/roles",
                        json={"role_code": "NSS_ERP_ADMIN", "scope_level": "NSS-WIDE"},
                        headers=mahila_admin_headers)
        assert r.status_code == 403, r.text
        r = client.delete(f"/api/v1/admin/users/{FAKE_UUID}/roles/{FAKE_UUID}", headers=mahila_admin_headers)
        assert r.status_code == 403, r.text

    def test_no_admin_permissions_in_session(self, client, mahila_admin_headers):
        r = client.get("/api/v1/auth/me", headers=mahila_admin_headers)
        assert r.status_code == 200, r.text
        me = r.json()
        perms = set(me["permissions"])
        assert not {p for p in perms if p.startswith("ADMIN_")}
        assert not perms & {"AUDIT_VIEW", "FOUNDATION_MANAGE", "PERSON_VIEW_SENSITIVE"}
        assert len(perms) == 18
        # scope list is non-global and /me carries the resolved subtree, not None
        assert me["admin_scope_org_pks"] is not None

    def test_audit_and_foundation_writes_refused(self, client, mahila_admin_headers):
        assert client.get("/api/v1/audit/change-log", headers=mahila_admin_headers).status_code == 403
        assert client.post("/api/v1/foundation/master-data", json={},
                           headers=mahila_admin_headers).status_code == 403
        assert client.post("/api/v1/foundation/settings", json={},
                           headers=mahila_admin_headers).status_code == 403

    def test_cannot_create_organizations(self, client, mahila_admin_headers):
        r = client.post("/api/v1/admin/organizations",
                        json={"organization_type_code": "ZILLA_SANGHA", "organization_name": "Nope"},
                        headers=mahila_admin_headers)
        assert r.status_code == 403, r.text


# ═══════════════════════════════════════════════════════════════════════
# Advisory Board admin
# ═══════════════════════════════════════════════════════════════════════

def _acting(position_pk, person_pk):
    return {"position_master_pk": position_pk, "person_pk": person_pk,
            "effective_from": "2026-02-01", "reason": "sec test"}


def _assignment(position_pk, holder):
    return {"position_master_pk": position_pk, "person_pk": holder["person_pk"],
            "sangha_sevi_pk": holder["sangha_sevi_pk"], "effective_from": "2026-02-01"}


class TestAdvisoryBoardAdminBodyRule:

    def test_can_view_bodies_and_search_members(self, client, ab_admin_headers):
        assert client.get(f"{GOV}/bodies", headers=ab_admin_headers).status_code == 200
        assert client.get("/api/v1/membership/search", params={"q": "ab"},
                          headers=ab_admin_headers).status_code == 200

    def test_acting_cover_allowed_on_advisory_board_only(self, client, write_conn, ab_admin_headers, ab_holder):
        pos = _position_pk(write_conn, "SECRETARY")
        ab = client.post(f"{GOV}/bodies/{_body_pk(write_conn, 'ADVISORY_BOARD')}/acting-assignments",
                         json=_acting(pos, ab_holder["person_pk"]), headers=ab_admin_headers)
        assert ab.status_code != 403, ab.text            # scope layer passed
        kendra = client.post(f"{GOV}/bodies/{_body_pk(write_conn, 'KENDRA_GB')}/acting-assignments",
                             json=_acting(pos, ab_holder["person_pk"]), headers=ab_admin_headers)
        assert kendra.status_code == 403, kendra.text
        sakha = client.post(f"{GOV}/bodies/{_first_sakha_body_pk(write_conn)}/acting-assignments",
                            json=_acting(pos, ab_holder["person_pk"]), headers=ab_admin_headers)
        assert sakha.status_code == 403, sakha.text

    def test_officer_seat_scope_passes_on_advisory_board_not_elsewhere(self, client, write_conn,
                                                                       ab_admin_headers, ab_holder):
        pos = _position_pk(write_conn, "PRESIDENT")
        ab = client.post(f"{GOV}/bodies/{_body_pk(write_conn, 'ADVISORY_BOARD')}/assignments",
                         json=_assignment(pos, ab_holder), headers=ab_admin_headers)
        assert ab.status_code != 403, ab.text            # may still 4xx on composition rules, never on scope
        kendra = client.post(f"{GOV}/bodies/{_body_pk(write_conn, 'KENDRA_GB')}/assignments",
                             json=_assignment(pos, ab_holder), headers=ab_admin_headers)
        assert kendra.status_code == 403, kendra.text
        sakha = client.post(f"{GOV}/bodies/{_first_sakha_body_pk(write_conn)}/assignments",
                            json=_assignment(pos, ab_holder), headers=ab_admin_headers)
        assert sakha.status_code == 403, sakha.text

    def test_sakha_nominated_member_seat_stays_with_the_sakha(self, client, write_conn,
                                                              ab_admin_headers, ab_holder):
        r = client.post(f"{GOV}/bodies/{_body_pk(write_conn, 'ADVISORY_BOARD')}/assignments",
                        json=_assignment(_position_pk(write_conn, "MEMBER"), ab_holder),
                        headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        assert "own admin" in r.json()["detail"]

    def test_body_crud_catalogues_and_elections_refused(self, client, write_conn, ab_admin_headers):
        ab_pk = _body_pk(write_conn, "ADVISORY_BOARD")
        r = client.patch(f"{GOV}/bodies/{ab_pk}", json={"body_name": "Renamed"}, headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        r = client.delete(f"{GOV}/bodies/{ab_pk}", headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        r = client.post(f"{GOV}/bodies", json={
            "body_type_master_pk": _body_type_pk(write_conn, "ADVISORY_BOARD"),
            "body_code": f"AB2_{uuid4().hex[:6].upper()}", "body_name": "Second AB",
            "effective_from": "2026-01-01"}, headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        r = client.post(f"{GOV}/body-types", json={"body_type_code": "X_AB_SEC", "body_type_name": "x"},
                        headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        r = client.post(f"{GOV}/positions",
                        json={"position_code": "X_AB_SEC", "position_name": "x", "display_order": 1},
                        headers=ab_admin_headers)
        assert r.status_code == 403, r.text


def _advisory_board_org_pk(write_conn):
    """The seeded singleton ADVISORY_BOARD organization (07_advisory_board_organization_patch.sql)."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'ADVISORY_BOARD' AND o.is_active = TRUE
    """)
    row = cur.fetchone()
    if not row:
        pytest.skip("Advisory Board organization not seeded (run the idempotent patch).")
    return str(row[0])


class TestAdvisoryBoardAdminOrganizationSurface:
    """Since 2026-10-30 the Advisory Board is an organization: its admin reaches
    that one organization (own correspondence register) and nothing else."""

    @pytest.mark.parametrize("path", [
        "/api/v1/family/families",
        "/api/v1/attendance/pujas",
        "/api/v1/admin/users",
        "/api/v1/admin/organizations",
        "/api/v1/admin/dashboard-stats",
        "/api/v1/audit/change-log",
    ])
    def test_person_family_attendance_and_admin_reads_are_403(self, client, ab_admin_headers, path):
        assert client.get(path, headers=ab_admin_headers).status_code == 403

    @pytest.mark.parametrize("path", [
        "/api/v1/organization/organizations",
        "/api/v1/organization/hierarchy",
        "/api/v1/correspondence",
    ])
    def test_organization_and_correspondence_reads_are_200(self, client, ab_admin_headers, path):
        assert client.get(path, headers=ab_admin_headers).status_code == 200

    def test_hierarchy_is_rooted_at_the_advisory_board_org_only(self, client, write_conn, ab_admin_headers):
        ab_pk = _advisory_board_org_pk(write_conn)
        rows = client.get("/api/v1/organization/hierarchy", headers=ab_admin_headers).json()
        rows = rows if isinstance(rows, list) else rows.get("organizations", [])
        assert {r["organization_pk"] for r in rows} == {ab_pk}

    def test_person_view_is_scope_bounded_for_the_advisory_board_admin(self, client, ab_admin_headers, ab_holder):
        """PERSON_VIEW (owner decision 2026-10-30): the scoped list is empty
        (the AB org has no members) and another person's detail is 403."""
        r = client.get("/api/v1/person/persons", headers=ab_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["persons"] == []
        r = client.get(f"/api/v1/person/persons/{ab_holder['person_pk']}", headers=ab_admin_headers)
        assert r.status_code == 403, r.text

    def test_organization_in_scope_search_returns_only_the_advisory_board(
            self, client, write_conn, ab_admin_headers):
        """Backs the Correspondence organization pickers (was /admin/organizations -> 403)."""
        ab_pk = _advisory_board_org_pk(write_conn)
        r = client.get("/api/v1/organization/organizations/in-scope?search=Advisory", headers=ab_admin_headers)
        assert r.status_code == 200, r.text
        assert {o["organization_pk"] for o in r.json()} == {ab_pk}
        r = client.get("/api/v1/organization/organizations/in-scope?search=Sakha", headers=ab_admin_headers)
        assert r.status_code == 200 and r.json() == []

    def test_advisory_board_dashboard_readable_by_its_admin(self, client, ab_admin_headers):
        r = client.get(f"{GOV}/advisory-board/dashboard", headers=ab_admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert {"members", "office_bearers", "acting_cover", "missing_sakhas",
                "seats_filled", "vacancies"} <= set(data)

    def test_advisory_board_organization_name_is_immutable(self, client, write_conn, ab_admin_headers):
        # The AB admin reaches its own org (ORGANIZATION_VIEW + scope), so a name change is the 422 below;
        # the same 422 for NSS_ERP_ADMIN is asserted in tests/api/test_admin.py.
        r = client.patch(f"/api/v1/admin/organizations/{_advisory_board_org_pk(write_conn)}",
                         json={"organization_name": "Renamed"}, headers=ab_admin_headers)
        assert r.status_code == 422, r.text

    def test_role_management_refused_and_no_admin_permissions(self, client, write_conn, ab_admin_headers):
        r = client.post(f"/api/v1/admin/users/{FAKE_UUID}/roles",
                        json={"role_code": "NSS_ERP_ADVISORY_BOARD_ADMIN", "scope_level": "ADVISORY_BOARD"},
                        headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        me = client.get("/api/v1/auth/me", headers=ab_admin_headers).json()
        assert set(me["permissions"]) == {
            "GOVERNANCE_VIEW", "GOVERNANCE_MANAGE", "MEMBERSHIP_VIEW",
            "CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE", "ORGANIZATION_VIEW", "FOUNDATION_VIEW",
            "PERSON_VIEW",
        }
        assert me["admin_scope_org_pks"] == [_advisory_board_org_pk(write_conn)], (
            "an Advisory Board scope reaches exactly the Advisory Board organization")


class TestAdvisoryBoardAdminCorrespondenceRegister:
    """Own register numbered/filed; other registers refused (admin scope)."""

    def _payload(self, org_pk):
        return {
            "register_organization_pk": org_pk, "direction": "OUTWARD",
            "correspondence_date": "2026-01-10", "received_or_sent_date": "2026-01-11",
            "subject": "AB register test", "sender_type": "EXTERNAL",
            "sender_external_name": "AB", "recipient_type": "EXTERNAL",
            "recipient_external_name": "Someone", "medium": "POST",
        }

    def test_files_and_numbers_under_its_own_register(self, client, write_conn, ab_admin_headers):
        ab_pk = _advisory_board_org_pk(write_conn)
        r = client.post("/api/v1/correspondence", json=self._payload(ab_pk), headers=ab_admin_headers)
        assert r.status_code == 201, r.text
        assert r.json()["reference_number"].startswith("NSSAB/OUT/")

    def test_refused_on_another_organizations_register(self, client, foreign_sakha_org_pk, ab_admin_headers):
        r = client.post("/api/v1/correspondence", json=self._payload(foreign_sakha_org_pk),
                        headers=ab_admin_headers)
        assert r.status_code == 403, r.text

    def test_refused_on_the_kendra_register(self, client, write_conn, ab_admin_headers):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'KENDRA' AND o.is_active = TRUE LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            pytest.skip("No Kendra organization.")
        r = client.post("/api/v1/correspondence", json=self._payload(str(row[0])), headers=ab_admin_headers)
        assert r.status_code == 403, r.text

    def test_second_advisory_board_organization_cannot_be_created(
            self, client, nss_admin_headers, ab_admin_headers):
        payload = {"organization_name": "Second AB", "organization_type_code": "ADVISORY_BOARD"}
        # The AB admin cannot create organizations at all (not an ORGANIZATION_MANAGE holder) -> 403.
        r = client.post("/api/v1/admin/organizations", json=payload, headers=ab_admin_headers)
        assert r.status_code == 403, r.text
        # The singleton rule itself (owner 2026-10-30): even NSS_ERP_ADMIN gets a clean 422.
        r = client.post("/api/v1/admin/organizations", json=payload, headers=nss_admin_headers)
        assert r.status_code == 422, r.text
        assert "unique and already exists" in r.text
