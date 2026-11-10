"""
NSS ERP — DB schema + parity tests for the Finance module (Tier 12,
SOL-FIN-004, SOL-FIN-005).

Two halves:

  DB-free (run with --noconftest): the controlled-value catalogues in
  api/schemas/finance.py, the lifecycle table in api/routers/finance.py and the
  CHECK lists in database/ddl/14_finance/ are three views of ONE definition;
  these tests fail if they drift. They also check the seed patches (PAYMENT_METHOD
  incl. UPI, id sequences, FINANCE_* permissions, the live-feed whitelist).

  DB (need a build with Phase 11i): table / constraint presence, the reference
  data and RBAC delivered by the two patches, and the behaviour of the CHECK
  constraints. Every throwaway row is inserted inside its own SAVEPOINT and
  rolled back.

NEVER RUN against a database when this file was written; the DB-free half was.
"""

import re
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import pytest

from api.routers import finance as router
from api.routers.live import LIVE_FEED_TABLES
from api.schemas import finance as S

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "database" / "ddl" / "14_finance"
TABLES = [
    "financial_year", "financial_scope", "fund_master", "financial_transaction",
    "financial_receipt", "financial_payment", "financial_transfer",
]


def _ddl(name: str) -> str:
    return (DDL / name).read_text(encoding="utf-8")


def _check_values(ddl_text: str, constraint: str) -> set[str]:
    """The quoted literals inside the named CHECK constraint."""
    m = re.search(rf"CONSTRAINT {constraint}\s+CHECK\s*\((.*?)\),?\n\n", ddl_text, re.S)
    assert m, f"constraint {constraint} not found"
    return set(re.findall(r"'([A-Z_]+)'", m.group(1)))


# ═══════════════════════════════════════════════════════════════════════
# DB-free parity
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("file,constraint,values", [
    ("01_financial_year.sql", "chk_financial_year_status", S.YEAR_STATUSES),
    ("02_financial_scope.sql", "chk_financial_scope_type", S.SCOPE_TYPES),
    ("02_financial_scope.sql", "chk_financial_scope_status", S.SCOPE_STATUSES),
    ("03_fund_master.sql", "chk_fund_master_type", S.FUND_TYPES),
    ("03_fund_master.sql", "chk_fund_master_status", S.FUND_STATUSES),
    ("04_financial_transaction.sql", "chk_financial_transaction_type", S.TRANSACTION_TYPES),
    ("04_financial_transaction.sql", "chk_financial_transaction_category", S.TRANSACTION_CATEGORIES),
    ("04_financial_transaction.sql", "chk_financial_transaction_status", S.TRANSACTION_STATUSES),
    ("05_financial_receipt.sql", "chk_financial_receipt_status", S.RECEIPT_STATUSES),
    ("06_financial_payment.sql", "chk_financial_payment_status", S.PAYMENT_STATUSES),
    ("07_financial_transfer.sql", "chk_financial_transfer_status", S.TRANSFER_STATUSES),
])
def test_ddl_check_lists_match_the_api_catalogues(file, constraint, values):
    assert _check_values(_ddl(file), constraint) == set(values)


def test_every_file_declares_the_standard_audit_and_soft_delete_columns():
    for f in sorted(DDL.glob("0*.sql")):
        text = f.read_text(encoding="utf-8")
        for col in ("is_active", "created_at", "created_by_sangha_sevi_pk", "updated_at",
                    "updated_by_sangha_sevi_pk", "deleted_at", "deleted_by_sangha_sevi_pk"):
            assert col in text, f"{f.name} lacks {col}"
        assert "_soft_delete" in text, f"{f.name} lacks the soft-delete CHECK"


def test_no_hand_written_audit_actor_fk():
    """The audit-actor FKs are added by ONE catalog-driven patch (Phase 13c); never hand-written."""
    for f in DDL.glob("0*.sql"):
        text = re.sub(r"--.*", "", f.read_text(encoding="utf-8"))
        assert not re.search(r"FOREIGN KEY\s*\(\s*(created|updated|deleted)_by_sangha_sevi_pk", text), f.name


