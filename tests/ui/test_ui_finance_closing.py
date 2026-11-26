"""
Finance "Closing <year>, Sangha by Sangha" card on Years & Scopes (owner request 2026-11-25; frontend/assets/js/finance-closing.js) - DB-free: source
parsing plus the pure getters run under node. Nothing opened in a browser.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from api.schemas.finance import YearClosingListResponse, YearClosingResult, YearClosingRow

FE = Path(__file__).resolve().parents[2] / "frontend"
JS = (FE / "assets/js/finance-closing.js").read_text(encoding="utf-8")
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
FIN_JS = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
HTML = (FE / "admin.html").read_text(encoding="utf-8")


def _card() -> str:
    start = HTML.index("<!-- Close the year, Sakha by Sakha and Kendra")
    return HTML[start:HTML.index("<!-- New scope form -->", start)]


class TestWiring:
    def test_the_mixin_is_loaded_and_installed(self):
        assert '<script src="/assets/js/finance-closing.js"></script>' in HTML
        assert "NSSFinanceClosing.install(NSSFinanceSinking.install(" in ADMIN_JS and "})))))))))), LIVE_REFRESH_CONFIG);" in ADMIN_JS

    def test_the_years_tab_loads_and_reloads_it(self):
        assert "await this.finClosingsLoad();" in FIN_JS and "await this.finClosingsLoad({ silent: true });" in FIN_JS

    def test_the_live_feed_reaches_the_years_tab(self):
        block = ADMIN_JS[ADMIN_JS.index("financial_year:"):]
        assert 'finance_year_closing: ["finStructure"]' in block
        assert re.search(r'financial_transaction: \[[^\]]*"finStructure"', block) and re.search(r'financial_transfer: \[[^\]]*"finStructure"', block)   # unfinished counts


class TestCardAgreesWithTheMixinAndTheApi:
    def test_every_identifier_the_card_uses_is_defined(self):
        defined = set(re.findall(r"\b(finClosing[A-Za-z]*)\s*[(:]", JS)) | set(re.findall(r"\bget (finClosing[A-Za-z]*)\(", JS))
        used = set(re.findall(r"\b(finClosing[A-Za-z]*)\b", _card()))
        assert used - defined == set(), used - defined

    def test_the_fields_the_card_reads_exist_in_the_api_model(self):
        for field in set(re.findall(r"\bc\.([a-z_]+)", _card())):
            assert field in YearClosingRow.model_fields, field
        for field in ("year_closed",):
            assert field in YearClosingResult.model_fields and field in JS
        assert {"financial_year_pk", "year_code", "year_status"} <= set(YearClosingListResponse.model_fields)

    def test_the_mixin_calls_only_routes_the_router_has(self):
        from api.routers.finance_closing import router

        paths = {r.path.replace("/api/v1/finance", "") for r in router.routes}
        assert "`/years/${year.financial_year_pk}/closings`" in JS
        assert "/years/{year_pk}/closings" in paths

    def test_every_kind_of_unfinished_work_is_shown(self):
        card = _card()
        assert "finClosingUnfinishedText(c)" in card and "finClosingUnfinishedCount(c)" in card
        for key in ("unfinished_transactions", "unfinished_transfers", "unfinished_receipts", "unfinished_payments", "unfinished_online_payments"):
            assert key in JS and key in YearClosingRow.model_fields

    def test_a_step_is_offered_only_where_the_server_says_the_caller_may(self):
        card = _card()
        assert 'x-show="c.can_act && c.next_status"' in card and "finClosingAct(c, c.next_status)" in card
        assert "if (!year || !row.can_act) return;" in JS                       # the page decides nothing about who may: the server's can_act

    def test_the_card_shows_only_while_a_year_can_still_close(self):
        assert 'x-show="finClosingYear && !finScope && !finScopeForm.show"' in _card()
        assert 'return y && ["OPEN", "CLOSING"].includes(y.status) ? y : null;' in JS


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
class TestUnderNode:
    def _run(self, body: str):
        start = JS.index("function financeClosingMixin() {")
        end = JS.index("    window.NSSFinanceClosing")
        script = f"""
        const NSS = {{ financeStatusLabel: (s) => "L:" + s }};
        const LABELS = {{ OPEN: "Open", CLOSING: "Closing", CLOSED: "Closed" }}, STEP_LABELS = {{ CLOSING: "Start closing", CLOSED: "Close books" }};
        {JS[start:end].rstrip()}
        const host = financeClosingMixin();
        host.finCurrentYear = null;
        const r = {{}};
        {body}
        console.log(JSON.stringify(r));
        """
        done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_labels_the_target_year_and_the_open_count(self):
        out = self._run("""
            r.labels = ["OPEN", "CLOSING", "CLOSED", "X"].map((s) => host.finClosingLabel(s));
            r.steps = ["CLOSING", "CLOSED"].map((s) => host.finClosingStepLabel(s));
            host.finCurrentYear = { status: "OPEN", year_code: "2026-27" }; r.open = host.finClosingTarget && host.finClosingTarget.year_code;
            host.finCurrentYear = { status: "CLOSING", year_code: "2026-27" }; r.closing = !!host.finClosingTarget;
            host.finCurrentYear = { status: "PLANNED", year_code: "2027-28" }; r.planned = host.finClosingTarget;
            host.finCurrentYear = { status: "CLOSED", year_code: "2025-26" }; r.closed = host.finClosingTarget;
            host.finCurrentYear = null; r.none = host.finClosingTarget;
            host.finClosings = [{ status: "CLOSED" }, { status: "OPEN" }, { status: "CLOSING" }]; r.left = host.finClosingsOpenCount;
            const row = { unfinished_transactions: 2, unfinished_transfers: 0, unfinished_receipts: 1, unfinished_payments: 0, unfinished_online_payments: 3 };
            r.text = host.finClosingUnfinishedText(row); r.count = host.finClosingUnfinishedCount(row); r.zero = host.finClosingUnfinishedCount({});
        """)
        assert out.pop("text") == "2 transaction(s), 1 draft receipt(s), 3 online payment(s)" and out.pop("count") == 6 and out.pop("zero") == 0
        assert out == {"labels": ["Open", "Closing", "Closed", "L:X"], "steps": ["Start closing", "Close books"], "open": "2026-27", "closing": True,
                       "planned": None, "closed": None, "none": None, "left": 2}
