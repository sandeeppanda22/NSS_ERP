"""
NSS ERP — Legacy-vs-new Local Sakha Number rule (GDR-009, owner 2026-11-01).

A member who was ALREADY a member (Regular/Associate or Darshak/Darshaka)
before this application existed is a LEGACY member and must supply their
existing Local Sakha Number; everyone else is auto-numbered by the shared
allocator. One validator (api/helpers.py::resolve_legacy_local_number /
validate_claim_local_numbers) is applied at registration, admin creation, claim
PATCH/approval, and the cross-Sakha attendance affiliation
(ensure_darshak_attendance_affiliation).

Registration / claim-approval HTTP coverage of the matrix lives next to the
existing tests (test_registration.py::TestClaimExisting,
test_claim_approval.py::TestApproveLegacyVsNewLocalSakhaNumber). This module
covers the validator itself, the admin create paths, the attendance helper,
and the registration_claim DDL/patch.

Real DB, per-test SAVEPOINT rollback. Written but NOT yet run against a
database (collect-only).
"""

from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException

from api.helpers import (
    ensure_darshak_attendance_affiliation,
    resolve_legacy_local_number,
    validate_claim_local_numbers,
)

from tests.api.test_admin import (  # noqa: F401  (fixtures reused by name)
    admin_user, admin_tokens, admin_headers, two_sakhas, regular_membership_type_pk,
)
from tests.api.test_local_sakha_id import (  # noqa: F401
    sakha, type_pks, _person, _create,
)

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
PATCH_SQL = REPO / "database/ddl/06_authentication/06_registration_claim_legacy_member_patch.sql"


# ── the shared validator (pure; no DB) ────────────────────────────────────

class TestResolveLegacyLocalNumber:
    def test_legacy_with_number_returns_stripped_number(self):
        assert resolve_legacy_local_number(True, "  1192 ") == "1192"

    def test_legacy_without_number_is_422(self):
        for blank in (None, "", "   "):
            with pytest.raises(HTTPException) as exc:
                resolve_legacy_local_number(True, blank, flag_field="f", number_field="n")
            assert exc.value.status_code == 422
            assert "n is required when f is true" in exc.value.detail

    def test_new_without_number_returns_none_for_autogeneration(self):
        assert resolve_legacy_local_number(False, None) is None
        assert resolve_legacy_local_number(False, "  ") is None
        assert resolve_legacy_local_number(None, "") is None

    def test_new_with_number_is_422_not_ignored(self):
        with pytest.raises(HTTPException) as exc:
            resolve_legacy_local_number(False, "55", flag_field="f", number_field="n")
        assert exc.value.status_code == 422
        assert "n must be blank when f is false" in exc.value.detail

    @pytest.mark.parametrize("bad", ["12 34", "-5", "a b", "x;y", "1\n2"])
    def test_legacy_number_shape_is_validated(self, bad):
        with pytest.raises(HTTPException) as exc:
            resolve_legacy_local_number(True, bad)
        assert exc.value.status_code == 422

    @pytest.mark.parametrize("good", ["1", "1192", "ESS000123", "A-1", "12/34", "7.1"])
    def test_legacy_number_shapes_accepted(self, good):
        assert resolve_legacy_local_number(True, good) == good


class TestValidateClaimLocalNumbers:
    def test_home_legacy_attendance_new(self):
        assert validate_claim_local_numbers(
            is_legacy_member=True, claimed_local_sakha_number="9",
            darshak_organization_pk="org", darshak_is_legacy_member=False,
            darshak_local_sakha_number=None,
        ) == ("9", None)

    def test_home_new_attendance_legacy_is_independent(self):
        assert validate_claim_local_numbers(
            is_legacy_member=False, claimed_local_sakha_number=None,
            darshak_organization_pk="org", darshak_is_legacy_member=True,
            darshak_local_sakha_number="D4",
        ) == (None, "D4")

    def test_attendance_fields_without_an_attending_sakha_are_422(self):
        for kwargs in ({"darshak_is_legacy_member": True}, {"darshak_local_sakha_number": "5"}):
            with pytest.raises(HTTPException) as exc:
                validate_claim_local_numbers(
                    is_legacy_member=False, claimed_local_sakha_number=None, **kwargs,
                )
            assert exc.value.status_code == 422

    def test_no_attending_sakha_returns_none_attendance_number(self):
        assert validate_claim_local_numbers(
            is_legacy_member=False, claimed_local_sakha_number=None,
        ) == (None, None)

    def test_error_text_names_the_claim_fields(self):
        with pytest.raises(HTTPException) as exc:
            validate_claim_local_numbers(is_legacy_member=True, claimed_local_sakha_number="")
        assert "claimed_local_sakha_number" in exc.value.detail
        with pytest.raises(HTTPException) as exc:
            validate_claim_local_numbers(
                is_legacy_member=False, claimed_local_sakha_number=None,
                darshak_organization_pk="org", darshak_is_legacy_member=True,
                darshak_local_sakha_number="",
            )
        assert "darshak_local_sakha_number" in exc.value.detail


