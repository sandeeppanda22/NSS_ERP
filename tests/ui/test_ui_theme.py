"""The shared look (frontend/assets/css/nss-theme.css) - DB-free source checks. Nothing here proves how it LOOKS; open the pages for that."""

import re
from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend"
THEME = (FRONT / "assets/css/nss-theme.css").read_text()
PAGES = {name: (FRONT / name).read_text() for name in ("admin.html", "dashboard.html")}


def test_the_admin_console_and_the_member_dashboard_use_it_and_load_it_last():
    for name, html in PAGES.items():
        assert re.search(r"<body class=\"nss-theme\"", html), name
        links = re.findall(r'<link rel="stylesheet" href="(/assets/css/[^"]+)"', html)
        assert links[-1] == "/assets/css/nss-theme.css", (name, links)      # after nss-layout.css, so it can restyle what that defines
        assert links.index("/assets/css/nss-theme.css") > links.index("/assets/css/nss-layout.css")


def test_every_rule_is_scoped_under_the_body_class():
    css = re.sub(r"/\*.*?\*/", "", THEME, flags=re.S)
    selectors = [s.strip() for block in re.findall(r"([^{}]+)\{", css) for s in block.split(",") if s.strip()]
    assert selectors and all(s.startswith(".nss-theme ") for s in selectors), [s for s in selectors if not s.startswith(".nss-theme ")]


def test_it_out_ranks_the_old_styles_without_important():
    assert "!important" not in re.sub(r"/\*.*?\*/", "", THEME, flags=re.S)         # the comments may talk about it


def test_the_outlined_cards_leave_the_state_coloured_pranami_cards_alone():
    assert '.nss-theme .data-card:not([class*="contrib-card"])' in THEME


def test_the_directory_toolbars_stay_a_grid_whatever_the_older_search_bar_rule_says():
    assert ".nss-theme .dir-toolbar {" in THEME and "display: grid;" in THEME.split(".nss-theme .dir-toolbar {")[1].split("}")[0]


def test_the_login_and_register_pages_are_untouched():
    for name in ("login.html", "register.html"):
        assert "nss-theme" not in (FRONT / name).read_text(), name


JS = FRONT / "assets/js"


def _labels(js_text: str, name: str) -> set[str]:
    block = js_text.split(f"const {name} = {{")[1].split("\n};")[0]
    return set(re.findall(r"^\s*(\w+):", block, re.M)) | set(re.findall(r",\s*(\w+):\s*\"", block))


def test_every_admin_tab_has_a_top_banner_title_and_both_banners_read_the_one_list():
    admin_js, html = (JS / "admin.js").read_text(), PAGES["admin.html"]
    labels = _labels(admin_js, "ADMIN_TAB_LABELS")
    views = set(re.findall(r"x-show=\"activeTab === '(\w+)'", html)) | set(re.findall(r"activeTab = '(\w+)'", html))
    assert not (views - labels - {"orgDashboard"}), sorted(views - labels - {"orgDashboard"})
    assert html.count('x-text="currentTabLabel"') == 2 and "})[activeTab]" not in html          # no second copy of the map
    assert 'if (this.activeTab === "orgDashboard") return this.viewingOrgDashboardLabel;' in admin_js


def test_every_member_dashboard_tab_has_a_top_banner_title():
    dash_js, html = (JS / "dashboard.js").read_text(), PAGES["dashboard.html"]
    labels = _labels(dash_js, "TAB_LABELS")
    tabs = set(re.findall(r"switchTab\('(\w+)'\)", html))
    special = {"orgDashboard", "advisoryBoard"}                     # titled by currentTabLabel itself
    assert not (tabs - labels - special), sorted(tabs - labels - special)


def test_member_directory_count_tiles_use_the_server_counts_and_filter_on_click():
    """The tiles come from `status_counts` of GET /membership/members and a tile click re-queries with that status."""
    root = Path(__file__).resolve().parents[2] / "frontend"
    html = (root / "admin.html").read_text(encoding="utf-8")
    js = (root / "assets/js/admin.js").read_text(encoding="utf-8")
    assert 'x-for="c in mdStatusTiles"' in html and 'mdPickStatus(c.status_code)' in html
    assert "this.mdStatusCounts = data.status_counts || [];" in js
    assert "get mdAllStatusesTotal()" in js and "mdPickStatus(code)" in js


def test_a_sakha_scoped_admin_sees_the_sakha_name_in_the_create_person_and_member_forms():
    """Owner 2026-11-20: the locked Sakha is shown BY NAME in a read-only box (not a select that read "Select..." until its options loaded)."""
    root = Path(__file__).resolve().parents[2] / "frontend"
    html = (root / "admin.html").read_text(encoding="utf-8")
    js = (root / "assets/js/admin.js").read_text(encoding="utf-8")
    assert html.count(':value="sakhaLockedName" disabled x-show="sakhaScope.mode === \'locked\'"') == 2          # Create Person & Account, Create Sangha Sevi
    for form in ("createForm", "ssForm"):
        assert f'<select class="nss-select" x-model="{form}.organization_pk" x-show="sakhaScope.mode !== \'locked\'">' in html
    assert "get sakhaLockedName()" in js and "this.sakhaScope.auto_select_pk" in js
