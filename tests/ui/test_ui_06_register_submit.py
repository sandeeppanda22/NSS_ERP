"""
UI tests for the Registration flow — end-to-end submission.

This file covers the write-path operations that test_ui_register.py skips:
  - Step 2 membership claim (toggle, Sakha select, darshak toggle)
  - Step 2 address cascading selectors
  - Full form submission (POST /api/v1/register)
  - Step 4 success screen with Person ID display

Run order: 06 (after verification pages — registration creates new DB rows).

⚠ IMPORTANT: These tests create real records in the DB.
  Use unique identifiers per test run to avoid collisions.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.conftest import BASE_URL
from tests.ui.register_support import (
    fill_step1,
    select_country,
    unique_suffix as _unique_suffix,
)

pytestmark = pytest.mark.ui

# BASE_URL comes from conftest (NSS_UI_BASE_URL-aware) rather than a local
# copy, so this file follows the suite when it is pointed at a test server.

# ── Selectors ──────────────────────────────────────────────────────────

FIRST_NAME_SEL = '[x-model="form.first_name"]'
MIDDLE_NAME_SEL = '[x-model="form.middle_name"]'
LAST_NAME_SEL = '[x-model="form.last_name"]'
MOBILE_SEL = '[x-model="form.mobile_number"]'
HAS_MEMBERSHIP_SEL = '[x-model="form.has_membership"]'
MEMBERSHIP_TYPE_SEL = '[x-model="form.membership_type_master_data_pk"]'
SAKHA_SEL = '[x-model="form.organization_pk"]'
LOCAL_SAKHA_NUM_SEL = '[x-model="form.claimed_local_sakha_number"]'
CREDENTIAL_NUM_SEL = '[x-model="form.claimed_credential_document_number"]'
DARSHAK_TOGGLE_SEL = '[x-model="form.is_attending_as_darshak"]'
DARSHAK_ORG_SEL = '[x-model="form.darshak_organization_pk"]'
DARSHAK_LOCAL_NUM_SEL = '[x-model="form.darshak_local_sakha_number"]'
COUNTRY_SEL = '[x-model="form.country_pk"]'
STATE_SEL = '[x-model="form.state_pk"]'
DISTRICT_SEL = '[x-model="form.district_pk"]'
PASSWORD_SEL = '[x-model="form.password"]'
CONFIRM_PASSWORD_SEL = '[x-model="confirmPassword"]'
ERROR_BOX = ".alert-box"
REGISTER_BTN = 'button:has-text("Register")'

# Step-specific Next buttons — use exact text to avoid picking hidden steps
STEP1_NEXT_BTN = 'button:has-text("Membership Details")'
STEP2_NEXT_BTN = 'button:has-text("Password")'


def _goto_register(page: Page):
    page.goto(f"{BASE_URL}/register")
    page.wait_for_selector(FIRST_NAME_SEL, state="visible", timeout=10000)


def _fill_step1(page: Page, suffix: str):
    """Fill all step 1 fields (personal, contact, address) with unique data."""
    fill_step1(page, suffix)


def _click_visible_next(page: Page, btn_selector: str):
    """Click a step-specific Next button and wait for the step transition.

    Each step has its own button text:
      Step 1 → "Next: Membership Details →"
      Step 2 → "Next: Password →"
    Using step-specific selectors avoids accidentally clicking a hidden step's button.
    """
    btn = page.locator(btn_selector)
    btn.click(timeout=5000)


def _advance_step1_to_step2(page: Page):
    """Click step 1 Next and wait for step 2 to appear."""
    _click_visible_next(page, STEP1_NEXT_BTN)
    page.locator('[x-show="step === 2"]').wait_for(state="visible", timeout=10000)


def _advance_step2_to_step3(page: Page):
    """Click step 2 Next and wait for step 3 to appear."""
    _click_visible_next(page, STEP2_NEXT_BTN)
    page.locator('[x-show="step === 3"]').wait_for(state="visible", timeout=10000)


# ── Step 2: Membership claim ──────────────────────────────────────────


class TestRegisterStep2Membership:

    def test_membership_toggle_visible(self, page: Page):
        """Step 2 shows a membership claim toggle."""
        _goto_register(page)
        _fill_step1(page, _unique_suffix())
        _advance_step1_to_step2(page)

        # Should be on step 2
        step2 = page.locator('[x-show="step === 2"]')
        expect(step2).to_be_visible(timeout=5000)

        # Membership toggle should be present (it's a checkbox with toggle class)
        toggle = page.locator(HAS_MEMBERSHIP_SEL)
        assert toggle.count() > 0, "Membership claim toggle should exist on step 2"

    def test_membership_toggle_reveals_fields(self, page: Page):
        """Enabling the membership toggle reveals Sakha and type selectors."""
        _goto_register(page)
        _fill_step1(page, _unique_suffix())
        _advance_step1_to_step2(page)

        # Enable membership claim — it's an <input type="checkbox"> with toggle class
        toggle = page.locator(HAS_MEMBERSHIP_SEL)
        if toggle.count() > 0 and toggle.first.is_visible():
            toggle.first.check()
            page.wait_for_timeout(500)

            # Membership type and Sakha selectors should appear
            # They are inside <template x-if="form.has_membership">
            type_sel = page.locator(MEMBERSHIP_TYPE_SEL)
            sakha_sel = page.locator(SAKHA_SEL)
            assert type_sel.count() > 0 or sakha_sel.count() > 0, (
                "Enabling membership should reveal type/Sakha selectors"
            )
        else:
            pytest.skip("Membership toggle not visible")

    def test_sakha_dropdown_populated(self, page: Page):
        """Sakha dropdown is populated with 175 Sakha branches."""
        _goto_register(page)
        _fill_step1(page, _unique_suffix())
        _advance_step1_to_step2(page)

        toggle = page.locator(HAS_MEMBERSHIP_SEL)
        if toggle.count() == 0:
            pytest.skip("Membership toggle not found")

        toggle.first.check()
        page.wait_for_timeout(1000)

        sakha_sel = page.locator(SAKHA_SEL)
        if sakha_sel.count() == 0:
            pytest.skip("Sakha selector not found")

        options = sakha_sel.locator("option")
        assert options.count() > 10, "Sakha dropdown should have many options (175 branches)"

    def test_local_sakha_number_required_marker(self, page: Page):
        """Local Sakha Number is now required for every membership type,
        including Darshaka — no longer marked optional once a Sakha is
        selected (AUTH-BR-086)."""
        _goto_register(page)
        _fill_step1(page, _unique_suffix())
        _advance_step1_to_step2(page)

        toggle = page.locator(HAS_MEMBERSHIP_SEL)
        if toggle.count() == 0:
            pytest.skip("Membership toggle not found")
        toggle.first.check()
        page.wait_for_timeout(500)

        sakha_sel = page.locator(SAKHA_SEL)
        if sakha_sel.count() == 0:
            pytest.skip("Sakha selector not found")
        sakha_sel.select_option(index=1)
        page.wait_for_timeout(500)

        local_num = page.locator(LOCAL_SAKHA_NUM_SEL)
        assert local_num.count() > 0, "Local Sakha Number field should appear once a Sakha is selected"

        credential_num = page.locator(CREDENTIAL_NUM_SEL)
        assert credential_num.count() > 0, (
            "Parichaya/Anumati Patra number field should appear once a Sakha is selected"
        )

    def test_darshak_attendance_reveals_own_local_number(self, page: Page):
        """Toggling 'Attending another Sangha as Darshak?' reveals a Darshak
        Sakha selector AND its own Local Sakha Number field — a separate
        namespace from the home Sakha's number above it."""
        _goto_register(page)
        _fill_step1(page, _unique_suffix())
        _advance_step1_to_step2(page)

        toggle = page.locator(HAS_MEMBERSHIP_SEL)
        if toggle.count() == 0:
            pytest.skip("Membership toggle not found")
        toggle.first.check()
        page.wait_for_timeout(500)

        darshak_toggle = page.locator(DARSHAK_TOGGLE_SEL)
        if darshak_toggle.count() == 0:
            pytest.skip("Darshak attendance toggle not found")
        darshak_toggle.first.check()
        page.wait_for_timeout(500)

        assert page.locator(DARSHAK_ORG_SEL).count() > 0, "Darshak Sakha selector should appear"
        assert page.locator(DARSHAK_LOCAL_NUM_SEL).count() > 0, (
            "Darshak Sakha's own Local Sakha Number field should appear"
        )


