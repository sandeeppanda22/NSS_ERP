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

import pytest
from uuid import uuid4

pytestmark = pytest.mark.integration

BASE = "/api/v1/correspondence"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

ADMIN_PASSWORD = "CorrAdminPass1"
SCOPED_PASSWORD = "CorrScopedPass1"


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
        self._assign_org_responsible(client, admin_headers, pk, register_org_pk)
        r1 = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"}, headers=admin_headers)
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"{BASE}/{pk}/transition", json={"new_status": "CLOSED"}, headers=admin_headers)
        assert r2.status_code == 422, r2.text
        assert "not a valid transition" in r2.json()["detail"].lower()

    def test_pending_action_requires_responsible_party(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"}, headers=admin_headers)
        assert r.status_code == 422, r.text
        assert "responsible" in r.json()["detail"].lower()

    def test_pending_action_after_responsible_assigned(self, client, admin_headers, register_org_pk):
        pk = _create(client, admin_headers, register_org_pk)["correspondence_pk"]
        self._assign_org_responsible(client, admin_headers, pk, register_org_pk)
        r = client.post(f"{BASE}/{pk}/transition", json={"new_status": "PENDING_ACTION"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status_value_code"] == "PENDING_ACTION"

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
        # Clear it — no status change, still REGISTERED
        r2 = client.post(f"{BASE}/{pk}/responsible-party", json={}, headers=admin_headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["responsible_organization_pk"] is None
        assert r2.json()["status_value_code"] == "REGISTERED"

    def test_assign_missing_record_404(self, client, admin_headers, register_org_pk):
        r = client.post(
            f"{BASE}/{FAKE_UUID}/responsible-party",
            json={"responsible_organization_pk": register_org_pk},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text


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
