"""
PDF receipt downloads (owner request 2026-11-17) - DB-free source and node checks, runnable with ``--noconftest``:

  * the shared helper ``NSS.downloadFile`` (fetch with the session token -> blob -> a saved file), run under node with stand-ins;
  * the member's Pranami tab and the "payment received" panel, and the admin console's receipts table, each call it for the real route;
  * nothing puts the token in a URL or opens the PDF through a plain link.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
CONFIG_JS = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
DASH_JS = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")
FIN_JS = (FE / "assets/js/finance.js").read_text(encoding="utf-8")
DASH_HTML = (FE / "dashboard.html").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _helper() -> str:
    return _between(CONFIG_JS, "    async downloadFile(url, fallbackName) {", "\n    },\n") + "\n    }"


class TestHelperSource:
    def test_it_uses_the_authenticated_fetch_and_a_blob_never_a_url_with_a_token(self):
        body = _helper()
        assert "NSSAuth.apiFetch(url)" in body and "res.blob()" in body and "URL.createObjectURL(blob)" in body
        assert "token" not in body.lower() and "window.open" not in body and "location" not in body

    def test_it_frees_the_object_url_and_removes_the_link(self):
        body = _helper()
        assert "URL.revokeObjectURL(href)" in body and "a.remove()" in body

    def test_it_throws_the_servers_own_message_on_a_refusal(self):
        assert "throw new Error(await this.extractError(res))" in _helper()

    def test_the_file_name_comes_from_the_server(self):
        assert "Content-Disposition" in _helper() and "fallbackName" in _helper()


class TestCallers:
    def test_the_member_download_calls_the_real_member_route(self):
        from api.main import app

        body = _between(DASH_JS, "async pranamiDownloadReceipt(receiptPk, receiptNumber)", "pranamiLatestDate()")
        assert "NSS.downloadFile(`/api/v1/finance/my-pranami/receipts/${receiptPk}/pdf`" in body
        paths = {r.path for r in app.routes}
        assert "/api/v1/finance/my-pranami/receipts/{receipt_pk}/pdf" in paths
        assert "this.pranami.receiptError = err.message" in body                    # a refusal is shown, not swallowed

    def test_the_admin_download_calls_the_real_admin_route(self):
        from api.main import app

        body = _between(FIN_JS, "async finDownloadReceipt(r)", "// Receipts")
        assert "NSS.downloadFile(`${BASE}/receipts/${r.financial_receipt_pk}/pdf`" in body and BASE_OK()
        assert "/api/v1/finance/receipts/{receipt_pk}/pdf" in {r.path for r in app.routes}
        assert "this.finEvidenceError = err.message" in body

    def test_the_pranami_history_offers_a_download_for_every_receipt(self):
        panel = _between(DASH_HTML, "<!-- ── Pranami (Finance, Tier 12) ──", "<div x-show=\"tab === 'documents'\">")
        assert '@click="pranamiDownloadReceipt(r.financial_receipt_pk, r.receipt_number)"' in panel and ">Download PDF<" in panel
        from api.schemas.finance import MyPranamiReceipt

        assert "financial_receipt_pk" in MyPranamiReceipt.model_fields

    def test_the_payment_received_panel_offers_the_new_receipt_at_once(self):
        panel = _between(DASH_HTML, "Payment received. Thank you", "pranamiPayClose()\">Done")
        assert "pranamiPayStart" not in panel
        assert 'x-show="pranamiPay.result && pranamiPay.result.financial_receipt_pk && pranamiPay.result.items.length === 0"' in panel
        assert "pranamiDownloadReceipt(pranamiPay.result.financial_receipt_pk, pranamiPay.result.receipt_number)" in panel
        from api.schemas.finance import MyPayment

        assert "financial_receipt_pk" in MyPayment.model_fields

    def test_the_admin_table_downloads_issued_and_cancelled_receipts_only(self):
        assert """x-show="['ISSUED','CANCELLED'].includes(r.status)" @click="finDownloadReceipt(r)">Download PDF""" in ADMIN_HTML

    def test_no_page_links_to_the_pdf_directly(self):
        for html in (DASH_HTML, ADMIN_HTML):
            assert not re.search(r'href="[^"]*/pdf"', html) and ":href=\"`/api/v1/finance" not in html


def BASE_OK() -> bool:
    return 'const BASE = "/api/v1/finance";' in FIN_JS


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestHelperUnderNode:
    def _run(self, response: dict, fallback: str | None = "fallback.pdf") -> dict:
        script = f"""
        const RESP = {json.dumps(response)};
        const clicked = []; const revoked = []; const created = [];
        globalThis.document = {{
            createElement: () => ({{ click() {{ clicked.push({{ href: this.href, name: this.download }}); }}, remove() {{ this.removed = true; }} }}),
            body: {{ appendChild() {{}} }},
        }};
        URL.createObjectURL = (b) => {{ created.push(b); return "blob:test"; }};
        URL.revokeObjectURL = (u) => revoked.push(u);
        globalThis.NSSAuth = {{ apiFetch: async (url) => ({{
            ok: RESP.ok, status: RESP.status, headers: {{ get: (h) => (h === "Content-Disposition" ? RESP.cd : null) }},
            blob: async () => "BLOB", json: async () => RESP.body,
        }}) }};
        {CONFIG_JS}
        (async () => {{
            let error = null;
            try {{ await NSS.downloadFile("/x", {json.dumps(fallback)}); }} catch (e) {{ error = e.message; }}
            await new Promise((r) => setTimeout(r, 10));
            console.log(JSON.stringify({{ clicked, created: created.length, error }}));
            process.exit(0);
        }})();
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_it_saves_the_file_under_the_servers_name(self):
        r = self._run({"ok": True, "status": 200, "cd": 'attachment; filename="NSS-Receipt-RCT9.pdf"'})
        assert r["error"] is None and r["created"] == 1
        assert r["clicked"] == [{"href": "blob:test", "name": "NSS-Receipt-RCT9.pdf"}]

    def test_it_falls_back_to_the_given_name(self):
        r = self._run({"ok": True, "status": 200, "cd": None})
        assert r["clicked"][0]["name"] == "fallback.pdf"

    def test_it_falls_back_to_a_generic_name(self):
        assert self._run({"ok": True, "status": 200, "cd": None}, fallback=None)["clicked"][0]["name"] == "download"

    def test_a_refusal_throws_and_saves_nothing(self):
        r = self._run({"ok": False, "status": 404, "cd": None, "body": {"detail": "Receipt not found."}})
        assert r["clicked"] == [] and r["created"] == 0 and "Receipt not found" in r["error"]


