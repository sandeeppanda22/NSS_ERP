-- =====================================================
-- NSS ERP
-- Module: Administration (Correspondence Register capability)
-- File: 04_correspondence_sequence_counter.sql
-- Table: nss.correspondence_sequence_counter
-- Depth: 1 (depends only on organization)
-- Version: 1.0
-- Authority: CORR-EXT-001 (reference-number format
--            <ORG_SHORT_CODE>/{IN|OUT}/YYYY-YY/NNN, per-organization,
--            per-direction, per-financial-year sequence),
--            SOL-ADMIN-009 §4.9
-- Owner: Administration
--
-- Design: mirrors nss.credential_sequence_counter
-- (database/ddl/05_membership/15_credential_sequence_counter.sql) —
-- the project's existing FY-scoped sequence-counter template — with
-- "credential_type" replaced by "direction" and "scope_organization_pk"
-- replaced by "register_organization_pk". Unlike
-- nss.sakha_local_number_counter (permanent, never resets),
-- correspondence reference numbers reset every financial year
-- (CORR-EXT-001 §3.2 "Annual Period"), so the credential_sequence_counter
-- shape — not the sakha_local_number_counter shape — is the correct fit.
--
-- One row per (register_organization_pk, direction, financial_year_start):
-- current_value is atomically incremented by
-- api/helpers.py::next_correspondence_reference_number() on every new
-- correspondence record, via INSERT ... ON CONFLICT ... DO UPDATE
-- SET current_value = current_value + 1 RETURNING current_value.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.correspondence_sequence_counter
(
    -- ── Identity ────────────────────────────────────────

    correspondence_sequence_counter_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- Owns the sequence: the register (organization) a correspondence
    -- record is filed under (nss.correspondence.register_organization_pk).
    register_organization_pk UUID NOT NULL,

    direction VARCHAR(10) NOT NULL,

    -- India financial year start (1 April). Matches
    -- credential_sequence_counter.financial_year_start exactly, so
    -- api/helpers.py::financial_year_bounds() is reused as-is.
    financial_year_start INTEGER NOT NULL,

    current_value INTEGER NOT NULL
        DEFAULT 0,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    -- ── Foreign Keys ────────────────────────────────────

    CONSTRAINT fk_corr_seq_counter_organization
        FOREIGN KEY (register_organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_corr_seq_counter_org_direction_fy
        UNIQUE (register_organization_pk, direction, financial_year_start),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_corr_seq_counter_direction
        CHECK (direction IN ('INWARD', 'OUTWARD')),

    CONSTRAINT chk_corr_seq_counter_fy
        CHECK (financial_year_start >= 2000)
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_corr_seq_counter_organization
    ON nss.correspondence_sequence_counter (register_organization_pk);
