"""
Sakha approval chain (owner decision 2026-11-17) - the DB-free parts: the pure rules (who must approve what), the bills rule, the
decision logic against a stand-in cursor, the wiring of the endpoints and the request / response schemas. Runs with ``--noconftest``;
the end-to-end behaviour is in test_finance_approval.py / test_finance_approval_security.py.
"""

import inspect
import re
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas import finance as S
from api.services import finance_approval as A

D = Decimal


class TestWhoMustApprove:
    @pytest.mark.parametrize("txn_type, amount, skips, limit, expected", [
        ("INCOME", D("500"), True, None, A.REQUIRES_NONE),                # Pranami / Parichaya Patra ...: no approval
        ("INCOME", D("500"), True, D("1"), A.REQUIRES_NONE),              # a limit never matters for income
        ("INCOME", D("500"), False, None, A.REQUIRES_BOTH),               # other income (a donation, a grant): both
        ("INCOME", D("500"), False, D("9999"), A.REQUIRES_BOTH),          # the Treasurer's limit is for SPENDING only
        ("EXPENSE", D("1000"), False, D("5000"), A.REQUIRES_TREASURER),   # within the limit: the Treasurer alone
        ("EXPENSE", D("5000"), False, D("5000"), A.REQUIRES_TREASURER),   # exactly the limit is still within it
        ("EXPENSE", D("5000.01"), False, D("5000"), A.REQUIRES_BOTH),     # a paisa above: the President too
        ("EXPENSE", D("1"), False, None, A.REQUIRES_BOTH),                # no limit and no default: always both
        ("ADJUSTMENT", D("10"), False, D("5000"), A.REQUIRES_BOTH),       # an adjustment is neither: both
        ("ADJUSTMENT", D("10"), True, D("5000"), A.REQUIRES_BOTH),
    ])
    def test_requirement(self, txn_type, amount, skips, limit, expected):
        assert A.requirement(txn_type, amount, skips, limit) == expected

    def test_stages(self):
        assert A.stages_for(A.REQUIRES_NONE) == [] and A.stages_for(A.REQUIRES_TREASURER) == [1] and A.stages_for(A.REQUIRES_BOTH) == [1, 2]

    def test_the_treasurer_is_always_first(self):
        assert all(stages[0] == 1 for stages in (A.stages_for(A.REQUIRES_TREASURER), A.stages_for(A.REQUIRES_BOTH)))


class TestBills:
    def test_only_a_spend_needs_bills(self):
        assert A.bills_problem("INCOME", D("100"), D("0"), 0) is None
        assert A.bills_problem("ADJUSTMENT", D("100"), D("0"), 0) is None

    def test_a_spend_needs_at_least_one_bill(self):
        assert "at least one bill" in A.bills_problem("EXPENSE", D("100"), D("0"), 0)

    @pytest.mark.parametrize("total", [D("99.99"), D("100.01"), D("200")])
    def test_the_bills_must_add_up_to_the_amount(self, total):
        assert "must be equal" in A.bills_problem("EXPENSE", D("100"), total, 2)

    def test_equal_bills_are_fine(self):
        assert A.bills_problem("EXPENSE", D("100"), D("100.00"), 3) is None


class FakeCursor:
    """A stand-in cursor: every execute() records the SQL and the next fetch returns the queued rows."""

    def __init__(self, *results):
        self.results = list(results)
        self.sql: list[str] = []
        self.description = None

    def execute(self, sql, params=None):
        self.sql.append(" ".join(sql.split()))
        self._current = self.results.pop(0) if self.results else []

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return list(self._current)


class User:
    actor_pk = "11111111-1111-1111-1111-111111111111"
    user_account_pk = "22222222-2222-2222-2222-222222222222"
    person_pk = "33333333-3333-3333-3333-333333333333"


