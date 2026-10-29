"""
NSS ERP — Tier 6 Correspondence Register API tests.

Integration tests for the Correspondence Register (SOL-ADMIN-009), covering
every endpoint of api/routers/correspondence.py:

  1. Create          — POST ""                         (always starts REGISTERED, §6.1)
  2. List            — GET  ""                          (filters + scope)
  3. Get             — GET  /{pk}                        (404 / scope 403)
  4. Transition      — POST /{pk}/transition             (§6.2 table + §6.3 reopen)
  5. Responsible     — POST /{pk}/responsible-party       (§5.4, any state)
  6. Documents       — POST/GET /{pk}/documents           (§8)
  7. Finance refs    — POST/GET /{pk}/finance-references   (§9, no FK yet)
  8. RBAC            — anonymous rejected

Runs against local PostgreSQL. The database must be bootstrapped with
DDL + seed before running (database/ddl/09_correspondence/*,
database/seed/00_bootstrap/03_role_permission.sql for
CORRESPONDENCE_VIEW/CORRESPONDENCE_MANAGE, and the CORRESPONDENCE_MEDIUM /
CORRESPONDENCE_STATUS / CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE master data).
"""

import re
from datetime import date

import pytest
from uuid import uuid4

from tests.change_request_support import create_sevi_less_account_headers

pytestmark = pytest.mark.integration

BASE = "/api/v1/correspondence"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "CorrAdminPass1"
SCOPED_PASSWORD = "CorrScopedPass1"
PERSON_PASSWORD = "CorrPersonPass1"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — admin builders (mirror tests/api/test_governance.py)
# ═══════════════════════════════════════════════════════════════════════

def _create_admin_with_scope(write_conn, *, role_code: str, scope_level: str, organization_pk):
    """
    Build a dedicated person + sangha_sevi + user_account + user_role +
    admin_scope row. Everything rolls back with the module SAVEPOINT.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_type_pk = cur.fetchone()[0]

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_status_pk = cur.fetchone()[0]

    if organization_pk is None:
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE LIMIT 1
        """)
        row = cur.fetchone()
        assert row, "No active SAKHA_SANGHA organization exists."
        home_organization_pk = row[0]
    else:
        home_organization_pk = organization_pk

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"CADM{suffix}", "CorrAdmin", suffix, f"cadm.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"CSSADM{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(home_organization_pk)))

    password = ADMIN_PASSWORD if scope_level == "NSS-WIDE" else SCOPED_PASSWORD
    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), hash_password(password)))
    user_account_pk = cur.fetchone()[0]

    cur.execute(
        "SELECT role_master_pk FROM nss.role_master WHERE role_code = %s AND is_active = TRUE",
        (role_code,),
    )
    role_row = cur.fetchone()
    assert role_row, f"{role_code} role not found in database."
    role_master_pk = role_row[0]

    cur.execute("""
        INSERT INTO nss.user_role (user_account_pk, role_master_pk)
        VALUES (%s, %s) RETURNING user_role_pk
    """, (str(user_account_pk), str(role_master_pk)))
    user_role_pk = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, %s, %s)
    """, (str(user_role_pk), scope_level,
          str(organization_pk) if (scope_level != "NSS-WIDE" and organization_pk) else None))

    return {
        "person_pk": person_pk,
        "user_account_pk": user_account_pk,
        "sangha_sevi_id": sangha_sevi_id,
        "password": password,
        "organization_pk": home_organization_pk,
    }


def _login_headers(client, login_id: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_person_with_login(
    write_conn, label: str, *, organization_pk: str, password: str = PERSON_PASSWORD,
    gender_value_code: str | None = None,
) -> dict:
    """
    A plain person + active sangha_sevi (at organization_pk) + logged-in
    user_account — no role/admin_scope at all. Used for PART 1/2/3 tests
    that need a real app-side "directed authority" (a recipient, a
    responsible party, a seated office-bearer) rather than an admin.
    Mirrors _create_admin_with_scope's person/sangha_sevi/user_account
    inserts, minus the role_master/admin_scope rows.

    gender_value_code (added 2026-10-25, for the gender-gated
    MAHILA_OFFICE_BEARER/KENDRA_MAHILA_VIA_SAKHA_PRESIDENT/SEVAK_OFFICE_
    BEARER addressing modes) is optional and defaults to None — every
    existing caller is unaffected and keeps getting a person with no
    gender set (gender_master_data_pk stays NULL), exactly as before.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_type_pk = cur.fetchone()[0]

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    membership_status_pk = cur.fetchone()[0]

    gender_master_data_pk = None
    if gender_value_code is not None:
        cur.execute("""
            SELECT md.master_data_pk FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = 'GENDER' AND md.value_code = %s AND md.is_active = TRUE
        """, (gender_value_code,))
        gender_row = cur.fetchone()
        assert gender_row, f"{gender_value_code} GENDER value not seeded."
        gender_master_data_pk = gender_row[0]

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email, gender_master_data_pk)
        VALUES (%s, %s, %s, %s, %s) RETURNING person_pk
    """, (f"CPSN{suffix}", label, suffix, f"cpsn.{suffix.lower()}@example.test",
          str(gender_master_data_pk) if gender_master_data_pk else None))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"CPSS{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        RETURNING sangha_sevi_pk
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(organization_pk)))
    sangha_sevi_pk = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
    """, (str(person_pk), hash_password(password)))

    return {
        "person_pk": str(person_pk),
        "sangha_sevi_pk": str(sangha_sevi_pk),
        "sangha_sevi_id": sangha_sevi_id,
        "password": password,
        "organization_pk": str(organization_pk),
    }


def _seat_office_bearer(write_conn, *, body_master_pk: str, position_code: str, person_pk: str, sangha_sevi_pk: str):
    """
    Direct SQL seat on body_member_assignment — mirrors
    tests/api/test_governance.py's parichalak_identity fixture note: there
    is no POST /assignments endpoint, body_member_assignment rows are only
    ever created via the election-result "apply" flow, so test setup for a
    specific seat goes straight to the table.
    """
    cur = write_conn.cursor()
    cur.execute(
        "SELECT position_master_pk FROM nss.position_master WHERE position_code = %s",
        (position_code,),
    )
    row = cur.fetchone()
    assert row, f"{position_code} position not seeded."
    position_master_pk = row[0]

    cur.execute(
        """
        INSERT INTO nss.body_member_assignment (
            body_master_pk, position_master_pk, person_pk, sangha_sevi_pk,
            effective_from, assignment_status
        ) VALUES (%s, %s, %s, %s, DATE '2020-01-01', 'ACTIVE')
        """,
        (str(body_master_pk), str(position_master_pk), str(person_pk), str(sangha_sevi_pk)),
    )


def _two_active_sakha_pks(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.organization_pk LIMIT 2
    """)
    rows = cur.fetchall()
    return [str(r[0]) for r in rows]


@pytest.fixture(scope="module")
def two_sakha_pks(write_conn):
    pks = _two_active_sakha_pks(write_conn)
    if len(pks) < 2:
        pytest.skip("Need at least two active SAKHA_SANGHA organizations.")
    return pks


@pytest.fixture(scope="module")
def register_org_pk(two_sakha_pks):
    """Primary register org — the scoped admin is scoped to this one."""
    return two_sakha_pks[0]


@pytest.fixture(scope="module")
def other_org_pk(two_sakha_pks):
    """A different org, OUTSIDE the scoped admin's scope."""
    return two_sakha_pks[1]


@pytest.fixture(scope="module")
def admin_user(write_conn):
    """NSS-WIDE NSS_ERP_ADMIN — holds CORRESPONDENCE_VIEW + MANAGE everywhere."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None,
    )


@pytest.fixture(scope="module")
def scoped_admin_user(write_conn, register_org_pk):
    """NSS_ERP_SAKHA_ADMIN scoped to register_org_pk."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=register_org_pk,
    )


@pytest.fixture(scope="module")
def admin_headers(client, admin_user):
    return _login_headers(client, admin_user["sangha_sevi_id"], admin_user["password"])


@pytest.fixture(scope="module")
def scoped_headers(client, scoped_admin_user):
    return _login_headers(client, scoped_admin_user["sangha_sevi_id"], scoped_admin_user["password"])


