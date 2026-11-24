"""
Kendra annual budget (FIN-BR-041) — the parts that need no database (run with ``--noconftest``):

  * the pure rules of api/services/finance_budget.py: what comes next, date order, no future dates, step guards, totals;
  * each guard fires BEFORE any SQL is sent (a stand-in cursor that fails on use);
  * the DDL CHECKs say what the service says (statuses, the order of the facts), the schema constants match the DDL;
  * the two tables are wired into all three build scripts, both validate scripts, the live-refresh whitelist and its trigger list;
  * the route table: ten routes, each behind a Finance permission, writes behind FINANCE_MANAGE, nothing commits.

The end-to-end behaviour is in tests/api/test_finance_budget.py (never run against a database when written); the SQL itself was
exercised in a throwaway single-user PostgreSQL 18 (a recording cursor captured the service's own queries and ran them).
"""

import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.schemas import finance as S
from api.services import finance_budget as B

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "database" / "ddl" / "14_finance"
BUDGET_DDL = (DDL / "21_finance_budget.sql").read_text(encoding="utf-8")
LINE_DDL = (DDL / "22_finance_budget_line.sql").read_text(encoding="utf-8")
PATCH_DDL = (DDL / "23_finance_budget_letters_patch.sql").read_text(encoding="utf-8")
TODAY = date(2026, 11, 22)


class NoSql:
    """A cursor that fails the test if a guard lets a statement through."""

    def execute(self, *a, **k):
        raise AssertionError("SQL was sent although the rule should have refused first")

    fetchone = fetchall = execute


def budget(status="DRAFT", lines=1, **over):
    row = {"finance_budget_pk": "b1", "organization_pk": "k1", "status": status, "line_count": lines, "referred_on": None,
           "advisory_views_date": None, "advisory_reference": None}
    row.update(over)
    return row


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises(HTTPException) as e:
        fn(*args, **kwargs)
    assert e.value.status_code == 422
    return e.value.detail


# ═══════════════════════════════════════════════════════════════════════
# Pure rules
# ═══════════════════════════════════════════════════════════════════════

class TestWhatComesNext:
    def test_each_status_names_its_next_step(self):
        assert "Add the budget lines" in B.next_step("DRAFT", 0)
        assert B.next_step("DRAFT", 3) == "Refer the draft to the Advisory Board."
        assert "Advisory Board's considered views" in B.next_step("REFERRED", 3)
        assert "resolution" in B.next_step("VIEWS_RECEIVED", 3)
        assert B.next_step("PASSED", 3) is None

    def test_a_line_can_change_in_any_status_but_past_draft_it_needs_a_reason(self):
        assert [B.changes_need_reason(s) for s in S.BUDGET_STATUSES] == [False, True, True, True]


class TestDates:
    def test_no_future_date(self):
        B.check_not_future(TODAY, "x", today=TODAY)
        assert "future" in refused(B.check_not_future, TODAY + timedelta(days=1), "The referral date", today=TODAY)

    def test_the_facts_keep_their_order(self):
        d = lambda n: TODAY + timedelta(days=n)
        B.check_dates_in_order(referred_on=d(0), views_date=d(0), resolution_date=d(0))              # the same day is fine
        B.check_dates_in_order(referred_on=d(0), views_date=d(3), resolution_date=d(5))
        assert "before the draft was referred" in refused(B.check_dates_in_order, referred_on=d(5), views_date=d(4), resolution_date=None)
        assert "before the Advisory Board's views" in refused(B.check_dates_in_order, referred_on=d(0), views_date=d(4), resolution_date=d(3))

    def test_missing_dates_are_not_compared(self):
        B.check_dates_in_order(referred_on=None, views_date=None, resolution_date=None)
        B.check_dates_in_order(referred_on=TODAY, views_date=None, resolution_date=TODAY)


