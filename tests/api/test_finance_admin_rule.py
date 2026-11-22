"""
Who may set up a Sangha's books - create its financial scopes and funds (owner 2026-11-22): a FINANCE ADMINISTRATOR, and being an admin does not make
anyone one by default. Exactly two ways:

  1. the seated Treasurer, President or Secretary of a Sakha, for THEIR Sakha (by seat);
  2. an admin who has been GIVEN a Finance role (NSS_ERP_SAKHA_FINANCE_ADMIN / NSS_ERP_KENDRA_FINANCE_ADMIN), within that role's own scope.

The NSS ERP Administrator (super administrator, by role) is one everywhere. DB-free: the rule runs against stand-in cursors; the end-to-end behaviour is in
tests/api/test_finance_approval.py (Treasurer) and tests/api/test_finance_scope_activate.py.
"""
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import finance as F
from api.services import finance_approval as A

ROOT = Path(__file__).resolve().parents[2]
PATCH = (ROOT / "database/seed/00_bootstrap/11_finance_admin_roles_patch.sql").read_text(encoding="utf-8")


class _User:
    """Just enough of UserContext: scopes, person, and the super-administrator test; dataclasses.replace needs a real dataclass, so use one."""


def _user(*roles, person="p1", super_admin=False):
    from api.services.rbac_service import ScopeInfo, UserContext

    scopes = [ScopeInfo(user_role_pk=None, role_code=r, scope_level="SAKHA", organization_pk="org-" + r) for r in roles]
    if super_admin:
        scopes.append(ScopeInfo(user_role_pk=None, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None))
    return UserContext(user_account_pk="u1", person_pk=person, scopes=scopes)


class _Cur:
    """Answers the two queries the rule asks: the seats held (via seat_service) and the Sakhas of those seats."""

    def __init__(self, office_orgs=()):
        self.office_orgs, self.sql = list(office_orgs), []

    def execute(self, sql, params=()):
        self.sql.append(" ".join(sql.split()))
        self._rows = []
        if "FROM nss.body_member_assignment" in sql:
            self._rows = [("body-1",)] if self.office_orgs else []
        elif "FROM nss.body_master bm" in sql:
            self._rows = [(o,) for o in self.office_orgs]

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


# ── the rule ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_super_administrator_is_a_finance_administrator_everywhere():
    assert F._is_finance_admin(_Cur(), _user(super_admin=True)) is True
    assert F._is_finance_admin(_Cur(), _user(super_admin=True), "any-org") is True and F._is_finance_admin(_Cur(), _user(super_admin=True), None) is True


@pytest.mark.parametrize("role", ["NSS_ERP_KENDRA_ADMIN", "NSS_ERP_SAKHA_ADMIN", "NSS_ERP_ANCHALIKA_ADMIN", "NSS_ERP_ZILLA_ADMIN", "NSS_ERP_PATHA_CHAKRA_ADMIN"])
def test_an_admin_role_alone_is_not_a_finance_administrator(role):
    assert F._is_finance_admin(_Cur(), _user(role)) is False
    assert F._is_finance_admin(_Cur(), _user(role), "org-x") is False


def test_a_view_only_role_is_not_one_either():
    assert F._is_finance_admin(_Cur(), _user("NSS_ERP_AUDITOR", "NSS_ERP_REPORT_VIEWER")) is False


def test_a_seated_treasurer_president_or_secretary_is_a_finance_administrator_of_their_own_sakha_only():
    cur = _Cur(office_orgs=["sakha-A"])
    assert F._is_finance_admin(cur, _user("NSS_ERP_SAKHA_TREASURER"), "sakha-A") is True
    assert F._is_finance_admin(cur, _user("NSS_ERP_SAKHA_ADMIN"), "sakha-A") is True           # a President / Secretary: by SEAT, whatever role carries it
    assert F._is_finance_admin(cur, _user("NSS_ERP_SAKHA_TREASURER"), "sakha-B") is False
    assert F._is_finance_admin(cur, _user("NSS_ERP_SAKHA_TREASURER"), None) is False             # a scope with no Sangha is for the global authority
    assert F._is_finance_admin(cur, _user("NSS_ERP_SAKHA_TREASURER")) is True                    # "anywhere": what the page asks to show its buttons


