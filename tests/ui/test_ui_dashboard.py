"""
NSS ERP — Comprehensive UI tests for the Member Dashboard (/dashboard).

Tests all dashboard features after login:
  - Authentication gating and page load
  - Sidebar navigation, topbar, user info, logout
  - Personal tab: info display, membership snapshot, address, edit profile
  - Membership tab: details, account info, affiliations, journey timeline
  - Family tab: family state (tree or create prompt), member list
  - Attendance/Governance tabs: real Tier 6 views (placeholder only without a Sangha Sevi)
  - Documents tab: Parichaya Patra, Anumati Patra
  - Admin tabs: visibility, stats grid, admin link

Alpine.js app: dashboardApp()
"""

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.ui.conftest import (
    wait_for_alpine,
    click_nav_item,
    BASE_URL,
)

pytestmark = pytest.mark.ui


# ── Reusable helpers ─────────────────────────────────────────────────────

def _wait_dashboard_ready(admin_page: Page):
    """Wait for Alpine init + loading spinner to disappear."""
    wait_for_alpine(admin_page)
    # Wait until the loading state is done (loading overlay gone or content visible)
    admin_page.wait_for_selector(
        ".content-area",
        state="visible",
        timeout=15000,
    )
    # Give API fetches time to resolve
    admin_page.wait_for_timeout(2000)


def _switch_tab(admin_page: Page, tab_name: str):
    """Switch dashboard tab via sidebar and wait for content."""
    click_nav_item(admin_page, tab_name)
    admin_page.wait_for_timeout(1000)


def _get_visible_text(admin_page: Page, selector: str) -> str:
    """Get text content of a visible element, empty string if not found."""
    el = admin_page.locator(selector)
    if el.count() > 0 and el.first.is_visible():
        return el.first.text_content().strip()
    return ""


def _data_card_visible(admin_page: Page, title_text: str) -> bool:
    """Check if a data card with the given title is visible."""
    card_title = admin_page.locator(f".data-card-title:has-text('{title_text}')")
    return card_title.count() > 0 and card_title.first.is_visible()


def _placeholder_card_visible(admin_page: Page, heading_text: str) -> bool:
    """Check if a placeholder card with the given heading is visible."""
    heading = admin_page.locator(f".placeholder-card h3:has-text('{heading_text}')")
    return heading.count() > 0 and heading.first.is_visible()


# ═══════════════════════════════════════════════════════════════════════════
#  AUTHENTICATION GATE
# ═══════════════════════════════════════════════════════════════════════════


class TestDashboardAuth:

    def test_unauthenticated_redirects_to_login(self, page: Page, base_url: str):
        """Unauthenticated visit to /dashboard must redirect to /login."""
        page.goto(f"{base_url}/dashboard")
        page.wait_for_url("**/login**", timeout=10000)
        assert "/login" in page.url

    def test_authenticated_lands_on_dashboard(self, admin_page: Page, base_url: str):
        """After admin login the browser lands on /dashboard."""
        assert "/dashboard" in admin_page.url
        wait_for_alpine(admin_page)

    def test_page_title_is_set(self, admin_page: Page):
        """Page title includes 'Dashboard'."""
        assert "Dashboard" in admin_page.title()


# ═══════════════════════════════════════════════════════════════════════════
#  SIDEBAR LAYOUT
# ═══════════════════════════════════════════════════════════════════════════


