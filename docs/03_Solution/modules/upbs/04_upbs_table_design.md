# NSS ERP — UPBS Table Design

**Document ID:** SOL-UPBS-004  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Utkala Pradeshika Bhakta Sammilani (UPBS)  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the database table-design baseline for the currently
frozen UPBS Registration Foundation.

The current UPBS foundation contains seven tables:

    upbs_event
    upbs_registration
    delegate_card
    prasad_patra
    accommodation_allocation
    camp_master
    guest_reference

The project schema review explicitly identifies these seven tables as the
current UPBS foundation.

---

# 2. Design Status

The UPBS table set is frozen at:

    7 tables

However, this document distinguishes between:

    Confirmed Table Identity
    Confirmed Architectural Relationship
    Standard Database Conventions
    Column-Level Details Requiring Final Confirmation

No unsupported column or business rule shall be treated as frozen merely
because it appears in an implementation example.

---

# 3. Current UPBS Tables

| # | Table | Purpose |
|---:|---|---|
| 1 | `upbs_event` | UPBS event |
| 2 | `upbs_registration` | Participant registration |
| 3 | `delegate_card` | Delegate identification |
| 4 | `prasad_patra` | Prasad participation artifact |
| 5 | `accommodation_allocation` | Accommodation assignment |
| 6 | `camp_master` | UPBS camp master |
| 7 | `guest_reference` | Guest/reference Sangha Sevi relationship |

---

# 4. Database Naming Standards

The UPBS tables shall follow the NSS-wide database naming standards.

## Primary Key

Primary keys use:

    <table_name>_pk

Examples:

    upbs_event_pk
    upbs_registration_pk
    delegate_card_pk

---

## Foreign Keys

Foreign keys shall reference the target table's primary key.

Example:

    upbs_event_pk

rather than using a business identifier as the FK.

The project-wide standard explicitly requires FKs to reference PKs.

---

# 5. Business Identifiers

Where a UPBS entity requires a human-readable business identifier, it shall
be separate from its UUID primary key.

Conceptually:

    <entity>_pk
        =
    technical primary key

    <entity>_id
        =
    business identifier

Business identifiers shall follow the project's naming standards.

---

# 6. Audit Standard

UPBS transactional tables shall follow the common NSS audit convention.

Where applicable:

    created_at
    created_by_sangha_sevi_pk

    updated_at
    updated_by_sangha_sevi_pk

    deleted_at
    deleted_by_sangha_sevi_pk

    is_active

The project source establishes this audit/soft-delete convention for major
transactional tables.

---

# 7. Soft Delete

Historical UPBS records shall not normally be physically deleted.

The common NSS principle is:

    History Never Deleted

Where a record must be withdrawn from normal operational use, the standard
soft-delete mechanism shall be used where appropriate.

---

# 8. `upbs_event`

## Purpose

Represents one UPBS event occurrence.

---

## Confirmed Identity

Table:

    upbs_event

Primary key:

    upbs_event_pk

---

## Logical Role

```text
upbs_event
    │
    └── upbs_registration
```

One UPBS event may have many registrations.

---

## Event Information

The event entity must be capable of representing the UPBS event identity and
event lifecycle.

The established event/session concepts include:

```
ADHIBASA
DAY_1
DAY_2
DAY_3
```

---

## Column Status

The following concepts are required by the source:

| Concept                   | Status            |
| ------------------------- | ----------------- |
| Event PK                  | CONFIRMED         |
| Event identity            | CONFIRMED         |
| Event/session association | CONFIRMED CONCEPT |
| Event date/time           | REQUIRED CONCEPT  |
| Event status              | REQUIRED CONCEPT  |
| Audit fields              | NSS STANDARD      |
| Exact column names/types  | FINAL SQL DESIGN  |

The exact physical column set is not frozen by the available source and shall
not be invented here.

---

# 9. `upbs_registration`

## Purpose

Represents participation/registration for a specific UPBS event.

---

## Confirmed Identity

Table:

```
upbs_registration
```

Primary key:

```
upbs_registration_pk
```

---

## Event Relationship

The registration belongs to:

```
upbs_event
```

Logical FK:

```
upbs_event_pk
```

Relationship:

```
upbs_event 1:N upbs_registration
```

---

## Participant Relationship

Where the participant is already represented in the NSS identity model,
the registration shall reference the existing person/member identity.

UPBS shall not create a duplicate person or Sangha Sevi identity.

---

## Registration Type

The current business rules establish:

```
DELEGATE PACKAGE
PRASAD ONLY
```

and prohibit:

```
DELEGATE ONLY
```

The physical representation of this classification must use the approved
master-data architecture rather than hard-coded UI-only values.

---

## Registration Information

