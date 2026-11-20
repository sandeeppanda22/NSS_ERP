"""
Sakha approval chain (owner decision 2026-11-17): the Treasurer approves first, then the President (the Secretary when no President
is seated); the Treasurer alone approves a spend within the head's limit; income on a head flagged "no approval" posts when it is
submitted; every spend carries bills that add up to its amount; the authority is the SEAT, never a permission.

Real integration tests (nothing mocked) against a database built with Phase 11i, 14_finance_head_fixed_amount_patch.sql,
15_finance_head_approval_patch.sql and the three new tables. The cast is tests/finance_approval_support.py.
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
    vacate,
)
from tests.finance_support import (  # noqa: F401  (fixtures)
    admin_h,
    admin_user,
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


@pytest.fixture(autouse=True)
def _no_default_limit(write_conn, register_org_pk):
    """The DB is rolled back per MODULE, not per test: a test that sets the Sakha's default Treasurer limit (2000, 100, 700 ...) would leave
    it behind and let the Treasurer approve alone in every later test. Start each test with no default."""
    write_conn.cursor().execute(
        "UPDATE nss.finance_approval_policy SET default_treasurer_limit = NULL WHERE organization_pk = %s", (str(register_org_pk),))


@pytest.fixture
def cw(client, admin_h, write_conn, register_org_pk):
    return chain_world(client, admin_h, write_conn, register_org_pk)


def pk(txn) -> str:
    return txn["financial_transaction_pk"]


def audit_actions(write_conn, table, record_pk) -> list[str]:
    cur = write_conn.cursor()
    cur.execute("SELECT action FROM nss.system_event_log WHERE table_name = %s AND record_pk::text = %s ORDER BY event_at", (table, str(record_pk)))
    return [r[0] for r in cur.fetchall()]


class TestIncomeOnAPreDefinedHead:
    def test_it_posts_when_it_is_submitted_with_no_approval(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "skip", "250.00")
        done = submit(client, sakha_admin_h, pk(txn))
        assert done["status"] == "POSTED"
        state = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()
        assert state["applies"] is True and state["requires"] == "NONE" and state["steps"] == []

    def test_the_audit_says_why_nobody_approved_it(self, client, cw, sakha_admin_h, write_conn):
        txn = record(client, sakha_admin_h, cw, "skip", "250.00")
        submit(client, sakha_admin_h, pk(txn))
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'financial_transaction' AND record_pk::text = %s "
                    "AND detail->>'approval_not_required' IS NOT NULL", (pk(txn),))
        assert cur.fetchone() is not None

    def test_no_approver_can_decide_it(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "skip", "250.00")
        submit(client, sakha_admin_h, pk(txn))
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn), expect=422)       # already posted: nothing is waiting

    def test_income_on_any_other_head_goes_through_both_approvers(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "income", "900.00")
        assert submit(client, sakha_admin_h, pk(txn))["status"] == "PENDING_APPROVAL"
        t, p = login(client, cw["people"]["treasurer"]), login(client, cw["people"]["president"])
        assert decide(client, t, pk(txn))["final"] is None
        assert get_txn(client, sakha_admin_h, pk(txn))["status"] == "PENDING_APPROVAL"
        done = decide(client, p, pk(txn))
        assert done["final"] == "APPROVED" and done["status"] == "POSTED"


class TestSpendingWithinTheTreasurersLimit:
    def test_the_treasurer_alone_approves_and_it_posts(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "4000.00")
        done = decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        assert done["final"] == "APPROVED" and done["status"] == "POSTED"

    def test_exactly_the_limit_is_still_within_it(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "5000.00")
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(txn))["final"] == "APPROVED"

    def test_a_paisa_above_the_limit_needs_the_president_too(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "5000.01")
        t = login(client, cw["people"]["treasurer"])
        assert decide(client, t, pk(txn))["final"] is None
        assert get_txn(client, sakha_admin_h, pk(txn))["status"] == "PENDING_APPROVAL"

    def test_a_head_with_no_limit_always_needs_both(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(txn))["final"] is None

    def test_the_sakha_default_limit_applies_to_a_head_without_its_own(self, client, cw, sakha_admin_h, register_org_pk):
        put = client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": "2000.00"}, headers=sakha_admin_h)
        assert put.status_code == 200 and put.json()["default_treasurer_limit"] == "2000.00"
        within = spend_ready(client, sakha_admin_h, cw, "unlimited", "1999.00")
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(within))["final"] == "APPROVED"
        above = spend_ready(client, sakha_admin_h, cw, "unlimited", "2000.01")
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(above))["final"] is None

    def test_clearing_the_default_makes_every_such_spend_need_both_again(self, client, cw, sakha_admin_h, register_org_pk):
        client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": "2000.00"}, headers=sakha_admin_h)
        cleared = client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": None}, headers=sakha_admin_h)
        assert cleared.json()["default_treasurer_limit"] is None
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "100.00")
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(txn))["final"] is None

    def test_a_heads_own_limit_wins_over_the_default(self, client, cw, sakha_admin_h, register_org_pk):
        client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": "100.00"}, headers=sakha_admin_h)
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "4000.00")                    # head limit 5,000 > default 100
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(txn))["final"] == "APPROVED"


class TestTheOrderAndTheSeats:
    def test_the_president_cannot_go_first(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        r = decide(client, login(client, cw["people"]["president"]), pk(txn), expect=403)
        assert "Treasurer" in r["detail"]

    def test_the_treasurer_cannot_approve_twice(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        t = login(client, cw["people"]["treasurer"])
        decide(client, t, pk(txn))
        decide(client, t, pk(txn), expect=403)                          # step 2 is the President's, not the Treasurer's again

    def test_the_secretary_cannot_act_while_a_president_is_seated(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        decide(client, login(client, cw["people"]["secretary"]), pk(txn), expect=403)

    def test_with_no_president_the_secretary_gives_the_second_approval_and_is_recorded_as_covering(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        vacate(write_conn, register_org_pk, "PRESIDENT")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        state = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()
        assert state["next_position"] == "SECRETARY" and state["next_cover_reason"] == "PRESIDENT_SEAT_VACANT"
        done = decide(client, login(client, cw["people"]["secretary"]), pk(txn))
        assert done["final"] == "APPROVED"
        steps = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()["steps"]
        assert [(s["step_no"], s["position_code"], s["cover_reason"]) for s in steps] == [
            (1, "TREASURER", None), (2, "SECRETARY", "PRESIDENT_SEAT_VACANT")]

    def test_a_vacant_treasurer_seat_blocks_everything(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        vacate(write_conn, register_org_pk, "TREASURER")
        r = decide(client, login(client, cw["people"]["treasurer"]), pk(txn), expect=422)
        assert "vacant" in r["detail"]
        state = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()
        assert state["blocked_reason"] and state["next_position"] is None

    def test_no_seated_president_or_secretary_blocks_the_second_step(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        vacate(write_conn, register_org_pk, "PRESIDENT")
        vacate(write_conn, register_org_pk, "SECRETARY")
        decide(client, login(client, cw["people"]["secretary"]), pk(txn), expect=422)

    def test_a_person_who_lost_the_seat_can_no_longer_approve(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        vacate(write_conn, register_org_pk, "TREASURER")
        from tests.finance_approval_support import seat_person

        new_treasurer = seat_person(write_conn, register_org_pk, "TREASURER", "FinTreasurer2")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn), expect=403)       # the old holder
        assert decide(client, login(client, new_treasurer), pk(txn))["final"] == "APPROVED"


class TestWhoRecordedIt:
    def test_the_treasurer_may_approve_a_spend_they_recorded_within_the_limit(self, client, cw, sakha_admin_h, write_conn):
        """Spending within the limit is the Treasurer's own authority: recording and approving it is the same office."""
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        write_conn.cursor().execute("UPDATE nss.financial_transaction SET created_by_sangha_sevi_pk = %s WHERE financial_transaction_pk = %s",
                                    (cw["people"]["treasurer"]["sangha_sevi_pk"], pk(txn)))
        assert decide(client, login(client, cw["people"]["treasurer"]), pk(txn))["final"] == "APPROVED"
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'financial_transaction' AND record_pk::text = %s AND action = 'APPROVE'", (pk(txn),))
        assert cur.fetchone()[0]["treasurer_recorded_it"] is True              # said so in the audit trail

    def test_a_recorder_who_is_also_the_president_cannot_give_the_second_approval(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.financial_transaction SET created_by_sangha_sevi_pk = %s WHERE financial_transaction_pk = %s",
                    (cw["people"]["president"]["sangha_sevi_pk"], pk(txn)))
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        r = decide(client, login(client, cw["people"]["president"]), pk(txn), expect=403)
        assert "recorded" in r["detail"]


