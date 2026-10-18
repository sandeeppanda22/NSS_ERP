"""
NSS ERP — Member Credential Administration API tests (MBR-010/019B/030H).

Integration tests for the four admin endpoints that round out per-member
credential management:

  GET  /api/v1/admin/credentials/members                      — per-member
                                                                   credential health
  GET  /api/v1/admin/credentials/members/{pk}/timeline          — full Anumati +
                                                                   Parichaya history
  POST /api/v1/admin/credentials/members/{pk}/issue             — issue/renew the
                                                                   expected credential
  POST /api/v1/admin/credentials/members/{pk}/promote           — Darshaka -> Regular
                                                                   (MBR-010/011A/030C)

These tests run against local PostgreSQL and roll back via conftest's
module-scoped SAVEPOINT — no manual cleanup needed.

Auth-gating (401/403) is deliberately not re-tested here — see
tests/security/ for that and tests/api/test_claim_approval.py's header
note for the convention this file follows. This file is about the
business logic: credential-health classification, the timeline shape,
issuance edge cases, and the promotion sequence end to end.

Every write that resolves a default issue/valid date passes those dates
explicitly, so none of these tests depend on the seeded Dola Purnima
festival-reference calendar being populated for any particular year —
only the promotion-default-date behaviour (left to the UI/manual path)
relies on that calendar, and no test here exercises the omitted-
effective_date branch for that reason.
"""

import pytest
from uuid import uuid4


pytestmark = pytest.mark.integration

TEST_PASSWORD = "CredTest1x"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_tokens(client, write_conn):
    """
    NSS-WIDE admin holding ADMIN_USER_MANAGE — satisfies every permission
    gate the credential endpoints check (MEMBERSHIP_VIEW/MANAGE or
    ADMIN_USER_MANAGE) and the sangha-sevi creation endpoint used below to
    build fixture members (ADMIN_USER_MANAGE or PERSON_MANAGE).

    Scavenges an existing admin rather than building one from scratch —
    mirrors tests/api/test_claim_approval.py's admin_tokens fixture.
    """
    cur = write_conn.cursor()
    cur.execute("""
        SELECT ua.user_account_pk, ss.sangha_sevi_id
        FROM nss.user_account ua
        JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk AND ss.is_active = TRUE
        JOIN nss.user_role ur ON ur.user_account_pk = ua.user_account_pk AND ur.is_active = TRUE
        JOIN nss.role_permission rp ON rp.role_master_pk = ur.role_master_pk AND rp.is_active = TRUE
        JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
        JOIN nss.admin_scope asc2 ON asc2.user_role_pk = ur.user_role_pk
                                   AND asc2.is_active = TRUE
                                   AND asc2.scope_level = 'NSS-WIDE'
        WHERE ua.is_active = TRUE
          AND ua.account_status = 'ACTIVE'
          AND pm.permission_code = 'ADMIN_USER_MANAGE'
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No NSS-WIDE admin with ADMIN_USER_MANAGE found.")
    admin_pk, sevi_id = row

    from api.services.auth_service import hash_password
    cur.execute("""
        UPDATE nss.user_account
        SET password_hash = %s, password_changed_at = NOW(),
            password_expires_at = NOW() + INTERVAL '365 days'
        WHERE user_account_pk = %s
    """, (hash_password(TEST_PASSWORD), str(admin_pk)))

    resp = client.post("/api/v1/auth/login", json={
        "login_id": sevi_id, "password": TEST_PASSWORD,
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.json()}")
    return resp.json()


@pytest.fixture(scope="module")
def admin_headers(admin_tokens):
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}


@pytest.fixture(scope="module")
def sakha_org_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No active SAKHA_SANGHA organization exists.")
    return str(row[0])


@pytest.fixture(scope="module")
def membership_type_pks(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.value_code, md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE'
          AND md.value_code IN ('PROBATIONARY', 'REGULAR') AND md.is_active = TRUE
    """)
    out = {code: str(pk) for code, pk in cur.fetchall()}
    if "PROBATIONARY" not in out or "REGULAR" not in out:
        pytest.skip("PROBATIONARY/REGULAR membership types must exist.")
    return out


