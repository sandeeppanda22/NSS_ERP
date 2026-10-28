-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 11_city_village.sql
-- Table: city_village
-- Depth: 3 (depends on district, postal_code)
-- Sequence: #32 of 87
-- Version: 3.0 — SOL-ARCH-010 Amendment (Member-Assisted
--          Geographic Entry, 2026-10-03): city_village is a
--          member-writable level. Added the shared member-
--          assisted columns (§16.8) and converted the three
--          UNIQUE constraints to partial unique indexes scoped
--          to APPROVED, active rows (FND-BR-090).
-- Version: 2.0 — SOL-ARCH-010 Amendment (2026-10-01):
--          simplified geographic FK model for all-India scale.
--          district_pk is now OPTIONAL (best-effort name match;
--          India's census/post romanizations drift at the
--          district level, so an unresolved district should
--          not block a locality from being loaded). A direct
--          nullable postal_code_pk FK is added as the primary
--          location anchor (village → PIN → state), replacing
--          the city_village_postal_code_map M:N junction, which
--          is retired (see 13_city_village_postal_code_map.sql).
--          Villages are 1:1 with PIN; the junction only ever
--          earned its keep for a handful of multi-PIN urban
--          localities, which now simply store one representative
--          PIN (same HO>PO>BO dedup rule used for postal_code).
-- Authority: SOL-ARCH-010, SOL-ARCH-010 Amendment (2026-10-01),
--            SOL-FND-004 §16
-- Owner: NSS_ERP_ADMIN
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.city_village
(
    city_village_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    district_pk UUID NULL,

    postal_code_pk UUID NULL,

    city_village_code VARCHAR(20) NOT NULL,

    city_village_name VARCHAR(150) NOT NULL,

    city_village_type VARCHAR(20) NOT NULL,

    display_order INTEGER NOT NULL
        DEFAULT 0,

    -- ── Member-Assisted Geographic Entry (§16.8) ────────

    entry_status VARCHAR(20) NOT NULL
        DEFAULT 'APPROVED',

    submitted_by_sangha_sevi_pk UUID NULL,

    -- Geography Auto-Create at Registration + Bulk-Seed Attribution
    -- (2026-10-21): records which PERSON caused this row to be created,
    -- for the registration-time auto-create path (api/helpers.py
    -- resolve_or_create_*) where the submitter has no JWT/sangha_sevi
    -- yet — person exists, sangha_sevi does not. Logically separate
    -- from submitted_by_sangha_sevi_pk (the member-authenticated
    -- "propose" flow in foundation.py); a row is stamped by at most one
    -- of the two. Also backfilled onto bulk-reference-seeded rows
    -- (Foundation Phase 2) post-build, pointing at the NSS Admin's
    -- person_pk (see the post-Phase-13 backfill step in
    -- database/scripts/02_build.sh / .ps1 / render_build.sh) for
    -- attribution consistency, since nobody "submitted" those via the
    -- app. No FK here (person doesn't exist yet in Phase 1) — the real
    -- FK is added by 05_membership/16_foundation_audit_fk.sql, same
    -- deferred-FK pattern as submitted_by_sangha_sevi_pk.
    submitted_by_person_pk UUID NULL,

    reviewed_by_sangha_sevi_pk UUID NULL,

    reviewed_at TIMESTAMPTZ NULL,

    admin_remarks TEXT NULL,

    corrected_into_city_village_pk UUID NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    CONSTRAINT fk_city_village_district
        FOREIGN KEY (district_pk)
        REFERENCES nss.district (district_pk),

    CONSTRAINT fk_city_village_postal_code
        FOREIGN KEY (postal_code_pk)
        REFERENCES nss.postal_code (postal_code_pk),

    CONSTRAINT fk_city_village_corrected_into
        FOREIGN KEY (corrected_into_city_village_pk)
        REFERENCES nss.city_village (city_village_pk),

    CONSTRAINT chk_city_village_entry_status
        CHECK (entry_status IN ('PENDING', 'APPROVED', 'CORRECTED')),

    CONSTRAINT chk_city_village_correction
        CHECK
        (
            (entry_status = 'CORRECTED'
                AND corrected_into_city_village_pk IS NOT NULL)
            OR
            (entry_status <> 'CORRECTED'
                AND corrected_into_city_village_pk IS NULL)
        ),

    CONSTRAINT chk_city_village_type
        CHECK
        (
            city_village_type IN
            (
                'CITY',
                'TOWN',
                'VILLAGE'
            )
        ),

    CONSTRAINT chk_city_village_soft_delete
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
ALTER TABLE nss.city_village
    ADD COLUMN IF NOT EXISTS submitted_by_person_pk UUID NULL;

CREATE INDEX IF NOT EXISTS idx_city_village_district
    ON nss.city_village (district_pk);

CREATE INDEX IF NOT EXISTS idx_city_village_postal_code
    ON nss.city_village (postal_code_pk);

CREATE INDEX IF NOT EXISTS idx_city_village_active
    ON nss.city_village (is_active);

CREATE INDEX IF NOT EXISTS idx_city_village_entry_status
    ON nss.city_village (entry_status);

CREATE INDEX IF NOT EXISTS idx_city_village_name
    ON nss.city_village USING gin (city_village_name gin_trgm_ops);

-- ── Canonical Uniqueness Among Approved Rows (FND-BR-090) ─
CREATE UNIQUE INDEX IF NOT EXISTS uq_city_village_district_code_approved
    ON nss.city_village (district_pk, city_village_code)
    WHERE entry_status = 'APPROVED' AND is_active = TRUE;

-- Version 3.1 (2026-10-21, owner-confirmed) — the two name-based
-- uniqueness rules were wrong about real Indian geography and were
-- silently discarding genuine villages at seed time (blind
-- `ON CONFLICT DO NOTHING`, no explicit target, in the seed file).
--
--   * uq_city_village_district_name_approved (district_pk, name) —
--     REMOVED outright. Verified against the loaded data: Tumakuru holds
--     18 distinct villages named "Hosahalli" (one per PIN), Mayurbhanj 15
--     "Rangamatia". ~45,000 real rows were being dropped on this alone.
--
--   * uq_city_village_postal_code_name_approved (postal_code_pk, name) —
--     WIDENED to include district_pk. PIN areas straddle district
--     borders, so 555 further groups of genuinely distinguishable
--     villages (same PIN + name, different district/state) were being
--     dropped too. Adding district_pk recovers them while still deduping
--     the ~13,799 rows that differ ONLY by LGD code and are therefore
--     identical in every field this ERP displays or uses.
--
-- city_village_code (the LGD code) is retained as reference data for
-- future re-sync against government releases, but is no longer the sole
-- canonical key; (district_pk, postal_code_pk, city_village_name) is.
-- Index drops are not covered by table-level existence-gating, so the
-- explicit DROPs below are required for already-built environments.
DROP INDEX IF EXISTS nss.uq_city_village_district_name_approved;
DROP INDEX IF EXISTS nss.uq_city_village_postal_code_name_approved;

CREATE UNIQUE INDEX IF NOT EXISTS uq_city_village_pin_name_district_approved
    ON nss.city_village (postal_code_pk, city_village_name, district_pk)
    WHERE entry_status = 'APPROVED' AND is_active = TRUE;
