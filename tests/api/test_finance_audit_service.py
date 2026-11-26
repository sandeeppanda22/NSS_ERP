"""
Finance — the Kendra's annual audit, Bye-Law Section G (api/services/finance_audit.py). DB-free: the pure rules, the DDL / schema parity and
the build-script wiring.
"""

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.schemas import finance as S
from api.services import finance_audit as A

ROOT = Path(__file__).resolve().parents[2]
DDL = (ROOT / "database/ddl/14_finance/27_finance_year_audit.sql").read_text()
TODAY = date.today()
D = lambda n: TODAY - timedelta(days=n)       # noqa: E731  (n days ago)


def _audit(status=A.APPOINTED, **kw):
    base = {"finance_year_audit_pk": "p", "status": status, "appointed_on": D(50), "report_date": None, "gb_placed_on": None, "approved_on": None,
            "report_reference": None, "report_link": None, "gb_reference": None, "approval_reference": None, "general_body_reference": None,
            "auditor_name": "A. Auditor", "auditor_firm": None, "appointment_reference": "GB/1", "year_code": "2025-26"}
    base.update(kw)
    return base


class _Cur:
    """Records the UPDATE the service writes (no database)."""
    def __init__(self):
        self.sql, self.params = None, None

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params


class TestTheChainCannotBeSkipped:
    def test_the_statuses_are_in_the_bye_law_order(self):
        assert A.STEP_ORDER == S.AUDIT_STATUSES

    @pytest.mark.parametrize("status,call", [
        (A.APPOINTED, lambda a: A.validate_gb(a, placed_on=D(1), reference="GB/2")),
        (A.APPOINTED, lambda a: A.approve(_Cur(), None, a, approved_on=D(1), reference="X")),
        (A.APPOINTED, lambda a: A.place_before_general_body(_Cur(), None, a, placed_on=D(1), reference="X")),
        (A.REPORT_RECEIVED, lambda a: A.approve(_Cur(), None, a, approved_on=D(1), reference="X")),
        (A.REPORT_RECEIVED, lambda a: A.place_before_general_body(_Cur(), None, a, placed_on=D(1), reference="X")),
        (A.PLACED_BEFORE_GB, lambda a: A.place_before_general_body(_Cur(), None, a, placed_on=D(1), reference="X")),
        (A.PLACED_BEFORE_GENERAL_BODY, lambda a: A.validate_report(a, reference="R", report_date=D(1), link=None)),
    ])
    def test_a_step_out_of_turn_is_refused(self, status, call):
        with pytest.raises(HTTPException) as e:
            call(_audit(status, report_date=D(40), gb_placed_on=D(30), approved_on=D(20)))
        assert e.value.status_code == 422

    def test_the_general_body_comes_only_after_the_combined_meeting_approved(self):
        with pytest.raises(HTTPException) as e:
            A.place_before_general_body(_Cur(), None, _audit(A.PLACED_BEFORE_GB, report_date=D(40), gb_placed_on=D(30)), placed_on=D(1), reference="X")
        assert "only after" in e.value.detail

    def test_every_step_in_turn_is_accepted(self):
        cur = _Cur()
        A.record_report(cur, "actor", _audit(), reference="R/1", report_date=D(40), link="https://example.org/r.pdf")
        assert "status = %s" in cur.sql and A.REPORT_RECEIVED in cur.params
        A.place_before_gb(cur, "actor", _audit(A.REPORT_RECEIVED, report_date=D(40)), placed_on=D(30), reference="GB/2", letter_pk="L")
        assert A.PLACED_BEFORE_GB in cur.params and "L" in cur.params
        A.approve(cur, "actor", _audit(A.PLACED_BEFORE_GB, report_date=D(40), gb_placed_on=D(30)), approved_on=D(20), reference="CM/1")
        assert A.APPROVED in cur.params
        A.place_before_general_body(cur, "actor", _audit(A.APPROVED, report_date=D(40), gb_placed_on=D(30), approved_on=D(20)), placed_on=D(10), reference="GBM/1")
        assert A.PLACED_BEFORE_GENERAL_BODY in cur.params


