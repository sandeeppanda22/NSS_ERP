# NSS ERP — Sevak Sangha ERD

**Document ID:** SOL-SEV-002  
**Version:** 2.0.0  
**Status:** DRAFT — CONSOLIDATION IN PROGRESS  
**Parent Module:** Sevak Sangha  
**Scope:** Conceptual Entity Relationship Model

---

# 1. Purpose

This document defines the conceptual Entity Relationship Diagram (ERD) for the Sevak Sangha Module.

It establishes:

- Core Sevak identity relationships
- NSS Membership relationship
- Sangha Sevi ID relationship
- Sevak participation
- Sakha association history
- Status lifecycle history
- Reactivation review
- Event participation
- Attendance
- Seva Assignment integration
- Organizational relationships

This document intentionally defines the **domain model**, not the final PostgreSQL table structure.

The physical table design is maintained separately in:

```text
06_sevak_table_design.md
```

---

# 2. ERD Design Principle

The Sevak module follows:

```text
Person
   ↓
NSS Membership
   ↓
Sangha Sevi ID
   ↓
Sevak Participation
```

Sevak participation is an additional NSS participation layer.

It does not replace or duplicate:

* Person
* Membership
* Sangha Sevi ID
* Organization

---

# 3. Ownership Principle

The following entities belong to other authoritative modules:

```text
Person
Membership
Sangha Sevi
Organization / Sakha
Event
Seva Category
```

The Sevak module references these entities.

The Sevak module owns the Sevak-specific entities and relationships.

Conceptually:

```text
┌─────────────────────────────┐
│     COMMON NSS DOMAIN       │
│                             │
│ Person                      │
│ Membership                  │
│ Sangha Sevi ID              │
│ Organization / Sakha        │
│ Event                       │
│ Seva Category               │
└──────────────┬──────────────┘
               │
               │ references
               ▼
┌─────────────────────────────┐
│      SEVAK MODULE           │
│                             │
│ Sevak Participation         │
│ Sakha Association History   │
│ Status History              │
│ Reactivation Review         │
│ Event Participation         │
│ Seva Assignment Integration │
└─────────────────────────────┘
```

---

# 4. Core Identity Relationship

The fundamental relationship is:

```text
PERSON
   │
   │ 1 : 1 / existing identity relationship
   ▼
MEMBERSHIP
   │
   │ 1 : 1
   ▼
SANGHA SEVI ID
   │
   │ 1 : 0..N historical participation records
   ▼
SEVAK PARTICIPATION
```

The exact physical cardinality of Person → Membership is governed by the Membership module.

The Sevak ERD does not redefine that relationship.

---

# 5. Person

`Person` is the foundational identity.

The Sevak module does not create a duplicate Person record.

Conceptually:

```text
PERSON
------
person_pk
```

The Sevak participation references the authoritative Person identity through the common NSS identity model.

Person owns:

* Name
* Gender
* Date of Birth
* Contact information
* Other identity attributes

The Sevak module consumes these attributes for eligibility and participation rules.

---

# 6. NSS Membership

NSS Membership is mandatory for Sevak participation.

Conceptually:

```text
PERSON
   │
   ▼
NSS MEMBERSHIP
   │
   ▼
SANGHA SEVI ID
```

The Sevak module does not create a separate Membership.

Membership owns:

* Membership lifecycle
* Membership Type
* Current Sakha
* Membership Transfer

The Sevak module reacts to Membership lifecycle events.

---

# 7. Sangha Sevi ID

Sangha Sevi ID is the authoritative NSS Membership identity.

Conceptually:

```text
MEMBERSHIP
     │
     ▼
SANGHA SEVI
     │
     ▼
SEVAK PARTICIPATION
```

Sevak participation does not create another permanent identity such as:

```text
SV000001
SV000002
```

No separate Sevak ID is frozen.

---

# 8. Organization / Sakha

The Sevak module references the common Organization/Sakha structure.

Conceptually:

```text
ORGANIZATION
     │
     └── SAKHA
```

A Sakha:

* May have a Sevak Sangha.
* May not have a Sevak Sangha.

The presence of a Sevak Sangha is therefore not assumed for every Sakha.

---

# 9. Sevak Sangha Organizational Context

The conceptual model recognizes a Sevak Sangha organizational context associated with an applicable Sakha/organizational unit.

```text
SAKHA
   │
   ├── Has Sevak Sangha
   │
   └── Does Not Have Sevak Sangha
```

