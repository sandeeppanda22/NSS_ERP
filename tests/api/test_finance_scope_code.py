"""
DB-free: the CODE of a financial scope and of a fund is made automatically from the Sangha's code + the TYPE's short code (owner 2026-11-22/23):
a scope ``EKM-ORG`` / ``EKM-EVT``, a fund ``EKM-GEN`` / ``EKM-SINK``; numbered when taken. The type codes are MASTER DATA (categories SCOPE_TYPE_CODE and
FUND_TYPE_CODE, seeded by seed/12_finance/05_ and 06_), never a constant in the code. The earlier name-based scope code and the "-GENERAL" form are gone;
scopes made with them keep the codes they have.
"""
import inspect
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.schemas.finance import FUND_TYPES, SCOPE_TYPES
from api.services import finance_contribution as FC
from api.services.finance_contribution import (
    code_part, first_free_scope_code, fund_code_for, fund_type_code, fund_type_codes, org_code_prefix, scope_code_for, scope_type_code, scope_type_codes,
)

ROOT = Path(__file__).resolve().parents[2]
FUND_SEED = (ROOT / "database/seed/12_finance/05_fund_type_code_patch.sql").read_text(encoding="utf-8")
SCOPE_SEED = (ROOT / "database/seed/12_finance/06_scope_type_code_patch.sql").read_text(encoding="utf-8")


def _seeded(text: str) -> dict[str, str]:
    """{type -> short code} from a seed patch: ('GEN', 'General fund', 'GENERAL', 10) rows."""
    return {kind: code for code, kind in re.findall(r"\('([A-Z]{2,6})',\s+'(?:[^']|'')+',\s+'([A-Z_]+)',\s+\d+\)", text)}


FUND_CODES, SCOPE_CODES = _seeded(FUND_SEED), _seeded(SCOPE_SEED)


class _Cur:
    """Answers the organization lookup (short_code, organization_code), the two type-code master categories, and which codes are already taken."""

    def __init__(self, org=("EKM", "SKH7"), taken=(), fund_codes=None, scope_codes=None):
        self.org, self.taken = org, set(taken)
        self.codes = {"FUND_TYPE_CODE": FUND_CODES if fund_codes is None else fund_codes, "SCOPE_TYPE_CODE": SCOPE_CODES if scope_codes is None else scope_codes}
        self._sql, self._params = "", ()

    def execute(self, sql, params=()):
        self._sql, self._params = sql, params

    def fetchone(self):
        if "FROM nss.organization" in self._sql:
            return self.org
        return (1,) if tuple(self._params) in self.taken else None

    def fetchall(self):
        return list(self.codes[self._params[0]].items()) if "nss.master_category" in self._sql else []


# ── the codes are master data ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("seed,types,count", [(FUND_CODES, FUND_TYPES, 10), (SCOPE_CODES, SCOPE_TYPES, 4)], ids=["fund types", "scope types"])
def test_the_seed_gives_every_type_a_short_code_of_three_to_five_unique_letters(seed, types, count):
    assert set(seed) == set(types)                                                  # none missing, none stale: parity with the DDL's type list
    assert len(set(seed.values())) == len(seed) == count
    for kind, code in seed.items():
        assert re.fullmatch(r"[A-Z]{3,5}", code), (kind, code)


def test_the_codes_are_the_agreed_ones():
    assert FUND_CODES == {"GENERAL": "GEN", "SINKING_FUND": "SINK", "PUBLICATION": "PUB", "SPECIFIC_PURPOSE": "SPEC", "MEMBERSHIP_SUBSCRIPTION": "SUBS",
                          "PRANAMI": "PRAN", "DONATION": "DON", "GRANT": "GRNT", "PROPERTY_INCOME": "PROP", "MISCELLANEOUS": "MISC"}
    assert SCOPE_CODES == {"ORGANIZATION": "ORG", "EVENT": "EVT", "SPECIAL_PURPOSE": "SPL", "RESTRICTED_FUND": "RSTR"}


