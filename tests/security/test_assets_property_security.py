"""
NSS ERP — Security tests for the Assets & Property API (api/routers/assets_property.py).

Focus: access control that the functional tests in tests/api/test_assets_property.py
don't already exercise —
  - every route rejects anonymous callers and garbage tokens (401);
  - every route rejects an authenticated user holding no ASSET_* permission
    (403): a plain member, an Attendance Marker, and the Advisory Board admin
    role (deliberately not granted the module, see GDR-010);
  - ASSET_VIEW alone (NSS_ERP_AUDITOR, scoped to a Sakha) reads in scope but
    can never write;
  - admin scope is evaluated on the EFFECTIVE CUSTODIAN organization (the active one, or - for a
    DISPOSED / RETIRED record - the last one, see TestTerminalRecordsKeepTheirScope): a
    scope-bounded admin of a different Sakha is refused on every sub-resource
    (exact router messages), cannot see the record in lists, and a
    custodian-less record is reachable only by NSS-wide administrators;
  - no member/public exposure: nothing here is reachable without a role.

Exact messages are asserted verbatim against api/routers/assets_property.py.
"""

import re

import pytest

from tests.assets_property_support import (  # noqa: F401  (fixtures)
    BASE, FAKE_UUID, _create_admin_with_scope, _login_headers, _with_sevi_pk, admin_h, admin_user, document_pks,
    make_asset, make_property, other_admin, other_admin_h, other_org_pk, plain_member, plain_member_h,
    register_org_pk, sakha_admin, sakha_admin_h, sakha_pks, viewer_h, viewer_user,
)
from tests.attendance_support import marker_h, marker_user  # noqa: F401  (fixtures)

pytestmark = pytest.mark.integration

_KINDS = ("properties", "assets")
_ROW = {"maintenance_type_code": "UPKEEP"}

# (method, path, json body) — one row per route; ids are FAKE_UUID so a request that got past
# authentication could only ever 404/403/422, never succeed.
ENDPOINTS: list[tuple[str, str, dict | None]] = []
for _k in _KINDS:
    _type = {"properties": ("property_name", "property_type_code", "LAND"), "assets": ("asset_name", "asset_type_code", "EQUIPMENT")}[_k]
    ENDPOINTS += [
        ("POST", f"{BASE}/{_k}", {_type[0]: "x", _type[1]: _type[2]}),
        ("GET", f"{BASE}/{_k}", None),
        ("GET", f"{BASE}/{_k}/{FAKE_UUID}", None),
        ("PATCH", f"{BASE}/{_k}/{FAKE_UUID}", {"notes": "x"}),
        ("POST", f"{BASE}/{_k}/{FAKE_UUID}/transition", {"status": "ACTIVE"}),
        ("DELETE", f"{BASE}/{_k}/{FAKE_UUID}", None),
        ("GET", f"{BASE}/{_k}/{FAKE_UUID}/custodianships", None),
        ("POST", f"{BASE}/{_k}/{FAKE_UUID}/custodianships", {"custodian_organization_pk": FAKE_UUID}),
        ("POST", f"{BASE}/{_k}/{FAKE_UUID}/custodianships/transfer", {"new_custodian_organization_pk": FAKE_UUID}),
        ("GET", f"{BASE}/{_k}/{FAKE_UUID}/maintenance-records", None),
        ("POST", f"{BASE}/{_k}/{FAKE_UUID}/maintenance-records", _ROW),
        ("GET", f"{BASE}/{_k}/{FAKE_UUID}/documents", None),
        ("POST", f"{BASE}/{_k}/{FAKE_UUID}/documents", {"document_master_pk": FAKE_UUID}),
        ("DELETE", f"{BASE}/{_k}/{FAKE_UUID}/documents/{FAKE_UUID}", None),
    ]
