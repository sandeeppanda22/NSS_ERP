"""
NSS ERP — DB schema tests for the Assets & Property module (Module #22,
SOL-AP-005, GDR-010).

Guards the structural invariants of the seven module tables and the
lifecycle / history guard triggers (database/ddl/11_assets_property/):

  - constraint + index presence (FKs, status CHECKs, soft-delete CHECKs,
    the AP-019 property-XOR-asset CHECKs, the AP-017 one-ACTIVE-custodian
    partial unique indexes, document-link uniqueness);
  - NO financial columns on any table (AP-031/039/060/061/063);
  - statutory records are property-only (AP-040: no asset_pk column);
  - the reference data (7 master categories, id sequences) delivered by
    seed/11_assets_property/01_assets_property_reference_data_patch.sql;
  - behaviour: status CHECKs, UNIQUE ids, mutual exclusivity, one ACTIVE
    custodian, history preservation on transfer (ENDED rows immutable),
    terminal lifecycle states, custody-before-activation, identifier
    immutability (fn_ap_entity_guard / fn_custodianship_guard).

Every throwaway row is inserted inside its own SAVEPOINT and rolled back, so
the seed-less test DB is left untouched. Needs organization + master_data
rows only (always present after a build).
"""

import uuid
from contextlib import contextmanager

import psycopg2
import pytest

pytestmark = [pytest.mark.db, pytest.mark.integration]

TABLES = [
    "property", "asset", "custodianship", "property_statutory_record",
    "maintenance_record", "property_document", "asset_document",
]

FINANCIAL_COLUMN_HINTS = (
    "amount", "cost", "price", "payment", "paid", "value", "valuation",
    "depreciation", "currency", "transaction", "expense", "income", "revenue_amount",
)


# ── introspection helpers ───────────────────────────────────────────────

def _constraint_exists(conn, name):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'nss' AND c.conname = %s
            """,
            (name,),
        )
        return cur.fetchone() is not None


def _index_exists(conn, name):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_indexes WHERE schemaname = 'nss' AND indexname = %s", (name,))
        return cur.fetchone() is not None


def _columns(conn, table):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'nss' AND table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@contextmanager
def _savepoint(conn):
    """Everything inside is rolled back, whatever happens (incl. an expected DB error)."""
    name = f"sp_ap_{uuid.uuid4().hex[:10]}"
    cur = conn.cursor()
    cur.execute(f"SAVEPOINT {name}")
    try:
        yield cur
    finally:
        cur.execute(f"ROLLBACK TO SAVEPOINT {name}")


# ── presence ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("table", TABLES)
def test_table_exists(write_conn, table):
    assert _columns(write_conn, table), f"nss.{table} is missing"


@pytest.mark.parametrize("constraint", [
    "uq_property_id", "fk_property_type", "chk_property_status", "chk_property_soft_delete",
    "uq_asset_id", "fk_asset_type", "chk_asset_status", "chk_asset_soft_delete",
    "fk_custodianship_property", "fk_custodianship_asset", "fk_custodianship_organization",
    "fk_custodianship_end_reason", "chk_custodianship_target_xor", "chk_custodianship_status",
    "chk_custodianship_dates", "chk_custodianship_ended_consistency", "chk_custodianship_soft_delete",
    "fk_psr_property", "fk_psr_obligation_type", "chk_psr_soft_delete",
    "fk_maintenance_property", "fk_maintenance_asset", "fk_maintenance_type",
    "chk_maintenance_target_xor", "chk_maintenance_soft_delete",
    "fk_property_document_property", "fk_property_document_document", "fk_property_document_relationship",
    "chk_property_document_soft_delete",
    "fk_property_acquisition_method", "fk_asset_acquisition_method",
    "fk_asset_document_asset", "fk_asset_document_document", "fk_asset_document_relationship",
    "chk_asset_document_soft_delete",
])
def test_constraint_exists(write_conn, constraint):
    assert _constraint_exists(write_conn, constraint), f"Expected constraint nss.{constraint}"


@pytest.mark.parametrize("index", [
    "uq_custodianship_active_property", "uq_custodianship_active_asset",
    "uq_property_document_active", "uq_asset_document_active",
    "idx_custodianship_property_status", "idx_custodianship_asset_status", "idx_custodianship_organization",
    "idx_property_status", "idx_property_type", "idx_asset_status", "idx_asset_type",
    "idx_psr_property", "idx_maintenance_property", "idx_maintenance_asset",
    "idx_property_acquisition_method", "idx_asset_acquisition_method",
])
def test_index_exists(write_conn, index):
    assert _index_exists(write_conn, index), f"Expected index nss.{index}"


@pytest.mark.parametrize("trigger", [
    "trg_property_guard", "trg_asset_guard", "trg_custodianship_guard", "trg_custodianship_custodian_guard",
    "trg_custodianship_terminal_guard",
])
def test_guard_trigger_exists(write_conn, trigger):
    with write_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_trigger WHERE tgname = %s AND NOT tgisinternal", (trigger,))
        assert cur.fetchone() is not None


@pytest.mark.parametrize("table", TABLES)
def test_standard_audit_columns(write_conn, table):
    """AP-070."""
    cols = _columns(write_conn, table)
    for c in ("created_at", "created_by_sangha_sevi_pk", "updated_at", "updated_by_sangha_sevi_pk",
              "deleted_at", "deleted_by_sangha_sevi_pk", "is_active"):
        assert c in cols, f"nss.{table} lacks audit column {c}"


@pytest.mark.parametrize("table", TABLES)
def test_no_financial_columns(write_conn, table):
    """AP-031/039/060/061/063: Finance owns every financial concept."""
    for c in _columns(write_conn, table):
        assert not any(h in c for h in FINANCIAL_COLUMN_HINTS), f"nss.{table}.{c} looks financial"


def test_statutory_record_is_property_only(write_conn):
    """AP-040: no asset_pk on property_statutory_record; property_pk is NOT NULL."""
    cols = _columns(write_conn, "property_statutory_record")
    assert "asset_pk" not in cols
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT is_nullable FROM information_schema.columns WHERE table_schema='nss' "
            "AND table_name='property_statutory_record' AND column_name='property_pk'"
        )
        assert cur.fetchone()[0] == "NO"


# ── reference data delivered by the idempotent patch ────────────────────

EXPECTED_MASTER_DATA = {
    "PROPERTY_TYPE": {"LAND", "BUILDING", "PREMISES", "OTHER_IMMOVABLE"},
    "ASSET_TYPE": {"EQUIPMENT", "FURNITURE", "INSTRUMENT", "ARTICLE", "OTHER_MOVABLE"},
    "CUSTODIANSHIP_END_REASON": {"TRANSFER", "DISSOLUTION_VESTING", "ORGANIZATIONAL_CHANGE", "OTHER", "DISPOSED", "RETIRED"},
    "STATUTORY_OBLIGATION_TYPE": {"LAND_REVENUE", "MUNICIPAL_TAX", "LAND_RECORD", "OTHER"},
    "MAINTENANCE_TYPE": {"REPAIR_MINOR", "REPAIR_MAJOR", "IMPROVEMENT", "ADDITION", "ALTERATION", "UPKEEP", "OTHER"},
    "ASSET_PROPERTY_DOCUMENT_RELATIONSHIP": {"TITLE_DEED", "LAND_RECORD", "MAINTENANCE_CERTIFICATE", "PHOTOGRAPH", "OTHER"},
    "ACQUISITION_METHOD": {"PURCHASE", "DONATION", "GIFT", "BEQUEST", "TRANSFER_IN", "CONSTRUCTION", "OTHER"},
}


@pytest.mark.parametrize("category", sorted(EXPECTED_MASTER_DATA))
def test_master_data_seeded_at_least_candidate_values(write_conn, category):
    """Admin-extendable sets: the candidate values must be present; extras (admin additions) are allowed."""
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT md.value_code FROM nss.master_data md
            JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
            WHERE mc.category_code = %s
            """,
            (category,),
        )
        seeded = {r[0] for r in cur.fetchall()}
    assert EXPECTED_MASTER_DATA[category] <= seeded


