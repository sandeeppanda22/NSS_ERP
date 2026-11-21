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
        # "direction" picks Money in (a contribution) or Money out (a plain EXPENSE head via /heads); it is not a ContributionCreate field
        assert bound - {"direction"} <= set(ContributionCreate.model_fields), bound - set(ContributionCreate.model_fields)
        assert {"head_name", "fixed_amount", "due_period", "allow_part_payment"} <= bound

    def test_the_submit_sends_exactly_the_contribution_fields(self):
        from api.schemas.finance import ContributionCreate

        body = _between(SETUP_JS, "async finContribSubmit()", "// A Sakha's copy of a Kendra contribution")
        assert '"/contributions"' in body
        contribution = body.split('"/contributions"', 1)[1]            # the income path; the expense path posts a plain head first
        sent = set(re.findall(r"\b(organization_pk|applies_to|head_name|description|fixed_amount|due_period|allow_part_payment|collection_account_pk|collection_scope_pk|collection_fund_pk|open_portal):", contribution))
        assert sent == {"organization_pk", "applies_to", "head_name", "description", "fixed_amount", "due_period", "allow_part_payment", "collection_account_pk",
                        "collection_scope_pk", "collection_fund_pk", "open_portal"}
        assert sent <= set(ContributionCreate.model_fields)
        assert "open_portal: false" in contribution, "a new head starts with its payment portal closed"
        # the scope / fund are the person's OPTIONAL choice (empty = the server uses the Sangha's general scope; owner 2026-11-20); the UPI and
        # Pranami flags stay the server's decision
        for forbidden in ("allow_upi", "is_pranami", "is_restricted"):
            assert forbidden not in body, forbidden
        expense = body.split('"/contributions"', 1)[0]
        assert 'direction: "EXPENSE"' in expense and "/heads" in expense

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
        assert 'x-show="finContribIsKendra && finContribForm.direction === \'INCOME\'"' in form and 'value="ALL_SAKHAS"' in form
        assert 'o.type_code === "KENDRA"' in SETUP_JS
        assert 'if (!this.finContribIsKendra) f.applies_to = "ORGANIZATION"' in SETUP_JS
        # a new head has no receiving account box: the portal uses the Sangha's default account when it is opened
        assert "finContribForm.collection_account_pk" not in form

    def test_the_buttons_are_for_configurers_only(self):
        assert re.search(r'x-show="canConfigureFinance" @click="finContribOpenCreate\(\)">\+ Create head', ADMIN_HTML)
        assert re.search(r'x-show="canConfigureFinance && h\.status === \'ACTIVE\' && finHeadPortalOpen\(h\) === false" @click="finHeadPortalOpenForm\(h\)"', ADMIN_HTML)
        assert re.search(r'x-show="canConfigureFinance && h\.status === \'ACTIVE\' && finHeadPortalOpen\(h\) === true && !h\.applies_to_all_sakhas" @click="finHeadPortal\(h, false\)"', ADMIN_HTML)

    def test_the_old_full_form_is_no_longer_offered(self):
        # Simple page (owner 2026-11-18): the advanced head form, templates, events and per-row editing are not reachable from the page.
        assert "'+ New head'" not in ADMIN_HTML and "@click=\"finHeadOpenCreate()\"" not in ADMIN_HTML

    def test_the_list_hides_while_a_contribution_form_is_open(self):
        assert 'x-show="!finHeadForm.show && !finContribForm.show && !finCopyForm.show && !finPortalForm.show"' in ADMIN_HTML
        assert "this.finContribForm.show || this.finPortalForm.show || this.finCopyForm.show" in SETUP_JS            # an open form counts as busy for live refresh

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
        assert "x-show=\"pranami.view === 'pay' && pranamiPay.heads.length > 0 && !pranamiPay.result\"" in _cards()


