# NSS ERP — Kishor Puja Table Design

**Document ID:** SOL-KISH-005  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kishor Puja  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical table design for the Kishor Puja module.

It translates the approved:

- Kishor Module Overview
- Kishor ERD
- Kishor Lifecycle
- Kishor Business Rules

into a structured relational table design.

This document does not generate SQL.

---

# 2. Design Principles

The Kishor table design follows the NSS ERP principles:

```text
Person ≠ Member

Kishor ≠ NSS Member

KH ID ≠ Sangha Sevi ID

Registration ≠ Attendance

History Never Deleted

Common Foundation First

Master Data Driven

Common Modules Own Their Domains
```

---

# 3. Kishor Domain Tables

The Kishor domain consists of four primary tables:

```text
kishor_participant

kishor_event

kishor_event_registration

kishor_membership_transition
```

This matches the frozen Kishor architecture.

---

# 4. Common Tables Used

Kishor integrates with existing common tables, including:

```text
person

family_group

family_relationship

organization

sangha_sevi

membership

attendance

audit
```

Kishor shall not duplicate these common domains.

---

# 5. Table Ownership

| Table                           | Owner                          | Purpose                     |
| ------------------------------- | ------------------------------ | --------------------------- |
| `kishor_participant`           | Kishor                        | Permanent KH identity       |
| `kishor_event`                 | Kishor/Event                  | Annual Kishor Puja         |
| `kishor_event_registration`    | Kishor                        | Event-specific registration |
| `kishor_membership_transition` | Kishor/Membership integration | KH → SS transition          |

---

# 6. `kishor_participant`

## Purpose

Stores the permanent identity of a Kishor participant.

One Person may have one Kishor identity.

The identity remains valid across multiple Kishor Puja years.

---

# 7. `kishor_participant` — Columns

| Column                    | Logical Type     | Required | Key    | Description                               |
| ------------------------- | ---------------- | -------: | ------ | ----------------------------------------- |
| `kishor_participant_pk`  | BIGINT           |      Yes | PK     | Internal primary key                      |
| `kishor_id`              | VARCHAR          |      Yes | UNIQUE | Permanent participant-facing KH ID        |
| `person_pk`               | BIGINT           |      Yes | FK     | Reference to `person`                     |
| `sakha_organization_pk`   | BIGINT           |      Yes | FK     | Participant's operational Sakha           |
| `guardian_sangha_sevi_pk` | BIGINT           |      Yes | FK     | Current assigned NSS Guardian             |
| `assigned_by_sakha_pk`    | BIGINT           |      Yes | FK     | Sakha responsible for Guardian assignment |
| `guardian_assigned_date`  | DATE             |      Yes | —      | Effective Guardian assignment date        |
| `registration_date`       | DATE             |      Yes | —      | Initial Kishor registration date         |
| `status`                  | Master/Data Type |      Yes | FK     | Participant status                        |
| `remarks`                 | TEXT             |       No | —      | Administrative remarks                    |
| `created_at`              | TIMESTAMP        |      Yes | —      | Creation timestamp                        |
| `created_by`              | BIGINT           |      Yes | FK     | Creating user                             |
| `updated_at`              | TIMESTAMP        |      Yes | —      | Last update timestamp                     |
| `updated_by`              | BIGINT           |      Yes | FK     | Updating user                             |

The Guardian-related fields are based on the frozen v2.1 Guardian Model. The Guardian reference is to `sangha_sevi`, not merely `person`.

---

# 8. `kishor_participant_pk`

Internal database primary key.

Characteristics:

```text
Unique
System Generated
Immutable
Never Reused
```

This is not the public KH ID.

---

# 9. `kishor_id`

Permanent participant-facing identifier.

Example:

```text
KH000001
KH000002
KH000123
```

Rules:

```text
Unique
Permanent
Immutable
Never Reused
```

The same KH ID is retained across years.

---

# 10. `person_pk`

Foreign key to the common Person table.

Relationship:

```text
person
   ↓
kishor_participant
```

The Kishor module does not duplicate Person information.

---