@pytest.mark.parametrize("code,prefix", [("PROPERTY", "PROP"), ("ASSET", "AST")])
def test_id_sequences_have_distinct_prefixes(write_conn, code, prefix):
    """AP-005/007/008: two namespaces, never colliding."""
    with write_conn.cursor() as cur:
        cur.execute("SELECT prefix FROM nss.id_sequence_master WHERE sequence_code = %s", (code,))
        row = cur.fetchone()
    assert row is not None and row[0] == prefix


def test_permissions_seeded_with_expected_grants(write_conn):
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pm.permission_code, rm.role_code
            FROM nss.role_permission rp
            JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
            JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk
            WHERE pm.permission_code IN ('ASSET_VIEW', 'ASSET_MANAGE') AND rp.is_active = TRUE
            """
        )
        grants = {(p, r) for p, r in cur.fetchall()}
    manage = {r for p, r in grants if p == "ASSET_MANAGE"}
    view = {r for p, r in grants if p == "ASSET_VIEW"}
    # Owner decisions 2026-11-02 (GDR-010): Anchalika / Zilla admins are VIEW-ONLY, the Mahila admin has none.
    assert manage == {
        "NSS_ERP_ADMIN", "NSS_ERP_KENDRA_ADMIN", "NSS_ERP_SAKHA_ADMIN", "NSS_ERP_PATHA_CHAKRA_ADMIN",
    }
    assert view == manage | {
        "NSS_ERP_ANCHALIKA_ADMIN", "NSS_ERP_ZILLA_ADMIN", "NSS_ERP_AUDITOR", "NSS_ERP_REPORT_VIEWER",
    }
    assert "NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN" not in view | manage
    assert "NSS_ERP_ATTENDANCE_MARKER" not in view | manage
    assert "NSS_ERP_ADVISORY_BOARD_ADMIN" not in view | manage


def test_withdrawn_grants_are_deactivated_not_deleted_or_absent(write_conn):
    """The 4 withdrawn grants are never ACTIVE (rows, if the old patch ever ran, are soft-deleted history)."""
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM nss.role_permission rp
            JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
            JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk
            WHERE rp.is_active = TRUE AND (
                (rm.role_code = 'NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN' AND pm.permission_code IN ('ASSET_VIEW', 'ASSET_MANAGE'))
                OR (rm.role_code IN ('NSS_ERP_ANCHALIKA_ADMIN', 'NSS_ERP_ZILLA_ADMIN') AND pm.permission_code = 'ASSET_MANAGE'))
            """
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            """
            SELECT COUNT(*) FROM nss.role_permission rp
            JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
            WHERE pm.permission_code IN ('ASSET_VIEW', 'ASSET_MANAGE') AND rp.is_active = FALSE AND rp.deleted_at IS NULL
            """
        )
        assert cur.fetchone()[0] == 0   # chk_role_permission_soft_delete


