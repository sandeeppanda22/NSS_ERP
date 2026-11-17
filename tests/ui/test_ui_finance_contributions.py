"""
Finance contributions UI (owner decision 2026-11-15) - DB-free source and node checks, runnable with ``--noconftest``.

  * admin console: the simple "Add a contribution" form, the copy-account form, "Update Sakhas" and the rules badges;
  * member dashboard: the contribution cards (paid / due colours, the amount box, the pay button) and the shared state map;
  * everything the pages send is a field the API really accepts, and nothing is shown that the API does not return.

Nothing here opens a browser; the card helpers and the state map are run under node against hostile / edge input.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
SETUP_JS = (FE / "assets/js/finance-setup.js").read_text(encoding="utf-8")
DASH_JS = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")
CONFIG_JS = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
BADGES = (FE / "assets/css/badges.css").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
DASH_HTML = (FE / "dashboard.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _contrib_form() -> str:
    return _between(ADMIN_HTML, "<!-- Simple contribution form", "<!-- Event form")


def _cards() -> str:
    return _between(DASH_HTML, "<!-- Your contributions:", "<!-- The payment in progress")


# ═══════════════════════════════════════════════════════════════════════
# Admin console
# ═══════════════════════════════════════════════════════════════════════

class TestAdminContributionForm:
    def test_the_form_binds_only_what_the_api_accepts(self):
        from api.schemas.finance import ContributionCreate

        form = _contrib_form()
        bound = {m.split(".")[1] for m in re.findall(r'x-model="(finContribForm\.[a-z_0-9.]+)"', form)} - {"organization"}
        assert bound <= set(ContributionCreate.model_fields), bound - set(ContributionCreate.model_fields)
        # the four things the owner asked for are all there
        assert {"head_name", "fixed_amount", "due_period", "allow_part_payment"} <= bound

    def test_the_submit_sends_exactly_the_contribution_fields(self):
        from api.schemas.finance import ContributionCreate

        body = _between(SETUP_JS, "async finContribSubmit()", "// A Sakha's copy of a Kendra contribution")
        assert '"/contributions"' in body
        sent = set(re.findall(r"\b(organization_pk|applies_to|head_name|description|fixed_amount|due_period|allow_part_payment|collection_account_pk):", body))
        assert sent == {"organization_pk", "applies_to", "head_name", "description", "fixed_amount", "due_period", "allow_part_payment", "collection_account_pk"}
        assert sent <= set(ContributionCreate.model_fields)
        # no code, direction, scope or UPI flag from the browser: the server decides those
        for forbidden in ("head_code", "direction", "collection_scope_pk", "allow_upi", "is_pranami", "is_restricted"):
            assert forbidden not in body, forbidden

    def test_the_form_checks_input_before_sending(self):
        body = _between(SETUP_JS, "async finContribSubmit()", "// A Sakha's copy of a Kendra contribution")
        assert "Choose the Sangha" in body and "needs a name" in body and "Choose how often" in body
        assert "MONEY_RE" in body and "<= 0" in body

    def test_amount_fields_appear_only_when_an_amount_is_typed(self):
        form = _contrib_form()
        assert form.count("finContribForm.fixed_amount.trim() !== ''") == 2        # how often + part payment
        assert "x-model=\"finContribForm.due_period\"" in form and "x-model=\"finContribForm.allow_part_payment\"" in form
        for value in ("YEARLY", "MONTHLY", "ONE_TIME"):
            assert f'value="{value}"' in form

    def test_all_sakhas_is_offered_for_the_kendra_only(self):
        form = _contrib_form()
        assert 'x-show="finContribIsKendra"' in form and 'value="ALL_SAKHAS"' in form
        assert 'o.type_code === "KENDRA"' in SETUP_JS
        assert 'if (!this.finContribIsKendra) f.applies_to = "ORGANIZATION"' in SETUP_JS
        # an all-Sakhas head collects nothing itself: the account box is hidden and not sent
        assert "finContribForm.applies_to !== 'ALL_SAKHAS'" in form
        assert 'collection_account_pk: allSakhas ? null' in SETUP_JS

    def test_the_buttons_are_for_approvers_only(self):
        assert re.search(r'x-show="canApproveFinance && !finHeadsAreEvents && !finHeadsAreTemplates" @click="finContribOpenCreate\(\)"', ADMIN_HTML)
        assert re.search(r'x-show="canApproveFinance && !h\.is_kendra_copy" @click="finHeadOpenEdit\(h\)"', ADMIN_HTML)
        assert re.search(r'x-show="canApproveFinance && h\.is_kendra_copy" @click="finCopyOpen\(h\)"', ADMIN_HTML)
        assert re.search(r'x-show="canApproveFinance && h\.applies_to_all_sakhas" @click="finHeadSyncCopies\(h\)"', ADMIN_HTML)

    def test_the_old_full_form_is_still_reachable_as_advanced(self):
        assert "'Advanced head'" in ADMIN_HTML and "finHeadOpenCreate()" in ADMIN_HTML

    def test_the_list_hides_while_a_contribution_form_is_open(self):
        assert 'x-show="!finHeadForm.show && !finContribForm.show && !finCopyForm.show"' in ADMIN_HTML
        assert "this.finContribForm.show || this.finCopyForm.show" in SETUP_JS            # an open form counts as busy for live refresh

    def test_the_forms_reset_when_the_tab_is_entered(self):
        assert "this.finContribForm = newContribForm(); this.finCopyForm = newCopyForm();" in SETUP_JS


class TestCopyAccountForm:
    def test_a_copy_sends_only_its_account(self):
        body = _between(SETUP_JS, "async finCopySubmit()", "// ── Events")
        assert 'PATCH' in body and "collection_account_pk" in body
        for forbidden in ("head_name", "fixed_amount", "due_period", "allow_part_payment", "is_pranami", "display_order"):
            assert forbidden not in body, forbidden

    def test_the_form_explains_what_follows_the_kendra(self):
        form = _between(ADMIN_HTML, "<!-- A Sakha's copy of a Kendra contribution", "<!-- Event form")
        assert "comes from the Kendra" in form and "x-model=\"finCopyForm.collection_account_pk\"" in form
        assert set(re.findall(r'x-model="([^"]+)"', form)) == {"finCopyForm.collection_account_pk"}

    def test_the_sync_button_posts_to_the_real_route(self):
        body = _between(SETUP_JS, "async finHeadSyncCopies(h)", "// A Sakha's copy of a Kendra contribution")
        assert "/sync-copies" in body and '"POST"' in body


class TestAdvancedFormAmountFields:
    def test_amount_fields_exist_on_edit_only(self):
        form = _between(ADMIN_HTML, "<!-- Simple contribution form", "<!-- Heads list -->") if False else ADMIN_HTML
        assert "finHeadForm.mode === 'edit' && finHeadForm.direction === 'INCOME'" in form
        body = _between(SETUP_JS, "async finHeadSubmit()", "// ── Contributions")
        assert "...fixed" in body and "const fixed = f.direction === \"INCOME\"" in body
        # create (POST /heads) never carries the amount: that is the simple form's job
        create = body.split('await this._finSend("POST", "/heads"')[1].split("});")[0]
        assert "fixed" not in create

    def test_the_edit_form_loads_the_current_amount(self):
        assert "fixed_amount: h.fixed_amount == null ? \"\" : String(h.fixed_amount)" in SETUP_JS
        assert "allow_part_payment: !!h.allow_part_payment" in SETUP_JS


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestRulesBadgesUnderNode:
    def _rules(self, head: dict):
        script = f"""
        const window = {{}}; const document = {{}};
        const NSS = {{ codeLabel: (c) => c, formatMoney: (v) => "Rs " + Number(v).toFixed(2) }};
        {SETUP_JS}
        const t = {{}}; window.NSSFinanceSetup.install(t);
        console.log(JSON.stringify(t.finHeadRules({json.dumps(head)})));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_a_yearly_head_shows_its_amount_and_schedule(self):
        assert self._rules({"fixed_amount": "500.00", "due_period": "YEARLY", "is_pranami": True, "allow_upi": True}) == ["Rs 500.00 yearly", "Pranami", "UPI"]

    def test_part_payment_is_flagged(self):
        assert "Part payment" in self._rules({"fixed_amount": "100", "due_period": "MONTHLY", "allow_part_payment": True})

    def test_a_kendra_source_shows_how_many_sakhas_hold_it(self):
        assert "All Sakhas (175)" in self._rules({"applies_to_all_sakhas": True, "copy_count": 175})

    def test_a_copy_says_where_it_stands(self):
        assert "Needs an account" in self._rules({"is_kendra_copy": True, "needs_account": True})
        assert "From the Kendra" in self._rules({"is_kendra_copy": True, "needs_account": False})

    def test_a_head_with_no_amount_shows_no_money(self):
        assert not any("Rs" in r for r in self._rules({"fixed_amount": None, "is_pranami": True}))


