"""
Finance UI (Tier 12) — source-parsing guards for frontend/assets/js/finance.js,
the Finance panels in frontend/admin.html and their wiring in admin.js /
nss-config.js / badges.css.

DB-free and browser-free (run with --noconftest): nothing here opens a page.
NEVER OPENED IN A BROWSER when this file was written — these tests only prove
that the markup, the mixin, the API routes and the shared maps agree with each
other, not that the screens render or behave.
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
ALL_JS = FIN_JS + "\n" + SETUP_JS
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
CONFIG_JS = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
BADGES = (FE / "assets/css/badges.css").read_text(encoding="utf-8")

TABS = ["finOverview", "finStructure", "finTransactions", "finTransfers", "finSetup", "finCollections"]


def _panel() -> str:
    start = ADMIN_HTML.index("VIEW: Finance (Tier 12)")
    return ADMIN_HTML[start:ADMIN_HTML.index("</div><!-- /Finance -->", start)]


def _sidebar() -> str:
    start = ADMIN_HTML.index("<!-- ── Finance group (collapsible, Tier 12)")
    return ADMIN_HTML[start:ADMIN_HTML.index("<!-- ── Audit & Diagnostics group", start)]


def _mixin_members() -> set[str]:
    """Methods / getters (one per line) and state keys (several may share a line) of the mixin object."""
    methods = re.findall(r"^ {12}(?:async\s+|get\s+)?(_?fin[A-Za-z]*)\s*\(", ALL_JS, re.M)
    state = re.findall(r"^ {12}(?:[A-Za-z_]+: .*?, )*?(_?fin[A-Za-z]*): ", ALL_JS, re.M)
    keys = re.findall(r"(?:^ {12}|, )(_?fin[A-Za-z]*): ", ALL_JS, re.M)
    getters = re.findall(r"^ {12}get\s+(_?fin[A-Za-z]*)\(", ALL_JS, re.M)
    return set(methods) | set(state) | set(keys) | set(getters)


class TestWiring:
    def test_script_is_loaded_before_admin_js_runs(self):
        assert '<script src="/assets/js/finance.js"></script>' in ADMIN_HTML

    def test_mixin_is_installed_into_the_admin_component(self):
        assert "NSSFinance.install(" in ADMIN_JS
        assert "window.NSSFinance" in FIN_JS
        assert "getOwnPropertyDescriptors" in FIN_JS             # not spread: getters stay live

    def test_install_never_overwrites_a_host_member(self):
        assert FIN_JS.count("hasOwnProperty.call(target, key)") == 1 and SETUP_JS.count("hasOwnProperty.call(target, key)") == 1
        assert "window.NSSFinanceSetup" in SETUP_JS and "getOwnPropertyDescriptors" in SETUP_JS
        assert "NSSFinanceSetup.install(" in ADMIN_JS and '<script src="/assets/js/finance-setup.js"></script>' in ADMIN_HTML

    def test_the_two_finance_mixins_define_disjoint_members(self):
        def names(src):
            return set(re.findall(r"^ {12}(?:async\s+|get\s+)?(_?fin[A-Za-z]*)\s*[(:]", src, re.M))
        assert not names(FIN_JS) & names(SETUP_JS), names(FIN_JS) & names(SETUP_JS)

    def test_no_member_collides_with_another_mixin_or_the_host(self):
        others = "".join((FE / "assets/js" / f).read_text(encoding="utf-8") for f in (
            "attendance-register.js", "audit-diagnostics.js", "live-refresh.js", "nss-layout.js", "assets-property.js"))
        # admin.js legitimately MENTIONS finEnterTab / finLive* / the tab names; it must not DEFINE a fin member.
        for name in _mixin_members() - set(TABS):
            assert not re.search(rf"^\s+{re.escape(name)}\s*\(", others, re.M), name
        # (the tab names are also object KEYS in admin.js' live-refresh config: values, not host members)
        defined_in_admin = set(re.findall(r"^ {8}(?:async\s+|get\s+)?(fin[A-Z][A-Za-z]*)\s*[(:]", ADMIN_JS, re.M)) - set(TABS)
        assert not defined_in_admin & _mixin_members(), defined_in_admin & _mixin_members()

    def test_no_inline_event_handlers_or_eval(self):
        assert not re.search(r"\son[a-z]+\s*=", _panel()), "CSP forbids inline handlers"
        for src in (FIN_JS, SETUP_JS):
            assert "eval(" not in src and "new Function" not in src and "innerHTML" not in src
        assert 'x-init="init()"' not in _panel()                  # Alpine 3 auto-runs init(); doubling it exhausts the pool

class TestMarkupAgreesWithMixin:
    def test_every_fin_identifier_used_in_the_panels_is_defined(self):
        used = set(re.findall(r"\b(fin[A-Z][A-Za-z]*)\b", _panel() + _sidebar()))
        # the four tab names are values (activeTab), not members
        missing = sorted(u for u in used if u not in _mixin_members() and u not in TABS)
        assert not missing, f"used in admin.html but not defined in finance.js: {missing}"

    def test_every_method_the_admin_js_calls_exists(self):
        for call in re.findall(r"\bthis\.(fin[A-Z][A-Za-z]*)\(", ADMIN_JS) + re.findall(r"\bh\.(fin[A-Z][A-Za-z]*)\(", ADMIN_JS):
            assert call in _mixin_members(), call
        # finance.js hands the two new tabs to the setup mixin
        for call in re.findall(r"\bthis\.(fin(?:Setup|Req)[A-Za-z]*)\(", FIN_JS):
            assert call in _mixin_members(), call

    def test_permission_getters(self):
        for flag, perms in (("canViewFinance", ("FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_APPROVE")),
                            ("canManageFinance", ("FINANCE_MANAGE", "FINANCE_APPROVE")),
                            ("canApproveFinance", ("FINANCE_APPROVE",))):
            body = re.search(rf"get {flag}\(\) \{{(.*?)\n            \}},", FIN_JS, re.S).group(1)
            for p in perms:
                assert f'"{p}"' in body, (flag, p)

    def test_sidebar_group_is_gated_and_has_four_entries(self):
        side = _sidebar()
        assert '<template x-if="canViewFinance">' in side
        for tab in TABS:
            assert f"finEnterTab('{tab}')" in side and f"activeTab === '{tab}'" in side
        assert "toggleNavGroup('finance')" in side

    def test_panels_exist_for_all_four_tabs(self):
        p = _panel()
        for tab in TABS:
            assert f"activeTab === '{tab}'" in p
        assert "canViewFinance" in p

    def test_write_controls_are_permission_gated(self):
        p = _panel()
        for needle in ("canManageFinance", "canApproveFinance"):
            assert needle in p
        # every "+ New" button sits behind a permission check
        for label in ("+ New year", "+ New scope", "+ New fund", "+ New transaction", "+ New transfer"):
            line = next(l for l in p.splitlines() if label in l)
            assert "x-show" in line and ("canManageFinance" in line or "canApproveFinance" in line), label

    def test_lifecycle_buttons_come_from_the_servers_table(self):
        p = _panel()
        for entity in ("year", "scope", "fund", "transaction", "receipt", "payment", "transfer"):
            assert f"finActions('{entity}'" in p, entity
        assert "/reference" in FIN_JS and "this.finRef.transitions" in FIN_JS


class TestApiUsage:
    def test_every_path_the_mixin_calls_is_a_real_route(self):
        from api.main import app

        routes = {re.sub(r"\{[^}]+\}", "{}", r.path.replace("/api/v1/finance", ""))
                  for r in app.routes if getattr(r, "path", "").startswith("/api/v1/finance")}
        called = set()
        for m in re.finditer(r"""(?:_finGet|_finSend)\(\s*(?:"[A-Z]+",\s*|method,\s*)?(["`])(/[^"`?]*)\1""", ALL_JS):
            path = re.sub(r"\$\{[^}]+\}", "{}", m.group(2))
            if path.endswith("{}{}"):          # _finReqAct(label, path): the action suffixes are checked below
                continue
            called.add(path)
        assert called, "no API calls found?"
        for path in called:
            assert path in routes, f"the Finance mixins call {path}, which the router does not serve"
        # the request actions share one helper, each with a literal suffix
        for suffix in ("/refresh", "/post", "/mock-pay"):
            assert f'"{suffix}"' in SETUP_JS or f"`{suffix}" in SETUP_JS or f'"{suffix}?' in SETUP_JS or suffix + "?outcome" in SETUP_JS, suffix
            assert f"/payment-requests/{{}}{suffix}" in routes, suffix

    def test_transition_path_is_built_from_the_entity_name(self):
        assert '`/${PLURAL[t.entity] || t.entity + "s"}/${t.pk}/transition`' in FIN_JS
        assert 'const PLURAL = { year: "years", payment_request: "payment-requests" };' in FIN_JS
        from api.main import app

        paths = {r.path for r in app.routes}
        param = {"years": "year_pk", "scopes": "scope_pk", "funds": "fund_pk", "transactions": "txn_pk", "receipts": "receipt_pk",
                 "payments": "payment_pk", "transfers": "transfer_pk", "accounts": "account_pk", "heads": "head_pk",
                 "payment-requests": "request_pk"}
        for entity in ("year", "scope", "fund", "transaction", "receipt", "payment", "transfer", "account", "head", "payment_request"):
            plural = {"year": "years", "payment_request": "payment-requests"}.get(entity, entity + "s")
            assert f"/api/v1/finance/{plural}/{{{param[plural]}}}/transition" in paths, entity

    def test_request_fields_match_the_schemas(self):
        from api.schemas import finance as S

        sent = {   # model -> fields the UI sends
            "TransactionCreate": ["financial_year_pk", "financial_scope_pk", "fund_master_pk", "transaction_type", "finance_head_pk",
                                  "amount", "transaction_date", "description", "sangha_sevi_id"],
            "ReceiptCreate": ["receipt_date", "amount", "received_from", "payment_method_code", "instrument_reference"],
            "PaymentCreate": ["payment_date", "amount", "paid_to", "payment_method_code", "instrument_reference"],
            "TransferCreate": ["financial_year_pk", "source_scope_pk", "destination_scope_pk", "source_fund_pk",
                               "destination_fund_pk", "amount", "transfer_date", "purpose"],
            "ScopeCreate": ["scope_code", "scope_name", "scope_type", "organization_pk", "financial_year_pk", "parent_scope_pk"],
            "FundCreate": ["fund_code", "fund_name", "fund_type", "financial_scope_pk", "is_restricted", "restriction_purpose", "organization_pk"],
            "YearCreate": ["start_year"],
            "HeadCreate": ["organization_pk", "head_code", "head_name", "description", "direction", "is_restricted", "restriction_purpose",
                           "required_fund_type", "is_pranami", "allow_upi", "collection_scope_pk", "collection_fund_pk", "collection_account_pk",
                           "display_order"],
            "HeadUpdate": ["head_name", "description", "restriction_purpose", "is_pranami", "allow_upi", "collection_scope_pk",
                           "collection_fund_pk", "collection_account_pk", "display_order"],
            "AccountCreate": ["organization_pk", "account_label", "account_type", "bank_name", "branch_name", "account_holder_name",
                              "account_number_last4", "ifsc_code", "upi_vpa", "gateway_provider", "gateway_credential_ref",
                              "gateway_merchant_ref", "is_default"],
            "PaymentRequestCreate": ["finance_head_pk", "amount", "sangha_sevi_id", "payer_name", "note"],
            "AdoptTemplates": ["organization_pk"],
        }
        for model, fields in sent.items():
            schema = getattr(S, model).model_fields
            for f in fields:
                assert f in schema, f"{model} has no field {f}"
                assert re.search(rf"\b{f}\b", ALL_JS), f"the Finance mixins never send {f}"
        # the member's own payment is sent from dashboard.js and carries exactly the head and the amount - no payer
        assert set(S.MyPayRequest.model_fields) == {"finance_head_pk", "amount"}
        assert "finance_head_pk: p.head, amount: String(p.amount).trim()" in DASH_JS

    def test_the_old_category_field_is_gone_from_the_ui(self):
        assert "transaction_category" not in re.sub(r"finHeadLabel\(row\)[^\n]*\n", "", ALL_JS).replace("row.transaction_category", "")
        assert "income_categories" not in ALL_JS and "finCategoryChoices" not in ADMIN_HTML

class TestSharedMaps:
    def test_every_status_has_a_label_and_a_badge(self):
        from api.schemas import finance as S

        label_block = re.search(r"FINANCE_STATUS_LABELS: \{(.*?)\n    \},", CONFIG_JS, re.S).group(1)
        badge_block = re.search(r"FINANCE_STATUS_BADGE_MAP: \{(.*?)\n    \},", CONFIG_JS, re.S).group(1)
        every = set(S.YEAR_STATUSES + S.SCOPE_STATUSES + S.FUND_STATUSES + S.TRANSACTION_STATUSES
                    + S.RECEIPT_STATUSES + S.PAYMENT_STATUSES + S.TRANSFER_STATUSES)
        for status in every:
            assert re.search(rf"\b{status}:", label_block), f"no label for {status}"
            assert re.search(rf"\b{status}:", badge_block), f"no badge for {status}"

    def test_every_badge_class_is_defined_in_badges_css(self):
        classes = set(re.findall(r"badge-fin-[a-z]+", re.search(r"FINANCE_STATUS_BADGE_MAP: \{(.*?)\n    \},", CONFIG_JS, re.S).group(1)))
        assert classes
        for c in classes:
            assert re.search(rf"^\.{c}\s*\{{", BADGES, re.M), c

    def test_step_verbs_cover_every_target_status(self):
        from api.routers.finance import _STEPS

        verbs = re.search(r"const STEP_VERBS = \{(.*?)\n    \};", FIN_JS, re.S).group(1)
        targets = {to for steps in _STEPS.values() for (_, to) in steps}
        for t in targets:
            assert re.search(rf"\b{t}:", verbs), f"no button caption for {t}"

    def test_live_map_and_hooks(self):
        from api.routers.live import LIVE_FEED_TABLES

        block = ADMIN_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        for table in ("financial_year", "financial_scope", "fund_master", "financial_transaction",
                      "financial_receipt", "financial_payment", "financial_transfer"):
            assert re.search(rf"^\s+{table}: \[", block, re.M), table
            assert table in LIVE_FEED_TABLES
        for tab in TABS:
            assert re.search(rf"{tab}: \{{ reload: \(h\) => h\.finLiveReload\(\), busy: \(h\) => h\.finLiveBusy\(\) \}}", ADMIN_JS), tab

    def test_entry_guard_and_hash_routes(self):
        assert "!this.canViewFinance && !this.hasGeneralAdminAccess" in ADMIN_JS
        assert ('const FINANCE_TABS = ["finOverview", "finStructure", "finTransactions", "finTransfers", "finSetup", "finCollections"];'
                in ADMIN_JS)
        for tab in TABS:
            assert f'{tab}: () => {{ if (this.canViewFinance) this.finEnterTab("{tab}"); }}' in ADMIN_JS

DASH_HTML = (FE / "dashboard.html").read_text(encoding="utf-8")
DASH_JS = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")


def _pranami_panel() -> str:
    start = DASH_HTML.index("<!-- ── Pranami (Finance, Tier 12) ──")
    return DASH_HTML[start:DASH_HTML.index("<div x-show=\"tab === 'documents'\">", start)]


class TestMemberPranamiTab:
    """The member dashboard's own "Pranami" tab (GET /finance/my-pranami)."""

    def test_sidebar_item_and_panel_exist(self):
        assert "@click=\"switchTab('pranami')\"" in DASH_HTML and "tab === 'pranami'" in DASH_HTML
        assert re.search(r">\s*Pranami\s*</a>", DASH_HTML)

    def test_loader_is_wired_into_every_entry_path(self):
        assert '"/api/v1/finance/my-pranami"' in DASH_JS
        assert 'tab === "pranami"' in DASH_JS and DASH_JS.count("this._loadPranami()") >= 2   # tab switch + direct load
        assert "_pranamiSeq" in DASH_JS                                                       # stale-response guard

    def test_live_refresh_covers_the_tab(self):
        block = DASH_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        assert 'financial_transaction: ["pranami"]' in block and 'financial_receipt: ["pranami"]' in block
        assert re.search(r"pranami: \{ reload: \(h\) => h\._loadPranami\(\{ silent: true \}\)", DASH_JS)

    def test_endpoint_is_login_only_and_has_no_id_parameter(self):
        from api.routers.finance import router

        route = next(r for r in router.routes if r.path == "/api/v1/finance/my-pranami")
        assert route.methods == {"GET"}
        assert not route.dependant.query_params and not route.dependant.path_params      # nothing to tamper with
        assert "get_current_user" in {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}

    def test_every_field_the_panel_reads_exists_in_the_schema(self):
        from api.schemas.finance import MyPranamiItem, MyPranamiReceipt

        panel = _pranami_panel()
        for field in re.findall(r"\bp\.([a-z_]+)", panel):
            assert field in MyPranamiItem.model_fields, field
        for field in re.findall(r"\br\.([a-z_]+)", panel):
            assert field in MyPranamiReceipt.model_fields, field

    def test_panel_is_csp_safe_and_only_the_pay_card_takes_input(self):
        panel = _pranami_panel()
        assert not re.search(r"\son[a-z]+\s*=", panel) and "<form" not in panel
        assert 'x-init="init()"' not in panel
        # the only inputs are the year filter and the pay card's head + amount
        assert set(re.findall(r'x-model="([^"]+)"', panel)) == {"pranami.year", "pranamiPay.head", "pranamiPay.amount"}
        # a link coming from the server is only ever rendered through the scheme-checking helpers
        for href in re.findall(r':href="([^"]+)"', panel):
            assert href.startswith(("pranamiSafeUrl(", "pranamiSafeUpi(")), href
        assert not re.search(r'[^:]href="(?!#)', panel), "no static href may point anywhere from the member panel"

    def test_admin_form_can_link_a_member(self):
        assert "sangha_sevi_id: blank(f.sangha_sevi_id)" in FIN_JS
        assert 'x-model="finTxnForm.sangha_sevi_id"' in ADMIN_HTML
        from api.schemas.finance import TransactionCreate, TransactionUpdate

        assert "sangha_sevi_id" in TransactionCreate.model_fields and "sangha_sevi_id" in TransactionUpdate.model_fields


def _screen(tab: str) -> str:
    """The markup of one tab's block inside the Finance panel."""
    start = _panel().index(f"x-show=\"activeTab === '{tab}'\"")
    nxt = [m.start() for m in re.finditer(r"<!-- ═════════", _panel()[start:])]
    return _panel()[start:start + nxt[0]] if nxt else _panel()[start:]


class TestCustomizationAndCollectionScreens:
    def test_two_more_sidebar_entries_and_panels(self):
        side = _sidebar()
        for tab, label in (("finSetup", "Heads &amp; Accounts"), ("finCollections", "UPI Collections")):
            assert f"finEnterTab('{tab}')" in side and f"activeTab === '{tab}'" in side and label in side
            assert f"activeTab === '{tab}'" in _panel()
        assert "'finSetup','finCollections'" in ADMIN_HTML

    def test_configuration_controls_are_hidden_without_the_approve_permission(self):
        setup = _screen("finSetup")
        for needle in ("+ New account", "Add Kendra templates", "finHeadOpenEdit(h)", "finAcctOpenEdit(a)"):
            line = next(l for l in setup.splitlines() if needle in l)
            assert "canApproveFinance" in line, f"{needle} must be gated on canApproveFinance"
        assert 'x-show="canApproveFinance" @click="finHeadOpenCreate()"' in setup

    def test_the_account_form_can_never_take_a_secret_or_a_full_account_number(self):
        form = _screen("finSetup")
        assert not re.search(r'type="password"', form)
        models = set(re.findall(r'x-model="(finAcctForm\.[a-z_0-9.]+)"', form))
        assert models == {"finAcctForm.organization.query", "finAcctForm.account_label", "finAcctForm.account_type",
                          "finAcctForm.account_holder_name", "finAcctForm.bank_name", "finAcctForm.branch_name",
                          "finAcctForm.account_number_last4", "finAcctForm.ifsc_code", "finAcctForm.upi_vpa",
                          "finAcctForm.gateway_provider", "finAcctForm.gateway_credential_ref", "finAcctForm.gateway_merchant_ref",
                          "finAcctForm.is_default"}
        assert 'maxlength="4"' in form and "LAST FOUR" in SETUP_JS and "never stored" in SETUP_JS
        assert "Never paste a key here" in form
        assert not re.search(r"key_secret|webhook_secret|api_key", SETUP_JS + form, re.I)

    def test_the_head_form_only_binds_server_known_fields(self):
        from api.schemas.finance import HeadCreate

        form = _screen("finSetup")
        bound = {m.split(".")[1] for m in re.findall(r'x-model="(finHeadForm\.[a-z_0-9.]+)"', form)} - {"organization", "lockedShape"}
        assert bound <= set(HeadCreate.model_fields), bound - set(HeadCreate.model_fields)

    def test_links_from_the_server_are_only_rendered_through_scheme_checks(self):
        collections = _screen("finCollections")
        for href in re.findall(r':href="([^"]+)"', collections):
            assert href.startswith(("finReqSafeUrl(", "finReqSafeUpi(")), href
        for target in re.findall(r'target="_blank"[^>]*', collections):
            assert 'rel="noopener noreferrer"' in target
        assert not re.search(r'[^:]href="(?!#)', collections)

    def test_the_simulator_is_only_offered_for_a_mock_request_on_a_server_that_enables_mock(self):
        getter = re.search(r"get finReqCanSimulate\(\) \{(.*?)\n            \},", SETUP_JS, re.S).group(1)
        assert 'provider === "MOCK"' in getter and 'finAcctProviders.includes("MOCK")' in getter and "canManageFinance" in getter
        assert 'x-show="finReqCanSimulate"' in _screen("finCollections")

    def test_booking_a_held_payment_is_an_approve_action(self):
        assert re.search(r'x-show="finReqNeedsBooking && canApproveFinance"', _screen("finCollections"))
        assert "finReqBook()" in _screen("finCollections")

    def test_lifecycle_buttons_for_the_new_entities_come_from_the_server_table(self):
        for entity in ("head", "account", "payment_request"):
            assert f"finActions('{entity}'" in _panel(), entity

    def test_the_new_live_tables_are_mapped_to_screens_that_exist(self):
        block = ADMIN_JS.split("// LIVE_TABLE_TABS:begin")[1].split("// LIVE_TABLE_TABS:end")[0]
        for table in ("finance_head", "financial_account", "upi_payment_request"):
            tabs = re.search(rf"^\s+{table}: \[(.*?)\]", block, re.M).group(1)
            for tab in re.findall(r'"([A-Za-z]+)"', tabs):
                assert tab in TABS, (table, tab)
        assert "finance_gateway_event" not in block, "the gateway log carries payer details and is not on the live feed"
        for tab in ("finSetup", "finCollections"):
            assert re.search(rf"{tab}: \{{ reload: \(h\) => h\.finLiveReload\(\), busy: \(h\) => h\.finLiveBusy\(\) \}}", ADMIN_JS), tab

    def test_polling_never_decides_a_payment_and_stops(self):
        for src, name in ((DASH_JS, "_pranamiPayPoll"),):
            body = src.split(f"{name}(pk, tries) {{")[1].split("pranamiPayClose()")[0]
            assert "tries > 400" in body and "document.hidden" in body and 'this.tab !== "pranami"' in body
            assert '"PAID"' in body and "status =" not in body.replace("p.result.status ===", ""), "the page may only REPORT the status it was given"

    def test_the_member_pay_card_posts_only_the_head_and_amount(self):
        pay = DASH_JS.split("async pranamiPayStart()")[1].split("_pranamiPayPoll(pk, tries) {")[0]
        assert "/api/v1/finance/my-pranami/pay" in pay and "sangha_sevi" not in pay and "person" not in pay
        card = _pranami_panel()
        assert "Pay Pranami by UPI" in card and 'x-show="pranamiPay.heads.length > 0"' in card


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestLinkHelpersAgainstHostileInput:
    """Run the real finance-setup.js helpers under node: a hostile server response must never become a clickable javascript: URL."""

    def _run(self, expr: str):
        script = f"""
        const window = {{}}; const document = {{}}; const NSS = {{ codeLabel: (c) => c }};
        {SETUP_JS}
        const t = {{}}; window.NSSFinanceSetup.install(t);
        console.log(JSON.stringify({expr}));
        """
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_only_https_is_a_payment_page(self):
        urls = ["https://rzp.io/i/abc", "HTTPS://x.example/pay", "http://plain.example", "javascript:alert(1)", " https://leading-space.example",
                "data:text/html,<script>1</script>", "//protocol-relative.example", "https:/no-slashes", None, 5, {}, ""]
        got = self._run("[" + ",".join(json.dumps(u) if u is not None else "null" for u in urls) + "].map((u) => t.finReqSafeUrl(u))")
        assert got == ["https://rzp.io/i/abc", "HTTPS://x.example/pay", "", "", "", "", "", "", "", "", "", ""]

    def test_only_a_upi_pay_deep_link_is_a_upi_link(self):
        uris = ["upi://pay?pa=a@b&am=1.00", "UPI://PAY?pa=x", "upi://mandate?x=1", "upi://", "javascript:upi://pay?x", "intent://pay", " upi://pay?x", "", None]
        got = self._run("[" + ",".join(json.dumps(u) if u is not None else "null" for u in uris) + "].map((u) => t.finReqSafeUpi(u))")
        assert got == ["upi://pay?pa=a@b&am=1.00", "UPI://PAY?pa=x", "", "", "", "", "", "", ""]

    def test_head_rules_summary(self):
        got = self._run('t.finHeadRules({ is_restricted: true, required_fund_type: "SINKING_FUND", is_pranami: true, allow_upi: true })')
        assert got == ["Restricted", "SINKING_FUND fund", "Pranami", "UPI"]
        assert self._run("t.finHeadRules({})") == []

@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestPureLogicInNode:
    """Run the pure helpers under node: formatMoney and the status maps from nss-config.js."""

    def _run(self, script: str):
        src = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
        wrapper = f"const window = {{}}; const document = {{}}; {src}\n{script}"
        out = subprocess.run([NODE, "-e", wrapper], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_format_money(self):
        data = self._run("""console.log(JSON.stringify([
            NSS.formatMoney("1234567.5"), NSS.formatMoney(0), NSS.formatMoney(null), NSS.formatMoney("abc"), NSS.formatMoney("100")]));""")
        assert data[0].replace(" ", "") == "₹12,34,567.50"       # Indian digit grouping
        assert data[1].replace(" ", "") == "₹0.00"
        assert data[2] == "—" and data[3] == "—"
        assert data[4].replace(" ", "") == "₹100.00"

    def test_status_label_and_badge_fallbacks(self):
        data = self._run("""console.log(JSON.stringify([
            NSS.financeStatusLabel("PENDING_APPROVAL"), NSS.financeStatusLabel("SOMETHING_NEW"),
            NSS.financeStatusBadgeClass("POSTED"), NSS.financeStatusBadgeClass("SOMETHING_NEW")]));""")
        assert data == ["Pending approval", "Something New", "badge-fin-done", "badge-muted"]
