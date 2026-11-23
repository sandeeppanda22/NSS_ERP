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


# ── a fund's code is made for the user (owner 2026-11-22): Sangha code + fund type code, the type codes being MASTER DATA ──────────────────────────────
from pathlib import Path

from api.schemas.finance import FUND_TYPES
from api.services.finance_contribution import fund_code_for, fund_type_code, fund_type_codes, org_code_prefix

_SEED = (Path(__file__).resolve().parents[2] / "database/seed/12_finance/05_fund_type_code_patch.sql").read_text(encoding="utf-8")
SEEDED = {fund_type: code for code, _name, fund_type in re.findall(r"\('([A-Z]{2,6})',\s+'([^']+)',\s+'([A-Z_]+)',\s+\d+\)", _SEED)}


class _FundCur:
    """Answers the organization lookup (short_code, organization_code), the FUND_TYPE_CODE master data, and which (scope, fund_code) pairs are taken."""

    def __init__(self, org=("EKM", "SKH7"), taken=(), codes=None):
        self.org, self.taken, self.codes = org, set(taken), (SEEDED if codes is None else codes)
        self._sql, self._params = "", ()

    def execute(self, sql, params=()):
        self._sql, self._params = sql, params

    def fetchone(self):
        if "FROM nss.organization" in self._sql:
            return self.org
        return (1,) if tuple(self._params) in self.taken else None

    def fetchall(self):
        return [(fund_type, code) for fund_type, code in self.codes.items()] if "nss.master_category" in self._sql else []


def test_the_seed_gives_every_fund_type_a_short_code_of_three_to_five_unique_letters():
    assert set(SEEDED) == set(FUND_TYPES)                                              # none missing, none stale: parity with the fund types
    codes = list(SEEDED.values())
    assert len(codes) == len(set(codes)) == 10
    for fund_type, code in SEEDED.items():
        assert re.fullmatch(r"[A-Z]{3,5}", code), (fund_type, code)


def test_the_codes_are_the_agreed_ones():
    assert SEEDED == {"GENERAL": "GEN", "SINKING_FUND": "SINK", "PUBLICATION": "PUB", "SPECIFIC_PURPOSE": "SPEC", "MEMBERSHIP_SUBSCRIPTION": "SUBS",
                      "PRANAMI": "PRAN", "DONATION": "DON", "GRANT": "GRNT", "PROPERTY_INCOME": "PROP", "MISCELLANEOUS": "MISC"}


def test_the_codes_are_master_data_not_a_constant_in_the_code():
    from api.schemas import finance as S

    assert not hasattr(S, "FUND_TYPE_CODES")                                           # one definition: the seed (and what an admin edits in Reference data)
    assert "INSERT INTO nss.master_category" in _SEED and "'FUND_TYPE_CODE'" in _SEED and "ON CONFLICT (master_category_pk, value_code) DO NOTHING" in _SEED
    assert "ON CONFLICT (category_code) DO NOTHING" in _SEED and not re.search(r"^\s*DELETE\s", _SEED, re.M | re.I)


def test_the_seed_is_wired_into_the_three_builds_after_the_finance_tables():
    root = Path(__file__).resolve().parents[2]
    for rel in ("database/scripts/02_build.sh", "render_build.sh", "database/scripts/02_build.ps1"):
        text = (root / rel).read_text(encoding="utf-8")
        assert text.rindex("05_fund_type_code_patch.sql") > text.rindex("03_finance_disbursement_purpose_patch.sql") > text.rindex("19_upi_payment_request_line.sql"), rel


def test_the_fund_types_match_the_database_check():
    ddl = (Path(__file__).resolve().parents[2] / "database/ddl/14_finance/03_fund_master.sql").read_text(encoding="utf-8")
    listed = re.search(r"CHECK \(fund_type IN \((.*?)\)\)", ddl, re.S).group(1)
    assert tuple(re.findall(r"'([A-Z_]+)'", listed)) == FUND_TYPES


