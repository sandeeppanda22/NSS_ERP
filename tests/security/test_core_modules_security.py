"""
NSS ERP — Auth/RBAC gating matrix for the five core read/write modules:
foundation (33 endpoints), organization (11), person (5), membership (9)
and family (16).

Until now only a handful of these endpoints had a 401/403 assertion
(organization stats, one admin-org list). This file closes that by driving
EVERY endpoint through two negative callers:

  * anonymous                      -> 401 on every endpoint
  * authenticated, role-less member -> 403 on every permission-gated
                                       endpoint (a member holds no
                                       permissions at all)

and then proves the other half of each gate — that the endpoints documented
as "authentication only" or "self / relative" really do admit a role-less
member, so a gate cannot be tightened into a regression unnoticed.

Family endpoints that are scoped to ONE family (ownership model) are covered
in tests/api/test_family_ownership.py; this file only adds the collection and
person-scoped family endpoints plus the anonymous sweep over all 16.

Request bodies are valid on purpose: permission dependencies run before body
validation, but ownership checks inside handlers run after it.
"""

import pytest

# Reuse the role-less-member factory instead of re-implementing it.
from tests.api.test_family_ownership import (  # noqa: F401  (fixtures)
    make_roleless_member,
    sakha_pk,
)


pytestmark = pytest.mark.integration

F = "/api/v1/foundation"
O = "/api/v1/organization"
P = "/api/v1/person"
M = "/api/v1/membership"
FAM = "/api/v1/family"
U = "00000000-0000-0000-0000-000000000000"

_MD_BODY = {"category_code": "X", "value_code": "X", "value_name": "X"}
_PROPOSE_DISTRICT = {"state_pk": U, "district_name": "Nowhere"}
_PROPOSE_PIN = {"state_pk": U, "postal_code": "123456"}
_PROPOSE_PO = {"postal_code_pk": U, "post_office_name": "Nowhere"}
_PROPOSE_CV = {"district_pk": U, "city_village_name": "Nowhere",
               "city_village_type": "VILLAGE"}
_FAM_BODY = {"person_pk": U}

# (method, path, json) — gated by a PERMISSION: anonymous 401, role-less 403.
PERMISSION_GATED = [
    # foundation — FOUNDATION_VIEW
    ("GET", f"{F}/categories", None),
    ("GET", f"{F}/categories/{U}", None),
    ("GET", f"{F}/master-data", None),
    ("GET", f"{F}/master-data/{U}", None),
    ("GET", f"{F}/settings", None),
    ("GET", f"{F}/settings/ANY_KEY", None),
    ("GET", f"{F}/sequences", None),
    ("GET", f"{F}/countries", None),
    ("GET", f"{F}/countries/{U}", None),
    ("GET", f"{F}/states", None),
    ("GET", f"{F}/states/{U}", None),
    ("GET", f"{F}/districts", None),
    ("GET", f"{F}/districts/{U}", None),
    ("GET", f"{F}/cities", None),
    ("GET", f"{F}/postal-codes", None),
    ("GET", f"{F}/post-offices?postal_code_pk={U}", None),
    ("GET", f"{F}/postal-code-mappings", None),
    ("GET", f"{F}/sakha-postal-codes", None),
    ("GET", f"{F}/documents", None),
    ("GET", f"{F}/festivals", None),
    ("GET", f"{F}/festival-calendar-dates", None),
    # foundation — FOUNDATION_MANAGE / FOUNDATION_CALENDAR_MANAGE
    ("POST", f"{F}/master-data", _MD_BODY),
    ("PATCH", f"{F}/master-data/{U}", {"value_name": "X"}),
    ("POST", f"{F}/settings",
     {"setting_key": "X", "setting_value": "1", "data_type": "STRING"}),
    ("PATCH", f"{F}/settings/ANY_KEY", {"setting_value": "1"}),
    ("POST", f"{F}/sequences",
     {"sequence_code": "X", "sequence_name": "X", "prefix": "X"}),
    ("PATCH", f"{F}/sequences/ANY_CODE", {"sequence_name": "X"}),
    ("POST", f"{F}/festival-calendar-dates",
     {"festival_code": "X", "calendar_year": 2030, "observed_date": "2030-03-01"}),
    ("PATCH", f"{F}/festival-calendar-dates/{U}", {"is_confirmed": True}),
    # organization — ORGANIZATION_VIEW
    ("GET", f"{O}/types", None),
    ("GET", f"{O}/statuses", None),
    ("GET", f"{O}/organizations", None),
    ("GET", f"{O}/organizations/{U}", None),
    ("GET", f"{O}/organizations/{U}/children", None),
    ("GET", f"{O}/organizations/{U}/children-stats", None),
    ("GET", f"{O}/organizations/{U}/stats", None),
    ("GET", f"{O}/organizations/{U}/wings", None),
    ("GET", f"{O}/organizations/{U}/wings/MAHILA_SANGHA/members", None),
    ("GET", f"{O}/hierarchy", None),
    # person — PERSON_VIEW (collection endpoints) or self/relative (detail)
    ("GET", f"{P}/persons", None),
    ("GET", f"{P}/search?q=abc", None),
    ("GET", f"{P}/persons/{U}", None),
    ("GET", f"{P}/persons/{U}/addresses", None),
    # membership — MEMBERSHIP_VIEW or self (detail/sub-resources)
    ("GET", f"{M}/members", None),
    ("GET", f"{M}/search?q=abc", None),
    ("GET", f"{M}/members/{U}", None),
    ("GET", f"{M}/members/{U}/affiliations", None),
    ("GET", f"{M}/members/{U}/parichaya-patra", None),
    ("GET", f"{M}/members/{U}/anumati-patra", None),
    ("GET", f"{M}/members/{U}/journey", None),
    ("GET", f"{M}/organizations/{U}/darshak-summary", None),
    # family — FAMILY_VIEW (collection) / person-scoped ownership
    ("GET", f"{FAM}/families", None),
    ("GET", f"{FAM}/person/{U}/families", None),
]