This does not require every Sakha to have a separate physical Sevak organization record.

The final physical representation shall be determined during Step 11.

---

# 10. Sevak Participation

The central Sevak entity is:

```text
SEVAK PARTICIPATION
```

It represents a person's participation in Sevak Sangha.

Conceptually:

```text
PERSON
   │
   ▼
MEMBERSHIP
   │
   ▼
SANGHA SEVI
   │
   ▼
SEVAK PARTICIPATION
```

The Sevak Participation entity contains the current and historical participation relationship.

---

# 11. Sevak Participation Status

Sevak Participation has only:

```text
ACTIVE
INACTIVE
```

No additional Sevak status categories are required.

Conceptually:

```text
SEVAK PARTICIPATION
        │
        ├── ACTIVE
        │
        └── INACTIVE
```

---

# 12. First Sevak Enrollment Date

The Sevak Participation lifecycle maintains:

```text
FIRST SEVAK ENROLLMENT DATE
```

This is permanent.

It does not change because of:

* Transfer
* Inactivation
* Reactivation

Conceptually:

```text
SEVAK PARTICIPATION
        │
        └── First Enrollment Date
```

---

# 13. Sakha Association History

Sakha association is effective-dated history.

Conceptually:

```text
SEVAK PARTICIPATION
        │
        │ 1 : N
        ▼
SEVAK SAKHA ASSOCIATION HISTORY
```

Example:

```text
Sevak Participation
       │
       ├── Sakha A
       │   01-Jan-2020 → 15-Aug-2026
       │
       └── Sakha B
           15-Aug-2026 → Current
```

The historical association is preserved.

---

# 14. Current Sakha

The current Sakha is derived from the applicable active/current association.

The Sevak module does not independently decide the person's current Sakha.

The authoritative source is NSS Membership.

Therefore:

```text
NSS MEMBERSHIP
      │
      ▼
CURRENT SAKHA
      │
      ▼
SEVAK SAKHA ASSOCIATION
```

---

# 15. Membership Transfer Relationship

Membership Transfer is an external lifecycle event from the Membership module.

Conceptually:

```text
MEMBERSHIP TRANSFER
        │
        ▼
CURRENT SAKHA CHANGES
        │
        ▼
SEVAK PARTICIPATION LIFECYCLE
```

The Sevak module does not create a separate Sevak Transfer process.

---

# 16. Transfer-Triggered Inactivation

When Membership transfers from Sakha A to Sakha B:

```text
SEVAK PARTICIPATION
ACTIVE
   │
   ▼
SYSTEM TRANSITION
   │
   ▼
INACTIVE
```

with:

```text
inactivation_source = SYSTEM
inactivation_reason = TRANSFERRED_TO_OTHER_SAKHA
```

No manual Sevak intervention is required.

---

# 17. New Sakha Sevak Participation

After transfer:

```text
NEW SAKHA
    │
    ├── Has Sevak Sangha
    │       │
    │       ▼
    │   New ACTIVE participation may be created
    │
    └── No Sevak Sangha
            │
            ▼
        No new current participation
```

The previous participation remains historical.

---

# 18. Death Relationship

Death is a Person/Membership lifecycle event.

Conceptually:

```text
PERSON / MEMBERSHIP
        │
        ▼
DECEASED
        │
        ▼
SEVAK PARTICIPATION
        │
        ▼
INACTIVE
```

with:

```text
inactivation_source = SYSTEM
inactivation_reason = DECEASED
```

The Sevak module consumes the authoritative death lifecycle event.

---

# 19. Global Deceased Status

`DECEASED` is not a Sevak-only concept.

The authoritative deceased status belongs to the Person/Membership lifecycle.

Therefore:

```text
PERSON
  │
  ▼
DECEASED
  │
  ├── Sevak → INACTIVE
  ├── Other applicable participation modules
  └── Other lifecycle-dependent modules
```

The Sevak ERD references the lifecycle result rather than owning the global deceased state.

---

# 20. Sevak Status History

Status changes must be historically preserved.

Conceptually:

```text
SEVAK PARTICIPATION
        │
        │ 1 : N
        ▼
SEVAK STATUS HISTORY
```

Example:

```text
2020-01-01  ACTIVE
2024-06-10  INACTIVE
2025-01-15  ACTIVE
2026-08-18  INACTIVE
```

The current status is the current lifecycle state.

Historical status records remain immutable historical information.

