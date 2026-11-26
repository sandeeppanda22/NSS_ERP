"""
Kendra annual audit screen (Finance > Annual Audit; frontend/assets/js/finance-audit.js + the panel in admin.html; Bye-Law Section G) — DB-free:
source checks plus a node run of the mixin against a stand-in server. Nothing here opens a browser.

  * what the page sends is what the API accepts (the request bodies are compared with the Pydantic models);
  * the page walks the five steps the server enforces and decides nothing about WHO may act;
  * the markup binds only members the mixin defines, uses no inline handlers, and is wired into the tab lists, live feed and loaders.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FE = Path(__file__).resolve().parents[2] / "frontend"
AUDIT_JS = (FE / "assets/js/finance-audit.js").read_text(encoding="utf-8")
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
FIN_JS = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
CONFIG_JS = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _panel() -> str:
    start = ADMIN_HTML.index("VIEW: Finance - the Kendra's annual audit")
    return ADMIN_HTML[start:ADMIN_HTML.index("<!-- ═════════ Sinking Fund dues ═════════ -->", start)]


class TestWiring:
    def test_the_mixin_is_loaded_and_installed(self):
        assert '<script src="/assets/js/finance-audit.js"></script>' in ADMIN_HTML
        assert "NSSFinanceAudit.install(NSSFinanceBudget.install(" in ADMIN_JS and "window.NSSFinanceAudit" in AUDIT_JS

    def test_the_tab_is_in_every_list_that_names_the_finance_tabs(self):
        assert '"finAudit"' in re.search(r"const FINANCE_TABS = \[.*?\];", ADMIN_JS).group(0)
        assert 'finAudit: "Kendra Annual Audit"' in ADMIN_JS
        assert re.search(r"finAudit: \{ reload: \(h\) => h\.finLiveReload\(\), busy: \(h\) => h\.finLiveBusy\(\) \}", ADMIN_JS)
        assert 'finAudit: () => this.canViewFinance && this.finEnterTab("finAudit")' in ADMIN_JS
        assert "'finAudit'" in ADMIN_HTML and "finEnterTab('finAudit')" in ADMIN_HTML

    def test_the_live_feed_follows_the_audit_table_and_the_year(self):
        block = re.search(r"finance_year_audit: \[(.*?)\]", ADMIN_JS).group(1)
        assert '"finAudit"' in block
        assert '"finAudit"' in re.search(r"^\s+financial_year: \[(.*?)\]", ADMIN_JS, re.M).group(1)

    def test_finance_js_enters_reloads_and_guards_the_tab(self):
        assert 'this.activeTab === "finAudit"' in FIN_JS and "await this.finAuditEnter();" in FIN_JS
        assert 'tab === "finAudit"' in FIN_JS and "this.finAuditReload()" in FIN_JS and "this.finAuditBusy()" in FIN_JS

    def test_the_new_statuses_have_labels_and_badges(self):
        for status in ("APPOINTED", "REPORT_RECEIVED", "PLACED_BEFORE_GB", "PLACED_BEFORE_GENERAL_BODY"):
            assert f"{status}:" in CONFIG_JS.split("FINANCE_STATUS_BADGE_MAP")[0] and f"{status}:" in CONFIG_JS.split("FINANCE_STATUS_BADGE_MAP")[1]


class TestTheKendraOnly:
    def test_the_sidebar_link_and_the_tab_are_shown_only_to_the_kendra_side(self):
        assert re.search(r'<a class="nav-item" x-show="finKendraSide"[^>]*finEnterTab\(\'finAudit\'\)', ADMIN_HTML)
        assert "activeTab === 'finAudit' && finKendraSide" in _panel()

    def test_writing_needs_permission_and_the_kendra_side(self):
        assert "get finAuditCanAct() { return this.canManageFinance && this.finKendraSide; }" in AUDIT_JS


class TestMarkup:
    def test_the_panel_binds_only_what_the_mixin_defines(self):
        from tests.ui.test_ui_finance import _mixin_members

        used = set(re.findall(r"\b(finAudit[A-Za-z]*)\b", _panel()))
        assert used and not (used - _mixin_members()), sorted(used - _mixin_members())

    def test_no_inline_handlers(self):
        assert not re.search(r"\son[a-z]+=", _panel())             # CSP: no inline event handlers

    def test_every_step_has_its_own_form(self):
        panel = _panel()
        for status in ("APPOINTED", "REPORT_RECEIVED", "PLACED_BEFORE_GB", "APPROVED"):
            assert f"finAudit.status === '{status}'" in panel
        for submit in ("finAuditReportSubmit", "finAuditGbSubmit", "finAuditApprovalSubmit", "finAuditGeneralSubmit", "finAuditStartSubmit", "finAuditFixSubmit"):
            assert f"{submit}()" in panel

    def test_the_parichalak_clause_is_shown(self):
        assert "Not subject to audit." in _panel() and "not_subject_to_audit" in _panel()

    def test_no_inline_display_on_an_x_show_element(self):
        for tag in re.findall(r"<[^>]*x-show=[^>]*>", _panel()):
            assert not re.search(r"style=\"[^\"]*display:\s*(flex|grid)", tag), tag


class TestWhatThePageSendsIsWhatTheApiAccepts:
    def test_the_request_bodies_match_the_models(self):
        from api.schemas import finance as S

        sent = {
            "AuditCreate": ["financial_year_pk", "auditor_name", "auditor_firm", "appointed_on", "appointment_reference", "notes"],
            "AuditReportWrite": ["report_reference", "report_date", "report_link"],
            "AuditGoverningBodyWrite": ["gb_placed_on", "gb_reference"],
            "AuditApprovalWrite": ["approved_on", "approval_reference"],
            "AuditGeneralBodyWrite": ["general_body_on", "general_body_reference"],
        }
        for model, keys in sent.items():
            fields = set(getattr(S, model).model_fields)
            assert set(keys) <= fields, (model, set(keys) - fields)
            for key in keys:
                assert re.search(rf"\b{key}\b", AUDIT_JS), key
        correct = set(S.AuditCorrectWrite.model_fields) - {"reason"}
        assert all(f"body.{col}" in AUDIT_JS for col in correct)


@pytest.mark.skipif(NODE is None, reason="node not available")
class TestMixinUnderNode:
    def _run(self, scenario: str):
        script = f"""
        global.window = global; global.NSS = {{ formatDate: (d) => "D(" + d + ")", financeStatusLabel: (s) => s }};
        global.NSSDialog = {{ confirm: async () => true }};
        const calls = [];
        {AUDIT_JS}
        const host = {{
            finYears: [{{ financial_year_pk: "y1", year_code: "2026-27", status: "OPEN" }}, {{ financial_year_pk: "y0", year_code: "2025-26", status: "CLOSED" }}],
            canManageFinance: true, finKendraSide: true, notes: [],
            _finNote(t) {{ this.notes.push(t); }},
            async finLoadYears() {{}},
            async _finGet(path, params) {{ calls.push(["GET", path, params || null]); return host.server(path); }},
            async _finSend(method, path, body) {{ calls.push([method, path, body]); return host.reply(method, path, body); }},
            server: () => ({{ items: [] }}), reply: () => ({{}}),
        }};
        NSSFinanceAudit.install(host);
        const detail = (over) => Object.assign({{ finance_year_audit_pk: "a1", status: "APPOINTED", auditor_name: "A", auditor_firm: null, appointment_reference: "GB/1",
            report_reference: null, report_link: null, gb_reference: null, approval_reference: null, general_body_reference: null }}, over || {{}});
        (async () => {{ {scenario} }})().then((out) => console.log(JSON.stringify(out)));
        """
        done = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_tracker_follows_the_status(self):
        out = self._run("""
            const at = (s) => { host.finAudit = detail({ status: s }); return host.finAuditSteps.map((x) => x.done ? "done" : (x.current ? "now" : "todo")); };
            return { a: at("APPOINTED"), r: at("REPORT_RECEIVED"), g: at("PLACED_BEFORE_GB"), p: at("APPROVED"), end: at("PLACED_BEFORE_GENERAL_BODY") };
        """)
        assert out == {"a": ["now", "todo", "todo", "todo", "todo"], "r": ["done", "now", "todo", "todo", "todo"], "g": ["done", "done", "now", "todo", "todo"],
                       "p": ["done", "done", "done", "now", "todo"], "end": ["done", "done", "done", "done", "done"]}

    def test_only_years_without_an_audit_are_offered_and_any_status_is(self):
        out = self._run("""
            host.finAudits = []; const all = host.finAuditYearChoices.map((y) => y.year_code);
            host.finAudits = [{ financial_year_pk: "y1" }]; const rest = host.finAuditYearChoices.map((y) => y.year_code);
            return { all, rest };
        """)
        assert out == {"all": ["2026-27", "2025-26"], "rest": ["2025-26"]}                 # a CLOSED year can be audited too

    def test_starting_sends_the_appointment_and_checks_the_required_facts_first(self):
        out = self._run("""
            host.reply = () => detail();
            host.finAuditStartOpen(); await host.finAuditStartSubmit(); const none = calls.length; const err = host.finAuditStart.error;
            Object.assign(host.finAuditStart, { year: "y0", name: " A. Auditor ", firm: "", reference: " GB/7 " });
            await host.finAuditStartSubmit();
            return { none, err, post: calls[0], opened: host.finAudit && host.finAudit.finance_year_audit_pk };
        """)
        assert out["none"] == 0 and out["err"] == "Choose the financial year."
        assert out["post"][:2] == ["POST", "/audits"] and out["opened"] == "a1"
        body = out["post"][2]
        assert body["auditor_name"] == "A. Auditor" and body["auditor_firm"] is None and body["appointment_reference"] == "GB/7" and body["financial_year_pk"] == "y0"

    def test_each_step_posts_to_its_own_path_and_a_non_https_link_never_leaves_the_page(self):
        out = self._run("""
            host.finAudit = detail(); host.reply = () => detail({ status: "REPORT_RECEIVED" });
            Object.assign(host.finAuditReport, { reference: " AR/1 ", date: "2026-02-01", link: "http://x.org/r" });
            await host.finAuditReportSubmit(); const refused = [calls.length, host.finAuditReport.error];
            host.finAuditReport.link = "https://x.org/r"; await host.finAuditReportSubmit();
            Object.assign(host.finAuditGb, { reference: "GB/2" }); await host.finAuditGbSubmit();
            Object.assign(host.finAuditApproval, { date: "2026-03-01", reference: "CM/1" }); await host.finAuditApprovalSubmit();
            Object.assign(host.finAuditGeneral, { date: "2026-04-01", reference: "GBM/1" }); await host.finAuditGeneralSubmit();
            return { refused, calls: calls.map((c) => [c[0], c[1]]), first: calls[0][2], gb: calls[1][2] };
        """)
        assert out["refused"] == [0, "The link must start with https://."]
        assert out["calls"] == [["POST", "/audits/a1/report"], ["POST", "/audits/a1/governing-body"], ["POST", "/audits/a1/approval"], ["POST", "/audits/a1/general-body"]]
        assert out["first"] == {"report_reference": "AR/1", "report_date": "2026-02-01", "report_link": "https://x.org/r"}
        assert out["gb"] == {"gb_placed_on": None, "gb_reference": "GB/2"}                       # no date: the server uses today

    def test_a_correction_sends_only_what_changed_and_needs_a_reason(self):
        out = self._run("""
            host.finAudit = detail({ auditor_firm: "Old & Co" }); host.reply = () => detail({ auditor_name: "B" });
            host.finAuditFixOpen(); host.finAuditFix.name = "B"; await host.finAuditFixSubmit(); const noReason = [calls.length, host.finAuditFix.error];
            host.finAuditFix.reason = "Spelling"; await host.finAuditFixSubmit();
            host.finAuditFixOpen(); host.finAuditFix.reason = "x"; await host.finAuditFixSubmit(); const same = host.finAuditFix.error;
            return { noReason, post: calls[0], same };
        """)
        assert out["noReason"] == [0, "Say why it is being corrected."]
        assert out["post"] == ["POST", "/audits/a1/correct", {"auditor_name": "B", "reason": "Spelling"}]
        assert out["same"] == "Nothing has been changed."

    def test_an_open_form_makes_the_tab_busy_for_live_refresh(self):
        out = self._run("""
            const r = { idle: host.finAuditBusy() };
            host.finAuditReport.reference = "half-typed"; r.typing = host.finAuditBusy();
            host.finAuditReport.reference = ""; host.finAuditStartOpen(); r.starting = host.finAuditBusy();
            return r;
        """)
        assert out == {"idle": False, "typing": True, "starting": True}

    def test_live_reload_rereads_the_open_audit_or_the_list(self):
        out = self._run("""
            host.server = (p) => p === "/audits" ? { items: [{ finance_year_audit_pk: "a1" }] } : detail({ status: "APPROVED" });
            await host.finAuditReload(); const list = host.finAudits.length;
            host.finAudit = detail(); await host.finAuditReload();
            return { list, status: host.finAudit.status, paths: calls.map((c) => c[1]) };
        """)
        assert out == {"list": 1, "status": "APPROVED", "paths": ["/audits", "/audits/a1"]}
