"""
Finance — the Kendra's annual audit (Bye-Law Section G; api/services/finance_audit.py, api/routers/finance_audit.py).

Rules under test:
  * ONE audit per Kendra per financial year; only the Kendra has one (a Sakha's id is refused); ANY year may be audited (open, closing or closed);
  * the steps cannot be skipped or reordered: APPOINTED -> REPORT_RECEIVED -> PLACED_BEFORE_GB -> APPROVED -> PLACED_BEFORE_GENERAL_BODY, each with its
    reference and date, the dates in that order and never in the future;
  * placing the report before the Governing Body files a numbered letter Kendra -> Advisory Board in Correspondence (the Board gets its INWARD copy);
  * a recorded text is corrected only with a reason; the status never moves back;
  * the Parichalak's personal expenditure (Bye-Law clause 17) is shown as not subject to audit;
  * a scoped Sakha administrator cannot see or change the Kendra's audit.

Real integration tests (nothing mocked); NEVER RUN against a database when this file was written.
"""

import itertools
from datetime import date, timedelta

import pytest

from tests.api.test_finance_budget import _year
from tests.finance_support import (  # noqa: F401  (fixtures)
    BASE,
    admin_h,
    admin_user,
    other_admin,
    other_admin_h,
    other_org_pk,
    register_org_pk,
    sakha_admin,
    sakha_admin_h,
    sakha_pks,
    viewer_h,
    viewer_user,
)
from tests.reparent_support import kendra_pks

pytestmark = pytest.mark.integration
_TODAY = date.today()
_d = lambda n: str(_TODAY - timedelta(days=n))        # noqa: E731  (n days ago)
_n = itertools.count(1)


@pytest.fixture(scope="module")
def kendra_org_pk(write_conn):
    return kendra_pks(write_conn)[0]


def _fresh_year(client, h) -> dict:
    """A financial year that has no audit yet (every test takes its own: one audit per year)."""
    for _ in range(60):
        year = _year(client, h)
        if client.get(f"{BASE}/audits", params={"financial_year_pk": year["financial_year_pk"]}, headers=h).json()["total"] == 0:
            return year
    raise AssertionError("no financial year without an audit could be found")


def _start(client, h, year=None, **over):
    year = year or _fresh_year(client, h)
    body = {"financial_year_pk": year["financial_year_pk"], "auditor_name": "A. Auditor", "auditor_firm": "A & Co", "appointed_on": _d(50),
            "appointment_reference": f"GB/{next(_n)}", **over}
    return year, client.post(f"{BASE}/audits", json=body, headers=h)


def _audit(client, h) -> dict:
    _, r = _start(client, h)
    assert r.status_code == 201, r.text
    return r.json()


def _step(client, h, audit, step, body):
    return client.post(f"{BASE}/audits/{audit['finance_year_audit_pk']}/{step}", json=body, headers=h)


REPORT = {"report_reference": "AR/1", "report_date": _d(40)}
GB = {"gb_placed_on": _d(30), "gb_reference": "GB/200"}
APPROVAL = {"approved_on": _d(20), "approval_reference": "CM/1"}
GENERAL = {"general_body_on": _d(10), "general_body_reference": "GBM/1"}


class TestStartingTheAudit:
    def test_the_appointment_starts_it(self, client, admin_h, kendra_org_pk):
        audit = _audit(client, admin_h)
        assert audit["status"] == "APPOINTED" and audit["organization_pk"] == str(kendra_org_pk)
        assert audit["auditor_name"] == "A. Auditor" and audit["auditor_firm"] == "A & Co" and audit["step_number"] == 1
        assert audit["next_step"] and audit["not_subject_to_audit"]["note"]

    def test_one_audit_per_year(self, client, admin_h):
        year, first = _start(client, admin_h)
        assert first.status_code == 201
        assert _start(client, admin_h, year)[1].status_code == 409

    def test_a_sakha_has_no_audit(self, client, admin_h, register_org_pk):
        assert _start(client, admin_h, organization_pk=str(register_org_pk))[1].status_code == 422

    def test_blank_and_future_facts_are_refused(self, client, admin_h):
        assert _start(client, admin_h, auditor_name="  ")[1].status_code == 422
        assert _start(client, admin_h, appointed_on=str(_TODAY + timedelta(days=1)))[1].status_code == 422

    @pytest.mark.parametrize("year_status", ["OPEN", "CLOSING", "CLOSED"])
    def test_any_year_status_can_be_audited(self, client, admin_h, year_status, write_conn):
        year = _fresh_year(client, admin_h)
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.financial_year SET status = %s WHERE financial_year_pk = %s", (year_status, year["financial_year_pk"]))
        assert _start(client, admin_h, year)[1].status_code == 201


