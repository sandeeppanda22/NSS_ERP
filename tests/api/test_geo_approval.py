"""
NSS ERP — Geo-Entry Approval router coverage (api/routers/geo_approval.py).

The Member-Assisted Geographic Entry approval queue (SOL-ARCH-010
Amendment, 2026-10-03; SOL-FND-004 §16.8, FND-BR-085 .. FND-BR-090) had
no dedicated test file. Members may type an unseen district / postal-code /
post-office / city-village value; it lands as entry_status='PENDING' and a
FOUNDATION_MANAGE admin either approves it (-> APPROVED) or corrects it
(find-or-create canonical, -> CORRECTED, re-point dependent
person_address FKs). This file exercises the generic
list/detail/approve/correct handlers across all four entities, plus the
scope-authority enforcement (ADMIN-BR-076) that anchors each entry through
its submitter's sangha_sevi.organization_pk.

Endpoints covered:
  GET  /api/v1/admin/geo-entries/{entity}             — list (scoped, status filter)
  GET  /api/v1/admin/geo-entries/{entity}/{pk}        — detail (found, 404, scope-denied)
  POST /api/v1/admin/geo-entries/{entity}/{pk}/approve — PENDING->APPROVED, 422 non-pending,
                                                          409 duplicate, scope-denied, in-scope OK
  POST /api/v1/admin/geo-entries/{entity}/{pk}/correct — find-or-create canonical,
                                                          422 non-pending, scope-denied

Auth-gating (401/403-for-missing-permission) lives in tests/security/;
this file focuses on business-logic and scoping correctness for
authenticated, permitted admins (global vs scope-bounded).

NOTE: cleanup is automatic via transaction rollback in conftest.py.
"""

import random
import pytest
from uuid import uuid4

from tests.registration_support import add_user_account


pytestmark = pytest.mark.integration


# ── Test constants ──────────────────────────────────────────────────────

ADMIN_PASSWORD = "GeoAdmin1x"
SCOPED_PASSWORD = "GeoScoped1x"

ENTITIES = ["district", "postal-code", "post-office", "city-village"]


# ── Helpers ─────────────────────────────────────────────────────────────

def _rand_pin() -> str:
    return str(random.randint(100000, 999999))


def _create_sevi(cur, organization_pk):
    """
    Create a fresh person + active sangha_sevi anchored at organization_pk.

    A clean build seeds ZERO demo Person/Membership rows (Phase 8 of
    02_build.sh is intentionally empty — only the bootstrap admin P1/SS1
    exists), so these tests must create their own submitters and reviewers
    rather than borrow seeded ones. All of it is rolled back by conftest's
    module SAVEPOINT.

    organization_pk must be a SAKHA_SANGHA org — MBR-038A's
    sakha_only_membership_trigger rejects membership anywhere else.
    """
    suffix = uuid4().hex[:10].upper()

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR'
          AND md.is_active = TRUE LIMIT 1
    """)
    mtype = cur.fetchone()[0]

    cur.execute("""
        SELECT md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'STATUS' AND md.value_code = 'ACTIVE'
          AND md.is_active = TRUE LIMIT 1
    """)
    mstatus = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.person (person_id, first_name, last_name, email)
        VALUES (%s, %s, %s, %s) RETURNING person_pk
    """, (
        f"TGEO{suffix}", "TestGeo", suffix,
        f"tgeo.{suffix.lower()}@example.test",
    ))
    person_pk = cur.fetchone()[0]

    sevi_id = f"TSSGEO{suffix}"
    cur.execute("""
        INSERT INTO nss.sangha_sevi (
            sangha_sevi_id, person_pk, membership_type_master_data_pk,
            membership_status_master_data_pk, organization_pk, joining_date
        ) VALUES (%s, %s, %s, %s, %s, DATE '2020-04-01')
        RETURNING sangha_sevi_pk
    """, (
        sevi_id, str(person_pk), str(mtype), str(mstatus),
        str(organization_pk),
    ))
    sevi_pk = cur.fetchone()[0]

    return {
        "person_pk": str(person_pk),
        "sangha_sevi_pk": str(sevi_pk),
        "sangha_sevi_id": sevi_id,
    }


