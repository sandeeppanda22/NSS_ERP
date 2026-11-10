"""
Finance — Bye-Law disbursement controls for Kendra / central Mahila Sangha money
(api/services/finance_authority.py, api/routers/finance_authority.py).

Rules under test (NSS Bye-Law F[b], F[c], Treasurer duty (7)(b); Mahila 7(ii)/(iii); FIN-BR-040):
  * a Kendra payment needs the Governing Body resolution, a permitted purpose and the PRESIDENT's written order;
  * only the seated TREASURER may start the disbursement, only the seated SECRETARY may countersign
    (joint operation), the two must be different people, and completion needs both signatures;
  * a vacant seat blocks the disbursement - the super administrator has no override;
  * other levels (a Sakha) are NOT subject to these rules (FIN-BR-044: no rule is invented).

Real integration tests (nothing mocked); NEVER RUN against a database when this file was written.
"""

from datetime import date, timedelta

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    _login_headers,
    admin_h,
    admin_user,
    make_fund,
    make_scope,
    make_txn,
    make_world,
    make_year,
    move,
    post_txn,
    raw_move,
    register_org_pk,
)
from tests.reparent_support import kendra_pks, seat, vacate_seat
from tests.attendance_support import _with_sevi_pk
from tests.api.test_correspondence import _create_admin_with_scope


# ═══════════════════════════════════════════════════════════════════════
# Cast: the Kendra Governing Body's President / Treasurer / Secretary, each a Kendra administrator
# (so they may call the finance endpoints) AND seated in the real office.
# ═══════════════════════════════════════════════════════════════════════

def _officer(write_conn):
    return _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_KENDRA_ADMIN", scope_level="NSS-WIDE", organization_pk=None))


@pytest.fixture(scope="module")
def officers(client, write_conn):
    kendra_pk, body_pk = kendra_pks(write_conn)
    cast = {"kendra_pk": kendra_pk, "body_pk": body_pk}
    for role in ("president", "treasurer", "secretary", "outsider"):
        person = _officer(write_conn)
        cast[role] = person
        cast[f"{role}_h"] = _login_headers(client, person["sangha_sevi_id"], person["password"])
    for role, position in (("president", "PRESIDENT"), ("treasurer", "TREASURER"), ("secretary", "SECRETARY")):
        seat(write_conn, body_pk, position, cast[role])
    return cast


def _ensure_seated(write_conn, officers):
    for role, position in (("president", "PRESIDENT"), ("treasurer", "TREASURER"), ("secretary", "SECRETARY")):
        seat(write_conn, officers["body_pk"], position, officers[role])


def _authority_body(**over):
    body = {
        "resolution_reference": "GB/2026/114", "resolution_date": (date.today() - timedelta(days=5)).isoformat(),
        "scheme_description": "Annual upkeep of Nilachala Kutir", "purpose_code": "KENDRA_NILACHALA_KUTIR",
        "parichalak_consulted": False,
        "president_order_reference": "PRES/2026/21", "president_order_date": (date.today() - timedelta(days=2)).isoformat(),
    }
    body.update(over)
    return body


def _kendra_payment(client, admin_h, officers, amount="500.00") -> dict:
    """An APPROVED payment in a fresh Kendra scope (the world is built by the super administrator)."""
    w = make_world(client, admin_h, officers["kendra_pk"])
    txn = make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE", amount=amount)
    pk = txn["financial_transaction_pk"]
    move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
    move(client, admin_h, "transactions", pk, "APPROVED")
    r = client.post(f"{BASE}/transactions/{pk}/payments", headers=admin_h, json={
        "payment_date": txn["transaction_date"], "amount": amount, "paid_to": "Temple priest", "payment_method_code": "BANK_TRANSFER"})
    assert r.status_code == 201, r.text
    payment = r.json()
    move(client, admin_h, "payments", payment["financial_payment_pk"], "APPROVED")
    return {"w": w, "txn": txn, "payment": payment, "pk": payment["financial_payment_pk"]}


def _authority(client, headers, pk, body=None, kind="payments"):
    return client.put(f"{BASE}/{kind}/{pk}/authority", headers=headers, json=body or _authority_body())


# ═══════════════════════════════════════════════════════════════════════
# Which levels are bound
# ═══════════════════════════════════════════════════════════════════════

