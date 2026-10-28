"""
NSS ERP — shared fixtures/helpers for the Attendance test modules
(tests/api/test_attendance.py and tests/security/test_attendance_security.py).

Builds on the admin/person/seat builders from tests/api/test_correspondence.py
(same Tier 6 pattern: real rows, rolled back with the module SAVEPOINT) rather
than re-implementing them. Test modules import the fixtures they need by name.

Cast (all at one "register" Sakha unless noted):
  admin_user       NSS_ERP_ADMIN, NSS-WIDE         (global oversight, ATT-044)
  sakha_admin      NSS_ERP_SAKHA_ADMIN, SAKHA scope (ATTENDANCE_VIEW + MANAGE, no seat)
  marker_user      NSS_ERP_ATTENDANCE_MARKER, SAKHA (ATTENDANCE_VIEW + MANAGE, no seat)
  secretary_user   SAKHA_ADMIN scoped + seated SECRETARY on the Sakha Governing Body
  president_user   SAKHA_ADMIN scoped + seated PRESIDENT on the Sakha Governing Body
  other_admin      SAKHA_ADMIN scoped to a DIFFERENT Sakha
  other_president  SAKHA_ADMIN scoped to the different Sakha + seated PRESIDENT there
  plain_member     person + login, no role at all (no ATTENDANCE_VIEW)

Review authority is a real seat on body_member_assignment, not a permission
(ATT-042), so the officers also need a role carrying ATTENDANCE_VIEW to get
past the endpoint's entry gate.
"""

from datetime import date, timedelta

import pytest

from tests.api.test_correspondence import (  # noqa: F401  (re-exported to test modules)
    ADMIN_PASSWORD,
    SCOPED_PASSWORD,
    _create_admin_with_scope,
    _create_person_with_login,
    _login_headers,
    _seat_office_bearer,
)

BASE = "/api/v1/attendance"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

# Far-past Sundays: no real data collides with these, and every stats call
# below passes this window so pre-existing rows can never skew an assertion.
FIRST_PUJA = date(2001, 3, 4)
PUJA_DATES = [FIRST_PUJA + timedelta(weeks=i) for i in range(5)]
WINDOW = {"from_date": "2001-01-01", "to_date": "2001-12-31"}


# ═══════════════════════════════════════════════════════════════════════
# Builders
# ═══════════════════════════════════════════════════════════════════════

def _sakha_gb_body_pk(write_conn, organization_pk) -> str:
    """The seeded (empty-shell) SAKHA_GOVERNING_BODY of a Sakha."""
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s
          AND bm.is_active = TRUE
        LIMIT 1
        """,
        (str(organization_pk),),
    )
    row = cur.fetchone()
    assert row, f"No seeded SAKHA_GOVERNING_BODY shell for {organization_pk}."
    return str(row[0])


def _seat_exclusive(write_conn, *, organization_pk, position_code: str, person_pk, sangha_sevi_pk):
    """
    Seat person as *position_code* on the Sakha's Governing Body, first
    deactivating any other currently-active holder of that position (a dev DB
    may carry demo-seeded office-bearers; _require_review_authority matches ANY
    current holder, so a stale one would mask a negative test). Rolled back
    with the module SAVEPOINT.
    """
    body_pk = _sakha_gb_body_pk(write_conn, organization_pk)
    cur = write_conn.cursor()
    cur.execute(
        """
        UPDATE nss.body_member_assignment a
        SET is_active = FALSE, effective_to = CURRENT_DATE - 1, deleted_at = NOW()
        FROM nss.position_master pm
        WHERE a.position_master_pk = pm.position_master_pk
          AND a.body_master_pk = %s AND pm.position_code = %s
          AND a.is_active = TRUE AND a.effective_to IS NULL
        """,
        (body_pk, position_code),
    )
    _seat_office_bearer(
        write_conn, body_master_pk=body_pk, position_code=position_code,
        person_pk=person_pk, sangha_sevi_pk=sangha_sevi_pk,
    )


def _with_sevi_pk(write_conn, identity: dict) -> dict:
    """_create_admin_with_scope doesn't return sangha_sevi_pk; look it up."""
    cur = write_conn.cursor()
    cur.execute(
        "SELECT sangha_sevi_pk FROM nss.sangha_sevi WHERE sangha_sevi_id = %s",
        (identity["sangha_sevi_id"],),
    )
    return {**identity, "sangha_sevi_pk": str(cur.fetchone()[0])}


def _scoped_user(write_conn, *, role_code: str, organization_pk) -> dict:
    return _with_sevi_pk(
        write_conn,
        _create_admin_with_scope(
            write_conn, role_code=role_code, scope_level="SAKHA", organization_pk=organization_pk,
        ),
    )


def new_member(write_conn, org_pk, label: str = "AttMember") -> dict:
    """A fresh active REGULAR member homed at *org_pk* (own identity, no history)."""
    return _create_person_with_login(write_conn, label, organization_pk=org_pk)


