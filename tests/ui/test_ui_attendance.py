"""
UI tests for Tier 6 Attendance (api/routers/attendance.py).

Closes the gap tests/README.md called out: Attendance had API and security
suites but no UI coverage at all, although it ships three surfaces:

  * admin.html "Attendance" nav group — Weekly Sangha Puja (create + mark),
    Attendance Reviews (action buttons), Watch List & Stats;
  * dashboard.html — the member's own "Attendance" tab and the designated
    marker's "Attendance Register" tab;
  * org-dashboard.js — the Sakha dashboard's attendance card / Top and Full
    Attendance tables.

Two kinds of test live here, deliberately in one file:

  1. SOURCE-LEVEL (no browser, no server): they parse the shipped HTML/JS and
     the router module, same style as test_ui_admin_correspondence.py and
     test_ui_badges.py. They protect wiring (nav -> tab -> loader, no dangling
     Alpine handlers), the three-copy search block that must stay identical,
     and the UI <-> API CONTRACT (every URL the frontend calls is a real route,
     every review action button maps to a real endpoint, no request exceeds a
     query bound the router enforces).

  2. BROWSER-LEVEL, LOGIC ONLY: attendance-register.js is the single shared
     implementation of "mark attendance" (mixed into admin.js and dashboard.js
     via NSSAttendanceRegister.install). These load that file on the static
     /login page (which already ships auth.js + nss-config.js), drive the mixin
     directly with `window.fetch` stubbed, and assert its tallies, filter,
     search-to-add, pre-fill and submit behaviour. They need the dev server
     (BASE_URL http://127.0.0.1:8001) but no seeded Attendance data and no
     particular user.

Written without a browser/server available: collection was verified, execution
was not. 

Run:
    python3 -m pytest tests/ui/test_ui_attendance.py
"""

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.ui.test_ui_auth_refresh import _MAKE_TOKEN

pytestmark = pytest.mark.ui

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
JS = FRONTEND / "assets" / "js"

ADMIN_HTML = FRONTEND / "admin.html"
DASHBOARD_HTML = FRONTEND / "dashboard.html"
ADMIN_JS = JS / "admin.js"
DASHBOARD_JS = JS / "dashboard.js"
ORG_DASHBOARD_JS = JS / "org-dashboard.js"
REGISTER_JS = JS / "attendance-register.js"
NSS_CONFIG_JS = JS / "nss-config.js"
ATTENDANCE_ROUTER = REPO_ROOT / "api" / "routers" / "attendance.py"
BADGES_CSS = FRONTEND / "assets" / "css" / "badges.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def admin_html() -> str:
    return _read(ADMIN_HTML)


@pytest.fixture(scope="module")
def dashboard_html() -> str:
    return _read(DASHBOARD_HTML)


@pytest.fixture(scope="module")
def admin_js() -> str:
    return _read(ADMIN_JS)


@pytest.fixture(scope="module")
def dashboard_js() -> str:
    return _read(DASHBOARD_JS)


@pytest.fixture(scope="module")
def register_js() -> str:
    return _read(REGISTER_JS)


@pytest.fixture(scope="module")
def nss_config_js() -> str:
    return _read(NSS_CONFIG_JS)


def _panel(html: str, tab: str, var: str = "activeTab") -> str:
    """The content panel opened by `x-show="<var> === '<tab>' ..."`, up to the next sibling panel."""
    m = re.search(rf"""<div x-show="{var} === '{tab}'[^"]*"[^>]*>""", html)
    assert m, f"No content panel for {tab!r} found."
    nxt = re.search(rf"""\n\s*<div x-show="{var} === '""", html[m.end():])
    return html[m.start(): m.end() + nxt.start()] if nxt else html[m.start():]


# ═══════════════════════════════════════════════════════════════════════
# 1. Admin navigation and tab wiring
# ═══════════════════════════════════════════════════════════════════════

ADMIN_ATT_TABS = {
    "attPujas": "loadAttPujas()",
    "attReviews": "loadAttReviews()",
    "attWatchList": "loadAttWatchList(); loadAttOrgStats()",
}


def test_attendance_nav_group_is_gated_on_view_permission(admin_html: str):
    # Gated on the view permission AND on a reach that can include a Sakha
    # (hasSakhaReach: KENDRA_MAHILA_SANGHA / ADVISORY_BOARD scopes reach no Sakha).
    start = admin_html.index("""<template x-if="canViewAttendance && hasSakhaReach">""")
    group = admin_html[start: admin_html.index("""<div class="nav-divider"></div>""", start)]
    assert "toggleNavGroup('attendance')" in group
    assert "isNavGroupCollapsed('attendance')" in group


@pytest.mark.parametrize("tab,loader", ADMIN_ATT_TABS.items())
def test_each_nav_item_switches_tab_and_runs_its_loader(tab: str, loader: str, admin_html: str):
    assert f"""activeTab === '{tab}' }}\"""" in admin_html
    assert f"activeTab = '{tab}'; {loader}" in admin_html, (
        f"The {tab} nav item must both switch the tab and call {loader}."
    )


@pytest.mark.parametrize("tab", ADMIN_ATT_TABS)
def test_each_panel_is_gated_on_view_permission(tab: str, admin_html: str):
    assert f"""<div x-show="activeTab === '{tab}' && canViewAttendance" x-cloak>""" in admin_html


@pytest.mark.parametrize("tab,loader", [
    ("attPujas", "this.loadAttPujas()"),
    ("attReviews", "this.loadAttReviews()"),
    ("attWatchList", "this.loadAttWatchList()"),
])
def test_deep_link_hash_loader_exists(tab: str, loader: str, admin_js: str):
    """Opening admin.html#attReviews directly must load the tab, not show an empty shell."""
    m = re.search(rf"{tab}:\s*\(\)\s*=>\s*\{{(.*?)\}},", admin_js)
    assert m and loader in m.group(1), f"admin.js tabLoaders[{tab}] must call {loader}."
    assert "canViewAttendance" in m.group(1), "The deep-link loader must respect the view permission."


def test_register_script_loads_before_the_pages_that_install_it(admin_html: str, dashboard_html: str):
    """adminPanel()/dashboardApp() call NSSAttendanceRegister.install() while they build their object."""
    for html, host_script in ((admin_html, "/assets/js/admin.js"), (dashboard_html, "/assets/js/dashboard.js")):
        assert html.index("/assets/js/attendance-register.js") < html.index(host_script)
        assert html.index("/assets/js/nss-config.js") < html.index("/assets/js/attendance-register.js")
        assert html.index("/assets/js/auth.js") < html.index("/assets/js/attendance-register.js")


def test_both_hosts_install_the_shared_register_once(admin_js: str, dashboard_js: str):
    for js in (admin_js, dashboard_js):
        assert len(re.findall(r"NSSAttendanceRegister\.install\(\{", js)) == 1


def test_hosts_own_their_after_save_hook(admin_js: str, dashboard_js: str, register_js: str):
    """install() never overwrites a host property, so each host's refresh hook must be defined by the host."""
    assert re.search(r"_afterAttendanceSaved\(\)\s*\{\s*return this\.loadAttPujas\(\)", admin_js)
    assert re.search(r"_afterAttendanceSaved\(\)", dashboard_js)
    assert re.search(r"_afterAttendanceSaved\(\)\s*\{\s*\}", register_js), "The mixin's default hook must be a no-op."


# ── No dangling Alpine handlers ─────────────────────────────────────────

# Verified present in admin.html at the time of writing; the point is that
# admin.js (or the shared mixin) must keep defining them.
ADMIN_ATT_HANDLERS = (
    "loadAttPujas", "submitCreatePuja", "openMarkAttendance", "closeMarkAttendance", "submitMarkAttendance",
    "attMarkSetAll", "searchAttMarkMember", "addAttMarkMember", "attMarkClearSearch", "_attInitials",
    "attMarkHomeRows", "attMarkDarshakRows", "submitCreateException", "searchAttExceptionMember",
    "pickAttExceptionMember", "loadAttReviews", "actOnReview", "loadAttWatchList", "loadAttOrgStats",
    "searchAttMemberStats", "loadAttMemberStats",
)