def test_the_codes_are_read_from_master_data():
    assert fund_type_codes(_FundCur()) == SEEDED
    assert fund_type_code(_FundCur(), "GRANT") == "GRNT"
    assert fund_type_codes(_FundCur(codes={"GENERAL": "GN"})) == {"GENERAL": "GN"}                   # whatever the admin made them


def test_an_admin_edited_code_is_what_the_next_fund_gets():
    assert fund_code_for(_FundCur(codes={**SEEDED, "GENERAL": "GENL"}), "scope-1", "org-1", "GENERAL") == "EKM-GENL"


def test_a_fund_type_with_no_code_is_a_clear_422_not_a_crash():
    import pytest
    from fastapi import HTTPException

    cur = _FundCur(codes={k: v for k, v in SEEDED.items() if k != "GRANT"})
    with pytest.raises(HTTPException) as e:
        fund_code_for(cur, "scope-1", "org-1", "GRANT")
    assert e.value.status_code == 422 and "Fund Type Code" in e.value.detail and "GRANT" in e.value.detail


def test_a_fund_code_is_the_sangha_code_then_the_type_code():
    assert fund_code_for(_FundCur(), "scope-1", "org-1", "GENERAL") == "EKM-GEN"
    assert fund_code_for(_FundCur(), "scope-1", "org-1", "SINKING_FUND") == "EKM-SINK"
    assert fund_code_for(_FundCur(), "scope-1", "org-1", "MEMBERSHIP_SUBSCRIPTION") == "EKM-SUBS"


def test_a_sangha_with_no_short_code_uses_its_organization_code():
    assert fund_code_for(_FundCur(org=(None, "SKH7")), "scope-1", "org-1", "PRANAMI") == "SKH7-PRAN"


def test_a_second_fund_of_the_same_type_in_the_scope_is_numbered_but_another_scope_is_not_affected():
    assert fund_code_for(_FundCur(taken={("scope-1", "EKM-GEN")}), "scope-1", "org-1", "GENERAL") == "EKM-GEN-2"
    assert fund_code_for(_FundCur(taken={("scope-1", "EKM-GEN"), ("scope-1", "EKM-GEN-2")}), "scope-1", "org-1", "GENERAL") == "EKM-GEN-3"
    assert fund_code_for(_FundCur(taken={("scope-1", "EKM-GEN")}), "scope-2", "org-1", "GENERAL") == "EKM-GEN"            # unique per scope, not system-wide


def test_with_no_sangha_the_type_code_stands_alone():
    assert fund_code_for(_FundCur(), "scope-1", None, "GRANT") == "GRNT"


def test_the_prefix_is_shared_with_the_scope_code():
    assert org_code_prefix(_FundCur(), "org-1") == "EKM" and org_code_prefix(_FundCur(), None) == ""
    assert scope_code_for(_OrgCur(), "org-1", "Rasa") == "EKM-RASA"                       # still the same helper underneath


def test_the_router_uses_the_helper_and_a_given_code_still_wins():
    import inspect

    from api.routers import finance as F

    src = inspect.getsource(F.create_fund)
    assert "contribution_service.fund_code_for(cur, body.financial_scope_pk, body.organization_pk or scope[\"organization_pk\"], body.fund_type)" in src
    assert "Fund code {code} already exists in this scope." in src                           # an explicit duplicate is still 409
    ref = inspect.getsource(F.reference)
    assert "fund_type_codes = contribution_service.fund_type_codes(cur)" in ref and '"fund_type_codes": fund_type_codes' in ref


def test_the_fund_code_is_optional_in_the_request_and_the_reference_carries_the_codes():
    from api.schemas.finance import FinanceReference, FundCreate

    assert FundCreate.model_fields["fund_code"].is_required() is False
    assert "fund_type_codes" in FinanceReference.model_fields