class TestStageHolders:
    """approver_for_stage reads the LIVE seats; patch the seat lookups to try every situation."""

    @pytest.fixture
    def seats(self, monkeypatch):
        held = {}
        monkeypatch.setattr(A, "_body_pk", lambda cur, org: "body")
        monkeypatch.setattr(A.seat_service, "live_seat_holder",
                            lambda cur, body, position: held.get(position))
        return held

    def test_stage_one_is_the_treasurer(self, seats):
        seats["TREASURER"] = ("p-t", "pos", False)
        assert A.approver_for_stage(None, "org", 1) == {"person_pk": "p-t", "position_code": "TREASURER", "cover_reason": None}

    def test_an_acting_treasurer_counts_and_is_marked(self, seats):
        seats["TREASURER"] = ("p-t", "pos", True)
        assert A.approver_for_stage(None, "org", 1)["cover_reason"] == "ACTING_COVER"

    def test_stage_two_is_the_president(self, seats):
        seats.update(PRESIDENT=("p-p", "pos", False), SECRETARY=("p-s", "pos", False))
        assert A.approver_for_stage(None, "org", 2) == {"person_pk": "p-p", "position_code": "PRESIDENT", "cover_reason": None}

    def test_an_acting_president_stands_in_for_the_president_not_the_secretary(self, seats):
        seats.update(PRESIDENT=("p-act", "pos", True), SECRETARY=("p-s", "pos", False))
        got = A.approver_for_stage(None, "org", 2)
        assert got["person_pk"] == "p-act" and got["position_code"] == "PRESIDENT" and got["cover_reason"] == "ACTING_COVER"

    def test_with_no_president_the_secretary_approves(self, seats):
        seats["SECRETARY"] = ("p-s", "pos", False)
        assert A.approver_for_stage(None, "org", 2) == {"person_pk": "p-s", "position_code": "SECRETARY", "cover_reason": "PRESIDENT_SEAT_VACANT"}

    def test_nobody_when_the_seats_are_vacant(self, seats):
        assert A.approver_for_stage(None, "org", 1) is None and A.approver_for_stage(None, "org", 2) is None

    def test_a_sakha_without_a_governing_body_has_nobody(self, monkeypatch):
        monkeypatch.setattr(A, "_body_pk", lambda cur, org: None)
        assert A.approver_for_stage(None, "org", 1) is None


def _txn(**over):
    base = {"financial_transaction_pk": "t1", "transaction_reference": "FTX1", "transaction_type": "EXPENSE", "amount": D("3000"),
            "status": "PENDING_APPROVAL", "finance_head_pk": "h1", "created_by_sangha_sevi_pk": "creator-sevi", "person_pk": None,
            "sangha_sevi_pk": None}
    base.update(over)
    return base


class TestDecide:
    """decide() with the state and the database stubbed: every refusal and the happy paths."""

    @pytest.fixture
    def world(self, monkeypatch):
        w = {"state": {"applies": True, "requires": A.REQUIRES_BOTH, "limit": D("5000"), "steps": [], "next_stage": 1,
                       "next_position": "TREASURER", "next_person_pk": User.person_pk, "next_cover_reason": None,
                       "complete": False, "blocked_reason": None},
             "maker": "someone-else", "problem": None, "inserted": [], "audited": []}
        monkeypatch.setattr(A, "state", lambda cur, txn, org: w["state"])
        monkeypatch.setattr(A, "submit_problems", lambda cur, txn, org: w["problem"])
        monkeypatch.setattr(A, "creator_person", lambda cur, pk: w["maker"])
        monkeypatch.setattr(A, "_audit", lambda cur, user, action, txn, summary, detail: w["audited"].append((action, detail)))

        class Cur(FakeCursor):
            def execute(inner, sql, params=None):
                if "INSERT INTO nss.finance_approval_step" in sql:
                    w["inserted"].append(params)
                inner._current = [("step-pk",)]

        w["cur"] = Cur()
        return w

    def call(self, world, decision="APPROVED", remarks=None, txn=None):
        return A.decide(world["cur"], User, txn or _txn(), "org", decision, remarks)

    def test_the_treasurer_approves_step_one_of_two(self, world):
        r = self.call(world)
        assert r["final"] is None and r["stage"] == 1 and r["position"] == "TREASURER"
        assert world["inserted"][0][1:5] == (1, "TREASURER", "APPROVED", User.person_pk)

    def test_the_treasurer_alone_finishes_a_spend_within_the_limit(self, world):
        world["state"]["requires"] = A.REQUIRES_TREASURER
        assert self.call(world)["final"] == "APPROVED"

    def test_the_second_step_finishes_it(self, world):
        world["state"].update(next_stage=2, next_position="PRESIDENT", steps=[{"step_no": 1, "decision": "APPROVED", "decided_by_person_pk": "treasurer-person"}])
        assert self.call(world)["final"] == "APPROVED"

    def test_only_the_person_in_the_seat_may_act(self, world):
        world["state"]["next_person_pk"] = "somebody-else"
        with pytest.raises(HTTPException) as e:
            self.call(world)
        assert e.value.status_code == 403 and "Treasurer" in e.value.detail and not world["inserted"]

    def test_a_vacant_seat_blocks(self, world):
        world["state"].update(next_person_pk=None, blocked_reason="The Treasurer seat of this Sakha is vacant, so nobody can approve yet.")
        with pytest.raises(HTTPException) as e:
            self.call(world)
        assert e.value.status_code == 422 and "vacant" in e.value.detail

    def test_the_treasurer_may_approve_what_they_recorded_themselves(self, world):
        world["maker"] = User.person_pk
        r = self.call(world)
        assert r["stage"] == 1 and world["audited"][0][1]["treasurer_recorded_it"] is True

    def test_the_president_may_not_approve_what_they_recorded(self, world):
        world["maker"] = User.person_pk
        world["state"].update(next_stage=2, next_position="PRESIDENT", steps=[{"step_no": 1, "decision": "APPROVED", "decided_by_person_pk": "x"}])
        with pytest.raises(HTTPException) as e:
            self.call(world)
        assert e.value.status_code == 403 and "recorded" in e.value.detail

    def test_the_second_approver_must_differ_from_the_first(self, world):
        world["state"].update(next_stage=2, next_position="SECRETARY", next_cover_reason="PRESIDENT_SEAT_VACANT",
                              steps=[{"step_no": 1, "decision": "APPROVED", "decided_by_person_pk": User.person_pk}])
        with pytest.raises(HTTPException) as e:
            self.call(world)
        assert e.value.status_code == 403 and "different person" in e.value.detail

    def test_a_secretary_in_cover_is_recorded_as_such(self, world):
        world["state"].update(next_stage=2, next_position="SECRETARY", next_cover_reason="PRESIDENT_SEAT_VACANT",
                              steps=[{"step_no": 1, "decision": "APPROVED", "decided_by_person_pk": "treasurer-person"}])
        r = self.call(world)
        assert r["final"] == "APPROVED" and r["position"] == "SECRETARY"
        assert world["inserted"][0][3] == "SECRETARY" or world["inserted"][0][2] == "SECRETARY"
        assert world["audited"][0][1]["cover_reason"] == "PRESIDENT_SEAT_VACANT"

    @pytest.mark.parametrize("remarks", [None, "", "   "])
    def test_a_rejection_needs_a_reason(self, world, remarks):
        with pytest.raises(HTTPException) as e:
            self.call(world, "REJECTED", remarks)
        assert e.value.status_code == 422 and not world["inserted"]

    def test_a_rejection_is_final(self, world):
        assert self.call(world, "REJECTED", "Not a Sangha expense")["final"] == "REJECTED"
        assert world["audited"][0][0] == "REJECT"

    def test_only_an_entry_waiting_for_approval_can_be_decided(self, world):
        with pytest.raises(HTTPException) as e:
            self.call(world, txn=_txn(status="DRAFT"))
        assert e.value.status_code == 422

    def test_an_entry_that_needs_no_approval_cannot_be_decided(self, world):
        world["state"]["requires"] = A.REQUIRES_NONE
        with pytest.raises(HTTPException) as e:
            self.call(world)
        assert "needs no approval" in e.value.detail

    def test_bills_are_rechecked_before_an_approval(self, world):
        world["problem"] = "The bills add up to 10.00 but the spend is 3,000.00; they must be equal."
        with pytest.raises(HTTPException) as e:
            self.call(world)
        assert "bills" in e.value.detail and not world["inserted"]

    def test_every_decision_is_audited(self, world):
        self.call(world)
        assert len(world["audited"]) == 1 and world["audited"][0][0] == "APPROVE"