DASHBOARD_ATT_HANDLERS = (
    "openMarkAttendance", "closeMarkAttendance", "submitMarkAttendance", "attMarkSetAll",
    "searchAttMarkMember", "addAttMarkMember", "attMarkClearSearch", "_attInitials",
    "onAttRegSakhaChange", "submitCreateAttRegPuja",
)

ORG_DASHBOARD_ATT_HANDLERS = (
    "openFullAttendance", "closeFullAttendance", "attFullFilteredMembers", "attRecentPadded",
    "attStatusLetterFor", "attStatusBadgeClassFor", "darshakVisibleRows",
)


@pytest.mark.parametrize("handler", ADMIN_ATT_HANDLERS)
def test_admin_handler_is_defined(handler: str, admin_js: str, register_js: str):
    assert re.search(rf"(async\s+)?{handler}\s*\(", admin_js + register_js), (
        f"admin.html calls {handler}() but neither admin.js nor attendance-register.js defines it."
    )


@pytest.mark.parametrize("handler", ADMIN_ATT_HANDLERS)
def test_admin_handler_is_used_by_the_markup(handler: str, admin_html: str):
    assert f"{handler}(" in admin_html, f"{handler}() is no longer in admin.html — update ADMIN_ATT_HANDLERS."


@pytest.mark.parametrize("handler", DASHBOARD_ATT_HANDLERS)
def test_dashboard_handler_is_defined(handler: str, dashboard_js: str, register_js: str):
    assert re.search(rf"(async\s+)?{handler}\s*\(", dashboard_js + register_js)


@pytest.mark.parametrize("handler", DASHBOARD_ATT_HANDLERS)
def test_dashboard_handler_is_used_by_the_markup(handler: str, dashboard_html: str):
    assert f"{handler}(" in dashboard_html


@pytest.mark.parametrize("handler", ORG_DASHBOARD_ATT_HANDLERS)
def test_org_dashboard_handler_is_defined_and_used(handler: str):
    js = _read(ORG_DASHBOARD_JS)
    assert re.search(rf"(async\s+)?{handler}\s*\(", js)
    assert f"{handler}(" in _read(DASHBOARD_HTML) or f"{handler}(" in _read(ADMIN_HTML)


# ═══════════════════════════════════════════════════════════════════════
# 2. The Mark Attendance panel
# ═══════════════════════════════════════════════════════════════════════

def test_create_puja_button_requires_manage_permission(admin_html: str):
    panel = _panel(admin_html, "attPujas")
    assert re.search(r"""x-show="canManageAttendance"\s*\n\s*@click="attPujaForm\.show = !attPujaForm\.show""", panel)


def test_create_puja_submit_is_disabled_until_sakha_and_date_are_chosen(admin_html: str):
    panel = _panel(admin_html, "attPujas")
    assert ':disabled="attPujaForm.saving || !attPujaForm.sakha_pk || !attPujaForm.puja_date"' in panel


def test_mark_attendance_row_button_requires_manage_permission(admin_html: str):
    panel = _panel(admin_html, "attPujas")
    assert re.search(r"""x-show="canManageAttendance" @click="openMarkAttendance\(p\)">Mark Attendance""", panel)


def test_register_panel_toggles_use_exactly_the_api_status_codes(admin_html: str, dashboard_html: str):
    """The P/A/E buttons and the bulk setters must emit the codes mark_attendance() accepts."""
    router_src = _read(ATTENDANCE_ROUTER)
    accepted = set(re.search(r'for code in \(([^)]*)\)', router_src).group(1).replace('"', "").replace(" ", "").split(","))
    assert accepted == {"PRESENT", "ABSENT", "EXCUSED_ABSENCE"}
    for html in (admin_html, dashboard_html):
        assigned = set(re.findall(r"attMarkTap\(row, '([A-Z_]+)'\)", html))
        bulk = set(re.findall(r"attMarkSetAll\('([A-Z_]+)'\)", html))
        assert assigned == accepted and bulk == accepted


def test_mark_panel_has_filter_chips_for_every_status(admin_html: str):
    panel = _panel(admin_html, "attPujas")
    for code in ("ALL", "NOT_MARKED", "PRESENT", "ABSENT", "EXCUSED_ABSENCE"):
        assert f"attMarkFilter = '{code}'" in panel


def test_mark_panel_separates_home_members_from_darshak_visitors(admin_html: str, dashboard_html: str):
    for html in (admin_html, dashboard_html):
        assert "attMarkHomeRows()" in html and "attMarkDarshakRows()" in html


def test_submit_button_is_disabled_while_saving(admin_html: str, dashboard_html: str):
    for html in (admin_html, dashboard_html):
        assert re.search(r""":disabled="attMarkSaving[^"]*" @click="submitMarkAttendance\(\)\"""", html)


def test_search_to_add_block_is_identical_in_admin_and_dashboard(admin_html: str, dashboard_html: str):
    """The block is hand-copied (no include mechanism); the markers say it MUST stay identical."""
    def block(html: str) -> str:
        m = re.search(r"<!-- ATT-MARK-SEARCH:START.*?-->(.*?)<!-- ATT-MARK-SEARCH:END -->", html, re.DOTALL)
        assert m, "ATT-MARK-SEARCH markers missing."
        return re.sub(r"\s+", " ", m.group(1)).strip()

    assert block(admin_html) == block(dashboard_html)


def test_live_register_markup_is_present_in_both_copies(admin_html: str, dashboard_html: str):
    """The panel is hand-copied into admin.html and dashboard.html; the live-register additions must be in both."""
    for html in (admin_html, dashboard_html):
        assert html.count('x-text="attRowMeta(row)"') == 2          # home grid + Darshak grid
        assert html.count('x-text="attRowHint(row)"') == 2
        assert html.count("'att-row-flash': row.flash") == 2
        assert 'x-text="attMarkProgressText"' in html               # "N of M marked"
        assert "attLiveReconnecting" in html and "attMarkSavedNote" in html
        assert "attMarkFilter = 'NOT_MARKED'" in html
        assert "Submit Attendance" not in html                      # now an explicit "Save N changes"
        assert not re.search(r"row\.attendance_status_code = '", html), "edits must go through attMarkTap()/attMarkSet()"


def test_poll_interval_numbers_live_only_in_the_shared_mixin(register_js: str):
    block = re.search(r"const LIVE_POLL = Object\.freeze\(\{(.*?)\}\);", register_js, re.DOTALL).group(1)
    assert "ACTIVE_MS: 2000" in block and "IDLE_MS: 10000" in block and "IDLE_AFTER_MS: 60000" in block
    assert "[4000, 8000, 16000, 30000]" in block
    assert "visibilitychange" in register_js and "If-None-Match" in register_js and "Retry-After" in register_js


def test_search_input_requires_two_characters_in_the_hint_and_the_code(admin_html: str, register_js: str):
    assert "attMarkSearchQuery.trim().length === 1" in admin_html and "at least 2 characters" in admin_html
    assert re.search(r"if \(q\.length < 2\)", register_js)


# ═══════════════════════════════════════════════════════════════════════
# 3. Attendance Reviews and the Watch List
# ═══════════════════════════════════════════════════════════════════════

def _router_review_actions() -> set[str]:
    from api.routers.attendance import router

    return {
        m.group(1)
        for r in router.routes
        if (m := re.fullmatch(r"/api/v1/attendance/reviews/\{review_pk\}/([a-z-]+)", r.path))
    }


def test_review_buttons_call_real_endpoints_and_cover_every_non_override_action():
    """Every action the UI posts exists on the router; the only one the UI omits is the President override."""
    ui_actions = set(re.findall(r"actOnReview\(rv, '([a-z-]+)'\)", _read(ADMIN_HTML)))
    router_actions = _router_review_actions()
    assert ui_actions <= router_actions, f"UI posts to unknown review actions: {ui_actions - router_actions}"
    assert router_actions - ui_actions == {"override"}


