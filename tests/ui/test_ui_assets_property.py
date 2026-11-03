"""
Assets & Property admin UI (Module #22, Tier 6) - source-level tests.

Parses the shipped files directly (no browser, no server), same style as
test_ui_scoped_role_tabs.py / test_ui_advisory_board_dashboard.py. Covers: tab
and sidebar gating, the /admin init() guard, permission-derived write buttons
(Auditor / Report Viewer are read-only), the endpoint URLs the screens call,
the lifecycle tables mirroring the router, friendly labels and badge classes
(no raw codes), stale-response guards and markup/JS handler parity.

Nothing here proves the screens work in a browser - that needs a manual pass.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
ADMIN_HTML = (FRONTEND / "admin.html").read_text(encoding="utf-8")
ADMIN_JS = (FRONTEND / "assets" / "js" / "admin.js").read_text(encoding="utf-8")
AP_JS = (FRONTEND / "assets" / "js" / "assets-property.js").read_text(encoding="utf-8")
NSS_CONFIG = (FRONTEND / "assets" / "js" / "nss-config.js").read_text(encoding="utf-8")
BADGES_CSS = (FRONTEND / "assets" / "css" / "badges.css").read_text(encoding="utf-8")
ROUTER = (REPO_ROOT / "api" / "routers" / "assets_property.py").read_text(encoding="utf-8")


def _panel() -> str:
    """The single Assets & Property panel markup (both tabs share it)."""
    start = ADMIN_HTML.index("VIEW: Assets & Property (Module #22, Tier 6)")
    end = ADMIN_HTML.index("</div><!-- /Assets & Property -->")
    return ADMIN_HTML[start:end]


def _sidebar() -> str:
    start = ADMIN_HTML.index("Assets & Property group (collapsible, Module #22)")
    return ADMIN_HTML[start:start + 3500]


def _js_block(source: str, opener: str, closer: str) -> str:
    start = source.index(opener) + len(opener)
    return source[start:source.index(closer, start)]


def _lifecycle_from_js() -> dict:
    block = _js_block(NSS_CONFIG, "ASSET_PROPERTY_LIFECYCLE: {", "ASSET_PROPERTY_ARCHIVABLE_STATUSES")
    out = {}
    for kind in ("properties", "assets"):
        part = block.split(f"{kind}: {{")[1]
        terminal = re.search(r'terminal: "(\w+)"', part).group(1)
        trans_block = _js_block(part, "transitions: {", "}")
        trans = {
            state: set(re.findall(r'"(\w+)"', members))
            for state, members in re.findall(r"(\w+):\s*\[([^\]]*)\]", trans_block)
        }
        out[kind] = {"terminal": terminal, "transitions": trans}
    return out


# ── Files and wiring ────────────────────────────────────────────────────


class TestWiring:

    def test_mixin_file_is_loaded_before_admin_js(self):
        mixin = ADMIN_HTML.index('<script src="/assets/js/assets-property.js"></script>')
        host = ADMIN_HTML.index('<script src="/assets/js/admin.js"></script>')
        assert mixin < host
        assert "?v=" not in ADMIN_HTML[mixin:mixin + 80], "never hand-maintain ?v="

    def test_mixin_is_installed_into_the_admin_component(self):
        assert "NSSAssetsProperty.install(NSSAttendanceRegister.install({" in ADMIN_JS
        assert ADMIN_JS.rstrip().endswith("}));\n}")
        assert "window.NSSAssetsProperty" in AP_JS

    def test_install_uses_descriptors_not_spread(self):
        # spread would freeze every getter (canManageAssets, apNextStatuses) at install time
        assert "getOwnPropertyDescriptors" in AP_JS

    def test_no_inline_event_handlers(self):
        assert not re.search(r"\son[a-z]+\s*=", _panel()), "CSP forbids inline handlers"
        assert "eval(" not in AP_JS and "new Function" not in AP_JS


# ── Gating ──────────────────────────────────────────────────────────────


class TestGating:

    def test_view_and_manage_permissions(self):
        view = re.search(r"get canViewAssets\(\) \{(.*?)\n            \},", AP_JS, re.DOTALL).group(1)
        manage = re.search(r"get canManageAssets\(\) \{(.*?)\n            \},", AP_JS, re.DOTALL).group(1)
        assert '"ASSET_VIEW"' in view and '"ASSET_MANAGE"' in view
        assert '"ASSET_MANAGE"' in manage and '"ASSET_VIEW"' not in manage

    def test_sidebar_group_and_panel_are_gated_on_view_permission(self):
        side = _sidebar()
        assert 'x-if="canViewAssets"' in side
        assert "apEnterTab('properties')" in side and "apEnterTab('assets')" in side
        assert "Assets &amp; Property" in side
        assert re.search(r">\s*Properties\s*</a>", side) and re.search(r">\s*Assets\s*</a>", side)
        assert "(activeTab === 'properties' || activeTab === 'assets') && canViewAssets" in _panel()

    def test_init_guard_admits_asset_only_users(self):
        guard = ADMIN_JS.split("// Redirect non-admin users to the dashboard.")[1].split("// Governance-only admin")[0]
        assert "!this.hasGeneralAdminAccess && !this.canViewGovernance && !this.canViewAssets" in guard
        assert 'window.location.href = "/dashboard"' in guard

    def test_limited_admin_lands_on_assets_without_general_loaders(self):
        limited = ADMIN_JS.split("if (!this.hasGeneralAdminAccess) {")[1].split("// Load reference data in parallel")[0]
        assert 'govHash === "assets" || govHash === "properties"' in limited
        assert "!this.canViewGovernance && this.canViewAssets" in limited
        assert "await this.apEnterTab()" in limited
        # one early return, before any general reference loader (users, roles, claims ...) runs
        assert limited.count("return;") == 1
        assert "fetchUsers" not in limited and "fetchAvailableRoles" not in limited

    def test_general_unrelated_sections_stay_hidden_for_limited_admins(self):
        # The People/Organizations/Directories/Settings groups sit inside this wrapper.
        assert '<template x-if="hasGeneralAdminAccess">' in ADMIN_HTML

    def test_deep_links(self):
        loaders = ADMIN_JS.split("const tabLoaders = {")[1].split("};")[0]
        assert "properties: () => { if (this.canViewAssets) this.apEnterTab(); }" in loaders
        assert "assets: () => { if (this.canViewAssets) this.apEnterTab(); }" in loaders
        # the hash IS the tab key, so #assets / #properties open the matching tab
        assert "_initialTab" in ADMIN_JS and "(_initialHash || \"users\")" in ADMIN_JS

    def test_every_write_control_is_permission_gated(self):
        lines = _panel().splitlines()
        write_handlers = [
            "apOpenCreate", "apOpenEdit", "apArchive", "apToggleMaintForm", "apEditMaintenance",
            "apDeleteMaintenance", "apToggleStatForm", "apEditStatutory", "apDeleteStatutory",
            "apToggleDocForm", "apDetachDocument", "apOpenAssign", "apOpenTransfer", "apStartTransition",
        ]
        gate = re.compile(r"canManageAssets|apCanAssignCustodian|apCanTransferCustody")
        for handler in write_handlers:
            hits = [i for i, ln in enumerate(lines) if f"@click=\"{handler}(" in ln]
            assert hits, f"{handler} button missing"
            for i in hits:
                window = "\n".join(lines[max(0, i - 6): i + 1])
                assert gate.search(window), f"{handler} is not gated on a manage permission"

    def test_derived_gates_build_on_manage_permission(self):
        for getter in ("apCanAssignCustodian", "apCanTransferCustody"):
            body = re.search(rf"get {getter}\(\) \{{(.*?)\n            \}},", AP_JS, re.DOTALL).group(1)
            assert "this.canManageAssets" in body
        assign = re.search(r"get apCanAssignCustodian\(\) \{(.*?)\n            \},", AP_JS, re.DOTALL).group(1)
        assert "this.isGovNssWideAdmin" in assign, "first-custodian assignment is NSS-wide only"
        assert "current_custodianship_pk" in assign

    def test_save_buttons_only_exist_inside_gated_forms(self):
        # form submit buttons live in x-show forms that only a manager can open
        for fn in ("apSubmitForm", "apSubmitMaintenance", "apSubmitStatutory", "apSubmitDocument",
                   "apSubmitAssign", "apSubmitTransfer", "apConfirmTerminalTransition"):
            assert f"{fn}()" in _panel()


# ── Endpoints ───────────────────────────────────────────────────────────


class TestEndpoints:

    def test_base_paths(self):
        assert 'const BASE = "/api/v1/assets-property";' in AP_JS
        assert 'prefix="/api/v1/assets-property"' in ROUTER
        assert '"/api/v1/foundation/master-data?category_code="' in AP_JS
        assert '"/api/v1/foundation/documents"' in AP_JS

    @pytest.mark.parametrize("fragment", [
        "${BASE}/${kind}?${params}",                       # GET list
        "${BASE}/${kind}/${pk}`",                          # GET detail / DELETE archive
        "${BASE}/${kind}`",                                # POST create
        "${BASE}/${kind}/${this.apSelectedPk}`",           # PATCH
        "${BASE}/${kind}/${pk}/transition",
        "${BASE}/${kind}/${pk}/custodianships",
        "${BASE}/${kind}/${pk}/custodianships/transfer",
        "${BASE}/maintenance-records/${f.editPk}",
        "${BASE}/${kind}/${pk}/maintenance-records",
        "${BASE}/statutory-records/${f.editPk}",
        "${BASE}/properties/${pk}/statutory-records",
        "${BASE}/${kind}/${pk}/documents",
        "${BASE}/${kind}/${pk}/documents/${d.link_pk}",
    ])
    def test_endpoint_templates_used(self, fragment):
        assert fragment in AP_JS

    def test_every_called_path_exists_in_the_router(self):
        for suffix in ("custodianships", "custodianships/transfer", "maintenance-records", "statutory-records",
                       "documents", "transition"):
            assert suffix in ROUTER
        assert '"/maintenance-records/{record_pk}"' in ROUTER
        assert '"/statutory-records/{record_pk}"' in ROUTER
        assert '"/properties/{entity_pk}/statutory-records"' in ROUTER

    def test_statutory_records_are_property_only(self):
        # there is no asset route; the markup section and loader are property-gated
        assert 'x-show="apIsProperty"' in _panel()
        assert 'if (kind === "properties") this.apLoadStatutory();' in AP_JS
        assert "/assets/${pk}/statutory" not in AP_JS

    def test_list_filters_use_the_router_query_names(self):
        for name in ('"q"', '"type_code"', '"status"', '"custodian_organization_pk"', "page_size"):
            assert name in AP_JS.split("async apLoadList()")[1].split("apApplyFilters()")[0]
        for param in ("q: str | None", "type_code: str | None", 'alias="status"', "custodian_organization_pk: UUID | None"):
            assert param in ROUTER

    def test_master_data_categories_match_the_contract(self):
        cats = set(re.findall(r'"([A-Z_]+)"', _js_block(AP_JS, "const CATEGORIES = [", "];")))
        assert cats == {
            "PROPERTY_TYPE", "ASSET_TYPE", "CUSTODIANSHIP_END_REASON", "STATUTORY_OBLIGATION_TYPE",
            "MAINTENANCE_TYPE", "ASSET_PROPERTY_DOCUMENT_RELATIONSHIP", "ACQUISITION_METHOD",
        }
        for cat in cats - {"CUSTODIANSHIP_END_REASON", "STATUTORY_OBLIGATION_TYPE", "MAINTENANCE_TYPE",
                           "ASSET_PROPERTY_DOCUMENT_RELATIONSHIP"}:
            assert f'"{cat}"' in ROUTER or cat in ROUTER

    def test_organization_pickers_use_the_scoped_endpoint(self):
        # reuses the generic corr* type-ahead (calls /organization/organizations/in-scope);
        # never the unscoped /selectable list and never a second copy of the search
        assert "organizations/in-scope" in ADMIN_JS
        assert "organizations/selectable" not in AP_JS
        assert "corrOnOrgQueryInput(apForm.custodian)" in _panel()
        assert "corrOnOrgQueryInput(apTransfer.newCustodian)" in _panel()
        assert "corrOnOrgQueryInput(apCustodianFilter)" in _panel()
        assert "NSSAuth.apiFetch(`/api/v1/organization" not in AP_JS

    def test_transfer_body_matches_the_schema(self):
        body = _js_block(AP_JS, "async apSubmitTransfer() {", "t.saving = true;")
        for key in ("new_custodian_organization_pk", "end_reason_code", "effective_from", "notes", "location_description"):
            assert key in body
        assert 'end_reason_code: t.end_reason_code || "TRANSFER"' in body
        assert "CUSTODIANSHIP_END_REASON" in _panel() and 'end_reason_code: "TRANSFER"' in AP_JS

    def test_create_body_matches_the_schemas(self):
        for key in ("property_name", "property_type_code", "holding_arrangement",
                    "asset_name", "asset_type_code", "condition"):
            assert f'"{key}"' in AP_JS
        for key in ("custodian_organization_pk", "custodian_effective_from", "acquired_at", "location_description"):
            assert key in AP_JS


# ── Lifecycle mirrors the router ────────────────────────────────────────


class TestLifecycle:

    def test_transition_tables_mirror_the_router(self):
        from api.routers.assets_property import _ARCHIVABLE_STATUSES, _ASSET, _PROPERTY

        js = _lifecycle_from_js()
        for kind, entity in (("properties", _PROPERTY), ("assets", _ASSET)):
            assert js[kind]["terminal"] == entity.terminal_status
            assert js[kind]["transitions"] == entity.transitions, kind
        archivable = set(re.findall(r'"(\w+)"', _js_block(NSS_CONFIG, "ASSET_PROPERTY_ARCHIVABLE_STATUSES: [", "]")))
        assert archivable == set(_ARCHIVABLE_STATUSES)

    def test_next_statuses_come_from_the_table_and_skip_activation_without_custodian(self):
        body = re.search(r"get apNextStatuses\(\) \{(.*?)\n            \},", AP_JS, re.DOTALL).group(1)
        assert "NSS.ASSET_PROPERTY_LIFECYCLE[this.apKind].transitions" in body
        assert 'from === "REGISTERED" && !this.apSelected.current_custodianship_pk' in body

    def test_archive_button_uses_the_archivable_set(self):
        body = re.search(r"get apCanArchive\(\) \{(.*?)\n            \},", AP_JS, re.DOTALL).group(1)
        assert "NSS.ASSET_PROPERTY_ARCHIVABLE_STATUSES" in body
        assert "canManageAssets && apCanArchive" in _panel()

    def test_terminal_move_asks_for_decision_reference_and_confirms(self):
        panel = _panel()
        assert "Governance decision reference" in panel
        start = AP_JS.index("async apStartTransition(to)")
        body = AP_JS[start:AP_JS.index("apCancelTransition()", start)]
        assert "ASSET_PROPERTY_LIFECYCLE[this.apKind].terminal" in body
        assert "NSSDialog.confirm" in body
        terminal = _js_block(AP_JS, "async apConfirmTerminalTransition() {", "async apSubmitTransition()")
        assert "NSSDialog.confirm" in terminal and 'confirmClass: "danger"' in terminal
        submit = _js_block(AP_JS, "async apSubmitTransition() {", "async apArchive()")
        assert "remarks: blank(t.remarks)" in submit

    def test_no_status_is_written_through_patch(self):
        patch_body = _js_block(AP_JS, "// PATCH semantics", "res = await NSSAuth.apiFetch(`${BASE}/${kind}/${this.apSelectedPk}`")
        assert "status" not in patch_body


# ── Labels and badges (no raw codes) ────────────────────────────────────


class TestLabelsAndBadges:

    def test_every_lifecycle_status_has_a_label_and_a_defined_badge(self):
        from api.routers.assets_property import _ASSET, _PROPERTY

        labels = _js_block(NSS_CONFIG, "ASSET_PROPERTY_STATUS_LABELS: {", "},")
        badges = _js_block(NSS_CONFIG, "ASSET_PROPERTY_STATUS_BADGE_MAP: {", "},")
        statuses = set(_PROPERTY.transitions) | set(_ASSET.transitions)
        for st in statuses:
            assert re.search(rf'\b{st}:\s+"[A-Z]', labels), f"no friendly label for {st}"
            assert re.search(rf"\b{st}:\s+\"badge-ap-", badges), f"no badge for {st}"
        for cls in set(re.findall(r'"(badge-ap-[a-z]+)"', badges + _js_block(NSS_CONFIG, "ASSET_CUSTODIANSHIP_BADGE_MAP: {", "},"))):
            assert re.search(rf"\.{cls}\s*\{{", BADGES_CSS), f"{cls} not defined in badges.css"

    def test_badge_classes_are_not_redefined_inline(self):
        for style in re.findall(r"<style.*?</style>", ADMIN_HTML, flags=re.DOTALL):
            assert "badge-ap-" not in style

    def test_markup_renders_status_through_the_label_helpers(self):
        panel = _panel()
        for line in panel.splitlines():
            if "x-text=" not in line:
                continue
            expr = line.split("x-text=", 1)[1]
            if re.search(r"\.status\b", expr):
                assert "NSS.asset" in expr or "apSelected && apSelected.status === " in line, line.strip()
            assert "value_code" not in expr and "_type_code" not in expr.replace("document_type_code", "") , line.strip()
        assert "NSS.assetPropertyStatusBadgeClass" in panel
        assert "NSS.assetCustodianshipBadgeClass" in panel

    def test_document_type_has_no_name_in_the_api_so_it_is_humanized(self):
        assert "NSS.codeLabel(d.document_type_code)" in _panel()
        assert "NSS.codeLabel(d.document_type_code)" in AP_JS

    def test_types_show_api_names_not_codes(self):
        panel = _panel()
        assert "r[apF.typeName]" in panel and "apSelected[apF.typeName]" in panel
        assert "m.maintenance_type_name" in panel and "r.obligation_type_name" in panel
        assert "d.relationship_type_name" in panel and "c.end_reason_name" in panel
        for option_loop in re.findall(r'<option :value="o\.value_code" x-text="([^"]+)"', panel):
            assert option_loop == "o.value_name"

    def test_transition_captions_cover_every_target_state(self):
        fn = _js_block(NSS_CONFIG, "assetPropertyTransitionLabel(from, to) {", "codeLabel(code)")
        for target in ("ACTIVE", "IN_CUSTODY", "UNDER_MAINTENANCE", "DISPOSED", "RETIRED"):
            assert target in fn
        assert "Return to service" in fn


# ── Behaviour guards ────────────────────────────────────────────────────


class TestStaleResponseGuards:

    def _methods(self) -> dict:
        parts = re.split(r"\n            (?=(?:async |get )?_?ap\w+\()", AP_JS)
        out = {}
        for part in parts[1:]:
            m = re.match(r"(?:async |get )?(_?ap\w+)\(", part)
            if m:
                out[m.group(1)] = part
        return out

    def test_every_record_bound_loader_checks_after_await(self):
        # catalogs / document registry are global, not tied to the open record
        global_loaders = {"apLoadCatalogs", "apLoadDocOptions"}
        methods = self._methods()
        assert len(methods) > 40
        for name, body in methods.items():
            if "await NSSAuth.apiFetch" not in body or name in global_loaders:
                continue
            assert ("_apStale(" in body or "seq !==" in body or "this.apKind !== kind" in body), (
                f"{name} awaits the network without a stale-response check")

    def test_selection_change_resets_dependent_state(self):
        reset = _js_block(AP_JS, "_apResetRecordState() {", "},")
        for state in ("apSub", "apTransition", "apTransfer", "apAssign", "apMaintForm", "apStatForm", "apDocForm"):
            assert state in reset
        open_body = _js_block(AP_JS, "async apOpen(pk) {", "apBackToList()")
        assert "_apResetRecordState()" in open_body and "++this._apDetailSeq" in open_body
        assert "this._apResetRecordState();" in _js_block(AP_JS, "apResetAll() {", "// Everything that hangs off")

    def test_tab_switch_resets_everything(self):
        enter = _js_block(AP_JS, "apEnterTab(kind) {", "},")
        assert "this.apResetAll()" in enter and "this.activeTab = kind" in enter
        assert "this._apListSeq++" in _js_block(AP_JS, "apResetAll() {", "// Everything that hangs off")

    def test_transfer_out_of_scope_is_handled(self):
        reload_fn = _js_block(AP_JS, "async _apReloadSelected(leftScopeNotice) {", "// ── Create / edit form")
        assert "res.status === 403" in reload_fn and "apBackToList()" in reload_fn
        assert "_apReloadSelected(" in _js_block(AP_JS, "async apSubmitTransfer() {", "// ── Maintenance records")

    def test_errors_use_the_shared_helper(self):
        assert AP_JS.count("NSS.errorMessage(data, res.status)") >= 8
        assert "NSS.extractError(res)" in AP_JS
        assert "alert(" not in re.sub(r"NSSDialog\.alert\(", "", AP_JS)

    def test_destructive_actions_confirm_with_nssdialog(self):
        for fn in ("async apArchive()", "async _apDeleteSub(", "async apDetachDocument(", "async apSubmitTransfer("):
            start = AP_JS.index(fn)
            nxt = AP_JS.find("\n            async ", start + 10)
            assert "NSSDialog.confirm" in AP_JS[start:nxt], fn


class TestMarkupJsParity:

    def test_every_identifier_used_by_the_panel_is_defined_in_the_mixin(self):
        used = set(re.findall(r"\bap[A-Z]\w*", _panel()))
        defined = set(re.findall(r"\bap[A-Z]\w*", AP_JS))
        assert used and not (used - defined), sorted(used - defined)

    def test_no_state_name_collides_with_the_host_component(self):
        # install() never overwrites a host property, so a collision would silently
        # shadow the mixin
        host = ADMIN_JS
        for name in ("apItems", "apForm", "apSelected", "apNotice", "canViewAssets", "canManageAssets",
                     "apKind", "apEnterTab"):
            assert not re.search(rf"^\s+(?:get\s+)?{name}\b\s*[:(]", host, re.MULTILINE), name

    def test_datepicker_model_paths_resolve_to_mixin_state(self):
        paths = re.findall(r"nssDatePicker\('(ap\w+)\.(\w+)'", _panel())
        assert len(paths) == 5
        state = {
            "apForm": ("acquired_at", "custodian_effective_from"),
            "apAssign": ("effective_from",),
            "apTransfer": ("effective_from",),
            "apMaintForm": ("performed_at",),
        }
        for obj, key in paths:
            assert key in state[obj], (obj, key)
            assert re.search(rf"\b{key}: \"\"", AP_JS)

    def test_property_only_fields_are_switched_not_duplicated(self):
        panel = _panel()
        assert panel.count("Maintenance records</h4>") == 1
        assert panel.count("Statutory records</h4>") == 1
        assert "apF.extraLabel" in panel
        assert "holding_arrangement" in AP_JS and "condition" in AP_JS
        assert "Holding arrangement" in AP_JS and "Condition" in AP_JS

    def test_no_duplicate_org_search_implementation(self):
        assert not re.search(r"apiFetch\(\s*[`\"'][^`\"']*/organization", AP_JS)
        assert "corrSelectOrg" in AP_JS and "corrOnOrgQueryInput" in _panel()

    def test_document_picker_uses_the_registry_and_excludes_attached(self):
        panel = _panel()
        assert "apDocChoices" in panel and "apDocOptionLabel(d)" in panel
        choices = re.search(r"get apDocChoices\(\) \{(.*?)\n            \},", AP_JS, re.DOTALL).group(1)
        assert "document_master_pk" in choices and "apSub.documents.items" in choices
        assert "document_master_pk: f.document_master_pk" in AP_JS
        assert "relationship_type_code: f.relationship_type_code || null" in AP_JS


class TestCustodianPickersArePhysicalOnly:
    """Owner rule 2026-11-02 (GDR-010 §2C): custodian pickers offer only physical organizations."""

    def test_shared_constant_is_built_from_the_sakha_like_list(self):
        m = re.search(r"NSS\.ASSET_CUSTODIAN_ORG_TYPES\s*=\s*\[([^\]]*)\]", NSS_CONFIG)
        assert m
        assert m.group(1).split(",")[0].strip() == "...NSS.SAKHA_LIKE_ORG_TYPES"
        assert re.findall(r'"([A-Z_]+)"', m.group(1)) == ["PATHA_CHAKRA", "KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA"]

    def test_no_second_literal_list_in_the_module_screen(self):
        for code in ("PATHA_CHAKRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA", "ANCHALIKA_SANGHA"):
            assert code not in AP_JS

    def test_one_picker_factory_carries_the_type_codes(self):
        assert re.search(r"const custodianPicker = \(\) => \(\{ \.\.\.emptyPicker\(\), typeCodes: NSS\.ASSET_CUSTODIAN_ORG_TYPES \}\);", AP_JS)

    def test_every_custodian_picker_uses_the_factory(self):
        # new record form, transfer, assign, and the list filter (initial state + both resets)
        assert "custodian: custodianPicker()" in AP_JS and AP_JS.count("custodian: custodianPicker()") >= 2
        assert "newCustodian: custodianPicker()" in AP_JS
        assert "apCustodianFilter: custodianPicker()" in AP_JS
        assert AP_JS.count("this.apCustodianFilter = custodianPicker();") >= 2
        # no custodian picker is still built from the unrestricted factory
        assert not re.search(r"(?:custodian|newCustodian|apCustodianFilter)\s*[:=]\s*emptyPicker\(\)", AP_JS)

    def test_shared_search_forwards_type_codes_as_repeated_type_code_only_when_set(self):
        block = _js_block(ADMIN_JS, "async corrSearchOrg(picker) {", "corrSelectOrg(picker, org) {")
        assert 'for (const t of picker.typeCodes || []) params.append("type_code", t);' in block
        assert "/api/v1/organization/organizations/in-scope" in block
        # correspondence pickers never set typeCodes, so their behaviour is unchanged
        assert "picker.typeCodes" not in ADMIN_JS.replace(block, "")

    def test_hint_is_shown_under_all_four_custodian_pickers(self):
        panel = _panel()
        assert panel.count('x-text="apCustodianHint"') == 4
        assert ("Property and assets are held by physical organizations: Sakha, Patha Chakra, Kendra, "
                "Nilachala Kutira, Smruti Mandira.") in AP_JS

    def test_include_sub_organizations_checkbox_drives_the_query_param(self):
        panel = _panel()
        assert 'x-model="apIncludeSub"' in panel and "Include sub-organizations" in panel
        assert 'x-show="apCustodianFilter.selected"' in panel[panel.index('x-model="apIncludeSub"') - 300:panel.index('x-model="apIncludeSub"')]
        assert 'if (this.apIncludeSub) params.set("include_sub_organizations", "true");' in AP_JS
        # only inside the custodian-filter branch
        load = _js_block(AP_JS, "async apLoadList() {", "apApplyFilters() {")
        assert load.index("if (this.apCustodianFilter.selected)") < load.index("include_sub_organizations")
        assert "apIncludeSub = false" in AP_JS

    def test_server_message_is_surfaced_through_the_shared_error_helper(self):
        # create / assign / transfer show the 422 text verbatim
        assert AP_JS.count("NSS.errorMessage(data, res.status)") >= 3
        for ctx in ("f.error = NSS.errorMessage", "a.error = NSS.errorMessage", "t.error = NSS.errorMessage"):
            assert ctx in AP_JS

    def test_no_inline_event_handlers_were_added(self):
        assert not re.search(r"\son(?:click|change|input)=", _panel())


class TestBelongsToUi:
    """GDR-010 item 4: optional 'belongs to' organization (any type), informational only."""

    HINT = ("Use this when an asset belongs to one organization (for example the Mahila Sangha) but is held under "
            "the supervision of a physical organization (for example the Kendra Sangha).")

    def test_hint_text_is_the_decided_wording(self):
        assert self.HINT in AP_JS
        assert 'x-text="apBelongsToHint"' in _panel()

    def test_pickers_are_unrestricted_not_custodian_pickers(self):
        assert "belongsTo: emptyPicker()" in AP_JS
        assert "apBelongsFilter: emptyPicker()" in AP_JS
        assert not re.search(r"belongs\w*\s*[:=]\s*custodianPicker\(\)", AP_JS, re.IGNORECASE)
        panel = _panel()
        assert "corrOnOrgQueryInput(apForm.belongsTo)" in panel
        assert "corrOnOrgQueryInput(apBelongsFilter)" in panel
        assert "Belongs to (if different from the holder)" in panel

    def test_create_and_patch_bodies_carry_the_field(self):
        assert "body.belongs_to_organization_pk = f.belongsTo.selected.organization_pk" in AP_JS
        # PATCH: null clears; compared against the loaded record like every other field
        assert "belongs_to_organization_pk: f.belongsTo.selected ? f.belongsTo.selected.organization_pk : null" in AP_JS
        assert "belongsTo: r.belongs_to_organization_pk" in AP_JS

    def test_list_filter_uses_the_router_query_name_and_resets(self):
        load = _js_block(AP_JS, "async apLoadList() {", "apApplyFilters() {")
        assert 'params.set("belongs_to_organization_pk", this.apBelongsFilter.selected.organization_pk)' in load
        assert "belongs_to_organization_pk: UUID | None" in ROUTER
        assert AP_JS.count("this.apBelongsFilter = emptyPicker();") >= 3     # reset-all, clear-filters, clear-picker

    def test_shown_only_when_set(self):
        panel = _panel()
        assert 'x-show="r.belongs_to_organization_name"' in panel
        assert 'x-show="apSelected && apSelected.belongs_to_organization_name"' in panel

    def test_response_and_request_fields_exist_in_the_schemas(self):
        schemas = (REPO_ROOT / "api" / "schemas" / "assets_property.py").read_text(encoding="utf-8")
        assert schemas.count("belongs_to_organization_pk: UUID | None") >= 6   # 2 create + 2 update + 2 response
        assert schemas.count("belongs_to_organization_name: str | None") == 2


class TestTerminalCustodyUi:
    """GDR-010 §2F: a Disposed / Retired record keeps showing its LAST custodian, tagged with the status badge."""

    def test_list_row_shows_the_status_badge_next_to_the_last_custodian(self):
        panel = _panel()
        row = panel[panel.index("r.current_custodian_organization_name"):]
        row = row[:row.index("</td>")]
        assert 'x-show="r.custodian_is_last"' in row
        assert "NSS.assetPropertyStatusBadgeClass(r.status)" in row and "NSS.assetPropertyStatusLabel(r.status)" in row

    def test_detail_header_labels_it_last_custodian_with_the_badge_and_end_date(self):
        panel = _panel()
        assert "apSelected.custodian_is_last ? 'Last custodian' : 'Custodian'" in panel
        assert 'x-show="apSelected && apSelected.custodian_is_last"' in panel
        assert "NSS.assetPropertyStatusBadgeClass(apSelected && apSelected.status)" in panel
        assert "apSelected.custodian_ended_at" in panel and "Custody ended" in panel

    def test_terminal_confirm_text_says_custody_is_ended_and_the_last_custodian_is_kept(self):
        terminal = _js_block(AP_JS, "async apConfirmTerminalTransition() {", "async apSubmitTransition()")
        assert "Its current custodianship will be ended today and kept in the history" in terminal
        assert "stays on the record as the last custodian" in terminal

    def test_no_new_state_makes_a_terminal_record_look_custodian_less(self):
        # assign / transfer stay gated on a live custodianship and a non-terminal record
        assert "!this.apSelected.current_custodianship_pk && !this.apIsTerminal" in AP_JS
        assert "!!this.apSelected.current_custodianship_pk && !this.apIsTerminal" in AP_JS

    def test_response_fields_exist_in_the_schemas(self):
        schemas = (REPO_ROOT / "api" / "schemas" / "assets_property.py").read_text(encoding="utf-8")
        assert schemas.count("custodian_is_last: bool") == 2
        assert schemas.count("custodian_ended_at: date | None") == 2

    def test_no_new_tailwind_classes_or_inline_handlers(self):
        panel = _panel()
        assert not re.search(r"\bon(click|change|input|submit)=", panel)


class TestAcquisitionMethodUi:
    """GDR-010 §2E: optional ACQUISITION_METHOD master-data select, informational only."""

    def test_form_select_uses_the_master_data_options(self):
        panel = _panel()
        assert 'x-model="apForm.acquisition_method_code"' in panel
        assert "apOptions('ACQUISITION_METHOD')" in panel
        assert '"ACQUISITION_METHOD"' in _js_block(AP_JS, "const CATEGORIES = [", "];")

    def test_create_and_patch_bodies_carry_the_field(self):
        assert "body.acquisition_method_code = f.acquisition_method_code" in AP_JS
        assert "acquisition_method_code: f.acquisition_method_code || null" in AP_JS        # PATCH: null clears
        assert "acquisition_method_code: r.acquisition_method_code || \"\"" in AP_JS         # edit form prefill

    def test_list_filter_uses_the_router_query_name_and_resets(self):
        load = _js_block(AP_JS, "async apLoadList() {", "apApplyFilters() {")
        assert 'params.set("acquisition_method_code", this.apAcquisitionFilter)' in load
        assert 'x-model="apAcquisitionFilter"' in _panel()
        assert "acquisition_method_code: str | None" in ROUTER
        assert AP_JS.count('this.apAcquisitionFilter = "";') >= 2                            # reset-all + clear-filters

    def test_detail_shows_the_method_name_not_the_code(self):
        assert "apSelected.acquisition_method_name" in _panel()

    def test_response_and_request_fields_exist_in_the_schemas(self):
        schemas = (REPO_ROOT / "api" / "schemas" / "assets_property.py").read_text(encoding="utf-8")
        assert schemas.count("acquisition_method_code: str | None") == 6    # 2 create + 2 update + 2 response
        assert schemas.count("acquisition_method_name: str | None") == 2