class TestStateMap:
    STATES = ("PAID", "PART", "DUE", "OPEN")

    def test_every_state_the_server_can_return_has_a_label_badge_and_card_class(self):
        for state in self.STATES:
            row = re.search(rf'{state}: \{{ label: "([^"]+)", badge: "([^"]+)", card: "([^"]+)" \}}', CONFIG_JS)
            assert row, state
            assert re.search(rf"\.{row.group(2)}\s*\{{", BADGES), f"{row.group(2)} is not defined in badges.css"
            assert re.search(rf"\.{row.group(3)}\s*\{{", BADGES), f"{row.group(3)} is not defined in badges.css"

    def test_the_colours_are_green_amber_red_and_grey(self):
        colours = {s: re.search(rf"\.contrib-card-{s}\s*\{{ border-color: #[0-9a-f]{{6}}; border-left: 4px solid (#[0-9a-f]{{6}})", BADGES).group(1)
                   for s in ("paid", "part", "due", "open")}
        assert colours == {"paid": "#16a34a", "part": "#d97706", "due": "#dc2626", "open": "#9ca3af"}

    def test_every_card_has_a_full_visible_outline(self):
        # owner 2026-11-18: a bare left bar on a white card was too faint to tell the cards apart
        assert re.search(r"\.contrib-card-paid, \.contrib-card-part, \.contrib-card-due, \.contrib-card-open \{ border: 1px solid #[0-9a-f]{6}; box-shadow:", BADGES)

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


class TestOpenPortalAsksForTheAmount:
    """Owner 2026-11-18: opening a head's payment portal asks what members are to pay."""

    def test_the_button_opens_a_form_and_the_form_sends_the_amount_fields(self):
        from api.schemas.finance import PortalToggle

        assert 'finHeadPortalOpenForm(h)">Open payment portal' in ADMIN_HTML
        body = _between(SETUP_JS, "async finPortalSubmit()", "async finHeadPortal(h, open)")
        assert "/portal" in body and "fixed_amount" in body and "due_period" in body and "allow_part_payment" in body
        assert {"open", "fixed_amount", "due_period", "allow_part_payment"} <= set(PortalToggle.model_fields)
        assert "MONEY_RE" in body and "<= 0" in body

    def test_a_kendra_copy_is_not_asked_for_an_amount(self):
        body = _between(SETUP_JS, "async finPortalSubmit()", "async finHeadPortal(h, open)")
        assert "follows_kendra ? { open: true }" in body
        assert "set by the Kendra" in ADMIN_HTML

    def test_the_form_counts_as_busy_for_live_refresh(self):
        assert "this.finPortalForm.show" in SETUP_JS


class TestThePaymentPageIsACheckout:
    """Owner 2026-11-18: the member's "Your payment" panel looks like a real checkout."""

    def _panel(self):
        return _between(DASH_HTML, "<!-- The payment in progress / its outcome", 'x-show="pranami.loading"')

    def test_it_shows_the_summary_the_steps_and_every_outcome(self):
        panel = self._panel()
        for needle in ("Amount to pay", "Paying to", "Paid by", "Payment reference", "Valid for", "Pay with UPI, a card or net banking",
                       "Payment received. Thank you!", "Payment did not go through", "Review", "Receipt", "pranamiExpiresIn()"):
            assert needle in panel, needle

    def test_the_demo_box_is_shown_only_for_a_demo_payment_and_offers_both_outcomes(self):
        panel = self._panel()
        assert 'x-show="pranamiPay.result && pranamiPay.result.demo_payable"' in panel and "TEST MODE" in panel
        assert "pranamiDemoPay('paid')" in panel and "pranamiDemoPay('failed')" in panel
        body = _between(DASH_JS, "async pranamiDemoPay(", "pranamiPayClose()")
        assert "/demo-pay?outcome=" in body and '"failed" : "paid"' in body

    def test_the_countdown_ticks_only_while_waiting_and_is_cleared_on_close(self):
        assert "_pranamiStartClock()" in _between(DASH_JS, "async pranamiPayStart(h)", "_pranamiPayPoll(pk, tries) {")
        assert "clearInterval(this._pranamiClock)" in _between(DASH_JS, "pranamiPayClose()", "// The \"valid for")
        clock = _between(DASH_JS, "_pranamiStartClock() {", "pranamiExpiresIn() {")
        assert '["CREATED", "PENDING"].includes(r.status)' in clock and "clearInterval" in clock

    def test_the_server_offers_both_demo_outcomes_and_no_other(self):
        import inspect
        from api.routers import finance_upi

        src = inspect.getsource(finance_upi.demo_pay_my_request)
        assert 'pattern="^(paid|failed)$"' in src and "payment.failed" in src