@pytest.fixture(scope="module")
def document_master_pk(write_conn):
    """A real document_master row — correspondence_document.document_master_pk is FK-constrained."""
    cur = write_conn.cursor()
    cur.execute(
        """
        INSERT INTO nss.document_master (document_type_code, document_name, storage_path)
        VALUES ('CORRESPONDENCE', %s, %s)
        RETURNING document_master_pk
        """,
        (f"Corr test doc {uuid4().hex[:8]}", f"/tmp/corr-{uuid4().hex[:8]}"),
    )
    return str(cur.fetchone()[0])


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — approval chain / directed-authority (PART 1/2/3 tests below)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def sakha_gb_body_pk(write_conn, register_org_pk):
    """
    The REAL seeded SAKHA_GOVERNING_BODY shell for register_org_pk — every
    active SAKHA_SANGHA gets one empty shell seeded (owner-confirmed
    2026-10-14, see database/seed/08_governance/03_body_master.sql), so no
    body creation call is needed (and avoids a second, ambiguous body of
    the same type on the same org — _find_body_master_pk's LIMIT 1 has no
    ORDER BY to break a tie)."""
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s AND bm.is_active = TRUE
        LIMIT 1
        """,
        (register_org_pk,),
    )
    row = cur.fetchone()
    assert row, "No seeded SAKHA_GOVERNING_BODY shell for register_org_pk."
    return str(row[0])


@pytest.fixture(scope="module")
def president_identity(write_conn, register_org_pk, sakha_gb_body_pk):
    """
    Seats a dedicated test person as PRESIDENT of register_org_pk's Sakha
    Governing Body. This dev DB can carry demo-seeded office-holders
    (RUN_DEMO_SEED), so any OTHER already-active PRESIDENT on the same
    body is deactivated first — _assignment_person_for_position()'s
    LIMIT 1 (no ORDER BY) would otherwise nondeterministically resolve to
    whichever of the two is returned first, making create_member_
    application()'s routing (and hence these tests) flaky. The deactivation
    is scoped to this module's SAVEPOINT, so it never persists.
    """
    cur = write_conn.cursor()
    cur.execute(
        """
        UPDATE nss.body_member_assignment a
        SET is_active = FALSE, effective_to = CURRENT_DATE - 1, deleted_at = NOW()
        FROM nss.position_master pm
        WHERE a.position_master_pk = pm.position_master_pk
          AND a.body_master_pk = %s AND pm.position_code = 'PRESIDENT'
          AND a.is_active = TRUE AND a.effective_to IS NULL
        """,
        (sakha_gb_body_pk,),
    )
    data = _create_person_with_login(write_conn, "SakhaPres", organization_pk=register_org_pk, password="CorrPresPass1")
    _seat_office_bearer(
        write_conn, body_master_pk=sakha_gb_body_pk, position_code="PRESIDENT",
        person_pk=data["person_pk"], sangha_sevi_pk=data["sangha_sevi_pk"],
    )
    return data



@pytest.fixture(scope="module")
def president_headers(client, president_identity):
    return _login_headers(client, president_identity["sangha_sevi_id"], president_identity["password"])


@pytest.fixture(scope="module")
def kendra_officer_identity(write_conn):
    """
    A real, currently-seated Kendra Governing Body office-bearer (any
    non-MEMBER position) — step 2's authority check
    (_require_seated_kendra_office_bearer) is keyed on the real KENDRA_GB,
    which is already at its 9-seat cap on this dev DB
    (fn_enforce_body_seat_limit, 12_governance_seat_limits.sql), so tests
    reuse an EXISTING seat holder rather than adding a 10th (which the DB
    trigger would reject). A known password is (re)provisioned on their
    user_account purely within this module's SAVEPOINT, so it never
    persists past the test run.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT a.person_pk, ss.sangha_sevi_id, ua.user_account_pk
        FROM nss.body_member_assignment a
        JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
        JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        JOIN nss.sangha_sevi ss ON ss.person_pk = a.person_pk AND ss.is_active = TRUE
        LEFT JOIN nss.user_account ua ON ua.person_pk = a.person_pk
        WHERE bm.body_code = 'KENDRA_GB' AND a.is_active = TRUE
          AND a.effective_to IS NULL AND a.assignment_status IN ('ASSIGNED', 'ACTIVE')
          AND pm.position_code != 'MEMBER'
        ORDER BY a.body_member_assignment_pk
        LIMIT 1
        """
    )
    row = cur.fetchone()
    assert row, "No active non-MEMBER office-bearer seated on the real KENDRA_GB."
    person_pk, sangha_sevi_id, user_account_pk = row

    password = "CorrKendraPass1"
    if user_account_pk is None:
        cur.execute(
            """
            INSERT INTO nss.user_account (
                person_pk, password_hash, account_status, force_password_change, password_expires_at
            ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
            """,
            (str(person_pk), hash_password(password)),
        )
    else:
        cur.execute(
            """
            UPDATE nss.user_account
            SET password_hash = %s, account_status = 'ACTIVE', password_expires_at = NOW() + INTERVAL '365 days'
            WHERE user_account_pk = %s
            """,
            (hash_password(password), str(user_account_pk)),
        )

    return {"person_pk": str(person_pk), "sangha_sevi_id": sangha_sevi_id, "password": password}


@pytest.fixture(scope="module")
def kendra_officer_headers(client, kendra_officer_identity):
    return _login_headers(client, kendra_officer_identity["sangha_sevi_id"], kendra_officer_identity["password"])


@pytest.fixture(scope="module")
def applicant_identity(write_conn, register_org_pk):
    """The member who files the "Send Application" — same home Sakha as
    president_identity (own-Sakha President routing requires it)."""
    return _create_person_with_login(write_conn, "Applicant", organization_pk=register_org_pk, password="CorrApplicantPass1")


@pytest.fixture(scope="module")
def applicant_headers(client, applicant_identity):
    return _login_headers(client, applicant_identity["sangha_sevi_id"], applicant_identity["password"])


@pytest.fixture(scope="module")
def plain_recipient_identity(write_conn, register_org_pk):
    """An ordinary member with no office-bearer seat at all — used to prove
    a PERSON-addressed correspondence's directed authority is the
    recipient themselves, not any admin-scope grant."""
    return _create_person_with_login(write_conn, "Recipient", organization_pk=register_org_pk, password="CorrRecipPass1")


@pytest.fixture(scope="module")
def plain_recipient_headers(client, plain_recipient_identity):
    return _login_headers(client, plain_recipient_identity["sangha_sevi_id"], plain_recipient_identity["password"])


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — Mahila Parichalana Mandali / Sevak Sangha office-bearers
# (owner-confirmed 2026-10-25, gender-gated MAHILA_OFFICE_BEARER /
# KENDRA_MAHILA_VIA_SAKHA_PRESIDENT / SEVAK_OFFICE_BEARER modes)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def mahila_pm_sakha_body_pk(write_conn, register_org_pk):
    """
    register_org_pk's own (Sakha-level) Mahila Parichalana Mandali — unlike
    sakha_gb_body_pk this is NOT pre-seeded (database/seed/08_governance/
    03_body_master.sql §header: "admins only ever manually create the
    per-Sakha Mahila Parichalana Mandali ... intentionally have NO seed
    file"), so this fixture creates the body_master row directly, mirroring
    that seed file's own INSERT shape (there is a real POST /bodies
    endpoint, but direct SQL matches this file's existing fixture
    convention for governance rows with no POST-based setup, e.g.
    sakha_gb_body_pk/_seat_office_bearer).
    """
    cur = write_conn.cursor()
    cur.execute(
        "SELECT body_type_master_pk FROM nss.body_type_master WHERE body_type_code = 'MAHILA_PARICHALANA_MANDALI'",
    )
    body_type_pk = cur.fetchone()[0]
    code = f"TEST_MAHILA_PM_{uuid4().hex[:8].upper()}"
    cur.execute(
        """
        INSERT INTO nss.body_master (body_type_master_pk, body_code, body_name, organization_pk, effective_from)
        VALUES (%s, %s, %s, %s, CURRENT_DATE)
        RETURNING body_master_pk
        """,
        (str(body_type_pk), code, "Test Sakha Mahila Parichalana Mandali", register_org_pk),
    )
    return str(cur.fetchone()[0])


@pytest.fixture(scope="module")
def sevak_sangha_body_pk(write_conn, register_org_pk):
    """register_org_pk's own Sevak Sangha Executive — also no seed file
    (same owner-confirmed "manually created" note as Mahila PM above)."""
    cur = write_conn.cursor()
    cur.execute(
        "SELECT body_type_master_pk FROM nss.body_type_master WHERE body_type_code = 'SEVAK_SANGHA_EXECUTIVE'",
    )
    body_type_pk = cur.fetchone()[0]
    code = f"TEST_SEVAK_SANGHA_{uuid4().hex[:8].upper()}"
    cur.execute(
        """
        INSERT INTO nss.body_master (body_type_master_pk, body_code, body_name, organization_pk, effective_from)
        VALUES (%s, %s, %s, %s, CURRENT_DATE)
        RETURNING body_master_pk
        """,
        (str(body_type_pk), code, "Test Sevak Sangha Executive", register_org_pk),
    )
    return str(cur.fetchone()[0])


@pytest.fixture(scope="module")
def mahila_office_bearer_identity(write_conn, register_org_pk, mahila_pm_sakha_body_pk):
    """A real, seated SECRETARY of register_org_pk's (freshly created) local
    Mahila Parichalana Mandali."""
    data = _create_person_with_login(
        write_conn, "MahilaSec", organization_pk=register_org_pk, password="CorrMahilaSecPass1",
        gender_value_code="FEMALE",
    )
    _seat_office_bearer(
        write_conn, body_master_pk=mahila_pm_sakha_body_pk, position_code="SECRETARY",
        person_pk=data["person_pk"], sangha_sevi_pk=data["sangha_sevi_pk"],
    )
    return data


@pytest.fixture(scope="module")
def mahila_office_bearer_headers(client, mahila_office_bearer_identity):
    return _login_headers(client, mahila_office_bearer_identity["sangha_sevi_id"], mahila_office_bearer_identity["password"])


@pytest.fixture(scope="module")
def sevak_office_bearer_identity(write_conn, register_org_pk, sevak_sangha_body_pk):
    """A real, seated SECRETARY of register_org_pk's (freshly created)
    local Sevak Sangha Executive."""
    data = _create_person_with_login(
        write_conn, "SevakSec", organization_pk=register_org_pk, password="CorrSevakSecPass1",
        gender_value_code="MALE",
    )
    _seat_office_bearer(
        write_conn, body_master_pk=sevak_sangha_body_pk, position_code="SECRETARY",
        person_pk=data["person_pk"], sangha_sevi_pk=data["sangha_sevi_pk"],
    )
    return data


@pytest.fixture(scope="module")
def sevak_office_bearer_headers(client, sevak_office_bearer_identity):
    return _login_headers(client, sevak_office_bearer_identity["sangha_sevi_id"], sevak_office_bearer_identity["password"])


@pytest.fixture(scope="module")
def kendra_mahila_officer_identity(write_conn):
    """
    A real, currently-seated office-bearer of the CENTRAL (Kendra-level,
    NSS-wide) Mahila Parichalana Mandali (body_code 'KENDRA_MAHILA_PM',
    database/seed/08_governance/03_body_master.sql) — this body is already
    at its 8-seat Kendra-level cap on this dev DB
    (fn_enforce_body_seat_limit's two-tier Mahila PM rule,
    12_governance_seat_limits.sql), so — exactly like kendra_officer_
    identity above for the real KENDRA_GB — this reuses an EXISTING seat
    holder rather than adding a 9th. A known password is (re)provisioned
    purely within this module's SAVEPOINT.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT a.person_pk, ss.sangha_sevi_id, ua.user_account_pk
        FROM nss.body_member_assignment a
        JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
        JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        JOIN nss.sangha_sevi ss ON ss.person_pk = a.person_pk AND ss.is_active = TRUE
        LEFT JOIN nss.user_account ua ON ua.person_pk = a.person_pk
        WHERE bm.body_code = 'KENDRA_MAHILA_PM' AND a.is_active = TRUE
          AND a.effective_to IS NULL AND a.assignment_status IN ('ASSIGNED', 'ACTIVE')
          AND pm.position_code != 'MEMBER'
        ORDER BY a.body_member_assignment_pk
        LIMIT 1
        """
    )
    row = cur.fetchone()
    assert row, "No active non-MEMBER office-bearer seated on the real KENDRA_MAHILA_PM."
    person_pk, sangha_sevi_id, user_account_pk = row

    password = "CorrKendraMahilaPass1"
    if user_account_pk is None:
        cur.execute(
            """
            INSERT INTO nss.user_account (
                person_pk, password_hash, account_status, force_password_change, password_expires_at
            ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
            """,
            (str(person_pk), hash_password(password)),
        )
    else:
        cur.execute(
            """
            UPDATE nss.user_account
            SET password_hash = %s, account_status = 'ACTIVE', password_expires_at = NOW() + INTERVAL '365 days'
            WHERE user_account_pk = %s
            """,
            (hash_password(password), str(user_account_pk)),
        )

    return {"person_pk": str(person_pk), "sangha_sevi_id": sangha_sevi_id, "password": password}


@pytest.fixture(scope="module")
def kendra_mahila_officer_headers(client, kendra_mahila_officer_identity):
    return _login_headers(client, kendra_mahila_officer_identity["sangha_sevi_id"], kendra_mahila_officer_identity["password"])


@pytest.fixture(scope="module")
def female_applicant_identity(write_conn, register_org_pk):
    """A FEMALE member in the same home Sakha as president_identity (own-
    Sakha President routing requires it for the 2-step Mahila mode)."""
    return _create_person_with_login(
        write_conn, "FemaleApplicant", organization_pk=register_org_pk, password="CorrFemaleApplicantPass1",
        gender_value_code="FEMALE",
    )


@pytest.fixture(scope="module")
def female_applicant_headers(client, female_applicant_identity):
    return _login_headers(client, female_applicant_identity["sangha_sevi_id"], female_applicant_identity["password"])


@pytest.fixture(scope="module")
def male_applicant_identity(write_conn, register_org_pk):
    """A MALE member in the same home Sakha as register_org_pk."""
    return _create_person_with_login(
        write_conn, "MaleApplicant", organization_pk=register_org_pk, password="CorrMaleApplicantPass1",
        gender_value_code="MALE",
    )


@pytest.fixture(scope="module")
def male_applicant_headers(client, male_applicant_identity):
    return _login_headers(client, male_applicant_identity["sangha_sevi_id"], male_applicant_identity["password"])


# ═══════════════════════════════════════════════════════════════════════
# Payload + create helper
# ═══════════════════════════════════════════════════════════════════════

def _payload(org_pk, *, direction="INWARD", subject="Test correspondence"):
    """
    Minimal valid CorrespondenceCreate — EXTERNAL sender + recipient so no
    person/organization FK is needed, non-future dates (§ validator).
    """
    return {
        "register_organization_pk": org_pk,
        "direction": direction,
        "correspondence_date": "2026-01-10",
        "received_or_sent_date": "2026-01-11",
        "subject": subject,
        "sender_type": "EXTERNAL",
        "sender_external_name": "External Sender",
        "recipient_type": "EXTERNAL",
        "recipient_external_name": "External Recipient",
        "medium": "POST",
    }


def _create(client, headers, org_pk, **kw) -> dict:
    r = client.post(BASE, json=_payload(org_pk, **kw), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════
# 1. Create
# ═══════════════════════════════════════════════════════════════════════

class TestCreate:
    def test_create_returns_201_starts_registered(self, client, admin_headers, register_org_pk):
        body = _create(client, admin_headers, register_org_pk)
        assert body["status_value_code"] == "REGISTERED"
        assert body["direction"] == "INWARD"
        assert body["reference_number"]  # server-minted, non-empty
        assert body["is_active"] is True

    def test_create_rejects_future_date(self, client, admin_headers, register_org_pk):
        body = _payload(register_org_pk)
        body["correspondence_date"] = "2099-01-01"
        r = client.post(BASE, json=body, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_create_rejects_bad_direction(self, client, admin_headers, register_org_pk):
        body = _payload(register_org_pk)
        body["direction"] = "SIDEWAYS"
        r = client.post(BASE, json=body, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_create_rejects_bad_party_consistency(self, client, admin_headers, register_org_pk):
        """EXTERNAL sender must give exactly one party identity — not external_name AND person_pk."""
        body = _payload(register_org_pk)
        body["sender_person_pk"] = FAKE_UUID  # now two identities on one party
        r = client.post(BASE, json=body, headers=admin_headers)
        assert r.status_code == 422, r.text


# ═══════════════════════════════════════════════════════════════════════
# 2. List
# ═══════════════════════════════════════════════════════════════════════

class TestList:
    def test_list_returns_items_key(self, client, admin_headers, register_org_pk):
        _create(client, admin_headers, register_org_pk)
        r = client.get(BASE, headers=admin_headers)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert "items" in payload and "total" in payload
        assert isinstance(payload["items"], list)

    def test_list_filter_by_org(self, client, admin_headers, register_org_pk):
        _create(client, admin_headers, register_org_pk)
        r = client.get(BASE, params={"register_organization_pk": register_org_pk}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert all(it["register_organization_pk"] == register_org_pk for it in r.json()["items"])

    def test_list_filter_by_direction(self, client, admin_headers, register_org_pk):
        _create(client, admin_headers, register_org_pk, direction="OUTWARD")
        r = client.get(BASE, params={"direction": "OUTWARD"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert all(it["direction"] == "OUTWARD" for it in r.json()["items"])

    def test_list_filter_by_status(self, client, admin_headers, register_org_pk):
        _create(client, admin_headers, register_org_pk)
        r = client.get(BASE, params={"status": "REGISTERED"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert all(it["status_value_code"] == "REGISTERED" for it in r.json()["items"])


# ═══════════════════════════════════════════════════════════════════════
# 3. Get
# ═══════════════════════════════════════════════════════════════════════

class TestGet:
    def test_get_returns_record(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.get(f"{BASE}/{pk}", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["correspondence_pk"] == pk

    def test_get_missing_returns_404(self, client, admin_headers):
        r = client.get(f"{BASE}/{FAKE_UUID}", headers=admin_headers)
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════
# 3b. History + reply-thread path tracker (owner-confirmed 2026-10-26:
#     "can we add history with path tracker for correspondance?"). events
#     reuses the EXISTING generic audit log (nss.system_event_log via
#     log_audit()) filtered to one record — no new write path, purely
#     additive/read-only. Same permission + scope gate as GET /{pk} itself.
# ═══════════════════════════════════════════════════════════════════════

class TestHistory:
    def test_auto_dispatch_is_logged_against_the_outward_row_too(
        self, client, admin_headers, register_org_pk, other_org_pk,
    ):
        outward = client.post(BASE, json=_org_payload(register_org_pk, other_org_pk), headers=admin_headers).json()
        assert outward["counterpart_correspondence_pk"], "precondition: auto-dispatch succeeded"
        events = client.get(f"{BASE}/{outward['correspondence_pk']}/history", headers=admin_headers).json()["events"]
        assert any("Auto-dispatched" in (e["summary"] or "") for e in events), [e["summary"] for e in events]
        inward_events = client.get(
            f"{BASE}/{outward['counterpart_correspondence_pk']}/history", headers=admin_headers).json()["events"]
        assert any("Auto-dispatched" in (e["summary"] or "") for e in inward_events)

    def test_a_soft_deleted_record_is_404_on_get_and_history(self, client, write_conn, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.correspondence SET is_active = FALSE, deleted_at = NOW() WHERE correspondence_pk = %s", (pk,))
        assert client.get(f"{BASE}/{pk}", headers=admin_headers).status_code == 404
        assert client.get(f"{BASE}/{pk}/history", headers=admin_headers).status_code == 404

    def test_history_includes_creation_and_auto_transition_events(
        self, client, admin_headers, register_org_pk,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        r = client.get(f"{BASE}/{pk}/history", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        summaries = [e["summary"] for e in data["events"]]
        assert any("Registered" in s for s in summaries if s), (
            f"No creation event found in {summaries!r}."
        )
        assert any("PENDING_ACTION" in s for s in summaries if s), (
            f"No auto-transition event found in {summaries!r}."
        )
        # Chronological order — creation must come before the later event.
        actions = [e["action"] for e in data["events"]]
        assert actions.index("CREATE") < len(actions) - 1 or len(actions) == 1
        assert data["thread_ancestors"] == []
        assert data["thread_descendants"] == []

    def test_history_thread_walks_both_directions(self, client, admin_headers, register_org_pk):
        original = _create(client, admin_headers, register_org_pk, direction="INWARD")
        reply = client.post(
            BASE,
            json=_payload(register_org_pk, direction="OUTWARD", subject="Re: Test correspondence")
            | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        ).json()

        r_reply_history = client.get(f"{BASE}/{reply['correspondence_pk']}/history", headers=admin_headers)
        assert r_reply_history.status_code == 200, r_reply_history.text
        reply_ancestors = r_reply_history.json()["thread_ancestors"]
        assert len(reply_ancestors) == 1
        assert reply_ancestors[0]["correspondence_pk"] == original["correspondence_pk"]
        assert reply_ancestors[0]["depth"] == 1

        r_original_history = client.get(f"{BASE}/{original['correspondence_pk']}/history", headers=admin_headers)
        assert r_original_history.status_code == 200, r_original_history.text
        original_descendants = r_original_history.json()["thread_descendants"]
        assert len(original_descendants) == 1
        assert original_descendants[0]["correspondence_pk"] == reply["correspondence_pk"]
        assert original_descendants[0]["depth"] == 1

    def test_history_missing_record_404(self, client, admin_headers):
        r = client.get(f"{BASE}/{FAKE_UUID}/history", headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_history_out_of_scope_rejected(self, client, admin_headers, scoped_headers, other_org_pk):
        """scoped_headers is scoped to register_org_pk only (see
        TestDispatch::test_out_of_scope_sender_rejected) — other_org_pk is
        outside its scope."""
        pk = _create(client, admin_headers, other_org_pk)["correspondence_pk"]
        r = client.get(f"{BASE}/{pk}/history", headers=scoped_headers)
        assert r.status_code == 403, r.text

    def test_history_anonymous_rejected(self, anon_client):
        r = anon_client.get(f"{BASE}/{FAKE_UUID}/history")
        assert r.status_code in (401, 403), r.text


# ═══════════════════════════════════════════════════════════════════════
# 4. Transition (§6.2 table + §6.3 reopen remarks)
# ═══════════════════════════════════════════════════════════════════════

class TestTransition:
    def _assign_org_responsible(self, client, headers, pk, org_pk):
        r = client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": org_pk},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        return r

    def test_registered_to_actioned_ok(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status_value_code"] == "ACTIONED"

    def test_same_status_rejected(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "REGISTERED"}, headers=admin_headers)
        assert r.status_code == 422, r.text
        assert "already" in r.json()["detail"].lower()

    def test_invalid_transition_rejected(self, client, admin_headers, register_org_pk):
        """PENDING_ACTION -> CLOSED is not in the §6.2 table."""
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        # Event-driven lifecycle (owner-confirmed 2026-10-26): assigning the
        # responsible party now auto-advances REGISTERED -> PENDING_ACTION
        # itself, so there is no longer a separate manual-transition step
        # to also exercise here — the record is already PENDING_ACTION the
        # moment _assign_org_responsible returns.
        self._assign_org_responsible(client, admin_headers, pk, register_org_pk)
        r2 = client.post(f"{BASE}/{pk}/transition", json={"new_status": "CLOSED"}, headers=admin_headers)
        assert r2.status_code == 422, r2.text
        assert "not a valid transition" in r2.json()["detail"].lower()

    def test_pending_action_requires_responsible_party(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"}, headers=admin_headers)
        assert r.status_code == 422, r.text
        assert "responsible" in r.json()["detail"].lower()

    def test_pending_action_transition_is_now_redundant_after_auto_advance(
        self, client, admin_headers, register_org_pk,
    ):
        """Event-driven lifecycle (owner-confirmed 2026-10-26): assigning a
        responsible party to a REGISTERED record now auto-advances it to
        PENDING_ACTION (TestEventDrivenLifecycle has the dedicated
        coverage). One direct consequence here: the manual /transition call
        this test used to rely on to REACH PENDING_ACTION is no longer
        reachable in that state at all — it 422s "already PENDING_ACTION",
        same as calling /transition with the record's current status
        always has (test_same_status_rejected). The manual endpoint itself
        is unchanged; there's just nothing left for it to do in this
        specific case."""
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        assign_response = self._assign_org_responsible(client, admin_headers, pk, register_org_pk)
        assert assign_response.json()["status_value_code"] == "PENDING_ACTION"

        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"}, headers=admin_headers)
        assert r.status_code == 422, r.text
        assert "already" in r.json()["detail"].lower()

    def test_reopen_requires_remarks(self, client, admin_headers, register_org_pk):
        """ACTIONED -> PENDING_ACTION (a reopen) needs non-empty remarks (§6.3)."""
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r_act = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert r_act.status_code == 200, r_act.text
        r_bad = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"}, headers=admin_headers)
        assert r_bad.status_code == 422, r_bad.text
        assert "remarks" in r_bad.json()["detail"].lower()
        r_ok = client.post(
            f"{BASE}/{pk}/transition",
            json={"new_status": "PENDING_ACTION", "remarks": "Reopened for review."},
            headers=admin_headers,
        )
        assert r_ok.status_code == 200, r_ok.text
        assert r_ok.json()["status_value_code"] == "PENDING_ACTION"

    def test_transition_missing_record_404(self, client, admin_headers):
        r = client.post(f"{BASE}/{FAKE_UUID}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════
# 5. Responsible party (§5.4)
# ═══════════════════════════════════════════════════════════════════════

class TestResponsibleParty:
    def test_assign_org_then_clear(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r1 = client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["responsible_organization_pk"] == register_org_pk
        # Event-driven lifecycle (owner-confirmed 2026-10-26, option 3):
        # assigning a responsible party to a REGISTERED record now
        # auto-advances it to PENDING_ACTION — see TestEventDrivenLifecycle
        # for the dedicated coverage of that amendment; this test's own
        # focus (assign-then-clear) just has to not assume the old
        # "never changes status" behavior any more.
        assert r1.json()["status_value_code"] == "PENDING_ACTION"
        # Clear it — §6.2's table has no PENDING_ACTION -> REGISTERED
        # transition at all (manual or automatic), so clearing the
        # responsible party does NOT revert the auto-advance; it just
        # empties the field on the now-PENDING_ACTION record.
        r2 = client.post(f"{BASE}/{pk}/responsible-party", json={}, headers=admin_headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["responsible_organization_pk"] is None
        assert r2.json()["status_value_code"] == "PENDING_ACTION"

    def test_assign_missing_record_404(self, client, admin_headers, register_org_pk):
        r = client.post(
            f"{BASE}/{FAKE_UUID}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════
# 5a2. Event-driven lifecycle (§5.4/§6.2 amendment, owner-confirmed
#      2026-10-26, option 3 of a 3-option proposal): status now ALSO
#      advances automatically as a side effect of (1) assigning a
#      responsible party to a REGISTERED record, and (2) a reply landing on
#      a still-open original under the SAME register. The manual
#      /transition endpoint is untouched and still reachable for every
#      transition — this is additive, not a replacement.
# ═══════════════════════════════════════════════════════════════════════

class TestEventDrivenLifecycle:
    def test_assigning_responsible_party_auto_advances_registered_to_pending_action(
        self, client, admin_headers, register_org_pk,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status_value_code"] == "PENDING_ACTION"

    def test_clearing_responsible_party_never_auto_advances(
        self, client, admin_headers, register_org_pk,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/responsible-party", json={}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status_value_code"] == "REGISTERED"

    def test_reassigning_at_a_non_registered_state_has_no_further_status_effect(
        self, client, admin_headers, register_org_pk,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        # First assignment: REGISTERED -> PENDING_ACTION (the new behavior).
        client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        # Manually advance further, past where assignment alone can reach.
        r_transition = client.post(
            f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers,
        )
        assert r_transition.status_code == 200, r_transition.text
        # Reassign again — §5.4's original guarantee ("reassigned at any
        # state" with no status side effect) must still hold once no
        # longer REGISTERED.
        r_reassign = client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_person_pk": None, "responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        assert r_reassign.status_code == 200, r_reassign.text
        assert r_reassign.json()["status_value_code"] == "ACTIONED"

    def test_reply_auto_actions_a_registered_original(self, client, admin_headers, register_org_pk):
        original = _create(client, admin_headers, register_org_pk, direction="INWARD")
        assert original["status_value_code"] == "REGISTERED"

        r_reply = client.post(
            BASE,
            json=_payload(register_org_pk, direction="OUTWARD", subject="Re: Test correspondence")
            | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        )
        assert r_reply.status_code == 201, r_reply.text

        r_original_after = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_original_after.json()["status_value_code"] == "ACTIONED"

    def test_reply_auto_actions_a_pending_action_original(self, client, admin_headers, register_org_pk):
        original = _create(client, admin_headers, register_org_pk, direction="INWARD")
        client.post(
            f"{BASE}/{original['correspondence_pk']}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        r_check = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_check.json()["status_value_code"] == "PENDING_ACTION"

        r_reply = client.post(
            BASE,
            json=_payload(register_org_pk, direction="OUTWARD")
            | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        )
        assert r_reply.status_code == 201, r_reply.text
        r_original_after = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_original_after.json()["status_value_code"] == "ACTIONED"

    def test_reply_to_an_already_actioned_original_is_a_silent_noop(
        self, client, admin_headers, register_org_pk,
    ):
        original = _create(client, admin_headers, register_org_pk, direction="INWARD")
        client.post(
            f"{BASE}/{original['correspondence_pk']}/transition",
            json={"new_status": "ACTIONED"}, headers=admin_headers,
        )
        r_reply = client.post(
            BASE,
            json=_payload(register_org_pk) | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        )
        assert r_reply.status_code == 201, r_reply.text
        r_original_after = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_original_after.json()["status_value_code"] == "ACTIONED"

    def test_reply_never_reopens_a_closed_original(self, client, admin_headers, register_org_pk):
        original = _create(client, admin_headers, register_org_pk, direction="INWARD")
        client.post(
            f"{BASE}/{original['correspondence_pk']}/transition",
            json={"new_status": "CLOSED"}, headers=admin_headers,
        )
        r_reply = client.post(
            BASE,
            json=_payload(register_org_pk) | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        )
        assert r_reply.status_code == 201, r_reply.text
        r_original_after = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_original_after.json()["status_value_code"] == "CLOSED", (
            "A reply must never auto-reopen a CLOSED original — CLOSED -> "
            "ACTIONED was never a valid transition, manual or automatic."
        )

    def test_reply_under_a_different_register_does_not_auto_action_the_original(
        self, client, admin_headers, register_org_pk, other_org_pk,
    ):
        """Scope guard: require_org_in_scope() in create_correspondence()
        only ever checks the REPLY's own register_organization_pk — without
        the register-match guard, naming an out-of-scope correspondence_pk
        as in_reply_to would let an admin mutate a record they have no
        authority over. register_org_pk/other_org_pk are deliberately
        different registers here."""
        original = _create(client, admin_headers, other_org_pk, direction="INWARD")
        assert original["status_value_code"] == "REGISTERED"

        r_reply = client.post(
            BASE,
            json=_payload(register_org_pk) | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        )
        assert r_reply.status_code == 201, r_reply.text

        r_original_after = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_original_after.json()["status_value_code"] == "REGISTERED", (
            "A reply filed under a DIFFERENT register than the original must "
            "not auto-transition it."
        )


# ═══════════════════════════════════════════════════════════════════════
# 5b. Dispatch — two-sided org-to-org register (v1.1, owner-confirmed
#     2026-10-25). register_org_pk/other_org_pk are both real seeded
#     SAKHA_SANGHA orgs with a short_code already assigned in this dev
#     DB (DSS7/KSS4-style), so next_correspondence_reference_number()
#     succeeds on both sides without any extra fixture setup.
# ═══════════════════════════════════════════════════════════════════════

def _org_payload(sender_org_pk, recipient_org_pk, *, subject="Inter-org test letter"):
    return {
        "register_organization_pk": sender_org_pk,
        "direction": "OUTWARD",
        "correspondence_date": "2026-01-10",
        "received_or_sent_date": "2026-01-11",
        "subject": subject,
        "sender_type": "ORGANIZATION",
        "sender_organization_pk": sender_org_pk,
        "recipient_type": "ORGANIZATION",
        "recipient_organization_pk": recipient_org_pk,
        "medium": "POST",
    }


class TestDispatch:
    def test_create_auto_dispatches_a_linked_inward_row_in_the_recipient_register(
        self, client, admin_headers, register_org_pk, other_org_pk,
    ):
        """
        Owner-confirmed 2026-10-26: "when the letter is sent intra org
        (within nss), i dont think there is any need to register it
        through receive application, it should auto register." The
        CREATE call itself now mints the recipient's INWARD counterpart —
        no separate POST /dispatch needed for the common case.
        """
        r_create = client.post(
            BASE, json=_org_payload(register_org_pk, other_org_pk), headers=admin_headers,
        )
        assert r_create.status_code == 201, r_create.text
        outward = r_create.json()

        inward_pk = outward["counterpart_correspondence_pk"]
        assert inward_pk is not None, "create() must auto-dispatch — counterpart_correspondence_pk should already be set."
        assert outward["counterpart_reference_number"]

        r_inward = client.get(f"{BASE}/{inward_pk}", headers=admin_headers)
        assert r_inward.status_code == 200, r_inward.text
        inward = r_inward.json()

        # Each side has its OWN register/direction/reference number.
        assert inward["register_organization_pk"] == other_org_pk
        assert inward["direction"] == "INWARD"
        assert inward["reference_number"] != outward["reference_number"]
        assert "/IN/" in inward["reference_number"]
        # Reciprocal link.
        assert inward["counterpart_correspondence_pk"] == outward["correspondence_pk"]
        assert inward["counterpart_reference_number"] == outward["reference_number"]
        # Same underlying letter, carried over verbatim.
        assert inward["subject"] == outward["subject"]
        assert inward["sender_type"] == "ORGANIZATION"
        assert inward["sender_organization_pk"] == register_org_pk
        # The INWARD copy's recipient is the receiving org itself (§4.6).
        assert inward["recipient_type"] == "ORGANIZATION"
        assert inward["recipient_organization_pk"] == other_org_pk

    def test_dispatch_after_auto_dispatch_is_409_not_a_second_mint(
        self, client, admin_headers, register_org_pk, other_org_pk,
    ):
        """A manual POST /dispatch after create() already auto-dispatched
        must 409, exactly like calling dispatch twice always has — it must
        never mint a SECOND counterpart for the same row."""
        pk = client.post(
            BASE, json=_org_payload(register_org_pk, other_org_pk), headers=admin_headers,
        ).json()["correspondence_pk"]

        r = client.post(f"{BASE}/{pk}/dispatch", headers=admin_headers)
        assert r.status_code == 409, r.text

    def test_dispatch_remains_the_manual_retry_when_recipient_has_no_short_code(
        self, client, admin_headers, register_org_pk, write_conn,
    ):
        """
        Auto-dispatch is best-effort: if the recipient organization has no
        short_code yet, next_correspondence_reference_number() 422s inside
        the mint attempt, create_correspondence() catches that and leaves
        the OUTWARD row un-dispatched (same as every row did before
        auto-dispatch existed) rather than failing the whole create. POST
        /dispatch remains the manual recovery path once an admin assigns
        the short_code afterwards.
        """
        no_short_code_org_pk = _create_test_organization(
            write_conn, name_prefix="No Short Code Recipient", type_code="SAKHA_SANGHA",
            parent_pk=None, short_code=None,
        )

        r_create = client.post(
            BASE, json=_org_payload(register_org_pk, no_short_code_org_pk), headers=admin_headers,
        )
        assert r_create.status_code == 201, r_create.text
        outward = r_create.json()
        assert outward["counterpart_correspondence_pk"] is None, (
            "Auto-dispatch must have been skipped (no short_code) and left "
            "the row un-dispatched, not failed the create."
        )

        # Still 422 — the short_code is still missing.
        r_dispatch_still_blocked = client.post(
            f"{BASE}/{outward['correspondence_pk']}/dispatch", headers=admin_headers,
        )
        assert r_dispatch_still_blocked.status_code == 422, r_dispatch_still_blocked.text

        # Admin assigns the short_code...
        cur = write_conn.cursor()
        cur.execute(
            "UPDATE nss.organization SET short_code = %s WHERE organization_pk = %s",
            (f"NS{uuid4().hex[:3].upper()}", no_short_code_org_pk),
        )

        # ...and the manual retry now succeeds.
        r_dispatch = client.post(f"{BASE}/{outward['correspondence_pk']}/dispatch", headers=admin_headers)
        assert r_dispatch.status_code == 200, r_dispatch.text
        assert r_dispatch.json()["counterpart_correspondence_pk"] is not None

    def test_external_recipient_cannot_be_dispatched(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]  # default EXTERNAL/EXTERNAL
        r = client.post(f"{BASE}/{pk}/dispatch", headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_person_recipient_cannot_be_dispatched(self, client, admin_headers, register_org_pk, plain_recipient_identity):
        payload = _payload(register_org_pk)
        payload["recipient_type"] = "PERSON"
        payload["recipient_person_pk"] = plain_recipient_identity["person_pk"]
        del payload["recipient_external_name"]
        r_create = client.post(BASE, json=payload, headers=admin_headers)
        assert r_create.status_code == 201, r_create.text

        r_dispatch = client.post(f"{BASE}/{r_create.json()['correspondence_pk']}/dispatch", headers=admin_headers)
        assert r_dispatch.status_code == 422, r_dispatch.text

    def test_inward_record_cannot_be_dispatched(self, client, admin_headers, register_org_pk, other_org_pk):
        payload = _org_payload(register_org_pk, other_org_pk)
        payload["direction"] = "INWARD"
        r_create = client.post(BASE, json=payload, headers=admin_headers)
        assert r_create.status_code == 201, r_create.text

        r_dispatch = client.post(f"{BASE}/{r_create.json()['correspondence_pk']}/dispatch", headers=admin_headers)
        assert r_dispatch.status_code == 422, r_dispatch.text

    def test_missing_record_404(self, client, admin_headers):
        r = client.post(f"{BASE}/{FAKE_UUID}/dispatch", headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_out_of_scope_sender_rejected(self, client, admin_headers, scoped_headers, other_org_pk, register_org_pk):
        """
        scoped_admin_user is scoped to register_org_pk only. Created here
        as the NSS-wide admin (scoped_headers has no scope over
        other_org_pk, so they could not even create this row), to isolate
        exactly one thing: dispatch's own require_org_in_scope check
        against the SENDER row, same gate create_correspondence() uses.
        """
        pk = client.post(
            BASE, json=_org_payload(other_org_pk, register_org_pk), headers=admin_headers,
        ).json()["correspondence_pk"]

        r = client.post(f"{BASE}/{pk}/dispatch", headers=scoped_headers)
        assert r.status_code == 403, r.text

    def test_cannot_dispatch_to_own_sending_organization(self, client, admin_headers, register_org_pk):
        r_create = client.post(
            BASE, json=_org_payload(register_org_pk, register_org_pk), headers=admin_headers,
        )
        assert r_create.status_code == 201, r_create.text

        r_dispatch = client.post(f"{BASE}/{r_create.json()['correspondence_pk']}/dispatch", headers=admin_headers)
        assert r_dispatch.status_code == 422, r_dispatch.text

    def test_anonymous_rejected(self, anon_client):
        r = anon_client.post(f"{BASE}/{FAKE_UUID}/dispatch")
        assert r.status_code in (401, 403), r.text


# ═══════════════════════════════════════════════════════════════════════
# 5c. Reply threading (v1.2, owner-confirmed 2026-10-26: "we should also
#     add reply option to letter too. which will have its own numbers
#     (conceptually same process)") — in_reply_to_correspondence_pk is
#     admin-supplied at create time; a reply is an ordinary row (own
#     reference_number via the normal per-register/per-direction/per-FY
#     counter) that additionally carries the link. No reciprocal update of
#     the original row (unlike counterpart_correspondence_pk) — the link is
#     one-directional, so "replies to X" would be a query, not a stored
#     field on X (not exercised by these tests; see CLAUDE.md Open items).
# ═══════════════════════════════════════════════════════════════════════

class TestReply:
    def test_reply_links_back_to_the_original_and_mints_its_own_reference_number(
        self, client, admin_headers, register_org_pk,
    ):
        original = _create(client, admin_headers, register_org_pk, direction="INWARD")

        r_reply = client.post(
            BASE,
            json=_payload(register_org_pk, direction="OUTWARD", subject="Re: Test correspondence")
            | {"in_reply_to_correspondence_pk": original["correspondence_pk"]},
            headers=admin_headers,
        )
        assert r_reply.status_code == 201, r_reply.text
        reply = r_reply.json()

        assert reply["in_reply_to_correspondence_pk"] == original["correspondence_pk"]
        assert reply["in_reply_to_reference_number"] == original["reference_number"]
        # Own reference number via the ordinary counter — no distinct
        # reply-numbering scheme (owner: "conceptually same process").
        assert reply["reference_number"] != original["reference_number"]
        assert "/OUT/" in reply["reference_number"]
        # The original is untouched — the link is one-directional.
        r_original_after = client.get(f"{BASE}/{original['correspondence_pk']}", headers=admin_headers)
        assert r_original_after.json()["in_reply_to_correspondence_pk"] is None

    def test_reply_to_a_nonexistent_record_404s(self, client, admin_headers, register_org_pk):
        r = client.post(
            BASE,
            json=_payload(register_org_pk) | {"in_reply_to_correspondence_pk": FAKE_UUID},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_reply_is_optional(self, client, admin_headers, register_org_pk):
        """Every pre-existing create call omits in_reply_to_correspondence_pk
        entirely — it must default to NULL, not be required."""
        r = client.post(BASE, json=_payload(register_org_pk), headers=admin_headers)
        assert r.status_code == 201, r.text
        assert r.json()["in_reply_to_correspondence_pk"] is None


# ═══════════════════════════════════════════════════════════════════════
# 6. Documents sub-resource (§8)
# ═══════════════════════════════════════════════════════════════════════

class TestDocuments:
    def test_associate_and_list(self, client, admin_headers, register_org_pk, document_master_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/documents",
            json={"document_master_pk": document_master_pk, "document_purpose": "ORIGINAL"},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["document_purpose"] == "ORIGINAL"

        r_list = client.get(f"{BASE}/{pk}/documents", headers=admin_headers)
        assert r_list.status_code == 200, r_list.text
        assert r_list.json()["total"] >= 1
        assert "items" in r_list.json()

    def test_associate_bad_purpose_rejected(self, client, admin_headers, register_org_pk, document_master_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/documents",
            json={"document_master_pk": document_master_pk, "document_purpose": "BOGUS"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_associate_missing_record_404(self, client, admin_headers, document_master_pk):
        r = client.post(
            f"{BASE}/{FAKE_UUID}/documents",
            json={"document_master_pk": document_master_pk, "document_purpose": "ORIGINAL"},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════
# 7. Finance references (§9 — no financial_transaction FK yet, Tier 12)
# ═══════════════════════════════════════════════════════════════════════

class TestFinanceReferences:
    def test_reference_and_list(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        txn_pk = str(uuid4())  # no FK — any UUID is accepted (§9.3 documented gap)
        r = client.post(
            f"{BASE}/{pk}/finance-references",
            json={"financial_transaction_pk": txn_pk, "relationship_type": "PAYMENT"},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["relationship_type_value_code"] == "PAYMENT"

        r_list = client.get(f"{BASE}/{pk}/finance-references", headers=admin_headers)
        assert r_list.status_code == 200, r_list.text
        assert r_list.json()["total"] >= 1
        assert "items" in r_list.json()

    def test_reference_missing_record_404(self, client, admin_headers):
        r = client.post(
            f"{BASE}/{FAKE_UUID}/finance-references",
            json={"financial_transaction_pk": str(uuid4()), "relationship_type": "PAYMENT"},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════
# 8. RBAC — anonymous rejected
# ═══════════════════════════════════════════════════════════════════════

class TestRBAC:
    def test_anonymous_list_rejected(self, anon_client):
        r = anon_client.get(BASE)
        assert r.status_code in (401, 403), r.text

    def test_anonymous_create_rejected(self, anon_client, register_org_pk):
        r = anon_client.post(BASE, json=_payload(register_org_pk))
        assert r.status_code in (401, 403), r.text


# ═══════════════════════════════════════════════════════════════════════
# 9. Member "Send Application" approval chain (PART 1 — 2026-10-22 fix)
#
# Root-cause fix under test: step 2 used to be auto-flipped to APPROVED
# the instant step 1 was approved (deciding on the Kendra office-bearer's
# behalf). Now step 2 stays genuinely PENDING until its own real decision,
# gated on step 1 already being APPROVED and on the caller being the
# actual seated Kendra Governing Body office-bearer at decision time.
# ═══════════════════════════════════════════════════════════════════════

def _file_kendra_application(client, applicant_headers, kendra_officer_identity, subject="Test routed application"):
    """File a KENDRA_VIA_SAKHA_PRESIDENT application (2-step approval chain) and return the 201 body."""
    r = client.post(
        f"{BASE}/my-applications",
        json={
            "addressing_mode": "KENDRA_VIA_SAKHA_PRESIDENT",
            "recipient_person_pk": kendra_officer_identity["person_pk"],
            "subject": subject,
        },
        headers=applicant_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestApprovalChain:
    def _file_application(self, client, applicant_headers, kendra_officer_identity):
        return _file_kendra_application(client, applicant_headers, kendra_officer_identity)

    def test_step2_not_pending_for_kendra_officer_before_step1_approved(
        self, client, applicant_headers, president_headers, kendra_officer_headers, kendra_officer_identity,
    ):
        app = self._file_application(client, applicant_headers, kendra_officer_identity)
        steps = {s["step_number"]: s for s in app["approval_steps"]}
        assert steps[1]["step_status"] == "PENDING"
        assert steps[2]["step_status"] == "PENDING"

        # Root-cause check: step 2 is NOT yet decidable/visible-as-pending
        # for the Kendra officer, since step 1 hasn't been approved yet.
        pending = client.get(f"{BASE}/approval-steps/pending-for-me", headers=kendra_officer_headers)
        assert pending.status_code == 200, pending.text
        assert app["correspondence_pk"] not in [i["correspondence_pk"] for i in pending.json()["items"]]

        step2_pk = steps[2]["correspondence_approval_step_pk"]
        r = client.post(
            f"{BASE}/approval-steps/{step2_pk}/decision",
            json={"decision": "APPROVE"},
            headers=kendra_officer_headers,
        )
        assert r.status_code == 422, r.text
        assert "step 1" in r.json()["detail"].lower()

    def test_full_chain_approve_reaches_pending_action(
        self, client, applicant_headers, president_headers, kendra_officer_headers, kendra_officer_identity,
    ):
        app = self._file_application(client, applicant_headers, kendra_officer_identity)
        corr_pk = app["correspondence_pk"]
        step1_pk = next(s for s in app["approval_steps"] if s["step_number"] == 1)["correspondence_approval_step_pk"]

        # Step 1 shows up as pending for the President, not for anyone else.
        pending_pres = client.get(f"{BASE}/approval-steps/pending-for-me", headers=president_headers)
        assert corr_pk in [i["correspondence_pk"] for i in pending_pres.json()["items"]]

        r1 = client.post(f"{BASE}/approval-steps/{step1_pk}/decision", json={"decision": "APPROVE"}, headers=president_headers)
        assert r1.status_code == 200, r1.text
        step2 = next(s for s in r1.json()["approval_steps"] if s["step_number"] == 2)
        assert step2["step_status"] == "PENDING"  # genuinely undecided, not auto-flipped

        # Now visible/actionable for the Kendra officer via both read paths.
        addressed = client.get(f"{BASE}/addressed-to-me", headers=kendra_officer_headers)
        assert corr_pk in [i["correspondence_pk"] for i in addressed.json()["items"]]
        pending_kendra = client.get(f"{BASE}/approval-steps/pending-for-me", headers=kendra_officer_headers)
        assert corr_pk in [i["correspondence_pk"] for i in pending_kendra.json()["items"]]

        r2 = client.post(
            f"{BASE}/approval-steps/{step2['correspondence_approval_step_pk']}/decision",
            json={"decision": "APPROVE"},
            headers=kendra_officer_headers,
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert next(s for s in body["approval_steps"] if s["step_number"] == 2)["step_status"] == "APPROVED"
        # Terminal approval maps to the existing §6.2 REGISTERED -> PENDING_ACTION transition.
        assert body["status_value_code"] == "PENDING_ACTION"
        assert body["responsible_person_pk"] == kendra_officer_identity["person_pk"]

    def test_step2_rejected_by_wrong_person_forbidden(
        self, client, applicant_headers, president_headers, kendra_officer_headers, kendra_officer_identity,
        plain_recipient_headers,
    ):
        app = self._file_application(client, applicant_headers, kendra_officer_identity)
        step1_pk = next(s for s in app["approval_steps"] if s["step_number"] == 1)["correspondence_approval_step_pk"]
        r1 = client.post(f"{BASE}/approval-steps/{step1_pk}/decision", json={"decision": "APPROVE"}, headers=president_headers)
        step2_pk = next(s for s in r1.json()["approval_steps"] if s["step_number"] == 2)["correspondence_approval_step_pk"]

        # Someone who isn't the addressed Kendra officer at all.
        r_wrong = client.post(
            f"{BASE}/approval-steps/{step2_pk}/decision", json={"decision": "APPROVE"}, headers=plain_recipient_headers,
        )
        assert r_wrong.status_code == 403, r_wrong.text

        # The real recipient rejects instead of approving — mirrors step 1's reject semantics.
        r_reject = client.post(
            f"{BASE}/approval-steps/{step2_pk}/decision", json={"decision": "REJECT"}, headers=kendra_officer_headers,
        )
        assert r_reject.status_code == 200, r_reject.text
        body = r_reject.json()
        assert next(s for s in body["approval_steps"] if s["step_number"] == 2)["step_status"] == "REJECTED"
        assert body["responsible_person_pk"] is None
        assert body["status_value_code"] == "REGISTERED"  # no status change on reject


# ═══════════════════════════════════════════════════════════════════════
# 9b. Same-person collapse (owner request, 2026-10-25): "if the two
#     consecutive steps approver is the same person, no need of one extra
#     step in between" — create_member_application() now creates only
#     step 1 when the Sakha President resolved for step 1 is the SAME
#     person as the applicant's chosen step-2 addressee, and that lone
#     step's own approval is then the chain's terminal decision.
#
# Deliberately uses other_org_pk (otherwise unused in this file) and seats
# the EXISTING kendra_officer_identity as its President, rather than
# touching register_org_pk/sakha_gb_body_pk/president_identity — those are
# depended on by TestOfficeBearerAddressingWithActingDelegate and
# TestGenderGatedAddressingModes further down this same SAVEPOINT-shared
# module, and must keep their original seat holder.
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def other_sakha_gb_body_pk(write_conn, other_org_pk):
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s AND bm.is_active = TRUE
        LIMIT 1
        """,
        (other_org_pk,),
    )
    row = cur.fetchone()
    assert row, "No seeded SAKHA_GOVERNING_BODY shell for other_org_pk."
    return str(row[0])


@pytest.fixture(scope="module")
def dual_officer_identity(write_conn, other_sakha_gb_body_pk, kendra_officer_identity):
    """Seats the real, already-seated Kendra GB officer as PRESIDENT of a
    SECOND Sakha too — same deactivate-then-seat pattern as
    president_identity, scoped to other_sakha_gb_body_pk only."""
    cur = write_conn.cursor()
    cur.execute(
        """
        UPDATE nss.body_member_assignment a
        SET is_active = FALSE, effective_to = CURRENT_DATE - 1, deleted_at = NOW()
        FROM nss.position_master pm
        WHERE a.position_master_pk = pm.position_master_pk
          AND a.body_master_pk = %s AND pm.position_code = 'PRESIDENT'
          AND a.is_active = TRUE AND a.effective_to IS NULL
        """,
        (other_sakha_gb_body_pk,),
    )
    # kendra_officer_identity's own dict carries no sangha_sevi_pk (only
    # the sangha_sevi_id string) — look it up directly.
    cur.execute(
        "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE person_pk = %s AND is_active = TRUE",
        (kendra_officer_identity["person_pk"],),
    )
    sangha_sevi_pk = str(cur.fetchone()[0])
    _seat_office_bearer(
        write_conn, body_master_pk=other_sakha_gb_body_pk, position_code="PRESIDENT",
        person_pk=kendra_officer_identity["person_pk"], sangha_sevi_pk=sangha_sevi_pk,
    )
    return kendra_officer_identity


@pytest.fixture(scope="module")
def dual_officer_applicant_identity(write_conn, other_org_pk):
    return _create_person_with_login(
        write_conn, "DualOfficerApplicant", organization_pk=other_org_pk, password="CorrDualApplicantPass1",
    )


@pytest.fixture(scope="module")
def dual_officer_applicant_headers(client, dual_officer_applicant_identity):
    return _login_headers(
        client, dual_officer_applicant_identity["sangha_sevi_id"], dual_officer_applicant_identity["password"],
    )


class TestCollapsedApprovalChainSamePerson:
    def test_only_one_step_created_when_both_approvers_are_the_same_person(
        self, client, dual_officer_applicant_headers, dual_officer_identity, kendra_officer_identity,
    ):
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "KENDRA_VIA_SAKHA_PRESIDENT",
                "recipient_person_pk": kendra_officer_identity["person_pk"],
                "subject": "Collapsed single-step test",
            },
            headers=dual_officer_applicant_headers,
        )
        assert r.status_code == 201, r.text
        app = r.json()
        assert len(app["approval_steps"]) == 1
        assert app["approval_steps"][0]["step_number"] == 1
        assert app["approval_steps"][0]["approver_person_pk"] == kendra_officer_identity["person_pk"]
        assert app["status_value_code"] == "REGISTERED"

    def test_approving_the_sole_step_is_terminal(
        self, client, dual_officer_applicant_headers, dual_officer_identity, kendra_officer_identity, kendra_officer_headers,
    ):
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "KENDRA_VIA_SAKHA_PRESIDENT",
                "recipient_person_pk": kendra_officer_identity["person_pk"],
                "subject": "Collapsed single-step terminal-decision test",
            },
            headers=dual_officer_applicant_headers,
        )
        assert r.status_code == 201, r.text
        app = r.json()
        step1_pk = app["approval_steps"][0]["correspondence_approval_step_pk"]

        r_decide = client.post(
            f"{BASE}/approval-steps/{step1_pk}/decision",
            json={"decision": "APPROVE"},
            headers=kendra_officer_headers,
        )
        assert r_decide.status_code == 200, r_decide.text
        body = r_decide.json()
        assert body["approval_steps"][0]["step_status"] == "APPROVED"
        # Terminal, same as a real step-2 approval — no second step was ever
        # created to wait on, so the chain is already fully decided here.
        assert body["status_value_code"] == "PENDING_ACTION"
        assert body["responsible_person_pk"] == kendra_officer_identity["person_pk"]