ENDPOINTS += [
    ("PATCH", f"{BASE}/maintenance-records/{FAKE_UUID}", {"notes": "x"}),
    ("DELETE", f"{BASE}/maintenance-records/{FAKE_UUID}", None),
    ("GET", f"{BASE}/properties/{FAKE_UUID}/statutory-records", None),
    ("POST", f"{BASE}/properties/{FAKE_UUID}/statutory-records", {"obligation_type_code": "OTHER"}),
    ("PATCH", f"{BASE}/statutory-records/{FAKE_UUID}", {"notes": "x"}),
    ("DELETE", f"{BASE}/statutory-records/{FAKE_UUID}", None),
]
IDS = [f"{m} {p.removeprefix(BASE)}" for m, p, _ in ENDPOINTS]
WRITES = [e for e in ENDPOINTS if e[0] != "GET"]
WRITE_IDS = [f"{m} {p.removeprefix(BASE)}" for m, p, _ in WRITES]


@pytest.fixture(scope="module")
def advisory_board_h(client, write_conn, sakha_pks):
    ab = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADVISORY_BOARD_ADMIN", scope_level="ADVISORY_BOARD", organization_pk=None))
    return _login_headers(client, ab["sangha_sevi_id"], ab["password"])


@pytest.fixture(scope="module")
def mahila_h(client, write_conn, sakha_pks):
    """NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN (NULL-organization scope): owner decision 2026-11-02 - no Assets & Property access."""
    m = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN", scope_level="KENDRA_MAHILA_SANGHA", organization_pk=None))
    return _login_headers(client, m["sangha_sevi_id"], m["password"])


@pytest.fixture(scope="module")
def grouping_view_hs(client, write_conn):
    """Anchalika and Zilla admins (conceptual groupings, each over a fresh Sakha child): VIEW-only (owner decision 2026-11-02)."""
    from uuid import uuid4

    from tests.api.test_correspondence import _create_test_organization

    out = {}
    for role, level, type_code in (("NSS_ERP_ANCHALIKA_ADMIN", "ANCHALIKA", "ANCHALIKA_SANGHA"),
                                   ("NSS_ERP_ZILLA_ADMIN", "ZILLA", "ZILLA_SANGHA")):
        parent = _create_test_organization(write_conn, name_prefix=f"AP sec {level}", type_code=type_code,
                                           parent_pk=None, short_code=f"S{level[0]}{uuid4().hex[:3].upper()}")
        kid = _create_test_organization(write_conn, name_prefix=f"AP sec {level} sakha", type_code="SAKHA_SANGHA",
                                        parent_pk=parent, short_code=f"K{level[0]}{uuid4().hex[:3].upper()}")
        user = _with_sevi_pk(write_conn, _create_admin_with_scope(
            write_conn, role_code=role, scope_level=level, organization_pk=parent))
        out[level] = {"headers": _login_headers(client, user["sangha_sevi_id"], user["password"]), "parent": parent, "kid": kid}
    return out


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    """Guard: a new Assets & Property route must be added to ENDPOINTS above."""
    from api.routers.assets_property import router

    routes = set()
    for r in router.routes:
        for m in r.methods:
            if m == "HEAD":
                continue
            for k in (_KINDS if "{kind}" in r.path else (None,)):
                path = r.path.replace("{kind}", k) if k else r.path
                routes.add((m, re.sub(r"\{[^}]+\}", FAKE_UUID, path)))
    assert routes == {(m, p) for m, p, _ in ENDPOINTS}
    assert len(router.routes) == 26


class TestAuthentication:

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_anonymous_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body).status_code == 401

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_garbage_token_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body, {"Authorization": "Bearer not.a.jwt"}).status_code == 401


