# NSS ERP — Cross-Module Architectural Principles

**Document ID:** ARCH-CROSS-001
**Version:** 1.0.0
**Status:** FROZEN — PROJECT-WIDE PRINCIPLES
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines architectural principles that apply across NSS ERP modules.

These principles govern ownership, cross-module references, shared infrastructure, financial transactions, documents, auditability, change history, and future module boundaries.

The purpose is to prevent duplicate ownership, conflicting table definitions, and inconsistent cross-module implementations.

---

# 2. Scope

These principles apply to:

- all existing NSS ERP modules;
- future modules;
- shared infrastructure capabilities;
- cross-module database relationships;
- physical table ownership and DDL authority.

Module-specific business rules remain authoritative within their respective module documentation.

---

# 3. One-Owner-Per-Table Principle

**ARCH-001 — One Physical Table = One Owning Module**

Every physical database table shall have exactly one owning module.

The owning module is responsible for:

- the authoritative table definition;
- business meaning of the data;
- DDL authority;
- schema evolution;
- module-level business rules governing the table.

Other modules may reference or consume the table but shall not create competing definitions of the same physical table.

## 3.1 Shared Does Not Mean Ownerless

A table may be used by many modules while still having one owner.

Example:

```text
Foundation
└── document_master

Person        ───────┐
Heritage      ───────┤
Publications  ───────┼──→ document_master
Other modules ───────┘
```

The consuming modules do not become owners.

---

# 4. Cross-Module Reference Principle

**ARCH-002 — Explicit Cross-Module References**

When one module needs data owned by another module:

* the owning module remains authoritative;
* the consuming module may reference it through an explicit relationship;
* the consuming module shall not duplicate the authoritative record;
* cross-module FK relationships shall be established only where semantically justified.

A shared table shall not be made polymorphic merely for convenience when explicit module-owned relationships can provide referential integrity.

---

# 5. Financial Transaction Ownership

**FIN-ARCH-001 — Finance Is the Sole Owner of Financial Transactions**

Any financial transaction, regardless of the business domain that originates it, belongs to the **Finance module**.

A non-Finance module may:

* originate a business event that results in a financial transaction;
* provide business context;
* classify or reference the transaction where appropriate;
* identify the property, programme, membership, asset, or other business object involved.

A non-Finance module shall **not create or own a duplicate financial transaction table**.

## 5.1 Examples

```text
Asset purchase
    Assets & Property → asset/acquisition context
             ↓
    Finance → purchase/payment transaction

Property tax
    Assets & Property → property/tax obligation context
             ↓
    Finance → tax payment transaction

Property income
    Assets & Property → property/income context
             ↓
    Finance → income transaction

Programme expense
    Programmes & Events → programme/event context
             ↓
    Finance → expense transaction

Membership fee
    Membership → membership context
             ↓
    Finance → financial transaction
```

## 5.2 Boundary

The originating module owns the **business context**.

Finance owns the **financial transaction**.

---

# 6. Common Document Registry

**DOC-ARCH-001 — Foundation-Owned Common Document Registry**

`document_master` is a common document registry owned by the **Foundation module**.

Person does not own `document_master`.

The registry may be referenced by multiple modules where their module designs explicitly establish a document relationship.

Current known consumers include:

* Person;
* Heritage;
* Publications;
* future modules where explicitly required.

## 6.1 Document Ownership Rule

The Foundation-owned registry provides document identity and storage metadata.

Business modules own the business relationship between their entities and documents.

The architecture shall not introduce a generic polymorphic `entity_type/entity_pk` relationship merely for convenience where explicit foreign-key relationships can be used.

## 6.2 Physical Storage

The following remain implementation/DDL concerns unless separately frozen:

* storage provider;
* filesystem/object-storage mechanism;
* exact storage reference format;
* version implementation;
* checksum implementation.

---

# 7. Change History and Data Change Boundaries

NSS ERP separates four concepts:

```text
Audit
  ↓
Who performed an action and when

Change History
  ↓
What data changed

Effective Dating
  ↓
When a value/relationship was valid

Migration
  ↓
What structural transformation occurred
and how entities are related across it
```

## 7.1 Change History

The project uses a hybrid approach:

* module-owned `_history` tables where domain-specific historical state is required;
* shared `field_change_log` owned by Foundation for business-significant field-level changes.

`field_change_log` shall not become an automatic copy of every technical UPDATE.

Routine technical modification tracking remains represented by the applicable audit columns and audit mechanisms.