# ═══════════════════════════════════════════════════════════════════════
# 10. Directed authority on /transition and /responsible-party
#     (PART 2 — owner-confirmed 2026-10-22)
#
# The pre-existing TestTransition/TestResponsibleParty classes above use
# EXTERNAL recipients throughout, so they continue to exercise the
# fallback path (no directed human authority exists -> CORRESPONDENCE_
# MANAGE + admin scope, unchanged) and pass with zero assertion changes —
# see report. These new tests exercise the PERSON-recipient path, where a
# blanket admin grant is no longer sufficient.
# ═══════════════════════════════════════════════════════════════════════

class TestDirectedAuthority:
    def _create_person_addressed(self, client, admin_headers, register_org_pk, recipient_person_pk):
        body = _payload(register_org_pk)
        body["recipient_type"] = "PERSON"
        body["recipient_person_pk"] = recipient_person_pk
        del body["recipient_external_name"]
        r = client.post(BASE, json=body, headers=admin_headers)
        assert r.status_code == 201, r.text
        return r.json()["correspondence_pk"]

    def test_admin_alone_cannot_transition_person_addressed_record(
        self, client, admin_headers, register_org_pk, plain_recipient_identity,
    ):
        pk = self._create_person_addressed(client, admin_headers, register_org_pk, plain_recipient_identity["person_pk"])
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert r.status_code == 403, r.text
        assert "not directed at you" in r.json()["detail"].lower()

    def test_actual_recipient_can_transition(
        self, client, admin_headers, register_org_pk, plain_recipient_identity, plain_recipient_headers,
    ):
        pk = self._create_person_addressed(client, admin_headers, register_org_pk, plain_recipient_identity["person_pk"])
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=plain_recipient_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status_value_code"] == "ACTIONED"

    def test_admin_alone_cannot_reassign_responsible_party(
        self, client, admin_headers, register_org_pk, plain_recipient_identity,
    ):
        pk = self._create_person_addressed(client, admin_headers, register_org_pk, plain_recipient_identity["person_pk"])
        r = client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        assert r.status_code == 403, r.text

    def test_external_recipient_still_falls_back_to_admin_scope(self, client, admin_headers, register_org_pk):
        """
        Owner-flagged edge case: an EXTERNAL recipient has no in-app person
        to delegate "directed-at" authority to at all, so this one row
        shape keeps the pre-existing CORRESPONDENCE_MANAGE + admin-scope
        gate — otherwise such a record could never be acted on by anyone.
        """
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert r.status_code == 200, r.text