---

# 21. Inactivation Metadata

Where participation becomes INACTIVE, the lifecycle may record:

```text
Source
Reason
Date/Time
Actor / System
```

Sources:

```text
MANUAL
SYSTEM
```

System-generated reasons include:

```text
TRANSFERRED_TO_OTHER_SAKHA
DECEASED
```

Manual inactivation reasons include:

```text
NO_LONGER_PARTICIPATING
PERSONAL_REASON
LONG_TERM_ABSENCE
OTHER
```

---

# 22. Reactivation Review

INACTIVE attendance can create a reactivation review.

Conceptually:

```text
SEVAK PARTICIPATION
        │
        │ 1 : N
        ▼
REACTIVATION REVIEW
```

Each review has a lifecycle:

```text
OPEN
  │
  ▼
CLOSED
```

Only one OPEN review may exist for a Sevak at a time.

---

# 23. Reactivation Review and Attendance

The relationship is:

```text
EVENT
   │
   ▼
ATTENDANCE
   │
   ▼
INACTIVE SEVAK
   │
   ▼
REACTIVATION REVIEW
```

Additional attendance while a review is OPEN attaches to the existing review.

Attendance itself does not change Sevak status.

---

# 24. Reactivation

Authorized review may result in:

```text
KEEP INACTIVE
```

or:

```text
REACTIVATE
```

If reactivated:

```text
INACTIVE
   │
   ▼
ACTIVE
```

The original First Sevak Enrollment Date remains unchanged.

---

# 25. No Automatic Reactivation Relationship

The ERD must not model:

```text
ATTENDANCE
    ↓
AUTOMATIC ACTIVE
```

Instead:

```text
ATTENDANCE
    ↓
REACTIVATION REVIEW
    ↓
AUTHORIZED DECISION
    ├── INACTIVE
    └── ACTIVE
```

---

# 26. Sevak Event Relationship

Sevak participation interacts with the common Event framework.

Current Sevak-specific event types are:

```text
SAKHA_SEVAK_SANGHA_SESSION
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

Conceptually:

```text
SEVAK PARTICIPATION
        │
        ▼
EVENT PARTICIPATION
        │
        ▼
EVENT
```

The Event entity itself belongs to the common Event framework.

---

# 27. Event Participation

A person participates in an event through an event participation relationship.

Conceptually:

```text
SEVAK PARTICIPATION
        │
        │ 1 : N
        ▼
EVENT PARTICIPATION
        │
        ▼
EVENT
```

Event participation may contain:

* Participant
* Intention
* Participation planning state
* Attendance relationship

The exact physical structure is deferred to the common Event/Attendance design.

---

# 28. Event Eligibility

Eligibility is derived from authoritative records.

The conceptual flow is:

```text
MEMBERSHIP
     │
     ├── Current Sakha
     ├── Anchalika
     ├── Zilla
     └── Gender
           │
           ▼
     EVENT ELIGIBILITY
```

and:

```text
SEVAK PARTICIPATION
     │
     └── Current Sevak status / association
           │
           ▼
     EVENT ELIGIBILITY
```

Eligibility is not stored as a permanent duplicate membership status.

---

# 29. Eligibility vs Participation

The ERD must distinguish:

```text
ELIGIBILITY
```

from:

```text
EVENT PARTICIPATION
```

A person may be eligible without participating.

Therefore:

```text
Eligible Person
      │
      ├── Does not participate
      │
      └── Participates
```

---

# 30. Attendance

Actual attendance belongs to the common Attendance/Event framework.

Conceptually:

```text
EVENT
   │
   ▼
EVENT PARTICIPATION
   │
   ▼
ATTENDANCE
```

For a person and event:

```text
Maximum one attendance record
```

Duplicate attendance must not be created.

---

# 31. Attendance and INACTIVE Sevak

The ERD relationship is:

```text
SEVAK PARTICIPATION
       │
       │ status = INACTIVE
       ▼
EVENT PARTICIPATION
       │
       ▼
ATTENDANCE
       │
       ▼
REACTIVATION REVIEW
```

This preserves the distinction between:

```text
Sevak Status
```

and:

```text
Attendance
```

---

# 32. Attendance Does Not Change Membership

Attendance at a Sevak event does not create:

```text
Membership Transfer
```

and does not create:

```text
Sevak Transfer
```

Therefore:

```text
EVENT ATTENDANCE
       │
       └── No direct relationship
              to Membership Transfer