def test_lifecycle_table_only_uses_known_statuses():
    status_sets = {
        "year": S.YEAR_STATUSES, "scope": S.SCOPE_STATUSES, "fund": S.FUND_STATUSES,
        "transaction": S.TRANSACTION_STATUSES, "receipt": S.RECEIPT_STATUSES,
        "payment": S.PAYMENT_STATUSES, "transfer": S.TRANSFER_STATUSES,
    }
    assert set(router._STEPS) == set(status_sets)
    for entity, steps in router._STEPS.items():
        for (src, dst), step in steps.items():
            assert src in status_sets[entity] and dst in status_sets[entity], (entity, src, dst)
            assert step.permission in ("FINANCE_MANAGE", "FINANCE_APPROVE")


def test_every_status_is_reachable_and_terminals_have_no_exit():
    for entity, steps in router._STEPS.items():
        sources = {s for s, _ in steps}
        targets = {t for _, t in steps}
        first = {"year": "PLANNED"}.get(entity, "DRAFT")
        assert first not in targets, f"{entity}: nothing may re-enter {first}"
        for terminal in ("CLOSED", "REJECTED", "CANCELLED", "COMPLETED", "SETTLED", "INACTIVE"):
            assert terminal not in sources, f"{entity}: {terminal} must be terminal"


def test_approving_is_maker_checked_everywhere_money_moves():
    for entity, pair in (("transaction", ("PENDING_APPROVAL", "APPROVED")), ("payment", ("DRAFT", "APPROVED")),
                         ("transfer", ("PENDING_APPROVAL", "APPROVED"))):
        assert router._STEPS[entity][pair].maker_checker
        assert router._STEPS[entity][pair].permission == "FINANCE_APPROVE"


def test_income_and_expense_categories_partition_the_categories():
    assert set(S.INCOME_CATEGORIES).isdisjoint(S.EXPENSE_CATEGORIES)
    assert set(S.INCOME_CATEGORIES) | set(S.EXPENSE_CATEGORIES) == set(S.TRANSACTION_CATEGORIES)


def test_reference_data_patch_content():
    sql = (ROOT / "database/seed/12_finance/01_finance_reference_data_patch.sql").read_text(encoding="utf-8")
    for code in ("CASH", "CHEQUE", "BANK_TRANSFER", "UPI", "DEMAND_DRAFT", "OTHER"):
        assert f"'PAYMENT_METHOD', '{code}'" in sql
    for seq, prefix in (("FINANCIAL_TRANSACTION", "FTX"), ("FINANCIAL_RECEIPT", "RCT"),
                        ("FINANCIAL_PAYMENT", "PAY"), ("FINANCIAL_TRANSFER", "FTR")):
        assert f"('{seq}'," in sql and f"'{prefix}'" in sql
    assert "ON CONFLICT" in sql                                  # idempotent, never overwrites admin edits


def test_permission_patch_content():
    sql = (ROOT / "database/seed/00_bootstrap/08_finance_permissions_patch.sql").read_text(encoding="utf-8")
    for code in ("FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_APPROVE"):
        assert f"('{code}'," in sql
    grants = set(re.findall(r"\('(NSS_ERP_[A-Z_]+)', '(FINANCE_[A-Z]+)'\)", sql))
    assert ("NSS_ERP_ADMIN", "FINANCE_APPROVE") in grants
    # Least privilege: only the global administrators approve; the Auditor and Anchalika/Zilla only view.
    approvers = {r for r, p in grants if p == "FINANCE_APPROVE"}
    assert approvers == {"NSS_ERP_ADMIN", "NSS_ERP_KENDRA_ADMIN"}
    assert {r for r, p in grants if p == "FINANCE_VIEW"} >= {"NSS_ERP_AUDITOR", "NSS_ERP_ANCHALIKA_ADMIN", "NSS_ERP_ZILLA_ADMIN"}
    assert not {r for r, _ in grants} & {"NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN", "NSS_ERP_ATTENDANCE_MARKER",
                                         "NSS_ERP_ADVISORY_BOARD_ADMIN"}


def test_finance_tables_are_on_the_live_feed():
    assert set(TABLES) <= LIVE_FEED_TABLES


