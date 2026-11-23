"""
Kendra annual budget screen (Finance > Annual Budget; frontend/assets/js/finance-budget.js + the panel in admin.html) — DB-free:
source checks plus a node run of the mixin against a stand-in server. Nothing here opens a browser.

  * what the page sends is what the API accepts (the request bodies are compared with the Pydantic models);
  * the page walks the steps the server enforces and decides nothing about WHO may act;
  * the markup binds only members the mixin defines, uses no inline handlers, and is wired into the tab lists, live feed and loaders.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FE = Path(__file__).resolve().parents[2] / "frontend"
BUDGET_JS = (FE / "assets/js/finance-budget.js").read_text(encoding="utf-8")
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
FIN_JS = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
CONFIG_JS = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
THEME = (FE / "assets/css/nss-theme.css").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _panel() -> str:
    start = ADMIN_HTML.index("VIEW: Finance - Kendra annual budget")
    return ADMIN_HTML[start:ADMIN_HTML.index("<!-- ═════════ Transactions ═════════ -->", start)]


class TestWiring:
    def test_the_mixin_is_installed_and_loaded(self):
        assert "NSSFinanceBudget.install(" in ADMIN_JS and "window.NSSFinanceBudget" in BUDGET_JS
        assert '<script src="/assets/js/finance-budget.js"></script>' in ADMIN_HTML
        assert BUDGET_JS.count("hasOwnProperty.call(target, key)") == 1 and "getOwnPropertyDescriptors" in BUDGET_JS

    def test_the_tab_is_in_every_list_that_names_the_finance_tabs(self):
        assert '"finBudget"' in re.search(r"const FINANCE_TABS = \[.*?\];", ADMIN_JS).group(0)
        assert re.search(r'finBudget: "[^"]+"', ADMIN_JS)                                              # banner title
        assert "activeTab === 'finBudget'" in ADMIN_HTML and "finEnterTab('finBudget')" in ADMIN_HTML    # panel + sidebar item
        assert "'finBudget'" in re.search(r"x-show=\"\['finOverview'[^\"]*\"", ADMIN_HTML).group(0)      # inside the Finance wrapper

    def test_a_refresh_and_the_live_feed_reach_it(self):
        assert 'finBudget: () => this.canViewFinance && this.finEnterTab("finBudget")' in ADMIN_JS
        assert re.search(r"finBudget: \{ reload: \(h\) => h\.finLiveReload\(\), busy: \(h\) => h\.finLiveBusy\(\) \}", ADMIN_JS)
        block = ADMIN_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        assert 'finance_budget: ["finBudget"]' in block and 'finance_budget_line: ["finBudget"]' in block
        assert 'this.activeTab === "finBudget"' in FIN_JS and "await this.finBudgetEnter();" in FIN_JS
        assert 'tab === "finBudget"' in FIN_JS and "this.finBudgetReload()" in FIN_JS and "this.finBudgetBusy()" in FIN_JS

    def test_every_status_the_api_can_return_has_a_label_and_a_badge(self):
        from api.schemas import finance as S

        labels = re.search(r"FINANCE_STATUS_LABELS: \{(.*?)\n    \},", CONFIG_JS, re.S).group(1)
        badges = re.search(r"FINANCE_STATUS_BADGE_MAP: \{(.*?)\n    \},", CONFIG_JS, re.S).group(1)
        for status in S.BUDGET_STATUSES:
            assert re.search(rf"\b{status}:", labels) and re.search(rf"\b{status}:", badges), status

    def test_the_step_tracker_style_exists_in_the_shared_theme_without_important(self):
        for cls in ("bud-steps", "bud-step", "bud-step__dot", "bud-step--current", "bud-step--done"):
            assert re.search(rf"^\.nss-theme \.{cls}\b", THEME, re.M), cls
        assert "!important" not in THEME.split("Kendra annual budget")[1]


class TestPanel:
    def test_no_inline_handlers_or_forms(self):
        panel = _panel()
        assert not re.search(r"\son[a-z]+\s*=", panel) and "<form" not in panel and 'x-init="init()"' not in panel

    def test_no_xshow_carries_an_inline_display(self):
        for tag in re.findall(r"<[^>]*x-show=[^>]*>", _panel()):
            assert not re.search(r"style=\"[^\"]*display\s*:\s*(flex|grid)", tag), tag

    def test_the_panel_binds_only_members_the_mixin_defines(self):
        defined = set(re.findall(r"\b(finBudget[A-Za-z]*)\s*[(:]", BUDGET_JS)) | set(re.findall(r"\bget (finBudget[A-Za-z]*)\(", BUDGET_JS))
        used = set(re.findall(r"\b(finBudget[A-Za-z]*)\b", _panel()))
        assert used and not used - defined, used - defined

    def test_the_helpers_it_borrows_exist_in_the_other_mixins(self):
        for name in ("finMoney", "finBadge", "finLabel", "finCode", "canManageFinance"):
            assert name in _panel() and re.search(rf"\b{name}\b", FIN_JS), name
        for helper in ("_finGet", "_finSend", "_finNote", "_finMoneyOk", "finLoadYears"):
            assert helper in FIN_JS

    def test_every_field_it_reads_exists_in_the_api_model(self):
        from api.schemas.finance import BudgetDetailResponse, BudgetLineResponse, BudgetResponse, BudgetTotals, BudgetUnbudgetedResponse

        panel = _panel()
        for var, model in (("finBudget", BudgetDetailResponse), ("b", BudgetResponse), ("l", BudgetLineResponse), ("u", BudgetUnbudgetedResponse)):
            for field in set(re.findall(rf"\b{var}\.([a-z_]+)", panel)):
                if field in ("length", "totals", "lines", "unbudgeted"):
                    continue
                assert field in model.model_fields, f"{var}.{field}"
        for field in set(re.findall(r"finBudget\.totals\.([a-z_]+)", panel)):
            assert field in BudgetTotals.model_fields, field

    def test_the_actions_are_shown_only_to_someone_who_may_record_and_the_page_decides_nothing_else(self):
        assert 'x-show="finBudgetCanAct && finBudget.status !== \'PASSED\'"' in _panel()
        assert "get finBudgetCanAct() { return !!this.finBudget && this.canManageFinance; }" in BUDGET_JS
        assert not re.search(r"(TREASURER|SECRETARY|PRESIDENT)", BUDGET_JS)                          # no seat logic on the page

    def test_lines_can_be_changed_in_every_status_and_past_draft_a_reason_is_asked(self):
        assert "get finBudgetCanEditLines() { return !!this.finBudget && this.canManageFinance; }" in BUDGET_JS
        assert "lines_editable" not in BUDGET_JS + _panel()
        assert "finBudget.changes_need_reason" in BUDGET_JS and 'x-model="finBudgetReason"' in _panel()


class TestWhatThePageSends:
    def test_every_request_body_is_what_the_api_accepts(self):
        from api.schemas.finance import BudgetCreate, BudgetLineWrite, BudgetPassWrite, BudgetReferWrite, BudgetReopenWrite, BudgetViewsWrite

        bodies = {
            "/budgets\"": (BudgetCreate, {"financial_year_pk"}),
            "/lines`": (BudgetLineWrite, {"finance_head_pk", "amount", "notes"}),
            "/refer`": (BudgetReferWrite, {"referred_on"}),
            "/advisory-views`": (BudgetViewsWrite, {"advisory_views_date", "advisory_views_summary"}),
            "/pass`": (BudgetPassWrite, {"resolution_reference", "resolution_date"}),
            "/reopen`": (BudgetReopenWrite, {"remarks"}),
        }
        for route, (model, sent) in bodies.items():
            assert route in BUDGET_JS, route
            assert sent <= set(model.model_fields), (route, sent - set(model.model_fields))
            assert set(model.model_fields) - sent == set() or all(not model.model_fields[f].is_required() for f in set(model.model_fields) - sent), route
            for field in sent:
                assert field in BUDGET_JS, field

    def test_the_budget_routes_it_calls_are_real(self):
        from api.main import app

        routes = {re.sub(r"\{[^}]+\}", "{}", r.path.replace("/api/v1/finance", "")) for r in app.routes if getattr(r, "path", "").startswith("/api/v1/finance")}
        for path in set(re.findall(r"`(/budgets[^`?]*)`|\"(/budgets)\"", BUDGET_JS)):
            p = re.sub(r"\$\{[^}]+\}", "{}", next(x for x in path if x))
            assert p in routes, p
        # the four step routes and the two line routes are all present as literals (a dynamic suffix could not be checked)
        for literal in ("/refer`", "/advisory-views`", "/pass`", "/reopen`", "/lines`", "/lines/${line.finance_budget_line_pk}`"):
            assert literal in BUDGET_JS, literal


# ═══════════════════════════════════════════════════════════════════════
# The mixin run for real in node, against a stand-in server
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(NODE is None, reason="node not available")
class TestMixinUnderNode:
    def _run(self, scenario: str):
        script = f"""
        global.window = global; global.NSS = {{ formatDate: (d) => "D(" + d + ")" }};
        global.NSSDialog = {{ confirm: async () => true }};
        const calls = [];
        {BUDGET_JS}
        const host = {{
            finYears: [{{ financial_year_pk: "y1", year_code: "2026-27", status: "OPEN" }}, {{ financial_year_pk: "y2", year_code: "2027-28", status: "PLANNED" }},
                       {{ financial_year_pk: "y0", year_code: "2025-26", status: "CLOSED" }}],
            canManageFinance: true, notes: [],
            _finNote(t) {{ this.notes.push(t); }},
            _finMoneyOk(v) {{ return Number(v) > 0 ? "" : "Amount must be positive"; }},
            async finLoadYears() {{}},
            async _finGet(path, params) {{ calls.push(["GET", path, params || null]); return host.server(path); }},
            async _finSend(method, path, body) {{ calls.push([method, path, body]); return host.reply(method, path, body); }},
            server: () => ({{ items: [] }}), reply: () => ({{}}),
        }};
        NSSFinanceBudget.install(host);
        const detail = (over) => Object.assign({{ finance_budget_pk: "b1", organization_pk: "k1", status: "DRAFT", changes_need_reason: false, lines: [], unbudgeted: [] }}, over || {{}});
        (async () => {{ {scenario} }})().then((out) => console.log(JSON.stringify(out)));
        """
        done = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_steps_tracker_follows_the_status(self):
        out = self._run("""
            const at = (s) => { host.finBudget = detail({ status: s }); return host.finBudgetSteps.map((x) => x.done ? "done" : (x.current ? "now" : "todo")); };
            return { draft: at("DRAFT"), referred: at("REFERRED"), views: at("VIEWS_RECEIVED"), passed: at("PASSED") };
        """)
        assert out == {"draft": ["now", "todo", "todo", "todo"], "referred": ["done", "now", "todo", "todo"],
                       "views": ["done", "done", "now", "todo"], "passed": ["done", "done", "done", "done"]}

    def test_a_budget_is_started_for_the_current_year_only_and_only_once(self):
        """Owner 2026-11-23: wherever a record is created the financial year is the current one, set for the user. finScopeYear (finance.js) is the current year."""
        out = self._run("""
            const r = {};
            host.finScopeYear = { financial_year_pk: "y1", year_code: "2026-27", status: "OPEN" };
            host.finBudgets = []; r.free = [host.finBudgetYear && host.finBudgetYear.year_code, host.finBudgetYearTaken];
            host.finBudgets = [{ financial_year_pk: "y1" }]; r.taken = [host.finBudgetYear, host.finBudgetYearTaken];
            host.finBudgets = [{ financial_year_pk: "other" }]; r.otherYear = host.finBudgetYear.year_code;
            host.finScopeYear = null; host.finBudgets = []; r.none = [host.finBudgetYear, host.finBudgetYearTaken];
            host.finScopeYear = { financial_year_pk: "y1", year_code: "2026-27", status: "OPEN" }; host.finBudgets = [];
            host.finBudgetStartOpen(); r.preselected = [host.finBudgetStart.show, host.finBudgetStart.year];
            host.finBudgets = [{ financial_year_pk: "y1" }]; host.finBudgetStartOpen(); r.nothingToSelect = host.finBudgetStart.year;
            return r;
        """)
        assert out == {"free": ["2026-27", False], "taken": [None, True], "otherYear": "2026-27", "none": [None, False],
                       "preselected": [True, "y1"], "nothingToSelect": ""}

    def test_a_head_with_a_line_is_not_offered_again(self):
        out = self._run("""
            host.finBudget = detail({ lines: [{ finance_head_pk: "h1" }] });
            host.finBudgetHeads = [{ finance_head_pk: "h1" }, { finance_head_pk: "h2" }];
            return host.finBudgetFreeHeads.map((h) => h.finance_head_pk);
        """)
        assert out == ["h2"]

    def test_lines_are_editable_in_every_status_for_someone_who_can_manage_and_a_reason_is_needed_past_draft(self):
        out = self._run("""
            const r = {};
            for (const s of ["DRAFT", "REFERRED", "VIEWS_RECEIVED", "PASSED"]) {
                host.finBudget = detail({ status: s, changes_need_reason: s !== "DRAFT" }); r[s] = [host.finBudgetCanEditLines, host.finBudgetNeedsReason];
            }
            host.finBudget = detail(); host.canManageFinance = false; r.viewer = host.finBudgetCanEditLines;
            return r;
        """)
        assert out == {"DRAFT": [True, False], "REFERRED": [True, True], "VIEWS_RECEIVED": [True, True], "PASSED": [True, True], "viewer": False}

    def test_a_change_to_a_locked_budget_is_not_sent_without_a_reason_and_carries_it_when_given(self):
        out = self._run("""
            host.finBudget = detail({ status: "PASSED", changes_need_reason: true }); host.reply = () => detail({ status: "PASSED", changes_need_reason: true });
            host.finBudgetLineOpen(null); host.finBudgetLine.head = "h1"; host.finBudgetLine.amount = "500";
            await host.finBudgetLineSave(); const without = calls.length; const err = host.finBudgetLine.error;
            host.finBudgetReason = "  Revised after the audit  "; await host.finBudgetLineSave();
            host.finBudgetReason = "  Revised after the audit  "; await host.finBudgetLineRemove({ finance_budget_line_pk: "l1", head_name: "Puja" });
            host.finBudgetReason = ""; await host.finBudgetLineRemove({ finance_budget_line_pk: "l2", head_name: "Travel" });
            return { without, err, calls, reasonClearedAfterASavedChange: host.finBudgetReason === "" };
        """)
        assert out["without"] == 0 and "Say why" in out["err"]
        assert out["calls"][0] == ["PUT", "/budgets/b1/lines", {"finance_head_pk": "h1", "amount": "500", "notes": None, "reason": "Revised after the audit"}]
        assert out["calls"][1][:2] == ["DELETE", "/budgets/b1/lines/l1?reason=Revised%20after%20the%20audit"]
        assert len(out["calls"]) == 2                                                  # the second removal had no reason and was not sent
        assert out["reasonClearedAfterASavedChange"] is True                           # every change gives its own reason

    def test_the_percent_of_a_line_used_is_capped_and_safe(self):
        out = self._run("""
            return [host.finBudgetUsedPercent({ amount: "2000.00", actual: "1000" }), host.finBudgetUsedPercent({ amount: "1000", actual: "5000" }),
                    host.finBudgetUsedPercent({ amount: "0", actual: "5" })];
        """)
        assert out == [50, 100, 0]

    def test_each_step_posts_its_own_route_and_nothing_goes_out_while_a_field_is_missing(self):
        out = self._run("""
            host.reply = () => detail({ status: "REFERRED" });
            host.finBudget = detail();
            host.finBudgetRefer.date = "2026-11-01"; await host.finBudgetDoRefer();
            host.finBudgetViews = { date: "", summary: "   ", saving: false, error: "" }; await host.finBudgetDoViews(); const blocked = calls.length;
            host.finBudgetViews = { date: "2026-11-05", summary: " Supports it ", saving: false, error: "" };
            await host.finBudgetDoViews();
            host.finBudgetPass = { reference: "GB/9", date: "2026-11-10", saving: false, error: "" };
            await host.finBudgetDoPass();
            host.finBudgetBack = { show: true, remarks: "  ", saving: false, error: "" }; await host.finBudgetDoBack(); const afterBlankBack = calls.length;
            host.finBudgetBack = { show: true, remarks: "raise the line", saving: false, error: "" }; await host.finBudgetDoBack();
            return { blocked, afterBlankBack, calls };
        """)
        assert out["blocked"] == 1 and out["afterBlankBack"] == 3                       # a blank summary and a blank reason sent nothing
        assert out["calls"] == [
            ["POST", "/budgets/b1/refer", {"referred_on": "2026-11-01"}],
            ["POST", "/budgets/b1/advisory-views", {"advisory_views_date": "2026-11-05", "advisory_views_summary": "Supports it"}],
            ["POST", "/budgets/b1/pass", {"resolution_reference": "GB/9", "resolution_date": "2026-11-10"}],
            ["POST", "/budgets/b1/reopen", {"remarks": "raise the line"}],
        ]

    def test_a_refusal_from_the_server_is_shown_on_the_form_and_the_form_stays_filled(self):
        out = self._run("""
            host._finSend = async () => { throw new Error("The budget is PASSED; it is final."); };
            host.finBudget = detail({ status: "VIEWS_RECEIVED" });
            host.finBudgetPass = { reference: "GB/9", date: "2026-11-10", saving: false, error: "" };
            await host.finBudgetDoPass();
            return { error: host.finBudgetPass.error, saving: host.finBudgetPass.saving, reference: host.finBudgetPass.reference, status: host.finBudget.status };
        """)
        assert out == {"error": "The budget is PASSED; it is final.", "saving": False, "reference": "GB/9", "status": "VIEWS_RECEIVED"}

    def test_a_line_is_saved_with_a_trimmed_amount_and_a_bad_amount_is_not_sent(self):
        out = self._run("""
            host.finBudget = detail(); host.reply = () => detail({ lines: [{ finance_head_pk: "h1" }] });
            host.finBudgetLine.head = "h1"; host.finBudgetLine.amount = "0"; await host.finBudgetLineSave(); const bad = calls.length;
            host.finBudgetLine.amount = " 2500.00 "; host.finBudgetLine.notes = "  "; await host.finBudgetLineSave();
            return { bad, call: calls[0], formClosed: !host.finBudgetLine.show, formStillThere: host.finBudgetLine.show === true,
                     emptied: host.finBudgetLine.head === "" && host.finBudgetLine.amount === "" };
        """)
        assert out["bad"] == 0
        assert out["call"] == ["PUT", "/budgets/b1/lines", {"finance_head_pk": "h1", "amount": "2500.00", "notes": None, "reason": None}]
        assert out["formClosed"] is False and out["formStillThere"] is True and out["emptied"] is True

    def test_removing_a_line_asks_first_and_calls_delete(self):
        out = self._run("""
            host.finBudget = detail({ lines: [{ finance_budget_line_pk: "l1", head_name: "Puja" }] }); host.reply = () => detail();
            await host.finBudgetLineRemove({ finance_budget_line_pk: "l1", head_name: "Puja" });
            return calls;
        """)
        assert out == [["DELETE", "/budgets/b1/lines/l1", None]]

    def test_starting_a_budget_uses_the_current_year_and_then_opens_the_draft(self):
        out = self._run("""
            host.reply = () => detail({ organization_pk: "k1" }); host.server = () => ({ items: [] });
            host.finScopeYear = null; host.finBudgets = [];
            host.finBudgetStartOpen(); await host.finBudgetStartSubmit(); const none = calls.length; const err = host.finBudgetStart.error;
            host.finScopeYear = { financial_year_pk: "y2", year_code: "2026-27", status: "OPEN" };
            host.finBudgetStartOpen(); await host.finBudgetStartSubmit();
            return { none, err, post: calls[0], opened: host.finBudget && host.finBudget.finance_budget_pk, heads: calls.find((c) => c[1] === "/heads") };
        """)
        assert out["none"] == 0 and out["err"] == "There is no current financial year to start a budget for."
        assert out["post"] == ["POST", "/budgets", {"financial_year_pk": "y2"}] and out["opened"] == "b1"        # the current year, not chosen from a list
        assert out["heads"][2] == {"organization_pk": "k1", "with_templates": False, "status": "ACTIVE", "page_size": 200}

    def test_an_open_form_makes_the_tab_busy_for_live_refresh(self):
        out = self._run("""
            const r = { idle: host.finBudgetBusy() };
            host.finBudgetViews.summary = "half-typed"; r.typing = host.finBudgetBusy();
            host.finBudgetViews.summary = ""; r.notEditing = host.finBudgetBusy(); host.finBudgetEdit(); r.editing = host.finBudgetBusy();
            host.finBudgetEditCancel(); r.afterCancel = host.finBudgetBusy();
            return r;
        """)
        assert out == {"idle": False, "typing": True, "notEditing": False, "editing": True, "afterCancel": False}

    def test_live_reload_rereads_the_open_budget_or_the_list(self):
        out = self._run("""
            host.server = (p) => p === "/budgets" ? { items: [{ finance_budget_pk: "b1" }] } : detail({ status: "REFERRED" });
            await host.finBudgetReload(); const list = host.finBudgets.length;
            host.finBudget = detail(); await host.finBudgetReload();
            return { list, status: host.finBudget.status, paths: calls.map((c) => c[1]) };
        """)
        assert out == {"list": 1, "status": "REFERRED", "paths": ["/budgets", "/budgets/b1"]}

    def test_a_kendra_with_no_heads_gets_the_standard_ones_copied_in_for_someone_who_may_configure(self):
        out = self._run("""
            let adopted = false;
            host.canConfigureFinance = true;
            host.server = (p) => ({ items: adopted ? [{ finance_head_pk: "h1" }] : [] });
            host._finSend = async (m, p, b) => { calls.push([m, p, b]); adopted = true; return {}; };
            host.finBudget = detail();
            await host._finBudgetLoadHeads();
            return { heads: host.finBudgetHeads.length, note: host.finBudgetHeadsNote, sent: calls.filter((c) => c[0] === "POST") };
        """)
        assert out == {"heads": 1, "note": "", "sent": [["POST", "/heads/adopt-templates", {"organization_pk": "k1"}]]}

    def test_without_that_permission_nothing_is_changed_and_the_page_says_who_to_ask(self):
        out = self._run("""
            host.canConfigureFinance = false;
            host.finBudget = detail();
            await host._finBudgetLoadHeads();
            return { heads: host.finBudgetHeads.length, note: host.finBudgetHeadsNote, posts: calls.filter((c) => c[0] === "POST").length };
        """)
        assert out["heads"] == 0 and out["posts"] == 0 and "configure finance" in out["note"]


class TestLettersAreAutomatic:
    def test_the_page_asks_for_no_letter_number_and_no_date_is_required(self):
        panel = _panel()
        assert "finBudgetViews.reference" not in panel and "advisory_reference" not in BUDGET_JS.split("finBudgetDoViews", 1)[1].split("finBudgetDoPass", 1)[0]
        assert "referred_on: f.date || null" in BUDGET_JS and "advisory_views_date: f.date || null" in BUDGET_JS      # empty = today, the server decides
        assert "Correspondence" in panel                                           # the page says a letter is filed

    def test_the_numbers_of_the_filed_letters_are_shown_from_the_api(self):
        from api.schemas.finance import BudgetResponse

        panel = _panel()
        for field in ("referral_reference", "referral_inward_reference", "advisory_reference", "views_inward_reference"):
            assert f"finBudget.{field}" in panel and field in BudgetResponse.model_fields, field


class TestEditingABudget:
    def test_edit_is_always_offered_to_someone_who_can_manage(self):
        panel = _panel()
        assert 'x-show="finBudgetCanEdit && !finBudgetEditing" @click="finBudgetEdit()">Edit budget</button>' in panel
        assert 'id="bud-lines-card"' in panel and 'id="bud-back-box"' in panel
        assert "finBudgetCanEdit() { return !!this.finBudget && this.canManageFinance; }" in BUDGET_JS

    @pytest.mark.skipif(NODE is None, reason="node not available")
    def test_edit_brings_the_lines_into_view_and_sending_back_is_a_separate_step(self):
        script = "global.window = global;\n" + BUDGET_JS + """
        const seen = [];
        global.document = { getElementById: (id) => ({ scrollIntoView() { seen.push(id); } }) };
        const host = { canManageFinance: true, $nextTick: (f) => f() }; NSSFinanceBudget.install(host);
        const r = {};
        for (const s of ["DRAFT", "REFERRED", "VIEWS_RECEIVED", "PASSED"]) { host.finBudget = { status: s }; r[s] = host.finBudgetCanEdit; }
        host.finBudget = { status: "PASSED" }; host.finBudgetEdit(); r.backFormAfterEdit = host.finBudgetBack.show;
        host.finBudget = { status: "REFERRED" }; host.finBudgetSendBack(); r.backFormAfterSendBack = host.finBudgetBack.show;
        host.canManageFinance = false; r.viewer = host.finBudgetCanEdit; r.seen = seen;
        console.log(JSON.stringify(r));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        assert json.loads(out.stdout) == {"DRAFT": True, "REFERRED": True, "VIEWS_RECEIVED": True, "PASSED": True, "backFormAfterEdit": False,
                                           "backFormAfterSendBack": True, "viewer": False, "seen": ["bud-lines-card", "bud-back-box"]}