# ── admin creation: legacy/new x regular/darshak ───────────────────────────

@pytest.fixture
def admin_ctx(write_conn, regular_membership_type_pk, two_sakhas, type_pks):
    if not regular_membership_type_pk or not two_sakhas:
        pytest.skip("Missing reference data.")
    return {"types": type_pks, "org": two_sakhas[0], "write_conn": write_conn}


def _card():
    """A random strict legacy Patra number (GDR-009 §2A), unique per call."""
    return f"{int(uuid4().int % 900_000) + 100_000}/2025/2026"


def _ss_body(ctx, type_code, **extra):
    return {
        "person_pk": _person(ctx["write_conn"]),
        "membership_type_pk": ctx["types"][type_code],
        "organization_pk": ctx["org"],
        "joining_date": "2024-04-01",
        **extra,
    }


def _home_local_id(write_conn, sangha_sevi_id):
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


@pytest.mark.parametrize("type_code", ["REGULAR", "PROBATIONARY"])
class TestAdminCreateSanghaSeviRuleMatrix:
    URL = "/api/v1/admin/sangha-sevi"

    def test_legacy_with_number_uses_the_typed_number(self, client, admin_headers, admin_ctx, type_code):
        number = str(9_100_000 + int(uuid4().int % 800_000))
        resp = client.post(self.URL, headers=admin_headers, json=_ss_body(
            admin_ctx, type_code, is_legacy_member=True, local_sakha_erp_id=number,
            credential_document_number=_card()))
        assert resp.status_code == 201, resp.json()
        assert _home_local_id(admin_ctx["write_conn"], resp.json()["sangha_sevi_id"]).endswith(number)

    def test_legacy_without_number_is_422(self, client, admin_headers, admin_ctx, type_code):
        resp = client.post(self.URL, headers=admin_headers, json=_ss_body(
            admin_ctx, type_code, is_legacy_member=True))
        assert resp.status_code == 422
        assert "local_sakha_erp_id is required" in resp.json()["detail"]

    def test_new_with_number_is_422(self, client, admin_headers, admin_ctx, type_code):
        resp = client.post(self.URL, headers=admin_headers, json=_ss_body(
            admin_ctx, type_code, is_legacy_member=False, local_sakha_erp_id="123"))
        assert resp.status_code == 422
        assert "must be blank" in resp.json()["detail"]

    def test_number_without_the_flag_defaults_to_new_and_is_422(self, client, admin_headers, admin_ctx, type_code):
        """The flag is explicit: a number alone is NOT inferred to mean legacy."""
        resp = client.post(self.URL, headers=admin_headers, json=_ss_body(
            admin_ctx, type_code, local_sakha_erp_id="123"))
        assert resp.status_code == 422

    def test_new_without_number_is_auto_generated(self, client, admin_headers, admin_ctx, type_code):
        resp = client.post(self.URL, headers=admin_headers, json=_ss_body(
            admin_ctx, type_code, is_legacy_member=False))
        assert resp.status_code == 201, resp.json()
        assert _home_local_id(admin_ctx["write_conn"], resp.json()["sangha_sevi_id"])


