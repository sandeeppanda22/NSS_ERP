"""
NSS ERP — DB schema tests for the Correspondence Register capability
(Administration; SOL-ADMIN-009, CORR-DECISION-003).

Guards the structural invariants of the three correspondence tables that
the register feature relies on:

  - nss.correspondence: register_organization_pk NOT NULL + FK (CORR-BR-003 /
    CORR-EXT-001 — whose register / admin-scope boundary); direction,
    sender_type, recipient_type CHECKs; the sender / recipient conditional-
    integrity compound CHECKs (exactly one of person / organization /
    external per party, SOL-ADMIN-009 §4.6); the sender person-detail
    consistency CHECKs (capacity / sender_person_organization_pk /
    sakha snapshot only when sender_type = 'PERSON', owner-confirmed
    2026-10-17); reference_number UNIQUE; soft-delete CHECK.
  - nss.correspondence_document: document_purpose CHECK, the
    (correspondence, document, purpose) UNIQUE, FKs, soft-delete CHECK.
  - nss.correspondence_finance_reference: relationship_type resolved to a
    master_data FK (owner-confirmed 2026-10-17, SOL-ADMIN-009 §6.5) backed
    by the CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE category seed
    (PAYMENT / RECEIPT / REFUND / TAX / ADJUSTMENT / OTHER); the
    (correspondence, transaction, relationship_type) UNIQUE; soft-delete
    CHECK. financial_transaction_pk is a plain UUID with no FK yet
    (Pass 2, Finance/Tier 12) — not asserted here.

Fresh builds seed no Person/Family/Membership data, so the behaviour
tests use EXTERNAL sender/recipient (free text, no person/org FK) for a
dependency-free valid baseline, a real seeded organization for
register_organization_pk, and any seeded master_data row for the
medium/status FKs (the schema puts no category CHECK on those columns).
Throwaway rows are inserted/rolled back inside their own SAVEPOINTs so
the seed-less test DB is left untouched.
"""

import uuid

import psycopg2
import pytest


pytestmark = [pytest.mark.db, pytest.mark.integration]


# ── Schema-introspection helper (mirrors tests/db/test_festival_schema.py) ──

