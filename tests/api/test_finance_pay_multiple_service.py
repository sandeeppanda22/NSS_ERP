"""
Paying several contributions in one UPI payment (owner request 2026-11-17) - the DB-free parts: the request schema, the creation rules
(one account, no duplicates, the cap), the all-or-nothing booking of the lines against a stand-in cursor, and the wiring. Runs with
``--noconftest``; the end-to-end payment is in test_finance_pay_multiple.py.
"""

import inspect
import re
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.routers import finance_upi as U
from api.schemas import finance as S

D = Decimal
H1, H2, H3 = ("00000000-0000-0000-0000-00000000000%d" % i for i in (1, 2, 3))


class TestRequestSchema:
    def test_one_to_twelve_items(self):
        assert len(S.MyPayMultipleRequest(items=[{"finance_head_pk": H1, "amount": "10"}]).items) == 1
        with pytest.raises(ValidationError):
            S.MyPayMultipleRequest(items=[])
        with pytest.raises(ValidationError):
            S.MyPayMultipleRequest(items=[{"finance_head_pk": H1, "amount": "1"}] * 13)

    @pytest.mark.parametrize("amount", ["0", "-1", "1.234", "abc"])
    def test_every_amount_is_a_positive_money_amount(self, amount):
        with pytest.raises(ValidationError):
            S.MyPayMultipleRequest(items=[{"finance_head_pk": H1, "amount": amount}])

    def test_the_payer_and_the_account_cannot_be_named(self):
        assert set(S.MyPayMultipleRequest.model_fields) == {"items"} and set(S.MyPayItem.model_fields) == {"finance_head_pk", "amount"}

    def test_the_member_view_lists_the_items_with_their_receipts(self):
        assert {"head_name", "amount", "receipt_number", "financial_receipt_pk"} == set(S.MyPaymentItem.model_fields)
        assert "items" in S.MyPayment.model_fields and S.MyPayment(
            upi_payment_request_pk=H1, request_reference="PRQ1", head_name="x", organization_name=None, amount="2", status="PAID", pay_url=None,
            upi_uri=None, expires_at="2026-11-17T10:00:00Z", paid_at=None, receipt_number=None).items == []


class Cur:
    """Records every statement; fetchone returns queued rows."""

    def __init__(self, *rows):
        self.rows = list(rows)
        self.sql: list[tuple[str, tuple | None]] = []

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class TestCreatingTheRequest:
    @pytest.fixture
    def stubs(self, monkeypatch):
        calls = {"stored": [], "prepared": []}

        def prepare(cur, head_pk):
            calls["prepared"].append(str(head_pk))
            return ({"finance_head_pk": head_pk, "head_name": f"Head {head_pk[-1]}", "organization_pk": "org"},
                    {"financial_scope_pk": f"scope-{head_pk[-1]}"}, None, {"financial_account_pk": calls.get("account", "acct")})

        monkeypatch.setattr(U, "_prepare_collection", prepare)
        monkeypatch.setattr(U, "_open_order_and_store", lambda cur, **kw: calls["stored"].append(kw) or "req-1")
        monkeypatch.setattr(U, "_max_amount", lambda: D("100000"))
        monkeypatch.setattr(U, "_min_amount", lambda: D("1"))
        return calls

    def make(self, items, cur=None, **kw):
        return U._create_multi_request(cur or Cur(), items=items, payer_person_pk="p", payer_sevi_pk="s", payer_name=None, actor_pk="a", **kw)

    def test_the_order_is_one_order_for_the_total(self, stubs):
        cur = Cur()
        assert self.make([(H1, D("100")), (H2, D("250.50"))], cur) == "req-1"
        assert stubs["stored"][0]["amount"] == D("350.50") and "2 contributions" in stubs["stored"][0]["description"]
        assert stubs["stored"][0]["head"]["finance_head_pk"] == H1                  # the request carries the FIRST head

    def test_one_line_per_contribution_numbered_from_one(self, stubs):
        cur = Cur()
        self.make([(H1, D("100")), (H2, D("250")), (H3, D("5"))], cur)
        lines = [p for sql, p in cur.sql if sql.startswith("INSERT INTO nss.upi_payment_request_line")]
        assert [(p[1], p[2], p[5]) for p in lines] == [(1, H1, D("100")), (2, H2, D("250")), (3, H3, D("5"))]

    def test_the_same_contribution_twice_is_refused(self, stubs):
        with pytest.raises(HTTPException) as e:
            self.make([(H1, D("1")), (H1, D("2"))])
        assert e.value.status_code == 422 and not stubs["stored"]

    def test_contributions_of_two_accounts_are_refused(self, stubs, monkeypatch):
        accounts = iter(["acct-A", "acct-B"])
        monkeypatch.setattr(U, "_prepare_collection", lambda cur, h: (
            {"finance_head_pk": h, "head_name": "x", "organization_pk": "o"}, {"financial_scope_pk": "s"}, None, {"financial_account_pk": next(accounts)}))
        with pytest.raises(HTTPException) as e:
            self.make([(H1, D("1")), (H2, D("2"))])
        assert e.value.status_code == 422 and "separately" in e.value.detail and not stubs["stored"]

    def test_the_total_cannot_pass_the_single_payment_cap(self, stubs):
        with pytest.raises(HTTPException) as e:
            self.make([(H1, D("60000")), (H2, D("40000.01"))])
        assert e.value.status_code == 422 and "limited" in e.value.detail and not stubs["prepared"]

    def test_every_head_is_validated_like_a_single_payment(self, stubs):
        self.make([(H1, D("1")), (H2, D("2"))])
        assert stubs["prepared"] == [H1, H2]


