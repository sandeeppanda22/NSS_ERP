"""
NSS ERP — shared builders for tests that call the public registration endpoints.

Not a test file. Anything that POSTs /api/v1/register or /api/v1/register/claim
needs the same mandatory address block and the same per-membership-type
credential rules, so they live here once instead of being re-typed in every
test module (standing "no duplicate code" rule). Test modules import what they
need by name, same convention as tests/attendance_support.py.

Registration rules this module encodes (api/routers/registration.py):
  - The address block is MANDATORY (country_pk, state_pk, district_pk,
    city_village_name, postal_code_value, address_line_1).
  - claimed_credential_document_number (Parichaya Patra number) is required
    for every membership type except Darshaka (PROBATIONARY).
  - claimed_local_sakha_number is required for every membership type except
    Darshaka at *registration* time (approval still insists on one).
"""

import random
from uuid import uuid4

import pytest


def registration_address(cur) -> dict:
    """
    A valid mandatory address block for POST /register and the person_address
    row it creates.

    Resolves an active state + APPROVED district pair from the seeded
    geography. The PIN is a random six-digit value: resolve_or_create_postal_code
    reuses a matching PIN or inserts a PENDING one, and everything rolls back
    with the calling module's SAVEPOINT either way. The village name is a fixed
    per-call unique string for the same find-or-create reason.

    Skips (never silently passes) when no usable geography is seeded.
    """
    cur.execute(
        """
        SELECT s.country_pk, s.state_pk, d.district_pk
        FROM nss.district d
        JOIN nss.state s ON s.state_pk = d.state_pk
        WHERE d.is_active = TRUE AND d.entry_status = 'APPROVED'
          AND s.is_active = TRUE
        ORDER BY s.created_at, d.created_at
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        pytest.skip("No active state/district seeded; cannot build a registration address.")
    country_pk, state_pk, district_pk = row
    return {
        "country_pk": str(country_pk),
        "state_pk": str(state_pk),
        "district_pk": str(district_pk),
        "city_village_name": f"RegTestVillage{uuid4().hex[:6]}",
        "postal_code_value": str(random.randint(100000, 999999)),
        "address_line_1": "1 Registration Test Road",
    }


def non_darshaka_credential_number() -> str:
    """A bare, globally-unique Parichaya Patra number for non-Darshaka claims."""
    return str(random.randint(100000, 999999))


def add_user_account(write_conn, person_pk, password, *, status="PENDING_APPROVAL", is_active=True) -> str:
    """
    Insert a user_account row for *person_pk* directly and return its pk.

    *is_active=False* produces the soft-deleted shape (uq_user_account_person is a
    plain UNIQUE, so such a row still occupies the person's slot). Shared by the
    registration and admin tests so neither re-types the INSERT.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    cur.execute(
        """
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, %s, FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
        """,
        (str(person_pk), hash_password(password), status),
    )
    ua_pk = str(cur.fetchone()[0])
    if not is_active:
        cur.execute(
            "UPDATE nss.user_account SET is_active = FALSE, deleted_at = NOW(), "
            "account_status = 'INACTIVE' WHERE user_account_pk = %s",
            (ua_pk,),
        )
    return ua_pk


def create_person_with_sangha_sevi(write_conn, organization_pk, id_prefix="TPS") -> tuple[str, str]:
    """
    Create a brand-new Person + active Regular Sangha Sevi in *organization_pk*
    and return ``(person_pk, sangha_sevi_id)``.

    Tests that need a login-capable caller with a KNOWN privilege level must
    use this rather than scavenging "the first existing member without an
    account": on a populated database that member may hold a governing-body
    seat, which auto-grants admin roles (§63) and silently makes a
    "scoped"/"unpermissioned" test user powerful or NSS-wide.
    """
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()
    cur.execute(
        "INSERT INTO nss.person (person_id, first_name, last_name, email) "
        "VALUES (%s, %s, %s, %s) RETURNING person_pk",
        (f"{id_prefix}{suffix}", "TestFresh", suffix, f"{id_prefix.lower()}.{suffix.lower()}@example.test"),
    )
    person_pk = str(cur.fetchone()[0])
    cur.execute(
        """
        SELECT
          (SELECT md.master_data_pk FROM nss.master_data md
             JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR'
              AND md.is_active = TRUE LIMIT 1),
          (SELECT md.master_data_pk FROM nss.master_data md
             JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE'
              AND md.is_active = TRUE LIMIT 1)
        """
    )
    mtype, mstatus = cur.fetchone()
    if mtype is None or mstatus is None:
        pytest.skip("MEMBERSHIP_TYPE/REGULAR or STATUS/ACTIVE master data missing.")
    sevi_id = f"TSS{id_prefix}{suffix}"
    cur.execute(
        """
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        """,
        (sevi_id, person_pk, str(mtype), str(mstatus), str(organization_pk)),
    )
    return person_pk, sevi_id