```

Membership remains authoritative.

---

# 33. Local Sakha Session Relationship

For:

```text
SAKHA_SEVAK_SANGHA_SESSION
```

the event is associated with a host Sakha.

Conceptually:

```text
SAKHA
  │
  ▼
SEVAK SANGHA SESSION
  │
  ▼
LOCAL PARTICIPANTS
```

The local session does not create cross-Sakha Sevak participation.

---

# 34. Anchalika/Zilla Puja Relationship

For:

```text
ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

the event is hosted by a registered Sakha within the applicable Anchalika/Zilla.

Conceptually:

```text
ANCHALIKA / ZILLA
        │
        ▼
EVENT
        │
        ▼
HOST SAKHA
        │
        ▼
PARTICIPANTS
```

The host Sakha is the event host/venue.

It does not become the participant's new Sakha.

---

# 35. Cross-Anchalika/Zilla Participation

A Sevak may participate in an applicable Anchalika/Zilla event outside their own Anchalika/Zilla.

Conceptually:

```text
SEVAK
  │
  ├── Current Anchalika = A
  │
  ▼
EVENT
  │
  └── Event Anchalika = B
```

The event participation does not modify:

```text
Current Sakha
Current Anchalika
Current Zilla
Membership
Sevak Association
```

---

# 36. Attendance Intention

Where intention is enabled:

```text
EVENT PARTICIPATION
        │
        ▼
ATTENDANCE INTENTION
```

Possible states include:

```text
INTERESTED / WILL ATTEND
I WON'T BE ATTENDING
NO RESPONSE
```

Intention is optional.

It does not constitute actual attendance.

---

# 37. Probable Attendance

Probable attendance is a planning concept.

Conceptually:

```text
EVENT
 │
 ├── Eligible Population
 │
 ├── Intention
 │
 └── Probable Attendance
          │
          ▼
      Planning View
```

Probable attendance is not the same as actual attendance.

---

# 38. Actual Attendance

Actual attendance is recorded separately:

```text
EVENT
   │
   ▼
ACTUAL ATTENDANCE
```

The actual attendance list is not limited to the probable attendance list.

A legitimate participant who did not previously indicate intention may still be recorded as present.

---

# 39. Seva Assignment Relationship

Seva is a separate operational domain.

Conceptually:

```text
SEVAK PARTICIPATION
        │
        │ 1 : N
        ▼
SEVA ASSIGNMENT
        │
        ▼
SEVA CATEGORY
```

A Sevak may have multiple Seva Assignments.

---

# 40. Seva Assignment Independence

Seva Assignment has its own lifecycle.

Therefore:

```text
SEVAK STATUS
     ≠
SEVA ASSIGNMENT STATUS
```

Example:

```text
Sevak = INACTIVE
Seva Assignment = ACTIVE
```

is valid while the assignment is under/after applicable review.

---

# 41. Seva Request and Approval

A Seva Assignment may originate from:

```text
SEVAK_REQUEST
```

or:

```text
SEVA_HEAD_RECOMMENDATION
```

Conceptually:

```text
SEVAK
  │
  ▼
SEVA REQUEST / RECOMMENDATION
  │
  ▼
SEVA APPROVAL
  │
  ▼
SEVA ASSIGNMENT
  │
  ▼
SEVA CATEGORY
```

The request/recommendation and final assignment are separate concepts.

---

# 42. Regular Sakha Seva

Regular Sakha Seva follows:

```text
SEVAK
  │
  ▼
SEVA CATEGORY
  │
  ▼
SEVA HEAD
  │
  ▼
SAKHA PRESIDENT
  │
  ▼
SEVA ASSIGNMENT
```

The detailed workflow is owned by:

```text
seva/01_seva_business_rules.md
```

---

# 43. UPBS Seva

UPBS Seva follows:

```text
SEVAK
  │
  ▼
UPBS SEVA CATEGORY
  │
  ▼
UPBS SEVA HEAD
  │
  ▼
KENDRA
  │
  ▼
PARICHALAK / PRESIDENT
  │
  ▼
UPBS SEVA ASSIGNMENT
```

The detailed workflow is owned by:

```text
seva/02_upbs_seva_rules.md
```

---

# 44. Multiple Seva Assignments

The conceptual relationship is:

```text
SEVAK PARTICIPATION
        │
        ├── SEVA ASSIGNMENT A
        ├── SEVA ASSIGNMENT B
        └── SEVA ASSIGNMENT C
```