def _req(**over):
    base = {"upi_payment_request_pk": "req", "request_reference": "PRQ9", "status": "PAID", "financial_transaction_pk": None,
            "paid_at": "2026-11-17", "paid_amount": D("350"), "amount": D("350"), "note": "A; B", "finance_head_pk": H1,
            "financial_scope_pk": "s1", "fund_master_pk": None, "payer_person_pk": "p", "payer_sangha_sevi_pk": "s", "payer_name": None,
            "provider_payment_id": "pay_1"}
    base.update(over)
    return base


def _line(n, head, amount, **over):
    return {"upi_payment_request_line_pk": f"l{n}", "line_no": n, "finance_head_pk": head, "financial_scope_pk": f"s{n}", "fund_master_pk": None,
            "amount": D(amount), **over}


class TestBookingTheLines:
    @pytest.fixture
    def booked(self, monkeypatch):
        state = {"calls": [], "lines": [_line(1, H1, "100"), _line(2, H2, "250")], "fail_on": None}
        monkeypatch.setattr(U, "_load_request", lambda cur, pk, lock=False: state.setdefault("req", _req()))
        monkeypatch.setattr(U, "_request_lines", lambda cur, pk: state["lines"])

        def book(cur, req, year_pk, txn_date, **kw):
            if state["fail_on"] == len(state["calls"]) + 1:
                raise HTTPException(status_code=422, detail="Financial scope is CLOSING.")
            state["calls"].append(kw)
            n = len(state["calls"])
            return (f"txn{n}", f"rcpt{n}", f"FTX{n}", f"RCT{n}")

        monkeypatch.setattr(U, "_book_one", book)
        return state

    def post(self, state):
        cur = Cur(("2026-11-17",), ("year-1",))
        state["cur"] = cur
        return U._post_paid_request(cur, "req", actor_pk=None), cur

    def test_every_line_is_booked_in_order_with_its_own_amount(self, booked):
        reason, cur = self.post(booked)
        assert reason is None
        assert [(c["head_pk"], c["amount"], c["label"]) for c in booked["calls"]] == [(H1, D("100"), " (1 of 2)"), (H2, D("250"), " (2 of 2)")]

    def test_each_line_and_the_request_record_what_was_booked(self, booked):
        _, cur = self.post(booked)
        updates = [(sql, p) for sql, p in cur.sql if sql.startswith("UPDATE nss.upi_payment_request")]
        line_updates = [p for sql, p in updates if "request_line" in sql]
        assert line_updates == [("txn1", "rcpt1", "l1"), ("txn2", "rcpt2", "l2")]
        request_update = [p for sql, p in updates if "request_line" not in sql][0]
        assert request_update[:2] == ("txn1", "rcpt1")                                # the request points at the first

    def test_it_is_all_or_nothing_through_a_savepoint(self, booked):
        booked["fail_on"] = 2
        reason, cur = self.post(booked)
        statements = [sql for sql, _ in cur.sql]
        assert reason == "Financial scope is CLOSING."
        assert "SAVEPOINT upi_multi_post" in statements and "ROLLBACK TO SAVEPOINT upi_multi_post" in statements
        assert "RELEASE SAVEPOINT upi_multi_post" not in statements
        assert not any(s.startswith("UPDATE nss.upi_payment_request") for s in statements)       # nothing is recorded as booked

    def test_a_successful_booking_releases_the_savepoint(self, booked):
        _, cur = self.post(booked)
        statements = [sql for sql, _ in cur.sql]
        assert statements.index("SAVEPOINT upi_multi_post") < statements.index("RELEASE SAVEPOINT upi_multi_post")

    def test_a_different_amount_than_asked_is_never_booked(self, booked):
        booked["req"] = _req(paid_amount=D("340"))
        reason, _ = self.post(booked)
        assert reason.startswith("AMOUNT_MISMATCH") and booked["calls"] == []

    def test_an_already_booked_request_is_left_alone(self, booked):
        booked["req"] = _req(financial_transaction_pk="done")
        assert U._post_paid_request(Cur(), "req", actor_pk=None) is None and booked["calls"] == []

    def test_a_request_that_is_not_paid_is_refused(self, booked):
        booked["req"] = _req(status="PENDING")
        assert U._post_paid_request(Cur(), "req", actor_pk=None) == "The request is not paid."

    def test_no_open_year_holds_the_payment(self, booked):
        reason = U._post_paid_request(Cur(("2026-11-17",), None), "req", actor_pk=None)
        assert reason and "No OPEN financial year" in reason and booked["calls"] == []

    def test_an_ordinary_request_without_lines_books_once_with_no_savepoint(self, booked):
        booked["lines"] = []
        reason, cur = self.post(booked)
        assert reason is None and len(booked["calls"]) == 1 and booked["calls"][0]["head_pk"] == H1 and booked["calls"][0]["amount"] == D("350")
        assert not any("SAVEPOINT" in sql for sql, _ in cur.sql)


