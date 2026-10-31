"""
Source-level tests for the admin.html / admin.js dependent-dropdown fixes
(owner decision 2026-10-30: every child list resets when its parent changes,
PIN narrowed by DISTRICT, stale async responses are discarded).

Needs no browser and no running server -- parses the shipped files directly
(same style as test_ui_dashboard_address.py).
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
HTML = (FRONTEND / "admin.html").read_text(encoding="utf-8")
JS = (FRONTEND / "assets" / "js" / "admin.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    """Source of method `name` up to the next 8-space-indented member."""
    m = re.search(rf"^        (?:async\s+)?{re.escape(name)}\s*\(.*?\)\s*\{{", JS, re.M)
    assert m, f"{name} not found in admin.js"
    nxt = re.search(r"^        (?:async\s+|get\s+)?[A-Za-z_]\w*\s*[\(:]", JS[m.end():], re.M)
    return JS[m.start(): m.end() + (nxt.start() if nxt else len(JS))]


@pytest.mark.parametrize("cascade,arr", [("_createLocCascade", "createOrgPostalCodes"),
                                         ("_editLocCascade", "locationPostalCodes")])
def test_org_forms_declare_postal_code_array_for_the_cascade(cascade, arr):
    start = JS.index(f"{cascade}: NSSLocation.create(")
    block = JS[start:start + 500]
    assert f"postalCodes: '{arr}'" in block
    assert re.search(rf"^        {arr}: \[\],", JS, re.M)


@pytest.mark.parametrize("model,arr,listid", [
    ("createOrgForm", "createOrgPostalCodes", "createOrgPostalCodeOptions"),
    ("editOrgForm", "locationPostalCodes", "editOrgPostalCodeOptions"),
])
def test_org_pin_input_is_district_gated_datalist_and_still_typeable(model, arr, listid):
    m = re.search(rf'<input[^>]*x-model="{model}\.postal_code_value"[^>]*>', HTML)
    assert m
    tag = m.group(0)
    assert f'list="{listid}"' in tag
    assert f':disabled="!{model}.district_pk"' in tag
    assert f'<datalist id="{listid}">' in HTML
    assert f'x-for="pc in {arr}"' in HTML


def test_edit_prefill_loads_pins_by_district():
    assert "loadLocationPostalCodes(org.district_pk)" in JS
    assert "loadPostalCodes(this, pk)" in JS


def test_geography_selects_are_bound_and_gated():
    for model, fn, gate in [("geoCountryPk", "geoSelectCountry", None),
                            ("geoStatePk", "geoSelectState", "geoCountryPk"),
                            ("geoDistrictPk", "geoSelectDistrict", "geoStatePk")]:
        m = re.search(rf'<select[^>]*@change="{fn}\(\$event\.target\.value\)"[^>]*>', HTML)
        assert m, fn
        assert f'x-model="{model}"' in m.group(0)
        if gate:
            assert f':disabled="!{gate}"' in m.group(0)


def test_geography_reset_helper_clears_every_dependent():
    body = _body("_geoResetBelow")
    for field in ("geoPostalCodePk", "geoCityPk", "geoPostOffices", "geoPostalCodeQuery",
                  "geoCityQuery", "geoSakhaQuery", "geoCities", "geoPostalCodes", "geoSakhas",
                  "geoDistrictPk", "geoDistricts", "geoStatePk", "geoStates",
                  "geoCitiesFallbackNotice"):
        assert field in body, field


@pytest.mark.parametrize("fn,level", [("geoSelectCountry", "country"),
                                      ("geoSelectState", "state"),
                                      ("geoSelectDistrict", "district")])
def test_geography_handlers_reset_and_guard_stale_responses(fn, level):
    body = _body(fn)
    assert f'_geoResetBelow("{level}")' in body
    assert "++this._geoSeq" in body
    assert "seq !== this._geoSeq" in body


def test_geography_pin_scope_uses_district_when_chosen():
    assert "postal-codes?district_pk=${districtPk}" in _body("geoSelectDistrict")
    assert "district_pk=${this.geoDistrictPk}" in _body("geoSearchPostalCodes")


def test_governance_body_change_resets_assign_state_and_guards():
    reset = _body("_resetGovBodyDependents")
    for field in ("govAssignForm", "govActingForm", "govAllowedPositions", "govAssignments",
                  "govInheritedPositions", "govSakhaFilter"):
        assert field in reset, field
    assert "_resetGovBodyDependents()" in _body("onGovBodyChange")
    bodies = _body("loadGovBodies")
    assert "govAssignableBodies" in bodies and 'this.govSelectedBodyPk = ""' in bodies
    for fn in ("loadGovAssignments", "_loadGovAllowedPositions", "searchGovPerson"):
        assert "bodyPk !== this.govSelectedBodyPk" in _body(fn), fn
    assert "stale()" in _body("loadGovBodySakhaScope")


def test_nomination_form_resets_on_election_change():
    opened = _body("openGovElection")
    assert "this.govNominationForm = this._blankGovNominationForm()" in opened
    blank = _body("_blankGovNominationForm")
    assert 'position_master_pk: ""' in blank and "selectedCandidate: null" in blank
    assert "_blankGovNominationForm()" in _body("createGovNomination")
    for fn in ("loadGovNominations", "loadGovElectionPositions"):
        assert "electionPk !== this.govSelectedElectionPk" in _body(fn), fn


def test_kumari_sevak_scope_has_stale_guard():
    body = _body("loadKumariSevakScope")
    assert "stale()" in body and "organization_type_code !== typeCode" in body


def test_correspondence_auto_resolve_clears_recipient():
    assert "this.corrClearPicker(f.recipientOrg)" in _body("corrResolveDefaultOrg")


def test_assign_role_button_needs_org_when_scope_requires_it():
    m = re.search(r'<button[^>]*@click="submitAssignRole\(\)"[^>]*>', HTML)
    assert m
    assert "roleScopeNeedsOrg && !roleForm.organization_pk" in m.group(0)
