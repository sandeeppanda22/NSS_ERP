-- =====================================================
-- NSS ERP
-- Module: Authentication & Security
-- File: 03_registration_claim.sql
-- Table: nss.registration_claim
-- Depth: 3 (depends on user_account, person, organization, master_data)
-- Version: 1.0
-- Authority: SOL-AUTH-006 (Registration Claim Business Rules),
--            SOL-AUTH-007 (Registration Claim Table Design)
-- Owner: Authentication & Security
--
-- Design decisions:
--   - Stores self-declared membership claims pending admin approval
--   - One PENDING claim per user_account at a time (partial unique index)
--   - claimed_local_sakha_number is validated at registration only for shape
--     and the legacy rule (is_legacy_member => required, else must be blank);
--     the admin verifies it at approval
--   - Claim lifecycle: PENDING -> APPROVED | REJECTED
--   - Approval triggers sangha_sevi + affiliation creation (API-level)
--   - person_pk is a denormalized FK for query convenience
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.registration_claim
(
    -- ── Identity ────────────────────────────────────────

    registration_claim_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Relationships ───────────────────────────────────

    user_account_pk UUID NOT NULL,

    person_pk UUID NOT NULL,

    -- ── Claimed Membership Details ──────────────────────

    claimed_organization_pk UUID NOT NULL,

    claimed_membership_type_master_data_pk UUID NOT NULL,

    claimed_local_sakha_number VARCHAR(20) NULL,

    -- LEGACY vs NEW (GDR-009, owner 2026-11-01). TRUE = the registrant was
    -- ALREADY a member (Regular/Associate/Darshak) before this system
    -- existed and states the number on their card in
    -- claimed_local_sakha_number; FALSE = new, and the number is
    -- auto-generated at approval (claimed_local_sakha_number must be NULL).
    -- An explicit flag, never inferred from "a number was typed". Admin
    -- verifies/corrects both at approval. See chk_registration_claim_legacy_*.
    is_legacy_member BOOLEAN NOT NULL DEFAULT FALSE,

    claimed_joining_date DATE NULL,

    -- Existing Parichaya Patra / Anumati Patra document number of a LEGACY
    -- member (is_legacy_member = TRUE), strictly <seq>/<yyyy>/<yyyy+1>
    -- (GDR-009 §2A). NULL for a new member: the number is then auto-minted at
    -- approval. Application-enforced (no CHECK). Distinct from
    -- claimed_local_sakha_number (Tier 2 identity) — this is the Tier 3
    -- annual Kendra/Sakha-wide credential number (MEM-PENDING-001 /
    -- Tier 4 Frozen Decisions "Three-tier member identity").
    claimed_credential_document_number VARCHAR(30) NULL,

    -- ── Darshak Attendance ──────────────────────────────

    darshak_organization_pk UUID NULL,

    -- Local Sakha Number at the darshak_organization_pk (attending) Sakha —
    -- separate namespace from claimed_local_sakha_number, which is the
    -- home Sakha's number. NULL while the attending Sakha hasn't assigned
    -- one yet; required at approval once darshak_organization_pk is set
    -- (mirrors claimed_local_sakha_number's own requirement).
    darshak_local_sakha_number VARCHAR(20) NULL,

    -- Legacy status AT THE ATTENDING SAKHA, independent of is_legacy_member
    -- (a person can be a legacy home-Sakha member and a new attendee
    -- elsewhere, or the reverse). TRUE = darshak_local_sakha_number is the
    -- existing Darshak number at that Sakha; FALSE = the next number in that
    -- Sakha's Darshak series is allocated at approval.
    darshak_is_legacy_member BOOLEAN NOT NULL DEFAULT FALSE,

    -- ── Claim Status ────────────────────────────────────

    claim_status VARCHAR(20) NOT NULL
        DEFAULT 'PENDING',

    -- ── Review ──────────────────────────────────────────

    reviewed_by_user_account_pk UUID NULL,

    reviewed_at TIMESTAMPTZ NULL,

    admin_remarks TEXT NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NULL,

    deleted_at TIMESTAMPTZ NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    -- ── Foreign Keys ────────────────────────────────────

    CONSTRAINT fk_registration_claim_user_account
        FOREIGN KEY (user_account_pk)
        REFERENCES nss.user_account (user_account_pk),

    CONSTRAINT fk_registration_claim_person
        FOREIGN KEY (person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_registration_claim_organization
        FOREIGN KEY (claimed_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_registration_claim_membership_type
        FOREIGN KEY (claimed_membership_type_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_registration_claim_darshak_org
        FOREIGN KEY (darshak_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_registration_claim_reviewer
        FOREIGN KEY (reviewed_by_user_account_pk)
        REFERENCES nss.user_account (user_account_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_registration_claim_status
        CHECK (claim_status IN ('PENDING', 'APPROVED', 'REJECTED')),

    CONSTRAINT chk_registration_claim_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        ),

    -- Legacy flag and number always agree: legacy <=> a number is stored.
    -- (The API reports a mismatch as a clear 422 first; these are the
    -- backstop. Patch: 06_registration_claim_legacy_member_patch.sql.)
    CONSTRAINT chk_registration_claim_legacy_home
        CHECK (is_legacy_member = (claimed_local_sakha_number IS NOT NULL)),

    CONSTRAINT chk_registration_claim_legacy_darshak
        CHECK (darshak_is_legacy_member = (darshak_local_sakha_number IS NOT NULL))
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_registration_claim_user_account
    ON nss.registration_claim (user_account_pk);

CREATE INDEX IF NOT EXISTS idx_registration_claim_person
    ON nss.registration_claim (person_pk);

CREATE INDEX IF NOT EXISTS idx_registration_claim_status
    ON nss.registration_claim (claim_status);

CREATE INDEX IF NOT EXISTS idx_registration_claim_organization
    ON nss.registration_claim (claimed_organization_pk);

-- Partial unique index: one PENDING claim per user_account (AUTH-BR-083)
CREATE UNIQUE INDEX IF NOT EXISTS uq_registration_claim_one_pending
    ON nss.registration_claim (user_account_pk)
    WHERE claim_status = 'PENDING';
