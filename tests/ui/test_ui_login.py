"""
UI tests for the Login page (/login).

Tests cover the Alpine.js loginApp() form: field validation, credential
verification, password visibility toggle, forgot-password flow, and the
register link.  All tests use the unauthenticated `page` fixture.
"""

import pytest
from tests.ui.conftest import (
    ADMIN_SS_ID,
    ADMIN_PASSWORD_BOOTSTRAP,
    ADMIN_PASSWORD_NEW,
)

pytestmark = pytest.mark.ui


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

LOGIN_ID_SEL = '[x-model="login_id"]'
PASSWORD_SEL = '[x-model="password"]'
SIGN_IN_BTN = "button:has-text('Sign In')"
EYE_BTN = '.eye-btn[\\@click="showPassword = !showPassword"]'
ERROR_DIV = '[x-text="error"]'
CHANGE_PW_NEW_SEL = '[x-model="newPassword"]'
CHANGE_PW_CONFIRM_SEL = '[x-model="confirmPassword"]'
CHANGE_PW_BTN = "button:has-text('Change Password')"


def _goto_login(page, base_url):
    page.goto(f"{base_url}/login")
    page.wait_for_selector(LOGIN_ID_SEL, state="visible")


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_login_page_loads(page, base_url):
    """Login page loads with the form visible and a title present."""
    _goto_login(page, base_url)

    assert page.is_visible(LOGIN_ID_SEL), "Login ID field should be visible"
    assert page.is_visible(PASSWORD_SEL), "Password field should be visible"
    assert page.is_visible(SIGN_IN_BTN), "Sign In button should be visible"
    title = page.title()
    assert title, "Page should have a non-empty title"


def test_login_empty_fields_disabled(page, base_url):
    """Sign In button should be disabled or non-functional when fields are empty."""
    _goto_login(page, base_url)

    btn = page.locator(SIGN_IN_BTN)
    is_disabled = btn.is_disabled()
    # Some implementations use :disabled, others use Alpine x-bind:disabled
    if not is_disabled:
        # Click and verify no navigation occurs (stays on /login)
        btn.click()
        page.wait_for_timeout(500)
        assert "/login" in page.url, "Should remain on login page when fields are empty"
    else:
        assert is_disabled, "Sign In button should be disabled with empty fields"


def test_login_invalid_credentials(page, base_url):
    """Submitting a valid user ID with a wrong password shows an error message."""
    _goto_login(page, base_url)

    page.fill(LOGIN_ID_SEL, ADMIN_SS_ID)
    page.fill(PASSWORD_SEL, "WrongPassword!99")
    page.wait_for_timeout(300)

    page.locator(SIGN_IN_BTN).click()
    page.wait_for_timeout(1000)

    error_el = page.locator(ERROR_DIV)
    error_el.wait_for(state="visible", timeout=5000)
    error_text = error_el.text_content()
    assert error_text and len(error_text) > 0, "An error message should be displayed for invalid credentials"


def test_login_invalid_user(page, base_url):
    """Submitting a non-existent user ID shows an error message."""
    _goto_login(page, base_url)

    page.fill(LOGIN_ID_SEL, "NONEXISTENT999")
    page.fill(PASSWORD_SEL, "SomePassword@1")
    page.wait_for_timeout(300)

    page.locator(SIGN_IN_BTN).click()
    page.wait_for_timeout(1000)

    error_el = page.locator(ERROR_DIV)
    error_el.wait_for(state="visible", timeout=5000)
    error_text = error_el.text_content()
    assert error_text and len(error_text) > 0, "An error message should be displayed for a non-existent user"


