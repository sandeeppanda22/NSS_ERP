"""
Source-level tests for the member self-service address UI on /dashboard
(personal tab, Address card): add / edit / remove / make-primary, with the
shared nssCombobox + NSSLocation wiring for geography.

Needs no browser and no running server -- parses the shipped files directly
(same style as test_ui_admin_correspondence.py).
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
HTML = (FRONTEND / "dashboard.html").read_text(encoding="utf-8")
JS = (FRONTEND / "assets" / "js" / "dashboard.js").read_text(encoding="utf-8")

PROPOSE = {
    "district_pk": "/api/v1/foundation/districts/propose",
    "city_village_pk": "/api/v1/foundation/city-villages/propose",
    "postal_code_pk": "/api/v1/foundation/postal-codes/propose",
    "post_office_pk": "/api/v1/foundation/post-offices/propose",
}
HANDLERS = [
    "startAddAddress", "startEditAddress", "cancelAddressForm", "saveAddress",
    "removeAddress", "makeAddressPrimary", "onAddrCountryChange",
    "onAddrStateChange", "addrIsPending",
]


def test_shared_scripts_and_styles_loaded():
    for needle in ("nss-location.js", "nss-combobox.js", "nss-combobox.css", "nss-dialog.js"):
        assert needle in HTML


@pytest.mark.parametrize("model,url", PROPOSE.items())
def test_each_geography_field_is_a_combobox_with_propose_url(model, url):
    assert f"nssCombobox('addrForm.{model}'" in HTML
    assert url in HTML


def test_pending_note_text_present():
    assert "New place" in HTML
    assert "reviewed by your Sakha admin" in HTML


@pytest.mark.parametrize("name", HANDLERS)
def test_handler_exists_in_js_and_is_used_in_html(name):
    assert re.search(rf"\b(async\s+)?{name}\s*\(", JS), f"{name} missing in dashboard.js"
    assert f"{name}(" in HTML, f"{name} not bound in dashboard.html"


def test_address_crud_endpoints_used():
    assert "${base}/${f.editPk}" in JS and "/addresses`" in JS
    assert '"PATCH"' in JS and '"DELETE"' in JS and '"POST"' in JS


def test_remove_uses_dialog_helper_not_window_confirm():
    block = JS[JS.index("async removeAddress"):]
    block = block[: block.index("async saveProfile")]
    assert "NSSDialog.confirm" in block
    assert "window.confirm" not in block and " confirm(" not in block.replace("NSSDialog.confirm", "")


def test_location_cascade_uses_member_accessible_base_path():
    assert "NSSLocation.create" in JS
    assert 'basePath: "/api/v1/register"' in JS
    assert 'form: "addrForm"' in JS


def test_no_inline_event_handlers_added_in_address_card():
    card = HTML[HTML.index("Add / edit address form"):]
    card = card[: card.index("personal-col (left)")]
    assert not re.search(r"\son(click|change|input)=", card)


def test_pin_is_district_narrowed_and_disabled_until_district():
    assert "data-cb-disabled=\"!addrForm.district_pk\"" in HTML[HTML.index("nssCombobox('addrForm.postal_code_pk'"):][:900]
    assert "loadPostalCodes(this, f.district_pk)" in JS
    assert "loadPostalCodes(this, f.state_pk)" not in JS


def test_district_change_clears_dependents_except_while_prefilling():
    block = JS[JS.index("async _onAddrDistrictChanged"):]
    block = block[: block.index("async _loadAddrPostOffices")]
    assert "_addrPrefilling" in block
    for field in ("city_village_pk", "postal_code_pk", "post_office_pk"):
        assert f"addrForm.{field} = \"\"" in block
    assert "_addrPrefilling = true" in JS and "_addrPrefilling = false" in JS


def test_save_address_refuses_orphan_dependents():
    block = JS[JS.index("async saveAddress"):]
    assert "Choose a district before" in block and "Choose a PIN before" in block
