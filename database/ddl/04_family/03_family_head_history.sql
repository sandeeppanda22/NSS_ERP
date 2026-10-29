-- =====================================================
-- NSS ERP
-- Module: Family
-- File: 03_family_head_history.sql
-- Table: nss.family_head_history
-- Depth: 3 (depends on family_group, person)
-- Version: 1.0
-- Authority: SOL-FAM-005 §8–§9, SOL-FAM-003
--            FAM-009, FAM-010
-- Owner: NSS_ERP_ADMIN
-- Note: Historical records are never deleted
--       (FAM-028). Only one active head per family
--       at any time, enforced by partial unique index.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.family_head_history
(
    -- ── Identity ────────────────────────────────────────

    family_head_history_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Relationships ───────────────────────────────────

    family_group_pk UUID NOT NULL,

    person_pk UUID NOT NULL,

    -- ── Effective Period ────────────────────────────────

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    -- ── Details ─────────────────────────────────────────

    reason VARCHAR(500) NULL,

    remarks TEXT NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT fk_family_head_family_group
        FOREIGN KEY (family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT fk_family_head_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT chk_family_head_effective_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_family_head_family_group
    ON nss.family_head_history (family_group_pk);

CREATE INDEX IF NOT EXISTS idx_family_head_person
    ON nss.family_head_history (person_pk);

-- Only one current (active) head per family group.
CREATE UNIQUE INDEX IF NOT EXISTS uq_family_head_current
    ON nss.family_head_history (family_group_pk)
    WHERE effective_to IS NULL;
