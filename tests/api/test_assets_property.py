"""
NSS ERP — Assets & Property API tests (Module #22, api/routers/assets_property.py).

Integration tests for every endpoint group:

  1. Properties      — register / list+filters / detail / PATCH / archive
  2. Assets          — same surface, asset vocabulary
  3. Lifecycle       — SOL-AP-003 transitions, terminal states, custody-before-activation
  4. Custodianship   — assign (first custodian), transfer = close + open, history (AP-017/018/042)
  5. Statutory       — property-only (AP-040), no asset route
  6. Maintenance     — property or asset, correct/delete
  7. Documents       — attach/detach via Foundation document_master
  8. Scope / RBAC    — custodian-organization admin scope, view-only role, audit trail
  9. Custodian type  — only PHYSICAL organizations hold property/assets (GDR-010 §2C);
                       include_sub_organizations list option
 10. Belongs to      — optional attribution organization (GDR-010 item 4): set / clear / filter,
                       informational only (no scope widening, custodian rule unaffected)
 11. Disposal / retirement closes custody (GDR-010 §2F): same-transaction ENDED custodianship,
                       last custodian still reported (custodian_is_last), scope / filters unchanged
 12. Acquisition method (GDR-010 §2E): set / clear / filter / unknown code, informational only

Authorization model under test: ASSET_VIEW/ASSET_MANAGE + admin scope on the
EFFECTIVE custodian organization (active, or the last one of a DISPOSED / RETIRED record); a custodian-less record is the global
authority's only. Runs against the local bootstrapped PostgreSQL (Phase 11g
DDL, ASSET_* permissions patch, reference-data patch); everything rolls back
with the module SAVEPOINT.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from tests.assets_property_support import (  # noqa: F401  (fixtures + helpers)
    BASE, ELIGIBLE_CUSTODIAN_TYPES, FAKE_UUID, INELIGIBLE_CUSTODIAN_TYPES, TODAY, _create_admin_with_scope,
    _login_headers, _with_sevi_pk, admin_h, admin_user, document_pks, make_asset, make_property, org_of_type, other_admin,
    other_admin_h, other_org_pk, plain_member, plain_member_h, register_org_pk, sakha_admin, sakha_admin_h,
    sakha_pks, transition, viewer_h, viewer_user,
)

pytestmark = pytest.mark.integration


# ═══════════════════════════════════════════════════════════════════════
# 1. Properties
# ═══════════════════════════════════════════════════════════════════════

class TestRegisterProperty:

    def test_scoped_admin_registers_with_own_custodian(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk, location_description="Puri",
                          holding_arrangement="In the name of Shri Shri Thakur")
        assert p["property_id"].startswith("PROP") and p["property_id"][4:].isdigit()
        assert p["status"] == "ACTIVE", "first custody advances REGISTERED -> ACTIVE (SOL-AP-003 §3.3)"
        assert p["current_custodian_organization_pk"] == register_org_pk
        assert p["property_type_code"] == "LAND"
        assert p["holding_arrangement"] == "In the name of Shri Shri Thakur"
        assert p["current_custodian_since"] == TODAY

    def test_ids_are_unique_and_sequential_per_namespace(self, client, sakha_admin_h, register_org_pk):
        a = make_property(client, sakha_admin_h, register_org_pk)
        b = make_property(client, sakha_admin_h, register_org_pk)
        assert int(b["property_id"][4:]) == int(a["property_id"][4:]) + 1
        asset = make_asset(client, sakha_admin_h, register_org_pk)
        assert asset["asset_id"].startswith("AST") and not asset["asset_id"].startswith("PROP")

    def test_scoped_admin_must_name_a_custodian(self, client, sakha_admin_h):
        r = client.post(f"{BASE}/properties", json={"property_name": "X", "property_type_code": "LAND"},
                        headers=sakha_admin_h)
        assert r.status_code == 422
        assert "custodian_organization_pk is required" in r.json()["detail"]

    def test_scoped_admin_cannot_register_for_foreign_organization(self, client, sakha_admin_h, other_org_pk):
        r = client.post(f"{BASE}/properties", headers=sakha_admin_h, json={
            "property_name": "X", "property_type_code": "LAND", "custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only register property records for this organization within your admin scope."

    def test_global_admin_may_register_without_custodian(self, client, admin_h):
        p = make_property(client, admin_h)
        assert p["status"] == "REGISTERED"
        assert p["current_custodian_organization_pk"] is None and p["current_custodianship_pk"] is None

    def test_unknown_type_code_is_422(self, client, admin_h):
        r = client.post(f"{BASE}/properties", json={"property_name": "X", "property_type_code": "NOPE"}, headers=admin_h)
        assert r.status_code == 422
        assert r.json()["detail"] == "Unknown PROPERTY_TYPE value 'NOPE'."

    def test_asset_type_code_is_not_a_property_type(self, client, admin_h):
        r = client.post(f"{BASE}/properties", json={"property_name": "X", "property_type_code": "EQUIPMENT"}, headers=admin_h)
        assert r.status_code == 422

    def test_unknown_custodian_organization_is_422(self, client, admin_h):
        r = client.post(f"{BASE}/properties", headers=admin_h, json={
            "property_name": "X", "property_type_code": "LAND", "custodian_organization_pk": FAKE_UUID})
        assert r.status_code == 422

    @pytest.mark.parametrize("body", [
        {"property_name": "", "property_type_code": "LAND"},
        {"property_type_code": "LAND"},
        {"property_name": "X"},
        {"property_name": "X", "property_type_code": "LAND", "custodian_effective_from": "2999-01-01"},
    ])
    def test_invalid_body_is_422(self, client, admin_h, body):
        assert client.post(f"{BASE}/properties", json=body, headers=admin_h).status_code == 422

    def test_no_financial_fields_in_the_response(self, client, admin_h):
        p = make_property(client, admin_h)
        assert not {k for k in p if any(w in k for w in ("amount", "cost", "price", "value", "payment"))}


class TestReadProperties:

    def test_detail_and_scope(self, client, sakha_admin_h, other_admin_h, admin_h, viewer_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk, location_description="Biratung")
        pk = p["property_pk"]
        for h in (sakha_admin_h, admin_h, viewer_h):
            r = client.get(f"{BASE}/properties/{pk}", headers=h)
            assert r.status_code == 200 and r.json()["property_pk"] == pk
        r = client.get(f"{BASE}/properties/{pk}", headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only view this property within your admin scope."

    def test_unknown_and_malformed_pk(self, client, admin_h):
        assert client.get(f"{BASE}/properties/{FAKE_UUID}", headers=admin_h).status_code == 404
        assert client.get(f"{BASE}/properties/not-a-uuid", headers=admin_h).status_code == 422

    def test_list_filters_and_paging(self, client, sakha_admin_h, admin_h, register_org_pk):
        tag = uuid4().hex[:8]
        a = make_property(client, sakha_admin_h, register_org_pk, property_name=f"Filter {tag} A", property_type_code="BUILDING")
        make_property(client, sakha_admin_h, register_org_pk, property_name=f"Filter {tag} B", property_type_code="LAND")
        q = client.get(f"{BASE}/properties", params={"q": tag}, headers=sakha_admin_h).json()
        assert q["total"] == 2 and q["page"] == 1
        by_type = client.get(f"{BASE}/properties", params={"q": tag, "type_code": "BUILDING"}, headers=sakha_admin_h).json()
        assert [i["property_pk"] for i in by_type["items"]] == [a["property_pk"]]
        by_status = client.get(f"{BASE}/properties", params={"q": tag, "status": "REGISTERED"}, headers=sakha_admin_h).json()
        assert by_status["total"] == 0
        by_cust = client.get(f"{BASE}/properties", params={"q": tag, "custodian_organization_pk": register_org_pk},
                             headers=admin_h).json()
        assert by_cust["total"] == 2
        paged = client.get(f"{BASE}/properties", params={"q": tag, "page": 2, "page_size": 1}, headers=sakha_admin_h).json()
        assert len(paged["items"]) == 1 and paged["total"] == 2 and paged["page_size"] == 1

    def test_list_page_size_is_capped(self, client, admin_h):
        assert client.get(f"{BASE}/properties", params={"page_size": 101}, headers=admin_h).status_code == 422

    def test_list_is_scoped_to_current_custodian(self, client, sakha_admin_h, other_admin_h, admin_h, register_org_pk):
        tag = uuid4().hex[:8]
        make_property(client, sakha_admin_h, register_org_pk, property_name=f"Scoped {tag}")
        orphan = make_property(client, admin_h, property_name=f"Scoped orphan {tag}")
        mine = client.get(f"{BASE}/properties", params={"q": tag}, headers=sakha_admin_h).json()
        assert mine["total"] == 1, "a custodian-less record is invisible to a scope-bounded admin"
        assert client.get(f"{BASE}/properties", params={"q": tag}, headers=other_admin_h).json()["total"] == 0
        all_ = client.get(f"{BASE}/properties", params={"q": tag}, headers=admin_h).json()
        assert {i["property_pk"] for i in all_["items"]} >= {orphan["property_pk"]} and all_["total"] == 2

    def test_foreign_custodian_filter_is_refused(self, client, other_admin_h, register_org_pk):
        r = client.get(f"{BASE}/properties", params={"custodian_organization_pk": register_org_pk}, headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only view this organization's property records within your admin scope."


class TestUpdateProperty:

    def test_patch_descriptive_fields_only(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        r = client.patch(f"{BASE}/properties/{p['property_pk']}", headers=sakha_admin_h, json={
            "property_name": "Renamed", "property_type_code": "PREMISES", "notes": "n",
            "status": "DISPOSED", "property_id": "HACKED"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["property_name"] == "Renamed" and body["property_type_code"] == "PREMISES" and body["notes"] == "n"
        assert body["status"] == "ACTIVE", "status is not writable through PATCH"
        assert body["property_id"] == p["property_id"], "identifier is immutable (AP-005)"

    def test_clear_optional_field_with_null(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk, location_description="here")
        r = client.patch(f"{BASE}/properties/{p['property_pk']}", json={"location_description": None}, headers=sakha_admin_h)
        assert r.status_code == 200 and r.json()["location_description"] is None

    @pytest.mark.parametrize("body", [{}, {"property_name": None}, {"property_name": "  "}, {"property_type_code": None},
                                      {"property_type_code": "BOGUS"}])
    def test_invalid_patch_is_422(self, client, sakha_admin_h, register_org_pk, body):
        p = make_property(client, sakha_admin_h, register_org_pk)
        assert client.patch(f"{BASE}/properties/{p['property_pk']}", json=body, headers=sakha_admin_h).status_code == 422

    def test_foreign_admin_cannot_patch(self, client, sakha_admin_h, other_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        r = client.patch(f"{BASE}/properties/{p['property_pk']}", json={"notes": "x"}, headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only edit this property within your admin scope."


class TestArchiveProperty:

    def test_live_property_cannot_be_archived(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        r = client.delete(f"{BASE}/properties/{p['property_pk']}", headers=sakha_admin_h)
        assert r.status_code == 409
        assert "DISPOSED" in r.json()["detail"]

    def test_registered_in_error_and_disposed_can_be_archived(self, client, sakha_admin_h, admin_h, register_org_pk):
        orphan = make_property(client, admin_h)
        assert client.delete(f"{BASE}/properties/{orphan['property_pk']}", headers=admin_h).status_code == 200
        assert client.get(f"{BASE}/properties/{orphan['property_pk']}", headers=admin_h).status_code == 404
        p = make_property(client, sakha_admin_h, register_org_pk)
        assert transition(client, sakha_admin_h, "properties", p["property_pk"], "DISPOSED").status_code == 200
        assert client.delete(f"{BASE}/properties/{p['property_pk']}", headers=sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/properties/{p['property_pk']}", headers=sakha_admin_h).status_code == 404

    def test_archived_property_row_is_retained(self, client, write_conn, admin_h):
        orphan = make_property(client, admin_h)
        client.delete(f"{BASE}/properties/{orphan['property_pk']}", headers=admin_h)
        cur = write_conn.cursor()
        cur.execute("SELECT is_active, deleted_at IS NOT NULL FROM nss.property WHERE property_pk = %s", (orphan["property_pk"],))
        assert cur.fetchone() == (False, True)


# ═══════════════════════════════════════════════════════════════════════
# 2. Assets
# ═══════════════════════════════════════════════════════════════════════

class TestAssets:

    def test_register_and_read(self, client, sakha_admin_h, other_admin_h, register_org_pk):
        a = make_asset(client, sakha_admin_h, register_org_pk, asset_type_code="INSTRUMENT", condition="good",
                       location_description="Prayer hall")
        assert a["status"] == "IN_CUSTODY" and a["condition"] == "good" and a["asset_type_code"] == "INSTRUMENT"
        assert client.get(f"{BASE}/assets/{a['asset_pk']}", headers=sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/assets/{a['asset_pk']}", headers=other_admin_h).status_code == 403

    def test_property_type_is_not_an_asset_type(self, client, admin_h):
        r = client.post(f"{BASE}/assets", json={"asset_name": "X", "asset_type_code": "LAND"}, headers=admin_h)
        assert r.status_code == 422
        assert r.json()["detail"] == "Unknown ASSET_TYPE value 'LAND'."

    def test_list_filters(self, client, sakha_admin_h, register_org_pk):
        tag = uuid4().hex[:8]
        make_asset(client, sakha_admin_h, register_org_pk, asset_name=f"Lamp {tag}", asset_type_code="ARTICLE")
        make_asset(client, sakha_admin_h, register_org_pk, asset_name=f"Chair {tag}", asset_type_code="FURNITURE")
        assert client.get(f"{BASE}/assets", params={"q": tag}, headers=sakha_admin_h).json()["total"] == 2
        r = client.get(f"{BASE}/assets", params={"q": tag, "type_code": "ARTICLE"}, headers=sakha_admin_h).json()
        assert r["total"] == 1 and r["items"][0]["asset_name"] == f"Lamp {tag}"

    def test_patch_condition_and_immutable_identity(self, client, sakha_admin_h, register_org_pk):
        a = make_asset(client, sakha_admin_h, register_org_pk)
        r = client.patch(f"{BASE}/assets/{a['asset_pk']}", json={"condition": "worn", "asset_id": "X", "status": "RETIRED"},
                         headers=sakha_admin_h)
        assert r.status_code == 200
        assert r.json()["condition"] == "worn" and r.json()["asset_id"] == a["asset_id"] and r.json()["status"] == "IN_CUSTODY"

    def test_asset_lifecycle(self, client, sakha_admin_h, register_org_pk):
        a = make_asset(client, sakha_admin_h, register_org_pk)
        pk = a["asset_pk"]
        assert transition(client, sakha_admin_h, "assets", pk, "DISPOSED").status_code == 422, "assets are RETIRED, not DISPOSED"
        assert transition(client, sakha_admin_h, "assets", pk, "UNDER_MAINTENANCE").json()["status"] == "UNDER_MAINTENANCE"
        assert transition(client, sakha_admin_h, "assets", pk, "IN_CUSTODY").json()["status"] == "IN_CUSTODY"
        assert transition(client, sakha_admin_h, "assets", pk, "UNDER_MAINTENANCE").status_code == 200
        r = transition(client, sakha_admin_h, "assets", pk, "RETIRED", remarks="Governing Body resolution 12")
        assert r.status_code == 200 and r.json()["status"] == "RETIRED"
        r = transition(client, sakha_admin_h, "assets", pk, "IN_CUSTODY")
        assert r.status_code == 422 and "terminal" in r.json()["detail"] and "AP-047" in r.json()["detail"]

    def test_archive_rules(self, client, sakha_admin_h, register_org_pk):
        a = make_asset(client, sakha_admin_h, register_org_pk)
        assert client.delete(f"{BASE}/assets/{a['asset_pk']}", headers=sakha_admin_h).status_code == 409
        transition(client, sakha_admin_h, "assets", a["asset_pk"], "RETIRED")
        assert client.delete(f"{BASE}/assets/{a['asset_pk']}", headers=sakha_admin_h).status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# 3. Lifecycle (property)
# ═══════════════════════════════════════════════════════════════════════

class TestPropertyLifecycle:

    def test_full_cycle_and_audit(self, client, write_conn, sakha_admin_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        assert transition(client, sakha_admin_h, "properties", pk, "UNDER_MAINTENANCE", "roof").json()["status"] == "UNDER_MAINTENANCE"
        assert transition(client, sakha_admin_h, "properties", pk, "ACTIVE").json()["status"] == "ACTIVE"
        r = transition(client, sakha_admin_h, "properties", pk, "DISPOSED", "Governing Body resolution 5")
        assert r.status_code == 200 and r.json()["status"] == "DISPOSED"
        cur = write_conn.cursor()
        cur.execute(
            "SELECT detail->>'remarks' FROM nss.system_event_log WHERE record_pk = %s AND action = 'STATUS_CHANGE' "
            "AND detail->>'to' = 'DISPOSED'", (pk,))
        assert cur.fetchone()[0] == "Governing Body resolution 5", "the Governance reference is recorded, not approved (AP-045)"

    @pytest.mark.parametrize("target,fragment", [
        ("BOGUS", "Unknown property status"),
        ("REGISTERED", "Invalid transition ACTIVE -> REGISTERED"),
        ("ACTIVE", "already ACTIVE"),
        ("IN_CUSTODY", "Unknown property status"),
    ])
    def test_invalid_targets_from_active(self, client, sakha_admin_h, register_org_pk, target, fragment):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = transition(client, sakha_admin_h, "properties", pk, target)
        assert r.status_code == 422 and fragment in r.json()["detail"]

    def test_disposed_is_terminal(self, client, sakha_admin_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        transition(client, sakha_admin_h, "properties", pk, "DISPOSED")
        for target in ("ACTIVE", "UNDER_MAINTENANCE", "REGISTERED"):
            r = transition(client, sakha_admin_h, "properties", pk, target)
            assert r.status_code == 422 and "AP-046" in r.json()["detail"]

    def test_leaving_registered_needs_a_custodian(self, client, admin_h):
        pk = make_property(client, admin_h)["property_pk"]
        r = transition(client, admin_h, "properties", pk, "ACTIVE")
        assert r.status_code == 422 and "AP-LIF-001" in r.json()["detail"]
        assert transition(client, admin_h, "properties", pk, "DISPOSED").status_code == 422

    def test_custody_transfer_never_changes_status(self, client, admin_h, register_org_pk, other_org_pk):
        p = make_property(client, admin_h, register_org_pk)
        transition(client, admin_h, "properties", p["property_pk"], "UNDER_MAINTENANCE")
        client.post(f"{BASE}/properties/{p['property_pk']}/custodianships/transfer", headers=admin_h,
                    json={"new_custodian_organization_pk": other_org_pk})
        assert client.get(f"{BASE}/properties/{p['property_pk']}", headers=admin_h).json()["status"] == "UNDER_MAINTENANCE"

    def test_view_only_role_cannot_transition(self, client, sakha_admin_h, viewer_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        assert transition(client, viewer_h, "properties", pk, "DISPOSED").status_code == 403

    def test_foreign_admin_cannot_transition(self, client, sakha_admin_h, other_admin_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = transition(client, other_admin_h, "properties", pk, "DISPOSED")
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only record a lifecycle event for this property within your admin scope."


# ═══════════════════════════════════════════════════════════════════════
# 4. Custodianship
# ═══════════════════════════════════════════════════════════════════════

class TestCustodianship:

    def test_assign_first_custodian_advances_registered(self, client, admin_h, register_org_pk):
        p = make_property(client, admin_h)
        r = client.post(f"{BASE}/properties/{p['property_pk']}/custodianships", headers=admin_h,
                        json={"custodian_organization_pk": register_org_pk, "notes": "first"})
        assert r.status_code == 201, r.text
        c = r.json()
        assert c["status"] == "ACTIVE" and c["property_pk"] == p["property_pk"] and c["asset_pk"] is None
        assert c["effective_to"] is None and c["end_reason_code"] is None and c["notes"] == "first"
        detail = client.get(f"{BASE}/properties/{p['property_pk']}", headers=admin_h).json()
        assert detail["status"] == "ACTIVE" and detail["current_custodianship_pk"] == c["custodianship_pk"]

    def test_scoped_admin_cannot_assign_to_a_custodian_less_record(self, client, admin_h, sakha_admin_h, register_org_pk):
        p = make_property(client, admin_h)
        r = client.post(f"{BASE}/properties/{p['property_pk']}/custodianships", headers=sakha_admin_h,
                        json={"custodian_organization_pk": register_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "This record has no custodian, so only NSS-wide administrators can assign a custodian to this property."

    def test_second_assignment_is_409(self, client, sakha_admin_h, admin_h, register_org_pk, other_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        r = client.post(f"{BASE}/properties/{p['property_pk']}/custodianships", headers=admin_h,
                        json={"custodian_organization_pk": other_org_pk})
        assert r.status_code == 409 and "AP-017" in r.json()["detail"]

    def test_transfer_closes_current_and_opens_new(self, client, admin_h, register_org_pk, other_org_pk):
        p = make_property(client, admin_h, register_org_pk)
        pk = p["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h, json={
            "new_custodian_organization_pk": other_org_pk, "notes": "moving", "location_description": "New hall"})
        assert r.status_code == 201, r.text
        prev, cur = r.json()["previous"], r.json()["current"]
        assert prev["custodianship_pk"] == p["current_custodianship_pk"]
        assert prev["status"] == "ENDED" and prev["effective_to"] == TODAY and prev["end_reason_code"] == "TRANSFER"
        assert prev["custodian_organization_pk"] == register_org_pk
        assert cur["status"] == "ACTIVE" and cur["custodian_organization_pk"] == other_org_pk and cur["effective_to"] is None
        detail = client.get(f"{BASE}/properties/{pk}", headers=admin_h).json()
        assert detail["status"] == "ACTIVE" and detail["location_description"] == "New hall"
        assert detail["current_custodian_organization_pk"] == other_org_pk

    def test_history_is_preserved_newest_first(self, client, admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, admin_h, register_org_pk)["property_pk"]
        client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h,
                    json={"new_custodian_organization_pk": other_org_pk})
        client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h, json={
            "new_custodian_organization_pk": register_org_pk, "end_reason_code": "DISSOLUTION_VESTING"})
        h = client.get(f"{BASE}/properties/{pk}/custodianships", headers=admin_h).json()
        assert h["total"] == 3
        assert [i["status"] for i in h["items"]].count("ACTIVE") == 1
        ended = [i for i in h["items"] if i["status"] == "ENDED"]
        assert {i["end_reason_code"] for i in ended} == {"TRANSFER", "DISSOLUTION_VESTING"}, "vesting is distinguishable (AP-058/059)"
        assert all(i["effective_to"] for i in ended)

    def test_transfer_validation(self, client, admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, admin_h, register_org_pk)["property_pk"]
        url = f"{BASE}/properties/{pk}/custodianships/transfer"
        assert client.post(url, headers=admin_h, json={"new_custodian_organization_pk": register_org_pk}).status_code == 422
        assert client.post(url, headers=admin_h, json={"new_custodian_organization_pk": FAKE_UUID}).status_code == 422
        assert client.post(url, headers=admin_h, json={"new_custodian_organization_pk": other_org_pk,
                                                       "end_reason_code": "BOGUS"}).status_code == 422
        future = (date.today() + timedelta(days=3)).isoformat()
        assert client.post(url, headers=admin_h, json={"new_custodian_organization_pk": other_org_pk,
                                                       "effective_from": future}).status_code == 422
        assert client.post(url, headers=admin_h, json={"new_custodian_organization_pk": other_org_pk,
                                                       "effective_from": "2000-01-01"}).status_code == 422
        assert client.get(f"{BASE}/properties/{pk}/custodianships", headers=admin_h).json()["total"] == 1, "nothing changed"

    def test_transfer_without_a_current_custodian_is_409(self, client, admin_h, other_org_pk):
        pk = make_property(client, admin_h)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 409

    def test_scoped_admin_needs_scope_over_both_organizations(self, client, sakha_admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=sakha_admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only transfer this property to this organization within your admin scope."
        assert client.get(f"{BASE}/properties/{pk}/custodianships", headers=sakha_admin_h).json()["total"] == 1

    def test_foreign_admin_cannot_transfer_away(self, client, sakha_admin_h, other_admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=other_admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only transfer custody of this property within your admin scope."

    def test_record_leaves_the_old_custodians_scope_after_transfer(self, client, sakha_admin_h, admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h,
                    json={"new_custodian_organization_pk": other_org_pk})
        assert client.get(f"{BASE}/properties/{pk}", headers=sakha_admin_h).status_code == 403

    def test_terminal_record_cannot_change_custody(self, client, admin_h, register_org_pk, other_org_pk):
        pk = make_property(client, admin_h, register_org_pk)["property_pk"]
        transition(client, admin_h, "properties", pk, "DISPOSED")
        r = client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 422 and "AP-046" in r.json()["detail"]

    def test_asset_custody_history(self, client, admin_h, register_org_pk, other_org_pk):
        a = make_asset(client, admin_h, register_org_pk)
        r = client.post(f"{BASE}/assets/{a['asset_pk']}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 201 and r.json()["current"]["asset_pk"] == a["asset_pk"]
        assert r.json()["current"]["property_pk"] is None
        assert client.get(f"{BASE}/assets/{a['asset_pk']}/custodianships", headers=admin_h).json()["total"] == 2
        assert client.get(f"{BASE}/assets/{a['asset_pk']}", headers=admin_h).json()["status"] == "IN_CUSTODY"

    def test_unknown_kind_and_record(self, client, admin_h, register_org_pk):
        assert client.get(f"{BASE}/widgets/{FAKE_UUID}/custodianships", headers=admin_h).status_code == 422
        assert client.get(f"{BASE}/assets/{FAKE_UUID}/custodianships", headers=admin_h).status_code == 404
        assert client.post(f"{BASE}/assets/{FAKE_UUID}/custodianships", headers=admin_h,
                           json={"custodian_organization_pk": register_org_pk}).status_code == 404

    def test_db_enforces_single_active_custodian(self, client, write_conn, admin_h, register_org_pk, other_org_pk, isolated_savepoint):
        import psycopg2
        pk = make_property(client, admin_h, register_org_pk)["property_pk"]
        cur = write_conn.cursor()
        with isolated_savepoint():
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cur.execute(
                    "INSERT INTO nss.custodianship (property_pk, custodian_organization_pk, status, effective_from) "
                    "VALUES (%s, %s, 'ACTIVE', CURRENT_DATE)", (pk, other_org_pk))


# ═══════════════════════════════════════════════════════════════════════
# 5. Statutory records — property only
# ═══════════════════════════════════════════════════════════════════════

class TestStatutoryRecords:

    def test_crud(self, client, sakha_admin_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h, json={
            "obligation_type_code": "LAND_REVENUE", "reference_number": "LR-77", "description": "annual"})
        assert r.status_code == 201, r.text
        rec = r.json()
        assert rec["property_pk"] == pk and rec["obligation_type_code"] == "LAND_REVENUE" and rec["reference_number"] == "LR-77"
        assert client.get(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h).json()["total"] == 1
        r = client.patch(f"{BASE}/statutory-records/{rec['property_statutory_record_pk']}", headers=sakha_admin_h,
                         json={"obligation_type_code": "MUNICIPAL_TAX", "notes": "corrected"})
        assert r.status_code == 200 and r.json()["obligation_type_code"] == "MUNICIPAL_TAX"
        assert client.delete(f"{BASE}/statutory-records/{rec['property_statutory_record_pk']}", headers=sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h).json()["total"] == 0
        assert client.delete(f"{BASE}/statutory-records/{rec['property_statutory_record_pk']}", headers=sakha_admin_h).status_code == 404

    def test_no_payment_fields_exist(self, client, sakha_admin_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h,
                        json={"obligation_type_code": "LAND_REVENUE", "amount": 100, "paid_on": "2026-01-01"})
        assert r.status_code == 201
        assert not {k for k in r.json() if "amount" in k or "paid" in k}, "payment is Finance's (AP-039)"

    def test_assets_have_no_statutory_routes(self, client, admin_h, register_org_pk):
        a = make_asset(client, admin_h, register_org_pk)
        assert client.get(f"{BASE}/assets/{a['asset_pk']}/statutory-records", headers=admin_h).status_code == 404
        assert client.post(f"{BASE}/assets/{a['asset_pk']}/statutory-records", headers=admin_h,
                           json={"obligation_type_code": "LAND_REVENUE"}).status_code == 404

    def test_unknown_obligation_type_and_empty_patch(self, client, sakha_admin_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        assert client.post(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h,
                           json={"obligation_type_code": "NOPE"}).status_code == 422
        rec = client.post(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h,
                          json={"obligation_type_code": "OTHER"}).json()
        assert client.patch(f"{BASE}/statutory-records/{rec['property_statutory_record_pk']}", json={},
                            headers=sakha_admin_h).status_code == 422

    def test_scope(self, client, sakha_admin_h, other_admin_h, viewer_h, register_org_pk):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        rec = client.post(f"{BASE}/properties/{pk}/statutory-records", headers=sakha_admin_h,
                          json={"obligation_type_code": "LAND_RECORD"}).json()
        rid = rec["property_statutory_record_pk"]
        assert client.get(f"{BASE}/properties/{pk}/statutory-records", headers=other_admin_h).status_code == 403
        assert client.post(f"{BASE}/properties/{pk}/statutory-records", headers=other_admin_h,
                           json={"obligation_type_code": "OTHER"}).status_code == 403
        assert client.patch(f"{BASE}/statutory-records/{rid}", json={"notes": "x"}, headers=other_admin_h).status_code == 403
        assert client.delete(f"{BASE}/statutory-records/{rid}", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/properties/{pk}/statutory-records", headers=viewer_h).status_code == 200
        assert client.delete(f"{BASE}/statutory-records/{rid}", headers=viewer_h).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# 6. Maintenance records
# ═══════════════════════════════════════════════════════════════════════

class TestMaintenanceRecords:

    def test_property_and_asset_records(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        a = make_asset(client, sakha_admin_h, register_org_pk)["asset_pk"]
        rp = client.post(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h, json={
            "maintenance_type_code": "REPAIR_MAJOR", "description": "roof", "performed_at": "2026-01-05"})
        ra = client.post(f"{BASE}/assets/{a}/maintenance-records", headers=sakha_admin_h, json={"maintenance_type_code": "UPKEEP"})
        assert rp.status_code == 201 and ra.status_code == 201
        assert rp.json()["property_pk"] == p and rp.json()["asset_pk"] is None and rp.json()["performed_at"] == "2026-01-05"
        assert ra.json()["asset_pk"] == a and ra.json()["property_pk"] is None
        assert client.get(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h).json()["total"] == 1
        assert client.get(f"{BASE}/assets/{a}/maintenance-records", headers=sakha_admin_h).json()["total"] == 1

    def test_recording_maintenance_does_not_change_status(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        client.post(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h, json={"maintenance_type_code": "REPAIR_MINOR"})
        assert client.get(f"{BASE}/properties/{p}", headers=sakha_admin_h).json()["status"] == "ACTIVE"

    @pytest.mark.parametrize("body", [
        {"maintenance_type_code": "NOPE"},
        {"maintenance_type_code": "UPKEEP", "performed_at": "2999-01-01"},
        {},
    ])
    def test_invalid_body_is_422(self, client, sakha_admin_h, register_org_pk, body):
        p = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        assert client.post(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h, json=body).status_code == 422

    def test_patch_and_delete(self, client, sakha_admin_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        rec = client.post(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h,
                          json={"maintenance_type_code": "UPKEEP"}).json()
        rid = rec["maintenance_record_pk"]
        r = client.patch(f"{BASE}/maintenance-records/{rid}", headers=sakha_admin_h,
                         json={"maintenance_type_code": "IMPROVEMENT", "notes": "n"})
        assert r.status_code == 200 and r.json()["maintenance_type_code"] == "IMPROVEMENT" and r.json()["property_pk"] == p
        assert client.patch(f"{BASE}/maintenance-records/{rid}", json={}, headers=sakha_admin_h).status_code == 422
        assert client.delete(f"{BASE}/maintenance-records/{rid}", headers=sakha_admin_h).status_code == 200
        assert client.delete(f"{BASE}/maintenance-records/{rid}", headers=sakha_admin_h).status_code == 404
        assert client.get(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h).json()["total"] == 0

    def test_scope(self, client, sakha_admin_h, other_admin_h, viewer_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        rid = client.post(f"{BASE}/properties/{p}/maintenance-records", headers=sakha_admin_h,
                          json={"maintenance_type_code": "UPKEEP"}).json()["maintenance_record_pk"]
        assert client.get(f"{BASE}/properties/{p}/maintenance-records", headers=other_admin_h).status_code == 403
        assert client.post(f"{BASE}/properties/{p}/maintenance-records", headers=other_admin_h,
                           json={"maintenance_type_code": "UPKEEP"}).status_code == 403
        r = client.patch(f"{BASE}/maintenance-records/{rid}", json={"notes": "x"}, headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only edit a maintenance record of this property within your admin scope."
        assert client.delete(f"{BASE}/maintenance-records/{rid}", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/properties/{p}/maintenance-records", headers=viewer_h).status_code == 200
        assert client.post(f"{BASE}/properties/{p}/maintenance-records", headers=viewer_h,
                           json={"maintenance_type_code": "UPKEEP"}).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# 7. Document links
# ═══════════════════════════════════════════════════════════════════════

class TestDocumentLinks:

    def test_attach_list_detach_reattach(self, client, sakha_admin_h, register_org_pk, document_pks):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        r = client.post(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h, json={
            "document_master_pk": document_pks[0], "relationship_type_code": "TITLE_DEED", "notes": "original"})
        assert r.status_code == 201, r.text
        link = r.json()
        assert link["property_pk"] == pk and link["asset_pk"] is None and link["relationship_type_code"] == "TITLE_DEED"
        assert link["document_master_pk"] == document_pks[0] and link["document_name"].startswith("AP test doc")
        assert client.post(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h,
                           json={"document_master_pk": document_pks[0]}).status_code == 409
        assert client.get(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h).json()["total"] == 1
        assert client.delete(f"{BASE}/properties/{pk}/documents/{link['link_pk']}", headers=sakha_admin_h).status_code == 200
        assert client.delete(f"{BASE}/properties/{pk}/documents/{link['link_pk']}", headers=sakha_admin_h).status_code == 404
        assert client.get(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h).json()["total"] == 0
        assert client.post(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h,
                           json={"document_master_pk": document_pks[0]}).status_code == 201

    def test_asset_link_and_optional_relationship(self, client, sakha_admin_h, register_org_pk, document_pks):
        a = make_asset(client, sakha_admin_h, register_org_pk)["asset_pk"]
        r = client.post(f"{BASE}/assets/{a}/documents", headers=sakha_admin_h, json={"document_master_pk": document_pks[1]})
        assert r.status_code == 201 and r.json()["asset_pk"] == a and r.json()["relationship_type_code"] is None

    def test_validation(self, client, sakha_admin_h, register_org_pk, document_pks):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        assert client.post(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h,
                           json={"document_master_pk": FAKE_UUID}).status_code == 422
        assert client.post(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h, json={
            "document_master_pk": document_pks[0], "relationship_type_code": "NOPE"}).status_code == 422

    def test_scope(self, client, sakha_admin_h, other_admin_h, viewer_h, register_org_pk, document_pks):
        pk = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        link = client.post(f"{BASE}/properties/{pk}/documents", headers=sakha_admin_h,
                           json={"document_master_pk": document_pks[0]}).json()
        assert client.get(f"{BASE}/properties/{pk}/documents", headers=other_admin_h).status_code == 403
        assert client.post(f"{BASE}/properties/{pk}/documents", headers=other_admin_h,
                           json={"document_master_pk": document_pks[1]}).status_code == 403
        assert client.delete(f"{BASE}/properties/{pk}/documents/{link['link_pk']}", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/properties/{pk}/documents", headers=viewer_h).status_code == 200
        assert client.post(f"{BASE}/properties/{pk}/documents", headers=viewer_h,
                           json={"document_master_pk": document_pks[1]}).status_code == 403

    def test_link_belongs_to_its_entity(self, client, sakha_admin_h, register_org_pk, document_pks):
        a = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        b = make_property(client, sakha_admin_h, register_org_pk)["property_pk"]
        link = client.post(f"{BASE}/properties/{a}/documents", headers=sakha_admin_h,
                           json={"document_master_pk": document_pks[0]}).json()
        assert client.delete(f"{BASE}/properties/{b}/documents/{link['link_pk']}", headers=sakha_admin_h).status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 8. RBAC + audit
# ═══════════════════════════════════════════════════════════════════════

class TestRbacAndAudit:

    def test_plain_member_and_anonymous_are_refused(self, client, plain_member_h):
        assert client.get(f"{BASE}/properties", headers=plain_member_h).status_code == 403
        assert client.get(f"{BASE}/assets").status_code == 401

    def test_view_only_role_reads_but_never_writes(self, client, sakha_admin_h, viewer_h, register_org_pk):
        p = make_property(client, sakha_admin_h, register_org_pk)
        assert client.get(f"{BASE}/properties/{p['property_pk']}", headers=viewer_h).status_code == 200
        assert client.get(f"{BASE}/properties", headers=viewer_h).status_code == 200
        assert client.post(f"{BASE}/properties", headers=viewer_h, json={
            "property_name": "X", "property_type_code": "LAND", "custodian_organization_pk": register_org_pk}).status_code == 403
        assert client.patch(f"{BASE}/properties/{p['property_pk']}", json={"notes": "x"}, headers=viewer_h).status_code == 403
        assert client.delete(f"{BASE}/properties/{p['property_pk']}", headers=viewer_h).status_code == 403

    def test_semantic_actions_are_audited(self, client, write_conn, admin_h, register_org_pk, other_org_pk):
        p = make_property(client, admin_h, register_org_pk)
        pk = p["property_pk"]
        client.post(f"{BASE}/properties/{pk}/custodianships/transfer", headers=admin_h,
                    json={"new_custodian_organization_pk": other_org_pk})
        transition(client, admin_h, "properties", pk, "UNDER_MAINTENANCE")
        cur = write_conn.cursor()
        cur.execute("SELECT action FROM nss.system_event_log WHERE module = 'assets_property' AND record_pk = %s", (pk,))
        actions = {r[0] for r in cur.fetchall()}
        assert {"CREATE", "STATUS_CHANGE"} <= actions
        cur.execute("SELECT count(*) FROM nss.system_event_log WHERE module = 'assets_property' AND action = 'TRANSFER' "
                    "AND detail->>'property_pk' = %s", (pk,))
        assert cur.fetchone()[0] == 1

    def test_field_changes_reach_field_change_log(self, client, write_conn, sakha_admin_h, register_org_pk):
        """AP-071: the DB audit trigger records business field changes."""
        p = make_property(client, sakha_admin_h, register_org_pk)
        client.patch(f"{BASE}/properties/{p['property_pk']}", json={"property_name": "Audited rename"}, headers=sakha_admin_h)
        cur = write_conn.cursor()
        cur.execute("SELECT count(*) FROM nss.field_change_log WHERE table_name = 'property' AND record_pk = %s",
                    (p["property_pk"],))
        assert cur.fetchone()[0] >= 1


# ═══════════════════════════════════════════════════════════════════════
# 9. Custodians are physical organizations (owner rule 2026-11-02, GDR-010 §2C)
# ═══════════════════════════════════════════════════════════════════════

_KIND_BODY = {
    "properties": lambda: {"property_name": f"AP type test {uuid4().hex[:6]}", "property_type_code": "LAND"},
    "assets": lambda: {"asset_name": f"AP type test {uuid4().hex[:6]}", "asset_type_code": "EQUIPMENT"},
}


def _assert_physical_only_message(detail: str, type_code: str):
    assert type_code in detail
    assert "physical organizations" in detail
    for name in ("Sakha", "Patha Chakra", "Kendra", "Nilachala Kutira", "Smruti Mandira"):
        assert name in detail


class TestCustodianMustBePhysical:

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    @pytest.mark.parametrize("type_code", INELIGIBLE_CUSTODIAN_TYPES)
    def test_create_with_non_eligible_custodian_is_422(self, client, write_conn, admin_h, kind, type_code):
        org_pk = org_of_type(write_conn, type_code)
        r = client.post(f"{BASE}/{kind}", headers=admin_h,
                        json={**_KIND_BODY[kind](), "custodian_organization_pk": org_pk})
        assert r.status_code == 422, r.text
        _assert_physical_only_message(r.json()["detail"], type_code)

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    @pytest.mark.parametrize("type_code", INELIGIBLE_CUSTODIAN_TYPES)
    def test_assign_non_eligible_custodian_is_422_and_record_stays_registered(
        self, client, write_conn, admin_h, kind, type_code,
    ):
        org_pk = org_of_type(write_conn, type_code)
        rec = (make_property if kind == "properties" else make_asset)(client, admin_h)
        pk = rec["property_pk" if kind == "properties" else "asset_pk"]
        r = client.post(f"{BASE}/{kind}/{pk}/custodianships", headers=admin_h,
                        json={"custodian_organization_pk": org_pk})
        assert r.status_code == 422, r.text
        _assert_physical_only_message(r.json()["detail"], type_code)
        assert client.get(f"{BASE}/{kind}/{pk}", headers=admin_h).json()["status"] == "REGISTERED"
        assert client.get(f"{BASE}/{kind}/{pk}/custodianships", headers=admin_h).json()["items"] == []

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    @pytest.mark.parametrize("type_code", INELIGIBLE_CUSTODIAN_TYPES)
    def test_transfer_to_non_eligible_custodian_is_422_and_custody_unchanged(
        self, client, write_conn, admin_h, register_org_pk, kind, type_code,
    ):
        org_pk = org_of_type(write_conn, type_code)
        rec = (make_property if kind == "properties" else make_asset)(client, admin_h, register_org_pk)
        pk = rec["property_pk" if kind == "properties" else "asset_pk"]
        r = client.post(f"{BASE}/{kind}/{pk}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": org_pk})
        assert r.status_code == 422, r.text
        _assert_physical_only_message(r.json()["detail"], type_code)
        history = client.get(f"{BASE}/{kind}/{pk}/custodianships", headers=admin_h).json()["items"]
        assert len(history) == 1 and history[0]["status"] == "ACTIVE"
        assert history[0]["custodian_organization_pk"] == register_org_pk

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    @pytest.mark.parametrize("type_code", ELIGIBLE_CUSTODIAN_TYPES)
    def test_every_eligible_type_is_accepted_on_create_assign_and_transfer(
        self, client, write_conn, admin_h, register_org_pk, other_org_pk, kind, type_code,
    ):
        org_pk = org_of_type(write_conn, type_code)
        maker = make_property if kind == "properties" else make_asset
        pk_col = "property_pk" if kind == "properties" else "asset_pk"
        created = maker(client, admin_h, org_pk)                      # create-with-custodian
        assert created["current_custodian_organization_pk"] == org_pk
        bare = maker(client, admin_h)                                  # assign first custodian
        r = client.post(f"{BASE}/{kind}/{bare[pk_col]}/custodianships", headers=admin_h,
                        json={"custodian_organization_pk": org_pk})
        assert r.status_code == 201, r.text
        source = register_org_pk if org_pk != register_org_pk else other_org_pk
        moved = maker(client, admin_h, source)                         # transfer into the type
        r = client.post(f"{BASE}/{kind}/{moved[pk_col]}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": org_pk})
        assert r.status_code == 201, r.text

    def test_scope_is_checked_for_eligible_foreign_custodian_even_when_type_is_fine(
        self, client, sakha_admin_h, other_org_pk,
    ):
        r = client.post(f"{BASE}/properties", headers=sakha_admin_h,
                        json={**_KIND_BODY["properties"](), "custodian_organization_pk": other_org_pk})
        assert r.status_code == 403


class TestIncludeSubOrganizations:
    """
    List option include_sub_organizations (with custodian_organization_pk):
    the organization AND its subtree, still intersected with the caller's scope.
    Own isolated tree (fresh Anchalika parent + two fresh Sakha children), never
    the real 173-Sakha Kendra.
    """

    @pytest.fixture
    def tree(self, write_conn):
        from tests.api.test_correspondence import _create_test_organization
        parent = _create_test_organization(
            write_conn, name_prefix="AP sub parent", type_code="ANCHALIKA_SANGHA", parent_pk=None,
            short_code=f"AS{uuid4().hex[:3].upper()}",
        )
        kids = [
            _create_test_organization(
                write_conn, name_prefix=f"AP sub sakha {i}", type_code="SAKHA_SANGHA", parent_pk=parent,
                short_code=f"AK{i}{uuid4().hex[:2].upper()}",
            )
            for i in (1, 2)
        ]
        return {"parent": parent, "kids": kids}

    @pytest.fixture
    def parent_admin_h(self, client, write_conn, tree):
        user = _with_sevi_pk(write_conn, _create_admin_with_scope(
            write_conn, role_code="NSS_ERP_ANCHALIKA_ADMIN", scope_level="ANCHALIKA", organization_pk=tree["parent"]))
        return _login_headers(client, user["sangha_sevi_id"], user["password"])

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_flag_matches_the_whole_subtree(self, client, admin_h, register_org_pk, tree, kind):
        maker = make_property if kind == "properties" else make_asset
        pk_col = "property_pk" if kind == "properties" else "asset_pk"
        a, b = (maker(client, admin_h, k) for k in tree["kids"])
        outsider = maker(client, admin_h, register_org_pk)
        params = {"custodian_organization_pk": tree["parent"], "page_size": 100}
        plain = client.get(f"{BASE}/{kind}", params=params, headers=admin_h).json()
        assert plain["total"] == 0                                    # the grouping itself holds nothing
        sub = client.get(f"{BASE}/{kind}", params={**params, "include_sub_organizations": "true"}, headers=admin_h).json()
        pks = {i[pk_col] for i in sub["items"]}
        assert pks == {a[pk_col], b[pk_col]}
        assert outsider[pk_col] not in pks

    def test_flag_is_ignored_without_a_custodian_filter(self, client, admin_h, register_org_pk):
        rec = make_property(client, admin_h, register_org_pk)
        r = client.get(f"{BASE}/properties", params={"include_sub_organizations": "true", "page_size": 100}, headers=admin_h)
        assert r.status_code == 200
        assert rec["property_pk"] in {i["property_pk"] for i in r.json()["items"]}

    def test_flag_false_is_the_exact_match_default(self, client, admin_h, tree):
        rec = make_property(client, admin_h, tree["kids"][0])
        r = client.get(f"{BASE}/properties", headers=admin_h, params={
            "custodian_organization_pk": tree["kids"][0], "include_sub_organizations": "false"})
        assert rec["property_pk"] in {i["property_pk"] for i in r.json()["items"]}

    def test_scoped_admin_of_the_parent_sees_the_subtree(self, client, admin_h, parent_admin_h, tree):
        rec = make_property(client, admin_h, tree["kids"][1])
        r = client.get(f"{BASE}/properties", headers=parent_admin_h, params={
            "custodian_organization_pk": tree["parent"], "include_sub_organizations": "true", "page_size": 100})
        assert r.status_code == 200
        assert rec["property_pk"] in {i["property_pk"] for i in r.json()["items"]}

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_disposed_records_are_still_found_by_their_last_custodian_subtree(
            self, client, admin_h, parent_admin_h, tree, kind):
        """GDR-010 §2F: the subtree filter matches the LAST custodian of a terminal record."""
        rec = (make_property if kind == "properties" else make_asset)(client, admin_h, tree["kids"][0])
        pk = rec["property_pk" if kind == "properties" else "asset_pk"]
        assert transition(client, admin_h, kind, pk, "DISPOSED" if kind == "properties" else "RETIRED").status_code == 200
        for h in (admin_h, parent_admin_h):
            r = client.get(f"{BASE}/{kind}", headers=h, params={
                "custodian_organization_pk": tree["parent"], "include_sub_organizations": "true", "page_size": 100})
            assert r.status_code == 200
            hit = [i for i in r.json()["items"] if i["property_pk" if kind == "properties" else "asset_pk"] == pk]
            assert len(hit) == 1 and hit[0]["custodian_is_last"] is True
            assert hit[0]["current_custodian_organization_pk"] == tree["kids"][0]
        assert client.get(f"{BASE}/{kind}/{pk}", headers=parent_admin_h).status_code == 200

    def test_flag_never_widens_beyond_the_callers_scope(self, client, admin_h, sakha_admin_h, register_org_pk, tree):
        """A Sakha-scoped admin may not use a parent they do not cover (403); the flag leaks nothing."""
        make_property(client, admin_h, tree["kids"][0])
        r = client.get(f"{BASE}/properties", headers=sakha_admin_h, params={
            "custodian_organization_pk": tree["parent"], "include_sub_organizations": "true"})
        assert r.status_code == 403
        # and on its own subtree it only ever returns what its scope covers
        own = client.get(f"{BASE}/properties", headers=sakha_admin_h, params={
            "custodian_organization_pk": register_org_pk, "include_sub_organizations": "true", "page_size": 100})
        assert own.status_code == 200
        assert all(i["current_custodian_organization_pk"] == register_org_pk for i in own.json()["items"])


    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_anchalika_admin_is_view_only(self, client, admin_h, parent_admin_h, tree, kind):
        """Owner decision 2026-11-02 (GDR-010): Anchalika / Zilla admins hold ASSET_VIEW but not ASSET_MANAGE."""
        rec = (make_property if kind == "properties" else make_asset)(client, admin_h, tree["kids"][0])
        pk = rec["property_pk" if kind == "properties" else "asset_pk"]
        assert client.get(f"{BASE}/{kind}/{pk}", headers=parent_admin_h).status_code == 200
        assert client.post(f"{BASE}/{kind}", headers=parent_admin_h, json={
            **_KIND_BODY[kind](), "custodian_organization_pk": tree["kids"][0]}).status_code == 403
        assert client.patch(f"{BASE}/{kind}/{pk}", headers=parent_admin_h, json={"notes": "x"}).status_code == 403
        assert transition(client, parent_admin_h, kind, pk, "UNDER_MAINTENANCE").status_code == 403
        assert client.post(f"{BASE}/{kind}/{pk}/custodianships/transfer", headers=parent_admin_h, json={
            "new_custodian_organization_pk": tree["kids"][1]}).status_code == 403
        assert client.delete(f"{BASE}/{kind}/{pk}", headers=parent_admin_h).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# 10. Belongs to (GDR-010 item 4)
# ═══════════════════════════════════════════════════════════════════════

_BT_PK = {"properties": "property_pk", "assets": "asset_pk"}


class TestBelongsTo:
    """
    Optional ``belongs_to_organization_pk``: attribution to an organization that is
    NOT the physical custodian (e.g. custodian = Kendra, belongs to = Mahila Sangha).
    Informational only: any ACTIVE organization type is accepted, null clears, and
    it never changes authorization, visibility or the custodian rule.
    """

    @pytest.fixture
    def wing_org(self, write_conn):
        """A non-custodian-eligible organization (Mahila Sangha) - the typical 'belongs to'."""
        return org_of_type(write_conn, "MAHILA_SANGHA")

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_default_is_unset(self, client, sakha_admin_h, register_org_pk, kind):
        rec = (make_property if kind == "properties" else make_asset)(client, sakha_admin_h, register_org_pk)
        assert rec["belongs_to_organization_pk"] is None and rec["belongs_to_organization_name"] is None

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_create_with_belongs_to_returns_pk_and_name(self, client, sakha_admin_h, register_org_pk, wing_org, kind):
        maker = make_property if kind == "properties" else make_asset
        rec = maker(client, sakha_admin_h, register_org_pk, belongs_to_organization_pk=wing_org)
        assert rec["belongs_to_organization_pk"] == wing_org
        assert rec["belongs_to_organization_name"]
        assert rec["current_custodian_organization_pk"] == register_org_pk      # custodian is a separate fact
        got = client.get(f"{BASE}/{kind}/{rec[_BT_PK[kind]]}", headers=sakha_admin_h).json()
        assert got["belongs_to_organization_pk"] == wing_org

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_patch_sets_changes_and_clears_with_null(self, client, sakha_admin_h, register_org_pk, other_org_pk, wing_org, kind):
        rec = (make_property if kind == "properties" else make_asset)(client, sakha_admin_h, register_org_pk)
        url = f"{BASE}/{kind}/{rec[_BT_PK[kind]]}"
        r = client.patch(url, headers=sakha_admin_h, json={"belongs_to_organization_pk": wing_org})
        assert r.status_code == 200 and r.json()["belongs_to_organization_pk"] == wing_org
        # an organization OUTSIDE the admin's scope is acceptable: it is attribution, not authority
        r = client.patch(url, headers=sakha_admin_h, json={"belongs_to_organization_pk": other_org_pk})
        assert r.status_code == 200 and r.json()["belongs_to_organization_pk"] == other_org_pk
        # omitting the field leaves it alone
        r = client.patch(url, headers=sakha_admin_h, json={"notes": "n"})
        assert r.json()["belongs_to_organization_pk"] == other_org_pk
        r = client.patch(url, headers=sakha_admin_h, json={"belongs_to_organization_pk": None})
        assert r.status_code == 200
        assert r.json()["belongs_to_organization_pk"] is None and r.json()["belongs_to_organization_name"] is None

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_unknown_or_inactive_organization_is_422(self, client, write_conn, sakha_admin_h, register_org_pk, kind):
        maker_body = _KIND_BODY[kind]()
        r = client.post(f"{BASE}/{kind}", headers=sakha_admin_h, json={
            **maker_body, "custodian_organization_pk": register_org_pk, "belongs_to_organization_pk": FAKE_UUID})
        assert r.status_code == 422 and "Belongs-to organization not found" in r.json()["detail"]
        from tests.api.test_correspondence import _create_test_organization
        dead = _create_test_organization(
            write_conn, name_prefix="AP dead belongs-to", type_code="SEVAK_SANGHA", parent_pk=None,
            short_code=f"B{uuid4().hex[:4].upper()}",
        )
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.organization SET is_active = FALSE, deleted_at = NOW() WHERE organization_pk = %s", (dead,))
        r = client.post(f"{BASE}/{kind}", headers=sakha_admin_h, json={
            **maker_body, "custodian_organization_pk": register_org_pk, "belongs_to_organization_pk": dead})
        assert r.status_code == 422
        rec = (make_property if kind == "properties" else make_asset)(client, sakha_admin_h, register_org_pk)
        r = client.patch(f"{BASE}/{kind}/{rec[_BT_PK[kind]]}", headers=sakha_admin_h, json={"belongs_to_organization_pk": dead})
        assert r.status_code == 422

    def test_malformed_pk_is_422(self, client, sakha_admin_h, register_org_pk):
        r = client.post(f"{BASE}/properties", headers=sakha_admin_h, json={
            **_KIND_BODY["properties"](), "custodian_organization_pk": register_org_pk, "belongs_to_organization_pk": "nope"})
        assert r.status_code == 422

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_any_organization_type_is_accepted(self, client, write_conn, sakha_admin_h, register_org_pk, kind):
        for type_code in INELIGIBLE_CUSTODIAN_TYPES:           # never valid as custodian ...
            if type_code == "ADVISORY_BOARD":
                continue                                        # singleton; covered by the others
            org = org_of_type(write_conn, type_code)
            rec = (make_property if kind == "properties" else make_asset)(
                client, sakha_admin_h, register_org_pk, belongs_to_organization_pk=org)  # ... but fine as belongs-to
            assert rec["belongs_to_organization_pk"] == org, type_code

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_list_filter_and_no_scope_widening(self, client, admin_h, sakha_admin_h, other_admin_h, register_org_pk, other_org_pk, wing_org, kind):
        maker = make_property if kind == "properties" else make_asset
        pk_col = _BT_PK[kind]
        mine = maker(client, admin_h, register_org_pk, belongs_to_organization_pk=wing_org)
        foreign = maker(client, admin_h, other_org_pk, belongs_to_organization_pk=wing_org)
        plain = maker(client, admin_h, register_org_pk)
        params = {"belongs_to_organization_pk": wing_org, "page_size": 100}
        # global admin: both attributed records, not the unattributed one
        seen = {i[pk_col] for i in client.get(f"{BASE}/{kind}", params=params, headers=admin_h).json()["items"]}
        assert {mine[pk_col], foreign[pk_col]} <= seen and plain[pk_col] not in seen
        # scoped admin: the filter is ANDed with the custodian scope, so the foreign record stays hidden
        seen = {i[pk_col] for i in client.get(f"{BASE}/{kind}", params=params, headers=sakha_admin_h).json()["items"]}
        assert mine[pk_col] in seen and foreign[pk_col] not in seen
        seen = {i[pk_col] for i in client.get(f"{BASE}/{kind}", params=params, headers=other_admin_h).json()["items"]}
        assert foreign[pk_col] in seen and mine[pk_col] not in seen

    def test_belongs_to_never_grants_access_to_the_attributed_organization(self, client, write_conn, admin_h, other_admin_h, register_org_pk, other_org_pk):
        """A record held by Sakha S1 that 'belongs to' Sakha S2 is still invisible/untouchable for S2's admin."""
        rec = make_property(client, admin_h, register_org_pk, belongs_to_organization_pk=other_org_pk)
        pk = rec["property_pk"]
        assert client.get(f"{BASE}/properties/{pk}", headers=other_admin_h).status_code == 403
        assert client.patch(f"{BASE}/properties/{pk}", headers=other_admin_h, json={"notes": "x"}).status_code == 403
        assert client.patch(f"{BASE}/properties/{pk}", headers=other_admin_h,
                            json={"belongs_to_organization_pk": None}).status_code == 403
        listed = client.get(f"{BASE}/properties", params={"page_size": 100}, headers=other_admin_h).json()["items"]
        assert pk not in {i["property_pk"] for i in listed}

    @pytest.mark.parametrize("kind", ["properties", "assets"])
    def test_custodian_rule_is_unaffected(self, client, write_conn, admin_h, register_org_pk, wing_org, kind):
        """belongs-to may be a wing org, but a wing org is still refused as CUSTODIAN."""
        r = client.post(f"{BASE}/{kind}", headers=admin_h, json={
            **_KIND_BODY[kind](), "custodian_organization_pk": wing_org, "belongs_to_organization_pk": wing_org})
        assert r.status_code == 422
        _assert_physical_only_message(r.json()["detail"], "MAHILA_SANGHA")
        # and belongs-to survives custody transfers untouched
        rec = (make_property if kind == "properties" else make_asset)(
            client, admin_h, register_org_pk, belongs_to_organization_pk=wing_org)
        kendra = org_of_type(write_conn, "KENDRA")
        t = client.post(f"{BASE}/{kind}/{rec[_BT_PK[kind]]}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": kendra})
        assert t.status_code == 201, t.text
        got = client.get(f"{BASE}/{kind}/{rec[_BT_PK[kind]]}", headers=admin_h).json()
        assert got["current_custodian_organization_pk"] == kendra and got["belongs_to_organization_pk"] == wing_org

    def test_change_is_audited(self, client, write_conn, sakha_admin_h, register_org_pk, wing_org):
        rec = make_asset(client, sakha_admin_h, register_org_pk)
        client.patch(f"{BASE}/assets/{rec['asset_pk']}", headers=sakha_admin_h, json={"belongs_to_organization_pk": wing_org})
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM nss.field_change_log
                WHERE table_name = 'asset' AND record_pk = %s AND field_name = 'belongs_to_organization_pk'
                """,
                (rec["asset_pk"],),
            )
            assert cur.fetchone()[0] >= 1


# ═══════════════════════════════════════════════════════════════════════
# 11. Disposal / retirement closes custody (GDR-010 §2F, owner decision 2026-11-03)
# ═══════════════════════════════════════════════════════════════════════

_TERMINAL = {"properties": "DISPOSED", "assets": "RETIRED"}
_MAKER = {"properties": make_property, "assets": make_asset}


def _pk_of(kind, rec):
    return rec[_BT_PK[kind]]


def _custody_rows(write_conn, kind, pk):
    cur = write_conn.cursor()
    cur.execute(
        f"""
        SELECT c.status, c.effective_to, er.value_code, c.custodian_organization_pk::text
        FROM nss.custodianship c
        LEFT JOIN nss.master_data er ON er.master_data_pk = c.end_reason_master_data_pk
        WHERE c.{_BT_PK[kind]} = %s ORDER BY c.effective_from, c.created_at
        """,
        (pk,),
    )
    return cur.fetchall()


@pytest.mark.parametrize("kind", ["properties", "assets"])
class TestTerminalTransitionClosesCustody:

    def test_active_record_reports_a_live_custodian(self, client, sakha_admin_h, register_org_pk, kind):
        rec = _MAKER[kind](client, sakha_admin_h, register_org_pk)
        assert rec["custodian_is_last"] is False and rec["custodian_ended_at"] is None

    def test_terminal_transition_ends_custody_in_the_same_request(
            self, client, write_conn, sakha_admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        r = transition(client, sakha_admin_h, kind, pk, _TERMINAL[kind], "Governing Body resolution 9")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == _TERMINAL[kind]
        # last custodian still on the record, flagged
        assert body["current_custodian_organization_pk"] == register_org_pk
        assert body["current_custodian_organization_name"]
        assert body["custodian_is_last"] is True and body["custodian_ended_at"] == TODAY
        assert body["current_custodianship_pk"] is not None
        # exactly one row, ENDED with the terminal end reason; nothing stays ACTIVE
        assert _custody_rows(write_conn, kind, pk) == [("ENDED", date.today(), _TERMINAL[kind], register_org_pk)]
        # the audit event names the custodianship that was ended
        cur = write_conn.cursor()
        cur.execute(
            "SELECT detail->>'ended_custodianship_pk' FROM nss.system_event_log WHERE record_pk = %s "
            "AND action = 'STATUS_CHANGE' AND detail->>'to' = %s", (pk, _TERMINAL[kind]))
        assert cur.fetchone()[0] == body["current_custodianship_pk"]

    def test_history_endpoint_keeps_the_ended_row_with_reason(self, client, sakha_admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        transition(client, sakha_admin_h, kind, pk, _TERMINAL[kind])
        items = client.get(f"{BASE}/{kind}/{pk}/custodianships", headers=sakha_admin_h).json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "ENDED" and items[0]["end_reason_code"] == _TERMINAL[kind]
        assert items[0]["effective_to"] == TODAY

    def test_visibility_and_scope_are_unchanged_for_the_same_admins(
            self, client, sakha_admin_h, other_admin_h, admin_h, viewer_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        transition(client, sakha_admin_h, kind, pk, _TERMINAL[kind])
        for h in (sakha_admin_h, admin_h, viewer_h):
            assert client.get(f"{BASE}/{kind}/{pk}", headers=h).status_code == 200
            assert client.get(f"{BASE}/{kind}/{pk}/custodianships", headers=h).status_code == 200
            assert client.get(f"{BASE}/{kind}/{pk}/maintenance-records", headers=h).status_code == 200
            assert client.get(f"{BASE}/{kind}/{pk}/documents", headers=h).status_code == 200
        # a foreign admin is refused exactly as before; the record is not 'custodian-less / NSS-wide only'
        assert client.get(f"{BASE}/{kind}/{pk}", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/{kind}/{pk}/custodianships", headers=other_admin_h).status_code == 403
        assert client.patch(f"{BASE}/{kind}/{pk}", headers=other_admin_h, json={"notes": "x"}).status_code == 403
        assert client.patch(f"{BASE}/{kind}/{pk}", headers=sakha_admin_h, json={"notes": "still editable"}).status_code == 200
        # the viewer still cannot write
        assert client.patch(f"{BASE}/{kind}/{pk}", headers=viewer_h, json={"notes": "x"}).status_code == 403

    def test_list_and_filters_find_the_terminal_record_by_its_last_custodian(
            self, client, sakha_admin_h, other_admin_h, admin_h, register_org_pk, other_org_pk, kind):
        tag = uuid4().hex[:8]
        name_key = "property_name" if kind == "properties" else "asset_name"
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk, **{name_key: f"Gone {tag}"}))
        transition(client, sakha_admin_h, kind, pk, _TERMINAL[kind])
        pk_col = _BT_PK[kind]

        def ids(h, **params):
            r = client.get(f"{BASE}/{kind}", headers=h, params={"q": tag, "page_size": 100, **params})
            assert r.status_code == 200, r.text
            return {i[pk_col] for i in r.json()["items"]}

        assert ids(sakha_admin_h) == {pk}
        assert ids(sakha_admin_h, status=_TERMINAL[kind]) == {pk}
        assert ids(sakha_admin_h, custodian_organization_pk=register_org_pk) == {pk}
        assert ids(sakha_admin_h, custodian_organization_pk=register_org_pk, include_sub_organizations="true") == {pk}
        assert ids(admin_h, custodian_organization_pk=register_org_pk) == {pk}
        assert ids(admin_h, custodian_organization_pk=other_org_pk) == set()
        # a foreign admin never sees it, and may not even filter on the organization
        assert ids(other_admin_h) == set()
        assert client.get(f"{BASE}/{kind}", headers=other_admin_h,
                          params={"custodian_organization_pk": register_org_pk}).status_code == 403

    def test_transfer_after_terminal_is_refused_and_assign_too(
            self, client, write_conn, admin_h, register_org_pk, other_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, admin_h, register_org_pk))
        transition(client, admin_h, kind, pk, _TERMINAL[kind])
        rule = "AP-046" if kind == "properties" else "AP-047"
        r = client.post(f"{BASE}/{kind}/{pk}/custodianships/transfer", headers=admin_h,
                        json={"new_custodian_organization_pk": other_org_pk})
        assert r.status_code == 422 and rule in r.json()["detail"]
        r = client.post(f"{BASE}/{kind}/{pk}/custodianships", headers=admin_h,
                        json={"custodian_organization_pk": other_org_pk})
        assert r.status_code == 422 and rule in r.json()["detail"]
        assert [row[0] for row in _custody_rows(write_conn, kind, pk)] == ["ENDED"]

    def test_second_terminal_transition_is_refused(self, client, admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, admin_h, register_org_pk))
        transition(client, admin_h, kind, pk, _TERMINAL[kind])
        assert transition(client, admin_h, kind, pk, _TERMINAL[kind]).status_code == 422

    def test_effective_custodian_is_the_most_recent_after_a_transfer(
            self, client, write_conn, sakha_admin_h, other_admin_h, admin_h, register_org_pk, other_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, admin_h, register_org_pk))
        assert client.post(f"{BASE}/{kind}/{pk}/custodianships/transfer", headers=admin_h,
                           json={"new_custodian_organization_pk": other_org_pk}).status_code == 201
        body = transition(client, admin_h, kind, pk, _TERMINAL[kind]).json()
        assert body["current_custodian_organization_pk"] == other_org_pk and body["custodian_is_last"] is True
        rows = _custody_rows(write_conn, kind, pk)
        assert [r[0] for r in rows] == ["ENDED", "ENDED"]
        assert {r[2] for r in rows} == {"TRANSFER", _TERMINAL[kind]}
        # scope follows the LAST custodian, not the first
        assert client.get(f"{BASE}/{kind}/{pk}", headers=other_admin_h).status_code == 200
        assert client.get(f"{BASE}/{kind}/{pk}", headers=sakha_admin_h).status_code == 403

    def test_terminal_end_reasons_are_reserved_for_the_lifecycle_event(
            self, client, write_conn, admin_h, register_org_pk, other_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, admin_h, register_org_pk))
        r = client.post(f"{BASE}/{kind}/{pk}/custodianships/transfer", headers=admin_h, json={
            "new_custodian_organization_pk": other_org_pk, "end_reason_code": _TERMINAL[kind]})
        assert r.status_code == 422 and "reserved" in r.json()["detail"]
        assert [row[0] for row in _custody_rows(write_conn, kind, pk)] == ["ACTIVE"]

    def test_non_terminal_transitions_keep_custody_active(self, client, write_conn, admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, admin_h, register_org_pk))
        transition(client, admin_h, kind, pk, "UNDER_MAINTENANCE")
        assert [row[0] for row in _custody_rows(write_conn, kind, pk)] == ["ACTIVE"]

    def test_terminal_record_can_be_archived_by_its_scoped_admin(
            self, client, sakha_admin_h, other_admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        transition(client, sakha_admin_h, kind, pk, _TERMINAL[kind])
        assert client.delete(f"{BASE}/{kind}/{pk}", headers=other_admin_h).status_code == 403
        assert client.delete(f"{BASE}/{kind}/{pk}", headers=sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/{kind}/{pk}", headers=sakha_admin_h).status_code == 404

    def test_terminal_end_reason_values_are_master_data(self, client, admin_h, kind):
        r = client.get("/api/v1/foundation/master-data", params={"category_code": "CUSTODIANSHIP_END_REASON"}, headers=admin_h)
        assert r.status_code == 200
        codes = {i["value_code"] for i in r.json()}
        assert {"TRANSFER", "DISSOLUTION_VESTING", "ORGANIZATIONAL_CHANGE", "OTHER", "DISPOSED", "RETIRED"} <= codes


# ═══════════════════════════════════════════════════════════════════════
# 12. Acquisition method (GDR-010 §2E, owner decision 2026-11-03)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kind", ["properties", "assets"])
class TestAcquisitionMethod:

    def test_default_is_unset(self, client, sakha_admin_h, register_org_pk, kind):
        rec = _MAKER[kind](client, sakha_admin_h, register_org_pk)
        assert rec["acquisition_method_code"] is None and rec["acquisition_method_name"] is None

    def test_create_with_method_returns_code_and_name(self, client, sakha_admin_h, register_org_pk, kind):
        rec = _MAKER[kind](client, sakha_admin_h, register_org_pk, acquisition_method_code="DONATION")
        assert rec["acquisition_method_code"] == "DONATION" and rec["acquisition_method_name"] == "Donation"
        again = client.get(f"{BASE}/{kind}/{_pk_of(kind, rec)}", headers=sakha_admin_h).json()
        assert again["acquisition_method_code"] == "DONATION"

    def test_patch_sets_changes_and_clears_with_null(self, client, sakha_admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        url = f"{BASE}/{kind}/{pk}"
        assert client.patch(url, json={"acquisition_method_code": "PURCHASE"}, headers=sakha_admin_h).json()["acquisition_method_code"] == "PURCHASE"
        assert client.patch(url, json={"acquisition_method_code": "BEQUEST"}, headers=sakha_admin_h).json()["acquisition_method_code"] == "BEQUEST"
        cleared = client.patch(url, json={"acquisition_method_code": None}, headers=sakha_admin_h).json()
        assert cleared["acquisition_method_code"] is None and cleared["acquisition_method_name"] is None
        # an unrelated PATCH leaves it alone
        client.patch(url, json={"acquisition_method_code": "GIFT"}, headers=sakha_admin_h)
        assert client.patch(url, json={"notes": "n"}, headers=sakha_admin_h).json()["acquisition_method_code"] == "GIFT"

    def test_unknown_code_is_422_on_create_and_patch(self, client, sakha_admin_h, register_org_pk, kind):
        body = {**_KIND_BODY[kind](), "custodian_organization_pk": register_org_pk, "acquisition_method_code": "NOPE"}
        r = client.post(f"{BASE}/{kind}", json=body, headers=sakha_admin_h)
        assert r.status_code == 422 and r.json()["detail"] == "Unknown ACQUISITION_METHOD value 'NOPE'."
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        r = client.patch(f"{BASE}/{kind}/{pk}", json={"acquisition_method_code": "NOPE"}, headers=sakha_admin_h)
        assert r.status_code == 422

    def test_a_value_of_another_category_is_not_accepted(self, client, sakha_admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        assert client.patch(f"{BASE}/{kind}/{pk}", json={"acquisition_method_code": "LAND"},
                            headers=sakha_admin_h).status_code == 422

    def test_every_seeded_method_is_accepted(self, client, admin_h, kind):
        for code in ("PURCHASE", "DONATION", "GIFT", "BEQUEST", "TRANSFER_IN", "CONSTRUCTION", "OTHER"):
            assert _MAKER[kind](client, admin_h, acquisition_method_code=code)["acquisition_method_code"] == code

    def test_list_filter(self, client, sakha_admin_h, register_org_pk, kind):
        tag = uuid4().hex[:8]
        name_key = "property_name" if kind == "properties" else "asset_name"
        a = _MAKER[kind](client, sakha_admin_h, register_org_pk, acquisition_method_code="PURCHASE", **{name_key: f"Acq {tag} A"})
        _MAKER[kind](client, sakha_admin_h, register_org_pk, acquisition_method_code="GIFT", **{name_key: f"Acq {tag} B"})
        _MAKER[kind](client, sakha_admin_h, register_org_pk, **{name_key: f"Acq {tag} C"})
        r = client.get(f"{BASE}/{kind}", headers=sakha_admin_h, params={"q": tag, "acquisition_method_code": "PURCHASE"}).json()
        assert [i[_BT_PK[kind]] for i in r["items"]] == [_pk_of(kind, a)]
        assert client.get(f"{BASE}/{kind}", headers=sakha_admin_h, params={"q": tag}).json()["total"] == 3
        assert client.get(f"{BASE}/{kind}", headers=sakha_admin_h,
                          params={"q": tag, "acquisition_method_code": "BEQUEST"}).json()["total"] == 0

    def test_it_never_widens_scope(self, client, sakha_admin_h, other_admin_h, register_org_pk, kind):
        rec = _MAKER[kind](client, sakha_admin_h, register_org_pk, acquisition_method_code="PURCHASE")
        r = client.get(f"{BASE}/{kind}", headers=other_admin_h, params={"acquisition_method_code": "PURCHASE", "page_size": 100})
        assert r.status_code == 200 and _pk_of(kind, rec) not in {i[_BT_PK[kind]] for i in r.json()["items"]}
        assert client.patch(f"{BASE}/{kind}/{_pk_of(kind, rec)}", json={"acquisition_method_code": "GIFT"},
                            headers=other_admin_h).status_code == 403

    def test_view_only_role_cannot_set_it(self, client, sakha_admin_h, viewer_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        assert client.patch(f"{BASE}/{kind}/{pk}", json={"acquisition_method_code": "GIFT"}, headers=viewer_h).status_code == 403

    def test_change_is_audited(self, client, write_conn, sakha_admin_h, register_org_pk, kind):
        pk = _pk_of(kind, _MAKER[kind](client, sakha_admin_h, register_org_pk))
        client.patch(f"{BASE}/{kind}/{pk}", json={"acquisition_method_code": "GIFT"}, headers=sakha_admin_h)
        cur = write_conn.cursor()
        cur.execute(
            "SELECT 1 FROM nss.field_change_log WHERE table_name = %s AND record_pk = %s "
            "AND field_name = 'acquisition_method_master_data_pk'",
            (_BT_PK[kind].removesuffix("_pk"), pk))
        assert cur.fetchone() is not None