class TestWiring:
    @staticmethod
    def _src(obj) -> str:
        return inspect.getsource(obj)

    def test_the_chain_only_governs_sakha_like_organizations(self):
        src = self._src(A.is_chain_org)
        assert "SAKHA_LIKE_ORG_TYPES_SQL" in src and "SAKHA_SANGHA" not in src          # one definition: never a hard-coded type

    def test_the_authority_is_the_seat_never_a_permission_or_the_super_admin(self):
        src = self._src(A)
        assert "has_any_permission" not in src and "is_super_admin" not in src and "has_permission" not in src
        assert "seat_service" in src

    def test_a_sakha_entry_cannot_be_approved_through_the_ordinary_transition(self):
        from api.routers import finance as F

        src = self._src(F.transition_transaction)
        assert 'body.status == "APPROVED"' in src and "approval_service.is_chain_org" in src
        # the check comes BEFORE the permission guard, so the message is the right one even for a super administrator
        assert src.index('body.status == "APPROVED"') < src.index("_guard_transition(")

    def test_submitting_a_sakha_entry_checks_its_bills_and_posts_a_no_approval_income(self):
        from api.routers import finance as F

        src = self._src(F.transition_transaction)
        assert "submit_problems" in src and "REQUIRES_NONE" in src and '"POSTED"' in src

    def test_ordinary_and_chain_moves_share_one_implementation(self):
        from api.routers import finance as F
        from api.routers import finance_approval as R

        assert "_move_transaction" in self._src(F.transition_transaction) and "F._move_transaction" in self._src(R._decide)

    def test_the_decision_routes_are_login_only_and_the_rest_are_permission_gated(self):
        from api.main import app

        for path in ("/api/v1/finance/transactions/{txn_pk}/approve", "/api/v1/finance/transactions/{txn_pk}/reject", "/api/v1/finance/my-approvals"):
            route = next(r for r in app.routes if getattr(r, "path", "") == path)
            names = {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}
            assert "get_current_user" in names, path
            assert not any(n in names for n in ("_check", "_dep")), path
        for path, method in (("/api/v1/finance/transactions/{txn_pk}/bills", "POST"), ("/api/v1/finance/approval-policy", "PUT")):
            route = next(r for r in app.routes if getattr(r, "path", "") == path and method in r.methods)
            assert "get_current_user" not in {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}, path

    def test_configuring_the_limit_needs_the_configure_permission(self):
        from api.routers import finance_approval as R

        assert inspect.signature(R.put_approval_policy).parameters["user"].default.dependency is R._CONFIGURE
        assert inspect.signature(R.add_bill).parameters["user"].default.dependency is R._MANAGE

    def test_every_write_is_audited(self):
        from api.routers import finance_approval as R

        for fn in (R.put_approval_policy, R.add_bill, R.remove_bill):
            assert "F._audit(" in self._src(fn), fn.__name__
        assert "_audit(" in self._src(A.decide)

    def test_bills_change_only_while_the_entry_is_a_draft_expense(self):
        from api.routers import finance_approval as R

        src = self._src(R._draft_expense)
        assert '"EXPENSE"' in src and '"DRAFT"' in src
        assert "_draft_expense(txn)" in self._src(R.add_bill) and "_draft_expense(txn)" in self._src(R.remove_bill)

    def test_a_bill_is_removed_softly(self):
        from api.routers import finance_approval as R

        src = self._src(R.remove_bill)
        assert "is_active = FALSE" in src and "DELETE FROM" not in src.upper()

    def test_the_approver_list_only_offers_what_the_caller_must_act_on(self):
        from api.routers import finance_approval as R

        src = self._src(R.my_approvals)
        assert "next_person_pk" in src and "REQUIRES_NONE" in src
        assert "get_connection" in src and "get_write_connection" not in src               # read-only

    def test_the_state_never_reads_a_permission(self):
        assert "permission" not in self._src(A.state)