# ═══════════════════════════════════════════════════════════════════════
# Member dashboard
# ═══════════════════════════════════════════════════════════════════════

class TestMemberCardsMarkup:
    def test_no_inline_handlers_or_forms(self):
        cards = _cards()
        assert not re.search(r"\son[a-z]+\s*=", cards) and "<form" not in cards and 'x-init="init()"' not in cards

    def test_every_field_a_card_reads_exists_in_the_api_model(self):
        from api.schemas.finance import MyPayableHead

        for field in set(re.findall(r"\bh\.([a-z_]+)", _cards())):
            assert field in MyPayableHead.model_fields, field

    def test_cards_are_grouped_by_sangha_and_coloured_by_state(self):
        cards = _cards()
        assert "pranamiPayGroups()" in cards and "g.name" in cards
        assert "NSS.contributionState(h.state).card" in cards and "NSS.contributionState(h.state).badge" in cards

    def test_the_amount_box_never_decides_the_payer_or_the_head(self):
        cards = _cards()
        assert not re.search(r'x-model=', cards)
        assert "pranamiPay.amounts[h.finance_head_pk] = $event.target.value" in cards
        assert "sangha_sevi" not in cards and "person" not in cards

    def test_the_pay_button_names_the_exact_amount_for_a_full_payment_head(self):
        cards = _cards()
        assert "'Pay ' + NSS.formatMoney(h.due_amount)" in cards and "pranamiCardAsksAmount(h)" in cards

    def test_an_unavailable_card_says_why_instead_of_hiding(self):
        assert 'x-show="!h.payable" x-text="h.unavailable_reason"' in _cards()

    def test_waiting_money_is_reported_never_counted(self):
        cards = _cards()
        assert "waiting for the bank to confirm" in cards and "pending_amount" in cards

    def test_cards_hide_while_a_payment_is_in_progress(self):
        assert 'x-show="pranamiPay.heads.length > 0 && !pranamiPay.result"' in _cards()


