-- =====================================================
-- NSS ERP
-- Module: Organization (Sakha re-parenting approval workflow)
-- File: 07_organization_reparent_step.sql
-- Table: nss.organization_reparent_step
-- Depth: 3 (depends on organization_reparent_request [Depth 2],
--          body_master, position_master, organization, person)
-- Version: 1.1 (2026-10-31: SOURCE_PARENT_PRESIDENT step added, step_order 1..4;
--          existing DBs get 09_organization_reparent_step_source_role_patch.sql)
-- Authority: Owner rule (2026-10-30) — see 06_organization_reparent_request.sql.
--
-- Approval chain, in all cases:
--   1  SAKHA_PRESIDENT         the moved Sakha's (or Sakha Asana's) own President
--   2  SOURCE_PARENT_PRESIDENT the LEAVING (current) Anchalika/Zilla President —
--                              absent when the current parent is Kendra
--   3  DEST_PARENT_PRESIDENT   the DESTINATION Anchalika/Zilla President
--   4  KENDRA_PRESIDENT        the Kendra President (final)
-- Fallback: a step with no seated President (live seat incl. acting cover),
-- or whose seat the requester themself holds, is assigned to the Kendra
-- President instead (never auto-approved, never skipped), recorded in
-- fallback_reason. Consecutive Kendra-President steps collapse into one,
-- so step_order is 1..4 but not necessarily contiguous from the role.
--
-- Design decisions:
--   - The approving SEAT is (assigned_body_master_pk, assigned_position_
--     master_pk). Authority at decision time is the LIVE seat on that body
--     (substantive holder or active acting delegate) — assigned_person_pk
--     is only who was seated when the chain was built (display/history),
--     never trusted for authorization.
--   - step_role is the ROLE the step was built for; on a fallback step the
--     assigned body is the Kendra Governing Body while step_role keeps the
--     original role (SAKHA_PRESIDENT / SOURCE_PARENT_PRESIDENT / DEST_PARENT_PRESIDENT).
--   - assigned_organization_pk NULL = the NSS-wide Kendra Governing Body
--     (body_master.organization_pk IS NULL).
--   - No ON DELETE CASCADE; soft delete only.
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE columns
--       included in Pass 1. Their FK constraints are deferred to
--       Pass 2, per project-wide two-pass DDL convention.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.organization_reparent_step
(
    -- ── Identity ────────────────────────────────────────

    organization_reparent_step_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_reparent_request_pk UUID NOT NULL,

    step_order SMALLINT NOT NULL,

    step_role VARCHAR(30) NOT NULL,

    -- ── Assigned seat ───────────────────────────────────

    assigned_organization_pk UUID NULL,

    assigned_body_master_pk UUID NOT NULL,

    assigned_position_master_pk UUID NOT NULL,

    assigned_person_pk UUID NULL,

    fallback_reason VARCHAR(300) NULL,

    -- ── Decision ────────────────────────────────────────

    step_status VARCHAR(10) NOT NULL
        DEFAULT 'PENDING',

    decided_by_person_pk UUID NULL,

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

    CONSTRAINT fk_org_reparent_step_request
        FOREIGN KEY (organization_reparent_request_pk)
        REFERENCES nss.organization_reparent_request (organization_reparent_request_pk),

    CONSTRAINT fk_org_reparent_step_organization
        FOREIGN KEY (assigned_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_org_reparent_step_body
        FOREIGN KEY (assigned_body_master_pk)
        REFERENCES nss.body_master (body_master_pk),

    CONSTRAINT fk_org_reparent_step_position
        FOREIGN KEY (assigned_position_master_pk)
        REFERENCES nss.position_master (position_master_pk),

    CONSTRAINT fk_org_reparent_step_assigned_person
        FOREIGN KEY (assigned_person_pk)
        REFERENCES nss.person (person_pk),

    CONSTRAINT fk_org_reparent_step_decided_by
        FOREIGN KEY (decided_by_person_pk)
        REFERENCES nss.person (person_pk),

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_org_reparent_step_request_order
        UNIQUE (organization_reparent_request_pk, step_order),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_org_reparent_step_order
        CHECK (step_order BETWEEN 1 AND 4),

    CONSTRAINT chk_org_reparent_step_role
        CHECK (step_role IN ('SAKHA_PRESIDENT', 'SOURCE_PARENT_PRESIDENT', 'DEST_PARENT_PRESIDENT', 'KENDRA_PRESIDENT')),

    CONSTRAINT chk_org_reparent_step_status
        CHECK (step_status IN ('PENDING', 'APPROVED', 'REJECTED')),

    CONSTRAINT chk_org_reparent_step_decided
        CHECK
        (
            (step_status = 'PENDING' AND decided_at IS NULL)
            OR
            (step_status <> 'PENDING' AND decided_at IS NOT NULL)
        ),

    CONSTRAINT chk_org_reparent_step_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_org_reparent_step_request
    ON nss.organization_reparent_step (organization_reparent_request_pk);

-- Primary access path for "awaiting my decision" (steps pending on a seat
-- the caller currently holds).
CREATE INDEX IF NOT EXISTS idx_org_reparent_step_body_pending
    ON nss.organization_reparent_step (assigned_body_master_pk)
    WHERE step_status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_org_reparent_step_active
    ON nss.organization_reparent_step (is_active);
