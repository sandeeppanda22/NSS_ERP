-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 21_membership_status_change_request.sql
-- Table: nss.membership_status_change_request
-- Depth: 4 (depends on sangha_sevi, master_data)
-- Version: 1.0
-- Authority: MBR-020 / MBR-021 / MBR-045 (status + history, never delete);
--            owner decision 2026-11-18 (see below)
-- Owner: NSS_ERP_ADMIN
-- Note: A change of a member's Membership Status (ACTIVE, SUSPENDED,
--       LAPSED, EXPELLED, DECEASED) is REQUESTED by a Governing Body member
--       (the member's Sakha GB or the Kendra GB) or an admin in scope and
--       APPROVED by the Parichalak (live seat incl. acting cover) or the
--       Kendra President. Only an approval changes sangha_sevi and writes
--       membership_status_history. One PENDING request per member.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.membership_status_change_request
(
    membership_status_change_request_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    -- The status the member held when the request was filed, and the one asked for.
    from_status_master_data_pk UUID NOT NULL,
    to_status_master_data_pk UUID NOT NULL,

    -- Date the new status takes effect (may be back-dated, never null).
    effective_date DATE NOT NULL,

    reason VARCHAR(500) NOT NULL,

    -- GOVERNING_BODY (GB member) or ADMIN (admin in scope).
    requested_via VARCHAR(20) NOT NULL,

    request_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    requested_by_sangha_sevi_pk UUID NULL,
    requested_by_user_account_pk UUID NULL,

    decided_at TIMESTAMPTZ NULL,
    decided_by_sangha_sevi_pk UUID NULL,
    decision_remarks VARCHAR(500) NULL,

    -- ── Audit ───────────────────────────────────────────

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL,
    created_by_sangha_sevi_pk UUID NULL,
    updated_by_sangha_sevi_pk UUID NULL,
    deleted_by_sangha_sevi_pk UUID NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT fk_msc_request_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_msc_request_from_status
        FOREIGN KEY (from_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_msc_request_to_status
        FOREIGN KEY (to_status_master_data_pk)
        REFERENCES nss.master_data (master_data_pk),

    CONSTRAINT fk_msc_request_user
        FOREIGN KEY (requested_by_user_account_pk)
        REFERENCES nss.user_account (user_account_pk),

    CONSTRAINT chk_msc_request_via
        CHECK (requested_via IN ('GOVERNING_BODY', 'ADMIN')),

    CONSTRAINT chk_msc_request_status
        CHECK (request_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),

    CONSTRAINT chk_msc_request_differs
        CHECK (from_status_master_data_pk <> to_status_master_data_pk),

    -- A decision is recorded exactly when the request left PENDING
    -- (a cancellation by the requester is also a decision timestamp).
    CONSTRAINT chk_msc_request_decided
        CHECK (
            (request_status = 'PENDING' AND decided_at IS NULL)
            OR
            (request_status <> 'PENDING' AND decided_at IS NOT NULL)
        ),

    CONSTRAINT chk_msc_request_soft_delete
        CHECK (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

-- One open request per member.
CREATE UNIQUE INDEX IF NOT EXISTS uq_msc_request_one_pending
    ON nss.membership_status_change_request (sangha_sevi_pk)
    WHERE request_status = 'PENDING' AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_msc_request_sevi
    ON nss.membership_status_change_request (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_msc_request_pending
    ON nss.membership_status_change_request (created_at DESC)
    WHERE request_status = 'PENDING' AND is_active = TRUE;