class TestSchemas:
    def test_a_bill_link_must_be_https(self):
        base = {"vendor_name": "OPTCL", "bill_date": "2026-11-01", "amount": "100"}
        assert S.BillCreate(**base, document_url="https://drive.example/x").document_url == "https://drive.example/x"
        assert S.BillCreate(**base, document_url="   ").document_url is None
        for bad in ("http://x.example", "javascript:alert(1)", "ftp://x", "//x.example", "https://has space"):
            with pytest.raises(ValidationError):
                S.BillCreate(**base, document_url=bad)

    @pytest.mark.parametrize("amount", ["0", "-1", "1.234", "abc"])
    def test_a_bill_amount_is_a_positive_money_amount(self, amount):
        with pytest.raises(ValidationError):
            S.BillCreate(vendor_name="x", bill_date="2026-11-01", amount=amount)

    def test_a_limit_must_be_positive(self):
        with pytest.raises(ValidationError):
            S.ApprovalPolicyWrite(organization_pk="00000000-0000-0000-0000-000000000001", default_treasurer_limit="0")
        assert S.ApprovalPolicyWrite(organization_pk="00000000-0000-0000-0000-000000000001").default_treasurer_limit is None

    def test_the_head_models_carry_the_approval_flags(self):
        for model in (S.HeadCreate, S.HeadUpdate, S.HeadResponse):
            assert {"skips_approval", "treasurer_limit", "requires_member"} <= set(model.model_fields), model.__name__

    def test_the_approver_item_exposes_names_not_ids_of_other_people(self):
        fields = set(S.MyApprovalItem.model_fields)
        assert {"recorded_by_name", "member_name"} <= fields
        assert not {f for f in fields if f.endswith("_person_pk") or f.endswith("sangha_sevi_pk")}
        assert not {f for f in S.ApprovalStepResponse.model_fields if f.endswith("_pk")}

    def test_the_head_response_fields_are_all_selected(self):
        from api.routers import finance_setup as setup

        for field in ("skips_approval", "treasurer_limit", "requires_member"):
            assert re.search(rf"\bh\.{field}\b", setup._HEAD_SELECT), field


def test_the_new_routes_are_registered():
    from api.main import app

    routes = {(m, r.path) for r in app.routes if getattr(r, "methods", None) for m in r.methods}
    base = "/api/v1/finance"
    for method, path in (("GET", "/approval-policy"), ("PUT", "/approval-policy"), ("GET", "/my-approvals"),
                         ("GET", "/transactions/{txn_pk}/approval"), ("GET", "/transactions/{txn_pk}/bills"),
                         ("POST", "/transactions/{txn_pk}/bills"), ("DELETE", "/transactions/{txn_pk}/bills/{bill_pk}"),
                         ("POST", "/transactions/{txn_pk}/approve"), ("POST", "/transactions/{txn_pk}/reject")):
        assert (method, base + path) in routes, (method, path)
