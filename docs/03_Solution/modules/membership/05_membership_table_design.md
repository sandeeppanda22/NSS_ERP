# NSS ERP — Membership Table Design

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Membership Table Design |
| Document ID | SOL-MEM-005 |
| Domain | Membership |
| Repository Path | docs/03_Solution/modules/membership/05_membership_table_design.md |
| Version | 1.0.0 |
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

# 28. Final Membership Table Set

The current logical Membership table set is:

```text
sangha_sevi

membership_status_history

membership_renewal_request

membership_renewal_history

membership_transfer_history

membership_journey_event

probationary_member_review

anumati_patra

anumati_patra_history

parichaya_patra

parichaya_patra_history
```

This table set reflects the Membership architecture developed during the NSS V2 database discussions, including the later addition of probationary_member_review and the first-class identity-document entities.

---

# End of Document