## 7.2 Migration

Migration is a dedicated capability for structural changes such as:

* rename where structurally significant;
* re-parent;
* transform;
* merge;
* split;
* other approved structural migrations.

Migration lineage is required conceptually.

Physical migration tables remain subject to detailed Migration DDL design.

## 7.3 Correction vs Migration

A simple business correction or ordinary rename does not automatically constitute a migration.

A structural transformation that changes entity relationships or organizational structure belongs to the Migration capability.

---

# 8. Effective Dating

Effective dating is not a requirement for every table.

Modules shall use temporal validity where their domain requires it.

The project does not require a universal shared temporal table.

Canonical naming conventions for effective dating will be established in the DB Standards document.

Organization's structural history will be addressed as part of the Migration / Structural Change design rather than by prematurely imposing a universal temporal model.

---

# 9. Audit and Accountability

Audit is separate from Change History and Migration.

Audit answers:

> **Who performed the action, when, and what system action occurred?**

Change History answers:

> **What business data changed?**

Migration answers:

> **What structural transformation was performed?**

The existing audit actor convention uses:

```text
created_by_sangha_sevi_pk
updated_by_sangha_sevi_pk
deleted_by_sangha_sevi_pk
```

Exact physical FK creation order is handled during DDL dependency planning.

---

# 10. Master Data Governance

Controlled master/reference values shall have a clear owning module.

The current common master-data architecture uses Foundation-owned master infrastructure where applicable.

Master-data changes shall be subject to:

* appropriate activation/deactivation rules;
* auditability;
* field-level change history where business-significant;
* module-specific authorization where required.

A module shall not create a duplicate master table for a value already governed by an authoritative shared master.

---

# 11. Approval and Workflow Boundary

Approval does not automatically imply a shared approval table.

Where approval/review semantics are domain-specific, the owning module shall retain its own:

* status;
* review;
* approval;
* escalation;
* lifecycle mechanism.

A shared approval table shall be introduced only if a future architectural decision establishes a genuinely common persistent approval model.

---

# 12. Domain Ownership vs Shared Infrastructure

A distinction shall be maintained between:

## Domain-owned data

Examples:

```text
Membership → membership records
Finance → financial transactions
Organization → organization records
Assets & Property → asset/property records
Programme & Events → programme/event records
```

## Shared infrastructure

Examples:

```text
Foundation → document_master
Foundation → field_change_log
Foundation → master-data infrastructure
```

Shared infrastructure is consumed by domain modules but does not absorb their business ownership.

---

# 13. Financial Context vs Financial Ownership

A business module may identify a financial consequence without owning the transaction.

For example:

```text
Assets & Property
    property_pk
    acquisition context
         │
         ▼
Finance
    financial transaction
```

The existence of a financial relationship does not transfer ownership of the business entity to Finance.

Likewise, Finance's ownership of a transaction does not make Finance the owner of the originating business entity.

---

# 14. Future Module Boundary Principle

A future business capability shall become a separate module when it represents a distinct domain with:

* authoritative entities;
* independent business rules;
* lifecycle or governance requirements;
* meaningful cross-module relationships.

A future module shall not be created merely because another module references its data.

The same one-owner-per-table principle applies to future modules.

---

# 15. Current Architectural Decisions

| **Decision** | **Status** |
|---|---|
| One-owner-per-table | FROZEN |
| Finance owns all financial transactions | FROZEN |
| `document_master` owned by Foundation | FROZEN |
| `field_change_log` owned by Foundation | FROZEN |
| Module-owned `_history` + shared field change log | FROZEN |
| Audit / Change History / Effective Dating / Migration separation | FROZEN |
| No universal shared approval table | FROZEN |
| Effective dating is module-specific where required | FROZEN |
| Migration lineage required conceptually | FROZEN |
| Exact Migration physical tables | OPEN — DDL/design phase |
| Exact cross-module FK creation order | OPEN — dependency/DDL phase |
| Correspondence register owned by Administration (CORR-DECISION-003) | FROZEN |
| Correspondence financial traceability via M:N junction (CORR-ARCH-001) | FROZEN |
| Correspondence is a reusable cross-module platform capability (CORR-ARCH-002) | FROZEN |
| Organization short code (3–5 letter, UNIQUE) for Sakha-level identity/correspondence (ORG-PENDING-001) | FROZEN |
| Local Sakha ERP ID conceptual rules + format (MEM-PENDING-001) | FROZEN — physical model ACCEPTED (`membership_sakha_affiliation`) |
| Visitor vs. Approved Darshak threshold (ATT-PENDING-001) | PENDING — DDL phase; Darshak local-number issuance SUPERSEDED |

