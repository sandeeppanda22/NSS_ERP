"""
Finance customization API (api/routers/finance_setup.py): per-Sangha finance heads (with Kendra templates) and receiving
accounts, and how the transaction rules follow a head instead of a fixed category list.

Real integration tests (nothing mocked): they need a bootstrapped DB with Phase 11i and the Finance patches (the 12 Kendra
head templates, PAYMENT_METHOD, the FINANCE_* permissions). Everything rolls back with the module SAVEPOINT.
"""

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    FAKE_UUID,
    adopt_templates,
    admin_h,
    admin_user,
    head_pk,
    kendra_admin,
    kendra_h,
    make_account,
    make_fund,
    make_head,
    make_scope,
    make_txn,
    make_world,
    make_year,
    mock_gateway,
    move,
    new_code,
    other_admin,
    other_admin_h,
    other_org_pk,
    plain_member,
    plain_member_h,
    post_txn,
    raw_move,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    txn_body,
    upi_world,
    viewer_h,
    viewer_user,
)

TEMPLATE_CODES = {
    "MEMBERSHIP_SUBSCRIPTION", "PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND", "DONATION_GENERAL",
    "DONATION_SPECIFIC_PURPOSE", "GRANT", "PUBLICATION_INCOME", "PROPERTY_INCOME", "MISCELLANEOUS_INCOME",
    "EXPENSE_GENERAL", "EXPENSE_RESTRICTED",
}


def heads_of(client, headers, **params):
    r = client.get(f"{BASE}/heads", params={"page_size": 200, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════
# Kendra templates + adoption
# ═══════════════════════════════════════════════════════════════════════

class TestTemplates:
    def test_the_twelve_kendra_templates_are_listed(self, client, admin_h):
        data = heads_of(client, admin_h, templates_only="true")
        got = {h["head_code"] for h in data["items"] if h["is_template"]}
        assert TEMPLATE_CODES <= got
        assert all(h["organization_pk"] is None and not h["allow_upi"] for h in data["items"])

    def test_adoption_copies_the_templates_into_a_sangha(self, client, admin_h, register_org_pk):
        r = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(register_org_pk)}, headers=admin_h)
        assert r.status_code == 200, r.text
        body = r.json()
        mine = {h["head_code"]: h for h in heads_of(client, admin_h, organization_pk=str(register_org_pk))["items"]}
        assert TEMPLATE_CODES <= set(mine)
        assert body["created"] + body["skipped"] >= len(TEMPLATE_CODES)
        pranami = mine["PRANAMI_ANNUAL"]
        assert pranami["is_pranami"] and not pranami["is_template"] and pranami["template_head_pk"]
        assert pranami["organization_pk"] == str(register_org_pk)
        assert mine["DONATION_SPECIFIC_PURPOSE"]["is_restricted"] and mine["PRANAMI_SINKING_FUND"]["required_fund_type"] == "SINKING_FUND"

    def test_adoption_never_copies_upi_settings(self, client, admin_h, register_org_pk):
        adopt_templates(client, admin_h, register_org_pk)
        assert not any(h["allow_upi"] or h["collection_account_pk"] for h in heads_of(client, admin_h, organization_pk=str(register_org_pk))["items"])

    def test_adoption_is_repeatable_and_skips_what_the_sangha_already_has(self, client, admin_h, other_org_pk):
        first = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(other_org_pk)}, headers=admin_h).json()
        again = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(other_org_pk)}, headers=admin_h).json()
        assert again["created"] == 0 and again["skipped"] >= first["created"]

    def test_a_chosen_subset_can_be_adopted(self, client, admin_h, write_conn, sakha_pks):
        cur = write_conn.cursor()                                  # an organization no other test adopts templates into
        cur.execute("SELECT organization_pk FROM nss.organization WHERE is_active = TRUE AND organization_pk <> ALL(%s::uuid[]) "
                    "AND organization_pk NOT IN (SELECT organization_pk FROM nss.finance_head WHERE organization_pk IS NOT NULL) "
                    "ORDER BY organization_pk LIMIT 1", (list(sakha_pks),))
        row = cur.fetchone()
        if row is None:
            pytest.skip("no spare organization")
        fresh = str(row[0])
        tmpl = {h["head_code"]: h["finance_head_pk"] for h in heads_of(client, admin_h, templates_only="true")["items"]}
        r = client.post(f"{BASE}/heads/adopt-templates", headers=admin_h,
                        json={"organization_pk": str(fresh), "template_pks": [tmpl["GRANT"], tmpl["PRANAMI_ANNUAL"]]})
        assert r.status_code == 200 and r.json()["created"] == 2 and r.json()["skipped"] == 0
        assert {h["head_code"] for h in heads_of(client, admin_h, organization_pk=str(fresh))["items"]} == {"GRANT", "PRANAMI_ANNUAL"}

    def test_unknown_template_pk_is_422(self, client, admin_h, register_org_pk):
        r = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(register_org_pk), "template_pks": [FAKE_UUID]}, headers=admin_h)
        assert r.status_code == 422

    def test_a_sangha_admin_cannot_adopt_into_a_foreign_sangha(self, client, kendra_h, other_admin_h, register_org_pk):
        # other_admin is a MANAGE-only admin of a different Sakha: no APPROVE, and no scope over this Sangha
        r = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(register_org_pk)}, headers=other_admin_h)
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Creating and editing heads
# ═══════════════════════════════════════════════════════════════════════