class TestPermissionGate:

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_member_without_asset_permission_is_403(self, method, path, body, client, plain_member_h):
        assert _call(client, method, path, body, plain_member_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_attendance_marker_has_no_asset_access(self, method, path, body, client, marker_h):
        """NSS_ERP_ATTENDANCE_MARKER is a single-purpose role (GDR-010)."""
        assert _call(client, method, path, body, marker_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_advisory_board_admin_has_no_asset_access(self, method, path, body, client, advisory_board_h):
        """Least privilege: the Advisory Board admin role is not granted ASSET_* (owner decision pending, GDR-010)."""
        assert _call(client, method, path, body, advisory_board_h).status_code == 403

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_mahila_admin_has_no_asset_access(self, method, path, body, client, mahila_h):
        """Owner decision 2026-11-02 (GDR-010): the Mahila admin role holds neither ASSET_VIEW nor ASSET_MANAGE."""
        assert _call(client, method, path, body, mahila_h).status_code == 403

    @pytest.mark.parametrize("level", ["ANCHALIKA", "ZILLA"])
    @pytest.mark.parametrize("method,path,body", WRITES, ids=WRITE_IDS)
    def test_anchalika_and_zilla_admins_cannot_write(self, level, method, path, body, client, grouping_view_hs):
        """Owner decision 2026-11-02: Anchalika / Zilla admins are VIEW-only - every mutating route is 403."""
        assert _call(client, method, path, body, grouping_view_hs[level]["headers"]).status_code == 403

    @pytest.mark.parametrize("level", ["ANCHALIKA", "ZILLA"])
    def test_anchalika_and_zilla_admins_can_read_their_subtree(self, level, client, admin_h, grouping_view_hs):
        g = grouping_view_hs[level]
        rec = make_property(client, admin_h, g["kid"])
        assert client.get(f"{BASE}/properties/{rec['property_pk']}", headers=g["headers"]).status_code == 200
        r = client.get(f"{BASE}/assets", params={"custodian_organization_pk": g["parent"], "include_sub_organizations": "true"},
                       headers=g["headers"])
        assert r.status_code == 200

    @pytest.mark.parametrize("method,path,body", WRITES, ids=WRITE_IDS)
    def test_view_only_role_cannot_write(self, method, path, body, client, viewer_h):
        """ASSET_VIEW (NSS_ERP_AUDITOR) reads but every mutating route needs ASSET_MANAGE."""
        assert _call(client, method, path, body, viewer_h).status_code == 403

    def test_view_only_role_can_read(self, client, sakha_admin_h, viewer_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        for path in (f"properties/{p}", f"properties/{p}/custodianships", f"properties/{p}/maintenance-records",
                     f"properties/{p}/statutory-records", f"properties/{p}/documents", "properties", "assets"):
            assert client.get(f"{BASE}/{path}", headers=viewer_h).status_code == 200, path

    def test_view_only_role_outside_its_scope_is_refused(self, client, other_admin_h, viewer_h, other_org_pk):
        """The auditor is scoped to the register Sakha; a record held by the other Sakha is out of scope."""
        p = make_property(client, other_admin_h, other_org_pk)["property_pk"]
        r = client.get(f"{BASE}/properties/{p}", headers=viewer_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only view this property within your admin scope."


class TestAdminScope:
    """other_admin is a SAKHA_ADMIN scoped to a different Sakha than the records below."""

    @pytest.fixture(scope="class")
    @classmethod
    def mine(cls, client, sakha_admin_h, document_pks, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        a = make_asset(client, sakha_admin_h, register_org_pk)
        rec = client.post(f"{BASE}/properties/{p['property_pk']}/statutory-records", headers=sakha_admin_h,
                          json={"obligation_type_code": "LAND_REVENUE"}).json()
        mr = client.post(f"{BASE}/assets/{a['asset_pk']}/maintenance-records", headers=sakha_admin_h, json=_ROW).json()
        link = client.post(f"{BASE}/properties/{p['property_pk']}/documents", headers=sakha_admin_h,
                           json={"document_master_pk": document_pks[0]}).json()
        return {"p": p["property_pk"], "a": a["asset_pk"], "rec": rec["property_statutory_record_pk"],
                "mr": mr["maintenance_record_pk"], "link": link["link_pk"]}

    @pytest.mark.parametrize("kind,key", [("properties", "p"), ("assets", "a")])
    def test_foreign_admin_is_refused_on_every_entity_route(self, kind, key, mine, client, other_admin_h, other_org_pk):
        noun = kind[:-1] if kind == "assets" else "property"
        e = mine[key]
        expect = {
            ("GET", ""): f"view this {noun}",
            ("PATCH", ""): f"edit this {noun}",
            ("DELETE", ""): f"archive this {noun}",
            ("POST", "/transition"): f"record a lifecycle event for this {noun}",
            ("GET", "/custodianships"): f"view this {noun}",
            ("POST", "/custodianships/transfer"): f"transfer custody of this {noun}",
            ("GET", "/maintenance-records"): f"view this {noun}",
            ("POST", "/maintenance-records"): f"record maintenance for this {noun}",
            ("GET", "/documents"): f"view this {noun}",
            ("POST", "/documents"): f"attach a document to this {noun}",
        }
        bodies = {
            ("PATCH", ""): {"notes": "x"}, ("POST", "/transition"): {"status": "UNDER_MAINTENANCE"},
            ("POST", "/custodianships/transfer"): {"new_custodian_organization_pk": other_org_pk},
            ("POST", "/maintenance-records"): _ROW, ("POST", "/documents"): {"document_master_pk": FAKE_UUID},
        }
        for (method, suffix), action in expect.items():
            r = client.request(method, f"{BASE}/{kind}/{e}{suffix}", json=bodies.get((method, suffix)), headers=other_admin_h)
            assert r.status_code == 403, (method, suffix, r.text)
            assert r.json()["detail"] == f"You can only {action} within your admin scope.", (method, suffix)

    def test_foreign_admin_is_refused_on_record_level_routes(self, mine, client, other_admin_h):
        for method, path, action in [
            ("PATCH", f"maintenance-records/{mine['mr']}", "edit a maintenance record of this asset"),
            ("DELETE", f"maintenance-records/{mine['mr']}", "delete a maintenance record of this asset"),
            ("PATCH", f"statutory-records/{mine['rec']}", "edit a statutory record of this property"),
            ("DELETE", f"statutory-records/{mine['rec']}", "delete a statutory record of this property"),
            ("GET", f"properties/{mine['p']}/statutory-records", "view this property"),
            ("POST", f"properties/{mine['p']}/statutory-records", "record a statutory obligation for this property"),
            ("DELETE", f"properties/{mine['p']}/documents/{mine['link']}", "detach a document from this property"),
        ]:
            body = {"notes": "x"} if method == "PATCH" else ({"obligation_type_code": "OTHER"} if method == "POST" else None)
            r = client.request(method, f"{BASE}/{path}", json=body, headers=other_admin_h)
            assert r.status_code == 403, (method, path, r.text)
            assert r.json()["detail"] == f"You can only {action} within your admin scope.", (method, path)

    def test_foreign_admin_cannot_assign_a_custodian_to_foreign_record(self, mine, client, other_admin_h, other_org_pk):
        r = client.post(f"{BASE}/properties/{mine['p']}/custodianships", headers=other_admin_h,
                        json={"custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only assign a custodian to this property within your admin scope."

    def test_nothing_was_modified_by_the_denied_calls(self, mine, client, sakha_admin_h):
        r = client.get(f"{BASE}/properties/{mine['p']}", headers=sakha_admin_h).json()
        assert r["status"] == "ACTIVE" and r["notes"] is None
        assert client.get(f"{BASE}/properties/{mine['p']}/statutory-records", headers=sakha_admin_h).json()["total"] == 1
        assert client.get(f"{BASE}/assets/{mine['a']}/maintenance-records", headers=sakha_admin_h).json()["total"] == 1
        assert client.get(f"{BASE}/properties/{mine['p']}/documents", headers=sakha_admin_h).json()["total"] == 1
        assert client.get(f"{BASE}/properties/{mine['p']}/custodianships", headers=sakha_admin_h).json()["total"] == 1

    def test_unfiltered_lists_do_not_leak_foreign_rows(self, mine, client, other_admin_h):
        for kind, key in (("properties", "p"), ("assets", "a")):
            seen = client.get(f"{BASE}/{kind}", params={"page_size": 100}, headers=other_admin_h).json()["items"]
            assert mine[key] not in {i["property_pk" if kind == "properties" else "asset_pk"] for i in seen}

    def test_foreign_custodian_filter_is_refused(self, mine, client, other_admin_h, register_org_pk):
        r = client.get(f"{BASE}/assets", params={"custodian_organization_pk": register_org_pk}, headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only view this organization's asset records within your admin scope."

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_include_sub_organizations_never_widens_scope(self, mine, client, other_admin_h, register_org_pk, kind):
        """include_sub_organizations is a filter, not a grant: a foreign organization is still 403, and the
        flag without a custodian filter changes nothing about what a scoped admin can see."""
        r = client.get(f"{BASE}/{kind}", params={"custodian_organization_pk": register_org_pk,
                                                 "include_sub_organizations": "true"}, headers=other_admin_h)
        assert r.status_code == 403
        seen = client.get(f"{BASE}/{kind}", params={"include_sub_organizations": "true", "page_size": 100},
                          headers=other_admin_h).json()["items"]
        assert mine["p" if kind == "properties" else "a"] not in {
            i["property_pk" if kind == "properties" else "asset_pk"] for i in seen}


class TestCustodianlessRecords:
    """A record with no custodian has no organizational anchor: NSS-wide administrators only."""

    def test_scoped_admin_cannot_see_or_touch_it(self, client, admin_h, sakha_admin_h, register_org_pk):
        orphan = make_property(client, admin_h)
        pk = orphan["property_pk"]
        detail = "This record has no custodian, so only NSS-wide administrators can {}."
        for method, path, body, action in [
            ("GET", f"properties/{pk}", None, "view this property"),
            ("PATCH", f"properties/{pk}", {"notes": "x"}, "edit this property"),
            ("POST", f"properties/{pk}/custodianships", {"custodian_organization_pk": register_org_pk},
             "assign a custodian to this property"),
            ("POST", f"properties/{pk}/maintenance-records", _ROW, "record maintenance for this property"),
        ]:
            r = client.request(method, f"{BASE}/{path}", json=body, headers=sakha_admin_h)
            assert r.status_code == 403, (method, path, r.text)
            assert r.json()["detail"] == detail.format(action)
        listed = client.get(f"{BASE}/properties", params={"page_size": 100}, headers=sakha_admin_h).json()["items"]
        assert pk not in {i["property_pk"] for i in listed}

    def test_global_admin_can(self, client, admin_h, register_org_pk):
        pk = make_property(client, admin_h)["property_pk"]
        assert client.get(f"{BASE}/properties/{pk}", headers=admin_h).status_code == 200
        assert client.post(f"{BASE}/properties/{pk}/custodianships", headers=admin_h,
                           json={"custodian_organization_pk": register_org_pk}).status_code == 201


class TestCustodyTransferNeedsBothScopes:

    def test_scoped_admin_cannot_push_a_record_onto_another_unit(self, client, sakha_admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=sakha_admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only transfer this property to this organization within your admin scope."

    def test_scoped_admin_cannot_pull_a_record_from_another_unit(self, client, other_admin_h, sakha_admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=other_admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only transfer custody of this property within your admin scope."

    def test_scoped_admin_cannot_register_for_a_foreign_unit(self, client, sakha_admin_h, other_org_pk):
        r = client.post(f"{BASE}/assets", headers=sakha_admin_h, json={
            "asset_name": "x", "asset_type_code": "EQUIPMENT", "custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only register asset records for this organization within your admin scope."


class TestTerminalRecordsKeepTheirScope:
    """
    GDR-010 §2F: disposal / retirement ENDs the custodianship, yet the record's scope anchor is the
    EFFECTIVE custodian (the last one). A terminal record must stay exactly as reachable as before -
    never downgraded to 'custodian-less / NSS-wide only' - and never leak to a foreign admin.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def gone(cls, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        a = make_asset(client, sakha_admin_h, register_org_pk)
        assert client.post(f"{BASE}/properties/{p['property_pk']}/transition", headers=sakha_admin_h,
                           json={"status": "DISPOSED"}).status_code == 200
        assert client.post(f"{BASE}/assets/{a['asset_pk']}/transition", headers=sakha_admin_h,
                           json={"status": "RETIRED"}).status_code == 200
        return {"properties": p["property_pk"], "assets": a["asset_pk"]}

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_owning_scope_still_reaches_it_not_the_custodianless_message(self, kind, gone, client, sakha_admin_h):
        r = client.get(f"{BASE}/{kind}/{gone[kind]}", headers=sakha_admin_h)
        assert r.status_code == 200 and r.json()["custodian_is_last"] is True
        assert client.patch(f"{BASE}/{kind}/{gone[kind]}", json={"notes": "n"}, headers=sakha_admin_h).status_code == 200

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_foreign_admin_is_refused_with_the_scope_message(self, kind, gone, client, other_admin_h):
        noun = "property" if kind == "properties" else "asset"
        for method, suffix, body, action in [
            ("GET", "", None, f"view this {noun}"),
            ("PATCH", "", {"notes": "x"}, f"edit this {noun}"),
            ("DELETE", "", None, f"archive this {noun}"),
            ("GET", "/custodianships", None, f"view this {noun}"),
            ("GET", "/maintenance-records", None, f"view this {noun}"),
            ("POST", "/maintenance-records", _ROW, f"record maintenance for this {noun}"),
            ("GET", "/documents", None, f"view this {noun}"),
        ]:
            r = client.request(method, f"{BASE}/{kind}/{gone[kind]}{suffix}", json=body, headers=other_admin_h)
            assert r.status_code == 403, (method, suffix, r.text)
            assert r.json()["detail"] == f"You can only {action} within your admin scope.", (method, suffix)

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_foreign_admin_does_not_see_it_in_lists_or_filters(self, kind, gone, client, other_admin_h, register_org_pk):
        key = "property_pk" if kind == "properties" else "asset_pk"
        status = "DISPOSED" if kind == "properties" else "RETIRED"
        seen = client.get(f"{BASE}/{kind}", params={"status": status, "page_size": 100}, headers=other_admin_h).json()["items"]
        assert gone[kind] not in {i[key] for i in seen}
        assert client.get(f"{BASE}/{kind}", params={"custodian_organization_pk": register_org_pk},
                          headers=other_admin_h).status_code == 403

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_view_only_role_reads_but_never_writes_it(self, kind, gone, client, viewer_h):
        assert client.get(f"{BASE}/{kind}/{gone[kind]}", headers=viewer_h).status_code == 200
        assert client.patch(f"{BASE}/{kind}/{gone[kind]}", json={"notes": "x"}, headers=viewer_h).status_code == 403
        assert client.delete(f"{BASE}/{kind}/{gone[kind]}", headers=viewer_h).status_code == 403

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_acquisition_method_filter_does_not_widen_scope(self, kind, gone, client, sakha_admin_h, other_admin_h):
        key = "property_pk" if kind == "properties" else "asset_pk"
        assert client.patch(f"{BASE}/{kind}/{gone[kind]}", json={"acquisition_method_code": "PURCHASE"},
                            headers=sakha_admin_h).status_code == 200
        params = {"acquisition_method_code": "PURCHASE", "page_size": 100}
        mine = client.get(f"{BASE}/{kind}", params=params, headers=sakha_admin_h).json()["items"]
        assert gone[kind] in {i[key] for i in mine}
        theirs = client.get(f"{BASE}/{kind}", params=params, headers=other_admin_h)
        assert theirs.status_code == 200 and gone[kind] not in {i[key] for i in theirs.json()["items"]}
