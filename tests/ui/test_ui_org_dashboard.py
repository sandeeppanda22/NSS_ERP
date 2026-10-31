"""
UI tests for the per-organization-tier dashboard (org-dashboard.js).

One Alpine component (`orgDashboardTab()`) renders six layouts — Sakha,
Anchalika, Zilla, Kendra, Patha Chakra, Mahila Sangha — chosen by the viewed
org's `organization_type_code`. It is embedded identically as a nested
`x-data` scope inside both host pages' own tab shell:

  * admin.html    — `<template x-if="activeTab === 'orgDashboard' && viewingOrgPk">`
  * dashboard.html — same tab body, host var is `tab` not `activeTab`

Both hosts wire the same `openOrgDashboard(orgPk)` / `viewingOrgPk` /
`dashboardOrgsFor(typeCode)` / `viewingOrgDashboardLabel` contract so the
nested component's markup and behaviour are identical either side — this is
the coverage-gap audit's "org dashboards + switcher" item.

Verified selectors/wiring (frontend/assets/js/org-dashboard.js,
frontend/admin.html, frontend/dashboard.html):
  * host state    : `viewingOrgPk` (null until set), `openOrgDashboard(orgPk)`
                    nulls it then sets it next tick (forces remount)
  * tier getters  : isSakha / isChildOverviewTier (Anchalika+Zilla) / isKendra
                    / isPathaChakra / isMahila — exactly the six ORGANIZATIONAL
                    role_master rows (SOL-ADMIN-004 §8.7), matched 1:1 against
                    each host's `x-show="is...."` tier blocks
  * entry point   : "View Dashboard" button (admin.html Organizations tab,
                    `@click="openOrgDashboard(org.organization_pk)"`)
  * switcher      : `<select id="orgSwitcherSelect">` in admin.html,
                    `id="orgSwitcherSelectDash"` in dashboard.html (the two
                    ids differ — verified, not a typo), shown only when
                    `dashboardOrgsFor(typeCode).length > 1`; each `<option>`
                    is a same-type org in the admin's scope; `@change` calls
                    `openOrgDashboard($event.target.value)`. admin.html's
                    option label appends " (CODE)"; dashboard.html's does not.
  * Sakha stats   : "Members" / "Families" / "Renewals Due" (badge-muted "Not
                    tracked yet") / "Attendance" (same) stat tiles; Darshak
                    card badge; "Recent Members" table
  * Anchalika/Zilla: "Sakha Sanghas" / "Total Members" / "Families" tiles,
                    Zilla-only "Renewals Due", Anchalika-only "Mahila Sanghas";
                    child-org table rows are `link link-hover` buttons that
                    themselves call `openOrgDashboard(c.organization_pk)`
                    (drill-down)

Two of the six tiers, and the switcher, require an admin whose scope actually
covers more than one org of a type to observe non-trivial states — these
browser tests are precondition-guarded and skip when the fixture DB doesn't
have that shape, per the family-management test's pattern. The tier-routing
and host-parity checks below need no browser at all.

Requires a live server + Postgres for the browser tests
(BASE_URL http://127.0.0.1:8001); the source-parity tests run anywhere.
"""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.ui.conftest import wait_for_alpine, click_nav_item

pytestmark = pytest.mark.ui

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
ORG_DASHBOARD_JS = FRONTEND / "assets" / "js" / "org-dashboard.js"

# The six ORGANIZATIONAL role_master tiers (SOL-ADMIN-004 §8.7), each with
# exactly one dashboard. Anchalika and Zilla share one x-show block
# (isChildOverviewTier), so 6 tiers map to 5 distinct getters.
TIER_GETTERS = [
    "isSakha",
    "isChildOverviewTier",  # covers Anchalika + Zilla
    "isKendra",
    "isPathaChakra",
    "isMahila",
]


def _read(path: Path) -> str:
    assert path.exists(), f"expected file missing: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


