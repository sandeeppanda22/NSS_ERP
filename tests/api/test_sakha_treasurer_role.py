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


def test_the_role_carries_view_manage_and_configure_but_never_approve():
    granted = set(re.findall(r"\('NSS_ERP_SAKHA_TREASURER', '([A-Z_]+)'\)", PATCH))
    assert granted == {"FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_CONFIGURE"}      # owner 2026-11-20: the Treasurer also configures the Sakha's finance
    assert "FINANCE_APPROVE" not in granted            # approvals follow the seats (finance_approval.py), recording / configuring / approving stay separate


def test_the_controls_that_bind_the_treasurer_are_refused_by_seat_in_every_place_they_can_be_changed():
    """FINANCE_CONFIGURE would let the Treasurer loosen their own check, so the API refuses those changes to the SEATED Treasurer."""
    import inspect

    from api.routers import finance_approval as router_approval
    from api.routers import finance_setup as router_setup
    from api.services import finance_approval as service

    assert "def require_not_the_treasurer(" in inspect.getsource(service)
    assert "A.require_not_the_treasurer(cur, user, body.organization_pk" in inspect.getsource(router_approval.put_approval_policy)      # the default limit
    create, update = inspect.getsource(router_setup.create_head), inspect.getsource(router_setup.update_head)
    assert "FA.require_not_the_treasurer(" in create and "body.skips_approval or body.treasurer_limit is not None" in create
    assert "FA.require_not_the_treasurer(" in update and "cur_skips" in update and "cur_limit" in update                 # only a CHANGED value counts


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