class TestStepGuards:
    def test_require_status_says_where_the_budget_is(self):
        assert "PASSED" in refused(B.require_status, budget("PASSED"), ("DRAFT",), "changing the lines")
        B.require_status(budget("DRAFT"), ("DRAFT",), "changing the lines")

    def test_blank_text_is_refused_and_trimmed(self):
        assert B.require_blank("  AB/7 ", "x") == "AB/7"
        assert "cannot be blank" in refused(B.require_blank, "   ", "The reference")
        assert "cannot be blank" in refused(B.require_blank, None, "The reference")

    @pytest.mark.parametrize("call", [
        lambda: B.refer(NoSql(), "a", budget("REFERRED"), TODAY, "l1"),                                                  # already referred
        lambda: B.refer(NoSql(), "a", budget("DRAFT", lines=0), TODAY, "l1"),                                            # nothing to refer
        lambda: B.refer(NoSql(), "a", budget("DRAFT"), date.today() + timedelta(days=2), "l1"),                          # not yet happened
        lambda: B.record_views(NoSql(), "a", budget("DRAFT"), reference="x", views_date=TODAY, summary="y", letter_pk="l2"),       # not referred
        lambda: B.record_views(NoSql(), "a", budget("VIEWS_RECEIVED"), reference="x", views_date=TODAY, summary="y", letter_pk="l2"),
        lambda: B.record_views(NoSql(), "a", budget("REFERRED", referred_on=date.today()), reference=" ", views_date=date.today(), summary="y", letter_pk="l2"),
        lambda: B.record_views(NoSql(), "a", budget("REFERRED", referred_on=date.today()), reference="x", views_date=date.today(), summary=" ", letter_pk="l2"),
        lambda: B.record_views(NoSql(), "a", budget("REFERRED", referred_on=date.today()), reference="x",
                               views_date=date.today() - timedelta(days=1), summary="y", letter_pk="l2"),     # before the referral
        lambda: B.pass_budget(NoSql(), "a", budget("DRAFT"), reference="GB", resolution_date=TODAY),               # no views on file
        lambda: B.pass_budget(NoSql(), "a", budget("REFERRED"), reference="GB", resolution_date=TODAY),
        lambda: B.pass_budget(NoSql(), "a", budget("PASSED"), reference="GB", resolution_date=TODAY),
        lambda: B.pass_budget(NoSql(), "a", budget("VIEWS_RECEIVED", advisory_views_date=date.today()), reference=" ", resolution_date=date.today()),
        lambda: B.pass_budget(NoSql(), "a", budget("VIEWS_RECEIVED", advisory_views_date=date.today()), reference="GB",
                              resolution_date=date.today() - timedelta(days=1)),                                  # before the views
        lambda: B.reopen(NoSql(), "a", budget("DRAFT")),
        lambda: B.reopen(NoSql(), "a", budget("PASSED")),                                                          # a passed budget is final
        lambda: B.put_line(NoSql(), "a", budget("REFERRED"), head_pk="h", amount=Decimal(1), notes=None),          # past draft: no reason given
        lambda: B.put_line(NoSql(), "a", budget("PASSED"), head_pk="h", amount=Decimal(1), notes=None, reason="   "),
        lambda: B.remove_line(NoSql(), "a", budget("PASSED"), "l"),
    ])
    def test_a_rule_refuses_before_any_sql_is_sent(self, call):
        with pytest.raises(HTTPException) as e:
            call()
        assert e.value.status_code == 422


class TestTotals:
    def test_planned_and_actual_with_unbudgeted_money_counted_as_actual(self):
        lines = [{"direction": "INCOME", "amount": Decimal(8000), "actual": Decimal(5000)},
                 {"direction": "EXPENSE", "amount": Decimal(2000), "actual": Decimal(2100)}]
        flagged = [{"direction": "EXPENSE", "actual": Decimal(300)}]
        t = B.totals(lines, flagged)
        assert (t["planned_income"], t["planned_expense"], t["planned_surplus"]) == (8000, 2000, 6000)
        assert (t["actual_income"], t["actual_expense"]) == (5000, 2400)

    def test_an_empty_budget_totals_to_zero(self):
        assert set(B.totals([], []).values()) == {Decimal(0)}


