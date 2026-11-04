"""
Aadhaar capture / reveal UI (GDR-011) - source-level + node-run logic tests.

No browser, no server, no DB. Two layers:
  1. LOGIC (needs `node`): the shared validator block in nss-config.js
     (NSS.aadhaar, between the AADHAAR-BEGIN/END markers) is run under node and
     compared with api/services/aadhaar_service.py on the same vectors.
  2. SOURCE: the field/validator are on register + admin forms, request bodies
     add `aadhaar_number` only through payloadValue (omitted when blank), the
     reveal button is gated, the revealed value is cleared on close and never
     stored/logged, and the dashboard self-service profile has no Aadhaar input.

Run DB-free with `pytest --noconftest tests/ui/test_ui_aadhaar.py`. Nothing here
proves the screens work in a browser.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from api.services import aadhaar_service as svc

pytestmark = pytest.mark.ui

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
JS = FE / "assets" / "js"
CONFIG_JS = (JS / "nss-config.js").read_text(encoding="utf-8")
ADMIN_JS = (JS / "admin.js").read_text(encoding="utf-8")
REGISTER_JS = (JS / "register.js").read_text(encoding="utf-8")
ADMIN_HTML = (FE / "admin.html").read_text(encoding="utf-8")
REGISTER_HTML = (FE / "register.html").read_text(encoding="utf-8")
DASHBOARD_HTML = (FE / "dashboard.html").read_text(encoding="utf-8")
node = shutil.which("node")


def _check_digit(payload: str) -> str:
    return next(d for d in "0123456789" if svc.verhoeff_valid(payload + d))


def _make(first: str, body: str) -> str:
    payload = (first + body)[:11]
    return payload + _check_digit(payload)


VALID = [_make("2", "3456789012"), _make("9", "8765432109"), _make("5", "0000000000")]
BAD_CHECKSUM = VALID[0][:-1] + str((int(VALID[0][-1]) + 1) % 10)
INPUTS = [
    VALID[0], f"{VALID[0][:4]} {VALID[0][4:8]} {VALID[0][8:]}", f"{VALID[0][:4]}-{VALID[0][4:8]}-{VALID[0][8:]}",
    f"  {VALID[0]}\t", VALID[1], VALID[2],
    BAD_CHECKSUM, "1234", "", "   ", "23456789012", VALID[0] + "0", "abcdefghijkl",
    _make("0", "3456789012"), _make("1", "3456789012"), VALID[0][:6] + "x" + VALID[0][7:],
]


def _python_result(raw: str):
    try:
        return svc.normalise_aadhaar(raw)
    except svc.AadhaarFormatError:
        return None


def _block() -> str:
    m = re.search(r"/\* AADHAAR-BEGIN \*/(.*?)/\* AADHAAR-END \*/", CONFIG_JS, re.DOTALL)
    assert m, "AADHAAR-BEGIN/END markers missing from nss-config.js"
    return m.group(1)


def _node(expr: str, data):
    code = f"const NSS = {{}}; {_block()}\nconst DATA = {json.dumps(data)};\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# -- Logic parity ------------------------------------------------------------

@pytest.mark.skipif(node is None, reason="node not installed")
def test_js_normalise_matches_python_on_every_vector():
    js = _node("DATA.map(v => NSS.aadhaar.normalise(v))", INPUTS)
    assert js == [_python_result(v) for v in INPUTS]


@pytest.mark.skipif(node is None, reason="node not installed")
def test_js_validate_blank_is_ok_and_invalid_uses_the_server_wording():
    res = _node("DATA.map(v => NSS.aadhaar.validate(v))", INPUTS)
    for raw, err in zip(INPUTS, res):
        if not raw.strip():
            assert err == ""
        else:
            assert (err == "") == (_python_result(raw) is not None), raw
            if err:
                assert err == svc.MALFORMED_MESSAGE


@pytest.mark.skipif(node is None, reason="node not installed")
def test_js_verhoeff_matches_python():
    samples = VALID + [BAD_CHECKSUM, "0", "12345", "2363", "x"]
    assert _node("DATA.map(v => NSS.aadhaar.verhoeffValid(v))", samples) == [svc.verhoeff_valid(s) for s in samples]


@pytest.mark.skipif(node is None, reason="node not installed")
def test_js_group_mask_and_payload_value():
    assert _node("NSS.aadhaar.group(DATA)", "234567890123456") == "2345 6789 0123"
    assert _node("NSS.aadhaar.group(DATA)", "2345-67") == "2345 67"
    assert _node("NSS.aadhaar.mask(DATA)", "1234") == "XXXX-XXXX-1234"
    assert _node("NSS.aadhaar.mask(DATA)", None) == ""
    v = VALID[0]
    spaced = f"{v[:4]} {v[4:8]} {v[8:]}"
    # blank omits the key; clear sends ""; a value sends the plain digits
    got = _node("[NSS.aadhaar.payloadValue('', false) === undefined, NSS.aadhaar.payloadValue('  ', false) === undefined,"
                " NSS.aadhaar.payloadValue('', true), NSS.aadhaar.payloadValue(DATA, false)]", spaced)
    assert got == [True, True, "", v]


# -- Source: forms -----------------------------------------------------------

def test_validator_is_defined_once_in_nss_config_only():
    assert "NSS.aadhaar = (() =>" in CONFIG_JS
    for src in (ADMIN_JS, REGISTER_JS):
        assert "verhoeff" not in src.lower() and "_VERHOEFF" not in src
    assert not (JS / "aadhaar.js").exists()


def test_register_form_has_optional_field_and_sends_only_when_non_empty():
    assert "Aadhaar number (optional)" in REGISTER_HTML
    assert 'inputmode="numeric"' in REGISTER_HTML and 'x-model="form.aadhaar_number"' in REGISTER_HTML
    assert "NSS.aadhaar.group(form.aadhaar_number)" in REGISTER_HTML
    assert "NSS.aadhaar.validate(this.form.aadhaar_number)" in REGISTER_JS
    assert re.search(r"payloadValue\(this\.form\.aadhaar_number, false\);\s*if \(aadhaarValue !== undefined\) payload\.aadhaar_number", REGISTER_JS)
    assert REGISTER_JS.count("payload.aadhaar_number") == 1
    # never in the sessionStorage draft, cleared after submit
    assert re.search(r"const \{ password, aadhaar_number, \.\.\.formNoPassword \} = this\.form;", REGISTER_JS)
    assert 'this.form.aadhaar_number = "";' in REGISTER_JS


def test_admin_forms_have_the_field_with_shared_validator():
    for model in ("newPersonForm.aadhaar_number", "profileEdit.aadhaar.input", "claimEditForm.aadhaar_number"):
        assert f'x-model="{model}"' in ADMIN_HTML, model
        assert f"NSS.aadhaar.group({model})" in ADMIN_HTML, model
    assert ADMIN_HTML.count("Aadhaar number (optional)") == 3
    assert ADMIN_HTML.count("Clear stored Aadhaar") == 2  # profile edit + claim edit, not create
    assert "x-model=\"profileEdit.aadhaar.clear\"" in ADMIN_HTML and "x-model=\"claimEditForm.aadhaar_clear\"" in ADMIN_HTML
    assert ADMIN_HTML.count("Stored encrypted and used only by authorised administrators.") == 3


def test_admin_request_bodies_use_payload_value_so_blank_is_omitted():
    assert ADMIN_JS.count("payload.aadhaar_number") == 3
    assert "NSS.aadhaar.payloadValue(f.aadhaar_number, false)" in ADMIN_JS                       # create person
    assert "NSS.aadhaar.payloadValue(this.profileEdit.aadhaar.input, this.profileEdit.aadhaar.clear)" in ADMIN_JS
    assert "NSS.aadhaar.payloadValue(f.aadhaar_number, f.aadhaar_clear)" in ADMIN_JS
    assert ADMIN_JS.count("if (npAadhaar !== undefined)") == 1
    # never a literal aadhaar_number key inside an object literal body
    assert not re.search(r"aadhaar_number:\s*(f|this)\.", ADMIN_JS)
    for v in ("NSS.aadhaar.validate(f.aadhaar_number)", "NSS.aadhaar.validate(this.profileEdit.aadhaar.input)",
              "NSS.aadhaar.validate(this.claimEditForm.aadhaar_number)"):
        assert v in ADMIN_JS, v


def test_current_mask_and_full_on_file_indicator_shown():
    assert "aadhaar_last4" in ADMIN_JS and "aadhaar_full_on_file" in ADMIN_JS
    assert "(full number on file)" in ADMIN_HTML
    assert "NSS.aadhaar.mask(profileEdit.aadhaar.last4)" in ADMIN_HTML
    assert "NSS.aadhaar.mask(pdSelected.aadhaar_last4)" in ADMIN_HTML


# -- Source: reveal ----------------------------------------------------------

def test_reveal_buttons_are_gated_by_permission_and_full_on_file():
    buttons = re.findall(r'<button[^>]*x-show="([^"]*)"[^>]*@click="revealAadhaar\(', ADMIN_HTML)
    assert len(buttons) == 2
    for gate in buttons:
        assert "canViewSensitive" in gate and "fullOnFile" in gate or "aadhaar_full_on_file" in gate
    assert re.search(r"get canViewSensitive\(\)\s*\{[^}]*PERSON_VIEW_SENSITIVE", ADMIN_JS)
    # the method re-checks the permission and confirms via NSSDialog (audit notice) first
    m = re.search(r"async revealAadhaar\(.*?\n        \},\n", ADMIN_JS, re.DOTALL)
    assert m
    body = m.group(0)
    assert "if (!this.canViewSensitive" in body
    assert body.index("NSSDialog.confirm") < body.index("/aadhaar`")
    assert "recorded in the audit log" in body
    assert "/api/v1/person/persons/${personPk}/aadhaar" in body
    for code in ("403", "404", "429", ">= 500"):
        assert code in body


def test_revealed_value_is_cleared_on_close_and_never_stored_or_logged():
    close = re.search(r"closeAadhaarReveal\(\) \{(.*?)\n        \},", ADMIN_JS, re.DOTALL).group(1)
    assert 'value: ""' in close and "open: false" in close
    assert '@click="closeAadhaarReveal()"' in ADMIN_HTML and '@click.self="closeAadhaarReveal()"' in ADMIN_HTML
    assert '<template x-if="aadhaarReveal.open">' in ADMIN_HTML          # DOM removed on close
    # no storage / console anywhere near the feature
    feature = "\n".join(re.findall(r"(?s)async revealAadhaar.*?closeAadhaarReveal\(\) \{.*?\n        \},", ADMIN_JS))
    assert feature
    for banned in ("localStorage", "sessionStorage", "console."):
        assert banned not in feature, banned
    assert "aadhaarReveal" not in re.search(r"(?s)const LIVE_TABLE_TABS.*?\n\};", ADMIN_JS).group(0)
    # nothing in the reveal state is fed to live-refresh reload state; busy hooks hold reloads back
    assert "!!h.aadhaarReveal.open" in ADMIN_JS
    assert "|| this.aadhaarReveal.open);" in ADMIN_JS


def test_edit_state_is_reset_on_cancel_and_after_save():
    assert ADMIN_JS.count('this.profileEdit.aadhaar.input = "";') >= 3
    assert 'this.claimEditForm.aadhaar_number = "";' in ADMIN_JS


# -- Source: hygiene ---------------------------------------------------------

def test_no_inline_handlers_added():
    for html in (ADMIN_HTML, REGISTER_HTML):
        assert not re.search(r"\son(click|input|change|submit|keyup)=", html)


def test_dashboard_self_service_profile_has_no_aadhaar_input():
    assert "aadhaar_number" not in DASHBOARD_HTML
    assert "aadhaar_number" not in (JS / "dashboard.js").read_text(encoding="utf-8")
    assert not re.search(r"<input[^>]*aadhaar", DASHBOARD_HTML, re.IGNORECASE)