# ═══════════════════════════════════════════════════════════════════════
# 11. "Involved-in" history (PART 3 — owner-confirmed 2026-10-22)
# ═══════════════════════════════════════════════════════════════════════

class TestMyInvolvements:
    def test_kendra_officer_sees_application_before_step1_approved(
        self, client, applicant_headers, kendra_officer_headers, kendra_officer_identity,
    ):
        """Unlike /addressed-to-me, /my-involvements is NOT gated on step 1
        being approved — an approver at any step sees it immediately."""
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "KENDRA_VIA_SAKHA_PRESIDENT",
                "recipient_person_pk": kendra_officer_identity["person_pk"],
                "subject": "Involvement visibility test",
            },
            headers=applicant_headers,
        )
        assert r.status_code == 201, r.text
        corr_pk = r.json()["correspondence_pk"]

        addressed = client.get(f"{BASE}/addressed-to-me", headers=kendra_officer_headers)
        assert corr_pk not in [i["correspondence_pk"] for i in addressed.json()["items"]]

        involvements = client.get(f"{BASE}/my-involvements", headers=kendra_officer_headers)
        assert involvements.status_code == 200, involvements.text
        assert corr_pk in [i["correspondence_pk"] for i in involvements.json()["items"]]

    def test_sender_sees_own_sent_application(self, client, applicant_headers, kendra_officer_identity):
        r = client.post(
            f"{BASE}/my-applications",
            json={"addressing_mode": "SAKHA_ORG", "subject": "Sender involvement test"},
            headers=applicant_headers,
        )
        assert r.status_code == 201, r.text
        corr_pk = r.json()["correspondence_pk"]

        involvements = client.get(f"{BASE}/my-involvements", headers=applicant_headers)
        assert involvements.status_code == 200, involvements.text
        assert corr_pk in [i["correspondence_pk"] for i in involvements.json()["items"]]

    def test_anonymous_rejected(self, anon_client):
        r = anon_client.get(f"{BASE}/my-involvements")
        assert r.status_code in (401, 403), r.text


# ═══════════════════════════════════════════════════════════════════════
# 12. Office-bearer addressing routes to a live acting delegate
#     (owner request, 2026-10-25 — selecting the delegate in the "Send
#     Application" dropdown must actually address the application to the
#     delegate's own person_pk, not the absent substantive holder)
# ═══════════════════════════════════════════════════════════════════════