def _constraint_exists(conn, name):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'nss' AND c.conname = %s
            """,
            (name,),
        )
        return cur.fetchone() is not None


# ── UNIQUE / CHECK / FK constraints across the three tables ─────────────

@pytest.mark.parametrize("constraint", [
    # correspondence — foreign keys
    "fk_correspondence_register_organization",
    "fk_correspondence_sender_person",
    "fk_correspondence_sender_organization",
    "fk_correspondence_sender_person_organization",
    "fk_correspondence_recipient_person",
    "fk_correspondence_recipient_organization",
    "fk_correspondence_responsible_person",
    "fk_correspondence_responsible_organization",
    "fk_correspondence_medium",
    "fk_correspondence_status",
    # correspondence — unique / check
    "uq_correspondence_reference_number",
    "chk_correspondence_direction",
    "chk_correspondence_sender_type",
    "chk_correspondence_recipient_type",
    "chk_correspondence_sender_person_capacity",
    "chk_correspondence_sender_person_detail_consistency",
    "chk_correspondence_sender_person_capacity_org",
    "chk_correspondence_sender_consistency",
    "chk_correspondence_recipient_consistency",
    "chk_correspondence_soft_delete",
    # correspondence_document
    "fk_corr_doc_correspondence",
    "fk_corr_doc_document",
    "uq_corr_doc_correspondence_document_purpose",
    "chk_corr_doc_purpose",
    "chk_corr_doc_soft_delete",
    # correspondence_finance_reference
    "fk_corr_fin_ref_correspondence",
    "fk_corr_fin_ref_relationship_type",
    "uq_corr_fin_ref_correspondence_transaction_type",
    "chk_corr_fin_ref_soft_delete",
])
def test_correspondence_constraint_exists(write_conn, constraint):
    assert _constraint_exists(write_conn, constraint), (
        f"Expected constraint nss.{constraint} to exist"
    )


# ── relationship_type seed presence (master_data FK, owner-confirmed) ───

def test_relationship_type_values_seeded(write_conn):
    """
    The six CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE values must be seeded
    under their master_category — this is what the resolved
    relationship_type_master_data_pk FK points at.
    """
    cur = write_conn.cursor()
    cur.execute(
        """
        SELECT md.value_code
        FROM nss.master_data md
        JOIN nss.master_category mc
          ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE'
        """
    )
    seeded = {r[0] for r in cur.fetchall()}
    assert seeded == {
        "PAYMENT", "RECEIPT", "REFUND", "TAX", "ADJUSTMENT", "OTHER",
    }, f"Unexpected relationship_type seed set: {seeded}"


# ── Shared valid-FK context + a single baseline-row inserter (no repeats) ──

@pytest.fixture
def ctx(write_conn):
    """
    Resolves the FK targets a valid correspondence row needs:
      - a real seeded organization (register_organization_pk),
      - any seeded master_data row (medium / status — no category CHECK),
      - the PAYMENT relationship_type master_data row.
    Skips the module cleanly if the expected seed data is absent.
    """
    cur = write_conn.cursor()

    cur.execute("SELECT organization_pk FROM nss.organization LIMIT 1")
    org = cur.fetchone()
    if org is None:
        pytest.skip("No seeded organization available for register_organization_pk.")

    cur.execute("SELECT master_data_pk FROM nss.master_data LIMIT 1")
    md = cur.fetchone()
    if md is None:
        pytest.skip("No seeded master_data row available for medium/status FKs.")

    cur.execute(
        """
        SELECT md.master_data_pk
        FROM nss.master_data md
        JOIN nss.master_category mc
          ON mc.master_category_pk = md.master_category_pk
        WHERE mc.category_code = 'CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE'
          AND md.value_code = 'PAYMENT'
        """
    )
    rel = cur.fetchone()
    if rel is None:
        pytest.skip("PAYMENT relationship_type not seeded.")

    return {
        "org_pk": str(org[0]),
        "md_pk": str(md[0]),
        "payment_pk": str(rel[0]),
    }


# Column order used by _insert_correspondence; the baseline is a valid
# EXTERNAL -> EXTERNAL inward letter. Negative tests pass overrides.
_CORR_COLUMNS = (
    "register_organization_pk", "reference_number", "direction",
    "correspondence_date", "received_or_sent_date", "subject",
    "sender_type", "sender_person_pk", "sender_organization_pk",
    "sender_external_name", "sender_person_capacity",
    "sender_person_organization_pk", "sender_sakha_erp_id_snapshot",
    "recipient_type", "recipient_person_pk", "recipient_organization_pk",
    "recipient_external_name", "medium_master_data_pk",
    "status_master_data_pk", "is_active", "deleted_at",
)


def _insert_correspondence(cur, ctx, reference_number, **overrides):
    """
    Insert one correspondence row and return its PK. A valid baseline is
    merged with `overrides` so each test states only the field it is
    probing — no repeated column lists.
    """
    row = {
        "register_organization_pk": ctx["org_pk"],
        "reference_number": reference_number,
        "direction": "INWARD",
        "correspondence_date": "2026-04-01",
        "received_or_sent_date": "2026-04-01",
        "subject": "Schema test correspondence",
        "sender_type": "EXTERNAL",
        "sender_person_pk": None,
        "sender_organization_pk": None,
        "sender_external_name": "External Sender",
        "sender_person_capacity": None,
        "sender_person_organization_pk": None,
        "sender_sakha_erp_id_snapshot": None,
        "recipient_type": "EXTERNAL",
        "recipient_person_pk": None,
        "recipient_organization_pk": None,
        "recipient_external_name": "External Recipient",
        "medium_master_data_pk": ctx["md_pk"],
        "status_master_data_pk": ctx["md_pk"],
        "is_active": True,
        "deleted_at": None,
    }
    row.update(overrides)
    placeholders = ", ".join(f"%({c})s" for c in _CORR_COLUMNS)
    columns = ", ".join(_CORR_COLUMNS)
    cur.execute(
        f"INSERT INTO nss.correspondence ({columns}) "
        f"VALUES ({placeholders}) RETURNING correspondence_pk",
        row,
    )
    return str(cur.fetchone()[0])


# ── correspondence: valid baseline + CHECK / UNIQUE behaviour ───────────

def test_valid_correspondence_row_inserts(write_conn, ctx):
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_valid_corr")
    pk = _insert_correspondence(cur, ctx, "KEN/IN/2026-27/001")
    assert pk
    cur.execute("ROLLBACK TO SAVEPOINT sp_valid_corr")


def test_bad_direction_rejected(write_conn, ctx):
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_dir")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_correspondence(cur, ctx, "KEN/IN/2026-27/002", direction="SIDEWAYS")
    cur.execute("ROLLBACK TO SAVEPOINT sp_dir")


def test_bad_sender_type_rejected(write_conn, ctx):
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_stype")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_correspondence(
            cur, ctx, "KEN/IN/2026-27/003",
            sender_type="ROBOT", sender_external_name="x",
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_stype")


def test_person_sender_without_person_pk_rejected(write_conn, ctx):
    """chk_correspondence_sender_consistency: a PERSON sender must carry
    sender_person_pk and no external/org fields."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_sender_consistency")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_correspondence(
            cur, ctx, "KEN/IN/2026-27/004",
            sender_type="PERSON",
            sender_person_pk=None,
            sender_external_name=None,
            # a PERSON sender needs a capacity, but no person_pk is set,
            # so the consistency CHECK must still reject it.
            sender_person_capacity="PERSONAL",
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_sender_consistency")


def test_non_person_sender_with_person_capacity_rejected(write_conn, ctx):
    """chk_correspondence_sender_person_detail_consistency: an ORGANIZATION
    or EXTERNAL sender must leave the person-detail columns NULL."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_detail_consistency")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_correspondence(
            cur, ctx, "KEN/IN/2026-27/005",
            sender_type="EXTERNAL",
            sender_external_name="External Sender",
            sender_person_capacity="PERSONAL",   # not allowed for EXTERNAL
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_detail_consistency")


def test_organizational_capacity_without_org_rejected(write_conn, ctx):
    """chk_correspondence_sender_person_capacity_org: ORGANIZATIONAL capacity
    requires sender_person_organization_pk to be set."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_cap_org")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_correspondence(
            cur, ctx, "KEN/IN/2026-27/006",
            sender_type="PERSON",
            sender_person_pk=str(uuid.uuid4()),      # satisfies consistency shape
            sender_external_name=None,
            sender_person_capacity="ORGANIZATIONAL",
            sender_person_organization_pk=None,       # <- the violation
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_cap_org")


def test_duplicate_reference_number_rejected(write_conn, ctx):
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_refnum")
    _insert_correspondence(cur, ctx, "KEN/IN/2026-27/010")
    cur.execute("RELEASE SAVEPOINT sp_refnum")

    cur.execute("SAVEPOINT sp_refnum_dup")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _insert_correspondence(cur, ctx, "KEN/IN/2026-27/010")
    cur.execute("ROLLBACK TO SAVEPOINT sp_refnum_dup")


def test_soft_delete_check_rejects_inactive_without_timestamp(write_conn, ctx):
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_softdel")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_correspondence(
            cur, ctx, "KEN/IN/2026-27/011",
            is_active=False, deleted_at=None,
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_softdel")


# ── correspondence_finance_reference: relationship_type FK + UNIQUE ─────

def test_finance_reference_valid_payment_inserts(write_conn, ctx):
    """End-to-end: the resolved master_data FK accepts a real PAYMENT PK."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_fin_valid")
    corr_pk = _insert_correspondence(cur, ctx, "KEN/IN/2026-27/020")
    cur.execute(
        """
        INSERT INTO nss.correspondence_finance_reference
            (correspondence_pk, financial_transaction_pk,
             relationship_type_master_data_pk)
        VALUES (%s, %s, %s)
        """,
        (corr_pk, str(uuid.uuid4()), ctx["payment_pk"]),
    )
    cur.execute("ROLLBACK TO SAVEPOINT sp_fin_valid")


def test_finance_reference_bad_relationship_type_rejected(write_conn, ctx):
    """fk_corr_fin_ref_relationship_type: a random UUID is not a master_data
    row and must be rejected."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_fin_fk")
    corr_pk = _insert_correspondence(cur, ctx, "KEN/IN/2026-27/021")
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            """
            INSERT INTO nss.correspondence_finance_reference
                (correspondence_pk, financial_transaction_pk,
                 relationship_type_master_data_pk)
            VALUES (%s, %s, %s)
            """,
            (corr_pk, str(uuid.uuid4()), str(uuid.uuid4())),
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_fin_fk")


