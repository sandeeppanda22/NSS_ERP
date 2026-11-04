"""
Depth cap + cycle guard on every recursive CTE in api/ (owner decision 2026-11-04).

One constant (api/helpers.py::MAX_RECURSION_DEPTH = 20) and one set of SQL
fragments (recursive_anchor_cols / recursive_step_cols / recursive_guard /
org_subtree_cte_sql) drive every ``WITH RECURSIVE``. Two groups:

  * Static guards (no DB): every ``WITH RECURSIVE`` literal under api/ carries
    the shared guard, and no per-site depth literal is hard-coded.
  * Behaviour tests (real DB like the rest of tests/api; temp tables, rolled
    back with the module SAVEPOINT) - written but NOT yet run against a
    database. The cycle is synthesised in a temp table because the
    organization triggers may refuse to build one in nss.organization.
"""

import re
from pathlib import Path

import pytest

from api.helpers import (
    HIERARCHY_MAX_DEPTH,
    MAX_RECURSION_DEPTH,
    org_subtree_cte_sql,
    recursive_anchor_cols,
    recursive_guard,
    recursive_step_cols,
)

REPO = Path(__file__).resolve().parents[2]
GUARD_TOKENS = ("recursive_guard(", "MAX_RECURSION_DEPTH", "HIERARCHY_MAX_DEPTH")


def _recursive_literals():
    """(file, line, text from 'WITH RECURSIVE' to the closing triple quote)."""
    found = []
    for path in sorted((REPO / "api").rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"WITH RECURSIVE", src):
            end = src.find('"""', m.end())
            end = len(src) if end == -1 else end
            found.append((path.relative_to(REPO), src.count("\n", 0, m.start()) + 1, src[m.start():end]))
    return found


class TestStaticGuards:
    def test_recursive_ctes_were_found(self):
        files = {str(p) for p, _, _ in _recursive_literals()}
        assert {"api/helpers.py", "api/routers/organization.py", "api/routers/correspondence.py",
                "api/routers/governance.py"} <= files

    def test_every_with_recursive_carries_the_shared_guard(self):
        bad = [f"{p}:{line}" for p, line, text in _recursive_literals()
               if not any(tok in text for tok in GUARD_TOKENS)]
        assert bad == [], f"WITH RECURSIVE without the shared depth guard: {bad}"

    def test_no_hard_coded_depth_literal(self):
        bad = [f"{p}:{line}" for p, line, text in _recursive_literals()
               if re.search(r"depth\s*<\s*\d+", text)]
        assert bad == [], f"per-site depth magic number: {bad}"

    def test_no_unguarded_inline_subtree_copy_outside_the_helper(self):
        # The subtree walk exists once (org_subtree_cte_sql); other modules must call it.
        for rel in ("api/routers/membership.py", "api/services/rbac_service.py"):
            assert "WITH RECURSIVE" not in (REPO / rel).read_text(encoding="utf-8"), rel

    def test_constants(self):
        assert MAX_RECURSION_DEPTH == 20           # real org tree is ~5 levels
        assert HIERARCHY_MAX_DEPTH == 10           # documented /organization/hierarchy cap
        assert MAX_RECURSION_DEPTH > 5 * 2

    def test_fragments_render(self):
        assert recursive_anchor_cols("o.pk") == "0 AS tree_depth, ARRAY[o.pk] AS tree_path"
        assert recursive_step_cols("t", "o.pk") == "t.tree_depth + 1, t.tree_path || o.pk"
        g = recursive_guard("t", "o.pk")
        assert f"t.tree_depth < {MAX_RECURSION_DEPTH}" in g and "NOT o.pk = ANY(t.tree_path)" in g

    def test_org_subtree_helper_renders_cap_and_cycle_guard(self):
        sql = org_subtree_cte_sql("SELECT %s::uuid")
        assert sql.startswith("WITH RECURSIVE subtree AS")
        assert f"tree_depth < {MAX_RECURSION_DEPTH}" in sql and "ANY(s.tree_path)" in sql
        assert "SELECT %s::uuid" in sql and sql.count("%s") == 1

    def test_hierarchy_keeps_its_documented_cap(self):
        src = (REPO / "api/routers/organization.py").read_text(encoding="utf-8")
        assert "t.depth < {HIERARCHY_MAX_DEPTH}" in src


