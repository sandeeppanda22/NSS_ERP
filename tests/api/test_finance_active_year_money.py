"""
Incoming and outgoing money belongs to the ACTIVE financial year (owner request 2026-11-25: "all the incoming and outgoing transactions should only be the
active FY"). The parts that need no database (``--noconftest``); the end-to-end behaviour is the integration class at the bottom (never run against a
database when written):

  * new entries and transfers: only in the current year (already so, finance.py::require_current_year) - and not for a Sangha that has started closing;
  * a RECEIPT (incoming evidence) and a PAYMENT (outgoing) are made only for a transaction of the current year;
  * a UPI payment is booked only into an OPEN year that covers its date, and is held for review when its Sangha has started closing the year;
  * the Transactions and Transfers lists open on the active year ("All years" and the closed ones stay one click away: looking back is how audit works).
"""
import inspect
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from api.routers import finance as F
from api.routers import finance_upi as U

from tests.finance_support import admin_h, admin_user, register_org_pk, sakha_pks, single_approval_levels  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[2]
FIN_JS = (ROOT / "frontend/assets/js/finance.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend/admin.html").read_text(encoding="utf-8")


def test_a_receipt_and_a_payment_are_made_only_in_the_active_year():
    # in the active year AND while it is OPEN (a closing or closed year pauses them), and not for a Sangha that has started closing its books
    assert 'require_current_year(cur, txn["financial_year_pk"], "receipt", open_only=True)' in inspect.getsource(F.create_receipt)
    assert 'require_current_year(cur, txn["financial_year_pk"], "payment", open_only=True)' in inspect.getsource(F.create_payment)
    for fn in (F.create_receipt, F.create_payment):
        assert 'check_sangha_year_open(cur, txn["financial_year_pk"], txn["scope_organization_pk"], new=True)' in inspect.getsource(fn)
    # finishing what is in progress is NOT a new record: approve / post / issue / complete are not re-checked against the active year
    for fn in (F.transition_transaction, F._check_transaction):
        assert "require_current_year(" not in inspect.getsource(fn), fn.__name__


def test_a_receipt_or_payment_for_another_year_is_refused_by_the_one_rule():
    class Cur:
        description = [("financial_year_pk",), ("year_code",), ("status",), ("start_date",), ("end_date",)]

        def execute(self, *_a, **_k):
            pass

        def fetchall(self):
            return [("a", "2026-27", "OPEN", None, None), ("b", "2027-28", "OPEN", None, None)]

    from fastapi import HTTPException

    F.require_current_year(Cur(), "b", "receipt")
    with pytest.raises(HTTPException) as e:
        F.require_current_year(Cur(), "a", "payment")
    assert e.value.status_code == 422 and "2027-28" in e.value.detail and "payment" in e.value.detail


def test_a_closing_sangha_holds_an_online_payment_for_review_instead_of_booking_it():
    src = inspect.getsource(U._book_one)
    assert "F.check_sangha_year_open(cur, year_pk, F._scope_row(cur, scope_pk)[\"organization_pk\"], new=True)" in src
    assert src.index("F._check_transaction(") < src.index("check_sangha_year_open") < src.index("INSERT INTO nss.financial_transaction")
    assert "except HTTPException as exc:" in inspect.getsource(U._post_paid_request)                       # the refusal becomes the review reason, not a lost payment


def test_the_year_an_online_payment_is_booked_into_is_an_open_one_covering_its_date():
    src = inspect.getsource(U._post_paid_request)
    assert "status = 'OPEN'" in src and "start_date <= %s AND end_date >= %s" in src and "No OPEN financial year covers the payment date" in src


def test_the_lists_open_on_the_active_year_and_all_years_is_one_click_away():
    assert 'if (!this._finTxnYearChosen) { this.finTxnYear = this.finActiveYearPk; this._finTxnYearChosen = true; }' in FIN_JS
    assert 'if (!this._finTransferYearChosen) { this.finTransferYear = this.finActiveYearPk; this._finTransferYearChosen = true; }' in FIN_JS
    assert "this.finTxnYear = this.finActiveYearPk;" in FIN_JS and "this.finTransferYear = this.finActiveYearPk;" in FIN_JS      # clearing the filters returns to it
    assert HTML.count('<option value="">All years (including closed)</option>') == 2


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_the_active_year_pk_follows_the_current_year():
    start = FIN_JS.index("            get finCurrentYear() {")
    end = FIN_JS.index("            get finOtherLiveYears() {")
    script = f"""
    const host = {{ finYears: [], {FIN_JS[start:end].rstrip().rstrip(",")} }};
    const set = (rows) => {{ host.finYears = rows.map(([code, status]) => ({{ year_code: code, status, financial_year_pk: "pk-" + code }})); }};
    const r = {{}};
    set([["2025-26", "CLOSED"], ["2026-27", "OPEN"], ["2027-28", "PLANNED"]]); r.open = host.finActiveYearPk;
    set([["2026-27", "CLOSING"], ["2027-28", "PLANNED"]]); r.closing = host.finActiveYearPk;
    set([]); r.none = host.finActiveYearPk;
    console.log(JSON.stringify(r));
    """
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip().splitlines()[-1]) == {"open": "pk-2026-27", "closing": "pk-2026-27", "none": ""}


