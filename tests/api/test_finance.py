"""
Finance API (Tier 12) — api/routers/finance.py.

Real integration tests (nothing mocked): they need a bootstrapped local DB with
Phase 11i, the FINANCE_* permissions patch and the Finance reference-data
patch. Each test builds its own financial year (start year 2090+), scope and
fund; everything rolls back with the module SAVEPOINT.

NEVER RUN against a database when this file was written (the sandbox blocks
sockets); the SQL of every query was replayed against the Finance DDL in a
throwaway single-user PostgreSQL 18 instead.
"""

from datetime import date

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    adopt_templates,
    head_pk,
    txn_body,
    _login_headers,
    FAKE_UUID,
    admin_h,
    admin_user,
    kendra_admin,
    kendra_h,
    make_fund,
    make_scope,
    make_txn,
    make_world,
    make_year,
    move,
    new_member,
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
    viewer_h,
    viewer_user,
)


# ═══════════════════════════════════════════════════════════════════════
# Reference
# ═══════════════════════════════════════════════════════════════════════

class TestReference:
    def test_reference_lists_upi_and_the_lifecycle_table(self, client, admin_h):
        r = client.get(f"{BASE}/reference", headers=admin_h)
        assert r.status_code == 200, r.text
        body = r.json()
        codes = [m["code"] for m in body["payment_methods"]]
        assert "UPI" in codes and "CASH" in codes
        assert body["head_directions"] == ["INCOME", "EXPENSE"] and "BANK" in body["account_types"]
        assert isinstance(body["gateway_providers"], list)
        pairs = {(t["from"], t["to"]) for t in body["transitions"]["transaction"]}
        assert ("PENDING_APPROVAL", "APPROVED") in pairs and ("POSTED", "SETTLED") in pairs

    def test_viewer_can_read_reference(self, client, viewer_h):
        assert client.get(f"{BASE}/reference", headers=viewer_h).status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Financial years
# ═══════════════════════════════════════════════════════════════════════

