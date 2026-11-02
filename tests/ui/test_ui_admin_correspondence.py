"""
Source-level tests for the admin Correspondence Register UI.

Closes the gap CLAUDE.md's "Open items" called out: api/routers/correspondence.py
has a full admin frontend (nav item, list, create form, detail, status
transition, documents, finance references) but had no tests/ui/ coverage at
all, so nothing stopped a rename in admin.js from silently orphaning an
Alpine binding in admin.html.

Two things this file is specifically here to protect:

  1. The inter-org (NSS-to-NSS) capability. §4.7 of the correspondence
     business rules is ERP-FROZEN and permits internal correspondence
     ("Kendra circular to all Sakhas"), and the DB/API support it via
     sender_type/recipient_type = 'ORGANIZATION'. That capability is only
     actually reachable because the create form offers ORGANIZATION in BOTH
     party dropdowns and wires an org typeahead to each. Dropping either
     option would silently remove a frozen-spec feature with no API change
     and no other test noticing.

  2. No dangling bindings. Every Alpine handler the correspondence markup
     calls must exist in admin.js.

Needs no browser and no running server — it parses the shipped files
directly, same style as test_ui_badges.py / test_ui_governance_card.py.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"

ADMIN_HTML = FRONTEND / "admin.html"
ADMIN_JS = FRONTEND / "assets" / "js" / "admin.js"
NSS_CONFIG_JS = FRONTEND / "assets" / "js" / "nss-config.js"


@pytest.fixture(scope="module")
def admin_html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def admin_js() -> str:
    return ADMIN_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nss_config_js() -> str:
    return NSS_CONFIG_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def correspondence_panel(admin_html: str) -> str:
    """
    Just the correspondence tab's content panel.

    Sliced from its own `x-show="activeTab === 'correspondence'"` opening div
    up to the next sibling tab panel, so assertions below cannot accidentally
    be satisfied by markup belonging to some other tab.
    """
    start = admin_html.index("""<div x-show="activeTab === 'correspondence'" x-cloak>""")
    nxt = admin_html.find("""<div x-show="activeTab === '""", start + 1)
    return admin_html[start:nxt] if nxt != -1 else admin_html[start:]


# ── Nav entry ───────────────────────────────────────────────────────────

def test_nav_item_exists_and_is_permission_gated(admin_html: str):
    assert "canViewCorrespondence" in admin_html, (
        "The Correspondence nav item must be gated on canViewCorrespondence."
    )
    assert """:class="{ active: activeTab === 'correspondence' }\"""" in admin_html
    assert "activeTab = 'correspondence'; loadCorrespondence()" in admin_html, (
        "Clicking the nav item must both switch the tab and trigger the loader."
    )


def test_permission_getters_exist(admin_js: str):
    for getter in ("canViewCorrespondence", "canManageCorrespondence"):
        assert re.search(rf"get\s+{getter}\s*\(", admin_js), (
            f"admin.js must define a `get {getter}()` — admin.html binds to it."
        )


def test_content_panel_exists(correspondence_panel: str):
    assert correspondence_panel.startswith(
        """<div x-show="activeTab === 'correspondence'" x-cloak>"""
    )
    assert "Correspondence Register" in correspondence_panel


# ── Inter-org capability (the frozen §4.7 feature) ──────────────────────

def test_both_party_dropdowns_offer_organization(correspondence_panel: str):
    """
    §4.7 (ERP-FROZEN) permits NSS-to-NSS correspondence. The DB CHECK and the
    API both accept sender_type/recipient_type = 'ORGANIZATION'; this is the
    only place a user can actually choose it.
    """
    for field in ("sender_type", "recipient_type"):
        select_match = re.search(
            rf"""x-model="corrCreateForm\.{field}"(.*?)</select>""",
            correspondence_panel,
            re.DOTALL,
        )
        assert select_match, f"No <select> bound to corrCreateForm.{field}."
        options = select_match.group(1)
        assert '<option value="ORGANIZATION">' in options, (
            f"corrCreateForm.{field} must offer ORGANIZATION — without it the "
            "frozen §4.7 inter-org capability is unreachable from the UI."
        )


def test_each_party_has_its_own_org_typeahead(correspondence_panel: str):
    """
    Choosing ORGANIZATION is useless without a picker to resolve the actual
    organization_pk, and sender/recipient must use SEPARATE state objects —
    sharing one would make an org-to-org letter impossible to address.

    The two parties use DIFFERENT query handlers by design (owner 2026-10-26):
    the sender searches every organization, while the recipient is restricted
    to the register org's own children (corrOnRecipientOrgQueryInput).
    """
    handlers = {
        "senderOrg": "corrOnOrgQueryInput",
        "recipientOrg": "corrOnRecipientOrgQueryInput",
    }
    for state, handler in handlers.items():
        assert f"corrCreateForm.{state}.query" in correspondence_panel
        assert f"{handler}(corrCreateForm.{state})" in correspondence_panel
        assert f"corrSelectOrg(corrCreateForm.{state}, org)" in correspondence_panel
    # The recipient must NOT fall back to the unrestricted search.
    assert "corrOnOrgQueryInput(corrCreateForm.recipientOrg)" not in correspondence_panel


def test_org_party_blocks_are_conditional_on_the_selected_type(correspondence_panel: str):
    """The org picker must only render when that party's type IS ORGANIZATION
    (the DB CHECK rejects a populated org FK on a PERSON/EXTERNAL party)."""
    for field in ("sender_type", "recipient_type"):
        assert (
            f"""<template x-if="corrCreateForm.{field} === 'ORGANIZATION'">"""
            in correspondence_panel
        )


# ── Create / write gating ───────────────────────────────────────────────

def test_create_buttons_require_manage_permission(correspondence_panel: str):
    for direction in ("OUTWARD", "INWARD"):
        button = re.search(
            rf"""<button[^>]*@click="toggleCorrCreateForm\('{direction}'\)">""",
            correspondence_panel, re.DOTALL,
        )
        assert button, f"No button wired to toggleCorrCreateForm('{direction}')."
        assert 'x-show="canManageCorrespondence"' in button.group(0), (
            f"The {direction} create button must be gated on "
            "canManageCorrespondence — CORRESPONDENCE_VIEW alone is read-only."
        )


