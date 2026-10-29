"""
NSS ERP — read endpoints of the Organization / Membership / Person modules
that had no test at all:

  GET /organization/organizations/selectable
  GET /organization/organizations/{pk}/wings
  GET /organization/organizations/{pk}/wings/{wing_type_code}/members
  GET /membership/directory
  GET /membership/organizations/{pk}/darshak-summary
  GET /person/search-selectable

Where the endpoint reports a count these tests build controlled rows inside
the module SAVEPOINT and assert on the DELTA, so they hold on a seed-less
database and on one with thousands of real members. 401/403 gating lives in
tests/security/test_core_modules_security.py (wing scope in
tests/security/test_organization_stats_security.py).
"""

from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration

ORG = "/api/v1/organization"
MEM = "/api/v1/membership"
PER = "/api/v1/person"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(scope="module")
def client(authed_client):
    return authed_client


# ── builders ────────────────────────────────────────────────────────────────

def _md_pk(cur, category, code):
    cur.execute(
        """
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = %s AND md.value_code = %s AND md.is_active = TRUE
        """,
        (category, code),
    )
    row = cur.fetchone()
    if row is None:
        pytest.skip(f"Master data {category}.{code} not seeded.")
    return str(row[0])


def make_member(write_conn, sakha_pk, *, first_name=None, gender=None,
                membership_type="REGULAR", district_pk=None):
    """person + active sangha_sevi in `sakha_pk`. Returns a dict of keys."""
    suffix = uuid4().hex[:10].upper()
    first_name = first_name or f"Gap{suffix}"
    with write_conn.cursor() as cur:
        gender_pk = _md_pk(cur, "GENDER", gender) if gender else None
        cur.execute(
            """
            INSERT INTO nss.person
                (person_id, first_name, last_name, email,
                 gender_master_data_pk, district_pk)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING person_pk
            """,
            (f"TGP{suffix}", first_name, "Matrixson",
             f"tgp.{suffix.lower()}@example.test", gender_pk, district_pk),
        )
        person_pk = str(cur.fetchone()[0])
        cur.execute(
            """
            INSERT INTO nss.sangha_sevi
                (sangha_sevi_id, person_pk, membership_type_master_data_pk,
                 membership_status_master_data_pk, organization_pk, joining_date)
            VALUES (%s, %s, %s, %s, %s, DATE '2024-04-01') RETURNING sangha_sevi_pk
            """,
            (f"TGS{suffix}", person_pk,
             _md_pk(cur, "MEMBERSHIP_TYPE", membership_type),
             _md_pk(cur, "STATUS", "ACTIVE"), sakha_pk),
        )
        sevi_pk = str(cur.fetchone()[0])
    return {"person_pk": person_pk, "sangha_sevi_pk": sevi_pk,
            "sangha_sevi_id": f"TGS{suffix}", "first_name": first_name}