@pytest.mark.integration
class TestThroughTheApi:
    def test_a_receipt_and_a_payment_for_an_older_years_transaction_are_refused(self, client, admin_h, register_org_pk, single_approval_levels):
        from tests.finance_support import BASE, make_scope, make_txn, make_year, move, new_year, post_txn

        old = make_year(client, admin_h)
        scope = make_scope(client, admin_h, register_org_pk, activate_with=admin_h)
        income = post_txn(client, admin_h, make_txn(client, admin_h, old, scope, kind="INCOME", amount="100.00"))
        expense = post_txn(client, admin_h, make_txn(client, admin_h, old, scope, kind="EXPENSE", amount="40.00"))
        later = new_year(client, admin_h, 2112)
        if later is not None:
            move(client, admin_h, "years", later["financial_year_pk"], "OPEN")                      # now the old year is not the active one
            r = client.post(f"{BASE}/transactions/{income['financial_transaction_pk']}/receipts", json={"receipt_date": old["start_date"], "amount": "100.00"}, headers=admin_h)
            assert r.status_code == 422 and "current financial year" in r.text
            r = client.post(f"{BASE}/transactions/{expense['financial_transaction_pk']}/payments", json={"payment_date": old["start_date"], "amount": "40.00"}, headers=admin_h)
            assert r.status_code == 422 and "current financial year" in r.text


# ── the payment option is switched off, with the reason, while the year (or the Sangha's books) is closing or closed ──────────────────────────────
class TestThePaymentOptionPauses:
    YEAR = {"year_code": "2026-27"}

    def test_it_is_open_only_while_the_year_is_open_and_the_sangha_has_not_started_closing(self):
        assert U.payment_pause({**self.YEAR, "status": "OPEN"}, "OPEN", "Ekamra Sakha") is None
        assert U.payment_pause({**self.YEAR, "status": "OPEN"}, None, "Ekamra Sakha") is None

    @pytest.mark.parametrize("status,word", [("CLOSING", "closing"), ("CLOSED", "closed"), ("PLANNED", "not open yet")])
    def test_a_year_that_is_not_open_pauses_it_and_says_so(self, status, word):
        reason = U.payment_pause({**self.YEAR, "status": status}, "OPEN", "Ekamra Sakha")
        assert "paused" in reason and "2026-27" in reason and word in reason and "resumes when the next financial year opens" in reason

    @pytest.mark.parametrize("state,word", [("CLOSING", "started closing"), ("CLOSED", "closed")])
    def test_a_sangha_that_started_closing_its_books_pauses_its_own_payments(self, state, word):
        reason = U.payment_pause({**self.YEAR, "status": "OPEN"}, state, "Ekamra Sakha")
        assert "Ekamra Sakha" in reason and word in reason and "2026-27" in reason

    def test_no_year_at_all_pauses_it(self):
        assert "no financial year yet" in U.payment_pause(None, None, "Ekamra Sakha")

    def test_the_cards_carry_paused_and_the_reason_and_the_pay_endpoints_refuse_with_it(self):
        src = inspect.getsource(U._member_cards)
        assert 'card["paused"] = bool(pause)' in src and 'card["payable"] = ready and not pause' in src
        assert 'if card is not None and card.get("paused"):' in inspect.getsource(U._check_card_amount)           # a single and a multi-item payment both use it
        assert "_check_card_amount(" in inspect.getsource(U.pay_my_pranami) and "_check_card_amount(" in inspect.getsource(U.pay_my_pranami_multiple)

    def test_the_member_page_disables_the_button_and_shows_the_reason_and_the_admin_buttons_say_why(self):
        member = (ROOT / "frontend/dashboard.html").read_text(encoding="utf-8")
        assert 'x-show="h.paused && h.state !== \'PAID\'"' in member and 'disabled :title="h.unavailable_reason"' in member
        assert ':disabled="!!finTxnYearPause" :title="finTxnYearPause" @click="finOpenReceiptForm()"' in HTML
        assert ':disabled="!!finTxnYearPause" :title="finTxnYearPause" @click="finOpenPaymentForm()"' in HTML

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
    def test_the_admin_page_says_why_for_a_year_that_is_closing_closed_or_no_longer_active(self):
        start = FIN_JS.index("            get finTxnYearPause() {")
        end = FIN_JS.index("            get finCanPayment() {")
        script = f"""
        const host = {{ finTxn: null, finYears: [], finActiveYearPk: "y2", {FIN_JS[start:end].rstrip().rstrip(",")} }};
        const yr = (pk, code, status) => ({{ financial_year_pk: pk, year_code: code, status }});
        host.finYears = [yr("y1", "2025-26", "CLOSED"), yr("y2", "2026-27", "OPEN"), yr("y3", "2027-28", "PLANNED"), yr("y4", "2024-25", "CLOSING")];
        const r = {{}};
        const of = (pk) => {{ host.finTxn = {{ financial_year_pk: pk }}; return host.finTxnYearPause; }};
        r.none = of("y2"); r.closed = of("y1"); r.planned = of("y3"); r.closing = of("y4"); r.unknown = of("zz");
        host.finTxn = null; r.noTxn = host.finTxnYearPause;
        host.finYears = [yr("y1", "2025-26", "OPEN"), yr("y2", "2026-27", "OPEN")]; r.notActive = of("y1");
        console.log(JSON.stringify(r));
        """
        done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr
        out = json.loads(done.stdout.strip().splitlines()[-1])
        assert out["none"] == "" and out["unknown"] == "" and out["noTxn"] == ""
        assert "closed" in out["closed"] and "2025-26" in out["closed"] and "paused" in out["closed"]
        assert "not open yet" in out["planned"] and "closing" in out["closing"]
        assert "no longer the active year" in out["notActive"]
