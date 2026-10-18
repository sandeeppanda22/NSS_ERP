-- =====================================================
-- NSS ERP
-- Module: Administration (Correspondence Register capability)
-- File: 03_correspondence_finance_reference.sql
-- Table: nss.correspondence_finance_reference
-- Depth: 5 (depends on correspondence and master_data;
--          financial_transaction FK deferred — Finance module not
--          yet built)
-- Version: 1.1 — relationship_type resolved to a master_data FK
--          (owner-confirmed 2026-10-17; see note below)
-- Authority: SOL-ADMIN-009 §6, FIN-ARCH-001 (Finance remains
--            authoritative owner of financial_transaction;
--            Administration only records the relationship)
-- Owner: Administration
--
-- Design decisions:
--   - financial_transaction_pk is a plain UUID column with NO FK
--     constraint in Pass 1, because nss.financial_transaction does
--     not exist yet (Finance is Tier 12). This mirrors the project's
--     two-pass pattern already used for audit-actor FKs
--     (SOL-ADMIN-009 §6.8, §7.2; DDL_CREATION_ORDER.md §5.2).
--     Application-layer validation enforces referential correctness
--     until the constraint below is added.
--
--     Pass 2 (run once nss.financial_transaction exists):
--         ALTER TABLE nss.correspondence_finance_reference
--             ADD CONSTRAINT fk_corr_fin_ref_transaction
--             FOREIGN KEY (financial_transaction_pk)
--             REFERENCES nss.financial_transaction (financial_transaction_pk);
--
--   - relationship_type enforcement is RESOLVED (owner-confirmed
--     2026-10-17; SOL-ADMIN-009 §6.5, §12, §14): implemented as a
--     master_data FK (relationship_type_master_data_pk), consistent
--     with the sibling controlled-value columns on correspondence
--     itself (medium_master_data_pk, status_master_data_pk) and the
--     project's Configuration Over Hardcoding principle — new
--     relationship types (beyond the six seeded below) can be added
--     via master_data without a DDL change. Values seeded under
--     master_category CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE
--     (database/seed/01_foundation/01_master_category.sql,
--     02_master_data.sql): PAYMENT, RECEIPT, REFUND, TAX, ADJUSTMENT,
--     OTHER.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE columns
--       included in Pass 1. Their FK constraints are deferred to
--       Pass 2, per project-wide two-pass DDL convention.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.correspondence_finance_reference
(
    -- ── Identity ────────────────────────────────────────

    correspondence_finance_reference_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    correspondence_pk UUID NOT NULL,

    -- No FK yet — see Pass 2 note above (financial_transaction
    -- does not exist until Finance/Tier 12 is built).
    financial_transaction_pk UUID NOT NULL,

    -- Enforcement RESOLVED — master_data FK (owner-confirmed
    -- 2026-10-17; see header note). Values seeded under
    -- master_category CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE.
    relationship_type_master_data_pk UUID NOT NULL,

    remarks TEXT NULL,

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

    -- ── Foreign Keys ────────────────────────────────────

    CONSTRAINT fk_corr_fin_ref_correspondence
        FOREIGN KEY (correspondence_pk)
        REFERENCES nss.correspondence (correspondence_pk),

    CONSTRAINT fk_corr_fin_ref_relationship_type
        FOREIGN KEY (relationship_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    -- fk_corr_fin_ref_transaction added in Pass 2 (see header note).

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_corr_fin_ref_correspondence_transaction_type
        UNIQUE (correspondence_pk, financial_transaction_pk, relationship_type_master_data_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_corr_fin_ref_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_corr_fin_ref_correspondence
    ON nss.correspondence_finance_reference (correspondence_pk);

CREATE INDEX IF NOT EXISTS idx_corr_fin_ref_transaction
    ON nss.correspondence_finance_reference (financial_transaction_pk);

CREATE INDEX IF NOT EXISTS idx_corr_fin_ref_relationship_type
    ON nss.correspondence_finance_reference (relationship_type_master_data_pk);

CREATE INDEX IF NOT EXISTS idx_corr_fin_ref_active
    ON nss.correspondence_finance_reference (is_active);