class TestOfficeBearerAddressingWithActingDelegate:
    def test_sakha_office_bearer_addressed_to_acting_delegate(
        self, client, write_conn, applicant_headers, register_org_pk, sakha_gb_body_pk, president_identity,
    ):
        """president_identity seats the substantive PRESIDENT. A second
        person is given a LIVE acting_position_assignment row for that same
        (body, position) — direct SQL, mirroring _seat_office_bearer's own
        style, since there is no POST endpoint for this either. Submitting
        the DELEGATE's person_pk (exactly what NSS.officeBearerDropdownOptions
        now puts in the "Active" option's value — see nss-config.js) must
        succeed and address the application to the delegate, not the
        absent President."""
        delegate = _create_person_with_login(
            write_conn, "ActingDelegate", organization_pk=register_org_pk, password="CorrDelegatePass1",
        )
        cur = write_conn.cursor()
        cur.execute(
            "SELECT position_master_pk FROM nss.position_master WHERE position_code = 'PRESIDENT'",
        )
        position_master_pk = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO nss.acting_position_assignment (
                body_master_pk, position_master_pk, person_pk,
                effective_from, acting_status
            ) VALUES (%s, %s, %s, CURRENT_DATE, 'ACTIVE')
            """,
            (sakha_gb_body_pk, position_master_pk, delegate["person_pk"]),
        )

        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "SAKHA_OFFICE_BEARER",
                "recipient_person_pk": delegate["person_pk"],
                "subject": "Addressed to the acting delegate",
            },
            headers=applicant_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["recipient_person_pk"] == delegate["person_pk"]
        # Confirm it did NOT silently fall back to the absent substantive
        # holder — that would defeat the whole point.
        assert r.json()["recipient_person_pk"] != president_identity["person_pk"]

    def test_sakha_office_bearer_rejects_a_non_bearer_non_delegate(
        self, client, write_conn, applicant_headers, register_org_pk,
    ):
        """A person with neither a substantive seat nor a live acting row
        on the Sakha's own bodies is still correctly rejected — the new
        acting-delegate branch in _assignment_position_for_person must not
        accidentally widen this into "any person is a valid recipient"."""
        nobody = _create_person_with_login(
            write_conn, "Nobody", organization_pk=register_org_pk, password="CorrNobodyPass1",
        )
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "SAKHA_OFFICE_BEARER",
                "recipient_person_pk": nobody["person_pk"],
                "subject": "Should be rejected",
            },
            headers=applicant_headers,
        )
        assert r.status_code == 422, r.text


# ═══════════════════════════════════════════════════════════════════════
# 11. Gender-gated Mahila Parichalana Mandali / Sevak Sangha addressing
#     modes (owner-confirmed 2026-10-25): "we have add mahila sangha also
#     (local and kendra) - only for female members, sevaka sangha
#     (local) - only for male members". Mirrors TestApprovalChain /
#     TestOfficeBearerAddressingWithActingDelegate's fixtures/conventions.
# ═══════════════════════════════════════════════════════════════════════

class TestGenderGatedAddressingModes:
    def test_female_can_address_mahila_office_bearer(
        self, client, female_applicant_headers, mahila_office_bearer_identity,
    ):
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "MAHILA_OFFICE_BEARER",
                "recipient_person_pk": mahila_office_bearer_identity["person_pk"],
                "subject": "Mahila PM application",
            },
            headers=female_applicant_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["recipient_person_pk"] == mahila_office_bearer_identity["person_pk"]

    def test_male_cannot_address_mahila_office_bearer(
        self, client, male_applicant_headers, mahila_office_bearer_identity,
    ):
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "MAHILA_OFFICE_BEARER",
                "recipient_person_pk": mahila_office_bearer_identity["person_pk"],
                "subject": "Should be forbidden",
            },
            headers=male_applicant_headers,
        )
        assert r.status_code == 403, r.text
        assert "MAHILA_OFFICE_BEARER" in r.json()["detail"]

    def test_male_can_address_sevak_office_bearer(
        self, client, male_applicant_headers, sevak_office_bearer_identity,
    ):
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "SEVAK_OFFICE_BEARER",
                "recipient_person_pk": sevak_office_bearer_identity["person_pk"],
                "subject": "Sevak Sangha application",
            },
            headers=male_applicant_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["recipient_person_pk"] == sevak_office_bearer_identity["person_pk"]

    def test_female_cannot_address_sevak_office_bearer(
        self, client, female_applicant_headers, sevak_office_bearer_identity,
    ):
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "SEVAK_OFFICE_BEARER",
                "recipient_person_pk": sevak_office_bearer_identity["person_pk"],
                "subject": "Should be forbidden",
            },
            headers=female_applicant_headers,
        )
        assert r.status_code == 403, r.text
        assert "SEVAK_OFFICE_BEARER" in r.json()["detail"]

    def test_null_gender_applicant_rejected_from_both_gendered_modes(
        self, client, applicant_headers,
    ):
        """applicant_identity (used throughout TestApprovalChain above) has
        no gender set at all — proves the fail-closed behaviour: NULL/unset
        gender is rejected from BOTH gendered modes, never defaulted to
        "allowed". The recipient_person_pk itself doesn't matter here (even
        FAKE_UUID is fine) — _require_gender() in correspondence.py is
        called before any body/position lookup, so the 403 fires first."""
        r_mahila = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "MAHILA_OFFICE_BEARER",
                "recipient_person_pk": FAKE_UUID,
                "subject": "Should be forbidden (null gender)",
            },
            headers=applicant_headers,
        )
        assert r_mahila.status_code == 403, r_mahila.text

        r_sevak = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "SEVAK_OFFICE_BEARER",
                "recipient_person_pk": FAKE_UUID,
                "subject": "Should be forbidden (null gender)",
            },
            headers=applicant_headers,
        )
        assert r_sevak.status_code == 403, r_sevak.text

    def test_kendra_mahila_via_sakha_president_creates_two_step_chain(
        self, client, female_applicant_headers, president_headers,
        kendra_mahila_officer_identity, kendra_mahila_officer_headers,
    ):
        """Mirrors TestApprovalChain.test_step2_not_pending_for_kendra_officer_
        before_step1_approved's shape — step 1 (own Sakha President) and
        step 2 (the central Mahila PM office-bearer) both start PENDING,
        exactly like the existing KENDRA_VIA_SAKHA_PRESIDENT chain."""
        r = client.post(
            f"{BASE}/my-applications",
            json={
                "addressing_mode": "KENDRA_MAHILA_VIA_SAKHA_PRESIDENT",
                "recipient_person_pk": kendra_mahila_officer_identity["person_pk"],
                "subject": "Test routed Mahila PM application",
            },
            headers=female_applicant_headers,
        )
        assert r.status_code == 201, r.text
        app = r.json()
        steps = {s["step_number"]: s for s in app["approval_steps"]}
        assert len(steps) == 2
        assert steps[1]["step_status"] == "PENDING"
        assert steps[2]["step_status"] == "PENDING"

        # Step 1 approval by the Sakha President makes step 2 visible/
        # actionable for the central Mahila PM office-bearer — same
        # mechanism, re-verified end to end for this new mode.
        step1_pk = steps[1]["correspondence_approval_step_pk"]
        r1 = client.post(f"{BASE}/approval-steps/{step1_pk}/decision", json={"decision": "APPROVE"}, headers=president_headers)
        assert r1.status_code == 200, r1.text
        step2 = next(s for s in r1.json()["approval_steps"] if s["step_number"] == 2)
        assert step2["step_status"] == "PENDING"

        addressed = client.get(f"{BASE}/addressed-to-me", headers=kendra_mahila_officer_headers)
        assert app["correspondence_pk"] in [i["correspondence_pk"] for i in addressed.json()["items"]]

        r2 = client.post(
            f"{BASE}/approval-steps/{step2['correspondence_approval_step_pk']}/decision",
            json={"decision": "APPROVE"},
            headers=kendra_mahila_officer_headers,
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert next(s for s in body["approval_steps"] if s["step_number"] == 2)["step_status"] == "APPROVED"
        assert body["status_value_code"] == "PENDING_ACTION"
        assert body["responsible_person_pk"] == kendra_mahila_officer_identity["person_pk"]


# ═══════════════════════════════════════════════════════════════════════
# 11. Broadcast — "Kendra/Anchalika/Zilla circular to all Sakhas under it"
#     (v1.1 follow-up, owner-confirmed 2026-10-26)
#
# Deliberately builds its OWN small, isolated org fixture (one fresh
# parent + two fresh SAKHA_SANGHA children) rather than using the real
# Kendra (which has 173 real Sakha children in this dev DB) — keeps the
# test fast/deterministic and never touches real production-shaped data.
# ═══════════════════════════════════════════════════════════════════════

def _create_test_organization(write_conn, *, name_prefix: str, type_code: str, parent_pk, short_code: str):
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'ORGANIZATION_TYPE' AND md.value_code = %s AND md.is_active = TRUE
        """,
        (type_code,),
    )
    type_row = cur.fetchone()
    assert type_row, f"{type_code} not a seeded ORGANIZATION_TYPE value."
    cur.execute(
        """
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
        """,
    )
    status_row = cur.fetchone()
    assert status_row, "ACTIVE not a seeded STATUS value."
    suffix = uuid4().hex[:8].upper()
    cur.execute(
        """
        INSERT INTO nss.organization (
            organization_name, organization_type_master_data_pk, status_master_data_pk,
            parent_organization_pk, short_code
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING organization_pk
        """,
        (f"{name_prefix} {suffix}", str(type_row[0]), str(status_row[0]),
         str(parent_pk) if parent_pk else None, short_code),
    )
    return str(cur.fetchone()[0])


@pytest.fixture(scope="module")
def broadcast_parent_org_pk(write_conn):
    """A fresh org with no pre-existing children — the broadcast "sender"."""
    return _create_test_organization(
        write_conn, name_prefix="Broadcast Test Parent", type_code="ANCHALIKA_SANGHA",
        parent_pk=None, short_code=f"BP{uuid4().hex[:3].upper()}",
    )


@pytest.fixture(scope="module")
def broadcast_child_sakha_pks(write_conn, broadcast_parent_org_pk):
    """Exactly two fresh SAKHA_SANGHA children under broadcast_parent_org_pk."""
    return [
        _create_test_organization(
            write_conn, name_prefix=f"Broadcast Test Sakha {i}", type_code="SAKHA_SANGHA",
            parent_pk=broadcast_parent_org_pk, short_code=f"BS{i}{uuid4().hex[:2].upper()}",
        )
        for i in range(1, 3)
    ]


@pytest.fixture(scope="module")
def broadcast_admin_headers(admin_headers):
    """
    NSS-WIDE admin_headers (already defined above), not a bespoke scoped
    admin — a scoped admin's personal sangha_sevi row must reference a
    SAKHA_SANGHA organization (fn_enforce_sakha_only_sangha_sevi, MBR-038A),
    which an ANCHALIKA-scoped admin_scope grant (needed to authorize THIS
    org) cannot itself be. NSS-WIDE sidesteps that mismatch entirely while
    still exercising require_org_in_scope() for real (is_super_admin()/
    is_nss_wide() short-circuits it to "always in scope", same as every
    other admin_headers-authorized create_correspondence()/dispatch test
    in this file already does). The dedicated out-of-scope rejection test
    below uses scoped_headers instead, which genuinely has no authority
    here.
    """
    return admin_headers


def _broadcast_payload(register_org_pk, recipient_type_code="SAKHA_SANGHA", **overrides):
    payload = {
        "register_organization_pk": register_org_pk,
        "recipient_organization_type_code": recipient_type_code,
        "correspondence_date": "2026-01-10",
        "received_or_sent_date": "2026-01-11",
        "subject": "Test circular",
        "medium": "CIRCULAR",
    }
    payload.update(overrides)
    return payload


