-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 12_postal_code.sql
-- Table: postal_code
-- Depth: 1 (depends on state only)
-- Version: 3.0 — SOL-ARCH-010 Amendment (Member-Assisted
--          Geographic Entry, 2026-10-03). PIN code is now a
--          member-writable level: a member may type an unseen
--          PIN, quarantined as PENDING until admin review. Added
--          the shared member-assisted columns (§16.8) and
--          converted uq_postal_code_code to a partial unique
--          index scoped to APPROVED, active rows (FND-BR-090).
-- Version: 2.0 — SOL-ARCH-010 Amendment (Simplified Geography
--          Model, 2026-10-02): country_pk and post_office_name
--          dropped. country_pk was redundant (reachable via
--          state_pk -> state.country_pk); post_office_name had
--          no source once post_office was retired (the new
--          4-file government source carries no post-office
--          data at all, only village/urban locality names,
--          which now live on city_village instead). Uniqueness
--          simplified to (postal_code) alone — one row per PIN,
--          dominant state chosen for the ~29 PINs that span
--          state lines.
-- Authority: SOL-ARCH-010 Amendment (PIN Code Geographic
--            Model, 2026-08-28; Simplified Geography Model,
--            2026-10-02)
-- Owner: NSS_ERP_ADMIN
-- Note: PIN codes carry a direct state_pk FK (PIN -> State is
--       always deterministic once a dominant state is chosen
--       for cross-state PINs). PIN -> District is NOT 1:1
--       (2,269 PINs legitimately span 2+ districts), so
--       district is intentionally NOT a column here — it is
--       reached through city_village, which carries its own
--       district_pk per locality row.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.postal_code
(
    postal_code_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    state_pk UUID NOT NULL,

    postal_code VARCHAR(20) NOT NULL,

    -- ── Member-Assisted Geographic Entry (§16.8) ────────

    entry_status VARCHAR(20) NOT NULL
        DEFAULT 'APPROVED',

    submitted_by_sangha_sevi_pk UUID NULL,

    -- Geography Auto-Create at Registration + Bulk-Seed Attribution
    -- (2026-10-21) — see nss.city_village.submitted_by_person_pk for the
    -- full explanation; identical rationale and deferred-FK pattern here.
    submitted_by_person_pk UUID NULL,

    reviewed_by_sangha_sevi_pk UUID NULL,

    reviewed_at TIMESTAMPTZ NULL,

    admin_remarks TEXT NULL,

    corrected_into_postal_code_pk UUID NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_postal_code_state
        FOREIGN KEY (state_pk)
        REFERENCES nss.state (state_pk),

    CONSTRAINT fk_postal_code_corrected_into
        FOREIGN KEY (corrected_into_postal_code_pk)
        REFERENCES nss.postal_code (postal_code_pk),

    CONSTRAINT chk_postal_code_entry_status
        CHECK (entry_status IN ('PENDING', 'APPROVED', 'CORRECTED')),

    CONSTRAINT chk_postal_code_correction
        CHECK
        (
            (entry_status = 'CORRECTED'
                AND corrected_into_postal_code_pk IS NOT NULL)
            OR
            (entry_status <> 'CORRECTED'
                AND corrected_into_postal_code_pk IS NULL)
        ),

    CONSTRAINT chk_postal_code_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- Idempotent safety net: tables created before submitted_by_person_pk was
-- added to the CREATE TABLE above never get it via CREATE TABLE IF NOT
-- EXISTS alone (that clause is a no-op when the table already exists).
-- This ALTER guarantees the column exists either way (same pattern as
-- master_data.applicable_modules / organization.has_own_premises).
ALTER TABLE nss.postal_code
    ADD COLUMN IF NOT EXISTS submitted_by_person_pk UUID NULL;

CREATE INDEX IF NOT EXISTS idx_postal_code_state
    ON nss.postal_code (state_pk);

CREATE INDEX IF NOT EXISTS idx_postal_code_code
    ON nss.postal_code (postal_code);

CREATE INDEX IF NOT EXISTS idx_postal_code_active
    ON nss.postal_code (is_active);

CREATE INDEX IF NOT EXISTS idx_postal_code_entry_status
    ON nss.postal_code (entry_status);

-- ── Canonical Uniqueness Among Approved Rows (FND-BR-090) ─
CREATE UNIQUE INDEX IF NOT EXISTS uq_postal_code_code_approved
    ON nss.postal_code (postal_code)
    WHERE entry_status = 'APPROVED' AND is_active = TRUE;
