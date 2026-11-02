"""
NSS ERP — governance seat lookups ("who holds seat X on body Y").

One shared home for the live-seat predicates that Correspondence (approval
chain addressing/decision), Organization re-parenting (approval chain) and
any later seat-based authority check need, so no router grows another copy.

"Seated" here means the position_code's substantive holder on the body
(body_member_assignment: active, open-ended, ASSIGNED/ACTIVE) OR a LIVE
acting delegate covering that (body, position) pair
(acting_position_assignment: ACTIVE, today within effective_from/to). Both
count as "holding the seat" — the same acting-cover rule Correspondence has
used since 2026-10-25 (see its approval-step docs).

Moved here verbatim from api/routers/correspondence.py (which now imports
them): find_body_master_pk, assignment_position_for_person,
assignment_person_for_position. New: live_seat_holder, person_holds_seat,
seat_body_pks_held.
"""

# Substantive seat predicate (alias `a` = body_member_assignment).
_SUBSTANTIVE_SEAT_SQL = (
    "a.is_active = TRUE AND a.effective_to IS NULL "
    "AND a.assignment_status IN ('ASSIGNED', 'ACTIVE')"
)

# Live acting-cover predicate (alias `apa` = acting_position_assignment).
_ACTING_SEAT_SQL = (
    "apa.is_active = TRUE AND apa.acting_status = 'ACTIVE' "
    "AND apa.effective_from <= CURRENT_DATE "
    "AND (apa.effective_to IS NULL OR apa.effective_to >= CURRENT_DATE)"
)


def find_body_master_pk(cur, body_type_code: str, organization_pk: str | None) -> str | None:
    """The active body_master row of the given type, NSS-wide (organization_pk
    is None) or org-scoped. Mirrors the WHERE-shape governance.py already uses
    for singleton vs. org-scoped bodies (e.g. public_national_bodies)."""
    if organization_pk is None:
        cur.execute(
            """
            SELECT bm.body_master_pk
            FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = %s AND bm.organization_pk IS NULL AND bm.is_active = TRUE
            LIMIT 1
            """,
            (body_type_code,),
        )
    else:
        cur.execute(
            """
            SELECT bm.body_master_pk
            FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = %s AND bm.organization_pk = %s AND bm.is_active = TRUE
            LIMIT 1
            """,
            (body_type_code, str(organization_pk)),
        )
    row = cur.fetchone()
    return str(row[0]) if row else None


def assignment_position_for_person(cur, body_master_pk: str, person_pk) -> str | None:
    """The position_master_pk of person_pk's current, active, non-MEMBER
    office-bearer seat on body_master_pk — either the substantive seat
    itself, OR a LIVE acting delegate currently covering that seat (owner
    request, 2026-10-25: selecting the delegate in the "Send Application"
    office-bearer dropdown must actually address the application to the
    delegate, not just display their name next to the absent holder — see
    NSS.officeBearerDropdownOptions in nss-config.js, which now submits
    the delegate's OWN person_pk as the option value). Returns the
    POSITION's pk either way (e.g. PRESIDENT), not a different pk per
    path — the position being addressed doesn't change, only who is
    currently standing in it. None if person_pk holds neither."""
    cur.execute(
        f"""
        SELECT a.position_master_pk
        FROM nss.body_member_assignment a
        JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        WHERE a.body_master_pk = %s AND a.person_pk = %s
          AND {_SUBSTANTIVE_SEAT_SQL}
          AND pm.position_code != 'MEMBER'
        LIMIT 1
        """,
        (str(body_master_pk), str(person_pk)),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    cur.execute(
        f"""
        SELECT apa.position_master_pk
        FROM nss.acting_position_assignment apa
        JOIN nss.position_master pm ON pm.position_master_pk = apa.position_master_pk
        WHERE apa.body_master_pk = %s AND apa.person_pk = %s
          AND {_ACTING_SEAT_SQL}
          AND pm.position_code != 'MEMBER'
        LIMIT 1
        """,
        (str(body_master_pk), str(person_pk)),
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def assignment_person_for_position(cur, body_master_pk: str, position_code: str):
    """(person_pk, position_master_pk) of whoever SUBSTANTIVELY holds
    position_code on body_master_pk, or None. Used to resolve the Sakha
    President to route a KENDRA_VIA_SAKHA_PRESIDENT application through.
    Acting cover is deliberately not applied here (Correspondence addresses
    the substantive holder; the picker submits a delegate explicitly) — use
    live_seat_holder() when the covering delegate is who should act."""
    cur.execute(
        f"""
        SELECT a.person_pk, a.position_master_pk
        FROM nss.body_member_assignment a
        JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        WHERE a.body_master_pk = %s AND pm.position_code = %s
          AND {_SUBSTANTIVE_SEAT_SQL}
        LIMIT 1
        """,
        (str(body_master_pk), position_code),
    )
    row = cur.fetchone()
    return (str(row[0]), str(row[1])) if row else None


def live_seat_holder(cur, body_master_pk: str, position_code: str):
    """(person_pk, position_master_pk, is_acting) of whoever CURRENTLY acts
    in position_code on body_master_pk, or None if the seat is unfilled.
    A live acting delegate covering the seat takes precedence over the
    substantive holder (they are the one standing in it today)."""
    cur.execute(
        f"""
        SELECT apa.person_pk, apa.position_master_pk
        FROM nss.acting_position_assignment apa
        JOIN nss.position_master pm ON pm.position_master_pk = apa.position_master_pk
        WHERE apa.body_master_pk = %s AND pm.position_code = %s
          AND {_ACTING_SEAT_SQL}
        ORDER BY apa.effective_from DESC
        LIMIT 1
        """,
        (str(body_master_pk), position_code),
    )
    row = cur.fetchone()
    if row:
        return (str(row[0]), str(row[1]), True)
    sub = assignment_person_for_position(cur, body_master_pk, position_code)
    return (sub[0], sub[1], False) if sub else None


def person_holds_seat(cur, body_master_pk: str, person_pk, position_code: str) -> bool:
    """True if person_pk is the substantive holder of, or a live acting
    delegate for, position_code on body_master_pk."""
    if person_pk is None or body_master_pk is None:
        return False
    return str(body_master_pk) in seat_body_pks_held(cur, person_pk, position_code)


def seat_body_pks_held(cur, person_pk, position_code: str) -> set[str]:
    """Every body_master_pk on which person_pk currently holds position_code
    (substantive or live acting). One query, for list filters that need the
    caller's seats rather than a per-row check."""
    if person_pk is None:
        return set()
    cur.execute(
        f"""
        SELECT a.body_master_pk
        FROM nss.body_member_assignment a
        JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        WHERE a.person_pk = %s AND pm.position_code = %s AND {_SUBSTANTIVE_SEAT_SQL}
        UNION
        SELECT apa.body_master_pk
        FROM nss.acting_position_assignment apa
        JOIN nss.position_master pm ON pm.position_master_pk = apa.position_master_pk
        WHERE apa.person_pk = %s AND pm.position_code = %s AND {_ACTING_SEAT_SQL}
        """,
        (str(person_pk), position_code, str(person_pk), position_code),
    )
    return {str(r[0]) for r in cur.fetchall()}
