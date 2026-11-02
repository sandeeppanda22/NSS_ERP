-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 01_body_type_master.sql
-- Table: nss.body_type_master
-- Depth: 0 (no governance FK dependencies)
-- Version: 1.1 — added max_members (DB-level seat-count backstop,
--          2026-10-21); see Design decisions below.
-- Version: 1.0
-- Authority: SOL-GOV-002 §4-5, SOL-GOV-004 §5,
--            GOV-BR-003/006, DDL_CREATION_ORDER (SOL-ARCH-010) #11
-- Owner: Governance
--
-- Design decisions:
--   - Classification master for governance bodies
--     (KENDRA_GOVERNING_BODY, SAKHA_GOVERNING_BODY,
--     ADVISORY_BOARD, MAHILA_PARICHALANA_MANDALI,
--     SEVAK_SANGHA_EXECUTIVE, COMMITTEE, ...)
--   - body_type_code stable + UNIQUE (GOV-BR-006, §5.5)
--   - Own master table (like role_master), NOT a
--     master_data category — matches frozen DDL order #11
--   - Historically-used types are soft-deleted, never
--     physically removed (§5.6, GOV-BR-063)
--   - max_members (added 2026-10-21, DB-level seat-count
--     backstop behind api/routers/governance.py's
--     _COMPOSITION_RULES/_resolve_seat_limit; enforced by
--     nss.fn_enforce_body_seat_limit() in
--     12_governance_seat_limits.sql): the flat total-seat
--     cap for this body type, where one applies as a single
--     constant — KENDRA_GOVERNING_BODY=9,
--     SAKHA_GOVERNING_BODY=9, SEVAK_SANGHA_EXECUTIVE=3,
--     ANCHALIKA_GOVERNING_BODY=3, ZILLA_GOVERNING_BODY=3,
--     PATHA_CHAKRA_GOVERNING_BODY=3 (seeded in
--     seed/08_governance/01_body_type_master.sql). Left NULL
--     for two body types whose real limit cannot be expressed
--     as one constant on this table:
--       - MAHILA_PARICHALANA_MANDALI: 8 directly-assignable
--         seats at Kendra level (organization_pk IS NULL on
--         the owning body_master row) vs 3 at Sakha level
--         (organization_pk IS NOT NULL) — same body_type, two
--         limits by org-nullness. The trigger derives the
--         right one from body_master.organization_pk at
--         write time.
--       - ADVISORY_BOARD: one seat per active Sakha Sangha
--         (SAKHA_COUNT in _resolve_seat_limit) — not a fixed
--         number at all; the trigger enforces the real
--         "one seat per Sakha" rule instead of a flat count.
--     NULL for any other/future body type simply means no
--     DB-level cap is enforced (unchanged behaviour).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are
--       NULLABLE columns included in Pass 1. Their FK
--       constraints are deferred to Pass 2.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.body_type_master
(
    -- ── Identity ────────────────────────────────────────

    body_type_master_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    body_type_code VARCHAR(50) NOT NULL,

    -- ── Attributes ──────────────────────────────────────

    body_type_name VARCHAR(150) NOT NULL,

    description TEXT NULL,

    -- Flat total-seat cap for this body type; NULL when no single
    -- constant applies (MAHILA_PARICHALANA_MANDALI, ADVISORY_BOARD —
    -- see the header note). Enforced by
    -- nss.fn_enforce_body_seat_limit() (12_governance_seat_limits.sql).
    max_members INTEGER NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_body_type_master_code
        UNIQUE (body_type_code),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_body_type_master_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        ),

    CONSTRAINT chk_body_type_master_max_members
        CHECK (max_members IS NULL OR max_members > 0)
);

-- Idempotent safety net: tables created before max_members was added
-- to the CREATE TABLE above (e.g. a database bootstrapped before this
-- DDL change) never get it via CREATE TABLE IF NOT EXISTS alone, since
-- that clause makes the whole statement a no-op when the table already
-- exists. This ALTER guarantees the column exists either way. NOTE:
-- under this project's existence-gated build (run_ddl / Invoke-Ddl —
-- see database/scripts/02_build.sh), the ENTIRE file is skipped once
-- nss.body_type_master already exists, so this ALTER (like the CREATE
-- TABLE above it) will NOT run on an already-bootstrapped environment
-- either — a full hard rebuild is required there. This safety net only
-- protects a genuinely fresh install.
ALTER TABLE nss.body_type_master
    ADD COLUMN IF NOT EXISTS max_members INTEGER NULL;

ALTER TABLE nss.body_type_master
    DROP CONSTRAINT IF EXISTS chk_body_type_master_max_members;
ALTER TABLE nss.body_type_master
    ADD CONSTRAINT chk_body_type_master_max_members
        CHECK (max_members IS NULL OR max_members > 0);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_body_type_master_active
    ON nss.body_type_master (is_active);
