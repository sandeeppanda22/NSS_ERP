"""
Shared cast and helpers for the Sakha approval chain tests (tests/api/test_finance_approval.py,
tests/security/test_finance_approval_security.py).

A "chain world" is one Sakha with: an OPEN year, an ACTIVE scope and fund, five heads (income that skips approval, income that does
not, a spend with a Treasurer limit, a spend with no limit, a reimbursement head) and a TREASURER, a PRESIDENT and a SECRETARY seated
on its Governing Body (new members, any previous holder of those seats is vacated; all rolled back with the module SAVEPOINT).
The entries are recorded by the Sakha admin (who holds FINANCE_MANAGE + FINANCE_CONFIGURE for that Sakha, not APPROVE).
"""

from uuid import uuid4

from tests.attendance_support import _seat_exclusive
from tests.finance_support import (  # noqa: F401  (re-exported)
    BASE,
    _login_headers,
    make_head,
    make_world,
    new_member,
)
from tests.reparent_support import vacate_seat


def seat_person(write_conn, org_pk, position_code: str, label: str) -> dict:
    """A fresh member of *org_pk*, seated as *position_code* on its Governing Body."""
    person = new_member(write_conn, org_pk, label)
    _seat_exclusive(write_conn, organization_pk=org_pk, position_code=position_code,
                    person_pk=person["person_pk"], sangha_sevi_pk=person["sangha_sevi_pk"])
    return person


def vacate(write_conn, org_pk, position_code: str) -> None:
    cur = write_conn.cursor()
    cur.execute(
        "SELECT bm.body_master_pk FROM nss.body_master bm JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk "
        "WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s AND bm.is_active = TRUE LIMIT 1", (str(org_pk),))
    vacate_seat(write_conn, str(cur.fetchone()[0]), position_code)


def chain_world(client, admin_h, write_conn, org_pk, *, limit="5000.00") -> dict:
    world = make_world(client, admin_h, org_pk)
    heads = {
        "skip": make_head(client, admin_h, org_pk, direction="INCOME", head_name="Pranami (no approval)", skips_approval=True),
        "income": make_head(client, admin_h, org_pk, direction="INCOME", head_name="Donation"),
        "limited": make_head(client, admin_h, org_pk, direction="EXPENSE", head_name="Electricity", treasurer_limit=limit),
        "unlimited": make_head(client, admin_h, org_pk, direction="EXPENSE", head_name="Repairs"),
        "reimburse": make_head(client, admin_h, org_pk, direction="EXPENSE", head_name="Member reimbursement",
                               requires_member=True, treasurer_limit=limit),
    }
    people = {
        "treasurer": seat_person(write_conn, org_pk, "TREASURER", "FinTreasurer"),
        "president": seat_person(write_conn, org_pk, "PRESIDENT", "FinPresident"),
        "secretary": seat_person(write_conn, org_pk, "SECRETARY", "FinSecretary"),
    }
    return {"w": world, "heads": heads, "people": people, "org_pk": str(org_pk)}


def login(client, person: dict) -> dict:
    return _login_headers(client, person["sangha_sevi_id"], person["password"])


def record(client, headers, cw, head_key: str, amount: str, *, kind: str | None = None, **over):
    """POST /transactions as *headers* (a recorder); returns the response so a test can assert on failures too."""
    head = cw["heads"][head_key]
    body = {
        "financial_year_pk": cw["w"]["year"]["financial_year_pk"], "financial_scope_pk": cw["w"]["scope"]["financial_scope_pk"],
        "fund_master_pk": cw["w"]["fund"]["fund_master_pk"],
        "transaction_type": kind or ("INCOME" if head["direction"] == "INCOME" else "EXPENSE"),
        "finance_head_pk": head["finance_head_pk"], "amount": amount, "transaction_date": cw["w"]["year"]["start_date"],
        "description": f"chain test {uuid4().hex[:6]}",
    }
    body.update(over)
    r = client.post(f"{BASE}/transactions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def add_bill(client, headers, txn_pk, amount: str, expect=201, **over):
    body = {"vendor_name": "OPTCL", "bill_number": f"B{uuid4().hex[:5]}", "bill_date": "2090-05-15", "amount": amount}
    body.update(over)
    r = client.post(f"{BASE}/transactions/{txn_pk}/bills", json=body, headers=headers)
    assert r.status_code == expect, r.text
    return r.json()


def submit(client, headers, txn_pk, expect=200):
    r = client.post(f"{BASE}/transactions/{txn_pk}/transition", json={"status": "PENDING_APPROVAL"}, headers=headers)
    assert r.status_code == expect, r.text
    return r.json()


def decide(client, headers, txn_pk, action="approve", remarks=None, expect=200):
    r = client.post(f"{BASE}/transactions/{txn_pk}/{action}", json={"remarks": remarks}, headers=headers)
    assert r.status_code == expect, f"{action}: {r.status_code} {r.text}"
    return r.json()


def get_txn(client, headers, pk) -> dict:
    r = client.get(f"{BASE}/transactions/{pk}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def spend_ready(client, recorder_h, cw, head_key: str, amount: str) -> dict:
    """A DRAFT spend with one bill that covers it, submitted for approval. Returns the entry."""
    txn = record(client, recorder_h, cw, head_key, amount)
    add_bill(client, recorder_h, txn["financial_transaction_pk"], amount)
    submit(client, recorder_h, txn["financial_transaction_pk"])
    return txn