class TestEditMode:
    """The reason box, the line form and Change / Remove appear only after "Edit budget" (offered in every status) and go away on Cancel."""

    def test_the_form_the_reason_and_the_row_buttons_show_only_in_edit_mode(self):
        panel = _panel()
        assert 'id="bud-line-form" x-show="finBudgetCanEditLines && finBudgetEditing"' in panel
        assert 'x-show="finBudgetCanEditLines && finBudgetEditing && finBudgetNeedsReason"' in panel
        assert panel.count('x-show="finBudgetCanEditLines && finBudgetEditing" @click="finBudgetLine') == 2          # Change and Remove
        assert "@click=\"finBudgetEditCancel()\">Cancel</button>" in panel and "+ Add a line" not in panel
        assert panel.index("Reason for changing the budget") < panel.index('id="bud-line-form"')                   # the reason comes first

    @pytest.mark.skipif(NODE is None, reason="node not available")
    def test_edit_opens_it_cancel_closes_it_and_drops_what_was_typed(self):
        script = "global.window = global;\n" + BUDGET_JS + """
        const seen = []; global.document = { getElementById: (id) => ({ scrollIntoView() { seen.push(id); } }) };
        const host = { canManageFinance: true, $nextTick: (f) => f() }; NSSFinanceBudget.install(host);
        const r = { start: host.finBudgetEditing };
        host.finBudget = { status: "PASSED", finance_budget_pk: "b1", changes_need_reason: true };
        host.finBudgetEdit(); r.opened = host.finBudgetEditing;
        host.finBudgetLineOpen({ finance_head_pk: "h1", amount: "2000.00", notes: "n" });
        host.finBudgetReason = "because";
        r.filled = [host.finBudgetLine.editing, host.finBudgetLine.head, host.finBudgetLine.amount];
        host.finBudgetEditCancel();
        r.cancelled = [host.finBudgetEditing, host.finBudgetLine.editing, host.finBudgetLine.head, host.finBudgetReason]; r.seen = seen;
        console.log(JSON.stringify(r));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        assert json.loads(out.stdout) == {"start": False, "opened": True, "filled": [True, "h1", "2000.00"], "cancelled": [False, False, "", ""],
                                           "seen": ["bud-lines-card", "bud-line-form"]}

    @pytest.mark.skipif(NODE is None, reason="node not available")
    def test_leaving_the_budget_or_the_list_always_ends_edit_mode(self):
        script = "global.window = global;\n" + BUDGET_JS + """
        const host = { canManageFinance: true, finYears: [], finLoadYears: async () => {}, _finGet: async () => ({ items: [] }) };
        NSSFinanceBudget.install(host);
        (async () => {
            const r = {};
            host.finBudgetEditing = true; host.finBudgetClose(); r.close = host.finBudgetEditing;
            host.finBudgetEditing = true; await host.finBudgetEnter(); r.enter = host.finBudgetEditing;
            console.log(JSON.stringify(r));
        })();
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        assert json.loads(out.stdout) == {"close": False, "enter": False}