class TestWiring:
    @staticmethod
    def _src(obj) -> str:
        return inspect.getsource(obj)

    def test_the_endpoint_is_login_only_rate_limited_and_serialises_per_head(self):
        src = self._src(U.pay_my_pranami_multiple)
        assert "get_current_user" in src and "pg_advisory_xact_lock" in src and "sorted(heads)" in src
        assert "_check_card_amount(" in src and "_check_open_request_cap(cur, user)" in src and "_create_multi_request(" in src
        assert "log_audit(" in src and '"multiple": True' in src
        assert "limiter.limit" in self._src(U).split("def pay_my_pranami_multiple")[0].rsplit("@router.post", 1)[1]

    def test_the_payer_is_always_the_token(self):
        src = self._src(U.pay_my_pranami_multiple)
        assert "payer_person_pk=user.person_pk" in src and "payer_sevi_pk=user.sangha_sevi_pk" in src and "payer_name=None" in src

    def test_every_item_passes_the_same_rules_as_a_single_payment(self):
        assert "_check_card_amount" in self._src(U.pay_my_pranami) and "_check_card_amount" in self._src(U.pay_my_pranami_multiple)

    def test_the_pending_amount_of_a_head_counts_the_lines_of_pending_multi_payments(self):
        src = self._src(U._member_cards)
        assert "upi_payment_request_line" in src and "UNION ALL" in src and "NOT EXISTS" in src

    def test_the_admin_list_names_a_multi_payment_and_counts_its_lines(self):
        assert "Several contributions" in U._REQ_SELECT and "AS line_count" in U._REQ_SELECT
        assert "line_count" in S.PaymentRequestResponse.model_fields

    def test_the_route_is_registered(self):
        from api.main import app

        assert ("POST", "/api/v1/finance/my-pranami/pay-multiple") in {(m, r.path) for r in app.routes if getattr(r, "methods", None) for m in r.methods}

    def test_the_line_table_is_a_live_and_validated_table(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        assert "upi_payment_request_line" in (root / "database/ddl/12_live_refresh/02_live_change_triggers.sql").read_text(encoding="utf-8")
        for name in ("02_build.sh", "02_build.ps1", "03_validate.sh", "03_validate.ps1"):
            assert "upi_payment_request_line" in (root / "database/scripts" / name).read_text(encoding="utf-8"), name
        assert "upi_payment_request_line" in (root / "render_build.sh").read_text(encoding="utf-8")

    def test_booking_one_amount_is_a_single_shared_function(self):
        assert "_book_one(" in self._src(U._post_paid_request) and self._src(U._post_paid_request).count("_book_one(") == 2
        assert "INSERT INTO nss.financial_transaction" in self._src(U._book_one) and "INSERT INTO nss.financial_transaction" not in self._src(U._post_paid_request)


class TestTheAmountLimits:
    """One UPI payment must be at least UPI_MIN_AMOUNT (Razorpay links start at Rs. 1) and at most UPI_MAX_AMOUNT."""

    @pytest.fixture(autouse=True)
    def limits(self, monkeypatch):
        monkeypatch.setattr(U, "_min_amount", lambda: D("1"))
        monkeypatch.setattr(U, "_max_amount", lambda: D("100000"))

    @pytest.mark.parametrize("amount", ["1", "1.00", "1.01", "500", "99999.99", "100000"])
    def test_inside_the_limits(self, amount):
        U._check_amount_limits(D(amount))

    @pytest.mark.parametrize("amount, text", [("0.01", "at least Rs. 1.00"), ("0.99", "at least Rs. 1.00"), ("100000.01", "limited to 1,00,000.00".replace("1,00,000", "100,000"))])
    def test_outside_the_limits_the_member_is_told_why(self, amount, text):
        with pytest.raises(HTTPException) as e:
            U._check_amount_limits(D(amount))
        assert e.value.status_code == 422 and text in e.value.detail

    def test_the_defaults_come_from_the_settings(self, monkeypatch):
        from api.config import settings

        monkeypatch.undo()
        assert settings.UPI_MIN_AMOUNT == "1" or settings.UPI_MIN_AMOUNT.replace(".", "").isdigit()
        assert U._min_amount() == D(settings.UPI_MIN_AMOUNT) and U._max_amount() == D(settings.UPI_MAX_AMOUNT)

    def test_a_raised_minimum_is_honoured(self, monkeypatch):
        monkeypatch.setattr(U, "_min_amount", lambda: D("50"))
        with pytest.raises(HTTPException) as e:
            U._check_amount_limits(D("49.99"))
        assert "at least Rs. 50.00" in e.value.detail
        U._check_amount_limits(D("50"))

    def test_every_way_of_creating_a_request_is_checked(self):
        import inspect

        for fn in (U._create_request, U._create_multi_request, U._open_order_and_store):
            assert "_check_amount_limits(" in inspect.getsource(fn), fn.__name__

    def test_a_single_payment_below_the_minimum_never_reaches_the_gateway(self, monkeypatch):
        reached = []
        monkeypatch.setattr(U, "_prepare_collection", lambda cur, h: reached.append("prepared"))
        with pytest.raises(HTTPException):
            U._create_request(Cur(), head_pk=H1, amount=D("0.50"), payer_person_pk="p", payer_sevi_pk="s", payer_name=None, note=None, actor_pk="a")
        assert reached == []

    def test_the_total_of_a_multi_item_payment_is_what_counts(self, monkeypatch):
        prepared = []
        monkeypatch.setattr(U, "_prepare_collection", lambda cur, h: prepared.append(h) or ({"finance_head_pk": h, "head_name": "x", "organization_pk": "o"},
                                                                                         {"financial_scope_pk": "s"}, None, {"financial_account_pk": "a"}))
        monkeypatch.setattr(U, "_open_order_and_store", lambda cur, **kw: "req")
        # 0.40 + 0.40 is below Rs. 1 in total: refused before anything is prepared
        with pytest.raises(HTTPException):
            U._create_multi_request(Cur(), items=[(H1, D("0.40")), (H2, D("0.40"))], payer_person_pk="p", payer_sevi_pk="s", payer_name=None, actor_pk="a")
        assert prepared == []
        # 0.60 + 0.60 reaches Rs. 1.20 together: accepted although each item is below Rs. 1
        assert U._create_multi_request(Cur(), items=[(H1, D("0.60")), (H2, D("0.60"))], payer_person_pk="p", payer_sevi_pk="s", payer_name=None, actor_pk="a") == "req"
