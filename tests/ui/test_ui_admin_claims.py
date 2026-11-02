"""
UI tests for the Registration Approvals (Claims) tab on the NSS ERP admin page.

Tests the claims interface: tab loading, status pill switching (Pending,
Approved, Rejected), table structure, detail view, and state reset on
tab switch.

Fixtures used:
  - admin_page: pre-authenticated admin browser page (SS1)
  - base_url: http://localhost:8001
"""

import re

import pytest
from playwright.sync_api import expect

from tests.ui.conftest import wait_for_alpine, click_nav_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _navigate_to_claims_tab(admin_page, base_url):
    """Navigate to the admin page and open the Claims / Registration Approvals tab."""
    admin_page.goto(f"{base_url}/admin")
    wait_for_alpine(admin_page)
    admin_page.wait_for_timeout(1000)

    # The sidebar nav item text is "Registration Approvals" with x-show permission guard
    claims_nav = admin_page.locator('.nav-item:has-text("Registration Approvals")')
    if claims_nav.count() > 0 and claims_nav.first.is_visible():
        claims_nav.first.click()
    else:
        pytest.skip("Registration Approvals nav item not visible (permissions)")

    # Wait for claims tab to be visible
    claims_div = admin_page.locator('[x-show="activeTab === \'claims\'"]')
    claims_div.wait_for(state="visible", timeout=5000)
    admin_page.wait_for_timeout(1000)


def _pill(admin_page, status: str):
    """
    A status pill scoped to the claims tab. admin.html has several other
    .tab-pills groups (change requests: "Pending ...", correspondence:
    "Pending Action") that stay in the DOM while hidden, so an unscoped
    `.tab-pill:has-text("Pending")` matches more than one element and fails
    Playwright's strict mode.
    """
    return admin_page.locator('[x-show="activeTab === \'claims\'"]').locator(
        ".tab-pill", has_text=re.compile(rf"^\s*{status}\b")
    )


def _click_status_pill(admin_page, status: str):
    """Click a status filter pill (Pending, Approved, Rejected)."""
    pill = _pill(admin_page, status)
    pill.click()
    admin_page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAdminClaims:
    """Registration Approvals / Claims tab on the admin page."""

    def test_claims_tab_loads(self, admin_page, base_url):
        """Switching to the claims tab should show the claims interface."""
        _navigate_to_claims_tab(admin_page, base_url)

        # The claims tab has status pills: Pending, Approved, Rejected
        pending_pill = _pill(admin_page, "Pending")
        expect(pending_pill).to_be_visible(timeout=5000)

    def test_claims_pending_tab_default(self, admin_page, base_url):
        """The Pending status pill should be active by default."""
        _navigate_to_claims_tab(admin_page, base_url)

        pending_pill = _pill(admin_page, "Pending")
        expect(pending_pill).to_be_visible(timeout=5000)

        classes = pending_pill.get_attribute("class") or ""
        assert "active" in classes, (
            f"Pending pill should be active by default, got classes: {classes}"
        )

    def test_claims_tab_switching(self, admin_page, base_url):
        """Clicking Approved and Rejected pills should change the view."""
        _navigate_to_claims_tab(admin_page, base_url)

        # Switch to Approved
        _click_status_pill(admin_page, "Approved")
        approved_pill = _pill(admin_page, "Approved")
        classes = approved_pill.get_attribute("class") or ""
        assert "active" in classes, "Approved pill should be active after clicking"

        # Switch to Rejected
        _click_status_pill(admin_page, "Rejected")
        rejected_pill = _pill(admin_page, "Rejected")
        classes = rejected_pill.get_attribute("class") or ""
        assert "active" in classes, "Rejected pill should be active after clicking"

    def test_claims_table_structure(self, admin_page, base_url):
        """The claims table should have expected column headers (when claims exist)."""
        _navigate_to_claims_tab(admin_page, base_url)

        # The table is inside <template x-if="!claimsLoading && claims.length > 0">
        # so headers only render when claims exist
        claims_div = admin_page.locator('[x-show="activeTab === \'claims\'"]')
        table = claims_div.locator(".admin-table")
        if table.count() == 0:
            pytest.skip("No claims loaded — table not rendered")

        headers = table.locator("th")
        header_texts = headers.all_text_contents()
        header_text_combined = " ".join(header_texts).lower()

        if not header_text_combined.strip():
            pytest.skip("Claims table has no visible headers (no claims data)")

        # Actual headers: Person ID, Name, Sakha, Membership, Local No., Submitted
        for expected in ["person id", "name", "sakha", "membership"]:
            assert expected in header_text_combined, (
                f"Claims table should have a '{expected}' column header, "
                f"got: {header_text_combined}"
            )

    def test_claims_detail_view(self, admin_page, base_url):
        """Clicking a claim row should show detail view (if claims exist)."""
        _navigate_to_claims_tab(admin_page, base_url)

        # Scope to claims tab to avoid picking user table rows
        claims_div = admin_page.locator('[x-show="activeTab === \'claims\'"]')
        rows = claims_div.locator("tbody tr")
        if rows.count() == 0:
            pytest.skip("No claims available to test detail view")

        # Claim rows have @click="viewClaim(c.registration_claim_pk)"
        rows.first.click()
        admin_page.wait_for_timeout(1000)

        # Detail view should show admin remarks textarea or Approve/Reject buttons
        approve_btn = admin_page.locator('button:has-text("Approve")')
        admin_remarks = admin_page.locator('[x-model="adminRemarks"]')
        assert approve_btn.count() > 0 or admin_remarks.count() > 0, (
            "Claim detail should show Approve button or admin remarks"
        )

    def test_claims_tab_switch_resets_detail(self, admin_page, base_url):
        """Switching status tabs should close the detail view."""
        _navigate_to_claims_tab(admin_page, base_url)

        claims_div = admin_page.locator('[x-show="activeTab === \'claims\'"]')
        rows = claims_div.locator("tbody tr")
        if rows.count() == 0:
            pytest.skip("No claims available to test detail reset")

        # Open a claim detail
        rows.first.click()
        admin_page.wait_for_timeout(1000)

        # Switch to another status tab — clicking sets selectedClaim = null
        _click_status_pill(admin_page, "Approved")
        admin_page.wait_for_timeout(500)

        # The detail remarks should no longer be visible
        admin_remarks = admin_page.locator('[x-model="adminRemarks"]')
        if admin_remarks.count() > 0:
            expect(admin_remarks.first).to_be_hidden(timeout=5000)
