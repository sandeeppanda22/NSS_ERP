"""
Security of the Sakha approval chain (owner decision 2026-11-17): the authority is the SEAT held now - no permission, no super
administrator, no other Sakha's office-bearer - and nothing about an entry leaks to anyone else. Real integration tests; the cast is
tests/finance_approval_support.py.
"""

import pytest

from tests.finance_approval_support import (
    BASE,
    add_bill,
    chain_world,
    decide,
    get_txn,
    login,
    record,
    spend_ready,
    submit,
)
from tests.finance_support import (  # noqa: F401  (fixtures)
    FAKE_UUID,
    admin_h,
    admin_user,
    kendra_admin,
    kendra_h,
    other_admin,
    other_admin_h,
    other_org_pk,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    viewer_h,
    viewer_user,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def cw(client, admin_h, write_conn, register_org_pk):
    return chain_world(client, admin_h, write_conn, register_org_pk)


def pk(txn) -> str:
    return txn["financial_transaction_pk"]


class TestAnonymousAndGarbage:
    @pytest.mark.parametrize("method,path,body", [
        ("GET", f"{BASE}/my-approvals", None),
        ("POST", f"{BASE}/transactions/{FAKE_UUID}/approve", {"remarks": None}),
        ("POST", f"{BASE}/transactions/{FAKE_UUID}/reject", {"remarks": "x"}),
        ("GET", f"{BASE}/approval-policy?organization_pk={FAKE_UUID}", None),
        ("PUT", f"{BASE}/approval-policy", {"organization_pk": FAKE_UUID}),
        ("GET", f"{BASE}/transactions/{FAKE_UUID}/bills", None),
        ("POST", f"{BASE}/transactions/{FAKE_UUID}/bills", {"vendor_name": "x", "bill_date": "2026-01-01", "amount": "1"}),
        ("DELETE", f"{BASE}/transactions/{FAKE_UUID}/bills/{FAKE_UUID}", None),
        ("GET", f"{BASE}/transactions/{FAKE_UUID}/approval", None),
    ])
    def test_no_token_is_401(self, method, path, body, client):
        assert client.request(method, path, json=body).status_code == 401

    def test_a_garbage_token_is_401(self, client):
        assert client.get(f"{BASE}/my-approvals", headers={"Authorization": "Bearer not.a.token"}).status_code == 401


class TestOnlyTheSeatHolderDecides:
    def test_the_super_administrator_cannot_approve_in_place_of_the_seat(self, client, cw, admin_h, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, admin_h, pk(txn), expect=403)
        decide(client, admin_h, pk(txn), "reject", "no", expect=403)
        assert get_txn(client, admin_h, pk(txn))["status"] == "PENDING_APPROVAL"

    def test_the_kendra_admin_cannot_either(self, client, cw, kendra_h, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, kendra_h, pk(txn), expect=403)

    def test_a_sakha_admin_who_records_cannot_approve(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, sakha_admin_h, pk(txn), expect=403)

    def test_a_plain_member_cannot(self, client, cw, plain_member_h, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, plain_member_h, pk(txn), expect=403)

    def test_a_refused_attempt_changes_nothing(self, client, cw, sakha_admin_h, write_conn, plain_member_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, plain_member_h, pk(txn), expect=403)
        cur = write_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nss.finance_approval_step WHERE financial_transaction_pk = %s", (pk(txn),))
        assert cur.fetchone()[0] == 0

    def test_another_sakhas_treasurer_cannot_approve(self, client, cw, admin_h, write_conn, other_org_pk, sakha_admin_h):
        theirs = chain_world(client, admin_h, write_conn, other_org_pk)
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, login(client, theirs["people"]["treasurer"]), pk(txn), expect=403)

    def test_one_sakhas_list_never_shows_anothers_entries(self, client, cw, admin_h, write_conn, other_org_pk, sakha_admin_h):
        theirs = chain_world(client, admin_h, write_conn, other_org_pk)
        mine = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        listed = client.get(f"{BASE}/my-approvals", headers=login(client, theirs["people"]["treasurer"])).json()["items"]
        assert pk(mine) not in {i["financial_transaction_pk"] for i in listed}

    def test_the_president_cannot_skip_the_treasurer_by_rejecting_first(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, login(client, cw["people"]["president"]), pk(txn), "reject", "No", expect=403)

    def test_an_unknown_entry_is_a_plain_404(self, client, cw):
        decide(client, login(client, cw["people"]["treasurer"]), FAKE_UUID, expect=404)

    def test_an_entry_of_a_scope_with_no_organization_is_not_reachable_through_the_chain(self, client, cw, admin_h):
        from tests.finance_support import make_fund, make_scope, make_year, txn_body

        year = make_year(client, admin_h)
        scope = make_scope(client, admin_h, None, activate_with=admin_h)
        fund = make_fund(client, admin_h, scope["financial_scope_pk"], activate_with=admin_h)
        r = client.post(f"{BASE}/transactions", json=txn_body(client, admin_h, {"year": year, "scope": scope, "fund": fund}, kind="INCOME", amount="10", fund=fund), headers=admin_h)
        assert r.status_code == 201, r.text
        decide(client, login(client, cw["people"]["treasurer"]), r.json()["financial_transaction_pk"], expect=404)

    def test_the_decision_body_cannot_name_another_approver_or_a_step(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        r = client.post(f"{BASE}/transactions/{pk(txn)}/approve", headers=login(client, cw["people"]["president"]),
                        json={"remarks": None, "step_no": 1, "person_pk": cw["people"]["treasurer"]["person_pk"], "position_code": "TREASURER"})
        assert r.status_code == 403                                           # the President is not who must act now, whatever the body says


class TestPermissionsOnTheRest:
    def test_a_viewer_reads_bills_and_state_but_cannot_change_anything(self, client, cw, sakha_admin_h, viewer_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        assert client.get(f"{BASE}/transactions/{pk(txn)}/bills", headers=viewer_h).status_code == 200
        assert client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=viewer_h).status_code == 200
        draft = record(client, sakha_admin_h, cw, "limited", "50.00")
        assert client.post(f"{BASE}/transactions/{pk(draft)}/bills", headers=viewer_h,
                           json={"vendor_name": "x", "bill_date": "2090-05-15", "amount": "50"}).status_code == 403

    def test_another_sakhas_admin_cannot_see_or_touch_the_bills(self, client, cw, sakha_admin_h, other_admin_h):
        txn = record(client, sakha_admin_h, cw, "limited", "50.00")
        add_bill(client, sakha_admin_h, pk(txn), "50.00")
        assert client.get(f"{BASE}/transactions/{pk(txn)}/bills", headers=other_admin_h).status_code == 403
        assert client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=other_admin_h).status_code == 403
        add_bill(client, other_admin_h, pk(txn), "1.00", expect=403)

    def test_a_plain_member_cannot_read_or_add_bills(self, client, cw, sakha_admin_h, plain_member_h):
        txn = record(client, sakha_admin_h, cw, "limited", "50.00")
        assert client.get(f"{BASE}/transactions/{pk(txn)}/bills", headers=plain_member_h).status_code == 403
        add_bill(client, plain_member_h, pk(txn), "50.00", expect=403)

    def test_the_default_limit_needs_configure_for_that_sakha(self, client, cw, register_org_pk, other_org_pk, viewer_h, other_admin_h, sakha_admin_h, plain_member_h):
        body = {"organization_pk": str(register_org_pk), "default_treasurer_limit": "1000"}
        for headers in (viewer_h, plain_member_h, other_admin_h):
            assert client.put(f"{BASE}/approval-policy", json=body, headers=headers).status_code == 403
        assert client.put(f"{BASE}/approval-policy", json=body, headers=sakha_admin_h).status_code == 200
        assert client.put(f"{BASE}/approval-policy", json={**body, "organization_pk": str(other_org_pk)}, headers=sakha_admin_h).status_code == 403

    def test_the_treasurer_cannot_raise_their_own_limit_by_being_the_treasurer(self, client, cw, register_org_pk):
        t = login(client, cw["people"]["treasurer"])                           # owner 2026-11-20: the Treasurer configures, but not the controls that bind THEM (by seat)
        assert client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": "99999999"}, headers=t).status_code == 403
        h = cw["heads"]["limited"]["finance_head_pk"]
        assert client.patch(f"{BASE}/heads/{h}", json={"treasurer_limit": "99999999"}, headers=t).status_code == 403

    def test_the_limit_applies_to_a_sakha_only(self, client, admin_h, write_conn):
        from tests.reparent_support import kendra_pks

        r = client.put(f"{BASE}/approval-policy", json={"organization_pk": kendra_pks(write_conn)[0], "default_treasurer_limit": "10"}, headers=admin_h)
        assert r.status_code == 422

    @pytest.mark.parametrize("value", ["0", "-5", "1.234", "abc", "99999999999999.99"])
    def test_a_bad_limit_is_refused(self, client, cw, register_org_pk, sakha_admin_h, value):
        r = client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": value}, headers=sakha_admin_h)
        assert r.status_code == 422