class TestBroadcast:
    def test_broadcast_creates_one_dispatched_row_per_recipient(
        self, client, broadcast_admin_headers, broadcast_parent_org_pk, broadcast_child_sakha_pks,
    ):
        r = client.post(f"{BASE}/broadcast", json=_broadcast_payload(broadcast_parent_org_pk), headers=broadcast_admin_headers)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["recipient_count"] == 2
        assert len(data["items"]) == 2

        seen_recipients = set()
        reference_numbers = set()
        for item in data["items"]:
            assert item["register_organization_pk"] == broadcast_parent_org_pk
            assert item["direction"] == "OUTWARD"
            assert item["sender_type"] == "ORGANIZATION"
            assert item["sender_organization_pk"] == broadcast_parent_org_pk
            assert item["recipient_type"] == "ORGANIZATION"
            assert item["recipient_organization_pk"] in broadcast_child_sakha_pks
            seen_recipients.add(item["recipient_organization_pk"])
            reference_numbers.add(item["reference_number"])

            # Already dispatched — same guarantee a manual create+dispatch
            # pair would give, done automatically.
            assert item["counterpart_correspondence_pk"] is not None
            assert item["counterpart_reference_number"]

            r_counterpart = client.get(f"{BASE}/{item['counterpart_correspondence_pk']}", headers=broadcast_admin_headers)
            assert r_counterpart.status_code == 200, r_counterpart.text
            counterpart = r_counterpart.json()
            assert counterpart["register_organization_pk"] == item["recipient_organization_pk"]
            assert counterpart["direction"] == "INWARD"
            assert counterpart["subject"] == item["subject"]
            assert counterpart["counterpart_correspondence_pk"] == item["correspondence_pk"]

        # Each of the two Sakhas got its own row (not the same row twice),
        # and each OUTWARD row has its own reference_number under the
        # sender's single counter (§4.1 — one counter per org+direction,
        # not per letter/recipient).
        assert seen_recipients == set(broadcast_child_sakha_pks)
        assert len(reference_numbers) == 2

    def test_broadcast_out_of_scope_sender_rejected(
        self, client, scoped_headers, broadcast_parent_org_pk,
    ):
        """scoped_headers is scoped to a DIFFERENT org (register_org_pk from
        the module-level fixtures) — no authority over broadcast_parent_org_pk."""
        r = client.post(f"{BASE}/broadcast", json=_broadcast_payload(broadcast_parent_org_pk), headers=scoped_headers)
        assert r.status_code == 403, r.text

    def test_broadcast_no_matching_descendant_type_rejected(
        self, client, broadcast_admin_headers, broadcast_parent_org_pk, broadcast_child_sakha_pks,
    ):
        r = client.post(
            f"{BASE}/broadcast",
            json=_broadcast_payload(broadcast_parent_org_pk, recipient_type_code="PATHA_CHAKRA"),
            headers=broadcast_admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_broadcast_leaf_organization_rejected(
        self, client, broadcast_admin_headers, broadcast_child_sakha_pks,
    ):
        """A Sakha (leaf, no descendants of its own) cannot broadcast."""
        r = client.post(
            f"{BASE}/broadcast",
            json=_broadcast_payload(broadcast_child_sakha_pks[0]),
            headers=broadcast_admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_broadcast_anonymous_rejected(self, anon_client, broadcast_parent_org_pk):
        r = anon_client.post(f"{BASE}/broadcast", json=_broadcast_payload(broadcast_parent_org_pk))
        assert r.status_code in (401, 403), r.text




# ═══════════════════════════════════════════════════════════════════════
# 12. Coverage gap-fill — validation, edge cases and member-facing reads
#     (added 2026-10-28 from the endpoint x test matrix; reuses the
#     builders and fixtures above, adds no new identity machinery except
#     create_sevi_less_account_headers for the "account with no Sangha Sevi" case)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def bare_headers(write_conn):
    """An ACTIVE account with NO sangha_sevi. Login 401s for it, so the token is minted."""
    return create_sevi_less_account_headers(write_conn, "CBARE")["headers"]


def _apply(client, headers, mode="SAKHA_ORG", **extra):
    return client.post(
        f"{BASE}/my-applications",
        json={"addressing_mode": mode, "subject": f"Gap-fill application {mode}", **extra},
        headers=headers,
    )


def _soft_delete_correspondence(write_conn, correspondence_pk):
    write_conn.cursor().execute(
        "UPDATE nss.correspondence SET is_active = FALSE, deleted_at = NOW() WHERE correspondence_pk = %s",
        (correspondence_pk,),
    )


def _deactivate_assignments(write_conn, *, person_pk, body_master_pk=None):
    """End every open seat of person_pk (optionally on one body). Call inside isolated_savepoint()."""
    cur = write_conn.cursor()
    cur.execute(
        """
        UPDATE nss.body_member_assignment
        SET is_active = FALSE, effective_to = CURRENT_DATE - 1, deleted_at = NOW()
        WHERE person_pk = %s AND is_active = TRUE AND effective_to IS NULL
          AND (%s::uuid IS NULL OR body_master_pk = %s::uuid)
        """,
        (str(person_pk), body_master_pk, body_master_pk),
    )


# ── POST "" : validation and numbering ───────────────────────────────────

class TestCreateValidation:

    @pytest.mark.parametrize("missing", [
        "register_organization_pk", "direction", "correspondence_date", "received_or_sent_date",
        "subject", "sender_type", "recipient_type", "medium",
    ])
    def test_missing_required_field_is_422(self, missing, client, admin_headers, register_org_pk):
        body = _payload(register_org_pk)
        del body[missing]
        assert client.post(BASE, json=body, headers=admin_headers).status_code == 422

    @pytest.mark.parametrize("override", [
        {"subject": "x" * 256},
        {"remarks": "x" * 2001},
        {"sender_type": "ROBOT"},
        {"recipient_type": "ROBOT"},
        {"received_or_sent_date": "2099-01-01"},
        {"correspondence_date": "10/01/2026"},
        {"sender_person_capacity": "PERSONAL"},  # capacity only applies to a PERSON sender
    ], ids=["subject-too-long", "remarks-too-long", "bad-sender-type", "bad-recipient-type",
            "future-received-date", "bad-date-format", "capacity-on-non-person"])
    def test_invalid_field_is_422(self, override, client, admin_headers, register_org_pk):
        r = client.post(BASE, json=_payload(register_org_pk) | override, headers=admin_headers)
        assert r.status_code == 422, r.text

    @pytest.mark.parametrize("sender", [
        {"sender_person_pk": FAKE_UUID},  # PERSON without a capacity
        {"sender_person_pk": FAKE_UUID, "sender_person_capacity": "ORGANIZATIONAL"},  # ...without the org
        {"sender_person_pk": FAKE_UUID, "sender_person_capacity": "PERSONAL",
         "sender_person_organization_pk": FAKE_UUID},  # PERSONAL must not name an org
    ], ids=["no-capacity", "organizational-without-org", "personal-with-org"])
    def test_person_sender_capacity_rules_are_422(self, sender, client, admin_headers, register_org_pk):
        body = _payload(register_org_pk)
        del body["sender_external_name"]
        body.update(sender_type="PERSON", **sender)
        assert client.post(BASE, json=body, headers=admin_headers).status_code == 422

    def test_recipient_with_two_identities_is_422(self, client, admin_headers, register_org_pk, other_org_pk):
        body = _payload(register_org_pk)
        body.update(recipient_type="ORGANIZATION", recipient_organization_pk=other_org_pk)  # still has external_name
        assert client.post(BASE, json=body, headers=admin_headers).status_code == 422

    def test_follow_up_date_may_be_in_the_future(self, client, admin_headers, register_org_pk):
        """§7.3: follow_up_date is a forward-looking target and exempt from the no-future-date rule."""
        r = client.post(BASE, json=_payload(register_org_pk) | {"follow_up_date": "2099-12-31"}, headers=admin_headers)
        assert r.status_code == 201, r.text
        assert r.json()["follow_up_date"] == "2099-12-31"

    def test_unknown_register_organization_is_rejected(self, client, admin_headers):
        r = client.post(BASE, json=_payload(FAKE_UUID), headers=admin_headers)
        assert r.status_code in (404, 422), r.text

    def test_unknown_medium_is_a_client_error(self, client, admin_headers, register_org_pk):
        r = client.post(BASE, json=_payload(register_org_pk) | {"medium": "CARRIER_PIGEON"}, headers=admin_headers)
        assert r.status_code == 422 and "CARRIER_PIGEON" in r.json()["detail"], r.text

    @pytest.mark.parametrize("letter_date,fy", [("2026-01-10", "2025-26"), ("2026-05-10", "2026-27")])
    def test_outward_reference_number_uses_the_letter_dates_financial_year(
        self, letter_date, fy, client, admin_headers, register_org_pk,
    ):
        """Outward numbering follows correspondence_date (like inward/broadcast), not today's date."""
        body = _payload(register_org_pk, direction="OUTWARD") | {
            "correspondence_date": letter_date, "received_or_sent_date": letter_date}
        r = client.post(BASE, json=body, headers=admin_headers)
        assert r.status_code == 201, r.text
        assert f"/OUT/{fy}/" in r.json()["reference_number"]

    def test_unknown_sender_person_is_422_not_500(
        self, client, admin_headers, register_org_pk, isolated_savepoint,
    ):
        body = _payload(register_org_pk)
        del body["sender_external_name"]
        body.update(sender_type="PERSON", sender_person_pk=FAKE_UUID, sender_person_capacity="PERSONAL")
        with isolated_savepoint():
            r = client.post(BASE, json=body, headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_scoped_admin_can_register_inside_their_scope(self, client, scoped_headers, register_org_pk):
        r = client.post(BASE, json=_payload(register_org_pk), headers=scoped_headers)
        assert r.status_code == 201, r.text

    def test_reference_numbers_follow_the_register_format_and_count_up_per_direction(
        self, client, admin_headers, register_org_pk,
    ):
        fmt = re.compile(r"^.+/(IN|OUT)/\d{4}-\d{2}/(\d+)$")
        first = _create(client, admin_headers, register_org_pk, direction="INWARD")["reference_number"]
        second = _create(client, admin_headers, register_org_pk, direction="INWARD")["reference_number"]
        outward = _create(client, admin_headers, register_org_pk, direction="OUTWARD")["reference_number"]
        m1, m2, m3 = fmt.match(first), fmt.match(second), fmt.match(outward)
        assert m1 and m2 and m3, (first, second, outward)
        assert (m1.group(1), m2.group(1), m3.group(1)) == ("IN", "IN", "OUT")
        assert int(m2.group(2)) == int(m1.group(2)) + 1, "per-register, per-direction, per-FY counter"
        assert m1.group(0).rsplit("/", 1)[0] == m2.group(0).rsplit("/", 1)[0], "same prefix + FY within a register"

    def test_letter_to_own_organization_is_not_dispatched(self, client, admin_headers, register_org_pk):
        r = client.post(BASE, json=_org_payload(register_org_pk, register_org_pk), headers=admin_headers)
        assert r.status_code == 201, r.text
        assert r.json()["counterpart_correspondence_pk"] is None

    def test_scoped_admin_cannot_reply_to_a_record_outside_their_scope(
        self, client, admin_headers, scoped_headers, register_org_pk, other_org_pk,
    ):
        foreign = _create(client, admin_headers, other_org_pk, direction="INWARD")
        r = client.post(
            BASE,
            json=_payload(register_org_pk, direction="OUTWARD") | {"in_reply_to_correspondence_pk": foreign["correspondence_pk"]},
            headers=scoped_headers,
        )
        assert r.status_code == 403, f"router answered {r.status_code} and leaked {r.text[:120]}"


# ── GET "" : list filters, paging and scope ──────────────────────────────

class TestListEdgeCases:

    @pytest.mark.parametrize("params", [
        {"direction": "SIDEWAYS"}, {"direction": "inward"}, {"page": 0}, {"page_size": 0}, {"page_size": 101},
    ], ids=["bad-direction", "lowercase-direction", "page-zero", "page-size-zero", "page-size-too-big"])
    def test_invalid_query_params_are_422(self, params, client, admin_headers):
        assert client.get(BASE, params=params, headers=admin_headers).status_code == 422

    def test_pagination_page_sizes_and_totals(self, client, admin_headers, register_org_pk):
        # created_at is the transaction start in this shared-transaction suite, so rows tie on
        # (correspondence_date, created_at); only sizes/totals are asserted, not page membership.
        for _ in range(3):
            _create(client, admin_headers, register_org_pk)
        params = {"register_organization_pk": register_org_pk, "page_size": 2}
        p1 = client.get(BASE, params=params | {"page": 1}, headers=admin_headers).json()
        p2 = client.get(BASE, params=params | {"page": 2}, headers=admin_headers).json()
        assert len(p1["items"]) == 2 and len(p2["items"]) >= 1
        assert p1["total"] >= 3 and p1["total"] == p2["total"]
        past_the_end = client.get(BASE, params=params | {"page": 10_000}, headers=admin_headers).json()
        assert past_the_end["items"] == [] and past_the_end["total"] == p1["total"]

    def test_newest_correspondence_date_first(self, client, admin_headers, register_org_pk):
        _create(client, admin_headers, register_org_pk)
        r = client.get(BASE, params={"register_organization_pk": register_org_pk, "page_size": 100}, headers=admin_headers)
        dates = [i["correspondence_date"] for i in r.json()["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_unknown_status_filter_returns_nothing(self, client, admin_headers):
        r = client.get(BASE, params={"status": "NOT_A_STATUS"}, headers=admin_headers)
        assert r.status_code == 200 and r.json() == {"items": [], "total": 0}

    def test_filters_combine(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk, direction="OUTWARD")["correspondence_pk"]
        client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        r = client.get(BASE, params={"register_organization_pk": register_org_pk, "direction": "OUTWARD",
                                     "status": "ACTIONED", "page_size": 100}, headers=admin_headers)
        items = r.json()["items"]
        assert pk in {i["correspondence_pk"] for i in items}
        assert all(i["direction"] == "OUTWARD" and i["status_value_code"] == "ACTIONED" for i in items)

    def test_scoped_admin_list_never_includes_another_register(
        self, client, admin_headers, scoped_headers, register_org_pk, other_org_pk,
    ):
        foreign = _create(client, admin_headers, other_org_pk)["correspondence_pk"]
        _create(client, admin_headers, register_org_pk)
        r = client.get(BASE, params={"page_size": 100}, headers=scoped_headers)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert items and {i["register_organization_pk"] for i in items} == {register_org_pk}
        assert foreign not in {i["correspondence_pk"] for i in items}

    def test_scoped_admin_filtering_on_a_foreign_register_gets_an_empty_page_not_a_leak(
        self, client, admin_headers, scoped_headers, other_org_pk,
    ):
        _create(client, admin_headers, other_org_pk)
        r = client.get(BASE, params={"register_organization_pk": other_org_pk}, headers=scoped_headers)
        assert r.status_code == 200 and r.json() == {"items": [], "total": 0}

    def test_soft_deleted_records_are_not_listed(self, client, write_conn, admin_headers, register_org_pk):
        params = {"register_organization_pk": register_org_pk, "page_size": 1}
        before = client.get(BASE, params=params, headers=admin_headers).json()["total"]
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        assert client.get(BASE, params=params, headers=admin_headers).json()["total"] == before + 1
        _soft_delete_correspondence(write_conn, pk)
        assert client.get(BASE, params=params, headers=admin_headers).json()["total"] == before


# ── GET /{pk} and /history ───────────────────────────────────────────────

class TestGetAndHistoryEdgeCases:

    def test_non_uuid_path_is_404(self, client, admin_headers):
        assert client.get(f"{BASE}/not-a-uuid", headers=admin_headers).status_code == 404

    def test_detail_carries_party_and_register_names(self, client, admin_headers, register_org_pk):
        body = client.get(f"{BASE}/{_create(client, admin_headers, register_org_pk)['correspondence_pk']}",
                          headers=admin_headers).json()
        assert body["register_organization_name"]
        assert body["sender_external_name"] == "External Sender" and body["recipient_external_name"] == "External Recipient"
        assert body["medium_value_code"] == "POST"
        assert body["counterpart_correspondence_pk"] is None and body["in_reply_to_correspondence_pk"] is None

    def test_history_events_are_chronological_and_name_the_actor(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED", "remarks": "done"}, headers=admin_headers)
        events = client.get(f"{BASE}/{pk}/history", headers=admin_headers).json()["events"]
        assert [e["event_at"] for e in events] == sorted(e["event_at"] for e in events)
        assert any(e["summary"] and "REGISTERED -> ACTIONED" in e["summary"] for e in events)
        assert any(e["actor_name"] for e in events)

    def test_history_walks_a_three_level_reply_thread(self, client, admin_headers, register_org_pk):
        a = _create(client, admin_headers, register_org_pk, direction="INWARD")["correspondence_pk"]
        b = client.post(BASE, json=_payload(register_org_pk, direction="OUTWARD") | {"in_reply_to_correspondence_pk": a},
                        headers=admin_headers).json()["correspondence_pk"]
        c = client.post(BASE, json=_payload(register_org_pk, direction="INWARD") | {"in_reply_to_correspondence_pk": b},
                        headers=admin_headers).json()["correspondence_pk"]

        up = client.get(f"{BASE}/{c}/history", headers=admin_headers).json()
        assert [(n["correspondence_pk"], n["depth"]) for n in up["thread_ancestors"]] == [(a, 2), (b, 1)], "oldest first"
        assert up["thread_descendants"] == []

        down = client.get(f"{BASE}/{a}/history", headers=admin_headers).json()
        assert [(n["correspondence_pk"], n["depth"]) for n in down["thread_descendants"]] == [(b, 1), (c, 2)]
        assert down["thread_ancestors"] == []

    def test_history_of_a_record_with_two_replies_lists_both(self, client, admin_headers, register_org_pk):
        a = _create(client, admin_headers, register_org_pk, direction="INWARD")["correspondence_pk"]
        replies = {
            client.post(BASE, json=_payload(register_org_pk, direction="OUTWARD") | {"in_reply_to_correspondence_pk": a},
                        headers=admin_headers).json()["correspondence_pk"]
            for _ in range(2)
        }
        nodes = client.get(f"{BASE}/{a}/history", headers=admin_headers).json()["thread_descendants"]
        assert {n["correspondence_pk"] for n in nodes} == replies and {n["depth"] for n in nodes} == {1}


# ── POST /{pk}/transition : the rest of the §6.2 table ───────────────────

def _record_in_state(client, headers, org_pk, state):
    """A fresh EXTERNAL-addressed record driven to *state* (admin fallback authority applies)."""
    pk = _create(client, headers, org_pk)["correspondence_pk"]
    if state == "PENDING_ACTION":
        r = client.post(f"{BASE}/{pk}/responsible-party", json={"responsible_organization_pk": org_pk}, headers=headers)
        assert r.status_code == 200 and r.json()["status_value_code"] == "PENDING_ACTION", r.text
    elif state != "REGISTERED":
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": state}, headers=headers)
        assert r.status_code == 200, r.text
    return pk


class TestTransitionTable:

    def test_registered_to_closed(self, client, admin_headers, register_org_pk):
        pk = _record_in_state(client, admin_headers, register_org_pk, "REGISTERED")
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "CLOSED"}, headers=admin_headers)
        assert r.status_code == 200 and r.json()["status_value_code"] == "CLOSED"

    def test_pending_action_to_actioned_to_closed(self, client, admin_headers, register_org_pk):
        pk = _record_in_state(client, admin_headers, register_org_pk, "PENDING_ACTION")
        assert client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"},
                           headers=admin_headers).json()["status_value_code"] == "ACTIONED"
        assert client.post(f"{BASE}/{pk}/transition", json={"new_status": "CLOSED"},
                           headers=admin_headers).json()["status_value_code"] == "CLOSED"

    def test_closed_can_be_reopened_with_remarks_even_without_a_responsible_party(
        self, client, admin_headers, register_org_pk,
    ):
        pk = _record_in_state(client, admin_headers, register_org_pk, "CLOSED")
        assert client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"},
                           headers=admin_headers).status_code == 422
        r = client.post(f"{BASE}/{pk}/transition",
                        json={"new_status": "PENDING_ACTION", "remarks": "New facts arrived."}, headers=admin_headers)
        assert r.status_code == 200 and r.json()["status_value_code"] == "PENDING_ACTION"

    @pytest.mark.parametrize("start,target", [
        ("CLOSED", "ACTIONED"), ("CLOSED", "REGISTERED"), ("ACTIONED", "REGISTERED"),
        ("PENDING_ACTION", "REGISTERED"),
    ])
    def test_transitions_outside_the_table_are_422(self, start, target, client, admin_headers, register_org_pk):
        pk = _record_in_state(client, admin_headers, register_org_pk, start)
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": target}, headers=admin_headers)
        assert r.status_code == 422 and "not a valid transition" in r.json()["detail"].lower()
        assert client.get(f"{BASE}/{pk}", headers=admin_headers).json()["status_value_code"] == start

    def test_whitespace_only_reopen_remarks_are_rejected(self, client, admin_headers, register_org_pk):
        pk = _record_in_state(client, admin_headers, register_org_pk, "ACTIONED")
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION", "remarks": "   "},
                        headers=admin_headers)
        assert r.status_code == 422 and "remarks" in r.json()["detail"].lower()

    @pytest.mark.parametrize("body", [
        {"new_status": "DONE"}, {"new_status": "actioned"}, {"remarks": "no status"}, {},
        {"new_status": "ACTIONED", "remarks": "x" * 2001},
    ], ids=["unknown", "lowercase", "missing-status", "empty", "remarks-too-long"])
    def test_invalid_body_is_422(self, body, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        assert client.post(f"{BASE}/{pk}/transition", json=body, headers=admin_headers).status_code == 422

    def test_transition_remarks_are_saved_and_kept_by_a_later_remark_less_transition(
        self, client, admin_headers, register_org_pk,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r1 = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED", "remarks": "Replied by post."},
                         headers=admin_headers)
        assert r1.json()["remarks"] == "Replied by post."
        r2 = client.post(f"{BASE}/{pk}/transition", json={"new_status": "CLOSED"}, headers=admin_headers)
        assert r2.json()["remarks"] == "Replied by post.", "remarks are only overwritten when supplied"

    def test_non_uuid_path_is_404(self, client, admin_headers):
        r = client.post(f"{BASE}/not-a-uuid/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert r.status_code in (404, 405)


# ── Directed authority: the paths not yet exercised ──────────────────────

class TestDirectedAuthorityEdgeCases:

    def _person_addressed(self, client, admin_headers, org_pk, person_pk):
        return TestDirectedAuthority._create_person_addressed(None, client, admin_headers, org_pk, person_pk)

    def test_responsible_person_gains_authority_and_ends_when_not_assigned(
        self, client, admin_headers, register_org_pk, plain_recipient_identity, plain_recipient_headers,
        applicant_identity, applicant_headers,
    ):
        pk = self._person_addressed(client, admin_headers, register_org_pk, plain_recipient_identity["person_pk"])
        before = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=applicant_headers)
        assert before.status_code == 403 and "not directed at you" in before.json()["detail"].lower()

        # The addressed recipient hands responsibility to the applicant.
        r = client.post(f"{BASE}/{pk}/responsible-party",
                        json={"responsible_person_pk": applicant_identity["person_pk"]}, headers=plain_recipient_headers)
        assert r.status_code == 200, r.text
        assert r.json()["responsible_person_pk"] == applicant_identity["person_pk"]
        assert r.json()["status_value_code"] == "PENDING_ACTION"

        after = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=applicant_headers)
        assert after.status_code == 200, after.text

    def test_seated_office_bearer_of_the_recipient_organization_can_act(
        self, client, admin_headers, register_org_pk, president_identity, president_headers,
        applicant_headers,
    ):
        pk = client.post(BASE, json=_org_payload(register_org_pk, register_org_pk), headers=admin_headers).json()["correspondence_pk"]
        # A bystander and the admin are not the Sakha's office-bearers.
        for h in (applicant_headers, admin_headers):
            r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=h)
            assert r.status_code == 403 and "not directed at you" in r.json()["detail"].lower()
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=president_headers)
        assert r.status_code == 200, r.text

    def test_organization_without_a_governing_body_falls_back_to_admin_scope(
        self, client, admin_headers, register_org_pk, broadcast_parent_org_pk, plain_recipient_headers,
    ):
        """No body_master models this org, so 'directed at' cannot apply (owner-flagged fallback)."""
        pk = client.post(BASE, json=_org_payload(register_org_pk, broadcast_parent_org_pk),
                         headers=admin_headers).json()["correspondence_pk"]
        denied = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=plain_recipient_headers)
        assert denied.status_code == 403 and denied.json()["detail"].startswith("Permission required to")
        ok = client.post(f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=admin_headers)
        assert ok.status_code == 200, ok.text

    def test_scoped_admin_can_act_on_an_external_record_inside_scope_only(
        self, client, admin_headers, scoped_headers, register_org_pk, other_org_pk,
    ):
        mine = _create(client, scoped_headers, register_org_pk)["correspondence_pk"]
        assert client.post(f"{BASE}/{mine}/transition", json={"new_status": "ACTIONED"},
                           headers=scoped_headers).status_code == 200
        theirs = _create(client, admin_headers, other_org_pk)["correspondence_pk"]
        assert client.post(f"{BASE}/{theirs}/transition", json={"new_status": "ACTIONED"},
                           headers=scoped_headers).status_code == 403