# ── Source-parity: tier routing is identical in both host pages ────────────


def test_org_dashboard_js_defines_all_tier_getters():
    js = _read(ORG_DASHBOARD_JS)
    for getter in TIER_GETTERS + ["isAnchalika", "isZilla", "isCentralMahila"]:
        assert re.search(rf"get {getter}\(\)", js), (
            f"org-dashboard.js no longer defines get {getter}() — "
            "a host's x-show tier block would silently stop matching"
        )


@pytest.mark.parametrize("host", ["admin.html", "dashboard.html"])
@pytest.mark.parametrize("getter", TIER_GETTERS)
def test_host_has_matching_tier_block(host, getter):
    """
    Every tier getter org-dashboard.js exposes has a corresponding
    `x-show="<getter>"` block in each host page — the two pages embed the
    same component and must stay in lockstep (this is what "one component,
    six layouts" means structurally).
    """
    html = _read(FRONTEND / host)
    assert re.search(rf'x-show="{getter}"', html), (
        f"{host} has no x-show=\"{getter}\" block — {getter} tier has no "
        "rendered layout in this host, so an org of that type would show a "
        "blank dashboard"
    )


# The three tiers whose "Total Members" is the home-based Parichay Patra +
# Darshak split served by /organizations/{pk}/stats. The Sakha tier is
# deliberately excluded: it uses sakhaTotalMembers, which ALSO adds visiting
# card-holders from other Sakhas (and its own per-Sakha tiles/labels).
SPLIT_TIERS = ["isChildOverviewTier", "isKendra", "isPathaChakra"]


@pytest.mark.parametrize("host", ["admin.html", "dashboard.html"])
@pytest.mark.parametrize("field", ["parichayPatraTotal", "darshakTotal"])
def test_split_tiles_present_in_host(host, field):
    """
    Anchalika/Zilla, Kendra and Patha Chakra each surface the Parichay Patra
    and Darshak figures. Asserted on the bound state field rather than the
    tile caption, so a wording change doesn't fail the test but dropping the
    binding does.
    """
    html = _read(FRONTEND / host)
    assert html.count(f"statNum({field})") >= len(SPLIT_TIERS), (
        f'{host} binds statNum({field}) fewer than {len(SPLIT_TIERS)} times — '
        "one of the Anchalika/Zilla, Kendra or Patha Chakra tiles lost it"
    )


@pytest.mark.parametrize("host", ["admin.html", "dashboard.html"])
def test_split_tiers_use_reconciling_member_total(host):
    """
    The three split tiers show orgMemberTotal (= Parichay Patra + Darshaks
    from the same /stats payload), not the raw childStats sum, so the headline
    figure always equals the two tiles beside it.
    """
    html = _read(FRONTEND / host)
    assert html.count('x-text="orgMemberTotal"') >= len(SPLIT_TIERS), (
        f"{host} does not bind orgMemberTotal in all {len(SPLIT_TIERS)} split "
        "tiers — a tier is back to a total that can disagree with its own tiles"
    )


def test_org_dashboard_js_loads_split_for_every_split_tier():
    """
    Every split tier actually fetches the figures it renders. Patha Chakra had
    no tier fetch at all before these tiles existed, so without this the tiles
    would silently render "—" forever.
    """
    js = _read(ORG_DASHBOARD_JS)
    for getter in SPLIT_TIERS:
        assert re.search(rf"if \(this\.{getter}\) return this\._load\w+\(\);", js), (
            f"_loadTierData() no longer routes {getter} to a loader — its "
            "Parichay Patra / Darshak tiles would never be populated"
        )
    for loader in ["_loadChildOrgData", "_loadKendraData", "_loadPathaChakraData"]:
        body = js.split(f"async {loader}(")[1].split("\n        },")[0]
        for field in ["parichay_patra_holders", "darshaks"]:
            assert field in body, f"{loader}() no longer reads statsRes.{field}"


