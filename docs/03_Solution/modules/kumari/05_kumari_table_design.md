# NSS ERP — Kumari Sangha Table Design

**Document ID:** SOL-KUM-005  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Kumari Sangha  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical table design for the Kumari Sangha module.

It translates the approved/frozen Kumari business rules, lifecycle and ERD into logical data structures.

This document defines:

- Logical entities
- Ownership
- Relationships
- Key attributes
- Identity boundaries
- Historical requirements
- Common-module reuse

This document does not define PostgreSQL SQL or Django migrations.

---

# 2. Core Kumari Tables

The current Kumari logical model contains five core tables:

```text
kumari_sangha

kumari_membership

kumari_activity

kumari_activity_participant

kumari_membership_transition
```

The project baseline identifies approximately five Kumari tables within the overall NSS V2 architecture.

---

# 3. Common Tables Reused

The Kumari module shall reuse common NSS tables for:

```text
person

family_group

family_relationship

organization

membership

sangha_sevi

governance

attendance

audit
```

The Kumari module shall not duplicate these foundation entities.

---

# 4. Table Ownership

| Table                          | Owner        | Purpose                 |
| ------------------------------ | ------------ | ----------------------- |
| `person`                       | Person       | Person identity         |
| `family_group`                 | Family       | Family identity         |
| `family_relationship`          | Family       | Family relationships    |
| `organization`                 | Organization | Organizational scope    |
| `membership`                   | Membership   | NSS Membership          |
| `sangha_sevi`                  | Membership   | NSS Membership identity |
| `kumari_sangha`                | Kumari       | Kumari Sangha context   |
| `kumari_membership`            | Kumari       | Kumari participation    |
| `kumari_activity`              | Kumari       | Kumari activities       |
| `kumari_activity_participant`  | Kumari       | Activity participation  |
| `kumari_membership_transition` | Kumari       | Kumari → NSS transition |

---

# 5. `kumari_sangha`

## 5.1 Purpose

Represents a Kumari Sangha organizational context.

A Kumari Sangha record provides the organizational context within which Kumari participants are enrolled and activities are conducted.

---

## 5.2 Logical Attributes

```text
kumari_sangha_pk

organization_pk

name

code

status

formed_date

remarks

created_at
created_by

updated_at
updated_by
```

These are logical attributes only.

The final physical schema remains subject to database implementation standards.

---

# 6. `kumari_sangha` — Primary Key

```text
kumari_sangha_pk
```

shall uniquely identify the Kumari Sangha record.

The primary key shall be system-generated according to the project database identity standards.

---

# 7. `kumari_sangha` — Organization Relationship

```text
organization
      │
      ▼
kumari_sangha
```

`organization_pk` associates the Kumari Sangha with the common Organization framework.

The Kumari module shall not create a separate organizational hierarchy.

---

# 8. `kumari_sangha` — No Duplicate Organization

The following table shall not be created:

```text
kumari_organization
```

The common Organization module remains authoritative.

---

# 9. `kumari_membership`

## 9.1 Purpose

Represents participation of a Person in Kumari Sangha.

This is **not NSS Membership**.

The distinction is mandatory:

```text
kumari_membership
        ≠
membership
```

---

# 10. `kumari_membership` — Logical Attributes

```text
kumari_membership_pk

kumari_id

person_pk

kumari_sangha_pk

status

joined_date

exit_date

exit_reason

remarks

created_at
created_by

updated_at
updated_by
```

The core frozen source identifies:

```text
kumari_membership_pk
kumari_id
person_pk
kumari_sangha_pk
status
joined_date
exit_date
exit_reason
```

as the logical structure.

---

# 11. `kumari_membership` — Primary Key

```text
kumari_membership_pk
```

uniquely identifies the Kumari participation record.

It is an internal database identifier.

It is not the public Kumari ID.

---

# 12. Kumari ID

```text
kumari_id
```

is the participant-facing Kumari identity.

Example:

```text
KM000001
KM000002
KM000003
```

The Kumari ID is:

```text
Unique
Permanent
Never Reused
```

It is separate from Sangha Sevi ID.

---

# 13. Kumari ID Generation

A Kumari ID shall be generated when the participant is enrolled into Kumari Sangha.

The system shall not generate a Sangha Sevi ID at this point.

---

# 14. Kumari ID Uniqueness