def test_review_panel_shows_per_row_errors_and_disables_while_busy(admin_html: str):
    panel = _panel(admin_html, "attReviews")
    assert 'x-show="attReviewActionError[rv.review_pk]"' in panel
    assert panel.count(':disabled="attReviewActionBusy === rv.review_pk"') == 6


def test_review_actions_are_not_hidden_by_permission(admin_html: str):
    """ATT-042: authority is the Secretary/President seat, enforced server-side; the UI must not guess it."""
    panel = _panel(admin_html, "attReviews")
    assert "canManageAttendance" not in panel


def test_review_status_filter_options_match_the_workflow_states(admin_html: str):
    panel = _panel(admin_html, "attReviews")
    options = set(re.findall(r'<option value="([A-Z_]*)"', panel[panel.index("attReviewStatusFilter"):][:1500]))
    assert {"OPEN", "DEFERRED", "CLOSED", "ESCALATED_TO_PRESIDENT", "ESCALATED_TO_PARICHALAK"} <= options


def test_review_status_badge_maps_cover_every_workflow_state(nss_config_js: str):
    block = re.search(r"ATTENDANCE_REVIEW_STATUS_BADGE_MAP:\s*\{(.*?)\},", nss_config_js, re.DOTALL).group(1)
    states = set(re.findall(r"^\s*([A-Z_]+):", block, re.MULTILINE))
    assert states == {"OPEN", "DEFERRED", "CLOSED", "ESCALATED_TO_PRESIDENT", "ESCALATED_TO_PARICHALAK"}
    css = _read(BADGES_CSS)
    for cls in re.findall(r'"(badge-attrev-[a-z_]+)"', block):
        assert f".{cls}" in css, f"{cls} is mapped in nss-config.js but not defined in badges.css"


def test_attendance_status_badge_classes_exist_in_the_shared_stylesheet(nss_config_js: str):
    block = re.search(r"ATTENDANCE_STATUS_BADGE_MAP:\s*\{(.*?)\},", nss_config_js, re.DOTALL).group(1)
    css = _read(BADGES_CSS)
    classes = re.findall(r'"(badge-att-[a-z_]+)"', block)
    assert len(classes) == 3
    for cls in classes:
        assert f".{cls}" in css


def test_attendance_badges_are_not_redefined_inline(admin_html: str, dashboard_html: str):
    """CLAUDE.md: badges.css owns badge classes; pages must not redefine them."""
    for html in (admin_html, dashboard_html):
        assert not re.search(r"<style[^>]*>[^<]*\.badge-att", html, re.DOTALL)


# ═══════════════════════════════════════════════════════════════════════
# 4. UI <-> API contract
# ═══════════════════════════════════════════════════════════════════════

FRONTEND_JS_WITH_ATTENDANCE_CALLS = [REGISTER_JS, ADMIN_JS, DASHBOARD_JS, ORG_DASHBOARD_JS]


def _frontend_attendance_urls() -> set[str]:
    """Every /api/v1/attendance/... literal in the frontend, `${...}` collapsed to `{}` and the query dropped."""
    urls: set[str] = set()
    for path in FRONTEND_JS_WITH_ATTENDANCE_CALLS:
        for raw in re.findall(r"""[`"'](/api/v1/attendance[^`"']*)[`"']""", _read(path)):
            collapsed = re.sub(r"\$\{[^}]*\}", "{}", raw).split("?")[0].rstrip("/")
            urls.add(collapsed)
    return urls


def test_every_frontend_attendance_url_is_a_real_route():
    from api.routers.attendance import router

    route_patterns = [re.sub(r"\{[^}]+\}", "{}", r.path) for r in router.routes]
    for url in sorted(_frontend_attendance_urls()):
        if url.endswith("/{}") and url.startswith("/api/v1/attendance/reviews/{}/"):
            # actOnReview(): the trailing segment is the action name, checked separately above.
            assert any(p.startswith("/api/v1/attendance/reviews/{}/") for p in route_patterns)
            continue
        assert url in route_patterns, f"Frontend calls {url}, which is not an attendance route."


def test_frontend_covers_the_endpoints_it_is_supposed_to_use():
    """A guard against the contract test above passing vacuously (e.g. a regex that matches nothing)."""
    urls = _frontend_attendance_urls()
    for expected in (
        "/api/v1/attendance/pujas", "/api/v1/attendance/pujas/{}/attendance", "/api/v1/attendance/pujas/{}/live",
        "/api/v1/attendance/records",
        "/api/v1/attendance/exceptions", "/api/v1/attendance/watch-list",
        "/api/v1/attendance/stats/organizations/{}", "/api/v1/attendance/stats/organizations/{}/members",
        "/api/v1/attendance/stats/members/{}", "/api/v1/attendance/reviews",
    ):
        assert expected in urls, f"{expected} is no longer called by the frontend."


def _router_page_size_bound(function_name: str) -> int:
    src = _read(ATTENDANCE_ROUTER)
    block = src[src.index(f"def {function_name}("):][:900]
    return int(re.search(r"page_size: int = Query\(\d+, ge=1, le=(\d+)\)", block).group(1))


def _max_page_size_constant() -> int:
    return int(re.search(r"MAX_PAGE_SIZE:\s*(\d+)", _read(NSS_CONFIG_JS)).group(1))


def _page_sizes_near(src: str, needle: str) -> list[int]:
    """Every page_size value written within a few lines of a call to *needle* (params are built just before the fetch)."""
    sent: list[int] = []
    for m in re.finditer(re.escape(needle), src):
        window = src[max(0, m.start() - 450): m.end() + 350]
        for value in re.findall(r"page_size\W+(?:String\()?\s*[\"']?(\d+|NSS\.MAX_PAGE_SIZE)", window):
            sent.append(_max_page_size_constant() if value.startswith("NSS") else int(value))
    return sent


@pytest.mark.parametrize("path", [
    pytest.param(REGISTER_JS, id="attendance-register.js"),
    pytest.param(DASHBOARD_JS, id="dashboard.js"),
    pytest.param(ORG_DASHBOARD_JS, id="org-dashboard.js"),
])
def test_records_requests_stay_within_the_routers_page_size_bound(path: Path):
    sent = _page_sizes_near(_read(path), "attendance/records")
    bound = _router_page_size_bound("list_records")
    assert sent, f"{path.name}: no page_size found near the /attendance/records call."
    assert max(sent) <= bound, f"{path.name} sends page_size={max(sent)} but the router allows at most {bound}."


@pytest.mark.parametrize("function_name,needle,path", [
    ("list_pujas", "attendance/pujas?", ADMIN_JS),
    ("list_pujas", "attendance/pujas?", DASHBOARD_JS),
    ("list_reviews", "attendance/reviews?", ADMIN_JS),
])
def test_list_requests_stay_within_the_routers_page_size_bound(function_name: str, needle: str, path: Path):
    sent = _page_sizes_near(_read(path), needle)
    assert sent, f"{path.name}: no page_size found near {needle}."
    assert max(sent) <= _router_page_size_bound(function_name)


def test_leaderboard_limit_is_within_the_routers_maximum():
    from api.helpers import MAX_LIMIT

    sent = [int(v) for v in re.findall(r"/members\?limit=(\d+)", _read(ORG_DASHBOARD_JS))]
    assert sent and max(sent) <= MAX_LIMIT


def test_member_directory_roster_limit_is_within_the_directory_maximum():
    from api.helpers import MAX_LIMIT

    assert _max_page_size_constant() <= MAX_LIMIT, "The roster/search calls send limit=NSS.MAX_PAGE_SIZE."


# ═══════════════════════════════════════════════════════════════════════
# 5. Dashboard surfaces (member history, marker register tab, Sakha card)
# ═══════════════════════════════════════════════════════════════════════

