"""
FAM-036 family "effective Sakha" majority rule — the single shared rule.

A family's effective Sakha is the Sakha holding the most CURRENT members'
active affiliations. Ties are broken DETERMINISTICALLY by the lowest
``organization_pk`` (UUID order — identical in PostgreSQL and in Python, so
the SQL ROW_NUMBER path and the Python sakha-alignment path always agree).

Two entry points, one rule:

  * ``family_majority_cte(...)`` — the SQL CTE spliced by ``family.py``
    (_FAMILY_SELECT) and ``organization.py`` (stats). Supersedes the copy in
    ``api/helpers.py`` (which lacks the tie-break); that constant is now
    unused and can be deleted.
  * ``sakha_majority_sort_key(...)`` — the same ordering for code that
    counts in Python (``/sakha-alignment``).
"""

from __future__ import annotations


def family_majority_cte(restrict_sql: str = "") -> str:
    """
    Return the ``family_majority AS (...)`` CTE (no trailing comma — the
    caller owns the CTE-list punctuation).

    *restrict_sql* optionally narrows the families the CTE evaluates, e.g.
    ``"AND fr.family_group_pk = %s"``. Single-family reads pass it so the
    majority is not computed over every family in the database; the caller
    must then supply the matching bind parameter FIRST (the WITH clause
    precedes everything else in the statement).
    """
    return f"""
    family_majority AS (
        SELECT fr.family_group_pk,
               aff.organization_pk  AS sakha_pk,
               COUNT(*)             AS cnt,
               ROW_NUMBER() OVER (
                   PARTITION BY fr.family_group_pk
                   ORDER BY COUNT(*) DESC, aff.organization_pk ASC
               ) AS rn
        FROM   nss.family_relationship fr
        JOIN   nss.sangha_sevi ss
               ON ss.person_pk = fr.person_pk AND ss.is_active = TRUE
        JOIN   nss.membership_sakha_affiliation aff
               ON aff.sangha_sevi_pk = ss.sangha_sevi_pk
              AND aff.effective_to IS NULL
        WHERE  fr.is_current = TRUE
               {restrict_sql}
        GROUP BY fr.family_group_pk, aff.organization_pk
    )
"""


# Unrestricted form (all families) — what the organization stats roll up.
FAMILY_MAJORITY_CTE_SQL = family_majority_cte()


def sakha_majority_sort_key(member_count: int, organization_pk) -> tuple:
    """
    Sort key (ascending) ranking Sakhas exactly as the SQL CTE does: most
    members first, then lowest organization_pk. ``min(..., key=...)`` of this
    is the effective Sakha.
    """
    return (-member_count, str(organization_pk))
