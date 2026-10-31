"""
Advisory Board dashboard wiring (owner decision 2026-10-30). Parses the shipped
files directly -- no browser, no server -- same style as
test_ui_admin_correspondence.py.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
DASHBOARD_HTML = (FRONTEND / "dashboard.html").read_text(encoding="utf-8")
DASHBOARD_JS = (FRONTEND / "assets" / "js" / "dashboard.js").read_text(encoding="utf-8")


def test_tab_is_offered_to_the_advisory_board_admin_and_nss_wide_admins():
    getter = re.search(r"get canViewAdvisoryBoardDashboard\(\) \{.*?\n        \},", DASHBOARD_JS, re.DOTALL).group(0)
    assert "this.isGovNssWideAdmin" in getter
    assert "NSS_ERP_ADVISORY_BOARD_ADMIN" in getter
    assert 'x-if="canViewAdvisoryBoardDashboard"' in DASHBOARD_HTML
    assert "switchTab('advisoryBoard')" in DASHBOARD_HTML


def test_loader_reads_the_single_dashboard_endpoint_and_is_wired_to_tab_switches():
    assert "/api/v1/governance/advisory-board/dashboard" in DASHBOARD_JS
    assert 'tab === "advisoryBoard"' in DASHBOARD_JS
    assert DASHBOARD_JS.count("_loadAdvisoryBoardDashboard()") >= 3  # definition + refresh + direct load


def test_panel_shows_roster_vacancies_office_bearers_acting_cover_and_links():
    start = DASHBOARD_HTML.index("x-show=\"tab === 'advisoryBoard'\"")
    end = DASHBOARD_HTML.index("<!-- ═══ Governance Tab ═══ -->")
    panel = DASHBOARD_HTML[start:end]
    for needle in (
        "adbDash.data.members", "adbDash.data.missing_sakhas", "adbDash.data.office_bearers",
        "adbDash.data.acting_cover", "adbDash.data.vacancies", "adbDash.data.seats_filled",
        'href="/admin#govAssignments"', 'href="/admin#correspondence"',
    ):
        assert needle in panel, needle
    # Meetings / decisions are not modelled: nothing may be rendered for them.
    assert "meeting" not in panel.lower().replace("meetings and decisions", "")