def test_marker_register_tab_is_only_offered_to_attendance_managers(dashboard_html: str):
    assert re.search(
        r"""switchTab\('attendanceRegister'\)" x-show="canManageAttendance">""", dashboard_html
    )


def test_marker_register_tab_initialises_on_open_and_on_deep_link(dashboard_js: str):
    assert dashboard_js.count("this._initAttendanceRegister()") >= 2


def test_member_attendance_tab_needs_an_active_sangha_sevi(dashboard_html: str):
    panel = _panel(dashboard_html, "attendance", var="tab")
    assert "!member || !member.sangha_sevi_pk" in panel and "member && member.sangha_sevi_pk" in panel
    assert "Puja History" in panel and "NSS.attStatusBadgeClass(r.attendance_status_code)" in panel


def test_member_history_reads_their_own_records_and_stats(dashboard_js: str):
    assert "sangha_sevi_pk: this.member.sangha_sevi_pk" in dashboard_js
    assert "/api/v1/attendance/stats/members/${this.member.sangha_sevi_pk}" in dashboard_js


def test_sakha_dashboard_attendance_card_is_permission_gated():
    js = _read(ORG_DASHBOARD_JS)
    assert re.search(r'get canSeeAttendance\(\)\s*\{[^}]*ATTENDANCE_VIEW[^}]*ATTENDANCE_MANAGE', js, re.DOTALL)
    assert "!this.isSakha || !this.canSeeAttendance" in js, "The card must only load for a Sakha, for a permitted viewer."


def test_top_attendance_card_shows_five_rows_and_full_view_shows_all():
    js = _read(ORG_DASHBOARD_JS)
    assert ".slice(0, 5)" in js
    html = _read(DASHBOARD_HTML)
    assert "attendanceTopMembers" in html and "attFullFilteredMembers()" in html


# ═══════════════════════════════════════════════════════════════════════
# 6. Shared register logic, driven in a browser with fetch stubbed
# ═══════════════════════════════════════════════════════════════════════

_SESSION = """
(args) => {
    localStorage.clear();
    localStorage.setItem('nss_access_token', args.token);
    localStorage.setItem('nss_refresh_token', 'refresh-token');
    localStorage.setItem('nss_user', JSON.stringify({ permissions: args.permissions }));
}
"""

# Page-side prelude: a recording fetch stub plus a fresh host with the mixin installed. `routes` is a
# list of [substring, {status, body}] pairs; the first whose substring occurs in the URL answers
# (anything else is a 404). The test body is spliced in as the body of an async function with `host`
# and `calls` in scope, and the whole thing is handed to page.evaluate() as ONE function source - no
# eval/new Function, which the app's CSP (no 'unsafe-eval') would block. window.fetch is always restored.
_RUN_TEMPLATE = """
async (routes) => {
    const calls = [];
    const realFetch = window.fetch;
    window.fetch = (url, opts = {}) => {
        calls.push({ url: String(url), method: opts.method || 'GET', body: opts.body || null });
        const hit = routes.find(([needle]) => String(url).includes(needle));
        const step = hit ? hit[1] : { status: 404, body: {} };
        return Promise.resolve({
            ok: step.status < 400, status: step.status, json: () => Promise.resolve(step.body),
        });
    };
    try {
        const host = NSSAttendanceRegister.install({});
        const result = await (async () => {
%BODY%
        })();
        return { result, calls };
    } finally {
        window.fetch = realFetch;
    }
}
"""


@pytest.fixture
def register_page(page: Page, base_url: str) -> Page:
    """The static login page already ships auth.js + nss-config.js; add the register on top."""
    page.goto(f"{base_url}/login")
    page.wait_for_function("() => typeof NSSAuth !== 'undefined' && typeof NSS !== 'undefined'", timeout=10_000)
    page.add_script_tag(url=f"{base_url}/assets/js/attendance-register.js")
    page.wait_for_function("() => typeof NSSAttendanceRegister !== 'undefined'", timeout=10_000)
    token = page.evaluate(_MAKE_TOKEN, 3600)
    page.evaluate(_SESSION, {"token": token, "permissions": ["ATTENDANCE_VIEW", "ATTENDANCE_MANAGE"]})
    return page


def _run(page: Page, body: str, routes=None):
    return page.evaluate(_RUN_TEMPLATE.replace("%BODY%", body), routes or [])


PUJA = "{ weekly_sangha_puja_pk: 'P1', sakha_pk: 'S1', sakha_name: 'Home Sakha', puja_date: '2001-03-04' }"


def test_tallies_exclude_excused_absence_from_the_percentage(register_page: Page):
    out = _run(register_page, """
        host.attMarkRows = [
            ...Array(3).fill({ attendance_status_code: 'PRESENT' }),
            { attendance_status_code: 'ABSENT' },
            ...Array(2).fill({ attendance_status_code: 'EXCUSED_ABSENCE' }),
        ];
        const c = host.attMarkCounts;
        host.attMarkRows = [{ attendance_status_code: 'EXCUSED_ABSENCE' }];
        return { c: { ...c }, onlyExcused: host.attMarkCounts.percentage };
    """)["result"]
    assert out["c"] == {"present": 3, "absent": 1, "excused": 2, "total": 6, "marked": 6, "unmarked": 0, "percentage": 75}
    assert out["onlyExcused"] is None


def test_percentage_is_out_of_the_whole_roster_unmarked_in_excused_out(register_page: Page):
    """Owner 2026-11-01: 8 present, 1 absent, 0 excused, 12 total (3 unmarked) is 67% (8/12), not 89% (8/9)."""
    out = _run(register_page, """
        const st = [...Array(8).fill('PRESENT'), 'ABSENT', null, null, null];
        host.attMarkRows = st.map(s => ({ attendance_status_code: s }));
        const c = host.attMarkCounts;
        const fn = NSSAttendanceRegister.registerAttendancePercentage;
        host.attMarkRows = [...st.map(s => ({ attendance_status_code: s })), { attendance_status_code: 'EXCUSED_ABSENCE' }];
        return { pct: c.percentage, total: c.total, withExcused: host.attMarkCounts.percentage,
                 fn: [fn(8, 0, 12), fn(8, 1, 13), fn(0, 0, 0), fn(0, 3, 3), fn(0, 0, 5)] };
    """)["result"]
    assert out["pct"] == 67 and out["total"] == 12
    assert out["withExcused"] == 67, "an excused member leaves the denominator (ATT-008): 8 / (13 - 1)"
    assert out["fn"] == [67, 67, None, None, 0]


def test_markup_shows_the_percentage_only_via_the_shared_formula(admin_html: str, dashboard_html: str, register_js: str):
    for html in (admin_html, dashboard_html):
        assert "attMarkCounts.percentage" in html
    assert register_js.count("Math.round(present / denom * 100)") == 1, "one shared formula"
    assert "c.present + c.absent" not in register_js


def _other_marker_run(body: str, answer: str = "true"):
    return f"""
        const dialogs = [];
        const realConfirm = NSSDialog.confirm;
        NSSDialog.confirm = async (msg, opts) => {{ dialogs.push({{ msg, opts }}); return {answer}; }};
        host.currentUser = {{ sangha_sevi_id: 'SS1' }};
        host.attMarkPuja = {PUJA};
        const mk = (pk, st, by) => host._attMarkRow({{ sangha_sevi_pk: pk, organization_pk: 'S1', first_name: pk }},
            st ? {{ attendance_status_code: st, version: '2026-01-01T10:00:00+00:00', marked_by_name: by + ' Name',
                    marked_by_sangha_sevi_id: by, marked_at: '2026-01-01T10:00:00+00:00' }} : null);
        try {{ {body} }} finally {{ NSSDialog.confirm = realConfirm; }}
    """