def test_login_success_redirect(page, base_url):
    """Valid credentials redirect to /dashboard (handles force_password_change)."""
    _goto_login(page, base_url)

    # Try the post-change password first; fall back to bootstrap default
    page.fill(LOGIN_ID_SEL, ADMIN_SS_ID)
    page.fill(PASSWORD_SEL, ADMIN_PASSWORD_NEW)
    page.wait_for_timeout(300)
    page.locator(SIGN_IN_BTN).click()
    page.wait_for_timeout(1500)

    # If still on /login, check whether force_password_change form appeared
    if "/login" in page.url:
        change_form = page.locator(CHANGE_PW_NEW_SEL)
        error_el = page.locator(ERROR_DIV)

        if change_form.is_visible():
            # force_password_change — fill and submit
            page.fill(CHANGE_PW_NEW_SEL, ADMIN_PASSWORD_NEW)
            page.fill(CHANGE_PW_CONFIRM_SEL, ADMIN_PASSWORD_NEW)
            page.wait_for_timeout(300)
            page.click(CHANGE_PW_BTN)
            page.wait_for_url(lambda url: "/login" not in url, timeout=15000)

        elif error_el.is_visible() and error_el.text_content():
            # Wrong password — retry with bootstrap default
            page.fill(LOGIN_ID_SEL, "")
            page.wait_for_timeout(200)
            page.fill(LOGIN_ID_SEL, ADMIN_SS_ID)
            page.fill(PASSWORD_SEL, ADMIN_PASSWORD_BOOTSTRAP)
            page.wait_for_timeout(300)
            page.locator(SIGN_IN_BTN).click()
            page.wait_for_timeout(1500)

            # Handle force_password_change after bootstrap login
            if "/login" in page.url and page.locator(CHANGE_PW_NEW_SEL).is_visible():
                page.fill(CHANGE_PW_NEW_SEL, ADMIN_PASSWORD_NEW)
                page.fill(CHANGE_PW_CONFIRM_SEL, ADMIN_PASSWORD_NEW)
                page.wait_for_timeout(300)
                page.click(CHANGE_PW_BTN)
                page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
            else:
                page.wait_for_url(lambda url: "/login" not in url, timeout=10000)

    assert "/dashboard" in page.url, "Should redirect to /dashboard after successful login"


def test_login_show_password_toggle(page, base_url):
    """Clicking the eye button toggles password field between 'password' and 'text' type."""
    _goto_login(page, base_url)

    password_input = page.locator(PASSWORD_SEL)
    page.fill(PASSWORD_SEL, "SomeSecret")

    # Initially the type should be "password"
    initial_type = password_input.get_attribute("type")
    assert initial_type == "password", "Password field should start with type='password'"

    # The shared x-pw-reveal directive (nss-password.js) wraps the input in .pw-reveal-wrap
    # next to a .pw-reveal-btn eye button.
    eye_btn = password_input.locator("xpath=..").locator(".pw-reveal-btn")
    eye_btn.click()
    page.wait_for_timeout(300)
    revealed_type = password_input.get_attribute("type")
    assert revealed_type == "text", "After clicking eye button, type should change to 'text'"

    # Click again to hide
    eye_btn.click()
    page.wait_for_timeout(300)
    hidden_type = password_input.get_attribute("type")
    assert hidden_type == "password", "After clicking eye button again, type should revert to 'password'"


def test_login_forgot_password_link(page, base_url):
    """Clicking the forgot password link shows the forgot password form."""
    _goto_login(page, base_url)

    # Click the forgot password trigger — use the specific link, not heading text
    forgot_link = page.locator('a.forgot-link:has-text("Forgot Password?")')
    forgot_link.click()
    page.wait_for_timeout(500)

    # The forgot password section should become visible
    forgot_section = page.locator('[x-show="showForgotPassword"]')
    forgot_section.wait_for(state="visible", timeout=5000)
    assert forgot_section.is_visible(), "Forgot password form should be visible after clicking the link"


def test_login_register_link(page, base_url):
    """The register link navigates to /register."""
    _goto_login(page, base_url)

    register_link = page.locator("a[href*='register']")
    register_link.click()
    page.wait_for_url("**/register", timeout=5000)

    assert "/register" in page.url, "Clicking the register link should navigate to /register"