class TestNothingLeaks:
    def test_an_approvers_item_carries_no_internal_ids_of_other_people(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        item = next(i for i in client.get(f"{BASE}/my-approvals", headers=login(client, cw["people"]["treasurer"])).json()["items"]
                    if i["financial_transaction_pk"] == pk(txn))
        text = str(item)
        for forbidden in (cw["people"]["president"]["person_pk"], cw["people"]["secretary"]["person_pk"], cw["people"]["treasurer"]["person_pk"],
                          "created_by_sangha_sevi_pk", "person_pk", "gateway", "password"):
            assert forbidden not in text, forbidden

    def test_a_step_shows_a_name_not_the_deciders_id(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        steps = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()["steps"]
        assert steps and all(set(s) == {"step_no", "position_code", "decision", "decided_at", "decided_by_name", "remarks", "cover_reason"} for s in steps)

    def test_a_hostile_remark_is_stored_as_text(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        remark = "x'); DROP TABLE nss.finance_approval_step;-- <script>alert(1)</script>"
        done = decide(client, login(client, cw["people"]["treasurer"]), pk(txn), "reject", remark)
        assert done["status"] == "REJECTED"
        steps = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()["steps"]
        assert steps[0]["remarks"] == remark

    def test_remarks_have_a_length_limit(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        r = client.post(f"{BASE}/transactions/{pk(txn)}/approve", json={"remarks": "x" * 2001}, headers=login(client, cw["people"]["treasurer"]))
        assert r.status_code == 422


class TestTheLedgerRulesStillHold:
    def test_approving_cannot_post_into_a_closed_year(self, client, cw, sakha_admin_h, admin_h, write_conn):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        year_pk = cw["w"]["year"]["financial_year_pk"]
        write_conn.cursor().execute("UPDATE nss.financial_year SET status = 'CLOSING' WHERE financial_year_pk = %s", (year_pk,))
        r = decide(client, login(client, cw["people"]["treasurer"]), pk(txn), expect=422)
        assert "year" in r["detail"].lower()
        assert get_txn(client, admin_h, pk(txn))["status"] == "PENDING_APPROVAL"

    def test_a_restricted_spend_still_cannot_exceed_its_fund(self, client, cw, admin_h, sakha_admin_h):
        from tests.finance_support import make_fund, make_head

        org = cw["org_pk"]
        fund = make_fund(client, admin_h, cw["w"]["scope"]["financial_scope_pk"], activate_with=admin_h, fund_type="SPECIFIC_PURPOSE",
                         is_restricted=True, restriction_purpose="Temple repair")
        head = make_head(client, admin_h, org, direction="EXPENSE", head_name="Temple repair", is_restricted=True,
                         restriction_purpose="Temple repair", treasurer_limit="5000.00")
        cw2 = {**cw, "heads": {**cw["heads"], "restricted": head}, "w": {**cw["w"], "fund": fund}}
        txn = record(client, sakha_admin_h, cw2, "restricted", "100.00")
        add_bill(client, sakha_admin_h, pk(txn), "100.00")
        submit(client, sakha_admin_h, pk(txn))
        r = decide(client, login(client, cw["people"]["treasurer"]), pk(txn), expect=422)
        assert "fund" in r["detail"].lower() or "balance" in r["detail"].lower() or "holds" in r["detail"].lower()