@pytest.fixture(scope="module")
def sakhas(write_conn):
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
            ORDER BY o.organization_name LIMIT 2
            """
        )
        rows = [str(r[0]) for r in cur.fetchall()]
    if not rows:
        pytest.skip("No Sakha Sangha available.")
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# GET /organization/organizations/selectable
# ═══════════════════════════════════════════════════════════════════════════


class TestSelectableOrganizations:

    def test_is_not_swallowed_by_the_pk_route(self, client):
        """'/organizations/selectable' is declared before '/{organization_pk}';
        if the order regressed this would 422 on 'selectable' as a UUID."""
        r = client.get(f"{ORG}/organizations/selectable")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_returns_only_active_organizations_with_required_fields(self, client):
        rows = client.get(f"{ORG}/organizations/selectable").json()
        for row in rows:
            assert row["is_active"] is True
            for field in ("organization_pk", "organization_name", "organization_type_code"):
                assert field in row

    def test_single_type_filter(self, client):
        rows = client.get(f"{ORG}/organizations/selectable",
                          params={"type_code": "SAKHA_SANGHA", "limit": 50}).json()
        assert rows and {r["organization_type_code"] for r in rows} == {"SAKHA_SANGHA"}

    def test_repeated_type_code_is_an_or_match(self, client):
        rows = client.get(
            f"{ORG}/organizations/selectable",
            params=[("type_code", "SAKHA_SANGHA"), ("type_code", "PATHA_CHAKRA"),
                    ("limit", 500)],
        ).json()
        types = {r["organization_type_code"] for r in rows}
        assert types <= {"SAKHA_SANGHA", "PATHA_CHAKRA"}
        assert "SAKHA_SANGHA" in types

    def test_unknown_type_is_empty(self, client):
        r = client.get(f"{ORG}/organizations/selectable", params={"type_code": "NO_SUCH"})
        assert r.status_code == 200 and r.json() == []

    def test_matches_admin_list_for_active_orgs(self, client):
        """No status filter: same rows as the admin list restricted to a type."""
        sel = client.get(f"{ORG}/organizations/selectable",
                         params={"type_code": "KENDRA"}).json()
        adm = client.get(f"{ORG}/organizations", params={"type_code": "KENDRA"}).json()
        assert {r["organization_pk"] for r in sel} == {r["organization_pk"] for r in adm}

    def test_pagination(self, client):
        assert len(client.get(f"{ORG}/organizations/selectable", params={"limit": 1}).json()) <= 1
        far = client.get(f"{ORG}/organizations/selectable", params={"offset": 100000})
        assert far.status_code == 200 and far.json() == []

    @pytest.mark.parametrize("params", [
        {"limit": 0}, {"limit": 100000}, {"offset": -1}, {"state_pk": "x"},
        {"country_pk": "x"}, {"district_pk": "x"}, {"postal_code_pk": "x"},
    ])
    def test_invalid_params_return_422(self, client, params):
        assert client.get(f"{ORG}/organizations/selectable", params=params).status_code == 422

    def test_unknown_geography_filter_is_empty(self, client):
        r = client.get(f"{ORG}/organizations/selectable", params={"state_pk": FAKE_UUID})
        assert r.status_code == 200 and r.json() == []


# ═════════════════════════��═════════════════════════════════════════════════
# GET /organization/organizations/{pk}/wings  (+ /wings/{code}/members)
# ═══════════════════════════════════════════════════════════════════════════


def _wing(summary, code):
    return next(w for w in summary["wings"] if w["wing_type_code"] == code)


class TestOrganizationWings:

    def _summary(self, client, pk):
        r = client.get(f"{ORG}/organizations/{pk}/wings")
        assert r.status_code == 200, r.text
        return r.json()

    def test_shape(self, client, sakhas):
        s = self._summary(client, sakhas[0])
        assert s["organization_pk"] == sakhas[0]
        assert s["organization_type_code"] == "SAKHA_SANGHA"
        assert s["sakha_sangha_count"] == 1             # a Sakha's subtree is itself
        assert [w["wing_type_code"] for w in s["wings"]] == [
            "MAHILA_SANGHA", "KUMARI_SANGHA", "SEVAK_SANGHA"]

    def test_only_mahila_is_derived(self, client, sakhas):
        s = self._summary(client, sakhas[0])
        mahila, kumari, sevak = (_wing(s, c) for c in
                                 ("MAHILA_SANGHA", "KUMARI_SANGHA", "SEVAK_SANGHA"))
        assert mahila["is_derived"] is True
        assert isinstance(mahila["member_count"], int) and mahila["member_count"] >= 0
        assert isinstance(mahila["gender_not_recorded_count"], int)
        assert mahila["member_count_note"] is None
        for w in (kumari, sevak):
            assert w["is_derived"] is False
            assert w["member_count"] is None
            assert w["gender_not_recorded_count"] is None
            assert w["member_count_note"]               # explains WHY it is None
        assert all(w["wing_type_name"] for w in s["wings"])
        assert all(w["organization_count"] >= 0 for w in s["wings"])

    def test_unknown_org_returns_404_and_bad_uuid_422(self, client):
        assert client.get(f"{ORG}/organizations/{FAKE_UUID}/wings").status_code == 404
        assert client.get(f"{ORG}/organizations/not-a-uuid/wings").status_code == 422

    def test_member_counts_follow_gender(self, client, write_conn, sakhas):
        """FEMALE members raise the Mahila roster; a member whose gender was
        never captured raises gender_not_recorded_count instead (the
        documented data-quality figure); MALE members change neither."""
        pk = sakhas[0]
        before = _wing(self._summary(client, pk), "MAHILA_SANGHA")
        make_member(write_conn, pk, gender="FEMALE")
        make_member(write_conn, pk, gender="FEMALE")
        make_member(write_conn, pk, gender="MALE")
        make_member(write_conn, pk, gender=None)
        after = _wing(self._summary(client, pk), "MAHILA_SANGHA")
        assert after["member_count"] == before["member_count"] + 2
        assert after["gender_not_recorded_count"] == before["gender_not_recorded_count"] + 1

    def test_summary_count_equals_roster_total(self, client, write_conn, sakhas):
        """The router's stated invariant: summary and roster share one
        predicate, so the count must be reproducible from the list."""
        pk = sakhas[0]
        make_member(write_conn, pk, gender="FEMALE")
        summary = _wing(self._summary(client, pk), "MAHILA_SANGHA")
        roster = client.get(f"{ORG}/organizations/{pk}/wings/MAHILA_SANGHA/members",
                            params={"limit": 500}).json()
        assert roster["total"] == summary["member_count"]

    def test_inactive_member_leaves_the_roster(self, client, write_conn, sakhas):
        pk = sakhas[0]
        m = make_member(write_conn, pk, gender="FEMALE")
        before = _wing(self._summary(client, pk), "MAHILA_SANGHA")["member_count"]
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.sangha_sevi SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP WHERE sangha_sevi_pk = %s",
                        (m["sangha_sevi_pk"],))
        after = _wing(self._summary(client, pk), "MAHILA_SANGHA")["member_count"]
        assert after == before - 1


class TestWingMembers:

    def _url(self, pk, code="MAHILA_SANGHA"):
        return f"{ORG}/organizations/{pk}/wings/{code}/members"

    def test_envelope_and_rows_are_female_members_of_the_subtree(self, client, write_conn, sakhas):
        pk = sakhas[0]
        m = make_member(write_conn, pk, gender="FEMALE", first_name="Wingtest")
        r = client.get(self._url(pk), params={"limit": 500})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["wing_type_code"] == "MAHILA_SANGHA"
        assert body["organization_pk"] == pk
        assert (body["limit"], body["offset"]) == (500, 0)
        assert body["total"] >= len(body["members"]) >= 1
        assert all(x["gender_code"] == "FEMALE" for x in body["members"])
        assert all(x["sakha_organization_pk"] == pk for x in body["members"])
        mine = next(x for x in body["members"] if x["sangha_sevi_pk"] == m["sangha_sevi_pk"])
        assert mine["person_pk"] == m["person_pk"]
        assert mine["sangha_sevi_id"] == m["sangha_sevi_id"]
        assert "Wingtest" in mine["full_name"]
        assert mine["sakha_organization_name"]

    def test_wing_code_is_case_insensitive(self, client, sakhas):
        r = client.get(self._url(sakhas[0], "mahila_sangha"))
        assert r.status_code == 200 and r.json()["wing_type_code"] == "MAHILA_SANGHA"

    @pytest.mark.parametrize("code", ["KUMARI_SANGHA", "SEVAK_SANGHA"])
    def test_non_derivable_wings_are_422_not_an_empty_list(self, client, sakhas, code):
        r = client.get(self._url(sakhas[0], code))
        assert r.status_code == 422, r.text
        assert r.json()["detail"]                 # says why

    def test_unknown_wing_type_returns_422(self, client, sakhas):
        r = client.get(self._url(sakhas[0], "NO_SUCH_WING"))
        assert r.status_code == 422, r.text
        assert "MAHILA_SANGHA" in r.json()["detail"]

    def test_unknown_org_returns_404(self, client):
        assert client.get(self._url(FAKE_UUID)).status_code == 404

    def test_pagination_total_is_not_a_page_length(self, client, write_conn, sakhas):
        pk = sakhas[0]
        for _ in range(3):
            make_member(write_conn, pk, gender="FEMALE")
        full = client.get(self._url(pk), params={"limit": 500}).json()
        page = client.get(self._url(pk), params={"limit": 1, "offset": 1}).json()
        assert len(page["members"]) == 1
        assert page["total"] == full["total"] >= 3
        assert page["members"][0]["sangha_sevi_pk"] == full["members"][1]["sangha_sevi_pk"]

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 100000}, {"offset": -1}])
    def test_invalid_pagination_returns_422(self, client, sakhas, params):
        assert client.get(self._url(sakhas[0]), params=params).status_code == 422

    def test_offset_past_end_is_empty_with_true_total(self, client, sakhas):
        body = client.get(self._url(sakhas[0]), params={"offset": 100000}).json()
        assert body["members"] == [] and body["total"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# GET /membership/directory
# ═══════════════════════════════════════════════════════════════════════════


class TestMemberDirectory:

    def test_browse_without_q_returns_envelope(self, client):
        r = client.get(f"{MEM}/directory")
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"members", "total"}
        assert body["total"] >= len(body["members"])

    def test_row_shape_excludes_admin_only_fields(self, client, write_conn, sakhas):
        m = make_member(write_conn, sakhas[0], first_name="Dirshape")
        rows = client.get(f"{MEM}/directory", params={"q": "Dirshape"}).json()["members"]
        row = next(x for x in rows if x["sangha_sevi_pk"] == m["sangha_sevi_pk"])
        for field in ("sangha_sevi_id", "person_id", "first_name", "last_name",
                      "organization_name", "membership_type_code", "status_code",
                      "district_name", "city_village_name", "mobile_number", "email",
                      "position_code", "position_name"):
            assert field in row
        # MemberResponse-only fields must not leak to the general audience.
        for field in ("membership_type_master_data_pk", "aadhaar_last4",
                      "is_darshak_attending", "date_of_birth"):
            assert field not in row
        assert row["position_code"] is None and row["position_name"] is None

    def test_search_finds_member_by_name_and_by_sangha_sevi_id(self, client, write_conn, sakhas):
        m = make_member(write_conn, sakhas[0], first_name="Zxqvdirone")
        by_name = client.get(f"{MEM}/directory", params={"q": "Zxqvdirone"}).json()
        assert m["sangha_sevi_pk"] in [x["sangha_sevi_pk"] for x in by_name["members"]]
        by_id = client.get(f"{MEM}/directory", params={"q": m["sangha_sevi_id"]}).json()
        assert m["sangha_sevi_pk"] in [x["sangha_sevi_pk"] for x in by_id["members"]]

    def test_search_without_match_is_empty(self, client):
        body = client.get(f"{MEM}/directory", params={"q": "qqqqzzzzxxxxwwww"}).json()
        assert body["members"] == [] and body["total"] == 0

    def test_organization_filter_restricts_to_that_sakha(self, client, write_conn, sakhas):
        m = make_member(write_conn, sakhas[0], first_name="Dirorg")
        rows = client.get(f"{MEM}/directory",
                          params={"organization_pk": sakhas[0], "q": "Dirorg"}).json()["members"]
        assert [x["sangha_sevi_pk"] for x in rows] == [m["sangha_sevi_pk"]]
        if len(sakhas) > 1:
            other = client.get(f"{MEM}/directory",
                               params={"organization_pk": sakhas[1], "q": "Dirorg"}).json()
            assert other["members"] == []

    def test_organization_filter_includes_subtree(self, client, write_conn, sakhas):
        """A higher body returns its descendants' members (subtree semantics)."""
        m = make_member(write_conn, sakhas[0], first_name="Dirtree")
        with write_conn.cursor() as cur:
            cur.execute("SELECT parent_organization_pk FROM nss.organization WHERE organization_pk = %s",
                        (sakhas[0],))
            parent = cur.fetchone()[0]
        if parent is None:
            pytest.skip("Sakha has no parent body.")
        rows = client.get(f"{MEM}/directory",
                          params={"organization_pk": str(parent), "q": "Dirtree"}).json()["members"]
        assert m["sangha_sevi_pk"] in [x["sangha_sevi_pk"] for x in rows]

    def test_district_filter(self, client, write_conn, sakhas):
        with write_conn.cursor() as cur:
            cur.execute("SELECT district_pk FROM nss.district WHERE is_active = TRUE LIMIT 2")
            districts = [str(r[0]) for r in cur.fetchall()]
        if len(districts) < 2:
            pytest.skip("Need two districts.")
        m = make_member(write_conn, sakhas[0], first_name="Dirdist", district_pk=districts[0])
        hit = client.get(f"{MEM}/directory", params={"district_pk": districts[0], "q": "Dirdist"}).json()
        assert m["sangha_sevi_pk"] in [x["sangha_sevi_pk"] for x in hit["members"]]
        miss = client.get(f"{MEM}/directory", params={"district_pk": districts[1], "q": "Dirdist"}).json()
        assert miss["members"] == []

    def test_inactive_members_are_excluded(self, client, write_conn, sakhas):
        m = make_member(write_conn, sakhas[0], first_name="Dirgone")
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.sangha_sevi SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP WHERE sangha_sevi_pk = %s",
                        (m["sangha_sevi_pk"],))
        rows = client.get(f"{MEM}/directory", params={"q": "Dirgone"}).json()["members"]
        assert m["sangha_sevi_pk"] not in [x["sangha_sevi_pk"] for x in rows]

    def test_pagination_total_is_independent_of_limit(self, client):
        full = client.get(f"{MEM}/directory", params={"limit": 500}).json()
        page = client.get(f"{MEM}/directory", params={"limit": 1}).json()
        assert len(page["members"]) <= 1
        assert page["total"] == full["total"]

    @pytest.mark.parametrize("params", [
        {"q": "a"}, {"limit": 0}, {"limit": 100000}, {"offset": -1},
        {"organization_pk": "x"}, {"district_pk": "x"},
    ])
    def test_invalid_params_return_422(self, client, params):
        assert client.get(f"{MEM}/directory", params=params).status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# GET /membership/organizations/{pk}/darshak-summary