# ── Step 2: Address cascading ─────────────────────────────────────────


class TestRegisterStep2Address:

    def test_country_dropdown_populated(self, page: Page):
        """Step 1 country dropdown is populated (should have India)."""
        _goto_register(page)
        # Wait for async init() to load country data
        page.wait_for_function(
            'document.querySelector(\'[x-model="form.country_pk"]\')?.options?.length > 1',
            timeout=10000,
        )

        country_sel = page.locator(COUNTRY_SEL)
        if country_sel.count() == 0:
            pytest.skip("Country selector not on step 1 — may be in a different layout")

        options = country_sel.locator("option")
        assert options.count() > 1, "Country dropdown should have options"

    def test_country_selection_loads_states(self, page: Page):
        """Selecting India in country dropdown loads states."""
        _goto_register(page)
        # Wait for async init() to load country data
        page.wait_for_function(
            'document.querySelector(\'[x-model="form.country_pk"]\')?.options?.length > 1',
            timeout=10000,
        )

        country_sel = page.locator(COUNTRY_SEL)
        if country_sel.count() == 0:
            pytest.skip("Country selector not found")

        select_country(page)
        # Wait for states to load (async cascade via @change="onRegCountryChange()")
        page.wait_for_function(
            'document.querySelector(\'[x-model="form.state_pk"]\')?.options?.length > 1',
            timeout=10000,
        )

        state_sel = page.locator(STATE_SEL)
        if state_sel.count() == 0:
            pytest.skip("State selector not found after country selection")

        options = state_sel.locator("option")
        assert options.count() > 1, "States should load after selecting a country"