class TestAWaitingPaymentCanBeResumedOrCancelled:
    """Owner 2026-11-18: leaving the payment page (Back, reload) must not leave an unexplained "waiting for the bank"."""

    def test_the_panel_cancel_really_cancels_and_back_does_not(self):
        panel = _between(DASH_HTML, "<!-- The payment in progress / its outcome", 'x-show="pranami.loading"')
        assert "pranamiCancelRequest(pranamiPay.result.upi_payment_request_pk)" in panel and ">Cancel payment<" in panel
        assert '@click="pranamiPayClose()">← Back to my Pranami' in panel          # Back only leaves; the request stays waiting

    def test_a_waiting_card_offers_resume_and_cancel(self):
        cards = _between(DASH_HTML, "<!-- Your contributions:", "<!-- The ticked contributions")
        assert 'x-show="Number(h.pending_amount) > 0 && h.pending_request_pk"' in cards
        assert 'pranamiResume(h)' in cards and 'pranamiCancelRequest(h.pending_request_pk)' in cards

    def test_the_handlers_call_the_member_routes_only(self):
        resume = _between(DASH_JS, "async pranamiResume(h)", "async pranamiCancelRequest(")
        cancel = _between(DASH_JS, "async pranamiCancelRequest(", "// DEMO gateway only")
        assert "/api/v1/finance/my-pranami/requests/${h.pending_request_pk}" in resume and "_pranamiPayPoll" in resume
        assert "/cancel" in cancel and '"POST"' in cancel and "NSSDialog.confirm" in cancel

    def test_the_server_cancels_only_the_callers_unpaid_request(self):
        import inspect
        from api.routers import finance_upi
        from api.schemas.finance import MyPayableHead

        src = inspect.getsource(finance_upi.cancel_my_request)
        assert "_not_found" in src and "_UNPAID" in src and '"status": "CANCELLED"' in src
        assert "pending_request_pk" in MyPayableHead.model_fields


class TestTheHeadsPageLayout:
    """Owner 2026-11-18: the Finance heads page is a clean header + tiles + toolbar + table, not a wall of badges."""

    def _page(self):
        return _between(ADMIN_HTML, "<div x-show=\"activeTab === 'finSetup'\" x-cloak>", "<!-- Account form -->")

    def test_a_locked_sangha_is_shown_as_a_chip_and_only_an_open_scope_asks(self):
        page = self._page()
        assert 'class="fh-chip" x-show="finSetupOrgLocked && finSetupOrg.selected"' in page
        assert 'class="fh-page__picker" x-show="!finSetupOrgLocked"' in page
        assert "(SAKHA_SANGHA)" not in page and "type_name: NSS.codeLabel(sc.organization_type_code)" in SETUP_JS

    def test_the_toolbar_filters_by_search_type_and_portal(self):
        page = self._page()
        for model in ("finHeadQ", "finHeadDirFilter", "finHeadPortalFilter"):
            assert f'x-model="{model}"' in page, model
        assert "finHeadsShown()" in page and "finHeadsMultiOrg()" in page

    def test_the_table_shows_amount_and_portal_not_rule_badges(self):
        page = self._page()
        for header in ("Head", "Scope", "Fund", "Members pay", "Portal"):
            assert f"<th>{header}</th>" in page, header
        assert "finHeadRules(h)" not in page and "No approval needed" not in page
        assert "finHeadAmountMain(h)" in page and "finHeadAmountPer(h)" in page and "Part payments allowed" in page

    def test_the_helpers_exist(self):
        for fn in ("finHeadsShown()", "finHeadsPortalCount(open)", "finHeadsMultiOrg()", "finHeadAmountLabel(h)", "finHeadAmountMain(h)", "finHeadAmountPer(h)"):
            assert fn in SETUP_JS, fn