The registration entity is expected to retain sufficient information for:

```
Event
Participant
Registration
Registration Type
Registration Status
Registration Timing
Audit
```

The exact physical column names/types require final SQL confirmation.

---

# 10. Registration Timing

The business rules explicitly allow:

```
Registration Before UPBS
Registration During UPBS
```

Therefore the registration model shall be capable of recording the
registration date/time.

---

# 11. Registration Identity

The registration shall have its own permanent technical identity:

```
upbs_registration_pk
```

and, where required, a separate business registration identifier.

The registration identifier is not:

```
Sangha Sevi ID
```

---

# 12. `delegate_card`

## Purpose

Represents the Delegate Card issued/associated with a Delegate Package.

---

## Confirmed Identity

Table:

```
delegate_card
```

Primary key:

```
delegate_card_pk
```

---

## Registration Relationship

Logical relationship:

```
upbs_registration
    │
    ▼
delegate_card
```

A Delegate Card belongs to the relevant UPBS participation context.

---

## Delegate Card Requirements

The entity must support:

```
Delegate identification
Event-specific association
Registration association
Card identification
Operational verification
```

The exact physical fields require final confirmation.

---

# 13. Delegate Card Is Event-Specific

A Delegate Card shall remain associated with its relevant UPBS event/
registration.

It shall not become the permanent NSS identity of the participant.

---

# 14. Delegate Card Verification

The Delegate Card is used for operational identification and security
verification at UPBS.

The database design shall therefore provide a reliable way to locate the
corresponding registration.

---

# 15. `prasad_patra`

## Purpose

Represents the Prasad Patra associated with a UPBS registration.

---

## Confirmed Identity

Table:

```
prasad_patra
```

Primary key:

```
prasad_patra_pk
```

---

## Registration Relationship

Logical relationship:

```
upbs_registration
    │
    ▼
prasad_patra
```

---

# 16. Prasad Package Relationship

The business rule is:

```
Delegate Package
    =
Delegate Card
    +
Prasad Patra
```

Therefore the physical design must preserve the relationship between the
Prasad Patra and the relevant registration.

---

# 17. Prasad Only

A Prasad Patra may exist for a:

```
PRASAD ONLY
```

registration.

Therefore Prasad participation shall not be implemented as a property
that exists only for Delegate Cards.

---

# 18. `accommodation_allocation`

## Purpose

Represents accommodation assigned to UPBS participation.

---

## Confirmed Identity

Table:

```
accommodation_allocation
```

Primary key:

```
accommodation_allocation_pk
```

---

## Registration Relationship

Logical relationship:

```
upbs_registration
    │
    ▼
accommodation_allocation
```

---

## Camp Relationship

Accommodation allocation references:

```
camp_master
```

Logical relationship:

```
camp_master
    │
    ▼
accommodation_allocation
```

---

# 19. Accommodation Information

The accommodation model must be capable of representing:

```
Registration / Participant
Camp
Allocation
Relevant event context
Allocation status
Audit
```

Exact room/bed/capacity fields are not frozen in the current source.

---

# 20. Accommodation Rules Not Yet Frozen

The current source does not establish a final physical model for:

```
Room
Bed
Block
Building
Capacity
Check-in
Check-out
Reallocation
```

Therefore these shall not be introduced as frozen tables or columns by
UPBS-004.

---

# 21. `camp_master`

## Purpose

Represents a defined UPBS accommodation camp.

---

## Confirmed Identity

Table:

```
camp_master
```

Primary key:

```
camp_master_pk
```

---

## Camp Master Role

Camp Master is master data.

It is referenced by accommodation allocation.

---

## Logical Relationship

```text
camp_master
     │
     │ 1:N
     ▼
accommodation_allocation
```

---

# 22. Camp Master Information

The camp master should provide the identity of the UPBS camp and the
information required for accommodation allocation.

Exact fields such as:

```
Camp Code
Camp Name
Location
Capacity
Gender
Status
```

shall only be frozen after the detailed accommodation rules are confirmed.

---

# 23. Camp Is Master Data

Camp definitions shall be maintained as configurable master data.

The system should not hard-code camp names in application code.

---

# 24. `guest_reference`

## Purpose

Represents the reference relationship for a UPBS guest.

---

## Confirmed Identity

Table:

```
guest_reference
```

Primary key:

```
guest_reference_pk
```

---

# 25. Reference Sangha Sevi

The business rule requires:

```
Reference Sangha Sevi
```

for guest management.

The reference must use the existing NSS Sangha Sevi/member identity.

---

# 26. Guest Reference Relationship

Conceptually:

```text
UPBS Guest / Registration
          │
          ▼
guest_reference
          │
          ▼
Existing Sangha Sevi
```

