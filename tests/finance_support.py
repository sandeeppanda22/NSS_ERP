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
from decimal import Decimal
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
# Passing tests KEEP their rows (conftest releases the per-test savepoint; only the module savepoint rolls back), so a
# year created by one test still exists in the next. The create-year API caps at 2100, hence a bounded range that
# make_year() walks, REUSING a year already in the wanted state and skipping one in any other state.
_YEAR_RANGE = range(2040, 2101)
_year_counter = itertools.cycle(_YEAR_RANGE)


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
    """
    A Financial Year in the wanted state (OPEN by default, else PLANNED). Needs a global FINANCE_APPROVE caller.
    An existing year of that state (within this helper's range) is REUSED - tests build their own scopes and funds, so
    sharing a year is harmless and keeps the number of years tiny; one is created only when none exists. Years that an
    earlier test closed or part-closed are in another state, so they are never picked.
    """
    wanted = "OPEN" if open_ else "PLANNED"
    years = client.get(f"{BASE}/years", headers=headers).json()["items"]
    for y in years:
        if y["status"] == wanted and int(y["year_code"][:4]) in _YEAR_RANGE:
            return y
    for _ in _YEAR_RANGE:
        r = client.post(f"{BASE}/years", json={"start_year": next(_year_counter)}, headers=headers)
        if r.status_code == 409:
            continue                                   # that year exists in some other state: try the next one
        assert r.status_code == 201, r.text
        year = r.json()
        return move(client, headers, "years", year["financial_year_pk"], "OPEN") if open_ else year
    raise AssertionError(f"no {wanted} financial year could be created or reused")


def adopt_templates(client, headers, organization_pk) -> dict | None:
    """
    Copy the Kendra head templates into a Sangha's catalogue (idempotent). Needs FINANCE_APPROVE: a caller without it
    gets None and relies on an approver having done it (make_world does).
    """
    r = client.post(f"{BASE}/heads/adopt-templates", json={"organization_pk": str(organization_pk)}, headers=headers)
    if r.status_code == 403:
        return None
    assert r.status_code == 200, r.text
    return r.json()


def head_pk(client, headers, scope, code) -> str:
    """The pk of the head with this CODE that a transaction in *scope* may use (its organization's own, or a template)."""
    r = client.get(f"{BASE}/heads", params={"for_scope_pk": scope["financial_scope_pk"], "q": code, "page_size": 200}, headers=headers)
    assert r.status_code == 200, r.text
    found = [h for h in r.json()["items"] if h["head_code"] == code]
    assert found, f"no ACTIVE head {code} for scope {scope['scope_code']}; adopt the templates first"
    return found[0]["finance_head_pk"]


def txn_body(client, headers, w, *, code=None, kind="INCOME", amount="10", fund=None, txn_date=None, **over) -> dict:
    """A transaction request body for world *w* (year + scope) using the head with this code (default: a plain income / expense)."""
    body = {
        "financial_year_pk": w["year"]["financial_year_pk"], "financial_scope_pk": w["scope"]["financial_scope_pk"],
        "transaction_type": kind,
        "finance_head_pk": head_pk(client, headers, w["scope"], code or ("PRANAMI_ANNUAL" if kind == "INCOME" else "EXPENSE_GENERAL")),
        "amount": amount, "transaction_date": txn_date or w["year"]["start_date"],
    }
    if fund is not None:
        body["fund_master_pk"] = fund["fund_master_pk"]
    body.update(over)
    return body


