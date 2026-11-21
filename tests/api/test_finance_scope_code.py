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
