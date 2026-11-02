"""
Shared Playwright helpers for the /register page UI tests.

Used by test_ui_register.py and test_ui_06_register_submit.py so the Step 1
fill logic lives in exactly one place. Step 1's "Next: Membership Details"
button stays :disabled until personal info, a contact, AND the full address
block (country/state/district, city/village, PIN, address line 1) are filled,
so every test that leaves Step 1 must go through fill_step1().
"""

import time

from playwright.sync_api import Page

FIRST_NAME_SEL = '[x-model="form.first_name"]'
LAST_NAME_SEL = '[x-model="form.last_name"]'
EMAIL_SEL = '[x-model="form.email"]'
GENDER_SEL = '[x-model="form.gender_master_data_pk"]'
COUNTRY_SEL = '[x-model="form.country_pk"]'
STATE_SEL = '[x-model="form.state_pk"]'
DISTRICT_SEL = '[x-model="form.district_pk"]'
CITY_SEL = '[x-model="form.city_village_name"]'
POSTAL_SEL = '[x-model="form.postal_code_value"]'
ADDRESS1_SEL = '[x-model="form.address_line_1"]'

# DOB uses the shared nssDatePicker: root carries data-nss-dp="<model path>",
# the visible input inside has x-model="display" (DD/MM/YYYY, auto-parsed to
# ISO). Do NOT match on the x-data text (see nssDatePicker('form.date_of_birth', {...})).
DOB_PICKER_SEL = '[data-nss-dp="form.date_of_birth"]'
DOB_INPUT_SEL = f'{DOB_PICKER_SEL} input[x-model="display"]'


def unique_suffix() -> str:
    """Unique suffix for test data to avoid duplicate-check collisions."""
    return str(int(time.time()))[-6:]


def fill_dob(page: Page, dd_mm_yyyy: str):
    """Type digits into the nssDatePicker (real keystrokes so @input fires)."""
    dob_input = page.locator(DOB_INPUT_SEL)
    if dob_input.count() == 0:
        return
    dob_input.first.click()
    page.wait_for_timeout(200)
    dob_input.first.fill("")
    page.wait_for_timeout(100)
    dob_input.first.type(dd_mm_yyyy.replace("/", ""), delay=50)
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)


def wait_for_options(page: Page, selector: str, timeout: int = 15000):
    """Wait until a <select> has more than the placeholder option."""
    page.wait_for_function(
        "sel => document.querySelector(sel)?.options?.length > 1",
        arg=selector,
        timeout=timeout,
    )


def wait_for_gender_options(page: Page, timeout: int = 15000):
    """Wait for init()'s async loadReferenceData() to populate genders."""
    wait_for_options(page, GENDER_SEL, timeout)


def select_country(page: Page):
    """Pick India (falls back to the first country) once the list has loaded.

    Not simply option index 1: the list is not guaranteed to start with India,
    and only India has seeded states/districts.
    """
    wait_for_options(page, COUNTRY_SEL)
    country = page.locator(COUNTRY_SEL)
    try:
        country.select_option(label="India", timeout=2000)
    except Exception:
        country.select_option(index=1)


def fill_address(page: Page):
    """Fill the mandatory Step 1 address block via the cascading selects.

    Country -> State -> District are dependent selects (each disabled until its
    parent is chosen and populated async), so wait for options between picks.
    Prefers India; falls back to the first country. Tries successive states
    until one has districts, since seed coverage can differ per state.
    City/village and PIN are free text (resolved/created server-side).
    """
    select_country(page)

    wait_for_options(page, STATE_SEL)
    state = page.locator(STATE_SEL)
    n_states = state.locator("option").count() - 1
    for idx in range(1, min(n_states, 5) + 1):
        state.select_option(index=idx)
        try:
            wait_for_options(page, DISTRICT_SEL, timeout=5000)
            break
        except Exception:
            continue
    else:
        raise AssertionError("No state with districts found in the first 5 states")
    page.locator(DISTRICT_SEL).select_option(index=1)

    # City input is enabled only once a district is selected.
    page.fill(CITY_SEL, "TestVillage")
    page.fill(POSTAL_SEL, "751024")
    page.fill(ADDRESS1_SEL, "1 Test Street")


def fill_step1(page: Page, suffix: str | None = None, *, dob: str = "15/06/1995",
               contact: bool = True, address: bool = True) -> str:
    """Fill every Step 1 field needed to enable 'Next: Membership Details'.

    Returns the suffix used. contact=False leaves mobile/email empty and
    address=False skips the address block, for tests of the disabled gate.
    """
    suffix = suffix or unique_suffix()
    page.fill(FIRST_NAME_SEL, f"Test{suffix}")
    page.fill(LAST_NAME_SEL, f"User{suffix}")
    fill_dob(page, dob)

    wait_for_gender_options(page)
    gender = page.locator(GENDER_SEL)
    if gender.is_visible():
        gender.select_option(index=1)

    if contact:
        page.fill(EMAIL_SEL, f"testuser{suffix}@example.com")
    if address:
        fill_address(page)
    page.wait_for_timeout(300)
    return suffix