def test_finance_reference_duplicate_rejected(write_conn, ctx):
    """uq_corr_fin_ref_correspondence_transaction_type: same correspondence +
    transaction + relationship_type cannot be referenced twice."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_fin_dup")
    corr_pk = _insert_correspondence(cur, ctx, "KEN/IN/2026-27/022")
    txn_pk = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO nss.correspondence_finance_reference
            (correspondence_pk, financial_transaction_pk,
             relationship_type_master_data_pk)
        VALUES (%s, %s, %s)
        """,
        (corr_pk, txn_pk, ctx["payment_pk"]),
    )
    cur.execute("RELEASE SAVEPOINT sp_fin_dup")

    cur.execute("SAVEPOINT sp_fin_dup_2")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute(
            """
            INSERT INTO nss.correspondence_finance_reference
                (correspondence_pk, financial_transaction_pk,
                 relationship_type_master_data_pk)
            VALUES (%s, %s, %s)
            """,
            (corr_pk, txn_pk, ctx["payment_pk"]),
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_fin_dup_2")


# ── correspondence_document: document_purpose CHECK ─────────────────────

def test_document_bad_purpose_rejected(write_conn, ctx):
    """chk_corr_doc_purpose: document_purpose is a fixed small set."""
    cur = write_conn.cursor()
    cur.execute("SAVEPOINT sp_doc_purpose")
    corr_pk = _insert_correspondence(cur, ctx, "KEN/IN/2026-27/030")
    cur.execute(
        """
        INSERT INTO nss.document_master
            (document_type_code, document_name, storage_path)
        VALUES ('CORRESPONDENCE', 'Schema test doc', '/tmp/schema-test')
        RETURNING document_master_pk
        """
    )
    doc_pk = str(cur.fetchone()[0])
    with pytest.raises(psycopg2.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO nss.correspondence_document
                (correspondence_pk, document_master_pk, document_purpose)
            VALUES (%s, %s, %s)
            """,
            (corr_pk, doc_pk, "BOGUS"),
        )
    cur.execute("ROLLBACK TO SAVEPOINT sp_doc_purpose")