def test_the_types_match_the_database_checks():
    fund = (ROOT / "database/ddl/14_finance/03_fund_master.sql").read_text(encoding="utf-8")
    scope = (ROOT / "database/ddl/14_finance/02_financial_scope.sql").read_text(encoding="utf-8")
    assert tuple(re.findall(r"'([A-Z_]+)'", re.search(r"CHECK \(fund_type IN \((.*?)\)\)", fund, re.S).group(1))) == FUND_TYPES
    assert tuple(re.findall(r"'([A-Z_]+)'", re.search(r"chk_financial_scope_type\s+CHECK \(scope_type IN\s+\((.*?)\)\)", scope, re.S).group(1))) == SCOPE_TYPES


def test_the_codes_are_master_data_not_constants_and_the_seeds_are_safe_to_rerun():
    from api.schemas import finance as S

    assert not hasattr(S, "FUND_TYPE_CODES") and not hasattr(S, "SCOPE_TYPE_CODES")
    for seed, category in ((FUND_SEED, "FUND_TYPE_CODE"), (SCOPE_SEED, "SCOPE_TYPE_CODE")):
        assert f"'{category}'" in seed and "ON CONFLICT (master_category_pk, value_code) DO NOTHING" in seed and "ON CONFLICT (category_code) DO NOTHING" in seed
        assert not re.search(r"^\s*DELETE\s", seed, re.M | re.I)