class TestHeads:
    def test_create_a_custom_head(self, client, admin_h, register_org_pk):
        h = make_head(client, admin_h, register_org_pk, head_name="Festival donation", description="Janmautsaba donations", display_order=5)
        assert h["status"] == "ACTIVE" and not h["is_template"] and h["organization_pk"] == str(register_org_pk)
        assert h["direction"] == "INCOME" and h["transaction_count"] == 0 and h["display_order"] == 5

    def test_a_lowercase_code_is_normalised_to_upper_case(self, client, admin_h, register_org_pk):
        code = new_code("low").lower()
        h = make_head(client, admin_h, register_org_pk, head_code=code)
        assert h["head_code"] == code.upper()

    @pytest.mark.parametrize("code", ["1ABC", "A", "HAS SPACE", "A-B", "X" * 51, "ÉCOLE", "ABC DEF", "A.B"])
    def test_code_must_be_upper_snake(self, client, admin_h, register_org_pk, code):
        r = client.post(f"{BASE}/heads", json={"organization_pk": str(register_org_pk), "head_code": code, "head_name": "x", "direction": "INCOME"},
                        headers=admin_h)
        assert r.status_code == 422

    def test_direction_must_be_known(self, client, admin_h, register_org_pk):
        r = client.post(f"{BASE}/heads", json={"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "SIDEWAYS"},
                        headers=admin_h)
        assert r.status_code == 422

    def test_duplicate_code_in_a_sangha_is_409_but_two_sanghas_may_share_one(self, client, admin_h, register_org_pk, other_org_pk):
        code = new_code("DUP")
        make_head(client, admin_h, register_org_pk, head_code=code)
        again = client.post(f"{BASE}/heads", json={"organization_pk": str(register_org_pk), "head_code": code, "head_name": "x", "direction": "INCOME"}, headers=admin_h)
        assert again.status_code == 409
        make_head(client, admin_h, other_org_pk, head_code=code)            # another Sangha: fine

    def test_a_restricted_head_must_say_what_it_is_restricted_to(self, client, admin_h, register_org_pk):
        body = {"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "INCOME", "is_restricted": True}
        assert client.post(f"{BASE}/heads", json=body, headers=admin_h).status_code == 422
        body.update(head_code=new_code(), restriction_purpose="Temple repair")
        assert client.post(f"{BASE}/heads", json=body, headers=admin_h).status_code == 201

    @pytest.mark.parametrize("flags", [{"is_pranami": True}, {"allow_upi": True}])
    def test_pranami_and_upi_are_income_only(self, client, admin_h, register_org_pk, flags):
        r = client.post(f"{BASE}/heads", headers=admin_h, json={
            "organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "EXPENSE", **flags})
        assert r.status_code == 422

    def test_unknown_required_fund_type_is_422(self, client, admin_h, register_org_pk):
        r = client.post(f"{BASE}/heads", json={"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x",
                                               "direction": "INCOME", "required_fund_type": "PIGGY_BANK"}, headers=admin_h)
        assert r.status_code == 422

    def test_a_template_can_only_be_created_by_the_global_authority(self, client, admin_h, kendra_h, sakha_admin_h):
        code = new_code("TPL")
        body = {"head_code": code, "head_name": "New template", "direction": "INCOME"}
        assert client.post(f"{BASE}/heads", json=body, headers=sakha_admin_h).status_code == 403
        r = client.post(f"{BASE}/heads", json=body, headers=kendra_h)
        assert r.status_code == 201 and r.json()["is_template"] is True
        # ... and it is then adoptable
        assert any(h["head_code"] == code for h in heads_of(client, admin_h, templates_only="true")["items"])

    def test_patch_edits_the_presentation_only(self, client, admin_h, register_org_pk):
        h = make_head(client, admin_h, register_org_pk, is_restricted=True, restriction_purpose="Temple repair")
        r = client.patch(f"{BASE}/heads/{h['finance_head_pk']}", headers=admin_h, json={
            "head_name": "Renamed", "description": "New text", "display_order": 7, "is_pranami": True, "restriction_purpose": "Temple roof",
            # none of these may change after creation; unknown to the update model, so they are ignored
            "head_code": "HACKED", "direction": "EXPENSE", "is_restricted": False, "organization_pk": FAKE_UUID})
        assert r.status_code == 200, r.text
        got = r.json()
        assert (got["head_name"], got["description"], got["display_order"], got["is_pranami"], got["restriction_purpose"]) == ("Renamed", "New text", 7, True, "Temple roof")
        assert got["head_code"] == h["head_code"] and got["direction"] == "INCOME" and got["is_restricted"] is True
        assert got["organization_pk"] == str(register_org_pk)

    def test_a_restricted_head_cannot_lose_its_purpose(self, client, admin_h, register_org_pk):
        h = make_head(client, admin_h, register_org_pk, is_restricted=True, restriction_purpose="Temple repair")
        assert client.patch(f"{BASE}/heads/{h['finance_head_pk']}", json={"restriction_purpose": None}, headers=admin_h).status_code == 422

    def test_blank_name_is_422(self, client, admin_h, register_org_pk):
        h = make_head(client, admin_h, register_org_pk)
        assert client.patch(f"{BASE}/heads/{h['finance_head_pk']}", json={"head_name": "   "}, headers=admin_h).status_code == 422

    def test_expense_head_cannot_become_pranami(self, client, admin_h, register_org_pk):
        h = make_head(client, admin_h, register_org_pk, direction="EXPENSE")
        assert client.patch(f"{BASE}/heads/{h['finance_head_pk']}", json={"is_pranami": True}, headers=admin_h).status_code == 422


class TestHeadVisibilityAndScope:
    def test_configuration_needs_the_approve_permission(self, client, sakha_admin_h, viewer_h, register_org_pk):
        body = {"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "INCOME"}
        assert client.post(f"{BASE}/heads", json=body, headers=sakha_admin_h).status_code == 403     # MANAGE alone is not enough
        assert client.post(f"{BASE}/heads", json=body, headers=viewer_h).status_code == 403

    def test_a_scoped_admin_sees_templates_and_only_their_own_sanghas_heads(self, client, admin_h, other_admin_h, register_org_pk, other_org_pk):
        mine = make_head(client, admin_h, register_org_pk, head_name="Private to S1")
        theirs = make_head(client, admin_h, other_org_pk, head_name="Private to S2")
        seen = {h["finance_head_pk"] for h in heads_of(client, other_admin_h)["items"]}
        assert theirs["finance_head_pk"] in seen and mine["finance_head_pk"] not in seen
        assert any(h["is_template"] for h in heads_of(client, other_admin_h)["items"])                  # templates are visible to every finance user
        assert client.get(f"{BASE}/heads/{mine['finance_head_pk']}", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/heads/{mine['finance_head_pk']}", headers=admin_h).status_code == 200

    def test_a_foreign_admin_cannot_edit_or_switch_off_a_head(self, client, admin_h, kendra_h, register_org_pk, other_admin_h):
        h = make_head(client, admin_h, register_org_pk)
        pk = h["finance_head_pk"]
        assert client.patch(f"{BASE}/heads/{pk}", json={"head_name": "x"}, headers=other_admin_h).status_code == 403
        assert raw_move(client, other_admin_h, "heads", pk, "INACTIVE").status_code == 403

    def test_templates_are_read_only_for_scoped_admins(self, client, sakha_admin_h):
        tmpl = heads_of(client, sakha_admin_h, templates_only="true")["items"][0]
        assert client.get(f"{BASE}/heads/{tmpl['finance_head_pk']}", headers=sakha_admin_h).status_code == 200
        assert client.patch(f"{BASE}/heads/{tmpl['finance_head_pk']}", json={"head_name": "x"}, headers=sakha_admin_h).status_code == 403

    def test_filters(self, client, admin_h, register_org_pk):
        h = make_head(client, admin_h, register_org_pk, is_pranami=True, head_name="Searchable Zebra Pranami")
        exp = make_head(client, admin_h, register_org_pk, direction="EXPENSE")
        got = {x["finance_head_pk"] for x in heads_of(client, admin_h, organization_pk=str(register_org_pk), q="Zebra", is_pranami="true")["items"]}
        assert got == {h["finance_head_pk"]}
        assert exp["finance_head_pk"] in {x["finance_head_pk"] for x in heads_of(client, admin_h, organization_pk=str(register_org_pk), direction="EXPENSE")["items"]}

    def test_templates_can_be_left_out_of_the_list(self, client, admin_h, other_admin_h, register_org_pk, other_org_pk):
        mine = make_head(client, admin_h, register_org_pk, head_name="Sangha owned")
        for headers in (admin_h, other_admin_h):
            items = heads_of(client, headers, with_templates="false")["items"]
            assert items and not any(h["is_template"] for h in items)
        assert mine["finance_head_pk"] in {h["finance_head_pk"] for h in heads_of(client, admin_h, with_templates="false")["items"]}
        assert any(h["is_template"] for h in heads_of(client, admin_h)["items"])                     # the default still includes them

    def test_for_scope_lists_only_active_heads_a_transaction_there_may_use(self, client, admin_h, register_org_pk, other_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        off = make_head(client, admin_h, register_org_pk, head_name="Switched off")
        move(client, admin_h, "heads", off["finance_head_pk"], "INACTIVE")
        foreign = make_head(client, admin_h, other_org_pk, head_name="Other Sangha")
        got = {h["finance_head_pk"] for h in heads_of(client, admin_h, for_scope_pk=w["scope"]["financial_scope_pk"])["items"]}
        assert off["finance_head_pk"] not in got and foreign["finance_head_pk"] not in got
        assert TEMPLATE_CODES <= {h["head_code"] for h in heads_of(client, admin_h, for_scope_pk=w["scope"]["financial_scope_pk"])["items"]}


# ═══════════════════════════════════════════════════════════════════════
# Transactions follow the head's rules (no fixed category list)
# ═══════════════════════════════════════════════════════════════════════

class TestTransactionsFollowTheHead:
    def test_the_transaction_stores_the_head_and_a_code_snapshot(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        custom = make_head(client, admin_h, register_org_pk, head_name="Festival donation")
        body = txn_body(client, admin_h, w, amount="75.00")
        body["finance_head_pk"] = custom["finance_head_pk"]
        r = client.post(f"{BASE}/transactions", json=body, headers=admin_h)
        assert r.status_code == 201, r.text
        t = r.json()
        assert t["finance_head_pk"] == custom["finance_head_pk"] and t["finance_head_name"] == "Festival donation"
        assert t["transaction_category"] == custom["head_code"]
        assert heads_of(client, admin_h, organization_pk=str(register_org_pk), q=custom["head_code"])["items"][0]["transaction_count"] == 1

    def test_a_head_of_another_sangha_is_refused(self, client, admin_h, register_org_pk, other_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        foreign = make_head(client, admin_h, other_org_pk)
        body = txn_body(client, admin_h, w)
        body["finance_head_pk"] = foreign["finance_head_pk"]
        r = client.post(f"{BASE}/transactions", json=body, headers=admin_h)
        assert r.status_code == 422 and "different organization" in r.text

    def test_a_template_cannot_be_used_on_a_sangha_scope_but_can_on_a_scope_without_organization(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        template = next(h for h in heads_of(client, admin_h, templates_only="true")["items"] if h["head_code"] == "GRANT")
        body = txn_body(client, admin_h, w)
        body["finance_head_pk"] = template["finance_head_pk"]
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422
        # a scope with no organization uses the global templates
        year = make_year(client, admin_h)
        free = make_scope(client, admin_h, None, activate_with=admin_h)
        ok = txn_body(client, admin_h, {"year": year, "scope": free}, code="GRANT")
        assert client.post(f"{BASE}/transactions", json=ok, headers=admin_h).status_code == 201

    def test_a_switched_off_head_takes_no_new_entries_until_it_is_switched_on_again(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        h = make_head(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w)
        body["finance_head_pk"] = h["finance_head_pk"]
        move(client, admin_h, "heads", h["finance_head_pk"], "INACTIVE")
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422
        move(client, admin_h, "heads", h["finance_head_pk"], "ACTIVE")
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 201

    def test_a_custom_restricted_head_needs_a_restricted_fund(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        h = make_head(client, admin_h, register_org_pk, is_restricted=True, restriction_purpose="Library")
        body = txn_body(client, admin_h, w)
        body["finance_head_pk"] = h["finance_head_pk"]
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422               # general fund / none
        fund = make_fund(client, admin_h, w["scope"]["financial_scope_pk"], activate_with=admin_h, fund_type="SPECIFIC_PURPOSE",
                         is_restricted=True, restriction_purpose="Library")
        body["fund_master_pk"] = fund["fund_master_pk"]
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 201

    def test_a_custom_head_can_demand_a_fund_type(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        h = make_head(client, admin_h, register_org_pk, required_fund_type="PUBLICATION")
        body = txn_body(client, admin_h, w, fund=w["fund"])                                                      # a GENERAL fund
        body["finance_head_pk"] = h["finance_head_pk"]
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422
        pub = make_fund(client, admin_h, w["scope"]["financial_scope_pk"], activate_with=admin_h, fund_type="PUBLICATION")
        body["fund_master_pk"] = pub["fund_master_pk"]
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 201

    def test_the_sinking_fund_template_still_needs_a_sakha(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        no_sakha = make_fund(client, admin_h, w["scope"]["financial_scope_pk"], activate_with=admin_h, fund_type="GENERAL")
        body = txn_body(client, admin_h, w, code="PRANAMI_SINKING_FUND", fund=no_sakha)
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422
        sinking = make_fund(client, admin_h, w["scope"]["financial_scope_pk"], fund_type="SINKING_FUND", organization_pk=str(register_org_pk))
        move(client, admin_h, "funds", sinking["fund_master_pk"], "ACTIVE")
        body["fund_master_pk"] = sinking["fund_master_pk"]
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 201

    def test_the_head_can_be_changed_on_a_draft_and_the_snapshot_follows(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"], category="DONATION_GENERAL")
        other = head_pk(client, admin_h, w["scope"], "GRANT")
        r = client.patch(f"{BASE}/transactions/{txn['financial_transaction_pk']}", json={"finance_head_pk": other}, headers=admin_h)
        assert r.status_code == 200 and r.json()["transaction_category"] == "GRANT"

    def test_old_transactions_keep_their_meaning_when_a_head_is_renamed_or_switched_off(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        h = make_head(client, admin_h, register_org_pk, head_name="Original name")
        body = txn_body(client, admin_h, w)
        body["finance_head_pk"] = h["finance_head_pk"]
        t = client.post(f"{BASE}/transactions", json=body, headers=admin_h).json()
        client.patch(f"{BASE}/heads/{h['finance_head_pk']}", json={"head_name": "Renamed later"}, headers=admin_h)
        move(client, admin_h, "heads", h["finance_head_pk"], "INACTIVE")
        again = client.get(f"{BASE}/transactions/{t['financial_transaction_pk']}", headers=admin_h).json()
        assert again["transaction_category"] == h["head_code"] and again["finance_head_name"] == "Renamed later"

    def test_transactions_can_be_filtered_by_head(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        a = make_txn(client, admin_h, w["year"], w["scope"], category="GRANT")
        make_txn(client, admin_h, w["year"], w["scope"], category="DONATION_GENERAL")
        r = client.get(f"{BASE}/transactions", params={"finance_head_pk": a["finance_head_pk"], "financial_scope_pk": w["scope"]["financial_scope_pk"]}, headers=admin_h)
        assert r.status_code == 200 and {t["financial_transaction_pk"] for t in r.json()["items"]} == {a["financial_transaction_pk"]}

    def test_summary_groups_by_head_with_its_name(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], category="GRANT", amount="40.00"))
        s = client.get(f"{BASE}/summary", params={"financial_year_pk": w["year"]["financial_year_pk"],
                                                  "financial_scope_pk": w["scope"]["financial_scope_pk"]}, headers=admin_h).json()
        row = next(c for c in s["by_category"] if c["transaction_category"] == "GRANT")
        assert row["finance_head_name"] == "Grant" and float(row["total"]) == 40.0


# ═══════════════════════════════════════════════════════════════════════
# UPI collection settings of a head
# ═══════════════════════════════════════════════════════════════════════

class TestHeadCollectionSettings:
    def _ingredients(self, client, admin_h, org, gw):
        w = make_world(client, admin_h, org)
        return w, make_account(client, admin_h, org, gw)

    def test_a_head_collects_into_its_sangha_scope_fund_and_account(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        h = u["head"]
        assert h["allow_upi"] and h["is_pranami"]
        assert h["collection_scope_code"] == u["world"]["scope"]["scope_code"] and h["collection_account_label"] == u["account"]["account_label"]

    def test_upi_needs_a_scope_and_an_account(self, client, admin_h, register_org_pk, mock_gateway):
        w, acct = self._ingredients(client, admin_h, register_org_pk, mock_gateway)
        body = {"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "INCOME", "allow_upi": True}
        assert client.post(f"{BASE}/heads", json=body, headers=admin_h).status_code == 422
        body.update(head_code=new_code(), collection_scope_pk=w["scope"]["financial_scope_pk"])
        assert client.post(f"{BASE}/heads", json=body, headers=admin_h).status_code == 422                # still no account
        body.update(head_code=new_code(), collection_account_pk=acct["financial_account_pk"])
        assert client.post(f"{BASE}/heads", json=body, headers=admin_h).status_code == 201

    def test_the_scope_and_account_must_belong_to_the_heads_sangha(self, client, admin_h, register_org_pk, other_org_pk, mock_gateway):
        w, acct = self._ingredients(client, admin_h, register_org_pk, mock_gateway)
        foreign_scope = make_world(client, admin_h, other_org_pk)["scope"]
        foreign_acct = make_account(client, admin_h, other_org_pk, mock_gateway)
        base = {"organization_pk": str(register_org_pk), "head_name": "x", "direction": "INCOME", "allow_upi": True}
        ok = {"collection_scope_pk": w["scope"]["financial_scope_pk"], "collection_account_pk": acct["financial_account_pk"]}
        for bad in ({"collection_scope_pk": foreign_scope["financial_scope_pk"]}, {"collection_account_pk": foreign_acct["financial_account_pk"]}):
            r = client.post(f"{BASE}/heads", json={**base, "head_code": new_code(), **ok, **bad}, headers=admin_h)
            assert r.status_code == 422, bad

    def test_the_account_must_have_a_payment_gateway(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        plain = make_account(client, admin_h, register_org_pk)                                           # no gateway
        r = client.post(f"{BASE}/heads", headers=admin_h, json={
            "organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "INCOME", "allow_upi": True,
            "collection_scope_pk": w["scope"]["financial_scope_pk"], "collection_account_pk": plain["financial_account_pk"]})
        assert r.status_code == 422 and "gateway" in r.text

    def test_a_restricted_head_must_collect_into_a_restricted_fund(self, client, admin_h, register_org_pk, mock_gateway):
        w, acct = self._ingredients(client, admin_h, register_org_pk, mock_gateway)
        body = {"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "INCOME", "allow_upi": True,
                "is_restricted": True, "restriction_purpose": "Library", "collection_scope_pk": w["scope"]["financial_scope_pk"],
                "collection_account_pk": acct["financial_account_pk"], "collection_fund_pk": w["fund"]["fund_master_pk"]}   # a GENERAL fund
        assert client.post(f"{BASE}/heads", json=body, headers=admin_h).status_code == 422

    def test_the_collection_scope_must_be_active(self, client, admin_h, register_org_pk, mock_gateway):
        acct = make_account(client, admin_h, register_org_pk, mock_gateway)
        draft = make_scope(client, admin_h, register_org_pk)                                              # DRAFT
        r = client.post(f"{BASE}/heads", headers=admin_h, json={
            "organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x", "direction": "INCOME", "allow_upi": True,
            "collection_scope_pk": draft["financial_scope_pk"], "collection_account_pk": acct["financial_account_pk"]})
        assert r.status_code == 422

    def test_a_template_can_never_collect_money(self, client, kendra_h, register_org_pk, mock_gateway, admin_h):
        w, acct = self._ingredients(client, admin_h, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/heads", headers=kendra_h, json={
            "head_code": new_code("TPL"), "head_name": "x", "direction": "INCOME", "allow_upi": True,
            "collection_scope_pk": w["scope"]["financial_scope_pk"], "collection_account_pk": acct["financial_account_pk"]})
        assert r.status_code == 422

    def test_collection_targets_can_be_changed_later_and_switched_off(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        new_acct = make_account(client, admin_h, register_org_pk, mock_gateway)
        pk = u["head"]["finance_head_pk"]
        r = client.patch(f"{BASE}/heads/{pk}", json={"collection_account_pk": new_acct["financial_account_pk"]}, headers=admin_h)
        assert r.status_code == 200 and r.json()["collection_account_pk"] == new_acct["financial_account_pk"]
        off = client.patch(f"{BASE}/heads/{pk}", json={"allow_upi": False}, headers=admin_h)
        assert off.status_code == 200 and off.json()["allow_upi"] is False

    def test_an_edit_that_would_break_the_set_up_is_refused(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        pk = u["head"]["finance_head_pk"]
        assert client.patch(f"{BASE}/heads/{pk}", json={"collection_account_pk": None}, headers=admin_h).status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Receiving accounts
# ═══════════════════════════════════════════════════════════════════════

class TestAccounts:
    def test_create_and_read_back(self, client, admin_h, register_org_pk):
        a = make_account(client, admin_h, register_org_pk, bank_name="Post Office", account_type="POST_OFFICE", ifsc_code=None)
        assert a["status"] == "ACTIVE" and a["account_type"] == "POST_OFFICE" and a["account_number_last4"] == "1234"
        assert a["gateway_provider"] is None and a["gateway_ready"] is False and a["head_count"] == 0
        assert client.get(f"{BASE}/accounts/{a['financial_account_pk']}", headers=admin_h).json()["account_label"] == a["account_label"]

    @pytest.mark.parametrize("field,bad", [
        ("account_number_last4", "123"), ("account_number_last4", "12345"), ("account_number_last4", "12ab"), ("account_number_last4", "1234567890123456"),
        ("ifsc_code", "sbin0001234x"), ("ifsc_code", "SBIN1001234"), ("ifsc_code", "SBIN00012"),
        ("upi_vpa", "no-at-sign"), ("upi_vpa", "@bank"), ("upi_vpa", "a@1"),
        ("gateway_credential_ref", "has space"), ("gateway_credential_ref", "1START"), ("gateway_credential_ref", "A" * 41),
        ("gateway_provider", "PAYPAL"), ("account_type", "WALLET"),
    ])
    def test_field_validation(self, client, admin_h, register_org_pk, field, bad):
        body = {"organization_pk": str(register_org_pk), "account_label": new_code("A"), "account_holder_name": "Holder", field: bad}
        if field == "gateway_credential_ref":
            body["gateway_provider"] = "MOCK"
        assert client.post(f"{BASE}/accounts", json=body, headers=admin_h).status_code == 422, (field, bad)

    def test_lowercase_ifsc_and_credential_names_are_normalised(self, client, admin_h, register_org_pk):
        a = make_account(client, admin_h, register_org_pk, ifsc_code="sbin0001234", gateway_provider="mock", gateway_credential_ref="my_set")
        assert a["ifsc_code"] == "SBIN0001234" and a["gateway_provider"] == "MOCK" and a["gateway_credential_ref"] == "MY_SET"

    def test_a_gateway_needs_its_credential_set_name(self, client, admin_h, register_org_pk):
        r = client.post(f"{BASE}/accounts", headers=admin_h, json={
            "organization_pk": str(register_org_pk), "account_label": new_code("A"), "account_holder_name": "H", "gateway_provider": "MOCK"})
        assert r.status_code == 422

    def test_a_full_account_number_or_a_secret_is_not_even_accepted_as_a_field(self, client, admin_h, register_org_pk):
        body = {"organization_pk": str(register_org_pk), "account_label": new_code("A"), "account_holder_name": "H",
                "account_number": "123456789012", "key_secret": "supersecret", "webhook_secret": "supersecret"}
        r = client.post(f"{BASE}/accounts", json=body, headers=admin_h)
        assert r.status_code == 201
        text = r.text
        assert "123456789012" not in text and "supersecret" not in text
        assert not any(k for k in r.json() if "secret" in k or k == "account_number")

    def test_label_is_unique_per_sangha_only(self, client, admin_h, register_org_pk, other_org_pk):
        label = new_code("L")
        make_account(client, admin_h, register_org_pk, account_label=label)
        again = client.post(f"{BASE}/accounts", json={"organization_pk": str(register_org_pk), "account_label": label, "account_holder_name": "H"}, headers=admin_h)
        assert again.status_code == 409
        make_account(client, admin_h, other_org_pk, account_label=label)

    def test_only_one_default_per_sangha(self, client, admin_h, register_org_pk):
        first = make_account(client, admin_h, register_org_pk, is_default=True)
        second = make_account(client, admin_h, register_org_pk, is_default=True)
        got = {a["financial_account_pk"]: a["is_default"] for a in client.get(f"{BASE}/accounts", params={"organization_pk": str(register_org_pk)}, headers=admin_h).json()["items"]}
        assert got[second["financial_account_pk"]] is True and got[first["financial_account_pk"]] is False
        client.patch(f"{BASE}/accounts/{first['financial_account_pk']}", json={"is_default": True}, headers=admin_h)
        got = {a["financial_account_pk"]: a["is_default"] for a in client.get(f"{BASE}/accounts", params={"organization_pk": str(register_org_pk)}, headers=admin_h).json()["items"]}
        assert got[first["financial_account_pk"]] is True and got[second["financial_account_pk"]] is False

    def test_gateway_ready_needs_the_provider_enabled_and_the_credentials_present(self, client, admin_h, register_org_pk, mock_gateway, monkeypatch):
        a = make_account(client, admin_h, register_org_pk, mock_gateway)
        pk = a["financial_account_pk"]
        assert client.get(f"{BASE}/accounts/{pk}", headers=admin_h).json()["gateway_ready"] is True
        monkeypatch.delenv(f"UPI_{mock_gateway.ref}_WEBHOOK_SECRET")                              # a half-configured set is not ready
        assert client.get(f"{BASE}/accounts/{pk}", headers=admin_h).json()["gateway_ready"] is False

    def test_gateway_is_not_ready_when_the_provider_is_not_enabled(self, client, admin_h, register_org_pk, monkeypatch):
        a = make_account(client, admin_h, register_org_pk, gateway_provider="MOCK", gateway_credential_ref="NOT_CONFIGURED_ANYWHERE")
        assert a["gateway_ready"] is False

    def test_edit(self, client, admin_h, register_org_pk):
        a = make_account(client, admin_h, register_org_pk)
        r = client.patch(f"{BASE}/accounts/{a['financial_account_pk']}", headers=admin_h,
                         json={"account_label": "Renamed account", "bank_name": "Canara Bank", "upi_vpa": "new@canara", "branch_name": None})
        assert r.status_code == 200 and (r.json()["account_label"], r.json()["bank_name"], r.json()["upi_vpa"]) == ("Renamed account", "Canara Bank", "new@canara")

    def test_an_account_in_use_cannot_lose_its_gateway_or_be_switched_off(self, client, admin_h, register_org_pk, mock_gateway):
        u = upi_world(client, admin_h, register_org_pk, mock_gateway)
        pk = u["account"]["financial_account_pk"]
        assert client.get(f"{BASE}/accounts/{pk}", headers=admin_h).json()["head_count"] == 1
        assert client.patch(f"{BASE}/accounts/{pk}", json={"gateway_provider": None, "gateway_credential_ref": None}, headers=admin_h).status_code == 422
        r = client.post(f"{BASE}/accounts/{pk}/transition", json={"status": "INACTIVE", "remarks": "closing the account"}, headers=admin_h)
        assert r.status_code == 422 and "UPI head" in r.text
        # once the head stops collecting, it can go
        client.patch(f"{BASE}/heads/{u['head']['finance_head_pk']}", json={"allow_upi": False}, headers=admin_h)
        done = client.post(f"{BASE}/accounts/{pk}/transition", json={"status": "INACTIVE", "remarks": "closing the account"}, headers=admin_h)
        assert done.status_code == 200 and done.json()["status"] == "INACTIVE" and done.json()["is_default"] is False

    def test_switching_an_account_off_needs_a_reason_and_it_can_be_switched_on_again(self, client, admin_h, register_org_pk):
        a = make_account(client, admin_h, register_org_pk)
        pk = a["financial_account_pk"]
        assert raw_move(client, admin_h, "accounts", pk, "INACTIVE").status_code == 422
        move(client, admin_h, "accounts", pk, "INACTIVE", remarks="Account closed")
        assert client.patch(f"{BASE}/accounts/{pk}", json={"bank_name": "x"}, headers=admin_h).status_code == 422   # frozen while off
        assert move(client, admin_h, "accounts", pk, "ACTIVE")["status"] == "ACTIVE"

    def test_scope_and_permissions(self, client, admin_h, sakha_admin_h, other_admin_h, viewer_h, register_org_pk):
        body = {"organization_pk": str(register_org_pk), "account_label": new_code("A"), "account_holder_name": "H"}
        assert client.post(f"{BASE}/accounts", json=body, headers=sakha_admin_h).status_code == 403        # MANAGE is not enough
        assert client.post(f"{BASE}/accounts", json=body, headers=viewer_h).status_code == 403
        a = make_account(client, admin_h, register_org_pk)
        pk = a["financial_account_pk"]
        assert client.get(f"{BASE}/accounts/{pk}", headers=sakha_admin_h).status_code == 200                # own Sakha may read
        assert client.get(f"{BASE}/accounts/{pk}", headers=other_admin_h).status_code == 403                # a foreign one may not
        assert pk not in {x["financial_account_pk"] for x in client.get(f"{BASE}/accounts", headers=other_admin_h).json()["items"]}
        assert client.patch(f"{BASE}/accounts/{pk}", json={"bank_name": "x"}, headers=other_admin_h).status_code == 403

    def test_list_filters(self, client, admin_h, register_org_pk):
        a = make_account(client, admin_h, register_org_pk, bank_name="Zebra Bank Unique")
        got = client.get(f"{BASE}/accounts", params={"q": "Zebra Bank Unique"}, headers=admin_h).json()
        assert [x["financial_account_pk"] for x in got["items"]] == [a["financial_account_pk"]]
