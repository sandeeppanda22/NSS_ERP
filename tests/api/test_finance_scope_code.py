"""
DB-free: the general scope of a Sangha gets a readable code (owner 2026-11-21): its short code + "-GENERAL" (EKM-GENERAL), numbered when taken, and
the old random form only when the Sangha has no short code. Existing scopes keep the codes they have.
"""
from api.services.finance_contribution import readable_scope_code


class _Cur:
    """A cursor that says which scope codes are already taken."""

    def __init__(self, taken=()):
        self.taken, self._last = set(taken), None

    def execute(self, sql, params=()):
        self._last = params[0] if params else None

    def fetchone(self):
        return (1,) if self._last in self.taken else None


def test_a_free_code_is_the_short_code_plus_general():
    assert readable_scope_code(_Cur(), "EKM") == "EKM-GENERAL"
    assert readable_scope_code(_Cur(), "ekm1") == "EKM1-GENERAL"                  # upper-cased


def test_a_taken_code_is_numbered():
    assert readable_scope_code(_Cur({"EKM-GENERAL"}), "EKM") == "EKM-GENERAL-2"
    assert readable_scope_code(_Cur({"EKM-GENERAL", "EKM-GENERAL-2"}), "EKM") == "EKM-GENERAL-3"


def test_no_short_code_or_nothing_free_falls_back_to_the_caller():
    assert readable_scope_code(_Cur(), None) is None and readable_scope_code(_Cur(), "") is None and readable_scope_code(_Cur(), "--") is None
    taken = {"EKM-GENERAL"} | {f"EKM-GENERAL-{n}" for n in range(2, 10)}
    assert readable_scope_code(_Cur(taken), "EKM") is None


def test_the_code_fits_the_column_and_the_creation_uses_the_helper():
    import inspect

    from api.services import finance_contribution as FC

    assert len("EKM1A-GENERAL-9") <= 50
    src = inspect.getsource(FC.ensure_org_scope)
    assert "readable_scope_code(cur, short_code)" in src and 'f"ORG{uuid4().hex[:8].upper()}"' in src       # the random form stays as the fallback


# ── the code of a NEW scope is made for the user (owner 2026-11-22): Sakha code + name ───────────────────────────────────────────────────────────
import re

import pytest

from api.services.finance_contribution import SCOPE_CODE_MAX, code_part, first_free_scope_code, scope_code_for


class _OrgCur(_Cur):
    """Also answers the organization lookup: (short_code, organization_code)."""

    def __init__(self, org=("EKM", "SKH7"), taken=()):
        super().__init__(taken)
        self.org, self._sql = org, ""

    def execute(self, sql, params=()):
        self._sql = sql
        super().execute(sql, params)

    def fetchone(self):
        return self.org if "FROM nss.organization" in self._sql else super().fetchone()


@pytest.mark.parametrize("text,expected", [("Annual festival", "ANNUAL-FESTIVAL"), ("  Rasa (2026) -- puja!  ", "RASA-2026-PUJA"), ("ekm", "EKM"), ("", ""), (None, ""), ("--", "")])
def test_a_name_becomes_a_code_part(text, expected):
    assert code_part(text) == expected


def test_the_code_is_the_sakha_code_then_the_name():
    assert scope_code_for(_OrgCur(), "org-1", "Annual Festival") == "EKM-ANNUAL-FESTIVAL"


def test_a_sakha_with_no_short_code_uses_its_organization_code():
    assert scope_code_for(_OrgCur(org=(None, "SKH7")), "org-1", "Annual Festival") == "SKH7-ANNUAL-FESTIVAL"
    assert scope_code_for(_OrgCur(org=("", "SKH7")), "org-1", "Rasa") == "SKH7-RASA"


def test_a_taken_code_is_numbered():
    assert scope_code_for(_OrgCur(taken={"EKM-RASA"}), "org-1", "Rasa") == "EKM-RASA-2"
    assert scope_code_for(_OrgCur(taken={"EKM-RASA", "EKM-RASA-2"}), "org-1", "Rasa") == "EKM-RASA-3"


def test_a_scope_with_no_organization_takes_the_name_alone():
    assert scope_code_for(_Cur(), None, "Special purpose drive") == "SPECIAL-PURPOSE-DRIVE"


def test_a_long_name_is_cut_to_fit_and_the_number_still_fits():
    code = scope_code_for(_OrgCur(), "org-1", "A very long festival name " * 6)
    assert len(code) <= SCOPE_CODE_MAX and re.fullmatch(r"EKM-[A-Z0-9-]+", code) and not code.endswith("-")
    base = code
    numbered = scope_code_for(_OrgCur(taken={base}), "org-1", "A very long festival name " * 6)
    assert len(numbered) <= SCOPE_CODE_MAX and numbered.endswith("-2") and numbered != base


def test_a_name_with_no_letters_or_digits_falls_back_to_the_random_form_only_without_a_prefix():
    assert scope_code_for(_OrgCur(), "org-1", "!!!") == "EKM"                       # the Sakha code alone is still a readable code
    assert re.fullmatch(r"SCOPE[0-9A-F]{8}", scope_code_for(_Cur(), None, "!!!"))


def test_nothing_free_in_the_numbered_range_returns_none_for_the_caller():
    assert first_free_scope_code(_Cur({"X"} | {f"X-{n}" for n in range(2, 5)}), "X", 4) is None


def test_scope_creation_and_the_general_scope_share_the_one_helper():
    import inspect

    from api.routers import finance as F
    from api.services import finance_contribution as FC

    assert "first_free_scope_code(cur, f\"{base}-GENERAL\", 9)" in inspect.getsource(FC.readable_scope_code)
    assert "contribution_service.scope_code_for(cur, body.organization_pk, name)" in inspect.getsource(F.create_scope)


def test_scope_and_fund_creation_can_be_active_at_once_and_the_code_is_optional():
    from api.schemas.finance import FundCreate, ScopeCreate

    scope = ScopeCreate(scope_name="Rasa", scope_type="EVENT")
    assert scope.scope_code is None and scope.activate is False                      # the API default is unchanged: DRAFT
    assert ScopeCreate(scope_name="Rasa", scope_type="EVENT", activate=True).activate is True
    assert FundCreate(fund_code="F", fund_name="n", fund_type="GENERAL", financial_scope_pk="00000000-0000-0000-0000-000000000001").activate is False