def make_scope(client, headers, organization_pk=None, *, activate_with=None, **over) -> dict:
    """A scope in DRAFT; pass activate_with=<approver headers> to move it to ACTIVE. A Sangha's scope also gets the head templates adopted."""
    body = {"scope_code": f"FS{uuid4().hex[:8].upper()}", "scope_name": f"Test scope {uuid4().hex[:5]}",
            "scope_type": "ORGANIZATION" if organization_pk else "SPECIAL_PURPOSE"}
    if organization_pk is not None:
        body["organization_pk"] = str(organization_pk)
    body.update(over)
    r = client.post(f"{BASE}/scopes", json=body, headers=headers)
    assert r.status_code == 201, r.text
    scope = r.json()
    if organization_pk is not None:
        adopt_templates(client, activate_with or headers, organization_pk)
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
    """Record a DRAFT transaction. *category* is the finance head CODE (default: a plain Pranami / general expense head)."""
    body = {
        "financial_year_pk": year["financial_year_pk"], "financial_scope_pk": scope["financial_scope_pk"],
        "transaction_type": kind,
        "finance_head_pk": head_pk(client, headers, scope, category or ("PRANAMI_ANNUAL" if kind == "INCOME" else "EXPENSE_GENERAL")),
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


# ═══════════════════════════════════════════════════════════════════════
# Customization (heads, accounts) and UPI collection helpers
# ═══════════════════════════════════════════════════════════════════════

import datetime as _dt
from types import SimpleNamespace

from api.config import settings
from api.services import upi_gateway


def new_code(prefix="T") -> str:
    """A unique UPPER_SNAKE head / credential code."""
    return f"{prefix}{uuid4().hex[:8].upper()}"


@pytest.fixture
def mock_gateway(monkeypatch):
    """
    Switch the MOCK UPI gateway ON for one test: enables the provider and defines a throw-away credential set in the
    environment (the way production does - nothing is in the database). Yields .ref (the credential-set NAME to put on an
    account) and .secret (its webhook secret, to sign events with).
    """
    monkeypatch.setattr(settings, "UPI_GATEWAY_ENABLED_PROVIDERS", "MOCK")
    ref = new_code("G")
    secret = "whsec_" + uuid4().hex
    monkeypatch.setenv(f"UPI_{ref}_KEY_ID", "key_" + uuid4().hex[:8])
    monkeypatch.setenv(f"UPI_{ref}_KEY_SECRET", "ksec_" + uuid4().hex)
    monkeypatch.setenv(f"UPI_{ref}_WEBHOOK_SECRET", secret)
    return SimpleNamespace(ref=ref, secret=secret)


def make_account(client, headers, organization_pk, gw=None, **over) -> dict:
    """A receiving account of a Sangha; with *gw* it is wired to the MOCK gateway credential set."""
    body = {"organization_pk": str(organization_pk), "account_label": f"Acct {uuid4().hex[:8]}", "account_holder_name": "Sakha Sangha",
            "bank_name": "State Bank of India", "account_number_last4": "1234", "ifsc_code": "SBIN0001234", "upi_vpa": "sakha@oksbi"}
    if gw is not None:
        body.update(gateway_provider="MOCK", gateway_credential_ref=gw.ref)
    body.update(over)
    r = client.post(f"{BASE}/accounts", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def make_head(client, headers, organization_pk, *, direction="INCOME", **over) -> dict:
    """A custom finance head of a Sangha (or, with organization_pk=None, a Kendra template)."""
    body = {"organization_pk": str(organization_pk) if organization_pk else None, "head_code": new_code("H"),
            "head_name": f"Head {uuid4().hex[:6]}", "direction": direction}
    body.update(over)
    r = client.post(f"{BASE}/heads", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def upi_world(client, admin_h_, org_pk, gw, *, restricted=False, **head_over) -> dict:
    """
    A Sangha ready to collect Pranami by UPI: OPEN year, ACTIVE scope + fund, a receiving account on the MOCK gateway and a
    Pranami head that collects into them. Returns {world, account, head}.
    """
    w = make_world(client, admin_h_, org_pk)
    fund = w["fund"]
    if restricted:
        fund = make_fund(client, admin_h_, w["scope"]["financial_scope_pk"], activate_with=admin_h_, fund_type="SPECIFIC_PURPOSE",
                         is_restricted=True, restriction_purpose="Temple repair")
    account = make_account(client, admin_h_, org_pk, gw)
    body = {"head_name": "UPI Pranami", "is_pranami": True, "allow_upi": True,
            "collection_scope_pk": w["scope"]["financial_scope_pk"], "collection_fund_pk": fund["fund_master_pk"],
            "collection_account_pk": account["financial_account_pk"]}
    if restricted:
        body.update(is_restricted=True, restriction_purpose="Temple repair")
    body.update(head_over)
    head = make_head(client, admin_h_, org_pk, **body)
    return {"world": w, "account": account, "head": head, "fund": fund}


def ensure_open_year_covering_today(write_conn) -> None:
    """UPI payments are booked on the day they are paid, so an OPEN financial year must cover today (the seeded one lapses)."""
    today = _dt.date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    code = f"{start_year}-{(start_year + 1) % 100:02d}"
    cur = write_conn.cursor()
    cur.execute("SELECT 1 FROM nss.financial_year WHERE is_active = TRUE AND status = 'OPEN' AND start_date <= %s AND end_date >= %s", (today, today))
    if cur.fetchone():
        return
    cur.execute("SELECT 1 FROM nss.financial_year WHERE year_code = %s", (code,))
    if cur.fetchone():
        cur.execute("UPDATE nss.financial_year SET status = 'OPEN' WHERE year_code = %s", (code,))
    else:
        cur.execute("INSERT INTO nss.financial_year (year_code, start_date, end_date, status) VALUES (%s, %s, %s, 'OPEN')",
                    (code, _dt.date(start_year, 4, 1), _dt.date(start_year + 1, 3, 31)))


def create_request(client, headers, head, amount="500.00", **over):
    body = {"finance_head_pk": head["finance_head_pk"], "amount": amount}
    body.update(over)
    return client.post(f"{BASE}/payment-requests", json=body, headers=headers)


def webhook(client, gw, order_id, *, kind="payment.paid", amount=None, payment_id=None, event_id=None, secret=None, provider="MOCK",
            tamper=None):
    """POST a (by default correctly SIGNED) MOCK webhook, the way the gateway would. *tamper* edits the body AFTER signing."""
    raw, headers = upi_gateway.build_mock_event(secret=secret or gw.secret, order_id=order_id, kind=kind, amount=amount,
                                                payment_id=payment_id, event_id=event_id)
    if tamper:
        raw = raw.replace(*tamper)
    return client.post(f"{BASE}/gateway/webhook/{provider}", content=raw, headers=headers)


def pay_request(client, gw, request, **over):
    """Simulate the payer paying a request in full (a signed 'paid' webhook for its order)."""
    amount = over.pop("amount", request["amount"])
    return webhook(client, gw, request["provider_order_id"], amount=Decimal(str(amount)) if amount is not None else None, **over)
