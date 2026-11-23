"""
Finance — a scope and a fund can be created ACTIVE at once, and a scope's code is made for the user (owner 2026-11-22: "why scope is draft
always and funds too, and scope code should come automatic (Sakha code + name)").

  * ``activate`` creates the scope ACTIVE; without it the API still creates a DRAFT (nothing else changes);
  * a fund created with ``activate`` is ACTIVE only when its scope is ACTIVE (a fund is never active in a draft scope);
  * no ``scope_code``: it is the Sakha's short code (organization code when it has none) + the scope name, numbered when taken;
  * a code that IS given is still used, and a duplicate is still 409.

Real integration tests (nothing mocked); NEVER RUN against a database when this file was written.
"""

from uuid import uuid4

import pytest

from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    admin_h,
    admin_user,
    kendra_admin,
    kendra_h,
    other_admin,
    other_admin_h,
    other_org_pk,
    plain_member_h,
    plain_sakha_admin,
    plain_sakha_admin_h,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    viewer_h,
    viewer_user,
)


def _prefix(write_conn, org_pk) -> str:
    cur = write_conn.cursor()
    cur.execute("SELECT COALESCE(NULLIF(short_code, ''), organization_code) FROM nss.organization WHERE organization_pk = %s", (org_pk,))
    return "".join(ch if ch.isalnum() else "-" for ch in cur.fetchone()[0].upper())


