-- =====================================================
-- NSS ERP
-- Module: Administration (Correspondence Register capability)
-- File: 02_correspondence_document.sql
-- Table: nss.correspondence_document
-- Depth: 5 (depends on correspondence, document_master)
-- Version: 1.0
-- Authority: SOL-ADMIN-009 §5, DOC-ARCH-001 (no polymorphic
--            entity FK in document_master)
-- Owner: Administration
--
-- Design decisions:
--   - Associates Foundation document_master rows with a
--     correspondence record; document_purpose distinguishes the
--     role a document plays (original letter, response, attachment,
--     supporting evidence).
--   - UNIQUE (correspondence_pk, document_master_pk, document_purpose):
--     the same document for the same correspondence in the same role
--     is a duplicate; the same document may be attached under a
--     different purpose.
--   - Dissociation is soft-delete only; no physical deletion
--     (SOL-ADMIN-009 §9).
--
-- Note: Audit actor FKs (*_by_sangha_sevi_pk) are NULLABLE columns
--       included in Pass 1. Their FK constraints are deferred to
--       Pass 2, per project-wide two-pass DDL convention.
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.correspondence_document
(
    -- ── Identity ────────────────────────────────────────

    correspondence_document_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    correspondence_pk UUID NOT NULL,

    document_master_pk UUID NOT NULL,

    document_purpose VARCHAR(20) NOT NULL,

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

    CONSTRAINT fk_corr_doc_correspondence
        FOREIGN KEY (correspondence_pk)
        REFERENCES nss.correspondence (correspondence_pk),

    CONSTRAINT fk_corr_doc_document
        FOREIGN KEY (document_master_pk)
        REFERENCES nss.document_master (document_master_pk),

    -- ── Unique Constraints ──────────────────────────────

    CONSTRAINT uq_corr_doc_correspondence_document_purpose
        UNIQUE (correspondence_pk, document_master_pk, document_purpose),

    -- ── CHECK Constraints ───────────────────────────────

    CONSTRAINT chk_corr_doc_purpose
        CHECK (document_purpose IN ('ORIGINAL', 'RESPONSE', 'ATTACHMENT', 'SUPPORTING')),

    CONSTRAINT chk_corr_doc_soft_delete
        CHECK
        (
            (is_active = TRUE AND deleted_at IS NULL)
            OR
            (is_active = FALSE AND deleted_at IS NOT NULL)
        )
);

-- ── Indexes ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_corr_doc_correspondence
    ON nss.correspondence_document (correspondence_pk);

CREATE INDEX IF NOT EXISTS idx_corr_doc_document
    ON nss.correspondence_document (document_master_pk);

CREATE INDEX IF NOT EXISTS idx_corr_doc_active
    ON nss.correspondence_document (is_active);