@pytest.mark.parametrize("host", ["admin.html", "dashboard.html"])
def test_host_wires_org_dashboard_tab(host):
    """Each host mounts the shared component with init(viewingOrgPk)."""
    html = _read(FRONTEND / host)
    assert 'x-data="orgDashboardTab()"' in html, f"{host} does not mount orgDashboardTab()"
    assert 'x-init="init(viewingOrgPk)"' in html, (
        f"{host} does not initialize orgDashboardTab() with viewingOrgPk"
    )


# The two hosts use different switcher ids (dashboard.html appends "Dash" to
# avoid an id collision if both host shells were ever composed together) —
# verified in source, not a guess.
SWITCHER_ID = {"admin.html": "orgSwitcherSelect", "dashboard.html": "orgSwitcherSelectDash"}


@pytest.mark.parametrize("host", ["admin.html", "dashboard.html"])
def test_host_has_org_switcher(host):
    """Both hosts render the same-org-type switcher, gated on >1 option."""
    html = _read(FRONTEND / host)
    assert f'id="{SWITCHER_ID[host]}"' in html, f"{host} missing org switcher <select>"
    assert '@change="openOrgDashboard($event.target.value)"' in html, (
        f"{host} switcher does not call openOrgDashboard() on change"
    )
    assert "dashboardOrgsFor(org?.organization_type_code).length > 1" in html, (
        f"{host} switcher is not gated on having more than one org to switch to"
    )


# ── Browser: reaching the dashboard via the real entry points ──────────────


@pytest.fixture
def org_dashboard(admin_page, base_url):
    """
    admin_page (SS1) on the admin Organizations tab, ready to drill into a
    dashboard via the real "View Dashboard" button.
    """
    admin_page.goto(f"{base_url}/admin")
    wait_for_alpine(admin_page)
    click_nav_item(admin_page, "Organizations")
    wait_for_alpine(admin_page)
    return admin_page


def test_view_dashboard_button_opens_org_dashboard(org_dashboard):
    """
    Clicking "View Dashboard" on an organization row switches to the
    orgDashboard tab and renders that org's tier layout (not the loading
    spinner / error state).
    """
    page = org_dashboard
    trigger = page.get_by_role("button", name="View Dashboard")
    if trigger.count() == 0:
        pytest.skip("no organizations visible in this admin's scope to drill into")
    trigger.first.click()
    wait_for_alpine(page)
    expect(page.locator("[x-show='loading']")).to_be_hidden(timeout=10_000)
    # admin.html carries one .alert-error container per panel (8 in total), so a
    # bare locator would trip strict mode. Assert none of them is showing.
    errors = page.locator(".alert-error")
    for i in range(errors.count()):
        expect(errors.nth(i)).to_be_hidden()
    # One of the six tier blocks must be showing; heading text proves it
    # rendered real data, not a blank/errored mount.
    heading = page.locator("h1.text-2xl.font-bold").first
    expect(heading).to_be_visible(timeout=10_000)
    assert heading.inner_text().strip(), "org dashboard heading rendered empty"


def test_org_switcher_present_only_with_multiple_same_type_orgs(org_dashboard):
    """
    The switcher select only renders when this admin's scope covers more
    than one organization of the viewed type — otherwise it's absent (not
    just hidden with one option), per `dashboardOrgsFor(...).length > 1`.
    """
    page = org_dashboard
    trigger = page.get_by_role("button", name="View Dashboard")
    if trigger.count() == 0:
        pytest.skip("no organizations visible in this admin's scope to drill into")
    trigger.first.click()
    wait_for_alpine(page)
    switcher = page.locator("#orgSwitcherSelect")
    if switcher.count() == 0:
        pytest.skip("admin scope has only one org of this type — switcher correctly absent")
    options = switcher.locator("option")
    assert options.count() > 1, (
        "switcher rendered with <=1 option — should have been absent instead "
        "(dashboardOrgsFor gate)"
    )
    count_label = page.locator(".org-switcher-count")
    expect(count_label).to_be_visible()
    assert "in your scope" in count_label.inner_text()


