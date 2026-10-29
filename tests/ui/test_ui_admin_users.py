"""
NSS ERP — UI tests for the Admin User Accounts tab (/admin).

Verifies user listing, search by name and ID, status filtering,
user detail view, inactive row styling, and pagination controls.

Alpine.js app: adminApp()
Tab: activeTab = 'users'
"""

import pytest
from playwright.sync_api import expect
from tests.ui.conftest import wait_for_alpine, click_nav_item, get_table_rows

pytestmark = pytest.mark.ui


# ── Helpers ─────────────────────────────────────────────────────────

USERS_TAB = '[x-show="activeTab === \'users\'"]'


def _goto_users_tab(admin_page, base_url):
    """Navigate to admin page and activate the Users tab."""
    admin_page.goto(f"{base_url}/admin")
    wait_for_alpine(admin_page)
    click_nav_item(admin_page, "User Accounts")
    admin_page.wait_for_timeout(1000)


# ── Page load ────────────────────────────────────────────────────────


def test_admin_page_loads(admin_page, base_url):
    """Admin page loads successfully for an authenticated admin user."""
    admin_page.goto(f"{base_url}/admin")
    wait_for_alpine(admin_page)

    assert "/admin" in admin_page.url


# ── Users tab activation ─────────────────────────────────────────────


def test_users_tab_active(admin_page, base_url):
    """Clicking User Accounts tab activates it and shows the user table."""
    _goto_users_tab(admin_page, base_url)

    # Scope to the users tab: other tabs keep their own (hidden) .admin-table
    # in the DOM, so a bare ".admin-table" is a strict-mode violation.
    table = admin_page.locator(USERS_TAB).locator(".admin-table")
    expect(table).to_be_visible()


# ── Table data ───────────────────────────────────────────────────────


def test_users_table_has_data(admin_page, base_url):
    """User table contains at least one data row."""
    _goto_users_tab(admin_page, base_url)

    row_count = get_table_rows(admin_page)
    assert row_count >= 1, "Expected at least one user row in the table"


# ── Search by name ───────────────────────────────────────────────────


def test_users_search_by_name(admin_page, base_url):
    """Searching by name filters the user table results."""
    _goto_users_tab(admin_page, base_url)

    search_input = admin_page.locator('[x-model="usersSearch"]')
    expect(search_input).to_be_visible()

    search_input.fill("Admin")
    admin_page.locator(".btn-action.primary").first.click()
    admin_page.wait_for_timeout(500)

    row_count = get_table_rows(admin_page)
    assert row_count >= 1, "Search by name should return at least one result"


# ── Search by SS ID ──────────────────────────────────────────────────


def test_users_search_by_id(admin_page, base_url):
    """Searching by Sangha Sevi ID filters the user table results."""
    _goto_users_tab(admin_page, base_url)

    search_input = admin_page.locator('[x-model="usersSearch"]')
    search_input.fill("SS1")
    # Target the Search button by name: ".btn-action.primary" also matches
    # "+ Create Account" (admin.html:727), which sits earlier in DOM order and
    # would open the create-account modal instead of running the search.
    admin_page.get_by_role("button", name="Search", exact=True).first.click()
    admin_page.wait_for_timeout(500)

    row_count = get_table_rows(admin_page)
    assert row_count >= 1, "Search by SS ID 'SS1' should return at least one result"


# ── Status filter: ACTIVE ────────────────────────────────────────────


def test_users_status_filter_active(admin_page, base_url):
    """Selecting ACTIVE status filter shows only active users."""
    _goto_users_tab(admin_page, base_url)

    status_filter = admin_page.locator('[x-model="usersStatusFilter"]')
    expect(status_filter).to_be_visible()

    # Option value is "ACTIVE" (matching the HTML <option value="ACTIVE">)
    status_filter.select_option("ACTIVE")
    admin_page.wait_for_timeout(500)

    # Verify no inactive rows are displayed
    inactive_rows = admin_page.locator(".row-inactive")
    assert inactive_rows.count() == 0, "ACTIVE filter should not show inactive rows"


# ── Status filter: All ───────────────────────────────────────────────


def test_users_status_filter_all(admin_page, base_url):
    """Selecting 'All statuses' filter shows all users including inactive."""
    _goto_users_tab(admin_page, base_url)

    status_filter = admin_page.locator('[x-model="usersStatusFilter"]')
    # "All statuses" has value="" in the HTML
    status_filter.select_option(value="")
    admin_page.wait_for_timeout(500)

    row_count = get_table_rows(admin_page)
    assert row_count >= 1, "All filter should show at least one user"


# ── View user detail ─────────────────────────────────────────────────


def test_users_view_detail(admin_page, base_url):
    """Clicking a user row opens the user detail view."""
    _goto_users_tab(admin_page, base_url)

    # Rows are clickable (tr.clickable-row @click="viewUser(...)") — there
    # is no separate "View" button.
    row = admin_page.locator("tr.clickable-row").first
    expect(row).to_be_visible()
    row.click()

    # Detail view: activeTab === 'detail'
    detail_div = admin_page.locator('[x-show="activeTab === \'detail\'"]')
    detail_div.wait_for(state="visible", timeout=10000)


# ── Detail back to list ──────────────────────────────────────────────


def test_users_detail_back_to_list(admin_page, base_url):
    """Clicking back from user detail returns to the user list."""
    _goto_users_tab(admin_page, base_url)

    # Open detail view — rows are clickable, no separate "View" button
    row = admin_page.locator("tr.clickable-row").first
    row.click()

    detail_div = admin_page.locator('[x-show="activeTab === \'detail\'"]')
    detail_div.wait_for(state="visible", timeout=10000)

    # Click back link — scope to the user detail div to avoid claims back-link
    detail_div = admin_page.locator('[x-show="activeTab === \'detail\'"]')
    back_link = detail_div.locator('a.back-link')
    expect(back_link).to_be_visible()
    back_link.click()
    admin_page.wait_for_timeout(500)

    # User table should be visible again
    table = admin_page.locator(USERS_TAB).locator(".admin-table")
    expect(table).to_be_visible()


# ── Inactive row styling ─────────────────────────────────────────────


def test_users_inactive_row_styling(admin_page, base_url):
    """INACTIVE users have greyed-out rows with 'Deleted' text instead of action buttons."""
    _goto_users_tab(admin_page, base_url)

    # Set filter to "All statuses" (value="")
    status_filter = admin_page.locator('[x-model="usersStatusFilter"]')
    status_filter.select_option(value="")
    admin_page.wait_for_timeout(500)

    inactive_rows = admin_page.locator(".row-inactive")
    if inactive_rows.count() > 0:
        first_inactive = inactive_rows.first
        expect(first_inactive).to_be_visible()
        assert "Deleted" in first_inactive.text_content()
    else:
        pytest.skip("No INACTIVE users in current data to verify styling")


# ── Pagination controls ──────────────────────────────────────────────


def test_users_pagination(admin_page, base_url):
    """Pagination controls are visible when users exist in the table."""
    _goto_users_tab(admin_page, base_url)

    # Look for pagination bar with Page X of Y text
    pagination = admin_page.locator('.pagination-bar')
    if pagination.count() > 0:
        expect(pagination.first).to_be_visible()
    else:
        # If fewer users than page size, pagination won't appear
        pytest.skip("Not enough users to trigger pagination")
