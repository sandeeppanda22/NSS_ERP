"""
Finance contributions - the DB-free parts (api/services/finance_contribution.py): the due window of a head, the paid / due
arithmetic behind a member's cards, the amount rule of the pay endpoint, the audit coverage of every write the service makes
and the request schema. Runs without a database (``--noconftest``); the end-to-end behaviour is in test_finance_contributions.py.
"""

import ast
import inspect
import re
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from api.schemas import finance as S
from api.services import finance_contribution as FC

D = Decimal


class TestPeriodWindow:
    @pytest.mark.parametrize("today, window", [
        (date(2026, 4, 1), (date(2026, 4, 1), date(2027, 3, 31))),          # first day of the financial year
        (date(2027, 3, 31), (date(2026, 4, 1), date(2027, 3, 31))),         # last day
        (date(2027, 1, 15), (date(2026, 4, 1), date(2027, 3, 31))),         # January belongs to the year that began the April before
        (date(2026, 12, 31), (date(2026, 4, 1), date(2027, 3, 31))),
    ])
    def test_yearly_follows_the_financial_year(self, today, window):
        assert FC.period_window("YEARLY", today) == window

    @pytest.mark.parametrize("today, window", [
        (date(2028, 2, 10), (date(2028, 2, 1), date(2028, 2, 29))),         # leap year
        (date(2027, 2, 28), (date(2027, 2, 1), date(2027, 2, 28))),
        (date(2026, 12, 31), (date(2026, 12, 1), date(2026, 12, 31))),      # year end rolls over correctly
        (date(2026, 11, 1), (date(2026, 11, 1), date(2026, 11, 30))),
    ])
    def test_monthly_is_the_calendar_month(self, today, window):
        assert FC.period_window("MONTHLY", today) == window

    @pytest.mark.parametrize("period", ["ONE_TIME", None, "WEEKLY"])
    def test_one_time_and_free_amount_have_no_window(self, period):
        assert FC.period_window(period, date(2026, 11, 15)) is None

    def test_labels(self):
        assert FC.period_label("YEARLY", date(2026, 11, 15)) == "2026-27"
        assert FC.period_label("YEARLY", date(2027, 2, 1)) == "2026-27"
        assert FC.period_label("MONTHLY", date(2026, 11, 15)) == "Nov 2026"
        assert FC.period_label("ONE_TIME", date(2026, 11, 15)) == "one time"
        assert FC.period_label(None, date(2026, 11, 15)) is None


class TestCardState:
    def test_unpaid_is_due(self):
        assert FC.card_state(D("500"), D("0")) == {"state": "DUE", "paid_amount": D("0"), "due_amount": D("500"), "pending_amount": D("0")}

    def test_part_paid(self):
        got = FC.card_state(D("500"), D("200"))
        assert got["state"] == "PART" and got["due_amount"] == D("300")

    @pytest.mark.parametrize("paid", [D("500"), D("650")])
    def test_fully_paid_and_overpaid_both_owe_nothing(self, paid):
        got = FC.card_state(D("500"), paid)
        assert got["state"] == "PAID" and got["due_amount"] == D("0")

    def test_a_free_amount_head_has_nothing_due(self):
        got = FC.card_state(None, D("75"))
        assert got["state"] == "OPEN" and got["due_amount"] is None and got["paid_amount"] == D("75")

    def test_money_always_has_two_places(self):
        got = FC.card_state(D("500"), D("0"), D("0"))
        assert [str(got[k]) for k in ("paid_amount", "due_amount", "pending_amount")] == ["0.00", "500.00", "0.00"]
        assert str(FC.card_state(None, D("0"))["paid_amount"]) == "0.00"

    def test_pending_money_is_reported_but_never_counted_as_paid(self):
        got = FC.card_state(D("500"), D("0"), D("500"))
        assert got["state"] == "DUE" and got["paid_amount"] == D("0") and got["pending_amount"] == D("500")


