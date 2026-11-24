"""
Finance "Sinking Fund dues" tab (Bye-Law C(i)(2)(xviii), FIN-BR-026; frontend/assets/js/finance-sinking.js) - DB-free: source parsing plus the pure
getters run under node. Nothing opened in a browser.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from api.schemas.finance import (SinkingExpenditureOption, SinkingReimbursementDetail, SinkingReimbursementEntry,
                                 SinkingReimbursementResponse)

FE = Path(__file__).resolve().parents[2] / "frontend"
JS = (FE / "assets/js/finance-sinking.js").read_text(encoding="utf-8")
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
FIN_JS = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
HTML = (FE / "admin.html").read_text(encoding="utf-8")
CONFIG = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")


def _panel() -> str:
    start = HTML.index("VIEW: Finance - Sinking Fund reimbursement")
    return HTML[start:HTML.index("<!-- ═════════ Transactions ═════════ -->", start)]


class TestWiring:
    def test_the_tab_is_in_every_list_that_names_the_finance_tabs(self):
        assert '"finSinking"' in re.search(r"const FINANCE_TABS = \[.*?\];", ADMIN_JS).group(0)
        assert re.search(r'finSinking: "[^"]+"', ADMIN_JS)                                             # the banner title
        assert "activeTab === 'finSinking'" in HTML and "finEnterTab('finSinking')" in HTML
        assert "'finSinking'" in re.search(r"x-show=\"\['finOverview'[^\"]*\"", HTML).group(0)         # the year strip's wrapper
        assert 'finSinking: () => this.canViewFinance && this.finEnterTab("finSinking")' in ADMIN_JS      # the #hash route
        assert re.search(r"finSinking: \{ reload: \(h\) => h\.finLiveReload\(\), busy: \(h\) => h\.finLiveBusy\(\) \}", ADMIN_JS)

    def test_the_live_feed_reaches_the_tab(self):
        block = ADMIN_JS[ADMIN_JS.index("financial_year:"):]
        assert 'finance_sinking_reimbursement: ["finSinking"]' in block and 'finance_sinking_reimbursement_entry: ["finSinking"]' in block
        assert re.search(r'financial_transaction: \[[^\]]*"finSinking"', block)                         # what is posted counts as reimbursed
        assert re.search(r'financial_year: \[[^\]]*"finSinking"', block)

    def test_finance_js_enters_reloads_and_guards_the_tab(self):
        assert 'this.activeTab === "finSinking"' in FIN_JS and "await this.finSinkingEnter();" in FIN_JS
        assert 'tab === "finSinking"' in FIN_JS and "this.finSinkingReload()" in FIN_JS and "this.finSinkingBusy()" in FIN_JS

    def test_the_mixin_is_loaded_and_installed(self):
        assert '<script src="/assets/js/finance-sinking.js"></script>' in HTML
        assert "NSSFinanceSinking.install(NSSFinanceBudget.install(" in ADMIN_JS
        assert "}))))))))), LIVE_REFRESH_CONFIG);" in ADMIN_JS

    def test_the_new_statuses_have_labels_and_badges(self):
        for status in ("PARTLY_REIMBURSED", "REIMBURSED"):
            assert f"{status}:" in CONFIG
        assert 'PARTLY_REIMBURSED: "badge-fin-pending"' in CONFIG and 'REIMBURSED: "badge-fin-done"' in CONFIG


class TestPanelAgreesWithTheMixinAndTheApi:
    def test_every_identifier_the_panel_uses_is_defined(self):
        defined = set(re.findall(r"\b(finSinking[A-Za-z]*)\s*[(:]", JS)) | set(re.findall(r"\bget (finSinking[A-Za-z]*)\(", JS))
        used = set(re.findall(r"\b(finSinking[A-Za-z]*)\b", _panel()))
        assert used - defined - {"finSinking"} == set(), used - defined          # "finSinking" alone is the open record AND the tab name

    def test_the_fields_the_panel_reads_exist_in_the_api_models(self):
        panel = _panel()
        for var, model in (("finSinking", SinkingReimbursementDetail), ("r", SinkingReimbursementResponse), ("e", SinkingReimbursementEntry),
                           ("o", SinkingExpenditureOption)):
            for field in set(re.findall(rf"\b{var}\.([a-z_]+)", panel)):
                if field in ("length", "reimbursements") and var != "finSinking":
                    continue
                assert field in model.model_fields or field == "length", (var, field)

    def test_the_mixin_calls_only_routes_the_router_has(self):
        from api.routers.finance_sinking import router

        paths = {r.path.replace("/api/v1/finance", "") for r in router.routes}
        for literal in set(re.findall(r'"(/sinking-reimbursements[^"`?]*)"', JS)):
            assert literal in paths or literal.rstrip("/") in paths, literal
        for template in set(re.findall(r"`(/sinking-reimbursements/\$\{pk\}[^`?]*)`", JS)):
            assert template.replace("${pk}", "{pk}") in paths, template

    def test_only_someone_who_may_act_sees_the_buttons(self):
        panel = _panel()
        assert "get finSinkingCanAct() { return this.canManageFinance && this.finKendraSide; }" in JS
        assert panel.count("finSinkingCanAct") >= 3
        assert 'x-show="finSinkingCanAct && !finSinkingRegister.show"' in panel

    def test_a_remove_is_offered_only_while_nothing_has_been_paid_back(self):
        assert "finSinkingCanAct && finSinking.reimbursements.length === 0" in _panel()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
class TestUnderNode:
    def _run(self, body: str):
        start = JS.index("function financeSinkingMixin() {")
        end = JS.index("    window.NSSFinanceSinking")
        script = f"""
        const NSS = {{ financeStatusLabel: (s) => "L:" + s }};
        const newRegister = () => ({{}}), newPay = () => ({{}}), newRemove = () => ({{}});
        const LABELS = {{ OPEN: "Owed", PARTLY_REIMBURSED: "Part reimbursed", REIMBURSED: "Reimbursed" }};
        {JS[start:end].rstrip()}
        const host = financeSinkingMixin();
        Object.defineProperty(host, "canManageFinance", {{ value: true }});
        host.finKendraSide = false;
        {body}
        """
        done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_labels_the_total_owed_and_the_room_left(self):
        out = self._run("""
            const r = {};
            r.labels = ["OPEN", "PARTLY_REIMBURSED", "REIMBURSED", "X"].map((s) => host.finSinkingLabel(s));
            host.finSinkings = [{ outstanding_amount: "700.00" }, { outstanding_amount: "0.00" }, { outstanding_amount: "50.25" }];
            r.owed = host.finSinkingOwed;
            host.finSinking = { amount_due: "1000.00", reimbursed_amount: "300.00", pending_amount: "200.00" }; r.room = host.finSinkingRoom;
            host.finSinking = { amount_due: "1000.00", reimbursed_amount: "900.00", pending_amount: "300.00" }; r.none = host.finSinkingRoom;
            host.finSinking = null; r.noRecord = host.finSinkingRoom;
            // the whole tab is the Kendra's procedure: acting needs the Kendra's side AND the permission
            host.finKendraSide = true; r.kendra = host.finSinkingCanAct; host.finKendraSide = false; r.sakha = host.finSinkingCanAct;
            console.log(JSON.stringify(r));
        """)
        assert out == {"labels": ["Owed", "Part reimbursed", "Reimbursed", "L:X"], "owed": "750.25", "room": 500, "none": 0, "noRecord": 0, "kendra": True, "sakha": False}


class TestSakhaByTheKendrasPage:
    def test_the_page_shows_the_sakha_table_the_waiting_spend_and_a_sakha_filter(self):
        panel = _panel()
        assert "Sakha by Sakha" in panel and 'x-for="s in finSinkingSummary"' in panel and "finSinkingPickSakha(s.sakha_organization_pk)" in panel
        assert "Spent from a Sinking Fund, not registered yet" in panel and 'x-for="o in finSinkingWaiting"' in panel
        assert 'x-model="finSinkingSakha"' in panel and "finSinkingRegisterOpen(o.financial_transaction_pk)" in panel
        assert "/sinking-reimbursements/summary" in JS and "organization_pk = this.finSinkingSakha" in JS.replace("params.organization_pk", "organization_pk")

    def test_the_summary_fields_the_panel_reads_exist_in_the_model(self):
        from api.schemas.finance import SinkingSakhaSummary

        for field in set(re.findall(r"\bs\.([a-z_]+)", _panel())):
            assert field in SinkingSakhaSummary.model_fields, field


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
class TestTheExpenseFormNamesTheSakha:
    """Owner 2026-11-24: adding an expense must name the Sakha when the money comes from a Sinking Fund (finance.js)."""

    def _run(self, body: str):
        fin = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
        start = fin.index("            get finTxnSakhaChoices() {")
        end = fin.index("            finTxnFormTypeChanged() {")
        script = f"""
        const host = {{ finTxnForm: {{ transaction_type: "EXPENSE", sakha_pk: "", fund_master_pk: "" }}, finTxnFormFunds: [], {fin[start:end].rstrip().rstrip(",")} }};
        const fund = (pk, type, org, name) => ({{ fund_master_pk: pk, fund_type: type, organization_pk: org, organization_name: name }});
        const r = {{}};
        {body}
        console.log(JSON.stringify(r));
        """
        done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_sakha_field_appears_only_for_an_expense_in_a_scope_with_sinking_funds(self):
        out = self._run("""
            host.finTxnFormFunds = [fund("f1", "GENERAL", null, null), fund("f2", "SINKING_FUND", "s2", "Utkal Sakha"), fund("f3", "SINKING_FUND", "s1", "Ekamra Sakha")];
            r.needs = host.finTxnNeedsSakha; r.choices = host.finTxnSakhaChoices.map((c) => c.organization_name);
            host.finTxnForm.transaction_type = "INCOME"; r.income = host.finTxnNeedsSakha;
            host.finTxnForm.transaction_type = "EXPENSE"; host.finTxnFormFunds = [fund("f1", "GENERAL", null, null)]; r.noSinking = host.finTxnNeedsSakha;
        """)
        assert out == {"needs": True, "choices": ["Ekamra Sakha", "Utkal Sakha"], "income": False, "noSinking": False}

    def test_choosing_a_sakha_narrows_the_funds_and_choosing_a_sinking_fund_fills_the_sakha_in(self):
        out = self._run("""
            host.finTxnFormFunds = [fund("f1", "GENERAL", null, null), fund("f2", "SINKING_FUND", "s2", "Utkal Sakha"), fund("f3", "SINKING_FUND", "s1", "Ekamra Sakha")];
            r.all = host.finTxnFundChoices.length;
            host.finTxnForm.sakha_pk = "s1"; host.finTxnSakhaChanged(); r.narrowed = host.finTxnFundChoices.map((f) => f.fund_master_pk); r.autoFund = host.finTxnForm.fund_master_pk;
            host.finTxnForm.sakha_pk = ""; host.finTxnForm.fund_master_pk = "f2"; host.finTxnFundChanged(); r.sakhaFromFund = host.finTxnForm.sakha_pk; r.isSinking = host.finTxnFundIsSinking;
            host.finTxnForm.fund_master_pk = "f1"; host.finTxnFundChanged(); r.cleared = [host.finTxnForm.sakha_pk, host.finTxnFundIsSinking];
        """)
        assert out == {"all": 3, "narrowed": ["f3"], "autoFund": "f3", "sakhaFromFund": "s2", "isSinking": True, "cleared": ["", False]}

    def test_the_form_refuses_a_sakha_without_its_sinking_fund(self):
        src = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
        assert "Choose the Sakha this expense is for (required for a Sinking Fund)." in src
        assert "Choose the Sinking Fund of that Sakha, or clear the Sakha." in src
        assert 'x-show="finTxnNeedsSakha"' in (FE / "admin.html").read_text(encoding="utf-8")


class TestSakhaAdminsAndOfficeBearersDoNotSeeIt:
    """Owner 2026-11-24: "Sakha admins or office bearers should not see this, as this is the Kendra's procedure"."""

    def test_the_sidebar_link_and_the_panel_need_the_kendra_side(self):
        assert re.search(r'<a class="nav-item" x-show="finKendraSide" :class="\{ active: activeTab === \'finSinking\' \}"', HTML)
        assert "x-show=\"activeTab === 'finSinking' && finKendraSide\"" in HTML
        # the Annual Budget link stays for everyone: Sakhas have budgets of their own (owner 2026-11-24)
        assert not re.search(r'<a class="nav-item" x-show="finKendraSide" :class="\{ active: activeTab === \'finBudget\' \}"', HTML)

    def test_the_flag_comes_from_the_server_and_is_loaded_before_the_sidebar_needs_it(self):
        assert "get finKendraSide() { return !!(this.finRef && this.finRef.kendra_side); }" in FIN_JS
        assert "if (this.canViewFinance) this.finLoadRef();" in ADMIN_JS

    def test_nothing_of_the_sakha_read_only_view_is_left(self):
        assert "can_manage" not in JS and "finSinkingSakhaOnly" not in JS and "finSinkingSakhaOnly" not in HTML
