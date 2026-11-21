"""
A refresh keeps the tab (owner 2026-11-21: "all finance tabs refreshed take you to Finance Overview ... when refreshed all tabs should display the same tab").

Admin console: the open tab is written into the address (#tab) on every switch and read back on load. The write used to be registered at the END of
admin.js init(), AFTER the early return that finance-only / governance-only / assets-only / audit-only admins take, so for them the hash was never
written and every refresh fell back to their landing tab. It is now registered before that return, a restricted admin's refresh stays on the tab in
the address when it belongs to an area they can view, and every tab that loads its own data has a loader for the refresh path.

Member dashboard: the tab is kept in sessionStorage; every tab _refreshTab() fills must also be filled on a direct load.
DB-free: source parsing plus a node-run of the area / permission rule.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FE = Path(__file__).resolve().parents[2] / "frontend"
ADMIN_JS = (FE / "assets/js/admin.js").read_text(encoding="utf-8")
DASH_JS = (FE / "assets/js/dashboard.js").read_text(encoding="utf-8")
node = shutil.which("node")

# Tabs that need no loader of their own on a refresh: the default list (loaded by init()), the two detail views whose hashes carry a pk and are handled
# separately, and plain forms.
NO_LOADER = {"users", "detail", "orgDashboard", "create", "createSS", "password"}


def _labels() -> set[str]:
    block = re.search(r"const ADMIN_TAB_LABELS = \{(.*?)\n\};", ADMIN_JS, re.S).group(1)
    return set(re.findall(r"\b([A-Za-z]+):\s*\"", block))


def _loader_keys() -> set[str]:
    block = ADMIN_JS.split("_tabLoaders() {", 1)[1].split("_tabArea(tab) {", 1)[0]
    return set(re.findall(r"^\s{20}([A-Za-z]+):\s*\(\)", block, re.M))


def test_every_admin_tab_that_loads_data_has_a_refresh_loader():
    missing = sorted(_labels() - _loader_keys() - NO_LOADER)
    assert not missing, f"a refresh on these tabs would open them empty: {missing}"
    assert "changeRequests" in _loader_keys()                 # was the one that was missing


def test_the_hash_is_written_before_a_restricted_admin_can_return_from_init():
    init = ADMIN_JS.split("        async init() {", 1)[1]
    watcher = init.index('history.replaceState(null, "", `#${tab}`)')
    restricted_return = init.index("if (!this.hasGeneralAdminAccess) {")
    assert watcher < restricted_return
    assert ADMIN_JS.count('history.replaceState(null, "", `#${tab}`)') == 1          # one writer, not a second copy at the end


def test_a_restricted_admins_refresh_honours_the_tab_in_the_address():
    init = ADMIN_JS.split("        async init() {", 1)[1]
    branch = init.split("if (!this.hasGeneralAdminAccess) {", 1)[1].split("return;", 1)[0]
    assert "this._restrictedTabLoader(govHash)" in branch and "this.activeTab = govHash;" in branch
    assert init.index("this._restrictedTabLoader(govHash)") < init.index("const financeLanding")      # the old landing logic stays as the fallback, after it


@pytest.mark.skipif(node is None, reason="node not available")
def test_the_area_and_permission_rule_runs_as_intended():
    start = ADMIN_JS.index("        _tabArea(tab) {")
    end = ADMIN_JS.index("        async init() {")
    code = f"""
        const host = {{ {ADMIN_JS[start:end]} }};
        host._tabLoaders = () => ({{ finStructure: () => "fin", govBodies: () => "gov", properties: () => "ap", auditEvents: () => "au",
                                     correspondence: () => "co", attPujas: () => "att", users: () => "u" }});
        const run = (flags, tab) => {{ const h = Object.assign(Object.create(host), {{ canViewFinance: false, canViewAssets: false, canViewAudit: false,
            canViewCorrespondence: false, canViewAttendance: false, canViewGovernance: false }}, flags); const l = h._restrictedTabLoader(tab); return l ? l() : null; }};
        console.log(JSON.stringify({{
            area: ["finFunds", "properties", "assets", "auditEvents", "liveMarkers", "correspondence", "attReviews", "govElections", "users", "personDir"].map((t) => host._tabArea(t)),
            fin_ok: run({{ canViewFinance: true }}, "finStructure"), fin_denied: run({{}}, "finStructure"),
            gov_ok: run({{ canViewGovernance: true }}, "govBodies"), a_finance_user_cannot_open_governance: run({{ canViewFinance: true }}, "govBodies"),
            general_tab_never: run({{ canViewFinance: true, canViewGovernance: true }}, "users"),
        }}));
    """
    out = subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["area"] == ["finance", "assets", "assets", "audit", "audit", "correspondence", "attendance", "governance", None, None]
    assert got["fin_ok"] == "fin" and got["fin_denied"] is None
    assert got["gov_ok"] == "gov" and got["a_finance_user_cannot_open_governance"] is None
    assert got["general_tab_never"] is None                   # a general-admin tab is never opened for a restricted admin from the address


def test_the_member_dashboard_fills_every_refreshed_tab_on_a_direct_load():
    init = DASH_JS.split("        async init() {", 1)[1].split("        _refreshTab(tab) {", 1)[0]
    assert "sessionStorage.getItem('nss_dashboard_tab')" in DASH_JS
    assert 'if (this.tab === "membership") {' in init and "this._loadMyChangeRequests();" in init
    assert 'this.tab === "sendApplication"' in init and 'this.tab.startsWith("admin_")' in init and "this._refreshTab(this.tab);" in init