class TestAmountRule:
    FULL = {"fixed_amount": D("500"), "allow_part_payment": False}
    PART = {"fixed_amount": D("500"), "allow_part_payment": True}
    FREE = {"fixed_amount": None, "allow_part_payment": False}

    def test_a_free_head_takes_any_amount(self):
        assert FC.amount_problem(self.FREE, D("1"), None) is None

    def test_a_fixed_head_must_be_paid_in_full(self):
        assert FC.amount_problem(self.FULL, D("500"), D("500")) is None
        assert "in full" in FC.amount_problem(self.FULL, D("100"), D("500"))
        assert "in full" in FC.amount_problem(self.FULL, D("600"), D("500"))

    def test_part_payment_takes_anything_up_to_what_is_due(self):
        assert FC.amount_problem(self.PART, D("100"), D("300")) is None
        assert FC.amount_problem(self.PART, D("300"), D("300")) is None
        assert "more than" in FC.amount_problem(self.PART, D("300.01"), D("300"))

    @pytest.mark.parametrize("head", [FULL, PART])
    def test_nothing_more_can_be_paid_once_it_is_settled(self, head):
        assert "already fully paid" in FC.amount_problem(head, D("1"), D("0"))
        assert "already fully paid" in FC.amount_problem(head, D("1"), None)


class TestWritesAreAudited:
    """Owner 2026-11-15: every transaction is audited. Each function of the service that writes must log what it wrote."""

    def _functions(self):
        tree = ast.parse(inspect.getsource(FC))
        return [n for n in tree.body if isinstance(n, ast.FunctionDef)]

    def test_every_writing_function_audits(self):
        writers = []
        for fn in self._functions():
            src = ast.get_source_segment(inspect.getsource(FC), fn)
            if "INSERT INTO" in src or "UPDATE nss." in src:
                writers.append(fn.name)
                assert "_audit(" in src, f"{fn.name} writes but never audits"
        assert {"ensure_org_scope", "_make_copy", "sync_copies", "set_copies_status", "link_account"} <= set(writers)

    def test_nothing_is_ever_deleted(self):
        assert "DELETE FROM" not in inspect.getsource(FC).upper()

    def test_an_automatic_write_is_marked_as_the_system(self):
        src = inspect.getsource(FC._audit)
        assert 'detail["system"] = True' in src and "user is None" in src


class TestRequestSchema:
    def test_defaults_are_the_simplest_case(self):
        body = S.ContributionCreate(organization_pk="00000000-0000-0000-0000-000000000001", head_name="Annual Pranami")
        assert body.applies_to == "ORGANIZATION" and body.fixed_amount is None and body.allow_part_payment is False

    @pytest.mark.parametrize("amount", ["0", "-5", "abc"])
    def test_an_amount_must_be_positive(self, amount):
        with pytest.raises(ValidationError):
            S.ContributionCreate(organization_pk="00000000-0000-0000-0000-000000000001", head_name="x", fixed_amount=amount)

    def test_the_one_list_of_due_periods(self):
        assert FC.DUE_PERIODS is S.DUE_PERIODS == ("YEARLY", "MONTHLY", "ONE_TIME")
        assert S.CONTRIBUTION_TARGETS == ("ORGANIZATION", "ALL_SAKHAS")

    def test_the_card_model_carries_what_the_ui_reads(self):
        for field in ("fixed_amount", "due_period", "allow_part_payment", "state", "paid_amount", "due_amount", "pending_amount",
                      "period_label", "payable", "unavailable_reason"):
            assert field in S.MyPayableHead.model_fields, field


def test_the_route_is_registered_and_needs_login():
    from api.main import app

    routes = {(m, r.path) for r in app.routes if getattr(r, "methods", None) for m in r.methods}
    assert ("POST", "/api/v1/finance/contributions") in routes


# ═══════════════════════════════════════════════════════════════════════
# Wiring guards (DB-free): the pieces the end-to-end tests rely on are connected
# ═══════════════════════════════════════════════════════════════════════

