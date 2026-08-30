# NSS ERP — Administration Correspondence Register ERD

**Document ID:** SOL-ADMIN-006
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Administration (Correspondence Register Capability)
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design for the Administration-owned Correspondence Register capability.

The Correspondence Register records inward and outward official communications. It does not own domain-specific business requests, financial transactions, or document storage.

**Governing Decision:** CORR-DECISION-003 (ARCH-CROSS-001 §16)

---

# 2. Entities

The Correspondence Register introduces three Administration-owned entities:

    correspondence
    correspondence_document
    correspondence_finance_reference

No existing Administration tables (RBAC foundation) are modified.

---

# 3. High-Level ERD

    Foundation                          Person              Organization
    ├── master_data                       │                       │
    ├── id_sequence_master                │                       │
    └── document_master                   │                       │
             ▲                            │                       │
             │                            │                       │
    ┌────────────────────────┐            │                       │
    │ correspondence_document│            │                       │
    └───────────┬────────────┘            │                       │
                │ N:1                     │                       │
                ▼                         │                       │
    ┌────────────────────────────────────────────────────────────────────┐
    │                        correspondence                              │
    ├────────────────────────────────────────────────────────────────────┤
    │ direction                                                          │
    │ sender (person / organization / external)                          │
    │ recipient (person / organization / external)                       │
    │ responsible_person → Person                                        │
    │ responsible_organization → Organization                            │
    │ medium → Foundation.master_data                                    │
    │ status → Foundation.master_data                                    │
    │ reference_number (via Foundation.id_sequence_master)                │
    └────────────────────────────────────┬───────────────────────────────┘
                                         │
                                         │ 1:N (optional)
                                         ▼
                        ┌─────────────────────────────────────┐
                        │ correspondence_finance_reference    │
                        └────────────────────┬────────────────┘
                                             │ N:1
                                             ▼
                                  Finance.financial_transaction

---

# 4. correspondence

## 4.1 Purpose

Records an official communication entering or leaving the organization.

A single table handles both inward and outward correspondence, distinguished by the direction attribute.

## 4.2 ERD Decision #1 — Single Table

Inward and outward correspondence share the same structural attributes. A single correspondence table with a direction discriminator is preferred over separate tables.

This decision may be revisited during Table Design only if materially different attribute sets emerge.

## 4.3 Direction

    INWARD   — communication received by NSS
    OUTWARD  — communication sent by NSS

Direction is a controlled value.

## 4.4 Sender and Recipient Model

A sender or recipient may be:

    NSS PERSON         — a known person in the ERP (FK to person)
    NSS ORGANIZATION   — a known organizational unit (FK to organization)
    EXTERNAL           — a party not represented in the ERP (free-text details)

### ERD Decision #2 — Addressee Representation

The ERD establishes the following representation:

    correspondence
    ├── sender_type                    (controlled: PERSON / ORGANIZATION / EXTERNAL)
    ├── sender_person_pk               (nullable FK → person.person_pk)
    ├── sender_organization_pk         (nullable FK → organization.organization_pk)
    ├── sender_external_name           (nullable — for EXTERNAL type)
    ├── sender_external_organization   (nullable — for EXTERNAL type)
    │
    ├── recipient_type                 (controlled: PERSON / ORGANIZATION / EXTERNAL)
    ├── recipient_person_pk            (nullable FK → person.person_pk)
    ├── recipient_organization_pk      (nullable FK → organization.organization_pk)
    ├── recipient_external_name        (nullable — for EXTERNAL type)
    └── recipient_external_organization (nullable — for EXTERNAL type)

**Constraint:** Exactly one of (person_pk, organization_pk, external_name) shall be populated for each sender/recipient, determined by the type.

**Alternative considered and deferred:** A separate correspondence_party junction table. Deferred because:

- Correspondence has exactly one sender and one recipient
- The inline representation is simpler for a 1:1 relationship
- No requirement for multiple senders/recipients per correspondence

This decision may be revisited during Table Design if additional party requirements emerge (e.g., CC recipients, distribution lists).