def test_opening_the_create_form_hides_the_list_and_its_filters(correspondence_panel: str):
    """
    Owner request (2026-10-25): "why are showing filters when we are
    selecting send/receive in first place?? isn't it confusing?" — the
    status pills, the organization/direction filter row and the register
    table all belong to the LIST, so the whole list card (and the pills
    above it) must hide while the create form is open, and vice versa.
    """
    assert '<div class="tab-pills" x-show="!corrCreateForm.show">' in correspondence_panel, (
        "The status-filter pills must hide while the create form is open."
    )
    assert '<div class="data-card" x-show="!corrCreateForm.show">' in correspondence_panel, (
        "The register list card (filters + table) must hide while the create form is open."
    )
    assert '<div class="data-card" x-show="corrCreateForm.show"' in correspondence_panel, (
        "The create form must be its OWN card, shown in place of the list — "
        "not nested inside the list card it replaces."
    )
    # The direction filter belongs to the list, so it must sit inside the
    # list card rather than anywhere near the create form.
    list_card_start = correspondence_panel.index('<div class="data-card" x-show="!corrCreateForm.show">')
    form_card_start = correspondence_panel.index('<div class="data-card" x-show="corrCreateForm.show"')
    assert form_card_start < list_card_start, "Create-form card should precede the list card."
    assert 'x-model="corrDirectionFilter"' in correspondence_panel[list_card_start:], (
        "The Inward/Outward DIRECTION FILTER must live inside the list card."
    )
    assert 'x-model="corrDirectionFilter"' not in correspondence_panel[form_card_start:list_card_start], (
        "The direction filter must not appear inside the create-form card."
    )


# ── Simplified create form (owner request, 2026-10-25: "make the ui
#    simpler for send/receive application/letter") ──────────────────────

def test_direction_is_no_longer_a_form_field(correspondence_panel: str):
    """Direction is fixed by which quick-action button opened the form
    (toggleCorrCreateForm('OUTWARD'|'INWARD')) — showing it again as an
    editable <select> would let an admin silently contradict the button
    they just clicked."""
    assert 'x-model="corrCreateForm.direction"' not in correspondence_panel


def test_date_collapses_to_one_field_by_default(correspondence_panel: str):
    assert "nssDatePicker('corrCreateForm.date')" in correspondence_panel
    # The two original independent fields must still exist (capability
    # preserved) but only inside the splitDates-gated block.
    split_block = re.search(
        r"""x-show="corrCreateForm\.splitDates"(.*?)</div>\s*<div x-data="nssDatePicker\('corrCreateForm\.follow_up_date""",
        correspondence_panel, re.DOTALL,
    )
    assert split_block, "No splitDates-gated block containing the two original date fields."
    assert "nssDatePicker('corrCreateForm.correspondence_date')" in split_block.group(1)
    assert "nssDatePicker('corrCreateForm.received_or_sent_date')" in split_block.group(1)


def test_other_party_is_the_only_party_shown_by_default(correspondence_panel: str):
    """
    For an OUTWARD letter, Recipient (the other party) must be visible
    outside any advanced disclosure; Sender (defaulted to "us") must not
    appear there. For INWARD, the reverse. Anchored on the party SECTION
    wrappers (.form-section inside the direction template) so the
    .corr-flow strip's own direction branches don't match.
    """
    outward_block = re.search(
        r"""<template x-if="corrCreateForm\.direction === 'OUTWARD' && !corrCreateForm\.isBroadcast">\s*<div class="form-section">(.*?)</template>""",
        correspondence_panel, re.DOTALL,
    )
    assert outward_block, "No OUTWARD-gated party section (.form-section) found."
    assert 'x-model="corrCreateForm.recipient_type"' in outward_block.group(1)
    assert 'x-model="corrCreateForm.sender_type"' not in outward_block.group(1)

    inward_block = re.search(
        r"""<template x-if="corrCreateForm\.direction === 'INWARD'">\s*<div class="form-section">(.*?)</template>""",
        correspondence_panel, re.DOTALL,
    )
    assert inward_block, "No INWARD-gated party section (.form-section) found."
    assert 'x-model="corrCreateForm.sender_type"' in inward_block.group(1)
    assert 'x-model="corrCreateForm.recipient_type"' not in inward_block.group(1)


def test_direction_is_stated_via_the_flow_strip(correspondence_panel: str):
    """Direction stopped being an editable field, so the form must still
    make it unambiguous — the From → To strip does that, with "our" org
    pinned to the correct side per direction."""
    assert 'class="corr-flow"' in correspondence_panel
    assert "corrSenderSummary" in correspondence_panel
    assert "corrRecipientSummary" in correspondence_panel


def test_more_options_disclosure_holds_the_rest(correspondence_panel: str):
    """Follow-up date, the "our side" override, and Responsible Party must
    all be inside the moreOptions-gated block — not shown by default."""
    more_options_block = re.search(
        r"""x-show="corrCreateForm\.moreOptions"(.*?)<div class="form-section" style="display:flex;""",
        correspondence_panel, re.DOTALL,
    )
    assert more_options_block, "No moreOptions-gated block found before the submit row."
    body = more_options_block.group(1)
    assert "corrCreateForm.usPartyOverride" in body
    assert "nssDatePicker('corrCreateForm.follow_up_date')" in body
    assert "Responsible Party" in body
    assert 'x-model="corrCreateForm.responsiblePerson.query"' in body
    assert 'x-model="corrCreateForm.responsibleOrg.query"' in body


