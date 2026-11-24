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
FUNDS_JS = (FE / "assets/js/finance-funds.js").read_text(encoding="utf-8")
BUDGET_JS = (FE / "assets/js/finance-budget.js").read_text(encoding="utf-8")
SINKING_JS = (FE / "assets/js/finance-sinking.js").read_text(encoding="utf-8")
ALL_JS = FIN_JS + "\n" + SETUP_JS + "\n" + FUNDS_JS + "\n" + BUDGET_JS + "\n" + SINKING_JS
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
CONFIG_JS = (FE / "assets/js/nss-config.js").read_text(encoding="utf-8")
BADGES = (FE / "assets/css/badges.css").read_text(encoding="utf-8")

TABS = ["finOverview", "finStructure", "finFunds", "finBudget", "finSinking", "finTransactions", "finTransfers", "finSetup", "finCollections"]


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
        assert not names(FUNDS_JS) & (names(FIN_JS) | names(SETUP_JS)), names(FUNDS_JS) & (names(FIN_JS) | names(SETUP_JS))

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
            assert "x-show" in line and ("canManageFinance" in line or "canApproveFinance" in line or "canAdministerFinance" in line), label   # scopes and funds: the stricter finance-administrator check

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
            if path.startswith("/{}s/{}/"):      # `/${kind}s/${id}/authority|countersign`: kind is payment or transfer
                called.update({f"/payments/{{}}/{path.rsplit('/', 1)[1]}", f"/transfers/{{}}/{path.rsplit('/', 1)[1]}"})
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
                           "required_fund_type", "is_pranami", "allow_upi", "collection_scope_pk", "collection_fund_pk", "collection_account_pk"],
            "HeadUpdate": ["head_name", "description", "restriction_purpose", "is_pranami", "allow_upi", "collection_scope_pk",
                           "collection_fund_pk", "collection_account_pk"],
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
        assert "finance_head_pk: p.head, amount }" in DASH_JS

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
        assert ('const FINANCE_TABS = ["finOverview", "finStructure", "finFunds", "finBudget", "finSinking", "finTransactions", "finTransfers", "finSetup", "finCollections"];'
                in ADMIN_JS)
        for tab in TABS:
            assert f'{tab}: () => this.canViewFinance && this.finEnterTab("{tab}")' in ADMIN_JS

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
        assert 'financial_transaction: ["pranami", "finApprovals"]' in block and 'financial_receipt: ["pranami"]' in block
        assert 'finance_approval_step: ["finApprovals"]' in block and 'finance_transaction_bill: ["finApprovals"]' in block
        assert re.search(r"finApprovals: \{ reload: \(h\) => h\._loadFinApprovals\(\{ silent: true \}\)", DASH_JS)
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
        # the only x-models are the history filters; each card's amount box reads :value / writes the amount map (no payer, no head field)
        assert set(re.findall(r'x-model="([^"]+)"', panel)) == {"pranami.year", "pranami.head", "pranami.org", "pranami.method", "pranami.from", "pranami.to"}
        assert "pranamiPay.amounts[h.finance_head_pk] = $event.target.value" in panel
        # a link coming from the server is only ever rendered through the scheme-checking helpers
        for href in re.findall(r':href="([^"]+)"', panel):
            assert href.startswith(("pranamiSafeUrl(", "pranamiSafeUpi(")), href
        assert not re.search(r'[^:]href="(?!#)', panel), "no static href may point anywhere from the member panel"

    def test_admin_form_can_link_a_member(self):
        assert "sangha_sevi_id: blank(f.sangha_sevi_id)" in FIN_JS
        assert 'x-model="finTxnForm.member.query"' in ADMIN_HTML                 # picked by name (owner 2026-11-20); the id the match sets is what is sent
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

    def test_configuration_controls_are_hidden_without_the_configure_permission(self):
        setup = _screen("finSetup")
        # Simple page (owner 2026-11-18): create a head, list heads, open / close a head's payment portal; accounts sit under "More".
        for needle in ("+ New account", "finAcctOpenEdit(a)", "+ Create head", "finHeadPortalOpenForm(h)", "finHeadPortal(h, false)", "finHeadOpenEdit(h)"):
            line = next(l for l in setup.splitlines() if needle in l)
            assert "canConfigureFinance" in line and "canApproveFinance" not in line, f"{needle} must be gated on canConfigureFinance"
        for gone in ("Add Kendra templates", "finHeadOpenCreate()", "finEventOpenCreate()", "finHeadSetView("):
            assert gone not in setup, f"{gone} is no longer offered on the page"
        assert "canApproveFinance" not in setup, "configuring is its own permission; approving is not needed to set a Sangha up"

    def test_the_account_form_can_never_take_a_secret_or_a_full_account_number(self):
        form = _screen("finSetup")
        # the read-only go-live checklist NAMES the environment variables to set on the server (it has no input at all); it is checked on its own
        checklist = form.split("<!-- Go-live checklist for a real gateway", 1)[1].split('<!-- Accounts list (under "More"', 1)[0]
        assert "<input" not in checklist and "<textarea" not in checklist and "x-model" not in checklist
        form = form.replace(checklist, "")
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
        from api.schemas.finance import HeadCreate, HeadUpdate

        form = _screen("finSetup")
        bound = {m.split(".")[1] for m in re.findall(r'x-model="(finHeadForm\.[a-z_0-9.]+)"', form)} - {"organization", "lockedShape"}
        known = set(HeadCreate.model_fields) | set(HeadUpdate.model_fields)       # the amount fields exist on the edit form only
        assert bound <= known, bound - known

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
        for entity in ("account", "payment_request"):             # a head's only actions are the portal buttons now
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
        pay = DASH_JS.split("async pranamiPayStart(h)")[1].split("_pranamiPayPoll(pk, tries) {")[0]
        assert "/api/v1/finance/my-pranami/pay" in pay and "sangha_sevi" not in pay and "person" not in pay
        card = _pranami_panel()
        assert "Pay online" in card and "x-show=\"pranami.view === 'pay' && pranamiPay.heads.length > 0 && !pranamiPay.result\"" in card


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

    def test_only_https_or_this_computer_is_a_payment_page(self):
        urls = ["https://rzp.io/i/abc", "HTTPS://x.example/pay", "http://plain.example", "javascript:alert(1)", " https://leading-space.example",
                "data:text/html,<script>1</script>", "//protocol-relative.example", "https:/no-slashes", None, 5, {}, "",
                "http://127.0.0.1:8099/pay/plink_1", "http://localhost/pay", "http://127.0.0.1.evil.example/x", "http://localhost@evil.example/x",
                "http://127.0.0.1:80@evil.example/x", "http://10.0.0.5/x"]
        got = self._run("[" + ",".join(json.dumps(u) if u is not None else "null" for u in urls) + "].map((u) => t.finReqSafeUrl(u))")
        assert got == ["https://rzp.io/i/abc", "HTTPS://x.example/pay", "", "", "", "", "", "", "", "", "", "",
                       "http://127.0.0.1:8099/pay/plink_1", "http://localhost/pay", "", "", "", ""]      # plain http only for this computer itself

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