## 4.5 Responsible Person

    responsible_person_pk → person.person_pk

The person responsible for acting on or following up the correspondence. FK to Person, not to user_account, because responsibility may fall on a person who does not have an ERP login.

## 4.6 Responsible Organization

    responsible_organization_pk → organization.organization_pk

The NSS organizational unit responsible for this correspondence/register entry. This identifies which part of the organization owns or is accountable for this communication (e.g., Kendra Office, a specific Sakha).

This is distinct from sender/recipient organization. For example:

    Sender:       District Collector (EXTERNAL)
    Recipient:    Kendra Sangha (ORGANIZATION)
    Responsible:  Kendra Office (responsible_organization_pk)

## 4.7 Medium

    medium_master_data_pk → Foundation.master_data.master_data_pk

Controlled through Foundation master data. Initial values:

    POST
    EMAIL
    HAND_DELIVERY
    CIRCULAR
    FAX
    COURIER

Extensible without schema change.

## 4.8 Status

    status_master_data_pk → Foundation.master_data.master_data_pk

Controlled through Foundation master data. Initial values:

    REGISTERED
    PENDING_ACTION
    ACTIONED
    CLOSED

Extensible without schema change. The semantic distinction between ACTIONED and CLOSED is defined in the Lifecycle document.

## 4.9 Reference Numbering

Uses Foundation id_sequence_master mechanism.

Format:

    INWARD:   NSS/IN/YYYY-YY/NNN
    OUTWARD:  NSS/OUT/YYYY-YY/NNN

Sequence resets annually following the NSS annual numbering period (01 April – 31 March). The sequence-period implementation and exact formatting are defined in Business Rules and Table Design. No FK to Finance is required.

## 4.10 Dates

    correspondence_date    — date of the communication itself
    received_or_sent_date  — date NSS received (inward) or sent (outward)
    follow_up_date         — expected follow-up date (nullable)

## 4.11 Subject and Remarks

    subject    — brief subject/title of the communication
    remarks    — additional notes (nullable)

---

# 5. correspondence_document

## 5.1 Purpose

Associates documents (scanned letters, attachments, enclosures, response copies) with a correspondence record.

This is an Administration-owned junction table following the DOC-ARCH-001 pattern (no polymorphic entity FK in document_master).

## 5.2 Relationship

    correspondence
         │
         │ 1:N
         ▼
    correspondence_document
         │
         │ N:1
         ▼
    Foundation.document_master

A correspondence record may have zero or more associated documents.

A document may be associated with multiple correspondence records (e.g., the same circular distributed to multiple recipients, or a document referenced in both original and response). The operational implications of shared document references are addressed in Business Rules.

## 5.3 Document Purpose

    document_purpose — controlled value

Initial values:

    ORIGINAL           — the original communication document
    RESPONSE           — a response to this correspondence
    ATTACHMENT         — an attachment/enclosure
    SUPPORTING         — supporting/reference document

Whether this is CHECK-constrained or master-data-driven is a Table Design decision.

---

# 6. correspondence_finance_reference

## 6.1 Purpose

Records the M:N relationship between correspondence and Finance transactions. This is not limited to payment-related correspondence — any Finance transaction (donation, purchase, tax payment, refund, salary, bank transaction, adjustment) may have related correspondence, and any correspondence may relate to multiple Finance transactions. Neither side is mandatory.

Administration does not own or duplicate the financial transaction. Finance remains the authoritative owner under FIN-ARCH-001.

**Governing Principle:** CORR-ARCH-001 — Financial Traceability

> Where a correspondence results in, refers to, or requires a financial transaction, the correspondence record shall be capable of referencing the corresponding Finance transaction. Correspondence shall not create, own, or duplicate financial transaction data.

## 6.2 Relationship

    correspondence (M)
         │
         │ M:N (via junction)
         │
    correspondence_finance_reference
         │
         │
         ▼
    Finance.financial_transaction (N)

- One correspondence can relate to several Finance transactions (e.g., government demand → tax ₹10,000 + penalty ₹500 → two transactions)
- One Finance transaction can relate to multiple correspondence records (e.g., payment → original demand + reminder + payment confirmation)
- Neither side is mandatory

