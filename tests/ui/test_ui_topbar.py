"""
UI tests for the shared topbar (nss-layout.js / nss-layout.css).

Two things were previously untested:

1. **Role-badge collapsing** in `NSSLayout.mixin().topbarUserInfo()` — one badge
   per distinct `role_code`, and SYSTEM roles that `NSS_ERP_ADMIN` already
   subsumes (`NSS_ERP_AUDITOR`, `NSS_ERP_REPORT_VIEWER`) are not badged at all.
   This is display-only: `nss.user_role` rows and the admin tabs are untouched.
2. **The topbar layout rules** that stop the page title wrapping onto a second
   line when the identity block carries several badges.

The badge tests call the real function in the real browser with synthetic
`currentUser` payloads (`page.evaluate`), so they assert the actual rendering
logic without depending on which roles the seed data happens to grant. The
layout tests read computed styles, which is where the wrap bug actually lived
(a flexbox automatic-minimum-size problem, not a badge-count problem).

`NSSLayout` is a top-level `const` in a classic script, so it is a global
lexical binding and reachable from page.evaluate.

Requires a live server + Postgres (BASE_URL http://127.0.0.1:8001). Run with:
    python3 -m pytest tests/ui/test_ui_topbar.py
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.ui.conftest import wait_for_alpine

pytestmark = pytest.mark.ui


_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

# Rendering topbarUserInfo() against a synthetic currentUser and returning the
# badge labels in document order.
_RENDER_BADGES = """
(scopes) => {
    const ctx = NSSLayout.mixin();
    ctx.currentUser = { person_name: 'Test User', sangha_sevi_id: 'SS999', scopes };
    const host = document.createElement('div');
    host.innerHTML = ctx.topbarUserInfo();
    return {
        badges: Array.from(host.querySelectorAll('.role-badge'))
                     .map(el => el.textContent),
        injected: host.querySelectorAll('img, script').length,
    };
}
"""


def _scope(role_code, role_name=None, scope_level="NSS-WIDE", organization_pk=None):
    return {
        "role_code": role_code,
        "role_name": role_name or role_code,
        "scope_level": scope_level,
        "organization_pk": organization_pk,
    }


@pytest.fixture
def layout_page(admin_page: Page, base_url):
    """Any page that loads nss-layout.js; /admin is authenticated already."""
    admin_page.goto(f"{base_url}/admin")
    wait_for_alpine(admin_page)
    # login.html does not load nss-layout.js, so a session that was not
    # accepted (bounced to /login) shows up as "NSSLayout is not defined".
    # Fail with the real cause instead.
    assert "/login" not in admin_page.url, (
        f"admin session bounced to {admin_page.url}; nss-layout.js is not "
        "loaded on /login, so NSSLayout is undefined there"
    )
    return admin_page


# ── Role-badge collapsing ───────────────────────────────────────────────────


class TestRoleBadgeCollapsing:

    def test_super_admin_suppresses_the_roles_it_subsumes(self, layout_page):
        """
        NSS_ERP_ADMIN is a strict permission superset of NSS_ERP_AUDITOR and
        NSS_ERP_REPORT_VIEWER (all three fixed at scope_level='NSS-WIDE'), so
        badging all three states the same thing three times.
        """
        result = layout_page.evaluate(_RENDER_BADGES, [
            _scope("NSS_ERP_ADMIN", "System Administrator"),
            _scope("NSS_ERP_AUDITOR", "Auditor"),
            _scope("NSS_ERP_REPORT_VIEWER", "Report Viewer"),
        ])
        assert result["badges"] == ["System Administrator"], (
            "a super admin's topbar should carry only the System Administrator "
            f"badge, got {result['badges']}"
        )

    def test_read_only_system_roles_are_kept_without_an_admin_role(self, layout_page):
        """
        The suppression is conditional on NSS_ERP_ADMIN being held. A plain
        auditor/report viewer must still see both badges — otherwise the collapse
        would be hiding access rather than de-duplicating it.
        """
        result = layout_page.evaluate(_RENDER_BADGES, [
            _scope("NSS_ERP_AUDITOR", "Auditor"),
            _scope("NSS_ERP_REPORT_VIEWER", "Report Viewer"),
        ])
        assert result["badges"] == ["Auditor", "Report Viewer"], result["badges"]

    def test_same_role_at_several_orgs_collapses_to_one_badge(self, layout_page):
        """
        The frozen RBAC has no unique constraint on nss.user_role: the same
        ORGANIZATIONAL role at three Sakhas is three legal rows. That is scope
        information, not identity information, so the topbar shows one badge.
        """
        result = layout_page.evaluate(_RENDER_BADGES, [
            _scope("NSS_ERP_SAKHA_ADMIN", "Sakha Administrator", "SAKHA", 11),
            _scope("NSS_ERP_SAKHA_ADMIN", "Sakha Administrator", "SAKHA", 12),
            _scope("NSS_ERP_SAKHA_ADMIN", "Sakha Administrator", "SAKHA", 13),
        ])
        assert result["badges"] == ["Sakha Administrator"], result["badges"]

    def test_organizational_roles_are_not_suppressed_by_admin(self, layout_page):
        """
        Only the two read-only SYSTEM roles are subsumed. An organizational role
        held alongside NSS_ERP_ADMIN still gets its own badge — suppressing it
        would be an interpretation of the RBAC, not a de-duplication of it.
        """
        result = layout_page.evaluate(_RENDER_BADGES, [
            _scope("NSS_ERP_ADMIN", "System Administrator"),
            _scope("NSS_ERP_SAKHA_ADMIN", "Sakha Administrator", "SAKHA", 11),
        ])
        assert result["badges"] == ["System Administrator", "Sakha Administrator"], (
            result["badges"]
        )

    def test_role_name_is_escaped(self, layout_page):
        """
        topbarUserInfo() builds an HTML string consumed by x-html, so role_name
        goes through _esc(). A crafted name must not become markup.
        """
        result = layout_page.evaluate(_RENDER_BADGES, [
            _scope("NSS_ERP_ADMIN", "<img src=x onerror=alert(1)>"),
        ])
        assert result["injected"] == 0, "role_name was rendered as live markup"
        assert result["badges"] == ["<img src=x onerror=alert(1)>"], result["badges"]

    def test_no_scopes_renders_no_badges(self, layout_page):
        result = layout_page.evaluate(_RENDER_BADGES, [])
        assert result["badges"] == []


# ── Topbar layout: the title must never wrap ────────────────────────────────


class TestTopbarLayout:

    def test_title_is_a_single_ellipsized_line(self, layout_page):
        """
        The title wrapped because its block could grow to the full text width.
        The fix is nowrap + hidden overflow + ellipsis on .topbar-title; assert
        the computed values rather than the stylesheet text.
        """
        style = layout_page.evaluate("""() => {
            const el = document.querySelector('.topbar-title');
            if (!el) return null;
            const cs = getComputedStyle(el);
            return {
                whiteSpace: cs.whiteSpace,
                overflow: cs.overflow,
                textOverflow: cs.textOverflow,
            };
        }""")
        assert style, ".topbar-title is missing from the page"
        assert style["whiteSpace"] == "nowrap", style
        assert style["overflow"] == "hidden", style
        assert style["textOverflow"] == "ellipsis", style

    def test_heading_block_can_shrink(self, layout_page):
        """
        min-width:0 on .topbar-heading is what actually permits the ellipsis —
        without it the flex item's automatic minimum size is its full text
        width, which is the root cause of the two-line topbar.
        """
        min_width = layout_page.evaluate(
            "() => getComputedStyle(document.querySelector('.topbar-heading')).minWidth"
        )
        assert min_width == "0px", f"expected min-width:0, got {min_width}"

    def test_identity_block_is_the_side_that_wraps(self, layout_page):
        """The badges may wrap, right-aligned; the title may not."""
        cs = layout_page.evaluate("""() => {
            const cs = getComputedStyle(document.querySelector('.topbar-user-info'));
            return { flexWrap: cs.flexWrap, justifyContent: cs.justifyContent };
        }""")
        assert cs["flexWrap"] == "wrap", cs
        assert cs["justifyContent"] == "flex-end", cs

    def test_title_stays_on_one_line_with_extra_badges(self, layout_page):
        """
        The regression test for the reported bug: add three more long badges to
        the identity block and the title must still occupy a single line.
        """
        result = layout_page.evaluate("""() => {
            const bar = document.querySelector('.topbar-user-info');
            for (const label of ['System Administration', 'Audit & Compliance',
                                 'Report Viewer (NSS-WIDE)']) {
                const span = document.createElement('span');
                span.className = 'role-badge';
                span.textContent = label;
                bar.appendChild(span);
            }
            const el = document.querySelector('.topbar-title');
            const cs = getComputedStyle(el);
            const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
            return { height: el.getBoundingClientRect().height, lineHeight: lh };
        }""")
        assert result["height"] <= result["lineHeight"] * 1.6, (
            "the topbar title grew past one line once extra badges were added: "
            f"{result}"
        )


# ── Source parity: both hosts use the shared classes ───────────────────────


@pytest.mark.parametrize("host", ["dashboard.html", "admin.html"])
def test_host_topbar_uses_shared_classes_not_inline_flex(host):
    """
    Both hosts previously styled the topbar's left side with an inline
    `style="display: flex; ..."`, which is where the wrap bug hid. Keep the
    layout in nss-layout.css so a fix applies to both pages at once.
    """
    html = (_FRONTEND / host).read_text(encoding="utf-8")
    for cls in ('class="topbar-left"', 'class="topbar-heading"'):
        assert cls in html, f"{host} no longer uses {cls}"
    topbar = html.split('class="topbar"', 1)[1][:1200]
    assert "display: flex" not in topbar, (
        f"{host} reintroduced inline flex styling inside the topbar"
    )
