"""
DB-free checks of the Sakha Treasurer finance role (owner 2026-11-20): the seated Treasurer of a Sakha's Governing Body is the finance
administrator of that Sakha - record and configure, never approve by permission, and nothing outside finance.
"""
import re
from pathlib import Path

from api.services import rbac_service

ROOT = Path(__file__).resolve().parents[2]
PATCH = (ROOT / "database/seed/00_bootstrap/10_sakha_treasurer_role_patch.sql").read_text(encoding="utf-8")


def test_the_composite_rule_gives_the_treasurer_seat_the_finance_role_over_the_sakhas_own_organization():
    rules = rbac_service._COMPOSITE_GRANT_RULES_SQL
    assert re.search(r"\('SAKHA_GOVERNING_BODY',\s+NULL,\s+ARRAY\['TREASURER'\],\s+'NSS_ERP_SAKHA_TREASURER',\s+'BODY_ORG'\)", rules)
    # the existing President / Secretary rule for the same body is untouched
    assert re.search(r"\('SAKHA_GOVERNING_BODY',\s+NULL,\s+ARRAY\['PRESIDENT','SECRETARY'\],\s+'NSS_ERP_SAKHA_ADMIN',\s+'BODY_ORG'\)", rules)


def test_the_role_carries_finance_view_and_manage_and_nothing_else():
    granted = set(re.findall(r"\('NSS_ERP_SAKHA_TREASURER', '([A-Z_]+)'\)", PATCH))
    assert granted == {"FINANCE_VIEW", "FINANCE_MANAGE"}
    assert "FINANCE_APPROVE" not in granted            # approvals follow the seats (finance_approval.py), recording / configuring / approving stay separate
    assert "FINANCE_CONFIGURE" not in granted          # the Treasurer must not be able to set the Treasurer's own approval limit


def test_the_role_is_an_organizational_sakha_scoped_role_and_the_patch_never_deletes():
    assert "'NSS_ERP_SAKHA_TREASURER'" in PATCH and "'ORGANIZATIONAL'" in PATCH and "'SAKHA'" in PATCH
    assert "ON CONFLICT (role_code) DO NOTHING" in PATCH and "ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING" in PATCH
    assert "DELETE" not in PATCH.upper().replace("NEVER REMOVES", "")


def test_the_three_build_scripts_apply_the_patch_after_the_finance_configure_patch():
    for rel, anchor in (("database/scripts/02_build.sh", "09_finance_configure_permission_patch.sql"),
                        ("render_build.sh", "09_finance_configure_permission_patch.sql"),
                        ("database/scripts/02_build.ps1", "09_finance_configure_permission_patch.sql")):
        text = (ROOT / rel).read_text(encoding="utf-8")
        calls = [m.start() for m in re.finditer(r"10_sakha_treasurer_role_patch\.sql", text)]
        assert calls, rel
        assert text.rindex("10_sakha_treasurer_role_patch.sql") > text.rindex(anchor), rel


def test_the_dashboard_offers_the_treasurer_a_finance_entry():
    js = (ROOT / "frontend/assets/js/dashboard.js").read_text(encoding="utf-8")
    block = js[js.index("NSS_ERP_SAKHA_TREASURER: {"):]
    assert 'adminUrl: "/admin#finOverview"' in block.split("},", 1)[0]