class TestAdminCreateUserRuleMatrix:
    URL = "/api/v1/admin/users"

    def _body(self, ctx, type_code, **extra):
        return {
            "person_pk": _person(ctx["write_conn"]),
            "password": "LegacyRule1Pass",
            "create_sangha_sevi": True,
            "membership_type_pk": ctx["types"][type_code],
            "organization_pk": ctx["org"],
            "joining_date": "2024-04-01",
            **extra,
        }

    @pytest.mark.parametrize("type_code", ["REGULAR", "PROBATIONARY"])
    def test_new_member_is_auto_numbered(self, client, admin_headers, admin_ctx, type_code):
        resp = client.post(self.URL, headers=admin_headers, json=self._body(admin_ctx, type_code))
        assert resp.status_code == 201, resp.json()
        assert _home_local_id(admin_ctx["write_conn"], resp.json()["sangha_sevi_id_generated"])

    @pytest.mark.parametrize("type_code", ["REGULAR", "PROBATIONARY"])
    def test_legacy_member_keeps_the_typed_number(self, client, admin_headers, admin_ctx, type_code):
        number = str(9_200_000 + int(uuid4().int % 700_000))
        resp = client.post(self.URL, headers=admin_headers, json=self._body(
            admin_ctx, type_code, is_legacy_member=True, local_sakha_erp_id=number,
            credential_document_number=_card()))
        assert resp.status_code == 201, resp.json()
        assert _home_local_id(admin_ctx["write_conn"], resp.json()["sangha_sevi_id_generated"]).endswith(number)

    def test_legacy_without_number_is_422(self, client, admin_headers, admin_ctx):
        resp = client.post(self.URL, headers=admin_headers, json=self._body(
            admin_ctx, "REGULAR", is_legacy_member=True))
        assert resp.status_code == 422

    def test_new_with_number_is_422(self, client, admin_headers, admin_ctx):
        resp = client.post(self.URL, headers=admin_headers, json=self._body(
            admin_ctx, "REGULAR", local_sakha_erp_id="77"))
        assert resp.status_code == 422

    def test_taken_legacy_number_is_409(self, client, admin_headers, admin_ctx):
        number = str(9_300_000 + int(uuid4().int % 600_000))
        ok = client.post(self.URL, headers=admin_headers, json=self._body(
            admin_ctx, "REGULAR", is_legacy_member=True, local_sakha_erp_id=number,
            credential_document_number=_card()))
        assert ok.status_code == 201, ok.json()
        clash = client.post(self.URL, headers=admin_headers, json=self._body(
            admin_ctx, "REGULAR", is_legacy_member=True, local_sakha_erp_id=number,
            credential_document_number=_card()))
        assert clash.status_code == 409


# ── cross-Sakha attendance affiliation helper (claim approval step 7) ──────

