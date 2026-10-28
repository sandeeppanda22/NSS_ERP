"""
NSS ERP — Security tests for the Correspondence Register
(api/routers/correspondence.py).

Focus: admin-scope negatives (require_org_in_scope — six distinct exact
error strings, one per mutating endpoint), permission negatives (no
CORRESPONDENCE_MANAGE at all), and anonymous-access negatives that are
NOT already covered by the happy-path assertions in
tests/api/test_correspondence.py.

Exact error strings asserted verbatim against the router source
(api/routers/correspondence.py):
  - create_correspondence:        "You can only register correspondence for this organization within your admin scope."
  - transition_status:            "You can only transition this correspondence record within your admin scope."
  - assign_responsible_party:     "You can only reassign responsibility for this correspondence record within your admin scope."
  - associate_document:           "You can only attach a document to this correspondence record within your admin scope."
  - associate_finance_reference:  "You can only reference a finance transaction from this correspondence record within your admin scope."

get_correspondence uses a DIFFERENT (non-require_org_in_scope) code path
with a DIFFERENT message — "This correspondence record is outside your
admin scope." — covered separately below.
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/correspondence"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "CorrSecAdminPass1"
SCOPED_PASSWORD = "CorrSecScopedPass1"
MEMBER_PASSWORD = "CorrSecMemberPass1"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — mirrors tests/api/test_correspondence.py's admin builder,
# plus a plain member (no CORRESPONDENCE_MANAGE at all).
# ═══════════════════════════════════════════════════════════════════════

def _membership_type_pk(write_conn, value_code: str = "REGULAR"):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = %s AND md.is_active = TRUE
        LIMIT 1
    """, (value_code,))
    row = cur.fetchone()
    assert row, f"MEMBERSHIP_TYPE '{value_code}' not seeded."
    return row[0]


def _membership_status_active_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    assert row, "STATUS 'ACTIVE' not seeded."
    return row[0]


def _create_admin_with_scope(write_conn, *, role_code: str, scope_level: str, organization_pk):
    """
    Build a dedicated person + sangha_sevi + user_account + user_role +
    admin_scope row. Everything rolls back with the module SAVEPOINT.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    membership_type_pk = _membership_type_pk(write_conn)
    membership_status_pk = _membership_status_active_pk(write_conn)

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
    """, (f"CSADM{suffix}", "CorrSecAdmin", suffix, f"csadm.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"CSADMSS{suffix}"
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
        "person_pk": str(person_pk),
        "sangha_sevi_id": sangha_sevi_id,
        "password": password,
        "organization_pk": str(home_organization_pk),
    }


def _create_plain_member(write_conn, home_org_pk: str):
    """A member with a user_account but NO role at all — no CORRESPONDENCE_MANAGE."""
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()

    membership_type_pk = _membership_type_pk(write_conn)
    membership_status_pk = _membership_status_active_pk(write_conn)

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (f"CSMEM{suffix}", "CorrSecMember", suffix, f"csmem.{suffix.lower()}@example.test"))
    person_pk = cur.fetchone()[0]

    sangha_sevi_id = f"CSMEMSS{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
    """, (sangha_sevi_id, str(person_pk), str(membership_type_pk),
          str(membership_status_pk), str(home_org_pk)))

    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status, force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
    """, (str(person_pk), hash_password(MEMBER_PASSWORD)))

    return {"sangha_sevi_id": sangha_sevi_id, "password": MEMBER_PASSWORD, "person_pk": str(person_pk)}