# ── Behaviour (real DB, temp tables only) ───────────────────────────────

def _walk_sql(table: str) -> str:
    return f"""
        WITH RECURSIVE w AS (
            SELECT n.id, {recursive_anchor_cols('n.id')}
            FROM {table} n WHERE n.id = 1
            UNION ALL
            SELECT n.id, {recursive_step_cols('w', 'n.id')}
            FROM {table} n JOIN w ON n.parent_id = w.id
            WHERE {recursive_guard('w', 'n.id')}
        )
        SELECT id, tree_depth FROM w ORDER BY tree_depth, id
    """


@pytest.mark.integration
class TestGuardBehaviour:
    def test_cycle_terminates_and_each_node_appears_once(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE cte_cycle (id int, parent_id int) ON COMMIT DROP")
            # 1 -> 2 -> 3 -> 1 (3's child is 1 again): a pure cycle.
            cur.execute("INSERT INTO cte_cycle VALUES (1, 3), (2, 1), (3, 2)")
            cur.execute(_walk_sql("cte_cycle"))
            assert cur.fetchall() == [(1, 0), (2, 1), (3, 2)]
            cur.execute("DROP TABLE cte_cycle")

    def test_deep_chain_is_capped_at_the_shared_constant(self, write_conn):
        n = MAX_RECURSION_DEPTH * 2
        with write_conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE cte_chain (id int, parent_id int)")
            cur.execute("INSERT INTO cte_chain SELECT g, g - 1 FROM generate_series(1, %s) g", (n,))
            cur.execute(_walk_sql("cte_chain"))
            rows = cur.fetchall()
            cur.execute("DROP TABLE cte_chain")
        assert len(rows) == MAX_RECURSION_DEPTH + 1
        assert rows[-1][1] == MAX_RECURSION_DEPTH

    def test_legitimate_depth_is_untouched(self, write_conn):
        with write_conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE cte_tree (id int, parent_id int)")
            cur.execute("INSERT INTO cte_tree VALUES (1, NULL), (2, 1), (3, 1), (4, 2), (5, 4), (6, 5)")
            cur.execute(_walk_sql("cte_tree"))
            rows = cur.fetchall()
            cur.execute("DROP TABLE cte_tree")
        assert [r[0] for r in rows] == [1, 2, 3, 4, 5, 6]
        assert max(r[1] for r in rows) == 4

    def test_org_subtree_matches_the_unguarded_walk_on_real_data(self, write_conn):
        """Results for legitimate trees are identical to the former unbounded CTE."""
        with write_conn.cursor() as cur:
            cur.execute("SELECT organization_pk FROM nss.organization WHERE parent_organization_pk IS NULL LIMIT 3")
            roots = [str(r[0]) for r in cur.fetchall()]
            if not roots:
                pytest.skip("no organizations")
            for root in roots:
                cur.execute(f"{org_subtree_cte_sql('SELECT %s::uuid')} SELECT organization_pk FROM subtree", (root,))
                guarded = {str(r[0]) for r in cur.fetchall()}
                cur.execute(
                    """
                    WITH RECURSIVE s AS (
                        SELECT organization_pk FROM nss.organization WHERE organization_pk = %s
                        UNION ALL
                        SELECT o.organization_pk FROM nss.organization o JOIN s ON o.parent_organization_pk = s.organization_pk
                    ) SELECT organization_pk FROM s
                    """,
                    (root,),
                )
                assert guarded == {str(r[0]) for r in cur.fetchall()}

    def test_scope_resolution_unchanged_for_the_admin_scope_helpers(self, write_conn):
        from api.services.rbac_service import org_subtree_pks

        with write_conn.cursor() as cur:
            cur.execute("SELECT organization_pk FROM nss.organization WHERE parent_organization_pk IS NULL LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("no organizations")
            subtree = org_subtree_pks(cur, row[0])
            assert str(row[0]) in subtree
            cur.execute("SELECT count(*) FROM nss.organization WHERE parent_organization_pk = %s", (str(row[0]),))
            assert len(subtree) >= 1 + cur.fetchone()[0]
