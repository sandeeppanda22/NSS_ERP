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