# Endpoints whose gate cannot be driven with a placeholder pk (they 404 an unknown
# person BEFORE the access gate), so 401/403 are asserted against real people in
# the dedicated tests below (test_membership_summary_rejects_anonymous,
# test_roleless_member_cannot_read_a_strangers_membership_summary).
DEDICATED_GATE_TESTS = [
    ("GET", f"{FAM}/person/{U}/membership-summary", None),
]

# Authentication-only endpoints: anonymous 401, but a role-less member is let in.
AUTH_ONLY = [
    ("GET", f"{O}/organizations/selectable", None),
    ("GET", f"{P}/search-selectable?q=abc", None),
    ("GET", f"{M}/directory", None),
    ("POST", f"{F}/districts/propose", _PROPOSE_DISTRICT),
    ("POST", f"{F}/postal-codes/propose", _PROPOSE_PIN),
    ("POST", f"{F}/post-offices/propose", _PROPOSE_PO),
    ("POST", f"{F}/city-villages/propose", _PROPOSE_CV),
    ("POST", f"{FAM}/families", {"family_name": "x", "sakha_organization_pk": U}),
]

# Family endpoints scoped to one family — only the anonymous sweep lives here.
FAMILY_SCOPED = [
    ("GET", f"{FAM}/families/{U}", None),
    ("GET", f"{FAM}/families/{U}/members", None),
    ("GET", f"{FAM}/families/{U}/head-history", None),
    ("GET", f"{FAM}/families/{U}/graph", None),
    ("GET", f"{FAM}/families/{U}/sakha-alignment", None),
    ("GET", f"{FAM}/families/{U}/admins", None),
    ("POST", f"{FAM}/families/{U}/members",
     {**_FAM_BODY, "relationship_type_code": "SON"}),
    ("DELETE", f"{FAM}/families/{U}/members", _FAM_BODY),
    ("POST", f"{FAM}/families/{U}/links",
     {"person_a_pk": U, "person_b_pk": U, "link_type": "SPOUSE_OF"}),
    ("POST", f"{FAM}/families/{U}/admins", _FAM_BODY),
    ("DELETE", f"{FAM}/families/{U}/admins", _FAM_BODY),
    ("POST", f"{FAM}/families/{U}/transfer-head", _FAM_BODY),
]


def _ids(cases):
    return [f"{m} {p.replace(U, '{pk}')}" for m, p, _ in cases]


