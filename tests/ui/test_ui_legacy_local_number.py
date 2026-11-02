"""
Source-level tests for the legacy-vs-new Local Sakha Number UX (GDR-009, owner
2026-11-01): register.html/register.js, admin.html/admin.js (Create User,
Create Sangha Sevi, Registration Approvals).

Needs no browser and no running server -- parses the shipped files directly
(same style as test_ui_admin_dropdown_resets.py). Written but not run against
a browser.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
REG_HTML = (FRONTEND / "register.html").read_text(encoding="utf-8")
REG_JS = (FRONTEND / "assets" / "js" / "register.js").read_text(encoding="utf-8")
ADMIN_HTML = (FRONTEND / "admin.html").read_text(encoding="utf-8")
ADMIN_JS = (FRONTEND / "assets" / "js" / "admin.js").read_text(encoding="utf-8")


# ── register ───────────────────────────────────────────────────────────────

def test_register_asks_the_explicit_legacy_question():
    assert "Were you already a member of NSS before this system?" in REG_HTML
    assert 'name="legacy_choice" value="yes"' in REG_HTML
    assert 'name="legacy_choice" value="no"' in REG_HTML
    # asked in every flow, including Apply for Darshak (no !darshakFlow gate)
    q = REG_HTML.index("Were you already a member of NSS before this system?")
    assert 'x-if="form.organization_pk"' in REG_HTML[q - 1500:q]


def test_register_number_input_only_after_yes_and_note_after_no():
    num = REG_HTML.index('x-model="form.claimed_local_sakha_number"')
    assert "form.legacy_choice === 'yes'" in REG_HTML[num - 1500:num]
    assert "assigned automatically" in REG_HTML
    assert "form.legacy_choice === 'no'" in REG_HTML


def test_register_asks_the_question_again_for_the_attendance_sakha():
    assert 'name="darshak_legacy_choice" value="yes"' in REG_HTML
    num = REG_HTML.index('x-model="form.darshak_local_sakha_number"')
    assert "form.darshak_legacy_choice === 'yes'" in REG_HTML[num - 1500:num]


def test_register_js_requires_the_answer_and_the_number_only_for_yes():
    assert 'legacy_choice: ""' in REG_JS and 'darshak_legacy_choice: ""' in REG_JS
    assert re.search(r'form\.legacy_choice === "yes" && !this\.form\.claimed_local_sakha_number\.trim\(\)', REG_JS)
    assert re.search(r'form\.darshak_legacy_choice === "yes" && !this\.form\.darshak_local_sakha_number\.trim\(\)', REG_JS)
    # the old unconditional requirement is gone
    assert not re.search(r"!this\.darshakFlow && !this\.form\.claimed_local_sakha_number\.trim\(\)", REG_JS)


def test_register_payloads_carry_explicit_flags_via_one_shared_helper():
    m = re.search(r"applyLegacyFields\(payload\) \{(.*?)\n        \},", REG_JS, re.S)
    assert m, "applyLegacyFields helper missing"
    body = m.group(1)
    assert "payload.is_legacy_member = legacy" in body
    assert "payload.darshak_is_legacy_member = dLegacy" in body
    # number only sent for legacy
    assert re.search(r"if \(legacy\) \{\s*payload\.claimed_local_sakha_number", body)
    assert re.search(r"if \(dLegacy\) payload\.darshak_local_sakha_number", body)
    # used by both POST /register and POST /register/claim; no second copy of the number logic
    assert REG_JS.count("this.applyLegacyFields(payload)") == 2
    assert "payload.claimed_local_sakha_number" not in REG_JS.replace(body, "")


def test_register_resets_the_answer_when_membership_type_changes():
    m = re.search(r"onMembershipTypeChange\(\) \{(.*?)\n        \},", REG_JS, re.S)
    assert 'this.form.legacy_choice = ""' in m.group(1)
    assert 'this.form.darshak_legacy_choice = ""' in m.group(1)


def test_no_inline_event_handlers_were_added():
    for name, text in (("register.html", REG_HTML), ("admin.html", ADMIN_HTML)):
        assert not re.search(r"\sonclick=|\sonchange=", text), name


# ── admin Create User / Create Sangha Sevi ───────────────────────────────────

@pytest.mark.parametrize("form", ["createForm", "ssForm"])
def test_admin_create_forms_have_the_legacy_checkbox_and_reveal_the_number(form):
    assert f'x-model="{form}.is_legacy_member"' in ADMIN_HTML
    num = ADMIN_HTML.index(f'x-model="{form}.local_sakha_number"')
    assert f"x-if=\"{form}.is_legacy_member\"" in ADMIN_HTML[num - 900:num]
    assert f"x-if=\"!{form}.is_legacy_member\"" in ADMIN_HTML
    assert "Auto-generated" in ADMIN_HTML


def test_admin_forms_default_to_new_and_reset_to_new():
    assert ADMIN_JS.count('is_legacy_member: false, local_sakha_number: ""') == 4


def test_admin_payloads_use_the_one_shared_helper():
    m = re.search(r"_localNumberPayloadFields\(form\) \{(.*?)\n        \},", ADMIN_JS, re.S)
    assert m
    assert "is_legacy_member: !!form.is_legacy_member" in m.group(1)
    assert "if (form.is_legacy_member)" in m.group(1)
    assert ADMIN_JS.count("...this._localNumberPayloadFields(") == 2
    # the old "send whatever was typed" logic is gone
    assert "payload.local_sakha_erp_id = num" not in ADMIN_JS


# ── Registration Approvals ───────────────────────────────────────────────────

def test_approvals_detail_shows_legacy_flag_and_number_or_to_be_generated():
    assert "selectedClaim?.is_legacy_member ? 'Yes" in ADMIN_HTML
    assert "will be generated on approval" in ADMIN_HTML
    assert "selectedClaim?.darshak_is_legacy_member" in ADMIN_HTML
    assert "To be generated" in ADMIN_HTML  # list column


def test_approvals_edit_form_lets_the_admin_verify_and_correct_both_flags():
    assert 'x-model="claimEditForm.is_legacy_member"' in ADMIN_HTML
    assert 'x-model="claimEditForm.darshak_is_legacy_member"' in ADMIN_HTML
    save = ADMIN_JS[ADMIN_JS.index("async saveClaimEdit()"):]
    save = save[:save.index("async ", 20)] if "async " in save[20:] else save
    assert "payload.is_legacy_member = f.is_legacy_member" in save
    assert "payload.darshak_is_legacy_member = f.darshak_is_legacy_member" in save
    # unchecking clears the number so flag + number travel together
    assert 'f.claimed_local_sakha_number = ""' in save
    assert 'f.claimed_credential_document_number = ""' in save
    assert 'if (!f.darshak_is_legacy_member) f.darshak_local_sakha_number = ""' in save


# ── Parichaya / Anumati Patra number (GDR-009 §2A) ───────────────────────────

def test_register_patra_number_is_inside_the_legacy_yes_branch_only():
    num = REG_HTML.index('x-model="form.claimed_credential_document_number"')
    # revealed by the same legacy answer as the Local Sakha Number, never standalone
    assert "form.legacy_choice === 'yes'" in REG_HTML[num - 3000:num]
    assert REG_HTML.count('x-model="form.claimed_credential_document_number"') == 1
    assert "345/2026/2027" in REG_HTML  # format hint
    assert "issued later" not in REG_HTML and "Kendra, on Dola Purnima" not in REG_HTML


def test_register_js_validates_and_sends_the_patra_number_only_for_legacy():
    assert re.search(r"/\^\(\[1-9\]\[0-9\]\*\)", REG_JS), "client-side <seq>/<yyyy>/<yyyy+1> check missing"
    body = re.search(r"applyLegacyFields\(payload\) \{(.*?)\n        \},", REG_JS, re.S).group(1)
    assert "payload.claimed_credential_document_number" in body
    # the old unconditional 'Parichaya Patra Number is required' gate and the
    # two ad-hoc payload copies are gone
    assert "Parichaya Patra Number is required." not in REG_JS
    assert REG_JS.count("payload.claimed_credential_document_number") == 1


@pytest.mark.parametrize("form", ["createForm", "ssForm"])
def test_admin_patra_number_input_follows_the_legacy_checkbox(form):
    assert f"{form}.credential_is_legacy" not in ADMIN_HTML  # separate checkbox removed
    num = ADMIN_HTML.index(f'x-model="{form}.credential_document_number"')
    assert f"x-if=\"{form}.is_legacy_member\"" in ADMIN_HTML[num - 700:num]
    assert "345/2026/2027" in ADMIN_HTML[num:num + 600]
    assert "credential_is_legacy" not in ADMIN_JS


def test_admin_credential_payload_is_sent_only_for_legacy_members():
    m = re.search(r"_credentialPayloadFields\(form\) \{(.*?)\n        \},", ADMIN_JS, re.S)
    assert m and "if (form.is_legacy_member)" in m.group(1)


def test_admin_success_message_reports_the_issued_credential_always():
    assert "_credentialIssuedNote" not in ADMIN_JS
    assert ADMIN_JS.count("issued: ${data.credential_document_number}") == 2
    assert "the Kendra issues it" not in ADMIN_JS and "the Kendra issues it" not in ADMIN_HTML


def test_approvals_detail_and_edit_show_the_patra_number_rule():
    assert "will be issued by the Kendra" not in ADMIN_HTML
    assert "Issued later by the Kendra" not in ADMIN_HTML
    edit = ADMIN_HTML.index('x-model="claimEditForm.claimed_credential_document_number"')
    assert "claimEditForm.is_legacy_member" in ADMIN_HTML[edit - 700:edit]


# ── A Darshaka cannot attend another Sakha (GDR-009 §2B) ─────────────────────

def test_register_hides_the_attendance_section_for_a_darshaka():
    assert 'x-show="!darshakFlow && !isDarshaka()"' in REG_HTML
    assert "must transfer to it" in REG_HTML


def test_dashboard_hides_apply_for_darshak_for_probationary_members():
    dash_html = (FRONTEND / "dashboard.html").read_text(encoding="utf-8")
    dash_js = (FRONTEND / "assets" / "js" / "dashboard.js").read_text(encoding="utf-8")
    btn = dash_html.index('@click="applyDarshak()"')
    assert "membership_type_code !== 'PROBATIONARY'" in dash_html[btn - 120:btn]
    body = dash_js[dash_js.index("applyDarshak() {"):][:500]
    assert 'membership_type_code === "PROBATIONARY"' in body
