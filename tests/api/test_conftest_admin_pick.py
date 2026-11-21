"""
DB-free guard for the shared admin-view login (tests/conftest.py::admin_view_token).

A SQL error in that one session-scoped query aborts the shared transaction and turns EVERY later test into
"InFailedSqlTransaction: current transaction is aborted" (2026-11-21: a JOIN placed after the WHERE did exactly that). The query text is checked
for clause order here, and was also run against a scratch PostgreSQL 18 with a scoped and a global admin (the global admin must be picked).
"""
import re
from pathlib import Path

CONFTEST = (Path(__file__).resolve().parents[1] / "conftest.py").read_text(encoding="utf-8")


def _query() -> str:
    start = CONFTEST.index("def admin_view_token")
    raw = re.search(r'cur\.execute\(\s*"""(.*?)"""', CONFTEST[start:], re.S).group(1)
    return "\n".join(re.sub(r"--.*", "", line) for line in raw.splitlines())


def test_the_clauses_are_in_sql_order():
    q = _query()
    order = [q.index(k) for k in ("SELECT", "FROM nss.user_account", "JOIN nss.role_master", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT 1")]
    assert order == sorted(order), "every JOIN must come before WHERE, then GROUP BY, HAVING, ORDER BY, LIMIT"
    assert q.count("WHERE") == 1 and q.count("GROUP BY") == 1


def test_it_prefers_the_global_administrator_deterministically():
    q = _query()
    assert "BOOL_OR(rm.role_code = 'NSS_ERP_ADMIN') DESC" in q
    assert re.search(r"ORDER BY .*ua\.user_account_pk\s+LIMIT 1", q, re.S), "a final tie-break column keeps the choice the same on every run"
