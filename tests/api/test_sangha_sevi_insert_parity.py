"""
Single creator of nss.sangha_sevi rows (standing no-duplicate rule).

Every runtime path that enrols a Sangha Sevi (admin create_user,
admin create_sangha_sevi, claim approval) goes through
api/helpers.py::create_sangha_sevi_with_home_affiliation(), which owns the
SS-ID allocation, the INSERT, the home affiliation and the audit rows.

Static guard (no DB, no network): no Python module under api/ other than
api/helpers.py may contain `INSERT INTO nss.sangha_sevi`. Seed SQL
(admin bootstrap, gitignored demo seed) and tests are outside api/ and are
deliberately not covered: they run before/outside the application.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API = REPO / "api"

# `\b` after the table name keeps sangha_sevi_* tables from matching.
_INSERT = re.compile(r"insert\s+into\s+(?:nss\.)?sangha_sevi(?![A-Za-z0-9_])", re.IGNORECASE)

ALLOWED = {"api/helpers.py"}


def _hits() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in API.rglob("*.py"):
        n = len(_INSERT.findall(path.read_text(encoding="utf-8")))
        if n:
            out[path.relative_to(REPO).as_posix()] = n
    return out


def test_only_the_shared_helper_inserts_sangha_sevi():
    stray = {p: n for p, n in _hits().items() if p not in ALLOWED}
    assert not stray, (
        "INSERT INTO nss.sangha_sevi found outside api/helpers.py "
        f"(use create_sangha_sevi_with_home_affiliation): {stray}"
    )


def test_helper_has_exactly_one_insert():
    assert _hits().get("api/helpers.py") == 1


def test_routers_call_the_shared_creator():
    for rel in ("api/routers/admin.py", "api/routers/claim_approval.py"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "create_sangha_sevi_with_home_affiliation(" in text, rel