Each assignment independently maintains:

* Category
* Origin
* Approval
* Status
* Effective date
* History

---

# 45. Seva and Inactivation

When Sevak becomes INACTIVE:

```text
SEVAK PARTICIPATION
        │
        ▼
INACTIVE
        │
        ▼
ACTIVE SEVA ASSIGNMENTS
        │
        ▼
REVIEW
```

The system does not automatically terminate every assignment.

Each assignment is independently reviewed.

---

# 46. Seva and Membership Transfer

Membership Transfer changes the person's current Sakha.

Conceptually:

```text
MEMBERSHIP TRANSFER
        │
        ▼
CURRENT SAKHA CHANGE
        │
        ├── SEVAK LIFECYCLE
        │
        └── SAKHA-SPECIFIC SEVA REVIEW
```

UPBS Seva follows its separate rules.

No independent Sevak Transfer relationship is created.

---

# 47. Gender Relationship

Gender is owned by Person.

The Sevak module uses Person gender for event eligibility.

Conceptually:

```text
PERSON
  │
  └── GENDER
        │
        ▼
SEVAK EVENT ELIGIBILITY
```

The male-only rule applies to Sevak Sangha event participation.

It does not automatically apply to Seva Assignment.

---

# 48. Seva Gender Independence

Seva Assignment may be performed by Male or Female NSS Members where permitted by the applicable Seva Category.

Therefore:

```text
PERSON.GENDER
      │
      ├── Sevak Sangha Event Eligibility
      │
      └── Seva Category Eligibility
```

These are independent rule evaluations.

---

# 49. Training Relationship

The module overview recognizes training as an organizational capability.

However, no mandatory training hierarchy is currently frozen.

Therefore the ERD does **not** require:

```text
SEVAK
   ↓
TRAINING PROGRAM
   ↓
TRAINING LEVEL
   ↓
CERTIFICATION
```

as a mandatory Sevak lifecycle relationship.

Any future training model shall be added only after its business rules are approved.

---

# 50. Governance Relationship

Sevak governance may use the common Governance module.

Conceptually:

```text
SEVAK
   │
   ▼
COMMON GOVERNANCE
   │
   ├── Body
   ├── Position
   └── Assignment
```

The exact Sevak executive structure remains pending.

The ERD therefore does not freeze Sevak-specific executive tables.

---

# 51. Core Conceptual ERD

The complete high-level relationship is:

```text
┌─────────────────┐
│     PERSON      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   MEMBERSHIP    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SANGHA SEVI    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   SEVAK PARTICIPATION   │
└───────┬───────┬─────────┘
        │       │
        │       ├───────────────────────────┐
        │       │                           │
        ▼       ▼                           ▼
┌────────────┐ ┌───────────────────┐ ┌─────────────────┐
│ SAKHA      │ │ STATUS HISTORY    │ │ REACTIVATION    │
│ ASSOCIATION│ │                   │ │ REVIEW          │
│ HISTORY    │ └───────────────────┘ └────────┬────────┘
└────────────┘                                │
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │  ATTENDANCE  │
                                      └──────────────┘

        SEVAK PARTICIPATION
                 │
                 ▼
        ┌───────────────────┐
        │ EVENT PARTICIP.   │
        └─────────┬─────────┘
                  │
        ┌─────────┼──────────────┐
        ▼         ▼              ▼
     EVENT     INTENTION     ATTENDANCE
        │
        ├── SAKHA SESSION
        │
        └── ANCHALIKA/ZILLA PUJA


        SEVAK PARTICIPATION
                 │
                 ▼
        ┌───────────────────┐
        │  SEVA ASSIGNMENT  │
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │   SEVA CATEGORY   │
        └───────────────────┘
```

---

# 52. Relationship Cardinalities

The conceptual cardinalities are:

| Relationship                                    |               Cardinality | Meaning                                     |
| ----------------------------------------------- | ------------------------: | ------------------------------------------- |
| Person → Membership                             |   Common Membership model | Membership-owned                            |
| Membership → Sangha Sevi                        |   Common Membership model | One authoritative Sangha Sevi identity      |
| Sangha Sevi → Sevak Participation               |       1 : 0..N historical | Sevak participation history                 |
| Sevak Participation → Sakha Association History |                     1 : N | Effective-dated Sakha history               |
| Sevak Participation → Status History            |                     1 : N | Lifecycle history                           |
| Sevak Participation → Reactivation Review       |                     1 : N | Historical review cycles                    |
| Sevak Participation → Event Participation       |                     1 : N | Event participation history                 |
| Event → Event Participation                     |                     1 : N | Participants                                |
| Event Participation → Attendance                |    0..1 applicable record | Actual attendance                           |
| Event Participation → Intention                 | 0..N historical responses | Planning intention                          |
| Sevak Participation → Seva Assignment           |                     1 : N | Multiple assignments permitted              |
| Seva Assignment → Seva Category                 |                     N : 1 | Category master                             |
| Sevak Participation → Governance Assignment     |                      0..N | Common Governance framework, pending detail |

---

# 53. Current Sakha Relationship

The authoritative relationship is:

```text
MEMBERSHIP
    │
    ▼
CURRENT SAKHA
    │
    ▼
SEVAK ASSOCIATION
```

The Sevak module must not create a competing independent current-Sakha field that can diverge from Membership.

Historical Sakha associations may be represented in Sevak-specific history where required for lifecycle/audit purposes.

---

# 54. Event Host Relationship

Every current Sevak event requires a registered Sakha as host.

Conceptually:

```text
SAKHA
  │
  │ hosts
  ▼
EVENT
```

For Anchalika/Zilla events:

```text
ANCHALIKA / ZILLA
       │
       ▼
EVENT
       │
       ▼
HOST SAKHA
```

The host Sakha's registered location is used.

The event retains a location snapshot for historical integrity.

---

# 55. Event Organizational Relationship

Event organizational scope is separate from host identity.

Example:

```text
Event Scope:
ANCHALIKA A

Host:
Sakha B

Participant:
Sakha C
```

The host Sakha does not become the participant's Sakha.

The participant's organizational identity remains determined by Membership.

---

# 56. No Cross-Sakha Local Participation Relationship

The ERD shall not contain:

```text
Sakha A Member
       │
       ▼
Sakha B Sevak Membership
```

for ordinary local Sakha sessions.

A local session participant remains associated with their authoritative organizational identity.

---

# 57. Cross-Anchalika/Zilla Event Relationship

For permitted larger events:

```text
Participant's Organization
          │
          ▼
Event Participation
          │
          ▼
Host Event
```

The participant's original organization remains unchanged.

This is an event relationship, not an organization-transfer relationship.

---

# 58. Audit Relationship

All Sevak lifecycle and operational entities require auditability.

Conceptually:

```text
BUSINESS ENTITY
      │
      ▼
AUDIT INFORMATION
```

The exact audit implementation follows the common NSS ERP Audit Standards.

The ERD does not duplicate a separate audit table for every entity.

---

# 59. History Principle

Historical relationships must be preserved.

This applies to:

* Sevak participation
* Status
* Sakha association
* Reactivation reviews
* Event participation
* Attendance
* Seva assignments
* Approvals

The ERD must therefore support historical records rather than only current-state snapshots.

---

# 60. No Physical Deletion

The conceptual model assumes:

```text
Historical Record
       ↓
Preserved
```

rather than:

```text
Historical Record
       ↓
DELETE
```

Inactivation, completion or ending represents lifecycle state rather than physical deletion.

---

# 61. ERD Boundary — Training

The old proposed model included:

```text
sevak_training_program
sevak_training_attendance
sevak_orientation_batch
```

However, current Sevak rules explicitly state that no formal mandatory training hierarchy is frozen and previously proposed training tables are not frozen.

Therefore these are **not included as mandatory core ERD entities at this stage**.

If training becomes a formally defined module capability later, it may be added through an approved ERD revision.

---

# 62. ERD Boundary — Activity

The old proposed model included:

```text
sevak_activity
sevak_activity_participant
```

The current architecture instead distinguishes:

```text
Sakha Sevak Sangha Session
Anchalika/Zilla Sevak Sangha Puja
Other Future Events
Seva
```

These have now been separated into dedicated business-rule documents.

Therefore a generic `Sevak Activity` entity is not frozen as the master operational abstraction.

---

# 63. ERD Boundary — Seva

Seva Assignment is shown as a relationship because the Sevak module participates in the Seva domain.

The detailed physical model belongs to the Seva module.

The Sevak ERD therefore does not duplicate the full Seva schema.

---

# 64. ERD Boundary — UPBS

UPBS Seva is shown as a specialized Seva relationship.