def test_switching_org_reloads_dashboard_for_new_org(org_dashboard):
    """Selecting a different same-type org in the switcher re-renders for it."""
    page = org_dashboard
    trigger = page.get_by_role("button", name="View Dashboard")
    if trigger.count() == 0:
        pytest.skip("no organizations visible in this admin's scope to drill into")
    trigger.first.click()
    wait_for_alpine(page)
    switcher = page.locator("#orgSwitcherSelect")
    if switcher.count() == 0:
        pytest.skip("admin scope has only one org of this type — nothing to switch between")
    heading_before = page.locator("h1.text-2xl.font-bold").first.inner_text()
    options = switcher.locator("option")
    values = [options.nth(i).get_attribute("value") for i in range(options.count())]
    current = switcher.input_value()
    other = next((v for v in values if v != current), None)
    if other is None:
        pytest.skip("switcher has no second distinct option to select")
    switcher.select_option(other)
    wait_for_alpine(page)
    expect(page.locator("[x-show='loading']")).to_be_hidden(timeout=10_000)
    heading_after = page.locator("h1.text-2xl.font-bold").first.inner_text()
    assert heading_after != heading_before, (
        "dashboard heading unchanged after switching org — remount did not occur"
    )


def test_child_org_drilldown_link_reopens_dashboard(org_dashboard):
    """
    In the Anchalika/Zilla/Kendra child-org table, a Sakha name is a
    link-style button that calls openOrgDashboard(c.organization_pk) —
    clicking it drills further down into that child's own dashboard.
    """
    page = org_dashboard
    trigger = page.get_by_role("button", name="View Dashboard")
    if trigger.count() == 0:
        pytest.skip("no organizations visible in this admin's scope to drill into")
    trigger.first.click()
    wait_for_alpine(page)
    drilldown_links = page.locator("table .link.link-hover")
    if drilldown_links.count() == 0:
        pytest.skip("viewed org has no child-org table rows to drill into (leaf/Sakha tier, or empty)")
    child_name = drilldown_links.first.inner_text()
    drilldown_links.first.click()
    wait_for_alpine(page)
    expect(page.locator("[x-show='loading']")).to_be_hidden(timeout=10_000)
    heading = page.locator("h1.text-2xl.font-bold").first
    expect(heading).to_be_visible(timeout=10_000)
    assert child_name in heading.inner_text(), (
        "drilling into a child org did not land on that child's own dashboard"
    )


# ── Tier arithmetic: Sakha and Mahila ──────────────────────────────────────
#
# The three "split" tiers above get their figures straight from /stats, so
# source parity is enough. The Sakha tier instead DERIVES four numbers in the
# browser, and the Mahila tier deliberately derives none. Both were asserted
# only structurally (the getter exists, the host has a block) — nothing checked
# that the arithmetic is right, which is where a double-counted Darshak would
# hide. orgDashboardTab() is a plain global factory whose getters can be driven
# directly with synthetic values.


@pytest.fixture
def tier_component(page, base_url):
    """
    A page where the orgDashboardTab() factory is loaded.

    These are pure-logic tests, so they deliberately do NOT log in: /login is
    public and already loads nss-config.js and auth.js (the only globals the
    getters touch), and org-dashboard.js is a static asset that just defines the
    factory. Skipping the login keeps them independent of session state and off
    the single-worker server's bcrypt path, which is what made an admin_page
    fixture flake here.
    """
    page.goto(f"{base_url}/login", wait_until="load", timeout=30_000)
    page.add_script_tag(url="/assets/js/org-dashboard.js")
    page.wait_for_function(
        "() => typeof orgDashboardTab === 'function'", timeout=15_000
    )
    return page


