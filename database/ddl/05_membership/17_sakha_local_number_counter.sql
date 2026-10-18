-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 17_sakha_local_number_counter.sql
-- Table: nss.sakha_local_number_counter
-- Depth: 3 (depends on organization)
-- Version: 1.0
-- Authority: MBR-030, MBR-030C, MBR-048
-- Owner: NSS_ERP_ADMIN
--
-- Note: Backs api/helpers.py::next_sakha_local_number(), which resolves
--       MBR-030C's "AUTO-SEQUENCING PENDING" status: per-Sakha,
--       per-namespace counter infrastructure for the Tier 2 Local Sakha
--       ERP Number now exists.
--
--       One row per (organization_pk, namespace) — REGULAR or DARSHAK,
--       the same two namespaces compose_local_sakha_erp_id() already
--       composes into the identifier string (short_code vs.
--       short_code+marker). The counter itself holds only the bare,
--       unmarked numeric sequence; the marker is applied at composition
--       time, not stored here.
--
--       Design decisions:
--         - Deliberately NOT a shared pattern with credential_sequence_
--           counter (05_membership/15): that counter is scoped by
--           financial year and resets every 1 April, because Kendra/
--           Anumati document numbers ARE annual (MBR-030A). A Local
--           Sakha ERP Number is permanent and never reassigned
--           (MBR-030, MBR-022) — so this counter carries NO financial-
--           year column and NEVER resets. This is the one deliberate
--           difference from the credential_sequence_counter shape.
--         - current_value is the last number issued, not the next one
--           (same convention as credential_sequence_counter) — callers
--           read the post-increment RETURNING value.
--         - No zero-padding: current_value is used as a plain integer,
--           formatted as-is by the caller (e.g. ESS1, ESS2 — never
--           ESS000001), per the project-wide loosened padding_length
--           decision already in force for every other business
--           identifier in this module (see 05_membership/README.md
--           "No zero-padding on any business identifier in this
--           module").
--         - Rows are created on demand (upsert), not pre-seeded —
--           there is no fixed list of (organization, namespace)
--           combinations to seed; every Sakha gets its own REGULAR and
--           DARSHAK counters the first time either namespace is used.
--         - This counter mints the number used ONLY when a caller does
--           NOT supply an explicit local_number (see
--           api/helpers.py::insert_sakha_affiliation()'s local_number
--           parameter) — manual/legacy-import entry still bypasses this
--           table entirely, by design, so a legacy register number can
--           be preserved verbatim without colliding with or advancing
--           the auto-sequence.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.sakha_local_number_counter
(
    sakha_local_number_counter_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- The Sakha this counter belongs to.
    organization_pk UUID NOT NULL,

    -- REGULAR (Regular/Associate namespace) or DARSHAK
    -- (Darshak/Probationary namespace, MBR-030C).
    namespace VARCHAR(20) NOT NULL,

    current_value INTEGER NOT NULL
        DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_sakha_local_number_counter_org
        FOREIGN KEY (organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT chk_sakha_local_number_counter_namespace
        CHECK (namespace IN ('REGULAR', 'DARSHAK')),

    CONSTRAINT uq_sakha_local_number_counter_scope
        UNIQUE (organization_pk, namespace)
);

CREATE INDEX IF NOT EXISTS idx_sakha_local_number_counter_org
    ON nss.sakha_local_number_counter (organization_pk);