# 11. `sakha_organization_pk`

References the participant's operational Sakha.

Purpose:

* Sakha ownership
* Sakha reporting
* Sakha visibility
* Guardian assignment context

The Organization module remains authoritative for the Sakha.

---

# 12. `guardian_sangha_sevi_pk`

References the assigned NSS Guardian.

The reference shall be:

```text
kishor_participant.guardian_sangha_sevi_pk
        ↓
sangha_sevi
```

It shall not use a generic `guardian_person_pk` as the authoritative Guardian relationship.

This reflects the frozen v2.1 Guardian Model.

---

# 13. `assigned_by_sakha_pk`

References the Sakha responsible for assigning the Guardian.

This preserves assignment authority.

---

# 14. `guardian_assigned_date`

Records the effective date of the current Guardian assignment.

Guardian history shall be preserved through the project's history/audit mechanisms.

---

# 15. `registration_date`

Records the date on which the participant first entered the Kishor system.

This is distinct from individual annual event registrations.

---

# 16. `status`

Represents the current Kishor participant status.

The final allowable values shall come from the approved master-data/business-rule definitions.

This field shall not be confused with:

```text
Registration Status
Participation Status
Attendance Status
Membership Status
```

---

# 17. `remarks`

Optional administrative notes.

Remarks shall not be used to store structured business data that belongs in dedicated columns or related tables.

---

# 18. Audit Columns

All Kishor domain tables shall follow the common project audit standard.

At minimum:

```text
created_at
created_by
updated_at
updated_by
```

---

# 19. `kishor_event`

## Purpose

Represents an annual Kishor Puja event.

Examples:

```text
Kishor Puja 2026
Kishor Puja 2027
Kishor Puja 2028
```

---

# 20. `kishor_event` — Columns

| Column                 | Logical Type     | Required | Key | Description            |
| ---------------------- | ---------------- | -------: | --- | ---------------------- |
| `kishor_event_pk`     | BIGINT           |      Yes | PK  | Event primary key      |
| `event_name`           | VARCHAR          |      Yes | —   | Event name             |
| `financial_year`       | VARCHAR/SMALLINT |      Yes | —   | Applicable year        |
| `event_date`           | DATE             |      Yes | —   | Event date             |
| `host_organization_pk` | BIGINT           |      Yes | FK  | Host organization      |
| `location_pk`          | BIGINT           |       No | FK  | Event location         |
| `status`               | Master/Data Type |      Yes | FK  | Event status           |
| `description`          | TEXT             |       No | —   | Event description      |
| `remarks`              | TEXT             |       No | —   | Administrative remarks |
| `created_at`           | TIMESTAMP        |      Yes | —   | Creation timestamp     |
| `created_by`           | BIGINT           |      Yes | FK  | Creating user          |
| `updated_at`           | TIMESTAMP        |      Yes | —   | Last update timestamp  |
| `updated_by`           | BIGINT           |      Yes | FK  | Updating user          |

The earlier frozen source identifies the event around `kishor_event_pk`, `event_name`, `financial_year`, `event_date`, and `host_organization_pk`.

---

# 21. `kishor_event_pk`

Internal primary key for the Kishor event.

It uniquely identifies one annual Kishor Puja occurrence.

---

# 22. `event_name`

Human-readable event name.

Examples:

```text
Kishor Puja 2026
Kishor Puja 2027
```

---

# 23. `financial_year`

Identifies the applicable year.

This supports:

* Annual reporting
* Historical participation
* Year-wise dashboards
* Event search

---

# 24. `event_date`

Scheduled date of the Kishor Puja.

---

# 25. `host_organization_pk`

References the common Organization module.

The host organization is not necessarily the same as every participant's Sakha.

---

# 26. `location_pk`

Where applicable, references the common Location framework.

Kishor shall not create a duplicate location master.

---

# 27. `status`

Represents the lifecycle state of the event.

The exact status master shall follow the common Event framework.

Potential examples may include:

```text
DRAFT
PUBLISHED
COMPLETED
CANCELLED
```

These examples are illustrative unless separately frozen by the common Event framework.

