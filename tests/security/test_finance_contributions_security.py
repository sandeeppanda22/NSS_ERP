"""
Security of the Finance contributions feature (owner decision 2026-11-15): who may add a contribution, who may touch a Sakha's
copy, what a member can see and pay, and what never leaks. Real integration tests (nothing mocked); they need the Phase 11i DDL
and ddl/14_finance/14_finance_head_fixed_amount_patch.sql applied.
"""

import json
import re
from uuid import uuid4

import pytest

from api.schemas import finance as S
from tests.finance_support import (  # noqa: F401  (fixtures)
    single_approval_levels,
    BASE,
    FAKE_UUID,
    _login_headers,
    admin_h,
    admin_user,
    ensure_open_year_covering_today,
    kendra_admin,
    kendra_h,
    make_account,
    mock_gateway,
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
    viewer_h,
    viewer_user,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("single_approval_levels")]


@pytest.fixture
def plain_member(write_conn, register_org_pk):
    return new_member(write_conn, register_org_pk, "FinConSec")


@pytest.fixture
def plain_member_h(client, plain_member):
    return _login_headers(client, plain_member["sangha_sevi_id"], plain_member["password"])


@pytest.fixture(autouse=True)
def _a_financial_year_covers_today(write_conn):
    ensure_open_year_covering_today(write_conn)


def _kendra_pk(write_conn) -> str:
    from tests.reparent_support import kendra_pks

    return kendra_pks(write_conn)[0]


def _post(client, headers, org_pk, **over):
    body = {"organization_pk": str(org_pk), "head_name": f"Sec {uuid4().hex[:6]}"}
    body.update(over)
    return client.post(f"{BASE}/contributions", json=body, headers=headers)


def _all_sakhas(client, headers, write_conn, **over) -> dict:
    r = _post(client, headers, _kendra_pk(write_conn), applies_to="ALL_SAKHAS", fixed_amount="500", due_period="YEARLY", **over)
    assert r.status_code == 201, r.text
    return r.json()["head"]


def _copy(client, headers, source_pk, org_pk) -> dict:
    items = client.get(f"{BASE}/heads", params={"organization_pk": str(org_pk), "page_size": 200, "with_templates": "false"}, headers=headers).json()["items"]
    return next(h for h in items if h["template_head_pk"] == source_pk)


# ═══════════════════════════════════════════════════════════════════════
# Who may add / refresh a contribution
# ═══════════════════════════════════════════════════════════════════════

class TestWhoMayConfigure:
    def test_anonymous_callers_are_turned_away(self, client, register_org_pk):
        assert client.post(f"{BASE}/contributions", json={"organization_pk": str(register_org_pk), "head_name": "x"}).status_code == 401
        assert client.post(f"{BASE}/heads/{FAKE_UUID}/sync-copies").status_code == 401

    @pytest.mark.parametrize("who", ["other_admin_h", "viewer_h", "plain_member_h"])
    def test_without_finance_configure_for_this_sakha_nobody_adds_a_contribution(self, request, client, register_org_pk, who):
        r = _post(client, request.getfixturevalue(who), register_org_pk)
        assert r.status_code == 403, (who, r.text)          # a foreign Sakha's admin, a viewer, a plain member

    def test_a_sakha_admin_configures_its_own_sakha_only(self, client, sakha_admin_h, register_org_pk, other_org_pk):
        assert _post(client, sakha_admin_h, register_org_pk).status_code == 201     # FINANCE_CONFIGURE, owner 2026-11-17
        assert _post(client, sakha_admin_h, other_org_pk).status_code == 403

    @pytest.mark.parametrize("who", ["sakha_admin_h", "other_admin_h", "viewer_h", "plain_member_h"])
    def test_nobody_outside_the_kendra_refreshes_the_copies(self, request, client, write_conn, admin_h, who):
        source = _all_sakhas(client, admin_h, write_conn)
        assert client.post(f"{BASE}/heads/{source['finance_head_pk']}/sync-copies", headers=request.getfixturevalue(who)).status_code == 403

    def test_the_kendra_admin_may(self, client, kendra_h, register_org_pk):
        assert _post(client, kendra_h, register_org_pk).status_code == 201

    def test_all_sakhas_cannot_be_used_by_a_sakha(self, client, admin_h, register_org_pk):
        r = _post(client, admin_h, register_org_pk, applies_to="ALL_SAKHAS")
        assert r.status_code == 422

    def test_sync_copies_only_works_on_an_all_sakhas_source(self, client, admin_h, register_org_pk):
        plain = _post(client, admin_h, register_org_pk).json()["head"]
        assert client.post(f"{BASE}/heads/{plain['finance_head_pk']}/sync-copies", headers=admin_h).status_code == 422
        assert client.post(f"{BASE}/heads/{FAKE_UUID}/sync-copies", headers=admin_h).status_code == 422     # "Finance head not found." is a 422 throughout

    def test_a_foreign_account_cannot_be_used_for_a_contribution(self, client, admin_h, register_org_pk, other_org_pk, mock_gateway):
        foreign = make_account(client, admin_h, other_org_pk, mock_gateway)
        assert _post(client, admin_h, register_org_pk, collection_account_pk=foreign["financial_account_pk"]).status_code == 422
        assert _post(client, admin_h, register_org_pk, collection_account_pk=FAKE_UUID).status_code in (404, 422)


