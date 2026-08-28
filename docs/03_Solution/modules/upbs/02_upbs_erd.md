# NSS ERP — UPBS Entity Relationship Design

**Document ID:** SOL-UPBS-002
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Utkala Pradeshika Bhakta Sammilani (UPBS)
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical Entity Relationship Design (ERD) for the
current UPBS foundation.

The ERD represents the relationships among the seven currently identified
UPBS foundation tables:

    upbs_event
    upbs_registration
    delegate_card
    prasad_patra
    accommodation_allocation
    camp_master
    guest_reference

The current source identifies these seven tables as the frozen UPBS
registration foundation.

---

# 2. ERD Scope

The current ERD covers:

```text
UPBS Event
    ↓
UPBS Registration
    ├── Delegate Card
    ├── Prasad Patra
    ├── Accommodation
    └── Guest Reference
              │
              ▼
          Camp Master
```

---

# 3. Current UPBS Tables

```text
1. upbs_event
2. upbs_registration
3. delegate_card
4. prasad_patra
5. accommodation_allocation
6. camp_master
7. guest_reference
```

Current foundation count:

```text
7 tables
```

This table set is explicitly identified in the project schema review.

---

# 4. High-Level ERD

```text
                         ┌─────────────────┐
                         │    upbs_event   │
                         └────────┬────────┘
                                  │
                                  │ 1 : N
                                  ▼
                     ┌────────────────────────┐
                     │   upbs_registration    │
                     └───────┬──────┬─────┬───┘
                             │      │     │
                   ┌─────────┘      │     └──────────┐
                   │                │                │
                   ▼                ▼                ▼
          ┌────────────────┐ ┌───────────────┐ ┌────────────────────┐
          │  delegate_card │ │ prasad_patra  │ │ accommodation_     │
          │                │ │               │ │ allocation          │
          └────────────────┘ └───────────────┘ └─────────┬──────────┘
                                                         │
                                                         │ N : 1
                                                         ▼
                                                ┌────────────────┐
                                                │   camp_master  │
                                                └────────────────┘

                     ┌────────────────────┐
                     │   guest_reference  │
                     └─────────┬──────────┘
                               │
                               │ references
                               ▼
                         NSS Person /
                       Sangha Sevi identity
```

The exact cardinalities of optional relationships shall be confirmed in
the detailed table-design document where the source has not frozen them.

---

# 5. `upbs_event`

## Purpose

`upbs_event` represents a UPBS event instance.

It is the event-level parent for UPBS registrations.

Conceptually:

```text
UPBS Event
    │
    └── Registrations
```

---

# 6. UPBS Event Relationship

```text
upbs_event
     │
     │ 1 : N
     ▼
upbs_registration
```

One UPBS event can have many registrations.

A registration belongs to a specific UPBS event.

---

# 7. UPBS Event Sessions

The existing project master-data design recognizes:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

as UPBS event sessions.

The detailed representation of sessions within `upbs_event` is to be
confirmed by the table-design document.

---

# 8. Event Lifecycle Boundary

The ERD does not introduce separate tables for:

```text
Adhibasa
Day 1
Day 2
Day 3
```

The existing UPBS event foundation owns the event structure.

---

# 9. `upbs_registration`

## Purpose

`upbs_registration` represents a person's participation/registration for a
specific UPBS event.

It is the central transactional entity in the current UPBS foundation.

---

# 10. Registration Relationship to Event

```text
upbs_event
     │
     │ 1 : N
     ▼
upbs_registration
```

Conceptually:

```text
One Event
    ↓
Many Registrations
```

---

# 11. Registration and NSS Identity

UPBS registration does not replace the NSS identity model.

Where the registrant is an NSS member, the registration references the
existing NSS person/member identity.

Conceptually:

```text
Person / Sangha Sevi
          │
          ▼
   UPBS Registration
```

The UPBS Module shall not create a second permanent membership identity.

---

# 12. Registration and Participation Package

The existing UPBS foundation supports participation concepts including:

```text
Delegate Package
Prasad Only
```

The exact physical representation of registration type belongs to the
frozen registration table design.

---

# 13. Delegate Card

`delegate_card` represents the Delegate Card associated with a UPBS
delegate registration.

Conceptually:

```text
upbs_registration
        │
        │ 1 : 0..1
        ▼
delegate_card
```

The exact cardinality must follow the finalized Delegate Card rule.

---

# 14. Delegate Package Relationship

The existing business model establishes:

```text
Delegate Package
      =
Delegate Card
+
Prasad Patra
```

Therefore:

```text
upbs_registration
        │
        ├────────► delegate_card
        │
        └────────► prasad_patra
```

---

# 15. Delegate Card Purpose

The Delegate Card provides identification during UPBS.

At UPBS entrances, the Delegate Card is shown to Security for verification.

This operational rule is frozen in the current UPBS foundation.

---

# 16. Prasad Patra

`prasad_patra` represents the Prasad Patra associated with the relevant
UPBS registration.

Conceptually:

```text
upbs_registration
        │
        │ 1 : 0..1
        ▼
prasad_patra
```

The exact cardinality depends on the finalized registration/package rules.