---

# 28. `description`

Optional event description.

---

# 29. `remarks`

Optional administrative notes.

---

# 30. `kishor_event_registration`

## Purpose

Represents registration of one Kishor participant for one Kishor event.

Relationship:

```text
kishor_participant
        ↓
kishor_event_registration
        ↑
kishor_event
```

---

# 31. `kishor_event_registration` — Columns

| Column                          | Logical Type     | Required | Key | Description                         |
| ------------------------------- | ---------------- | -------: | --- | ----------------------------------- |
| `kishor_event_registration_pk` | BIGINT           |      Yes | PK  | Registration primary key            |
| `kishor_participant_pk`        | BIGINT           |      Yes | FK  | Kishor participant                 |
| `kishor_event_pk`              | BIGINT           |      Yes | FK  | Kishor event                       |
| `registration_date`             | DATE             |      Yes | —   | Registration date                   |
| `registration_status`           | Master/Data Type |      Yes | FK  | Registration state                  |
| `sakha_organization_pk`         | BIGINT           |      Yes | FK  | Sakha associated with registration  |
| `guardian_sangha_sevi_pk`       | BIGINT           |       No | FK  | Guardian applicable to registration |
| `participation_status`          | Master/Data Type |       No | FK  | Event participation state           |
| `remarks`                       | TEXT             |       No | —   | Administrative remarks              |
| `created_at`                    | TIMESTAMP        |      Yes | —   | Creation timestamp                  |
| `created_by`                    | BIGINT           |      Yes | FK  | Creating user                       |
| `updated_at`                    | TIMESTAMP        |      Yes | —   | Last update timestamp               |
| `updated_by`                    | BIGINT           |      Yes | FK  | Updating user                       |

---

# 32. Registration Primary Key

`kishor_event_registration_pk` uniquely identifies one registration record.

---

# 33. Participant Foreign Key

```text
kishor_event_registration.kishor_participant_pk
        ↓
kishor_participant.kishor_participant_pk
```

---

# 34. Event Foreign Key

```text
kishor_event_registration.kishor_event_pk
        ↓
kishor_event.kishor_event_pk
```

---

# 35. One Participant — One Registration Per Event

The logical business key is:

```text
kishor_participant_pk
+
kishor_event_pk
```

A participant shall not have duplicate active registrations for the same event.

The physical uniqueness constraint will be finalized during database implementation.

---

# 36. `registration_date`

Date on which the participant was registered for the specific Kishor event.

This differs from:

```text
kishor_participant.registration_date
```

which represents the participant's initial entry into Kishor.

---

# 37. `registration_status`

Represents the state of the event registration.

It is distinct from participant status.

---

# 38. `sakha_organization_pk`

Records the Sakha context applicable to the event registration.

This supports historical reporting and organizational ownership.

---

# 39. `guardian_sangha_sevi_pk`

Optional historical Guardian context for the particular event registration.

This is useful when the participant's Guardian changes between annual events.

The authoritative current Guardian remains on `kishor_participant`.

---

# 40. `participation_status`

Records the participant's event-specific participation state where required.

It is not the same as attendance.

---

# 41. Registration vs Attendance

The table shall not store attendance details as a substitute for the common Attendance module.

Conceptually:

```text
Registration
    ≠
Attendance
```

If attendance is required, the common Attendance framework shall be used.

---

# 42. Historical Registration

Completed annual registrations shall remain historically available.

Example:

```text
KH000123

2026 Registration
2027 Registration
2028 Registration
```

---

# 43. `kishor_membership_transition`

## Purpose

Records the transition between Kishor participation and approved NSS Membership.

---

# 44. `kishor_membership_transition` — Columns