class TestApplicability:
    def test_kendra_payment_is_bound_by_the_bye_law(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        r = client.get(f"{BASE}/payments/{p['pk']}/authority", headers=admin_h)
        assert r.status_code == 200, r.text
        state = r.json()
        assert state["applies"] is True and state["bye_law_basis"] == "KENDRA"
        assert state["authority"] is None and "Record the Governing Body resolution" in state["next_step"]
        assert any("President" in line for line in state["requirements"])

    def test_sakha_payment_is_not_bound_and_keeps_working(self, client, admin_h, register_org_pk):
        w = make_world(client, admin_h, register_org_pk)
        txn = make_txn(client, admin_h, w["year"], w["scope"], kind="EXPENSE", amount="100.00")
        pk = txn["financial_transaction_pk"]
        move(client, admin_h, "transactions", pk, "PENDING_APPROVAL")
        move(client, admin_h, "transactions", pk, "APPROVED")
        pay = client.post(f"{BASE}/transactions/{pk}/payments", headers=admin_h, json={
            "payment_date": txn["transaction_date"], "amount": "100.00"}).json()["financial_payment_pk"]
        state = client.get(f"{BASE}/payments/{pay}/authority", headers=admin_h).json()
        assert state["applies"] is False and state["bye_law_basis"] is None
        assert _authority(client, admin_h, pay).status_code == 422          # nothing to record at this level
        for target in ("APPROVED", "INITIATED", "COMPLETED"):               # FIN-BR-044: no Kendra rule invented
            assert move(client, admin_h, "payments", pay, target)["status"] == target

    def test_reference_lists_the_permitted_purposes(self, client, admin_h):
        codes = {p["code"] for p in client.get(f"{BASE}/reference", headers=admin_h).json()["disbursement_purposes"]}
        assert {"KENDRA_NILACHALA_KUTIR", "KENDRA_MATHA_GURU_DHAMA_DONATION", "MAHILA_SPECIFIC_PURPOSE"} <= codes


# ═══════════════════════════════════════════════════════════════════════
# Steps 1 and 2: the resolution, the purpose and the President's order
# ═══════════════════════════════════��═══════════════════════════════════

class TestRecordingTheAuthority:
    def test_cannot_disburse_without_any_authority(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        r = raw_move(client, officers["treasurer_h"], "payments", p["pk"], "INITIATED")
        assert r.status_code == 422 and "resolution" in r.json()["detail"].lower()

    def test_authority_is_recorded_and_returned(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        r = _authority(client, admin_h, p["pk"])
        assert r.status_code == 200, r.text
        a = r.json()["authority"]
        assert a["resolution_reference"] == "GB/2026/114" and a["purpose_code"] == "KENDRA_NILACHALA_KUTIR"
        assert a["president_person_pk"] == str(officers["president"]["person_pk"])      # the seated President at recording
        assert a["treasurer_signed_at"] is None and "Treasurer" in r.json()["next_step"]

    @pytest.mark.parametrize("over", [
        {"president_order_reference": None, "president_order_date": None},                  # Kendra: the order is mandatory
        {"president_order_date": (date.today() - timedelta(days=30)).isoformat()},          # order before the resolution
        {"purpose_code": "MAHILA_SPECIFIC_PURPOSE"},                                        # another body's purpose
        {"purpose_code": "NOT_A_PURPOSE"},
        {"resolution_date": (date.today() + timedelta(days=3)).isoformat()},                # a future resolution
        {"resolution_reference": "  "},
        {"purpose_code": "KENDRA_SATSIKSHYA_BISTAR", "parichalak_consulted": False},        # F[A](vi): consult the Parichalak
    ])
    def test_incomplete_or_wrong_authority_is_422(self, client, admin_h, officers, over):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"], _authority_body(**over)).status_code == 422

    def test_satsiksha_bistar_is_accepted_after_consulting_the_parichalak(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        r = _authority(client, admin_h, p["pk"], _authority_body(purpose_code="KENDRA_SATSIKSHYA_BISTAR", parichalak_consulted=True))
        assert r.status_code == 200, r.text

    def test_no_president_seated_blocks_recording(self, client, write_conn, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        vacate_seat(write_conn, officers["body_pk"], "PRESIDENT")
        try:
            r = _authority(client, admin_h, p["pk"])
            assert r.status_code == 422 and "President" in r.json()["detail"]
        finally:
            _ensure_seated(write_conn, officers)


# ═══════════════════════════════════════════════════════════════════════
# Step 3: Treasurer disburses, Secretary countersigns
# ═══════════════════════════════════════════════════════════════════════

class TestJointOperation:
    def test_full_chain(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        t = raw_move(client, officers["treasurer_h"], "payments", p["pk"], "INITIATED")
        assert t.status_code == 200, t.text
        state = client.get(f"{BASE}/payments/{p['pk']}/authority", headers=admin_h).json()
        assert state["authority"]["treasurer_person_pk"] == str(officers["treasurer"]["person_pk"])
        assert state["next_step"] == "The Secretary countersigns"
        # completion needs the Secretary too
        early = raw_move(client, officers["treasurer_h"], "payments", p["pk"], "COMPLETED")
        assert early.status_code == 422 and "jointly" in early.json()["detail"]
        c = client.post(f"{BASE}/payments/{p['pk']}/countersign", headers=officers["secretary_h"])
        assert c.status_code == 200, c.text
        assert c.json()["authority"]["secretary_person_pk"] == str(officers["secretary"]["person_pk"])
        assert raw_move(client, officers["treasurer_h"], "payments", p["pk"], "COMPLETED").status_code == 200

    def test_only_the_treasurer_may_start_the_disbursement(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        for who in ("outsider_h", "secretary_h", "president_h"):
            assert raw_move(client, officers[who], "payments", p["pk"], "INITIATED").status_code == 403, who

    def test_super_administrator_has_no_override(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        assert raw_move(client, admin_h, "payments", p["pk"], "INITIATED").status_code == 403

    def test_only_the_secretary_may_countersign_and_only_after_the_treasurer(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        # before the disbursement is started there is nothing to countersign
        assert client.post(f"{BASE}/payments/{p['pk']}/countersign", headers=officers["secretary_h"]).status_code == 422
        assert raw_move(client, officers["treasurer_h"], "payments", p["pk"], "INITIATED").status_code == 200
        for who in ("treasurer_h", "outsider_h", "president_h", "admin_h"):
            headers = admin_h if who == "admin_h" else officers[who]
            assert client.post(f"{BASE}/payments/{p['pk']}/countersign", headers=headers).status_code == 403, who
        assert client.post(f"{BASE}/payments/{p['pk']}/countersign", headers=officers["secretary_h"]).status_code == 200
        assert client.post(f"{BASE}/payments/{p['pk']}/countersign", headers=officers["secretary_h"]).status_code == 422  # once

    def test_authority_is_locked_after_the_treasurer_signs(self, client, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        assert raw_move(client, officers["treasurer_h"], "payments", p["pk"], "INITIATED").status_code == 200
        assert _authority(client, admin_h, p["pk"], _authority_body(resolution_reference="CHANGED")).status_code == 422

    def test_vacant_treasurer_seat_blocks_the_disbursement(self, client, write_conn, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        vacate_seat(write_conn, officers["body_pk"], "TREASURER")
        try:
            r = raw_move(client, officers["treasurer_h"], "payments", p["pk"], "INITIATED")
            assert r.status_code == 422 and "Treasurer" in r.json()["detail"]
        finally:
            _ensure_seated(write_conn, officers)

    def test_treasurer_and_secretary_cannot_be_the_same_person(self, client, write_conn, admin_h, officers):
        p = _kendra_payment(client, admin_h, officers)
        assert _authority(client, admin_h, p["pk"]).status_code == 200
        assert raw_move(client, officers["treasurer_h"], "payments", p["pk"], "INITIATED").status_code == 200
        # the Treasurer is also seated as Secretary: still cannot countersign their own disbursement
        seat(write_conn, officers["body_pk"], "SECRETARY", officers["treasurer"])
        try:
            assert client.post(f"{BASE}/payments/{p['pk']}/countersign", headers=officers["treasurer_h"]).status_code == 422
        finally:
            _ensure_seated(write_conn, officers)


# ═══════════════════════════════════════════════════════════════════════
# Transfers out of Kendra money are disbursements too
# ═══════════════════════════════════════════════════════════════════════

class TestKendraTransfers:
    def _transfer(self, client, admin_h, officers, register_org_pk):
        src = make_world(client, admin_h, officers["kendra_pk"])
        dst = make_world(client, admin_h, register_org_pk)
        post_txn(client, admin_h, make_txn(client, admin_h, src["year"], src["scope"], fund=src["fund"], amount="900.00"))
        r = client.post(f"{BASE}/transfers", headers=admin_h, json={
            "financial_year_pk": src["year"]["financial_year_pk"], "source_scope_pk": src["scope"]["financial_scope_pk"],
            "destination_scope_pk": dst["scope"]["financial_scope_pk"], "source_fund_pk": src["fund"]["fund_master_pk"],
            "destination_fund_pk": dst["fund"]["fund_master_pk"], "amount": "300.00",
            "transfer_date": src["year"]["start_date"], "purpose": "Support to an affiliated Sakha"})
        assert r.status_code == 201, r.text
        pk = r.json()["financial_transfer_pk"]
        move(client, admin_h, "transfers", pk, "PENDING_APPROVAL")
        move(client, admin_h, "transfers", pk, "APPROVED")
        return pk

    def test_executing_needs_the_authority_and_the_treasurer(self, client, admin_h, officers, register_org_pk):
        pk = self._transfer(client, admin_h, officers, register_org_pk)
        assert raw_move(client, officers["treasurer_h"], "transfers", pk, "EXECUTED").status_code == 422     # no authority
        body = _authority_body(purpose_code="KENDRA_AFFILIATED_SAKHA")
        assert _authority(client, admin_h, pk, body, kind="transfers").status_code == 200
        assert raw_move(client, admin_h, "transfers", pk, "EXECUTED").status_code == 403                    # not the Treasurer
        assert raw_move(client, officers["treasurer_h"], "transfers", pk, "EXECUTED").status_code == 200
        assert raw_move(client, officers["treasurer_h"], "transfers", pk, "COMPLETED").status_code == 422   # needs the Secretary
        assert client.post(f"{BASE}/transfers/{pk}/countersign", headers=officers["secretary_h"]).status_code == 200
        assert raw_move(client, officers["treasurer_h"], "transfers", pk, "COMPLETED").status_code == 200