def test_tapping_a_status_over_someone_elses_mark_asks_naming_who(register_page: Page):
    out = _run(register_page, _other_marker_run("""
        host.attMarkRows = [mk('a', 'ABSENT', 'SS7'), mk('b', 'ABSENT', 'SS1'), mk('c', 'ABSENT', 'SS7'), mk('d', null, 'SS7')];
        await host.attMarkTap(host.attMarkRows[0], 'PRESENT');   // someone else's, different -> asks
        await host.attMarkTap(host.attMarkRows[1], 'PRESENT');   // my own -> never asks
        await host.attMarkTap(host.attMarkRows[2], 'ABSENT');    // same status -> nothing to ask
        await host.attMarkTap(host.attMarkRows[3], 'PRESENT');   // unmarked -> never asks
        return { dialogs, rows: host.attMarkRows.map(r => [r.attendance_status_code, r.dirty, r.confirmedOverwrite]) };
    """))["result"]
    [d] = out["dialogs"]
    assert "Marked Absent by SS7 Name" in d["msg"] and "change it?" in d["msg"]
    assert out["rows"] == [["PRESENT", True, True], ["PRESENT", True, False], ["ABSENT", False, False], ["PRESENT", True, False]]


def test_cancelling_keeps_the_other_markers_mark(register_page: Page):
    out = _run(register_page, _other_marker_run("""
        host.attMarkRows = [mk('a', 'ABSENT', 'SS7')];
        await host.attMarkTap(host.attMarkRows[0], 'PRESENT');
        const r = host.attMarkRows[0];
        return { dialogs: dialogs.length, row: [r.attendance_status_code, r.dirty, r.confirmedOverwrite] };
    """, "false"))["result"]
    assert out == {"dialogs": 1, "row": ["ABSENT", False, False]}


def test_confirmed_overwrite_is_sent_in_overwrite_sangha_sevi_pks(register_page: Page):
    out = _run(register_page, _seq([{"status": 201, "body": {"records": [
        _rec("a", "PRESENT", "2026-01-01T10:40:00+00:00")], "total": 1}}]) + _other_marker_run("""
        host.attMarkRows = [mk('a', 'ABSENT', 'SS7')];
        await host.attMarkTap(host.attMarkRows[0], 'PRESENT');
        await host.submitMarkAttendance();
        return { dialogs: dialogs.length, confirmed: host.attMarkRows[0].confirmedOverwrite };
    """))
    [post] = [c for c in out["calls"] if c["method"] == "POST"]
    body = json.loads(post["body"])
    assert body["overwrite_sangha_sevi_pks"] == ["a"] and body["records"][0]["expected_version"] == "2026-01-01T10:00:00+00:00"
    assert out["result"] == {"dialogs": 1, "confirmed": False}, "asked once (the tap), not again on Save"


def test_bulk_set_skips_other_markers_rows_unless_confirmed_once(register_page: Page):
    script = """
        host.attMarkRows = [mk('a', 'ABSENT', 'SS7'), mk('b', 'ABSENT', 'SS8'), mk('c', 'ABSENT', 'SS1'), mk('d', null, 'SS7')];
        await host.attMarkSetAll('PRESENT');
        return { dialogs, rows: host.attMarkRows.map(r => [r.attendance_status_code, r.confirmedOverwrite]) };
    """
    skipped = _run(register_page, _other_marker_run(script, "false"))["result"]
    [d] = skipped["dialogs"]
    assert "2 members were marked by someone else" in d["msg"]
    assert skipped["rows"] == [["ABSENT", False], ["ABSENT", False], ["PRESENT", False], ["PRESENT", False]]
    confirmed = _run(register_page, _other_marker_run(script, "true"))["result"]
    assert len(confirmed["dialogs"]) == 1, "one question for the whole batch"
    assert confirmed["rows"] == [["PRESENT", True], ["PRESENT", True], ["PRESENT", False], ["PRESENT", False]]


def test_filter_and_bulk_set_only_touch_the_rows_on_screen(register_page: Page):
    out = _run(register_page, """
        host.attMarkRows = ['PRESENT', 'PRESENT', 'ABSENT', 'EXCUSED_ABSENCE'].map(
            (s, i) => ({ sangha_sevi_pk: 'm' + i, attendance_status_code: s }));
        host.attMarkFilter = 'ABSENT';
        const visible = host.attMarkVisibleRows().length;
        host.attMarkSetAll('PRESENT');
        return { visible, statuses: host.attMarkRows.map(r => r.attendance_status_code) };
    """)["result"]
    assert out["visible"] == 1
    assert out["statuses"] == ["PRESENT", "PRESENT", "PRESENT", "EXCUSED_ABSENCE"]


def test_all_filter_bulk_set_retags_everyone(register_page: Page):
    out = _run(register_page, """
        host.attMarkRows = ['PRESENT', 'ABSENT'].map((s, i) => ({ sangha_sevi_pk: 'm' + i, attendance_status_code: s }));
        host.attMarkSetAll('EXCUSED_ABSENCE');
        return host.attMarkRows.map(r => r.attendance_status_code);
    """)["result"]
    assert out == ["EXCUSED_ABSENCE", "EXCUSED_ABSENCE"]


def test_visitors_from_another_sakha_are_split_out_and_ignore_the_filter(register_page: Page):
    out = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [
            host._attMarkRow({{ sangha_sevi_pk: 'a', organization_pk: 'S1', first_name: 'A' }}, null),
            host._attMarkRow({{ sangha_sevi_pk: 'b', organization_pk: 'S2', first_name: 'B' }}, null),
        ];
        host.attMarkFilter = 'ABSENT';
        return {{
            home: host.attMarkHomeRows().map(r => r.sangha_sevi_pk),
            darshak: host.attMarkDarshakRows().map(r => r.sangha_sevi_pk),
            flags: host.attMarkRows.map(r => r.is_darshak),
        }};
    """)["result"]
    assert out == {"home": [], "darshak": ["b"], "flags": [False, True]}, "home rows obey the filter, visitors do not"


def test_row_builder_starts_unmarked_and_joins_the_name(register_page: Page):
    row = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        return host._attMarkRow({{ sangha_sevi_pk: 'a', sangha_sevi_id: 'SS9', organization_pk: 'S1',
                                   first_name: 'Asha', middle_name: null, last_name: 'Devi',
                                   membership_type_code: 'REGULAR', local_sakha_erp_id: 'ESS7' }}, null);
    """)["result"]
    # No default status: an untouched row is unmarked and must never be saved.
    assert row["attendance_status_code"] is None and row["already_marked"] is False
    assert row["dirty"] is False and row["ackVersion"] is None and row["serverState"]["status"] is None
    assert row["person_name"] == "Asha Devi" and row["local_sakha_erp_id"] == "ESS7"


def test_permission_getters_track_the_cached_user_live(register_page: Page):
    out = _run(register_page, """
        const read = () => [host.canViewAttendance, host.canManageAttendance];
        const set = (p) => localStorage.setItem('nss_user', JSON.stringify({ permissions: p }));
        const seen = {};
        set([]); seen.none = read();
        set(['ATTENDANCE_VIEW']); seen.view = read();
        set(['ATTENDANCE_MANAGE']); seen.manage = read();
        localStorage.removeItem('nss_user'); seen.loggedOut = read();
        return seen;
    """)["result"]
    assert out == {"none": [False, False], "view": [True, False], "manage": [True, True], "loggedOut": [False, False]}


def test_install_keeps_host_properties_and_isolates_state_per_host(register_page: Page):
    out = _run(register_page, """
        const owned = NSSAttendanceRegister.install({ _afterAttendanceSaved() { return 'host'; }, attMarkFilter: 'ABSENT' });
        const a = NSSAttendanceRegister.install({});
        const b = NSSAttendanceRegister.install({});
        a.attMarkRows.push({ sangha_sevi_pk: 'x' });
        return { hook: owned._afterAttendanceSaved(), filter: owned.attMarkFilter,
                 defaultHook: a._afterAttendanceSaved() ?? null, aRows: a.attMarkRows.length, bRows: b.attMarkRows.length };
    """)["result"]
    assert out == {"hook": "host", "filter": "ABSENT", "defaultHook": None, "aRows": 1, "bRows": 0}