| Column                    | Logical Type     | Required | Key | Description               |
| ------------------------- | ---------------- | -------: | --- | ------------------------- |
| `transition_pk`           | BIGINT           |      Yes | PK  | Transition primary key    |
| `kishor_participant_pk`  | BIGINT           |      Yes | FK  | Kishor participant       |
| `sangha_sevi_pk`          | BIGINT           |      Yes | FK  | Resulting NSS Sangha Sevi |
| `transition_date`         | DATE             |      Yes | —   | Transition date           |
| `membership_type_granted` | Master/Data Type |      Yes | FK  | Membership type granted   |
| `remarks`                 | TEXT             |       No | —   | Administrative remarks    |
| `created_at`              | TIMESTAMP        |      Yes | —   | Creation timestamp        |
| `created_by`              | BIGINT           |      Yes | FK  | Creating user             |
| `updated_at`              | TIMESTAMP        |      Yes | —   | Last update timestamp     |
| `updated_by`              | BIGINT           |      Yes | FK  | Updating user             |

The source explicitly identifies the transition structure around:

```text
transition_pk
kishor_participant_pk
sangha_sevi_pk
transition_date
membership_type_granted
```

---

# 45. `transition_pk`

Internal primary key for the transition record.

---

# 46. `sangha_sevi_pk`

References the common Sangha Sevi identity created/approved through the Membership module.

Kishor does not generate the Sangha Sevi ID independently.

---

# 47. `transition_date`

Date on which the approved transition relationship became effective.

---

# 48. `membership_type_granted`

Records the Membership type associated with the approved transition.

The Membership module remains authoritative for allowable membership types.

---

# 49. KH → SS Relationship

The permanent historical relationship is:

```text
kishor_participant
        ↓
kishor_membership_transition
        ↓
sangha_sevi
```

Example:

```text
KH000123
   ↓
Transition
   ↓
SS000456
```

---

# 50. No Automatic Membership

A Kishor participant shall not receive a Sangha Sevi ID merely by:

* Registration
* Attendance
* Participation
* Completion of Kishor Puja

Membership requires the common Membership approval process.

---

# 51. No Duplicate Person

Membership transition shall not create another Person record.

The same Person remains connected to:

```text
Kishor History
+
NSS Membership
```

---

# 52. Foreign-Key Summary

```text
kishor_participant.person_pk
        ↓
person

kishor_participant.sakha_organization_pk
        ↓
organization

kishor_participant.guardian_sangha_sevi_pk
        ↓
sangha_sevi

kishor_participant.assigned_by_sakha_pk
        ↓
organization

kishor_event.host_organization_pk
        ↓
organization

kishor_event.location_pk
        ↓
location framework

kishor_event_registration.kishor_participant_pk
        ↓
kishor_participant

kishor_event_registration.kishor_event_pk
        ↓
kishor_event

kishor_event_registration.sakha_organization_pk
        ↓
organization

kishor_event_registration.guardian_sangha_sevi_pk
        ↓
sangha_sevi

kishor_membership_transition.kishor_participant_pk
        ↓
kishor_participant

kishor_membership_transition.sangha_sevi_pk
        ↓
sangha_sevi
```

---

# 53. Logical Relationship Cardinalities

```text
Person
  1
  |
  0..1
Kishor Participant
```

```text
Kishor Participant
  1
  |
  N
Kishor Event Registration
```

```text
Kishor Event
  1
  |
  N
Kishor Event Registration
```

```text
Kishor Participant
  1
  |
  N
Membership Transition
```

---

# 54. Permanent Identity Model

```text
PERSON
   ↓
KISHOR_PARTICIPANT
   ↓
KH000123
```

The KH ID remains permanent.

---

# 55. Annual Event Model

```text
KISHOR_PARTICIPANT
       |
       +---- REGISTRATION 2026
       |
       +---- REGISTRATION 2027
       |
       +---- REGISTRATION 2028
```

---

# 56. Guardian Model

```text
SANGHA_SEVI
     |
     | Guardian
     ↓
KISHOR_PARTICIPANT
```

The Guardian must be an NSS Member belonging to the participant's Sakha.

The Sakha assigns the Guardian.

---

# 57. Guardian Assignment Fields

The frozen Guardian requirement is represented by:

```text
guardian_sangha_sevi_pk
assigned_by_sakha_pk
guardian_assigned_date
```

These fields shall not be replaced by a generic free-text Guardian field.