class TestThePayerPickerOfAPaymentRequest:
    """Owner 2026-11-18: asking a member for a UPI payment shows matching names while typing."""

    def test_matches_appear_while_typing_and_picking_sets_the_member_id(self):
        form = _between(ADMIN_HTML, 'x-show="finReqForm.show" x-cloak>', "Create payment request")
        assert 'x-model="finReqForm.member.query"' in form and '@input="finMemberInput(finReqForm)"' in form
        assert '@click="finMemberPick(finReqForm, m)"' in form and "finMemberName(m)" in form
        assert 'x-show="!finReqForm.member.selected"' in form                      # a typed payer name only for a non-member
        assert 'x-model="finReqForm.sangha_sevi_id"' not in form                   # the id is never typed by hand any more
        pick = _between(SETUP_JS, "finMemberPick(form, x) {", "finMemberClear(form)")
        assert "form.sangha_sevi_id = x.sangha_sevi_id" in pick and 'form.payer_name = ""' in pick

    def test_the_search_waits_for_two_characters_debounces_and_uses_the_member_directory(self):
        inp = _between(SETUP_JS, "finMemberInput(form) {", "async finMemberSearch(form)")
        assert "q.length < 2" in inp and "setTimeout" in inp and "300" in inp
        search = _between(SETUP_JS, "async finMemberSearch(form) {", "finMemberName(x)")
        assert "/api/v1/membership/directory" in search and "m.query.trim() === q" in search     # a late reply never overwrites newer typing

    def test_the_request_still_posts_the_member_id_and_payer_name_only(self):
        body = _between(SETUP_JS, "async finReqSubmit()", "async finReqOpen(pk)")
        assert "sangha_sevi_id: blank(f.sangha_sevi_id)" in body and "payer_name: blank(f.payer_name)" in body and "member" not in body.split("_finSend")[1].split("});")[0]


class TestARequestMadeForAMemberShowsInTheirPranamiTab:
    """Owner 2026-11-18: a payment request typed against a member's name appears in that member's Pranami tab by itself."""

    def test_the_tab_lists_requests_asked_of_the_member_with_pay_and_decline(self):
        block = _between(DASH_HTML, "<!-- Payment requests a treasurer / admin made for this member", "<!-- Your contributions")
        assert 'x-for="rq in pranamiPay.requests"' in block and "rq.asked_by_name" in block
        assert "pranamiPayRequested(rq)" in block and "pranamiCancelRequest(rq.upi_payment_request_pk)" in block
        body = _between(DASH_JS, "async _loadPranamiRequests() {", "pranamiPayRequested(r) {")
        assert "/api/v1/finance/my-pranami/requests" in body and "asked_by_name" in body      # only the ones somebody ASKED (own ones live on the cards)

    def test_it_opens_the_same_checkout_and_refreshes_by_itself(self):
        pay = _between(DASH_JS, "pranamiPayRequested(r) {", "async _loadPranami(opts")
        assert "_pranamiStartClock()" in pay and "_pranamiPayPoll(" in pay
        block = DASH_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        assert 'upi_payment_request: ["pranami"]' in block
        assert "this._loadPranamiRequests();" in _between(DASH_JS, "async _loadPranamiPayHeads() {", "async _loadPranamiRequests()")

    def test_the_server_lists_only_the_callers_own_open_requests(self):
        import inspect
        from api.routers import finance_upi
        from api.schemas.finance import MyPaymentRequest

        src = inspect.getsource(finance_upi.my_open_requests)
        assert "r.payer_person_pk = %s" in src and "'CREATED', 'PENDING'" in src
        assert list(inspect.signature(finance_upi.my_open_requests).parameters) == ["user", "conn"]      # no id parameter: only ever the caller's own
        assert {"asked_by_name", "note", "upi_payment_request_pk", "demo_payable"} <= set(MyPaymentRequest.model_fields)