# ═══════════════════════════════════════════════════════════════════════
# The History view of the Pranami tab
# ═══════════════════════════════════════════════════════════════════════

def _pranami_panel() -> str:
    return _between(DASH_HTML, "<div x-show=\"tab === 'pranami'\">", "<!-- ── Finance approvals")


def _history() -> str:
    return _between(_pranami_panel(), "<!-- History: every payment", "</table>")


class TestPranamiHistoryView:
    def test_two_views_one_default(self):
        panel = _pranami_panel()
        assert "pranami.view = 'pay'" in panel and "pranami.view = 'history'" in panel
        assert 'view: "pay"' in DASH_JS                                          # opens on what to pay
        assert panel.index("pranami.view = 'pay'") < panel.index("pranami.view = 'history'")

    def test_each_view_shows_only_its_own_blocks(self):
        panel = _pranami_panel()
        assert "x-show=\"pranami.view === 'pay' && pranamiPay.heads.length > 0 && !pranamiPay.result\"" in panel     # the contribution cards
        assert "x-show=\"pranami.view === 'pay' && pranamiPay.result\"" in panel                                      # the payment in progress
        assert "x-show=\"pranami.view === 'history' && pranamiFiltered().length > 0\"" in panel                       # the history table
        assert "x-show=\"pranami.view === 'history'\"" in panel                                                       # totals + year filter

    def test_the_history_is_a_table_with_a_download_on_every_receipt_row(self):
        h = _history()
        for header in ("Date", "Towards", "Paid to", "Method", "Status", "Receipt"):
            assert f"<th>{header}</th>" in h, header
        assert ">Amount</th>" in h
        assert '@click="pranamiDownloadReceipt(r.financial_receipt_pk, r.receipt_number)"' in h and ">Download PDF<" in h
        assert 'x-for="r in p.receipts" :key="r.financial_receipt_pk"' in h
        assert "No receipt yet" in h                                       # a row without a receipt says so, with no dead button

    def test_every_field_the_history_reads_exists_in_the_api_models(self):
        from api.schemas.finance import MyPranamiItem, MyPranamiReceipt

        h = _history()
        for field in set(re.findall(r"\bp\.([a-z_]+)", h)):
            assert field in MyPranamiItem.model_fields, field
        for field in set(re.findall(r"\br\.([a-z_]+)", h)):
            assert field in MyPranamiReceipt.model_fields, field

    def test_the_year_filter_and_totals_belong_to_the_history_view(self):
        summary = _between(_pranami_panel(), "<div class=\"data-card\" x-show=\"pranami.view === 'history'\">", "<!-- Your contributions")
        assert "pranamiTotal()" in summary and 'x-model="pranami.year"' in summary and "pranamiYears()" in summary

    def test_the_history_shows_no_counts_or_internal_numbers(self):
        # owner 2026-11-18: no "N contributions" badge, and no transaction / receipt numbers on screen (the receipt number only names the PDF file)
        panel = _pranami_panel()
        assert 'x-text="pranamiFiltered().length' not in panel
        for shown in ("p.transaction_reference", 'x-text="r.receipt_number"', "x-text=\"'· ' + it.receipt_number\""):
            assert shown not in _history(), shown

    def test_the_history_has_professional_filters_over_the_members_own_list(self):
        panel = _pranami_panel()
        for model in ("pranami.year", "pranami.head", "pranami.org", "pranami.method", "pranami.from", "pranami.to"):
            assert f'x-model="{model}"' in panel, model
        assert "pranamiClearFilters()" in panel and "pranamiFiltersActive()" in panel
        body = DASH_JS.split("pranamiFiltered() {")[1].split("pranamiTotal()")[0]
        for field in ("year_code", "transaction_date", "payment_method_name"):
            assert field in body, field

    def test_nothing_to_pay_points_to_the_history(self):
        panel = _pranami_panel()
        assert "There is nothing for you to pay right now" in panel and "in History" in panel

    def test_the_history_page_has_no_inline_handlers(self):
        panel = _pranami_panel()
        assert not re.search(r"\son[a-z]+\s*=", panel) and "<form" not in panel
        assert set(re.findall(r'x-model="([^"]+)"', panel)) == {"pranami.year", "pranami.head", "pranami.org", "pranami.method", "pranami.from", "pranami.to"}

    def test_no_x_show_carries_an_inline_display(self):
        for line in _pranami_panel().splitlines():
            if "x-show=" in line:
                assert not re.search(r'style="[^"]*display\s*:\s*(flex|grid)', line), line.strip()[:120]


class TestThePaymentSummaryButton:
    """Owner 2026-11-20: a payment for several contributions can be downloaded as ONE summary page (each contribution keeps its own receipt)."""

    def test_the_button_shows_only_for_a_multi_item_payment_and_calls_the_summary_endpoint(self):
        html = (FE / "dashboard.html").read_text(encoding="utf-8")
        js = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")
        line = next(l for l in html.splitlines() if "pranamiDownloadSummary(" in l)
        assert "Download payment summary (PDF)" in html
        block = html[html.index("Download payment summary (PDF)") - 420: html.index("Download payment summary (PDF)")]
        assert "pranamiPay.result.items.length > 1" in block
        assert "NSS.downloadFile(`/api/v1/finance/my-pranami/requests/${requestPk}/summary-pdf`" in js
        from api.main import app

        assert "/api/v1/finance/my-pranami/requests/{request_pk}/summary-pdf" in {r.path for r in app.routes}