# ═══════════════════════════════════════════════════════════════════════════


class TestDarshakSummary:

    def _get(self, client, pk):
        r = client.get(f"{MEM}/organizations/{pk}/darshak-summary")
        assert r.status_code == 200, r.text
        return r.json()

    def test_shape(self, client, sakhas):
        body = self._get(client, sakhas[0])
        assert set(body) == {"home_probationary_count", "attending_from_other_sakha_count"}
        assert all(isinstance(v, int) and v >= 0 for v in body.values())

    def test_unknown_org_returns_404_and_bad_uuid_422(self, client):
        assert client.get(f"{MEM}/organizations/{FAKE_UUID}/darshak-summary").status_code == 404
        assert client.get(f"{MEM}/organizations/x/darshak-summary").status_code == 422

    def test_home_probationary_counts_only_darshaka_members(self, client, write_conn, sakhas):
        pk = sakhas[0]
        before = self._get(client, pk)["home_probationary_count"]
        make_member(write_conn, pk, membership_type="PROBATIONARY")
        make_member(write_conn, pk, membership_type="REGULAR")
        gone = make_member(write_conn, pk, membership_type="PROBATIONARY")
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.sangha_sevi SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP WHERE sangha_sevi_pk = %s",
                        (gone["sangha_sevi_pk"],))
        assert self._get(client, pk)["home_probationary_count"] == before + 1

    def test_attending_from_other_sakha_counts_open_affiliations_only(
        self, client, write_conn, sakhas
    ):
        if len(sakhas) < 2:
            pytest.skip("Need two Sakhas.")
        home, visited = sakhas
        before = self._get(client, visited)["attending_from_other_sakha_count"]
        guest = make_member(write_conn, home)
        stale = make_member(write_conn, home)
        local = make_member(write_conn, visited)       # home == visited: not "other"
        with write_conn.cursor() as cur:
            for sevi, closed, org in ((guest, False, visited), (stale, True, visited),
                                      (local, False, visited)):
                suffix = uuid4().hex[:8].upper()
                cur.execute(
                    """
                    INSERT INTO nss.membership_sakha_affiliation
                        (sangha_sevi_pk, organization_pk, local_sakha_erp_id,
                         effective_from, effective_to, affiliation_status,
                         source_event_type)
                    VALUES (%s, %s, %s, DATE '2024-04-01', %s, %s, 'ENROLLMENT')
                    """,
                    (sevi["sangha_sevi_pk"], org, f"TD{suffix}",
                     "2024-06-01" if closed else None,
                     "ARCHIVED" if closed else "ACTIVE"),
                )
        assert self._get(client, visited)["attending_from_other_sakha_count"] == before + 1