def test_matrix_covers_every_endpoint():
    """Guard: the three tables together must list every route of the five
    routers (33 + 11 + 5 + 9 + 16 = 74), so a new endpoint cannot ship
    without a gate assertion."""
    from api.main import app

    prefixes = (F, O, P, M, FAM)
    registered = {
        (m, r.path)
        for r in app.routes
        if getattr(r, "methods", None) and r.path.startswith(prefixes)
        # membership_change_request.py shares the /membership prefix.
        and not r.path.startswith(f"{M}/change-requests")
        for m in r.methods
        if m != "HEAD"
    }
    assert len(registered) == 74, f"router endpoint count changed: {len(registered)}"

    def templ(path):
        return path.split("?")[0]

    listed = set()
    for method, path, _ in PERMISSION_GATED + AUTH_ONLY + FAMILY_SCOPED + DEDICATED_GATE_TESTS:
        listed.add((method, templ(path)))
    # Compare structurally: replace each registered {param} segment by U / a
    # literal-agnostic wildcard.
    import re

    def matches(reg, concrete):
        pattern = "^" + re.sub(r"\{[^/]+\}", "[^/]+", reg[1]) + "$"
        return reg[0] == concrete[0] and re.match(pattern, concrete[1])

    missing = [r for r in registered if not any(matches(r, c) for c in listed)]
    assert not missing, f"endpoints without a gate assertion: {sorted(missing)}"


@pytest.mark.parametrize(
    "method,path,body", PERMISSION_GATED + AUTH_ONLY + FAMILY_SCOPED,
    ids=_ids(PERMISSION_GATED + AUTH_ONLY + FAMILY_SCOPED),
)
def test_anonymous_is_rejected(anon_client, method, path, body):
    r = anon_client.request(method, path, json=body)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}: {r.text}"


@pytest.fixture(scope="module")
def member(make_roleless_member, sakha_pk):
    return make_roleless_member(sakha_pk)


@pytest.mark.parametrize("method,path,body", PERMISSION_GATED, ids=_ids(PERMISSION_GATED))
def test_roleless_member_is_forbidden(member, method, path, body):
    r = member["client"].request(method, path, json=body)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text}"


_AUTH_ONLY_READS = [c for c in AUTH_ONLY if c[0] == "GET"]


@pytest.mark.parametrize(
    "method,path,body", _AUTH_ONLY_READS, ids=_ids(_AUTH_ONLY_READS),
)
def test_authentication_only_reads_admit_roleless_member(member, method, path, body):
    r = member["client"].request(method, path, json=body)
    assert r.status_code == 200, f"{method} {path} -> {r.status_code}: {r.text}"


def test_roleless_member_can_start_a_family(member, sakha_pk):
    """POST /families is self-service — no FAMILY_MANAGE needed."""
    r = member["client"].post(
        f"{FAM}/families",
        json={"family_name": "Gate Test Paribara", "sakha_organization_pk": sakha_pk},
    )
    assert r.status_code == 201, r.text


@pytest.mark.parametrize(
    "path",
    [
        "{M}/members/{sevi}",
        "{M}/members/{sevi}/affiliations",
        "{M}/members/{sevi}/parichaya-patra",
        "{M}/members/{sevi}/anumati-patra",
        "{M}/members/{sevi}/journey",
        "{P}/persons/{person}",
        "{P}/persons/{person}/addresses",
        "{FAM}/person/{person}/families",
        "{FAM}/person/{person}/membership-summary",
    ],
)
def test_member_can_read_own_records(make_roleless_member, sakha_pk, write_conn, path):
    """The 'self' half of the self-or-permission gates."""
    me = make_roleless_member(sakha_pk)
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s",
            (me["person_pk"],),
        )
        sevi = str(cur.fetchone()[0])
    url = path.format(M=M, P=P, FAM=FAM, sevi=sevi, person=me["person_pk"])
    r = me["client"].get(url)
    assert r.status_code == 200, f"{url} -> {r.status_code}: {r.text}"