The UPBS-specific physical entities belong to the UPBS/Seva design.

The Sevak ERD only represents the relationship:

```text
Sevak
   ↓
UPBS Seva Assignment
```

---

# 65. ERD Boundary — Attendance

Attendance is a common ERP capability.

The Sevak module supplies:

```text
Event
Participant
Sevak Status
```

to the Attendance process.

The Sevak module does not create a separate attendance architecture for every Sevak event.

---

# 66. ERD Boundary — Governance

Governance is a common ERP capability.

The Sevak module may reference:

```text
Body
Position
Assignment
```

through the common Governance framework.

The Sevak-specific executive structure remains pending.

---

# 67. ERD Boundary — RBAC

RBAC belongs to Administration.

The Sevak module does not create:

```text
Sevak Admin Role
Sevak Permission Table
```

as a separate authorization system.

The module uses centralized RBAC.

---

# 68. Conceptual Lifecycle ERD

```text
PERSON
   │
   ▼
MEMBERSHIP
   │
   ▼
SANGHA SEVI
   │
   ▼
SEVAK PARTICIPATION
   │
   ├── ACTIVE
   │
   └── INACTIVE
         │
         ▼
   REACTIVATION REVIEW
         │
       ┌─┴─┐
       ▼   ▼
    ACTIVE INACTIVE
```

Transfer enters through:

```text
MEMBERSHIP TRANSFER
        │
        ▼
CURRENT SAKHA CHANGE
        │
        ▼
SEVAK LIFECYCLE
```

Death enters through:

```text
PERSON / MEMBERSHIP DEATH
        │
        ▼
DECEASED
        │
        ▼
SEVAK INACTIVE
```

---

# 69. Conceptual Participation ERD

```text
SEVAK PARTICIPATION
        │
        ▼
EVENT PARTICIPATION
        │
   ┌────┼────┐
   ▼    ▼    ▼
INTENTION  PROBABLE  ATTENDANCE
                    │
                    ▼
             REACTIVATION REVIEW
             (if INACTIVE Sevak)
```

Eligibility is calculated separately.

---

# 70. Conceptual Seva ERD

```text
SEVAK PARTICIPATION
        │
        ▼
SEVA REQUEST / RECOMMENDATION
        │
        ▼
APPROVAL
        │
        ▼
SEVA ASSIGNMENT
        │
        ▼
SEVA CATEGORY
```

Multiple assignments are permitted.

---

# 71. Conceptual Organizational ERD

```text
ORGANIZATION
     │
     ├── ANCHALIKA
     │      │
     │      └── ZILLA
     │             │
     │             └── SAKHA
     │
     └── KENDRA
```

The exact organization hierarchy belongs to the Organization module.

The Sevak module consumes the authoritative organizational relationships.

---

# 72. Complete Domain Map

```text
                         ┌───────────────┐
                         │    PERSON     │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │   MEMBERSHIP  │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  SANGHA SEVI  │
                         └───────┬───────┘
                                 │
                                 ▼
                  ┌──────────────────────────┐
                  │    SEVAK PARTICIPATION   │
                  └────────────┬─────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
     SAKHA HISTORY       STATUS HISTORY     REACTIVATION
                                               REVIEW
            │
            │
            └───────────────────────────────────────┐
                                                    │
                                                    ▼
                                           EVENT PARTICIPATION
                                                    │
                              ┌─────────────────────┼──────────────┐
                              │                     │              │
                              ▼                     ▼              ▼
                         INTENTION             ATTENDANCE      PROBABLE
                                                                  │
                                                                  ▼
                                                         REACTIVATION
                                                            REVIEW


                  SEVAK PARTICIPATION
                           │
                           ▼
                    SEVA ASSIGNMENT
                           │
                           ▼
                     SEVA CATEGORY
```

---

# 73. Entity Ownership Summary