# ═══════════════════════════════════════════════════════════════════════
# The DDL says what the service says
# ═══════════════════════════════════════════════════════════════════════

def _check(sql: str, name: str) -> str:
    return re.search(rf"CONSTRAINT {name}\s+CHECK\s*\((.*?)\),?\n\n", sql, re.S).group(1)


class TestSchemaParity:
    def test_the_status_list_is_the_same_in_the_ddl_and_the_schema(self):
        listed = re.search(r"status IN \(([^)]*)\)", _check(BUDGET_DDL, "chk_finance_budget_status")).group(1)
        assert tuple(re.findall(r"'([A-Z_]+)'", listed)) == S.BUDGET_STATUSES
        assert (B.DRAFT, B.REFERRED, B.VIEWS_RECEIVED, B.PASSED) == S.BUDGET_STATUSES

    def test_each_step_s_facts_are_enforced_by_the_database_too(self):
        assert "(status = 'DRAFT') = (referred_on IS NULL)" in " ".join(BUDGET_DDL.split())
        views = " ".join(_check(BUDGET_DDL, "chk_finance_budget_views").split())
        assert "status IN ('VIEWS_RECEIVED', 'PASSED')" in views and "advisory_reference IS NOT NULL" in views and "advisory_views_summary IS NOT NULL" in views
        resolution = " ".join(_check(BUDGET_DDL, "chk_finance_budget_resolution").split())
        assert "status = 'PASSED'" in resolution and "resolution_reference IS NOT NULL" in resolution and "resolution_date IS NOT NULL" in resolution

    def test_the_date_order_is_enforced_by_the_database_too(self):
        order = " ".join(_check(BUDGET_DDL, "chk_finance_budget_order").split())
        assert "advisory_views_date >= referred_on" in order and "resolution_date >= advisory_views_date" in order

    def test_one_budget_per_year_per_organization_and_one_line_per_head(self):
        assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_budget_year_org\s+ON nss\.finance_budget \(financial_year_pk, organization_pk\) WHERE is_active = TRUE", BUDGET_DDL)
        assert re.search(r"uq_finance_budget_line_head\s+ON nss\.finance_budget_line \(finance_budget_pk, finance_head_pk\) WHERE is_active = TRUE", LINE_DDL)

    def test_a_line_is_a_positive_amount(self):
        assert "CHECK (amount > 0)" in LINE_DDL

    @pytest.mark.parametrize("sql", [BUDGET_DDL, LINE_DDL], ids=["finance_budget", "finance_budget_line"])
    def test_the_audit_columns_and_soft_delete_are_there(self, sql):
        for column in ("is_active", "created_at", "created_by_sangha_sevi_pk", "updated_at", "updated_by_sangha_sevi_pk",
                       "deleted_at", "deleted_by_sangha_sevi_pk"):
            assert re.search(rf"^\s+{column} ", sql, re.M), column
        assert "soft_delete" in sql and "CREATE TABLE IF NOT EXISTS" in sql

    def test_no_trailing_alter_safety_net(self):
        for sql in (BUDGET_DDL, LINE_DDL):
            assert not re.search(r"^\s*ALTER TABLE", sql, re.M)             # run_ddl skips the whole file for an existing table


# ═══════════════════════════════════════════════════════════════════════
# Wiring
# ═══════════════════════════════════════════════════════════════════════

TABLES = ("finance_budget", "finance_budget_line")