# ═══════════════════════════════════════════════════════════════════════════
# GET /person/search-selectable
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonSearchSelectable:

    def test_requires_query(self, client):
        assert client.get(f"{PER}/search-selectable").status_code == 422

    @pytest.mark.parametrize("params", [
        {"q": "a"}, {"q": "ab", "limit": 0}, {"q": "ab", "limit": 100000},
        {"q": "ab", "offset": -1}, {"q": "x" * 101},
    ])
    def test_invalid_params_return_422(self, client, params):
        assert client.get(f"{PER}/search-selectable", params=params).status_code == 422

    def test_returns_same_envelope_as_admin_search(self, client, write_conn, sakhas):
        m = make_member(write_conn, sakhas[0], first_name="Zxqvsel")
        sel = client.get(f"{PER}/search-selectable", params={"q": "Zxqvsel"})
        adm = client.get(f"{PER}/search", params={"q": "Zxqvsel"})
        assert sel.status_code == 200, sel.text
        assert set(sel.json()) == {"persons", "total"}
        assert m["person_pk"] in [p["person_pk"] for p in sel.json()["persons"]]
        assert sel.json() == adm.json()               # one shared implementation

    def test_summary_projection_has_no_sensitive_fields(self, client, write_conn, sakhas):
        make_member(write_conn, sakhas[0], first_name="Zxqvsens")
        rows = client.get(f"{PER}/search-selectable", params={"q": "Zxqvsens"}).json()["persons"]
        assert rows
        for banned in ("aadhaar_encrypted", "aadhaar_hash", "aadhaar_last4"):
            assert all(banned not in r for r in rows)

    def test_no_match_is_empty(self, client):
        body = client.get(f"{PER}/search-selectable", params={"q": "qqqqzzzzxxxxwwww"}).json()
        assert body["persons"] == [] and body["total"] == 0

    def test_email_shaped_query_uses_the_local_part(self, client, write_conn, sakhas):
        m = make_member(write_conn, sakhas[0], first_name="Zxqvmail")
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.person SET email = %s WHERE person_pk = %s",
                        ("zxqvmail.person@example.test", m["person_pk"]))
        rows = client.get(f"{PER}/search-selectable",
                          params={"q": "zxqvmail.person@example.test"}).json()["persons"]
        assert m["person_pk"] in [p["person_pk"] for p in rows]