class TestResponsiblePartyEdgeCases:

    def test_assigning_a_person_sets_the_field_and_advances_status(
        self, client, admin_headers, register_org_pk, applicant_identity,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/responsible-party",
                        json={"responsible_person_pk": applicant_identity["person_pk"]}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["responsible_person_pk"] == applicant_identity["person_pk"]
        assert r.json()["responsible_organization_pk"] is None
        assert r.json()["status_value_code"] == "PENDING_ACTION"

    def test_switching_from_person_to_organization_clears_the_person(
        self, client, admin_headers, register_org_pk, applicant_identity,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        client.post(f"{BASE}/{pk}/responsible-party",
                    json={"responsible_person_pk": applicant_identity["person_pk"]}, headers=admin_headers)
        r = client.post(f"{BASE}/{pk}/responsible-party",
                        json={"responsible_organization_pk": register_org_pk}, headers=admin_headers)
        assert r.json()["responsible_person_pk"] is None
        assert r.json()["responsible_organization_pk"] == register_org_pk

    def test_person_and_organization_together_is_422(self, client, admin_headers, register_org_pk, applicant_identity):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/responsible-party",
                        json={"responsible_person_pk": applicant_identity["person_pk"],
                              "responsible_organization_pk": register_org_pk}, headers=admin_headers)
        assert r.status_code == 422

    def test_unknown_person_is_422_not_500(self, client, admin_headers, register_org_pk, isolated_savepoint):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        with isolated_savepoint():
            r = client.post(f"{BASE}/{pk}/responsible-party", json={"responsible_person_pk": FAKE_UUID},
                            headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_the_assignment_is_written_to_the_history(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        client.post(f"{BASE}/{pk}/responsible-party", json={"responsible_organization_pk": register_org_pk},
                    headers=admin_headers)
        summaries = [e["summary"] or "" for e in client.get(f"{BASE}/{pk}/history", headers=admin_headers).json()["events"]]
        assert any("Reassigned responsible party" in s for s in summaries)


# ── Documents and finance references: the rest of §8 / §9 ───────────────

class TestDocumentsEdgeCases:

    def test_new_record_has_no_documents(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.get(f"{BASE}/{pk}/documents", headers=admin_headers)
        assert r.status_code == 200 and r.json() == {"items": [], "total": 0}

    def test_list_for_missing_record_is_404(self, client, admin_headers):
        assert client.get(f"{BASE}/{FAKE_UUID}/documents", headers=admin_headers).status_code == 404

    def test_same_document_under_different_purposes_is_allowed(
        self, client, admin_headers, register_org_pk, document_master_pk,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        for purpose in ("ORIGINAL", "ATTACHMENT", "SUPPORTING", "RESPONSE"):
            r = client.post(f"{BASE}/{pk}/documents",
                            json={"document_master_pk": document_master_pk, "document_purpose": purpose, "remarks": purpose.lower()},
                            headers=admin_headers)
            assert r.status_code == 201, (purpose, r.text)
        listed = client.get(f"{BASE}/{pk}/documents", headers=admin_headers).json()
        assert listed["total"] == 4 and {i["document_purpose"] for i in listed["items"]} == {
            "ORIGINAL", "ATTACHMENT", "SUPPORTING", "RESPONSE"}

    def test_same_document_and_purpose_twice_is_409(
        self, client, admin_headers, register_org_pk, document_master_pk, isolated_savepoint,
    ):
        """uq_corr_doc_correspondence_document_purpose, surfaced by the integrity handler."""
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        body = {"document_master_pk": document_master_pk, "document_purpose": "ORIGINAL"}
        assert client.post(f"{BASE}/{pk}/documents", json=body, headers=admin_headers).status_code == 201
        with isolated_savepoint():
            r = client.post(f"{BASE}/{pk}/documents", json=body, headers=admin_headers)
        assert r.status_code == 409, r.text

    def test_unknown_document_is_422_not_500(self, client, admin_headers, register_org_pk, isolated_savepoint):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        with isolated_savepoint():
            r = client.post(f"{BASE}/{pk}/documents",
                            json={"document_master_pk": FAKE_UUID, "document_purpose": "ORIGINAL"}, headers=admin_headers)
        assert r.status_code == 422, r.text

    @pytest.mark.parametrize("body", [
        {}, {"document_purpose": "ORIGINAL"}, {"document_master_pk": "not-a-uuid", "document_purpose": "ORIGINAL"},
    ], ids=["empty", "no-document", "bad-uuid"])
    def test_invalid_body_is_422(self, body, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        assert client.post(f"{BASE}/{pk}/documents", json=body, headers=admin_headers).status_code == 422

    def test_documents_can_be_attached_to_a_closed_record_without_reopening_it(
        self, client, admin_headers, register_org_pk, document_master_pk,
    ):
        """§8: attachable at any state, no status side effect."""
        pk = _record_in_state(client, admin_headers, register_org_pk, "CLOSED")
        r = client.post(f"{BASE}/{pk}/documents",
                        json={"document_master_pk": document_master_pk, "document_purpose": "SUPPORTING"},
                        headers=admin_headers)
        assert r.status_code == 201, r.text
        assert client.get(f"{BASE}/{pk}", headers=admin_headers).json()["status_value_code"] == "CLOSED"

    def test_non_uuid_record_id_is_422(self, client, admin_headers, document_master_pk):
        r = client.post(f"{BASE}/not-a-uuid/documents",
                        json={"document_master_pk": document_master_pk, "document_purpose": "ORIGINAL"},
                        headers=admin_headers)
        assert r.status_code == 422


class TestFinanceReferencesEdgeCases:

    def test_new_record_has_no_references(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.get(f"{BASE}/{pk}/finance-references", headers=admin_headers)
        assert r.status_code == 200 and r.json() == {"items": [], "total": 0}

    def test_list_for_missing_record_is_404(self, client, admin_headers):
        assert client.get(f"{BASE}/{FAKE_UUID}/finance-references", headers=admin_headers).status_code == 404

    @pytest.mark.parametrize("relationship", ["PAYMENT", "RECEIPT", "REFUND", "TAX", "ADJUSTMENT", "OTHER"])
    def test_every_seeded_relationship_type_is_accepted(self, relationship, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/finance-references",
                        json={"financial_transaction_pk": str(uuid4()), "relationship_type": relationship, "remarks": "r"},
                        headers=admin_headers)
        assert r.status_code == 201, r.text
        assert r.json()["relationship_type_value_code"] == relationship and r.json()["remarks"] == "r"

    def test_same_transaction_with_different_relationship_types_is_allowed(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        txn = str(uuid4())
        for relationship in ("PAYMENT", "TAX"):
            assert client.post(f"{BASE}/{pk}/finance-references",
                               json={"financial_transaction_pk": txn, "relationship_type": relationship},
                               headers=admin_headers).status_code == 201
        assert client.get(f"{BASE}/{pk}/finance-references", headers=admin_headers).json()["total"] == 2

    def test_exact_duplicate_reference_is_409(self, client, admin_headers, register_org_pk, isolated_savepoint):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        body = {"financial_transaction_pk": str(uuid4()), "relationship_type": "PAYMENT"}
        assert client.post(f"{BASE}/{pk}/finance-references", json=body, headers=admin_headers).status_code == 201
        with isolated_savepoint():
            r = client.post(f"{BASE}/{pk}/finance-references", json=body, headers=admin_headers)
        assert r.status_code == 409, r.text

    def test_unknown_relationship_type_is_a_client_error(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/finance-references",
                        json={"financial_transaction_pk": str(uuid4()), "relationship_type": "BARTER"}, headers=admin_headers)
        assert r.status_code == 422 and "BARTER" in r.json()["detail"], r.text

    @pytest.mark.parametrize("body", [
        {}, {"relationship_type": "PAYMENT"}, {"financial_transaction_pk": "not-a-uuid", "relationship_type": "PAYMENT"},
    ], ids=["empty", "no-transaction", "bad-uuid"])
    def test_invalid_body_is_422(self, body, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        assert client.post(f"{BASE}/{pk}/finance-references", json=body, headers=admin_headers).status_code == 422

    def test_references_persist_on_a_closed_record(self, client, admin_headers, register_org_pk):
        pk = _record_in_state(client, admin_headers, register_org_pk, "CLOSED")
        r = client.post(f"{BASE}/{pk}/finance-references",
                        json={"financial_transaction_pk": str(uuid4()), "relationship_type": "REFUND"}, headers=admin_headers)
        assert r.status_code == 201, r.text


# ── Broadcast: validation and atomicity-adjacent failures ────────────────

class TestBroadcastValidation:

    @pytest.mark.parametrize("missing", ["register_organization_pk", "recipient_organization_type_code", "subject",
                                         "medium", "correspondence_date", "received_or_sent_date"])
    def test_missing_required_field_is_422(self, missing, client, broadcast_admin_headers, broadcast_parent_org_pk):
        body = _broadcast_payload(broadcast_parent_org_pk)
        del body[missing]
        assert client.post(f"{BASE}/broadcast", json=body, headers=broadcast_admin_headers).status_code == 422

    @pytest.mark.parametrize("override", [
        {"correspondence_date": "2099-01-01"}, {"received_or_sent_date": "2099-01-01"}, {"subject": "x" * 256},
    ], ids=["future-correspondence-date", "future-received-date", "subject-too-long"])
    def test_invalid_field_is_422(self, override, client, broadcast_admin_headers, broadcast_parent_org_pk):
        r = client.post(f"{BASE}/broadcast", json=_broadcast_payload(broadcast_parent_org_pk, **override),
                        headers=broadcast_admin_headers)
        assert r.status_code == 422

    def test_unknown_organization_type_code_is_422(
        self, client, broadcast_admin_headers, broadcast_parent_org_pk, broadcast_child_sakha_pks,
    ):
        r = client.post(f"{BASE}/broadcast",
                        json=_broadcast_payload(broadcast_parent_org_pk, recipient_type_code="NOT_A_TYPE"),
                        headers=broadcast_admin_headers)
        assert r.status_code == 422 and "No active NOT_A_TYPE" in r.json()["detail"]

    def test_unknown_sender_organization_is_rejected(self, client, broadcast_admin_headers):
        r = client.post(f"{BASE}/broadcast", json=_broadcast_payload(FAKE_UUID), headers=broadcast_admin_headers)
        assert r.status_code in (404, 422), r.text

    def test_a_recipient_without_a_short_code_fails_the_whole_circular(
        self, client, write_conn, broadcast_admin_headers, isolated_savepoint,
    ):
        """The inward counterpart cannot be numbered, so the request is a 422 (and rolls back in production)."""
        parent = _create_test_organization(
            write_conn, name_prefix="Broadcast NoCode Parent", type_code="ANCHALIKA_SANGHA",
            parent_pk=None, short_code=f"NP{uuid4().hex[:3].upper()}",
        )
        _create_test_organization(
            write_conn, name_prefix="Broadcast NoCode Sakha", type_code="SAKHA_SANGHA",
            parent_pk=parent, short_code=None,
        )
        with isolated_savepoint():
            r = client.post(f"{BASE}/broadcast", json=_broadcast_payload(parent), headers=broadcast_admin_headers)
        assert r.status_code == 422 and "short code" in r.json()["detail"].lower()


# ── POST /my-applications ────────────────────────────────────────────────

class TestMemberApplicationCreate:

    def test_sakha_org_application_is_a_registered_outward_letter_from_the_member(
        self, client, applicant_headers, applicant_identity, register_org_pk,
    ):
        r = _apply(client, applicant_headers, remarks="please consider", follow_up_date="2099-01-01")
        assert r.status_code == 201, r.text
        b = r.json()
        assert (b["direction"], b["status_value_code"], b["medium_value_code"]) == ("OUTWARD", "REGISTERED", "HAND_DELIVERY")
        assert b["sender_type"] == "PERSON" and b["sender_person_pk"] == applicant_identity["person_pk"]
        assert b["sender_person_capacity"] == "PERSONAL"
        assert b["recipient_type"] == "ORGANIZATION" and b["recipient_organization_pk"] == register_org_pk
        assert b["register_organization_pk"] == register_org_pk
        assert b["correspondence_date"] == b["received_or_sent_date"] == date.today().isoformat()
        assert b["approval_steps"] == [] and b["responsible_person_pk"] is None
        assert b["counterpart_correspondence_pk"] is None
        assert b["remarks"] == "please consider" and b["follow_up_date"] == "2099-01-01"
        assert re.match(r"^.+/OUT/\d{4}-\d{2}/\d+$", b["reference_number"])

    def test_applications_draw_from_the_registers_outward_counter(self, client, applicant_headers):
        a = _apply(client, applicant_headers).json()["reference_number"]
        b = _apply(client, applicant_headers).json()["reference_number"]
        assert int(b.rsplit("/", 1)[1]) == int(a.rsplit("/", 1)[1]) + 1

    def test_addressed_to_a_seated_office_bearer_has_no_approval_chain(
        self, client, applicant_headers, president_identity, president_headers,
    ):
        r = _apply(client, applicant_headers, "SAKHA_OFFICE_BEARER", recipient_person_pk=president_identity["person_pk"])
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["recipient_type"] == "PERSON" and b["recipient_person_pk"] == president_identity["person_pk"]
        assert b["approval_steps"] == []
        # Directly addressed, so it is in the officer's inbox straight away.
        inbox = client.get(f"{BASE}/addressed-to-me", params={"page_size": 100}, headers=president_headers).json()["items"]
        assert b["correspondence_pk"] in {i["correspondence_pk"] for i in inbox}

    @pytest.mark.parametrize("mode", [
        "SAKHA_OFFICE_BEARER", "KENDRA_VIA_SAKHA_PRESIDENT", "MAHILA_OFFICE_BEARER",
        "KENDRA_MAHILA_VIA_SAKHA_PRESIDENT", "SEVAK_OFFICE_BEARER",
    ])
    def test_office_bearer_modes_require_a_recipient(self, mode, client, applicant_headers):
        assert _apply(client, applicant_headers, mode).status_code == 422

    def test_sakha_org_mode_rejects_a_recipient(self, client, applicant_headers, president_identity):
        r = _apply(client, applicant_headers, "SAKHA_ORG", recipient_person_pk=president_identity["person_pk"])
        assert r.status_code == 422

    @pytest.mark.parametrize("body", [
        {"addressing_mode": "TELEPATHY", "subject": "s"},
        {"addressing_mode": "SAKHA_ORG"},
        {"subject": "no mode"},
        {"addressing_mode": "SAKHA_ORG", "subject": "x" * 256},
        {"addressing_mode": "SAKHA_ORG", "subject": "s", "remarks": "x" * 2001},
    ], ids=["bad-mode", "no-subject", "no-mode", "subject-too-long", "remarks-too-long"])
    def test_invalid_body_is_422(self, body, client, applicant_headers):
        assert client.post(f"{BASE}/my-applications", json=body, headers=applicant_headers).status_code == 422

    def test_kendra_mode_to_someone_who_is_not_a_kendra_officer_is_422(
        self, client, applicant_headers, plain_recipient_identity, president_identity,
    ):
        r = _apply(client, applicant_headers, "KENDRA_VIA_SAKHA_PRESIDENT",
                   recipient_person_pk=plain_recipient_identity["person_pk"])
        assert r.status_code == 422 and "Kendra-level office-bearer" in r.json()["detail"]

    def test_kendra_mode_without_a_sitting_sakha_president_is_422(
        self, client, write_conn, isolated_savepoint, dual_officer_applicant_headers, kendra_officer_identity,
        other_sakha_gb_body_pk,
    ):
        with isolated_savepoint():
            write_conn.cursor().execute(
                """
                UPDATE nss.body_member_assignment a
                SET is_active = FALSE, effective_to = CURRENT_DATE - 1, deleted_at = NOW()
                FROM nss.position_master pm
                WHERE a.position_master_pk = pm.position_master_pk AND a.body_master_pk = %s
                  AND pm.position_code = 'PRESIDENT' AND a.is_active = TRUE AND a.effective_to IS NULL
                """,
                (other_sakha_gb_body_pk,),
            )
            r = _apply(client, dual_officer_applicant_headers, "KENDRA_VIA_SAKHA_PRESIDENT",
                       recipient_person_pk=kendra_officer_identity["person_pk"])
        assert r.status_code == 422 and "no sitting President" in r.json()["detail"]

    def test_account_without_a_sangha_sevi_cannot_apply(self, client, bare_headers):
        r = _apply(client, bare_headers)
        assert r.status_code == 403 and "no active Sangha Sevi record" in r.json()["detail"]

    def test_anonymous_cannot_apply(self, anon_client):
        assert anon_client.post(f"{BASE}/my-applications",
                                json={"addressing_mode": "SAKHA_ORG", "subject": "s"}).status_code in (401, 403)


# ── GET /my-applications, /my-applications/{pk} ──────────────────────────

class TestMyApplicationsRead:

    def test_list_shows_only_the_callers_own(
        self, client, applicant_headers, applicant_identity, plain_recipient_headers,
    ):
        first = _apply(client, applicant_headers).json()["correspondence_pk"]
        second = _apply(client, applicant_headers).json()["correspondence_pk"]
        mine = client.get(f"{BASE}/my-applications", params={"page_size": 100}, headers=applicant_headers).json()
        ids = [i["correspondence_pk"] for i in mine["items"]]
        assert {first, second} <= set(ids) and mine["total"] >= len(ids)
        assert {i["sender_person_pk"] for i in mine["items"]} == {applicant_identity["person_pk"]}
        theirs = client.get(f"{BASE}/my-applications", params={"page_size": 100}, headers=plain_recipient_headers).json()
        assert {first, second}.isdisjoint(i["correspondence_pk"] for i in theirs["items"])

    def test_pagination(self, client, applicant_headers):
        _apply(client, applicant_headers)
        _apply(client, applicant_headers)
        r = client.get(f"{BASE}/my-applications", params={"page_size": 1, "page": 2}, headers=applicant_headers).json()
        assert len(r["items"]) == 1 and r["total"] >= 2

    @pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
    def test_pagination_bounds_are_422(self, params, client, applicant_headers):
        assert client.get(f"{BASE}/my-applications", params=params, headers=applicant_headers).status_code == 422

    def test_account_without_a_sangha_sevi_sees_an_empty_list(self, client, bare_headers):
        r = client.get(f"{BASE}/my-applications", headers=bare_headers)
        assert r.status_code == 200 and r.json() == {"items": [], "total": 0}

    def test_detail_of_own_application(self, client, applicant_headers):
        pk = _apply(client, applicant_headers).json()["correspondence_pk"]
        r = client.get(f"{BASE}/my-applications/{pk}", headers=applicant_headers)
        assert r.status_code == 200, r.text
        assert r.json()["correspondence_pk"] == pk and r.json()["approval_steps"] == []

    def test_detail_includes_the_approval_chain(self, client, applicant_headers, president_identity, kendra_officer_identity):
        app = _file_kendra_application(client, applicant_headers, kendra_officer_identity)
        steps = client.get(f"{BASE}/my-applications/{app['correspondence_pk']}", headers=applicant_headers).json()["approval_steps"]
        assert [s["step_number"] for s in steps] == [1, 2]
        assert steps[0]["approver_person_pk"] == president_identity["person_pk"]
        assert steps[1]["approver_person_pk"] == kendra_officer_identity["person_pk"]

    def test_someone_elses_application_is_404_not_403(
        self, client, applicant_headers, plain_recipient_headers, admin_headers,
    ):
        pk = _apply(client, applicant_headers).json()["correspondence_pk"]
        for h in (plain_recipient_headers, admin_headers):
            assert client.get(f"{BASE}/my-applications/{pk}", headers=h).status_code == 404

    def test_unknown_and_malformed_ids_are_404(self, client, applicant_headers):
        assert client.get(f"{BASE}/my-applications/{FAKE_UUID}", headers=applicant_headers).status_code == 404
        assert client.get(f"{BASE}/my-applications/not-a-uuid", headers=applicant_headers).status_code == 404

    def test_a_soft_deleted_application_is_gone(self, client, write_conn, applicant_headers):
        pk = _apply(client, applicant_headers).json()["correspondence_pk"]
        _soft_delete_correspondence(write_conn, pk)
        assert client.get(f"{BASE}/my-applications/{pk}", headers=applicant_headers).status_code == 404
        listed = client.get(f"{BASE}/my-applications", params={"page_size": 100}, headers=applicant_headers).json()
        assert pk not in {i["correspondence_pk"] for i in listed["items"]}

    def test_anonymous_is_rejected(self, anon_client):
        assert anon_client.get(f"{BASE}/my-applications").status_code in (401, 403)
        assert anon_client.get(f"{BASE}/my-applications/{FAKE_UUID}").status_code in (401, 403)


# ── GET /addressed-to-me, /approval-steps/pending-for-me ─────────────────

class TestAddressedToMeAndPendingForMe:

    def test_an_organization_addressed_application_is_not_in_any_persons_inbox(
        self, client, applicant_headers, president_headers, president_identity,
    ):
        pk = _apply(client, applicant_headers, "SAKHA_ORG").json()["correspondence_pk"]
        inbox = client.get(f"{BASE}/addressed-to-me", params={"page_size": 100}, headers=president_headers).json()["items"]
        assert pk not in {i["correspondence_pk"] for i in inbox}

    def test_the_sender_does_not_see_their_own_application_in_their_inbox(self, client, applicant_headers):
        pk = _apply(client, applicant_headers).json()["correspondence_pk"]
        inbox = client.get(f"{BASE}/addressed-to-me", params={"page_size": 100}, headers=applicant_headers).json()["items"]
        assert pk not in {i["correspondence_pk"] for i in inbox}

    @pytest.mark.parametrize("path", ["addressed-to-me", "approval-steps/pending-for-me", "my-involvements"])
    @pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
    def test_pagination_bounds_are_422(self, path, params, client, applicant_headers):
        assert client.get(f"{BASE}/{path}", params=params, headers=applicant_headers).status_code == 422

    @pytest.mark.parametrize("path", ["addressed-to-me", "approval-steps/pending-for-me", "my-involvements"])
    def test_account_without_a_sangha_sevi_gets_an_empty_page(self, path, client, bare_headers):
        r = client.get(f"{BASE}/{path}", headers=bare_headers)
        assert r.status_code == 200 and r.json() == {"items": [], "total": 0}

    @pytest.mark.parametrize("path", ["addressed-to-me", "approval-steps/pending-for-me"])
    def test_anonymous_is_rejected(self, path, anon_client):
        assert anon_client.get(f"{BASE}/{path}").status_code in (401, 403)

    def test_pending_for_me_is_empty_for_someone_with_nothing_to_decide(self, client, plain_recipient_headers):
        r = client.get(f"{BASE}/approval-steps/pending-for-me", headers=plain_recipient_headers)
        assert r.status_code == 200 and r.json()["items"] == []

    def test_a_decided_step_leaves_the_presidents_pending_list(
        self, client, applicant_headers, president_headers, kendra_officer_identity,
    ):
        app = _file_kendra_application(client, applicant_headers, kendra_officer_identity)
        step1 = app["approval_steps"][0]["correspondence_approval_step_pk"]
        listed = lambda: {i["correspondence_pk"] for i in client.get(  # noqa: E731
            f"{BASE}/approval-steps/pending-for-me", params={"page_size": 100}, headers=president_headers).json()["items"]}
        assert app["correspondence_pk"] in listed()
        client.post(f"{BASE}/approval-steps/{step1}/decision", json={"decision": "APPROVE"}, headers=president_headers)
        assert app["correspondence_pk"] not in listed()


# ── POST /approval-steps/{pk}/decision : the rest of the chain ───────────

class TestApprovalDecisionEdgeCases:

    def _decide(self, client, headers, step_pk, decision="APPROVE", **extra):
        return client.post(f"{BASE}/approval-steps/{step_pk}/decision", json={"decision": decision, **extra}, headers=headers)

    def _filed(self, client, applicant_headers, kendra_officer_identity):
        app = _file_kendra_application(client, applicant_headers, kendra_officer_identity)
        steps = {s["step_number"]: s["correspondence_approval_step_pk"] for s in app["approval_steps"]}
        return app, steps[1], steps[2]

    def test_step_one_rejection_stops_the_chain(
        self, client, applicant_headers, president_headers, kendra_officer_headers, kendra_officer_identity,
    ):
        app, step1, step2 = self._filed(client, applicant_headers, kendra_officer_identity)
        r = self._decide(client, president_headers, step1, "REJECT", remarks="Not appropriate")
        assert r.status_code == 200, r.text
        body = r.json()
        s1, s2 = (next(s for s in body["approval_steps"] if s["step_number"] == n) for n in (1, 2))
        assert s1["step_status"] == "REJECTED" and s1["remarks"] == "Not appropriate" and s1["decided_at"]
        assert s2["step_status"] == "PENDING" and s2["decided_at"] is None
        assert body["responsible_person_pk"] is None and body["status_value_code"] == "REGISTERED"

        # The Kendra officer never sees it as actionable, and cannot decide step 2 out of order.
        for path in ("addressed-to-me", "approval-steps/pending-for-me"):
            items = client.get(f"{BASE}/{path}", params={"page_size": 100}, headers=kendra_officer_headers).json()["items"]
            assert app["correspondence_pk"] not in {i["correspondence_pk"] for i in items}, path
        out_of_order = self._decide(client, kendra_officer_headers, step2)
        assert out_of_order.status_code == 422 and "step 1" in out_of_order.json()["detail"].lower()

    def test_step_one_approval_hands_responsibility_to_the_step_two_approver(
        self, client, applicant_headers, president_headers, kendra_officer_identity,
    ):
        _, step1, _ = self._filed(client, applicant_headers, kendra_officer_identity)
        body = self._decide(client, president_headers, step1, "APPROVE", remarks="Forwarded").json()
        assert body["responsible_person_pk"] == kendra_officer_identity["person_pk"]
        assert body["status_value_code"] == "REGISTERED", "only the terminal approval advances the status"
        s1 = next(s for s in body["approval_steps"] if s["step_number"] == 1)
        assert s1["step_status"] == "APPROVED" and s1["remarks"] == "Forwarded" and s1["decided_at"]

    def test_a_step_cannot_be_decided_twice(
        self, client, applicant_headers, president_headers, kendra_officer_identity,
    ):
        _, step1, _ = self._filed(client, applicant_headers, kendra_officer_identity)
        assert self._decide(client, president_headers, step1).status_code == 200
        again = self._decide(client, president_headers, step1, "REJECT")
        assert again.status_code == 422 and "already APPROVED" in again.json()["detail"]

    def test_unknown_step_is_404(self, client, president_headers):
        assert self._decide(client, president_headers, FAKE_UUID).status_code == 404

    @pytest.mark.parametrize("body", [{}, {"decision": "MAYBE"}, {"decision": "approve"}, {"remarks": "no decision"},
                                      {"decision": "APPROVE", "remarks": "x" * 2001}])
    def test_invalid_body_is_422(self, body, client, president_headers):
        r = client.post(f"{BASE}/approval-steps/{FAKE_UUID}/decision", json=body, headers=president_headers)
        assert r.status_code == 422

    def test_only_the_named_approver_may_decide_step_one(
        self, client, applicant_headers, plain_recipient_headers, admin_headers, kendra_officer_headers,
        kendra_officer_identity,
    ):
        _, step1, _ = self._filed(client, applicant_headers, kendra_officer_identity)
        # Not the sender, not a bystander, not an NSS-wide admin, not the step-2 approver.
        for h in (applicant_headers, plain_recipient_headers, admin_headers, kendra_officer_headers):
            r = self._decide(client, h, step1)
            assert r.status_code == 403 and "not awaiting your decision" in r.json()["detail"]

    def test_a_president_who_lost_the_seat_can_no_longer_decide(
        self, client, write_conn, isolated_savepoint, applicant_headers, president_headers, president_identity,
        kendra_officer_identity, sakha_gb_body_pk,
    ):
        _, step1, _ = self._filed(client, applicant_headers, kendra_officer_identity)
        with isolated_savepoint():
            _deactivate_assignments(write_conn, person_pk=president_identity["person_pk"], body_master_pk=sakha_gb_body_pk)
            r = self._decide(client, president_headers, step1)
        assert r.status_code == 403 and "no longer the seated President" in r.json()["detail"]

    def test_a_kendra_officer_who_lost_the_seat_can_no_longer_decide_step_two(
        self, client, write_conn, isolated_savepoint, applicant_headers, president_headers,
        kendra_officer_headers, kendra_officer_identity,
    ):
        _, step1, step2 = self._filed(client, applicant_headers, kendra_officer_identity)
        assert self._decide(client, president_headers, step1).status_code == 200
        with isolated_savepoint():
            _deactivate_assignments(write_conn, person_pk=kendra_officer_identity["person_pk"])
            r = self._decide(client, kendra_officer_headers, step2)
        assert r.status_code == 403 and "no longer a seated central-level office-bearer" in r.json()["detail"]

    def test_anonymous_cannot_decide(self, anon_client):
        r = anon_client.post(f"{BASE}/approval-steps/{FAKE_UUID}/decision", json={"decision": "APPROVE"})
        assert r.status_code in (401, 403)


# ── GET /my-involvements ─────────────────────────────────────────────────

class TestMyInvolvementsEdgeCases:

    def test_a_responsible_party_sees_the_record_and_a_bystander_does_not(
        self, client, admin_headers, register_org_pk, plain_recipient_identity, plain_recipient_headers,
        applicant_headers,
    ):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        client.post(f"{BASE}/{pk}/responsible-party",
                    json={"responsible_person_pk": plain_recipient_identity["person_pk"]}, headers=admin_headers)
        seen = client.get(f"{BASE}/my-involvements", params={"page_size": 100}, headers=plain_recipient_headers).json()["items"]
        assert pk in {i["correspondence_pk"] for i in seen}
        other = client.get(f"{BASE}/my-involvements", params={"page_size": 100}, headers=applicant_headers).json()["items"]
        assert pk not in {i["correspondence_pk"] for i in other}

    def test_a_directly_addressed_recipient_sees_it_and_an_unrelated_member_does_not(
        self, client, applicant_headers, president_identity, president_headers, plain_recipient_headers,
    ):
        pk = _apply(client, applicant_headers, "SAKHA_OFFICE_BEARER",
                    recipient_person_pk=president_identity["person_pk"]).json()["correspondence_pk"]
        for h, expected in ((president_headers, True), (applicant_headers, True), (plain_recipient_headers, False)):
            items = client.get(f"{BASE}/my-involvements", params={"page_size": 100}, headers=h).json()["items"]
            assert (pk in {i["correspondence_pk"] for i in items}) is expected

    def test_total_matches_the_number_of_involvements(self, client, applicant_headers):
        _apply(client, applicant_headers)
        r = client.get(f"{BASE}/my-involvements", params={"page_size": 1}, headers=applicant_headers).json()
        full = client.get(f"{BASE}/my-involvements", params={"page_size": 100}, headers=applicant_headers).json()
        assert r["total"] == full["total"] >= 1 and len(r["items"]) == 1
