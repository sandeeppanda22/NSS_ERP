"""
UI tests for the Self-Registration page (/register).

Tests cover the Alpine.js registerApp() multi-step form (steps 1-4):
step 1 (personal info), step 2 (membership), step 3 (password), and
navigation between steps.  All tests use the unauthenticated `page` fixture.
"""

import pytest

from tests.ui.register_support import (
    fill_step1,
)

pytestmark = pytest.mark.ui


# ------------------------------------------------------------------
# Selectors
# ------------------------------------------------------------------

FIRST_NAME_SEL = '[x-model="form.first_name"]'
LAST_NAME_SEL = '[x-model="form.last_name"]'
MOBILE_SEL = '[x-model="form.mobile_number"]'
EMAIL_SEL = '[x-model="form.email"]'
GENDER_SEL = '[x-model="form.gender_master_data_pk"]'
HAS_MEMBERSHIP_SEL = '[x-model="form.has_membership"]'
PASSWORD_SEL = '[x-model="form.password"]'
CONFIRM_PASSWORD_SEL = '[x-model="confirmPassword"]'
ERROR_BOX = ".alert-box"
STEPPER_DOT = ".stepper-dot"

# Step-specific Next buttons — use exact text to avoid picking hidden steps
# Step 1: "Next: Membership Details →", Step 2: "Next: Password →"
STEP1_NEXT_BTN = 'button:has-text("Membership Details")'
STEP2_NEXT_BTN = 'button:has-text("Password")'
REGISTER_BTN = 'button:has-text("Register")'


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _goto_register(page, base_url):
    page.goto(f"{base_url}/register")
    page.wait_for_selector(FIRST_NAME_SEL, state="visible")


def _fill_step1_required(page):
    """Fill the minimum required fields on step 1 (personal info, contact,
    and the mandatory address block) so the Next button is enabled."""
    fill_step1(page, dob="15/01/2000")


def _advance_to_step2(page):
    """Click the step 1 Next button and wait for step 2 to appear."""
    page.locator(STEP1_NEXT_BTN).click(timeout=5000)
    page.locator('[x-show="step === 2"]').wait_for(state="visible", timeout=10000)


def _advance_to_step3(page):
    """From step 2, skip membership and advance to step 3."""
    # has_membership defaults to false — just click the step 2 Next button
    page.locator(STEP2_NEXT_BTN).click(timeout=5000)
    page.locator('[x-show="step === 3"]').wait_for(state="visible", timeout=10000)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_register_page_loads(page, base_url):
    """Registration page loads with step 1 visible and stepper dots present."""
    _goto_register(page, base_url)

    step1 = page.locator('[x-show="step === 1"]')
    assert step1.is_visible(), "Step 1 should be visible on page load"

    dots = page.locator(STEPPER_DOT)
    assert dots.count() > 0, "Stepper dots should be present"

    assert page.is_visible(FIRST_NAME_SEL), "First name field should be visible"


def test_register_step1_mandatory_fields(page, base_url):
    """Step 1 requires first_name, last_name, date of birth, and gender before proceeding."""
    _goto_register(page, base_url)

    # The Next button has :disabled binding — should be disabled when fields are empty
    next_btn = page.locator(STEP1_NEXT_BTN)
    is_disabled = next_btn.is_disabled()

    if not is_disabled:
        next_btn.click()
        page.wait_for_timeout(500)
        # Should still be on step 1
        step1 = page.locator('[x-show="step === 1"]')
        assert step1.is_visible(), "Should remain on step 1 when mandatory fields are empty"
    else:
        assert is_disabled, "Next button should be disabled when mandatory fields are empty"


def test_register_step1_contact_required(page, base_url):
    """At least one of mobile number or email must be provided."""
    _goto_register(page, base_url)

    # Fill everything (incl. address) except contact info
    fill_step1(page, contact=False)

    # Ensure mobile and email are empty
    page.fill(MOBILE_SEL, "")
    page.fill(EMAIL_SEL, "")
    page.wait_for_timeout(300)

    # The Next button's :disabled binding checks (!form.mobile_number && !form.email)
    # so it should be disabled when both are empty
    next_btn = page.locator(STEP1_NEXT_BTN)
    is_disabled = next_btn.is_disabled()

    if not is_disabled:
        # Button enabled despite empty contacts — click and check goStep2() validation
        next_btn.click()
        page.wait_for_timeout(500)
        step1 = page.locator('[x-show="step === 1"]')
        error_visible = page.locator(ERROR_BOX).is_visible()
        assert step1.is_visible() or error_visible, (
            "Should remain on step 1 or show an error when no contact info is provided"
        )
    else:
        assert is_disabled, "Next button should be disabled when no contact info is provided"