The exact physical FK structure requires final confirmation against the
existing Person/Membership schema.

---

# 27. No Duplicate Person

The following table shall NOT be created:

```
upbs_person
```

Guest identity must reuse the existing NSS Person foundation.

---

# 28. No Duplicate Member

The following shall NOT be created:

```
upbs_member
```

UPBS shall reference the authoritative NSS membership identity.

---

# 29. Relationship Matrix

| Table                      | Related Entity      | Relationship                     |
| -------------------------- | ------------------- | -------------------------------- |
| `upbs_registration`        | `upbs_event`        | N:1                              |
| `delegate_card`            | `upbs_registration` | Event participation relationship |
| `prasad_patra`             | `upbs_registration` | Event participation relationship |
| `accommodation_allocation` | `upbs_registration` | Allocation relationship          |
| `accommodation_allocation` | `camp_master`       | N:1                              |
| `guest_reference`          | NSS Sangha Sevi     | Reference relationship           |

---

# 30. Registration-Centric Model

The current UPBS foundation is registration-centric:

```text
                     upbs_event
                         │
                         ▼
                upbs_registration
                         │
            ┌────────────┼────────────┐
            │            │            │
            ▼            ▼            ▼
      delegate_card  prasad_patra  accommodation
                                      │
                                      ▼
                                  camp_master

                    guest_reference
                           │
                           ▼
                    Sangha Sevi
```

---

# 31. Participation Package Integrity

The database/application design shall preserve:

```text
DELEGATE PACKAGE
    ├── Delegate Card
    └── Prasad Patra

PRASAD ONLY
    └── Prasad Patra

DELEGATE ONLY
    └── PROHIBITED
```

---

# 32. Registration Status

A registration lifecycle/status is required for operational management.

The exact status values are not frozen in the available source.

Therefore values such as:

```
DRAFT
CONFIRMED
CANCELLED
```

shall not be declared final by this document.

They require confirmation in the detailed functional/business design.

---

# 33. Event Status

Similarly, UPBS event lifecycle is required, but the exact database status
enumeration is not frozen in the source available for this document.

Do not hard-code an assumed status list.

---

# 34. Master Data Principle

Where the project has an approved master-data architecture, configurable
values shall be stored in master data rather than hard-coded.

This applies particularly to:

```
Event Session
Registration Type
Meal Type
Camp Classification
Other configurable UPBS categories
```

---

# 35. Event Session

The established UPBS sessions are:

```
ADHIBASA
DAY_1
DAY_2
DAY_3
```

The project master-data source identifies these as event-session values.

The final FK/master-table implementation shall follow the approved master
data catalogue.

---

# 36. Meal Tracking Boundary

The functional requirement supports:

```
Breakfast
Lunch
Dinner
```

and QR-based meal tracking.

However, the current frozen seven-table UPBS foundation does not include a
dedicated frozen meal-scan table.

Therefore this table design does NOT add:

```
upbs_meal_scan
```

at this stage.

---

# 37. Future Meal Table

If detailed QR meal persistence requires a dedicated table, that table shall
be introduced only after:

```
Meal Business Rules
    ↓
Operational Design
    ↓
Approved Schema Change
```

It is not part of the current seven-table freeze.

---

# 38. Committee Boundary

The current seven-table foundation does not contain:

```
upbs_committee
```

UPBS Committee Management shall reuse the common governance/body model
where applicable.

No UPBS-specific committee table is added here.

---

# 39. Volunteer Boundary

The current seven-table foundation does not contain a finalized UPBS
volunteer table.

The source identifies UPBS Volunteer Structure as pending.

Therefore no final volunteer table is added by UPBS-004.

---

# 40. Day 1–Day 3 Operational Boundary

The current foundation does not freeze separate operational tables for:

```
Day 1
Day 2
Day 3
```

Detailed operational tables require separate approved design.

---

# 41. Attendance Boundary

UPBS event attendance is a functional requirement.

However, this document does not create a separate UPBS attendance table
because the current frozen UPBS foundation does not identify one.

The relationship between general Attendance and UPBS event participation
shall be resolved in the detailed Attendance/UPBS operational design.

---

# 42. Audit Fields

Transactional UPBS tables should use the common NSS audit standard.

Expected standard fields include:

```text
created_at
created_by_sangha_sevi_pk

updated_at
updated_by_sangha_sevi_pk

deleted_at
deleted_by_sangha_sevi_pk

is_active
```

The exact applicability of each field to master/reference tables shall follow
the project-wide audit standard.

---

# 43. UUID Primary Keys

UPBS primary keys shall use the project-standard UUID-based PK architecture.

Examples:

```text
upbs_event_pk
upbs_registration_pk
delegate_card_pk
prasad_patra_pk
accommodation_allocation_pk
camp_master_pk
guest_reference_pk
```