def test_register_org_has_three_resolution_tiers(correspondence_panel: str):
    """
    Owner follow-up, 2026-10-25: "if a person is admin for both sakha and
    kendra how will he send/receive for both? no option for that", then
    "can we have a browser like tab inside send/receive application, each
    tab for each org type... and in form the org name should show", then
    2026-10-26: "when tab is anchalika, we should have a dropdown to selcet
    the anchalika, not a tab for each anchalika, and it should be
    Anchalika/Zilla".

    So tier 2 is one .tab-pill per org TIER (not per org), plus a dropdown
    inside the active tier to choose which org of that tier, plus a strip
    showing the chosen org's real NAME. All three tiers must stay mutually
    exclusive-by-default so an admin never sees neither a picker nor a value.
    """
    assert "corrCreateForm.orgAutoResolved" in correspondence_panel
    assert "corrCreateForm.orgMultipleChoices" in correspondence_panel
    assert "corrCreateForm.orgPickerExpanded = true" in correspondence_panel

    # Tier 2 — the tab-per-TIER switcher plus its per-tier dropdown.
    switcher = re.search(
        r"""x-show="corrCreateForm\.orgMultipleChoices && !corrCreateForm\.orgPickerExpanded">(.*?)<div class="typeahead-wrap""",
        correspondence_panel, re.DOTALL,
    )
    assert switcher, "No orgMultipleChoices-gated 'Filing For' switcher found."
    body = switcher.group(1)
    assert 'class="tab-pills"' in body, "The multi-org switcher must reuse the existing .tab-pills chrome."
    tab_button = re.search(r"""<button type="button" class="tab-pill"(.*?)</button>""", body, re.DOTALL)
    assert tab_button, "No .tab-pill <button> found inside the switcher."
    # Tabs iterate TIER GROUPS and are labelled by the group, never by an org.
    assert "corrCreateForm.orgTabGroups" in body, (
        "The tabs must iterate orgTabGroups (org TIERS) — owner 2026-10-26: "
        "'not a tab for each anchalika'."
    )
    assert "corrSelectRegisterTab(g.key)" in tab_button.group(1)
    assert "corrCreateForm.activeOrgTab === g.key" in tab_button.group(1), (
        "A tab's active state must track the active TIER, not a selected org."
    )
    assert 'x-text="g.label"' in tab_button.group(1)

    # The per-tier dropdown — shown only when that tier holds several orgs.
    dropdown = re.search(
        r"""x-show="corrActiveTabOrgs\.length > 1"(.*?)</select>""", body, re.DOTALL,
    )
    assert dropdown, (
        "No 'corrActiveTabOrgs.length > 1' dropdown found — a tier holding "
        "several orgs (e.g. Anchalika/Zilla, Sakha) must offer a dropdown."
    )
    assert 'x-model="corrCreateForm.activeOrgPk"' in dropdown.group(1)
    assert "corrSelectOrgChoice(corrCreateForm.activeOrgPk)" in dropdown.group(1)
    assert "org.organization_name" in dropdown.group(1), (
        "Dropdown options must be labelled by org NAME (that is the whole "
        "point of picking WHICH anchalika)."
    )

    # The chosen org's actual NAME — not just its tier (the tab label) —
    # must be visible once a tab/dropdown choice is active.
    assert 'class="field-resolved" x-show="corrCreateForm.org.selected"' in body
    assert "corrCreateForm.org.selected?.organization_name" in body

    # Tier 3 — manual search is the fallback when NEITHER tier 1 nor tier
    # 2 resolved (or when explicitly expanded from either).
    assert (
        """x-show="(!corrCreateForm.orgAutoResolved && !corrCreateForm.orgMultipleChoices) || corrCreateForm.orgPickerExpanded\""""
        in correspondence_panel
    ), "The manual picker's visibility must be the fallback for BOTH the auto-resolved and the multi-choice tiers."


def test_register_tab_groups_merge_anchalika_and_zilla(admin_js: str):
    """Owner 2026-10-26: the tier tab "should be Anchalika/Zilla" — one tab
    covering both types, since they are the same tier of the frozen
    Kendra -> Anchalika/Zilla -> Sakha hierarchy. The two apex singletons
    keep no register and must not appear as tabs at all."""
    groups = re.search(
        r"const CORR_REGISTER_TAB_GROUPS = \[(.*?)\];", admin_js, re.DOTALL,
    )
    assert groups, "CORR_REGISTER_TAB_GROUPS not found."
    body = groups.group(1)
    merged = re.search(
        r"""\{\s*key:\s*"ANCHALIKA_ZILLA",\s*label:\s*"Anchalika/Zilla",\s*typeCodes:\s*\[([^\]]*)\]""",
        body,
    )
    assert merged, 'No single {key:"ANCHALIKA_ZILLA", label:"Anchalika/Zilla"} group found.'
    assert "ANCHALIKA_SANGHA" in merged.group(1) and "ZILLA_SANGHA" in merged.group(1), (
        "The Anchalika/Zilla tab must cover BOTH org types."
    )
    assert "NILACHALA_KUTIRA" not in body and "SMRUTI_MANDIRA" not in body, (
        "The apex singletons keep no correspondence register — no tab for them."
    )


def test_circular_toggle_renders_after_the_register_org_picker(correspondence_panel: str):
    """Owner 2026-10-26: "I want send circular under kendra and anchalika/
    zilla tab not above it.." — the circular checkbox must render AFTER the
    Register Organization section's closing </div>, not before it, so the
    control reads as belonging to the chosen register rather than floating
    above the choice of which register it even applies to."""
    register_org_end = correspondence_panel.index(
        '@click="corrCreateForm.orgPickerExpanded = true">Change</button>'
    )
    circular_checkbox = correspondence_panel.index(
        'x-model="corrCreateForm.isBroadcast"'
    )
    assert circular_checkbox > register_org_end, (
        "The circular checkbox must appear in the markup AFTER the Register "
        "Organization picker, not before it."
    )
    # And still before the Essentials (Date/Medium/Subject) section — it's
    # scoped to the register choice, not pushed all the way to the bottom.
    essentials_start = correspondence_panel.index('<!-- Essentials -->')
    assert circular_checkbox < essentials_start


