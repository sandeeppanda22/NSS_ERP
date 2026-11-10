"""
UI tests for the Audit & Diagnostics admin tabs (System Event Log explorer and
Live Change Markers) - frontend/assets/js/audit-diagnostics.js, admin.html, admin.js.

  1. SOURCE-LEVEL (no browser, no server): sidebar entries, AUDIT_VIEW gating,
     endpoints used, no inline handlers, poll policy, wiring in admin.js.
  2. LOGIC (needs `node` only): the pure helpers changedMarkers / relativeTime.

Written without a browser: nothing here drives a page.
Run DB-free: python3 -m pytest tests/ui/test_ui_audit_diagnostics.py --noconftest
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "frontend" / "assets" / "js"
MIXIN_JS = JS / "audit-diagnostics.js"
node = shutil.which("node")


@pytest.fixture(scope="module")
def mixin() -> str:
    return MIXIN_JS.read_text()


@pytest.fixture(scope="module")
def admin_html() -> str:
    return (ROOT / "frontend" / "admin.html").read_text()


@pytest.fixture(scope="module")
def admin_js() -> str:
    return (JS / "admin.js").read_text()


def _node(expr: str):
    code = (f"global.window = {{}}; require({json.dumps(str(MIXIN_JS))});"
            f"const A = window.NSSAuditDiagnostics; console.log(JSON.stringify({expr}));")
    out = subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ── Source level ───────────────────────────────────────────────────────────

def test_script_is_loaded_before_admin_js(admin_html):
    assert admin_html.index("/assets/js/audit-diagnostics.js") < admin_html.index("/assets/js/admin.js")


def test_admin_js_installs_the_mixin_and_closes_the_chain(admin_js):
    assert "NSSAuditDiagnostics.install(NSSAssetsProperty.install(" in admin_js
    assert re.search(r"\}\)+, LIVE_REFRESH_CONFIG\);", admin_js)
    assert "this.auditTabChanged(tab)" in admin_js


def test_two_sidebar_entries_gated_by_can_view_audit(admin_html):
    group = admin_html.split("<!-- ── Audit & Diagnostics group", 1)[1].split("<!-- ── Correspondence Register", 1)[0]
    assert '<template x-if="canViewAudit">' in group
    assert "auditEventsEnter()" in group and "liveMarkersEnter()" in group
    assert "activeTab === 'auditEvents'" in group and "activeTab === 'liveMarkers'" in group
    assert "System Event Log" in group and "Live Change Markers" in group
    assert "toggleNavGroup('audit')" in group


def test_panels_are_gated_by_tab_and_permission(admin_html):
    assert "activeTab === 'auditEvents' && canViewAudit" in admin_html
    assert "activeTab === 'liveMarkers' && canViewAudit" in admin_html


def test_permission_is_audit_view(mixin):
    assert re.search(r'get canViewAudit\(\) \{.*?includes\("AUDIT_VIEW"\)', mixin, re.DOTALL)


def test_hash_routes_and_landing_for_audit_only_users(admin_js):
    assert 'auditEvents: () => { if (this.canViewAudit) this.auditEventsEnter(); }' in admin_js
    assert 'liveMarkers: () => { if (this.canViewAudit) this.liveMarkersEnter(); }' in admin_js
    assert "!this.canViewAssets && !this.canViewAudit) {" in admin_js


def test_endpoints_used(mixin):
    assert 'const BASE = "/api/v1/audit";' in mixin
    for path in ("/events/facets", "/events?", "/events/${pk}", "/change-log?", "/live-change-markers"):
        assert path in mixin, path


def test_field_changes_use_the_audit_router_not_foundation(mixin):
    assert "/api/v1/foundation" not in mixin
    assert "changed_from: row.event_at, changed_to: row.event_at" in mixin


def test_poll_policy_lives_in_one_object(mixin):
    block = re.search(r"const AUDIT_POLL = Object\.freeze\(\{(.*?)\}\);", mixin, re.DOTALL).group(1)
    assert "EVENTS_MS: 15000" in block and "MARKERS_MS: 5000" in block
    assert int(re.search(r"EVENTS_MS: (\d+)", block).group(1)) >= 10000   # never hammer system_event_log
    assert "setInterval" not in mixin
    assert mixin.count("document.hidden") >= 2          # both pollers pause while the browser tab is hidden
    assert "visibilitychange" in mixin
    assert "live-refresh" not in mixin.replace("live-refresh.js (", "").lower().split("*/", 1)[1]  # no competing poller


def test_event_auto_refresh_is_off_by_default(mixin):
    assert "aeAuto: false," in mixin


def test_default_window_is_24h(mixin):
    assert "DEFAULT_WINDOW_MS = 24 * 3600 * 1000" in mixin


def test_no_inline_handlers_or_innerhtml(mixin, admin_html):
    assert "onclick" not in mixin.lower() and "innerHTML" not in mixin
    start = admin_html.index("VIEW: System Event Log explorer")
    end = admin_html.index("<!-- /Live Change Markers -->")
    section = admin_html[start:end]
    assert not re.search(r'\son[a-z]+="', section)
    assert "x-html" not in section


def test_markers_screens_derive_from_the_admin_live_map(mixin):
    assert "typeof LIVE_TABLE_TABS" in mixin and "TAB_LABELS" in mixin


def test_summary_tiles_and_filter_present(admin_html):
    sec = admin_html.split("VIEW: Live Change Markers", 1)[1].split("<!-- /Live Change Markers -->", 1)[0]
    for needle in ("Watched tables", "Latest change number", "Most recently changed", "lm-just-changed",
                   'x-model="lmFilter"', "lmFiltered", "m.on_live_whitelist"):
        assert needle in sec, needle


def test_event_explorer_has_all_filters_sort_paging_detail(admin_html):
    sec = admin_html.split("VIEW: System Event Log explorer", 1)[1].split("<!-- /System Event Log -->", 1)[0]
    for needle in ("aeFilters.table", "aeFilters.action", "aeFilters.module", "aeFilters.actor", "aeFilters.record",
                   "aeFilters.from", "aeFilters.to", "aeFilters.q", "aeToggleSort()", "aePrev()", "aeNext()",
                   "aeOpen(r)", "aeFields", "aeDetailJson", "aeExportCsv()", "aeSetAuto("):
        assert needle in sec, needle


def test_badges_are_defined_in_badges_css_not_inline(admin_html):
    css = (ROOT / "frontend" / "assets" / "css" / "badges.css").read_text()
    for cls in ("badge-audit-success", "badge-audit-failed"):
        assert f".{cls}" in css
        assert f".{cls}" not in admin_html.split("</style>", 1)[0]


# ── Logic (node only) ──────────────────────────────────────────────────────

@pytest.mark.skipif(node is None, reason="node not available")
def test_changed_markers_logic():
    out = _node("""(() => {
      const m = (t, s) => ({ table_name: t, change_seq: s });
      const first = A.changedMarkers([m("a", 5), m("b", 3)], null);
      const same = A.changedMarkers([m("a", 5), m("b", 3)], first.seen);
      const moved = A.changedMarkers([m("a", 9), m("b", 3), m("c", 12)], first.seen);
      const lower = A.changedMarkers([m("a", 4)], first.seen);
      return { first: first.changed, seen: first.seen, same: same.changed, moved: moved.changed, lower: lower.changed };
    })()""")
    assert out == {"first": [], "seen": {"a": 5, "b": 3}, "same": [], "moved": ["a"], "lower": []}


@pytest.mark.skipif(node is None, reason="node not available")
def test_relative_time_logic():
    out = _node("[A.relativeTime(0, 4000), A.relativeTime(0, 120000), A.relativeTime(0, 7200000), "
                "A.relativeTime(0, 172800000), A.relativeTime(10000, 0)]")
    assert out == ["4 s ago", "2 min ago", "2 h ago", "2 d ago", "0 s ago"]