def _insert_pending(write_conn, entity, submitter_ss_pk, anchors):
    """Insert one PENDING row for *entity*, anchored to a submitter sangha_sevi.

    Returns the new entry_pk as a string. Anchor FKs (state / district /
    postal_code) come from the module `anchors` fixture.
    """
    sfx = uuid4().hex[:6]
    with write_conn.cursor() as cur:
        if entity == "district":
            cur.execute(
                "INSERT INTO nss.district "
                "(state_pk, district_code, district_name, entry_status, "
                " submitted_by_sangha_sevi_pk) "
                "VALUES (%s, %s, %s, 'PENDING', %s) RETURNING district_pk",
                (anchors["state_pk"], f"DT{sfx}", f"Testdist {sfx}", submitter_ss_pk),
            )
        elif entity == "postal-code":
            cur.execute(
                "INSERT INTO nss.postal_code "
                "(state_pk, postal_code, entry_status, submitted_by_sangha_sevi_pk) "
                "VALUES (%s, %s, 'PENDING', %s) RETURNING postal_code_pk",
                (anchors["state_pk"], _rand_pin(), submitter_ss_pk),
            )
        elif entity == "post-office":
            cur.execute(
                "INSERT INTO nss.post_office "
                "(postal_code_pk, post_office_name, entry_status, "
                " submitted_by_sangha_sevi_pk) "
                "VALUES (%s, %s, 'PENDING', %s) RETURNING post_office_pk",
                (anchors["postal_code_pk"], f"Testpo {sfx}", submitter_ss_pk),
            )
        elif entity == "city-village":
            cur.execute(
                "INSERT INTO nss.city_village "
                "(district_pk, postal_code_pk, city_village_code, "
                " city_village_name, city_village_type, entry_status, "
                " submitted_by_sangha_sevi_pk) "
                "VALUES (%s, %s, %s, %s, 'VILLAGE', 'PENDING', %s) "
                "RETURNING city_village_pk",
                (anchors["district_pk"], anchors["postal_code_pk"],
                 f"CV{sfx}", f"Testcv {sfx}", submitter_ss_pk),
            )
        else:
            raise AssertionError(f"unknown entity {entity}")
        return str(cur.fetchone()[0])


def _correction_value(entity):
    """A valid corrected_value payload shape for *entity* (FND-BR-087)."""
    sfx = uuid4().hex[:6]
    if entity == "district":
        return {"district_name": f"Canon Dist {sfx}"}
    if entity == "postal-code":
        return {"postal_code": _rand_pin()}
    if entity == "post-office":
        return {"post_office_name": f"Canon PO {sfx}"}
    if entity == "city-village":
        return {"city_village_name": f"Canon CV {sfx}", "city_village_type": "VILLAGE"}
    raise AssertionError(entity)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def foundation_admin_tokens(client, write_conn):
    """NSS-WIDE admin holding FOUNDATION_MANAGE — the global authority."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT ua.user_account_pk, ss.sangha_sevi_id
        FROM nss.user_account ua
        JOIN nss.person p ON p.person_pk = ua.person_pk
        JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk AND ss.is_active = TRUE
        JOIN nss.user_role ur ON ur.user_account_pk = ua.user_account_pk AND ur.is_active = TRUE
        JOIN nss.role_permission rp ON rp.role_master_pk = ur.role_master_pk AND rp.is_active = TRUE
        JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
        JOIN nss.admin_scope asc2 ON asc2.user_role_pk = ur.user_role_pk
                                   AND asc2.is_active = TRUE
                                   AND asc2.scope_level = 'NSS-WIDE'
        WHERE ua.is_active = TRUE
          AND ua.account_status = 'ACTIVE'
          AND pm.permission_code = 'FOUNDATION_MANAGE'
        LIMIT 1
    """)
    row = cur.fetchone()
    if row is None:
        pytest.skip("No NSS-WIDE admin with FOUNDATION_MANAGE. Cannot run geo-approval tests.")
    admin_pk, sevi_id = row

    from api.services.auth_service import hash_password
    cur.execute("""
        UPDATE nss.user_account
        SET password_hash = %s, password_changed_at = NOW(),
            password_expires_at = NOW() + INTERVAL '365 days'
        WHERE user_account_pk = %s
    """, (hash_password(ADMIN_PASSWORD), str(admin_pk)))

    response = client.post("/api/v1/auth/login", json={
        "login_id": sevi_id, "password": ADMIN_PASSWORD,
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.json()}")

    return {
        "access_token": response.json()["access_token"],
        "user_account_pk": str(admin_pk),
    }


@pytest.fixture(scope="module")
def sakha_orgs(write_conn):
    """Two distinct active SAKHA_SANGHA orgs, for scope-boundary tests."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk
        FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
        ORDER BY o.created_at
        LIMIT 2
    """)
    rows = cur.fetchall()
    if len(rows) < 2:
        pytest.skip("Need at least two active SAKHA_SANGHA organizations for scope tests.")
    return {"org_a": str(rows[0][0]), "org_b": str(rows[1][0])}


