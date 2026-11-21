"""
Sakha approval chain UI (owner decision 2026-11-17) - DB-free source and node checks, runnable with ``--noconftest``:

  * admin console: bills + approval status on a transaction, the Treasurer's default limit, the head flags;
  * member dashboard: the "Finance approvals" tab the Treasurer / President / Secretary decide from;
  * what the pages send is what the API accepts; the page decides nothing about WHO may approve (the server checks the seat).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
FIN_JS = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
SETUP_JS = (FE / "assets/js/finance-setup.js").read_text(encoding="utf-8")
DASH_JS = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
DASH_HTML = (FE / "dashboard.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _approvals_panel() -> str:
    return _between(DASH_HTML, "<!-- ── Finance approvals", "<div x-show=\"tab === 'documents'\">")


def _txn_cards() -> str:
    return _between(ADMIN_HTML, "<!-- Sakha approval chain (owner 2026-11-17)", "<!-- Receipts (income) -->")


class TestApproverPage:
    def test_nav_item_and_panel_exist_and_the_item_hides_when_nothing_waits(self):
        assert "switchTab('finApprovals')" in DASH_HTML
        assert 'x-show="finApprovalsCount() > 0 || tab === \'finApprovals\'"' in DASH_HTML
        assert 'x-show="tab === \'finApprovals\'"' in DASH_HTML

    def test_the_page_has_no_inline_handlers_or_forms_and_takes_no_model_input(self):
        panel = _approvals_panel()
        assert not re.search(r"\son[a-z]+\s*=", panel) and "<form" not in panel and 'x-init="init()"' not in panel
        assert "x-model" not in panel                                         # remarks are read with :value / @input, like the pay cards

    def test_every_field_it_reads_exists_in_the_api_model(self):
        from api.schemas.finance import ApprovalStepResponse, BillResponse, MyApprovalItem

        panel = _approvals_panel()
        for field in set(re.findall(r"\bit\.([a-z_]+)", panel)):
            assert field in MyApprovalItem.model_fields, field
        for field in set(re.findall(r"\bb\.([a-z_]+)", panel)):
            assert field in BillResponse.model_fields, field
        for field in set(re.findall(r"\bst\.([a-z_]+)", panel)):
            assert field in ApprovalStepResponse.model_fields, field

    def test_a_bill_link_is_only_rendered_through_the_https_check(self):
        panel = _approvals_panel()
        for href in re.findall(r':href="([^"]+)"', panel):
            assert href.startswith("pranamiSafeUrl("), href
        assert 'rel="noopener noreferrer"' in panel
        assert not re.search(r'[^:]href="(?!#)', panel)

    def test_the_decision_posts_only_remarks_to_the_real_routes(self):
        body = _between(DASH_JS, "async finApprovalDecide(item, decision)", "pranamiLatestDate()")
        assert "/api/v1/finance/transactions/${pk}/" in body and '"approve"' in body and '"reject"' in body
        assert "JSON.stringify({ remarks: remarks || null })" in body
        for forbidden in ("person", "sangha_sevi", "position", "step"):
            assert forbidden not in body, forbidden                            # who / which step is the server's decision

    def test_a_rejection_needs_a_reason_before_anything_is_sent(self):
        body = _between(DASH_JS, "async finApprovalDecide(item, decision)", "pranamiLatestDate()")
        assert 'decision === "REJECTED" && !remarks' in body and body.index('!remarks') < body.index("apiFetch")

    def test_the_list_is_loaded_for_everyone_and_refreshed_live(self):
        assert "this._loadFinApprovals({ silent: true });" in DASH_JS
        assert re.search(r'finApprovals: \{ reload: \(h\) => h\._loadFinApprovals\(\{ silent: true \}\), busy: \(h\) => !!h\.finApprovals\.acting \}', DASH_JS)
        block = DASH_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        assert 'finance_approval_step: ["finApprovals"]' in block and 'finance_transaction_bill: ["finApprovals"]' in block

    def test_the_endpoint_the_page_calls_is_login_only(self):
        from api.main import app

        route = next(r for r in app.routes if getattr(r, "path", "") == "/api/v1/finance/my-approvals")
        assert "get_current_user" in {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}


class TestAdminTransactionDetail:
    def test_the_cards_read_only_fields_the_api_returns(self):
        from api.schemas.finance import ApprovalState, BillResponse

        cards = _txn_cards()
        for field in set(re.findall(r"\bfinApproval\.([a-z_]+)", cards)):
            assert field in ApprovalState.model_fields, field
        for field in set(re.findall(r"\bb\.([a-z_]+)", cards)):
            assert field in BillResponse.model_fields, field

    def test_the_bill_form_sends_what_the_api_accepts(self):
        from api.schemas.finance import BillCreate

        body = _between(FIN_JS, "async finSubmitBill()", "async finRemoveBill(b)")
        sent = set(re.findall(r"\b(vendor_name|bill_number|bill_date|amount|document_url|description):", body))
        assert sent == {"vendor_name", "bill_number", "bill_date", "amount", "document_url", "description"} and sent <= set(BillCreate.model_fields)
        assert "/bills`" in body and "https:" in body

    def test_bills_can_change_only_on_a_draft_spend_by_a_recorder(self):
        getter = _between(FIN_JS, "get finBillsEditable()", "// \"Treasurer approves alone")
        assert "canManageFinance" in getter and '"EXPENSE"' in getter and '"DRAFT"' in getter
        assert 'x-show="finBillsEditable && !finBillForm.show"' in _txn_cards()

    def test_a_removed_bill_calls_delete_and_a_204_is_not_parsed_as_json(self):
        assert '"DELETE"' in FIN_JS and "res.status === 204 ? null : res.json()" in FIN_JS

    def test_the_ordinary_approve_button_is_hidden_for_a_sakha_entry(self):
        body = _between(FIN_JS, "finActions(entity, status)", "finAskTransition")
        assert 'entity === "transaction" && t.to === "APPROVED" && this.finApproval && this.finApproval.applies' in body

    def test_the_page_never_decides_who_may_approve(self):
        assert not re.search(r"(person_pk|currentUser)[^\n]*(TREASURER|SECRETARY|PRESIDENT)", FIN_JS + SETUP_JS)
        assert "isTreasurer" not in FIN_JS + SETUP_JS + DASH_JS

    def test_bill_links_are_only_rendered_through_the_scheme_check(self):
        cards = _txn_cards()
        for href in re.findall(r':href="([^"]+)"', cards):
            assert href.startswith("finBillSafeUrl("), href
        assert 'rel="noopener noreferrer"' in cards

    def test_the_new_live_tables_are_mapped_to_screens_that_exist(self):
        block = ADMIN_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        assert re.search(r'finance_transaction_bill: \["finTransactions"\]', block) and re.search(r'finance_approval_step: \["finTransactions"\]', block)
        assert re.search(r'finance_approval_policy: \["finSetup"\]', block)

    def test_an_open_bill_form_counts_as_busy_for_live_refresh(self):
        assert "this.finBillForm]" in FIN_JS


class TestLimitAndHeadFlags:
    def test_the_limit_card_belongs_to_a_sakha_and_needs_the_configure_permission(self):
        card = _between(ADMIN_HTML, "<!-- The Treasurer's default approval limit", "<!-- Simple contribution form")
        assert 'x-show="finPolicyApplies && finSetupMore"' in card and 'x-show="canConfigureFinance && !finControlsLocked"' in card
        assert ':disabled="!canConfigureFinance || finControlsLocked"' in card           # owner 2026-11-20: not for a user who is only the Treasurer
        assert "(NSS.SAKHA_LIKE_ORG_TYPES || []).includes(o.type_code)" in SETUP_JS            # never a hard-coded Sakha type

    def test_the_limit_is_saved_through_the_real_route(self):
        body = _between(SETUP_JS, "async finPolicySave()", "// ")
        assert '"PUT", "/approval-policy"' in body and "default_treasurer_limit" in body
        from api.schemas.finance import ApprovalPolicyWrite

        assert {"organization_pk", "default_treasurer_limit"} <= set(ApprovalPolicyWrite.model_fields)

    def test_the_head_form_binds_the_new_flags_the_api_accepts(self):
        from api.schemas.finance import HeadCreate, HeadUpdate

        form = _between(ADMIN_HTML, "<!-- Heads list -->", "<!-- Account form -->") if "<!-- Heads list -->" in ADMIN_HTML else ADMIN_HTML
        bound = {m.split(".")[1] for m in re.findall(r'x-model="(finHeadForm\.[a-z_0-9.]+)"', ADMIN_HTML)}
        assert {"skips_approval", "treasurer_limit", "requires_member"} <= bound
        known = set(HeadCreate.model_fields) | set(HeadUpdate.model_fields)
        assert {"skips_approval", "treasurer_limit", "requires_member"} <= known

    def test_income_sends_only_the_income_flag_and_a_spend_only_the_expense_flags(self):
        body = _between(SETUP_JS, "async finHeadSubmit()", "// ── Contributions")
        assert 'f.direction === "INCOME"' in body and "{ skips_approval: f.skips_approval }" in body
        assert "{ treasurer_limit: limit, requires_member: f.requires_member }" in body

    def test_the_rules_badges_describe_the_flags(self):
        assert '"No approval needed"' in SETUP_JS and "Treasurer up to" in SETUP_JS and '"Names the member"' in SETUP_JS


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestApproverHelpersUnderNode:
    def _run(self, expr: str):
        helpers = _between(DASH_JS, "        finApprovalsCount() {", "        async finApprovalDecide(item, decision) {")
        helpers = "finApprovalsCount() {" + helpers
        script = f"""
        const NSS = {{ formatMoney: (v) => "Rs " + Number(v).toFixed(2) }};
        const t = {{ finApprovals: {{ items: [1, 2, 3] }}, {helpers} }};
        console.log(JSON.stringify({expr}));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_the_count(self):
        assert self._run("t.finApprovalsCount()") == 3

    @pytest.mark.parametrize("code, label", [("TREASURER", "Treasurer"), ("PRESIDENT", "President"), ("SECRETARY", "Secretary")])
    def test_the_office_label(self, code, label):
        assert self._run(f't.finApprovalOffice({{ position_code: "{code}" }})') == label

    def test_the_rule_text_for_each_situation(self):
        alone = self._run('t.finApprovalRuleText({ requires: "TREASURER", stage: 1, limit: "5000" })')
        assert "only one needed" in alone and "Rs 5000.00" in alone
        first = self._run('t.finApprovalRuleText({ requires: "TREASURER_THEN_PRESIDENT", stage: 1, cover_reason: null })')
        assert "Step 1 of 2" in first and "President" in first
        second = self._run('t.finApprovalRuleText({ requires: "TREASURER_THEN_PRESIDENT", stage: 2, cover_reason: null })')
        assert "Step 2 of 2" in second and "Treasurer has approved" in second
        cover = self._run('t.finApprovalRuleText({ requires: "TREASURER_THEN_PRESIDENT", stage: 2, cover_reason: "PRESIDENT_SEAT_VACANT" })')
        assert "no President is seated" in cover and "as Secretary" in cover