@pytest.mark.parametrize("table", ["property", "asset"])
def test_belongs_to_organization_column_and_fk(write_conn, table):
    """GDR-010 item 4: nullable belongs_to_organization_pk -> nss.organization on property and asset."""
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = 'nss' AND table_name = %s AND column_name = 'belongs_to_organization_pk'
            """,
            (table,),
        )
        row = cur.fetchone()
        assert row is not None and row[0] == "YES"
        cur.execute(
            """
            SELECT confrelid::regclass::text FROM pg_constraint
            WHERE conname = %s AND conrelid = %s::regclass AND contype = 'f'
            """,
            (f"fk_{table}_belongs_to_org", f"nss.{table}"),
        )
        assert cur.fetchone()[0].endswith("organization")


@pytest.mark.parametrize("table", ["property", "asset"])
def test_belongs_to_organization_rejects_unknown_organization(write_conn, ctx, table):
    import psycopg2

    maker = _property if table == "property" else _asset
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        with write_conn.cursor() as cur:
            cur.execute("SAVEPOINT bt_fk")
            try:
                maker(cur, ctx, belongs_to_organization_pk=str(uuid.uuid4()))
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT bt_fk")


# ── behaviour ───────────────────────────────────────────────────────────

@pytest.fixture
def ctx(write_conn):
    """FK targets: two organizations + one master_data pk per category used below."""
    with write_conn.cursor() as cur:
        # Custodians must be PHYSICAL organizations (GDR-010 §2C trigger), so the
        # two FK-target organizations are picked through the SQL definition.
        cur.execute(
            """
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE nss.fn_is_asset_custodian_org_type(md.value_code)
            ORDER BY o.organization_pk LIMIT 2
            """
        )
        orgs = [str(r[0]) for r in cur.fetchall()]
        if len(orgs) < 2:
            pytest.skip("Need two seeded custodian-eligible (physical) organizations.")
        out = {"org_a": orgs[0], "org_b": orgs[1]}
        for key, category, code in (
            ("ptype", "PROPERTY_TYPE", "LAND"), ("atype", "ASSET_TYPE", "EQUIPMENT"),
            ("end_reason", "CUSTODIANSHIP_END_REASON", "TRANSFER"),
            ("mtype", "MAINTENANCE_TYPE", "UPKEEP"), ("otype", "STATUTORY_OBLIGATION_TYPE", "LAND_REVENUE"),
        ):
            cur.execute(
                """
                SELECT md.master_data_pk FROM nss.master_data md
                JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = %s AND md.value_code = %s
                """,
                (category, code),
            )
            row = cur.fetchone()
            if row is None:
                pytest.skip(f"{category}/{code} not seeded (reference-data patch missing).")
            out[key] = str(row[0])
    return out


def _property(cur, ctx, **over):
    row = {"property_id": f"PT{uuid.uuid4().hex[:10]}", "property_name": "Schema test property",
           "property_type_master_data_pk": ctx["ptype"], "status": "REGISTERED"}
    row.update(over)
    cols = ", ".join(row)
    cur.execute(f"INSERT INTO nss.property ({cols}) VALUES ({', '.join(['%s'] * len(row))}) RETURNING property_pk",
                list(row.values()))
    return str(cur.fetchone()[0])


def _asset(cur, ctx, **over):
    row = {"asset_id": f"AT{uuid.uuid4().hex[:10]}", "asset_name": "Schema test asset",
           "asset_type_master_data_pk": ctx["atype"], "status": "REGISTERED"}
    row.update(over)
    cols = ", ".join(row)
    cur.execute(f"INSERT INTO nss.asset ({cols}) VALUES ({', '.join(['%s'] * len(row))}) RETURNING asset_pk",
                list(row.values()))
    return str(cur.fetchone()[0])


def _custody(cur, *, property_pk=None, asset_pk=None, org, status="ACTIVE", **over):
    row = {"property_pk": property_pk, "asset_pk": asset_pk, "custodian_organization_pk": org,
           "status": status, "effective_from": "2026-01-01"}
    row.update(over)
    cols = ", ".join(row)
    cur.execute(f"INSERT INTO nss.custodianship ({cols}) VALUES ({', '.join(['%s'] * len(row))}) RETURNING custodianship_pk",
                list(row.values()))
    return str(cur.fetchone()[0])


def test_valid_rows_insert(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        a = _asset(cur, ctx)
        assert p and a


def test_property_bad_status_rejected(write_conn, ctx):
    with _savepoint(write_conn) as cur, pytest.raises(psycopg2.errors.CheckViolation):
        _property(cur, ctx, status="TRANSFERRED")


def test_asset_bad_status_rejected(write_conn, ctx):
    with _savepoint(write_conn) as cur, pytest.raises(psycopg2.errors.CheckViolation):
        _asset(cur, ctx, status="DISPOSED")   # property vocabulary, not an asset state


def test_duplicate_business_id_rejected(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        _property(cur, ctx, property_id="DUPTEST1")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            _property(cur, ctx, property_id="DUPTEST1")


def test_soft_delete_check(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        pk = _property(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.property SET is_active = FALSE WHERE property_pk = %s", (pk,))


def test_custodianship_requires_exactly_one_target(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p, a = _property(cur, ctx), _asset(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            _custody(cur, property_pk=p, asset_pk=a, org=ctx["org_a"])
    with _savepoint(write_conn) as cur, pytest.raises(psycopg2.errors.CheckViolation):
        _custody(cur, org=ctx["org_a"])


def test_maintenance_requires_exactly_one_target(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p, a = _property(cur, ctx), _asset(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO nss.maintenance_record (property_pk, asset_pk, maintenance_type_master_data_pk) VALUES (%s, %s, %s)",
                (p, a, ctx["mtype"]),
            )
    with _savepoint(write_conn) as cur, pytest.raises(psycopg2.errors.CheckViolation):
        cur.execute("INSERT INTO nss.maintenance_record (maintenance_type_master_data_pk) VALUES (%s)", (ctx["mtype"],))


def test_one_active_custodian_per_property(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        _custody(cur, property_pk=p, org=ctx["org_a"])
        with pytest.raises(psycopg2.errors.UniqueViolation):
            _custody(cur, property_pk=p, org=ctx["org_b"])


def test_one_active_custodian_per_asset(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        _custody(cur, asset_pk=a, org=ctx["org_a"])
        with pytest.raises(psycopg2.errors.UniqueViolation):
            _custody(cur, asset_pk=a, org=ctx["org_b"])


def test_ended_custodianship_needs_end_date_and_reason(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        c = _custody(cur, property_pk=p, org=ctx["org_a"])
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.custodianship SET status = 'ENDED', effective_to = '2026-02-01' WHERE custodianship_pk = %s", (c,))
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            _custody(cur, property_pk=p, org=ctx["org_a"], effective_to="2026-02-01")   # ACTIVE with an end date


def test_effective_to_not_before_effective_from(write_conn, ctx):
    with _savepoint(write_conn) as cur, pytest.raises(psycopg2.errors.CheckViolation):
        _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_a"], status="ENDED",
                 effective_to="2025-12-31", end_reason_master_data_pk=ctx["end_reason"])


def test_transfer_preserves_history(write_conn, ctx):
    """AP-018/042/072: the old row is ENDED (not overwritten/deleted), a new ACTIVE row is opened."""
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        old = _custody(cur, property_pk=p, org=ctx["org_a"])
        cur.execute(
            "UPDATE nss.custodianship SET status = 'ENDED', effective_to = '2026-03-01', end_reason_master_data_pk = %s WHERE custodianship_pk = %s",
            (ctx["end_reason"], old),
        )
        _custody(cur, property_pk=p, org=ctx["org_b"], effective_from="2026-03-01")
        cur.execute("SELECT status, custodian_organization_pk::text FROM nss.custodianship WHERE property_pk = %s ORDER BY effective_from", (p,))
        assert cur.fetchall() == [("ENDED", ctx["org_a"]), ("ACTIVE", ctx["org_b"])]


def test_ended_custodianship_is_immutable(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        old = _custody(cur, property_pk=p, org=ctx["org_a"])
        cur.execute(
            "UPDATE nss.custodianship SET status = 'ENDED', effective_to = '2026-03-01', end_reason_master_data_pk = %s WHERE custodianship_pk = %s",
            (ctx["end_reason"], old),
        )
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.custodianship SET notes = 'rewrite history' WHERE custodianship_pk = %s", (old,))


def test_custodian_and_target_are_immutable(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        c = _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_a"])
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.custodianship SET custodian_organization_pk = %s WHERE custodianship_pk = %s", (ctx["org_b"], c))


def test_custodianship_status_only_moves_forward(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        c = _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_a"])
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.custodianship SET status = 'ASSIGNED' WHERE custodianship_pk = %s", (c,))


def test_cannot_leave_registered_without_custodianship(write_conn, ctx):
    """AP-LIF-001."""
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.asset SET status = 'IN_CUSTODY' WHERE asset_pk = %s", (a,))


def test_property_lifecycle_and_terminal_disposed(write_conn, ctx):
    """SOL-AP-003 §3.2; AP-046."""
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        _custody(cur, property_pk=p, org=ctx["org_a"])
        for target in ("ACTIVE", "UNDER_MAINTENANCE", "ACTIVE", "DISPOSED"):
            cur.execute("UPDATE nss.property SET status = %s WHERE property_pk = %s", (target, p))
        for bad in ("ACTIVE", "REGISTERED", "UNDER_MAINTENANCE"):
            cur.execute("SAVEPOINT inner_sp")
            with pytest.raises(psycopg2.errors.CheckViolation):
                cur.execute("UPDATE nss.property SET status = %s WHERE property_pk = %s", (bad, p))
            cur.execute("ROLLBACK TO SAVEPOINT inner_sp")


def test_property_cannot_skip_to_disposed_from_registered(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        _custody(cur, property_pk=p, org=ctx["org_a"])
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.property SET status = 'DISPOSED' WHERE property_pk = %s", (p,))


def test_asset_lifecycle_and_terminal_retired(write_conn, ctx):
    """SOL-AP-003 §4.2; AP-047; AP-LIF-002 (UNDER_MAINTENANCE -> RETIRED)."""
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        _custody(cur, asset_pk=a, org=ctx["org_a"])
        for target in ("IN_CUSTODY", "UNDER_MAINTENANCE", "RETIRED"):
            cur.execute("UPDATE nss.asset SET status = %s WHERE asset_pk = %s", (target, a))
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.asset SET status = 'IN_CUSTODY' WHERE asset_pk = %s", (a,))


def test_business_identifiers_are_immutable(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.property SET property_id = 'CHANGED' WHERE property_pk = %s", (p,))
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.asset SET asset_id = 'CHANGED' WHERE asset_pk = %s", (a,))


def test_document_link_unique_while_active_but_reattachable(write_conn, ctx):
    """One live link per (entity, document); a detached (soft-deleted) link frees the slot."""
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        cur.execute(
            "INSERT INTO nss.document_master (document_type_code, document_name, storage_path) VALUES ('AP_TEST', %s, %s) RETURNING document_master_pk",
            (f"doc {uuid.uuid4().hex[:6]}", "/tmp/ap-test"),
        )
        doc = str(cur.fetchone()[0])
        cur.execute("INSERT INTO nss.asset_document (asset_pk, document_master_pk) VALUES (%s, %s)", (a, doc))
        cur.execute("SAVEPOINT dup_sp")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute("INSERT INTO nss.asset_document (asset_pk, document_master_pk) VALUES (%s, %s)", (a, doc))
        cur.execute("ROLLBACK TO SAVEPOINT dup_sp")
        cur.execute("UPDATE nss.asset_document SET is_active = FALSE, deleted_at = NOW() WHERE asset_pk = %s", (a,))
        cur.execute("INSERT INTO nss.asset_document (asset_pk, document_master_pk) VALUES (%s, %s)", (a, doc))


def test_statutory_and_maintenance_rows_insert(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        p, a = _property(cur, ctx), _asset(cur, ctx)
        cur.execute(
            "INSERT INTO nss.property_statutory_record (property_pk, obligation_type_master_data_pk, reference_number) VALUES (%s, %s, 'LR-1')",
            (p, ctx["otype"]),
        )
        cur.execute("INSERT INTO nss.maintenance_record (property_pk, maintenance_type_master_data_pk) VALUES (%s, %s)", (p, ctx["mtype"]))
        cur.execute("INSERT INTO nss.maintenance_record (asset_pk, maintenance_type_master_data_pk) VALUES (%s, %s)", (a, ctx["mtype"]))


def test_audit_trigger_covers_new_tables(write_conn):
    """AP-071: Phase 14 attaches the generic audit trigger to every nss table, including these."""
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname = ANY(%s)",
            ([f"trg_audit_{t}" for t in TABLES],),
        )
        assert cur.fetchone()[0] == len(TABLES)


# ── custodians are physical organizations (owner rule 2026-11-02, GDR-010 §2C) ──

ELIGIBLE = ["SAKHA_SANGHA", "SAKHA_ASANA", "PATHA_CHAKRA", "KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA"]
NON_ELIGIBLE = [
    "ANCHALIKA_SANGHA", "ZILLA_SANGHA", "KUMARI_SANGHA", "SEVAK_SANGHA", "MAHILA_SANGHA",
    "PARIBARIK_ASANA", "PARIBARIK_SANGHA", "ADVISORY_BOARD",
]
_SINGLETONS = {"KENDRA", "NILACHALA_KUTIRA", "SMRUTI_MANDIRA", "ADVISORY_BOARD"}


def _org_of_type(cur, type_code):
    """An active organization of *type_code*: the seeded row, else (non-singleton) a throwaway insert."""
    cur.execute(
        """
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = %s AND o.is_active = TRUE ORDER BY o.organization_pk LIMIT 1
        """,
        (type_code,),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])
    if type_code in _SINGLETONS:
        pytest.skip(f"No active {type_code} organization is seeded.")
    cur.execute(
        """
        INSERT INTO nss.organization (organization_name, organization_type_master_data_pk, status_master_data_pk)
        SELECT %s, t.master_data_pk, s.master_data_pk
        FROM nss.master_data t
        JOIN nss.master_category tc ON tc.master_category_pk = t.master_category_pk AND tc.category_code = 'ORGANIZATION_TYPE'
        JOIN nss.master_data s ON s.value_code = 'ACTIVE'
        JOIN nss.master_category sc ON sc.master_category_pk = s.master_category_pk AND sc.category_code = 'STATUS'
        WHERE t.value_code = %s
        RETURNING organization_pk
        """,
        (f"AP custodian test {uuid.uuid4().hex[:8]}", type_code),
    )
    return str(cur.fetchone()[0])


@pytest.mark.parametrize("type_code", ELIGIBLE)
def test_function_accepts_every_physical_type(write_conn, type_code):
    with write_conn.cursor() as cur:
        cur.execute("SELECT nss.fn_is_asset_custodian_org_type(%s)", (type_code,))
        assert cur.fetchone()[0] is True


@pytest.mark.parametrize("type_code", NON_ELIGIBLE + ["SOMETHING_ELSE", ""])
def test_function_refuses_everything_else(write_conn, type_code):
    with write_conn.cursor() as cur:
        cur.execute("SELECT nss.fn_is_asset_custodian_org_type(%s)", (type_code,))
        assert cur.fetchone()[0] is False


def test_function_is_false_for_null(write_conn):
    with write_conn.cursor() as cur:
        cur.execute("SELECT nss.fn_is_asset_custodian_org_type(NULL)")
        assert cur.fetchone()[0] is False


@pytest.mark.parametrize("type_code", NON_ELIGIBLE)
def test_trigger_refuses_non_eligible_custodian_on_insert(write_conn, ctx, type_code):
    with _savepoint(write_conn) as cur:
        org = _org_of_type(cur, type_code)
        p = _property(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation, match="physical organizations"):
            _custody(cur, property_pk=p, org=org)
    with _savepoint(write_conn) as cur:
        org = _org_of_type(cur, type_code)
        a = _asset(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation, match="physical organizations"):
            _custody(cur, asset_pk=a, org=org)


@pytest.mark.parametrize("type_code", ELIGIBLE)
def test_trigger_accepts_every_physical_custodian_on_insert(write_conn, ctx, type_code):
    with _savepoint(write_conn) as cur:
        org = _org_of_type(cur, type_code)
        assert _custody(cur, property_pk=_property(cur, ctx), org=org)


@pytest.mark.parametrize("type_code", NON_ELIGIBLE)
def test_trigger_refuses_repointing_custodian_to_non_eligible_on_update(write_conn, ctx, type_code):
    """UPDATE OF custodian_organization_pk is guarded too (the immutability guard would also refuse it;
    the eligibility trigger fires first by name and must hold on its own)."""
    with _savepoint(write_conn) as cur:
        org = _org_of_type(cur, type_code)
        c = _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_a"])
        # BEFORE row triggers fire in name order: trg_custodianship_custodian_guard
        # precedes trg_custodianship_guard (immutability), so ITS message surfaces.
        with pytest.raises(psycopg2.errors.CheckViolation, match="physical organizations"):
            cur.execute("UPDATE nss.custodianship SET custodian_organization_pk = %s WHERE custodianship_pk = %s", (org, c))


def test_trigger_does_not_block_unrelated_updates(write_conn, ctx):
    """Closing / annotating a custodianship (no change of custodian) never re-evaluates the organization type."""
    with _savepoint(write_conn) as cur:
        c = _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_a"])
        cur.execute("UPDATE nss.custodianship SET notes = 'still fine' WHERE custodianship_pk = %s", (c,))
        cur.execute(
            "UPDATE nss.custodianship SET status = 'ENDED', effective_to = '2026-03-01', end_reason_master_data_pk = %s "
            "WHERE custodianship_pk = %s",
            (ctx["end_reason"], c),
        )


# ── acquisition method (owner decision 2026-11-03, GDR-010 §2E) ─────────

@pytest.mark.parametrize("table", ["property", "asset"])
def test_acquisition_method_column_and_fk(write_conn, table):
    with write_conn.cursor() as cur:
        cur.execute(
            "SELECT is_nullable FROM information_schema.columns WHERE table_schema = 'nss' "
            "AND table_name = %s AND column_name = 'acquisition_method_master_data_pk'", (table,))
        row = cur.fetchone()
        assert row is not None and row[0] == "YES"
        cur.execute(
            "SELECT confrelid::regclass::text FROM pg_constraint WHERE conname = %s AND conrelid = %s::regclass AND contype = 'f'",
            (f"fk_{table}_acquisition_method", f"nss.{table}"))
        assert cur.fetchone()[0].endswith("master_data")


@pytest.mark.parametrize("table", ["property", "asset"])
def test_acquisition_method_rejects_unknown_master_data(write_conn, ctx, table):
    maker = _property if table == "property" else _asset
    with _savepoint(write_conn) as cur:
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            maker(cur, ctx, acquisition_method_master_data_pk=str(uuid.uuid4()))


@pytest.mark.parametrize("table", ["property", "asset"])
def test_acquisition_method_accepts_a_seeded_value(write_conn, ctx, table):
    maker = _property if table == "property" else _asset
    with _savepoint(write_conn) as cur:
        cur.execute(
            "SELECT md.master_data_pk FROM nss.master_data md JOIN nss.master_category mc "
            "ON mc.master_category_pk = md.master_category_pk WHERE mc.category_code = 'ACQUISITION_METHOD' "
            "AND md.value_code = 'PURCHASE'")
        pk = str(cur.fetchone()[0])
        assert maker(cur, ctx, acquisition_method_master_data_pk=pk)


# ── disposal / retirement closes custody (owner decision 2026-11-03, GDR-010 §2F) ──

@pytest.fixture
def terminal_reasons(write_conn):
    out = {}
    with write_conn.cursor() as cur:
        for code in ("DISPOSED", "RETIRED"):
            cur.execute(
                "SELECT md.master_data_pk FROM nss.master_data md JOIN nss.master_category mc "
                "ON mc.master_category_pk = md.master_category_pk "
                "WHERE mc.category_code = 'CUSTODIANSHIP_END_REASON' AND md.value_code = %s", (code,))
            row = cur.fetchone()
            if row is None:
                pytest.skip(f"CUSTODIANSHIP_END_REASON/{code} not seeded (reference-data patch missing).")
            out[code] = str(row[0])
    return out


def _end_custody(cur, custodianship_pk, reason_pk, on="2026-06-01"):
    cur.execute(
        "UPDATE nss.custodianship SET status = 'ENDED', effective_to = %s, end_reason_master_data_pk = %s "
        "WHERE custodianship_pk = %s", (on, reason_pk, custodianship_pk))


def test_property_terminal_transition_with_custody_close_passes_the_guards(write_conn, ctx, terminal_reasons):
    """The API ENDs the custody and sets DISPOSED in one transaction; neither guard objects (either order)."""
    for custody_first in (True, False):
        with _savepoint(write_conn) as cur:
            p = _property(cur, ctx)
            c = _custody(cur, property_pk=p, org=ctx["org_a"])
            cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))
            if custody_first:
                _end_custody(cur, c, terminal_reasons["DISPOSED"])
            cur.execute("UPDATE nss.property SET status = 'DISPOSED' WHERE property_pk = %s", (p,))
            if not custody_first:
                _end_custody(cur, c, terminal_reasons["DISPOSED"])
            cur.execute("SELECT status FROM nss.custodianship WHERE custodianship_pk = %s", (c,))
            assert cur.fetchone()[0] == "ENDED"


def test_asset_terminal_transition_with_custody_close_passes_the_guards(write_conn, ctx, terminal_reasons):
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        c = _custody(cur, asset_pk=a, org=ctx["org_a"])
        cur.execute("UPDATE nss.asset SET status = 'IN_CUSTODY' WHERE asset_pk = %s", (a,))
        _end_custody(cur, c, terminal_reasons["RETIRED"])
        cur.execute("UPDATE nss.asset SET status = 'RETIRED' WHERE asset_pk = %s", (a,))


def test_custody_required_rule_applies_only_when_leaving_registered(write_conn, ctx, terminal_reasons):
    """A DISPOSED property whose only custodianship is ENDED is fine: the rule is checked when leaving REGISTERED."""
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        c = _custody(cur, property_pk=p, org=ctx["org_a"])
        cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))
        _end_custody(cur, c, terminal_reasons["DISPOSED"])
        cur.execute("UPDATE nss.property SET status = 'DISPOSED' WHERE property_pk = %s", (p,))
    with _savepoint(write_conn) as cur:   # ...and it still bites when leaving REGISTERED with no custody at all
        p = _property(cur, ctx)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))


def test_ended_terminal_custodianship_stays_immutable(write_conn, ctx, terminal_reasons):
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        c = _custody(cur, property_pk=p, org=ctx["org_a"])
        cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))
        _end_custody(cur, c, terminal_reasons["DISPOSED"])
        cur.execute("UPDATE nss.property SET status = 'DISPOSED' WHERE property_pk = %s", (p,))
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE nss.custodianship SET notes = 'rewrite' WHERE custodianship_pk = %s", (c,))


def test_one_active_custodian_rule_unchanged(write_conn, ctx, terminal_reasons):
    """After the close, the partial unique index no longer counts the row (nothing is ACTIVE)."""
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        c = _custody(cur, property_pk=p, org=ctx["org_a"])
        _end_custody(cur, c, terminal_reasons["DISPOSED"])
        cur.execute("SELECT count(*) FROM nss.custodianship WHERE property_pk = %s AND status = 'ACTIVE'", (p,))
        assert cur.fetchone()[0] == 0


def test_terminal_records_refuse_new_custodianships(write_conn, ctx, terminal_reasons):
    """fn_custodianship_terminal_guard (AP-046/047)."""
    with _savepoint(write_conn) as cur:
        p = _property(cur, ctx)
        c = _custody(cur, property_pk=p, org=ctx["org_a"])
        cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))
        _end_custody(cur, c, terminal_reasons["DISPOSED"])
        cur.execute("UPDATE nss.property SET status = 'DISPOSED' WHERE property_pk = %s", (p,))
        with pytest.raises(psycopg2.errors.CheckViolation, match="AP-046"):
            _custody(cur, property_pk=p, org=ctx["org_b"])
    with _savepoint(write_conn) as cur:
        a = _asset(cur, ctx)
        c = _custody(cur, asset_pk=a, org=ctx["org_a"])
        cur.execute("UPDATE nss.asset SET status = 'IN_CUSTODY' WHERE asset_pk = %s", (a,))
        _end_custody(cur, c, terminal_reasons["RETIRED"])
        cur.execute("UPDATE nss.asset SET status = 'RETIRED' WHERE asset_pk = %s", (a,))
        with pytest.raises(psycopg2.errors.CheckViolation, match="AP-047"):
            _custody(cur, asset_pk=a, org=ctx["org_b"])


def test_live_records_still_accept_custodianships(write_conn, ctx):
    with _savepoint(write_conn) as cur:
        assert _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_a"])
        assert _custody(cur, asset_pk=_asset(cur, ctx), org=ctx["org_a"])


# ── idempotent patches (database/ddl/11_assets_property/11_*, 12_*) ──────

from pathlib import Path   # noqa: E402

_DDL_DIR = Path(__file__).resolve().parents[2] / "database" / "ddl" / "11_assets_property"


def test_terminal_custody_patch_closes_active_custody_and_is_idempotent(write_conn, ctx, terminal_reasons):
    """12_assets_property_terminal_custody_patch.sql: DML only, so the writer role can run it (twice)."""
    sql = (_DDL_DIR / "12_assets_property_terminal_custody_patch.sql").read_text()
    with _savepoint(write_conn) as cur:
        p, a = _property(cur, ctx), _asset(cur, ctx)
        pc = _custody(cur, property_pk=p, org=ctx["org_a"], effective_from="2026-01-01")
        ac = _custody(cur, asset_pk=a, org=ctx["org_a"], effective_from="2026-01-01")
        cur.execute("UPDATE nss.property SET status = 'ACTIVE' WHERE property_pk = %s", (p,))
        cur.execute("UPDATE nss.asset SET status = 'IN_CUSTODY' WHERE asset_pk = %s", (a,))
        cur.execute("UPDATE nss.property SET status = 'DISPOSED' WHERE property_pk = %s", (p,))   # legacy: custody left ACTIVE
        cur.execute("UPDATE nss.asset SET status = 'RETIRED' WHERE asset_pk = %s", (a,))
        # a live record's ACTIVE custody must be left alone
        live = _custody(cur, property_pk=_property(cur, ctx), org=ctx["org_b"])

        cur.execute(sql)
        cur.execute(
            "SELECT c.status, c.effective_to >= c.effective_from, er.value_code FROM nss.custodianship c "
            "JOIN nss.master_data er ON er.master_data_pk = c.end_reason_master_data_pk WHERE c.custodianship_pk = %s", (pc,))
        assert cur.fetchone() == ("ENDED", True, "DISPOSED")
        cur.execute(
            "SELECT c.status, c.effective_to >= c.effective_from, er.value_code FROM nss.custodianship c "
            "JOIN nss.master_data er ON er.master_data_pk = c.end_reason_master_data_pk WHERE c.custodianship_pk = %s", (ac,))
        assert cur.fetchone() == ("ENDED", True, "RETIRED")
        cur.execute("SELECT status FROM nss.custodianship WHERE custodianship_pk = %s", (live,))
        assert cur.fetchone()[0] == "ACTIVE"

        cur.execute(sql)                       # second run: nothing left to do, nothing raises
        cur.execute("SELECT status FROM nss.custodianship WHERE custodianship_pk IN (%s, %s)", (pc, ac))
        assert {r[0] for r in cur.fetchall()} == {"ENDED"}


def test_terminal_custody_patch_leaves_nothing_active_on_the_live_database(write_conn):
    with write_conn.cursor() as cur:
        cur.execute(
            """
            SELECT (SELECT COUNT(*) FROM nss.custodianship c JOIN nss.property p ON p.property_pk = c.property_pk
                    WHERE p.status = 'DISPOSED' AND c.status = 'ACTIVE' AND c.is_active)
                 + (SELECT COUNT(*) FROM nss.custodianship c JOIN nss.asset a ON a.asset_pk = c.asset_pk
                    WHERE a.status = 'RETIRED' AND c.status = 'ACTIVE' AND c.is_active)
            """
        )
        assert cur.fetchone()[0] == 0


@pytest.mark.parametrize("fname", [
    "10_assets_property_belongs_to_patch.sql", "11_assets_property_acquisition_method_patch.sql",
])
def test_ddl_patches_are_written_idempotently(fname):
    """The writer role cannot run DDL, so check the patch text: every statement is guarded."""
    import re
    sql = (_DDL_DIR / fname).read_text()
    code = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    assert "ADD COLUMN IF NOT EXISTS" in code
    assert not re.search(r"ALTER TABLE[^;]*ADD CONSTRAINT[^;]*;", code.split("DO $$")[0]), "constraints must sit in the guarded DO block"
    assert "IF NOT EXISTS (SELECT 1 FROM pg_constraint" in code
    for stmt in re.findall(r"CREATE (?:UNIQUE )?INDEX [^\n]*", code):
        assert "IF NOT EXISTS" in stmt, stmt
    assert not re.search(r"\bDROP\b|\bDELETE\b|\bTRUNCATE\b", code)