@pytest.fixture(scope="module")
def scoped_foundation_admin_tokens(write_conn, client, sakha_orgs):
    """
    An admin holding FOUNDATION_MANAGE but scoped ONLY to org_b (not org_a),
    used to prove geo-entry endpoints deny out-of-scope submissions.

    Picks any role_master that carries FOUNDATION_MANAGE and is NOT the
    blanket NSS_ERP_ADMIN role (which would resolve to global authority via
    is_super_admin), assigns it to a fresh user_account on a person who
    already has an active sangha_sevi (needed to be recorded as reviewer),
    and anchors its admin_scope at org_b.
    """
    from api.services.auth_service import hash_password

    cur = write_conn.cursor()
    cur.execute("""
        SELECT rm.role_master_pk
        FROM nss.role_master rm
        JOIN nss.role_permission rp ON rp.role_master_pk = rm.role_master_pk AND rp.is_active = TRUE
        JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
        WHERE pm.permission_code = 'FOUNDATION_MANAGE'
          AND rm.role_code <> 'NSS_ERP_ADMIN'
          AND rm.is_active = TRUE
        LIMIT 1
    """)
    role_row = cur.fetchone()
    if role_row is None:
        pytest.skip("No scope-bounded role carries FOUNDATION_MANAGE; cannot build scoped admin.")
    role_pk = str(role_row[0])

    # Created fresh in org_b — the reviewer must itself hold an active
    # sangha_sevi (approve/correct record it as reviewer), and a clean
    # build has no spare seeded persons to borrow.
    actor = _create_sevi(cur, sakha_orgs["org_b"])
    person_pk, sevi_id = actor["person_pk"], actor["sangha_sevi_id"]

    cur.execute("""
        INSERT INTO nss.user_account (
            person_pk, password_hash, account_status,
            force_password_change, password_expires_at
        ) VALUES (%s, %s, 'ACTIVE', FALSE, NOW() + INTERVAL '365 days')
        RETURNING user_account_pk
    """, (str(person_pk), hash_password(SCOPED_PASSWORD)))
    ua_pk = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO nss.user_role (user_account_pk, role_master_pk)
        VALUES (%s, %s) RETURNING user_role_pk
    """, (str(ua_pk), role_pk))
    ur_pk = cur.fetchone()[0]

    # Scope to org_b ONLY (SAKHA level) — org_a must be out of scope. The
    # subtree resolver keys off organization_pk, not the scope_level label.
    cur.execute("""
        INSERT INTO nss.admin_scope (user_role_pk, scope_level, organization_pk)
        VALUES (%s, 'SAKHA', %s)
    """, (str(ur_pk), sakha_orgs["org_b"]))

    response = client.post("/api/v1/auth/login", json={
        "login_id": sevi_id, "password": SCOPED_PASSWORD,
    })
    if response.status_code != 200:
        pytest.skip(f"Scoped admin login failed: {response.json()}")

    return {"access_token": response.json()["access_token"]}


@pytest.fixture(scope="module")
def submitters(write_conn, sakha_orgs):
    """
    Two sangha_sevi submitters, one anchored in org_a (out of the scoped
    admin's scope) and one in org_b (in scope).

    Both are created fresh — a clean build has only the bootstrap admin's
    sangha_sevi, so there is nothing to borrow. Rolled back by conftest's
    module SAVEPOINT.
    """
    cur = write_conn.cursor()
    return {
        "org_a": _create_sevi(cur, sakha_orgs["org_a"])["sangha_sevi_pk"],
        "org_b": _create_sevi(cur, sakha_orgs["org_b"])["sangha_sevi_pk"],
    }


@pytest.fixture(scope="module")
def anchors(write_conn):
    """
    Canonical APPROVED anchor rows (state + district + postal_code) that the
    four entity INSERTs hang off: post_office needs a postal_code_pk,
    city_village needs district_pk + postal_code_pk.
    """
    cur = write_conn.cursor()
    cur.execute(
        "SELECT state_pk FROM nss.state WHERE is_active = TRUE ORDER BY created_at LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        pytest.skip("No active state in seed; cannot anchor geo-entry tests.")
    state_pk = str(row[0])
    sfx = uuid4().hex[:6]

    cur.execute(
        "INSERT INTO nss.district (state_pk, district_code, district_name, entry_status) "
        "VALUES (%s, %s, %s, 'APPROVED') RETURNING district_pk",
        (state_pk, f"AN{sfx}", f"Anchordist {sfx}"),
    )
    district_pk = str(cur.fetchone()[0])

    cur.execute(
        "INSERT INTO nss.postal_code (state_pk, postal_code, entry_status) "
        "VALUES (%s, %s, 'APPROVED') RETURNING postal_code_pk",
        (state_pk, _rand_pin()),
    )
    postal_code_pk = str(cur.fetchone()[0])

    return {"state_pk": state_pk, "district_pk": district_pk, "postal_code_pk": postal_code_pk}


def _auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ── GET /{entity} — list ────────────────────────────────────────────────

class TestGeoEntryList:

    def test_unknown_entity_404(self, client, foundation_admin_tokens):
        resp = client.get(
            "/api/v1/admin/geo-entries/not-a-real-entity",
            headers=_auth(foundation_admin_tokens),
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_nss_wide_sees_pending_from_any_org(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)

        resp = client.get(
            f"/api/v1/admin/geo-entries/{entity}?status=PENDING&page_size=100",
            headers=_auth(foundation_admin_tokens),
        )
        assert resp.status_code == 200, resp.json()
        pks = {e["entry_pk"] for e in resp.json()["entries"]}
        assert entry_pk in pks

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_scoped_admin_sees_only_in_scope(
        self, client, scoped_foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        out_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        in_pk = _insert_pending(write_conn, entity, submitters["org_b"], anchors)

        resp = client.get(
            f"/api/v1/admin/geo-entries/{entity}?status=PENDING&page_size=100",
            headers=_auth(scoped_foundation_admin_tokens),
        )
        assert resp.status_code == 200, resp.json()
        pks = {e["entry_pk"] for e in resp.json()["entries"]}
        assert in_pk in pks, "Scoped admin must see in-scope (org_b) submissions."
        assert out_pk not in pks, "Scoped admin must NOT see out-of-scope (org_a) submissions."


# ── GET /{entity}/{pk} — detail ─────────────────────────────────────────

class TestGeoEntryDetail:

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_detail_success(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        resp = client.get(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}",
            headers=_auth(foundation_admin_tokens),
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["entry_pk"] == entry_pk
        assert data["entity"] == entity
        assert data["entry_status"] == "PENDING"
        assert data["submitted_by_sangha_sevi_pk"] == submitters["org_a"]

    def test_detail_not_found(self, client, foundation_admin_tokens):
        resp = client.get(
            "/api/v1/admin/geo-entries/district/00000000-0000-0000-0000-000000000000",
            headers=_auth(foundation_admin_tokens),
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_detail_scope_denied(
        self, client, scoped_foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        resp = client.get(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}",
            headers=_auth(scoped_foundation_admin_tokens),
        )
        assert resp.status_code == 403


# ── POST /{entity}/{pk}/approve ─────────────────────────────────────────

class TestApproveGeoEntry:

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_approve_pending_success(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        resp = client.post(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}/approve",
            headers=_auth(foundation_admin_tokens),
            json={"admin_remarks": "Looks correct."},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["entry_status"] == "APPROVED"
        assert data["reviewed_by_sangha_sevi_pk"] is not None
        assert data["reviewed_at"] is not None

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_approve_non_pending_422(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        first = client.post(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}/approve",
            headers=_auth(foundation_admin_tokens), json={},
        )
        assert first.status_code == 200, first.json()

        second = client.post(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}/approve",
            headers=_auth(foundation_admin_tokens), json={},
        )
        assert second.status_code == 422
        assert "PENDING" in second.json()["detail"]

    def test_approve_duplicate_returns_409(
        self, client, foundation_admin_tokens, anchors, write_conn
    ):
        """Approving a PENDING district whose (state, name) already has an
        APPROVED canonical row collides with uq_district_state_name_approved
        -> translated to a 409 pointing at /correct (FND-BR-090)."""
        sfx = uuid4().hex[:6]
        dup_name = f"Dupdist {sfx}"
        with write_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO nss.district (state_pk, district_code, district_name, entry_status) "
                "VALUES (%s, %s, %s, 'APPROVED')",
                (anchors["state_pk"], f"DC{sfx}", dup_name),
            )
            cur.execute(
                "INSERT INTO nss.district (state_pk, district_code, district_name, entry_status) "
                "VALUES (%s, %s, %s, 'PENDING') RETURNING district_pk",
                (anchors["state_pk"], f"DP{sfx}", dup_name),
            )
            pending_pk = str(cur.fetchone()[0])

        resp = client.post(
            f"/api/v1/admin/geo-entries/district/{pending_pk}/approve",
            headers=_auth(foundation_admin_tokens), json={},
        )
        assert resp.status_code == 409, resp.json()
        assert "correct" in resp.json()["detail"].lower()

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_approve_scope_denied(
        self, client, scoped_foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        resp = client.post(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}/approve",
            headers=_auth(scoped_foundation_admin_tokens), json={},
        )
        assert resp.status_code == 403

        tbl, pk_col = {
            "district": ("district", "district_pk"),
            "postal-code": ("postal_code", "postal_code_pk"),
            "post-office": ("post_office", "post_office_pk"),
            "city-village": ("city_village", "city_village_pk"),
        }[entity]
        with write_conn.cursor() as cur:
            cur.execute(
                f"SELECT entry_status FROM nss.{tbl} WHERE {pk_col} = %s",
                (entry_pk,),
            )
            assert cur.fetchone()[0] == "PENDING", "Denied approval must not mutate status."

    def test_scoped_admin_approves_in_scope(
        self, client, scoped_foundation_admin_tokens, submitters, anchors, write_conn
    ):
        """Positive path: a scope-bounded admin may approve a submission from
        within their own subtree (org_b)."""
        entry_pk = _insert_pending(write_conn, "district", submitters["org_b"], anchors)
        resp = client.post(
            f"/api/v1/admin/geo-entries/district/{entry_pk}/approve",
            headers=_auth(scoped_foundation_admin_tokens), json={},
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["entry_status"] == "APPROVED"


# ── POST /{entity}/{pk}/correct ─────────────────────────────────────────

class TestCorrectGeoEntry:

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_correct_creates_canonical(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn, entity
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        resp = client.post(
            f"/api/v1/admin/geo-entries/{entity}/{entry_pk}/correct",
            headers=_auth(foundation_admin_tokens),
            json={"corrected_value": _correction_value(entity),
                  "admin_remarks": "Normalised the member's typed value."},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["original_pk"] == entry_pk
        assert data["canonical_pk"] != entry_pk
        assert data["canonical_was_newly_created"] is True

        tbl, pk_col, self_fk = {
            "district": ("district", "district_pk", "corrected_into_district_pk"),
            "postal-code": ("postal_code", "postal_code_pk", "corrected_into_postal_code_pk"),
            "post-office": ("post_office", "post_office_pk", "corrected_into_post_office_pk"),
            "city-village": ("city_village", "city_village_pk", "corrected_into_city_village_pk"),
        }[entity]
        with write_conn.cursor() as cur:
            cur.execute(
                f"SELECT entry_status, {self_fk} FROM nss.{tbl} WHERE {pk_col} = %s",
                (entry_pk,),
            )
            status_val, corrected_into = cur.fetchone()
            assert status_val == "CORRECTED"
            assert str(corrected_into) == data["canonical_pk"]

    def test_correct_finds_existing_canonical(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn
    ):
        """When an APPROVED canonical row already matches corrected_value, the
        correction re-points at it rather than creating a duplicate."""
        sfx = uuid4().hex[:6]
        canon_name = f"Existing Dist {sfx}"
        with write_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO nss.district (state_pk, district_code, district_name, entry_status) "
                "VALUES (%s, %s, %s, 'APPROVED') RETURNING district_pk",
                (anchors["state_pk"], f"EX{sfx}", canon_name),
            )
            canonical_pk = str(cur.fetchone()[0])

        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        resp = client.post(
            f"/api/v1/admin/geo-entries/district/{entry_pk}/correct",
            headers=_auth(foundation_admin_tokens),
            json={"corrected_value": {"district_name": canon_name},
                  "admin_remarks": "Member misspelled an existing district."},
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["canonical_was_newly_created"] is False
        assert data["canonical_pk"] == canonical_pk

    def test_correct_non_pending_422(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn
    ):
        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        approve = client.post(
            f"/api/v1/admin/geo-entries/district/{entry_pk}/approve",
            headers=_auth(foundation_admin_tokens), json={},
        )
        assert approve.status_code == 200

        resp = client.post(
            f"/api/v1/admin/geo-entries/district/{entry_pk}/correct",
            headers=_auth(foundation_admin_tokens),
            json={"corrected_value": {"district_name": "Whatever"},
                  "admin_remarks": "too late"},
        )
        assert resp.status_code == 422
        assert "PENDING" in resp.json()["detail"]

    def test_correct_scope_denied(
        self, client, scoped_foundation_admin_tokens, submitters, anchors, write_conn
    ):
        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        resp = client.post(
            f"/api/v1/admin/geo-entries/district/{entry_pk}/correct",
            headers=_auth(scoped_foundation_admin_tokens),
            json={"corrected_value": {"district_name": "Denied"},
                  "admin_remarks": "should not apply"},
        )
        assert resp.status_code == 403

        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT entry_status FROM nss.district WHERE district_pk = %s",
                (entry_pk,),
            )
            assert cur.fetchone()[0] == "PENDING", "Denied correction must not mutate status."


# ── Remaining endpoint x edge-case matrix ────────────────────────────────

UNKNOWN_PK = "00000000-0000-0000-0000-0000000000dd"


class TestGeoEntryListEdges:

    URL = "/api/v1/admin/geo-entries/{}"

    @pytest.mark.parametrize("params", [
        {"status": "BOGUS"}, {"status": "pending"}, {"page": 0},
        {"page_size": 0}, {"page_size": 101},
    ])
    def test_invalid_query_is_422(self, client, foundation_admin_tokens, params):
        resp = client.get(self.URL.format("district"), headers=_auth(foundation_admin_tokens),
                          params=params)
        assert resp.status_code == 422

    @pytest.mark.parametrize("entry_status", ["PENDING", "APPROVED", "CORRECTED"])
    def test_status_filter_only_returns_that_status(
        self, client, foundation_admin_tokens, entry_status
    ):
        resp = client.get(self.URL.format("district"), headers=_auth(foundation_admin_tokens),
                          params={"status": entry_status, "page_size": 5})
        assert resp.status_code == 200
        assert all(r["entry_status"] == entry_status for r in resp.json()["entries"])

    def test_approved_entry_leaves_pending_queue(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn
    ):
        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        url = self.URL.format("district")

        def queue(status_value):
            body = client.get(url, headers=_auth(foundation_admin_tokens),
                              params={"status": status_value, "page_size": 100}).json()
            return {r["entry_pk"] for r in body["entries"]}

        before = queue("PENDING")
        assert client.post(f"{url}/{entry_pk}/approve", headers=_auth(foundation_admin_tokens),
                           json={}).status_code == 200
        assert entry_pk in before or len(before) >= 100
        assert entry_pk not in queue("PENDING")


class TestGeoEntryNotFoundAndValidation:

    BASE = "/api/v1/admin/geo-entries"

    def test_unknown_entity_is_404_on_every_verb(self, client, foundation_admin_tokens):
        h = _auth(foundation_admin_tokens)
        assert client.get(f"{self.BASE}/nope/{UNKNOWN_PK}", headers=h).status_code == 404
        assert client.post(f"{self.BASE}/nope/{UNKNOWN_PK}/approve", headers=h, json={}).status_code == 404
        assert client.post(f"{self.BASE}/nope/{UNKNOWN_PK}/correct", headers=h, json={
            "corrected_value": {}, "admin_remarks": "x"}).status_code == 404

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_unknown_entry_pk_is_404(self, client, foundation_admin_tokens, entity):
        h = _auth(foundation_admin_tokens)
        assert client.get(f"{self.BASE}/{entity}/{UNKNOWN_PK}", headers=h).status_code == 404
        assert client.post(f"{self.BASE}/{entity}/{UNKNOWN_PK}/approve", headers=h, json={}).status_code == 404
        corrected = client.post(f"{self.BASE}/{entity}/{UNKNOWN_PK}/correct", headers=h, json={
            "corrected_value": _correction_value(entity), "admin_remarks": "x"})
        assert corrected.status_code == 404

    def test_malformed_entry_pk_is_422(self, client, foundation_admin_tokens):
        h = _auth(foundation_admin_tokens)
        assert client.get(f"{self.BASE}/district/not-a-uuid", headers=h).status_code == 422
        assert client.post(f"{self.BASE}/district/not-a-uuid/approve", headers=h, json={}).status_code == 422

    @pytest.mark.parametrize("body", [
        {"corrected_value": {"district_name": "X"}},                        # no remarks
        {"corrected_value": {"district_name": "X"}, "admin_remarks": ""},   # blank remarks
        {"admin_remarks": "no value"},                                      # no corrected_value
        {"corrected_value": "not-an-object", "admin_remarks": "x"},
        {"corrected_value": {"district_name": "X"}, "admin_remarks": "r" * 501},
    ])
    def test_correct_body_validation_is_422(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn, body
    ):
        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        resp = client.post(f"{self.BASE}/district/{entry_pk}/correct",
                           headers=_auth(foundation_admin_tokens), json=body)
        assert resp.status_code == 422
        with write_conn.cursor() as cur:
            cur.execute("SELECT entry_status FROM nss.district WHERE district_pk = %s", (entry_pk,))
            assert cur.fetchone()[0] == "PENDING"

    @pytest.mark.parametrize("entity,bad_value,fragment", [
        ("district", {}, "district_name"),
        ("district", {"district_name": "   "}, "district_name"),
        ("postal-code", {"postal_code": "12AB"}, "6-digit"),
        ("postal-code", {}, "6-digit"),
        ("post-office", {}, "post_office_name"),
        ("city-village", {}, "city_village_name"),
        ("city-village", {"city_village_name": "Valid Name", "city_village_type": "HAMLET"},
         "CITY, TOWN, or VILLAGE"),
    ])
    def test_correct_rejects_unusable_corrected_value(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn,
        entity, bad_value, fragment
    ):
        entry_pk = _insert_pending(write_conn, entity, submitters["org_a"], anchors)
        resp = client.post(f"{self.BASE}/{entity}/{entry_pk}/correct",
                           headers=_auth(foundation_admin_tokens),
                           json={"corrected_value": bad_value, "admin_remarks": "bad value"})
        assert resp.status_code == 422
        assert fragment in resp.json()["detail"]

    def test_approve_records_reviewer_and_remarks(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn
    ):
        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        resp = client.post(f"{self.BASE}/district/{entry_pk}/approve",
                           headers=_auth(foundation_admin_tokens),
                           json={"admin_remarks": "checked against the census list"})
        assert resp.status_code == 200
        assert resp.json()["admin_remarks"] == "checked against the census list"
        assert resp.json()["reviewed_by_sangha_sevi_pk"]

    def test_approve_already_corrected_entry_is_422(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn
    ):
        entry_pk = _insert_pending(write_conn, "district", submitters["org_a"], anchors)
        assert client.post(
            f"{self.BASE}/district/{entry_pk}/correct", headers=_auth(foundation_admin_tokens),
            json={"corrected_value": _correction_value("district"), "admin_remarks": "fix"},
        ).status_code == 200
        resp = client.post(f"{self.BASE}/district/{entry_pk}/approve",
                           headers=_auth(foundation_admin_tokens), json={})
        assert resp.status_code == 422
        assert "CORRECTED" in resp.json()["detail"]

    def test_correct_repoints_person_address_at_the_canonical_row(
        self, client, foundation_admin_tokens, submitters, anchors, write_conn
    ):
        """FND-BR-088: addresses that referenced the typed-in value follow the correction."""
        entry_pk = _insert_pending(write_conn, "city-village", submitters["org_a"], anchors)
        with write_conn.cursor() as cur:
            cur.execute("SELECT person_pk FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s",
                        (submitters["org_a"],))
            person_pk = cur.fetchone()[0]
            cur.execute("""
                SELECT md.master_data_pk FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'ADDRESS_TYPE' AND md.value_code = 'PERMANENT'
                  AND md.is_active = TRUE LIMIT 1
            """)
            address_type_pk = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO nss.person_address (
                    person_pk, address_type_master_data_pk, address_line_1,
                    city_village_pk, is_primary
                ) VALUES (%s, %s, '1 Geo Test Lane', %s, TRUE) RETURNING person_address_pk
            """, (str(person_pk), str(address_type_pk), entry_pk))
            address_pk = cur.fetchone()[0]

        resp = client.post(f"{self.BASE}/city-village/{entry_pk}/correct",
                           headers=_auth(foundation_admin_tokens),
                           json={"corrected_value": _correction_value("city-village"),
                                 "admin_remarks": "normalised spelling"})
        assert resp.status_code == 200, resp.json()
        canonical_pk = resp.json()["canonical_pk"]
        with write_conn.cursor() as cur:
            cur.execute("SELECT city_village_pk FROM nss.person_address WHERE person_address_pk = %s",
                        (address_pk,))
            assert str(cur.fetchone()[0]) == canonical_pk