class TestWiring:
    @pytest.mark.parametrize("script", ["database/scripts/02_build.sh", "render_build.sh"])
    def test_the_shell_builds_create_both_tables_in_order(self, script):
        text = (ROOT / script).read_text(encoding="utf-8")
        budget_at = text.index("21_finance_budget.sql")
        assert budget_at < text.index("22_finance_budget_line.sql")                      # the line table needs the budget table
        for t in TABLES:
            assert f'run_ddl "{t}" "{t}"' in text
        assert text.index("10_upi_payment_request.sql") < budget_at                       # the year and head tables exist first
        assert text.index("05_finance_head.sql") < budget_at

    def test_the_powershell_build_does_the_same(self):
        text = (ROOT / "database/scripts/02_build.ps1").read_text(encoding="utf-8")
        assert text.index("21_finance_budget.sql") < text.index("22_finance_budget_line.sql")
        for t in TABLES:
            assert f'Invoke-Ddl "{t}" "{t}"' in text

    @pytest.mark.parametrize("script,check", [("database/scripts/03_validate.sh", "check_table_exists"), ("database/scripts/03_validate.ps1", "Check-TableExists")])
    def test_both_validate_scripts_check_the_tables(self, script, check):
        text = (ROOT / script).read_text(encoding="utf-8")
        for t in TABLES:
            assert f'{check} "{t}"' in text

    def test_the_live_feed_watches_both_tables_in_the_whitelist_and_the_trigger_list(self):
        from api.routers.live import LIVE_FEED_TABLES

        triggers = (ROOT / "database/ddl/12_live_refresh/02_live_change_triggers.sql").read_text(encoding="utf-8")
        for t in TABLES:
            assert t in LIVE_FEED_TABLES and f"'{t}'" in triggers

    def test_the_schema_test_lists_the_two_files(self):
        text = (ROOT / "tests/db/test_finance_schema.py").read_text(encoding="utf-8")
        assert '"21_finance_budget.sql"' in text and '"22_finance_budget_line.sql"' in text


# ═══════════════════════════════════════════════════════════════════════
# The routes
# ═══════════════════════════════════════════════════════════════════════

EXPECTED = {
    ("GET", "/api/v1/finance/budgets"), ("POST", "/api/v1/finance/budgets"), ("GET", "/api/v1/finance/budgets/{budget_pk}"),
    ("PUT", "/api/v1/finance/budgets/{budget_pk}/lines"), ("DELETE", "/api/v1/finance/budgets/{budget_pk}/lines/{line_pk}"),
    ("POST", "/api/v1/finance/budgets/{budget_pk}/refer"), ("POST", "/api/v1/finance/budgets/{budget_pk}/advisory-views"),
    ("POST", "/api/v1/finance/budgets/{budget_pk}/pass"), ("POST", "/api/v1/finance/budgets/{budget_pk}/reopen"),
    ("POST", "/api/v1/finance/budgets/{budget_pk}/correct"),
}


class TestRoutes:
    def test_the_ten_routes_and_only_those(self):
        from api.routers.finance_budget import router

        assert {(m, r.path) for r in router.routes for m in r.methods if m != "HEAD"} == EXPECTED
        assert len(router.routes) == 10

    def test_the_app_serves_them_once_each(self):
        from api.main import app

        served = [(m, r.path) for r in app.routes for m in getattr(r, "methods", ()) if m != "HEAD" and "/finance/budgets" in getattr(r, "path", "")]
        assert sorted(served) == sorted(EXPECTED)

    def test_every_route_needs_a_finance_permission_and_every_write_the_manage_one(self):
        from api.routers import finance as F
        from api.routers.finance_budget import router

        for r in router.routes:
            names = {getattr(d.call, "__name__", "") for d in r.dependant.dependencies}
            assert "_check" in names, f"{r.path} has no permission dependency"
        # reads use the VIEW dependency object, writes the MANAGE one (the same objects finance.py defines)
        calls = {(m, r.path): [d.call for d in r.dependant.dependencies] for r in router.routes for m in r.methods if m != "HEAD"}
        for key, deps in calls.items():
            expected = F._VIEW if key[0] == "GET" else F._MANAGE
            assert expected in deps, key

    def test_the_router_does_not_commit_and_builds_no_sql_from_input(self):
        text = (ROOT / "api/routers/finance_budget.py").read_text(encoding="utf-8")
        service = (ROOT / "api/services/finance_budget.py").read_text(encoding="utf-8")
        assert ".commit(" not in text + service and ".rollback(" not in text + service
        assert not re.search(r"execute\(\s*f[\"'][^\"']*\{(?!_BUDGET|where_sql|_ACTUAL|', '\.join|', '\.join\(sets\))", service)

    def test_every_write_is_audited(self):
        text = (ROOT / "api/routers/finance_budget.py").read_text(encoding="utf-8")
        writes = len(re.findall(r"@router\.(?:post|put|delete)\(", text))
        assert writes == 8 and text.count("F._audit(") == writes