`kumari_id` shall be unique within the Kumari identity namespace.

A previous Kumari ID shall never be assigned to another Person.

---

# 15. Person Relationship

```text
person
   │
   │ 1
   │
   ▼
kumari_membership
```

The Person table remains authoritative for:

* Name
* Gender
* Date of birth
* Contact information
* Person lifecycle

Kumari stores only the domain-specific participation relationship.

---

# 16. Family Relationship

The Kumari participant may be associated with the common Family model through the Person.

Conceptually:

```text
family_group
      │
      ▼
person
      │
      ▼
kumari_membership
```

The Kumari table shall not duplicate:

```text
family_group_pk
```

unless a future approved requirement establishes a direct, necessary Kumari-family relationship.

The Person/Family relationship remains authoritative.

---

# 17. Kumari Sangha Relationship

```text
kumari_sangha
      │
      │ 1
      │
      ▼
kumari_membership
```

A Kumari Sangha may have multiple Kumari participants.

---

# 18. Kumari Membership Status

The logical status model supports the frozen Kumari lifecycle:

```text
ACTIVE

MARRIED_OUT

BECAME_NSS_MEMBER

WITHDRAWN

DECEASED
```

These statuses preserve the reason for the end of active Kumari participation.

---

# 19. Exit Date

```text
exit_date
```

records the effective date on which active Kumari participation ended.

It shall be populated when applicable.

---

# 20. Exit Reason

```text
exit_reason
```

preserves why active Kumari participation ended.

Examples:

```text
MARRIED_OUT
BECAME_NSS_MEMBER
WITHDRAWN
DECEASED
```

The final master-data representation shall follow the project Master Data standard.

---

# 21. History Preservation

A `kumari_membership` record shall not be physically deleted merely because participation ends.

The record must remain available for historical reporting.

---

# 22. `kumari_activity`

## 22.1 Purpose

Represents activities conducted under Kumari Sangha.

Activities are separate from Kumari membership.

---

# 23. `kumari_activity` — Logical Attributes

```text
kumari_activity_pk

kumari_sangha_pk

activity_type

activity_name

description

activity_date

start_date

end_date

location_pk

status

remarks

created_at
created_by

updated_at
updated_by
```

The exact final attribute set remains subject to detailed activity requirements.

---

# 24. Activity Types

Potential activity classifications include:

```text
REGULAR_ACTIVITY

TRAINING

DINA_LIPI

NIYAM_PANCHAK

DASA_SHEELA

CHARACTER_BUILDING

SPIRITUAL_EDUCATION

SERVICE_ACTIVITY
```

These should be treated as logical examples until the corresponding master-data definitions are formally approved.

---

# 25. Activity Date

An activity may have:

```text
activity_date
```

and, where required:

```text
start_date
end_date
```

This allows both one-day and multi-day activities.

---

# 26. Activity Location

Where an activity has a location, it should reference the common Location/Organization framework.

The Kumari module shall not create a separate location master.

---

# 27. Activity Status

The activity lifecycle shall support the common event/activity status model where applicable.

Possible logical states may include:

```text
DRAFT
PUBLISHED
COMPLETED
CANCELLED
```

The final common Event/Activity status master shall remain authoritative.

---

# 28. Activity History

Completed or cancelled activities shall remain historically available.

An activity shall not be physically deleted merely because it is completed or cancelled.

---

# 29. `kumari_activity_participant`

## 29.1 Purpose

Represents participation of Kumari participants in Kumari activities.

It resolves the many-to-many relationship between:

```text
kumari_membership
```

and:

```text
kumari_activity
```

---

# 30. Activity Participation Relationship

```text
kumari_membership
        │
        │ 1
        ▼
kumari_activity_participant
        ▲
        │ 1
        │
kumari_activity
```

Conceptually:

```text
One Kumari
   ↓
Many Activities

One Activity
   ↓
Many Kumaris
```

---

# 31. `kumari_activity_participant` — Logical Attributes

```text
kumari_activity_participant_pk

kumari_activity_pk

kumari_membership_pk

participation_status

participation_date

remarks

created_at
created_by

updated_at
updated_by
```

---

# 32. Participation Status

Participation status is separate from Kumari membership status.

For example:

```text
Kumari Membership:
ACTIVE

Activity Participation:
ATTENDED
```

The two statuses shall never be treated as interchangeable.

---

# 33. Attendance Relationship