class TestRegistrationOriginEntryScope:
    """
    Entries auto-created at self-registration carry submitted_by_person_pk and have no
    sangha_sevi yet; the scope anchor is then the submitter's PENDING claim's Sakha.
    """

    @pytest.fixture
    def person_entries(self, write_conn, sakha_orgs, anchors):
        """(entry in org_a's claim, entry in org_b's claim) — both person-submitted."""
        from tests.api.test_admin_credentials import _create_person
        out = {}
        with write_conn.cursor() as cur:
            cur.execute("""
                SELECT md.master_data_pk FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'PROBATIONARY'
                  AND md.is_active = TRUE LIMIT 1
            """)
            type_pk = str(cur.fetchone()[0])
        for key in ("org_a", "org_b"):
            person_pk = str(_create_person(write_conn, "GEOP"))
            ua_pk = add_user_account(write_conn, person_pk, SCOPED_PASSWORD)
            sfx = uuid4().hex[:6]
            with write_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nss.registration_claim (
                        user_account_pk, person_pk, claimed_organization_pk,
                        claimed_membership_type_master_data_pk,
                        claimed_local_sakha_number, claim_status
                    ) VALUES (%s, %s, %s, %s, 'G1', 'PENDING')
                """, (ua_pk, person_pk, sakha_orgs[key], type_pk))
                cur.execute("""
                    INSERT INTO nss.city_village
                        (district_pk, postal_code_pk, city_village_code, city_village_name,
                         city_village_type, entry_status, submitted_by_person_pk)
                    VALUES (%s, %s, %s, %s, 'VILLAGE', 'PENDING', %s)
                    RETURNING city_village_pk
                """, (anchors["district_pk"], anchors["postal_code_pk"], f"GP{sfx}",
                      f"Personvillage {sfx}", person_pk))
                out[key] = str(cur.fetchone()[0])
        return out

    def test_scoped_admin_reaches_entry_via_pending_claim_org(
        self, client, scoped_foundation_admin_tokens, person_entries
    ):
        url = f"/api/v1/admin/geo-entries/city-village/{person_entries['org_b']}"
        assert client.get(url, headers=_auth(scoped_foundation_admin_tokens)).status_code == 200

    def test_scoped_admin_denied_entry_whose_claim_is_elsewhere(
        self, client, scoped_foundation_admin_tokens, person_entries, write_conn
    ):
        pk = person_entries["org_a"]
        base = f"/api/v1/admin/geo-entries/city-village/{pk}"
        assert client.get(base, headers=_auth(scoped_foundation_admin_tokens)).status_code == 403
        denied = client.post(f"{base}/approve", headers=_auth(scoped_foundation_admin_tokens), json={})
        assert denied.status_code == 403
        with write_conn.cursor() as cur:
            cur.execute("SELECT entry_status FROM nss.city_village WHERE city_village_pk = %s", (pk,))
            assert cur.fetchone()[0] == "PENDING"