@pytest.fixture
def two_coded_sakhas(write_conn):
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
          AND o.short_code IS NOT NULL AND btrim(o.short_code) <> ''
        ORDER BY o.organization_name LIMIT 2
    """)
    rows = [str(r[0]) for r in cur.fetchall()]
    cur.close()
    if len(rows) < 2:
        pytest.skip("Need two Sakhas with short_codes.")
    return rows


def _attend(write_conn, sevi_pk, org_pk, local_number):
    cur = write_conn.cursor()
    try:
        return ensure_darshak_attendance_affiliation(
            cur, sangha_sevi_pk=sevi_pk, organization_pk=org_pk,
            local_number=local_number, effective_from=None,
            actor_pk=None, actor_user_account_pk=None, module="test",
        )
    finally:
        cur.close()


def _aff_local_id(write_conn, aff_pk):
    cur = write_conn.cursor()
    cur.execute(
        "SELECT local_sakha_erp_id FROM nss.membership_sakha_affiliation "
        "WHERE membership_sakha_affiliation_pk = %s", (aff_pk,))
    value = cur.fetchone()[0]
    cur.close()
    return value


class TestAttendanceAffiliationHelper:
    def test_new_attendee_gets_the_next_darshak_number(self, write_conn, two_coded_sakhas, type_pks):
        home, away = two_coded_sakhas
        member = _create(write_conn, home, type_pks["REGULAR"])
        aff = _attend(write_conn, member["sangha_sevi_pk"], away, None)
        assert aff
        other = _create(write_conn, away, type_pks["PROBATIONARY"])
        # Same Sakha, same Darshak series: the attendee and a later Darshaka
        # draw distinct numbers from one counter.
        assert _aff_local_id(write_conn, aff) != other["local_sakha_erp_id"]

    def test_legacy_attendee_keeps_the_typed_number_in_the_darshak_series(self, write_conn, two_coded_sakhas, type_pks):
        home, away = two_coded_sakhas
        member = _create(write_conn, home, type_pks["REGULAR"])
        typed = str(9_400_000 + int(uuid4().int % 500_000))
        aff = _attend(write_conn, member["sangha_sevi_pk"], away, typed)
        assert _aff_local_id(write_conn, aff).endswith(typed)

    def test_collision_is_a_loud_409(self, write_conn, two_coded_sakhas, type_pks):
        home, away = two_coded_sakhas
        first = _create(write_conn, home, type_pks["REGULAR"])
        second = _create(write_conn, home, type_pks["REGULAR"])
        typed = str(9_500_000 + int(uuid4().int % 400_000))
        assert _attend(write_conn, first["sangha_sevi_pk"], away, typed)
        with pytest.raises(HTTPException) as exc:
            _attend(write_conn, second["sangha_sevi_pk"], away, typed)
        assert exc.value.status_code == 409

    def test_skipped_only_when_an_open_affiliation_already_exists(self, write_conn, two_coded_sakhas, type_pks):
        home, away = two_coded_sakhas
        member = _create(write_conn, home, type_pks["REGULAR"])
        assert _attend(write_conn, member["sangha_sevi_pk"], home, None) is None, "home Sakha is already open"
        first = _attend(write_conn, member["sangha_sevi_pk"], away, None)
        assert first
        assert _attend(write_conn, member["sangha_sevi_pk"], away, None) is None, "second call must skip"

    def test_a_taken_number_is_not_skipped_when_the_member_has_no_open_affiliation(self, write_conn, two_coded_sakhas, type_pks):
        """The old ON CONFLICT DO NOTHING hid this; it must now surface."""
        home, away = two_coded_sakhas
        holder = _create(write_conn, home, type_pks["REGULAR"])
        newcomer = _create(write_conn, home, type_pks["REGULAR"])
        typed = str(9_600_000 + int(uuid4().int % 300_000))
        _attend(write_conn, holder["sangha_sevi_pk"], away, typed)
        with pytest.raises(HTTPException) as exc:
            _attend(write_conn, newcomer["sangha_sevi_pk"], away, typed)
        assert exc.value.status_code == 409


# ── registration_claim DDL + patch ──────────────────���──────────────────────

class TestRegistrationClaimLegacyColumns:
    def test_columns_exist_with_false_default(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'nss' AND table_name = 'registration_claim'
              AND column_name IN ('is_legacy_member', 'darshak_is_legacy_member')
        """)
        rows = {r[0]: r for r in cur.fetchall()}
        cur.close()
        assert set(rows) == {"is_legacy_member", "darshak_is_legacy_member"}
        for _name, nullable, default in rows.values():
            assert nullable == "NO" and "false" in default.lower()

    def test_no_existing_row_disagrees_with_its_number(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM nss.registration_claim
            WHERE is_legacy_member <> (claimed_local_sakha_number IS NOT NULL)
               OR darshak_is_legacy_member <> (darshak_local_sakha_number IS NOT NULL)
        """)
        assert cur.fetchone()[0] == 0
        cur.close()

    def test_check_rejects_a_number_without_the_legacy_flag(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("SELECT EXISTS (SELECT 1 FROM nss.user_account)")
        if not cur.fetchone()[0]:
            pytest.skip("No user_account to anchor a claim row.")
        cur.execute("SAVEPOINT chk")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("""
                INSERT INTO nss.registration_claim (
                    user_account_pk, person_pk, claimed_organization_pk,
                    claimed_membership_type_master_data_pk,
                    claimed_local_sakha_number, is_legacy_member, claim_status)
                SELECT ua.user_account_pk, ua.person_pk, o.organization_pk, md.master_data_pk,
                       'X1', FALSE, 'PENDING'
                FROM nss.user_account ua, nss.organization o, nss.master_data md
                LIMIT 1
            """)
        cur.execute("ROLLBACK TO SAVEPOINT chk")
        cur.close()

    def test_patch_is_idempotent_on_an_already_patched_table(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE is_legacy_member) FROM nss.registration_claim")
        before = cur.fetchone()
        cur.execute(PATCH_SQL.read_text())
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE is_legacy_member) FROM nss.registration_claim")
        assert cur.fetchone() == before
        cur.close()

    def test_patch_defaults_existing_claims_by_whether_they_carry_a_number(self):
        """Source check of the default-derivation (a pre-existing-DB-only path
        that cannot be exercised on an already-patched database)."""
        sql = PATCH_SQL.read_text()
        assert "SET is_legacy_member = TRUE" in sql and "claimed_local_sakha_number IS NOT NULL" in sql
        assert "SET darshak_is_legacy_member = TRUE" in sql and "darshak_local_sakha_number IS NOT NULL" in sql
        assert "NULLIF(BTRIM(claimed_local_sakha_number), '')" in sql, "blank numbers normalised first"
        # The data change happens only when the column is first added.
        assert sql.index("ADD COLUMN is_legacy_member") < sql.index("SET is_legacy_member = TRUE")
        assert "IF NOT EXISTS" in sql
        assert "chk_registration_claim_legacy_home" in sql and "chk_registration_claim_legacy_darshak" in sql


# ── build wiring (source) ──────────────────────────────────────────────────

class TestPatchWiring:
    @pytest.mark.parametrize("script,needle", [
        ("database/scripts/02_build.sh", "06_authentication/06_registration_claim_legacy_member_patch.sql"),
        ("render_build.sh", "06_authentication/06_registration_claim_legacy_member_patch.sql"),
        ("database/scripts/02_build.ps1", "06_authentication\\06_registration_claim_legacy_member_patch.sql"),
    ])
    def test_patch_is_wired_after_the_registration_claim_ddl(self, script, needle):
        text = (REPO / script).read_text()
        assert needle in text
        assert text.index("03_registration_claim.sql") < text.index(needle)

    @pytest.mark.parametrize("script", ["database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"])
    def test_validate_checks_the_columns_and_constraints(self, script):
        text = (REPO / script).read_text()
        assert "is_legacy_member" in text
        assert "chk_registration_claim_legacy_home" in text