def test_build_scripts_run_the_finance_phase():
    for rel in ("database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "14_finance" in text and "08_finance_permissions_patch" in text and "12_finance" in text, rel
        for t in TABLES:
            assert t in text, f"{rel} does not build {t}"


def test_live_triggers_are_installed_after_the_last_finance_table_is_built():
    """
    02_live_change_triggers.sql SKIPS tables that do not exist yet, so on a fresh build it must run AFTER the
    Finance DDL (Phase 11i); otherwise those tables get no trigger or marker row until a second build.
    """
    for rel in ("database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        calls = [m.start() for m in re.finditer(r"^(?:run_sql|Invoke-Sql) \"live_change_triggers\"", text, re.M)]
        assert len(calls) == 1, f"{rel}: the trigger step must be invoked exactly once"
        for table in TABLES:
            ddl = re.search(rf"^(?:run_ddl|Invoke-Ddl) \"{table}\"", text, re.M)
            assert ddl and ddl.start() < calls[0], f"{rel}: {table} is built after the live-change triggers are installed"
        # ... and the marker TABLE itself must exist before the triggers reference it
        assert re.search(r"^(?:run_ddl|Invoke-Ddl) \"live_change_marker\"", text, re.M).start() < calls[0], rel


# ═══════════════════════════════════════════════════════════════════════
# DB tests (a build with Phase 11i + the two patches)
# ═══════════════════════════════════════════════════════════════════════

db = pytest.mark.db


def _columns(conn, table):
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nss' AND table_name=%s", (table,))
        return {r[0] for r in cur.fetchall()}


@contextmanager
def _savepoint(conn):
    name = f"sp_fin_{uuid.uuid4().hex[:10]}"
    cur = conn.cursor()
    cur.execute(f"SAVEPOINT {name}")
    try:
        yield cur
    finally:
        cur.execute(f"ROLLBACK TO SAVEPOINT {name}")


@db
@pytest.mark.integration
@pytest.mark.parametrize("table", TABLES)
def test_table_exists_with_audit_columns(write_conn, table):
    cols = _columns(write_conn, table)
    assert cols, f"nss.{table} is missing"
    assert {"is_active", "created_at", "created_by_sangha_sevi_pk", "deleted_at"} <= cols


@db
@pytest.mark.integration
def test_payment_method_is_a_master_data_fk_on_receipt_and_payment(write_conn):
    for table in ("financial_receipt", "financial_payment"):
        assert "payment_method_master_data_pk" in _columns(write_conn, table)
        assert "instrument_reference" in _columns(write_conn, table)


