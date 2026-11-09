"""
NSS ERP — Aadhaar exposure security tests (GDR-011, PER-BR-081).

Part 1 (DB-free; runs with ``pytest --noconftest``): source/OpenAPI sweeps that
pin WHERE Aadhaar-related fields may appear — no response model carries
``aadhaar_encrypted``/``aadhaar_hash``; the full number only leaves through
``PersonAadhaarResponse``; ``aadhaar_last4`` only in the two gated person
responses; every writer validates through the one shared validator; the audit
trigger redacts the columns.

Part 2 (needs the DB + ``cryptography``): a response sweep — after a number is
stored, no read endpoint returns the digits, the blob or the hash — and the
permission footprint of ``PERSON_VIEW_SENSITIVE``.
"""

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "api"

ALLOWED_LAST4_FILES = {
    "api/routers/person.py", "api/routers/admin.py", "api/schemas/person.py",
    "api/schemas/admin.py", "api/services/aadhaar_service.py", "api/services/person_scope.py",
}
GATED_RESPONSES = {"PersonResponse", "PersonProfileResponse"}


def _py_files():
    return [p for p in API.rglob("*.py") if "__pycache__" not in p.parts]


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _class_fields(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names = [t.target.id for t in node.body
                     if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)]
            yield node.name, names


# ── Part 1: DB-free sweeps ───────────────────────────────────────────────

class TestSourceSweeps:
    def test_no_pydantic_model_carries_ciphertext_or_hash(self):
        for p in _py_files():
            for cls, fields in _class_fields(p):
                assert "aadhaar_encrypted" not in fields and "aadhaar_hash" not in fields, (_rel(p), cls)

    def test_full_number_field_only_in_requests_and_the_reveal_response(self):
        for p in _py_files():
            for cls, fields in _class_fields(p):
                if "aadhaar_number" in fields and cls.endswith("Response"):
                    assert cls == "PersonAadhaarResponse", (_rel(p), cls)

    def test_last4_only_in_the_two_gated_responses_with_the_on_file_flag(self):
        seen = set()
        for p in _py_files():
            for cls, fields in _class_fields(p):
                if "aadhaar_last4" in fields:
                    assert cls in GATED_RESPONSES, (_rel(p), cls)
                    assert "aadhaar_full_on_file" in fields, cls
                    seen.add(cls)
        assert seen == GATED_RESPONSES

    def test_last4_token_is_confined_to_the_known_files(self):
        for p in _py_files():
            if "aadhaar_last4" in p.read_text(encoding="utf-8"):
                assert _rel(p) in ALLOWED_LAST4_FILES, f"{_rel(p)} mentions aadhaar_last4"

    def test_ciphertext_column_is_only_read_as_a_flag_or_by_the_reveal(self):
        pat = re.compile(r"aadhaar_encrypted")
        for p in _py_files():
            if _rel(p) == "api/services/aadhaar_service.py":
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if pat.search(line) and not line.strip().startswith(("#", '"""', "-", "*")):
                    ok = ("IS NOT NULL" in line or "SELECT aadhaar_encrypted" in line
                          or line.strip().startswith('"SELECT aadhaar_encrypted')
                          or "aadhaar_encrypted" in line and "never" in line.lower())
                    assert ok, f"{_rel(p)}:{i} reads aadhaar_encrypted: {line.strip()}"
            # the hash column is touched only inside the shared writer
            text = p.read_text(encoding="utf-8")
            assert "aadhaar_hash" not in re.sub(r"#.*|\"\"\"[\s\S]*?\"\"\"", "", text), _rel(p)

    def test_gated_endpoints_pass_through_the_one_helper(self):
        person = (API / "routers" / "person.py").read_text(encoding="utf-8")
        admin = (API / "routers" / "admin.py").read_text(encoding="utf-8")
        assert "gate_aadhaar_fields(conn, person_pk, user, result)" in person
        assert "gate_aadhaar_fields(conn, person_pk, user, profile)" in admin

    def test_writers_use_the_shared_validator_and_the_one_writer(self):
        for rel in ("routers/registration.py", "routers/admin.py", "routers/claim_approval.py",
                    "schemas/admin.py"):
            assert "aadhaar_field_validator" in (API / rel).read_text(encoding="utf-8"), rel
        helpers = (API / "helpers.py").read_text(encoding="utf-8")
        assert "set_person_aadhaar" in helpers
        # nobody else updates the three columns directly
        for p in _py_files():
            if _rel(p) == "api/services/aadhaar_service.py":
                continue
            assert not re.search(r"SET[^\"']*aadhaar_", p.read_text(encoding="utf-8")), _rel(p)

    def test_self_service_profile_request_has_no_aadhaar_field(self):
        from api.schemas.auth import UpdateProfileRequest
        assert "aadhaar_number" not in UpdateProfileRequest.model_fields

    def test_audit_trigger_redacts_the_columns(self):
        sql = (ROOT / "database/ddl/01_foundation/15_audit_trigger.sql").read_text(encoding="utf-8")
        for col in ("aadhaar_encrypted", "aadhaar_hash", "aadhaar_last4"):
            assert f"'{col}'" in sql
        assert "[REDACTED]" in sql and "v_old_log" in sql and "v_new_log" in sql

    def test_env_example_and_config_declare_the_keys(self):
        env = (API / ".env.example").read_text(encoding="utf-8")
        from api.config import settings
        for name in ("AADHAAR_ENCRYPTION_KEYS", "AADHAAR_HASH_PEPPER", "AADHAAR_REVEAL_RATE_LIMIT"):
            assert name in env and hasattr(settings, name)
        assert settings.AADHAAR_REVEAL_RATE_LIMIT