---

# 17. Prasad Only

The current business model supports:

```text
Prasad Only
```

Therefore a registration may involve Prasad participation without being a
Delegate Package.

The ERD must preserve this distinction.

---

# 18. Delegate Only

The current rule states:

```text
Delegate Only
=
Not Allowed
```

A Delegate Package includes Prasad Patra.

Therefore the ERD must not model Delegate Card as an independently purchasable
package detached from the required Prasad relationship.

---

# 19. Accommodation Allocation

`accommodation_allocation` represents accommodation assigned to a UPBS
registration.

Conceptually:

```text
upbs_registration
        │
        │ 1 : N / 0..N
        ▼
accommodation_allocation
```

The final cardinality depends on the detailed accommodation rules.

---

# 20. Camp Master

`camp_master` represents the defined UPBS accommodation camps.

Conceptually:

```text
camp_master
     │
     │ 1 : N
     ▼
accommodation_allocation
```

One camp may have multiple accommodation allocations.

---

# 21. Accommodation Relationship

The logical relationship is:

```text
upbs_registration
        │
        ▼
accommodation_allocation
        │
        ▼
camp_master
```

This provides the chain:

```text
Participant
    ↓
Registration
    ↓
Accommodation Allocation
    ↓
Camp
```

---

# 22. Guest Reference

`guest_reference` represents the UPBS guest/reference relationship.

The existing UPBS rules require a reference Sangha Sevi for guest
management.

Conceptually:

```text
UPBS Registration / Guest
          │
          ▼
   guest_reference
          │
          ▼
Reference Sangha Sevi
```

The exact FK structure shall follow the detailed table design.

---

# 23. Reference Sangha Sevi

The reference person shall use the authoritative NSS Sangha Sevi identity.

The UPBS Module must not create a separate permanent person/member identity
for the reference person.

---

# 24. Person / Membership Foundation

The UPBS ERD therefore integrates with the common NSS identity foundation.

Conceptually:

```text
person
   │
   ▼
membership / sangha_sevi
   │
   ├──────────────┐
   │              │
   ▼              ▼
UPBS Registration  Guest Reference
```

The exact existing table names and FK columns are owned by the Foundation
and Membership designs.

---

# 25. Complete Logical Relationship

```text
                         NSS PERSON / MEMBER
                                  │
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  UPBS EVENT       │
                         └────────┬─────────┘
                                  │
                                  │ 1:N
                                  ▼
                         ┌──────────────────┐
                         │ UPBS REGISTRATION│
                         └───┬────┬────┬────┘
                             │    │    │
                     ┌───────┘    │    └──────────────┐
                     │            │                   │
                     ▼            ▼                   ▼
              ┌────────────┐ ┌────────────┐  ┌──────────────────┐
              │ DELEGATE   │ │ PRASAD     │  │ ACCOMMODATION    │
              │ CARD       │ │ PATRA      │  │ ALLOCATION       │
              └────────────┘ └────────────┘  └────────┬─────────┘
                                                       │
                                                       │
                                                       ▼
                                                ┌─────────────┐
                                                │ CAMP MASTER │
                                                └─────────────┘

                         GUEST REFERENCE
                               │
                               ▼
                     REFERENCE SANGHA SEVI
```

---

# 26. Relationship Summary

| Parent                  | Child                      | Logical Relationship                      |
| ----------------------- | -------------------------- | ----------------------------------------- |
| `upbs_event`            | `upbs_registration`        | 1:N                                       |
| `upbs_registration`     | `delegate_card`            | 1:0..1, subject to final rule             |
| `upbs_registration`     | `prasad_patra`             | 1:0..1, subject to package rule           |
| `upbs_registration`     | `accommodation_allocation` | 1:N / 0..N, subject to accommodation rule |
| `camp_master`           | `accommodation_allocation` | 1:N                                       |
| UPBS registration/guest | `guest_reference`          | Reference relationship                    |
| `guest_reference`       | Sangha Sevi                | References existing NSS identity          |

---

# 27. No Duplicate Event Tables

The ERD does not create:

```text
upbs_adhibasa
upbs_day1
upbs_day2
upbs_day3
```

The current foundation uses the UPBS event/session model.

---

# 28. No Duplicate Person Table

The UPBS Module does not create:

```text
upbs_person
```

Existing NSS Person/Member identity is reused.

---

# 29. No Duplicate Member Identity

The UPBS Module does not create:

```text
upbs_member_id
```

The authoritative NSS identity remains the existing Sangha Sevi/member
identity.

---

# 30. No Duplicate Camp Allocation

Accommodation assignment is represented through:

```text
accommodation_allocation
```

It is not duplicated inside `upbs_registration`.

---

# 31. No Duplicate Camp Master

All defined UPBS camps are represented through:

```text
camp_master
```

Accommodation allocations reference the camp.

---

# 32. Event Session Model

The existing master-data foundation recognizes:

```text
event_session

ADHIBASA
DAY_1
DAY_2
DAY_3
```

The session concept should be reused rather than creating separate physical
tables for each day.

---

# 33. Meal Model

The project master-data design identifies:

```text
meal_type

BREAKFAST
LUNCH
DINNER
```

The current seven-table UPBS foundation does not include a separate frozen
meal-scan table in the identified table set.

Therefore the detailed QR meal-tracking schema is intentionally not invented
in this ERD.

---

# 34. QR Meal Tracking Boundary

The operational requirement supports QR-based meal tracking.

However, the current frozen seven-table foundation does not establish a
separate physical meal-scan entity.

Therefore:

```text
QR Meal Tracking
=
Functional Requirement

not yet:
=
Additional Frozen Table
```

A future detailed UPBS operational design may introduce the required entity
after the business rules are finalized.

---

# 35. Committee Boundary

UPBS Committee Management is part of the broader functional scope.

However, the current seven-table frozen UPBS foundation does not include a
dedicated:

```text
upbs_committee
```

table.

The common Unified Body Governance Model should be reused for committee
management where applicable.

---

# 36. Volunteer Boundary

UPBS Volunteer Structure is not yet fully frozen.

The current ERD therefore does not introduce a final volunteer table set.

The existing Sevak/Seva framework may provide the identity and participation
foundation where applicable.

---

# 37. Day 1 / Day 2 / Day 3 Boundary

The project source explicitly identifies UPBS Day 1, Day 2, and Day 3
operations as not yet frozen.

Therefore this ERD does not invent additional operational tables for those
days.

---

# 38. Historical Integrity

UPBS records shall preserve historical event participation.

The general NSS architecture follows:

```text
History Never Deleted
```

Therefore completed UPBS records should remain historically traceable.

---

# 39. Event Independence

Each UPBS event is independently identifiable.

A person's registration in one UPBS event does not become their registration
for another UPBS event.

Conceptually:

```text
Person
  │
  ├── UPBS Event 2025
  │      └── Registration
  │
  └── UPBS Event 2026
         └── Registration
```

---

# 40. Registration Independence

A registration belongs to one event.

A person may have registrations for multiple UPBS events over time, subject
to applicable registration rules.

---

# 41. Delegate Card History

Delegate Cards belong to the relevant UPBS registration/event context.

A Delegate Card from one UPBS event must not automatically become the Delegate
Card for a future event.

---

# 42. Accommodation History

Accommodation allocation is event-specific.

Historical accommodation allocation should remain associated with its UPBS
registration/event context.

---

# 43. Guest Reference History

Guest-reference information should remain historically associated with the
relevant UPBS participation.

Changing a reference for a future event must not rewrite historical event
records.

---

# 44. Referential Integrity

The physical PostgreSQL implementation shall enforce valid relationships
between the UPBS foundation tables.

Exact:

```text
Foreign Keys
ON DELETE rules
ON UPDATE rules
Indexes
Unique constraints
```

will be defined in the table-design/SQL stage.

---

# 45. Cardinality Caution

Where the current source does not explicitly freeze cardinality, this ERD
uses:

```text
0..1
0..N
N
```

only as a logical working representation.

The final physical cardinality shall be determined from approved UPBS
business rules.

---

# 46. Current Frozen Foundation

```text
                 UPBS FOUNDATION
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      UPBS EVENT   REGISTRATION   SUPPORT
                                   ARTIFACTS
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                    DELEGATE       PRASAD     ACCOMMODATION
                      CARD          PATRA       ALLOCATION
                                                    │
                                                    ▼
                                                  CAMP
```

---

# 47. Logical Data Flow

```text
NSS Person / Member
        │
        ▼
UPBS Event
        │
        ▼
UPBS Registration
        │
        ├── Delegate Card
        │
        ├── Prasad Patra
        │
        ├── Accommodation Allocation
        │          │
        │          ▼
        │      Camp Master
        │
        └── Guest Reference
```

---

# 48. Current Table Count

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference

Total = 7
```

---

# 49. ERD Freeze Boundary

The following are currently represented:

```text
✓ Event
✓ Registration
✓ Delegate Card
✓ Prasad Patra
✓ Accommodation
✓ Camp
✓ Guest Reference
```

The following require further operational design:

```text
○ Day 1 operations
○ Day 2 operations
○ Day 3 operations
○ Detailed volunteer structure
○ Detailed QR meal-scan persistence
○ Detailed committee structure
```

---

# 50. Architectural Principle

The UPBS ERD follows:

```text
Existing NSS Identity
        ↓
UPBS Event
        ↓
UPBS Registration
        ↓
Participation Artifacts
        ↓
Accommodation / Guest Support
```

No duplicate NSS identity or governance architecture is introduced.

---

# 51. Source Alignment

The current schema review explicitly identifies the seven UPBS foundation
tables:

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

and identifies the UPBS Registration Foundation as a frozen area.

The master-data source identifies:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

as event sessions and:

```text
BREAKFAST
LUNCH
DINNER
```

as meal types.

The source also explicitly identifies UPBS Day 1/2/3 operations and Volunteer
Structure as not yet frozen.

---

# 52. Status

DOCUMENT STATUS:

```
DRAFT — SOURCE ALIGNED
```

VERSION:

```
1.0.0
```

---

# End of Document
