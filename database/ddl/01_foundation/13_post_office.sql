-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 13_post_office.sql
-- Table: post_office
-- Depth: 2 (depends on postal_code)
-- Version: 1.0 — SOL-ARCH-010 Amendment (Member-Assisted
--          Geographic Entry, 2026-10-03). Reinstates the
--          post office level that the 2026-10-02 Simplified
--          Geography Model had retired. A single PIN code can
--          carry many post offices (one HO + several SO/BO),
--          so post_office hangs off postal_code and is one of
--          the four member-writable geographic levels
--          (District, PIN code, Post Office, City/Village).
-- Authority: SOL-ARCH-010 Amendment (2026-10-03),
--            SOL-FND-004 §16.7, FND-BR-085 .. FND-BR-090
-- Owner: NSS_ERP_ADMIN
-- Note: Member-assisted entry columns (entry_status,
--       submitted_by_sangha_sevi_pk, reviewed_by_sangha_sevi_pk,
--       reviewed_at, admin_remarks, corrected_into_post_office_pk)
--       are shared across the four writable geographic tables
--       (district, postal_code, post_office, city_village) —
--       see SOL-FND-004 §16.8.
-- Note: submitted_by/reviewed_by reference nss.sangha_sevi.
--       The columns are created here as plain nullable UUID
--       (Foundation builds before Membership — sangha_sevi
--       doesn't exist yet); the real FK constraints are added
--       by 05_membership/16_foundation_audit_fk.sql once
--       sangha_sevi exists (Phase 7b of 02_build.sh).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.post_office
(
    -- ── Identity ────────────────────────────────────────

    post_office_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Relationships ───────────────────────────────────

    postal_code_pk UUID NOT NULL,

    -- ── Attributes ──────────────────────────────────────

    post_office_name VARCHAR(150) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    -- ── Member-Assisted Geographic Entry (§16.8) ────────

    -- PENDING  = member-typed, awaiting admin review (quarantined,
    --            not shown in shared dropdowns).
    -- APPROVED = canonical shared value (seeded rows start here).
    -- CORRECTED = retired after admin supplied a canonical value;
    --            corrected_into_post_office_pk points at the survivor.
    entry_status VARCHAR(20) NOT NULL
        DEFAULT 'APPROVED',

    -- Logical refs to nss.sangha_sevi (no FK — see header note).
    submitted_by_sangha_sevi_pk UUID NULL,

    -- Geography Auto-Create at Registration + Bulk-Seed Attribution
    -- (2026-10-21) — see nss.city_village.submitted_by_person_pk for the
    -- full explanation; identical rationale and deferred-FK pattern here.
    submitted_by_person_pk UUID NULL,

    reviewed_by_sangha_sevi_pk UUID NULL,

    reviewed_at TIMESTAMPTZ NULL,

    admin_remarks TEXT NULL,

    -- Self-reference: when CORRECTED, the canonical survivor row.
    corrected_into_post_office_pk UUID NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Foreign Keys ────────────────────────────────────

    CONSTRAINT fk_post_office_postal_code
        FOREIGN KEY (postal_code_pk)
        REFERENCES nss.postal_code (postal_code_pk),

    CONSTRAINT fk_post_office_corrected_into
        FOREIGN KEY (corrected_into_post_office_pk)
        REFERENCES nss.post_office (post_office_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_post_office_entry_status
        CHECK (entry_status IN ('PENDING', 'APPROVED', 'CORRECTED')),

    -- A CORRECTED row must point at its survivor; any other
    -- status must not (FND-BR-087).
    CONSTRAINT chk_post_office_correction
        CHECK
        (
            (entry_status = 'CORRECTED'
                AND corrected_into_post_office_pk IS NOT NULL)
            OR
            (entry_status <> 'CORRECTED'
                AND corrected_into_post_office_pk IS NULL)
        ),

    CONSTRAINT chk_post_office_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

-- Idempotent safety net: tables created before submitted_by_person_pk was
-- added to the CREATE TABLE above never get it via CREATE TABLE IF NOT
-- EXISTS alone (that clause is a no-op when the table already exists).
-- This ALTER guarantees the column exists either way (same pattern as
-- master_data.applicable_modules / organization.has_own_premises).
ALTER TABLE nss.post_office
    ADD COLUMN IF NOT EXISTS submitted_by_person_pk UUID NULL;

CREATE INDEX IF NOT EXISTS idx_post_office_postal_code
    ON nss.post_office (postal_code_pk);

CREATE INDEX IF NOT EXISTS idx_post_office_active
    ON nss.post_office (is_active);

CREATE INDEX IF NOT EXISTS idx_post_office_entry_status
    ON nss.post_office (entry_status);

CREATE INDEX IF NOT EXISTS idx_post_office_name
    ON nss.post_office USING gin (post_office_name gin_trgm_ops);

-- ── Canonical Uniqueness Among Approved Rows (FND-BR-090) ─
-- One PIN can hold many post offices, but a given post-office
-- name is unique within a PIN only among APPROVED, active rows.
-- PENDING / CORRECTED rows are exempt, so a member's save never
-- collides with the canonical row it may turn out to duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS uq_post_office_pin_name_approved
    ON nss.post_office (postal_code_pk, post_office_name)
    WHERE entry_status = 'APPROVED' AND is_active = TRUE;