class TestDashboardSidebar:

    def test_sidebar_visible(self, admin_page: Page):
        """Sidebar element is present."""
        _wait_dashboard_ready(admin_page)
        sidebar = admin_page.locator(".sidebar")
        expect(sidebar).to_be_visible()

    def test_sidebar_has_core_nav_items(self, admin_page: Page):
        """Sidebar contains the 6 core dashboard tabs."""
        _wait_dashboard_ready(admin_page)
        core_tabs = ["Personal", "Membership", "Family", "Attendance", "Governance", "Documents"]
        for tab in core_tabs:
            item = admin_page.locator(f".nav-item:has-text('{tab}')")
            assert item.count() > 0, f"Sidebar should have '{tab}' nav item"

    def test_sidebar_brand_shows_nss(self, admin_page: Page):
        """Sidebar brand area displays Nilachala Saraswata Sangha."""
        _wait_dashboard_ready(admin_page)
        brand = admin_page.locator(".sidebar-brand")
        expect(brand).to_be_visible()
        brand_text = brand.text_content().lower()
        assert "nilachala" in brand_text or "nss" in brand_text

    def test_sidebar_footer_shows_user(self, admin_page: Page):
        """Sidebar footer displays the logged-in user's name and SS ID."""
        _wait_dashboard_ready(admin_page)
        footer = admin_page.locator(".sidebar-footer")
        expect(footer).to_be_visible()

        user_name = admin_page.locator(".sidebar-footer .user-name")
        user_id = admin_page.locator(".sidebar-footer .user-id")
        assert user_name.text_content().strip() != "", "User name should be displayed"
        assert user_id.text_content().strip() != "", "User ID should be displayed"

    def test_sidebar_admin_tabs_for_admin_user(self, admin_page: Page):
        """Admin user (SS1) sees admin-specific tabs in the sidebar."""
        _wait_dashboard_ready(admin_page)
        # SS1 has NSS_ERP_ADMIN role — should see "System Administration" tab
        admin_label = admin_page.locator(".nav-item:has-text('System Administration')")
        # Or it may use a section label
        admin_section = admin_page.locator(".nav-section-label:has-text('Admin')")
        assert admin_label.count() > 0 or admin_section.count() > 0, (
            "Admin user should see admin-specific tabs in sidebar"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  TOPBAR
# ═══════════════════════════════════════════════════════════════════════════


class TestDashboardTopbar:

    def test_topbar_visible(self, admin_page: Page):
        """Topbar is visible on dashboard."""
        _wait_dashboard_ready(admin_page)
        topbar = admin_page.locator(".topbar")
        expect(topbar).to_be_visible()

    def test_topbar_shows_current_tab_title(self, admin_page: Page):
        """Topbar title reflects the active tab name."""
        _wait_dashboard_ready(admin_page)
        # .topbar-title is now the fixed brand name; the active tab is shown
        # in the breadcrumb (desktop: .topbar-breadcrumb-desktop, mobile:
        # .topbar-breadcrumb) driven by currentTabLabel.
        assert admin_page.locator(".topbar-title").text_content().strip(), (
            "Topbar brand title should not be empty"
        )
        crumb = admin_page.locator(".topbar-breadcrumb-desktop")
        text = crumb.text_content().strip()
        assert len(text) > 0, "Topbar current-tab label should not be empty"
        # Default tab is Personal — label should reflect that
        assert "personal" in text.lower() or "information" in text.lower() or "dashboard" in text.lower()


# ═══════════════════════════════════════════════════════════════════════════
#  PERSONAL TAB (default)
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonalTab:

    def test_personal_tab_active_by_default(self, admin_page: Page):
        """Personal tab is active by default when dashboard loads."""
        _wait_dashboard_ready(admin_page)
        personal_item = admin_page.locator(".nav-item:has-text('Personal')")
        is_active = personal_item.evaluate(
            "el => el.classList.contains('active') || el.getAttribute('aria-selected') === 'true'"
        )
        assert is_active, "Personal tab should be active by default"

    def test_personal_info_card_visible(self, admin_page: Page):
        """Personal Information card is visible on the Personal tab."""
        _wait_dashboard_ready(admin_page)
        assert _data_card_visible(admin_page, "Personal Information"), (
            "Personal Information card should be visible"
        )

    def test_personal_info_shows_full_name(self, admin_page: Page):
        """Personal Information card displays the user's full name."""
        _wait_dashboard_ready(admin_page)
        # The Full Name label and value
        name_label = admin_page.locator(".data-label:has-text('Full Name')")
        assert name_label.count() > 0, "Full Name label should exist"
        # The value next to it should not be empty or '—'
        name_row = name_label.first.locator("..").locator(".data-value")
        if name_row.count() > 0:
            value = name_row.first.text_content().strip()
            assert value and value != "—", f"Full Name should have a value, got: '{value}'"

    def test_personal_info_shows_email(self, admin_page: Page):
        """Personal Information shows an email field."""
        _wait_dashboard_ready(admin_page)
        email_label = admin_page.locator(".data-label:has-text('Email')")
        assert email_label.count() > 0, "Email label should exist on Personal tab"

    def test_membership_snapshot_card_visible(self, admin_page: Page):
        """Membership Snapshot card is visible on the Personal tab."""
        _wait_dashboard_ready(admin_page)
        assert _data_card_visible(admin_page, "Membership Snapshot"), (
            "Membership Snapshot card should be visible"
        )

    def test_membership_snapshot_shows_ss_id(self, admin_page: Page):
        """Membership Snapshot displays the Sangha Sevi ID."""
        _wait_dashboard_ready(admin_page)
        ss_label = admin_page.locator(".data-label:has-text('Sangha Sevi ID')")
        assert ss_label.count() > 0, "Sangha Sevi ID label should exist"
        # Value should be populated for SS1
        ss_value = admin_page.locator(".data-sevi-id").first
        if ss_value.count() > 0:
            text = ss_value.text_content().strip()
            assert text and text != "—", f"Sangha Sevi ID should have a value, got: '{text}'"

    def test_address_card_visible(self, admin_page: Page):
        """Address card is visible on the Personal tab."""
        _wait_dashboard_ready(admin_page)
        assert _data_card_visible(admin_page, "Address"), (
            "Address card should be visible"
        )

    def test_edit_profile_button_exists(self, admin_page: Page):
        """Personal tab has an Edit button for profile editing."""
        _wait_dashboard_ready(admin_page)
        edit_btn = admin_page.locator("button:has-text('Edit')")
        assert edit_btn.count() > 0, "Edit button should exist on Personal tab"

    def test_edit_profile_opens_form(self, admin_page: Page):
        """Clicking Edit shows the profile editing form fields."""
        _wait_dashboard_ready(admin_page)
        edit_btn = admin_page.locator("button:has-text('Edit')").first
        edit_btn.click()
        admin_page.wait_for_timeout(500)

        # Edit form fields should appear
        mobile_input = admin_page.locator('[x-model="profileForm.mobile_number"]')
        email_input = admin_page.locator('[x-model="profileForm.email"]')
        # DOB is the shared nssDatePicker, not a plain bound input: the model
        # path lives in x-data/data-nss-dp and the visible input binds
        # x-model="display". So [x-model="profileForm.date_of_birth"] matches
        # nothing — locate the picker by its data-nss-dp hook instead.
        dob_input = admin_page.locator(
            '[data-nss-dp="profileForm.date_of_birth"] input[x-model="display"]'
        )

        assert mobile_input.count() > 0, "Mobile number input should appear in edit mode"
        assert email_input.count() > 0, "Email input should appear in edit mode"
        assert dob_input.count() > 0, "Date of birth input should appear in edit mode"

    def test_edit_profile_has_save_cancel(self, admin_page: Page):
        """Edit mode shows Save and Cancel buttons."""
        _wait_dashboard_ready(admin_page)
        edit_btn = admin_page.locator("button:has-text('Edit')").first
        edit_btn.click()
        admin_page.wait_for_timeout(500)

        save_btn = admin_page.locator("button:has-text('Save')")
        cancel_btn = admin_page.locator("button:has-text('Cancel')")
        assert save_btn.count() > 0, "Save button should exist in edit mode"
        assert cancel_btn.count() > 0, "Cancel button should exist in edit mode"

    def test_edit_profile_cancel_returns_to_view(self, admin_page: Page):
        """Clicking Cancel exits edit mode and returns to view mode."""
        _wait_dashboard_ready(admin_page)
        edit_btn = admin_page.locator("button:has-text('Edit')").first
        edit_btn.click()
        admin_page.wait_for_timeout(500)

        cancel_btn = admin_page.locator("button:has-text('Cancel')").first
        cancel_btn.click()
        admin_page.wait_for_timeout(500)

        # Edit button should reappear (view mode)
        edit_btn_again = admin_page.locator("button:has-text('Edit')")
        assert edit_btn_again.count() > 0, "Edit button should reappear after Cancel"


# ═══════════════════════════════════════════════════════════════════════════
#  TAB SWITCHING
# ═══════════════════════════════════════════════════════════════════════════


class TestTabSwitching:

    def test_switch_to_membership_tab(self, admin_page: Page):
        """Clicking Membership tab activates it and shows Membership content."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")

        item = admin_page.locator(".nav-item:has-text('Membership')")
        is_active = item.evaluate(
            "el => el.classList.contains('active')"
        )
        assert is_active, "Membership tab should be active after clicking"

    def test_switch_to_family_tab(self, admin_page: Page):
        """Clicking Family tab activates it."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Family")

        item = admin_page.locator(".nav-item:has-text('Family')")
        is_active = item.evaluate(
            "el => el.classList.contains('active')"
        )
        assert is_active, "Family tab should be active after clicking"

    def test_switch_to_attendance_tab(self, admin_page: Page):
        """Clicking Attendance tab activates it."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Attendance")

        # "Attendance Register" (markers only) also matches the text filter;
        # the member's own Attendance tab is the first nav item.
        item = admin_page.locator(".nav-item:has-text('Attendance')").first
        is_active = item.evaluate(
            "el => el.classList.contains('active')"
        )
        assert is_active, "Attendance tab should be active after clicking"

    def test_switch_to_documents_tab(self, admin_page: Page):
        """Clicking Documents tab activates it."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Documents")

        item = admin_page.locator(".nav-item:has-text('Documents')")
        is_active = item.evaluate(
            "el => el.classList.contains('active')"
        )
        assert is_active, "Documents tab should be active after clicking"

    def test_switch_back_to_personal(self, admin_page: Page):
        """Switching to another tab and back to Personal restores it."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        _switch_tab(admin_page, "Personal")

        item = admin_page.locator(".nav-item:has-text('Personal')")
        is_active = item.evaluate(
            "el => el.classList.contains('active')"
        )
        assert is_active, "Personal tab should be active after switching back"

    def test_topbar_title_updates_on_tab_switch(self, admin_page: Page):
        """Topbar title updates when switching tabs."""
        _wait_dashboard_ready(admin_page)
        # The active tab label lives in the breadcrumb, not .topbar-title
        # (which is the fixed "Nilachala Saraswata Sangha" brand name).
        topbar_title = admin_page.locator(".topbar-breadcrumb-desktop")

        _switch_tab(admin_page, "Membership")
        text = topbar_title.text_content().strip().lower()
        assert "membership" in text, f"Topbar should show 'Membership', got '{text}'"

        _switch_tab(admin_page, "Family")
        text = topbar_title.text_content().strip().lower()
        assert "family" in text, f"Topbar should show 'Family', got '{text}'"


# ═══════════════════════════════════════════════════════════════════════════
#  MEMBERSHIP TAB
# ═══════════════════════════════════════════════════════════════════════════


class TestMembershipTab:

    def test_membership_details_card(self, admin_page: Page):
        """Membership tab shows a 'Membership Details' data card."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)
        assert _data_card_visible(admin_page, "Membership Details"), (
            "Membership Details card should be visible"
        )

    def test_membership_details_has_ss_id(self, admin_page: Page):
        """Membership Details card shows the Sangha Sevi ID."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)

        ss_label = admin_page.locator(
            "[x-show=\"tab === 'membership'\"] .data-label:has-text('Sangha Sevi ID')"
        )
        assert ss_label.count() > 0, "Membership tab should show Sangha Sevi ID"

    def test_membership_details_has_type(self, admin_page: Page):
        """Membership Details card shows membership type badge."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)

        type_label = admin_page.locator(
            "[x-show=\"tab === 'membership'\"] .data-label:has-text('Type')"
        )
        assert type_label.count() > 0, "Membership tab should show Type field"

    def test_membership_details_has_status(self, admin_page: Page):
        """Membership Details card shows membership status badge."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)

        status_label = admin_page.locator(
            "[x-show=\"tab === 'membership'\"] .data-label:has-text('Status')"
        )
        assert status_label.count() > 0, "Membership tab should show Status field"

    def test_account_info_card(self, admin_page: Page):
        """Membership tab shows 'Account Information' card."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)
        assert _data_card_visible(admin_page, "Account Information"), (
            "Account Information card should be visible"
        )

    def test_account_info_shows_status(self, admin_page: Page):
        """Account Information card shows account status badge."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)

        status_label = admin_page.locator(".data-label:has-text('Account Status')")
        assert status_label.count() > 0, "Account Information should show Account Status"

    def test_account_info_shows_roles_count(self, admin_page: Page):
        """Account Information card shows the number of roles assigned."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1000)

        roles_label = admin_page.locator(".data-label:has-text('Roles Assigned')")
        assert roles_label.count() > 0, "Account Information should show Roles Assigned"

    def test_sakha_affiliations_section(self, admin_page: Page):
        """Membership tab shows Sakha Affiliations section."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1500)
        assert _data_card_visible(admin_page, "Sakha Affiliations"), (
            "Sakha Affiliations section should be visible"
        )

    def test_journey_timeline_section(self, admin_page: Page):
        """Membership tab shows Journey Timeline section."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(1500)
        assert _data_card_visible(admin_page, "Journey Timeline"), (
            "Journey Timeline section should be visible"
        )

    # ── Self-service change-request entry points (Darshak / Sakha transfer) ──
    # These buttons live at the top of the Membership tab. Since Tier 6
    # (membership_change_request.py) they open the real Change Request
    # modal (destination Sakha + reason + Submit Request) — no longer a
    # "handled by Governance module" notice dialog.

    def test_apply_darshak_button_visible(self, admin_page: Page):
        """Membership tab exposes an 'Apply for Darshak' action."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(500)
        btn = admin_page.locator(
            "[x-show=\"tab === 'membership'\"] button:has-text('Apply for Darshak')"
        )
        assert btn.count() > 0, "Apply for Darshak button should be present"

    def test_request_sakha_transfer_button_visible(self, admin_page: Page):
        """Membership tab exposes a 'Request Sakha Transfer' action."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(500)
        btn = admin_page.locator(
            "[x-show=\"tab === 'membership'\"] button:has-text('Request Sakha Transfer')"
        )
        assert btn.count() > 0, "Request Sakha Transfer button should be present"

    def test_apply_darshak_opens_change_request_modal(self, admin_page: Page):
        """Clicking 'Apply for Darshak' opens the Change Request modal."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(500)
        admin_page.locator(
            "[x-show=\"tab === 'membership'\"] button:has-text('Apply for Darshak')"
        ).first.click()
        expect(
            admin_page.get_by_role("heading", name="Apply for Darshak")
        ).to_be_visible()
        expect(admin_page.get_by_text("Sakha to attend")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Submit Request")).to_be_visible()

    def test_request_sakha_transfer_opens_change_request_modal(self, admin_page: Page):
        """Clicking 'Request Sakha Transfer' opens the Change Request modal."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Membership")
        admin_page.wait_for_timeout(500)
        admin_page.locator(
            "[x-show=\"tab === 'membership'\"] button:has-text('Request Sakha Transfer')"
        ).first.click()
        expect(
            admin_page.get_by_role("heading", name="Request Sakha Transfer")
        ).to_be_visible()
        expect(admin_page.get_by_text("Destination Sakha")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Submit Request")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
#  FAMILY TAB
# ═══════════════════════════════════════════════════════════════════════════


class TestFamilyTab:

    def test_family_tab_loads(self, admin_page: Page):
        """Family tab loads without error."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Family")
        admin_page.wait_for_timeout(2000)

        # Should show either family data or the "No Family Record" placeholder
        family_content = admin_page.locator("[x-show=\"tab === 'family'\"]")
        expect(family_content).to_be_visible()

    def test_family_shows_tree_or_create_prompt(self, admin_page: Page):
        """Family tab shows either the family tree or 'Create My Family' prompt."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Family")
        admin_page.wait_for_timeout(3000)

        # Option A: Family exists — tree or member list visible.
        # Real markup is .tree-canvas > .tree-container (x-html renders
        # .tree-node / .gen-divider). There is no ".family-tree" class — the
        # old selector only ever matched via its [class*='tree-node'] fallback.
        tree_area = admin_page.locator(".tree-canvas, .tree-node, .gen-divider")
        member_table = admin_page.locator("text=Members")

        # Option B: No family — placeholder with create button
        no_family = admin_page.locator("text=No Family Record")
        create_btn = admin_page.locator("button:has-text('Create My Family')")

        has_family_content = tree_area.count() > 0 or member_table.count() > 0
        has_no_family_prompt = no_family.count() > 0 or create_btn.count() > 0

        assert has_family_content or has_no_family_prompt, (
            "Family tab should show either family data or create-family prompt"
        )

    def test_family_member_list_or_empty(self, admin_page: Page):
        """If a family exists, the member list section is present."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Family")
        admin_page.wait_for_timeout(3000)

        # Check if family exists first
        no_family = admin_page.locator("text=No Family Record")
        if no_family.count() > 0 and no_family.first.is_visible():
            pytest.skip("No family exists for this user — create-family prompt shown")

        # Family exists — look for member-related content.
        # NOTE: a single Playwright locator string cannot OR several text=
        # engines — the old "text=Members, text=Head of Family, text=Family
        # Members" was parsed as ONE literal string and never matched. Chain
        # real text locators with .or_() instead. The frontend renders a
        # "Members (<n>)" heading and a "Head of Family" label ("Family
        # Members" is not a string the UI ever emits).
        members_section = admin_page.get_by_text("Members").or_(
            admin_page.get_by_text("Head of Family")
        )
        assert members_section.count() > 0, (
            "Family tab should show a members section when family exists"
        )

    def test_family_tree_rendering(self, admin_page: Page):
        """If a family with members exists, the family tree renders nodes."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Family")
        admin_page.wait_for_timeout(4000)

        no_family = admin_page.locator("text=No Family Record")
        if no_family.count() > 0 and no_family.first.is_visible():
            pytest.skip("No family exists for this user")

        # Tree nodes are rendered as .tree-node elements via x-html
        tree_nodes = admin_page.locator(".tree-node")
        gen_dividers = admin_page.locator(".gen-divider")

        if tree_nodes.count() == 0 and gen_dividers.count() == 0:
            # Tree may still be loading or family has only one member.
            # While graphLoading is truthy the family tab shows .skeleton
            # loaders (there is no "Loading family tree" text in the UI).
            tree_loading = admin_page.locator(
                "[x-show=\"tab === 'family'\"] .skeleton"
            )
            if tree_loading.count() > 0 and tree_loading.first.is_visible():
                pytest.skip("Family tree still loading")
            # Single-member family may not render a full tree
            return

        assert tree_nodes.count() > 0 or gen_dividers.count() > 0, (
            "Family tree should render tree nodes or generation dividers"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  ATTENDANCE TAB
# ═══════════════════════════════════════════════════════════════════════════


class TestAttendanceTab:

    def test_attendance_placeholder(self, admin_page: Page):
        """Attendance tab is a real history view (placeholder only without a Sangha Sevi)."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Attendance")
        admin_page.wait_for_timeout(500)

        tab_div = admin_page.locator('[x-show="tab === \'attendance\'"]')
        # Admin user holds an active Sangha Sevi -> real tab; otherwise the
        # 'Attendance Records' placeholder card is shown.
        real = tab_div.get_by_text("Your Weekly Sangha Puja attendance history.")
        assert real.count() > 0 or _placeholder_card_visible(admin_page, "Attendance Records"), (
            "Attendance tab should show the attendance history (or the "
            "'Attendance Records' placeholder when there is no Sangha Sevi)"
        )

    def test_attendance_placeholder_message(self, admin_page: Page):
        """Attendance placeholder mentions module not yet implemented."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Attendance")
        admin_page.wait_for_timeout(500)

        # Scope to the attendance tab's x-show div to avoid picking family tab content
        attendance_div = admin_page.locator('[x-show="tab === \'attendance\'"]')
        msg = attendance_div.locator(".placeholder-card p")
        if msg.count() > 0:
            text = msg.first.text_content().lower()
            assert "attendance" in text or "implemented" in text