---

# 58. Current vs Historical Guardian

Current participant Guardian:

```text
kishor_participant.guardian_sangha_sevi_pk
```

Historical event Guardian, where required:

```text
kishor_event_registration.guardian_sangha_sevi_pk
```

This prevents later Guardian changes from destroying historical event context.

---

# 59. Family Integration

The Kishor module uses the common Family relationship:

```text
family_group
    ↓
family_relationship
    ↓
person
    ↓
kishor_participant
```

No Kishor-specific family table is introduced.

---

# 60. Family Visibility

Family users may access their own family's Kishor information, including:

```text
Participant Details
Registration Details
Activity History
Training History
Participation Status
Guardian Details
Membership Transition Status
```

Access remains restricted to the user's own family.

---

# 61. Sakha Visibility

Sakha users access Kishor records within their authorized Sakha scope.

The Sakha scope is based on:

```text
sakha_organization_pk
```

---

# 62. Kendra Visibility

Kendra users may access Kishor records across Sakhas according to RBAC.

No separate Kendra-specific Kishor table is required.

---

# 63. Common Attendance Integration

Kishor does not introduce:

```text
kishor_attendance
```

as a core table.

Where required:

```text
kishor event
       ↓
common attendance framework
```

The Attendance module remains authoritative.

---

# 64. Common Audit Integration

Kishor uses the common Audit framework.

No:

```text
kishor_audit
```

table is introduced.

---

# 65. Common Organization Integration

Kishor uses:

```text
organization
```

for:

* Participant Sakha
* Guardian assignment Sakha
* Event host organization

No Kishor-specific organization master is introduced.

---

# 66. Common Membership Integration

Kishor uses:

```text
membership
sangha_sevi
```

for the Membership transition and Guardian identity.

---

# 67. Status Fields

Status fields shall use approved master data where the project standard requires master-driven values.

Potential status categories include:

```text
Participant Status
Registration Status
Participation Status
Event Status
```

These shall remain separate.

---

# 68. No Combined Status

The table design shall not create a generic field such as:

```text
status
```

that attempts to represent:

```text
Registration
Attendance
Membership
Participation
```

simultaneously.

---

# 69. Unique Identity Constraints

Logical uniqueness requirements:

```text
kishor_id
```

must be unique.

The participant identity:

```text
person_pk
```

must not produce multiple active Kishor identities.

The event registration combination:

```text
kishor_participant_pk
+
kishor_event_pk
```

must not produce duplicate active registrations.

---

# 70. Referential Integrity

All foreign keys shall enforce valid references to their owning modules.

Examples:

```text
person_pk → person

sangha_sevi_pk → sangha_sevi

organization_pk → organization
```

No orphaned Kishor references shall be permitted.

---

# 71. Historical Integrity

Completed records shall remain available for:

* Historical reports
* Family dashboards
* Sakha reports
* Kendra reports
* Membership transition traceability
* Audit

---

# 72. Soft Deletion / Deactivation

The physical implementation shall follow the project-wide soft-delete/history standard.

The business rules do not authorize physical deletion of historical Kishor participation records.

---

# 73. Indexing Requirements

The final PostgreSQL implementation should provide efficient lookup for:

```text
kishor_id

person_pk

sakha_organization_pk

guardian_sangha_sevi_pk

kishor_event_pk

registration_date

financial_year

sangha_sevi_pk
```

Exact indexes shall be finalized during physical database optimization.

---

# 74. Search Requirements

The table design should support searches by:

```text
KH ID
Participant Name
Person ID
Sakha
Guardian
Event Year
Event
Registration Status
Participation Status
Membership Transition
```

Name search remains a Person-module concern.

---

# 75. Reporting Requirements

The design supports:

```text
Total Kishor Participants

Participants by Sakha

Annual Registrations

Annual Participation

Guardian Distribution

Participants by Event

Family Participation

KH → SS Transitions
```

---

# 76. Family Dashboard Data

Family Dashboard can derive:

```text
Person
   +
Family Relationship
   +
Kishor Participant
   +
Event Registration
   +
Guardian
   +
Membership Transition
```