class TestByeLawAuthorityPanel:
    """The Bye-Law disbursement panel: one panel for payments AND transfers, wired to the six API routes."""

    def test_one_panel_two_entry_points(self):
        p = _panel()
        assert p.count("Bye-Law authority —") == 1                      # a single implementation (no duplicate markup)
        assert "finAuthOpen('payment'" in p and "finAuthOpen('transfer'" in p

    def test_api_paths_are_real_routes(self):
        assert "`/${a.kind}s/${a.pk}/authority`" in FIN_JS and "`/${a.kind}s/${a.pk}/countersign`" in FIN_JS
        from api.routers.finance_authority import router
        paths = {r.path for r in router.routes}
        assert "/api/v1/finance/payments/{payment_pk}/authority" in paths and "/api/v1/finance/transfers/{transfer_pk}/countersign" in paths

    def test_request_fields_match_the_schema(self):
        from api.schemas.finance import AuthorityWrite
        for field in ("resolution_reference", "resolution_date", "scheme_description", "purpose_code",
                      "parichalak_consulted", "president_order_reference", "president_order_date"):
            assert field in AuthorityWrite.model_fields and field in FIN_JS

    def test_signing_is_not_a_client_side_decision(self):
        # the UI only offers the buttons; the Treasurer/Secretary seat is checked by the server
        # Office names appear in this file only as LABELS for what the server reports; nothing here decides who may act.
        assert "countersign" in FIN_JS and "isTreasurer" not in FIN_JS and "isSecretary" not in FIN_JS and "isPresident" not in FIN_JS
        assert not re.search(r"(person_pk|currentUser)[^\n]*(TREASURER|SECRETARY|PRESIDENT)", FIN_JS)

    def test_panel_is_live_refresh_aware(self):
        assert re.search(r"this\.finAuth[,\]]", FIN_JS)                    # an open panel counts as busy for the live feed
        assert "finance_disbursement_authority" in ADMIN_JS


class TestMemberDestinationsAndEventsUi:
    def test_the_pay_card_groups_by_sangha_and_names_the_destination(self):
        card = _pranami_panel()
        assert "pranamiPayGroups()" in card and "g.name" in card              # one block per Sangha, named
        assert "organization_name" in card                                    # the result line says WHICH Sangha is being paid
        assert "pranamiPayGroups()" in DASH_JS
        # every field read off a head / group is one the API really returns
        from api.schemas.finance import MyPayableHead
        for field in re.findall(r"\bh\.([a-z_]+)", card):
            assert field in MyPayableHead.model_fields, field

    def test_the_event_form_posts_what_the_api_accepts(self):
        from api.schemas.finance import EventCreate
        body = SETUP_JS.split("async finEventSubmit()")[1].split("async finHeadAdopt()")[0] if "async finHeadAdopt()" in SETUP_JS else SETUP_JS.split("async finEventSubmit()")[1]
        assert '"/events"' in body
        for field in ("organization_pk", "event_name", "description", "collection_account_pk"):
            assert field in EventCreate.model_fields and field in body

    def test_events_are_configured_by_an_approver_only(self):
        p = _panel()
        assert "finEventOpenCreate()" not in p, "events have their own module; the Heads page no longer offers them"
        assert "/events" in SETUP_JS and "finEventOpenCreate" in SETUP_JS      # the API call and its handler are kept