def make_puja(client, headers, sakha_pk, puja_date: date, remarks: str | None = None) -> dict:
    r = client.post(
        f"{BASE}/pujas",
        json={"sakha_pk": str(sakha_pk), "puja_date": puja_date.isoformat(), "remarks": remarks},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def mark(client, headers, puja_pk, *items) -> dict:
    """items: (sangha_sevi_pk, status_code[, remarks]) tuples."""
    records = [
        {"sangha_sevi_pk": i[0], "attendance_status_code": i[1], **({"remarks": i[2]} if len(i) > 2 else {})}
        for i in items
    ]
    r = client.post(f"{BASE}/pujas/{puja_pk}/attendance", json={"records": records}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def sakha_pks(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        JOIN nss.body_master bm ON bm.organization_pk = o.organization_pk AND bm.is_active = TRUE
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
          AND bt.body_type_code = 'SAKHA_GOVERNING_BODY'
        ORDER BY o.organization_pk LIMIT 2
    """)
    pks = [str(r[0]) for r in cur.fetchall()]
    if len(pks) < 2:
        pytest.skip("Need two active SAKHA_SANGHA organizations with a Governing Body shell.")
    return pks


@pytest.fixture(scope="module")
def register_org_pk(sakha_pks):
    return sakha_pks[0]


@pytest.fixture(scope="module")
def other_org_pk(sakha_pks):
    """A Sakha OUTSIDE every scoped test user's scope (except other_*)."""
    return sakha_pks[1]


@pytest.fixture(scope="module")
def admin_user(write_conn):
    return _with_sevi_pk(
        write_conn,
        _create_admin_with_scope(
            write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None,
        ),
    )


@pytest.fixture(scope="module")
def sakha_admin(write_conn, register_org_pk):
    return _scoped_user(write_conn, role_code="NSS_ERP_SAKHA_ADMIN", organization_pk=register_org_pk)


@pytest.fixture(scope="module")
def marker_user(write_conn, register_org_pk):
    return _scoped_user(write_conn, role_code="NSS_ERP_ATTENDANCE_MARKER", organization_pk=register_org_pk)


@pytest.fixture(scope="module")
def secretary_user(write_conn, register_org_pk):
    u = _scoped_user(write_conn, role_code="NSS_ERP_SAKHA_ADMIN", organization_pk=register_org_pk)
    _seat_exclusive(write_conn, organization_pk=register_org_pk, position_code="SECRETARY",
                    person_pk=u["person_pk"], sangha_sevi_pk=u["sangha_sevi_pk"])
    return u


@pytest.fixture(scope="module")
def president_user(write_conn, register_org_pk):
    u = _scoped_user(write_conn, role_code="NSS_ERP_SAKHA_ADMIN", organization_pk=register_org_pk)
    _seat_exclusive(write_conn, organization_pk=register_org_pk, position_code="PRESIDENT",
                    person_pk=u["person_pk"], sangha_sevi_pk=u["sangha_sevi_pk"])
    return u


@pytest.fixture(scope="module")
def other_admin(write_conn, other_org_pk):
    return _scoped_user(write_conn, role_code="NSS_ERP_SAKHA_ADMIN", organization_pk=other_org_pk)


@pytest.fixture(scope="module")
def other_president(write_conn, other_org_pk):
    u = _scoped_user(write_conn, role_code="NSS_ERP_SAKHA_ADMIN", organization_pk=other_org_pk)
    _seat_exclusive(write_conn, organization_pk=other_org_pk, position_code="PRESIDENT",
                    person_pk=u["person_pk"], sangha_sevi_pk=u["sangha_sevi_pk"])
    return u


@pytest.fixture(scope="module")
def plain_member(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "AttPlain")


def _headers_fixture(name: str, user_fixture_name: str):
    @pytest.fixture(scope="module", name=name)
    def _fx(client, request):
        u = request.getfixturevalue(user_fixture_name)
        return _login_headers(client, u["sangha_sevi_id"], u["password"])
    return _fx


admin_h = _headers_fixture("admin_h", "admin_user")
sakha_admin_h = _headers_fixture("sakha_admin_h", "sakha_admin")
marker_h = _headers_fixture("marker_h", "marker_user")
secretary_h = _headers_fixture("secretary_h", "secretary_user")
president_h = _headers_fixture("president_h", "president_user")
other_admin_h = _headers_fixture("other_admin_h", "other_admin")
other_president_h = _headers_fixture("other_president_h", "other_president")
plain_member_h = _headers_fixture("plain_member_h", "plain_member")


@pytest.fixture(scope="module")
def register_pujas(client, admin_h, register_org_pk):
    """Five consecutive weekly pujas (2001) at the register Sakha."""
    return [make_puja(client, admin_h, register_org_pk, d) for d in PUJA_DATES]