def test_searching_with_fewer_than_two_characters_makes_no_request(register_page: Page):
    out = _run(register_page, """
        host.attMarkSearchQuery = ' a ';
        host.attMarkSearchResults = [{ sangha_sevi_pk: 'stale' }];
        host.searchAttMarkMember();
        await new Promise(r => setTimeout(r, 450));
        return { results: host.attMarkSearchResults.length, searching: host.attMarkSearching, calls: calls.length };
    """)
    assert out["result"] == {"results": 0, "searching": False, "calls": 0}


def test_search_hits_the_directory_and_hides_members_already_in_the_grid(register_page: Page):
    out = _run(register_page, """
        host.attMarkRows = [{ sangha_sevi_pk: 'inGrid' }];
        host.attMarkSearchQuery = 'asha';
        host.searchAttMarkMember();
        await new Promise(r => setTimeout(r, 600));
        return host.attMarkSearchResults.map(m => m.sangha_sevi_pk);
    """, routes=[["/membership/directory", {"status": 200, "body": {"members": [
        {"sangha_sevi_pk": "inGrid"}, {"sangha_sevi_pk": "new1"}, {"sangha_sevi_pk": "new2"}]}}]])
    assert out["result"] == ["new1", "new2"]
    assert any("/api/v1/membership/directory?q=asha&limit=10" in c["url"] for c in out["calls"])


def test_picking_a_search_result_adds_it_once_and_clears_the_box(register_page: Page):
    out = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        const m = {{ sangha_sevi_pk: 'v1', organization_pk: 'S2', first_name: 'Visitor' }};
        host.attMarkSearchQuery = 'vis';
        host.attMarkSearchResults = [m, {{ sangha_sevi_pk: 'v2' }}];
        host.addAttMarkMember(m);
        host.addAttMarkMember(m);
        return {{ rows: host.attMarkRows.map(r => [r.sangha_sevi_pk, r.is_darshak]),
                  query: host.attMarkSearchQuery, left: host.attMarkSearchResults.map(r => r.sangha_sevi_pk) }};
    """)["result"]
    assert out == {"rows": [["v1", True]], "query": "", "left": ["v2"]}


def test_initials_helper(register_page: Page):
    out = _run(register_page, """
        return [host._attInitials({ first_name: 'asha', last_name: 'devi' }), host._attInitials({})];
    """)["result"]
    assert out == ["AD", "?"]


_ROSTER = {"members": [
    {"sangha_sevi_pk": "a", "sangha_sevi_id": "SS1", "organization_pk": "S1", "first_name": "A", "last_name": "One"},
    {"sangha_sevi_pk": "b", "sangha_sevi_id": "SS2", "organization_pk": "S1", "first_name": "B", "last_name": "Two"},
]}
_RECORDS = {"records": [
    {"weekly_sangha_puja_pk": "P1", "sangha_sevi_pk": "b", "attendance_status_code": "ABSENT"},
    {"weekly_sangha_puja_pk": "OTHER", "sangha_sevi_pk": "a", "attendance_status_code": "ABSENT"},
]}


def test_opening_the_register_prefills_only_this_pujas_recorded_statuses(register_page: Page):
    out = _run(register_page, f"""
        await host.openMarkAttendance({PUJA});
        const seen = {{ loading: host.attMarkLoading, error: host.attMarkError,
                  rows: host.attMarkRows.map(r => [r.sangha_sevi_pk, r.attendance_status_code, r.already_marked]) }};
        host.closeMarkAttendance();
        return seen;
    """, routes=[["/membership/directory", {"status": 200, "body": _ROSTER}],
                 ["/attendance/records", {"status": 200, "body": _RECORDS}]])
    assert out["result"] == {"loading": False, "error": "",
                             "rows": [["a", None, False], ["b", "ABSENT", True]]}
    urls = [c["url"] for c in out["calls"]]
    assert any("/api/v1/membership/directory?" in u and "organization_pk=S1" in u for u in urls)
    assert any("/api/v1/attendance/records?" in u and "organization_pk=S1" in u
               and "weekly_sangha_puja_pk=P1" in u and "page_size=200" in u for u in urls)


def test_the_records_request_is_within_the_apis_page_size_cap(register_page: Page):
    out = _run(register_page, f"await host.openMarkAttendance({PUJA}); host.closeMarkAttendance(); return null;",
               routes=[["/membership/directory", {"status": 200, "body": _ROSTER}],
                       ["/attendance/records", {"status": 200, "body": _RECORDS}]])
    sizes = [int(m.group(1)) for c in out["calls"] if "/attendance/records" in c["url"]
             for m in [re.search(r"page_size=(\d+)", c["url"])] if m]
    assert sizes and max(sizes) <= 200


def test_a_failed_roster_load_is_reported_and_leaves_no_rows(register_page: Page):
    out = _run(register_page, f"""
        await host.openMarkAttendance({PUJA});
        return {{ loading: host.attMarkLoading, error: host.attMarkError, rows: host.attMarkRows.length }};
    """, routes=[["/membership/directory", {"status": 500, "body": {}}]])
    assert out["result"] == {"loading": False, "error": "Failed to load this Sakha's member roster.", "rows": 0}


# A scripted fetch for tests that need different answers to successive calls (the stub in
# _RUN_TEMPLATE answers by URL only): `seq` steps are consumed in order; every call is recorded.
_SEQ_FETCH = """
        const seq = %SEQ%;
        window.fetch = (url, opts = {}) => {
            calls.push({ url: String(url), method: opts.method || 'GET', body: opts.body || null,
                         headers: opts.headers || {} });
            const step = seq.shift() || { status: 404, body: {} };
            return Promise.resolve({
                ok: step.status >= 200 && step.status < 300, status: step.status,
                json: () => Promise.resolve(step.body),
                headers: { get: (n) => (step.headers || {})[n] || null },
            });
        };
"""


def _seq(steps: list) -> str:
    return _SEQ_FETCH.replace("%SEQ%", json.dumps(steps))


def _rec(pk, status, version, by="Marker One", sevi="SS9", at=None):
    return {"sangha_sevi_pk": pk, "attendance_status_code": status, "version": version,
            "marked_by_name": by, "marked_by_sangha_sevi_id": sevi, "marked_at": at or version,
            "weekly_sangha_puja_pk": "P1", "sangha_sevi_id": "SS-" + pk, "person_name": "Person " + pk,
            "home_organization_pk": "S1", "home_organization_name": "Home", "membership_type_code": "REGULAR"}


def test_submit_sends_only_the_dirty_rows_with_the_version_each_was_last_seen_at(register_page: Page):
    out = _run(register_page, _seq([{"status": 201, "body": {"records": [
        _rec("b", "ABSENT", "2026-01-01T10:05:00.123456+00:00"),
        _rec("c", "PRESENT", "2026-01-01T10:05:00.123456+00:00"),
    ], "total": 2}}]) + f"""
        let refreshed = 0;
        host._afterAttendanceSaved = () => {{ refreshed++; }};
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [
            host._attMarkRow({{ sangha_sevi_pk: 'a', organization_pk: 'S1' }}, null),                 // untouched, unmarked
            host._attMarkRow({{ sangha_sevi_pk: 'b', organization_pk: 'S1' }}, {json.dumps(_rec("b", "PRESENT", "2026-01-01T10:00:00.000001+00:00"))}),
            host._attMarkRow({{ sangha_sevi_pk: 'c', organization_pk: 'S1' }}, null),
            host._attMarkRow({{ sangha_sevi_pk: 'd', organization_pk: 'S1' }}, {json.dumps(_rec("d", "ABSENT", "2026-01-01T09:00:00+00:00"))}),  // untouched, marked
        ];
        host.attMarkSet(host.attMarkRows[1], 'ABSENT');   // changed an existing mark
        host.attMarkSet(host.attMarkRows[2], 'PRESENT');  // marked a new one
        host.attMarkSet(host.attMarkRows[3], 'ABSENT');   // set to what the server already has -> not dirty
        const before = host.attMarkDirtyCount;
        await host.submitMarkAttendance();
        const [b, c] = [host.attMarkRows[1], host.attMarkRows[2]];
        return {{ before, refreshed, open: host.attMarkPuja !== null, saving: host.attMarkSaving,
                  error: host.attMarkError, note: host.attMarkSavedNote, dirty: host.attMarkDirtyCount,
                  b: [b.attendance_status_code, b.ackVersion, b.dirty], c: [c.attendance_status_code, c.ackVersion] }};
    """)
    assert out["result"] == {
        "before": 2, "refreshed": 1, "open": True, "saving": False, "error": "", "note": "Saved 2 changes.",
        "dirty": 0, "b": ["ABSENT", "2026-01-01T10:05:00.123456+00:00", False],
        "c": ["PRESENT", "2026-01-01T10:05:00.123456+00:00"],
    }, "the panel must stay open after Save (live register) and rebaseline to the server's versions"
    [post] = [c for c in out["calls"] if c["method"] == "POST"]
    assert post["url"].endswith("/api/v1/attendance/pujas/P1/attendance")
    assert json.loads(post["body"]) == {
        "records": [
            {"sangha_sevi_pk": "b", "attendance_status_code": "ABSENT", "expected_version": "2026-01-01T10:00:00.000001+00:00"},
            {"sangha_sevi_pk": "c", "attendance_status_code": "PRESENT", "expected_version": None},
        ],
        "overwrite_sangha_sevi_pks": [],
    }, "untouched rows are never sent; expected_version is echoed verbatim (null = saw it unmarked)"


def test_saving_with_nothing_dirty_sends_nothing(register_page: Page):
    out = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [host._attMarkRow({{ sangha_sevi_pk: 'a', organization_pk: 'S1' }}, null)];
        await host.submitMarkAttendance();
        return host.attMarkSavedNote;
    """)
    assert out["result"] == "Nothing to save." and out["calls"] == []


