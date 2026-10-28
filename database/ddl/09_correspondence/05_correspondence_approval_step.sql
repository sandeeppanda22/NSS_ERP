-- =====================================================
-- NSS ERP
-- Module: Administration (Correspondence Register capability)
-- File: 05_correspondence_approval_step.sql
-- Table: nss.correspondence_approval_step
-- Depth: 5 (depends on correspondence [Depth 4], person, position_master,
--          organization)
-- Version: 1.0
-- Authority: Member Dashboard "Send Application" feature (owner request,
--            2026-10-21) — a member addressing a Kendra-level
--            office-bearer must route the application through their own
--            Sakha President first; only after the President
--            approves/forwards it does it become visible to the target
--            Kendra-level office-bearer. ADDITIVE to SOL-ADMIN-009 —
--            does not alter nss.correspondence's columns, the §6.2
--            status-transition table, or any of the 9 existing
--            Correspondence endpoints.
-- Owner: Administration / Governance (cross-cutting; FKs to both
--        nss.correspondence and nss.position_master)
--
-- Design decisions:
--   - This is a routing/approval-chain overlay, independent of
--     nss.correspondence.status (§6.2 REGISTERED/PENDING_ACTION/
--     ACTIONED/CLOSED remains untouched by step 1; only step 2's own
--     terminal APPROVE drives one specific, already-valid §6.2 transition
--     — see decide_approval_step() in api/routers/correspondence.py). A
--     correspondence row addressed "via Sakha President to a Kendra
--     office-bearer" gets exactly two rows here:
--       step_number = 1 — the Sakha President's decision (PENDING until
--                          acted on).
--       step_number = 2 — the Kendra-level office-bearer's OWN decision
--                          (PENDING until acted on). Fixed 2026-10-22
--                          (owner-confirmed root-cause fix): step 2 used
--                          to be auto-flipped to APPROVED by the API the
--                          instant step 1 was approved, deciding on the
--                          Kendra office-bearer's behalf with no real
--                          decision mechanism for step 2 at all. Step 2's
--                          step_status now only ever changes via its own
--                          genuine decision (api layer, decide_approval_step());
--                          "step 2 is now visible/actionable" is a pure
--                          read-time filter (step 1 APPROVED) in
--                          list_addressed_to_me()/
--                          list_pending_approvals_for_me(), never a stored
--                          status flip. Step 2 cannot be decided before
--                          step 1 is APPROVED (API-enforced, not a CHECK
--                          constraint here — see header note below on why
--                          this table doesn't encode that itself).
--   - Only correspondence created via the member "Send Application"
--     Kendra-via-Sakha-President addressing mode get rows here; direct
--     addressing (own Sakha as an organization, or a named Sakha
--     office-bearer) has no approval_step rows at all — every other
--     Correspondence row (including every pre-existing one) simply has
--     zero matching rows, hence additive/optional.
--   - approver_person_pk is captured at creation time (the Sakha
--     President seated when the application was filed, resp. the
--     specific Kendra office-bearer the member selected) — not a live
--     lookup — so the chain remains meaningful even if someone later
--     resigns the position; decision-time authorization re-verifies the
--     acting user is still the seated office-bearer separately (API
--     layer), this table just records who was asked / what happened.
--   - approver_organization_pk is the org context of that seat: the
--     member's Sakha for step 1 (never NULL — a Sakha Governing Body is
--     always org-scoped). For step 2 it is NULLable because the Kendra
--     Governing Body is an NSS-wide singleton (body_master.organization_pk
--     IS NULL, per 08_governance/03_body_master.sql's NSS-wide-singleton
--     convention) — mirrored here rather than inventing a non-NULL
--     placeholder.
--   - No ON DELETE CASCADE anywhere, consistent with
--     01_correspondence.sql's project-wide convention.
--   - CORR-BR-015 (hard-delete not permitted) applies here too;
--     soft-delete only.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE columns
--       included in Pass 1. Their FK constraints are deferred to
--       Pass 2, per project-wide two-pass DDL convention.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.correspondence_approval_step
(
    -- ── Identity ────────────────────────────────────────

    correspondence_approval_step_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    correspondence_pk UUID NOT NULL,

    -- 1 = Sakha President decision, 2 = Kendra office-bearer
    -- delivery/visibility record. See header note.
    step_number SMALLINT NOT NULL,

    -- ── Approver ────────────────────────────────────────

    approver_person_pk UUID NOT NULL,

    approver_position_master_pk UUID NOT NULL,

    -- NULL for an NSS-wide singleton body (step 2 / Kendra Governing
    -- Body) — see header note. Always populated for step 1 (a Sakha
    -- Governing Body is always org-scoped).
    approver_organization_pk UUID NULL,

    -- ── Decision ────────────────────────────────────────

    step_status VARCHAR(10) NOT NULL
        DEFAULT 'PENDING',

    decided_at TIMESTAMPTZ NULL,

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

    CONSTRAINT fk_corr_appr_step_correspondence
        FOREIGN KEY (correspondence_pk)
        REFERENCES nss.correspondence (correspondence_pk),

    CONSTRAINT fk_corr_appr_step_approver_person
        FOREIGN KEY (approver_person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_corr_appr_step_position
        FOREIGN KEY (approver_position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_corr_appr_step_organization
        FOREIGN KEY (approver_organization_pk)
        REFERENCES nss.organization (organization_pk),

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_corr_appr_step_correspondence_step
        UNIQUE (correspondence_pk, step_number),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_corr_appr_step_number
        CHECK (step_number IN (1, 2)),

    CONSTRAINT chk_corr_appr_step_status
        CHECK (step_status IN ('PENDING', 'APPROVED', 'REJECTED')),

    CONSTRAINT chk_corr_appr_step_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_corr_appr_step_correspondence
    ON nss.correspondence_approval_step (correspondence_pk);

-- Primary access path for "my pending approvals" (the Sakha President's or
-- Kendra office-bearer's dashboard, api's list_pending_approvals_for_me()) —
-- step_number is deliberately NOT in this index: both steps are decided by
-- a human approver now (fixed 2026-10-22), but a given approver_person_pk
-- only ever has one step row genuinely actionable at a time (step 2 is
-- additionally gated at the API layer on step 1 already being APPROVED),
-- so filtering on (approver_person_pk, step_status) alone is sufficient and
-- keeps the index usable by both steps without a two-column partial-index
-- split.
CREATE INDEX IF NOT EXISTS idx_corr_appr_step_approver_pending
    ON nss.correspondence_approval_step (approver_person_pk, step_status)
    WHERE step_status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_corr_appr_step_active
    ON nss.correspondence_approval_step (is_active);