def test_no_seat_no_office_even_with_the_treasurer_role_left_over():
    assert F._is_finance_admin(_Cur(office_orgs=[]), _user("NSS_ERP_SAKHA_TREASURER"), "sakha-A") is False


def test_an_assigned_finance_role_makes_an_admin_one_within_that_roles_scope(monkeypatch):
    seen = {}

    def fake_reach(cur, user):
        seen["roles"] = sorted(s.role_code for s in user.scopes)
        return {"sakha-A", "child-of-A"}

    monkeypatch.setattr(F, "actor_scope_org_pks", fake_reach)
    admin = _user("NSS_ERP_SAKHA_ADMIN", "NSS_ERP_SAKHA_FINANCE_ADMIN")
    assert F._is_finance_admin(_Cur(), admin, "sakha-A") is True and F._is_finance_admin(_Cur(), admin, "child-of-A") is True
    assert F._is_finance_admin(_Cur(), admin, "sakha-B") is False
    assert F._is_finance_admin(_Cur(), admin, None) is False
    assert seen["roles"] == ["NSS_ERP_SAKHA_FINANCE_ADMIN"]                    # ONLY the Finance role's reach counts, not the plain admin role's
    assert F._is_finance_admin(_Cur(), admin) is True                          # anywhere


def test_a_finance_role_with_global_reach_covers_everything(monkeypatch):
    monkeypatch.setattr(F, "actor_scope_org_pks", lambda cur, user: None)
    assert F._is_finance_admin(_Cur(), _user("NSS_ERP_KENDRA_FINANCE_ADMIN"), "any") is True
    assert F._is_finance_admin(_Cur(), _user("NSS_ERP_KENDRA_FINANCE_ADMIN"), None) is True


def test_the_refusal_is_a_403_that_names_the_two_ways_in():
    with pytest.raises(HTTPException) as e:
        F._require_finance_admin(_Cur(), _user("NSS_ERP_SAKHA_ADMIN"), "create a fund", "org-1")
    assert e.value.status_code == 403 and "Treasurer, President or Secretary" in e.value.detail and "Finance role" in e.value.detail
    F._require_finance_admin(_Cur(), _user(super_admin=True), "create a fund", "org-1")           # no error


def test_scope_and_fund_creation_ask_it_per_sangha_before_anything_else_is_revealed():
    scope, fund = inspect.getsource(F.create_scope), inspect.getsource(F.create_fund)
    assert '_require_finance_admin(cur, user, "create a financial scope", body.organization_pk)' in scope
    assert '_require_finance_admin(cur, user, "create a fund", scope["organization_pk"])' in fund           # the fund's SCOPE's Sangha
    assert scope.index("_require_finance_admin(") < scope.index("_require_org_access(")
    assert fund.index("_require_finance_admin(") < fund.index("_require_org_access(")


def test_the_reference_tells_the_page_and_the_old_role_based_check_is_gone():
    from api.schemas.finance import FinanceReference

    assert "finance_admin" in FinanceReference.model_fields and '"finance_admin": finance_admin' in inspect.getsource(F.reference)
    assert not hasattr(F, "TREASURER_ROLE") and not hasattr(F, "_FINANCE_WRITE_PERMISSIONS")


# ── the seats ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_three_offices_are_the_treasurer_president_and_secretary():
    assert A.FINANCE_OFFICES == ("TREASURER", "PRESIDENT", "SECRETARY")


def test_office_sakhas_reads_the_seats_and_returns_the_sakhas_of_the_bodies():
    cur = _Cur(office_orgs=["sakha-A", "sakha-B"])
    assert A.office_sakhas(cur, "p1") == {"sakha-A", "sakha-B"}
    sql = next(s for s in cur.sql if "FROM nss.body_master bm" in s)
    assert "bt.body_type_code = %s" in sql and "bm.organization_pk IS NOT NULL" in sql           # only SAKHA Governing Bodies, never the Kendra's or an NSS-wide one
    assert A.office_sakhas(_Cur(), "p1") == set() and A.office_sakhas(_Cur(office_orgs=["x"]), None) == set()


