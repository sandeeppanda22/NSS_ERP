# NSS ERP — Administration Correspondence Register Table Design

**Document ID:** SOL-ADMIN-009
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration (Correspondence Register Capability)
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the table-design baseline for the Administration-owned Correspondence Register capability.

The Correspondence Register introduces three tables:

    correspondence
    correspondence_document
    correspondence_finance_reference

These tables extend the Administration module's ownership inventory alongside the existing RBAC tables (SOL-ADMIN-004). No RBAC tables are modified.

**Governing ERD:** SOL-ADMIN-006
**Governing Lifecycle:** SOL-ADMIN-007
**Governing Business Rules:** SOL-ADMIN-008

---

# 2. Table Ownership Declaration

**Administration OWNS (DDL authority):**

    correspondence
    correspondence_document
    correspondence_finance_reference

**Administration REFERENCES via FK (does not own):**

    Foundation.master_data
    Foundation.document_master
    Person.person
    Organization.organization
    Finance.financial_transaction (optional — may not exist at deployment time)

**Application/Service Dependency (no FK):**

    Foundation.id_sequence_master (used by reference-number generation service)

id_sequence_master is consumed by the application layer to generate reference numbers. It is not an FK target of any correspondence column. This distinction follows the same principle as Finance: do not create database dependencies where an application-level service/reference is sufficient.

---

# 3. Database Standards Applied

All tables follow the project-wide database standards:

    Primary key naming:    <table_name>_pk
    Primary key type:      UUID
    FK naming:             <referenced_table>_pk (or prefixed for disambiguation)
    Audit columns:         created_at, created_by_sangha_sevi_pk,
                           updated_at, updated_by_sangha_sevi_pk,
                           deleted_at, deleted_by_sangha_sevi_pk
    Soft-delete:           is_active (BOOLEAN, DEFAULT TRUE)
    Naming convention:     snake_case

---

# 4. correspondence

## 4.1 Purpose

Records an official inward or outward communication registered by NSS.

## 4.2 Primary Key

    correspondence_pk    UUID    NOT NULL

## 4.3 Columns

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| correspondence_pk | UUID | NOT NULL | PK |
| reference_number | VARCHAR | NOT NULL | System-generated, immutable, UNIQUE |
| direction | VARCHAR | NOT NULL | Controlled: INWARD / OUTWARD |
| correspondence_date | DATE | NOT NULL | Date on the communication |
| received_or_sent_date | DATE | NOT NULL | Date NSS received (in) or sent (out) |
| follow_up_date | DATE | NULL | Target follow-up date |
| subject | VARCHAR | NOT NULL | Brief subject/title |
| remarks | TEXT | NULL | Additional notes |
| sender_type | VARCHAR | NOT NULL | Controlled: PERSON / ORGANIZATION / EXTERNAL |
| sender_person_pk | UUID | NULL | FK → person.person_pk |
| sender_organization_pk | UUID | NULL | FK → organization.organization_pk |
| sender_external_name | VARCHAR | NULL | Free text — external party name |
| sender_external_organization | VARCHAR | NULL | Free text — external party organization |
| recipient_type | VARCHAR | NOT NULL | Controlled: PERSON / ORGANIZATION / EXTERNAL |
| recipient_person_pk | UUID | NULL | FK → person.person_pk |
| recipient_organization_pk | UUID | NULL | FK → organization.organization_pk |
| recipient_external_name | VARCHAR | NULL | Free text — external party name |
| recipient_external_organization | VARCHAR | NULL | Free text — external party organization |
| responsible_person_pk | UUID | NULL | FK → person.person_pk |
| responsible_organization_pk | UUID | NULL | FK → organization.organization_pk |
| medium_master_data_pk | UUID | NOT NULL | FK → master_data.master_data_pk |
| status_master_data_pk | UUID | NOT NULL | FK → master_data.master_data_pk |
| is_active | BOOLEAN | NOT NULL | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL | |
| created_by_sangha_sevi_pk | UUID | NOT NULL | FK → (audit actor) |
| updated_at | TIMESTAMPTZ | NOT NULL | |
| updated_by_sangha_sevi_pk | UUID | NOT NULL | FK → (audit actor) |
| deleted_at | TIMESTAMPTZ | NULL | Soft-delete timestamp |
| deleted_by_sangha_sevi_pk | UUID | NULL | FK → (audit actor) |

## 4.4 Foreign Keys