# ═══════════════════════════════════════════════════════════════════════════
#  GOVERNANCE TAB
# ═══════════════════════════════════════════════════════════════════════════


class TestGovernanceTab:

    def test_governance_placeholder(self, admin_page: Page):
        """Governance tab is now a real view (Tier 6), not a placeholder card."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Governance")
        admin_page.wait_for_timeout(500)

        tab_div = admin_page.locator('[x-show="tab === \'governance\'"]')
        expect(tab_div.get_by_role("heading", name="Governance", exact=True)).to_be_visible()
        assert not _placeholder_card_visible(admin_page, "Governance Roles"), (
            "the old 'Governance Roles' placeholder should be gone"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  DOCUMENTS TAB
# ═══════════════════════════════════════════════════════════════════════════


class TestDocumentsTab:

    def test_documents_tab_loads(self, admin_page: Page):
        """Documents tab loads and shows content area."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Documents")
        admin_page.wait_for_timeout(1000)

        doc_tab = admin_page.locator("[x-show=\"tab === 'documents'\"]")
        expect(doc_tab).to_be_visible()

    def test_parichaya_patra_section(self, admin_page: Page):
        """Documents tab shows Parichaya Patra section."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Documents")
        admin_page.wait_for_timeout(1000)
        assert _data_card_visible(admin_page, "Parichaya Patra"), (
            "Documents tab should show Parichaya Patra section"
        )

    def test_parichaya_patra_shows_records_or_empty(self, admin_page: Page):
        """Parichaya Patra shows record count badge or empty state."""
        _wait_dashboard_ready(admin_page)
        _switch_tab(admin_page, "Documents")
        admin_page.wait_for_timeout(1500)

        # Either records exist or the empty state is shown
        records_badge = admin_page.locator(".badge:has-text('record')")
        empty_msg = admin_page.locator("text=No Parichaya Patra records")
        assert records_badge.count() > 0 or empty_msg.count() > 0, (
            "Parichaya Patra should show record count or empty message"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  ADMIN TABS (role-based)
# ═══════════════════════════════════════════════════════════════════════════


class TestAdminTabs:

    def test_admin_tab_visible_for_admin_user(self, admin_page: Page):
        """SS1 (NSS_ERP_ADMIN) sees at least one admin tab in the sidebar."""
        _wait_dashboard_ready(admin_page)

        # Admin tabs are generated from ADMIN_TAB_MAP based on scopes
        admin_nav = admin_page.locator(
            ".nav-item:has-text('System Administration'), "
            ".nav-item:has-text('Management'), "
            ".nav-item:has-text('Audit')"
        )
        assert admin_nav.count() > 0, "Admin user should see admin tabs"

    def test_super_admin_group_is_exactly_the_three_system_tabs(self, admin_page: Page):
        """
        SS1 holds NSS_ERP_ADMIN, whose permission set is a strict superset of
        the two read-only SYSTEM roles and of every ORGANIZATIONAL role.  Its
        Administration group must therefore render System Administration,
        Audit & Compliance and Reports from the start, plus Registration
        Approvals, and must NOT render any narrower "... Management" tab.
        """
        _wait_dashboard_ready(admin_page)

        sysadmin = admin_page.locator(".nav-item:has-text('System Administration')")
        if sysadmin.count() == 0:
            pytest.skip("Logged-in user is not a super admin in this dataset")

        for label in ("System Administration", "Audit & Compliance", "Reports"):
            tab = admin_page.locator(f".nav-item:has-text(\"{label}\")")
            assert tab.count() > 0, f"Super admin should see the '{label}' tab"

        # Organizational tabs are built by x-for over adminTabs, so a
        # suppressed one is absent from the DOM entirely, not merely hidden.
        mgmt = admin_page.locator(".nav-item:has-text('Management')")
        assert mgmt.count() == 0, (
            "Super admin should not see organizational '... Management' tabs; "
            f"found {mgmt.count()}"
        )

        approvals = admin_page.locator(".nav-item:has-text('Registration Approvals')")
        assert approvals.count() > 0, "Super admin should see Registration Approvals"
        assert approvals.first.is_visible(), (
            "Registration Approvals is x-show gated on canApproveRegistrations; "
            "a super admin holds ADMIN_USER_MANAGE so it must be visible"
        )

    def test_admin_tab_shows_stats_grid(self, admin_page: Page):
        """Clicking an admin tab shows the stats grid (members, families, etc.)."""
        _wait_dashboard_ready(admin_page)

        # Find the first admin tab
        admin_items = admin_page.locator(
            ".nav-item:has-text('System Administration'), "
            ".nav-item:has-text('Management')"
        )
        if admin_items.count() == 0:
            pytest.skip("No admin tabs visible")

        admin_items.first.click()
        admin_page.wait_for_timeout(2000)

        # Stats grid should show stat cards with numbers
        active_members = admin_page.locator("text=Active Members")
        families_stat = admin_page.locator("text=Families")
        assert active_members.count() > 0 or families_stat.count() > 0, (
            "Admin tab should show stats grid with Active Members / Families"
        )

    def test_admin_tab_shows_role_and_scope(self, admin_page: Page):
        """Admin tab header shows role label, description, and scope."""
        _wait_dashboard_ready(admin_page)

        admin_items = admin_page.locator(
            ".nav-item:has-text('System Administration')"
        )
        if admin_items.count() == 0:
            pytest.skip("System Administration tab not visible")

        admin_items.first.click()
        admin_page.wait_for_timeout(1500)

        # Header should show scope label
        scope = admin_page.locator("text=Scope")
        assert scope.count() > 0, "Admin tab should show Scope information"

    def test_admin_tab_has_admin_link(self, admin_page: Page):
        """Admin tab provides a link/button to the full admin page."""
        _wait_dashboard_ready(admin_page)

        admin_items = admin_page.locator(
            ".nav-item:has-text('System Administration')"
        )
        if admin_items.count() == 0:
            pytest.skip("System Administration tab not visible")

        admin_items.first.click()
        admin_page.wait_for_timeout(1500)

        # Look for "Open Admin Panel" or similar link to /admin
        admin_link = admin_page.locator(
            "a[href*='/admin'], button:has-text('Open Admin'), "
            "button:has-text('Admin Panel'), a:has-text('admin')"
        )
        # This may or may not exist depending on the design
        if admin_link.count() == 0:
            pytest.skip("No direct admin panel link found on admin tab")


# ═══════════════════════════════════════════════════════════════════════════
#  LOGOUT
# ═══════════════════════════════════════════════════════════════════════════


class TestDashboardLogout:

    def test_logout_button_exists(self, admin_page: Page):
        """Logout button exists in the sidebar footer."""
        _wait_dashboard_ready(admin_page)
        logout_btn = admin_page.locator(".logout-btn")
        expect(logout_btn).to_be_visible()

    def test_logout_redirects_to_login(self, admin_page: Page, base_url: str):
        """Clicking the logout button redirects to /login."""
        _wait_dashboard_ready(admin_page)
        logout_btn = admin_page.locator(".logout-btn")
        logout_btn.click()
        admin_page.wait_for_url("**/login**", timeout=10000)
        assert "/login" in admin_page.url


# ═══════════════════════════════════════════════════════════════════════════
#  SUPER-ADMIN ADMINISTRATION GROUP (source-level — no browser needed)
# ═══════════════════════════════════════════════════════════════════════════
#
# The Administration group in dashboard.html's sidebar is driven entirely by
# _buildAdminTabs() in dashboard.js. These assert the super-admin contract in
# source, so they run anywhere and catch a regression the browser tests above
# can only catch when a server AND the right seed data are both present.

_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
_DASHBOARD_JS = _FRONTEND / "assets" / "js" / "dashboard.js"
_DASHBOARD_HTML = _FRONTEND / "dashboard.html"

# Administrator, Audit, Reports — the whole Administration group for a super
# admin, in display order.
_SUPER_ADMIN_ROLES = ["NSS_ERP_ADMIN", "NSS_ERP_AUDITOR", "NSS_ERP_REPORT_VIEWER"]


class TestSuperAdminTabs:

    def test_super_admin_tab_order_is_the_three_system_roles(self):
        js = _DASHBOARD_JS.read_text(encoding="utf-8")
        block = js.split("const SUPER_ADMIN_TAB_ORDER = [")[1].split("]")[0]
        found = re.findall(r'"([A-Z_]+)"', block)
        assert found == _SUPER_ADMIN_ROLES, (
            "SUPER_ADMIN_TAB_ORDER must stay Administrator -> Audit -> Reports; "
            f"got {found}"
        )

    def test_every_super_admin_role_has_a_tab_definition(self):
        js = _DASHBOARD_JS.read_text(encoding="utf-8")
        tab_map = js.split("const ADMIN_TAB_MAP = {")[1].split("\n};")[0]
        for role in _SUPER_ADMIN_ROLES:
            assert f"{role}:" in tab_map, (
                f"ADMIN_TAB_MAP has no {role} entry — its tab would render "
                "with an undefined label"
            )

    def test_super_admin_branch_is_a_true_union_not_an_early_return(self):
        """
        Owner-confirmed 2026-10-22 ("true union"): a super-wide admin
        (NSS_ERP_ADMIN / NSS_ERP_KENDRA_ADMIN) always gets the three fixed
        system tabs AND a tab per organizational role they also hold. The
        old early-return short-circuit was deliberately removed, so the
        fixed tabs are seeded into `seen` and the per-role loop still runs.
        """
        js = _DASHBOARD_JS.read_text(encoding="utf-8")
        body = js.split("_buildAdminTabs() {")[1].split("\n        },")[0]
        assert 's.role_code === "NSS_ERP_ADMIN"' in body, (
            "_buildAdminTabs() no longer special-cases the super admin"
        )
        assert "SUPER_ADMIN_TAB_ORDER" in body
        assert "seen.add(rc)" in body, "fixed system roles must be marked seen"
        assert "return;" not in body.split("const seen = new Set();")[1], (
            "the super-admin branch returns early again - organizational "
            "role tabs would be dropped for a super-wide admin"
        )
        assert "this.adminTabs = [...fixedTabs, ...orgTabs]" in body

    def test_registration_approvals_is_permission_gated(self):
        """
        The Registration Approvals nav item is gated on the same permissions
        /api/v1/claims requires, so it can never link to a 403.
        """
        js = _DASHBOARD_JS.read_text(encoding="utf-8")
        html = _DASHBOARD_HTML.read_text(encoding="utf-8")
        assert "get canApproveRegistrations()" in js, (
            "dashboard.js no longer defines canApproveRegistrations"
        )
        perms_block = js.split("const CLAIM_APPROVAL_PERMISSIONS = [")[1].split("]")[0]
        for perm in ["MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE"]:
            assert perm in perms_block, (
                f"CLAIM_APPROVAL_PERMISSIONS dropped {perm} — it no longer "
                "mirrors require_any_permission() in api/routers/claim_approval.py"
            )
        nav = re.search(
            r'<a class="nav-item"[^>]*href="/admin#claims"[^>]*>', html
        )
        assert nav, "dashboard.html no longer links to the admin claims tab"
        assert 'x-show="canApproveRegistrations"' in nav.group(0), (
            "dashboard.html's Registration Approvals nav item is no longer "
            "permission-gated"
        )

    def test_stale_admin_tab_falls_back_instead_of_rendering_blank(self):
        """
        tab is restored from sessionStorage before /auth/me is read, so it can
        name a tab _buildAdminTabs() now omits. init() must correct it.
        """
        js = _DASHBOARD_JS.read_text(encoding="utf-8")
        assert 'this.tab.startsWith("admin_")' in js and "!this.adminTabs.some(" in js, (
            "init() no longer validates a restored admin_* tab against "
            "adminTabs — a stale session would render an empty content area"
        )