def test_register_step1_to_step2_navigation(page, base_url):
    """Filling required fields and clicking Next advances to step 2."""
    _goto_register(page, base_url)
    _fill_step1_required(page)
    _advance_to_step2(page)

    step2 = page.locator('[x-show="step === 2"]')
    assert step2.is_visible(), "Step 2 should be visible after completing step 1"


def test_register_step2_back_button(page, base_url):
    """Back button on step 2 returns to step 1 with data preserved."""
    _goto_register(page, base_url)
    _fill_step1_required(page)
    _advance_to_step2(page)

    # Click back — step 2 Back button. Scoped to the step-2 card: the hidden
    # 'darshak-entry' and 'lookup' cards also have "← Back" buttons and come
    # earlier in the DOM, so an unscoped .first picked a hidden one.
    back_btn = page.locator('[x-show="step === 2"] button:has-text("Back")')
    back_btn.click()
    page.wait_for_timeout(500)

    step1 = page.locator('[x-show="step === 1"]')
    step1.wait_for(state="visible", timeout=5000)
    assert step1.is_visible(), "Step 1 should be visible after clicking Back"

    # Verify data is preserved — first name starts with "Test" (has unique suffix)
    first_name_value = page.locator(FIRST_NAME_SEL).input_value()
    assert first_name_value.startswith("Test"), "First name should be preserved after going back"

    last_name_value = page.locator(LAST_NAME_SEL).input_value()
    assert last_name_value.startswith("User"), "Last name should be preserved after going back"


def test_register_step2_to_step3(page, base_url):
    """Skipping membership on step 2 and clicking Next advances to step 3."""
    _goto_register(page, base_url)
    _fill_step1_required(page)
    _advance_to_step2(page)
    _advance_to_step3(page)

    step3 = page.locator('[x-show="step === 3"]')
    assert step3.is_visible(), "Step 3 should be visible after completing step 2"
    assert page.is_visible(PASSWORD_SEL), "Password field should be visible on step 3"


def test_register_step3_password_validation(page, base_url):
    """Password must be 8+ characters with uppercase, lowercase, and a digit."""
    _goto_register(page, base_url)
    _fill_step1_required(page)
    _advance_to_step2(page)
    _advance_to_step3(page)

    # isPasswordValid(): pw.length >= 8, /[A-Z]/.test(pw), /\d/.test(pw), confirm === pw
    # Note: no lowercase requirement — ALLUPPERCASE1 is valid
    weak_passwords = ["short", "alllowercase1", "NoDigitsHere", "Ab1"]

    for weak in weak_passwords:
        page.fill(PASSWORD_SEL, weak)
        page.fill(CONFIRM_PASSWORD_SEL, weak)
        page.wait_for_timeout(300)

        register_btn = page.locator(REGISTER_BTN).first
        is_disabled = register_btn.is_disabled()

        if not is_disabled:
            register_btn.click()
            page.wait_for_timeout(500)
            # Should still be on step 3 or show an error
            step3 = page.locator('[x-show="step === 3"]')
            error_visible = page.locator(ERROR_BOX).is_visible()
            assert step3.is_visible() or error_visible, (
                f"Weak password '{weak}' should not be accepted"
            )
        # Clear for next iteration
        page.fill(PASSWORD_SEL, "")
        page.fill(CONFIRM_PASSWORD_SEL, "")
        page.wait_for_timeout(200)


def test_register_step3_password_mismatch(page, base_url):
    """Confirm password must match the password field."""
    _goto_register(page, base_url)
    _fill_step1_required(page)
    _advance_to_step2(page)
    _advance_to_step3(page)

    page.fill(PASSWORD_SEL, "ValidPass@1")
    page.fill(CONFIRM_PASSWORD_SEL, "DifferentPass@2")
    page.wait_for_timeout(300)

    register_btn = page.locator(REGISTER_BTN).first
    is_disabled = register_btn.is_disabled()

    if not is_disabled:
        register_btn.click()
        page.wait_for_timeout(500)
        # Should remain on step 3 or show an error
        step3 = page.locator('[x-show="step === 3"]')
        error_visible = page.locator(ERROR_BOX).is_visible()
        assert step3.is_visible() or error_visible, (
            "Mismatched passwords should not be accepted"
        )
    else:
        assert is_disabled, "Register button should be disabled when passwords do not match"


def test_register_login_link(page, base_url):
    """The 'Already registered?' link navigates to /login."""
    _goto_register(page, base_url)

    login_link = page.locator("a[href*='login']")
    login_link.click()
    page.wait_for_url("**/login", timeout=5000)

    assert "/login" in page.url, "Clicking the login link should navigate to /login"
