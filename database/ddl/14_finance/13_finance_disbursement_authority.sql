-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 13_finance_disbursement_authority.sql
-- Table: nss.finance_disbursement_authority
-- Depth: 7 (depends on financial_payment, financial_transfer, master_data, person)
-- Version: 1.0
-- Authority: NSS Bye-Law F[A](vi), F[b], F[c](i)(ii)(iii)(iv)(v), Duties of the
--            Treasurer (7)(a)(b); Mahila Sangha Bye-Law 6(viii), 7(ii), 7(iii);
--            business rules FIN-BR-029, FIN-BR-039, FIN-BR-040, FIN-BR-043,
--            FIN-BR-045, FIN-BR-046, FIN-BR-048..050.
-- Owner: NSS_ERP_ADMIN
-- Note: One row per DISBURSEMENT (a payment, or a transfer OUT of a Kendra /
--       central Mahila Sangha scope) that those Bye-Laws govern. It keeps the
--       three Kendra steps SEPARATE (FIN-BR-040):
--         1. scheme approval by the Governing Body (resolution reference/date,
--            scheme, permitted purpose),
--         2. the President's written order (Kendra only),
--         3. disbursement by the Treasurer, jointly operated with the
--            Secretary (F[b] / MS-7(ii)): two different office-bearers sign.
--       bye_law_basis KENDRA needs the President's order; MAHILA needs the
--       Parichalak consultation flag (MS-7(iii)(a)) instead. Other levels
--       (Anchalika, Zilla, Sakha, events) have NO row: their authorization
--       matrix is PENDING and is not invented from the Kendra rules (FIN-BR-044).
--       The signers are the office-bearers sitting in the Treasurer / Secretary
--       seat at the moment they sign (recorded as person_pk).
-- =====================================================

CREATE TABLE IF NOT EXISTS nss.finance_disbursement_authority
(
    finance_disbursement_authority_pk UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    financial_payment_pk UUID NULL,

    financial_transfer_pk UUID NULL,

    bye_law_basis VARCHAR(10) NOT NULL,

    -- Step 1: Governing Body scheme approval / resolution (F[c](i), MS-7(iii)(i)).
    resolution_reference VARCHAR(100) NOT NULL,

    resolution_date DATE NOT NULL,

    scheme_description TEXT NOT NULL,

    -- Permitted purpose (F[c](ii)-(v), F[A](vi), MS-7(iii)); master_data DISBURSEMENT_PURPOSE.
    purpose_master_data_pk UUID NOT NULL,

    parichalak_consulted BOOLEAN NOT NULL
        DEFAULT FALSE,

    -- Step 2: the President's written order (Kendra, Treasurer duty (7)(b)).
    president_order_reference VARCHAR(100) NULL,

    president_order_date DATE NULL,

    president_person_pk UUID NULL,

    -- Step 3: joint operation by the Treasurer and the Secretary (F[b], MS-7(ii)).
    treasurer_person_pk UUID NULL,

    treasurer_signed_at TIMESTAMPTZ NULL,

    secretary_person_pk UUID NULL,

    secretary_signed_at TIMESTAMPTZ NULL,

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

    CONSTRAINT fk_fda_payment
        FOREIGN KEY (financial_payment_pk)
        REFERENCES nss.financial_payment (financial_payment_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fda_transfer
        FOREIGN KEY (financial_transfer_pk)
        REFERENCES nss.financial_transfer (financial_transfer_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fda_purpose
        FOREIGN KEY (purpose_master_data_pk)
        REFERENCES nss.master_data (master_data_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fda_president
        FOREIGN KEY (president_person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fda_treasurer
        FOREIGN KEY (treasurer_person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    CONSTRAINT fk_fda_secretary
        FOREIGN KEY (secretary_person_pk)
        REFERENCES nss.person (person_pk) ON DELETE RESTRICT,

    -- A disbursement is exactly one of: a payment, a transfer.
    CONSTRAINT chk_fda_one_target
        CHECK ((financial_payment_pk IS NOT NULL) <> (financial_transfer_pk IS NOT NULL)),

    CONSTRAINT chk_fda_basis
        CHECK (bye_law_basis IN ('KENDRA', 'MAHILA')),

    CONSTRAINT chk_fda_text_not_blank
        CHECK (BTRIM(resolution_reference) <> '' AND BTRIM(scheme_description) <> ''),

    -- Kendra: the order of the President is mandatory and complete (FIN-BR-040).
    CONSTRAINT chk_fda_kendra_president_order
        CHECK (bye_law_basis <> 'KENDRA'
               OR (president_order_reference IS NOT NULL AND BTRIM(president_order_reference) <> ''
                   AND president_order_date IS NOT NULL AND president_person_pk IS NOT NULL)),

    -- The order cannot predate the scheme it executes.
    CONSTRAINT chk_fda_order_after_resolution
        CHECK (president_order_date IS NULL OR president_order_date >= resolution_date),

    -- A signature is a (person, time) pair; the two signers are different persons.
    CONSTRAINT chk_fda_treasurer_pair
        CHECK ((treasurer_person_pk IS NULL) = (treasurer_signed_at IS NULL)),

    CONSTRAINT chk_fda_secretary_pair
        CHECK ((secretary_person_pk IS NULL) = (secretary_signed_at IS NULL)),

    CONSTRAINT chk_fda_joint_signers_differ
        CHECK (treasurer_person_pk IS NULL OR secretary_person_pk IS NULL OR treasurer_person_pk <> secretary_person_pk),

    -- Joint operation: the Secretary countersigns only after the Treasurer.
    CONSTRAINT chk_fda_secretary_after_treasurer
        CHECK (secretary_person_pk IS NULL OR treasurer_person_pk IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fda_payment
    ON nss.finance_disbursement_authority (financial_payment_pk) WHERE financial_payment_pk IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_fda_transfer
    ON nss.finance_disbursement_authority (financial_transfer_pk) WHERE financial_transfer_pk IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fda_purpose
    ON nss.finance_disbursement_authority (purpose_master_data_pk);