class TestHeadsListScopeAndEdit:
    """Owner 2026-11-20: the heads list shows each head's scope code and name and offers Edit (a Sakha's copy of a Kendra head
    only changes its account; an all-Sakhas head sends no collection fields)."""

    def test_list_shows_the_scope_and_offers_edit(self):
        setup = _screen("finSetup")
        assert "<th>Scope</th>" in setup and 'x-text="h.collection_scope_code"' in setup and 'x-text="h.collection_scope_name || h.collection_scope_code"' in setup       # name first, code small
        assert "Each Sakha's own scope" in setup and "finHeadOpenEdit(h)" in setup
        assert "<th>Fund</th>" in setup and 'x-text="h.collection_fund_code"' in setup and 'x-text="h.collection_fund_name"' in setup

    def test_edit_sends_only_what_each_kind_of_head_may_change(self):
        js = (FE / "assets/js/finance-setup.js").read_text(encoding="utf-8")
        assert 'f.kind === "copy"' in js and 'collection_account_pk: f.collection_account_pk || null' in js
        assert 'f.kind === "source"' in js


class TestCreateHeadScopeAndFund:
    """Owner 2026-11-20: the Create head form lets the person see and choose the scope (and a fund); empty = automatic."""

    def test_form_offers_scope_and_fund_and_sends_them(self):
        setup = _screen("finSetup")
        js = (FE / "assets/js/finance-setup.js").read_text(encoding="utf-8")
        assert 'x-model="finContribForm.collection_scope_pk"' in setup and 'x-model="finContribForm.collection_fund_pk"' in setup
        assert "Automatic — the Sangha's general scope" in setup
        assert "finContribScopeChanged()" in setup and "async finContribScopeChanged()" in js
        assert js.count("f.collection_scope_pk || null") >= 2           # contribution and plain expense head
        assert "allSakhas ? null" in js                                 # a head for all Sakhas never sends a scope