# ═══════════════════════════════════════════════════════════════════════
# The letters filed in Correspondence (owner request 2026-11-22)
# ═══════════════════════════════════════════════════════════════════════

class Recorder:
    """Records the one UPDATE a step sends (the rules have already passed)."""

    def __init__(self):
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), list(params)))


def _updated_columns(rec: Recorder) -> dict:
    sql, params = rec.statements[-1]
    cols = re.findall(r"(\w+) = %s", sql.split(" WHERE ")[0])
    return dict(zip(cols, params))


class TestLetterText:
    LINES = [{"direction": "INCOME", "head_name": "Pranami", "amount": Decimal("8000")},
             {"direction": "EXPENSE", "head_name": "Puja", "amount": Decimal("2000.5")},
             {"direction": "EXPENSE", "head_name": "Travel", "amount": Decimal("300")}]

    def test_the_referral_letter_lists_every_line_and_the_totals(self):
        text = B.referral_remarks(self.LINES)
        assert "Planned income: Pranami 8,000.00. Total 8,000.00." in text
        assert "Planned spending: Puja 2,000.50; Travel 300.00. Total 2,300.50." in text

    def test_a_budget_with_only_one_side_still_reads_properly(self):
        assert B.referral_remarks(self.LINES[:1]).startswith("Planned income:") and "spending" not in B.referral_remarks(self.LINES[:1])

    def test_a_long_budget_is_cut_to_what_a_register_remark_can_hold(self):
        many = [{"direction": "EXPENSE", "head_name": f"Head number {i} with a long name", "amount": Decimal(i + 1)} for i in range(200)]
        text = B.referral_remarks(many)
        assert len(text) <= B.LETTER_REMARKS_MAX and text.endswith("…")

    def test_the_subjects_name_the_year_and_fit_the_subject_column(self):
        for subject in (B.referral_subject("2026-27"), B.views_subject("2026-27")):
            assert "2026-27" in subject and len(subject) <= 255
        assert "Advisory Board" in B.referral_subject("2026-27") and "views" in B.views_subject("2026-27")


class TestStepsStoreTheirLetters:
    def test_referring_stores_the_letter_and_the_date(self):
        rec = Recorder()
        B.refer(rec, "actor", budget("DRAFT"), TODAY - timedelta(days=1), "letter-1")
        assert _updated_columns(rec) == {"status": "REFERRED", "referred_on": TODAY - timedelta(days=1), "referral_correspondence_pk": "letter-1",
                                         "updated_by_sangha_sevi_pk": "actor"}

    def test_the_views_store_the_replys_number_and_letter(self):
        rec = Recorder()
        B.record_views(rec, "actor", budget("REFERRED", referred_on=TODAY - timedelta(days=3)), reference=" NSSAB/OUT/2026-27/001 ",
                       views_date=TODAY - timedelta(days=1), summary=" Supports it ", letter_pk="letter-2")
        cols = _updated_columns(rec)
        assert cols["advisory_reference"] == "NSSAB/OUT/2026-27/001" and cols["views_correspondence_pk"] == "letter-2"
        assert cols["advisory_views_summary"] == "Supports it" and cols["status"] == "VIEWS_RECEIVED"

    def test_sending_it_back_clears_the_links_but_nothing_in_correspondence_is_touched(self):
        rec = Recorder()
        B.reopen(rec, "actor", budget("VIEWS_RECEIVED"))
        cols = _updated_columns(rec)
        assert cols["referral_correspondence_pk"] is None and cols["views_correspondence_pk"] is None and cols["status"] == "DRAFT"
        assert len(rec.statements) == 1 and "correspondence" not in rec.statements[0][0].split(" SET ")[0]      # only finance_budget is written

    def test_validation_runs_without_any_sql_so_a_refused_step_files_no_letter(self):
        B.validate_refer(budget("DRAFT"), TODAY)
        assert refused(B.validate_refer, budget("DRAFT", lines=0), TODAY)
        assert refused(B.validate_refer, budget("REFERRED"), TODAY)
        assert B.validate_views(budget("REFERRED", referred_on=TODAY - timedelta(days=2)), TODAY - timedelta(days=1), "  said yes ") == "said yes"
        assert refused(B.validate_views, budget("DRAFT"), TODAY, "x")
        assert refused(B.validate_views, budget("REFERRED", referred_on=TODAY), TODAY - timedelta(days=1), "x")
        assert refused(B.validate_views, budget("REFERRED", referred_on=TODAY - timedelta(days=2)), TODAY - timedelta(days=1), "  ")