@pytest.fixture(scope="module")
def active_status_pk(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE' AND md.is_active = TRUE
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("STATUS/ACTIVE master data is missing.")
    return str(row[0])


def _create_person(write_conn, label):
    """Dedicated throwaway person — never scavenged, per project convention."""
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()
    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s)
        RETURNING person_pk
    """, (
        f"T{label}{suffix}", f"Test{label}", suffix,
        f"t{label.lower()}.{suffix.lower()}@example.test",
    ))
    return cur.fetchone()[0]


def _create_darshaka_member(client, admin_headers, write_conn, sakha_org_pk, membership_type_pks):
    """
    Create a fresh Darshaka (PROBATIONARY) Sangha Sevi with an ACTIVE
    Anumati Patra and an open Darshak-namespace Sakha affiliation, via the
    real POST /admin/sangha-sevi path — so fixture data is produced the
    same way a real admin produces it, not hand-crafted to match what the
    credentials endpoints expect.

    Explicit credential_valid_from/_to sidestep the Dola Purnima validity-
    window default (no dependency on which festival years are seeded);
    a random local_sakha_erp_id avoids colliding with other tests/parallel
    runs in the same Sakha's Darshak namespace.
    """
    person_pk = _create_person(write_conn, "DRSK")
    local_number = str(uuid4().int)[:6]
    resp = client.post(
        "/api/v1/admin/sangha-sevi",
        headers=admin_headers,
        json={
            "person_pk": str(person_pk),
            "membership_type_pk": membership_type_pks["PROBATIONARY"],
            "organization_pk": sakha_org_pk,
            "joining_date": "2024-01-15",
            "local_sakha_erp_id": local_number,
            "credential_issue_date": "2024-01-15",
            "credential_valid_from": "2024-01-15",
            "credential_valid_to": "2030-01-01",
        },
    )
    assert resp.status_code == 201, f"Darshaka fixture creation failed: {resp.text}"
    data = resp.json()
    return {
        "sangha_sevi_pk": data["sangha_sevi_pk"],
        "sangha_sevi_id": data["sangha_sevi_id"],
        "person_pk": str(person_pk),
    }


def _create_member_without_credential(write_conn, sakha_org_pk, membership_type_pk, active_status_pk, label):
    """
    Insert a Sangha Sevi directly, with NO credential and NO Sakha
    affiliation. create_sangha_sevi() always issues the mandatory
    credential (MBR-010/014), so a MISSING-state member can't be produced
    through the normal API — this is the one place a direct INSERT is the
    right tool, not a shortcut around it.
    """
    cur = write_conn.cursor()
    person_pk = _create_person(write_conn, label)
    suffix = uuid4().hex[:8].upper()
    ss_id = f"T{label}{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2024-01-15')
        RETURNING sangha_sevi_pk
    """, (ss_id, str(person_pk), membership_type_pk, active_status_pk, sakha_org_pk))
    ss_pk = cur.fetchone()[0]
    return {"sangha_sevi_pk": str(ss_pk), "sangha_sevi_id": ss_id, "person_pk": str(person_pk)}


@pytest.fixture(scope="module")
def darshaka_member(client, admin_headers, write_conn, sakha_org_pk, membership_type_pks):
    """A single Darshaka member shared by the read-only list/timeline tests."""
    return _create_darshaka_member(client, admin_headers, write_conn, sakha_org_pk, membership_type_pks)


@pytest.fixture(scope="module")
def missing_regular_member(write_conn, sakha_org_pk, membership_type_pks, active_status_pk):
    """REGULAR Sangha Sevi with no Parichaya Patra — expected MISSING."""
    return _create_member_without_credential(
        write_conn, sakha_org_pk, membership_type_pks["REGULAR"], active_status_pk, "MISSR",
    )


@pytest.fixture(scope="module")
def missing_probationary_member(write_conn, sakha_org_pk, membership_type_pks, active_status_pk):
    """PROBATIONARY Sangha Sevi with no Anumati Patra — expected MISSING."""
    return _create_member_without_credential(
        write_conn, sakha_org_pk, membership_type_pks["PROBATIONARY"], active_status_pk, "MISSP",
    )


# ── GET /credentials/members ────────────────────────────────────────────