class TestStateMap:
    STATES = ("PAID", "PART", "DUE", "OPEN")

    def test_every_state_the_server_can_return_has_a_label_badge_and_card_class(self):
        for state in self.STATES:
            row = re.search(rf'{state}: \{{ label: "([^"]+)", badge: "([^"]+)", card: "([^"]+)" \}}', CONFIG_JS)
            assert row, state
            assert re.search(rf"\.{row.group(2)}\s*\{{", BADGES), f"{row.group(2)} is not defined in badges.css"
            assert re.search(rf"\.{row.group(3)}\s*\{{", BADGES), f"{row.group(3)} is not defined in badges.css"

    def test_the_colours_are_green_amber_red_and_grey(self):
        colours = {s: re.search(rf"\.contrib-card-{s}\s*\{{ border-left: 4px solid (#[0-9a-f]{{6}})", BADGES).group(1) for s in ("paid", "part", "due", "open")}
        assert colours == {"paid": "#16a34a", "part": "#d97706", "due": "#dc2626", "open": "#9ca3af"}

    def test_the_states_match_what_the_service_returns(self):
        from api.services.finance_contribution import card_state
        from decimal import Decimal

        produced = {card_state(Decimal("10"), Decimal("10"))["state"], card_state(Decimal("10"), Decimal("4"))["state"],
                    card_state(Decimal("10"), Decimal("0"))["state"], card_state(None, Decimal("0"))["state"]}
        assert produced == set(self.STATES)

    def test_the_card_colours_do_not_redefine_the_shared_badges_inline(self):
        assert "badge-fin-live" in CONFIG_JS and ".badge-fin-live" in BADGES                 # reused, defined once
        assert not re.search(r"\.badge-fin-live\s*\{[^}]*\}[^.]*\.badge-fin-live", BADGES, re.S)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestCardHelpersUnderNode:
    """The pure helpers of dashboard.js (amount label, can-pay, amount box) run under node against edge cases."""

    def _run(self, expr: str, amounts: dict | None = None):
        helpers = _between(DASH_JS, "        pranamiCardAmountLabel(h) {", "        pranamiSafeUrl(url)")
        helpers = "pranamiCardAmountLabel(h) {" + helpers
        script = f"""
        const NSS = {{ formatMoney: (v) => "Rs " + Number(v).toFixed(2) }};
        const t = {{ pranamiPay: {{ amounts: {json.dumps(amounts or {})} }}, {helpers} }};
        console.log(JSON.stringify({expr}));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    @pytest.mark.parametrize("period, text", [("YEARLY", "Rs 500.00 per financial year"), ("MONTHLY", "Rs 500.00 per month"), ("ONE_TIME", "Rs 500.00, one time")])
    def test_amount_labels(self, period, text):
        assert self._run(f't.pranamiCardAmountLabel({{ fixed_amount: "500", due_period: "{period}" }})') == text

    def test_a_free_head_has_no_amount_label(self):
        assert self._run('t.pranamiCardAmountLabel({ fixed_amount: null, due_period: null })') == ""

    @pytest.mark.parametrize("head, can", [
        ({"payable": True, "state": "DUE", "fixed_amount": "500", "allow_part_payment": False, "pending_amount": "0"}, True),
        ({"payable": True, "state": "PAID", "fixed_amount": "500", "allow_part_payment": False, "pending_amount": "0"}, False),
        ({"payable": False, "state": "DUE", "fixed_amount": "500", "allow_part_payment": False, "pending_amount": "0"}, False),
        ({"payable": True, "state": "DUE", "fixed_amount": "500", "allow_part_payment": False, "pending_amount": "500"}, False),   # a full-payment head already waiting
        ({"payable": True, "state": "PART", "fixed_amount": "500", "allow_part_payment": True, "pending_amount": "100"}, True),     # parts may follow parts
        ({"payable": True, "state": "OPEN", "fixed_amount": None, "allow_part_payment": False, "pending_amount": "0"}, True),
    ])
    def test_can_pay(self, head, can):
        assert self._run(f"t.pranamiCardCanPay({json.dumps(head)})") is can

    def test_only_part_or_free_heads_ask_for_an_amount(self):
        assert self._run('t.pranamiCardAsksAmount({ fixed_amount: "500", allow_part_payment: false })') is False
        assert self._run('t.pranamiCardAsksAmount({ fixed_amount: "500", allow_part_payment: true })') is True
        assert self._run('t.pranamiCardAsksAmount({ fixed_amount: null, allow_part_payment: false })') is True

    def test_a_full_payment_head_is_always_paid_in_full_whatever_was_typed(self):
        head = '{ finance_head_pk: "p1", fixed_amount: "500", allow_part_payment: false, due_amount: "500.00" }'
        assert self._run(f"t.pranamiCardAmount({head})", {"p1": "1"}) == "500.00"

    def test_a_part_head_defaults_to_what_is_due_and_keeps_what_was_typed(self):
        head = '{ finance_head_pk: "p1", fixed_amount: "500", allow_part_payment: true, due_amount: "300.00" }'
        assert self._run(f"t.pranamiCardAmount({head})") == "300.00"
        assert self._run(f"t.pranamiCardAmount({head})", {"p1": "120"}) == "120"

    def test_a_free_head_starts_empty(self):
        assert self._run('t.pranamiCardAmount({ finance_head_pk: "p1", fixed_amount: null, allow_part_payment: false, due_amount: null })') == ""


class TestPayRequestFromTheCard:
    def test_the_pay_call_sends_the_head_and_the_amount_only(self):
        body = _between(DASH_JS, "async pranamiPayStart(h)", "_pranamiPayPoll(pk, tries) {")
        assert "finance_head_pk: p.head, amount }" in body
        assert "/api/v1/finance/my-pranami/pay" in body and "sangha_sevi" not in body and "person" not in body

    def test_the_amount_is_validated_before_sending(self):
        body = _between(DASH_JS, "async pranamiPayStart(h)", "_pranamiPayPoll(pk, tries) {")
        assert r"^\d+(\.\d{1,2})?$" in body and "<= 0" in body

    def test_closing_a_payment_reloads_the_cards(self):
        assert "this._loadPranamiPayHeads();" in _between(DASH_JS, "pranamiPayClose()", "pranamiLatestDate()")

    def test_a_paid_payment_refreshes_the_cards(self):
        poll = _between(DASH_JS, "_pranamiPayPoll(pk, tries) {", "pranamiPayClose()")
        assert 'this._loadPranami({ silent: true })' in poll          # which reloads the cards too (see _loadPranami)
        assert "this._loadPranamiPayHeads();" in _between(DASH_JS, "async _loadPranami(opts = {}) {", "// Financial years that have")