# ── the roles ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_finance_roles_are_scoped_organizational_roles_that_carry_only_finance():
    for role, level in (("NSS_ERP_SAKHA_FINANCE_ADMIN", "SAKHA"), ("NSS_ERP_KENDRA_FINANCE_ADMIN", "KENDRA")):
        assert re.search(rf"\('{role}',\s+'[^']+',\s+'ORGANIZATIONAL',\s+'{level}'", PATCH), role
    granted = {}
    for role, permission in re.findall(r"\('(NSS_ERP_[A-Z_]+FINANCE_ADMIN)',\s+'([A-Z_]+)'\)", PATCH):
        granted.setdefault(role, set()).add(permission)
    assert granted["NSS_ERP_SAKHA_FINANCE_ADMIN"] == {"FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_CONFIGURE"}      # a Sakha approves by its seats, never by permission
    assert granted["NSS_ERP_KENDRA_FINANCE_ADMIN"] == {"FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_CONFIGURE", "FINANCE_APPROVE"}   # the Kendra has no seat chain
    assert not any(p.startswith("ADMIN_") for ps in granted.values() for p in ps)                                   # a Finance role is not an admin role
    assert "ON CONFLICT (role_code) DO NOTHING" in PATCH and "ON CONFLICT (role_master_pk, permission_master_pk) DO NOTHING" in PATCH
    assert "DELETE" not in PATCH.upper().replace("NEVER REMOVES", "")


def test_the_role_names_in_the_code_are_the_ones_the_patch_creates():
    for role in F.FINANCE_ADMIN_ROLES:
        assert f"'{role}'" in PATCH


