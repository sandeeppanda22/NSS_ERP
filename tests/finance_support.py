"""
NSS ERP — shared fixtures/helpers for the Finance test modules
(tests/api/test_finance.py, tests/security/test_finance_security.py).

Builds on the Attendance cast (tests/attendance_support.py: real rows, rolled
back with the module SAVEPOINT).

Cast (the "register" Sakha = S1, the "other" Sakha = S2):
  admin_user    NSS_ERP_ADMIN, NSS-WIDE            VIEW + MANAGE + APPROVE, global; the super administrator
                                                   (exempt from the maker-checker rule)
  kendra_admin  NSS_ERP_KENDRA_ADMIN, NSS-WIDE     VIEW + MANAGE + APPROVE, global, NOT a super administrator
  sakha_admin   NSS_ERP_SAKHA_ADMIN, scoped S1     VIEW + MANAGE for S1's financial scopes (no APPROVE)
  other_admin   NSS_ERP_SAKHA_ADMIN, scoped S2     a foreign Sakha
  viewer_user   NSS_ERP_AUDITOR, scoped S1         FINANCE_VIEW only
  plain_member  person + login, no role at all     no FINANCE_* permission

Prerequisites (database build): Phase 11i DDL, the FINANCE_* permissions patch
and the Finance reference-data patch (PAYMENT_METHOD incl. UPI, id sequences).

Each test builds its own financial year (start year 2090-2100: far from any real
one, distinct within a test) so tests never depend on, or disturb, seeded data.
"""

import itertools
from datetime import date
from uuid import uuid4

import pytest

from tests.attendance_support import (  # noqa: F401  (re-exported to test modules)
    FAKE_UUID,
    _create_admin_with_scope,
    _login_headers,
    _with_sevi_pk,
    admin_h,
    admin_user,
    new_member,
    other_admin,
    other_admin_h,
    other_org_pk,
    plain_member,
    plain_member_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
)

BASE = "/api/v1/finance"
# Cycled, not counted: every test rolls back, so years may repeat ACROSS tests, and the create-year API caps at 2100.
_year_counter = itertools.cycle(range(2090, 2101))


@pytest.fixture(scope="module")
def kendra_admin(write_conn):
    return _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_KENDRA_ADMIN", scope_level="NSS-WIDE", organization_pk=None))


@pytest.fixture(scope="module")
def kendra_h(client, kendra_admin):
    return _login_headers(client, kendra_admin["sangha_sevi_id"], kendra_admin["password"])


@pytest.fixture(scope="module")
def viewer_user(write_conn, register_org_pk):
    """FINANCE_VIEW only (NSS_ERP_AUDITOR), scoped to the register Sakha."""
    return _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_AUDITOR", scope_level="SAKHA", organization_pk=register_org_pk))


@pytest.fixture(scope="module")
def viewer_h(client, viewer_user):
    return _login_headers(client, viewer_user["sangha_sevi_id"], viewer_user["password"])


# ═══════════════════════════════════════════════════════════════════════
# Builders (every one asserts the success status so a failure points at the cause)
# ═══════════════════════════════════════════════════════════════════════

def move(client, headers, kind, pk, status_code_, remarks=None, expect=200):
    r = client.post(f"{BASE}/{kind}/{pk}/transition", json={"status": status_code_, "remarks": remarks}, headers=headers)
    assert r.status_code == expect, f"{kind} -> {status_code_}: {r.status_code} {r.text}"
    return r.json() if expect == 200 else r


def raw_move(client, headers, kind, pk, status_code_, remarks=None):
    return client.post(f"{BASE}/{kind}/{pk}/transition", json={"status": status_code_, "remarks": remarks}, headers=headers)


def make_year(client, headers, *, open_: bool = True) -> dict:
    """A fresh Financial Year (OPEN by default). Needs a global FINANCE_APPROVE caller."""
    r = client.post(f"{BASE}/years", json={"start_year": next(_year_counter)}, headers=headers)
    assert r.status_code == 201, r.text
    year = r.json()
    if open_:
        year = move(client, headers, "years", year["financial_year_pk"], "OPEN")
    return year


def make_scope(client, headers, organization_pk=None, *, activate_with=None, **over) -> dict:
    """A scope in DRAFT; pass activate_with=<approver headers> to move it to ACTIVE."""
    body = {"scope_code": f"FS{uuid4().hex[:8].upper()}", "scope_name": f"Test scope {uuid4().hex[:5]}",
            "scope_type": "ORGANIZATION" if organization_pk else "SPECIAL_PURPOSE"}
    if organization_pk is not None:
        body["organization_pk"] = str(organization_pk)
    body.update(over)
    r = client.post(f"{BASE}/scopes", json=body, headers=headers)
    assert r.status_code == 201, r.text
    scope = r.json()
    if activate_with is not None:
        scope = move(client, activate_with, "scopes", scope["financial_scope_pk"], "ACTIVE")
    return scope


def make_fund(client, headers, scope_pk, *, activate_with=None, **over) -> dict:
    body = {"fund_code": f"FD{uuid4().hex[:8].upper()}", "fund_name": f"Test fund {uuid4().hex[:5]}",
            "fund_type": "GENERAL", "financial_scope_pk": str(scope_pk)}
    body.update(over)
    r = client.post(f"{BASE}/funds", json=body, headers=headers)
    assert r.status_code == 201, r.text
    fund = r.json()
    if activate_with is not None:
        fund = move(client, activate_with, "funds", fund["fund_master_pk"], "ACTIVE")
    return fund


def make_txn(client, headers, year, scope, *, fund=None, kind="INCOME", category=None, amount="1000.00",
             txn_date=None, **over) -> dict:
    body = {
        "financial_year_pk": year["financial_year_pk"], "financial_scope_pk": scope["financial_scope_pk"],
        "transaction_type": kind,
        "transaction_category": category or ("PRANAMI_ANNUAL" if kind == "INCOME" else "EXPENSE_GENERAL"),
        "amount": amount,
        "transaction_date": (txn_date or date.fromisoformat(year["start_date"]).replace(day=15, month=5)).isoformat(),
    }
    if fund is not None:
        body["fund_master_pk"] = fund["fund_master_pk"]
    body.update(over)
    r = client.post(f"{BASE}/transactions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def post_txn(client, headers, txn) -> dict:
    """DRAFT -> PENDING_APPROVAL -> APPROVED -> POSTED (the caller must be the super admin or the approver differ)."""
    pk = txn["financial_transaction_pk"]
    for target in ("PENDING_APPROVAL", "APPROVED", "POSTED"):
        txn = move(client, headers, "transactions", pk, target)
    return txn


def make_world(client, admin_h_, org_pk) -> dict:
    """An OPEN year, an ACTIVE scope owned by *org_pk* and an ACTIVE general fund."""
    year = make_year(client, admin_h_)
    scope = make_scope(client, admin_h_, org_pk, activate_with=admin_h_)
    fund = make_fund(client, admin_h_, scope["financial_scope_pk"], activate_with=admin_h_)
    return {"year": year, "scope": scope, "fund": fund}