class TestInputIsHostileSafe:
    @pytest.mark.parametrize("over", [
        {"fixed_amount": "1.234", "due_period": "YEARLY"},                # more than two decimals
        {"fixed_amount": "99999999999999.99", "due_period": "YEARLY"},     # beyond the money cap
        {"fixed_amount": "NaN", "due_period": "YEARLY"},
        {"fixed_amount": "Infinity", "due_period": "YEARLY"},
        {"description": "x" * 2001},
        {"head_name": "y" * 151},
        {"organization_pk": "not-a-uuid"},
        {"fixed_amount": "5", "due_period": "yearly"},                    # the value list is exact
    ])
    def test_bad_values_are_refused(self, client, admin_h, register_org_pk, over):
        body = {"organization_pk": str(register_org_pk), "head_name": "Probe"}
        body.update(over)
        assert client.post(f"{BASE}/contributions", json=body, headers=admin_h).status_code == 422

    def test_markup_and_sql_in_the_name_are_stored_as_text(self, client, admin_h, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        name = "x'); DROP TABLE nss.finance_head;-- <script>alert(1)</script>"
        r = _post(client, admin_h, register_org_pk, head_name=name)
        assert r.status_code == 201 and r.json()["head"]["head_name"] == name
        assert client.get(f"{BASE}/heads", params={"organization_pk": str(register_org_pk), "q": "DROP TABLE"}, headers=admin_h).json()["total"] >= 1

    def test_the_server_decides_the_code_direction_and_flags(self, client, admin_h, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        r = _post(client, admin_h, register_org_pk, head_code="HACKED", direction="EXPENSE", is_restricted=True, allow_upi=False,
                  applies_to_all_sakhas=True, template_head_pk=FAKE_UUID, status="INACTIVE")
        assert r.status_code == 201
        h = r.json()["head"]
        assert h["head_code"].startswith("CONTRIB_") and h["direction"] == "INCOME" and h["is_restricted"] is False
        assert h["applies_to_all_sakhas"] is False and h["template_head_pk"] is None and h["status"] == "ACTIVE"


# ═══════════════════════════════════════════════════════════════════════
# A Sakha's copy
# ═══════════════════════════════════════════════════════════════════════

class TestTheCopyIsTheKendrasToDefine:
    def test_nobody_without_configure_rights_over_that_sakha_can_change_a_copy(self, client, admin_h, write_conn, register_org_pk, other_admin_h, plain_member_h):
        # FINANCE_CONFIGURE is held by the Sakha's own admin (it may pick its account or switch its copy off), not by a foreign Sakha's admin.
        copy = _copy(client, admin_h, _all_sakhas(client, admin_h, write_conn)["finance_head_pk"], register_org_pk)
        pk = copy["finance_head_pk"]
        for headers in (other_admin_h, plain_member_h):
            assert client.patch(f"{BASE}/heads/{pk}", json={"collection_account_pk": None}, headers=headers).status_code == 403
            assert client.post(f"{BASE}/heads/{pk}/transition", json={"status": "INACTIVE"}, headers=headers).status_code == 403

    def test_even_an_approver_cannot_rewrite_the_kendras_terms_in_a_copy(self, client, admin_h, write_conn, register_org_pk):
        copy = _copy(client, admin_h, _all_sakhas(client, admin_h, write_conn)["finance_head_pk"], register_org_pk)
        for body in ({"fixed_amount": "1", "due_period": "YEARLY"}, {"fixed_amount": None}, {"due_period": "MONTHLY"}, {"allow_part_payment": True},
                     {"head_name": "Cheaper"}, {"description": "x"}, {"is_pranami": False}, {"allow_upi": False},
                     {"collection_scope_pk": FAKE_UUID}):
            r = client.patch(f"{BASE}/heads/{copy['finance_head_pk']}", json=body, headers=admin_h)
            assert r.status_code == 403, body
        after = client.get(f"{BASE}/heads/{copy['finance_head_pk']}", headers=admin_h).json()
        assert (after["head_name"], after["fixed_amount"], after["due_period"]) == (copy["head_name"], copy["fixed_amount"], copy["due_period"])

    def test_a_copys_account_must_belong_to_that_sakha(self, client, admin_h, write_conn, register_org_pk, other_org_pk, mock_gateway):
        copy = _copy(client, admin_h, _all_sakhas(client, admin_h, write_conn)["finance_head_pk"], register_org_pk)
        foreign = make_account(client, admin_h, other_org_pk, mock_gateway)
        r = client.patch(f"{BASE}/heads/{copy['finance_head_pk']}", json={"collection_account_pk": foreign["financial_account_pk"]}, headers=admin_h)
        assert r.status_code == 422

    def test_the_source_never_collects_and_cannot_be_made_to(self, client, admin_h, write_conn, mock_gateway):
        source = _all_sakhas(client, admin_h, write_conn)
        account = make_account(client, admin_h, _kendra_pk(write_conn), mock_gateway)
        for body in ({"allow_upi": True}, {"collection_account_pk": account["financial_account_pk"]}, {"collection_scope_pk": FAKE_UUID}):
            assert client.patch(f"{BASE}/heads/{source['finance_head_pk']}", json=body, headers=admin_h).status_code == 422, body


# ═══════════════════════════════════════════════════════════════════════
# The member's cards
# ═══════════════════════════════════════════════════════════════════════

class TestMemberCardsDoNotLeak:
    def _setup(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)
        return source, _copy(client, admin_h, source["finance_head_pk"], register_org_pk)

    def test_a_card_carries_only_the_declared_fields(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        _, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        cards = client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json()
        assert cards and all(set(c) == set(S.MyPayableHead.model_fields) for c in cards)

    def test_no_account_credential_or_internal_id_reaches_a_member(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        _, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        text = client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).text
        for secret in (mock_gateway.secret, mock_gateway.ref, mine["collection_account_pk"], mine["collection_scope_pk"]):
            assert secret not in text
        for key in ("gateway_credential_ref", "gateway_provider", "gateway_merchant_ref", "financial_account_pk", "template_head_pk", "head_code",
                    "created_by", "applies_to_all_sakhas"):
            assert key not in text, key

    def test_a_member_sees_neither_the_source_nor_another_sakhas_copy(self, client, admin_h, write_conn, register_org_pk, other_org_pk, mock_gateway, plain_member_h):
        source, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        theirs = _copy(client, admin_h, source["finance_head_pk"], other_org_pk)
        offered = {c["finance_head_pk"] for c in client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json()}
        assert mine["finance_head_pk"] in offered
        assert source["finance_head_pk"] not in offered and theirs["finance_head_pk"] not in offered

    def test_the_source_and_another_sakhas_copy_cannot_be_paid_even_with_the_id(self, client, admin_h, write_conn, register_org_pk, other_org_pk, mock_gateway, plain_member_h):
        source, _ = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        theirs = _copy(client, admin_h, source["finance_head_pk"], other_org_pk)
        for pk in (source["finance_head_pk"], theirs["finance_head_pk"]):
            r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": pk, "amount": "500.00"}, headers=plain_member_h)
            assert r.status_code == 422, pk

    def test_a_switched_off_copy_cannot_be_paid(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        source, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        client.post(f"{BASE}/heads/{source['finance_head_pk']}/transition", json={"status": "INACTIVE"}, headers=admin_h)
        offered = {c["finance_head_pk"] for c in client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json()}
        assert mine["finance_head_pk"] not in offered
        assert client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": "500.00"}, headers=plain_member_h).status_code == 422

    def test_the_payer_and_the_amount_rule_cannot_be_overridden(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member, plain_member_h):
        _, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        other = new_member(write_conn, register_org_pk, "FinConVictim")
        # a cheaper amount, another member's identity, a different paid total: all ignored or refused
        r = client.post(f"{BASE}/my-pranami/pay", headers=plain_member_h, json={
            "finance_head_pk": mine["finance_head_pk"], "amount": "1.00", "paid_amount": "500.00", "sangha_sevi_id": other["sangha_sevi_id"],
            "payer_person_pk": other["person_pk"]})
        assert r.status_code == 422
        ok = client.post(f"{BASE}/my-pranami/pay", headers=plain_member_h, json={
            "finance_head_pk": mine["finance_head_pk"], "amount": "500.00", "sangha_sevi_id": other["sangha_sevi_id"], "payer_person_pk": other["person_pk"]})
        assert ok.status_code == 201
        full = client.get(f"{BASE}/payment-requests/{ok.json()['upi_payment_request_pk']}", headers=admin_h).json()
        assert full["payer_sangha_sevi_id"] == plain_member["sangha_sevi_id"]

    def test_one_members_payment_never_changes_anothers_card(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        from tests.finance_support import pay_request

        _, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": "500.00"}, headers=plain_member_h).json()
        full = client.get(f"{BASE}/payment-requests/{r['upi_payment_request_pk']}", headers=admin_h).json()
        assert pay_request(client, mock_gateway, full).status_code == 200
        other = new_member(write_conn, register_org_pk, "FinConB2")
        other_h = _login_headers(client, other["sangha_sevi_id"], other["password"])
        theirs = {c["finance_head_pk"]: c for c in client.get(f"{BASE}/my-pranami/heads", headers=other_h).json()}
        assert theirs[mine["finance_head_pk"]]["state"] == "DUE" and theirs[mine["finance_head_pk"]]["paid_amount"] == "0.00"

    def test_a_forged_webhook_amount_cannot_settle_a_fixed_head(self, client, admin_h, write_conn, register_org_pk, mock_gateway, plain_member_h):
        from tests.finance_support import pay_request

        _, mine = self._setup(client, admin_h, write_conn, register_org_pk, mock_gateway)
        r = client.post(f"{BASE}/my-pranami/pay", json={"finance_head_pk": mine["finance_head_pk"], "amount": "500.00"}, headers=plain_member_h).json()
        full = client.get(f"{BASE}/payment-requests/{r['upi_payment_request_pk']}", headers=admin_h).json()
        pay_request(client, mock_gateway, full, amount="1.00")                      # the bank says 1 rupee arrived, not 500
        card = next(c for c in client.get(f"{BASE}/my-pranami/heads", headers=plain_member_h).json() if c["finance_head_pk"] == mine["finance_head_pk"])
        assert card["state"] != "PAID" and card["paid_amount"] != "500.00"


class TestNothingLeaksOnTheAdminSide:
    def test_no_secret_in_any_contribution_response(self, client, admin_h, write_conn, register_org_pk, mock_gateway):
        make_account(client, admin_h, register_org_pk, mock_gateway, is_default=True)
        source = _all_sakhas(client, admin_h, write_conn)
        texts = [client.get(f"{BASE}/heads", params={"organization_pk": str(register_org_pk)}, headers=admin_h).text,
                 client.get(f"{BASE}/heads/{source['finance_head_pk']}", headers=admin_h).text,
                 client.post(f"{BASE}/heads/{source['finance_head_pk']}/sync-copies", headers=admin_h).text,
                 json.dumps(_post(client, admin_h, register_org_pk).json())]
        for text in texts:
            assert mock_gateway.secret not in text and not re.search(r"key_secret|webhook_secret", text)

    def test_the_sakha_admin_sees_only_their_own_sakhas_copies(self, client, admin_h, write_conn, register_org_pk, other_org_pk, sakha_admin_h):
        source = _all_sakhas(client, admin_h, write_conn)["finance_head_pk"]
        mine, theirs = _copy(client, admin_h, source, register_org_pk), _copy(client, admin_h, source, other_org_pk)
        listed = {h["finance_head_pk"] for h in client.get(f"{BASE}/heads", params={"page_size": 200, "with_templates": "false"}, headers=sakha_admin_h).json()["items"]}
        assert mine["finance_head_pk"] in listed and theirs["finance_head_pk"] not in listed
        assert client.get(f"{BASE}/heads/{theirs['finance_head_pk']}", headers=sakha_admin_h).status_code == 403