@pytest.fixture(scope="module")
def spec():
    from api.main import app
    return app.openapi()


class TestOpenApiSweep:
    def test_ciphertext_and_hash_appear_in_no_schema(self, spec):
        for name, schema in spec["components"]["schemas"].items():
            props = schema.get("properties", {})
            assert "aadhaar_encrypted" not in props and "aadhaar_hash" not in props, name

    def test_full_number_only_in_requests_and_reveal_response(self, spec):
        for name, schema in spec["components"]["schemas"].items():
            if "aadhaar_number" in schema.get("properties", {}):
                assert name == "PersonAadhaarResponse" or name.endswith("Request"), name

    def test_reveal_route_exists_once_and_is_get_only(self, spec):
        paths = [p for p in spec["paths"] if "aadhaar" in p]
        assert paths == ["/api/v1/person/persons/{person_pk}/aadhaar"]
        assert list(spec["paths"][paths[0]]) == ["get"]


class TestRequestSchemas:
    VALID = "234567890124"

    def _valid(self):
        from tests.api.test_aadhaar_service import make_aadhaar
        return make_aadhaar()

    def test_registration_and_admin_requests_validate_and_normalise(self):
        from api.routers.admin import AdminCreatePersonRequest
        from api.routers.claim_approval import UpdateClaimRequest
        from api.routers.registration import RegisterRequest
        from api.schemas.admin import UpdatePersonProfileRequest
        n = self._valid()
        spaced = f"{n[:4]} {n[4:8]} {n[8:]}"
        for model in (RegisterRequest, AdminCreatePersonRequest, UpdateClaimRequest, UpdatePersonProfileRequest):
            assert "aadhaar_number" in model.model_fields, model
            f = model.model_fields["aadhaar_number"]
            assert not f.is_required()
        assert UpdatePersonProfileRequest(aadhaar_number=spaced).aadhaar_number == n
        assert UpdatePersonProfileRequest(aadhaar_number="").aadhaar_number == ""
        assert UpdatePersonProfileRequest().aadhaar_number is None
        assert UpdateClaimRequest(aadhaar_number=spaced).aadhaar_number == n
        with pytest.raises(ValueError):
            UpdatePersonProfileRequest(aadhaar_number="1234")
        with pytest.raises(ValueError):
            UpdateClaimRequest(aadhaar_number="2345678901xx")


# ── Part 2: DB response sweep + permission footprint ────────────────────