def test_both_seeds_are_wired_into_the_three_builds_after_the_finance_tables():
    for rel in ("database/scripts/02_build.sh", "render_build.sh", "database/scripts/02_build.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert text.rindex("06_scope_type_code_patch.sql") > text.rindex("05_fund_type_code_patch.sql") > text.rindex("19_upi_payment_request_line.sql"), rel


def test_the_codes_are_read_from_master_data():
    assert fund_type_codes(_Cur()) == FUND_CODES and scope_type_codes(_Cur()) == SCOPE_CODES
    assert fund_type_code(_Cur(), "GRANT") == "GRNT" and scope_type_code(_Cur(), "EVENT") == "EVT"
    assert scope_type_codes(_Cur(scope_codes={"EVENT": "EV"})) == {"EVENT": "EV"}               # whatever the admin made them


def test_a_type_with_no_code_is_a_clear_422_not_a_crash():
    with pytest.raises(HTTPException) as e:
        scope_code_for(_Cur(scope_codes={}), "org-1", "EVENT")
    assert e.value.status_code == 422 and "Scope Type Code" in e.value.detail and "EVENT" in e.value.detail
    with pytest.raises(HTTPException) as e:
        fund_code_for(_Cur(fund_codes={}), "scope-1", "org-1", "GRANT")
    assert e.value.status_code == 422 and "Fund Type Code" in e.value.detail and "GRANT" in e.value.detail


# ── the scope code ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [("ekm", "EKM"), ("ek m (1)", "EK-M-1"), ("", ""), (None, ""), ("--", "")])
def test_a_code_part_is_upper_case_letters_and_digits(text, expected):
    assert code_part(text) == expected


def test_a_scope_code_is_the_sangha_code_then_the_scope_type_code():
    assert scope_code_for(_Cur(), "org-1", "ORGANIZATION") == "EKM-ORG"
    assert scope_code_for(_Cur(), "org-1", "EVENT") == "EKM-EVT"
    assert scope_code_for(_Cur(), "org-1", "SPECIAL_PURPOSE") == "EKM-SPL"
    assert scope_code_for(_Cur(), "org-1", "RESTRICTED_FUND") == "EKM-RSTR"


def test_the_name_no_longer_matters():
    assert "scope_name" not in inspect.signature(scope_code_for).parameters and "scope_type" in inspect.signature(scope_code_for).parameters


def test_a_sangha_with_no_short_code_uses_its_organization_code():
    assert scope_code_for(_Cur(org=(None, "SKH7")), "org-1", "EVENT") == "SKH7-EVT"
    assert scope_code_for(_Cur(org=("", "SKH7")), "org-1", "ORGANIZATION") == "SKH7-ORG"


def test_a_taken_scope_code_is_numbered_system_wide():
    assert scope_code_for(_Cur(taken={("EKM-EVT",)}), "org-1", "EVENT") == "EKM-EVT-2"
    assert scope_code_for(_Cur(taken={("EKM-EVT",), ("EKM-EVT-2",)}), "org-1", "EVENT") == "EKM-EVT-3"


def test_a_scope_with_no_organization_takes_the_type_code_alone():
    assert scope_code_for(_Cur(), None, "SPECIAL_PURPOSE") == "SPL"


def test_when_every_number_is_taken_the_random_form_is_the_last_resort():
    taken = {("EKM-EVT",)} | {(f"EKM-EVT-{n}",) for n in range(2, 100)}
    assert re.fullmatch(r"SCOPE[0-9A-F]{8}", scope_code_for(_Cur(taken=taken), "org-1", "EVENT"))
    assert first_free_scope_code(_Cur(taken={("X",), ("X-2",), ("X-3",), ("X-4",)}), "X", 4) is None


def test_the_earlier_scope_code_logic_is_removed():
    assert not hasattr(FC, "readable_scope_code")                                                  # the "-GENERAL" form
    src = inspect.getsource(FC)
    assert 'f"{base}-GENERAL"' not in src and 'f"ORG{uuid4()' not in src and "def scope_code_for(cur, organization_pk, scope_name" not in src


def test_every_way_a_scope_is_made_uses_the_one_function():
    from api.routers import finance as F
    from api.routers import finance_setup as FS

    assert "contribution_service.scope_code_for(cur, body.organization_pk, body.scope_type)" in inspect.getsource(F.create_scope)
    assert 'scope_code_for(cur, org_pk, "ORGANIZATION")' in inspect.getsource(FC.ensure_org_scope)           # a Sangha's automatic general scope
    event = inspect.getsource(FS.create_event)
    assert 'FC.scope_code_for(cur, body.organization_pk, "EVENT")' in event and 'f"EVT{suffix}"' not in event


def test_the_prefix_is_shared_by_scope_and_fund_codes():
    assert org_code_prefix(_Cur(), "org-1") == "EKM" and org_code_prefix(_Cur(), None) == ""
    assert fund_code_for(_Cur(), "scope-1", "org-1", "GENERAL") == "EKM-GEN"


def test_the_request_and_the_reference():
    from api.schemas.finance import FinanceReference, FundCreate, ScopeCreate
    from api.routers import finance as F

    scope = ScopeCreate(scope_name="Rasa", scope_type="EVENT")
    assert scope.scope_code is None and scope.activate is False                      # the API default is unchanged: DRAFT
    assert ScopeCreate(scope_name="Rasa", scope_type="EVENT", activate=True).activate is True
    assert FundCreate.model_fields["fund_code"].is_required() is False and FundCreate.model_fields["activate"].default is False
    assert {"fund_type_codes", "scope_type_codes"} <= set(FinanceReference.model_fields)
    ref = inspect.getsource(F.reference)
    assert "scope_type_codes = contribution_service.scope_type_codes(cur)" in ref and '"scope_type_codes": scope_type_codes' in ref


# ── a fund's code (unchanged rule, now sharing the helpers) ───────────────────────────────────────────────────────────────────────────────────────
def test_a_fund_code_is_the_sangha_code_then_the_type_code():
    assert fund_code_for(_Cur(), "scope-1", "org-1", "SINKING_FUND") == "EKM-SINK"
    assert fund_code_for(_Cur(org=(None, "SKH7")), "scope-1", "org-1", "PRANAMI") == "SKH7-PRAN"
    assert fund_code_for(_Cur(), "scope-1", None, "GRANT") == "GRNT"


def test_a_second_fund_of_the_same_type_in_the_scope_is_numbered_per_scope():
    assert fund_code_for(_Cur(taken={("scope-1", "EKM-GEN")}), "scope-1", "org-1", "GENERAL") == "EKM-GEN-2"
    assert fund_code_for(_Cur(taken={("scope-1", "EKM-GEN")}), "scope-2", "org-1", "GENERAL") == "EKM-GEN"       # unique per scope, not system-wide


def test_an_admin_edited_fund_code_is_what_the_next_fund_gets():
    assert fund_code_for(_Cur(fund_codes={**FUND_CODES, "GENERAL": "GENL"}), "scope-1", "org-1", "GENERAL") == "EKM-GENL"


def test_the_fund_router_still_uses_its_helper_and_a_given_code_wins():
    from api.routers import finance as F

    src = inspect.getsource(F.create_fund)
    assert "contribution_service.fund_code_for(cur, body.financial_scope_pk, body.organization_pk or scope[\"organization_pk\"], body.fund_type)" in src
    assert "Fund code {code} already exists in this scope." in src