## 6.3 Attributes

    correspondence_finance_reference_pk    (UUID)
    correspondence_pk                      (FK → correspondence)
    financial_transaction_pk               (FK → Finance.financial_transaction)
    relationship_type                      (controlled — values TBD in Business Rules)
    remarks                                (nullable)
    --- standard audit columns ---

## 6.4 Relationship Type

Candidate values (NOT frozen — to be established in Business Rules based on actual Finance model):

    PAYMENT
    RECEIPT
    REFUND
    TAX
    ADJUSTMENT
    OTHER

Whether this is CHECK-constrained or master-data-driven is a Table Design decision.

## 6.5 Optional Cross-Module Reference

This table creates an optional reference to Finance. It is not a mandatory dependency:

- Most correspondence records will have zero finance references
- The FK to financial_transaction is populated only when a genuine financial consequence exists
- Administration can function fully without Finance being implemented (the junction table simply remains empty until Finance is available)

---

# 7. Cross-Module Traceability Architecture

## 7.1 CORR-ARCH-002 — Cross-Module Record Traceability (Reusable Platform Capability)

Correspondence is a reusable cross-module capability. Administration owns the Correspondence Register, but any module may use it to record, associate, and trace official communications related to that module's business records. The consuming module remains the owner of its business process and records.

A module may associate its forms, applications, requests, transactions, or other business records with correspondence without transferring ownership of those records to Administration.

## 7.2 Module Usage Examples

| Module | Example Correspondence Use |
|--------|---------------------------|
| Membership | Renewal application, membership-related letters, Gruhasana requests |
| Sevak | Sevak application/request/correspondence |
| Governance | Submission to President/Secretary, committee communications |
| Assets & Property | Government property notice, land correspondence, statutory demands |
| Finance | Vendor/bank/tax correspondence linked to transactions |
| Organization | Reorganization/re-parenting communication |
| Person | Person-related applications or official documents |
| Programmes & Events | Venue requests, external invitations, event correspondence |

## 7.3 Form vs Application vs Correspondence

Three distinct concepts:

    FORM
        Structured information the user fills in.

    APPLICATION
        A request submitted by a person/organization,
        potentially using a form.

    CORRESPONDENCE
        The official communication/document associated
        with that application or business matter.

Example — Membership Renewal:

    Membership
        └── membership_renewal_request (Membership owns)
                 ├── Renewal Form data
                 ├── Gruhasana Renewal data
                 └── Correspondence references (Administration provides)
                        ├── Application submitted
                        ├── Supporting letter
                        └── Response

The owning module retains its business process. Administration provides the correspondence facility.

## 7.4 Candidate Cross-Module References

Beyond Finance, correspondence may need to reference:

    Correspondence
         │
         ├── Finance transaction
         │      └── donation / purchase / tax / refund / salary / bank / adjustment
         │
         ├── Membership record
         │      └── renewal / application
         │
         ├── Governance record
         │      └── resolution / decision
         │
         ├── Assets & Property record
         │      └── property / maintenance / statutory matter
         │
         ├── Organization record
         │      └── organizational change
         │
         └── Person record
                └── member/person-related correspondence

## 7.5 Current Physical Implementation

Only correspondence_finance_reference is established as a concrete table in this ERD, because:

- Finance transactions are the most clearly justified cross-module reference for correspondence
- The relationship pattern (M:N, optional, junction) is demonstrated and proven

## 7.6 General Mechanism — Deferred

The physical mechanism for references to other modules (Membership, Governance, Assets & Property, Organization) is deferred to Table Design.

Possible approaches include:

- Module-specific junction tables (e.g., correspondence_property_reference)
- A general-purpose reference table with controlled target-type/target-pk columns
- No additional junction tables (UI-level linking without FK enforcement)

The choice depends on:

- Which cross-module references are operationally required vs. nice-to-have
- Whether PostgreSQL FK enforcement is needed (type-specific junctions) or referential integrity can be application-enforced (generic reference)
- Whether the relationship is bidirectional at the schema level