Where the common Attendance module records actual attendance, the Kumari activity participation record shall remain conceptually separate from attendance.

```text
Eligibility
    ≠
Participation
    ≠
Attendance
```

No separate `kumari_attendance` table is currently part of the frozen five-table Kumari model.

---

# 34. Training

Training may be represented as a Kumari activity where the common activity framework is sufficient.

Example:

```text
kumari_activity
activity_type = TRAINING
```

No dedicated training table is currently frozen for Kumari.

---

# 35. Dina-Lipi

Dina-Lipi may be represented through the activity framework at the current logical level.

Example:

```text
kumari_activity
activity_type = DINA_LIPI
```

Detailed Dina-Lipi tracking structures shall only be added if an approved business requirement requires them.

---

# 36. Niyam Panchak

Niyam Panchak may be represented through the activity framework at the current logical level.

Detailed assessment structures are not currently frozen.

---

# 37. Dasa Sheela

Dasa Sheela may be represented through the activity framework at the current logical level.

Detailed assessment structures are not currently frozen.

---

# 38. `kumari_membership_transition`

## 38.1 Purpose

Records transition from Kumari participation to NSS Membership.

This preserves the historical relationship between:

```text
Kumari ID
```

and:

```text
Sangha Sevi ID
```

---

# 39. `kumari_membership_transition` — Logical Attributes

```text
transition_pk

kumari_membership_pk

sangha_sevi_pk

transition_date

membership_type_granted

remarks

created_at
created_by

updated_at
updated_by
```

The frozen source explicitly identifies the core transition fields:

```text
transition_pk
kumari_membership_pk
sangha_sevi_pk
transition_date
membership_type_granted
remarks
```

---

# 40. Transition Relationship

```text
kumari_membership
       │
       │
       ▼
kumari_membership_transition
       │
       ▼
sangha_sevi
```

This is a cross-module relationship.

---

# 41. Sangha Sevi Ownership

`sangha_sevi` is owned by the common Membership module.

The Kumari module does not create:

```text
kumari_sangha_sevi
```

---

# 42. NSS Membership Relationship

The transition ultimately corresponds to approved NSS Membership.

Conceptually:

```text
kumari_membership
       │
       ▼
transition
       │
       ▼
NSS Membership
       │
       ▼
sangha_sevi
       │
       ▼
SS000456
```

The Membership module owns the approval process and official membership identity.

---

# 43. Membership Type Granted

The transition record preserves the membership type granted.

Possible values include:

```text
REGULAR_MEMBER

PROBATIONARY_MEMBER
```

The authoritative Membership module owns the actual membership type master.

---

# 44. Transition Date

```text
transition_date
```

records when the approved Kumari → NSS transition took effect.

---

# 45. Transition History

Transition records shall never be physically deleted.

The system must preserve:

```text
Kumari ID
NSS ID
Transition Date
Membership Type
```

for historical traceability.

---

# 46. Direct Regular Membership

The table design supports direct Regular Membership transition for a long-term Kumari participant where approved.

```text
KM000123
    ↓
Transition
    ↓
SS000456
membership_type = REGULAR_MEMBER
```

This follows the frozen business rule that probation is not automatically mandatory for every long-term Kumari participant.

---

# 47. Probationary Membership

The same transition model supports:

```text
KM000123
    ↓
Transition
    ↓
SS000456
membership_type = PROBATIONARY_MEMBER
```

The actual decision belongs to the common Membership authority.

---

# 48. Identity Relationship

The permanent identity relationship is:

```text
KM000123
      │
      │ transition
      ▼
SS000456
```

The Kumari ID remains historically valid.

The Sangha Sevi ID is independently generated according to NSS Membership rules.

---

# 49. No NSS ID at Kumari Enrollment

The following design is prohibited:

```text
Kumari Enrollment
      ↓
Sangha Sevi ID
```

Instead:

```text
Kumari Enrollment
      ↓
KM ID

Later:
Membership Approval
      ↓
SS ID
```

---

# 50. No Duplicate Person

The transition shall not create another Person record.

The same:

```text
person_pk
```

is associated with both:

```text
Kumari Participation
```

and later:

```text
NSS Membership
```

---

# 51. Common Family Architecture

The Kumari module shall reuse:

```text
family_group
family_relationship
```

for family integration.