class TestYears:
    def test_create_runs_april_to_march(self, client, admin_h):
        year = make_year(client, admin_h, open_=False)
        assert year["status"] == "PLANNED"
        start = date.fromisoformat(year["start_date"])
        end = date.fromisoformat(year["end_date"])
        assert (start.month, start.day) == (4, 1) and (end.month, end.day) == (3, 31)
        assert end.year == start.year + 1
        assert year["year_code"] == f"{start.year}-{(start.year + 1) % 100:02d}"

    def test_duplicate_year_is_409(self, client, admin_h):
        year = make_year(client, admin_h, open_=False)
        start = int(year["year_code"][:4])
        assert client.post(f"{BASE}/years", json={"start_year": start}, headers=admin_h).status_code == 409

    def test_lifecycle_is_ordered(self, client, admin_h):
        year = make_year(client, admin_h, open_=False)
        pk = year["financial_year_pk"]
        assert raw_move(client, admin_h, "years", pk, "CLOSED").status_code == 422     # skipping steps
        for target in ("OPEN", "CLOSING", "CLOSED"):
            assert move(client, admin_h, "years", pk, target)["status"] == target
        assert raw_move(client, admin_h, "years", pk, "OPEN").status_code == 422        # no reopening (PENDING)

    def test_cannot_close_with_unfinished_transactions(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        make_txn(client, admin_h, w["year"], w["scope"])                               # stays DRAFT
        pk = w["year"]["financial_year_pk"]
        move(client, admin_h, "years", pk, "CLOSING")
        r = raw_move(client, admin_h, "years", pk, "CLOSED")
        assert r.status_code == 422 and "transaction" in r.text

    def test_scoped_admin_cannot_manage_years(self, client, sakha_admin_h):
        assert client.post(f"{BASE}/years", json={"start_year": 2095}, headers=sakha_admin_h).status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Scopes
# ═══════════════════════════════════════════════════════════════════════

class TestScopes:
    def test_scoped_admin_creates_in_own_organization(self, client, sakha_admin_h, register_org_pk):
        scope = make_scope(client, sakha_admin_h, register_org_pk)
        assert scope["status"] == "DRAFT" and scope["organization_pk"] == str(register_org_pk)

    def test_scoped_admin_cannot_create_in_foreign_organization(self, client, sakha_admin_h, other_org_pk):
        body = {"scope_code": "FSX1", "scope_name": "x", "scope_type": "ORGANIZATION", "organization_pk": str(other_org_pk)}
        assert client.post(f"{BASE}/scopes", json=body, headers=sakha_admin_h).status_code == 403

    def test_scope_without_organization_is_global_only(self, client, sakha_admin_h, admin_h):
        body = {"scope_code": "FSNOORG1", "scope_name": "x", "scope_type": "SPECIAL_PURPOSE"}
        assert client.post(f"{BASE}/scopes", json=body, headers=sakha_admin_h).status_code == 403
        assert client.post(f"{BASE}/scopes", json=body, headers=admin_h).status_code == 201

    def test_organization_scope_requires_organization(self, client, admin_h):
        body = {"scope_code": "FSBAD1", "scope_name": "x", "scope_type": "ORGANIZATION"}
        assert client.post(f"{BASE}/scopes", json=body, headers=admin_h).status_code == 422

    def test_unknown_type_and_duplicate_code(self, client, admin_h):
        assert client.post(f"{BASE}/scopes", json={"scope_code": "FSB2", "scope_name": "x", "scope_type": "NOPE"},
                           headers=admin_h).status_code == 422
        scope = make_scope(client, admin_h)
        dup = {"scope_code": scope["scope_code"], "scope_name": "again", "scope_type": "SPECIAL_PURPOSE"}
        assert client.post(f"{BASE}/scopes", json=dup, headers=admin_h).status_code == 409

    def test_activation_needs_approve(self, client, admin_h, sakha_admin_h, register_org_pk):
        scope = make_scope(client, sakha_admin_h, register_org_pk)
        assert raw_move(client, sakha_admin_h, "scopes", scope["financial_scope_pk"], "ACTIVE").status_code == 403
        assert move(client, admin_h, "scopes", scope["financial_scope_pk"], "ACTIVE")["status"] == "ACTIVE"

    def test_visibility_is_bounded_by_admin_scope(self, client, admin_h, other_admin_h, sakha_admin_h, register_org_pk):
        scope = make_scope(client, admin_h, register_org_pk)
        pk = scope["financial_scope_pk"]
        assert client.get(f"{BASE}/scopes/{pk}", headers=sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/scopes/{pk}", headers=other_admin_h).status_code == 403
        listed = client.get(f"{BASE}/scopes", params={"q": scope["scope_code"]}, headers=other_admin_h).json()
        assert listed["total"] == 0

    def test_parent_cannot_be_own_descendant(self, client, admin_h):
        parent = make_scope(client, admin_h)
        child = make_scope(client, admin_h, parent_scope_pk=parent["financial_scope_pk"])
        r = client.patch(f"{BASE}/scopes/{parent['financial_scope_pk']}",
                         json={"parent_scope_pk": child["financial_scope_pk"]}, headers=admin_h)
        assert r.status_code == 422

    def test_patch_renames(self, client, admin_h):
        scope = make_scope(client, admin_h)
        r = client.patch(f"{BASE}/scopes/{scope['financial_scope_pk']}", json={"scope_name": "Renamed"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["scope_name"] == "Renamed"


# ═══════════════════════════════════════════════════════════════════════
# Funds
# ═══════════════════════════════════════════════════════════════════════

class TestFunds:
    def test_restricted_fund_needs_a_purpose(self, client, admin_h):
        scope = make_scope(client, admin_h)
        body = {"fund_code": "FR1", "fund_name": "x", "fund_type": "SPECIFIC_PURPOSE",
                "financial_scope_pk": scope["financial_scope_pk"], "is_restricted": True}
        assert client.post(f"{BASE}/funds", json=body, headers=admin_h).status_code == 422
        body["restriction_purpose"] = "Temple repair"
        assert client.post(f"{BASE}/funds", json=body, headers=admin_h).status_code == 201

    def test_sinking_fund_needs_a_sakha(self, client, admin_h, register_org_pk):
        scope = make_scope(client, admin_h)
        body = {"fund_code": "SF1", "fund_name": "Sinking", "fund_type": "SINKING_FUND",
                "financial_scope_pk": scope["financial_scope_pk"]}
        assert client.post(f"{BASE}/funds", json=body, headers=admin_h).status_code == 422
        body["organization_pk"] = str(register_org_pk)
        r = client.post(f"{BASE}/funds", json=body, headers=admin_h)
        assert r.status_code == 201, r.text

    def test_duplicate_code_in_scope_is_409(self, client, admin_h):
        scope = make_scope(client, admin_h)
        fund = make_fund(client, admin_h, scope["financial_scope_pk"])
        dup = {"fund_code": fund["fund_code"], "fund_name": "again", "fund_type": "GENERAL",
               "financial_scope_pk": scope["financial_scope_pk"]}
        assert client.post(f"{BASE}/funds", json=dup, headers=admin_h).status_code == 409

    def test_fund_only_activates_in_an_active_scope(self, client, admin_h):
        scope = make_scope(client, admin_h)                                           # DRAFT
        fund = make_fund(client, admin_h, scope["financial_scope_pk"])
        assert raw_move(client, admin_h, "funds", fund["fund_master_pk"], "ACTIVE").status_code == 422
        move(client, admin_h, "scopes", scope["financial_scope_pk"], "ACTIVE")
        assert move(client, admin_h, "funds", fund["fund_master_pk"], "ACTIVE")["status"] == "ACTIVE"

    def test_restriction_locked_after_draft(self, client, admin_h):
        w = make_world(client, admin_h, None)
        r = client.patch(f"{BASE}/funds/{w['fund']['fund_master_pk']}", json={"is_restricted": True}, headers=admin_h)
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Transactions
# ═══════════════════════════════════════════════════════════════════════

class TestTransactions:
    def test_create_is_a_draft_with_a_minted_reference(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"], fund=w["fund"], amount="2500.50")
        assert txn["status"] == "DRAFT" and txn["transaction_reference"].startswith("FTX")
        assert txn["amount"] in ("2500.50", 2500.5)

    @pytest.mark.parametrize("amount", ["0", "-5", "1.234"])
    def test_bad_amounts_are_422(self, client, admin_h, register_org_pk, amount):
        w = make_world(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w, amount=amount)
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422

    def test_date_must_fall_inside_the_year(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w, txn_date="2001-01-01")
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422

    def test_needs_open_year_and_active_scope(self, client, admin_h, register_org_pk):
        planned = make_year(client, admin_h, open_=False)
        scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h)
        body = txn_body(client, admin_h, {"year": planned, "scope": scope})
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422   # year PLANNED
        year = make_year(client, admin_h)
        draft_scope = make_scope(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, {"year": year, "scope": draft_scope})
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422   # scope DRAFT

    def test_category_must_match_type(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w, kind="EXPENSE", code="PRANAMI_ANNUAL")      # an INCOME head on an expense
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422

    def test_fund_must_belong_to_the_scope(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        other = make_world(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w, fund=other["fund"])
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422

    def test_full_income_lifecycle(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"], fund=w["fund"])
        txn = post_txn(client, admin_h, txn)
        assert txn["status"] == "POSTED"
        assert move(client, admin_h, "transactions", txn["financial_transaction_pk"], "SETTLED")["status"] == "SETTLED"

    def test_only_drafts_are_editable(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        r = client.patch(f"{BASE}/transactions/{pk}", json={"amount": "75.00", "description": "edited"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["description"] == "edited"
        move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
        assert client.patch(f"{BASE}/transactions/{pk}", json={"amount": "1"}, headers=admin_h).status_code == 422

    def test_reject_and_cancel_need_remarks(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
        assert raw_move(client, admin_h, "transactions", pk, "REJECTED").status_code == 422
        assert move(client, admin_h, "transactions", pk, "REJECTED", remarks="Not covered by the scheme")["status"] == "REJECTED"
        assert raw_move(client, admin_h, "transactions", pk, "POSTED").status_code == 422   # terminal

    def test_posted_transaction_cannot_be_cancelled(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"]))
        r = raw_move(client, admin_h, "transactions", txn["financial_transaction_pk"], "CANCELLED", "oops")
        assert r.status_code == 422                                                         # reversal mechanism is PENDING

    def test_creator_cannot_approve_own_transaction(self, client, kendra_h, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, kendra_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        move(client, kendra_h, "transactions", pk, "PENDING_APPROVAL")
        assert raw_move(client, kendra_h, "transactions", pk, "APPROVED").status_code == 403   # maker-checker
        assert move(client, admin_h, "transactions", pk, "APPROVED")["status"] == "APPROVED"   # someone else may

    def test_super_admin_may_self_approve(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
        assert move(client, admin_h, "transactions", pk, "APPROVED")["status"] == "APPROVED"

    def test_scoped_admin_records_but_cannot_approve(self, client, admin_h, sakha_admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, sakha_admin_h, w["year"], w["scope"])
        pk = txn["financial_transaction_pk"]
        assert move(client, sakha_admin_h, "transactions", pk, "PENDING_APPROVAL")["status"] == "PENDING_APPROVAL"
        assert raw_move(client, sakha_admin_h, "transactions", pk, "APPROVED").status_code == 403

    def test_list_filters(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        make_txn(client, admin_h, w["year"], w["scope"], amount="11")
        make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE", amount="12")
        r = client.get(f"{BASE}/transactions", params={"financial_scope_pk": w["scope"]["financial_scope_pk"],
                                                       "transaction_type": "EXPENSE"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["total"] == 1


class TestRestrictedMoney:
    def _restricted_world(self, client, admin_h, org_pk):
        w = make_world(client, admin_h, org_pk)
        fund = make_fund(client, admin_h, w["scope"]["financial_scope_pk"], activate_with=admin_h, fund_type="SPECIFIC_PURPOSE",
                         is_restricted=True, restriction_purpose="Temple repair")
        return w, fund

    def test_specific_purpose_donation_needs_a_restricted_fund(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w, code="DONATION_SPECIFIC_PURPOSE")
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422
        body["fund_master_pk"] = w["fund"]["fund_master_pk"]                                 # general fund: still no
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422

    def test_restricted_expense_must_use_restricted_category(self, client, admin_h, register_org_pk):
        w, fund = self._restricted_world(client, admin_h, register_org_pk)
        body = txn_body(client, admin_h, w, kind="EXPENSE", code="EXPENSE_GENERAL", fund=fund)
        assert client.post(f"{BASE}/transactions", json=body, headers=admin_h).status_code == 422

    def test_restricted_expense_cannot_exceed_the_fund_balance(self, client, admin_h, register_org_pk):
        w, fund = self._restricted_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], fund=fund,
                                           category="DONATION_SPECIFIC_PURPOSE", amount="1000.00"))
        too_much = make_txn(client, admin_h, w["year"], w["scope"], fund=fund, kind="EXPENSE",
                            category="EXPENSE_RESTRICTED", amount="1500.00")
        pk = too_much["financial_transaction_pk"]
        move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
        r = raw_move(client, admin_h, "transactions", pk, "APPROVED")
        assert r.status_code == 422 and "exceeds" in r.text
        ok = make_txn(client, admin_h, w["year"], w["scope"], fund=fund, kind="EXPENSE",
                      category="EXPENSE_RESTRICTED", amount="400.00")
        assert post_txn(client, admin_h, ok)["status"] == "POSTED"
        funds = client.get(f"{BASE}/funds/{fund['fund_master_pk']}", headers=admin_h).json()
        assert float(funds["balance"]) == 600.0


# ═══════════════════════════════════════════════════════════════════════
# Receipts and payments (UPI is the demo payment method)
# ═══════════════════════════════════════════════════════════════════════

class TestReceipts:
    def _posted_income(self, client, admin_h, org_pk, amount="1000.00"):
        w = make_world(client, admin_h, org_pk)
        return post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], amount=amount))

    def test_upi_receipt_issue_and_cancel(self, client, admin_h, register_org_pk):
        txn = self._posted_income(client, admin_h, register_org_pk)
        pk = txn["financial_transaction_pk"]
        r = client.post(f"{BASE}/transactions/{pk}/receipts", headers=admin_h, json={
            "receipt_date": txn["transaction_date"], "amount": "1000.00", "received_from": "Devotee",
            "payment_method_code": "UPI", "instrument_reference": "UPI1234567890"})
        assert r.status_code == 201, r.text
        receipt = r.json()
        assert receipt["status"] == "DRAFT" and receipt["payment_method_code"] == "UPI"
        assert receipt["receipt_number"].startswith("RCT")
        rp = receipt["financial_receipt_pk"]
        assert client.post(f"{BASE}/receipts/{rp}/transition", json={"status": "ISSUED"}, headers=admin_h).json()["status"] == "ISSUED"
        assert client.get(f"{BASE}/transactions/{pk}", headers=admin_h).json()["receipted_amount"] in ("1000.00", 1000, 1000.0)
        assert client.post(f"{BASE}/receipts/{rp}/transition", json={"status": "CANCELLED"}, headers=admin_h).status_code == 422
        done = client.post(f"{BASE}/receipts/{rp}/transition", json={"status": "CANCELLED", "remarks": "Wrong payer"}, headers=admin_h)
        assert done.status_code == 200 and done.json()["cancellation_reason"] == "Wrong payer"

    def test_unknown_payment_method_is_422(self, client, admin_h, register_org_pk):
        txn = self._posted_income(client, admin_h, register_org_pk)
        r = client.post(f"{BASE}/transactions/{txn['financial_transaction_pk']}/receipts", headers=admin_h, json={
            "receipt_date": txn["transaction_date"], "amount": "10", "payment_method_code": "BARTER"})
        assert r.status_code == 422

    def test_receipts_cannot_exceed_the_transaction(self, client, admin_h, register_org_pk):
        txn = self._posted_income(client, admin_h, register_org_pk, amount="100.00")
        url = f"{BASE}/transactions/{txn['financial_transaction_pk']}/receipts"
        payload = {"receipt_date": txn["transaction_date"], "amount": "60.00"}
        assert client.post(url, json=payload, headers=admin_h).status_code == 201
        assert client.post(url, json=payload, headers=admin_h).status_code == 422

    def test_draft_or_expense_transactions_take_no_receipt(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        draft = make_txn(client, admin_h, w["year"], w["scope"])
        expense = post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE"))
        for t in (draft, expense):
            r = client.post(f"{BASE}/transactions/{t['financial_transaction_pk']}/receipts", headers=admin_h,
                            json={"receipt_date": t["transaction_date"], "amount": "10"})
            assert r.status_code == 422


class TestPayments:
    def test_upi_payment_lifecycle(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE", amount="500.00")
        pk = txn["financial_transaction_pk"]
        move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
        move(client, admin_h, "transactions", pk, "APPROVED")
        r = client.post(f"{BASE}/transactions/{pk}/payments", headers=admin_h, json={
            "payment_date": txn["transaction_date"], "amount": "500.00", "paid_to": "Priest",
            "payment_method_code": "UPI", "instrument_reference": "UPI998877"})
        assert r.status_code == 201, r.text
        payment = r.json()
        assert payment["payment_reference"].startswith("PAY") and payment["payment_method_code"] == "UPI"
        pp = payment["financial_payment_pk"]
        for target in ("APPROVED", "INITIATED", "COMPLETED"):
            assert move(client, admin_h, "payments", pp, target)["status"] == target
        assert float(client.get(f"{BASE}/transactions/{pk}", headers=admin_h).json()["paid_amount"]) == 500.0

    def test_payment_needs_an_approved_expense(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        draft = make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE")
        r = client.post(f"{BASE}/transactions/{draft['financial_transaction_pk']}/payments", headers=admin_h,
                        json={"payment_date": draft["transaction_date"], "amount": "10"})
        assert r.status_code == 422

    def test_payments_cannot_exceed_the_transaction(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE", amount="100.00"))
        url = f"{BASE}/transactions/{txn['financial_transaction_pk']}/payments"
        body = {"payment_date": txn["transaction_date"], "amount": "70.00"}
        assert client.post(url, json=body, headers=admin_h).status_code == 201
        assert client.post(url, json=body, headers=admin_h).status_code == 422

    def test_payment_approval_is_maker_checker(self, client, kendra_h, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE", amount="100.00"))
        payment = client.post(f"{BASE}/transactions/{txn['financial_transaction_pk']}/payments", headers=kendra_h,
                              json={"payment_date": txn["transaction_date"], "amount": "100.00"}).json()
        pp = payment["financial_payment_pk"]
        assert raw_move(client, kendra_h, "payments", pp, "APPROVED").status_code == 403
        assert move(client, admin_h, "payments", pp, "APPROVED")["status"] == "APPROVED"


# ═══════════════════════════════════════════════════════════════════════
# Transfers
# ═══════════════════════════════════════════════════════════════════════

class TestTransfers:
    def _body(self, w1, w2, amount="100.00", **over):
        body = {"financial_year_pk": w1["year"]["financial_year_pk"], "source_scope_pk": w1["scope"]["financial_scope_pk"],
                "destination_scope_pk": w2["scope"]["financial_scope_pk"], "amount": amount,
                "transfer_date": w1["year"]["start_date"], "purpose": "Annual grant to Mahila Sangha"}
        body.update(over)
        return body

    def test_same_scope_is_422(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        assert client.post(f"{BASE}/transfers", json=self._body(w, w), headers=admin_h).status_code == 422

    def test_transfer_moves_fund_balances(self, client, admin_h, register_org_pk):
        w1 = make_world(client, admin_h, register_org_pk)
        w2 = make_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, w1["year"], w1["scope"], fund=w1["fund"], amount="1000.00"))
        body = self._body(w1, w2, amount="400.00", source_fund_pk=w1["fund"]["fund_master_pk"],
                          destination_fund_pk=w2["fund"]["fund_master_pk"])
        r = client.post(f"{BASE}/transfers", json=body, headers=admin_h)
        assert r.status_code == 201, r.text
        tr = r.json()
        assert tr["status"] == "DRAFT" and tr["transfer_reference"].startswith("FTR")
        pk = tr["financial_transfer_pk"]
        for target in ("PENDING_APPROVAL", "APPROVED", "EXECUTED", "COMPLETED"):
            assert move(client, admin_h, "transfers", pk, target)["status"] == target
        src = client.get(f"{BASE}/funds/{w1['fund']['fund_master_pk']}", headers=admin_h).json()
        dst = client.get(f"{BASE}/funds/{w2['fund']['fund_master_pk']}", headers=admin_h).json()
        assert float(src["balance"]) == 600.0 and float(dst["balance"]) == 400.0

    def test_cannot_take_more_than_the_source_fund_holds(self, client, admin_h, register_org_pk):
        w1 = make_world(client, admin_h, register_org_pk)
        w2 = make_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, w1["year"], w1["scope"], fund=w1["fund"], amount="50.00"))
        tr = client.post(f"{BASE}/transfers", json=self._body(w1, w2, amount="80.00", source_fund_pk=w1["fund"]["fund_master_pk"]),
                         headers=admin_h).json()
        pk = tr["financial_transfer_pk"]
        move(client, admin_h, "transfers", pk, "PENDING_APPROVAL")
        r = raw_move(client, admin_h, "transfers", pk, "APPROVED")
        assert r.status_code == 422 and "exceeds" in r.text

    def test_needs_scope_over_both_ends(self, client, admin_h, sakha_admin_h, register_org_pk, other_org_pk):
        mine = make_world(client, admin_h, register_org_pk)
        foreign = make_world(client, admin_h, other_org_pk)
        assert client.post(f"{BASE}/transfers", json=self._body(mine, foreign), headers=sakha_admin_h).status_code == 403

    def test_approval_is_maker_checker(self, client, kendra_h, admin_h, register_org_pk):
        w1 = make_world(client, admin_h, register_org_pk)
        w2 = make_world(client, admin_h, register_org_pk)
        tr = client.post(f"{BASE}/transfers", json=self._body(w1, w2), headers=kendra_h).json()
        pk = tr["financial_transfer_pk"]
        move(client, kendra_h, "transfers", pk, "PENDING_APPROVAL")
        assert raw_move(client, kendra_h, "transfers", pk, "APPROVED").status_code == 403
        assert move(client, admin_h, "transfers", pk, "APPROVED")["status"] == "APPROVED"


# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════

class TestSummary:
    def test_totals_follow_posted_transactions_only(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], fund=w["fund"], amount="1000.00"))
        post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], fund=w["fund"], kind="EXPENSE", amount="250.00"))
        make_txn(client, admin_h, w["year"], w["scope"], amount="999.00")                  # draft: not counted
        r = client.get(f"{BASE}/summary", params={"financial_year_pk": w["year"]["financial_year_pk"],
                                                  "financial_scope_pk": w["scope"]["financial_scope_pk"]}, headers=admin_h)
        assert r.status_code == 200, r.text
        s = r.json()
        assert float(s["income_total"]) == 1000.0 and float(s["expense_total"]) == 250.0 and float(s["net"]) == 750.0
        assert s["draft_transactions"] == 1
        fund_row = next(f for f in s["by_fund"] if f["fund_master_pk"] == w["fund"]["fund_master_pk"])
        assert float(fund_row["balance"]) == 750.0

    def test_scoped_admin_sees_only_own_scopes(self, client, admin_h, other_admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, w["year"], w["scope"], fund=w["fund"], amount="1000.00"))
        params = {"financial_year_pk": w["year"]["financial_year_pk"]}
        # the foreign admin cannot even ask about this scope ...
        r = client.get(f"{BASE}/summary", params={**params, "financial_scope_pk": w["scope"]["financial_scope_pk"]}, headers=other_admin_h)
        assert r.status_code == 403
        # ... and its fund never shows in their year-wide summary (the year may be shared with other tests' data)
        s = client.get(f"{BASE}/summary", params=params, headers=other_admin_h).json()
        assert all(f["fund_master_pk"] != w["fund"]["fund_master_pk"] for f in s["by_fund"])


# ═══════════════════════════════════════════════════════════════════════
# Member-facing: "My Pranami" (GET /finance/my-pranami, login only)
# ═══════════════════════════════════════════════════════════════════════

class TestMyPranami:
    def _pranami(self, client, admin_h_, world, member, *, category="PRANAMI_ANNUAL", amount="500.00", post=True, kind="INCOME"):
        txn = make_txn(client, admin_h_, world["year"], world["scope"], kind=kind, category=category, amount=amount,
                       sangha_sevi_id=member["sangha_sevi_id"])
        return post_txn(client, admin_h_, txn) if post else txn

    def test_member_sees_their_own_posted_pranami_with_upi_receipt(self, client, admin_h, plain_member, plain_member_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = self._pranami(client, admin_h, w, plain_member)
        pk = txn["financial_transaction_pk"]
        assert txn["sangha_sevi_id"] == plain_member["sangha_sevi_id"] and txn["person_pk"]      # the id resolved both links
        r = client.post(f"{BASE}/transactions/{pk}/receipts", headers=admin_h, json={
            "receipt_date": txn["transaction_date"], "amount": "500.00", "payment_method_code": "UPI",
            "instrument_reference": "UPI5550001"})
        assert r.status_code == 201, r.text
        issued = client.post(f"{BASE}/receipts/{r.json()['financial_receipt_pk']}/transition", json={"status": "ISSUED"}, headers=admin_h)
        assert issued.status_code == 200, issued.text
        draft = client.post(f"{BASE}/transactions/{pk}/receipts", headers=admin_h,
                            json={"receipt_date": txn["transaction_date"], "amount": "1.00"})   # a second DRAFT: must not show
        assert draft.status_code == 422                                                         # (500 already receipted: cap)

        body = client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()
        assert body["sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        mine = [i for i in body["items"] if i["financial_transaction_pk"] == pk]
        assert len(mine) == 1
        item = mine[0]
        assert item["transaction_category"] == "PRANAMI_ANNUAL" and float(item["amount"]) == 500.0 and item["status"] == "POSTED"
        assert [x["receipt_number"][:3] for x in item["receipts"]] == ["RCT"]
        assert item["receipts"][0]["payment_method_name"] == "UPI" and item["receipts"][0]["instrument_reference"] == "UPI5550001"

    def test_draft_receipts_are_not_shown(self, client, admin_h, plain_member, plain_member_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = self._pranami(client, admin_h, w, plain_member)
        client.post(f"{BASE}/transactions/{txn['financial_transaction_pk']}/receipts", headers=admin_h,
                    json={"receipt_date": txn["transaction_date"], "amount": "100.00"})          # stays DRAFT
        item = next(i for i in client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]
                    if i["financial_transaction_pk"] == txn["financial_transaction_pk"])
        assert item["receipts"] == []

    def test_only_counted_pranami_of_the_right_kind_is_shown(self, client, admin_h, plain_member, plain_member_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        shown = self._pranami(client, admin_h, w, plain_member, category="PRANAMI_SPECIAL")
        hidden = [
            self._pranami(client, admin_h, w, plain_member, post=False),                         # DRAFT
            self._pranami(client, admin_h, w, plain_member, category="DONATION_GENERAL"),        # not Pranami
            self._pranami(client, admin_h, w, plain_member, kind="EXPENSE", category="EXPENSE_GENERAL"),
        ]
        items = client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]
        refs = {i["transaction_reference"] for i in items}
        assert shown["transaction_reference"] in refs
        for h in hidden:
            assert h["transaction_reference"] not in refs
        assert {i["transaction_category"] for i in items} <= {"PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND"}
        assert all(i["status"] in ("POSTED", "SETTLED") for i in items)

    def test_a_member_never_sees_another_members_pranami(self, client, admin_h, plain_member, plain_member_h, write_conn, register_org_pk):
        other = new_member(write_conn, register_org_pk, "FinOther")
        other_h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        w = make_world(client, admin_h, register_org_pk)
        theirs = self._pranami(client, admin_h, w, other)
        mine_refs = {i["transaction_reference"] for i in client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"]}
        their_refs = {i["transaction_reference"] for i in client.get(f"{BASE}/my-pranami", headers=other_h).json()["items"]}
        assert theirs["transaction_reference"] in their_refs
        assert theirs["transaction_reference"] not in mine_refs

    def test_response_exposes_only_the_documented_fields(self, client, admin_h, plain_member, plain_member_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        self._pranami(client, admin_h, w, plain_member)
        item = client.get(f"{BASE}/my-pranami", headers=plain_member_h).json()["items"][0]
        assert set(item) == {"financial_transaction_pk", "transaction_reference", "transaction_date", "year_code",
                             "transaction_category", "finance_head_name", "amount", "scope_name", "organization_name", "status", "receipts"}


class TestLinkingAMember:
    def _body(self, client, headers, w, **over):
        # the world's scope belongs to a Sangha, so the head must be that Sangha's own (the templates were adopted into it)
        body = txn_body(client, headers, w, amount="10")
        body.update(over)
        return body

    def test_unknown_member_id_is_422(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        r = client.post(f"{BASE}/transactions", json=self._body(client, admin_h, w, sangha_sevi_id="SS999999999"), headers=admin_h)
        assert r.status_code == 422

    def test_member_must_be_inside_the_admins_scope(self, client, admin_h, other_admin_h, plain_member, other_org_pk):
        w = make_world(client, admin_h, other_org_pk)                     # a scope the foreign admin may use ...
        r = client.post(f"{BASE}/transactions", json=self._body(client, admin_h, w, sangha_sevi_id=plain_member["sangha_sevi_id"]), headers=other_admin_h)
        assert r.status_code == 403                                       # ... but not this member (they belong to the other Sakha)

    def test_draft_can_be_relinked_and_unlinked(self, client, admin_h, plain_member, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"], category="PRANAMI_ANNUAL")
        pk = txn["financial_transaction_pk"]
        assert txn["sangha_sevi_id"] is None
        linked = client.patch(f"{BASE}/transactions/{pk}", json={"sangha_sevi_id": plain_member["sangha_sevi_id"]}, headers=admin_h)
        assert linked.status_code == 200 and linked.json()["sangha_sevi_id"] == plain_member["sangha_sevi_id"]
        cleared = client.patch(f"{BASE}/transactions/{pk}", json={"sangha_sevi_id": None}, headers=admin_h)
        assert cleared.status_code == 200 and cleared.json()["sangha_sevi_id"] is None and cleared.json()["person_pk"] is None