_SAKHA_GETTERS = """
({ memberTotal, homeProbationary, visiting }) => {
    const c = orgDashboardTab();
    c.org = { organization_type_code: 'SAKHA_SANGHA', organization_pk: 1 };
    c.sakhaMemberTotal = memberTotal;
    c.darshak = {
        home_probationary_count: homeProbationary,
        attending_from_other_sakha_count: visiting,
    };
    return {
        isSakha: c.isSakha,
        parichay: c.parichayPatraHolderCount,
        visiting: c.visitingDarshakCount,
        darshaks: c.sakhaDarshakTotal,
        total: c.sakhaTotalMembers,
        rendered: c.statNum(c.sakhaTotalMembers),
    };
}
"""


class TestSakhaTierArithmetic:

    def test_parichay_holders_are_members_minus_home_darshaks(self, tier_component):
        """
        /membership/members?org_code= counts every home member regardless of
        membership_type, and a Parichay Patra is issued to every type EXCEPT
        PROBATIONARY — so the card-holder count is the difference, no extra query.
        """
        res = tier_component.evaluate(_SAKHA_GETTERS, {
            "memberTotal": 100, "homeProbationary": 18, "visiting": 7,
        })
        assert res["isSakha"] is True
        assert res["parichay"] == 82

    def test_darshak_tile_sums_both_flavours(self, tier_component):
        """Own probationary entrants + card-holders visiting from other Sakhas."""
        res = tier_component.evaluate(_SAKHA_GETTERS, {
            "memberTotal": 100, "homeProbationary": 18, "visiting": 7,
        })
        assert res["darshaks"] == 25
        assert res["visiting"] == 7

    def test_total_members_adds_visitors_exactly_once(self, tier_component):
        """
        The Sakha total is the one place visiting Darshaks count, and the three
        tiles must reconcile: parichay holders + all Darshaks == total members.
        Anything else means someone is counted twice or lost.
        """
        res = tier_component.evaluate(_SAKHA_GETTERS, {
            "memberTotal": 100, "homeProbationary": 18, "visiting": 7,
        })
        assert res["total"] == 107
        assert res["parichay"] + res["darshaks"] == res["total"]

    def test_zero_counts_are_shown_as_zero_not_as_unknown(self, tier_component):
        res = tier_component.evaluate(_SAKHA_GETTERS, {
            "memberTotal": 0, "homeProbationary": 0, "visiting": 0,
        })
        assert res["parichay"] == 0
        assert res["darshaks"] == 0
        assert res["total"] == 0
        assert res["rendered"] == "0"

    def test_unknown_member_total_stays_unknown(self, tier_component):
        """
        null means "could not be determined" (request failed / no permission /
        no org_code). It must not become 0 — the codebase never shows a
        confident zero for an unbacked figure.
        """
        res = tier_component.evaluate(_SAKHA_GETTERS, {
            "memberTotal": None, "homeProbationary": 0, "visiting": 3,
        })
        assert res["parichay"] is None
        assert res["total"] is None
        assert res["rendered"] == "—"

    def test_missing_darshak_summary_does_not_fabricate_a_visitor_count(
        self, tier_component
    ):
        """
        visitingDarshakCount uses ?? so an absent key reads as unknown, while the
        tiles that must stay additive fall back to 0.
        """
        res = tier_component.evaluate("""() => {
            const c = orgDashboardTab();
            c.org = { organization_type_code: 'SAKHA_SANGHA' };
            c.sakhaMemberTotal = 40;
            c.darshak = {};
            return { visiting: c.visitingDarshakCount, darshaks: c.sakhaDarshakTotal,
                     total: c.sakhaTotalMembers };
        }""")
        assert res["visiting"] is None
        assert res["darshaks"] == 0
        assert res["total"] == 40

    def test_broad_tier_total_excludes_visiting_darshaks(self, tier_component):
        """
        The rollup tiers stay home-based: adding cross-Sakha attendance there
        would count one person under two Sakhas. orgMemberTotal must ignore the
        darshak summary entirely.
        """
        res = tier_component.evaluate("""() => {
            const c = orgDashboardTab();
            c.org = { organization_type_code: 'ANCHALIKA_SANGHA' };
            c.parichayPatraTotal = 300;
            c.darshakTotal = 45;
            c.darshak = { home_probationary_count: 45,
                          attending_from_other_sakha_count: 60 };
            return { total: c.orgMemberTotal, isChildOverviewTier: c.isChildOverviewTier };
        }""")
        assert res["isChildOverviewTier"] is True
        assert res["total"] == 345, (
            "a broad tier total picked up visiting Darshaks — that double-counts"
        )


