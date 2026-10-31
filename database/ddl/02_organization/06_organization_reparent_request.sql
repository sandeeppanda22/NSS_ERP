-- =====================================================
-- NSS ERP
-- Module: Organization (Sakha re-parenting approval workflow)
-- File: 06_organization_reparent_request.sql
-- Table: nss.organization_reparent_request
-- Depth: 2 (depends on organization [Depth 1], user_account, person,
--          sangha_sevi)
-- Version: 1.0
-- Authority: Owner rule (2026-10-30) — re-parenting a Sakha (moving it
--            under a different Anchalika/Zilla Sangha, including the
--            "Assign Sakha" action and the initial move out of Kendra)
--            (SAKHA_SANGHA or SAKHA_ASANA) must always be approved,
--            EXCEPT when done by a Kendra Governing Body member or the
--            NSS_ERP_ADMIN super administrator, who may do it directly. Rule recorded
--            in docs/03_Solution/modules/organization/ (non-frozen);
--            a GDR is pending (new governance rule).
--
-- Design decisions:
--   - One row per re-parent REQUEST. The Sakha's parent_organization_pk
--     does NOT change while the request is PENDING; it changes only when
--     the final approval step is APPROVED (api/services/
--     org_reparent_service.py::apply_approved_reparent, atomically, after
--     re-validating target/type/cycle/active).
--   - At most one open (PENDING) request per Sakha — enforced by the
--     partial unique index below, not only by the API.
--   - from_parent_organization_pk is the parent AT REQUEST TIME (history /
--     display); the apply step re-reads the live parent.
--   - Requester identity is captured three ways (user_account, person,
--     sangha_sevi) so the record survives later role/seat changes.
--   - Steps live in nss.organization_reparent_step (06 -> 07).
--   - No ON DELETE CASCADE; soft delete only (History Never Deleted).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE columns
--       included in Pass 1. Their FK constraints are deferred to
--       Pass 2, per project-wide two-pass DDL convention.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.organization_reparent_request
(
    -- ── Identity ────────────────────────────────────────

    organization_reparent_request_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    -- ── Subject ─────────────────────────────────────────

    sakha_organization_pk UUID NOT NULL,

    from_parent_organization_pk UUID NULL,

    to_parent_organization_pk UUID NOT NULL,

    -- ── Requester ───────────────────────────────────────

    requested_by_user_account_pk UUID NOT NULL,

    requested_by_person_pk UUID NOT NULL,

    requested_by_sangha_sevi_pk UUID NULL,

    request_reason TEXT NULL,

    -- ── Outcome ─────────────────────────────────────────

    request_status VARCHAR(10) NOT NULL
        DEFAULT 'PENDING',

    -- Set when the request leaves PENDING (APPROVED / REJECTED /
    -- CANCELLED). decided_by_person_pk is NULL for a system close
    -- (failed re-validation at apply time, or superseded by a direct
    -- Kendra Governing Body / NSS_ERP_ADMIN change).
    decided_at TIMESTAMPTZ NULL,

    decided_by_person_pk UUID NULL,

    decision_remarks TEXT NULL,

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

    CONSTRAINT fk_org_reparent_req_sakha
        FOREIGN KEY (sakha_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_org_reparent_req_from_parent
        FOREIGN KEY (from_parent_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_org_reparent_req_to_parent
        FOREIGN KEY (to_parent_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_org_reparent_req_user_account
        FOREIGN KEY (requested_by_user_account_pk)
        REFERENCES nss.user_account (user_account_pk),

    CONSTRAINT fk_org_reparent_req_person
        FOREIGN KEY (requested_by_person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_org_reparent_req_sangha_sevi
        FOREIGN KEY (requested_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_org_reparent_req_decided_by
        FOREIGN KEY (decided_by_person_pk)
        REFERENCES nss.person (person_pk),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_org_reparent_req_status
        CHECK (request_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),

    CONSTRAINT chk_org_reparent_req_not_self
        CHECK (sakha_organization_pk <> to_parent_organization_pk),

    CONSTRAINT chk_org_reparent_req_decided
        CHECK
        (
            (request_status = 'PENDING' AND decided_at IS NULL)
            OR
            (request_status <> 'PENDING' AND decided_at IS NOT NULL)
        ),

    CONSTRAINT chk_org_reparent_req_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

-- At most one open request per Sakha.
CREATE UNIQUE INDEX IF NOT EXISTS uq_org_reparent_req_one_open_per_sakha
    ON nss.organization_reparent_request (sakha_organization_pk)
    WHERE request_status = 'PENDING' AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_org_reparent_req_sakha
    ON nss.organization_reparent_request (sakha_organization_pk);

CREATE INDEX IF NOT EXISTS idx_org_reparent_req_requester
    ON nss.organization_reparent_request (requested_by_person_pk);

CREATE INDEX IF NOT EXISTS idx_org_reparent_req_status
    ON nss.organization_reparent_request (request_status);

CREATE INDEX IF NOT EXISTS idx_org_reparent_req_active
    ON nss.organization_reparent_request (is_active);