def test_the_three_build_scripts_apply_the_patch_after_the_treasurer_patch():
    for rel in ("database/scripts/02_build.sh", "render_build.sh", "database/scripts/02_build.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert text.rindex("11_finance_admin_roles_patch.sql") > text.rindex("10_sakha_treasurer_role_patch.sql"), rel


# ═══════════════════════════════════════════════════════════════════════
# "All finance related should come from finance roles" (owner 2026-11-22)
# ═══════════════════════════════════════════════════════════════════════
BOOT = ROOT / "database/seed/00_bootstrap"
ADMIN_ROLES = ("NSS_ERP_KENDRA_ADMIN", "NSS_ERP_SAKHA_ADMIN", "NSS_ERP_PATHA_CHAKRA_ADMIN", "NSS_ERP_ANCHALIKA_ADMIN", "NSS_ERP_ZILLA_ADMIN")
REVOKE = (BOOT / "12_finance_permissions_revoke_patch.sql").read_text(encoding="utf-8")


def _grants(text: str) -> set[tuple[str, str]]:
    return set(re.findall(r"\('(NSS_ERP_[A-Z_]+)',\s+'(FINANCE_[A-Z]+)'\)", text))


def test_the_original_patches_no_longer_grant_finance_to_any_admin_role():
    granted = _grants((BOOT / "08_finance_permissions_patch.sql").read_text(encoding="utf-8")) | _grants((BOOT / "09_finance_configure_permission_patch.sql").read_text(encoding="utf-8"))
    assert not {r for r, _ in granted} & set(ADMIN_ROLES)
    assert {r for r, _ in granted} == {"NSS_ERP_ADMIN", "NSS_ERP_AUDITOR", "NSS_ERP_REPORT_VIEWER"}                 # the super administrator and the read-only system roles


def test_the_revoke_patch_withdraws_exactly_what_the_admin_roles_used_to_carry():
    withdrawn = _grants(REVOKE)
    assert {r for r, _ in withdrawn} == set(ADMIN_ROLES)
    assert withdrawn == {
        ("NSS_ERP_KENDRA_ADMIN", "FINANCE_VIEW"), ("NSS_ERP_KENDRA_ADMIN", "FINANCE_MANAGE"), ("NSS_ERP_KENDRA_ADMIN", "FINANCE_APPROVE"), ("NSS_ERP_KENDRA_ADMIN", "FINANCE_CONFIGURE"),
        ("NSS_ERP_SAKHA_ADMIN", "FINANCE_VIEW"), ("NSS_ERP_SAKHA_ADMIN", "FINANCE_MANAGE"), ("NSS_ERP_SAKHA_ADMIN", "FINANCE_CONFIGURE"),
        ("NSS_ERP_PATHA_CHAKRA_ADMIN", "FINANCE_VIEW"), ("NSS_ERP_PATHA_CHAKRA_ADMIN", "FINANCE_MANAGE"),
        ("NSS_ERP_ANCHALIKA_ADMIN", "FINANCE_VIEW"), ("NSS_ERP_ZILLA_ADMIN", "FINANCE_VIEW"),
    }
    assert "is_active  = FALSE" in REVOKE and "deleted_at = NOW()" in REVOKE and "rp.is_active           = TRUE" in REVOKE       # soft delete, idempotent
    assert not re.search(r"^\s*DELETE\s", REVOKE, re.M | re.I)


def test_nothing_the_revoke_patch_withdraws_is_granted_again_by_a_finance_role_patch():
    again = _grants(PATCH) | _grants((BOOT / "10_sakha_treasurer_role_patch.sql").read_text(encoding="utf-8"))
    assert not {r for r, _ in again} & set(ADMIN_ROLES)


def test_the_three_builds_run_the_revoke_after_every_patch_that_grants():
    for rel in ("database/scripts/02_build.sh", "render_build.sh", "database/scripts/02_build.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        revoke = text.rindex("12_finance_permissions_revoke_patch.sql")
        for earlier in ("08_finance_permissions_patch.sql", "09_finance_configure_permission_patch.sql", "10_sakha_treasurer_role_patch.sql", "11_finance_admin_roles_patch.sql"):
            assert revoke > text.rindex(earlier), (rel, earlier)


def test_the_finance_offices_hold_the_finance_roles_by_seat():
    from api.services import rbac_service

    rules = rbac_service._COMPOSITE_GRANT_RULES_SQL
    assert re.search(r"\('SAKHA_GOVERNING_BODY',\s+NULL,\s+ARRAY\['PRESIDENT','SECRETARY'\],\s+'NSS_ERP_SAKHA_FINANCE_ADMIN',\s+'BODY_ORG'\)", rules)
    # the Kendra, by the Bye-Law: the Treasurer (in charge of the funds, keeps the accounts) and the Secretary (keeps the records and accounts, prepares the
    # budget, operates the funds jointly with the Treasurer) - NOT the President, whose part is the written order for a disbursement
    assert re.search(r"\('KENDRA_GOVERNING_BODY',\s+NULL,\s+ARRAY\['TREASURER','SECRETARY'\],\s+'NSS_ERP_KENDRA_FINANCE_ADMIN',\s+'NULL'\)", rules)
    assert "PRESIDENT" not in re.search(r"\('KENDRA_GOVERNING_BODY',[^)]*?'NSS_ERP_KENDRA_FINANCE_ADMIN'", rules, re.S).group(0)
    assert re.search(r"\('SAKHA_GOVERNING_BODY',\s+NULL,\s+ARRAY\['TREASURER'\],\s+'NSS_ERP_SAKHA_TREASURER',\s+'BODY_ORG'\)", rules)       # unchanged
    assert re.search(r"\('SAKHA_GOVERNING_BODY',\s+NULL,\s+ARRAY\['PRESIDENT','SECRETARY'\],\s+'NSS_ERP_SAKHA_ADMIN',\s+'BODY_ORG'\)", rules)  # their admin role stays, without finance
    for role in ("NSS_ERP_SAKHA_FINANCE_ADMIN", "NSS_ERP_KENDRA_FINANCE_ADMIN"):
        assert f"'{role}'" in PATCH                                                  # the roles the rules grant are the ones the patch creates


def test_every_role_that_still_carries_finance_is_a_finance_role_or_a_system_role():
    carrying = set()
    for name in ("08_finance_permissions_patch.sql", "09_finance_configure_permission_patch.sql", "10_sakha_treasurer_role_patch.sql", "11_finance_admin_roles_patch.sql"):
        carrying |= {r for r, _ in _grants((BOOT / name).read_text(encoding="utf-8"))}
    assert carrying == {"NSS_ERP_ADMIN", "NSS_ERP_AUDITOR", "NSS_ERP_REPORT_VIEWER", "NSS_ERP_SAKHA_TREASURER", "NSS_ERP_SAKHA_FINANCE_ADMIN", "NSS_ERP_KENDRA_FINANCE_ADMIN"}


def test_the_page_unlocks_the_treasurers_controls_only_for_a_finance_role():
    js = (ROOT / "frontend/assets/js/finance-setup.js").read_text(encoding="utf-8")
    body = js.split("get finControlsLocked()", 1)[1].split("},", 1)[0]
    assert '"NSS_ERP_SAKHA_FINANCE_ADMIN"' in body and '"NSS_ERP_KENDRA_FINANCE_ADMIN"' in body and '"NSS_ERP_SAKHA_ADMIN"' not in body
    dash = (ROOT / "frontend/assets/js/dashboard.js").read_text(encoding="utf-8")
    for role in ("NSS_ERP_SAKHA_FINANCE_ADMIN", "NSS_ERP_KENDRA_FINANCE_ADMIN"):
        assert f"{role}: {{" in dash                                                  # the member dashboard offers a Finance entry


# ── the Kendra's seats follow the Bye-Law (owner 2026-11-22: "for Kendra finance, refer bye-law") ──────────────────────────────────────────────────────
NSS_REF = ROOT / "docs/01_Authoritative_References/NSS"


def _ref(*parts: str) -> str:
    return " ".join((NSS_REF.joinpath(*parts)).read_text(encoding="utf-8").split())


def test_the_bye_law_says_what_the_kendra_seat_rule_rests_on():
    treasurer = _ref("SECTION-C_CONSTITUTION_OF_THE_KENDRA_SANGHA", "REF-003-C(i)(7)_Duties_of_the_Treasurer.md")
    assert "The Treasurer shall be in charge of the funds of Kendra Sangha and maintain proper accounts" in treasurer          # C(i)(7)(a)
    assert "only on the written orders of the President for execution of any scheme" in treasurer                              # C(i)(7)(b): the President's part is the ORDER
    secretary = _ref("SECTION-C_CONSTITUTION_OF_THE_KENDRA_SANGHA", "REF-003-C(i)(5)_Duties_of_the_Secretary.md")
    assert "The Secretary shall maintain all the records, the accounts and documents of the Kendra Sangha" in secretary          # C(i)(5)(b)
    assert "Draft Annual Budget" in secretary                                                                                 # C(i)(5)(e)
    funds = _ref("SECTION-F_FUNDS_OF_THE_KENDRA_SANGHA", "REF-003-F[b]_Maintenance_of_the_Funds.md")
    assert "operated upon jointly by the Secretary and the Treasurer" in funds                                                  # F[b]


def test_so_the_kendras_finance_seats_are_the_treasurer_and_the_secretary_and_not_the_president():
    from api.services import rbac_service

    row = re.search(r"\('KENDRA_GOVERNING_BODY',\s+NULL,\s+ARRAY\[([^\]]*)\],\s+'NSS_ERP_KENDRA_FINANCE_ADMIN'", rbac_service._COMPOSITE_GRANT_RULES_SQL)
    assert row and set(re.findall(r"'([A-Z_]+)'", row.group(1))) == {"TREASURER", "SECRETARY"}
    assert "PRESIDENT" in PATCH and "written order" in PATCH                                       # the patch says why he is not in it
    assert "REF-003-C(i)(7)(a)" in PATCH and "REF-003-F[b]" in PATCH                               # and cites the clauses