| Entity / Concept          | Owner                      | Sevak Relationship            |
| ------------------------- | -------------------------- | ----------------------------- |
| Person                    | Person Module              | Identity                      |
| Membership                | Membership Module          | Mandatory prerequisite        |
| Sangha Sevi ID            | Membership Module          | Authoritative identity        |
| Organization              | Organization Module        | Sakha/Anchalika/Zilla context |
| Sevak Participation       | Sevak Module               | Core Sevak entity             |
| Sakha Association History | Sevak/Membership lifecycle | Historical Sevak association  |
| Status History            | Sevak Module               | Lifecycle history             |
| Reactivation Review       | Sevak Module               | INACTIVE attendance review    |
| Event                     | Common Event framework     | Sevak event                   |
| Event Participation       | Event/Attendance framework | Sevak participant             |
| Attendance                | Attendance framework       | Actual participation          |
| Seva Category             | Seva module                | Assignment category           |
| Seva Assignment           | Seva module                | Sevak assignment              |
| UPBS Seva                 | UPBS/Seva                  | Specialized assignment        |
| Governance                | Governance module          | Optional future relationship  |
| RBAC                      | Administration             | Authorization                 |
| Audit                     | Common Audit framework     | Cross-module history          |

---

# 74. ERD Design Rules

The following rules govern the conceptual ERD:

1. Person remains the authoritative identity.
2. Membership remains the authoritative membership relationship.
3. Sangha Sevi ID remains the authoritative NSS identity.
4. Sevak is an additional participation layer.
5. No separate Sevak identity is created.
6. Current Sakha follows Membership.
7. Sakha history is preserved.
8. Transfer is initiated by Membership lifecycle.
9. Death is initiated by Person/Membership lifecycle.
10. Sevak status is ACTIVE or INACTIVE.
11. Status history is preserved.
12. INACTIVE attendance may create reactivation review.
13. Attendance does not directly update Sevak status.
14. Events are separate from Sevak lifecycle.
15. Local Sakha participation does not create cross-Sakha Sevak participation.
16. Anchalika/Zilla events may support cross-Anchalika/Zilla participation.
17. Seva Assignment is separate from Sevak status.
18. Multiple Seva Assignments are supported.
19. Training is not a mandatory core ERD dependency.
20. Governance uses the common Governance framework.
21. RBAC uses the common Administration framework.
22. Historical records are preserved.
23. Physical deletion of historical business records is prohibited.

---

# 75. Physical Schema Boundary

This ERD does not freeze:

* PostgreSQL table names
* Primary key names
* Foreign key names
* Indexes
* Constraints
* Enumerated types
* Trigger implementation
* Partitioning
* Exact audit-table implementation

Those decisions belong to:

```text
06_sevak_table_design.md
```

---

# 76. Step 11 Dependency

The final table design must be derived from:

```text
01_sevak_module_overview.md
03_sevak_lifecycle.md
04_sevak_participation_rules.md
05_sevak_business_rules.md
sangha/01_sakha_sevak_sangha_session_rules.md
sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md
seva/01_seva_business_rules.md
seva/02_upbs_seva_rules.md
events/01_other_sevak_event_rules.md
```

The table design must not simply copy the old proposed table list.

---

# 77. Deprecated / Not-Frozen Old Entities

The following old proposed entities are **not automatically carried into the final schema**:

```text
sevak_training_program
sevak_training_attendance
sevak_orientation_batch
sevak_activity
sevak_activity_participant
```

They were previously proposed in the working table design, but the current rules do not freeze them as mandatory core entities. 

Likewise, the generic:

```text
sevak_sangha
```

entity requires final validation against the Organization model before being frozen physically.

---

# 78. ERD Freeze Status

### Frozen

```text
Person relationship
Membership relationship
Sangha Sevi relationship
Sevak Participation concept
ACTIVE / INACTIVE lifecycle
Sakha association history
Transfer relationship
Death relationship
Reactivation Review
Event participation relationship
Attendance relationship
Seva Assignment relationship
Multiple Seva Assignments
Centralized Governance relationship
Centralized RBAC relationship
```

### Not Yet Frozen

```text
Exact PostgreSQL table structure
Exact PK/FK naming
Training schema
Certification schema
Detailed Sevak governance schema
Exact Sevak Sangha physical organization table
Detailed Event physical schema
Detailed Seva physical schema
```

---

# 79. Related Documents

```text
01_sevak_module_overview.md

03_sevak_lifecycle.md

04_sevak_participation_rules.md

05_sevak_business_rules.md

06_sevak_table_design.md

sangha/
├── 01_sakha_sevak_sangha_session_rules.md
└── 02_anchalika_zilla_sevak_sangha_puja_rules.md

seva/
├── 01_seva_business_rules.md
└── 02_upbs_seva_rules.md

events/
└── 01_other_sevak_event_rules.md
```

Related modules:

```text
Person
Membership
Organization
Attendance
Governance
Administration
Seva
UPBS
Reports
```

---

# End of Document
