"""
DB-free guard: a member is a person. /organizations/{pk}/children-stats counted persons through family links only, so a member with no
family (one created through the admin Create Person / Sangha Sevi flow) made "members > persons" (3 vs 2 on the dev database). The person
count is now the persons in the Sakha's families UNION the persons of its active home members. The CTE was also run in a scratch PostgreSQL 18.
"""
from api.routers.organization import _CHILDREN_STATS_SQL


def _person_counts() -> str:
    start = _CHILDREN_STATS_SQL.index("person_counts AS (")
    return _CHILDREN_STATS_SQL[start:_CHILDREN_STATS_SQL.index("),\n", start)]


def test_person_count_includes_the_sakhas_own_active_members_without_double_counting():
    cte = _person_counts()
    assert "UNION" in cte and "UNION ALL" not in cte           # UNION de-duplicates a member who is also in a family
    assert "JOIN   nss.sangha_sevi ss" in cte and "ss.is_active = TRUE" in cte and "ss.person_pk" in cte
    assert "fr.is_current = TRUE" in cte                         # family links still count only the current ones
    assert "COUNT(DISTINCT person_pk)" in cte


def test_member_count_is_still_the_home_membership_of_the_sakha():
    assert "ss.organization_pk = sp.sakha_pk" in _CHILDREN_STATS_SQL
