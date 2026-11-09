"""
UI tests for the live-refresh feed (frontend/assets/js/live-refresh.js).

Owner decision 2026-11-03: data refreshes automatically, without reloading a tab
or the page. One poll per open page of GET /api/v1/live/changes; a per-page
table -> tab map says what to re-run.

  1. SOURCE-LEVEL (no browser, no server): the policy constants, the single
     poller (no setInterval), CSP-safe banner, script wiring in admin.html /
     dashboard.html, the removed redundant Refresh buttons, the kept ones, the
     attendance poller left alone.
  2. LOGIC (needs `node` only, no browser): the two pure functions
     (pollDelay, changedTabs) are executed under node with a stub `window`.

Written without a browser: nothing here drives a page; node logic tests ran
where node was available.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "frontend" / "assets" / "js"
LIVE_JS = JS / "live-refresh.js"
node = shutil.which("node")


@pytest.fixture(scope="module")
def live_js() -> str:
    return LIVE_JS.read_text()


@pytest.fixture(scope="module")
def admin_html() -> str:
    return (ROOT / "frontend" / "admin.html").read_text()


@pytest.fixture(scope="module")
def dashboard_html() -> str:
    return (ROOT / "frontend" / "dashboard.html").read_text()


def _node(expr: str):
    code = f"global.window = {{}}; require({json.dumps(str(LIVE_JS))}); const L = window.NSSLiveRefresh;" \
           f"console.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ── Source level ───────────────────────────────────────────────────────────

def test_policy_numbers_live_only_in_the_live_feed_object(live_js):
    block = re.search(r"const LIVE_FEED = Object\.freeze\(\{(.*?)\n    \}\);", live_js, re.DOTALL).group(1)
    assert "ACTIVE_MS: 5000" in block and "IDLE_MS: 15000" in block and "IDLE_AFTER_MS: 60000" in block
    assert "[4000, 8000, 16000, 30000]" in block
    assert 'ENDPOINT: "/api/v1/live/changes"' in block
    assert "visibilitychange" in live_js and "Retry-After" in live_js


def test_one_poller_no_setinterval_and_no_inline_handlers(live_js):
    assert "setInterval" not in live_js
    assert "onclick" not in live_js.lower() and "innerHTML" not in live_js
    assert 'addEventListener("click"' in live_js  # banner button wired without inline handlers


def test_banner_text_and_xignore(live_js):
    assert "This view has new updates" in live_js and "x-ignore" in live_js


def test_scripts_are_loaded_before_the_page_scripts(admin_html, dashboard_html):
    assert admin_html.index("live-refresh.js") < admin_html.index("/assets/js/admin.js")
    assert dashboard_html.index("live-refresh.js") < dashboard_html.index("/assets/js/dashboard.js")


@pytest.mark.parametrize("script,tab_var", [("admin.js", "activeTab"), ("dashboard.js", "tab")])
def test_hosts_install_the_mixin_and_start_it_after_auth(script, tab_var):
    src = (JS / script).read_text()
    assert "NSSLiveRefresh.install(" in src and "LIVE_REFRESH_CONFIG" in src
    assert "this.liveStart();" in src and f'$watch("{tab_var}"' in src and "liveTabOpened" in src
    assert f"activeTab: (h) => h.{tab_var}" in src


def test_attendance_poller_is_untouched_and_not_on_the_feed():
    reg = (JS / "attendance-register.js").read_text()
    for needle in ("ACTIVE_MS: 2000", "IDLE_MS: 10000", "_attPollDelay", "_attRegisterShown", "If-None-Match"):
        assert needle in reg
    assert "live-refresh" not in reg.lower()
    for script in ("admin.js", "dashboard.js"):
        mapping = re.search(r"// LIVE_TABLE_TABS:begin(.*?)// LIVE_TABLE_TABS:end", (JS / script).read_text(), re.DOTALL).group(1)
        assert not re.search(r"attPujas|attReviews|attWatchList|attendanceRegister", mapping)


def test_redundant_refresh_buttons_were_removed_and_the_tally_one_kept(admin_html):
    assert 'loadClaims()">Refresh' not in admin_html
    assert 'loadChangeRequests()">Refresh' not in admin_html
    # Ballot tables are withheld from the feed, so the tally keeps its manual refresh.
    assert 'loadGovTally()">Refresh' in admin_html


def test_loaders_accept_silent_without_a_second_code_path():
    admin = (JS / "admin.js").read_text()
    for loader in ("loadClaims", "loadChangeRequests", "loadCorrespondence", "loadGovBodies",
                   "loadGovAssignments", "loadGovElections"):
        assert re.search(rf"async {loader}\(opts = \{{\}}\)", admin), loader
    assert "async apLoadList(opts = {})" in (JS / "assets-property.js").read_text()
    # The reload hooks call the SAME loaders the tab-open handlers call.
    assert "reload: (h) => Promise.all([h.loadClaims({ silent: true }), h.reloadSelectedClaim()])" in admin
    # The open claim is re-read through the SAME request viewClaim uses, never a second copy,
    # and not while an edit is open.
    assert admin.count("/api/v1/admin/claims/${claimPk}`") == 1
    assert "async reloadSelectedClaim()" in admin
    assert re.search(r"async reloadSelectedClaim\(\) \{\s+if \(!this\.selectedClaim \|\| this\.claimEditing\) return;", admin)


def test_org_dashboard_registers_as_a_live_target():
    src = (JS / "org-dashboard.js").read_text()
    assert 'registerTarget("orgDashboard", this)' in src and 'unregisterTarget("orgDashboard", this)' in src
    assert "liveReload()" in src and "liveBusy()" in src
    assert "_loadAttendanceCard" not in src[src.index("async liveReload()"):src.index("async init(orgPk)")]


# ── Pure logic under node ──────────────────────────────────────────────────

@pytest.mark.skipif(node is None, reason="node not installed")
def test_poll_delay():
    out = _node("""{
      a: L.pollDelay(0, 0), under: L.pollDelay(0, 59999), idle: L.pollDelay(0, 60000),
      back: [1,2,3,4,5,9].map(n => L.pollDelay(n, 0)),
      ra: L.pollDelay(1, 0, 20000), shortRa: L.pollDelay(2, 0, 1000),
      feed: { a: L.LIVE_FEED.ACTIVE_MS, i: L.LIVE_FEED.IDLE_MS, after: L.LIVE_FEED.IDLE_AFTER_MS }
    }""")
    assert (out["a"], out["under"], out["idle"]) == (5000, 5000, 15000)
    assert out["back"] == [4000, 8000, 16000, 30000, 30000, 30000]
    assert (out["ra"], out["shortRa"]) == (20000, 8000)
    assert out["feed"] == {"a": 5000, "i": 15000, "after": 60000}


@pytest.mark.skipif(node is None, reason="node not installed")
def test_changed_tabs_compares_change_seq_per_table_after_a_baseline():
    out = _node("""(() => {
      const map = { registration_claim: ["claims", "claimsBadge"], election: ["govElections"] };
      const ch = (table, seq) => ({ table_name: table, change_seq: seq });
      // first reply (no baseline yet): records the numbers, affects no tab
      const base = L.changedTabs([ch("registration_claim", 10), ch("election", 4)], null, map);
      // same numbers again: nothing
      const same = L.changedTabs([ch("registration_claim", 10), ch("election", 4)], base.seen, map);
      // one table moved: only its tabs; the other stays quiet; seen advances
      const moved = L.changedTabs([ch("registration_claim", 12), ch("election", 4)], base.seen, map);
      const after = L.changedTabs([ch("registration_claim", 12), ch("election", 4)], moved.seen, map);
      // only the table whose number differs is reported (per-table compare, no global cursor)
      const lower = L.changedTabs([ch("registration_claim", 10), ch("election", 5)], base.seen, map);
      // an unmapped table and a bad number are ignored; a table first seen after the baseline counts
      const odd = L.changedTabs([ch("unmapped", 99), ch("election", "nonsense"), ch("registration_claim", 11)],
                                { election: 4 }, map);
      return { base: base.tabs, baseSeen: base.seen, same: same.tabs, moved: moved.tabs, after: after.tabs,
               lower: lower.tabs, odd: odd.tabs };
    })()""")
    assert out == {
        "base": [], "baseSeen": {"registration_claim": 10, "election": 4}, "same": [],
        "moved": ["claims", "claimsBadge"], "after": [],
        "lower": ["govElections"],
        "odd": ["claims", "claimsBadge"],
    }


# ── Batch 2 (Users, Organizations, directories, reference data, geography, settings, member dashboard) ──

BATCH2_ADMIN_TABS = ("users", "detail", "organizations", "orgHierarchy", "personDir", "memberDir", "credentials",
                     "credentialsBadge", "refData", "geography", "geoApprovals", "geoApprovalsBadge", "sysSettings")
BATCH2_DASHBOARD_TABS = ("personal", "membership", "documents", "family", "governance", "adminStats")


def _map(script):
    src = (JS / script).read_text()
    block = re.search(r"// LIVE_TABLE_TABS:begin\n(.*?)// LIVE_TABLE_TABS:end", src, re.DOTALL).group(1)
    return {m.group(1): re.findall(r'"([A-Za-z]+)"', m.group(2))
            for m in re.finditer(r"^\s+([a-z_]+): \[(.*?)\],?\s*$", block, re.MULTILINE)}


def _config_tabs(script):
    src = (JS / script).read_text()
    cfg = re.search(r"const LIVE_REFRESH_CONFIG = \{(.*?)\n\};", src, re.DOTALL).group(1)
    return cfg[cfg.index("tabs: {"):]


@pytest.mark.parametrize("tab", BATCH2_ADMIN_TABS)
def test_admin_batch2_tab_is_mapped_and_has_a_reload_hook(tab):
    assert any(tab in tabs for tabs in _map("admin.js").values()), tab
    assert re.search(rf"^        {tab}: ", _config_tabs("admin.js"), re.MULTILINE), tab


@pytest.mark.parametrize("tab", BATCH2_DASHBOARD_TABS)
def test_dashboard_batch2_tab_is_mapped_and_has_a_reload_hook(tab):
    assert any(tab in tabs for tabs in _map("dashboard.js").values()), tab
    assert re.search(rf"^        {tab}: ", _config_tabs("dashboard.js"), re.MULTILINE), tab


@pytest.mark.parametrize("tab", [t for t in BATCH2_ADMIN_TABS if t not in ("orgHierarchy", "personDir", "credentialsBadge", "geoApprovalsBadge")])
def test_admin_batch2_interactive_tabs_declare_busy_hooks(tab):
    entry = re.search(rf"^        {tab}: \{{(.*?)^        \}},", _config_tabs("admin.js"), re.MULTILINE | re.DOTALL)
    assert entry and "busy:" in entry.group(1), tab


def test_batch2_loaders_accept_silent_with_stale_response_guards():
    admin = (JS / "admin.js").read_text()
    for loader, seq in (("fetchUsers", "_usersSeq"), ("loadOrganizations", "_orgsSeq"),
                        ("fetchPersonDirectory", "_pdSeq"), ("fetchMemberDirectory", "_mdSeq"),
                        ("loadGeoEntries", "_geoEntriesSeq")):
        assert re.search(rf"async {loader}\(opts = \{{\}}\)", admin), loader
        assert f"const seq = ++this.{seq};" in admin, loader
    assert "async loadCredentials(page = 1, opts = {})" in admin and "_credsSeq" in admin
    for loader in ("loadOrgHierarchy", "loadReferenceData", "loadMasterValues", "loadDocuments",
                   "reloadSettings", "loadFestivalCalendar"):
        assert re.search(rf"async {loader}\(opts = \{{\}}\)", admin), loader
    assert "async _reloadUserDetail()" in admin and "_userDetailSeq" in admin
    assert "async geoLiveReload()" in admin
    dash = (JS / "dashboard.js").read_text()
    for loader in ("_fetchPersonalDetail", "_fetchFamilyDetail", "_loadGraph", "_loadGovernanceBodies",
                   "_loadOpenElectionsForVoting", "_loadMyChangeRequests"):
        assert re.search(rf"async {loader}\(opts = \{{\}}\)", dash), loader
    assert "_adminStatsSeq" in dash


def test_silent_user_detail_reload_does_not_reset_the_profile_editor():
    admin = (JS / "admin.js").read_text()
    body = admin[admin.index("async _reloadUserDetail()"):admin.index("_usersLiveBusy()")]
    assert "loadProfileEdit" not in body and "selectedUser = null" not in body


def test_every_whitelisted_table_is_used_by_some_page_map():
    from api.routers.live import LIVE_FEED_TABLES
    mapped = set(_map("admin.js")) | set(_map("dashboard.js"))
    assert not (set(LIVE_FEED_TABLES) - mapped), set(LIVE_FEED_TABLES) - mapped


def test_sequence_and_ballot_and_attendance_tables_stay_off_the_maps():
    for script in ("admin.js", "dashboard.js"):
        for table in _map(script):
            assert table not in {"id_sequence_master", "user_session", "credential_sequence_counter"}
            assert "attendance" not in table.replace("darshak_attendance_registration", "")
            assert not table.startswith("election_vote")


def test_live_marker_diagnostics_labels_cover_the_batch2_admin_tabs():
    src = (JS / "audit-diagnostics.js").read_text()
    block = src[src.index("const TAB_LABELS"):src.index("/** Rows whose change_seq")]
    for tab in BATCH2_ADMIN_TABS:
        assert re.search(rf"\b{tab}:", block), tab


def test_advisory_board_and_governance_catalog_tabs_have_live_hooks():
    """2026-11-09 audit: these two read-only views were the only data tabs of their pages
    with watched tables behind them but no hook."""
    dash = (JS / "dashboard.js").read_text()
    admin = (JS / "admin.js").read_text()
    # Member dashboard: the Advisory Board tab refreshes silently (no spinner, no error flash).
    assert "reload: (h) => h._loadAdvisoryBoardDashboard({ silent: true })" in dash
    assert "async _loadAdvisoryBoardDashboard(opts = {})" in dash
    for table in ("body_master", "body_member_assignment", "body_type_master", "position_master", "person"):
        assert re.search(rf'{table}: \[[^\]]*"advisoryBoard"', dash), table
    # Admin console: Governance catalogue refreshes on body-type / position changes, busy while a form is open.
    assert "reload: (h) => h.loadGovCatalog({ silent: true })" in admin
    assert "async loadGovCatalog(opts = {})" in admin
    assert 'body_type_master: ["govCatalog"]' in admin and 'position_master: ["govCatalog"]' in admin