@db
@pytest.mark.integration
def test_payment_methods_and_sequences_are_seeded(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("""SELECT md.value_code FROM nss.master_data md
                       JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                       WHERE mc.category_code = 'PAYMENT_METHOD' AND md.is_active""")
        assert {"CASH", "UPI"} <= {r[0] for r in cur.fetchall()}
        cur.execute("SELECT sequence_code, prefix FROM nss.id_sequence_master WHERE sequence_code LIKE 'FINANCIAL\\_%'")
        assert dict(cur.fetchall()) == {"FINANCIAL_TRANSACTION": "FTX", "FINANCIAL_RECEIPT": "RCT",
                                        "FINANCIAL_PAYMENT": "PAY", "FINANCIAL_TRANSFER": "FTR"}


@db
@pytest.mark.integration
def test_permissions_are_seeded(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("SELECT permission_code FROM nss.permission_master WHERE permission_code LIKE 'FINANCE\\_%' AND is_active")
        assert {r[0] for r in cur.fetchall()} == {"FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_APPROVE"}
        cur.execute("""SELECT rm.role_code FROM nss.role_permission rp
                       JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
                       JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk
                       WHERE pm.permission_code = 'FINANCE_APPROVE' AND rp.is_active""")
        assert {r[0] for r in cur.fetchall()} == {"NSS_ERP_ADMIN", "NSS_ERP_KENDRA_ADMIN"}


@db
@pytest.mark.integration
def test_initial_financial_year_exists(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("SELECT status FROM nss.financial_year WHERE year_code = '2026-27'")
        row = cur.fetchone()
    assert row is not None


@db
@pytest.mark.integration
@pytest.mark.parametrize("sql", [
    # reversed dates
    "INSERT INTO nss.financial_year (year_code, start_date, end_date) VALUES ('T-1', '2090-04-01', '2090-03-31')",
    # unknown status
    "INSERT INTO nss.financial_year (year_code, start_date, end_date, status) VALUES ('T-2', '2090-04-01', '2091-03-31', 'BOGUS')",
    # restricted fund without a purpose is checked after the scope below
])
def test_financial_year_checks_reject(write_conn, sql):
    with _savepoint(write_conn) as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(sql)


@db
@pytest.mark.integration
def test_transaction_amount_must_be_positive_and_year_code_unique(write_conn):
    with _savepoint(write_conn) as cur:
        cur.execute("INSERT INTO nss.financial_year (year_code, start_date, end_date, status) "
                    "VALUES ('T-3', '2090-04-01', '2091-03-31', 'OPEN') RETURNING financial_year_pk")
        year = cur.fetchone()[0]
        cur.execute("INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type, status) "
                    "VALUES ('TS-3', 'x', 'EVENT', 'ACTIVE') RETURNING financial_scope_pk")
        scope = cur.fetchone()[0]
        insert = ("INSERT INTO nss.financial_transaction (transaction_reference, financial_year_pk, financial_scope_pk, "
                  "transaction_type, transaction_category, amount, transaction_date) "
                  "VALUES (%s, %s, %s, 'INCOME', 'GRANT', %s, '2090-05-01')")
        cur.execute("SAVEPOINT a")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(insert, ("T-REF-0", year, scope, 0))
        cur.execute("ROLLBACK TO SAVEPOINT a")
        cur.execute(insert, ("T-REF-1", year, scope, 10))
        cur.execute("SAVEPOINT b")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(insert, ("T-REF-1", year, scope, 10))
        cur.execute("ROLLBACK TO SAVEPOINT b")
        cur.execute("SAVEPOINT c")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute("INSERT INTO nss.financial_year (year_code, start_date, end_date) VALUES ('T-3', '2092-04-01', '2093-03-31')")
        cur.execute("ROLLBACK TO SAVEPOINT c")


@db
@pytest.mark.integration
def test_scope_restricted_fund_transfer_and_receipt_checks(write_conn):
    with _savepoint(write_conn) as cur:
        cur.execute("INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type) VALUES ('TS-4', 'x', 'EVENT') RETURNING financial_scope_pk")
        scope = cur.fetchone()[0]
        cur.execute("INSERT INTO nss.financial_year (year_code, start_date, end_date) VALUES ('T-4', '2090-04-01', '2091-03-31') RETURNING financial_year_pk")
        year = cur.fetchone()[0]
        checks = [
            ("INSERT INTO nss.fund_master (fund_code, fund_name, fund_type, financial_scope_pk, is_restricted) "
             "VALUES ('TF', 'x', 'GRANT', %s, TRUE)", (scope,)),                                  # restricted, no purpose
            ("INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type, parent_scope_pk) "
             "SELECT 'TS-5', 'x', 'EVENT', financial_scope_pk FROM nss.financial_scope WHERE scope_code = 'TS-4'", ()),  # valid: control
            ("INSERT INTO nss.financial_transfer (transfer_reference, financial_year_pk, source_scope_pk, destination_scope_pk, "
             "amount, transfer_date, purpose) VALUES ('TT-1', %s, %s, %s, 5, '2090-05-01', 'x')", (year, scope, scope)),  # same scope
        ]
        expected = [psycopg2.errors.CheckViolation, None, psycopg2.errors.CheckViolation]
        for i, ((sql, params), exc) in enumerate(zip(checks, expected)):
            cur.execute(f"SAVEPOINT s{i}")
            if exc is None:
                cur.execute(sql, params)
            else:
                with pytest.raises(exc):
                    cur.execute(sql, params)
            cur.execute(f"ROLLBACK TO SAVEPOINT s{i}")