The frozen project architecture identifies Family as the common foundation for youth participant visibility.

---

# 52. Family Visibility

Family dashboards may expose authorized Kumari information such as:

```text
Participant Details
Registration Details
Activity History
Training History
Participation Status
Membership Transition Status
```

Access shall be limited to the user's own family.

The family visibility rule is frozen in the project source.

---

# 53. Organization Reuse

Kumari Sangha shall reuse:

```text
organization
```

for organizational scope.

No:

```text
kumari_sakha
kumari_organization
```

tables shall be created.

---

# 54. Governance Reuse

If Kumari governance/coordinator structures are required, the common Unified Governance Model shall be reused.

Potential common structures include:

```text
body_master
body_member_assignment
position_master
```

No Kumari-specific governance table is currently frozen.

---

# 55. Attendance Reuse

Attendance shall use the common Attendance module.

No:

```text
kumari_attendance
```

table is currently part of the Kumari core table set.

---

# 56. Audit Reuse

Audit shall use the common Audit module.

No:

```text
kumari_audit
```

table shall be created.

---

# 57. Security / RBAC Reuse

Kumari access shall use common NSS RBAC.

No:

```text
kumari_permission
kumari_role
kumari_user
```

tables shall be created.

---

# 58. Master Data Reuse

Where applicable, Kumari shall use common master-data structures for:

```text
Status
Activity Type
Organization Type
Membership Type
Transition Type
Exit Reason
```

---

# 59. Core Foreign-Key Relationships

The logical relationships are:

```text
organization
      │
      ▼
kumari_sangha
      │
      ▼
kumari_membership
      │
      ├───────────────┐
      │               │
      ▼               ▼
kumari_activity_   kumari_membership_
participant        transition
      ▲               │
      │               ▼
      │           sangha_sevi
      │
      │
kumari_activity
```

---

# 60. Person Relationship

```text
person
   │
   ▼
kumari_membership
```

The Person record is the common identity anchor.

---

# 61. Complete Logical Model

```text
PERSON
  │
  ▼
KUMARI_MEMBERSHIP
  │
  ├──────────────► KUMARI_ACTIVITY_PARTICIPANT
  │                       ▲
  │                       │
  │                  KUMARI_ACTIVITY
  │
  └──────────────► KUMARI_MEMBERSHIP_TRANSITION
                           │
                           ▼
                      SANGHA_SEVI
```

with:

```text
KUMARI_SANGHA
      │
      ▼
KUMARI_MEMBERSHIP
```

and:

```text
ORGANIZATION
      │
      ▼
KUMARI_SANGHA
```

---

# 62. Core Table Count

Current Kumari-specific logical tables:

```text
1. kumari_sangha
2. kumari_membership
3. kumari_activity
4. kumari_activity_participant
5. kumari_membership_transition
```

Total:

```text
5
```

This matches the project baseline's identified Kumari table count.

---

# 63. Tables Not Required

The following are not part of the current Kumari design:

```text
kumari_person
kumari_family
kumari_family_relationship

kumari_organization

kumari_nss_membership
kumari_sangha_sevi

kumari_attendance

kumari_governance
kumari_governing_body

kumari_finance
kumari_audit

kumari_permission
kumari_role
```

Common NSS modules own these capabilities.

---

# 64. Potential Future Tables

The following are deliberately not frozen:

```text
kumari_dina_lipi
kumari_niyam_panchak
kumari_dasa_sheela
kumari_training
kumari_assessment
kumari_certificate
```

They shall only be introduced if approved business requirements demonstrate that the common activity framework is insufficient.

---

# 65. No Premature Normalization

The table design shall not create separate physical tables merely because a business concept has a distinct name.

For example:

```text
Dina-Lipi
Niyam Panchak
Dasa Sheela
```

do not automatically require separate tables.

The current requirement supports representing them as Kumari activities.

---

# 66. History Preservation

All core Kumari records shall support historical preservation.

At minimum:

```text
kumari_membership
kumari_activity
kumari_activity_participant
kumari_membership_transition
```

shall remain historically traceable.

---

# 67. Audit Fields

Kumari-specific tables shall follow project audit standards.

Logical audit fields:

```text
created_at
created_by
updated_at
updated_by
```

Where the common project standard requires soft deletion, the applicable common fields shall be used.

Physical implementation remains subject to the project-wide Audit Standards.

---

# 68. Identifier Principles

