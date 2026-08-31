# NSS ERP — Membership Table Design

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Membership Table Design |
| Document ID | SOL-MEM-005 |
| Domain | Membership |
| Repository Path | docs/03_Solution/modules/membership/05_membership_table_design.md |
| Version | 1.1.0 |
| Status | Draft |
| Authority | NSS ERP Membership Module |
| Parent Document | 01_membership_module_overview.md |
| Related Documents | 02_membership_erd.md, 03_membership_lifecycle.md, 04_membership_business_rules.md |
| Effective Date | TBD |

---

# 1. Purpose

This document defines the logical PostgreSQL table design for the NSS ERP Membership Module.

It translates the Membership ERD and approved business rules into database-oriented structures.

The final SQL implementation shall follow the project-wide database standards.

---

# 2. Database Standards

Membership tables shall follow:

```text
UUID internal primary keys

Human-readable business IDs

Master-data driven values

Foreign keys reference internal primary keys

Auditability

Soft-delete principles

History preservation
```

---

# 3. Membership Core Tables

The Membership domain includes the following principal tables:

```text
sangha_sevi

membership_status_history

membership_renewal_request

membership_renewal_history

membership_transfer_history

membership_sakha_affiliation

membership_journey_event

probationary_member_review

parichaya_patra

parichaya_patra_history

anumati_patra

anumati_patra_history
```

---

# 4. sangha_sevi

## Purpose

Stores the core Membership identity.

## Columns

```text
sangha_sevi_pk
sangha_sevi_id
person_pk
membership_type_pk
membership_status_pk
organization_pk
joining_date
renewal_due_date
remarks
created_at
created_by_sangha_sevi_pk
updated_at
updated_by_sangha_sevi_pk
deleted_at
deleted_by_sangha_sevi_pk
is_active
```

## Key Rules

```text
sangha_sevi_pk
    PRIMARY KEY

sangha_sevi_id
    UNIQUE NOT NULL

person_pk
    UNIQUE NOT NULL
```

The unique Person relationship implements:

```text
One Person
    |
One Membership
```

### Local Sakha ERP ID — Not on This Table (MEM-PENDING-001)

The `sangha_sevi` table does not carry a `local_sakha_erp_id`
column. The Local Sakha ERP ID belongs to the **affiliation period**,
not the permanent identity record. It resides on the accepted
`membership_sakha_affiliation` table (see §27.1).

Format (FROZEN in CROSS_MODULE_PRINCIPLES.md §20.2):

```text
Format:  <3–5 character Organization/Sakha Short Code><8-digit sequence>
Example: EKM00000123
```

---

# 5. Sangha Sevi ID

The business identifier:

```text
sangha_sevi_id
```

shall be:

```text
Globally Unique
Permanent
Never Reused
Never Changed
System Generated
```

Example:

```text
SS00000001
SS00000002
SS00000003
```

### Sangha Sevi ID vs. Local Sakha ERP ID (MEM-PENDING-001 annotation)

These are distinct identity tiers:

```text
Sangha Sevi ID  — permanent, NSS-wide, never changes, never reused
Local Sakha ERP ID — Sakha-scoped, one active per member, may be
                     archived on transfer and reactivated on return
```

The Sangha Sevi ID is the primary business key on this table.
The Local Sakha ERP ID resides on `membership_sakha_affiliation` (§27.1).

---

# 6. membership_status_history

## Purpose

Stores historical Membership status changes.

## Columns

```text
membership_status_history_pk
sangha_sevi_pk
membership_status_pk
effective_from
effective_to
reason
remarks
created_at
created_by_sangha_sevi_pk
```

## Principle

Current status may be available through the Membership record.

Historical status shall be maintained here.

---

# 7. membership_renewal_request

## Purpose

Stores renewal requests before final approval.

## Columns

```text
membership_renewal_request_pk
sangha_sevi_pk
requested_date
requested_by_sangha_sevi_pk
status
reviewed_by_sangha_sevi_pk
reviewed_date
remarks
created_at
updated_at
```

---

# 8. membership_renewal_history

## Purpose

Stores approved Membership renewal history.

## Columns

```text
membership_renewal_history_pk
sangha_sevi_pk
renewal_date
valid_from
valid_to
approved_by_sangha_sevi_pk
remarks
created_at
```

## Principle

Every completed renewal remains permanently traceable.

---

# 9. membership_transfer_history

## Purpose

Stores historical Membership transfers between organizational units.

## Columns

```text
membership_transfer_history_pk
sangha_sevi_pk
old_organization_pk
new_organization_pk
transfer_type
transfer_reason
requested_date
approved_date
effective_date
old_local_sakha_number
new_local_sakha_number
approved_by_sangha_sevi_pk
remarks
created_at
```

## Rules

```text
Sangha Sevi ID does not change.

Transfer history is never deleted.

Old organizational association remains traceable.

New organizational association becomes effective according to the approved transfer workflow.
```

### Transfer and Local Sakha ERP ID (MEM-PENDING-001 annotation)