def test_member_cannot_read_another_members_records(
    make_roleless_member, sakha_pk, write_conn
):
    """Self-or-permission must be self-ONLY for a role-less caller."""
    me, other = make_roleless_member(sakha_pk), make_roleless_member(sakha_pk)
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s",
            (other["person_pk"],),
        )
        sevi = str(cur.fetchone()[0])
    for url in (
        f"{M}/members/{sevi}",
        f"{M}/members/{sevi}/journey",
        f"{P}/persons/{other['person_pk']}",
        f"{P}/persons/{other['person_pk']}/addresses",
        f"{FAM}/person/{other['person_pk']}/families",
        f"{FAM}/person/{other['person_pk']}/membership-summary",
    ):
        r = me["client"].get(url)
        assert r.status_code == 403, f"{url} -> {r.status_code}: {r.text}"


def test_roleless_member_cannot_read_a_strangers_membership_summary(
    make_roleless_member, sakha_pk
):
    """Real (existing) person pk: the 404-first check passes, the gate says 403."""
    me, other = make_roleless_member(sakha_pk), make_roleless_member(sakha_pk)
    r = me["client"].get(f"{FAM}/person/{other['person_pk']}/membership-summary")
    assert r.status_code == 403, r.text


def test_membership_summary_rejects_anonymous(anon_client):
    r = anon_client.get(f"{FAM}/person/{U}/membership-summary")
    assert r.status_code == 401, r.text


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN SCOPE (ADMIN-BR-076/077) on the read endpoints that used to be
# unscoped: a Sakha-scoped admin reaches organizations / persons / members /
# families inside their own subtree only. Read-only lookups documented as
# NSS-wide (member search/directory, /person/search*, /organizations list)
# are deliberately NOT asserted here.
# ═══════════════════════════════════════════════════════════════════════════

from tests.api.test_correspondence import (  # noqa: E402
    SCOPED_PASSWORD,
    _create_admin_with_scope,
    _create_person_with_login,
    _login_headers,
)