| Column | References |
|--------|-----------|
| sender_person_pk | person.person_pk |
| sender_organization_pk | organization.organization_pk |
| recipient_person_pk | person.person_pk |
| recipient_organization_pk | organization.organization_pk |
| responsible_person_pk | person.person_pk |
| responsible_organization_pk | organization.organization_pk |
| medium_master_data_pk | master_data.master_data_pk |
| status_master_data_pk | master_data.master_data_pk |
| created_by_sangha_sevi_pk | (audit actor — deferred FK per two-pass DDL) |
| updated_by_sangha_sevi_pk | (audit actor — deferred FK per two-pass DDL) |
| deleted_by_sangha_sevi_pk | (audit actor — deferred FK per two-pass DDL) |

## 4.5 Unique Constraints

    UNIQUE (reference_number)

## 4.6 CHECK Constraints

    direction IN ('INWARD', 'OUTWARD')

    -- Sender conditional integrity
    CHECK (
        (sender_type = 'PERSON'
            AND sender_person_pk IS NOT NULL
            AND sender_organization_pk IS NULL
            AND sender_external_name IS NULL
            AND sender_external_organization IS NULL)
     OR
        (sender_type = 'ORGANIZATION'
            AND sender_person_pk IS NULL
            AND sender_organization_pk IS NOT NULL
            AND sender_external_name IS NULL
            AND sender_external_organization IS NULL)
     OR
        (sender_type = 'EXTERNAL'
            AND sender_person_pk IS NULL
            AND sender_organization_pk IS NULL
            AND sender_external_name IS NOT NULL)
            -- sender_external_organization remains optional for EXTERNAL
    )

    -- Recipient conditional integrity
    CHECK (
        (recipient_type = 'PERSON'
            AND recipient_person_pk IS NOT NULL
            AND recipient_organization_pk IS NULL
            AND recipient_external_name IS NULL
            AND recipient_external_organization IS NULL)
     OR
        (recipient_type = 'ORGANIZATION'
            AND recipient_person_pk IS NULL
            AND recipient_organization_pk IS NOT NULL
            AND recipient_external_name IS NULL
            AND recipient_external_organization IS NULL)
     OR
        (recipient_type = 'EXTERNAL'
            AND recipient_person_pk IS NULL
            AND recipient_organization_pk IS NULL
            AND recipient_external_name IS NOT NULL)
            -- recipient_external_organization remains optional for EXTERNAL
    )

## 4.7 Application-Enforced Constraints

The following constraints are enforced at the application level in addition to the database CHECK constraints:

- correspondence_date must not be in the future
- received_or_sent_date must not be in the future
- PENDING_ACTION state requires responsible_person_pk OR responsible_organization_pk

Rationale: Date-future validation depends on current time (not a static row constraint). State-transition guards are lifecycle rules enforced by the application state machine.

## 4.8 Indexes

    idx_correspondence_reference_number        — reference_number (covered by UNIQUE)
    idx_correspondence_direction               — direction
    idx_correspondence_status                  — status_master_data_pk
    idx_correspondence_responsible_person      — responsible_person_pk
    idx_correspondence_responsible_org         — responsible_organization_pk
    idx_correspondence_correspondence_date     — correspondence_date
    idx_correspondence_sender_person           — sender_person_pk
    idx_correspondence_recipient_person        — recipient_person_pk

## 4.9 Reference Number Generation

- Generated by application service using Foundation id_sequence_master at record creation
- Format: NSS/{IN|OUT}/YYYY-YY/NNN
- Separate sequences per direction per annual period
- Immutable after assignment
- No FK from correspondence to id_sequence_master — the service reads the sequence configuration and writes the formatted reference_number as a VARCHAR value
- Exact sequence implementation (PostgreSQL SEQUENCE, advisory lock, application counter) is a DDL-phase decision

---

# 5. correspondence_document

## 5.1 Purpose

Associates documents from Foundation document_master with a correspondence record.

Follows DOC-ARCH-001 pattern — no polymorphic entity FK in document_master.

## 5.2 Primary Key

    correspondence_document_pk    UUID    NOT NULL

## 5.3 Columns

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| correspondence_document_pk | UUID | NOT NULL | PK |
| correspondence_pk | UUID | NOT NULL | FK → correspondence.correspondence_pk |
| document_master_pk | UUID | NOT NULL | FK → document_master.document_master_pk |
| document_purpose | VARCHAR | NOT NULL | Controlled value |
| remarks | TEXT | NULL | Optional context for this association |
| is_active | BOOLEAN | NOT NULL | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL | |
| created_by_sangha_sevi_pk | UUID | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |
| updated_by_sangha_sevi_pk | UUID | NOT NULL | |
| deleted_at | TIMESTAMPTZ | NULL | |
| deleted_by_sangha_sevi_pk | UUID | NULL | |

