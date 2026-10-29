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
    start = admin_html.index("""<template x-if="canViewAttendance">""")
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
        assigned = set(re.findall(r"row\.attendance_status_code = '([A-Z_]+)'", html))
        bulk = set(re.findall(r"attMarkSetAll\('([A-Z_]+)'\)", html))
        assert assigned == accepted and bulk == accepted


def test_mark_panel_has_filter_chips_for_every_status(admin_html: str):
    panel = _panel(admin_html, "attPujas")
    for code in ("ALL", "PRESENT", "ABSENT", "EXCUSED_ABSENCE"):
        assert f"attMarkFilter = '{code}'" in panel


def test_mark_panel_separates_home_members_from_darshak_visitors(admin_html: str, dashboard_html: str):
    for html in (admin_html, dashboard_html):
        assert "attMarkHomeRows()" in html and "attMarkDarshakRows()" in html


def test_submit_button_is_disabled_while_saving(admin_html: str, dashboard_html: str):
    for html in (admin_html, dashboard_html):
        assert re.search(r""":disabled="attMarkSaving" @click="submitMarkAttendance\(\)\"""", html)


def test_search_to_add_block_is_identical_in_admin_and_dashboard(admin_html: str, dashboard_html: str):
    """The block is hand-copied (no include mechanism); the markers say it MUST stay identical."""
    def block(html: str) -> str:
        m = re.search(r"<!-- ATT-MARK-SEARCH:START.*?-->(.*?)<!-- ATT-MARK-SEARCH:END -->", html, re.DOTALL)
        assert m, "ATT-MARK-SEARCH markers missing."
        return re.sub(r"\s+", " ", m.group(1)).strip()

    assert block(admin_html) == block(dashboard_html)


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
        "/api/v1/attendance/pujas", "/api/v1/attendance/pujas/{}/attendance", "/api/v1/attendance/records",
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
    assert out["c"] == {"present": 3, "absent": 1, "excused": 2, "total": 6, "percentage": 75}
    assert out["onlyExcused"] is None


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


def test_row_builder_defaults_to_present_and_joins_the_name(register_page: Page):
    row = _run(register_page, f"""
        host.attMarkPuja = {PUJA};
        return host._attMarkRow({{ sangha_sevi_pk: 'a', sangha_sevi_id: 'SS9', organization_pk: 'S1',
                                   first_name: 'Asha', middle_name: null, last_name: 'Devi',
                                   membership_type_code: 'REGULAR', local_sakha_erp_id: 'ESS7' }}, null);
    """)["result"]
    assert row["attendance_status_code"] == "PRESENT" and row["already_marked"] is False
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
        return {{ loading: host.attMarkLoading, error: host.attMarkError,
                  rows: host.attMarkRows.map(r => [r.sangha_sevi_pk, r.attendance_status_code, r.already_marked]) }};
    """, routes=[["/membership/directory", {"status": 200, "body": _ROSTER}],
                 ["/attendance/records", {"status": 200, "body": _RECORDS}]])
    assert out["result"] == {"loading": False, "error": "",
                             "rows": [["a", "PRESENT", False], ["b", "ABSENT", True]]}
    urls = [c["url"] for c in out["calls"]]
    assert any("/api/v1/membership/directory?" in u and "organization_pk=S1" in u for u in urls)
    assert any("/api/v1/attendance/records?" in u and "organization_pk=S1" in u
               and "weekly_sangha_puja_pk=P1" in u and "page_size=200" in u for u in urls)


def test_the_records_request_is_within_the_apis_page_size_cap(register_page: Page):
    out = _run(register_page, f"await host.openMarkAttendance({PUJA}); return null;",
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


def test_submit_posts_one_status_per_row_closes_the_panel_and_runs_the_host_hook(register_page: Page):
    out = _run(register_page, f"""
        let refreshed = 0;
        host._afterAttendanceSaved = () => {{ refreshed++; }};
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [
            {{ sangha_sevi_pk: 'a', attendance_status_code: 'PRESENT', person_name: 'ignored' }},
            {{ sangha_sevi_pk: 'b', attendance_status_code: 'EXCUSED_ABSENCE', is_darshak: true }},
        ];
        await host.submitMarkAttendance();
        return {{ refreshed, open: host.attMarkPuja !== null, saving: host.attMarkSaving, error: host.attMarkError }};
    """, routes=[["/attendance/pujas/P1/attendance", {"status": 201, "body": {"records": [], "total": 0}}]])
    assert out["result"] == {"refreshed": 1, "open": False, "saving": False, "error": ""}
    [post] = [c for c in out["calls"] if c["method"] == "POST"]
    assert post["url"].endswith("/api/v1/attendance/pujas/P1/attendance")
    assert json.loads(post["body"]) == {"records": [
        {"sangha_sevi_pk": "a", "attendance_status_code": "PRESENT"},
        {"sangha_sevi_pk": "b", "attendance_status_code": "EXCUSED_ABSENCE"},
    ]}


def test_a_rejected_submit_keeps_the_register_open_and_shows_the_servers_reason(register_page: Page):
    out = _run(register_page, f"""
        let refreshed = 0;
        host._afterAttendanceSaved = () => {{ refreshed++; }};
        host.attMarkPuja = {PUJA};
        host.attMarkRows = [{{ sangha_sevi_pk: 'a', attendance_status_code: 'PRESENT' }}];
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