class TestRejection:
    def test_a_rejection_needs_a_reason_and_ends_the_entry(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        t = login(client, cw["people"]["treasurer"])
        decide(client, t, pk(txn), "reject", None, expect=422)
        decide(client, t, pk(txn), "reject", "   ", expect=422)
        done = decide(client, t, pk(txn), "reject", "Not a Sangha expense")
        assert done["final"] == "REJECTED" and done["status"] == "REJECTED"
        decide(client, t, pk(txn), expect=422)                                       # nothing left to decide

    def test_the_president_can_reject_after_the_treasurer_approved(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        done = decide(client, login(client, cw["people"]["president"]), pk(txn), "reject", "Bill looks altered")
        assert done["status"] == "REJECTED"
        steps = client.get(f"{BASE}/transactions/{pk(txn)}/approval", headers=sakha_admin_h).json()["steps"]
        assert [s["decision"] for s in steps] == ["APPROVED", "REJECTED"] and steps[1]["remarks"] == "Bill looks altered"


class TestOrdinaryApprovalIsClosedForASakha:
    def test_not_even_the_super_administrator_can_approve_a_sakha_entry_from_the_ordinary_button(self, client, cw, admin_h, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        r = client.post(f"{BASE}/transactions/{pk(txn)}/transition", json={"status": "APPROVED"}, headers=admin_h)
        assert r.status_code == 422 and "Treasurer" in r.json()["detail"]

    def test_the_super_administrator_is_not_a_seat_holder(self, client, cw, admin_h, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        decide(client, admin_h, pk(txn), expect=403)


class TestBills:
    def test_a_spend_cannot_be_submitted_without_bills(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "limited", "100.00")
        r = client.post(f"{BASE}/transactions/{pk(txn)}/transition", json={"status": "PENDING_APPROVAL"}, headers=sakha_admin_h)
        assert r.status_code == 422 and "at least one bill" in r.json()["detail"]

    def test_the_bills_must_add_up_to_the_spend(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "limited", "100.00")
        add_bill(client, sakha_admin_h, pk(txn), "60.00")
        r = client.post(f"{BASE}/transactions/{pk(txn)}/transition", json={"status": "PENDING_APPROVAL"}, headers=sakha_admin_h)
        assert r.status_code == 422 and "must be equal" in r.json()["detail"]
        add_bill(client, sakha_admin_h, pk(txn), "40.00")
        assert submit(client, sakha_admin_h, pk(txn))["status"] == "PENDING_APPROVAL"

    def test_the_list_totals_the_live_bills(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "limited", "100.00")
        a = add_bill(client, sakha_admin_h, pk(txn), "60.00")
        add_bill(client, sakha_admin_h, pk(txn), "40.00")
        listed = client.get(f"{BASE}/transactions/{pk(txn)}/bills", headers=sakha_admin_h).json()
        assert listed["count"] == 2 and listed["total_amount"] == "100.00"
        assert client.delete(f"{BASE}/transactions/{pk(txn)}/bills/{a['finance_transaction_bill_pk']}", headers=sakha_admin_h).status_code == 204
        after = client.get(f"{BASE}/transactions/{pk(txn)}/bills", headers=sakha_admin_h).json()
        assert after["count"] == 1 and after["total_amount"] == "40.00"

    def test_a_removed_bill_stays_in_the_audit_trail(self, client, cw, sakha_admin_h, write_conn):
        txn = record(client, sakha_admin_h, cw, "limited", "100.00")
        bill = add_bill(client, sakha_admin_h, pk(txn), "100.00")
        client.delete(f"{BASE}/transactions/{pk(txn)}/bills/{bill['finance_transaction_bill_pk']}", headers=sakha_admin_h)
        actions = audit_actions(write_conn, "finance_transaction_bill", bill["finance_transaction_bill_pk"])
        assert "CREATE" in actions and "DELETE" in actions
        cur = write_conn.cursor()
        cur.execute("SELECT is_active, deleted_at FROM nss.finance_transaction_bill WHERE finance_transaction_bill_pk = %s", (bill["finance_transaction_bill_pk"],))
        active, deleted_at = cur.fetchone()
        assert active is False and deleted_at is not None

    def test_bills_are_frozen_once_the_entry_is_submitted(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        add_bill(client, sakha_admin_h, pk(txn), "1.00", expect=422)
        bills = client.get(f"{BASE}/transactions/{pk(txn)}/bills", headers=sakha_admin_h).json()["items"]
        assert client.delete(f"{BASE}/transactions/{pk(txn)}/bills/{bills[0]['finance_transaction_bill_pk']}", headers=sakha_admin_h).status_code == 422

    def test_income_has_no_bills(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "income", "100.00")
        add_bill(client, sakha_admin_h, pk(txn), "100.00", expect=422)

    @pytest.mark.parametrize("url", ["http://x.example/b", "javascript:alert(1)", "ftp://x.example"])
    def test_only_an_https_link_is_accepted(self, client, cw, sakha_admin_h, url):
        txn = record(client, sakha_admin_h, cw, "limited", "100.00")
        add_bill(client, sakha_admin_h, pk(txn), "100.00", expect=422, document_url=url)

    def test_an_https_link_is_kept(self, client, cw, sakha_admin_h):
        txn = record(client, sakha_admin_h, cw, "limited", "100.00")
        bill = add_bill(client, sakha_admin_h, pk(txn), "100.00", document_url="https://drive.example/bill1")
        assert bill["document_url"] == "https://drive.example/bill1"

    def test_the_bill_must_still_cover_the_spend_when_an_approver_decides(self, client, cw, sakha_admin_h, write_conn):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.finance_transaction_bill SET amount = 1 WHERE financial_transaction_pk = %s", (pk(txn),))
        r = decide(client, login(client, cw["people"]["treasurer"]), pk(txn), expect=422)
        assert "bills" in r["detail"]


class TestReimbursingAMember:
    def test_the_member_must_be_named(self, client, cw, sakha_admin_h, plain_member):
        txn = record(client, sakha_admin_h, cw, "reimburse", "300.00")
        add_bill(client, sakha_admin_h, pk(txn), "300.00", vendor_name="Member's shop")
        r = client.post(f"{BASE}/transactions/{pk(txn)}/transition", json={"status": "PENDING_APPROVAL"}, headers=sakha_admin_h)
        assert r.status_code == 422 and "name the member" in r.json()["detail"]

    def test_with_the_member_named_it_goes_through_and_the_approver_sees_who(self, client, cw, sakha_admin_h, plain_member):
        txn = record(client, sakha_admin_h, cw, "reimburse", "300.00", sangha_sevi_id=plain_member["sangha_sevi_id"])
        add_bill(client, sakha_admin_h, pk(txn), "300.00", vendor_name="Member's shop")
        submit(client, sakha_admin_h, pk(txn))
        mine = client.get(f"{BASE}/my-approvals", headers=login(client, cw["people"]["treasurer"])).json()
        item = next(i for i in mine["items"] if i["financial_transaction_pk"] == pk(txn))
        assert item["member_name"] and item["bills_total"] == "300.00"


class TestTheApproversList:
    def test_each_office_bearer_sees_only_what_waits_for_them(self, client, cw, sakha_admin_h):
        both = spend_ready(client, sakha_admin_h, cw, "unlimited", "50.00")
        t, p, s = (login(client, cw["people"][k]) for k in ("treasurer", "president", "secretary"))
        ids = lambda h: {i["financial_transaction_pk"] for i in client.get(f"{BASE}/my-approvals", headers=h).json()["items"]}
        assert pk(both) in ids(t) and pk(both) not in ids(p) and pk(both) not in ids(s)
        decide(client, t, pk(both))
        assert pk(both) not in ids(t) and pk(both) in ids(p) and pk(both) not in ids(s)

    def test_an_item_carries_what_the_approver_needs_to_judge_it(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        item = next(i for i in client.get(f"{BASE}/my-approvals", headers=login(client, cw["people"]["treasurer"])).json()["items"]
                    if i["financial_transaction_pk"] == pk(txn))
        assert item["stage"] == 1 and item["position_code"] == "TREASURER" and item["requires"] == "TREASURER" and item["limit"] == "5000.00"
        assert item["head_name"] == "Electricity" and item["amount"] == "100.00" and len(item["bills"]) == 1 and item["transaction_type"] == "EXPENSE"

    def test_a_plain_member_has_nothing_waiting(self, client, cw, sakha_admin_h, plain_member_h):
        spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        assert client.get(f"{BASE}/my-approvals", headers=plain_member_h).json() == {"items": [], "total": 0}

    def test_a_decided_entry_leaves_the_list(self, client, cw, sakha_admin_h):
        txn = spend_ready(client, sakha_admin_h, cw, "limited", "100.00")
        t = login(client, cw["people"]["treasurer"])
        decide(client, t, pk(txn))
        assert pk(txn) not in {i["financial_transaction_pk"] for i in client.get(f"{BASE}/my-approvals", headers=t).json()["items"]}

    def test_a_secretary_in_cover_sees_the_second_step(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        vacate(write_conn, register_org_pk, "PRESIDENT")
        item = next(i for i in client.get(f"{BASE}/my-approvals", headers=login(client, cw["people"]["secretary"])).json()["items"]
                    if i["financial_transaction_pk"] == pk(txn))
        assert item["stage"] == 2 and item["position_code"] == "SECRETARY" and item["cover_reason"] == "PRESIDENT_SEAT_VACANT"
        assert [s["position_code"] for s in item["steps"]] == ["TREASURER"]


class TestEveryDecisionIsAudited:
    def test_both_approvals_and_the_posting_are_in_the_trail(self, client, cw, sakha_admin_h, write_conn):
        txn = spend_ready(client, sakha_admin_h, cw, "unlimited", "10.00")
        decide(client, login(client, cw["people"]["treasurer"]), pk(txn))
        decide(client, login(client, cw["people"]["president"]), pk(txn))
        actions = audit_actions(write_conn, "financial_transaction", pk(txn))
        assert actions.count("APPROVE") == 2 and actions.count("STATUS_CHANGE") >= 3          # submitted, approved, posted
        cur = write_conn.cursor()
        cur.execute("SELECT step_no, position_code, decision FROM nss.finance_approval_step WHERE financial_transaction_pk = %s ORDER BY step_no", (pk(txn),))
        assert cur.fetchall() == [(1, "TREASURER", "APPROVED"), (2, "PRESIDENT", "APPROVED")]

    def test_the_limit_change_is_audited_with_the_old_and_new_value(self, client, cw, sakha_admin_h, write_conn, register_org_pk):
        client.put(f"{BASE}/approval-policy", json={"organization_pk": str(register_org_pk), "default_treasurer_limit": "700.00"}, headers=sakha_admin_h)
        cur = write_conn.cursor()
        # Not "the latest row": every row of this module shares one transaction, so event_at is identical and earlier tests' policy
        # audits (2000.00, 100.00) tie with this one. Find this change by its own values; the DB trigger's rows carry no "to".
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'finance_approval_policy' "
                    "AND detail->>'organization_pk' = %s AND detail->>'to' = '700.00'", (str(register_org_pk),))
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0]["from"] is None                     # the autouse fixture cleared the default before the test


class TestHeadFlagsAreValidated:
    def test_income_cannot_carry_a_spending_limit_and_a_spend_cannot_skip_approval(self, client, admin_h, register_org_pk):
        from tests.finance_support import new_code

        base = {"organization_pk": str(register_org_pk), "head_code": new_code(), "head_name": "x"}
        assert client.post(f"{BASE}/heads", json={**base, "direction": "INCOME", "treasurer_limit": "10.00"}, headers=admin_h).status_code == 422
        assert client.post(f"{BASE}/heads", json={**base, "head_code": new_code(), "direction": "EXPENSE", "skips_approval": True}, headers=admin_h).status_code == 422
        assert client.post(f"{BASE}/heads", json={**base, "head_code": new_code(), "direction": "INCOME", "requires_member": True}, headers=admin_h).status_code == 422

    def test_the_flags_can_be_edited_later(self, client, cw, admin_h):
        h = cw["heads"]["limited"]["finance_head_pk"]
        r = client.patch(f"{BASE}/heads/{h}", json={"treasurer_limit": "9000.00"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["treasurer_limit"] == "9000.00"
        cleared = client.patch(f"{BASE}/heads/{h}", json={"treasurer_limit": None}, headers=admin_h)
        assert cleared.json()["treasurer_limit"] is None
        assert client.patch(f"{BASE}/heads/{h}", json={"skips_approval": True}, headers=admin_h).status_code == 422       # an EXPENSE head

    def test_a_kendra_head_for_all_sakhas_hands_the_flag_to_its_copies(self, client, admin_h, write_conn, cw):
        from tests.reparent_support import kendra_pks

        r = client.post(f"{BASE}/contributions", json={"organization_pk": kendra_pks(write_conn)[0], "head_name": "Kendra Pranami", "applies_to": "ALL_SAKHAS",
                                                         "fixed_amount": "100", "due_period": "YEARLY"}, headers=admin_h)
        assert r.status_code == 201, r.text
        source = r.json()["head"]
        assert source["skips_approval"] is True                                       # a contribution is a pre-defined income head
        items = client.get(f"{BASE}/heads", params={"organization_pk": cw["org_pk"], "page_size": 200, "with_templates": "false"}, headers=admin_h).json()["items"]
        copy = next(h for h in items if h["template_head_pk"] == source["finance_head_pk"])
        assert copy["skips_approval"] is True


class TestAnotherLevelIsUntouched:
    def test_an_entry_of_a_scope_without_an_organization_keeps_the_ordinary_approval(self, client, admin_h):
        from tests.finance_support import make_fund, make_scope, make_year, move, txn_body

        year = make_year(client, admin_h)
        scope = make_scope(client, admin_h, None, activate_with=admin_h)            # an NSS-wide scope: no organization
        fund = make_fund(client, admin_h, scope["financial_scope_pk"], activate_with=admin_h)
        w = {"year": year, "scope": scope, "fund": fund}
        body = txn_body(client, admin_h, w, kind="INCOME", amount="10", fund=fund)
        r = client.post(f"{BASE}/transactions", json=body, headers=admin_h)
        assert r.status_code == 201, r.text
        t = r.json()["financial_transaction_pk"]
        move(client, admin_h, "transactions", t, "PENDING_APPROVAL")
        approver = move(client, admin_h, "transactions", t, "APPROVED")            # the super administrator's ordinary approval still works there
        assert approver["status"] == "APPROVED"


class TestTheSeatedTreasurerRecordsTheSakhasFinance:
    """Owner 2026-11-20: the Treasurer is the finance administrator of their own Sakha: they view and RECORD its finance without any admin role
    (the live seat grants NSS_ERP_SAKHA_TREASURER = FINANCE_VIEW + FINANCE_MANAGE, scoped to the Sakha). It confers no configuration and no
    approval by permission, and it ends with the seat."""

    def test_the_treasurer_records_an_entry_and_sees_it_in_the_list(self, client, cw):
        t = login(client, cw["people"]["treasurer"])
        txn = record(client, t, cw, "income", "125.00")
        got = client.get(f"{BASE}/transactions/{pk(txn)}", headers=t)
        assert got.status_code == 200 and got.json()["amount"] in ("125.00", "125")

    def test_the_treasurer_sees_only_their_own_sakhas_scopes(self, client, cw, other_org_pk, admin_h):
        from tests.finance_support import make_scope

        theirs = make_scope(client, admin_h, other_org_pk, activate_with=admin_h)
        t = login(client, cw["people"]["treasurer"])
        items = client.get(f"{BASE}/scopes", headers=t, params={"page_size": 100}).json()["items"]
        assert items and all(i["organization_pk"] == cw["org_pk"] for i in items)
        assert theirs["financial_scope_pk"] not in {i["financial_scope_pk"] for i in items}

    def test_the_treasurer_still_cannot_configure_or_approve_by_permission(self, client, cw, register_org_pk):
        t = login(client, cw["people"]["treasurer"])
        txn = record(client, t, cw, "income", "50.00")
        assert client.post(f"{BASE}/contributions", headers=t, json={"organization_pk": str(register_org_pk), "head_name": "Mine"}).status_code == 403
        assert client.post(f"{BASE}/transactions/{pk(txn)}/transition", headers=t, json={"status": "APPROVED"}).status_code in (403, 422)

    def test_the_president_secretary_and_a_plain_member_are_unchanged(self, client, cw, plain_member_h):
        assert client.get(f"{BASE}/transactions", headers=plain_member_h).status_code == 403          # a member is no finance user
        p = login(client, cw["people"]["president"])
        assert client.get(f"{BASE}/transactions", headers=p).status_code == 200                      # the President is the Sakha admin by SEAT, as before

    def test_the_access_ends_with_the_seat(self, client, cw, write_conn, register_org_pk):
        t = login(client, cw["people"]["treasurer"])
        assert client.get(f"{BASE}/transactions", headers=t).status_code == 200
        vacate(write_conn, register_org_pk, "TREASURER")
        assert client.get(f"{BASE}/transactions", headers=t).status_code == 403