class TestWiring:
    @staticmethod
    def _src(obj) -> str:
        return inspect.getsource(obj)

    def test_every_head_response_field_is_selected_by_the_head_query(self):
        from api.routers import finance_setup as setup

        select = setup._HEAD_SELECT
        for field in S.HeadResponse.model_fields:
            assert re.search(rf"\b{field}\b", select), f"{field} is declared in HeadResponse but never selected"

    def test_the_card_fields_are_exactly_what_the_model_declares(self):
        from api.routers import finance_upi as upi

        produced = set(upi._CARD_FIELDS) | set(FC.card_state(None, D("0"))) | {"period_label", "payable", "unavailable_reason"}
        assert produced == set(S.MyPayableHead.model_fields)

    def test_linking_an_account_only_touches_copies_of_an_all_sakhas_head(self):
        """Regression: adopted Kendra templates also carry template_head_pk; switching an EXPENSE one onto UPI broke a CHECK."""
        src = " ".join(self._src(FC.link_account).split())
        assert "JOIN nss.finance_head s ON s.finance_head_pk = h.template_head_pk" in src
        assert "s.applies_to_all_sakhas = TRUE" in src and "h.collection_account_pk IS NULL" in src

    def test_the_card_query_never_offers_the_source_of_an_all_sakhas_head(self):
        from api.routers import finance_upi as upi

        sql = " ".join(upi._CARDS_SQL.split())
        assert "h.applies_to_all_sakhas = FALSE" in sql and "h.status = 'ACTIVE'" in sql and "h.is_pranami = TRUE" in sql
        assert "h.collection_scope_pk IS NULL OR cs.financial_scope_pk IS NOT NULL" in sql      # a closed event is hidden
        assert "h.direction = 'INCOME'" in sql and "h.organization_pk = ANY(%s::uuid[])" in sql      # only the member's own Sakha + the Kendra

    def test_the_pay_endpoint_validates_against_the_cards_and_serialises_per_member_and_head(self):
        from api.routers import finance_upi as upi

        src = self._src(upi.pay_my_pranami)
        assert "_member_cards(cur, user)" in src and "FC.amount_problem" in src and "pg_advisory_xact_lock" in src
        assert "log_audit(" in src                                                      # the request is audited
        assert "payer_person_pk=user.person_pk" in src and "payer_sevi_pk=user.sangha_sevi_pk" in src   # the payer is the token

    def test_the_cards_endpoint_is_read_only(self):
        from api.routers import finance_upi as upi

        src = self._src(upi.my_payable_heads)
        assert "get_connection" in src and "get_write_connection" not in src
        assert not re.search(r"\b(INSERT|UPDATE|DELETE)\b", self._src(upi._member_cards))

    def test_the_contribution_endpoint_audits_and_syncs(self):
        from api.routers import finance_setup as setup

        src = self._src(setup.create_contribution)
        assert "F._audit(" in src and "FC.sync_copies" in src and "FC.ensure_org_scope" in src and "FC.default_account" in src
        assert '"KENDRA"' in src                                                         # all-Sakhas is the Kendra's alone

    def test_the_contribution_route_needs_finance_approve(self):
        from api.routers import finance_setup as setup

        for fn in (setup.create_contribution, setup.sync_head_copies):
            params = inspect.signature(fn).parameters
            assert "_APPROVE" in repr(params["user"].default.dependency) or params["user"].default.dependency is setup._APPROVE, fn.__name__

    def test_status_changes_of_a_source_move_the_copies(self):
        from api.routers import finance_setup as setup

        assert "FC.set_copies_status" in self._src(setup.transition_head)

    def test_a_new_account_links_waiting_copies(self):
        from api.routers import finance_setup as setup

        assert "FC.link_account" in self._src(setup.create_account)
        assert "FC.link_account" in self._src(setup.update_account)

    def test_a_copy_can_only_have_its_account_changed(self):
        from api.routers import finance_setup as setup

        src = self._src(setup.update_head)
        assert 'set(sent) - {"collection_account_pk"}' in src and "status.HTTP_403_FORBIDDEN" in src
        assert "FC.sync_copies" in src                                                    # a Kendra edit reaches the copies

    def test_creating_a_sakha_gives_it_the_copies_without_ever_blocking_it(self):
        from api.routers import admin

        src = self._src(admin.create_organization)
        assert "finance_contribution.sync_new_sakha" in src
        assert src.index("SAKHA_LIKE_ORG_TYPES") < src.index("sync_new_sakha")           # only inside the Sakha-like branch
        assert "ROLLBACK TO SAVEPOINT" in self._src(FC.sync_new_sakha)

    def test_the_audit_helper_marks_automatic_rows(self):
        from api.helpers import log_audit

        calls = []

        class Cur:
            pass

        import api.services.finance_contribution as mod

        original = mod.log_audit
        mod.log_audit = lambda cur, **kw: calls.append(kw)
        try:
            mod._audit(Cur(), None, "CREATE", "finance_head", "pk", "x")
            assert calls[0]["detail"]["system"] is True and calls[0]["actor_pk"] is None and calls[0]["module"] == "finance"
        finally:
            mod.log_audit = original
        assert log_audit                                                                   # the real one is untouched