_CONFLICT_409 = {"status": 409, "body": {"detail": {"message": "x", "conflicts": [{
    "sangha_sevi_pk": "b", "current_status_code": "ABSENT", "changed_by_name": "Other Marker",
    "changed_by_sangha_sevi_id": "SS7", "changed_at": "2026-01-01T10:32:00+00:00", "requested_status_code": "PRESENT"}]}}}


def _conflict_run(answer: str, follow_up: list):
    return _seq([_CONFLICT_409, *follow_up]) + f"""
        const dialogs = [];
        const realConfirm = NSSDialog.confirm;
        NSSDialog.confirm = async (msg, opts) => {{ dialogs.push({{ msg, opts }}); return {answer}; }};
        try {{
            host.attMarkPuja = {PUJA};
            host.attMarkRows = [
                host._attMarkRow({{ sangha_sevi_pk: 'a', organization_pk: 'S1', first_name: 'Asha' }}, null),
                host._attMarkRow({{ sangha_sevi_pk: 'b', organization_pk: 'S1', first_name: 'Bina' }}, null),
            ];
            host.attMarkSet(host.attMarkRows[0], 'PRESENT');
            host.attMarkSet(host.attMarkRows[1], 'PRESENT');
            await host.submitMarkAttendance();
            return {{ dialogs, rows: host.attMarkRows.map(r => [r.sangha_sevi_pk, r.attendance_status_code, r.dirty]),
                      error: host.attMarkError }};
        }} finally {{ NSSDialog.confirm = realConfirm; }}
    """


def test_a_409_names_who_changed_it_and_overwrite_resends_with_confirmation(register_page: Page):
    out = _run(register_page, _conflict_run("true", [{"status": 201, "body": {"records": [
        _rec("a", "PRESENT", "2026-01-01T10:40:00+00:00"), _rec("b", "PRESENT", "2026-01-01T10:40:00+00:00")], "total": 2}}]))
    [dialog] = out["result"]["dialogs"]
    assert "Bina" in dialog["msg"] and "Other Marker" in dialog["msg"] and "Absent" in dialog["msg"]
    assert dialog["opts"]["confirmText"] == "Overwrite these" and dialog["opts"]["cancelText"] == "Keep theirs"
    posts = [json.loads(c["body"]) for c in out["calls"] if c["method"] == "POST"]
    assert len(posts) == 2 and posts[0]["overwrite_sangha_sevi_pks"] == []
    assert posts[1]["overwrite_sangha_sevi_pks"] == ["b"] and len(posts[1]["records"]) == 2
    assert out["result"]["rows"] == [["a", "PRESENT", False], ["b", "PRESENT", False]]


def test_keep_theirs_drops_only_the_conflicting_edit_and_resends_the_rest(register_page: Page):
    out = _run(register_page, _conflict_run("false", [{"status": 201, "body": {"records": [
        _rec("a", "PRESENT", "2026-01-01T10:40:00+00:00")], "total": 1}}]))
    posts = [json.loads(c["body"]) for c in out["calls"] if c["method"] == "POST"]
    assert [r["sangha_sevi_pk"] for r in posts[1]["records"]] == ["a"] and posts[1]["overwrite_sangha_sevi_pks"] == []
    assert out["result"]["rows"] == [["a", "PRESENT", False], ["b", "ABSENT", False]], "b shows the other marker's mark"