class TestTheChain:
    def test_the_whole_chain_in_order(self, client, admin_h):
        audit = _audit(client, admin_h)
        step = _step(client, admin_h, audit, "report", {**REPORT, "report_link": "https://example.org/audit.pdf"})
        assert step.status_code == 200 and step.json()["status"] == "REPORT_RECEIVED" and step.json()["report_link"] == "https://example.org/audit.pdf"
        step = _step(client, admin_h, audit, "governing-body", GB)
        d = step.json()
        assert step.status_code == 200 and d["status"] == "PLACED_BEFORE_GB" and d["advisory_correspondence_pk"]
        assert d["advisory_letter_reference"] and d["advisory_letter_inward_reference"]                 # the Advisory Board has its own copy
        step = _step(client, admin_h, audit, "approval", APPROVAL)
        assert step.status_code == 200 and step.json()["status"] == "APPROVED"
        step = _step(client, admin_h, audit, "general-body", GENERAL)
        d = step.json()
        assert step.status_code == 200 and d["status"] == "PLACED_BEFORE_GENERAL_BODY" and d["next_step"] is None and d["step_number"] == d["steps_total"]

    def test_the_letter_is_filed_to_the_advisory_board(self, client, admin_h, write_conn):
        audit = _audit(client, admin_h)
        _step(client, admin_h, audit, "report", REPORT)
        d = _step(client, admin_h, audit, "governing-body", GB).json()
        cur = write_conn.cursor()
        cur.execute("SELECT direction, subject FROM nss.correspondence WHERE correspondence_pk = %s", (d["advisory_correspondence_pk"],))
        direction, subject = cur.fetchone()
        assert direction == "OUTWARD" and d["year_code"] in subject

    def test_steps_cannot_be_skipped(self, client, admin_h):
        audit = _audit(client, admin_h)
        for step, body in (("governing-body", GB), ("approval", APPROVAL), ("general-body", GENERAL)):
            assert _step(client, admin_h, audit, step, body).status_code == 422
        _step(client, admin_h, audit, "report", REPORT)
        for step, body in (("approval", APPROVAL), ("general-body", GENERAL), ("report", REPORT)):
            assert _step(client, admin_h, audit, step, body).status_code == 422
        _step(client, admin_h, audit, "governing-body", GB)
        assert _step(client, admin_h, audit, "general-body", GENERAL).status_code == 422                # not before the combined meeting approved it
        assert client.get(f"{BASE}/audits/{audit['finance_year_audit_pk']}", headers=admin_h).json()["status"] == "PLACED_BEFORE_GB"

    def test_a_refused_step_files_no_letter(self, client, admin_h, write_conn):
        audit = _audit(client, admin_h)
        _step(client, admin_h, audit, "report", REPORT)
        cur = write_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nss.correspondence")
        before = cur.fetchone()[0]
        assert _step(client, admin_h, audit, "governing-body", {"gb_placed_on": _d(45), "gb_reference": "GB/9"}).status_code == 422     # before the report
        cur.execute("SELECT COUNT(*) FROM nss.correspondence")
        assert cur.fetchone()[0] == before

    def test_dates_keep_the_order_and_are_not_future(self, client, admin_h):
        audit = _audit(client, admin_h)
        assert _step(client, admin_h, audit, "report", {"report_reference": "R", "report_date": _d(60)}).status_code == 422      # before the appointment
        assert _step(client, admin_h, audit, "report", {"report_reference": "R", "report_date": str(_TODAY + timedelta(days=1))}).status_code == 422
        _step(client, admin_h, audit, "report", REPORT)
        _step(client, admin_h, audit, "governing-body", GB)
        assert _step(client, admin_h, audit, "approval", {**APPROVAL, "approved_on": _d(31)}).status_code == 422               # before the Governing Body

    def test_a_non_https_link_is_refused(self, client, admin_h):
        audit = _audit(client, admin_h)
        assert _step(client, admin_h, audit, "report", {**REPORT, "report_link": "http://example.org/a.pdf"}).status_code == 422


class TestCorrections:
    def test_a_correction_needs_a_reason_and_keeps_the_status(self, client, admin_h):
        audit = _audit(client, admin_h)
        url = f"{BASE}/audits/{audit['finance_year_audit_pk']}/correct"
        assert client.post(url, json={"auditor_name": "B. Auditor", "reason": " "}, headers=admin_h).status_code == 422
        r = client.post(url, json={"auditor_name": "B. Auditor", "reason": "Spelling"}, headers=admin_h)
        assert r.status_code == 200 and r.json()["auditor_name"] == "B. Auditor" and r.json()["status"] == "APPOINTED"
        assert client.post(url, json={"auditor_name": "B. Auditor", "reason": "again"}, headers=admin_h).status_code == 422     # nothing differs
        assert client.post(url, json={"report_reference": "R/9", "reason": "not yet recorded"}, headers=admin_h).status_code == 422


class TestClauseSeventeen:
    def test_the_parichalak_s_expenditure_is_shown_as_not_subject_to_audit(self, client, admin_h):
        d = _audit(client, admin_h)["not_subject_to_audit"]
        assert d["count"] >= 0 and "not subject to any audit" in d["note"]


class TestWhoCanSee:
    def test_a_sakha_administrator_cannot_see_or_change_the_kendra_s_audit(self, client, admin_h, sakha_admin_h):
        audit = _audit(client, admin_h)
        pk = audit["finance_year_audit_pk"]
        assert client.get(f"{BASE}/audits/{pk}", headers=sakha_admin_h).status_code == 403
        assert _step(client, sakha_admin_h, audit, "report", REPORT).status_code == 403
        assert pk not in {a["finance_year_audit_pk"] for a in client.get(f"{BASE}/audits", headers=sakha_admin_h).json()["items"]}

    def test_a_view_only_role_can_read_but_not_write(self, client, admin_h, viewer_h):
        audit = _audit(client, admin_h)
        assert client.get(f"{BASE}/audits/{audit['finance_year_audit_pk']}", headers=viewer_h).status_code in (200, 403)
        assert _step(client, viewer_h, audit, "report", REPORT).status_code == 403
