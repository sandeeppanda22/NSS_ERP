"""
NSS ERP — Local Sakha ID is ALWAYS generated (owner 2026-11-01).

Covers the shared allocation rule (api/helpers.py::next_sakha_local_number ->
nss.fn_next_sakha_local_number), the one shared enrollment helper
(create_sangha_sevi_with_home_affiliation) and the HTTP paths that use it
(POST /admin/sangha-sevi, POST /admin/users with create_sangha_sevi).

Real DB, per-test SAVEPOINT rollback (tests/conftest.py). Written but NOT yet
run against a database (collect-only).
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.helpers import (
    create_sangha_sevi_with_home_affiliation,
    insert_sakha_affiliation,
    next_sakha_local_number,
)

from tests.api.test_admin import (  # noqa: F401  (fixtures reused by name)
    admin_user, admin_tokens, admin_headers, two_sakhas, regular_membership_type_pk,
)

pytestmark = pytest.mark.integration


# ── fixtures / helpers ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sakha(write_conn):
    """An active SAKHA_SANGHA that already has a short_code."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
          AND o.short_code IS NOT NULL AND btrim(o.short_code) <> ''
        ORDER BY o.organization_name LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    if row is None:
        pytest.skip("No active SAKHA_SANGHA with a short_code.")
    return str(row[0])