## 5.4 Foreign Keys

| Column | References |
|--------|-----------|
| correspondence_pk | correspondence.correspondence_pk |
| document_master_pk | document_master.document_master_pk |

## 5.5 CHECK Constraints

    document_purpose IN ('ORIGINAL', 'RESPONSE', 'ATTACHMENT', 'SUPPORTING')

## 5.6 Unique Constraints

    UNIQUE (correspondence_pk, document_master_pk, document_purpose)

Rationale: The same document associated with the same correspondence for the same purpose is a duplicate. Different purposes for the same document on the same correspondence are permitted.

## 5.7 Indexes

    idx_corr_doc_correspondence    — correspondence_pk
    idx_corr_doc_document          — document_master_pk

---

# 6. correspondence_finance_reference

## 6.1 Purpose

Records the M:N relationship between correspondence and Finance transactions.

Any Finance transaction type may be referenced. Finance remains the authoritative owner (FIN-ARCH-001). Administration only records the relationship.

## 6.2 Primary Key

    correspondence_finance_reference_pk    UUID    NOT NULL

## 6.3 Columns

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| correspondence_finance_reference_pk | UUID | NOT NULL | PK |
| correspondence_pk | UUID | NOT NULL | FK → correspondence.correspondence_pk |
| financial_transaction_pk | UUID | NOT NULL | FK → financial_transaction.financial_transaction_pk |
| relationship_type | VARCHAR | NOT NULL | Controlled value (PENDING — values TBD) |
| remarks | TEXT | NULL | Optional context |
| is_active | BOOLEAN | NOT NULL | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL | |
| created_by_sangha_sevi_pk | UUID | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |
| updated_by_sangha_sevi_pk | UUID | NOT NULL | |
| deleted_at | TIMESTAMPTZ | NULL | |
| deleted_by_sangha_sevi_pk | UUID | NULL | |

## 6.4 Foreign Keys

| Column | References |
|--------|-----------|
| correspondence_pk | correspondence.correspondence_pk |
| financial_transaction_pk | financial_transaction.financial_transaction_pk |

## 6.5 CHECK Constraints

    relationship_type — mechanism deferred (CHECK or master_data)

Candidate values (PENDING until Finance model frozen):

    PAYMENT
    RECEIPT
    REFUND
    TAX
    ADJUSTMENT
    OTHER

## 6.6 Unique Constraints

    UNIQUE (correspondence_pk, financial_transaction_pk, relationship_type)

Rationale: Prevents duplicate references of the same type. A single correspondence may reference the same transaction with different relationship types if semantically justified.

## 6.7 Indexes

    idx_corr_fin_ref_correspondence     — correspondence_pk
    idx_corr_fin_ref_transaction        — financial_transaction_pk

## 6.8 Optional Dependency

The FK to financial_transaction is an optional cross-module dependency:

- If Finance tables do not yet exist at deployment time, this table may be created without the FK constraint (constraint added in Pass 2 of the two-pass DDL approach)
- The table remains structurally valid even without the FK — application-layer validation ensures referential correctness until the constraint is added
- This follows the same deferred-FK pattern established for audit actor FKs

---

# 7. Cross-Module FK Dependencies

## 7.1 Mandatory FK Dependencies (must exist before correspondence tables)

| Target Table | Owner | Required For |
|-------------|-------|-------------|
| person | Person | sender/recipient/responsible FKs |
| organization | Organization | sender/recipient/responsible FKs |
| master_data | Foundation | medium, status FKs |
| document_master | Foundation | correspondence_document FK |

## 7.2 Optional FK Dependencies (may not exist at deployment time)

| Target Table | Owner | Required For | Strategy |
|-------------|-------|-------------|----------|
| financial_transaction | Finance | correspondence_finance_reference FK | Two-pass DDL — add FK in Pass 2 |

## 7.3 Application/Service Dependencies (no FK)

| Target | Used By | Purpose |
|--------|---------|---------|
| id_sequence_master | Reference number generation service | Sequence configuration for NSS/IN/YYYY-YY/NNN format |

## 7.4 Deferred FK Dependencies (audit actors)

| Target | Required For | Strategy |
|--------|-------------|----------|
| Audit actor table (sangha_sevi / user_account) | created_by / updated_by / deleted_by | Two-pass DDL — add FK in Pass 2 |

---

# 8. DDL Creation Order

Within the Correspondence Register capability:

    1. correspondence              (depends on person, organization, master_data)
    2. correspondence_document     (depends on correspondence, document_master)
    3. correspondence_finance_reference (depends on correspondence; financial_transaction FK deferred)