---

# 16. Correspondence Register

**CORR-DECISION-003 — Administration Correspondence Register**

The NSS ERP shall provide an Administration-owned correspondence register for inward and outward official communications. The capability shall support basic registration, reference numbering, sender/recipient information, subject, date, medium, status/follow-up information, and association with Foundation-owned documents. Domain-specific business requests remain owned by their respective modules. Financial transactions remain exclusively owned by Finance under FIN-ARCH-001. No generic application/workflow engine is introduced by this decision.

## 16.1 Ownership

```text
Administration
└── Correspondence Register
    ├── Inward correspondence
    └── Outward correspondence
```

## 16.2 Ownership Boundaries

| What | Owner |
|------|-------|
| Correspondence register (recording official communications) | Administration |
| Documents/attachments associated with correspondence | Foundation (`document_master`) |
| Membership renewal/transfer requests | Membership |
| Gruhasana renewal | Membership |
| Financial transactions arising from correspondence | Finance |
| Governing-body authority decisions | Governance |
| Property-related matters | Assets & Property |
| Other domain-specific requests | Their owning module |

## 16.3 What This Decision Does Not Introduce

- A generic form/application engine
- A standalone Correspondence & Applications module
- Application workflow tables
- A BPM/workflow automation system
- Domain-specific request tables (these remain with their owning modules)

## 16.4 Physical Design

Physical table design (one table vs. two, column list, reference numbering scheme) shall be established during the Administration Correspondence Register documentation phase.

## 16.5 Source Authority

The original project proposal (2013-14) §1.7 identifies "Correspondence within members & Sakha Sangha & with outside agencies" as an ERP requirement. This decision addresses that requirement through Administration ownership rather than a separate module.

## 16.6 CORR-ARCH-001 — Financial Traceability

Where a correspondence results in, refers to, or requires a financial transaction, the correspondence record shall be capable of referencing the corresponding Finance transaction. This is not limited to payments — any Finance transaction (donation, purchase, tax, refund, salary, bank, adjustment) may have related correspondence. Correspondence shall not create, own, or duplicate financial transaction data. Finance remains the authoritative owner of the financial transaction.

## 16.7 CORR-ARCH-002 — Cross-Module Record Traceability (Reusable Platform Capability)

Correspondence is a reusable cross-module capability. Administration owns the Correspondence Register, but any module may use it to record, associate, and trace official communications related to that module's business records. The consuming module remains the owner of its business process and records. A module may associate its forms, applications, requests, transactions, or other business records with correspondence without transferring ownership of those records to Administration.

---

# 17. Relationship to Module Documentation

This document provides project-wide architectural principles.

Module documents shall remain authoritative for:

* module-specific business rules;
* entity definitions;
* lifecycle rules;
* module-owned tables;
* module-specific constraints;
* domain-specific workflows.

Where a module document conflicts with a frozen project-wide principle, the conflict shall be resolved through an explicit architecture decision rather than silently overriding either document.

---

# 18. Change Control

Changes to the principles in this document shall be made through an explicit architecture decision.

A change affecting:

* table ownership;
* cross-module FK relationships;
* financial transaction ownership;
* common infrastructure ownership;
* migration/history architecture;

shall be reviewed for impact on the ownership matrix, dependency graph, DB Standards, and DDL plan.

---

# 19. Status

**DOCUMENT STATUS:** FROZEN — PROJECT-WIDE ARCHITECTURAL PRINCIPLES

**VERSION:** 1.2.0

**Note:** Physical implementation details remain subject to the DB Standards, final dependency graph, module table designs, and DDL phase.

---

# 20. Pending Design Notes — DDL Phase

The following design decisions are confirmed directionally but require
physical schema resolution during the DDL phase. They do not change
module ownership or introduce new dependencies.

## 20.1 Organization Short Code (ORG-PENDING-001) — FROZEN

**Affects:** Organization, Membership, Administration (Correspondence)

**Status:** FROZEN

Every organization (primarily Sakhas) shall have a short alphabetic
code derived from its name:

```text
Column:   organization_short_code
Type:     VARCHAR(5), UNIQUE, NOT NULL
Default:  3 letters; 4 or 5 letters only when shorter code collides
Examples: ESS (Ekamra Sangha), KEN (Kendra)
```

