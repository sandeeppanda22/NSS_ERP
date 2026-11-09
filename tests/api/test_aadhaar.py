"""
NSS ERP — Aadhaar capture, gated last-4 and reveal endpoint (GDR-011).

Real rows, rolled back with the module SAVEPOINT. Needs a bootstrapped DB and
the ``cryptography`` package (skipped without it). Service-level crypto tests
live in tests/api/test_aadhaar_service.py; response/source sweeps and the
permission matrix in tests/security/test_aadhaar_security.py.

NEVER RUN against the project DB at the time of writing.
"""

import pytest

from tests.aadhaar_support import (  # noqa: F401  (fixtures)
    FAKE_UUID, admin_h, admin_user, aadhaar_keys, auditor, auditor_h, db_row, make_aadhaar,
    new_subject, no_aadhaar_keys, other_org_pk, register_org_pk, requires_crypto, sakha_admin,
    sakha_admin_h, sakha_pks, sens_in, sens_in_h, sens_out, sens_out_h, set_number, subject,
    subject_h, unique_aadhaar,
)

pytestmark = [pytest.mark.integration, requires_crypto]

PER = "/api/v1/person/persons"


class TestCapture:
    def test_admin_patch_stores_ciphertext_hash_and_derived_last4(
        self, client, write_conn, admin_h, subject, aadhaar_keys
    ):
        n = unique_aadhaar()
        spaced = f"{n[:4]} {n[4:8]}-{n[8:]}"
        r = set_number(client, admin_h, subject["person_pk"], spaced)
        assert r.status_code == 200, r.text
        row = db_row(write_conn, subject["person_pk"])
        assert row["enc"] is not None and n.encode() not in row["enc"]
        assert row["enc"].startswith(b"v1:t1:")
        assert row["last4"] == n[-4:]
        assert row["hash"] and len(row["hash"]) == 64 and row["hash"] != n

    @pytest.mark.parametrize("bad", ["1234", "12345678901", "2345678901234", "abcd efgh ijkl",
                                     "000000000000", "123456789012"])
    def test_malformed_or_bad_checksum_is_422_and_nothing_is_stored(
        self, client, write_conn, admin_h, register_org_pk, aadhaar_keys, bad
    ):
        m = new_subject(write_conn, register_org_pk, "AadhaarBad")
        r = set_number(client, admin_h, m["person_pk"], bad)
        assert r.status_code == 422, r.text
        assert db_row(write_conn, m["person_pk"]) == {"enc": None, "hash": None, "last4": None}

    def test_leading_one_with_valid_checksum_is_422(self, client, write_conn, admin_h, register_org_pk, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarOne")
        assert set_number(client, admin_h, m["person_pk"], make_aadhaar("1")).status_code == 422

    def test_blank_clears_all_three_columns(self, client, write_conn, admin_h, register_org_pk, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarClear")
        assert set_number(client, admin_h, m["person_pk"], unique_aadhaar()).status_code == 200
        assert db_row(write_conn, m["person_pk"])["enc"] is not None
        assert set_number(client, admin_h, m["person_pk"], "").status_code == 200
        assert db_row(write_conn, m["person_pk"]) == {"enc": None, "hash": None, "last4": None}

    def test_duplicate_number_is_409_and_does_not_name_the_holder(
        self, client, write_conn, admin_h, register_org_pk, aadhaar_keys
    ):
        a = new_subject(write_conn, register_org_pk, "AadhaarDupA")
        b = new_subject(write_conn, register_org_pk, "AadhaarDupB")
        n = unique_aadhaar()
        assert set_number(client, admin_h, a["person_pk"], n).status_code == 200
        r = set_number(client, admin_h, b["person_pk"], n)
        assert r.status_code == 409, r.text
        assert a["person_pk"] not in r.text and n not in r.text
        assert db_row(write_conn, b["person_pk"])["enc"] is None

    def test_same_person_may_resubmit_the_same_number(self, client, write_conn, admin_h, register_org_pk, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarSame")
        n = unique_aadhaar()
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200

    def test_without_keys_capture_is_503_and_stores_nothing(
        self, client, write_conn, admin_h, register_org_pk, no_aadhaar_keys
    ):
        m = new_subject(write_conn, register_org_pk, "AadhaarNoKeys")
        r = set_number(client, admin_h, m["person_pk"], unique_aadhaar())
        assert r.status_code == 503, r.text
        assert "not configured" in r.json()["detail"]
        assert db_row(write_conn, m["person_pk"]) == {"enc": None, "hash": None, "last4": None}

    def test_aadhaar_only_patch_is_not_a_422_no_fields(self, client, write_conn, admin_h, register_org_pk, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarOnly")
        assert set_number(client, admin_h, m["person_pk"], unique_aadhaar()).status_code == 200

    def test_admin_create_person_accepts_aadhaar(self, client, write_conn, admin_h, aadhaar_keys):
        cur = write_conn.cursor()
        cur.execute("""SELECT md.master_data_pk FROM nss.master_data md
                       JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                       WHERE mc.category_code = 'GENDER' AND md.is_active LIMIT 1""")
        gender = str(cur.fetchone()[0])
        n = unique_aadhaar()
        r = client.post("/api/v1/admin/persons", headers=admin_h, json={
            "first_name": "Aadhaarcreate", "last_name": "Test", "date_of_birth": "1990-01-01",
            "gender_master_data_pk": gender, "email": "aadhaar.create.test@example.org",
            "aadhaar_number": n,
        })
        assert r.status_code == 201, r.text
        assert n not in r.text
        row = db_row(write_conn, r.json()["person_pk"])
        assert row["last4"] == n[-4:] and row["enc"] is not None

    def test_admin_create_person_rejects_bad_number(self, client, admin_h, aadhaar_keys):
        r = client.post("/api/v1/admin/persons", headers=admin_h, json={
            "first_name": "Aadhaarbad", "last_name": "Test", "date_of_birth": "1990-01-01",
            "gender_master_data_pk": FAKE_UUID, "email": "aadhaar.bad.test@example.org",
            "aadhaar_number": "1234",
        })
        assert r.status_code == 422

    def test_self_service_profile_never_stores_aadhaar(self, client, write_conn, register_org_pk, aadhaar_keys):
        from tests.aadhaar_support import _login_headers
        m = new_subject(write_conn, register_org_pk, "AadhaarSelfEdit")
        h = _login_headers(client, m["sangha_sevi_id"], m["password"])
        r = client.patch("/api/v1/auth/profile", headers=h,
                         json={"aadhaar_number": unique_aadhaar(), "remarks": "self edit"})
        assert r.status_code == 200, r.text
        assert db_row(write_conn, m["person_pk"]) == {"enc": None, "hash": None, "last4": None}


@pytest.fixture(scope="module")
def gating_holder(client, write_conn, admin_h, register_org_pk, aadhaar_keys):
    m = new_subject(write_conn, register_org_pk, "AadhaarHolder")
    n = unique_aadhaar()
    assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
    from tests.aadhaar_support import _login_headers
    m["number"] = n
    m["headers"] = _login_headers(client, m["sangha_sevi_id"], m["password"])
    return m


class TestLastFourGating:
    def test_self_sees_last4_and_flag(self, client, gating_holder):
        d = client.get(f"{PER}/{gating_holder['person_pk']}", headers=gating_holder["headers"]).json()
        assert d["aadhaar_last4"] == gating_holder["number"][-4:]
        assert d["aadhaar_full_on_file"] is True

    def test_global_admin_sees_last4(self, client, gating_holder, admin_h):
        d = client.get(f"{PER}/{gating_holder['person_pk']}", headers=admin_h).json()
        assert d["aadhaar_last4"] == gating_holder["number"][-4:]

    def test_permitted_admin_in_scope_sees_last4(self, client, gating_holder, sens_in_h):
        d = client.get(f"{PER}/{gating_holder['person_pk']}", headers=sens_in_h).json()
        assert d["aadhaar_last4"] == gating_holder["number"][-4:]

    def test_permitted_admin_out_of_scope_cannot_even_open_the_person(self, client, gating_holder, sens_out_h):
        assert client.get(f"{PER}/{gating_holder['person_pk']}", headers=sens_out_h).status_code == 403

    def test_ordinary_admin_gets_null(self, client, gating_holder, sakha_admin_h):
        r = client.get(f"{PER}/{gating_holder['person_pk']}", headers=sakha_admin_h)
        assert r.status_code == 200
        d = r.json()
        assert d["aadhaar_last4"] is None and d["aadhaar_full_on_file"] is None

    def test_auditor_gets_null(self, client, gating_holder, auditor_h):
        r = client.get(f"{PER}/{gating_holder['person_pk']}", headers=auditor_h)
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            d = r.json()
            assert d["aadhaar_last4"] is None and d["aadhaar_full_on_file"] is None

    def test_admin_profile_view_is_gated_the_same_way(self, client, gating_holder, admin_h, sakha_admin_h):
        url = f"/api/v1/admin/persons/{gating_holder['person_pk']}"
        full = client.get(url, headers=admin_h).json()
        assert full["aadhaar_last4"] == gating_holder["number"][-4:] and full["aadhaar_full_on_file"] is True
        plain = client.get(url, headers=sakha_admin_h).json()
        assert plain["aadhaar_last4"] is None and plain["aadhaar_full_on_file"] is None
        assert "aadhaar_number" not in full and "aadhaar_hash" not in full


@pytest.fixture(scope="module")
def reveal_holder(client, write_conn, admin_h, register_org_pk, aadhaar_keys):
    m = new_subject(write_conn, register_org_pk, "AadhaarReveal")
    m["number"] = unique_aadhaar()
    assert set_number(client, admin_h, m["person_pk"], m["number"]).status_code == 200
    return m


class TestReveal:
    def test_global_admin_gets_decrypted_digits_only(self, client, reveal_holder, admin_h):
        r = client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=admin_h)
        assert r.status_code == 200, r.text
        assert r.json() == {"person_pk": reveal_holder["person_pk"], "aadhaar_number": reveal_holder["number"]}
        assert r.headers["cache-control"].startswith("no-store")

    def test_permitted_admin_in_scope_gets_200(self, client, reveal_holder, sens_in_h):
        r = client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=sens_in_h)
        assert r.status_code == 200 and r.json()["aadhaar_number"] == reveal_holder["number"]

    def test_permitted_admin_out_of_scope_is_403(self, client, reveal_holder, sens_out_h):
        assert client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=sens_out_h).status_code == 403

    def test_ordinary_admin_is_403(self, client, reveal_holder, sakha_admin_h):
        r = client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=sakha_admin_h)
        assert r.status_code == 403 and reveal_holder["number"] not in r.text

    def test_auditor_is_403(self, client, reveal_holder, auditor_h):
        assert client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=auditor_h).status_code == 403

    def test_the_person_themself_does_not_get_the_full_number(self, client, write_conn, register_org_pk, admin_h, aadhaar_keys):
        from tests.aadhaar_support import _login_headers
        m = new_subject(write_conn, register_org_pk, "AadhaarSelf")
        n = unique_aadhaar()
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
        h = _login_headers(client, m["sangha_sevi_id"], m["password"])
        r = client.get(f"{PER}/{m['person_pk']}/aadhaar", headers=h)
        assert r.status_code == 403 and n not in r.text

    def test_unauthenticated_is_401(self, client, reveal_holder):
        assert client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar").status_code == 401

    def test_unknown_person_is_404(self, client, admin_h):
        assert client.get(f"{PER}/{FAKE_UUID}/aadhaar", headers=admin_h).status_code == 404

    def test_no_ciphertext_is_404_not_on_record(self, client, write_conn, register_org_pk, admin_h):
        m = new_subject(write_conn, register_org_pk, "AadhaarNone")
        r = client.get(f"{PER}/{m['person_pk']}/aadhaar", headers=admin_h)
        assert r.status_code == 404
        assert "not on record" in r.json()["detail"].lower()

    def test_successful_reveal_writes_an_audit_row_without_the_value(self, client, write_conn, reveal_holder, admin_h, admin_user):
        assert client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=admin_h).status_code == 200
        cur = write_conn.cursor()
        cur.execute(
            """SELECT summary, detail::text, is_success, actor_user_account_pk
               FROM nss.system_event_log
               WHERE action = 'VIEW_SENSITIVE' AND table_name = 'person' AND record_pk = %s
               ORDER BY event_at DESC""",
            (reveal_holder["person_pk"],),
        )
        rows = cur.fetchall()
        assert rows, "reveal must write a VIEW_SENSITIVE audit row"
        summary, detail, ok, actor = rows[0]
        assert ok is True and actor is not None
        assert reveal_holder["number"] not in (summary or "") and reveal_holder["number"] not in (detail or "")

    def test_denied_reveal_writes_no_audit_row(self, client, write_conn, reveal_holder, sakha_admin_h):
        cur = write_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nss.system_event_log WHERE action='VIEW_SENSITIVE' AND record_pk=%s",
                    (reveal_holder["person_pk"],))
        before = cur.fetchone()[0]
        client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=sakha_admin_h)
        cur.execute("SELECT COUNT(*) FROM nss.system_event_log WHERE action='VIEW_SENSITIVE' AND record_pk=%s",
                    (reveal_holder["person_pk"],))
        assert cur.fetchone()[0] == before

    def test_corrupted_ciphertext_is_500_without_a_value(self, client, write_conn, register_org_pk, admin_h, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarCorrupt")
        n = unique_aadhaar()
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.person SET aadhaar_encrypted = %s WHERE person_pk = %s",
                    (b"v1:t1:AAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", m["person_pk"]))
        r = client.get(f"{PER}/{m['person_pk']}/aadhaar", headers=admin_h)
        assert r.status_code == 500 and n not in r.text and "aadhaar_number" not in r.text

    def test_reveal_is_rate_limited_per_user(self, client, reveal_holder, admin_h):
        codes = [client.get(f"{PER}/{reveal_holder['person_pk']}/aadhaar", headers=admin_h).status_code
                 for _ in range(12)]
        assert codes[0] == 200 and 429 in codes     # default AADHAAR_REVEAL_RATE_LIMIT = 10/minute


class TestAuditRedaction:
    def test_trigger_redacts_aadhaar_values_in_both_logs(self, client, write_conn, admin_h, register_org_pk, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarAudit")
        n = unique_aadhaar()
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
        cur = write_conn.cursor()
        cur.execute(
            """SELECT field_name, old_value, new_value FROM nss.field_change_log
               WHERE table_name='person' AND record_pk=%s AND field_name LIKE 'aadhaar_%%'""",
            (m["person_pk"],),
        )
        rows = cur.fetchall()
        assert {r[0] for r in rows} >= {"aadhaar_encrypted", "aadhaar_hash", "aadhaar_last4"}
        for _, old, new in rows:
            assert (new or "[REDACTED]") == "[REDACTED]" and (old or "[REDACTED]") == "[REDACTED]"
        cur.execute(
            "SELECT detail::text FROM nss.system_event_log WHERE table_name='person' AND record_pk=%s",
            (m["person_pk"],),
        )
        blob = " ".join(r[0] or "" for r in cur.fetchall())
        assert n not in blob and f'"aadhaar_last4": "{n[-4:]}"' not in blob
