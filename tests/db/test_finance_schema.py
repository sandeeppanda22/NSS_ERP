"""
NSS ERP — DB schema + parity tests for the Finance module (Tier 12,
SOL-FIN-004, SOL-FIN-005, owner decisions 2026-11-10: customizable finance heads,
per-Sangha receiving accounts, UPI collection).

Two halves:

  DB-free (run with --noconftest): the controlled-value catalogues in
  api/schemas/finance.py, the lifecycle table in api/routers/finance.py and the
  CHECK lists in database/ddl/14_finance/ are three views of ONE definition;
  these tests fail if they drift. They also pin the seed / structure patches, the
  build order in all three build scripts, the validate scripts, the live-feed
  wiring, and two security properties of the SCHEMA itself: no Finance table can
  hold a secret, and no table stores a full account number.

  DB (need a build with Phase 11i + the patches): table / constraint presence, the
  reference data, RBAC and Kendra head templates delivered by the patches, and the
  behaviour of the CHECK / UNIQUE constraints. Every throwaway row is inserted
  inside its own SAVEPOINT and rolled back.

NEVER RUN against a database when this file was written; the DB-free half was, and the same
DDL + patches were applied (fresh build, idempotent re-run, and an upgrade of an OLD-shape database
holding rows) in a throwaway single-user PostgreSQL 18.
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
SEED = ROOT / "database" / "seed" / "12_finance"

# (file, table) in BUILD / dependency order - the order the build scripts run them.
TABLE_FILES = [
    ("01_financial_year.sql", "financial_year"),
    ("02_financial_scope.sql", "financial_scope"),
    ("03_fund_master.sql", "fund_master"),
    ("04_financial_account.sql", "financial_account"),
    ("05_finance_head.sql", "finance_head"),
    ("06_financial_transaction.sql", "financial_transaction"),
    ("07_financial_receipt.sql", "financial_receipt"),
    ("08_financial_payment.sql", "financial_payment"),
    ("09_financial_transfer.sql", "financial_transfer"),
    ("10_upi_payment_request.sql", "upi_payment_request"),
    ("11_finance_gateway_event.sql", "finance_gateway_event"),
    ("13_finance_disbursement_authority.sql", "finance_disbursement_authority"),
]
TABLES = [t for _, t in TABLE_FILES]
APPEND_ONLY = {"finance_gateway_event"}                  # an event log: no soft delete, no audit-actor columns
AUDITED_FILES = [f for f, t in TABLE_FILES if t not in APPEND_ONLY]
FEED_TABLES = [t for t in TABLES if t not in APPEND_ONLY]  # the gateway log carries payer details: never on the live feed
BUILD_SCRIPTS = ("database/scripts/02_build.sh", "database/scripts/02_build.ps1", "render_build.sh")

OLD_CATEGORY_CODES = {          # the 12 former fixed transaction categories, kept verbatim as the Kendra templates
    "MEMBERSHIP_SUBSCRIPTION", "PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND", "DONATION_GENERAL",
    "DONATION_SPECIFIC_PURPOSE", "GRANT", "PUBLICATION_INCOME", "PROPERTY_INCOME", "MISCELLANEOUS_INCOME",
    "EXPENSE_GENERAL", "EXPENSE_RESTRICTED",
}


def _ddl(name: str) -> str:
    return (DDL / name).read_text(encoding="utf-8")


def _script(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _check_values(ddl_text: str, constraint: str) -> set[str]:
    """The quoted literals inside the named CHECK constraint."""
    # the constraint ends at "),<blank line>" or, when it is the table's last one, at ")<newline>);"
    m = re.search(rf"CONSTRAINT {constraint}\s+CHECK\s*\((.*?)\)(?:,\n\n|\n\);)", ddl_text, re.S)
    assert m, f"constraint {constraint} not found"
    return set(re.findall(r"'([A-Z_]+)'", m.group(1)))


def _code_only(ddl_text: str) -> str:
    return re.sub(r"--.*", "", ddl_text)


# ═══════════════════════════════════════════════════════════════════════
# DB-free parity: DDL <-> API catalogues <-> lifecycle table
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("file,constraint,values", [
    ("01_financial_year.sql", "chk_financial_year_status", S.YEAR_STATUSES),
    ("02_financial_scope.sql", "chk_financial_scope_type", S.SCOPE_TYPES),
    ("02_financial_scope.sql", "chk_financial_scope_status", S.SCOPE_STATUSES),
    ("03_fund_master.sql", "chk_fund_master_type", S.FUND_TYPES),
    ("03_fund_master.sql", "chk_fund_master_status", S.FUND_STATUSES),
    ("04_financial_account.sql", "chk_financial_account_type", S.ACCOUNT_TYPES),
    ("04_financial_account.sql", "chk_financial_account_status", S.ACCOUNT_STATUSES),
    ("05_finance_head.sql", "chk_finance_head_direction", S.HEAD_DIRECTIONS),
    ("05_finance_head.sql", "chk_finance_head_status", S.HEAD_STATUSES),
    ("05_finance_head.sql", "chk_finance_head_fund_type", S.FUND_TYPES),
    ("06_financial_transaction.sql", "chk_financial_transaction_type", S.TRANSACTION_TYPES),
    ("06_financial_transaction.sql", "chk_financial_transaction_status", S.TRANSACTION_STATUSES),
    ("07_financial_receipt.sql", "chk_financial_receipt_status", S.RECEIPT_STATUSES),
    ("08_financial_payment.sql", "chk_financial_payment_status", S.PAYMENT_STATUSES),
    ("09_financial_transfer.sql", "chk_financial_transfer_status", S.TRANSFER_STATUSES),
    ("10_upi_payment_request.sql", "chk_upi_payment_request_status", S.PAYMENT_REQUEST_STATUSES),
    ("11_finance_gateway_event.sql", "chk_finance_gateway_event_outcome", S.GATEWAY_EVENT_OUTCOMES),
])
def test_ddl_check_lists_match_the_api_catalogues(file, constraint, values):
    assert _check_values(_ddl(file), constraint) == set(values)


def test_there_is_no_fixed_transaction_category_list_any_more():
    """Heads are data: the category CHECK is gone from the DDL, dropped by the patch, and absent from the API."""
    assert "chk_financial_transaction_category" not in _code_only(_ddl("06_financial_transaction.sql"))
    assert "DROP CONSTRAINT IF EXISTS chk_financial_transaction_category" in _ddl("12_finance_heads_patch.sql")
    for name in ("INCOME_CATEGORIES", "EXPENSE_CATEGORIES", "TRANSACTION_CATEGORIES", "PRANAMI_CATEGORIES"):
        assert not hasattr(S, name), name


@pytest.mark.parametrize("file", AUDITED_FILES)
def test_every_table_declares_the_standard_audit_and_soft_delete_columns(file):
    text = _ddl(file)
    for col in ("is_active", "created_at", "created_by_sangha_sevi_pk", "updated_at",
                "updated_by_sangha_sevi_pk", "deleted_at", "deleted_by_sangha_sevi_pk"):
        assert col in text, f"{file} lacks {col}"
    assert "_soft_delete" in text, f"{file} lacks the soft-delete CHECK"


def test_the_gateway_event_log_is_append_only():
    text = _code_only(_ddl("11_finance_gateway_event.sql"))
    assert "is_active" not in text and "deleted_at" not in text and "_by_sangha_sevi_pk" not in text
    # idempotency: a SIGNED provider event id is unique; a forged one can never block a real one
    assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_gateway_event_signed\s+ON nss\.finance_gateway_event \(provider, event_id\)\s+WHERE signature_valid = TRUE", text)


def test_no_hand_written_audit_actor_fk():
    """The audit-actor FKs are added by ONE catalog-driven patch (Phase 13c); never hand-written."""
    for file, _ in TABLE_FILES:
        assert not re.search(r"FOREIGN KEY\s*\(\s*(created|updated|deleted)_by_sangha_sevi_pk", _code_only(_ddl(file))), file


def test_no_finance_table_can_hold_a_secret_or_a_full_account_number():
    """
    Security property of the SCHEMA: gateway secrets live in the server environment (an account stores only the NAME of a
    credential set), and bank account numbers are never stored whole (last four digits only).
    """
    bad_fragments = ("secret", "password", "passwd", "token", "api_key", "apikey", "private_key", "cvv", "pan_number", "aadhaar")
    for file, table in TABLE_FILES:
        for col in re.findall(r"^\s{4}([a-z_0-9]+)\s+(?:UUID|VARCHAR|TEXT|BOOLEAN|NUMERIC|INTEGER|DATE|TIMESTAMPTZ|JSONB|CHAR)\b", _code_only(_ddl(file)), re.M):
            assert not any(f in col for f in bad_fragments), f"{table}.{col} looks like a secret column"
            assert col != "account_number", f"{table}.{col}: the full account number must never be stored"
    acct = _code_only(_ddl("04_financial_account.sql"))
    assert "account_number_last4" in acct
    assert re.search(r"chk_financial_account_credential_ref\s+CHECK \(gateway_credential_ref IS NULL OR gateway_credential_ref ~ '\^\[A-Z\]\[A-Z0-9_\]\{0,39\}\$'\)", acct), \
        "a credential reference must be constrained to an environment-variable-safe NAME"


def test_head_table_enforces_its_own_invariants_in_the_database():
    head = _code_only(_ddl("05_finance_head.sql"))
    for constraint in ("chk_finance_head_code", "chk_finance_head_direction", "chk_finance_head_restriction",
                       "chk_finance_head_income_only", "chk_finance_head_upi_target", "chk_finance_head_template_inert",
                       "uq_finance_head_org_code"):
        assert constraint in head, constraint
    assert "uq_finance_head_template_code" in head            # UNIQUE(org, code) treats NULL orgs as distinct: templates need their own
    assert re.search(r"fk_finance_head_template\s+FOREIGN KEY \(template_head_pk\)", head)


def test_payment_request_invariants_in_the_database():
    req = _code_only(_ddl("10_upi_payment_request.sql"))
    assert "uq_upi_payment_request_provider_order" in req and "UNIQUE (provider, provider_order_id)" in req
    assert "chk_upi_payment_request_paid" in req and "chk_upi_payment_request_posted" in req and "chk_upi_payment_request_amount" in req
    assert "CHECK (financial_transaction_pk IS NULL OR status = 'PAID')" in req


def test_lifecycle_table_only_uses_known_statuses():
    status_sets = {
        "year": S.YEAR_STATUSES, "scope": S.SCOPE_STATUSES, "fund": S.FUND_STATUSES,
        "transaction": S.TRANSACTION_STATUSES, "receipt": S.RECEIPT_STATUSES,
        "payment": S.PAYMENT_STATUSES, "transfer": S.TRANSFER_STATUSES,
        "account": S.ACCOUNT_STATUSES, "head": S.HEAD_STATUSES, "payment_request": S.PAYMENT_REQUEST_STATUSES,
    }
    assert set(router._STEPS) == set(status_sets)
    for entity, steps in router._STEPS.items():
        for (src, dst), step in steps.items():
            assert src in status_sets[entity] and dst in status_sets[entity], (entity, src, dst)
            assert step.permission in ("FINANCE_MANAGE", "FINANCE_APPROVE")


def test_every_status_is_reachable_and_terminals_have_no_exit():
    reversible = {"account", "head"}                   # configuration is switched off and on, never deleted
    initial = {"year": "PLANNED", "payment_request": "CREATED"}
    for entity, steps in router._STEPS.items():
        sources = {s for s, _ in steps}
        targets = {t for _, t in steps}
        if entity not in reversible:
            first = initial.get(entity, "DRAFT")
            assert first not in targets, f"{entity}: nothing may re-enter {first}"
        for terminal in ("CLOSED", "REJECTED", "CANCELLED", "COMPLETED", "SETTLED", "PAID", "FAILED", "EXPIRED"):
            assert terminal not in sources, f"{entity}: {terminal} must be terminal"
        if entity not in reversible:
            assert "INACTIVE" not in sources, f"{entity}: INACTIVE must be terminal"


def test_money_is_only_ever_marked_paid_by_the_gateway_never_by_a_user_step():
    """PAID / FAILED / EXPIRED of a UPI request are set only by the signed webhook path, so no manual transition may reach them."""
    targets = {t for (_, t) in router._STEPS["payment_request"]}
    assert targets == {"CANCELLED"}


def test_approving_is_maker_checked_everywhere_money_moves():
    for entity, pair in (("transaction", ("PENDING_APPROVAL", "APPROVED")), ("payment", ("DRAFT", "APPROVED")),
                         ("transfer", ("PENDING_APPROVAL", "APPROVED"))):
        assert router._STEPS[entity][pair].maker_checker
        assert router._STEPS[entity][pair].permission == "FINANCE_APPROVE"


def test_configuration_changes_need_the_approve_permission():
    """A head decides what is restricted and where UPI lands; an account decides where it is paid."""
    for entity in ("account", "head"):
        assert all(step.permission == "FINANCE_APPROVE" for step in router._STEPS[entity].values()), entity


# ═══════════════════════════════════════════════════════════════════════
# DB-free: seeds + patches
# ═══════════════════════════════════════════════════════════════════════

def test_reference_data_patch_content():
    sql = (SEED / "01_finance_reference_data_patch.sql").read_text(encoding="utf-8")
    for code in ("CASH", "CHEQUE", "BANK_TRANSFER", "UPI", "DEMAND_DRAFT", "OTHER"):
        assert f"'PAYMENT_METHOD', '{code}'" in sql
    for seq, prefix in (("FINANCIAL_TRANSACTION", "FTX"), ("FINANCIAL_RECEIPT", "RCT"), ("FINANCIAL_PAYMENT", "PAY"),
                        ("FINANCIAL_TRANSFER", "FTR"), ("UPI_PAYMENT_REQUEST", "PRQ")):
        assert f"('{seq}'," in sql and f"'{prefix}'" in sql, seq
    assert "ON CONFLICT" in sql                                  # idempotent, never overwrites admin edits


def _template_rows() -> dict[str, str]:
    sql = (SEED / "02_finance_head_templates_patch.sql").read_text(encoding="utf-8")
    return {m.group(1): m.group(0) for m in re.finditer(r"\(NULL, '([A-Z_]+)',[^\n]*\)[,\n]", sql)}


def test_head_templates_are_exactly_the_former_categories():
    rows = _template_rows()
    assert set(rows) == OLD_CATEGORY_CODES, "the templates must carry the old category codes verbatim (the heads patch maps old rows onto them)"


def test_head_templates_carry_the_right_rules():
    rows = _template_rows()
    assert all("'INCOME'" in rows[c] for c in OLD_CATEGORY_CODES if not c.startswith("EXPENSE"))
    assert all("'EXPENSE'" in rows[c] for c in ("EXPENSE_GENERAL", "EXPENSE_RESTRICTED"))
    pranami = {c for c, r in rows.items() if re.search(r"'INCOME', (?:FALSE|TRUE), (?:NULL|'[^']*'), (?:NULL|'[A-Z_]+'), TRUE,", r)}
    assert pranami == {"PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND"}
    assert "'SINKING_FUND'" in rows["PRANAMI_SINKING_FUND"]
    for code in ("DONATION_SPECIFIC_PURPOSE", "PUBLICATION_INCOME", "EXPENSE_RESTRICTED"):
        assert "TRUE, '" in rows[code], f"{code} must be restricted and say what it is restricted to"
    sql = (SEED / "02_finance_head_templates_patch.sql").read_text(encoding="utf-8")
    assert "ON CONFLICT (head_code) WHERE organization_pk IS NULL DO NOTHING" in sql
    assert "allow_upi" not in sql and "collection_" not in sql, "a template is a blueprint: it never collects money"


def test_heads_structure_patch_is_idempotent_and_maps_old_rows_losslessly():
    sql = _ddl("12_finance_heads_patch.sql")
    code = _code_only(sql)
    assert "ADD COLUMN IF NOT EXISTS finance_head_pk" in code and "DROP CONSTRAINT IF EXISTS chk_financial_transaction_category" in code
    assert "CREATE INDEX IF NOT EXISTS idx_financial_transaction_head" in code
    assert re.search(r"h\.organization_pk IS NULL\s+AND h\.head_code = t\.transaction_category", code)     # map by the old category code
    assert "t.finance_head_pk IS NULL" in code                                                          # only unmapped rows are touched
    # tightening to NOT NULL is guarded: an unexpected old category must never fail a build
    assert re.search(r"IF NOT EXISTS \(SELECT 1 FROM nss\.financial_transaction WHERE finance_head_pk IS NULL\) THEN\s+ALTER TABLE nss\.financial_transaction ALTER COLUMN finance_head_pk SET NOT NULL", code)
    assert "RAISE WARNING" in code


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


# ═══════════════════════════════════════════════════════════════════════
# DB-free: wiring (live feed, build scripts, validate scripts)
# ═══════════════════════════════════════════════════════════════════════

def test_finance_tables_are_on_the_live_feed_except_the_gateway_log():
    assert set(FEED_TABLES) <= LIVE_FEED_TABLES
    assert not LIVE_FEED_TABLES & APPEND_ONLY, "the gateway event log carries payer details and must stay off the live feed"
    trig = (ROOT / "database/ddl/12_live_refresh/02_live_change_triggers.sql").read_text(encoding="utf-8")
    for t in FEED_TABLES:
        assert f"'{t}'" in trig, t
    for t in APPEND_ONLY:
        assert f"'{t}'" not in trig, t


@pytest.mark.parametrize("rel", BUILD_SCRIPTS)
def test_build_scripts_run_every_finance_file_in_dependency_order(rel):
    text = _script(rel)
    assert "08_finance_permissions_patch" in text
    positions = []
    for file, table in TABLE_FILES:
        m = re.search(rf"^(?:run_ddl|Invoke-Ddl) \"{table}\".*{re.escape(file)}", text, re.M)
        assert m, f"{rel} does not build {table} from {file}"
        positions.append(m.start())
    assert positions == sorted(positions), f"{rel}: Finance tables are not built in dependency order"
    for patch in ("01_finance_reference_data_patch", "02_finance_head_templates_patch", "12_finance_heads_patch"):
        assert re.search(rf"^(?:run_sql|Invoke-Sql) .*{patch}", text, re.M), f"{rel} does not run {patch}"


@pytest.mark.parametrize("rel", BUILD_SCRIPTS)
def test_patches_run_in_the_order_they_depend_on(rel):
    text = _script(rel)
    idx = lambda needle: re.search(rf"^(?:run_sql|Invoke-Sql|run_ddl|Invoke-Ddl) .*{needle}", text, re.M).start()
    # reference data (PAYMENT_METHOD, id sequences) and the table it needs, then the templates, THEN the patch that maps old rows onto them
    assert idx('"finance_gateway_event"') < idx("01_finance_reference_data_patch") < idx("02_finance_head_templates_patch") < idx("12_finance_heads_patch")
    assert idx("12_finance_heads_patch") < idx('"live_change_triggers"')
    assert idx("08_finance_permissions_patch") < idx('"financial_year"')            # permissions are Phase 0


def test_live_triggers_are_installed_after_the_last_finance_table_is_built():
    """
    02_live_change_triggers.sql SKIPS tables that do not exist yet, so on a fresh build it must run AFTER the
    Finance DDL (Phase 11i); otherwise those tables get no trigger or marker row until a second build.
    """
    for rel in BUILD_SCRIPTS:
        text = _script(rel)
        calls = [m.start() for m in re.finditer(r"^(?:run_sql|Invoke-Sql) \"live_change_triggers\"", text, re.M)]
        assert len(calls) == 1, f"{rel}: the trigger step must be invoked exactly once"
        for table in TABLES:
            ddl = re.search(rf"^(?:run_ddl|Invoke-Ddl) \"{table}\"", text, re.M)
            assert ddl and ddl.start() < calls[0], f"{rel}: {table} is built after the live-change triggers are installed"
        assert re.search(r"^(?:run_ddl|Invoke-Ddl) \"live_change_marker\"", text, re.M).start() < calls[0], rel


@pytest.mark.parametrize("rel", ["database/scripts/03_validate.sh", "database/scripts/03_validate.ps1"])
def test_validate_scripts_check_every_finance_table_and_the_patches(rel):
    text = _script(rel)
    for table in TABLES:
        assert re.search(rf"(?:check_table_exists|Check-TableExists) \"{table}\"", text), f"{rel} does not check {table} exists"
    for needle in ("every transaction has a finance head", "no UPI-enabled head without a collection scope and account",
                   "no PAID UPI request left unposted without a review reason", "Kendra template finance heads present",
                   "PAYMENT_METHOD master_data present"):
        assert needle in text, f"{rel}: missing check '{needle}'"


def test_ddl_folder_has_no_orphan_file():
    """Every .sql in the folder is a table file or a known patch, and all of them are named in the build scripts."""
    files = {p.name for p in DDL.glob("*.sql")}
    assert files == {f for f, _ in TABLE_FILES} | {"12_finance_heads_patch.sql"}
    for rel in BUILD_SCRIPTS:
        text = _script(rel)
        for f in files:
            assert f in text, f"{rel} never runs {f}"


# ═══════════════════════════════════════════════════════════════════════
# DB tests (a build with Phase 11i + the patches)
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


def _expect(cur, exc, sql, params=()):
    """Run one statement that must violate a constraint, without poisoning the surrounding transaction."""
    name = f"x{uuid.uuid4().hex[:8]}"
    cur.execute(f"SAVEPOINT {name}")
    with pytest.raises(exc):
        cur.execute(sql, params)
    cur.execute(f"ROLLBACK TO SAVEPOINT {name}")


def _org(cur):
    cur.execute("SELECT organization_pk FROM nss.organization WHERE is_active = TRUE ORDER BY organization_pk LIMIT 1")
    row = cur.fetchone()
    if row is None:
        pytest.skip("no organization row in this database")
    return row[0]


@db
@pytest.mark.integration
@pytest.mark.parametrize("table", TABLES)
def test_table_exists(write_conn, table):
    cols = _columns(write_conn, table)
    assert cols, f"nss.{table} is missing"
    if table not in APPEND_ONLY:
        assert {"is_active", "created_at", "created_by_sangha_sevi_pk", "deleted_at"} <= cols


@db
@pytest.mark.integration
def test_payment_method_is_a_master_data_fk_on_receipt_and_payment(write_conn):
    for table in ("financial_receipt", "financial_payment"):
        assert "payment_method_master_data_pk" in _columns(write_conn, table)
        assert "instrument_reference" in _columns(write_conn, table)


@db
@pytest.mark.integration
def test_transaction_is_tied_to_a_head_not_a_fixed_category(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("SELECT is_nullable FROM information_schema.columns WHERE table_schema='nss' AND table_name='financial_transaction' AND column_name='finance_head_pk'")
        assert cur.fetchone()[0] == "NO"
        cur.execute("SELECT COUNT(*) FROM pg_constraint WHERE conname = 'chk_financial_transaction_category'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM nss.financial_transaction WHERE finance_head_pk IS NULL")
        assert cur.fetchone()[0] == 0


@db
@pytest.mark.integration
def test_payment_methods_and_sequences_are_seeded(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("""SELECT md.value_code FROM nss.master_data md
                       JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                       WHERE mc.category_code = 'PAYMENT_METHOD' AND md.is_active""")
        assert {"CASH", "UPI"} <= {r[0] for r in cur.fetchall()}
        cur.execute("SELECT sequence_code, prefix FROM nss.id_sequence_master WHERE sequence_code LIKE 'FINANCIAL\\_%' OR sequence_code = 'UPI_PAYMENT_REQUEST'")
        assert dict(cur.fetchall()) == {"FINANCIAL_TRANSACTION": "FTX", "FINANCIAL_RECEIPT": "RCT", "FINANCIAL_PAYMENT": "PAY",
                                        "FINANCIAL_TRANSFER": "FTR", "UPI_PAYMENT_REQUEST": "PRQ"}


@db
@pytest.mark.integration
def test_kendra_head_templates_are_seeded_and_inert(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("SELECT head_code, direction, is_restricted, is_pranami, allow_upi, collection_account_pk, collection_scope_pk "
                    "FROM nss.finance_head WHERE organization_pk IS NULL AND is_active")
        rows = {r[0]: r for r in cur.fetchall()}
    assert OLD_CATEGORY_CODES <= set(rows)
    assert all(not r[4] and r[5] is None and r[6] is None for r in rows.values()), "a template never collects money"
    assert {c for c, r in rows.items() if r[3]} >= {"PRANAMI_ANNUAL", "PRANAMI_SPECIAL", "PRANAMI_SINKING_FUND"}


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
        assert cur.fetchone() is not None


@db
@pytest.mark.integration
@pytest.mark.parametrize("sql", [
    "INSERT INTO nss.financial_year (year_code, start_date, end_date) VALUES ('T-1', '2090-04-01', '2090-03-31')",            # reversed dates
    "INSERT INTO nss.financial_year (year_code, start_date, end_date, status) VALUES ('T-2', '2090-04-01', '2091-03-31', 'BOGUS')",
])
def test_financial_year_checks_reject(write_conn, sql):
    with _savepoint(write_conn) as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(sql)


def _txn_world(cur, code="TEST"):
    cur.execute("INSERT INTO nss.financial_year (year_code, start_date, end_date, status) VALUES (%s, '2090-04-01', '2091-03-31', 'OPEN') RETURNING financial_year_pk", (f"T-{code}",))
    year = cur.fetchone()[0]
    cur.execute("INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type, status) VALUES (%s, 'x', 'EVENT', 'ACTIVE') RETURNING financial_scope_pk", (f"TS-{code}",))
    scope = cur.fetchone()[0]
    cur.execute("INSERT INTO nss.finance_head (organization_pk, head_code, head_name, direction) VALUES (NULL, %s, 'Test head', 'INCOME') RETURNING finance_head_pk", (f"TEST_HEAD_{code}",))
    return year, scope, cur.fetchone()[0]


@db
@pytest.mark.integration
def test_transaction_amount_must_be_positive_and_references_unique(write_conn):
    with _savepoint(write_conn) as cur:
        year, scope, head = _txn_world(cur, "A")
        insert = ("INSERT INTO nss.financial_transaction (transaction_reference, financial_year_pk, financial_scope_pk, finance_head_pk, "
                  "transaction_type, transaction_category, amount, transaction_date) VALUES (%s, %s, %s, %s, 'INCOME', 'TEST_HEAD_A', %s, '2090-05-01')")
        _expect(cur, psycopg2.errors.CheckViolation, insert, ("T-REF-0", year, scope, head, 0))
        cur.execute(insert, ("T-REF-1", year, scope, head, 10))
        _expect(cur, psycopg2.errors.UniqueViolation, insert, ("T-REF-1", year, scope, head, 10))
        _expect(cur, psycopg2.errors.UniqueViolation,
                "INSERT INTO nss.financial_year (year_code, start_date, end_date) VALUES ('T-A', '2092-04-01', '2093-03-31')")
        # a transaction without a head is refused (NOT NULL)
        _expect(cur, psycopg2.errors.NotNullViolation,
                "INSERT INTO nss.financial_transaction (transaction_reference, financial_year_pk, financial_scope_pk, transaction_type, "
                "transaction_category, amount, transaction_date) VALUES ('T-REF-2', %s, %s, 'INCOME', 'X', 1, '2090-05-01')", (year, scope))


@db
@pytest.mark.integration
def test_scope_fund_and_transfer_checks(write_conn):
    with _savepoint(write_conn) as cur:
        cur.execute("INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type) VALUES ('TS-4', 'x', 'EVENT') RETURNING financial_scope_pk")
        scope = cur.fetchone()[0]
        cur.execute("INSERT INTO nss.financial_year (year_code, start_date, end_date) VALUES ('T-4', '2090-04-01', '2091-03-31') RETURNING financial_year_pk")
        year = cur.fetchone()[0]
        _expect(cur, psycopg2.errors.CheckViolation,
                "INSERT INTO nss.fund_master (fund_code, fund_name, fund_type, financial_scope_pk, is_restricted) VALUES ('TF', 'x', 'GRANT', %s, TRUE)", (scope,))
        _expect(cur, psycopg2.errors.CheckViolation,
                "INSERT INTO nss.financial_transfer (transfer_reference, financial_year_pk, source_scope_pk, destination_scope_pk, amount, "
                "transfer_date, purpose) VALUES ('TT-1', %s, %s, %s, 5, '2090-05-01', 'x')", (year, scope, scope))


@db
@pytest.mark.integration
class TestAccountConstraints:
    BASE = "INSERT INTO nss.financial_account (organization_pk, account_label, account_holder_name{cols}) VALUES (%s, %s, 'Holder'{vals})"

    def _insert(self, extra_cols="", extra_vals=""):
        return self.BASE.format(cols=extra_cols, vals=extra_vals)

    @pytest.mark.parametrize("col,bad", [
        ("account_number_last4", "123"), ("account_number_last4", "12ab"), ("account_number_last4", "    "),
        ("ifsc_code", "sbin0001234"), ("ifsc_code", "SBIN1001234"), ("ifsc_code", "SBIN000123"),
        ("upi_vpa", "no-at-sign"), ("upi_vpa", "@bank"), ("upi_vpa", "a@1"),
        ("gateway_credential_ref", "lowercase"), ("gateway_credential_ref", "HAS SPACE"), ("gateway_credential_ref", "1START"),
        ("account_type", "WALLET"), ("status", "DELETED"),
    ])
    def test_format_checks(self, write_conn, col, bad):
        with _savepoint(write_conn) as cur:
            _expect(cur, psycopg2.errors.CheckViolation, self._insert(f", {col}", ", %s"), (_org(cur), "L1", bad))

    def test_a_longer_account_number_cannot_even_be_stored(self, write_conn):
        """The column itself is VARCHAR(4): a full number is refused by the TYPE, before any CHECK."""
        with _savepoint(write_conn) as cur:
            _expect(cur, psycopg2.errors.StringDataRightTruncation, self._insert(", account_number_last4", ", %s"), (_org(cur), "L0", "1234567890"))

    def test_a_gateway_needs_its_credential_set_name(self, write_conn):
        with _savepoint(write_conn) as cur:
            _expect(cur, psycopg2.errors.CheckViolation, self._insert(", gateway_provider", ", 'RAZORPAY'"), (_org(cur), "L2"))
            org = _org(cur)
            cur.execute(self._insert(", gateway_provider, gateway_credential_ref", ", 'RAZORPAY', 'SAKHA_A'"), (org, "L3"))

    def test_label_unique_per_organization_and_one_default(self, write_conn):
        with _savepoint(write_conn) as cur:
            org = _org(cur)
            cur.execute(self._insert(", is_default", ", TRUE"), (org, "A"))
            _expect(cur, psycopg2.errors.UniqueViolation, self._insert(), (org, "A"))
            _expect(cur, psycopg2.errors.UniqueViolation, self._insert(", is_default", ", TRUE"), (org, "B"))
            cur.execute(self._insert(), (org, "C"))                                  # a second NON-default is fine


@db
@pytest.mark.integration
class TestHeadConstraints:
    INS = ("INSERT INTO nss.finance_head (organization_pk, head_code, head_name, direction{cols}) "
           "VALUES (%s, %s, 'Name', %s{vals})")

    def _sql(self, cols="", vals=""):
        return self.INS.format(cols=cols, vals=vals)

    @pytest.mark.parametrize("code", ["lower", "1ABC", "A", "HAS SPACE", "A-B"])
    def test_code_format(self, write_conn, code):
        with _savepoint(write_conn) as cur:
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(), (None, code, "INCOME"))

    def test_direction_and_restriction_rules(self, write_conn):
        with _savepoint(write_conn) as cur:
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(), (None, "BADDIR", "SIDEWAYS"))
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(", is_restricted", ", TRUE"), (None, "RESTR", "INCOME"))   # no purpose
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(", is_pranami", ", TRUE"), (None, "EXPP", "EXPENSE"))       # Pranami is income-only
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(", required_fund_type", ", 'NOT_A_FUND'"), (None, "BADFT", "INCOME"))

    def test_upi_needs_a_target_and_a_template_never_collects(self, write_conn):
        with _savepoint(write_conn) as cur:
            org = _org(cur)
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(", allow_upi", ", TRUE"), (org, "NOTARGET", "INCOME"))    # no scope / account
            _expect(cur, psycopg2.errors.CheckViolation, self._sql(", allow_upi", ", TRUE"), (None, "TMPLUPI", "INCOME"))      # a template cannot collect

    def test_codes_are_unique_per_organization_and_among_templates(self, write_conn):
        with _savepoint(write_conn) as cur:
            org = _org(cur)
            cur.execute(self._sql(), (org, "ORGCODE", "INCOME"))
            _expect(cur, psycopg2.errors.UniqueViolation, self._sql(), (org, "ORGCODE", "INCOME"))
            cur.execute(self._sql(), (None, "TMPLCODE_X", "INCOME"))
            _expect(cur, psycopg2.errors.UniqueViolation, self._sql(), (None, "TMPLCODE_X", "INCOME"))   # NULL organizations are still unique among templates


@db
@pytest.mark.integration
class TestUpiRequestAndGatewayEvent:
    def _request_world(self, cur):
        org = _org(cur)
        cur.execute("INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type, organization_pk, status) VALUES ('TS-REQ', 'x', 'ORGANIZATION', %s, 'ACTIVE') RETURNING financial_scope_pk", (org,))
        scope = cur.fetchone()[0]
        cur.execute("INSERT INTO nss.financial_account (organization_pk, account_label, account_holder_name, gateway_provider, gateway_credential_ref) "
                    "VALUES (%s, 'U1', 'Holder', 'MOCK', 'T_U') RETURNING financial_account_pk", (org,))
        account = cur.fetchone()[0]
        cur.execute("INSERT INTO nss.finance_head (organization_pk, head_code, head_name, direction, allow_upi, collection_scope_pk, collection_account_pk) "
                    "VALUES (%s, 'UPI_HEAD_T', 'x', 'INCOME', TRUE, %s, %s) RETURNING finance_head_pk", (org, scope, account))
        return account, cur.fetchone()[0], scope

    INS = ("INSERT INTO nss.upi_payment_request (request_reference, financial_account_pk, finance_head_pk, financial_scope_pk, amount, provider, "
           "provider_order_id, expires_at, status{cols}) VALUES (%s, %s, %s, %s, %s, 'MOCK', %s, NOW() + INTERVAL '30 minutes', %s{vals})")

    def test_request_rules(self, write_conn):
        with _savepoint(write_conn) as cur:
            account, head, scope = self._request_world(cur)
            ins = lambda c="", v="": self.INS.format(cols=c, vals=v)
            _expect(cur, psycopg2.errors.CheckViolation, ins(), ("PRQ-T0", account, head, scope, 0, "o0", "PENDING"))              # amount > 0
            _expect(cur, psycopg2.errors.CheckViolation, ins(), ("PRQ-T0", account, head, scope, 10, "o0", "PAID"))                # PAID needs its evidence
            cur.execute(ins(), ("PRQ-T1", account, head, scope, 10, "o1", "PENDING"))
            _expect(cur, psycopg2.errors.UniqueViolation, ins(), ("PRQ-T2", account, head, scope, 10, "o1", "PENDING"))           # one request per provider order
            _expect(cur, psycopg2.errors.UniqueViolation, ins(), ("PRQ-T1", account, head, scope, 10, "o9", "PENDING"))           # reference unique
            cur.execute(ins(", provider_payment_id, paid_amount, paid_at", ", 'pay_1', 10, NOW()"), ("PRQ-T3", account, head, scope, 10, "o3", "PAID"))

    def test_a_transaction_may_only_hang_off_a_paid_request(self, write_conn):
        with _savepoint(write_conn) as cur:
            account, head, scope = self._request_world(cur)
            year, scope2, h2 = _txn_world(cur, "U")
            cur.execute("INSERT INTO nss.financial_transaction (transaction_reference, financial_year_pk, financial_scope_pk, finance_head_pk, transaction_type, "
                        "transaction_category, amount, transaction_date, status) VALUES ('T-U', %s, %s, %s, 'INCOME', 'TEST_HEAD_U', 5, '2090-05-01', 'POSTED') RETURNING financial_transaction_pk", (year, scope2, h2))
            txn = cur.fetchone()[0]
            _expect(cur, psycopg2.errors.CheckViolation,
                    self.INS.format(cols=", financial_transaction_pk", vals=", %s"), ("PRQ-T4", account, head, scope, 10, "o4", "PENDING", txn))

    def test_gateway_event_idempotency_only_covers_signed_events(self, write_conn):
        with _savepoint(write_conn) as cur:
            ins = ("INSERT INTO nss.finance_gateway_event (provider, event_id, signature_valid, payload, outcome) "
                   "VALUES ('MOCK', %s, %s, '{}', 'IGNORED')")
            cur.execute(ins, ("evt-1", True))
            _expect(cur, psycopg2.errors.UniqueViolation, ins, ("evt-1", True))          # a replay of a signed event is refused
            cur.execute(ins, ("evt-1", False))                                           # a FORGED copy is recorded, and can never block the real one
            cur.execute(ins, ("evt-1", False))
            _expect(cur, psycopg2.errors.CheckViolation,
                    "INSERT INTO nss.finance_gateway_event (provider, event_id, signature_valid, payload, outcome) VALUES ('MOCK', 'e2', TRUE, '{}', 'BOGUS')")


# ═══════════════════════════════════════════════════════════════════════
# Bye-Law disbursement authority (Kendra / central Mahila Sangha money) - DB-free parity
# ═══════════════════════════════════════════════════════════════════════

class TestDisbursementAuthorityParity:
    def test_service_status_steps_exist_in_the_lifecycles(self):
        from api.services import finance_authority as FA

        assert {FA.KIND_STEPS["payment"]["start"], FA.KIND_STEPS["payment"]["finish"], *FA.KIND_STEPS["payment"]["open"]} <= set(S.PAYMENT_STATUSES)
        assert {FA.KIND_STEPS["transfer"]["start"], FA.KIND_STEPS["transfer"]["finish"], *FA.KIND_STEPS["transfer"]["open"]} <= set(S.TRANSFER_STATUSES)
        # the Treasurer's step and the completion step are real transitions of the one lifecycle table
        assert ("APPROVED", "INITIATED") in router._STEPS["payment"] and ("INITIATED", "COMPLETED") in router._STEPS["payment"]
        assert ("APPROVED", "EXECUTED") in router._STEPS["transfer"] and ("EXECUTED", "COMPLETED") in router._STEPS["transfer"]

    def test_basis_values_match_the_ddl_check(self):
        from api.services import finance_authority as FA

        ddl = _ddl("13_finance_disbursement_authority.sql")
        assert _check_values(ddl, "chk_fda_basis") == {FA.KENDRA, FA.MAHILA}
        assert set(FA.BODY_TYPE) == {FA.KENDRA, FA.MAHILA}

    def test_purpose_seed_is_prefixed_by_the_body_and_covers_the_bye_law(self):
        text = (SEED / "03_finance_disbursement_purpose_patch.sql").read_text(encoding="utf-8")
        codes = set(re.findall(r"\('((?:KENDRA|MAHILA)_[A-Z_]+)',", text))
        assert len(codes) >= 20
        # F[c](ii)-(v), F[A](vi) and Mahila 7(iii)(b)-(h)(j)(k) each have a purpose
        assert {"KENDRA_NILACHALA_KUTIR", "KENDRA_MATHA_GURU_DHAMA_DONATION", "KENDRA_SATSIKSHYA_BISTAR",
                "KENDRA_SPECIFIC_PURPOSE", "MAHILA_SPECIFIC_PURPOSE", "MAHILA_PRESIDENT_VP_EXPENSES"} <= codes
        from api.services import finance_authority as FA

        assert FA.PARICHALAK_PURPOSES <= codes

    def test_the_ddl_encodes_the_three_separate_kendra_steps(self):
        ddl = _code_only(_ddl("13_finance_disbursement_authority.sql"))
        for needle in ("chk_fda_one_target", "chk_fda_kendra_president_order", "chk_fda_joint_signers_differ",
                       "chk_fda_secretary_after_treasurer", "chk_fda_order_after_resolution", "uq_fda_payment", "uq_fda_transfer"):
            assert needle in ddl, needle

    def test_build_scripts_create_the_table_and_apply_the_purpose_patch(self):
        for rel in BUILD_SCRIPTS:
            src = _script(rel)
            assert "13_finance_disbursement_authority.sql" in src and "03_finance_disbursement_purpose_patch.sql" in src, rel
            assert src.index("13_finance_disbursement_authority.sql") < src.index("03_finance_disbursement_purpose_patch.sql"), rel
            assert src.index("03_finance_disbursement_purpose_patch.sql") < src.index("02_live_change_triggers.sql"), rel
