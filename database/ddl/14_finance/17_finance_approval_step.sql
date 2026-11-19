-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 17_finance_approval_step.sql
-- Table: nss.finance_approval_step
-- Depth: 4 (depends on financial_transaction, person)
-- Version: 1.0
-- Authority: owner decision 2026-11-17 (Sakha approval chain: Treasurer first, then the President - the Secretary when no
--            President is seated or covering; the Treasurer alone for a spend inside the head's limit).
-- Owner: NSS_ERP_ADMIN
-- Note: One row per DECISION taken on a Sakha transaction. The authority is the governing-body SEAT the decider holds at the
--       moment of deciding (position_code), never a permission or the super administrator: recorded here with the person
--       so the books show who approved in which office and why that office (cover_reason when the Secretary stood in for a
--       vacant President seat). A step is recorded once per transaction (uq_fas_step); a rejection is a step too.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_approval_step
(
    finance_approval_step_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    financial_transaction_pk UUID NOT NULL,

    step_no SMALLINT NOT NULL,

    position_code VARCHAR(30) NOT NULL,

    decision VARCHAR(10) NOT NULL,

    decided_by_person_pk UUID NOT NULL,

    decided_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    remarks TEXT NULL,

    cover_reason VARCHAR(40) NULL,

    -- ── Lifecycle / Audit ───────────────────────────────

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by_sangha_sevi_pk UUID NULL,

    updated_at TIMESTAMPTZ NULL,

    updated_by_sangha_sevi_pk UUID NULL,

    deleted_at TIMESTAMPTZ NULL,

    deleted_by_sangha_sevi_pk UUID NULL,

    CONSTRAINT fk_fas_transaction
        FOREIGN KEY (financial_transaction_pk)
        REFERENCES nss.financial_transaction (financial_transaction_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fas_person
        FOREIGN KEY (decided_by_person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT chk_fas_step_no
        CHECK (step_no IN (1, 2)),

    CONSTRAINT chk_fas_position
        CHECK (position_code IN ('TREASURER', 'PRESIDENT', 'SECRETARY')),

    CONSTRAINT chk_fas_decision
        CHECK (decision IN ('APPROVED', 'REJECTED')),

    CONSTRAINT chk_fas_cover_reason
        CHECK (cover_reason IS NULL OR cover_reason IN ('PRESIDENT_SEAT_VACANT', 'ACTING_COVER')),

    -- Step 1 is the Treasurer's; step 2 is the President's or, in cover, the Secretary's.
    CONSTRAINT chk_fas_position_matches_step
        CHECK ((step_no = 1 AND position_code = 'TREASURER') OR (step_no = 2 AND position_code IN ('PRESIDENT', 'SECRETARY'))),

    -- A rejection must say why.
    CONSTRAINT chk_fas_reject_remarks
        CHECK (decision <> 'REJECTED' OR (remarks IS NOT NULL AND BTRIM(remarks) <> '')),

    CONSTRAINT chk_fas_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fas_step
    ON nss.finance_approval_step (financial_transaction_pk, step_no) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_fas_person
    ON nss.finance_approval_step (decided_by_person_pk);
