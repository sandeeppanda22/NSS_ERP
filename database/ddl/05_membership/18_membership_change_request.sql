-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 18_membership_change_request.sql
-- Table: nss.membership_change_request
-- Depth: 3 (depends on sangha_sevi, organization x2)
-- Version: 1.0
-- Authority: MBR-029, MBR-048, MBR-049
-- Owner: NSS_ERP_ADMIN
--
-- Note: Workflow table backing the "Sakha Transfer" and "Apply for
--       Darshak" member-facing actions (api/routers/membership_change_
--       request.py). Two-step request/release/accept workflow:
--
--         PENDING_SOURCE_RELEASE
--           -> (source Sakha releases)      -> PENDING_DESTINATION_ACCEPT
--           -> (source Sakha rejects)       -> REJECTED_BY_SOURCE   [terminal]
--         PENDING_DESTINATION_ACCEPT
--           -> (destination Sakha accepts)  -> COMPLETED            [terminal]
--           -> (destination Sakha rejects)  -> REJECTED_BY_DESTINATION [terminal]
--
--       Both request_type values ('TRANSFER', 'DARSHAK') share this same
--       workflow shape, but differ in what COMPLETED does to
--       nss.membership_sakha_affiliation (see api/routers/
--       membership_change_request.py):
--         TRANSFER — closes the old (old_organization_pk) affiliation row
--           and opens a new one at new_organization_pk; writes
--           nss.membership_transfer_history + a TRANSFER journey event.
--         DARSHAK  — opens a second, concurrently-active affiliation row
--           at new_organization_pk WITHOUT closing the old (home) one —
--           uq_mem_sakha_aff_active is scoped per (sangha_sevi_pk,
--           organization_pk), so a home affiliation and a Darshak
--           affiliation at a different Sakha legally coexist. No
--           membership_transfer_history row (nothing was transferred).
--
--       old_organization_pk is the member's home Sakha at request time.
--       For a DARSHAK request this is informational only (the home
--       affiliation is never closed) — it is still recorded because it
--       is what the destination Sakha and the attending-Darshak audit
--       trail need to show "coming from".
--
--       new_local_number / effective_date are filled only at COMPLETED:
--       new_local_number is either auto-generated (api/helpers.py::
--       next_sakha_local_number(), the common case) or admin-supplied
--       for a legacy-import case (is_legacy_import at the API layer);
--       effective_date is resolved to the next confirmed Dola Purnima
--       on or after the destination-decision date (api/helpers.py::
--       next_festival_date_on_or_after(), same festival-calendar lookup
--       issue_membership_credential() already uses — not reimplemented
--       here).
--
--       Design decisions:
--         - Modeled as ONE row per request (not two, one per decision
--           stage) so the full lifecycle of a single request is always
--           one query away — mirrors membership_renewal_request's
--           single-row-per-workflow shape, extended to two decision
--           stages instead of one.
--         - The review-consistency CHECK below is the two-stage
--           extension of membership_renewal_request's
--           chk_mem_renewal_req_review_consistency (05_membership/03):
--           source_decided_* must be NULL while PENDING_SOURCE_RELEASE,
--           and NOT NULL for every later status; destination_decided_*
--           must be NULL until a destination decision has actually been
--           made (COMPLETED or REJECTED_BY_DESTINATION).
--         - The partial unique index below (one open request per member)
--           mirrors registration_claim's uq_registration_claim_one_pending
--           (06_authentication/03) — a member cannot have two
--           concurrently open change requests in flight.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.membership_change_request
(
    membership_change_request_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    sangha_sevi_pk UUID NOT NULL,

    -- TRANSFER or DARSHAK.
    request_type VARCHAR(20) NOT NULL,

    -- The member's home Sakha at request time. For DARSHAK this is
    -- informational only — see header note above.
    old_organization_pk UUID NOT NULL,

    -- The Sakha being requested (transfer destination, or the Sakha the
    -- member wants to attend as a Darshak).
    new_organization_pk UUID NOT NULL,

    transfer_reason VARCHAR(500) NULL,

    -- The member themself, or an admin filing on their behalf.
    requested_by_sangha_sevi_pk UUID NOT NULL,

    requested_date DATE NOT NULL
        DEFAULT CURRENT_DATE,

    -- PENDING_SOURCE_RELEASE, PENDING_DESTINATION_ACCEPT, COMPLETED,
    -- REJECTED_BY_SOURCE, REJECTED_BY_DESTINATION.
    status VARCHAR(30) NOT NULL
        DEFAULT 'PENDING_SOURCE_RELEASE',

    -- ── Source (old_organization_pk) decision ────────────────────
    source_decided_by_sangha_sevi_pk UUID NULL,
    source_decided_at TIMESTAMPTZ NULL,
    source_remarks TEXT NULL,

    -- ── Destination (new_organization_pk) decision ───────────────
    destination_decided_by_sangha_sevi_pk UUID NULL,
    destination_decided_at TIMESTAMPTZ NULL,
    destination_remarks TEXT NULL,

    -- Filled at COMPLETED only — see header note above.
    new_local_number VARCHAR(30) NULL,

    effective_date DATE NULL,

    remarks TEXT NULL,

    -- ── Audit ───────────────────────────────────────────
    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    -- ── Constraints ─────────────────────────────────────

    CONSTRAINT fk_mem_change_req_sevi
        FOREIGN KEY (sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_mem_change_req_old_org
        FOREIGN KEY (old_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_mem_change_req_new_org
        FOREIGN KEY (new_organization_pk)
        REFERENCES nss.organization (organization_pk),

    CONSTRAINT fk_mem_change_req_requested_by
        FOREIGN KEY (requested_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_mem_change_req_source_decided_by
        FOREIGN KEY (source_decided_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT fk_mem_change_req_destination_decided_by
        FOREIGN KEY (destination_decided_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),

    CONSTRAINT chk_mem_change_req_type
        CHECK (request_type IN ('TRANSFER', 'DARSHAK')),

    CONSTRAINT chk_mem_change_req_different_orgs
        CHECK (old_organization_pk <> new_organization_pk),

    CONSTRAINT chk_mem_change_req_status
        CHECK
        (
            status IN
            (
                'PENDING_SOURCE_RELEASE', 'PENDING_DESTINATION_ACCEPT',
                'COMPLETED', 'REJECTED_BY_SOURCE', 'REJECTED_BY_DESTINATION'
            )
        ),

    -- Two-stage review consistency (extends membership_renewal_request's
    -- chk_mem_renewal_req_review_consistency to a second decision stage):
    --   PENDING_SOURCE_RELEASE       -> no source or destination decision yet.
    --   PENDING_DESTINATION_ACCEPT   -> source decided (released); no
    --                                    destination decision yet.
    --   REJECTED_BY_SOURCE           -> source decided (rejected); no
    --                                    destination decision (never reached).
    --   COMPLETED / REJECTED_BY_DESTINATION
    --                                -> both source and destination decided.
    CONSTRAINT chk_mem_change_req_review_consistency
        CHECK
        (
            (
                status = 'PENDING_SOURCE_RELEASE'
                AND source_decided_by_sangha_sevi_pk IS NULL
                AND source_decided_at IS NULL
                AND destination_decided_by_sangha_sevi_pk IS NULL
                AND destination_decided_at IS NULL
            )
            OR
            (
                status IN ('PENDING_DESTINATION_ACCEPT', 'REJECTED_BY_SOURCE')
                AND source_decided_by_sangha_sevi_pk IS NOT NULL
                AND source_decided_at IS NOT NULL
                AND destination_decided_by_sangha_sevi_pk IS NULL
                AND destination_decided_at IS NULL
            )
            OR
            (
                status IN ('COMPLETED', 'REJECTED_BY_DESTINATION')
                AND source_decided_by_sangha_sevi_pk IS NOT NULL
                AND source_decided_at IS NOT NULL
                AND destination_decided_by_sangha_sevi_pk IS NOT NULL
                AND destination_decided_at IS NOT NULL
            )
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_mem_change_req_sevi
    ON nss.membership_change_request (sangha_sevi_pk);

CREATE INDEX IF NOT EXISTS idx_mem_change_req_status
    ON nss.membership_change_request (status);

CREATE INDEX IF NOT EXISTS idx_mem_change_req_old_org
    ON nss.membership_change_request (old_organization_pk);

CREATE INDEX IF NOT EXISTS idx_mem_change_req_new_org
    ON nss.membership_change_request (new_organization_pk);

-- One open (non-terminal-status) request per member at a time — mirrors
-- uq_registration_claim_one_pending (06_authentication/03_registration_claim.sql).
CREATE UNIQUE INDEX IF NOT EXISTS uq_mem_change_req_one_open
    ON nss.membership_change_request (sangha_sevi_pk)
    WHERE status IN ('PENDING_SOURCE_RELEASE', 'PENDING_DESTINATION_ACCEPT');
