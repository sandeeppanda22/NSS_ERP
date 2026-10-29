"""
NSS ERP — UI tests for the Admin Member Directory tab (/admin).

Covers the per-member detail card (opened by clicking a directory row →
viewMember → mdSelected) and its membership-change entry points:
"Sakha Transfer" and "Apply for Darshak". Those are per-person actions —
they live on the selected member's detail card, not the org-level Quick
Actions grid — and open a notice pointing to where the member files the request (their
dashboard Membership tab) and where it is reviewed ("Sakha Transfer / Darshak").

Alpine.js app: adminApp()
Tab: activeTab = 'memberDir'
"""

import pytest
from playwright.sync_api import expect
from tests.ui.conftest import wait_for_alpine, click_nav_item

pytestmark = pytest.mark.ui


def _goto_member_directory(admin_page, base_url):
    """Navigate to the admin page and activate the Member Directory tab."""
    admin_page.goto(f"{base_url}/admin")
    wait_for_alpine(admin_page)
    click_nav_item(admin_page, "Member Directory")
    admin_page.wait_for_timeout(1500)


def _select_first_member(admin_page):
    """Click the first directory row to open its detail card.

    Returns True if a member was selected, False if the directory is empty
    (e.g. only bootstrap data seeded) so the caller can skip.
    """
    rows = admin_page.locator(".nss-dir-row")
    if rows.count() == 0:
        return False
    rows.first.click()
    admin_page.wait_for_timeout(1000)
    return True


# ── Tab activation ───────────────────────────────────────────────────


def test_member_directory_tab_active(admin_page, base_url):
    """Member Directory tab activates and its panel is visible."""
    _goto_member_directory(admin_page, base_url)
    panel = admin_page.locator("[x-show=\"activeTab === 'memberDir'\"]")
    expect(panel.first).to_be_visible()


# ── Per-member detail card actions ──────────────────────────────────


def test_selected_member_shows_change_actions(admin_page, base_url):
    """Selecting a member reveals the Sakha Transfer / Apply for Darshak
    actions on that member's detail card."""
    _goto_member_directory(admin_page, base_url)
    if not _select_first_member(admin_page):
        pytest.skip("No members seeded in the directory")
    transfer_btn = admin_page.locator("button:has-text('Sakha Transfer')")
    darshak_btn = admin_page.locator("button:has-text('Apply for Darshak')")
    assert transfer_btn.count() > 0, "Sakha Transfer action should be present"
    assert darshak_btn.count() > 0, "Apply for Darshak action should be present"


def test_apply_darshak_shows_governance_notice(admin_page, base_url):
    """Clicking 'Apply for Darshak' on a member opens the redirect notice (member files it themself)."""
    _goto_member_directory(admin_page, base_url)
    if not _select_first_member(admin_page):
        pytest.skip("No members seeded in the directory")
    admin_page.locator("button:has-text('Apply for Darshak')").first.click()
    overlay = admin_page.locator("#nss-dialog-overlay")
    expect(overlay).to_be_visible()
    message = admin_page.locator("#nss-dialog-message")
    text = message.text_content() or ""
    assert "Sakha Transfer / Darshak" in text and "Apply for Darshak" in text, (
        "Darshak notice should point to the member dashboard flow and the "
        "'Sakha Transfer / Darshak' review queue"
    )


def test_sakha_transfer_shows_governance_notice(admin_page, base_url):
    """Clicking 'Sakha Transfer' on a member opens the redirect notice (member files it themself)."""
    _goto_member_directory(admin_page, base_url)
    if not _select_first_member(admin_page):
        pytest.skip("No members seeded in the directory")
    admin_page.locator("button:has-text('Sakha Transfer')").first.click()
    overlay = admin_page.locator("#nss-dialog-overlay")
    expect(overlay).to_be_visible()
    message = admin_page.locator("#nss-dialog-message")
    text = message.text_content() or ""
    assert "Sakha Transfer / Darshak" in text and "Request Sakha Transfer" in text, (
        "Sakha transfer notice should point to the member dashboard flow and "
        "the 'Sakha Transfer / Darshak' review queue"
    )