@pytest.fixture(scope="module")
def type_pks(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT md.value_code, md.master_data_pk FROM nss.master_data md
        JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'MEMBERSHIP_TYPE'
          AND md.value_code IN ('REGULAR', 'PROBATIONARY') AND md.is_active = TRUE
    """)
    out = {c: str(pk) for c, pk in cur.fetchall()}
    cur.close()
    if "REGULAR" not in out or "PROBATIONARY" not in out:
        pytest.skip("REGULAR/PROBATIONARY membership types missing.")
    return out


def _person(write_conn):
    cur = write_conn.cursor()
    suffix = uuid4().hex[:10].upper()
    cur.execute(
        "INSERT INTO nss.person (person_id, first_name, last_name, email) "
        "VALUES (%s, %s, %s, %s) RETURNING person_pk",
        (f"TLS{suffix}", "TestLocalId", suffix, f"tls.{suffix.lower()}@example.test"),
    )
    pk = str(cur.fetchone()[0])
    cur.close()
    return pk


def _create(write_conn, org_pk, type_pk, *, local_number=None, is_darshak=None):
    cur = write_conn.cursor()
    try:
        return create_sangha_sevi_with_home_affiliation(
            cur,
            person_pk=_person(write_conn),
            membership_type_pk=type_pk,
            organization_pk=org_pk,
            joining_date=None,
            actor_pk=None,
            actor_user_account_pk=None,
            module="test",
            local_number=local_number,
            is_darshak=is_darshak,
        )
    finally:
        cur.close()


# ── allocation rule ──────────────────────────────────────────────────────

class TestAllocator:
    def test_two_creations_in_one_sakha_get_distinct_numbers(self, write_conn, sakha, type_pks):
        a = _create(write_conn, sakha, type_pks["REGULAR"])
        b = _create(write_conn, sakha, type_pks["REGULAR"])
        assert a["local_sakha_erp_id"] != b["local_sakha_erp_id"]

    def test_numbers_are_sequential_per_namespace(self, write_conn, sakha):
        cur = write_conn.cursor()
        n1 = int(next_sakha_local_number(cur, sakha))
        n2 = int(next_sakha_local_number(cur, sakha))
        assert n2 == n1 + 1
        cur.close()

    def test_darshak_and_regular_namespaces_are_separate(self, write_conn, sakha, type_pks):
        reg = _create(write_conn, sakha, type_pks["REGULAR"])
        dar = _create(write_conn, sakha, type_pks["PROBATIONARY"])
        assert reg["local_sakha_erp_id"] != dar["local_sakha_erp_id"]

    def test_explicit_number_is_stepped_over_not_reused(self, write_conn, sakha, type_pks):
        cur = write_conn.cursor()
        upcoming = int(next_sakha_local_number(cur, sakha)) + 1  # the number the NEXT call would mint
        cur.close()
        taken = _create(write_conn, sakha, type_pks["REGULAR"], local_number=str(upcoming))
        auto = _create(write_conn, sakha, type_pks["REGULAR"])
        assert auto["local_sakha_erp_id"] != taken["local_sakha_erp_id"]

    def test_archived_number_is_never_reissued(self, write_conn, sakha, type_pks):
        first = _create(write_conn, sakha, type_pks["REGULAR"])
        cur = write_conn.cursor()
        cur.execute(
            "UPDATE nss.membership_sakha_affiliation SET effective_to = CURRENT_DATE, "
            "affiliation_status = 'ARCHIVED' WHERE membership_sakha_affiliation_pk = %s",
            (first["affiliation_pk"],),
        )
        cur.close()
        later = [_create(write_conn, sakha, type_pks["REGULAR"])["local_sakha_erp_id"] for _ in range(3)]
        assert first["local_sakha_erp_id"] not in later

    def test_explicit_duplicate_number_is_409(self, write_conn, sakha, type_pks):
        a = _create(write_conn, sakha, type_pks["REGULAR"])
        bare = a["local_sakha_erp_id"]
        cur = write_conn.cursor()
        cur.execute("SELECT short_code FROM nss.organization WHERE organization_pk = %s", (sakha,))
        short_code = cur.fetchone()[0]
        cur.close()
        with pytest.raises(HTTPException) as exc:
            _create(write_conn, sakha, type_pks["REGULAR"], local_number=bare[len(short_code):])
        assert exc.value.status_code == 409

    def test_missing_short_code_fails_loudly_with_422(self, write_conn, sakha, type_pks):
        # The module shares ONE transaction: undo the NULLing in a savepoint, otherwise every
        # later test in this module sees a Sakha without a short_code.
        cur = write_conn.cursor()
        cur.execute("SAVEPOINT null_short_code")
        try:
            cur.execute("UPDATE nss.organization SET short_code = NULL WHERE organization_pk = %s", (sakha,))
            with pytest.raises(HTTPException) as exc:
                _create(write_conn, sakha, type_pks["REGULAR"])
            assert exc.value.status_code == 422
            assert "short_code" in exc.value.detail
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT null_short_code")
            cur.execute("RELEASE SAVEPOINT null_short_code")
            cur.close()


class TestSharedCreator:
    def test_creator_returns_sevi_and_open_home_affiliation(self, write_conn, sakha, type_pks):
        out = _create(write_conn, sakha, type_pks["REGULAR"])
        cur = write_conn.cursor()
        cur.execute(
            """
            SELECT msa.local_sakha_erp_id, msa.affiliation_status, msa.effective_to
            FROM nss.membership_sakha_affiliation msa
            JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = msa.sangha_sevi_pk
            WHERE ss.sangha_sevi_pk = %s AND msa.organization_pk = ss.organization_pk
            """,
            (out["sangha_sevi_pk"],),
        )
        local_id, aff_status, eff_to = cur.fetchone()
        cur.close()
        assert local_id == out["local_sakha_erp_id"] and local_id
        assert aff_status == "ACTIVE" and eff_to is None

    def test_blank_local_number_is_treated_as_absent(self, write_conn, sakha, type_pks):
        out = _create(write_conn, sakha, type_pks["REGULAR"], local_number="   ")
        assert out["local_sakha_erp_id"]

    def test_insert_sakha_affiliation_still_autogenerates(self, write_conn, sakha, type_pks):
        out = _create(write_conn, sakha, type_pks["REGULAR"])
        cur = write_conn.cursor()
        # second (Darshak-style) affiliation elsewhere is unaffected by the home one
        cur.execute(
            "SELECT organization_pk FROM nss.organization o "
            "JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk "
            "WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active AND o.organization_pk <> %s "
            "AND o.short_code IS NOT NULL LIMIT 1", (sakha,))
        row = cur.fetchone()
        if row is None:
            pytest.skip("Need a second Sakha.")
        aff = insert_sakha_affiliation(
            cur, sangha_sevi_pk=out["sangha_sevi_pk"], organization_pk=str(row[0]),
            effective_from=None, is_darshak=True,
        )
        assert aff
        cur.close()


# ── HTTP creation paths (fixtures live in test_admin.py's module scope) ──

class TestAdminCreationPaths:
    """
    POST /admin/sangha-sevi and POST /admin/users(create_sangha_sevi=true)
    without local_sakha_erp_id must still open the home affiliation.
    These tests reuse the admin login fixtures by importing them.
    """

    def _home_local_id(self, write_conn, sangha_sevi_id):
        cur = write_conn.cursor()
        cur.execute(
            """
            SELECT msa.local_sakha_erp_id FROM nss.sangha_sevi ss
            JOIN nss.membership_sakha_affiliation msa
              ON msa.sangha_sevi_pk = ss.sangha_sevi_pk
             AND msa.organization_pk = ss.organization_pk AND msa.effective_to IS NULL
            WHERE ss.sangha_sevi_id = %s
            """,
            (sangha_sevi_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def test_create_sangha_sevi_without_number_autogenerates(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": _person(write_conn),
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 201, resp.json()
        assert self._home_local_id(write_conn, resp.json()["sangha_sevi_id"])

    def test_two_creations_get_distinct_numbers(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        ids = []
        for _ in range(2):
            resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
                "person_pk": _person(write_conn),
                "membership_type_pk": regular_membership_type_pk,
                "organization_pk": two_sakhas[0],
                "joining_date": "2024-04-01",
            })
            assert resp.status_code == 201, resp.json()
            ids.append(self._home_local_id(write_conn, resp.json()["sangha_sevi_id"]))
        assert ids[0] and ids[1] and ids[0] != ids[1]

    def test_create_user_with_sangha_sevi_without_number_autogenerates(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        resp = client.post("/api/v1/admin/users", headers=admin_headers, json={
            "person_pk": _person(write_conn),
            "password": "LocalIdPass1",
            "create_sangha_sevi": True,
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
        })
        assert resp.status_code == 201, resp.json()
        ss_id = resp.json().get("sangha_sevi_id_generated")
        assert ss_id, resp.json()
        assert self._home_local_id(write_conn, ss_id)

    def test_typed_number_is_still_honoured(
        self, client, admin_headers, regular_membership_type_pk, two_sakhas, write_conn
    ):
        if not regular_membership_type_pk or not two_sakhas:
            pytest.skip("Missing reference data.")
        number = str(uuid4().int)[:7]
        resp = client.post("/api/v1/admin/sangha-sevi", headers=admin_headers, json={
            "person_pk": _person(write_conn),
            "membership_type_pk": regular_membership_type_pk,
            "organization_pk": two_sakhas[0],
            "joining_date": "2024-04-01",
            "local_sakha_erp_id": number,
            "is_legacy_member": True,
            "credential_document_number": f"{int(uuid4().int % 900_000) + 100_000}/2025/2026",
        })
        assert resp.status_code == 201, resp.json()
        assert self._home_local_id(write_conn, resp.json()["sangha_sevi_id"]).endswith(number)