No separate family-facing Kishor table is required.

---

# 77. Sakha Dashboard Data

Sakha Dashboard can derive:

```text
Kishor Participants
+
Event Registrations
+
Guardian Assignments
+
Participation
```

filtered by the authorized Sakha.

---

# 78. Kendra Dashboard Data

Kendra Dashboard can aggregate:

```text
All Kishor Participants
+
All Events
+
All Registrations
+
All Sakhas
+
Guardian Assignments
+
Membership Transitions
```

---

# 79. Table Boundary — Person

Kishor shall not store duplicate:

```text
Name
Gender
DOB
Mobile
Email
Address
```

when those values belong to Person.

---

# 80. Table Boundary — Family

Kishor shall not store duplicate:

```text
Father
Mother
Spouse
Children
Family Head
Family Address
```

Family relationships belong to the Family module.

---

# 81. Table Boundary — Organization

Kishor shall not store duplicate Sakha master information.

The Organization module owns organizational identity and hierarchy.

---

# 82. Table Boundary — Membership

Kishor shall not store duplicate:

```text
Sangha Sevi ID
Membership Status
Membership Renewal
Membership Transfer
Membership History
```

The Membership module owns these domains.

---

# 83. Table Boundary — Attendance

Kishor shall not duplicate the Attendance engine.

---

# 84. Table Boundary — Event

If a common Event framework becomes authoritative, Kishor-specific event data shall contain only the additional Kishor-specific information required by the approved architecture.

This document preserves the current logical `kishor_event` entity.

---

# 85. No SQL Schema

This document intentionally does not contain:

```text
CREATE TABLE
ALTER TABLE
CREATE INDEX
CREATE TRIGGER
CREATE SEQUENCE
Django migration
```

Those belong to the physical database implementation stage.

---

# 86. No Premature Physical Constraint

Where the business requirement is clear but the exact PostgreSQL implementation has not been frozen, this document records the logical requirement without prescribing SQL syntax.

---

# 87. Core Table Summary

```text
1. kishor_participant
   Permanent Kishor identity

2. kishor_event
   Annual Kishor Puja event

3. kishor_event_registration
   Participant registration for an event

4. kishor_membership_transition
   KH → NSS Membership relationship
```

---

# 88. Complete Logical Model

```text
                         PERSON
                           |
                           v
                  KISHOR_PARTICIPANT
                   |       |       |
                   |       |       |
                   |       |       +---- Guardian ----> SANGHA_SEVI
                   |       |
                   |       +---- Sakha -------------> ORGANIZATION
                   |
                   +----< KISHOR_EVENT_REGISTRATION >---- KISHOR_EVENT
                   |
                   +----< KISHOR_MEMBERSHIP_TRANSITION >- SANGHA_SEVI
```

---

# 89. Final Table Design

```text
kishor_participant
        |
        +---- kishor_event_registration ---- kishor_event
        |
        +---- kishor_membership_transition ---- sangha_sevi
        |
        +---- guardian_sangha_sevi ---- sangha_sevi
        |
        +---- sakha_organization ---- organization
        |
        +---- person ---- family
```

---

# 90. Final Architecture Rules

The physical implementation shall preserve:

```text
One Person
   ↓
One Kishor Identity
   ↓
One Permanent KH ID
   ↓
Many Annual Registrations
   ↓
Many Participation Records through event/attendance integration
   ↓
Optional Membership Transition
   ↓
Sangha Sevi
```

Guardian:

```text
Sakha
   ↓
Assigns
   ↓
NSS Member / Sangha Sevi
   ↓
Kishor Participant
```

---

# 91. Source Alignment

This table design reflects the currently frozen Kishor source:

```text
Annual Event-Based Kishor Puja

Permanent KH ID

Sakha-Based Registration

Sakha-Assigned NSS Guardian

Family Visibility

Year-wise Participation

KH → SS Membership Transition
```

The source identifies Kishor Puja as an annual event/activity rather than a permanent organizational unit.

---

# 92. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

---

# End of Document