class TestTheAskForAPaymentPage:
    """Owner 2026-11-18: the "Ask for a UPI payment" page - form on the left, a live summary on the right, a tidy request list."""

    def _page(self):
        return _between(ADMIN_HTML, "<!-- Create form: who is paying", "<!-- Detail: one request")

    def test_the_form_is_split_into_who_and_what_with_a_live_summary(self):
        page = self._page()
        for needle in ("Who is paying?", "What is it for?", "Request summary", "ask-summary", "finReqHeadSel()", "Create payment request", "← Back to list"):
            assert needle in page, needle
        for model in ("finReqForm.member.query", "finReqForm.payer_name", "finReqForm.finance_head_pk", "finReqForm.amount", "finReqForm.note"):
            assert f'x-model="{model}"' in page, model

    def test_a_fixed_amount_prefills_the_amount_once(self):
        body = _between(SETUP_JS, "finReqHeadChanged() {", "finReqOpenForm() {")
        assert "fixed_amount" in body and 'String(this.finReqForm.amount || "").trim()' in body

    def test_the_list_shows_payer_name_first_and_filters_as_you_type(self):
        page = self._page()
        for header in ("Payer", "For", "Asked on", "Status"):
            assert f"<th>{header}</th>" in page, header
        assert 'x-model="finReqQ" @input.debounce.300ms="finReqApply()"' in page
        assert "r.payer_name || r.payer_sangha_sevi_id" in page


class TestTheRequestDetailPage:
    """Owner 2026-11-18: one payment request - amount and status on top, the steps, details, sharing, the demo gateway."""

    def _detail(self):
        return _between(ADMIN_HTML, "<!-- Detail: one request", "</div><!-- /Finance -->")

    def test_it_leads_with_the_amount_the_status_and_the_progress_steps(self):
        d = self._detail()
        for needle in ("← Back to requests", "Payment request", "pay-amount", "finBadge(finReq.status)", "Asked", "Paid", "Booked and receipted"):
            assert needle in d, needle

    def test_the_actions_keep_their_gates(self):
        d = self._detail()
        assert "canManageFinance && ['CREATED','PENDING'].includes(finReq.status)" in d and "finReqRefresh()" in d
        assert 'x-show="finReqNeedsBooking && canApproveFinance"' in d and "finReqBook()" in d
        assert "finActions('payment_request', finReq.status)" in d

    def test_sharing_and_the_demo_gateway_are_separate_blocks(self):
        d = self._detail()
        assert "Share with the payer" in d and "finReqSafeUrl(finReq.pay_url)" in d and "finReqSafeUpi(finReq.upi_uri)" in d
        assert 'class="pay-test" x-show="finReqCanSimulate"' in d and "TEST MODE" in d
        for outcome in ("paid", "failed", "expired"):
            assert f"finReqSimulate('{outcome}')" in d, outcome
        assert "Gateway details" in d                     # the order / payment ids are tucked away, not the first thing seen


class TestTheGoLiveChecklist:
    """Owner 2026-11-18: before registering with Razorpay, the app shows what to register and what is still missing."""

    def test_the_card_lists_the_four_things_and_never_a_secret(self):
        card = _between(ADMIN_HTML, "<!-- Go-live checklist for a real gateway", '<!-- Accounts list (under "More"')
        for needle in ("Razorpay is switched on for this server", "Register this webhook address in the Razorpay dashboard", "API keys are on the server",
                       "Payment window is long enough", "finCopyWebhook(", "webhook_events", "scripts/fake_razorpay.py"):
            assert needle in card, needle
        assert "x-model" not in card and "type=\"password\"" not in card

    def test_it_loads_when_more_is_opened_from_the_readiness_route(self):
        assert '@click="finToggleMore()"' in ADMIN_HTML
        body = _between(SETUP_JS, "finToggleMore() {", "finGatewayProvider(name)")
        assert 'this._finGet("/gateway/readiness")' in body

    def test_the_server_returns_names_and_urls_only(self):
        from api.schemas.finance import GatewayProviderReadiness, GatewayReadiness

        fields = set(GatewayReadiness.model_fields) | set(GatewayProviderReadiness.model_fields)
        assert not {f for f in fields if any(w in f for w in ("secret", "key_id", "password", "token"))}