The design distinguishes:

```text
Database Primary Key
        ≠
Business Identifier
```

Example:

```text
kumari_membership_pk
        ≠
KM000123
```

and:

```text
sangha_sevi_pk
        ≠
SS000456
```

---

# 69. Business Identifier Permanence

The business identifiers:

```text
KM000123
SS000456
```

shall never be reassigned to another person.

---

# 70. Cross-Module Ownership

| Concept              | Owning Module       |
| -------------------- | ------------------- |
| Person identity      | Person              |
| Family               | Family              |
| Organization         | Organization        |
| Kumari participation | Kumari              |
| Kumari activity      | Kumari              |
| NSS Membership       | Membership          |
| Sangha Sevi ID       | Membership          |
| Attendance           | Attendance          |
| Governance           | Governance          |
| Audit                | Audit               |
| Security             | Administration/RBAC |

---

# 71. Database Design Principle

The Kumari module follows:

```text
Common Foundation
        +
Kumari-Specific Domain Entities
        ↓
Kumari Solution
```

This avoids duplicate foundation tables while preserving Kumari-specific business behavior.

---

# 72. Unified Youth Framework Decision

An earlier design discussion proposed a generic:

```text
youth_program
youth_participant
youth_registration
```

framework.

The current Kumari baseline retains the **separate five-table Kumari logical model**.

Therefore this document does not introduce `youth_*` tables.

The earlier unified-youth proposal is not treated as the current Kumari table design.

---

# 73. Kishor Boundary

Kumari and Kishor Puja shall remain separate business domains.

Kumari uses:

```text
kumari_sangha
kumari_membership
kumari_activity
kumari_activity_participant
kumari_membership_transition
```

Kishor Puja has its own event-oriented model.

The two modules may reuse common foundation entities but shall not be merged merely because both are youth programs.

---

# 74. Physical PostgreSQL Schema

This document does not finalize PostgreSQL DDL.

The logical design must first be approved through the Solution documentation process.

Only then may implementation artifacts define:

```text
CREATE TABLE
FOREIGN KEY
UNIQUE
CHECK
INDEX
TRIGGER
```

as required.

---

# 75. SQL Creation Prohibited at This Stage

No SQL schema shall be generated as part of this document.

The current project workflow remains:

```text
Source / REF
      ↓
Business Rules
      ↓
Solution
      ↓
Logical Table Design
      ↓
Physical Schema
```

---

# 76. Traceability

The table design derives from:

```text
Kumari Business Rules
Kumari Lifecycle
Kumari ERD
Kumari Identity & Transition Rules
Common Person/Family Foundation
Common Membership Identity Model
Common Organization Model
Common Audit/RBAC Standards
```

The project governance model requires downstream Solution artifacts to remain traceable to their governing requirements and authoritative references.

---

# 77. Final Logical Architecture

```text
                     PERSON
                       │
                       ▼
               KUMARI MEMBERSHIP
                 KM000123
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      ACTIVITIES    PARTICIPATION  TRANSITION
          │            │            │
          │            │            ▼
          │            │        SANGHA SEVI
          │            │          SS000456
          │            │
          └────────────┘

ORGANIZATION
      │
      ▼
KUMARI SANGHA
      │
      ▼
KUMARI MEMBERSHIP
```

---

# 78. Final Identity Architecture

```text
                    PERSON
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
  KUMARI MEMBERSHIP          NSS MEMBERSHIP
          │                       │
          ▼                       ▼
      KM000123                SS000456
          │                       │
          └──── TRANSITION ───────┘
```

The two identities remain separate and permanently traceable.

---

# 79. Final Decision

The current Kumari module consists of:

```text
Kumari-Specific:

kumari_sangha
kumari_membership
kumari_activity
kumari_activity_participant
kumari_membership_transition
```

and reuses:

```text
Common:

person
family_group
family_relationship
organization
membership
sangha_sevi
governance
attendance
audit
```

No additional Kumari tables are frozen at this time.

---

# 80. Status

```text
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED

VERSION:
1.0.0
```

The Kumari Solution documentation set is now complete at the five-document level:

```text
01_kumari_module_overview.md       ✓
02_kumari_erd.md                   ✓
03_kumari_lifecycle.md             ✓
04_kumari_business_rules.md        ✓
05_kumari_table_design.md          ✓
```

---

# End of Document
