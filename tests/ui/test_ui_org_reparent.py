"""
Source-level tests for the Sakha re-parent approval UI (owner rule
2026-10-30): the admin "Assign Sakhas" tab (admin.js/admin.html) and the
President approvals panel on the member dashboard (dashboard.js/
dashboard.html).

Needs no browser and no running server — parses the shipped files directly,
same style as test_ui_admin_correspondence.py. Written but not yet run.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
JS = FRONTEND / "assets" / "js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def admin_js():
    return _read(JS / "admin.js")


@pytest.fixture(scope="module")
def admin_html():
    return _read(FRONTEND / "admin.html")


@pytest.fixture(scope="module")
def dashboard_js():
    return _read(JS / "dashboard.js")


@pytest.fixture(scope="module")
def dashboard_html():
    return _read(FRONTEND / "dashboard.html")


@pytest.fixture(scope="module")
def nss_config_js():
    return _read(JS / "nss-config.js")


def _assign_panel(admin_html: str) -> str:
    start = admin_html.index("VIEW: Assign Sakhas to Anchalika/Zilla Sangha")
    end = admin_html.index("VIEW: Reference Data")
    return admin_html[start:end]


def test_assign_sakha_handles_the_202_deferred_response(admin_js: str):
    fn = re.search(r"async assignSakhaToParent\(s\)\s*\{.*?\n        \},", admin_js, re.DOTALL)
    assert fn, "assignSakhaToParent() not found."
    body = fn.group(0)
    assert "res.status === 202" in body and "reparent_request" in body
    # The 202 branch must return BEFORE the success path mutates the row's parent.
    assert body.index("res.status === 202") < body.index("s.parent_organization_pk = newParentPk")
    assert "assignSakhaNotice" in body


def test_assign_sakha_lists_sakha_asana_too_and_fetch_helper_repeats_type_code(admin_js: str):
    assert "_fetchAllAdminOrganizations(NSS.SAKHA_LIKE_ORG_TYPES)" in admin_js
    assert 'params.append("type_code", tc)' in admin_js


def test_assign_sakha_loads_and_cancels_requests_through_the_org_reparent_api(admin_js: str):
    assert "/api/v1/org-reparent?" in admin_js
    assert re.search(r"/api/v1/org-reparent/\$\{r\.organization_reparent_request_pk\}/cancel", admin_js)
    assert "_loadAssignSakhaRequests()" in admin_js


def test_assign_sakha_markup_bindings_exist_in_admin_js(admin_html: str, admin_js: str):
    panel = _assign_panel(admin_html)
    for name in ("assignSakhaNotice", "assignSakhaRequestFor", "assignSakhaIsPending", "cancelAssignSakhaRequest"):
        assert name in panel, f"{name} not used in the Assign Sakha panel."
        assert re.search(rf"\b{name}\b\s*[(:]", admin_js), f"{name} missing from admin.js."


def test_assign_button_is_disabled_while_a_request_is_pending(admin_html: str):
    panel = _assign_panel(admin_html)
    assert "assignSakhaIsPending(s)" in panel.split("assignSakhaToParent(s)")[0].rsplit("<button", 1)[1]


def test_dashboard_panel_uses_the_org_reparent_api(dashboard_js: str):
    assert "/api/v1/org-reparent?awaiting_my_decision=true" in dashboard_js
    assert re.search(
        r"/api/v1/org-reparent/\$\{req\.organization_reparent_request_pk\}/steps/\$\{step\.organization_reparent_step_pk\}/decide",
        dashboard_js,
    )
    assert "_loadReparentApprovals()" in dashboard_js
    # Reject needs remarks, mirroring the server rule.
    fn = re.search(r"async decideReparentStep\(req, decision\)\s*\{.*?\n        \},", dashboard_js, re.DOTALL)
    assert fn and 'decision === "REJECT" && !remarks' in fn.group(0)


def test_dashboard_markup_bindings_exist_in_dashboard_js(dashboard_html: str, dashboard_js: str):
    for name in ("reparentApprovals", "reparentRemarks", "reparentDeciding", "decideReparentStep"):
        assert name in dashboard_html, f"{name} not used in dashboard.html."
        assert re.search(rf"\b{name}\b\s*[(:]", dashboard_js), f"{name} missing from dashboard.js."


def test_pending_items_count_includes_reparent_approvals(dashboard_js: str):
    fn = re.search(r"myTotalPendingItemsCount\(\)\s*\{.*?\n        \},", dashboard_js, re.DOTALL)
    assert fn and "myPendingReparentApprovalsCount()" in fn.group(0)


def test_shared_chain_label_helpers_live_in_nss_config_not_duplicated(
    nss_config_js: str, admin_js: str, dashboard_js: str, admin_html: str, dashboard_html: str
):
    for helper in ("REPARENT_ROLE_LABELS", "reparentStatusBadgeClass(status)", "reparentStepLabel(step)"):
        assert helper in nss_config_js
    for src in (admin_js, dashboard_js):
        assert "REPARENT_ROLE_LABELS" not in src, "role labels must come from NSS (nss-config.js), not be redefined."
    assert "NSS.reparentStepLabel(" in admin_html and "NSS.reparentStepLabel(" in dashboard_html


def test_no_inline_event_handlers_in_the_new_markup(admin_html: str, dashboard_html: str):
    """CSP script-src has no 'unsafe-inline'."""
    for html in (_assign_panel(admin_html), dashboard_html):
        assert not re.search(r"\sonclick=", html)


def test_chain_label_map_has_the_leaving_parent_step(nss_config_js: str):
    """Owner 2026-10-31: Sakha President -> leaving Anchalika/Zilla President ->
    destination Anchalika/Zilla President -> Kendra President."""
    block = re.search(r"REPARENT_ROLE_LABELS:\s*\{(.*?)\}", nss_config_js, re.DOTALL)
    assert block, "REPARENT_ROLE_LABELS not found."
    body = block.group(1)
    roles = re.findall(r"([A-Z_]+):", body)
    assert roles == ["SAKHA_PRESIDENT", "SOURCE_PARENT_PRESIDENT", "DEST_PARENT_PRESIDENT", "KENDRA_PRESIDENT"]
    assert "Leaving Anchalika/Zilla President" in body


def test_assign_tab_hint_states_the_four_step_chain(admin_html: str):
    panel = _assign_panel(admin_html)
    flat = re.sub(r"\s+", " ", panel)
    assert ("Sakha President, then the leaving Anchalika/Zilla President, then the destination "
            "Anchalika/Zilla President, then the Kendra President") in flat


def test_sakha_like_types_come_from_the_one_shared_constant(admin_js: str, dashboard_js: str, nss_config_js: str):
    assert 'SAKHA_LIKE_ORG_TYPES: ["SAKHA_SANGHA", "SAKHA_ASANA"]' in nss_config_js
    for js in (admin_js, dashboard_js):
        assert "NSS.orgLevelTypes(" in js, "dashboard-level lookups must widen the Sakha level to Asana."
    assert "NSS.SAKHA_LIKE_ORG_TYPES" in admin_js
    assert "NSS.appendSakhaLikeTypeCodes(" in dashboard_js
    org_dash = _read(JS / "org-dashboard.js")
    assert "NSS.isSakhaLike(this.orgTypeCode)" in org_dash