class TestTheChecklistFollowsTheAccounts:
    def test_it_is_refreshed_when_an_account_is_saved_and_on_every_reload(self):
        assert "this.finGatewayRefresh()" in _between(SETUP_JS, "async finSetupReload() {", "finSetupBusy()")
        assert "this.finGatewayRefresh()" in _between(SETUP_JS, 'this._finNote(edit ? "Receiving account updated."', "} catch")
        assert "finGatewayRefresh() { return this.finSetupMore ? this.finGatewayLoad() : Promise.resolve(); }" in SETUP_JS


class TestTheOpenPortalFormAsksForADueDate:
    """Owner 2026-11-19: a due date for every Pranami when opening the portal, with a preview of the member's card."""

    def _form(self):
        return _between(ADMIN_HTML, "<!-- Open payment portal: what members are asked to pay", "<!-- Heads list -->")

    def test_the_form_has_amount_frequency_due_date_and_a_preview(self):
        form = self._form()
        for needle in ("How much?", "When?", "Due by", "every Pranami has a due date", "What members will see", "finPortalPreview()", "← Back to heads"):
            assert needle in form, needle
        for model in ("finPortalForm.fixed_amount", "finPortalForm.due_date", "finPortalForm.allow_part_payment"):
            assert f'x-model="{model}"' in form, model
        for period in ("YEARLY", "MONTHLY", "ONE_TIME"):
            assert f"finPortalForm.due_period = '{period}'" in form, period

    def test_a_default_date_is_offered_and_the_date_is_required_with_an_amount_and_sent(self):
        assert "_finDefaultDueDate(period) {" in SETUP_JS and "-03-31" in SETUP_JS
        body = _between(SETUP_JS, "async finPortalSubmit() {", "// List helpers of the simple Heads page")
        assert "Choose the date this Pranami is due by." in body and "due_date: f.due_date" in body
        assert "!f.follows_kendra && !f.due_date" in body, "the date is required for a free-amount Pranami too"

    def test_the_when_section_is_shown_for_a_free_amount_but_the_frequency_is_not(self):
        form = self._form()
        when = _between(form, "<h3 class=\"ask-section__title\">When?</h3>", "</section>")
        assert 'x-show="finPortalForm.fixed_amount.trim() !== \'\'"' in when.split("Due by")[0]       # only the frequency waits for an amount
        assert 'x-model="finPortalForm.due_date"' in when and "fixed_amount.trim()" not in when.split("Due by")[1]

    def test_members_see_the_date_and_an_overdue_mark_and_admins_see_it_in_the_list(self):
        assert "(h.overdue ? 'Overdue — was due by ' : 'Due by ') + formatDate(h.due_date)" in DASH_HTML
        assert "'Due by ' + NSS.formatDate(h.due_date)" in ADMIN_HTML


class TestAnUnfinishedPaymentHasClearButtons:
    """Owner 2026-11-20: Resume payment and Cancel payment are real buttons in a visible panel, not small text links."""

    def test_the_pending_panel_has_primary_resume_and_danger_cancel_buttons(self):
        html = (FE / "dashboard.html").read_text(encoding="utf-8")
        box = html[html.index('class="pend-box"'):]
        box = box[:box.index("Pay together with others")]
        assert 'class="btn-action primary" @click="pranamiResume(h)">Resume payment</button>' in box
        assert 'class="btn-action danger"' in box and ">Cancel payment</button>" in box and "pranamiCancelRequest(h.pending_request_pk)" in box
        assert 'class="link-action" @click="pranamiResume(h)"' not in html
        # the waiting screen's Cancel is a danger button too
        assert 'class="btn-action danger pay-btn" :disabled="pranamiPay.saving" @click="pranamiCancelRequest(pranamiPay.result.upi_payment_request_pk)"' in html
