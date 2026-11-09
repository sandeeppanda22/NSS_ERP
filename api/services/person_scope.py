"""Non-raising ADMIN-BR-076 person-scope probe shared by person.py and family.py."""

from __future__ import annotations

from fastapi import HTTPException

from api.services.rbac_service import UserContext, require_person_in_scope


def person_in_admin_scope(conn, person_pk, user: UserContext) -> bool:
    """
    True when a permission-holding admin may reach *person_pk* under
    ADMIN-BR-076: the person's active Sangha Sevi organization lies inside the
    admin's scope subtree (the rule ``GET /person/persons`` already applies to
    its list). NSS_ERP_ADMIN / NSS-WIDE are unrestricted.

    An unknown/inactive person counts as in scope so the calling endpoint can
    report its own 404 (existence before authorization). Callers keep their
    ownership fallbacks (self / relative) for when this returns False.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.person WHERE person_pk = %s AND is_active = TRUE",
            (str(person_pk),),
        )
        if cur.fetchone() is None:
            return True
        try:
            require_person_in_scope(cur, user, str(person_pk), "view persons")
        except HTTPException:
            return False
    return True


def can_view_aadhaar_last4(conn, person_pk, user: UserContext) -> bool:
    """
    GDR-011: may *user* see ``aadhaar_last4`` (and the on-file flag) of
    *person_pk*? Only the person themself, or a PERSON_VIEW_SENSITIVE holder
    whose admin scope covers the person. The permission alone never confers
    global reach — NSS_ERP_ADMIN is global only through its scope
    (ADMIN-BR-077). Family/relative access does NOT qualify.
    """
    if str(person_pk) == str(user.person_pk):
        return True
    return user.has_permission("PERSON_VIEW_SENSITIVE") and person_in_admin_scope(conn, person_pk, user)


def gate_aadhaar_fields(conn, person_pk, user: UserContext, model) -> None:
    """
    Apply the GDR-011 visibility rule to a response *model* in place: when
    the caller may not see Aadhaar data, ``aadhaar_last4`` and
    ``aadhaar_full_on_file`` become None. The ONE helper every response that
    carries those two fields must pass through (a source-sweep test in
    tests/security enforces it).
    """
    if not can_view_aadhaar_last4(conn, person_pk, user):
        model.aadhaar_last4 = None
        model.aadhaar_full_on_file = None