This ERD does not freeze the general mechanism. It freezes only the Finance-specific junction because Finance traceability has a clear, immediate operational justification.

**Explicitly excluded:** A giant polymorphic related_record_type + related_record_pk table. Each cross-module relationship needs proper architectural design with typed FKs where referential integrity is required.

## 7.7 ERP Questions This Enables

Cross-module traceability enables the ERP to answer:

- "Why did this transaction happen?" → Find the correspondence.
- "What happened because of this letter?" → Find Finance transactions and other related records.
- "What communications relate to this renewal?" → Find correspondence linked to Membership record.
- "Show all correspondence for this property" → Find correspondence linked to Assets & Property record.

## 7.8 Bidirectional Visibility

Cross-module references shall support bidirectional visibility:

- From correspondence: "Related Records" showing linked Finance transactions, properties, etc.
- From the referenced record: "Related Correspondence" showing linked communications

This is a UI/query concern, not necessarily a schema concern. The junction table provides the data; the application presents it from both directions.

---

# 8. Cross-Module Dependencies

| External Module | Relationship | Direction | Mandatory? |
|----------------|-------------|-----------|------------|
| Foundation | master_data (medium, status) | Administration consumes | Yes |
| Foundation | id_sequence_master (reference numbering) | Administration consumes | Yes |
| Foundation | document_master (via correspondence_document) | Administration consumes | Yes |
| Person | person (sender, recipient, responsible person) | Administration references | Yes |
| Organization | organization (sender, recipient, responsible org) | Administration references | Yes |
| Finance | financial_transaction (via correspondence_finance_reference) | Administration references | No — optional |

## 8.1 What Is NOT a Mandatory Dependency

| Module | Relationship |
|--------|-------------|
| Finance (financial_year) | No FK to financial_year; numbering uses Foundation sequence with NSS annual period |
| Finance (financial_transaction) | Optional cross-module reference via junction; Administration functions without Finance |
| Membership | Correspondence does not own membership requests; future traceability TBD |
| Governance | Correspondence does not own authority decisions; future traceability TBD |
| Assets & Property | Correspondence does not own property records; future traceability TBD |
| Authentication | Responsibility ≠ ERP login |

---

# 9. Ownership Boundaries

## 9.1 Administration Owns

    correspondence
    correspondence_document
    correspondence_finance_reference

## 9.2 Administration Does NOT Own

    Foundation.document_master          — Foundation
    Foundation.master_data              — Foundation
    Foundation.id_sequence_master       — Foundation
    Person.person                       — Person
    Organization.organization           — Organization
    Finance.financial_transaction       — Finance
    Domain-specific request lifecycles  — Respective modules
    Financial transactions              — Finance

## 9.3 FIN-ARCH-001 Compliance

Correspondence does not create or own financial transaction records. Where a communication results in a financial obligation or payment, Finance owns the transaction; correspondence records the communication and may reference the Finance transaction via correspondence_finance_reference.

## 9.4 Reusable Capability Boundary

Administration owns the Correspondence Register infrastructure. Consuming modules (Membership, Governance, Finance, Assets & Property, etc.) use the capability but do not transfer ownership of their business records to Administration.

    Membership owns → membership_renewal_request
    Administration provides → correspondence registration and traceability
    Neither owns the other's records

---

# 10. Relationship to Existing Administration Tables

The Correspondence Register is a separate capability within Administration. It has no FK relationship to the RBAC tables:

    RBAC Foundation                 Correspondence Register
    ├── role_master                 ├── correspondence
    ├── permission_master           ├── correspondence_document
    ├── role_permission             └── correspondence_finance_reference
    ├── user_role
    └── admin_scope

These are independent concerns within the same owning module. Authorization for correspondence operations uses the standard RBAC mechanism (permission + scope) but there is no schema coupling between the two entity groups.

---

# 11. Cardinality Summary