def _scope(client, h, org_pk, name, **over):
    body = {"scope_name": name, "scope_type": "ORGANIZATION", "organization_pk": str(org_pk)}
    body.update(over)
    r = client.post(f"{BASE}/scopes", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _unique(word="Drive") -> str:
    return f"{word} {uuid4().hex[:6]}"


def _number(code: str, base: str) -> int:
    """1 for ``base``, N for ``base-N``: the position in the numbering of one Sangha's codes of one type."""
    assert code == base or code.startswith(base + "-"), (code, base)
    return int(code[len(base) + 1:]) if code != base else 1


class TestScopeCode:
    """Owner 2026-11-23: the scope code is the Sangha's code + the scope TYPE's code (master data: ORG, EVT, SPL, RSTR), numbered when taken; the name plays no part."""

    def test_the_code_is_the_sakha_code_then_the_scope_type_code(self, client, admin_h, register_org_pk, write_conn):
        base = _prefix(write_conn, register_org_pk)
        for scope_type, code in (("ORGANIZATION", "ORG"), ("EVENT", "EVT"), ("SPECIAL_PURPOSE", "SPL"), ("RESTRICTED_FUND", "RSTR")):
            scope = _scope(client, admin_h, register_org_pk, _unique(), scope_type=scope_type)
            assert _number(scope["scope_code"], f"{base}-{code}") >= 1, scope["scope_code"]

    def test_the_name_plays_no_part(self, client, admin_h, register_org_pk, write_conn):
        a = _scope(client, admin_h, register_org_pk, "Annual Festival", scope_type="EVENT")["scope_code"]
        b = _scope(client, admin_h, register_org_pk, "Something else entirely", scope_type="EVENT")["scope_code"]
        base = f"{_prefix(write_conn, register_org_pk)}-EVT"
        assert "FESTIVAL" not in a and _number(b, base) == _number(a, base) + 1                 # numbered by type, whatever the names

    def test_a_second_scope_of_the_same_type_is_numbered(self, client, admin_h, register_org_pk, write_conn):
        base = f"{_prefix(write_conn, register_org_pk)}-SPL"
        first = _scope(client, admin_h, register_org_pk, _unique(), scope_type="SPECIAL_PURPOSE")["scope_code"]
        second = _scope(client, admin_h, register_org_pk, _unique(), scope_type="SPECIAL_PURPOSE")["scope_code"]
        assert _number(second, base) == _number(first, base) + 1

    def test_a_code_that_is_given_is_still_used_and_a_duplicate_is_refused(self, client, admin_h, register_org_pk):
        code = f"MINE{uuid4().hex[:6].upper()}"
        assert _scope(client, admin_h, register_org_pk, _unique(), scope_code=code)["scope_code"] == code
        r = client.post(f"{BASE}/scopes", json={"scope_code": code, "scope_name": "x", "scope_type": "SPECIAL_PURPOSE"}, headers=admin_h)
        assert r.status_code == 409

    def test_a_scope_with_no_organization_takes_the_type_code_alone(self, client, admin_h):
        r = client.post(f"{BASE}/scopes", json={"scope_name": _unique(), "scope_type": "SPECIAL_PURPOSE"}, headers=admin_h)
        assert r.status_code == 201 and (r.json()["scope_code"] == "SPL" or r.json()["scope_code"].startswith("SPL-"))

    def test_a_blank_name_is_refused(self, client, admin_h, register_org_pk):
        r = client.post(f"{BASE}/scopes", json={"scope_name": "   ", "scope_type": "ORGANIZATION", "organization_pk": str(register_org_pk)}, headers=admin_h)
        assert r.status_code == 422

    def test_the_reference_lists_the_scope_type_codes_and_they_are_master_data(self, client, admin_h):
        codes = client.get(f"{BASE}/reference", headers=admin_h).json()["scope_type_codes"]
        assert codes == {"ORGANIZATION": "ORG", "EVENT": "EVT", "SPECIAL_PURPOSE": "SPL", "RESTRICTED_FUND": "RSTR"}
        listed = client.get("/api/v1/foundation/master-data", params={"category_code": "SCOPE_TYPE_CODE"}, headers=admin_h)
        assert listed.status_code == 200 and len(listed.json()) == 4

    def test_an_edited_scope_type_code_is_what_the_next_scope_gets_and_a_missing_one_is_a_clear_422(self, client, admin_h, register_org_pk, write_conn):
        cur = write_conn.cursor()
        sub = "(SELECT master_category_pk FROM nss.master_category WHERE category_code = 'SCOPE_TYPE_CODE')"
        cur.execute(f"UPDATE nss.master_data SET value_code = 'RSTD' WHERE description = 'RESTRICTED_FUND' AND master_category_pk = {sub}")
        assert _scope(client, admin_h, register_org_pk, _unique(), scope_type="RESTRICTED_FUND")["scope_code"].startswith(f"{_prefix(write_conn, register_org_pk)}-RSTD")
        cur.execute(f"UPDATE nss.master_data SET is_active = FALSE, deleted_at = NOW() WHERE description = 'SPECIAL_PURPOSE' AND master_category_pk = {sub}")
        r = client.post(f"{BASE}/scopes", json={"scope_name": "x", "scope_type": "SPECIAL_PURPOSE", "organization_pk": str(register_org_pk)}, headers=admin_h)
        assert r.status_code == 422 and "Scope Type Code" in r.text


class TestActiveAtOnce:
    def test_the_default_is_still_a_draft(self, client, admin_h, register_org_pk):
        assert _scope(client, admin_h, register_org_pk, _unique())["status"] == "DRAFT"

    def test_activate_creates_it_active_and_it_is_audited(self, client, admin_h, register_org_pk, write_conn):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        assert scope["status"] == "ACTIVE"
        cur = write_conn.cursor()
        cur.execute("SELECT detail FROM nss.system_event_log WHERE table_name = 'financial_scope' AND record_pk::text = %s AND action = 'CREATE'",
                    (scope["financial_scope_pk"],))
        assert any(row[0] and row[0].get("status") == "ACTIVE" and row[0].get("code_generated") is True for row in cur.fetchall())

    def test_a_fund_in_an_active_scope_is_created_active(self, client, admin_h, register_org_pk):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        r = client.post(f"{BASE}/funds", json={"fund_code": f"F{uuid4().hex[:6].upper()}", "fund_name": "General", "fund_type": "GENERAL",
                                               "financial_scope_pk": scope["financial_scope_pk"], "activate": True}, headers=admin_h)
        assert r.status_code == 201 and r.json()["status"] == "ACTIVE"

    def test_a_fund_in_a_draft_scope_stays_a_draft_even_when_asked_to_activate(self, client, admin_h, register_org_pk):
        scope = _scope(client, admin_h, register_org_pk, _unique())                     # DRAFT
        r = client.post(f"{BASE}/funds", json={"fund_code": f"F{uuid4().hex[:6].upper()}", "fund_name": "General", "fund_type": "GENERAL",
                                               "financial_scope_pk": scope["financial_scope_pk"], "activate": True}, headers=admin_h)
        assert r.status_code == 201 and r.json()["status"] == "DRAFT"

    def test_a_fund_without_activate_is_a_draft(self, client, admin_h, register_org_pk):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        r = client.post(f"{BASE}/funds", json={"fund_code": f"F{uuid4().hex[:6].upper()}", "fund_name": "General", "fund_type": "GENERAL",
                                               "financial_scope_pk": scope["financial_scope_pk"]}, headers=admin_h)
        assert r.status_code == 201 and r.json()["status"] == "DRAFT"

    def test_an_active_scope_takes_transactions_straight_away(self, client, admin_h, register_org_pk):
        from tests.finance_support import adopt_templates, make_txn, make_year

        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        adopt_templates(client, admin_h, register_org_pk)                                # the Sakha's heads (a new scope does this in make_scope)
        year = make_year(client, admin_h)
        make_txn(client, admin_h, year, scope, kind="INCOME")                            # would be refused for a DRAFT scope


class TestWhoMayCreateScopesAndFunds:
    """Owner 2026-11-22: only a FINANCE ADMINISTRATOR - the Sakha's seated Treasurer / President / Secretary (tests/api/test_finance_approval.py) or an admin
    GIVEN a Finance role. Being an admin does not make anyone one by default."""

    def _body(self, org_pk):
        return {"scope_name": _unique("Books"), "scope_type": "ORGANIZATION", "organization_pk": str(org_pk)}

    def test_a_sakha_admin_with_no_finance_role_cannot_create_a_scope_or_a_fund(self, client, admin_h, plain_sakha_admin_h, register_org_pk):
        r = client.post(f"{BASE}/scopes", headers=plain_sakha_admin_h, json=self._body(register_org_pk))
        assert r.status_code == 403 and "finance administrator" in r.text and "Finance role" in r.text
        scope = _scope(client, admin_h, register_org_pk, _unique())
        fund = {"fund_code": f"F{uuid4().hex[:6].upper()}", "fund_name": "x", "fund_type": "GENERAL", "financial_scope_pk": scope["financial_scope_pk"]}
        r = client.post(f"{BASE}/funds", headers=plain_sakha_admin_h, json=fund)
        assert r.status_code == 403 and "finance administrator" in r.text

    def test_that_same_admin_still_holds_the_finance_permissions_and_can_read(self, client, plain_sakha_admin_h):
        assert client.get(f"{BASE}/scopes", headers=plain_sakha_admin_h).status_code == 200
        assert client.get(f"{BASE}/reference", headers=plain_sakha_admin_h).json()["finance_admin"] is False

    def test_a_sakha_admin_given_the_finance_role_can_for_their_own_sakha_only(self, client, sakha_admin_h, register_org_pk, other_org_pk):
        r = client.post(f"{BASE}/scopes", headers=sakha_admin_h, json={**self._body(register_org_pk), "activate": True})
        assert r.status_code == 201 and r.json()["status"] == "ACTIVE"
        fund = {"fund_code": f"F{uuid4().hex[:6].upper()}", "fund_name": "x", "fund_type": "GENERAL", "financial_scope_pk": r.json()["financial_scope_pk"]}
        assert client.post(f"{BASE}/funds", headers=sakha_admin_h, json=fund).status_code == 201
        assert client.post(f"{BASE}/scopes", headers=sakha_admin_h, json=self._body(other_org_pk)).status_code == 403
        assert client.get(f"{BASE}/reference", headers=sakha_admin_h).json()["finance_admin"] is True

    def test_the_kendra_admin_given_the_kendra_finance_role_can(self, client, kendra_h):
        r = client.post(f"{BASE}/scopes", headers=kendra_h, json={"scope_name": _unique("Kendra books"), "scope_type": "SPECIAL_PURPOSE"})
        assert r.status_code == 201, r.text

    def test_the_super_administrator_always_can(self, client, admin_h, register_org_pk, other_org_pk):
        assert client.post(f"{BASE}/scopes", headers=admin_h, json=self._body(register_org_pk)).status_code == 201
        assert client.post(f"{BASE}/scopes", headers=admin_h, json=self._body(other_org_pk)).status_code == 201

    def test_a_view_only_role_and_a_member_cannot(self, client, viewer_h, plain_member_h, register_org_pk):
        for h in (viewer_h, plain_member_h):
            assert client.post(f"{BASE}/scopes", headers=h, json=self._body(register_org_pk)).status_code == 403

    def test_a_given_finance_role_also_lets_the_admin_set_up_funds_and_it_is_reported_to_the_page(self, client, other_admin_h, other_org_pk):
        r = client.post(f"{BASE}/scopes", headers=other_admin_h, json={**self._body(other_org_pk), "activate": True})
        assert r.status_code == 201
        assert client.get(f"{BASE}/reference", headers=other_admin_h).json()["finance_admin"] is True


class TestFundCode:
    """Owner 2026-11-22: the fund code is the Sangha's code + the fund type's code (EKM-GEN); numbered when the scope already has one of that type."""

    def _fund(self, client, h, scope, fund_type="GENERAL", **over):
        body = {"fund_name": _unique("Fund"), "fund_type": fund_type, "financial_scope_pk": scope["financial_scope_pk"]}
        body.update(over)
        return client.post(f"{BASE}/funds", json=body, headers=h)

    def test_the_code_is_the_sakha_code_plus_the_type_code(self, client, admin_h, register_org_pk, write_conn):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        r = self._fund(client, admin_h, scope)
        assert r.status_code == 201 and r.json()["fund_code"] == f"{_prefix(write_conn, register_org_pk)}-GEN", r.text
        r2 = self._fund(client, admin_h, scope, fund_type="PUBLICATION")
        assert r2.json()["fund_code"] == f"{_prefix(write_conn, register_org_pk)}-PUB"

    def test_a_second_fund_of_the_same_type_in_the_scope_is_numbered(self, client, admin_h, register_org_pk, write_conn):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        first, second, third = (self._fund(client, admin_h, scope).json()["fund_code"] for _ in range(3))
        assert second == first + "-2" and third == first + "-3"

    def test_the_same_type_in_another_scope_takes_the_plain_code_again(self, client, admin_h, register_org_pk):
        a = self._fund(client, admin_h, _scope(client, admin_h, register_org_pk, _unique(), activate=True)).json()["fund_code"]
        b = self._fund(client, admin_h, _scope(client, admin_h, register_org_pk, _unique(), activate=True)).json()["fund_code"]
        assert a == b                                                               # unique per scope, not system-wide

    def test_a_sinking_fund_is_coded_from_the_sakha_it_belongs_to(self, client, admin_h, register_org_pk, other_org_pk, write_conn):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        r = self._fund(client, admin_h, scope, fund_type="SINKING_FUND", organization_pk=str(other_org_pk))
        assert r.status_code == 201 and r.json()["fund_code"] == f"{_prefix(write_conn, other_org_pk)}-SINK", r.text

    def test_a_code_that_is_given_is_still_used_and_a_duplicate_is_refused(self, client, admin_h, register_org_pk):
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        code = f"MY{uuid4().hex[:6].upper()}"
        assert self._fund(client, admin_h, scope, fund_code=code).json()["fund_code"] == code
        assert self._fund(client, admin_h, scope, fund_code=code).status_code == 409
        assert self._fund(client, admin_h, scope, fund_code="   ").status_code == 422

    def test_the_reference_lists_the_type_codes(self, client, admin_h):
        codes = client.get(f"{BASE}/reference", headers=admin_h).json()["fund_type_codes"]
        assert codes["GENERAL"] == "GEN" and len(set(codes.values())) == len(codes) == 10


class TestFundTypeCodesAreMasterData:
    def test_the_codes_are_in_the_reference_data_with_the_other_master_data(self, client, admin_h, write_conn):
        cur = write_conn.cursor()
        cur.execute("""SELECT md.value_code, md.description FROM nss.master_data md JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                        WHERE mc.category_code = 'FUND_TYPE_CODE' AND md.is_active""")
        assert dict((d, c) for c, d in cur.fetchall())["GENERAL"] == "GEN"
        listed = client.get("/api/v1/foundation/master-data", params={"category_code": "FUND_TYPE_CODE"}, headers=admin_h)     # the Reference Data screen's own list
        assert listed.status_code == 200 and {m["value_code"]: m["description"] for m in listed.json()}["GEN"] == "GENERAL" and len(listed.json()) == 10

    def test_an_edited_code_is_what_the_next_fund_gets(self, client, admin_h, register_org_pk, write_conn):
        cur = write_conn.cursor()
        cur.execute("""UPDATE nss.master_data SET value_code = 'GENL' WHERE description = 'GENERAL' AND master_category_pk =
                        (SELECT master_category_pk FROM nss.master_category WHERE category_code = 'FUND_TYPE_CODE')""")
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        r = client.post(f"{BASE}/funds", json={"fund_name": "x", "fund_type": "GENERAL", "financial_scope_pk": scope["financial_scope_pk"]}, headers=admin_h)
        assert r.status_code == 201 and r.json()["fund_code"].endswith("-GENL"), r.text
        assert client.get(f"{BASE}/reference", headers=admin_h).json()["fund_type_codes"]["GENERAL"] == "GENL"

    def test_a_fund_type_whose_code_was_switched_off_gets_a_clear_422(self, client, admin_h, register_org_pk, write_conn):
        cur = write_conn.cursor()
        cur.execute("""UPDATE nss.master_data SET is_active = FALSE, deleted_at = NOW() WHERE description = 'GRANT' AND master_category_pk =
                        (SELECT master_category_pk FROM nss.master_category WHERE category_code = 'FUND_TYPE_CODE')""")
        scope = _scope(client, admin_h, register_org_pk, _unique(), activate=True)
        r = client.post(f"{BASE}/funds", json={"fund_name": "x", "fund_type": "GRANT", "financial_scope_pk": scope["financial_scope_pk"]}, headers=admin_h)
        assert r.status_code == 422 and "Fund Type Code" in r.text
        ok = client.post(f"{BASE}/funds", json={"fund_name": "x", "fund_code": "OWNCODE", "fund_type": "GRANT", "financial_scope_pk": scope["financial_scope_pk"]}, headers=admin_h)
        assert ok.status_code == 201 and ok.json()["fund_code"] == "OWNCODE"                    # giving a code still works
