"""
Paying several contributions at once (owner request 2026-11-17) - DB-free source and node checks, runnable with ``--noconftest``: the
tick boxes on the cards, the "pay all together" bar, the request sent, and the selection helpers run under node (one Sangha at a time,
the total in whole paise, nothing selectable that cannot be paid).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
DASH_JS = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")
DASH_HTML = (FE / "dashboard.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _panel() -> str:
    return _between(DASH_HTML, "<div x-show=\"tab === 'pranami'\">", "<!-- ── Finance approvals")


class TestMarkup:
    def test_each_payable_card_has_a_tick_box_that_never_uses_a_model(self):
        panel = _panel()
        assert 'type="checkbox" :checked="!!pranamiPay.selected[h.finance_head_pk]" :disabled="pranamiSelectDisabled(h)" @change="pranamiToggle(h)"' in panel
        assert set(re.findall(r'x-model="([^"]+)"', panel)) == {"pranami.year", "pranami.head", "pranami.org", "pranami.method", "pranami.from", "pranami.to"}

    def test_the_tick_box_is_only_for_a_card_that_can_be_paid(self):
        assert 'x-show="pranamiCardCanPay(h)"' in _between(_panel(), "Pay together with others", "</label>") or "pranamiCardCanPay(h)" in _panel().split("Pay together with others")[0].rsplit("<label", 1)[1]

    def test_the_pay_all_bar_needs_two_or_more_and_only_on_the_pay_view(self):
        panel = _panel()
        assert "x-show=\"pranami.view === 'pay' && !pranamiPay.result && pranamiSelectedHeads().length >= 2\"" in panel
        bar = _between(panel, "<!-- The ticked contributions of one Sangha", "<!-- The payment in progress")
        assert '@click="pranamiPayMultiple()"' in bar and '@click="pranamiClearSelection()"' in bar and "pranamiSelectedTotal()" in bar

    def test_a_group_offers_select_all_when_two_can_be_paid(self):
        assert 'x-show="pranamiGroupPayableCount(g) >= 2" @click="pranamiSelectGroup(g)"' in _panel()

    def test_the_result_lists_the_items_and_one_download_per_receipt(self):
        panel = _panel()
        block = _between(panel, 'x-show="pranamiPay.result && pranamiPay.result.items.length > 0"', "['CREATED','PENDING']")
        assert 'x-for="it in (pranamiPay.result ? pranamiPay.result.items : [])"' in block
        assert 'pranamiDownloadReceipt(it.financial_receipt_pk, it.receipt_number)' in block
        from api.schemas.finance import MyPaymentItem

        for field in set(re.findall(r"\bit\.([a-z_]+)", block)):
            assert field in MyPaymentItem.model_fields, field

    def test_the_single_download_button_is_only_for_a_single_payment(self):
        assert "pranamiPay.result.financial_receipt_pk && pranamiPay.result.items.length === 0" in _panel()

    def test_no_x_show_carries_an_inline_display(self):
        for line in _panel().splitlines():
            if "x-show=" in line:
                assert not re.search(r'style="[^"]*display\s*:\s*(flex|grid)', line), line.strip()[:110]


class TestRequest:
    def test_it_posts_only_heads_and_amounts_to_the_real_route(self):
        from api.main import app

        body = _between(DASH_JS, "async pranamiPayMultiple()", "async pranamiPayStart(h)")
        assert '"/api/v1/finance/my-pranami/pay-multiple"' in body and "JSON.stringify({ items })" in body
        assert "items.push({ finance_head_pk: h.finance_head_pk, amount })" in body
        for forbidden in ("person", "sangha_sevi", "account", "organization"):
            assert forbidden not in body, forbidden
        assert "/api/v1/finance/my-pranami/pay-multiple" in {r.path for r in app.routes}

    def test_it_checks_the_selection_and_every_amount_before_sending(self):
        body = _between(DASH_JS, "async pranamiPayMultiple()", "async pranamiPayStart(h)")
        assert "heads.length < 2" in body and r"^\d+(\.\d{1,2})?$" in body and body.index("heads.length < 2") < body.index("apiFetch")

    def test_the_payment_is_polled_like_a_single_one_and_the_selection_cleared(self):
        body = _between(DASH_JS, "async pranamiPayMultiple()", "async pranamiPayStart(h)")
        assert "this._pranamiPayPoll(p.result.upi_payment_request_pk, 0)" in body and "p.selected = {}" in body

    def test_closing_the_panel_clears_the_ticks(self):
        assert "this.pranamiPay.selected = {};" in _between(DASH_JS, "pranamiPayClose()", "pranamiLatestDate()")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestSelectionUnderNode:
    HEADS = [
        {"finance_head_pk": "a", "organization_pk": "SAKHA", "head_name": "Annual", "payable": True, "state": "DUE", "fixed_amount": "500", "allow_part_payment": False, "pending_amount": "0", "due_amount": "500.00"},
        {"finance_head_pk": "b", "organization_pk": "SAKHA", "head_name": "Monthly", "payable": True, "state": "DUE", "fixed_amount": "100", "allow_part_payment": False, "pending_amount": "0", "due_amount": "100.00"},
        {"finance_head_pk": "c", "organization_pk": "SAKHA", "head_name": "Donation", "payable": True, "state": "OPEN", "fixed_amount": None, "allow_part_payment": False, "pending_amount": "0", "due_amount": None},
        {"finance_head_pk": "k", "organization_pk": "KENDRA", "head_name": "Kendra", "payable": True, "state": "DUE", "fixed_amount": "50", "allow_part_payment": False, "pending_amount": "0", "due_amount": "50.00"},
        {"finance_head_pk": "x", "organization_pk": "SAKHA", "head_name": "Paid", "payable": True, "state": "PAID", "fixed_amount": "10", "allow_part_payment": False, "pending_amount": "0", "due_amount": "0.00"},
        {"finance_head_pk": "n", "organization_pk": "SAKHA", "head_name": "Not set up", "payable": False, "state": "DUE", "fixed_amount": "10", "allow_part_payment": False, "pending_amount": "0", "due_amount": "10.00"},
    ]

    def _run(self, statements: str, expr: str, amounts: dict | None = None):
        helpers = _between(DASH_JS, "        pranamiCardAmountLabel(h) {", "        async pranamiPayMultiple() {")
        helpers = "pranamiCardAmountLabel(h) {" + helpers
        script = f"""
        const NSS = {{ formatMoney: (v) => "Rs " + Number(v).toFixed(2) }};
        const t = {{ pranamiPay: {{ heads: {json.dumps(self.HEADS)}, amounts: {json.dumps(amounts or {})}, selected: {{}} }}, {helpers} }};
        {statements}
        console.log(JSON.stringify({expr}));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_ticking_selects_and_unticking_clears(self):
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]); t.pranamiToggle(t.pranamiPay.heads[0]);", "t.pranamiSelectedHeads().length") == 0
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]);", "t.pranamiSelectedHeads().map(h => h.finance_head_pk)") == ["a"]

    def test_only_one_sangha_can_be_selected_at_a_time(self):
        r = self._run("t.pranamiToggle(t.pranamiPay.heads[0]);", "[t.pranamiSelectDisabled(t.pranamiPay.heads[3]), t.pranamiSelectDisabled(t.pranamiPay.heads[1])]")
        assert r == [True, False]                                           # the Kendra card is blocked, a Sakha card is not
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]); t.pranamiToggle(t.pranamiPay.heads[3]);", "t.pranamiSelectedHeads().length") == 1

    def test_a_card_that_cannot_be_paid_can_never_be_selected(self):
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[4]); t.pranamiToggle(t.pranamiPay.heads[5]);", "t.pranamiSelectedHeads().length") == 0
        assert self._run("", "[t.pranamiSelectDisabled(t.pranamiPay.heads[4]), t.pranamiSelectDisabled(t.pranamiPay.heads[5])]") == [True, True]

    def test_the_total_is_in_whole_paise(self):
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]); t.pranamiToggle(t.pranamiPay.heads[1]);", "t.pranamiSelectedPaise()") == 60000
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]); t.pranamiToggle(t.pranamiPay.heads[2]);",
                         "t.pranamiSelectedPaise()", {"c": "0.1"}) == 50010            # 500.00 + 0.10, never 500.10000000000001
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[1]); t.pranamiToggle(t.pranamiPay.heads[2]);",
                         "t.pranamiSelectedPaise()", {"c": "0.3"}) == 10030
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]);", "t.pranamiSelectedTotal()") == "Rs 500.00"

    def test_a_full_payment_card_always_counts_its_whole_due_amount(self):
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]);", "t.pranamiSelectedPaise()", {"a": "1"}) == 50000

    def test_select_all_picks_every_payable_card_of_the_group_and_replaces_the_old_selection(self):
        statements = "t.pranamiToggle(t.pranamiPay.heads[3]); t.pranamiSelectGroup({ heads: t.pranamiPay.heads.filter(h => h.organization_pk === 'SAKHA') });"
        assert self._run(statements, "t.pranamiSelectedHeads().map(h => h.finance_head_pk).sort()") == ["a", "b", "c"]

    def test_clear_and_the_group_count(self):
        assert self._run("t.pranamiToggle(t.pranamiPay.heads[0]); t.pranamiClearSelection();", "t.pranamiSelectedHeads().length") == 0
        assert self._run("", "t.pranamiGroupPayableCount({ heads: t.pranamiPay.heads.filter(h => h.organization_pk === 'SAKHA') })") == 3


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestAPartPaymentShowsTheBalanceNextTime:
    """Owner 2026-11-19: after a member pays part of a head, the next visit shows what is still due, not the amount they typed last time."""

    PART = {"finance_head_pk": "p", "organization_pk": "SAKHA", "head_name": "Annual", "payable": True, "state": "DUE", "fixed_amount": "110",
            "allow_part_payment": True, "pending_amount": "0", "due_amount": "110.00"}

    def _run(self, statements: str, expr: str):
        helpers = _between(DASH_JS, "        pranamiCardAmountLabel(h) {", "        async pranamiPayMultiple() {")
        helpers = "pranamiCardAmountLabel(h) {" + helpers
        script = f"""
        const NSS = {{ formatMoney: (v) => "Rs " + Number(v).toFixed(2) }};
        const t = {{ pranamiPay: {{ heads: [{json.dumps(self.PART)}], amounts: {{}}, selected: {{}} }}, {helpers} }};
        {statements}
        console.log(JSON.stringify({expr}));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_the_box_starts_at_what_is_due_and_keeps_what_the_member_types(self):
        assert self._run("", "t.pranamiCardAmount(t.pranamiPay.heads[0])") == "110.00"
        assert self._run('t.pranamiPay.amounts.p = "50";', "t.pranamiCardAmount(t.pranamiPay.heads[0])") == "50"

    def test_after_a_part_payment_the_typed_amount_is_replaced_by_the_new_balance(self):
        script = """
        t._forgetStaleTypedAmounts();                                   // first look: remembers the due amount
        t.pranamiPay.amounts.p = "50";                                  // the member types 50 and pays it
        t.pranamiPay.heads = [Object.assign({}, t.pranamiPay.heads[0], { due_amount: "60.00", paid_amount: "50.00", state: "PART" })];
        t._forgetStaleTypedAmounts();                                   // the cards reload: 60 is now due
        """
        assert self._run(script, "t.pranamiCardAmount(t.pranamiPay.heads[0])") == "60.00"

    def test_a_typed_amount_survives_a_reload_that_changed_nothing(self):
        script = """
        t._forgetStaleTypedAmounts();
        t.pranamiPay.amounts.p = "50";
        t._forgetStaleTypedAmounts();
        """
        assert self._run(script, "t.pranamiCardAmount(t.pranamiPay.heads[0])") == "50"

    def test_the_card_names_the_balance_next_to_the_amount_box(self):
        assert "'Amount (₹) — balance due ' + NSS.formatMoney(h.due_amount)" in DASH_HTML