This code is reused as:

1. Prefix in `local_sakha_number` (member identity within Sakha)
2. Prefix in correspondence reference (`ESS/OUT/2027-28/001`)

The existing `organization_id` format (`SKH00000001`, `ANC00000001`) remains
unchanged — it is the system-generated permanent business identifier.
`organization_short_code` is a separate human-assigned attribute.

**Dependency:** CORR-EXT-001 is now unblocked.

## 20.2 Local Sakha ERP ID — Conceptual Rules and Format (MEM-PENDING-001)

**Affects:** Membership, Organization

**Status:** Conceptual identity rules and ID format FROZEN;
physical model ACCEPTED (`membership_sakha_affiliation`).

### Format — FROZEN

```text
<3–5 character Organization/Sakha Short Code><8-digit sequence>
Examples: ESS00000123, PURI00000001, BBSR00000042
```

`ESS00000123` is a canonical example, not a restriction to three-character
codes. The short code length varies by organization (see ORG-PENDING-001).

The short code is the `organization_short_code` defined in
ORG-PENDING-001. The 8-digit zero-padded sequence is Sakha-assigned
and increments per Sakha independently.

### Conceptual Identity Rules — FROZEN

1. Every Sangha Sevi has one permanent, NSS-wide **Sangha Sevi ID**
   (e.g. `SS00000001`).
2. A person has **one active Local Sakha ERP ID** associated with their
   current recognized/base Sakha membership.
3. Existing Sakha register numbers should be **carried forward into the
   ERP Local Sakha ID wherever they can be reliably mapped** (e.g. old
   Sakha number `123` → `ESS00000123`), avoiding unnecessary
   renumbering.
4. Existing Sakha numbers remain available as historical migration
   references (legacy numbers are never discarded).
5. "Darshak" is an operational term that can apply to two distinct
   categories:
   - **New Probationary Member** (operationally called "Darshak") — a
     person entering NSS membership who does not already hold a
     Parichaya Patra from another Sangha. This person **receives a new
     Local Sakha ERP ID** from the Sakha where membership is being
     established.
   - **Approved Darshak** (existing member of another Sangha) — a
     person who already holds a recognized Parichaya Patra/membership
     at a different Sakha. This person **does not receive a second
     Local Sakha ERP ID**; they continue to be identified by the Local
     Sakha ERP ID of their base/recognized Sakha. The attendance
     record's organizational context identifies the receiving Sakha.

   ```text
                        DARSHAK
                           │
                ┌──────────┴──────────┐
                │                     │
         Probationary Member    Existing Member
         (new NSS member)       (other Sangha)
                │                     │
         NEW local ERP ID       EXISTING base ID
                │                     │
         CTC00000124            ESS00000123
   ```

6. When Parichaya Patra/membership is formally transferred:
   - the previous Local Sakha ERP ID becomes **ARCHIVED**;
   - archived IDs are **never reassigned to another person**;
   - if the same person returns to the same Sakha, their archived ID
     may be **REACTIVATED**;
   - the receiving Sakha issues the next number in its own sequence;
   - the Sangha Sevi ID remains unchanged.
7. Legacy → ERP number mapping must preserve historical traceability.

### Superseded

The following earlier proposals are explicitly **SUPERSEDED** by the
rules above:

- "A member may hold multiple ACTIVE local numbers simultaneously
  (home Sakha + approved Darshak Sakha(s))." — replaced by the
  one-active-Local-Sakha-ERP-ID rule (rule 2).
- "Approved Darshak → local Sakha number issued by visited Sakha." —
  replaced by rule 5 (existing-member Approved Darshak uses base-Sakha
  ID; new Probationary Member receives an ID from the enrolling Sakha).
- "Darshak gets no local ID" (overly broad) — replaced by the
  two-category distinction in rule 5.

### Identity Relationship

```text
Sangha Sevi ID (permanent, NSS-wide)
      │
      │ 1
      ▼
Current recognized/base Sakha (organization_pk)
      │
      ▼
One Active Local Sakha ERP ID
      │
      ├── Regular attendance at base Sakha
      │
      ├── Darshak attendance at another Sakha
      │       (existing member — same Local ERP ID, different
      │        attendance context)
      │
      └── Probationary Member at enrolling Sakha
              (new member — receives Local ERP ID from this Sakha)
```

On transfer:

```text
Old Local Sakha ERP ID → ARCHIVED (never reused)
New Sakha sequence     → New Local Sakha ERP ID
Sangha Sevi ID         → UNCHANGED
```

### Lifecycle

```text
Member joins Sakha A     → ESS00000123 (ACTIVE)
Darshak at Sakha B       → ESS00000123 (still ACTIVE at base Sakha A)
Transfer to Sakha B      → ESS00000123 (ARCHIVED), CTC00000042 (ACTIVE)
Returns to Sakha A       → CTC00000042 (ARCHIVED), ESS00000123 (REACTIVATED)
```

Archived IDs are never reassigned to another person. If the same
Sangha Sevi returns to the same Sakha, their previous Local Sakha ERP
ID may be reactivated. The Sakha's sequence continues independently
for genuinely new members.

### Issuance Rules

| Scenario | Local ERP ID issued? |
|----------|:---:|
| Home Sakha member (new or returning) | Yes |
| Probationary Member / operational Darshak (new to NSS, no Parichaya Patra elsewhere) | Yes — from enrolling Sakha |
| Approved Darshak (existing member of another Sangha, with approval) | No — uses base-Sakha ID |
| Visitor (≤4 consecutive Sundays, no approval) | No |

### Key Properties

- Assigned by the Sakha (not centrally)
- Not a global identifier — scope is the issuing Sakha
- Linked to `sangha_sevi_id` (which is permanent and global)
- One active Local Sakha ERP ID per person at any time
- Parichaya Patra remains at home Sakha for Approved Darshak scenario
- Probationary Member (operational Darshak) receives ID from enrolling
  Sakha — this is their base Sakha, not a "visited" Sakha

### DDL-Phase Resolution — ACCEPTED Physical Model

Membership owns the authoritative history of a person's recognized
Sakha affiliations. `membership_transfer_history` records transfer
events but does not serve as the complete effective-dated affiliation
history. The accepted physical separation is:

```text
Membership
│
├── Permanent identity
│     └── sangha_sevi (sangha_sevi_id, organization_pk)
│
├── Sakha affiliation history       ← ACCEPTED physical table
│     ├── Sakha (organization_pk)
│     ├── effective period (effective_from / effective_to)
│     ├── affiliation status (ACTIVE / ARCHIVED / REACTIVATED)
│     ├── Local Sakha ERP ID
│     ├── legacy Sakha number (inline, migration)
│     └── source event (ENROLLMENT / TRANSFER / REACTIVATION)
│
└── Transfer history
      └── transfer event / approval workflow details (unchanged)
```

**Accepted table:** `membership_sakha_affiliation`

```text
membership_sakha_affiliation_pk     UUID PK
sangha_sevi_pk                      FK → sangha_sevi
organization_pk                     FK → organization (the Sakha)
local_sakha_erp_id                  VARCHAR NOT NULL
effective_from                      DATE NOT NULL
effective_to                        DATE NULL (NULL = current)
affiliation_status                  VARCHAR NOT NULL
                                      (ACTIVE / ARCHIVED / REACTIVATED)
source_event_type                   VARCHAR NOT NULL
                                      (ENROLLMENT / TRANSFER / REACTIVATION)
source_event_pk                     UUID NULL
legacy_sakha_number                 VARCHAR NULL (migration only)
created_at / created_by / updated_at / updated_by
```

**Constraints:**
- One ACTIVE/REACTIVATED affiliation per `sangha_sevi_pk` at any time
  (partial unique index: `UNIQUE(sangha_sevi_pk) WHERE effective_to IS NULL`)
- Local Sakha ERP ID unique within its Sakha scope:
  `UNIQUE(organization_pk, local_sakha_erp_id)`
- CHECK: `(effective_to IS NULL AND affiliation_status IN ('ACTIVE','REACTIVATED'))
  OR (effective_to IS NOT NULL AND affiliation_status = 'ARCHIVED')`

**Reactivation mechanics:** On return to a previously held Sakha, a
**new affiliation period row** is created with the same
`local_sakha_erp_id`, `affiliation_status = 'REACTIVATED'`, and
`source_event_type = 'REACTIVATION'`. The prior ARCHIVED row is **not
reopened** — this preserves clean historical periods for audit:

```text
2019 ─────── 2023    Ekamra   ESS00000123   ARCHIVED
2023 ─────── 2026    Cuttack  CTC00000042   ARCHIVED
2026 ─────── →       Ekamra   ESS00000123   REACTIVATED
```

