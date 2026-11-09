"""
NSS ERP — shared fixtures/helpers for the Aadhaar test modules (GDR-011):
tests/api/test_aadhaar.py and tests/security/test_aadhaar_security.py.

Cast (register Sakha unless noted), built on tests/attendance_support.py:
  admin_user / admin_h     NSS_ERP_ADMIN, NSS-WIDE            (PERSON_VIEW_SENSITIVE, global)
  sens_in / sens_in_h      NSS_ERP_KENDRA_ADMIN, SAKHA scope  (PERSON_VIEW_SENSITIVE, register Sakha only)
  sens_out / sens_out_h    NSS_ERP_KENDRA_ADMIN, SAKHA scope at the OTHER Sakha
  sakha_admin / _h         NSS_ERP_SAKHA_ADMIN (PERSON_VIEW + PERSON_MANAGE, NO PERSON_VIEW_SENSITIVE)
  auditor / auditor_h      NSS_ERP_AUDITOR NSS-WIDE (grant revoked by patch 07)
  subject                  plain member homed at the register Sakha, owns the number
  subject_h                that member's login

Random AES keys/pepper are installed on ``settings`` for the module
(``aadhaar_keys``); every test that needs them uses the fixture, and the whole
module is skipped when the ``cryptography`` package is missing.
"""

import base64
import importlib.util
import os

import pytest

from api.config import settings
from api.services.aadhaar_service import verhoeff_valid
from tests.attendance_support import (  # noqa: F401  (fixtures re-exported)
    FAKE_UUID, _create_admin_with_scope, _headers_fixture, _login_headers, _scoped_user,
    _with_sevi_pk, admin_h, admin_user, new_member, other_org_pk, register_org_pk,
    sakha_admin, sakha_admin_h, sakha_pks,
)

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
requires_crypto = pytest.mark.skipif(not HAS_CRYPTO, reason="'cryptography' is not installed")


def make_aadhaar(first: str = "2", body: str = "3456789012") -> str:
    """12 digits, valid Verhoeff, not starting 0/1 — random body for uniqueness via *body*."""
    payload = (first + body)[:11]
    for d in "0123456789":
        if verhoeff_valid(payload + d):
            return payload + d
    raise AssertionError


def unique_aadhaar() -> str:
    """A fresh valid number (the unique index would 409 a reused one)."""
    while True:
        digits = "".join(str(b % 10) for b in os.urandom(10))
        n = make_aadhaar("3", digits)
        if n[0] not in "01":
            return n


@pytest.fixture(scope="module")
def aadhaar_keys():
    old = (settings.AADHAAR_ENCRYPTION_KEYS, settings.AADHAAR_HASH_PEPPER)
    settings.AADHAAR_ENCRYPTION_KEYS = "t1:" + base64.b64encode(os.urandom(32)).decode()
    settings.AADHAAR_HASH_PEPPER = "test-pepper-" + os.urandom(6).hex()
    yield
    settings.AADHAAR_ENCRYPTION_KEYS, settings.AADHAAR_HASH_PEPPER = old


@pytest.fixture
def no_aadhaar_keys():
    old = (settings.AADHAAR_ENCRYPTION_KEYS, settings.AADHAAR_HASH_PEPPER)
    settings.AADHAAR_ENCRYPTION_KEYS = ""
    settings.AADHAAR_HASH_PEPPER = ""
    yield
    settings.AADHAAR_ENCRYPTION_KEYS, settings.AADHAAR_HASH_PEPPER = old


@pytest.fixture(scope="module")
def sens_in(write_conn, register_org_pk):
    return _scoped_user(write_conn, role_code="NSS_ERP_KENDRA_ADMIN", organization_pk=register_org_pk)


@pytest.fixture(scope="module")
def sens_out(write_conn, other_org_pk):
    return _scoped_user(write_conn, role_code="NSS_ERP_KENDRA_ADMIN", organization_pk=other_org_pk)


@pytest.fixture(scope="module")
def auditor(write_conn):
    return _with_sevi_pk(
        write_conn,
        _create_admin_with_scope(
            write_conn, role_code="NSS_ERP_AUDITOR", scope_level="NSS-WIDE", organization_pk=None,
        ),
    )


@pytest.fixture(scope="module")
def subject(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "AadhaarSubject")


sens_in_h = _headers_fixture("sens_in_h", "sens_in")
sens_out_h = _headers_fixture("sens_out_h", "sens_out")
auditor_h = _headers_fixture("auditor_h", "auditor")
subject_h = _headers_fixture("subject_h", "subject")


def db_row(write_conn, person_pk) -> dict:
    cur = write_conn.cursor()
    cur.execute(
        "SELECT aadhaar_encrypted, aadhaar_hash, aadhaar_last4 FROM nss.person WHERE person_pk = %s",
        (str(person_pk),),
    )
    enc, hashed, last4 = cur.fetchone()
    return {"enc": None if enc is None else bytes(enc), "hash": hashed, "last4": last4}


def set_number(client, admin_headers, person_pk, number: str):
    return client.patch(
        f"/api/v1/admin/persons/{person_pk}", headers=admin_headers,
        json={"aadhaar_number": number},
    )


def new_subject(write_conn, register_org_pk, label: str) -> dict:
    return new_member(write_conn, register_org_pk, label)