class TestSakhaAsanaTier:
    """Owner 2026-10-31: a Sakha Asana is a full Sakha (NSS.SAKHA_LIKE_ORG_TYPES)."""

    @pytest.mark.parametrize("type_code,expected", [
        ("SAKHA_SANGHA", True),
        ("SAKHA_ASANA", True),
        ("ANCHALIKA_SANGHA", False),
        ("MAHILA_SANGHA", False),
    ])
    def test_is_sakha_covers_both_sakha_like_types(self, tier_component, type_code, expected):
        got = tier_component.evaluate("""(code) => {
            const c = orgDashboardTab();
            c.org = { organization_type_code: code };
            return c.isSakha;
        }""", type_code)
        assert got is expected

class TestMahilaTier:

    @pytest.mark.parametrize("type_code,expected", [
        ("MAHILA_SANGHA", True),
        ("SAKHA_SANGHA", False),
        ("KENDRA", False),
    ])
    def test_is_mahila_matches_only_its_own_type(
        self, tier_component, type_code, expected
    ):
        got = tier_component.evaluate("""(code) => {
            const c = orgDashboardTab();
            c.org = { organization_type_code: code };
            return c.isMahila;
        }""", type_code)
        assert got is expected

    @pytest.mark.parametrize("parent,expected", [
        ("KENDRA", True),
        ("SAKHA_SANGHA", False),
        (None, False),
    ])
    def test_central_mahila_is_decided_by_the_parent_type(
        self, tier_component, parent, expected
    ):
        """
        A Mahila Sangha hangs off either the Kendra (central) or a Sakha (local),
        and the Parichalana Mandali's remit differs — so the tier states which.
        """
        got = tier_component.evaluate("""(parent) => {
            const c = orgDashboardTab();
            c.org = { organization_type_code: 'MAHILA_SANGHA',
                      parent_organization_type_code: parent };
            return c.isCentralMahila;
        }""", parent)
        assert got is expected

    def test_mahila_tier_issues_no_requests_and_invents_no_counts(
        self, tier_component
    ):
        """
        There is no mahila module and no governance tables in the DDL yet, so
        _loadTierData() intentionally does nothing for this tier: its widgets are
        honest placeholders. Assert both halves — no fetch, and every count left
        null so statNum() renders "—" instead of a fabricated 0.
        """
        res = tier_component.evaluate("""async () => {
            const c = orgDashboardTab();
            c.org = { organization_type_code: 'MAHILA_SANGHA', organization_pk: 9 };
            const calls = [];
            const real = NSSAuth.apiFetch;
            NSSAuth.apiFetch = (url) => {
                calls.push(url);
                return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
            };
            try {
                await c._loadTierData();
            } finally {
                NSSAuth.apiFetch = real;
            }
            return {
                calls,
                sakhaMemberTotal: c.sakhaMemberTotal,
                parichayPatraTotal: c.parichayPatraTotal,
                darshakTotal: c.darshakTotal,
                rendered: c.statNum(c.parichayPatraTotal),
            };
        }""")
        assert res["calls"] == [], (
            "the Mahila tier fired a request; it has no backing tables yet"
        )
        assert res["sakhaMemberTotal"] is None
        assert res["parichayPatraTotal"] is None
        assert res["darshakTotal"] is None
        assert res["rendered"] == "—"