class TestFundsTab:
    """Owner request 2026-11-20: a Funds tab in the Finance group - every fund across all scopes, with filters, create / edit and the
    lifecycle buttons (the same finance.js code the scope detail uses)."""

    def test_the_mixin_is_loaded_installed_and_never_overwrites_the_host(self):
        assert '<script src="/assets/js/finance-funds.js"></script>' in ADMIN_HTML
        assert "NSSFinanceFunds.install(" in ADMIN_JS and "window.NSSFinanceFunds" in FUNDS_JS
        assert FUNDS_JS.count("hasOwnProperty.call(target, key)") == 1 and "getOwnPropertyDescriptors" in FUNDS_JS

    def test_the_tab_is_in_the_sidebar_the_wrapper_the_labels_and_the_live_feed(self):
        assert "finEnterTab('finFunds')" in _sidebar()
        assert "'finFunds'" in ADMIN_HTML.split("includes(activeTab) && canViewFinance")[0].rsplit("[", 1)[1]
        assert 'finFunds: "Finance Funds"' in ADMIN_JS
        for table in ("financial_scope", "fund_master"):
            assert re.search(rf"^\s+{table}: \[[^\]]*\"finFunds\"", ADMIN_JS, re.M), table
        assert re.search(r"finFunds: \{ reload: \(h\) => h\.finLiveReload\(\), busy: \(h\) => h\.finLiveBusy\(\) \}", ADMIN_JS)
        assert 'tab === "finFunds"' in FIN_JS and 'this.activeTab === "finFunds"' in FIN_JS

    def test_the_panel_lists_filters_and_reuses_the_shared_fund_actions(self):
        panel = ADMIN_HTML[ADMIN_HTML.index("activeTab === 'finFunds'\" x-cloak"):]
        panel = panel[:panel.index("activeTab === 'finTransactions'")]
        for needle in ("finFundsAll", "finFundsFilter.scope", "finFundsFilter.type", "finFundsFilter.status", "finFundsFilter.restricted",
                       "finSubmitFund()", "finStartFundEdit(f)", "finActions('fund', f.status)", "finAskTransition('fund'", "finFundsOpenNew()"):
            assert needle in panel, needle
        assert "canManageFinance" in panel

    def test_creating_a_fund_names_its_scope_and_refreshes_the_tab_on_screen(self):
        assert 'financial_scope_pk: scopePk' in FIN_JS and "Choose the financial scope this fund belongs to." in FIN_JS
        assert 'if (entity === "fund" && this.activeTab === "finFunds")' in FIN_JS

    def test_the_funds_tab_follows_the_admin_scope_sangha(self):
        """A Sakha admin's admin scope names one Sangha: it is selected and locked (never asked); wider admins may search one Sangha."""
        assert "const own = this.finSetupScopeOrg;" in FUNDS_JS and "this.corrSelectOrg(this.finFundsOrg, own)" in FUNDS_JS
        assert "get finFundsOrgLocked() { return !!this.finSetupScopeOrg; }" in FUNDS_JS
        assert "params.organization_pk = this.finFundsOrgPk" in FUNDS_JS and FUNDS_JS.count("organization_pk") >= 3
        panel = ADMIN_HTML[ADMIN_HTML.index("activeTab === 'finFunds'\" x-cloak"):]
        panel = panel[:panel.index("activeTab === 'finTransactions'")]
        assert 'x-show="finFundsOrgLocked && finFundsOrg.selected"' in panel and 'x-show="!finFundsOrgLocked"' in panel
        assert "finFundsOrgChanged()" in panel and "finFundsClearOrg()" in panel
        assert "get finFundsDefaultScope()" in FUNDS_JS and "financial_scope_pk: this.finFundsDefaultScope" in FUNDS_JS

    def test_a_single_sakha_admin_has_the_sangha_chosen_and_locked_in_every_finance_form(self):
        """Owner 2026-11-20: an admin scoped to one Sakha has the Sangha selected for them, with no way to change it."""
        for form in ("finScopeForm", "finFundForm", "finContribForm", "finEventForm"):
            assert f'x-model="{form}.organization.query" :disabled="finSetupOrgLocked"' in ADMIN_HTML, form
        assert "finHeadForm.mode === 'edit' || finSetupOrgLocked" in ADMIN_HTML and "finAcctForm.mode === 'edit' || finSetupOrgLocked" in ADMIN_HTML
        assert ADMIN_HTML.count('x-show="!finSetupOrgLocked" @click="corrClearPicker(') == 3
        assert "_finOwnOrgPicker(extra)" in FIN_JS and "organization: this._finOwnOrgPicker()," in FIN_JS       # the scope form is prefilled
        assert "this.finSetupScopeOrg ? this.finSetupScopeOrg.organization_pk" in FIN_JS                          # and the submit never trusts the picker

    def test_an_edit_form_shows_the_sangha_name_in_its_text_box(self):
        """Owner 2026-11-20: the Sangha name sits IN the box (query), not only in the hint under it."""
        assert "const pickerWith = (pk, name) =>" in SETUP_JS and "query: pk ? (name || \"\") : \"\"" in SETUP_JS
        assert "organization: pickerWith(h.organization_pk, h.organization_name)" in SETUP_JS        # edit finance head
        assert "organization: pickerWith(a.organization_pk, a.organization_name)" in SETUP_JS        # edit receiving account
        assert "selected: { organization_pk: a.organization_pk" not in SETUP_JS

    def test_the_edit_form_always_offers_scope_and_fund_and_no_display_order(self):
        """Owner 2026-11-20: scope and fund can be changed when editing a head (not only with UPI on); Display order is gone and lists sort by name."""
        setup = _screen("finSetup")
        assert "<h4 class=\"form-section-title\">Books into</h4>" in setup
        assert "finHeadForm.kind === 'normal'" in setup                     # a copy / an all-Sakhas head have no scope of their own
        assert 'x-model="finHeadForm.collection_scope_pk"' in setup and 'x-model="finHeadForm.collection_fund_pk"' in setup
        assert "Where UPI collections go" in setup and "Money lands in account" in setup
        assert "display_order" not in setup and "display_order" not in SETUP_JS and "Display order" not in setup

    def test_a_head_can_be_deleted_only_when_unused_and_through_the_server(self):
        setup = _screen("finSetup")
        line = next(l for l in setup.splitlines() if "finHeadDelete(h)" in l)
        assert "canConfigureFinance" in line and "!h.transaction_count" not in line       # owner 2026-11-21: Delete is ALWAYS there; it explains when it cannot delete
        assert 'this._finSend("DELETE", `/heads/${h.finance_head_pk}`)' in SETUP_JS
        assert "NSSDialog.confirm(" in SETUP_JS.split("async finHeadDelete(h)", 1)[1].split("finHeadCancel()", 1)[0]