def test_recipient_candidates_allow_sakha_patha_chakra_anchalika_zilla_to_address_kendra(admin_js: str):
    """Owner 2026-10-26: "Sakha, pathachakra, anachalik/zilla can send
    letter to kendra" — the one upward exception to the descendants-only
    recipient rule. A Kendra register itself gets no such exception (it has
    nothing further upward)."""
    getter = re.search(r"get corrRecipientOrgCandidates\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert getter, "corrRecipientOrgCandidates getter not found."
    body = getter.group(0)
    assert 'NSS.isSakhaLike(t) || ["PATHA_CHAKRA", "ANCHALIKA_SANGHA", "ZILLA_SANGHA", "ADVISORY_BOARD"].includes(t)' in body, (
        "Must special-case exactly these register types (Sakha-like types via "
        "NSS.isSakhaLike, plus the three tiers and the Advisory Board "
        "organization, 2026-10-30) for the upward "
        "Kendra exception."
    )
    assert "this.kendraOrg" in body, "Must add the real Kendra org (this.kendraOrg), not a synthetic stand-in."
    # Still delegates to the shared descendant walk for the base candidates —
    # this is an ADDITION to that list, not a replacement of it.
    assert "this._corrDescendantOrgs(o.organization_pk)" in body


def test_reply_button_opens_a_prefilled_create_form(correspondence_panel: str, admin_js: str):
    """Owner 2026-10-26: "we should also add reply option to letter too.
    which will have its own numbers (conceptually same process)" — Reply
    opens the ORDINARY create form (own reference_number via the normal
    counter), pre-filled and linked via in_reply_to_correspondence_pk, not a
    separate reply-specific endpoint/payload."""
    assert 'replyToCorrespondence(corrSelected)' in correspondence_panel, (
        "No Reply action wired to the detail view's corrSelected record."
    )
    assert 'x-show="corrSelected?.in_reply_to_correspondence_pk"' in correspondence_panel, (
        "The detail view must show the forward 'In Reply To' link when present."
    )

    fn = re.search(r"replyToCorrespondence\(original\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "replyToCorrespondence() not found."
    body = fn.group(0)
    assert "this.corrResetCreateForm()" in body, "Must start from a clean form, not a stale one."
    assert 'f.show = true' in body
    assert (
        'f.direction = original.direction === "OUTWARD" ? "INWARD" : "OUTWARD"' in body
    ), "The reply's direction must be the OPPOSITE of the original's."
    assert "f.inReplyToPk = original.correspondence_pk" in body, (
        "Must carry the link forward so it reaches the create payload."
    )
    assert "f.subject" in body and "Re: " in body, "Subject must be pre-filled with a 'Re: ' prefix."
    # The party carried over from the original flips which FORM FIELD it
    # occupies (sender vs recipient), matching the direction flip.
    assert 'this.corrPrefillParty("recipient", original, "sender")' in body
    assert 'this.corrPrefillParty("sender", original, "recipient")' in body


def test_reply_clears_corr_selected_so_the_form_is_actually_visible(
    correspondence_panel: str, admin_js: str,
):
    """Regression (owner report, 2026-10-26: "REPLY TO CORRESPONDENCE LETTER
    NOT WORKING. nothing happening"). The create form's whole wrapper (list
    + form, shared markup) is gated on x-show="!corrSelected && ...", while
    Reply is launched FROM the detail view, where corrSelected is still set.
    Setting corrCreateForm.show=true alone therefore opens the form INVISIBLY
    behind the still-showing detail panel — replyToCorrespondence() must also
    null out corrSelected, same as backToCorrList() does."""
    wrapper = re.search(
        r'<div x-show="(![^"]*corrSelected[^"]*)">', correspondence_panel,
    )
    assert wrapper, "Expected a list/create-form wrapper gated on !corrSelected."
    assert "corrCreateForm.show" not in wrapper.group(1), (
        "Sanity check: the wrapper gating the create form must NOT also "
        "require corrCreateForm.show to be false — it should be the plain "
        "!corrSelected wrapper the form lives inside."
    )

    fn = re.search(r"replyToCorrespondence\(original\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "replyToCorrespondence() not found."
    assert "this.corrSelected = null" in fn.group(0), (
        "replyToCorrespondence() must clear corrSelected — otherwise the "
        "newly-opened create form stays hidden behind the detail view."
    )


def test_reply_payload_field_is_submitted_with_create(admin_js: str):
    """The create payload must actually carry inReplyToPk through as
    in_reply_to_correspondence_pk — pre-filling the form is useless if the
    submit doesn't send the link."""
    fn = re.search(r"async createCorrespondence\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "createCorrespondence() not found."
    assert "in_reply_to_correspondence_pk: f.inReplyToPk || null," in fn.group(0)


def test_resolve_default_org_populates_the_switcher_for_a_small_scope(admin_js: str):
    """
    Owner follow-up (2026-10-26): a first version of this method called
    GET /admin/organizations and keyed off its total-org count — but that
    endpoint collapses to "every org in the system" the instant ANY of
    the admin's grants is NSS-WIDE scope_level, which a Kendra-President
    composite grant (§63) always is. That silently defeated the whole
    feature for exactly the dual-role case it was built for ("kendra
    president, who is also sakhas president"). Must instead read the
    admin's own RAW currentUser.scopes array and resolve each grant
    individually — a NULL organization_pk (NSS-WIDE) resolves to the
    real Kendra org, same as myOrgDashboardPk already does.
    """
    fn = re.search(
        r"corrResolveDefaultOrg\(\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert fn, "corrResolveDefaultOrg() not found."
    body = fn.group(0)
    assert "async " not in admin_js[max(0, fn.start() - 10):fn.start()], (
        "corrResolveDefaultOrg() must be synchronous — it reads already-loaded "
        "client state (currentUser.scopes/this.organizations), no network call."
    )
    assert "/api/v1/admin/organizations" not in body, (
        "Must not key off the backend's admin-scope org-count endpoint — that "
        "collapses to unrestricted for any NSS-WIDE grant, which defeats the "
        "dual Kendra+Sakha admin case this method exists for."
    )
    assert "this.currentUser?.scopes" in body
    assert "s.organization_pk || kendraPk" in body, (
        "Each scope grant must resolve its OWN organization_pk individually "
        "(NSS-WIDE grants carry a NULL org_pk -> resolve to the real Kendra org) "
        "— not be short-circuited by an overall is_nss_wide()-style check."
    )
    # Candidates are grouped into TIER tabs (owner 2026-10-26), so the
    # switcher is driven by orgTabGroups rather than a flat org list.
    assert "CORR_REGISTER_TAB_GROUPS" in body, (
        "Candidates must be grouped into tier tabs, not listed one tab per org."
    )
    assert "f.orgTabGroups = groups" in body
    assert "f.orgMultipleChoices = true" in body
    assert "this.corrSelectRegisterTab(groups[0].key);" in body.split("f.orgMultipleChoices = true")[1], (
        "A tier tab must be pre-selected on open — otherwise the form shows a "
        "row of tabs with none of them active and no register org chosen at all."
    )


def test_resolve_default_org_scope_derivation_stays_agnostic(admin_js: str):
    """
    Owner follow-ups (2026-10-26): first "we also should have tab option for
    anchalika/zilla and patha chakra too", then "we should have anchalika/
    zilla and pathhchakra tab also for send and receive".

    Two halves, deliberately:
      1. The SCOPE-DERIVED tabs stay org-type/role agnostic — a dual-role
         admin's own scopes drive their tabs whatever org type(s) those are
         (Sakha+Kendra, Anchalika+Zilla, Patha Chakra+Sakha, …), with no
         role_code / org-type branching. A hardcoded list here is exactly
         what silently stops covering a type nobody thought to add.
      2. On top of that, an NSS-wide / Kendra-equivalent admin — who has no
         per-org scope for the apex registers — additionally gets the parent
         register orgs seeded as tabs. This is the ONE place org-type names
         are allowed, and it is gated on isGovNssWideAdmin so a scope-bounded
         admin never enters it.
    """
    fn = re.search(
        r"corrResolveDefaultOrg\(\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert fn, "corrResolveDefaultOrg() not found."
    body = fn.group(0)
    guard = "if (this.isGovNssWideAdmin)"
    assert guard in body, "NSS-wide apex-tab seeding branch (owner 2026-10-26) not found."
    scope_part, apex_part = body.split(guard, 1)

    # Half 1: scope derivation must not branch on role or org type.
    for needle in (
        "SAKHA", "KENDRA_GOVERNING_BODY", "ANCHALIKA", "ZILLA", "PATHA_CHAKRA",
        "role_code", "organization_type",
    ):
        assert needle not in scope_part, (
            f"The scope-derivation half of corrResolveDefaultOrg() references "
            f"{needle!r} — it must resolve whatever currentUser.scopes contains "
            "regardless of which org type(s) that happens to be."
        )
    assert "for (const s of scopes)" in scope_part, (
        "The scope-derivation loop must still iterate currentUser.scopes."
    )
    # Half 2: the apex branch is deliberately org-type-aware (the owner's ask),
    # but sources its type list from CORR_REGISTER_TAB_GROUPS rather than its
    # own parallel copy — so adding a tier tab can't silently leave an
    # NSS-wide admin unable to file for that tier.
    assert "CORR_REGISTER_TAB_GROUPS.flatMap(g => g.typeCodes)" in apex_part, (
        "The NSS-wide branch must offer exactly the types the tier tabs cover, "
        "derived from CORR_REGISTER_TAB_GROUPS, not a duplicated literal list."
    )


# ── Status filters and transitions ──────────────────────────────────────

CORRESPONDENCE_STATUSES = ("REGISTERED", "PENDING_ACTION", "ACTIONED", "CLOSED")


def test_status_filter_covers_every_status(correspondence_panel: str):
    for code in CORRESPONDENCE_STATUSES:
        assert f"corrStatusFilter = '{code}'" in correspondence_panel, (
            f"Missing a filter button for CORRESPONDENCE_STATUS {code}."
        )


def test_transition_status_box_was_removed(correspondence_panel: str, admin_js: str):
    """Owner 2026-10-26: "remove the trnasition status box entirely" — the
    event-driven lifecycle amendment (same date) made REGISTERED->
    PENDING_ACTION/->ACTIONED automatic, so the manual "Transition Status"
    dropdown box was retired from the detail view. POST /{pk}/transition
    itself is UNCHANGED (still a live, valid endpoint — ACTIONED->CLOSED and
    both reopen transitions, §6.3, remain reachable only via direct API call
    until/unless a lighter replacement control is added); this is a UI-only
    removal, not a backend one."""
    assert "Transition Status" not in correspondence_panel
    for removed in ("corrTransitionForm", "submitCorrTransition", "corrNextStatuses", "corrIsReopenTransition"):
        assert removed not in correspondence_panel, f"{removed} still referenced in the correspondence markup."
        assert removed not in admin_js, f"{removed} is dead code — remove it from admin.js too."


def test_reopen_remarks_field_is_conditional(correspondence_panel: str):
    """
    §6.3: reopening (ACTIONED/CLOSED -> PENDING_ACTION) REQUIRES remarks, and
    the API 422s without them. No UI control for it exists any more (see
    test_transition_status_box_was_removed) — reopening is API-only for now,
    so there is nothing left to assert about a remarks field in the markup.
    """
    assert "required to reopen" not in correspondence_panel


# ── Theming comes from nss-config.js, not hand-written literals ─────────

def test_badges_use_the_shared_helpers(correspondence_panel: str, nss_config_js: str):
    for helper in (
        "correspondenceDirectionBadgeClass",
        "correspondenceStatusBadgeClass",
    ):
        assert f"NSS.{helper}(" in correspondence_panel, (
            f"Correspondence badges must be themed via NSS.{helper}()."
        )
        assert re.search(rf"\b{helper}\s*\(", nss_config_js), (
            f"nss-config.js must define {helper}()."
        )


# ── Circular / broadcast (owner request, 2026-10-26: "sometimes, kendra/
#    anchalika/zilla send letter to all sakhas under it") ───────────────

def test_circular_toggle_only_offered_outward(correspondence_panel: str):
    # Owner 2026-10-26 follow-up: the circular "should be inside kendra
    # sangha, anchalaika/zilla tab only" — so the checkbox is gated on
    # direction === 'OUTWARD' AND corrCanBroadcast (the selected register org
    # being a Kendra/Anchalika/Zilla), never on a Sakha or Patha Chakra
    # register, and never on an inward letter.
    checkbox = re.search(
        r"""<label class="remember-label"[^>]*x-show="corrCreateForm\.direction === 'OUTWARD' && corrCanBroadcast">\s*<input type="checkbox" x-model="corrCreateForm\.isBroadcast">""",
        correspondence_panel,
    )
    assert checkbox, (
        "The circular checkbox (x-model=corrCreateForm.isBroadcast) must be "
        "gated to direction === 'OUTWARD' && corrCanBroadcast — a circular "
        "only makes sense for a letter WE are sending, and only from a "
        "Kendra/Anchalika/Zilla register (a parent of other org types)."
    )


def test_circular_mode_replaces_recipient_with_a_type_picker(correspondence_panel: str):
    """When isBroadcast is on: the single Recipient section must be hidden,
    and a 'Send To Every' organization-type select shown instead — driven by
    corrBroadcastTypeOptions (the descendant types actually present under the
    selected register org), not the full orgTypes catalog and not a new
    fetch."""
    assert (
        """<template x-if="corrCreateForm.direction === 'OUTWARD' && !corrCreateForm.isBroadcast">"""
        in correspondence_panel
    ), "The single-recipient Recipient section must hide when isBroadcast is on."
    type_picker = re.search(
        r"""x-show="corrCreateForm\.direction === 'OUTWARD' && corrCanBroadcast && corrCreateForm\.isBroadcast">(.*?)</div>""",
        correspondence_panel, re.DOTALL,
    )
    assert type_picker, "No 'Send To Every' organization-type picker found."
    assert 'x-model="corrCreateForm.broadcastRecipientTypeCode"' in type_picker.group(1)
    assert "corrBroadcastTypeOptions" in type_picker.group(1), (
        "The 'Send To Every' select must iterate corrBroadcastTypeOptions "
        "(descendant types under the selected org), not the full orgTypes "
        "catalog — owner 2026-10-26: 'we cannot add all types in dropdown'."
    )


def test_circular_mode_hides_the_sender_override(correspondence_panel: str):
    """A circular is ALWAYS sent BY the organization (CorrespondenceBroadcastCreate
    has no sender_type/sender_person_* fields at all) — the "our side"
    override checkbox must not be offered in this mode."""
    override_checkbox = re.search(
        r"""<label class="remember-label"[^>]*x-show="([^"]*)">\s*<input type="checkbox" x-model="corrCreateForm\.usPartyOverride">""",
        correspondence_panel,
    )
    assert override_checkbox, "No usPartyOverride checkbox found."
    assert "!corrCreateForm.isBroadcast" in override_checkbox.group(1), (
        "The sender-override checkbox must be hidden while isBroadcast is on."
    )


def test_circular_gating_corrcanbroadcast_only_parent_types(admin_js: str):
    """corrCanBroadcast (owner 2026-10-26: circular "inside kendra sangha,
    anchalaika/zilla tab only") must allow exactly KENDRA / ANCHALIKA_SANGHA /
    ZILLA_SANGHA and nothing else — never SAKHA_SANGHA or PATHA_CHAKRA."""
    getter = re.search(r"get corrCanBroadcast\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert getter, "corrCanBroadcast getter not found."
    body = getter.group(0)
    assert '["KENDRA", "ANCHALIKA_SANGHA", "ZILLA_SANGHA"].includes(' in body, (
        "corrCanBroadcast must gate on exactly KENDRA/ANCHALIKA_SANGHA/ZILLA_SANGHA."
    )
    # Reads either source shape so a search-selected org (type_code) gates too.
    assert "organization_type_code || o.type_code" in body


def test_broadcast_type_options_walk_subtree_and_exclude_apex(admin_js: str):
    """corrBroadcastTypeOptions (owner 2026-10-26: "we cannot add all types in
    dropdown. check the repo for parent and child relationship. (always
    exclude kutira and smurti mandira)") must derive the dropdown from the
    live parent/child subtree of the selected org — the same links the
    backend's org_subtree_pks() recursion uses, via the shared
    _corrDescendantOrgs() walk (which owns the apex exclusion) — and return a
    filtered slice of the orgTypes catalog rather than a new fetch."""
    getter = re.search(r"get corrBroadcastTypeOptions\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert getter, "corrBroadcastTypeOptions getter not found."
    body = getter.group(0)
    assert "this._corrDescendantOrgs(o.organization_pk)" in body, (
        "Must derive its types from the selected org's descendants, via the "
        "shared walk (which excludes Kutira/Smruti Mandira)."
    )
    assert "this.orgTypes.filter(" in body, (
        "Must return a filtered subset of the already-loaded orgTypes catalog "
        "(no new fetch, preserves option shape/order)."
    )


def test_register_switcher_offers_parent_org_tabs_for_nss_wide_admin(admin_js: str):
    """corrResolveDefaultOrg (owner 2026-10-26: "we should have anchalika/
    zilla and pathhchakra tab also for send and receive") must, for an
    NSS-wide / Kendra-equivalent admin, seed the apex/parent register orgs as
    tab choices in addition to the scope-derived ones — gated on
    isGovNssWideAdmin so a scope-bounded admin is unaffected."""
    fn = re.search(r"corrResolveDefaultOrg\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "corrResolveDefaultOrg() not found."
    body = fn.group(0)
    assert "this.isGovNssWideAdmin" in body, (
        "Apex-tab seeding must be gated on isGovNssWideAdmin so scoped admins "
        "keep seeing only their own register."
    )
    assert "CORR_REGISTER_TAB_GROUPS" in body, (
        "An NSS-wide admin must get a register tab for every tier the tab "
        "groups cover (Kendra / Anchalika-Zilla / Patha Chakra / Sakha), "
        "sourced from CORR_REGISTER_TAB_GROUPS rather than a duplicated list."
    )
    # Keeps the broadcast controls consistent whenever the register changes.
    assert "this.corrSyncBroadcastToOrg()" in body


def test_recipient_org_picker_is_scoped_to_the_registers_children(admin_js: str, correspondence_panel: str):
    """Owner 2026-10-26: "in receipient only childrem under that parent should
    show, not everything else". The recipient-organization type-ahead must
    filter the register org's own descendants in-memory, NOT call the global
    corrSearchOrg()/admin-organizations search every other org picker uses."""
    # Candidates come from the shared subtree walk, rooted at the register org.
    cand = re.search(r"get corrRecipientOrgCandidates\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert cand, "corrRecipientOrgCandidates getter not found."
    assert "this._corrDescendantOrgs(o.organization_pk)" in cand.group(0), (
        "Recipient candidates must be the register org's descendants, via the "
        "shared _corrDescendantOrgs() walk."
    )

    handler = re.search(r"corrOnRecipientOrgQueryInput\(picker\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert handler, "corrOnRecipientOrgQueryInput() not found."
    hbody = handler.group(0)
    assert "this.corrRecipientOrgCandidates" in hbody
    assert "corrSearchOrg" not in hbody and "apiFetch" not in hbody, (
        "The recipient picker must not reach the global org-search endpoint — "
        "that is exactly the 'everything else' the owner asked to remove."
    )

    # Both recipient-org inputs in the markup must use the scoped handler.
    recipient_inputs = re.findall(
        r"""x-model="corrCreateForm\.recipientOrg\.query"\s*\n\s*@input="(\w+)\(""",
        correspondence_panel,
    )
    assert recipient_inputs, "No recipientOrg query inputs found."
    assert set(recipient_inputs) == {"corrOnRecipientOrgQueryInput"}, (
        f"Every recipientOrg input must use the subtree-scoped handler; "
        f"found {sorted(set(recipient_inputs))}."
    )


def test_shared_descendant_walk_is_used_by_both_consumers(admin_js: str):
    """Standing no-duplicates rule: the subtree walk behind the circular's
    type dropdown and the recipient candidates must be ONE helper, not two
    copies of the same traversal.

    (Scoped to the correspondence consumers on purpose. scopeOrgPkSet has its
    own, pre-existing walk with a genuinely different contract — many roots,
    roots included, returns pks, no org-type exclusion — so it is deliberately
    not folded in here.)"""
    helper = re.search(r"_corrDescendantOrgs\(rootPk\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert helper, "_corrDescendantOrgs() helper not found."
    assert 'new Set(["NILACHALA_KUTIRA", "SMRUTI_MANDIRA"])' in helper.group(0), (
        "The shared walk must exclude the apex singletons (owner: 'always "
        "exclude kutira and smurti mandira')."
    )
    assert "parent_organization_pk" in helper.group(0)
    for consumer in ("get corrBroadcastTypeOptions()", "get corrRecipientOrgCandidates()"):
        fn = re.search(re.escape(consumer) + r"\s*\{.*?\n        \},", admin_js, re.DOTALL)
        assert fn, f"{consumer} not found."
        assert "this._corrDescendantOrgs(" in fn.group(0), (
            f"{consumer} must delegate to the shared _corrDescendantOrgs() walk."
        )
        assert "childrenByParent" not in fn.group(0), (
            f"{consumer} carries its own parent/child traversal — delegate to "
            "_corrDescendantOrgs() instead of duplicating it."
        )


def test_create_correspondence_delegates_broadcast_to_its_own_method(admin_js: str):
    fn = re.search(
        r"async createCorrespondence\(\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert fn, "createCorrespondence() not found."
    assert "if (f.isBroadcast) { return this.createBroadcastCorrespondence(); }" in fn.group(0), (
        "createCorrespondence() must delegate to createBroadcastCorrespondence() "
        "for isBroadcast — the two payload shapes share no fields."
    )

    broadcast_fn = re.search(
        r"async createBroadcastCorrespondence\(\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert broadcast_fn, "createBroadcastCorrespondence() not found."
    body = broadcast_fn.group(0)
    assert '"/api/v1/correspondence/broadcast"' in body
    assert "recipient_organization_type_code" in body
    # Deliberately absent: no sender_type/sender_organization_pk in the
    # request body — the backend hardcodes sender=ORGANIZATION itself.
    assert "sender_type" not in body
    assert "recipient_count" in body, "Must surface how many orgs the circular actually reached."


# ── Dispatch (v1.1, two-sided org-to-org register) ──────────────────────

def test_dispatch_button_gated_to_outward_organization_with_no_counterpart(correspondence_panel: str):
    """
    Dispatch only ever makes sense for an OUTWARD row addressed to
    recipient_type=ORGANIZATION that has no counterpart yet — showing it
    anywhere else (PERSON/EXTERNAL recipient, an INWARD row, or an
    already-dispatched row) would offer an action the API will always
    422/409 on.
    """
    assert (
        """x-show="corrSelected?.direction === 'OUTWARD' && corrSelected?.recipient_type === 'ORGANIZATION'\""""
        in correspondence_panel
    ), "The dispatch section must be gated to OUTWARD + recipient_type=ORGANIZATION."
    assert 'x-show="!corrSelected?.counterpart_correspondence_pk"' in correspondence_panel, (
        "The Dispatch button itself must be gated on the row not already having a counterpart."
    )
    button_match = re.search(
        r"""<button[^>]*@click="dispatchCorrespondence\(\)"[^>]*>""",
        correspondence_panel, re.DOTALL,
    )
    assert button_match, "No <button> wired to dispatchCorrespondence()."
    assert 'x-show="canManageCorrespondence"' in button_match.group(0), (
        "The Dispatch button must be gated on canManageCorrespondence like every other write action."
    )


def test_dispatched_counterpart_is_shown_on_both_sides(correspondence_panel: str):
    """Once dispatched, each side must show a clickable link to its
    counterpart via viewCorrespondence() — the pk alone is meaningless to
    a human reading the register."""
    assert "corrSelected?.counterpart_reference_number" in correspondence_panel
    assert "viewCorrespondence(corrSelected.counterpart_correspondence_pk)" in correspondence_panel


# ── History + reply-thread path tracker ──────────────────────────────────
# (owner 2026-10-26: "can we add history with path tracker for
# correspondance?")

def test_history_section_is_wired(correspondence_panel: str):
    assert ">History</h4>" in correspondence_panel
    assert "corrHistory.events" in correspondence_panel
    assert "corrHistoryLoading" in correspondence_panel
    assert "corrHistoryError" in correspondence_panel


def test_reply_thread_path_renders_ancestors_this_record_and_descendants(correspondence_panel: str):
    assert "corrHistory.ancestors" in correspondence_panel
    assert "corrHistory.descendants" in correspondence_panel
    # Thread nodes must link via the SAME viewCorrespondence() the detail
    # view's own cross-links (counterpart/in-reply-to) already use —
    # not a separate, duplicated navigation path.
    assert 'viewCorrespondence(node.correspondence_pk)' in correspondence_panel


def test_view_correspondence_loads_history(admin_js: str):
    fn = re.search(r"async viewCorrespondence\(pk\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "viewCorrespondence() not found."
    assert "this.loadCorrHistory()" in fn.group(0), (
        "viewCorrespondence() must trigger the history/path-tracker load, "
        "same as it already does for documents/finance references."
    )
    # Stale history from the PREVIOUSLY viewed record must not flash while
    # the new fetch is in flight.
    assert "this.corrHistory = { events: [], ancestors: [], descendants: [] };" in fn.group(0)


def test_load_corr_history_hits_the_history_endpoint(admin_js: str):
    fn = re.search(r"async loadCorrHistory\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "loadCorrHistory() not found."
    assert "/history`" in fn.group(0)
    assert "this.corrHistory = await res.json();" in fn.group(0)


# ── No dangling Alpine bindings ─────────────────────────────────────────

# Every handler the correspondence markup calls. Verified present in
# admin.html at the time of writing; the point of the test is that admin.js
# must keep defining them.
CORRESPONDENCE_HANDLERS = (
    "loadCorrespondence",
    "corrApplyFilters",
    "corrClearOrgFilter",
    "corrSelectOrg",
    "corrOnOrgQueryInput",
    "toggleCorrCreateForm",
    "createCorrespondence",
    "viewCorrespondence",
    "submitCorrResponsibleParty",
    "dispatchCorrespondence",
    "corrSelectOrgChoice",
)


@pytest.mark.parametrize("handler", CORRESPONDENCE_HANDLERS)
def test_handler_is_defined_in_admin_js(handler: str, admin_js: str):
    assert re.search(rf"(async\s+)?{handler}\s*\(", admin_js), (
        f"admin.html calls {handler}() but admin.js does not define it."
    )


@pytest.mark.parametrize("handler", CORRESPONDENCE_HANDLERS)
def test_handler_is_actually_used_by_the_markup(handler: str, admin_html: str):
    """Guards the other direction: a handler listed above that the markup no
    longer calls means this test file has gone stale, not that the app is
    broken — fail loudly rather than keep asserting something meaningless."""
    assert f"{handler}(" in admin_html, (
        f"{handler}() is no longer referenced anywhere in admin.html — update "
        "CORRESPONDENCE_HANDLERS in this test."
    )


# ── Simplified create form — JS-side defaulting logic ───────────────────
# corrResolveDefaultOrg() is an internal helper (not directly Alpine-bound
# in admin.html, so it doesn't belong in CORRESPONDENCE_HANDLERS above) —
# verified here instead by checking it's actually wired into the one place
# that must call it.

def test_toggle_create_form_resolves_default_org_and_todays_date(admin_js: str):
    toggle_fn = re.search(
        r"toggleCorrCreateForm\(direction\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert toggle_fn, "toggleCorrCreateForm() not found."
    body = toggle_fn.group(0)
    assert "corrResolveDefaultOrg()" in body, (
        "toggleCorrCreateForm() must call corrResolveDefaultOrg() so the "
        "register organization is pre-filled when the form opens."
    )
    assert "corrCreateForm.date = new Date().toISOString().slice(0, 10)" in body, (
        "toggleCorrCreateForm() must default the collapsed Date field to today."
    )


def test_create_correspondence_defaults_our_side_to_the_register_org(admin_js: str):
    """
    The core simplification: unless usPartyOverride is set, the OUTWARD
    sender / INWARD recipient must be forced to ORGANIZATION = the
    register org — never left to whatever f.sender_type/f.recipient_type
    happens to hold (that state only matters for the override picker).
    """
    fn = re.search(
        r"async createCorrespondence\(\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert fn, "createCorrespondence() not found."
    body = fn.group(0)
    assert 'const usIsSender = f.direction === "OUTWARD";' in body
    assert (
        'if (usIsSender && !f.usPartyOverride) {\n'
        '                body.sender_type = "ORGANIZATION";\n'
        '                body.sender_organization_pk = f.org.selected.organization_pk;'
    ) in body
    assert (
        '} else if (!usIsSender && !f.usPartyOverride) {\n'
        '                body.recipient_type = "ORGANIZATION";\n'
        '                body.recipient_organization_pk = f.org.selected.organization_pk;'
    ) in body
    # The other party's fields are only populated when it's genuinely in
    # question — i.e. precisely the complement of the two blocks above.
    assert "if (!usIsSender || f.usPartyOverride) {" in body
    assert "if (usIsSender || f.usPartyOverride) {" in body


def test_create_correspondence_honours_split_dates(admin_js: str):
    fn = re.search(
        r"async createCorrespondence\(\)\s*\{.*?\n        \},",
        admin_js, re.DOTALL,
    )
    assert fn, "createCorrespondence() not found."
    body = fn.group(0)
    assert "const correspondence_date = f.splitDates ? f.correspondence_date : f.date;" in body
    assert "const received_or_sent_date = f.splitDates ? f.received_or_sent_date : f.date;" in body


def test_register_tab_groups_include_the_advisory_board_tab(admin_js: str):
    """Owner 2026-10-30: "Advisory Board needs a correspondence register" — the
    singleton ADVISORY_BOARD organization gets its own register tab group."""
    body = re.search(r"const CORR_REGISTER_TAB_GROUPS = \[(.*?)\];", admin_js, re.DOTALL).group(1)
    assert re.search(
        r"""\{\s*key:\s*"ADVISORY_BOARD",\s*label:\s*"Advisory Board",\s*typeCodes:\s*\["ADVISORY_BOARD"\]""", body,
    ), "No Advisory Board tab group."


def test_advisory_board_scope_resolves_to_its_own_register(admin_js: str):
    """The ADVISORY_BOARD scope level carries no organization_pk, so its register
    is resolved by TYPE through the shared NULL_ORG_SCOPE_ORG_TYPE map."""
    assert re.search(r"const NULL_ORG_SCOPE_ORG_TYPE = \{[^}]*ADVISORY_BOARD:\s*\"ADVISORY_BOARD\"", admin_js, re.DOTALL)
    resolve = admin_js.split("corrResolveDefaultOrg() {")[1].split("// Group the candidates")[0]
    assert "NULL_ORG_SCOPE_ORG_TYPE[s.scope_level]" in resolve


def test_broadcast_type_options_never_offer_the_singleton_advisory_board(admin_js: str):
    getter = re.search(r"get corrBroadcastTypeOptions\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL).group(0)
    assert 'typeCodes.delete("ADVISORY_BOARD")' in getter
    assert '"ADVISORY_BOARD"' not in re.search(r"get corrCanBroadcast\(\)\s*\{.*?\n        \},", admin_js, re.DOTALL).group(0)


def test_org_picker_search_uses_the_scope_aware_in_scope_endpoint(admin_js: str):
    """The Correspondence organization-filter / sender / responsible pickers
    used /admin/organizations (ADMIN_USER_VIEW), which 403'd -- silently empty
    -- for the Advisory Board admin. They now call the scoped
    /organization/organizations/in-scope (ORGANIZATION_VIEW)."""
    body = re.search(r"async corrSearchOrg\(picker\) \{.*?\n        \},", admin_js, re.DOTALL).group(0)
    assert "/api/v1/organization/organizations/in-scope" in body
    assert "/api/v1/admin/organizations" not in body
    # results are normalised to the type_name / type_code shape the markup reads
    assert "type_name: o.organization_type_name" in body