try:
    from tests.aadhaar_support import (  # noqa: F401  (fixtures)
        aadhaar_keys, admin_h, admin_user, auditor, auditor_h, db_row, new_subject, other_org_pk,
        register_org_pk, requires_crypto, sakha_admin, sakha_admin_h, sakha_pks, sens_in,
        sens_in_h, set_number, subject, subject_h, unique_aadhaar,
    )
except Exception:  # pragma: no cover - collection must survive a missing optional import
    requires_crypto = pytest.mark.skip(reason="aadhaar support unavailable")


@pytest.mark.integration
@requires_crypto
class TestResponseSweep:
    def test_no_read_endpoint_returns_digits_blob_or_hash(
        self, client, write_conn, admin_h, sakha_admin_h, sens_in_h, register_org_pk, aadhaar_keys
    ):
        m = new_subject(write_conn, register_org_pk, "AadhaarSweep")
        n = unique_aadhaar()
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
        row = db_row(write_conn, m["person_pk"])
        # Values that must never appear anywhere (digits, stored hash, stored blob).
        secrets_ = [n, row["hash"], row["enc"].decode()]
        # Column NAMES must not appear in ordinary responses; the audit endpoints legitimately list
        # the field names (with the value redacted), so they are exempt from the name check only.
        column_names = ["aadhaar_encrypted", "aadhaar_hash"]
        urls = [
            f"/api/v1/person/persons/{m['person_pk']}",
            f"/api/v1/person/persons/{m['person_pk']}/addresses",
            "/api/v1/person/persons?limit=500",
            f"/api/v1/person/persons/search?q={m['sangha_sevi_id']}",
            f"/api/v1/admin/persons/{m['person_pk']}",
            f"/api/v1/membership/sangha-sevi/{m['sangha_sevi_pk']}" if m.get("sangha_sevi_pk") else "/api/v1/person/persons?limit=1",
            f"/api/v1/audit/change-log?table_name=person&record_pk={m['person_pk']}",
            f"/api/v1/audit/events?record_pk={m['person_pk']}",
        ]
        for headers in (admin_h, sens_in_h, sakha_admin_h):
            for url in urls:
                r = client.get(url, headers=headers)
                body = r.text
                checks = secrets_ if "/audit/" in url else secrets_ + column_names
                for s in checks:
                    assert s not in body, f"{url} leaked {s[:6]}… to a caller"

    def test_change_log_shows_the_columns_only_as_redacted(self, client, write_conn, admin_h, register_org_pk, aadhaar_keys):
        m = new_subject(write_conn, register_org_pk, "AadhaarLog")
        n = unique_aadhaar()
        assert set_number(client, admin_h, m["person_pk"], n).status_code == 200
        r = client.get(f"/api/v1/audit/change-log?table_name=person&record_pk={m['person_pk']}&limit=500",
                       headers=admin_h)
        if r.status_code == 200:
            rows = [x for x in r.json() if x["field_name"].startswith("aadhaar_")]
            assert rows
            assert all(x["new_value"] == "[REDACTED]" for x in rows)
            assert n not in json.dumps(r.json())


@pytest.mark.integration
class TestPermissionFootprint:
    def _holders(self, write_conn):
        cur = write_conn.cursor()
        cur.execute(
            """SELECT rm.role_code FROM nss.role_permission rp
               JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk
               JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
               WHERE pm.permission_code = 'PERSON_VIEW_SENSITIVE' AND rp.is_active = TRUE
               ORDER BY rm.role_code"""
        )
        return [r[0] for r in cur.fetchall()]

    def test_only_admin_and_kendra_admin_hold_person_view_sensitive(self, write_conn):
        assert self._holders(write_conn) == ["NSS_ERP_ADMIN", "NSS_ERP_KENDRA_ADMIN"]

    def test_auditor_grant_is_soft_deleted_not_removed(self, write_conn):
        cur = write_conn.cursor()
        cur.execute(
            """SELECT rp.is_active, rp.deleted_at IS NOT NULL FROM nss.role_permission rp
               JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk
               JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
               WHERE pm.permission_code = 'PERSON_VIEW_SENSITIVE' AND rm.role_code = 'NSS_ERP_AUDITOR'"""
        )
        rows = cur.fetchall()
        assert all(a is False and d is True for a, d in rows)