class TestLetterWiring:
    def test_nobody_types_the_advisory_reference_any_more(self):
        assert "advisory_reference" not in S.BudgetViewsWrite.model_fields
        assert set(S.BudgetViewsWrite.model_fields) == {"advisory_views_date", "advisory_views_summary"}
        assert S.BudgetViewsWrite(advisory_views_summary="ok").advisory_views_date is None          # today, decided by the server
        assert S.BudgetReferWrite().referred_on is None

    def test_the_response_carries_the_letter_numbers(self):
        for field in ("referral_correspondence_pk", "referral_reference", "referral_inward_reference", "advisory_reference",
                      "views_correspondence_pk", "views_inward_reference"):
            assert field in S.BudgetResponse.model_fields, field

    def test_the_ddl_and_the_patch_carry_the_two_letter_links(self):
        for column in ("referral_correspondence_pk", "views_correspondence_pk"):
            assert re.search(rf"^\s+{column} UUID NULL", BUDGET_DDL, re.M), column
            assert f"ADD COLUMN IF NOT EXISTS {column} UUID NULL" in PATCH_DDL
        for fk in ("fk_finance_budget_referral_letter", "fk_finance_budget_views_letter"):
            assert f"CONSTRAINT {fk}" in BUDGET_DDL and fk in PATCH_DDL and "REFERENCES nss.correspondence (correspondence_pk)" in BUDGET_DDL
        assert "IF NOT EXISTS (SELECT 1 FROM pg_constraint" in PATCH_DDL                     # the constraints are idempotent too

    @pytest.mark.parametrize("script,needle", [("database/scripts/02_build.sh", 'run_sql "finance budget letters patch"'),
                                                ("render_build.sh", 'run_sql "finance budget letters patch"'),
                                                ("database/scripts/02_build.ps1", 'Invoke-Sql "finance budget letters patch"')])
    def test_the_patch_runs_on_every_build_after_the_budget_tables(self, script, needle):
        text = (ROOT / script).read_text(encoding="utf-8")
        assert needle in text and "23_finance_budget_letters_patch.sql" in text
        assert text.index("22_finance_budget_line.sql") < text.index("23_finance_budget_letters_patch.sql")
        assert text.index("09_correspondence") < text.index("23_finance_budget_letters_patch.sql")        # the Correspondence tables exist first

    def test_the_budget_files_its_letters_through_the_one_correspondence_function(self):
        router = (ROOT / "api/routers/finance_budget.py").read_text(encoding="utf-8")
        corr = (ROOT / "api/routers/correspondence.py").read_text(encoding="utf-8")
        assert router.count("C.register_correspondence(") == 1 and "check_scope=False" in router
        assert "INSERT INTO nss.correspondence" not in router                       # no second copy of the registration SQL
        assert "def register_correspondence(cur, user, body: CorrespondenceCreate, *, check_scope: bool = True)" in corr
        assert corr.count("register_correspondence(cur, user, body)") == 1          # POST /correspondence calls it too
        assert corr.count("if check_scope:") == 2                                   # the register's scope and the original's scope

    def test_the_budget_never_files_a_letter_before_its_own_rules_have_passed(self):
        router = (ROOT / "api/routers/finance_budget.py").read_text(encoding="utf-8")
        refer = router.split("def refer_budget", 1)[1].split("@router.post", 1)[0]
        views = router.split("def record_advisory_views", 1)[1].split("@router.post", 1)[0]
        assert refer.index("B.validate_refer(") < refer.index("_file_letter(") < refer.index("B.refer(")
        assert views.index("B.validate_views(") < views.index("_file_letter(") < views.index("B.record_views(")

    def test_the_replys_letter_belongs_to_the_advisory_boards_register_and_is_threaded_to_its_copy(self):
        router = (ROOT / "api/routers/finance_budget.py").read_text(encoding="utf-8")
        views = router.split("def record_advisory_views", 1)[1].split("@router.post", 1)[0]
        assert "register_pk=board_pk, sender_pk=board_pk, recipient_pk=budget[\"organization_pk\"]" in views
        assert "in_reply_to=B.inward_copy_pk(cur, budget[\"referral_correspondence_pk\"], board_pk)" in views

    def test_the_letter_body_is_a_valid_correspondence_create(self):
        from api.schemas.correspondence import CorrespondenceCreate

        body = CorrespondenceCreate(
            register_organization_pk="00000000-0000-0000-0000-000000000001", direction="OUTWARD", correspondence_date=date.today(),
            received_or_sent_date=date.today(), subject=B.referral_subject("2026-27"), remarks=B.referral_remarks(TestLetterText.LINES),
            sender_type="ORGANIZATION", sender_organization_pk="00000000-0000-0000-0000-000000000001",
            recipient_type="ORGANIZATION", recipient_organization_pk="00000000-0000-0000-0000-000000000002", medium="HAND_DELIVERY")
        assert body.direction == "OUTWARD"