class TestTheFinanceEntryPicksItsMemberByName:
    """Owner 2026-11-20: the entry form no longer asks for a typed Sangha Sevi ID; it shares the payer picker (finMemberInput / Pick / Clear)."""

    def test_the_entry_form_uses_the_shared_member_picker_not_a_typed_id(self):
        html = ADMIN_HTML
        assert 'x-model="finTxnForm.sangha_sevi_id"' not in html                                   # never typed by hand any more
        assert 'x-model="finTxnForm.member.query"' in html and '@input="finMemberInput(finTxnForm)"' in html
        assert '@click="finMemberPick(finTxnForm, m)"' in html and '@click="finMemberClear(finTxnForm)"' in html

    def test_one_picker_implementation_serves_both_forms(self):
        assert "finMemberInput(form) {" in SETUP_JS and "async finMemberSearch(form) {" in SETUP_JS
        assert "finReqMemberInput" not in SETUP_JS and "finReqMemberPick" not in ADMIN_HTML          # the payer form passes ITS form instead of a copy
        assert "member: emptyPicker()" in FIN_JS and "Choose the member from the list that appears as you type" in FIN_JS
        # editing an entry shows the member's NAME in the box, from the response's person_name
        assert "`${txn.person_name || \"\"} (${txn.sangha_sevi_id})`" in FIN_JS
        assert "sangha_sevi_id: blank(f.sangha_sevi_id)" in FIN_JS                                  # what is sent is still the id the match set


class TestTheTreasurersOwnControlsAreGreyedOut:
    """Owner 2026-11-20: a user who reaches Finance only through the Treasurer seat configures finance but cannot change the limit / 'needs no approval'."""

    def test_the_locked_flag_is_the_treasurer_role_without_an_admin_role(self):
        assert "get finControlsLocked()" in SETUP_JS
        body = SETUP_JS.split("get finControlsLocked()", 1)[1].split("},", 1)[0]
        assert '"NSS_ERP_SAKHA_TREASURER"' in body and '"NSS_ERP_ADMIN"' in body and '"NSS_ERP_SAKHA_FINANCE_ADMIN"' in body and '"NSS_ERP_KENDRA_FINANCE_ADMIN"' in body
        assert '"NSS_ERP_KENDRA_ADMIN"' not in body and '"NSS_ERP_SAKHA_ADMIN"' not in body              # an admin role alone no longer unlocks them (it carries no finance)

    def test_the_limit_and_the_no_approval_fields_follow_it(self):
        setup = _screen("finSetup")
        assert 'x-model="finPolicy.input" :disabled="!canConfigureFinance || finControlsLocked"' in setup
        assert 'x-show="canConfigureFinance && !finControlsLocked"' in setup                                   # the Save limit button is gone
        assert setup.count('x-model="finHeadForm.skips_approval" :disabled="finControlsLocked"') == 2
        assert 'x-model="finHeadForm.treasurer_limit" :disabled="finControlsLocked"' in setup


class TestDeleteExplainsAndSwitchOffIsOffered:
    """Owner 2026-11-21: Delete never silently disappears. A used head (or a Sakha's copy of a Kendra head) is not deleted - the person is told why and
    offered Switch off; an INACTIVE head can be switched back on; the Scope / Fund cells read cleanly."""

    def test_a_used_head_or_a_copy_is_offered_switch_off_instead_of_a_delete(self):
        body = SETUP_JS.split("async finHeadDelete(h)", 1)[1].split("async finHeadSwitch(h, to)", 1)[0]
        assert "h.is_kendra_copy || Number(h.transaction_count) > 0" in body and "_finHeadOfferSwitchOff(h)" in body
        assert "err.status === 409 || err.status === 403" in body                       # the server has the last word
        assert "money history is never erased" in body and "Switch the head off?" in body

    def test_switch_off_and_on_use_the_lifecycle_endpoint(self):
        body = SETUP_JS.split("async finHeadSwitch(h, to)", 1)[1].split("finHeadCancel()", 1)[0]
        assert '"POST", `/heads/${h.finance_head_pk}/transition`, { status: to, remarks: null }' in body
        setup = _screen("finSetup")
        assert next(l for l in setup.splitlines() if "finHeadSwitchOff(h)" in l).count("is_kendra_copy") == 1          # only where Delete cannot remove it
        assert "finHeadSwitch(h, 'ACTIVE')" in setup and "h.status === 'INACTIVE'" in setup

    def test_the_thrown_error_carries_the_http_status(self):
        assert "e.status = res.status; throw e;" in FIN_JS

    def test_the_scope_and_fund_cells_are_tidied(self):
        css = (FE / "assets/css/style.css").read_text(encoding="utf-8")
        setup = _screen("finSetup")
        assert 'class="fh-cell-scope"' in setup and 'class="fh-cell-fund"' in setup
        assert ".fh-cell-fund { min-width: 9rem; white-space: nowrap; }" in css

    def test_the_row_buttons_wrap_inside_a_fixed_width_instead_of_running_off_the_edge(self):
        css = (FE / "assets/css/style.css").read_text(encoding="utf-8")
        rule = next(l for l in css.splitlines() if l.startswith(".fh-actions {"))
        assert "flex-wrap: wrap" in rule and "width: 19rem" in rule and "flex-wrap: nowrap" not in rule
        assert ".fh-actions .btn-action { white-space: nowrap; }" in css                  # a button's own label still never splits

    def test_a_switched_off_head_shows_inactive_only_not_a_portal_state_as_well(self):
        setup = _screen("finSetup")
        assert """x-show="finHeadPortalOpen(h) === false && h.status === 'ACTIVE'">Closed</span>""" in setup
        assert """x-show="finHeadPortalOpen(h) === true && h.status === 'ACTIVE'">Open</span>""" in setup
        assert """x-show="h.status !== 'ACTIVE'" x-text="finLabel(h.status)\"""" in setup                   # the Inactive badge is unchanged

    def test_the_scope_column_is_wide_enough_for_the_usual_name_on_one_line(self):
        css = (FE / "assets/css/style.css").read_text(encoding="utf-8")
        assert ".fh-cell-scope { min-width: 14rem; max-width: 19rem; }" in css and ".fh-cell-scope .fh-name { font-size: 0.85rem; white-space: nowrap;" in css


