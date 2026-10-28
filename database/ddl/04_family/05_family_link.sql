-- =====================================================
-- NSS ERP
-- Module: Family
-- File: 05_family_link.sql
-- Table: nss.family_link
-- Depth: 3 (depends on family_group, person)
-- Version: 1.1 — added SIBLING_OF link_type (owner decision, 2026-10-22);
--          see the link_type semantics note below.
-- Version: 1.0
-- Authority: ERP-DECISION — Graph-based dynamic
--            relationship model
-- Owner: NSS_ERP_ADMIN
-- Note: Stores only direct biological/legal edges
--       between family members. All extended
--       relationships (grandfather, uncle, cousin,
--       etc.) are computed dynamically via graph
--       traversal relative to the viewer.
--
--       link_type semantics:
--         PARENT_OF  — person_a is parent of person_b
--                      (directed)
--         SPOUSE_OF  — person_a and person_b are spouses
--                      (bidirectional; store one row)
--         SIBLING_OF — person_a and person_b are siblings
--                      (bidirectional; store one row).
--                      Added 2026-10-22 (owner decision):
--                      a member adding a Brother/Sister via
--                      the dashboard previously only got a
--                      family_relationship row — with no
--                      family_link edge when they had no
--                      parent yet in the graph, they were
--                      invisible in the tree view. SIBLING_OF
--                      lets a direct sibling edge be created
--                      without requiring a parent first.
--                      Symmetric like SPOUSE_OF, not
--                      directional like PARENT_OF — same
--                      "store one row, either direction"
--                      convention. See api/services/
--                      family_graph.py for how a SIBLING_OF
--                      edge is labelled (and how it composes
--                      with shared-parent-derived sibling
--                      paths without double-counting).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.family_link
(
    -- ── Identity ────────────────────────────────────────

    family_link_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Relationships ───────────────────────────────────

    family_group_pk UUID NOT NULL,

    -- The "from" person in the directed edge
    person_a_pk UUID NOT NULL,

    -- The "to" person in the directed edge
    person_b_pk UUID NOT NULL,

    -- PARENT_OF, SPOUSE_OF or SIBLING_OF — see header note
    link_type VARCHAR(20) NOT NULL,

    -- ── Effective Period ────────────────────────────────

    effective_from DATE NOT NULL,

    effective_to DATE NULL,

    is_current BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT fk_family_link_family_group
        FOREIGN KEY (family_group_pk)
        REFERENCES nss.family_group (family_group_pk),

    CONSTRAINT fk_family_link_person_a
        FOREIGN KEY (person_a_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_family_link_person_b
        FOREIGN KEY (person_b_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT chk_family_link_type
        CHECK (link_type IN ('PARENT_OF', 'SPOUSE_OF', 'SIBLING_OF')),

    CONSTRAINT chk_family_link_no_self
        CHECK (person_a_pk <> person_b_pk),

    CONSTRAINT chk_family_link_effective_range
        CHECK
        (
            effective_to IS NULL
            OR effective_to >= effective_from
        ),

    CONSTRAINT chk_family_link_current_consistency
        CHECK
        (
            (is_current = TRUE AND effective_to IS NULL)
            OR
            (is_current = FALSE AND effective_to IS NOT NULL)
        )
);

-- Idempotent safety net: on a database bootstrapped before SIBLING_OF was
-- added, CREATE TABLE IF NOT EXISTS above is a no-op (the table already
-- exists), so chk_family_link_type would still only allow PARENT_OF/
-- SPOUSE_OF. This ALTER guarantees the widened CHECK either way. NOTE:
-- under this project's existence-gated build (run_ddl / Invoke-Ddl — see
-- database/scripts/02_build.sh), the ENTIRE file is skipped once
-- nss.family_link already exists, so this ALTER (like the CREATE TABLE
-- above it) will NOT run on an already-bootstrapped environment either —
-- a full hard rebuild is required there. This safety net only protects a
-- genuinely fresh install.
ALTER TABLE nss.family_link
    DROP CONSTRAINT IF EXISTS chk_family_link_type;
ALTER TABLE nss.family_link
    ADD CONSTRAINT chk_family_link_type
        CHECK (link_type IN ('PARENT_OF', 'SPOUSE_OF', 'SIBLING_OF'));

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_family_link_family_group
    ON nss.family_link (family_group_pk);

CREATE INDEX IF NOT EXISTS idx_family_link_person_a
    ON nss.family_link (person_a_pk);

CREATE INDEX IF NOT EXISTS idx_family_link_person_b
    ON nss.family_link (person_b_pk);

CREATE INDEX IF NOT EXISTS idx_family_link_is_current
    ON nss.family_link (is_current);

-- A given directed edge should not be duplicated
-- while current.
CREATE UNIQUE INDEX IF NOT EXISTS uq_family_link_current
    ON nss.family_link (family_group_pk, person_a_pk, person_b_pk, link_type)
    WHERE is_current = TRUE;