**Decisions recorded:**

| Component | Decision |
|---|---|
| `sangha_sevi` | No `local_sakha_erp_id` — the local ID belongs to the affiliation period |
| `membership_sakha_affiliation` | ACCEPTED as physical table |
| `membership_transfer_history` | RETAINED unchanged — transfer-event record |
| Legacy mapping | Inline `legacy_sakha_number` on affiliation row; separate mapping table PENDING if multi-source evidence emerges |
| Sevak `sevak_sakha_association` | DEFERRED — Membership affiliation is the candidate authoritative source; Sevak consumption model resolved at Sevak DDL phase |

**Cross-module note:** The Sevak module's `sevak_sakha_association`
already maintains effective-dated Sakha history with the same
conceptual shape. Whether that table references `membership_sakha_affiliation`
directly, maintains a derived copy, or retains its existing
independent structure is a downstream design decision — not frozen
here.

**Dependency:** Requires ORG-PENDING-001 (organization_short_code) — FROZEN.

## 20.3 Visitor vs. Approved Darshak Threshold (ATT-PENDING-001)

**Affects:** Attendance, Membership

**Classification:** ERP operational refinement — not source-derived.
The existing DARSHAK_BUSINESS_RULE.md uses "Darshak" as the umbrella
term. Introducing "Visitor" and "Approved Darshak" as sub-categories
is a project design decision, not a Bye-Law distinction.

### Visitor (no approval)

```text
- Existing member attending another Sakha for ≤4 consecutive Sundays
- No local Sakha number issued by the receiving Sakha
- Attendance recorded against sangha_sevi_id
- Portal displays as "Visitor" in that Sakha
- The person's existing base-Sakha Local ERP ID is unaffected
```

Note: the Visitor threshold is an **attendance rule** governing
cross-Sakha casual attendance. It is separate from Local Sakha ERP ID
issuance (governed by MEM-PENDING-001). A Probationary Member at their
own enrolling Sakha is not a "Visitor" — they are at their base Sakha
and receive a Local Sakha ERP ID per MEM-PENDING-001 rule 5.

### Approved Darshak (with approval)

```text
- Approval required from visited Sakha
- Existing member of another Sangha (holds Parichaya Patra elsewhere)
- No local Sakha number issued by receiving Sakha
  (SUPERSEDED — see MEM-PENDING-001 rule 5)
- Darshak uses base-Sakha Local ERP ID for identification
- Attendance recorded with receiving Sakha as organizational context
- Parichaya Patra stays at home Sakha
```

**Important distinction (MEM-PENDING-001 rule 5):** "Darshak" is an
operational term that applies to both new Probationary Members and
existing members of another Sangha. Only the **existing-member**
Approved Darshak retains their base-Sakha ID here. A new Probationary
Member (operationally also called "Darshak") **does** receive a Local
Sakha ERP ID from the Sakha where membership is being established —
that Sakha is their base Sakha.

### Threshold Rule

After 4 consecutive Sunday attendances at another Sakha without
approval, the system shall enforce either:

- Cessation of visitor attendance at that Sakha, OR
- Initiation of Darshak approval workflow

### Implementation Constraints

- The "4 consecutive" threshold is a business rule. The exact
  enforcement mechanism (system-blocked vs. notification-driven) is a
  DDL/application-phase decision.
- The threshold is **derivable** from existing attendance records
  (`sangha_sevi_pk` + `attendance_sakha_pk` + consecutive puja dates).
  No dedicated counter column should be added to the attendance schema
  unless DDL analysis proves derivation is insufficient.
- DARSHAK_BUSINESS_RULE.md will need updating to distinguish Visitor
  vs. Approved Darshak — but that update belongs to the DDL phase,
  not this document.

---

# 21. Pending Design Notes — Status

| ID | Title | Modules Affected | Blocking? |
|----|-------|-----------------|:---------:|
| ORG-PENDING-001 | Organization Short Code | Org, Mem, Admin | FROZEN — CORR-EXT-001 unblocked |
| MEM-PENDING-001 | Local Sakha ERP ID — Conceptual Rules + Format | Mem, Org | Rules + format FROZEN; physical model ACCEPTED — `membership_sakha_affiliation` table |
| ATT-PENDING-001 | Visitor vs. Approved Darshak Threshold | Att, Mem | No (Attendance DDL can proceed without); Darshak local-number issuance SUPERSEDED by MEM-PENDING-001 |