class TestEditAlways:
    """Owner 2026-11-22: "edit always" - a line can change in every status; past DRAFT the change must say why."""

    def test_a_draft_needs_no_reason(self):
        assert B.require_reason(budget("DRAFT"), None) is None
        assert B.require_reason(budget("DRAFT"), "  tidy  ") == "tidy"

    @pytest.mark.parametrize("state", ["REFERRED", "VIEWS_RECEIVED", "PASSED"])
    def test_past_draft_a_reason_is_required_and_trimmed(self, state):
        assert "say why" in refused(B.require_reason, budget(state), None)
        assert "say why" in refused(B.require_reason, budget(state), "   ")
        assert B.require_reason(budget(state), "  Satsiksha line raised  ") == "Satsiksha line raised"

    def test_a_locked_status_no_longer_refuses_the_change_itself(self):
        """With a reason, put_line gets as far as the database (the stand-in cursor fails the moment it is used)."""
        for state in ("REFERRED", "VIEWS_RECEIVED", "PASSED"):
            with pytest.raises(AssertionError, match="SQL was sent"):
                B.put_line(NoSql(), "a", budget(state), head_pk="h", amount=Decimal(1), notes=None, reason="why")
            with pytest.raises(AssertionError, match="SQL was sent"):
                B.remove_line(NoSql(), "a", budget(state), "l", "why")

    def test_the_response_says_when_a_reason_is_needed(self):
        assert "changes_need_reason" in S.BudgetResponse.model_fields and "lines_editable" not in S.BudgetResponse.model_fields
        assert B.present(budget("DRAFT"))["changes_need_reason"] is False and B.present(budget("PASSED"))["changes_need_reason"] is True

    def test_the_line_body_and_the_delete_accept_a_reason(self):
        assert "reason" in S.BudgetLineWrite.model_fields
        text = (ROOT / "api/routers/finance_budget.py").read_text(encoding="utf-8")
        assert "reason: str | None = Query(None, max_length=500" in text
        put = text.split("def put_budget_line", 1)[1].split("@router.delete", 1)[0]
        assert '"amount_before"' in put and '"reason": reason' in put                      # the audit trail keeps old amount, status and reason