---

# 44. Foreign Key Naming

Foreign keys shall reference the target primary key.

Examples:

```text
upbs_event_pk
upbs_registration_pk
camp_master_pk
sangha_sevi_pk
person_pk
```

Business IDs shall not be used as relational FK substitutes.

---

# 45. Indexing Principles

The final PostgreSQL implementation shall index:

* Primary keys
* Foreign keys
* Approved business identifiers
* Search fields used operationally
* Unique business identifiers

Exact index definitions belong to the SQL implementation stage.

---

# 46. Unique Constraints

Unique constraints shall be introduced only where required by approved
business rules.

Examples requiring final confirmation include:

```
Registration business ID
Delegate Card identifier
Prasad Patra identifier
Camp code
```

This document does not invent uniqueness rules not supported by the source.

---

# 47. Check Constraints

Database CHECK constraints should enforce frozen business rules where
practical.

For example, the Delegate Only prohibition may be represented through the
approved registration-type model.

However, exact implementation depends on whether registration type is
stored through a master table or another approved model.

---

# 48. Referential Integrity

The physical PostgreSQL schema shall enforce valid references between:

```
Event
Registration
Delegate Card
Prasad Patra
Accommodation
Camp
Guest Reference
NSS Identity
```

---

# 49. Delete Rules

Historical UPBS data shall be protected.

The final SQL shall use appropriate ON DELETE behavior to prevent accidental
destruction of historical event participation.

Exact ON DELETE behavior shall be defined during SQL implementation.

---

# 50. Historical Records

UPBS historical data shall remain traceable.

Examples:

```
Previous UPBS Event
Previous Registration
Previous Delegate Card
Previous Prasad Participation
Previous Accommodation
Previous Guest Reference
```

shall not be silently rewritten because a new UPBS event is created.

---

# 51. Event Isolation

The schema shall ensure that participation records belong to their correct
UPBS event.

Example:

```text
UPBS 2025
   └── Registration A

UPBS 2026
   └── Registration B
```

Registration A must not be silently reassigned to UPBS 2026.

---

# 52. Identity Isolation

The following identities must remain distinct:

```text
Person
Sangha Sevi
UPBS Registration
Delegate Card
Prasad Patra
```

---

# 53. Finance Boundary

UPBS registration/prasad/accommodation information may contain amounts or
financially relevant information if approved.

Actual financial accounting belongs to the Finance module.

UPBS shall not create a duplicate financial ledger.

---

# 54. Notification Boundary

UPBS notifications shall use the common notification framework.

No:

```
upbs_notification
```

table is introduced by this design.

---

# 55. Document Boundary

Delegate cards or other digital UPBS artifacts may eventually use the common
Document Management architecture.

The UPBS table design shall not create a duplicate document repository.

---

# 56. Current Frozen Table Count

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference

TOTAL = 7
```

---

# 57. Tables Explicitly Not Added

The following are intentionally NOT part of this frozen table design:

```text
upbs_meal_scan
upbs_committee
upbs_volunteer
upbs_day1_operation
upbs_day2_operation
upbs_day3_operation
upbs_attendance
upbs_notification
upbs_order
upbs_payment
upbs_inventory
```

Each requires either an existing common framework or a separate approved
future design.

---

# 58. Current Schema Boundary

```text
                 UPBS FROZEN FOUNDATION
                           │
                           ▼
                    upbs_event
                           │
                           ▼
                 upbs_registration
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
       delegate_card  prasad_patra  accommodation
                                           │
                                           ▼
                                      camp_master

                                 guest_reference
                                      │
                                      ▼
                                Sangha Sevi
```

---

# 59. Implementation Readiness

The current document establishes:

```
Table Identity
Logical Purpose
Relationships
Naming Standards
Audit Boundary
Historical Boundary
Future Expansion Boundary
```

The following remain required before final PostgreSQL DDL:

```
Exact column list
Exact data types
Exact NOT NULL rules
Exact FK definitions
Exact unique constraints
Exact CHECK constraints
Exact indexes
Exact ON DELETE behavior
Exact master-data FK mappings
```

These shall be finalized against the approved source and business rules
before SQL generation.

---

# 60. Source Alignment

The project schema review explicitly identifies the UPBS foundation as:

```
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

for a total of seven tables.

The project-wide database standard establishes:

```
<table>_pk
```

for primary keys and requires foreign keys to reference primary keys.
It also establishes the standard audit/soft-delete fields for transactional
tables.

The current project baseline identifies UPBS Registration Foundation as
frozen while UPBS Volunteer Structure and Day 1/2/3 Operations remain
separate pending operational domains.

---

# 61. Status

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