The `old_local_sakha_number` and `new_local_sakha_number` columns on
this table serve as **historical transition snapshots** — recording
what the member's Local Sakha ERP ID was before and after each
transfer. They are not the authoritative current-ID source.

Key rules from MEM-PENDING-001:

* On transfer: old Local Sakha ERP ID is archived (never reassigned
  to another person). New Sakha issues the next number in sequence.
* On return to the same Sakha: the same person's previously archived
  ID may be reactivated (not a new issuance).
* An existing-member Approved Darshak attending another Sakha does not
  trigger a transfer and does not receive a second Local Sakha ERP ID.
* A new Probationary Member (operationally also called "Darshak")
  **does** receive a Local Sakha ERP ID from the enrolling Sakha —
  that Sakha is their base Sakha (see MEM-PENDING-001 rule 5).

This table remains the transfer-event record. The authoritative
current Local Sakha ERP ID resides on the accepted
`membership_sakha_affiliation` table (see §27.1).

---

# 10. membership_journey_event

## Purpose

Provides a chronological history of important Membership lifecycle events.

## Columns

```text
membership_journey_event_pk
sangha_sevi_pk
event_type
event_date
event_reference
remarks
created_at
created_by_sangha_sevi_pk
```

## Example Events

```text
MEMBERSHIP_CREATED

PROBATIONARY_STARTED

TRAINING_STARTED

PROBATIONARY_REVIEW

REGULAR_ENROLMENT

ASSOCIATE_ENROLMENT

RENEWAL

TRANSFER

STATUS_CHANGE
```

The final event catalogue shall be controlled through project master data.

---

# 11. probationary_member_review

## Purpose

Stores the historical review of Probationary Membership progression.

## Columns

```text
probationary_member_review_pk
sangha_sevi_pk
review_date
reviewed_by_sangha_sevi_pk
review_type
outcome
training_completed
sakha_recommendation
remarks
created_at
updated_at
```

## Principle

The review record preserves progression history.

It does not replace the Membership record.

---

# 12. anumati_patra

## Purpose

Stores the Membership-level Anumati Patra record.

## Columns

```text
anumati_patra_pk
sangha_sevi_pk
document_number
issue_date
valid_from
valid_to
status
document_reference
remarks
created_at
updated_at
```

---

# 13. anumati_patra_history

## Purpose

Stores historical changes to Anumati Patra records.

## Columns

```text
anumati_patra_history_pk
anumati_patra_pk
change_type
change_date
previous_status
new_status
document_reference
remarks
created_at
```

---

# 14. parichaya_patra

## Purpose

Stores the Parichaya Patra record associated with applicable Membership.

## Columns

```text
parichaya_patra_pk
sangha_sevi_pk
document_number
issue_date
valid_from
valid_to
status
document_reference
remarks
created_at
updated_at
```

---

# 15. parichaya_patra_history

## Purpose

Stores historical Parichaya Patra changes.

## Columns

```text
parichaya_patra_history_pk
parichaya_patra_pk
change_type
change_date
previous_status
new_status
document_reference
remarks
created_at
```

---

# 16. Membership Type Master

Membership Type shall be master-data driven.

Official values:

```text
PROBATIONARY
REGULAR
ASSOCIATE
```

The ERP shall not store:

```text
DARSHAK
FULL_MEMBER
```

as official Membership Type values.

---

# 17. Membership Status Master

Membership Status shall be maintained separately from Membership Type.

The Membership Overview identifies examples including:

```text
ACTIVE
RENEWAL_PENDING
EXPIRED
SUSPENDED
ON_HOLD
DISCIPLINARY_REVIEW
TRANSFERRED
DECEASED
```

The final master-data implementation shall control permitted values and lifecycle transitions.

---

# 18. Organization Foreign Key

The current Membership organizational association shall reference:

```text
organization.organization_pk
```

Historical transfers shall be stored in:

```text
membership_transfer_history
```

---

# 19. Person Foreign Key

The Membership record shall reference:

```text
person.person_pk
```

The relationship is:

```text
person
   1
   |
   |
   0..1
   v
sangha_sevi
```

The database shall enforce the one-Membership-per-Person rule.

---

# 20. Foreign Key Naming

Foreign keys shall reference the internal primary key.

Correct:

```text
person_pk
organization_pk
membership_type_pk
membership_status_pk
```

Not:

```text
person_id
organization_id
membership_type_id
```

when those fields are intended to be foreign keys.

---

# 21. Primary Key Standard

Every Membership transactional table shall use a UUID internal primary key.

Examples:

```text
sangha_sevi_pk
membership_status_history_pk
membership_transfer_history_pk
membership_renewal_request_pk
membership_renewal_history_pk
membership_journey_event_pk
```

---

# 22. Audit Standard

Transactional Membership tables shall preserve audit information where applicable:

```text
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk
```

and:

```text
is_active
```

where the table lifecycle requires it.

---

# 23. Soft Delete

Physical deletion of Membership history is prohibited.

Historical records shall remain available.

Where an entity becomes inactive, the system shall use controlled lifecycle/status mechanisms rather than deleting historical information.

---

# 24. Historical Integrity

The following shall never be destroyed:

```text
Membership identity

Status history

Renewal history

Transfer history

Journey events

Probationary reviews

Identity-document history
```

---

# 25. Membership Table Relationship Summary

```text
PERSON
   |
   +-- SANGHA_SEVI
          |
          +-- MEMBERSHIP_STATUS_HISTORY
          |
          +-- MEMBERSHIP_RENEWAL_REQUEST
          |
          +-- MEMBERSHIP_RENEWAL_HISTORY
          |
          +-- MEMBERSHIP_TRANSFER_HISTORY
          |
          +-- MEMBERSHIP_SAKHA_AFFILIATION
          |         +-- Local Sakha ERP ID (per period)
          |         +-- Affiliation status / effective dates
          |
          +-- MEMBERSHIP_JOURNEY_EVENT
          |
          +-- PROBATIONARY_MEMBER_REVIEW
          |
          +-- ANUMATI_PATRA
          |      +-- ANUMATI_PATRA_HISTORY
          |
          +-- PARICHAYA_PATRA
                 +-- PARICHAYA_PATRA_HISTORY
```

---

# 26. Attendance Boundary

Attendance tables do not belong to the Membership core schema.

Attendance is maintained by the Attendance Module.

Membership provides the Membership identity used by Attendance.

Relationship:

```text
Membership
    |
Attendance
    |
Attendance Review
```

Attendance Review may influence Membership workflows, but Attendance does not directly overwrite Membership history.

---

# 27. Governance Boundary

Membership eligibility does not itself create governance positions.

Governance assignments shall be maintained by the Governance Module.

Relationship:

```text
Membership
    |
Eligibility
    |
Governance Workflow
    |
Position Assignment
```

---

# 27.1 membership_sakha_affiliation — ACCEPTED Physical Model (MEM-PENDING-001)

## Purpose

Stores authoritative effective-dated Sakha affiliations, including the
Local Sakha ERP ID for each period. Accepted as the physical model per
CROSS_MODULE_PRINCIPLES.md §20.2 (2026-08-31).

## Columns

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
created_at
created_by_sangha_sevi_pk
updated_at
updated_by_sangha_sevi_pk
```

## Key Rules

```text
membership_sakha_affiliation_pk
    PRIMARY KEY

sangha_sevi_pk
    FK → sangha_sevi NOT NULL

organization_pk
    FK → organization NOT NULL

local_sakha_erp_id
    NOT NULL
    UNIQUE(organization_pk, local_sakha_erp_id)
```

## Constraints

One active affiliation per person at any time:

```text
UNIQUE(sangha_sevi_pk) WHERE effective_to IS NULL
```

Status/effective_to consistency:

```text
CHECK (
    (effective_to IS NULL AND affiliation_status IN ('ACTIVE', 'REACTIVATED'))
    OR
    (effective_to IS NOT NULL AND affiliation_status = 'ARCHIVED')
)
```

## Lifecycle Behavior

**Enrollment:** New row with `source_event_type = 'ENROLLMENT'`,
`effective_to = NULL`, `affiliation_status = 'ACTIVE'`.

**Transfer out:** Close current row (`effective_to = transfer_date`,
`affiliation_status = 'ARCHIVED'`). New row at new Sakha with
`source_event_type = 'TRANSFER'`.

**Reactivation (return to same Sakha):** A **new affiliation period
row** is created with the same `local_sakha_erp_id`,
`affiliation_status = 'REACTIVATED'`, `source_event_type = 'REACTIVATION'`.
The prior ARCHIVED row is **not reopened**.

```text
2019 ─────── 2023    Ekamra   EKM00000123   ARCHIVED
2023 ─────── 2026    Cuttack  CTC00000042   ARCHIVED
2026 ─────── →       Ekamra   EKM00000123   REACTIVATED
```

**Probationary Member (operational Darshak):** Same as enrollment —
receives a row at the enrolling Sakha with a new Local Sakha ERP ID.

**Existing-member Approved Darshak:** No row at the receiving Sakha.
Uses their existing ACTIVE row at their base Sakha.

## Legacy Number

`legacy_sakha_number` stores the original Sakha register number before
ERP migration. Only populated on the initial/migrated affiliation
record. A separate migration mapping table remains PENDING if
multi-source evidence emerges.

## Cross-Module Note

The Sevak module's `sevak_sakha_association` maintains effective-dated
Sakha history with the same conceptual shape. Whether that table
references `membership_sakha_affiliation` directly, maintains a
derived copy, or retains its existing independent structure is a
downstream design decision deferred to the Sevak DDL phase.

---

# 28. Final Membership Table Set

The current logical Membership table set is:

```text
sangha_sevi

membership_status_history

membership_renewal_request

membership_renewal_history

membership_transfer_history

membership_sakha_affiliation

membership_journey_event

probationary_member_review

anumati_patra

anumati_patra_history

parichaya_patra

parichaya_patra_history
```

This table set reflects the Membership architecture developed during
the NSS V2 database discussions, including the later addition of
probationary_member_review, the first-class identity-document entities,
and `membership_sakha_affiliation` (accepted 2026-08-31 per
MEM-PENDING-001 — see §27.1).

---