class TestScopesAndFundsAreActiveAtOnce:
    """Owner 2026-11-22: a scope's code is made for the user and neither a scope nor a fund starts as an extra-step draft."""

    def test_the_scope_form_asks_no_code_and_sends_none(self):
        form = _between_text(FIN_JS, "async finSubmitScope()", "async finOpenScope")
        assert "scope_code:" not in form and "f.scope_code" not in form and "activate: true" in form and "The scope name is required." in form
        assert "finScopeForm.scope_code" not in ADMIN_HTML and "Made automatically" in ADMIN_HTML
        assert 'scope_code: "", scope_name' not in FIN_JS

    def test_the_fund_form_asks_to_be_active_and_says_what_happened(self):
        form = _between_text(FIN_JS, "async finSubmitFund()", "finStartFundEdit(fund)")
        assert "activate: true" in form and 'created.status === "ACTIVE"' in form and "created and active" in form

    def test_what_the_pages_send_is_what_the_api_accepts(self):
        from api.schemas.finance import FundCreate, ScopeCreate

        assert {"activate", "scope_name", "scope_type"} <= set(ScopeCreate.model_fields) and "activate" in FundCreate.model_fields
        assert ScopeCreate.model_fields["scope_code"].is_required() is False


def _between_text(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class TestOnlyAFinanceAdministratorCreatesScopesAndFunds:
    def test_the_create_buttons_follow_the_servers_answer(self):
        assert "get canAdministerFinance() {" in FIN_JS and "this.finRef.finance_admin" in FIN_JS
        for button in ('x-show="canAdministerFinance" @click="finOpenScopeForm()">+ New scope</button>',
                       'x-show="canAdministerFinance && !finFundForm.show" @click="finFundsOpenNew()">+ New fund</button>'):
            assert button in ADMIN_HTML
        assert 'x-show="canAdministerFinance && !finFundForm.show && [\'DRAFT\',\'ACTIVE\'].includes(finScope.status)"' in ADMIN_HTML
        assert 'x-show="canManageFinance" @click="finOpenScopeForm()"' not in ADMIN_HTML

    def test_the_reference_field_exists_in_the_api(self):
        from api.schemas.finance import FinanceReference

        assert "finance_admin" in FinanceReference.model_fields


class TestFundCodeIsAutomatic:
    def test_the_fund_form_asks_no_code_and_sends_none(self):
        form = _between_text(FIN_JS, "async finSubmitFund()", "finStartFundEdit(fund)")
        assert "fund_code:" not in form and "f.fund_code" not in form and "The fund name is required." in form
        assert "finFundForm.fund_code" not in ADMIN_HTML and 'fund_code: "", fund_name' not in FIN_JS

    def test_both_fund_forms_say_the_code_is_made_automatically_with_the_types_code(self):
        assert ADMIN_HTML.count("finRef.fund_type_codes[finFundForm.fund_type]") == 2                    # the two fund forms

    def test_the_type_codes_reach_the_page_from_the_reference(self):
        from api.schemas.finance import FinanceReference

        assert "fund_type_codes" in FinanceReference.model_fields           # read from master data (category FUND_TYPE_CODE) by the reference endpoint


class TestScopeCodeShowsItsTypeCode:
    def test_the_scope_form_shows_how_the_code_is_made_with_the_types_own_code(self):
        assert "finRef.scope_type_codes[finScopeForm.scope_type]" in ADMIN_HTML
        assert ADMIN_HTML.count("Made automatically: the Sakha\\'s code + ") == 3                         # one scope form, two fund forms
        assert "Made automatically: the Sakha's code + the name" not in ADMIN_HTML

    def test_the_type_codes_reach_the_page_from_the_reference(self):
        from api.schemas.finance import FinanceReference

        assert "scope_type_codes" in FinanceReference.model_fields


class TestTheYearStripIsOnEverySection:
    """Owner 2026-11-23: the financial year and its status are shown at the top of every Finance section."""

    def _wrapper(self) -> str:
        start = ADMIN_HTML.index("<!-- The financial year and its status, on every Finance section -->")
        return ADMIN_HTML[start:start + 3500]

    def test_the_strip_sits_in_the_one_wrapper_every_finance_section_shares(self):
        strip = ADMIN_HTML.index("fin-year-strip")
        wrapper = ADMIN_HTML.rindex("['finOverview','finStructure','finFunds','finBudget','finSinking','finTransactions','finTransfers','finSetup','finCollections'].includes(activeTab)", 0, strip)
        first_section = ADMIN_HTML.index("<!-- ═════════ Overview", strip) if "<!-- ═════════ Overview" in ADMIN_HTML[strip:] else len(ADMIN_HTML)
        assert wrapper < strip < first_section                                           # inside the wrapper, before any section: so on every one of them

    def test_it_shows_the_year_its_status_its_dates_and_what_the_status_means(self):
        strip = self._wrapper()
        for needle in ("finCurrentYear.year_code", 'finBadge(finCurrentYear.status)', "finLabel(finCurrentYear.status)", "finDate(finCurrentYear.start_date)",
                       "finDate(finCurrentYear.end_date)", "finYearMeaning(finCurrentYear.status)", "finOtherLiveYears", "No financial year exists yet"):
            assert needle in strip, needle

    def test_every_status_has_its_meaning_in_the_shared_config(self):
        from api.schemas.finance import YEAR_STATUSES

        block = re.search(r"FINANCE_YEAR_STATUS_MEANING: \{(.*?)\n    \},", CONFIG_JS, re.S).group(1)
        for status in YEAR_STATUSES:
            assert re.search(rf"\b{status}: \"", block), status

    def test_every_section_loads_the_years_and_the_live_feed_keeps_them_fresh(self):
        enter = FIN_JS.split("async finEnterTab(tab) {", 1)[1].split("if (this.activeTab === \"finOverview\")", 1)[0]
        assert "this.finLoadYears()" in enter                                           # before any section's own branch
        reload_ = FIN_JS.split("async finLiveReload() {", 1)[1][:400]
        assert 'await this.finLoadYears()' in reload_
        admin = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
        block = re.search(r"financial_year: \[(.*?)\]", admin, re.S).group(1)
        for tab in TABS:
            assert f'"{tab}"' in block, tab                                             # every Finance section follows a year's status

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
    def test_the_current_year_and_the_others_run_as_intended(self):
        import json
        import subprocess

        start = FIN_JS.index("            get finCurrentYear() {")
        end = FIN_JS.index("            // The latest financial year (by start).")
        config = CONFIG_JS[CONFIG_JS.index("    FINANCE_YEAR_STATUS_MEANING: {"):CONFIG_JS.index("    FINANCE_STATUS_LABELS: {")]
        script = f"""
        const NSS = {{ {config} formatDate: (d) => "D(" + d + ")" }};
        const host = {{ finYears: [], {FIN_JS[start:end].rstrip().rstrip(",")} }};
        const set = (rows) => {{ host.finYears = rows.map(([code, status]) => ({{ year_code: code, status, financial_year_pk: code }})); }};
        const r = {{}};
        set([["2026-27", "OPEN"], ["2027-28", "PLANNED"], ["2025-26", "CLOSED"]]);
        r.current = host.finCurrentYear.year_code; r.others = host.finOtherLiveYears.map((y) => y.year_code + ":" + y.status);
        set([["2025-26", "CLOSED"], ["2026-27", "CLOSED"]]); r.noneOpen = host.finCurrentYear.year_code; r.noneOpenOthers = host.finOtherLiveYears.length;   // the latest, closed
        set([["2026-27", "CLOSING"], ["2027-28", "PLANNED"]]); r.closing = [host.finCurrentYear.year_code, host.finOtherLiveYears.map((y) => y.year_code)];
        set([["2027-28", "PLANNED"], ["2028-29", "PLANNED"]]); r.planned = [host.finCurrentYear.year_code, host.finOtherLiveYears.map((y) => y.year_code)];
        set([]); r.empty = host.finCurrentYear;
        set([["2026-27", "OPEN"]]); r.meaning = host.finYearMeaning("OPEN"); r.unknown = host.finYearMeaning("NOPE"); r.date = [host.finDate("2026-04-01"), host.finDate(null)];
        console.log(JSON.stringify(r));
        """
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        got = json.loads(out.stdout)
        assert got["current"] == "2026-27" and got["others"] == ["2027-28:PLANNED"]            # the open year, then what comes next (closed years are history)
        assert got["noneOpen"] == "2026-27" and got["noneOpenOthers"] == 0
        assert got["closing"] == ["2026-27", ["2027-28"]]                                      # the year being wound up leads; the next one follows
        assert got["planned"] == ["2027-28", ["2028-29"]]                                      # nothing open yet: the earliest planned leads
        assert got["empty"] is None and "working year" in got["meaning"] and got["unknown"] == ""


class TestTheYearIsTheCurrentOneWhereverARecordIsCreated:
    """Owner 2026-11-23: every create form has the financial year pre-selected to the CURRENT one, with no option to change. The lists and the summary keep
    their year filters (looking back, closed years included, is how audit works)."""

    def _form(self, marker: str, length: int = 2600) -> str:
        i = ADMIN_HTML.index(marker)
        return ADMIN_HTML[i:i + length]

    def test_the_create_forms_show_the_year_as_text_not_a_dropdown(self):
        txn = self._form("'New transaction' : 'Edit transaction'")
        transfer = self._form('Moves money between two different financial scopes')
        scope = self._form("<!-- New scope form -->", 6000)
        for form in (txn, transfer, scope):
            assert 'x-model="finTxnForm.financial_year_pk"' not in form and 'x-model="finTransferForm.financial_year_pk"' not in form
            assert 'x-model="finScopeForm.financial_year_pk"' not in form
        assert 'x-model="finTxnForm.financial_year_pk"' not in ADMIN_HTML and 'x-model="finTransferForm.financial_year_pk"' not in ADMIN_HTML
        assert 'x-model="finScopeForm.financial_year_pk"' not in ADMIN_HTML 
        # the budget form is the one choice (owner 2026-11-24): the current year, or - in advance - the next one; nothing else is offered
        assert 'x-model="finBudgetStart.year"' in ADMIN_HTML and "finBudgetNextYear" in ADMIN_HTML
        assert ADMIN_HTML.count("The current financial year, set for you.") >= 4                                  # scope, transaction, transfer, budget
        assert 'x-show="finBudgetYear">The current financial year, set for you.' in ADMIN_HTML and "finBudgetYearTaken" in ADMIN_HTML

    def test_the_filters_and_the_summary_still_let_you_look_back(self):
        for model in ("finSumYear", "finTxnYear", "finTransferYear"):
            assert f'x-model="{model}"' in ADMIN_HTML, model

    def test_the_forms_open_with_the_current_year_chosen(self):
        assert "f.financial_year_pk = this.finEntryYear.financial_year_pk;" in FIN_JS and "f.transfer_date = this._finClampDate(this.finEntryYear)" in FIN_JS
        assert "financial_year_pk: this.finScopeYear ? this.finScopeYear.financial_year_pk : \"\"" in FIN_JS
        assert "const first = this.finBudgetYear || this.finBudgetNextYear;" in (FE / "assets/js/finance-budget.js").read_text(encoding="utf-8")

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
    def test_which_year_each_form_uses_runs_as_intended(self):
        import json
        import subprocess

        start = FIN_JS.index("            get finEntryYear() {")
        end = FIN_JS.index("            get finYearChoices()") if False else FIN_JS.index("            finYearLabelFor(pk)")
        end = FIN_JS.index("\n", end) + 1
        label_src = FIN_JS[start:end]
        cur_start = FIN_JS.index("            get finCurrentYear() {")
        cur_end = FIN_JS.index("            get finOtherLiveYears() {")
        config = CONFIG_JS[CONFIG_JS.index("    FINANCE_STATUS_LABELS: {"):CONFIG_JS.index("    FINANCE_STATUS_BADGE_MAP: {")]
        script = f"""
        const NSS = {{ {config} financeStatusLabel(s) {{ return this.FINANCE_STATUS_LABELS[s] || s; }} }};
        const host = {{ finYears: [], {FIN_JS[cur_start:cur_end].rstrip().rstrip(",")}, {label_src.rstrip().rstrip(",")} }};
        const set = (rows) => {{ host.finYears = rows.map(([code, status]) => ({{ year_code: code, status, financial_year_pk: code }})); }};
        const r = {{}};
        set([["2026-27", "OPEN"], ["2027-28", "PLANNED"]]);
        r.entry = host.finEntryYear.year_code; r.scope = host.finScopeYear.year_code; r.label = host.finYearLabel(host.finEntryYear); r.byPk = host.finYearLabelFor("2027-28");
        set([["2026-27", "CLOSING"], ["2027-28", "PLANNED"]]); r.closing = [host.finEntryYear, host.finScopeYear.year_code];     // nothing may be RECORDED in it, a scope may still belong to it
        set([["2026-27", "CLOSED"]]); r.closed = [host.finEntryYear, host.finScopeYear];
        set([]); r.none = [host.finEntryYear, host.finScopeYear, host.finYearLabel(null), host.finYearLabel(null, "No open year"), host.finYearLabelFor("zzz")];
        console.log(JSON.stringify(r));
        """
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        got = json.loads(out.stdout)
        assert got["entry"] == "2026-27" and got["scope"] == "2026-27" and got["label"] == "2026-27 (Open)" and got["byPk"] == "2027-28 (Planned)"
        assert got["closing"] == [None, "2026-27"] and got["closed"] == [None, None]
        assert got["none"] == [None, None, "No financial year", "No open year", "-"]