All three tables are created after Foundation, Person, and Organization tables exist (Tier 1–2 in implementation order).

---

# 9. Soft-Delete Behaviour

All three tables use the standard soft-delete pattern:

    is_active = FALSE
    deleted_at = current timestamp
    deleted_by_sangha_sevi_pk = acting user

Hard-delete is not permitted for correspondence records (CORR-BR-015).

For correspondence_document and correspondence_finance_reference:

- Dissociation uses soft-delete (is_active = FALSE)
- Physical deletion is not performed
- Historical associations remain queryable for audit

---

# 10. ON DELETE Behaviour

| FK | ON DELETE |
|----|----------|
| correspondence_document.correspondence_pk | RESTRICT |
| correspondence_document.document_master_pk | RESTRICT |
| correspondence_finance_reference.correspondence_pk | RESTRICT |
| correspondence_finance_reference.financial_transaction_pk | RESTRICT |
| correspondence.sender_person_pk | RESTRICT |
| correspondence.sender_organization_pk | RESTRICT |
| correspondence.recipient_person_pk | RESTRICT |
| correspondence.recipient_organization_pk | RESTRICT |
| correspondence.responsible_person_pk | RESTRICT |
| correspondence.responsible_organization_pk | RESTRICT |
| correspondence.medium_master_data_pk | RESTRICT |
| correspondence.status_master_data_pk | RESTRICT |

Rationale: No cascading deletes. Referenced records cannot be deleted while correspondence references them. This preserves historical integrity.

---

# 11. Future Cross-Module Reference Tables

## 11.1 Deferred Tables

The following tables are architecturally permitted (CORR-ARCH-002) but not introduced in this design:

    correspondence_membership_reference
    correspondence_property_reference
    correspondence_governance_reference

## 11.2 When to Introduce

These tables should be introduced only when:

- The target module's table design is frozen
- An operational need for FK-enforced cross-module traceability is confirmed
- The junction pattern matches correspondence_finance_reference (same structure)

## 11.3 What Is NOT Introduced

    correspondence_generic_reference (polymorphic — explicitly rejected)

---

# 12. Controlled-Value Strategy

| Field | Enforcement | Justification |
|-------|-------------|---------------|
| direction | CHECK constraint | Fixed binary set — will not change |
| sender_type / recipient_type | CHECK constraint (within compound CHECK) | Fixed ternary set — will not change |
| document_purpose | CHECK constraint | Small, stable set |
| relationship_type | TBD (CHECK or master_data) | PENDING — depends on Finance model |
| medium | FK to master_data | Extensible set — new mediums expected |
| status | FK to master_data | Extensible set — lifecycle states |

---

# 13. Tables NOT Introduced

This table design does not introduce:

    correspondence_history         — NOT introduced; state reconstruction follows the
                                     project-wide Data Change Architecture (audit columns +
                                     Foundation.field_change_log) unless a correspondence-
                                     specific requirement is subsequently established
    correspondence_party           — inline representation chosen (ERD Decision #2)
    correspondence_thread          — no threading requirement
    correspondence_workflow        — no workflow engine
    correspondence_template        — no template mechanism
    correspondence_approval        — no approval table
    correspondence_notification    — no notification table
    correspondence_generic_reference — rejected; no polymorphic table

---

# 14. Open DDL-Phase Decisions

| Decision | Status |
|----------|--------|
| Exact PostgreSQL sequence strategy for reference_number | DDL phase |
| Exact VARCHAR lengths (or use TEXT) | DDL phase |
| Exact index types (btree, GIN for text search) | DDL phase |
| relationship_type enforcement mechanism (CHECK vs master_data FK) | Depends on Finance model |
| Partitioning strategy (if volume warrants) | DDL phase |
| Audit actor FK target table (sangha_sevi vs user_account) | Project-wide decision |

---

# 15. Summary

| Table | Columns (excl. audit) | FKs | Key Constraints |
|-------|----------------------|-----|-----------------|
| correspondence | 20 | 8 mandatory + 3 deferred | UNIQUE(reference_number), CHECK(direction), CHECK(sender conditional), CHECK(recipient conditional) |
| correspondence_document | 4 | 2 | UNIQUE(correspondence_pk, document_master_pk, document_purpose), CHECK(document_purpose) |
| correspondence_finance_reference | 4 | 2 | UNIQUE(correspondence_pk, financial_transaction_pk, relationship_type) |

---

# 16. Status

DOCUMENT STATUS:

    DRAFT — SOURCE ALIGNED

VERSION:

    1.0.0