| Relationship | Cardinality |
|-------------|-------------|
| correspondence → correspondence_document | 1:N |
| correspondence_document → document_master | N:1 |
| correspondence → correspondence_finance_reference | 1:N |
| correspondence_finance_reference → financial_transaction | N:1 |
| correspondence ↔ financial_transaction (effective) | M:N |
| correspondence → person (sender) | N:1 (nullable) |
| correspondence → organization (sender) | N:1 (nullable) |
| correspondence → person (recipient) | N:1 (nullable) |
| correspondence → organization (recipient) | N:1 (nullable) |
| correspondence → person (responsible) | N:1 |
| correspondence → organization (responsible) | N:1 |
| correspondence → master_data (medium) | N:1 |
| correspondence → master_data (status) | N:1 |

---

# 12. Tables Not Introduced

This ERD does not introduce:

    correspondence_party                    — deferred; inline representation chosen
    correspondence_thread                   — no threading requirement established
    correspondence_workflow                  — no workflow engine
    correspondence_template                  — no template mechanism
    correspondence_approval                  — no approval table (domain modules own their approvals)
    correspondence_membership_reference      — deferred; general mechanism TBD in Table Design
    correspondence_property_reference        — deferred; general mechanism TBD in Table Design
    correspondence_governance_reference      — deferred; general mechanism TBD in Table Design
    correspondence_generic_reference         — rejected; no polymorphic table
    inward_correspondence                    — merged into single table
    outward_correspondence                   — merged into single table

---

# 13. Open Questions

| Question | Status |
|----------|--------|
| CC/distribution list support | DEFERRED — no current requirement |
| Correspondence threading (reply chains) | DEFERRED — no current requirement |
| External party master (contacts database) | DEFERRED — free text for now |
| General cross-module reference mechanism (beyond Finance) | DEFERRED — Table Design decision |
| document_purpose controlled via master_data or CHECK | Table Design decision |
| sender_type/recipient_type controlled via master_data or CHECK | Table Design decision |
| relationship_type (finance ref) controlled via master_data or CHECK | Table Design decision |
| Exact nullable FK constraint enforcement mechanism | Table Design decision |

---

# 14. ERD Decisions Frozen

| Decision | Status |
|----------|--------|
| ERD Decision #1 — Single correspondence table with direction | FROZEN |
| ERD Decision #2 — Inline addressee (person/org/external) with type discriminator | FROZEN |
| Medium via Foundation master_data | FROZEN |
| Status via Foundation master_data | FROZEN |
| Reference numbering via Foundation id_sequence_master (NSS annual period) | FROZEN |
| Responsible person FK to person (not user_account) | FROZEN |
| No Finance FK dependency for numbering | FROZEN |
| DOC-ARCH-001 pattern for document association | FROZEN |
| CORR-ARCH-001 — Finance traceability via optional M:N junction | FROZEN |
| CORR-ARCH-002 — General cross-module traceability as reusable platform capability | FROZEN |
| Finance is optional cross-module reference, not mandatory dependency | FROZEN |
| No polymorphic related_record_type + related_record_pk table | FROZEN |
| General cross-module reference physical mechanism | OPEN — Table Design |

---

# 15. Architectural Principles Established

## CORR-ARCH-001 — Financial Traceability

Where a correspondence results in, refers to, or requires a financial transaction, the correspondence record shall be capable of referencing the corresponding Finance transaction. This is not limited to payments — any Finance transaction (donation, purchase, tax, refund, salary, bank, adjustment) may have related correspondence. Correspondence shall not create, own, or duplicate financial transaction data. Finance remains the authoritative owner of the financial transaction.

## CORR-ARCH-002 — Cross-Module Record Traceability (Reusable Platform Capability)

Correspondence is a reusable cross-module capability. Administration owns the Correspondence Register, but any module may use it to record, associate, and trace official communications related to that module's business records. The consuming module remains the owner of its business process and records. A module may associate its forms, applications, requests, transactions, or other business records with correspondence without transferring ownership of those records to Administration.

---

# 16. Status

DOCUMENT STATUS:

    DRAFT — SOURCE ALIGNED

VERSION:

    1.0.0