class TestListMemberCredentials:
    def test_list_shape(self, client, admin_headers):
        resp = client.get(
            "/api/v1/admin/credentials/members?page=1&page_size=5",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert {"members", "total", "page", "page_size"} <= data.keys()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert isinstance(data["members"], list)

    def test_filter_by_membership_type_probationary(self, client, admin_headers, darshaka_member):
        # Combine with search, same reasoning as test_filter_by_state_missing:
        # a page_size cap can't guarantee the fixture row survives against
        # however many real PROBATIONARY members already exist.
        resp = client.get(
            f"/api/v1/admin/credentials/members?membership_type=PROBATIONARY"
            f"&search={darshaka_member['sangha_sevi_id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        rows = {m["sangha_sevi_id"]: m for m in resp.json()["members"]}
        assert darshaka_member["sangha_sevi_id"] in rows
        row = rows[darshaka_member["sangha_sevi_id"]]
        assert row["expected_card_type"] == "ANUMATI_PATRA"
        assert row["credential_state"] == "OK"
        assert row["credential_document_number"]

    def test_filter_by_state_missing(self, client, admin_headers, missing_regular_member):
        # state=MISSING alone can have more real MISSING rows than one page
        # holds (page_size is capped at 200) — combine with search so the
        # fixture member is found regardless of how much live data exists,
        # rather than widening the page to chase a growing haystack.
        resp = client.get(
            f"/api/v1/admin/credentials/members?state=MISSING"
            f"&search={missing_regular_member['sangha_sevi_id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        rows = {m["sangha_sevi_id"]: m for m in resp.json()["members"]}
        assert missing_regular_member["sangha_sevi_id"] in rows
        row = rows[missing_regular_member["sangha_sevi_id"]]
        assert row["expected_card_type"] == "PARICHAYA_PATRA"
        assert row["credential_document_number"] is None

    def test_search_by_sangha_sevi_id(self, client, admin_headers, darshaka_member):
        resp = client.get(
            f"/api/v1/admin/credentials/members?search={darshaka_member['sangha_sevi_id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        ids = [m["sangha_sevi_id"] for m in resp.json()["members"]]
        assert darshaka_member["sangha_sevi_id"] in ids

    def test_invalid_state_value_rejected(self, client, admin_headers):
        resp = client.get(
            "/api/v1/admin/credentials/members?state=BOGUS",
            headers=admin_headers,
        )
        assert resp.status_code == 422


# ── GET /credentials/members/{pk}/timeline ──────────────────────────────

class TestMemberCredentialTimeline:
    def test_timeline_darshaka(self, client, admin_headers, darshaka_member):
        resp = client.get(
            f"/api/v1/admin/credentials/members/{darshaka_member['sangha_sevi_pk']}/timeline",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sangha_sevi_id"] == darshaka_member["sangha_sevi_id"]
        assert len(data["entries"]) == 1
        entry = data["entries"][0]
        assert entry["card_type"] == "ANUMATI_PATRA"
        assert entry["status"] == "ACTIVE"
        assert len(entry["history"]) == 1
        assert entry["history"][0]["change_type"] == "ISSUED"
        assert entry["history"][0]["new_status"] == "ACTIVE"
        assert entry["history"][0]["previous_status"] is None

    def test_timeline_not_found(self, client, admin_headers):
        resp = client.get(
            f"/api/v1/admin/credentials/members/{uuid4()}/timeline",
            headers=admin_headers,
        )
        assert resp.status_code == 404


# ── POST /credentials/members/{pk}/issue ────────────────────────────────

class TestIssueCredential:
    def test_issue_conflict_when_active_credential_exists(self, client, admin_headers, darshaka_member):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{darshaka_member['sangha_sevi_pk']}/issue",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 409

    def test_issue_auto_mints_for_missing_member(self, client, admin_headers, missing_regular_member):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{missing_regular_member['sangha_sevi_pk']}/issue",
            headers=admin_headers,
            json={
                "issue_date": "2026-10-12",
                "valid_from": "2026-10-12",
                "valid_to": "2030-01-01",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["card_type"] == "PARICHAYA_PATRA"
        assert data["document_number"]
        assert data["sangha_sevi_pk"] == missing_regular_member["sangha_sevi_pk"]

    def test_issue_with_manual_document_number(self, client, admin_headers, missing_probationary_member):
        manual_number = str(uuid4().int)[:5]
        resp = client.post(
            f"/api/v1/admin/credentials/members/{missing_probationary_member['sangha_sevi_pk']}/issue",
            headers=admin_headers,
            json={
                "document_number": manual_number,
                "issue_date": "2026-10-12",
                "valid_from": "2026-10-12",
                "valid_to": "2030-01-01",
                "remarks": "Legacy card entered by hand",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["card_type"] == "ANUMATI_PATRA"
        assert manual_number in data["document_number"]

    def test_issue_not_found(self, client, admin_headers):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{uuid4()}/issue",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 404


# ── POST /credentials/members/{pk}/promote ──────────────────────────────

class TestPromoteToRegular:
    def test_promote_requires_probationary(self, client, admin_headers, missing_regular_member):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{missing_regular_member['sangha_sevi_pk']}/promote",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 422
        assert "darshaka" in resp.json()["detail"].lower()

    def test_promote_not_found(self, client, admin_headers):
        resp = client.post(
            f"/api/v1/admin/credentials/members/{uuid4()}/promote",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 404

    def test_promote_success(self, client, admin_headers, write_conn, sakha_org_pk, membership_type_pks):
        member = _create_darshaka_member(client, admin_headers, write_conn, sakha_org_pk, membership_type_pks)

        resp = client.post(
            f"/api/v1/admin/credentials/members/{member['sangha_sevi_pk']}/promote",
            headers=admin_headers,
            json={"effective_date": "2026-10-12", "remarks": "test promotion"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["previous_membership_type_code"] == "PROBATIONARY"
        assert data["new_membership_type_code"] == "REGULAR"
        assert data["expired_anumati_patra_pk"] is not None
        assert data["parichaya_document_number"]
        assert data["archived_affiliation_local_id"] is not None
        assert data["new_affiliation_local_id"] is not None
        assert data["archived_affiliation_local_id"] != data["new_affiliation_local_id"]
        assert data["effective_date"] == "2026-10-12"

        cur = write_conn.cursor()

        # Membership type actually flipped.
        cur.execute(
            """
            SELECT mt.value_code FROM nss.sangha_sevi ss
            JOIN nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk
            WHERE ss.sangha_sevi_pk = %s
            """,
            (member["sangha_sevi_pk"],),
        )
        assert cur.fetchone()[0] == "REGULAR"

        # Old Anumati Patra preserved, not deleted, marked EXPIRED (MBR-019C).
        cur.execute(
            "SELECT status FROM nss.anumati_patra WHERE anumati_patra_pk = %s",
            (data["expired_anumati_patra_pk"],),
        )
        assert cur.fetchone()[0] == "EXPIRED"

        # Exactly one open Sakha affiliation after the archive/open swap.
        cur.execute(
            """
            SELECT COUNT(*) FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = %s AND effective_to IS NULL
            """,
            (member["sangha_sevi_pk"],),
        )
        assert cur.fetchone()[0] == 1

    def test_promote_twice_refused(self, client, admin_headers, write_conn, sakha_org_pk, membership_type_pks):
        member = _create_darshaka_member(client, admin_headers, write_conn, sakha_org_pk, membership_type_pks)

        first = client.post(
            f"/api/v1/admin/credentials/members/{member['sangha_sevi_pk']}/promote",
            headers=admin_headers,
            json={"effective_date": "2026-10-12"},
        )
        assert first.status_code == 200, first.text

        second = client.post(
            f"/api/v1/admin/credentials/members/{member['sangha_sevi_pk']}/promote",
            headers=admin_headers,
            json={"effective_date": "2026-10-12"},
        )
        assert second.status_code == 422

    def test_promote_then_timeline_shows_both_credentials(
        self, client, admin_headers, write_conn, sakha_org_pk, membership_type_pks,
    ):
        """
        The core feature intent (MBR-010/019C): after promotion, a member's
        timeline shows their EXPIRED Anumati Patra followed by their ACTIVE
        Parichaya Patra — never a gap, never a silently-replaced row.
        """
        member = _create_darshaka_member(client, admin_headers, write_conn, sakha_org_pk, membership_type_pks)

        promote_resp = client.post(
            f"/api/v1/admin/credentials/members/{member['sangha_sevi_pk']}/promote",
            headers=admin_headers,
            json={"effective_date": "2026-10-12"},
        )
        assert promote_resp.status_code == 200, promote_resp.text

        timeline_resp = client.get(
            f"/api/v1/admin/credentials/members/{member['sangha_sevi_pk']}/timeline",
            headers=admin_headers,
        )
        assert timeline_resp.status_code == 200
        entries = timeline_resp.json()["entries"]
        assert len(entries) == 2
        assert entries[0]["card_type"] == "ANUMATI_PATRA"
        assert entries[0]["status"] == "EXPIRED"
        assert entries[1]["card_type"] == "PARICHAYA_PATRA"
        assert entries[1]["status"] == "ACTIVE"
        assert entries[1]["local_sakha_erp_id"] is not None