class TestDatesAndText:
    def test_dates_keep_the_order(self):
        with pytest.raises(HTTPException):
            A.validate_report(_audit(), reference="R", report_date=D(60), link=None)             # before the appointment
        with pytest.raises(HTTPException):
            A.validate_gb(_audit(A.REPORT_RECEIVED, report_date=D(40)), placed_on=D(41), reference="GB/2")
        with pytest.raises(HTTPException):
            A.approve(_Cur(), None, _audit(A.PLACED_BEFORE_GB, report_date=D(40), gb_placed_on=D(30)), approved_on=D(31), reference="X")

    def test_the_same_day_is_fine(self):
        A.check_dates_in_order(appointed_on=D(5), report_date=D(5), gb_placed_on=D(5), approved_on=D(5), general_body_on=D(5))

    def test_nothing_is_dated_in_the_future(self):
        with pytest.raises(HTTPException):
            A.validate_appoint(auditor_name="A", appointed_on=TODAY + timedelta(days=1), appointment_reference="GB/1")
        with pytest.raises(HTTPException):
            A.validate_report(_audit(), reference="R", report_date=TODAY + timedelta(days=1), link=None)

    def test_blank_references_are_refused(self):
        for bad in ("", "   "):
            with pytest.raises(HTTPException):
                A.validate_appoint(auditor_name="A", appointed_on=D(1), appointment_reference=bad)
            with pytest.raises(HTTPException):
                A.validate_appoint(auditor_name=bad, appointed_on=D(1), appointment_reference="GB/1")
            with pytest.raises(HTTPException):
                A.validate_report(_audit(), reference=bad, report_date=D(1), link=None)

    def test_the_report_link_must_be_https(self):
        assert A.clean_link("  https://example.org/r.pdf ") == "https://example.org/r.pdf"
        assert A.clean_link("  ") is None and A.clean_link(None) is None
        for bad in ("http://example.org/r.pdf", "javascript:alert(1)", "ftp://x"):
            with pytest.raises(HTTPException):
                A.clean_link(bad)

    def test_each_status_says_what_comes_next(self):
        assert [A.next_step(s) is None for s in A.STEP_ORDER] == [False, False, False, False, True]


class TestCorrections:
    def test_a_reason_is_required_and_a_real_change(self):
        a = _audit(A.REPORT_RECEIVED, report_reference="R/1", report_date=D(40))
        with pytest.raises(HTTPException):
            A.validate_correction(a, {"auditor_name": "B"}, " ")
        with pytest.raises(HTTPException):
            A.validate_correction(a, {"auditor_name": "A. Auditor"}, "same")                     # nothing differs
        assert A.validate_correction(a, {"auditor_name": "B. Auditor", "auditor_firm": None}, "typo") == {"auditor_name": "B. Auditor", "_reason": "typo"}

    def test_only_what_has_been_recorded_can_be_corrected(self):
        with pytest.raises(HTTPException):
            A.validate_correction(_audit(), {"report_reference": "R/9"}, "typo")
        with pytest.raises(HTTPException):
            A.validate_correction(_audit(), {"report_link": "https://example.org/x"}, "late link")
        with pytest.raises(HTTPException):
            A.validate_correction(_audit(A.REPORT_RECEIVED, report_reference="R", report_date=D(1)), {"gb_reference": "GB/9"}, "typo")

    def test_dates_and_status_cannot_be_corrected(self):
        for col in ("status", "appointed_on", "report_date"):
            with pytest.raises(HTTPException):
                A.validate_correction(_audit(), {col: "x"}, "no")


class TestBayeLawClauseSeventeen:
    def test_the_parichalak_s_personal_expenditure_is_outside_the_audit(self):
        assert A.EXEMPT_PURPOSES == ("KENDRA_PARICHALAK_EXPENDITURE",)
        assert "not subject to any audit" in A.EXEMPT_NOTE

    def test_the_purpose_exists_in_the_seed(self):
        seed = (ROOT / "database/seed/12_finance/03_finance_disbursement_purpose_patch.sql").read_text()
        assert all(code in seed for code in A.EXEMPT_PURPOSES)


class TestTheDdlSaysWhatTheServiceSays:
    def test_the_status_list_is_the_same_in_the_ddl_and_the_schema(self):
        block = re.search(r"CONSTRAINT chk_finance_year_audit_status\s+CHECK \(status IN \((.*?)\)\)", DDL, re.S).group(1)
        assert tuple(re.findall(r"'([A-Z_]+)'", block)) == S.AUDIT_STATUSES
        assert (A.APPOINTED, A.REPORT_RECEIVED, A.PLACED_BEFORE_GB, A.APPROVED, A.PLACED_BEFORE_GENERAL_BODY) == S.AUDIT_STATUSES

    def test_one_audit_per_kendra_per_year(self):
        assert "uq_finance_year_audit_year_org" in DDL and "WHERE is_active = TRUE" in DDL

    def test_the_year_status_gates_nothing(self):
        import inspect
        assert "CLOSED" not in inspect.getsource(A.create) and "CLOSING" not in inspect.getsource(A.create)      # any year may be audited (owner 2026-11-26)

    def test_the_correctable_columns_exist_in_the_ddl(self):
        for col in A.CORRECTABLE:
            assert f"\n    {col} " in DDL


class TestWiring:
    @pytest.mark.parametrize("script", ["database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh",
                                        "database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"])
    def test_the_table_is_wired_into_every_script(self, script):
        assert "finance_year_audit" in (ROOT / script).read_text()

    def test_the_table_is_on_the_live_feed(self):
        from api.routers.live import LIVE_FEED_TABLES
        assert "finance_year_audit" in LIVE_FEED_TABLES
        assert "'finance_year_audit'" in (ROOT / "database/ddl/12_live_refresh/02_live_change_triggers.sql").read_text()