@pytest.fixture(scope="module")
def two_scope_sakhas(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
            ORDER BY o.organization_name LIMIT 2
        """)
        rows = [str(r[0]) for r in cur.fetchall()]
    if len(rows) < 2:
        pytest.skip("Need two active Sakhas.")
    return rows


@pytest.fixture(scope="module")
def scope_world(client, write_conn, two_scope_sakhas):
    """A Sakha admin scoped to sakha A, a member+family inside A, and a
    member+family inside B (outside the admin's scope)."""
    a, b = two_scope_sakhas
    admin = _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=a,
    )
    headers = _login_headers(client, admin["sangha_sevi_id"], SCOPED_PASSWORD)

    def member_with_family(org):
        m = _create_person_with_login(write_conn, "ScopeFam", organization_pk=org)
        h = _login_headers(client, m["sangha_sevi_id"], m["password"])
        r = client.post(
            f"{FAM}/families",
            json={"family_name": "Scope Paribara", "sakha_organization_pk": org},
            headers=h,
        )
        assert r.status_code == 201, r.text
        return {**m, "headers": h, "family_pk": r.json()["family_group_pk"]}

    return {
        "a": a, "b": b, "headers": headers,
        "inside": member_with_family(a), "outside": member_with_family(b),
    }


def _get(client, world, path):
    return client.get(path, headers=world["headers"])


class TestScopedAdminOrganizationReads:
    @pytest.mark.parametrize("suffix", ["", "/children", "/children-stats"])
    def test_in_scope_org_is_readable(self, client, scope_world, suffix):
        r = _get(client, scope_world, f"{O}/organizations/{scope_world['a']}{suffix}")
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("suffix", ["", "/children", "/children-stats"])
    def test_out_of_scope_org_is_403(self, client, scope_world, suffix):
        r = _get(client, scope_world, f"{O}/organizations/{scope_world['b']}{suffix}")
        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("suffix", ["", "/children", "/children-stats"])
    def test_unknown_org_is_404_before_403(self, client, scope_world, suffix):
        r = _get(client, scope_world, f"{O}/organizations/{U}{suffix}")
        assert r.status_code == 404, r.text

    def test_darshak_summary_scope(self, client, scope_world):
        ok = _get(client, scope_world, f"{M}/organizations/{scope_world['a']}/darshak-summary")
        assert ok.status_code == 200, ok.text
        out = _get(client, scope_world, f"{M}/organizations/{scope_world['b']}/darshak-summary")
        assert out.status_code == 403, out.text
        unknown = _get(client, scope_world, f"{M}/organizations/{U}/darshak-summary")
        assert unknown.status_code == 404, unknown.text


class TestScopedAdminPersonAndMemberReads:
    @pytest.mark.parametrize("suffix", ["", "/addresses"])
    def test_person_in_and_out_of_scope(self, client, scope_world, suffix):
        inside, outside = scope_world["inside"], scope_world["outside"]
        assert _get(client, scope_world, f"{P}/persons/{inside['person_pk']}{suffix}").status_code == 200
        assert _get(client, scope_world, f"{P}/persons/{outside['person_pk']}{suffix}").status_code == 403

    def test_unknown_person_is_404(self, client, scope_world):
        assert _get(client, scope_world, f"{P}/persons/{U}").status_code == 404

    @pytest.mark.parametrize(
        "suffix", ["", "/affiliations", "/parichaya-patra", "/anumati-patra", "/journey"]
    )
    def test_member_in_and_out_of_scope(self, client, scope_world, suffix):
        inside, outside = scope_world["inside"], scope_world["outside"]
        assert _get(client, scope_world, f"{M}/members/{inside['sangha_sevi_pk']}{suffix}").status_code == 200
        assert _get(client, scope_world, f"{M}/members/{outside['sangha_sevi_pk']}{suffix}").status_code == 403

    def test_unknown_member_is_404(self, client, scope_world):
        assert _get(client, scope_world, f"{M}/members/{U}").status_code == 404

    def test_person_search_remains_nss_wide(self, client, scope_world):
        """Documented-global lookup: the person picker must find people who
        are not yet attached to any Sakha, so it is not scope-filtered."""
        outside = scope_world["outside"]
        r = _get(client, scope_world, f"{P}/search?q={outside['sangha_sevi_id'][:6]}")
        assert r.status_code == 200, r.text


class TestScopedAdminFamilyOverride:
    """FAMILY_VIEW / FAMILY_MANAGE reach only families whose effective Sakha
    is inside the admin's scope (the ownership path is independent of scope)."""

    def test_in_scope_family_is_readable(self, client, scope_world):
        fam = scope_world["inside"]["family_pk"]
        for suffix in ("", "/members", "/head-history", "/admins", "/sakha-alignment"):
            r = _get(client, scope_world, f"{FAM}/families/{fam}{suffix}")
            assert r.status_code == 200, f"{suffix}: {r.text}"

    def test_out_of_scope_family_is_403(self, client, scope_world):
        fam = scope_world["outside"]["family_pk"]
        for suffix in ("", "/members", "/head-history", "/admins", "/sakha-alignment"):
            r = _get(client, scope_world, f"{FAM}/families/{fam}{suffix}")
            assert r.status_code == 403, f"{suffix}: {r.text}"

    def test_out_of_scope_family_cannot_be_managed(self, client, scope_world):
        fam, head = scope_world["outside"]["family_pk"], scope_world["outside"]["person_pk"]
        r = client.post(
            f"{FAM}/families/{fam}/admins", json={"person_pk": head},
            headers=scope_world["headers"],
        )
        assert r.status_code == 403, r.text
        r = client.post(
            f"{FAM}/families/{fam}/transfer-head", json={"person_pk": head},
            headers=scope_world["headers"],
        )
        assert r.status_code == 403, r.text

    def test_person_family_context_scope(self, client, scope_world):
        inside, outside = scope_world["inside"], scope_world["outside"]
        for tail in ("families", "membership-summary"):
            assert _get(client, scope_world, f"{FAM}/person/{inside['person_pk']}/{tail}").status_code == 200
            assert _get(client, scope_world, f"{FAM}/person/{outside['person_pk']}/{tail}").status_code == 403

    def test_owner_keeps_access_regardless_of_scope(self, client, scope_world):
        """The scope bound applies to the permission override only: the
        family's own members (ownership path) read it regardless."""
        out = scope_world["outside"]
        r = client.get(f"{FAM}/families/{out['family_pk']}", headers=out["headers"])
        assert r.status_code == 200, r.text
