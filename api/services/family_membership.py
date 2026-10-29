"""
Family membership departure — one shared path.

Every way a person stops being a current member of a family (Remove Member,
being moved by Add Member, founding a new family) must leave the family in a
consistent state:

  * the family_relationship and the person's family_link edges are closed
    (soft-delete — history is never deleted, FAM-027/028);
  * any current family_admin row is closed (an ex-member must not keep
    membership-changing authority);
  * if the leaver was the current head, the head record is closed and
    headship passes to a successor (FAM-051: exactly one head), preferring
    the leaver's spouse, else the longest-standing remaining member;
  * if nobody remains, the family is dissolved (ACTIVE -> INACTIVE soft
    delete per the family lifecycle doc), never left memberless-but-active.

Callers still own the family_transition_history row for moves (the
fn_family_move_requires_transition constraint trigger checks it at COMMIT).
"""

from __future__ import annotations

from api.helpers import log_audit, next_id


def _pick_successor(cur, family_group_pk: str, leaver_pk: str, spouse_pk: str | None):
    """Spouse if still a current member, else earliest-joined (then person_id)."""
    if spouse_pk is not None:
        cur.execute("""
            SELECT person_pk FROM nss.family_relationship
            WHERE  family_group_pk = %s AND person_pk = %s AND is_current = TRUE
        """, (family_group_pk, spouse_pk))
        row = cur.fetchone()
        if row:
            return str(row[0])
    cur.execute("""
        SELECT fr.person_pk
        FROM   nss.family_relationship fr
        JOIN   nss.person p ON p.person_pk = fr.person_pk
        WHERE  fr.family_group_pk = %s
          AND  fr.is_current = TRUE
          AND  fr.person_pk <> %s
        ORDER BY fr.effective_from, p.person_id
        LIMIT 1
    """, (family_group_pk, leaver_pk))
    row = cur.fetchone()
    return str(row[0]) if row else None


def close_family_membership(
    cur,
    *,
    family_group_pk: str,
    person_pk: str,
    on_date,
    remark: str,
    head_reason: str,
    actor_pk: str | None = None,
    actor_user_account_pk: str | None = None,
) -> dict:
    """
    Close *person_pk*'s current membership of *family_group_pk* (see module
    docstring for everything this covers). Returns
    ``{"relationship_pk", "was_head", "successor_pk", "dissolved"}``;
    ``relationship_pk`` is None when the person was not a current member.
    """
    fg, person = str(family_group_pk), str(person_pk)

    # Spouse is read BEFORE the links are closed (used for succession).
    cur.execute("""
        SELECT CASE WHEN person_a_pk = %s THEN person_b_pk ELSE person_a_pk END
        FROM   nss.family_link
        WHERE  family_group_pk = %s AND link_type = 'SPOUSE_OF'
          AND  is_current = TRUE AND (person_a_pk = %s OR person_b_pk = %s)
        ORDER BY effective_from, family_link_pk
        LIMIT 1
    """, (person, fg, person, person))
    row = cur.fetchone()
    spouse_pk = str(row[0]) if row else None

    cur.execute("""
        UPDATE nss.family_relationship
        SET    is_current = FALSE,
               effective_to = %s,
               remarks = COALESCE(remarks || ' | ', '') || %s,
               updated_at = CURRENT_TIMESTAMP
        WHERE  family_group_pk = %s AND person_pk = %s AND is_current = TRUE
        RETURNING family_relationship_pk
    """, (on_date, remark, fg, person))
    row = cur.fetchone()
    result = {"relationship_pk": str(row[0]) if row else None,
              "was_head": False, "successor_pk": None, "dissolved": False}
    if row is None:
        return result

    cur.execute("""
        UPDATE nss.family_link
        SET    is_current = FALSE, effective_to = %s, updated_at = CURRENT_TIMESTAMP
        WHERE  family_group_pk = %s AND (person_a_pk = %s OR person_b_pk = %s)
          AND  is_current = TRUE
    """, (on_date, fg, person, person))

    cur.execute("""
        UPDATE nss.family_admin
        SET    effective_to = %s,
               remarks = COALESCE(remarks || ' | ', '') || 'Closed: left family',
               updated_at = CURRENT_TIMESTAMP
        WHERE  family_group_pk = %s AND person_pk = %s AND effective_to IS NULL
    """, (on_date, fg, person))

    cur.execute("""
        UPDATE nss.family_head_history
        SET    effective_to = %s,
               reason = COALESCE(reason, '') || ' — left family',
               updated_at = CURRENT_TIMESTAMP
        WHERE  family_group_pk = %s AND person_pk = %s AND effective_to IS NULL
        RETURNING family_head_history_pk
    """, (on_date, fg, person))
    if cur.fetchone():
        result["was_head"] = True
        successor = _pick_successor(cur, fg, person, spouse_pk)
        if successor:
            cur.execute("""
                INSERT INTO nss.family_head_history
                    (family_group_pk, person_pk, effective_from, reason)
                VALUES (%s, %s, %s, %s)
            """, (fg, successor, on_date, head_reason))
            result["successor_pk"] = successor

    cur.execute("""
        SELECT 1 FROM nss.family_relationship
        WHERE  family_group_pk = %s AND is_current = TRUE LIMIT 1
    """, (fg,))
    if cur.fetchone() is None:
        cur.execute("""
            UPDATE nss.family_group
            SET    is_active = FALSE, deleted_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
            WHERE  family_group_pk = %s AND is_active = TRUE
        """, (fg,))
        log_audit(cur, action="DELETE", table_name="family_group", record_pk=fg,
                  actor_pk=actor_pk, actor_user_account_pk=actor_user_account_pk,
                  module="family", summary="Family dissolved: last member left")
        result["dissolved"] = True
    return result


def next_family_id(cur, *, actor_pk: str | None = None) -> str:
    """
    Atomically allocate the next family business ID (F1, F2, ...).

    Uses the ``FAMILY`` row of id_sequence_master (via helpers.next_id). The
    counter is first raised to the highest numeric family_id already issued:
    families created before this counter was used (MAX+1 era, demo seeds)
    would otherwise make the first allocations collide with uq_family_id.
    The UPDATE takes the counter row's lock, so concurrent creators serialize
    here and never receive the same number.
    """
    cur.execute("""
        UPDATE nss.id_sequence_master
        SET    current_value = GREATEST(current_value, (
                   SELECT COALESCE(MAX(CAST(SUBSTRING(family_id FROM 2) AS INTEGER)), 0)
                   FROM   nss.family_group
                   WHERE  family_id ~ '^F[0-9]+$'))
        WHERE  sequence_code = 'FAMILY'
    """)
    return next_id(cur, "FAMILY", actor_pk=actor_pk)