def test_a_dirty_row_whose_server_state_changed_is_flagged_and_never_silently_overwritten(register_page: Page):
    out = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [
            host._attMarkRow({{ sangha_sevi_pk: 'a', organization_pk: 'S1' }}, null),
            host._attMarkRow({{ sangha_sevi_pk: 'b', organization_pk: 'S1' }}, null),
        ];
        host.attMarkSet(host.attMarkRows[0], 'PRESENT');                    // a: my unsaved edit
        await host._attApplyLive({{ server_time: 'T', marked_count: 2, changed: [
            {{ sangha_sevi_pk: 'a', attendance_status_code: 'ABSENT', version: '2026-01-01T10:32:00+00:00',
               marked_by_name: 'Other Marker', marked_by_sangha_sevi_id: 'SS7', marked_at: '2026-01-01T10:32:00+00:00', is_active: true }},
            {{ sangha_sevi_pk: 'b', attendance_status_code: 'PRESENT', version: '2026-01-01T10:33:00+00:00',
               marked_by_name: 'Other Marker', marked_by_sangha_sevi_id: 'SS7', marked_at: '2026-01-01T10:33:00+00:00', is_active: true }},
        ] }});
        const [a, b] = host.attMarkRows;
        const first = {{ a: [a.attendance_status_code, a.dirty, host.attRowStale(a)], b: [b.attendance_status_code, b.dirty, b.flash, host.attRowStale(b)],
                         hint: host.attRowHint(a).startsWith('Other Marker marked Absent at') }};
        // the same payload again (server overlap) and an older one change nothing
        await host._attApplyLive({{ changed: [{{ sangha_sevi_pk: 'b', attendance_status_code: 'ABSENT', version: '2026-01-01T10:31:00+00:00', is_active: true }}] }});
        first.bAfterStale = b.attendance_status_code;
        // someone else saves exactly what I wanted -> no longer dirty
        host.attMarkSet(b, 'ABSENT');
        await host._attApplyLive({{ changed: [{{ sangha_sevi_pk: 'b', attendance_status_code: 'ABSENT', version: '2026-01-01T10:40:00+00:00', is_active: true }}] }});
        first.bConverged = [b.dirty, b.ackVersion];
        return first;
    """)["result"]
    assert out["a"] == ["PRESENT", True, True], "local edit kept, flagged stale"
    assert out["b"] == ["PRESENT", False, True, False], "untouched row updates in place and flashes"
    assert out["hint"] is True
    assert out["bAfterStale"] == "PRESENT"
    assert out["bConverged"] == [False, "2026-01-01T10:40:00+00:00"]


def test_live_removal_unmarks_an_untouched_row_and_unknown_members_are_fetched(register_page: Page):
    out = _run(register_page, _seq([{"status": 200, "body": {"records": [
        _rec("z", "PRESENT", "2026-01-01T10:50:00+00:00")]}}]) + f"""
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [host._attMarkRow({{ sangha_sevi_pk: 'a', organization_pk: 'S1' }}, {json.dumps(_rec("a", "PRESENT", "2026-01-01T10:00:00+00:00"))})];
        await host._attApplyLive({{ changed: [
            {{ sangha_sevi_pk: 'a', attendance_status_code: 'PRESENT', version: '2026-01-01T10:45:00+00:00', is_active: false }},
            {{ sangha_sevi_pk: 'z', attendance_status_code: 'PRESENT', version: '2026-01-01T10:50:00+00:00', is_active: true }},
        ] }});
        return {{ rows: host.attMarkRows.map(r => [r.sangha_sevi_pk, r.attendance_status_code]), counts: host.attMarkProgressText }};
    """)["result"]
    assert out == {"rows": [["a", None], ["z", "PRESENT"]], "counts": "1 of 2 marked"}


def test_poll_policy_constants_and_delays(register_page: Page):
    out = _run(register_page, """
        const P = NSSAttendanceRegister.LIVE_POLL;
        const d = (f, ms, ra) => host._attPollDelay(f, ms, ra);
        return { P: { a: P.ACTIVE_MS, i: P.IDLE_MS, after: P.IDLE_AFTER_MS, back: [...P.BACKOFF_MS] },
                 active: d(0, 0), justUnder: d(0, 59999), idle: d(0, 60000),
                 backoff: [1, 2, 3, 4, 5, 9].map(n => d(n, 0)),
                 retryAfterWins: d(1, 0, 20000), shorterRetryAfterIgnored: d(2, 0, 1000) };
    """)["result"]
    assert out["P"] == {"a": 2000, "i": 10000, "after": 60000, "back": [4000, 8000, 16000, 30000]}
    assert (out["active"], out["justUnder"], out["idle"]) == (2000, 2000, 10000)
    assert out["backoff"] == [4000, 8000, 16000, 30000, 30000, 30000]
    assert (out["retryAfterWins"], out["shorterRetryAfterIgnored"]) == (20000, 8000)


def test_activity_returns_the_poll_to_the_fast_cadence(register_page: Page):
    out = _run(register_page, """
        host._attPollActivityAt = Date.now() - 120000;           // long idle
        const idle = host._attPollDelay(0, Date.now() - host._attPollActivityAt, 0);
        host._attTouch();                                        // a local edit / remote change / save
        const fast = host._attPollDelay(0, Date.now() - host._attPollActivityAt, 0);
        return { idle, fast };
    """)["result"]
    assert out == {"idle": 10000, "fast": 2000}


def test_a_hidden_register_tab_makes_no_request_and_rechecks_slowly(register_page: Page):
    out = _run(register_page, _seq([{"status": 200, "body": {"server_time": "2026-01-01T10:00:00+00:00", "marked_count": 0, "changed": []}}]) + f"""
        host.attMarkPuja = {PUJA};
        host._attPolling = true;
        host._attRegisterShown = () => false;                    // the host tab is not on screen
        const gen = host._attPollGen;
        await host._attPollOnce(gen);
        const timerSet = host._attPollTimer !== null;
        clearTimeout(host._attPollTimer);
        host._attStopPolling();
        return {{ timerSet }};
    """)
    assert out["result"] == {"timerSet": True}
    assert [c for c in out["calls"] if "/live" in c["url"]] == []


def test_a_429_with_retry_after_waits_at_least_that_long(register_page: Page):
    out = _run(register_page, _seq([{"status": 429, "headers": {"Retry-After": "25"}, "body": {}}]) + f"""
        host.attMarkPuja = {PUJA};
        host._attPolling = true;
        const gen = host._attPollGen;
        await host._attPollOnce(gen);
        const r = [host.attLiveReconnecting, host._attPollFailures, host._attPollRetryAfterMs,
                   host._attPollDelay(host._attPollFailures, 0, host._attPollRetryAfterMs)];
        clearTimeout(host._attPollTimer);
        host._attStopPolling();
        return r;
    """)["result"]
    assert out == [True, 1, 25000, 25000]


def test_a_poll_sends_the_cursor_and_etag_handles_304_and_flags_reconnecting(register_page: Page):
    out = _run(register_page, _seq([
        {"status": 200, "headers": {"ETag": '"e1"'}, "body": {"server_time": "2026-01-01T10:00:00+00:00", "marked_count": 0, "changed": []}},
        {"status": 304, "body": {}},
        {"status": 500, "body": {}},
    ]) + f"""
        host.attMarkPuja = {PUJA};
        host._attPolling = true;                       // polling "started", but drive the ticks by hand
        const gen = host._attPollGen;
        await host._attPollOnce(gen);  const afterFirst = [host._attPollSince, host._attPollEtag];
        clearTimeout(host._attPollTimer);
        await host._attPollOnce(gen);  const after304 = host.attLiveReconnecting;
        clearTimeout(host._attPollTimer);
        await host._attPollOnce(gen);  const afterError = [host.attLiveReconnecting, host._attPollFailures];
        clearTimeout(host._attPollTimer);
        host._attStopPolling();
        return {{ afterFirst, after304, afterError }};
    """)
    assert out["result"] == {"afterFirst": ["2026-01-01T10:00:00+00:00", '"e1"'], "after304": False, "afterError": [True, 1]}
    live = [c for c in out["calls"] if "/live" in c["url"]]
    assert len(live) == 3 and "since=" not in live[0]["url"] and "If-None-Match" not in live[0]["headers"]
    assert "since=2026-01-01T10%3A00%3A00%2B00%3A00" in live[1]["url"] and live[1]["headers"]["If-None-Match"] == '"e1"'


def test_filter_chip_not_marked_lists_only_unmarked_rows(register_page: Page):
    out = _run(register_page, """
        host.attMarkRows = [{ sangha_sevi_pk: 'a', attendance_status_code: null }, { sangha_sevi_pk: 'b', attendance_status_code: 'ABSENT' }];
        host.attMarkFilter = 'NOT_MARKED';
        return [host.attMarkVisibleRows().map(r => r.sangha_sevi_pk), host.attMarkProgressText, host.attMarkProgressPercent];
    """)["result"]
    assert out == [["a"], "1 of 2 marked", 50]


def test_a_rejected_submit_keeps_the_register_open_and_shows_the_servers_reason(register_page: Page):
    out = _run(register_page, f"""
        let refreshed = 0;
        host._afterAttendanceSaved = () => {{ refreshed++; }};
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [{{ sangha_sevi_pk: 'a', attendance_status_code: 'PRESENT', dirty: true }}];
        await host.submitMarkAttendance();
        return {{ refreshed, open: host.attMarkPuja !== null, rows: host.attMarkRows.length,
                  saving: host.attMarkSaving, error: host.attMarkError }};
    """, routes=[["/attendance/pujas/P1/attendance", {"status": 403, "body": {
        "detail": "You can only mark attendance for this Sakha within your admin scope."}}]])
    assert out["result"] == {"refreshed": 0, "open": True, "rows": 1, "saving": False,
                             "error": "You can only mark attendance for this Sakha within your admin scope."}


def test_submit_without_an_open_puja_does_nothing(register_page: Page):
    out = _run(register_page, "await host.submitMarkAttendance(); return host.attMarkSaving;")
    assert out["result"] is False and out["calls"] == []


def test_closing_the_register_clears_rows_and_search(register_page: Page):
    out = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [{{ sangha_sevi_pk: 'a' }}];
        host.attMarkSearchQuery = 'xx';
        host.attMarkSearchResults = [{{ sangha_sevi_pk: 'z' }}];
        host.closeMarkAttendance();
        return [host.attMarkPuja, host.attMarkRows.length, host.attMarkSearchQuery, host.attMarkSearchResults.length];
    """)["result"]
    assert out == [None, 0, "", 0]
