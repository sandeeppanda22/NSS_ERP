"""
NSS ERP — shared helper for Membership Change Request tests.

Not a test file. A member may hold only ONE open change request at a time
(uq_mem_change_req_one_open + the router's 409 guard), but the API and
security modules each reuse a single module-scoped member across many
tests. ``retire_open_requests`` closes whatever that member left open so
each test starts clean, instead of every test minting a fresh member.

Also hosts ``create_sevi_less_account_headers``: login now refuses an
account whose person has no active Sangha Sevi, so tests that need such a
caller (to prove a 403/empty-result path) mint the JWT directly.
"""

from uuid import uuid4


def retire_open_requests(conn, sangha_sevi_pk) -> None:
    """Move every still-open request of *sangha_sevi_pk* to REJECTED_BY_SOURCE (satisfies chk_mem_change_req_review_consistency)."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE nss.membership_change_request
        SET status = 'REJECTED_BY_SOURCE',
            source_decided_by_sangha_sevi_pk = requested_by_sangha_sevi_pk,
            source_decided_at = NOW()
        WHERE sangha_sevi_pk = %s
          AND status IN ('PENDING_SOURCE_RELEASE', 'PENDING_DESTINATION_ACCEPT')
        """,
        (str(sangha_sevi_pk),),
    )


def create_sevi_less_account_headers(conn, id_prefix: str = "BARE", label: str = "Bare") -> dict:
    """
    Create a person + ACTIVE user_account with NO sangha_sevi row and return
    ``{"person_pk", "user_account_pk", "login_id", "headers"}``.

    POST /auth/login 401s for such an account ("No Sangha Sevi membership
    found"), so the bearer token is minted directly with the same
    ``create_access_token`` the login endpoint uses. ``get_current_user``
    still accepts it (RBAC context loads with a NULL sangha_sevi), which is
    exactly the caller shape the endpoint-level guards must handle.
    """
    from api.services.auth_service import create_access_token, hash_password

    suffix = uuid4().hex[:10].upper()
    person_id = f"{id_prefix}{suffix}"
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO nss.person (person_id, first_name, last_name, email) "
        "VALUES (%s, %s, %s, %s) RETURNING person_pk",
        (person_id, label, suffix, f"{id_prefix.lower()}.{suffix.lower()}@example.test"),
    )
    person_pk = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
        """,
        (str(person_pk), hash_password("Unused1x")),
    )
    user_account_pk = cur.fetchone()[0]
    token = create_access_token(user_account_pk, person_pk, person_id)
    return {
        "person_pk": str(person_pk),
        "user_account_pk": str(user_account_pk),
        "login_id": person_id,
        "headers": {"Authorization": f"Bearer {token}"},
    }