def _login_headers(client, login_id: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _two_active_sakha_pks(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.organization_pk LIMIT 2
    """)
    return [str(r[0]) for r in cur.fetchall()]


@pytest.fixture(scope="module")
def two_sakha_pks(write_conn):
    pks = _two_active_sakha_pks(write_conn)
    if len(pks) < 2:
        pytest.skip("Need at least two active SAKHA_SANGHA organizations.")
    return pks


@pytest.fixture(scope="module")
def register_org_pk(two_sakha_pks):
    """The org correspondence will be registered under."""
    return two_sakha_pks[0]


@pytest.fixture(scope="module")
def outside_org_pk(two_sakha_pks):
    """A different org — OUTSIDE the scoped admin's scope."""
    return two_sakha_pks[1]


@pytest.fixture(scope="module")
def nss_wide_admin(write_conn):
    """NSS-WIDE NSS_ERP_ADMIN — holds CORRESPONDENCE_VIEW + MANAGE everywhere."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None,
    )


@pytest.fixture(scope="module")
def nss_wide_headers(client, nss_wide_admin):
    return _login_headers(client, nss_wide_admin["sangha_sevi_id"], nss_wide_admin["password"])


@pytest.fixture(scope="module")
def outside_scoped_admin(write_conn, outside_org_pk):
    """A SAKHA-scoped admin whose scope is OUTSIDE register_org_pk."""
    return _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_SAKHA_ADMIN", scope_level="SAKHA", organization_pk=outside_org_pk,
    )


@pytest.fixture(scope="module")
def outside_scoped_headers(client, outside_scoped_admin):
    return _login_headers(client, outside_scoped_admin["sangha_sevi_id"], outside_scoped_admin["password"])


@pytest.fixture(scope="module")
def plain_member(write_conn, register_org_pk):
    return _create_plain_member(write_conn, register_org_pk)


@pytest.fixture(scope="module")
def member_headers(client, plain_member):
    return _login_headers(client, plain_member["sangha_sevi_id"], plain_member["password"])


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
        (f"Corr sec test doc {uuid4().hex[:8]}", f"/tmp/corr-sec-{uuid4().hex[:8]}"),
    )
    return str(cur.fetchone()[0])


def _payload(org_pk, *, direction="INWARD", subject="Security test correspondence"):
    """Minimal valid CorrespondenceCreate — EXTERNAL sender + recipient, non-future dates."""
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
# create_correspondence — admin-scope negative
# ═══════════════════════════════════════════════════════════════════════

class TestCreateScope:
    def test_out_of_scope_admin_cannot_register(self, client, outside_scoped_headers, register_org_pk):
        r = client.post(BASE, json=_payload(register_org_pk), headers=outside_scoped_headers)
        assert r.status_code == 403
        assert (
            "You can only register correspondence for this organization within your admin scope."
            in r.text
        )

    def test_nss_wide_admin_can_register_anywhere(self, client, nss_wide_headers, register_org_pk):
        r = client.post(BASE, json=_payload(register_org_pk), headers=nss_wide_headers)
        assert r.status_code == 201, r.text


# ═══════════════════════════════════════════════════════════════════════
# get_correspondence — DIFFERENT scope-check code path / message
# ═══════════════════════════════════════════════════════════════════════

class TestGetScope:
    def test_out_of_scope_admin_cannot_view(self, client, nss_wide_headers, outside_scoped_headers, register_org_pk):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.get(f"{BASE}/{pk}", headers=outside_scoped_headers)
        assert r.status_code == 403
        assert "This correspondence record is outside your admin scope." in r.text

    def test_nss_wide_admin_can_view_anywhere(self, client, nss_wide_headers, register_org_pk):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.get(f"{BASE}/{pk}", headers=nss_wide_headers)
        assert r.status_code == 200, r.text


# ═══════════════════════════════════════════════════════════════════════
# transition_status — admin-scope negative (fires before any §6.2/§6.3
# business-rule validation)
# ═══════════════════════════════════════════════════════════════════════

class TestTransitionScope:
    def test_out_of_scope_admin_cannot_transition(
        self, client, nss_wide_headers, outside_scoped_headers, register_org_pk,
    ):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/transition",
            json={"new_status": "ACTIONED"},
            headers=outside_scoped_headers,
        )
        assert r.status_code == 403
        assert (
            "You can only transition this correspondence record within your admin scope."
            in r.text
        )


# ═══════════════════════════════════════════════════════════════════════
# assign_responsible_party — admin-scope negative
# ═══════════════════════════════════════════════════════════════════════

class TestResponsiblePartyScope:
    def test_out_of_scope_admin_cannot_assign(
        self, client, nss_wide_headers, outside_scoped_headers, register_org_pk,
    ):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=outside_scoped_headers,
        )
        assert r.status_code == 403
        assert (
            "You can only reassign responsibility for this correspondence record within your admin scope."
            in r.text
        )


# ═══════════════════════════════════════════════════════════════════════
# associate_document — admin-scope negative (fires before the
# document_master_pk FK is ever used — a fake UUID is safe here)
# ═══════════════════════════════════════════════════════════════════════

class TestDocumentScope:
    def test_out_of_scope_admin_cannot_attach(
        self, client, nss_wide_headers, outside_scoped_headers, register_org_pk,
    ):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/documents",
            json={"document_master_pk": FAKE_UUID, "document_purpose": "ORIGINAL"},
            headers=outside_scoped_headers,
        )
        assert r.status_code == 403
        assert (
            "You can only attach a document to this correspondence record within your admin scope."
            in r.text
        )

    def test_nss_wide_admin_can_attach_anywhere(
        self, client, nss_wide_headers, register_org_pk, document_master_pk,
    ):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/documents",
            json={"document_master_pk": document_master_pk, "document_purpose": "ORIGINAL"},
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text


# ═══════════════════════════════════════════════════════════════════════
# associate_finance_reference — admin-scope negative (fires before the
# financial_transaction_pk is ever used — there's no FK yet, Tier 12,
# so a fake UUID is safe for both the scope-negative AND happy-path case)
# ═══════════════════════════════════════════════════════════════════════

class TestFinanceReferenceScope:
    def test_out_of_scope_admin_cannot_reference(
        self, client, nss_wide_headers, outside_scoped_headers, register_org_pk,
    ):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/finance-references",
            json={"financial_transaction_pk": str(uuid4()), "relationship_type": "PAYMENT"},
            headers=outside_scoped_headers,
        )
        assert r.status_code == 403
        assert (
            "You can only reference a finance transaction from this correspondence record "
            "within your admin scope." in r.text
        )

    def test_nss_wide_admin_can_reference_anywhere(self, client, nss_wide_headers, register_org_pk):
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/finance-references",
            json={"financial_transaction_pk": str(uuid4()), "relationship_type": "PAYMENT"},
            headers=nss_wide_headers,
        )
        assert r.status_code == 201, r.text


# ═══════════════════════════════════════════════════════════════════════
# Permission negatives (no CORRESPONDENCE_MANAGE / CORRESPONDENCE_VIEW
# at all — plain member holds neither)
# ═══════════════════════════════════════════════════════════════════════

class TestNoCorrespondencePermission:
    def test_create_requires_manage_permission(self, client, member_headers, register_org_pk):
        r = client.post(BASE, json=_payload(register_org_pk), headers=member_headers)
        assert r.status_code == 403

    def test_list_requires_view_permission(self, client, member_headers):
        r = client.get(BASE, headers=member_headers)
        assert r.status_code == 403

    def test_get_requires_view_permission(self, client, member_headers):
        r = client.get(f"{BASE}/{FAKE_UUID}", headers=member_headers)
        assert r.status_code == 403

    def test_transition_requires_manage_permission(self, client, nss_wide_headers, member_headers, register_org_pk):
        """
        PART 2 changed /transition's authority model (owner-confirmed
        2026-10-22, see _require_directed_authority in
        api/routers/correspondence.py): it no longer checks
        CORRESPONDENCE_MANAGE directly, so a FAKE_UUID 404 would short-
        circuit before any permission is even evaluated. This now uses a
        REAL EXTERNAL-recipient record — the one row shape with no
        directed human authority, which still falls back to the
        pre-existing CORRESPONDENCE_MANAGE + admin-scope gate — so a
        plain member genuinely lacking that permission still gets 403.
        """
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/transition", json={"new_status": "ACTIONED"}, headers=member_headers,
        )
        assert r.status_code == 403

    def test_responsible_party_requires_manage_permission(self, client, nss_wide_headers, member_headers, register_org_pk):
        """See test_transition_requires_manage_permission's note above —
        same PART 2 authority-model change, same EXTERNAL-recipient
        fallback-path fixture."""
        pk = _create(client, nss_wide_headers, register_org_pk)["correspondence_pk"]
        r = client.post(
            f"{BASE}/{pk}/responsible-party", json={}, headers=member_headers,
        )
        assert r.status_code == 403

    def test_documents_requires_manage_permission(self, client, member_headers):
        r = client.post(
            f"{BASE}/{FAKE_UUID}/documents",
            json={"document_master_pk": FAKE_UUID, "document_purpose": "ORIGINAL"},
            headers=member_headers,
        )
        assert r.status_code == 403

    def test_finance_references_requires_manage_permission(self, client, member_headers):
        r = client.post(
            f"{BASE}/{FAKE_UUID}/finance-references",
            json={"financial_transaction_pk": str(uuid4()), "relationship_type": "PAYMENT"},
            headers=member_headers,
        )
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Anonymous access
# ═══════════════════════════════════════════════════════════════════════

class TestAnonymousAccess:
    def test_create_requires_auth(self, anon_client, register_org_pk):
        r = anon_client.post(BASE, json=_payload(register_org_pk))
        assert r.status_code in (401, 403)

    def test_list_requires_auth(self, anon_client):
        r = anon_client.get(BASE)
        assert r.status_code in (401, 403)

    def test_get_requires_auth(self, anon_client):
        r = anon_client.get(f"{BASE}/{FAKE_UUID}")
        assert r.status_code in (401, 403)

    def test_transition_requires_auth(self, anon_client):
        r = anon_client.post(f"{BASE}/{FAKE_UUID}/transition", json={"new_status": "ACTIONED"})
        assert r.status_code in (401, 403)

    def test_responsible_party_requires_auth(self, anon_client):
        r = anon_client.post(f"{BASE}/{FAKE_UUID}/responsible-party", json={})
        assert r.status_code in (401, 403)

    def test_documents_requires_auth(self, anon_client):
        r = anon_client.post(
            f"{BASE}/{FAKE_UUID}/documents",
            json={"document_master_pk": FAKE_UUID, "document_purpose": "ORIGINAL"},
        )
        assert r.status_code in (401, 403)

    def test_finance_references_requires_auth(self, anon_client):
        r = anon_client.post(
            f"{BASE}/{FAKE_UUID}/finance-references",
            json={"financial_transaction_pk": str(uuid4()), "relationship_type": "PAYMENT"},
        )
        assert r.status_code in (401, 403)