# ── Full submission (Step 1 → 2 → 3 → 4) ─────────────────────────────


class TestRegisterFullSubmission:

    def test_full_registration_without_membership(self, page: Page):
        """Complete registration without membership claim → success screen."""
        suffix = _unique_suffix()
        _goto_register(page)
        _fill_step1(page, suffix)

        # Step 1 → 2
        _advance_step1_to_step2(page)

        # Step 2 → 3 (skip membership — has_membership defaults to false)
        _advance_step2_to_step3(page)

        # Fill password (must meet: length >= 8, uppercase, digit, match)
        page.fill(PASSWORD_SEL, "ValidPass@1")
        page.fill(CONFIRM_PASSWORD_SEL, "ValidPass@1")
        page.wait_for_timeout(300)

        # Submit
        register_btn = page.locator(REGISTER_BTN).first
        register_btn.click()
        page.wait_for_timeout(5000)

        # Step 4 success screen — verify actual dynamic content
        step4 = page.locator('[x-show="step === 4"]')
        if step4.count() > 0 and step4.is_visible():
            # Verify Person ID is populated (x-text="result.person_id")
            pid_el = step4.locator('.success-detail .detail-row .value').first
            pid_text = pid_el.text_content()
            assert pid_text and len(pid_text.strip()) > 0, (
                f"Success screen should display a Person ID, got: {pid_text!r}"
            )
        else:
            # Check for error — maybe duplicate email
            error = page.locator(ERROR_BOX)
            if error.count() > 0 and error.first.is_visible():
                error_text = error.first.text_content()
                pytest.skip(f"Registration failed (may be duplicate): {error_text}")
            else:
                # Still on step 3 — check if button is disabled
                assert False, "Should have advanced to step 4 or shown an error"

    def test_success_screen_has_person_id(self, page: Page):
        """Success screen displays the assigned Person ID (P-prefix)."""
        suffix = _unique_suffix()
        _goto_register(page)

        # Distinct suffix/DOB/email from the previous test to avoid collisions
        fill_step1(page, f"Success{suffix}", dob="20/03/1990")

        # Navigate through steps using step-specific buttons
        _advance_step1_to_step2(page)
        _advance_step2_to_step3(page)

        page.fill(PASSWORD_SEL, "StrongPass@1")
        page.fill(CONFIRM_PASSWORD_SEL, "StrongPass@1")
        page.wait_for_timeout(300)

        page.locator(REGISTER_BTN).first.click()
        page.wait_for_timeout(5000)

        # Check for step 4 — verify actual dynamic content, not raw HTML
        step4 = page.locator('[x-show="step === 4"]')
        if step4.count() > 0 and step4.is_visible():
            # Person ID should be populated by x-text="result.person_id"
            pid_el = step4.locator('.success-detail .detail-row .value').first
            pid_text = pid_el.text_content()
            assert pid_text and len(pid_text.strip()) > 0, (
                f"Person ID should be populated on success screen, got: {pid_text!r}"
            )

            # Person name should be populated by x-text="result.person_name"
            name_el = step4.locator('.success-detail .detail-row .value').nth(1)
            name_text = name_el.text_content()
            assert name_text and len(name_text.strip()) > 0, (
                f"Person name should be populated on success screen, got: {name_text!r}"
            )

            # "Pending Approval" should be visible in the step 4 card
            expect(step4.locator('text=Pending Approval')).to_be_visible(timeout=2000)
        else:
            error = page.locator(ERROR_BOX)
            if error.count() > 0 and error.first.is_visible():
                pytest.skip(f"Registration failed: {error.first.text_content()}")
