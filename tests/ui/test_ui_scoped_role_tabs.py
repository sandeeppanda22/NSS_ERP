"""
NSS ERP — Source-level UI tests for the two NULL-organization admin roles
(owner decisions 2026-10-30): NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN and
NSS_ERP_ADVISORY_BOARD_ADMIN.

Pure source parsing (no browser interaction), same style as
TestSuperAdminTabs in test_ui_dashboard.py. Before this change neither role had
an ADMIN_TAB_MAP entry, so such users got no admin tab; and the /admin page
guard turned the Advisory Board admin (no ADMIN_* / MEMBERSHIP_APPROVE) away.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
_DASHBOARD_JS = (_FRONTEND / "assets" / "js" / "dashboard.js").read_text(encoding="utf-8")
_ADMIN_JS = (_FRONTEND / "assets" / "js" / "admin.js").read_text(encoding="utf-8")
_ADMIN_HTML = (_FRONTEND / "admin.html").read_text(encoding="utf-8")
_DASHBOARD_HTML = (_FRONTEND / "dashboard.html").read_text(encoding="utf-8")

MAHILA = "NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN"
ADVISORY = "NSS_ERP_ADVISORY_BOARD_ADMIN"


def _tab_map() -> str:
    return _DASHBOARD_JS.split("const ADMIN_TAB_MAP = {")[1].split("\n};")[0]


class TestDashboardTabs:

    def test_both_roles_have_a_tab_definition(self):
        tab_map = _tab_map()
        assert f"{MAHILA}: {{" in tab_map
        assert f"{ADVISORY}: {{" in tab_map
        assert "Mahila Sangha Management" in tab_map
        assert "Advisory Board Management" in tab_map

    def test_neither_role_joins_the_super_admin_tab_set(self):
        block = _DASHBOARD_JS.split("const SUPER_ADMIN_TAB_ORDER = [")[1].split("]")[0]
        assert MAHILA not in block and ADVISORY not in block

    def test_mahila_is_an_org_level_role_with_stats_and_dashboard_entry(self):
        org_roles = _DASHBOARD_JS.split("const ORG_LEVEL_ADMIN_ROLES = new Set([")[1].split("]);")[0]
        assert MAHILA in org_roles and ADVISORY not in org_roles
        stats = _DASHBOARD_JS.split("_buildAdminStats() {")[1].split("\n        },")[0]
        assert f"{MAHILA}:" in stats
        assert f"{ADVISORY}:" not in stats, "the Advisory Board tab has no stats source (no stats permission)"
        assert "mahilaScopeOrgs" in _DASHBOARD_JS
        assert 'type_code=MAHILA_SANGHA' in _DASHBOARD_JS
        assert "MAHILA_SANGHA" in _DASHBOARD_JS.split("const DASHBOARD_LEVELS = [")[1].split("];")[0]

    def test_stat_grid_hidden_when_a_role_has_no_stats(self):
        assert 'x-show="adminStats[at.roleCode]"' in _DASHBOARD_HTML


class TestAdminPage:

    def test_entry_guard_admits_a_governance_only_admin(self):
        init = _ADMIN_JS.split("async init() {")[1].split("// Load reference data in parallel")[0]
        assert "hasGeneralAdminAccess" in init and "canViewGovernance" in init
        assert 'window.location.href = "/dashboard"' in init

    def test_governance_only_admin_can_open_its_correspondence_register(self):
        init = _ADMIN_JS.split("async init() {")[1]
        branch = init.split("if (!this.hasGeneralAdminAccess) {")[1].split("// Load reference data in parallel")[0]
        assert "canViewCorrespondence" in branch and "fetchOrganizations" in branch
        assert '"correspondence"' in branch and "loadCorrespondence" in branch

    def test_advisory_board_only_admin_is_decided_from_scope_rows(self):
        getter = _ADMIN_JS.split("get isAdvisoryBoardOnlyAdmin() {")[1].split("\n        },")[0]
        assert "admin_scope_org_pks" not in getter, "the AB scope now reaches its own organization"
        assert 's.scope_level === "ADVISORY_BOARD"' in getter

    def test_governance_only_admin_skips_the_general_loaders(self):
        init = _ADMIN_JS.split("async init() {")[1]
        governance_branch = init.split("if (!this.hasGeneralAdminAccess) {")[1].split("return;")[0]
        assert "govAssignments" in governance_branch
        assert "fetchUsers" not in governance_branch

    def test_general_nav_groups_hidden_without_general_access(self):
        assert '<template x-if="hasGeneralAdminAccess">' in _ADMIN_HTML
        assert "canViewAttendance && hasSakhaReach" in _ADMIN_HTML
        assert 'x-show="!isAdvisoryBoardOnlyAdmin"' in _ADMIN_HTML          # Elections nav item
        assert 'x-show="canManageGovBodies"' in _ADMIN_HTML                 # body create / edit

    def test_scope_set_uses_the_server_resolved_reach(self):
        scope_set = _ADMIN_JS.split("get scopeOrgPkSet() {")[1].split("\n        },")[0]
        assert "admin_scope_org_pks" in scope_set

    def test_org_edit_is_scope_based_not_permission_based(self):
        can_edit = _ADMIN_JS.split("canEditOrg(org) {")[1].split("\n        },")[0]
        assert "includes(\"ORGANIZATION_MANAGE\")" not in can_edit
        assert "scopeOrgPkSet" in can_edit

    def test_advisory_board_admin_sees_only_the_advisory_board_body(self):
        bodies = _ADMIN_JS.split("get govAssignableBodies() {")[1].split("canEditOrg")[0]
        assert "isAdvisoryBoardOnlyAdmin" in bodies
        assert 'body_type_code === "ADVISORY_BOARD"' in bodies

    def test_register_resolution_no_longer_sends_null_org_scopes_to_kendra(self):
        resolve = _ADMIN_JS.split("corrResolveDefaultOrg() {")[1].split("// Group the candidates")[0]
        assert 's.scope_level === "NSS-WIDE" || s.scope_level === "KENDRA"' in resolve
        assert "KENDRA_MAHILA_SANGHA" in resolve
