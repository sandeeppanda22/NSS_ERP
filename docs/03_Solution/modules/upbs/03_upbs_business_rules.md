# NSS ERP — UPBS Business Rules

**Document ID:** SOL-UPBS-003
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED
**Module:** Utkala Pradeshika Bhakta Sammilani (UPBS)
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the business rules governing the currently frozen
UPBS Registration Foundation.

The rules cover:

- UPBS Event
- Registration
- Participation Packages
- Delegate Card
- Prasad Patra
- Accommodation
- Camp
- Guest Reference
- Meal Tracking
- Event Sessions
- Historical Records

Rules for UPBS Day 1/Day 2/Day 3 detailed operations and the complete
Volunteer Structure are not frozen by this document.

---

# 2. Rule Status Convention

Each rule is classified as:

- FROZEN — established by the current project source
- SOURCE-ALIGNED — directly derived from the existing project foundation
- PENDING — requires further business discussion
- FUTURE — outside the current frozen foundation

---

# 3. UPBS Event Rules

## UPBS-BR-001 — UPBS Event Identity

**Status:** FROZEN

Every UPBS occurrence shall be represented as a distinct UPBS event.

The authoritative event entity is:

    upbs_event

A UPBS registration belongs to a specific UPBS event.

---

## UPBS-BR-002 — Event-Specific Registration

**Status:** FROZEN

A UPBS registration is participation in a particular UPBS event.

UPBS registration shall not replace or modify the person's permanent NSS
membership identity.

---

## UPBS-BR-003 — UPBS Event Sessions

**Status:** FROZEN

The UPBS event structure recognizes:

    ADHIBASA
    DAY_1
    DAY_2
    DAY_3

These represent the established UPBS event sessions.

---

## UPBS-BR-004 — No Separate Event Table Per Day

**Status:** SOURCE-ALIGNED

The system shall not create independent event entities merely for:

    Adhibasa
    Day 1
    Day 2
    Day 3

They belong to the UPBS event/session model.

---

# 4. Registration Rules

## UPBS-BR-005 — Registration Availability

**Status:** FROZEN

UPBS registration may be completed:

    Before UPBS

or:

    During UPBS

This is explicitly established in the current UPBS foundation.

---

## UPBS-BR-006 — Registration Belongs to Event

**Status:** FROZEN

Every UPBS registration shall belong to a specific UPBS event.

Conceptually:

    UPBS Event
        ↓
    UPBS Registration

---

## UPBS-BR-007 — NSS Identity Reuse

**Status:** FROZEN

Where a participant is an NSS member, the existing NSS person/member/Sangha
Sevi identity shall be reused.

UPBS shall not create another permanent NSS member identity.

---

## UPBS-BR-008 — Registration Does Not Create Membership

**Status:** FROZEN

UPBS registration does not:

- Create NSS Membership
- Create a Sangha Sevi ID
- Change Membership Type
- Change Membership Status
- Transfer a member between Sakhas

---

## UPBS-BR-009 — Event Participation Is Separate From Membership

**Status:** FROZEN

The system shall distinguish:

    NSS Membership

from:

    UPBS Event Participation

A person's UPBS participation does not redefine their membership identity.

---

# 5. Participation Package Rules

## UPBS-BR-010 — Supported Participation Concepts

**Status:** FROZEN

The current UPBS foundation recognizes:

    Delegate Package
    Prasad Only

---

## UPBS-BR-011 — Delegate Package Composition

**Status:** FROZEN

The Delegate Package contains:

    Delegate Card
    +
    Prasad Patra

This composition is explicitly established in the current project rules.

---

## UPBS-BR-012 — Prasad Only

**Status:** FROZEN

Prasad Only registration is permitted.

A participant may register for Prasad without taking the Delegate Package.

---

## UPBS-BR-013 — Delegate Only Prohibited

**Status:** FROZEN

Delegate Only registration is not permitted.

A Delegate Package includes the associated Prasad Patra.

Therefore:

    Delegate Card without required Prasad
    =
    Not Allowed

---

## UPBS-BR-014 — Package Integrity

**Status:** FROZEN

The system shall preserve the relationship between:

    Delegate Package
        ↓
    Delegate Card
        +
    Prasad Patra

The UI shall not allow a valid Delegate Package to be represented as
Delegate-only participation.

---

# 6. Delegate Card Rules

## UPBS-BR-015 — Delegate Card

**Status:** FROZEN

A Delegate Card is associated with the applicable UPBS registration.

The authoritative table is:

    delegate_card

---

## UPBS-BR-016 — Delegate Identification

**Status:** SOURCE-ALIGNED

The Delegate Card serves as an identification artifact during UPBS.

At UPBS entrances, the Delegate Card may be presented for security
verification.

---

## UPBS-BR-017 — Event-Specific Delegate Card

**Status:** SOURCE-ALIGNED

A Delegate Card belongs to its relevant UPBS event/registration context.

A Delegate Card from one UPBS event shall not automatically become the
Delegate Card for another UPBS event.

---

## UPBS-BR-018 — Delegate Card Does Not Replace Sangha Sevi ID

**Status:** FROZEN

The Delegate Card is an event-specific identification artifact.

It is not:

    Sangha Sevi ID

and does not replace the permanent NSS membership identity.

---

# 7. Prasad Patra Rules

## UPBS-BR-019 — Prasad Patra

**Status:** FROZEN

The UPBS foundation maintains Prasad Patra through:

    prasad_patra

---

## UPBS-BR-020 — Prasad in Delegate Package

**Status:** FROZEN

Every valid Delegate Package includes the corresponding Prasad Patra.

---

## UPBS-BR-021 — Prasad Only

**Status:** FROZEN

A participant may register for Prasad without becoming a Delegate.

---

## UPBS-BR-022 — Prasad Participation Is Separate From Membership

**Status:** SOURCE-ALIGNED

Prasad participation does not create or modify NSS membership.

---

# 8. Accommodation Rules

## UPBS-BR-023 — Accommodation Supported

**Status:** FROZEN

UPBS supports accommodation management.

The current foundation contains:

    accommodation_allocation

and:

    camp_master

---

## UPBS-BR-024 — Accommodation Allocation

**Status:** SOURCE-ALIGNED

Accommodation shall be represented as an allocation associated with the
relevant UPBS participation.

---

## UPBS-BR-025 — Camp Master

**Status:** FROZEN

UPBS camps are maintained through:

    camp_master

A camp is a master-data entity used by accommodation allocation.

---

## UPBS-BR-026 — Accommodation Is Event-Specific

**Status:** SOURCE-ALIGNED

Accommodation allocation shall belong to the relevant UPBS event context.

Historical accommodation allocation must remain traceable.

---

## UPBS-BR-027 — Detailed Accommodation Rules

**Status:** PENDING

The current source does not provide sufficient detail to freeze rules for:

- Room allocation
- Bed allocation
- Capacity
- Family/group accommodation
- Camp capacity
- Reallocation
- Check-in
- Check-out
- Accommodation priority

These shall be addressed in the detailed UPBS operational design.

---

# 9. Guest Rules

## UPBS-BR-028 — Guest Management

**Status:** FROZEN

UPBS supports guest management.

The current foundation contains:

    guest_reference

---

## UPBS-BR-029 — Reference Sangha Sevi Mandatory

**Status:** FROZEN

A guest must have a reference Sangha Sevi.

The project source explicitly establishes:

    Reference Sangha Sevi mandatory

---

## UPBS-BR-030 — Reference Uses Existing NSS Identity

**Status:** SOURCE-ALIGNED

The reference person shall be identified using the authoritative NSS
Sangha Sevi/member identity.

The UPBS Module shall not create a separate reference-person identity.

---

## UPBS-BR-031 — Guest Reference Traceability

**Status:** SOURCE-ALIGNED

The relationship between a guest and the reference Sangha Sevi shall remain
traceable for the relevant UPBS event.

---

# 10. Meal Tracking Rules

## UPBS-BR-032 — Meal Tracking

**Status:** FROZEN

UPBS supports meal tracking.

The current meal types are:

    BREAKFAST
    LUNCH
    DINNER

---

## UPBS-BR-033 — QR-Based Meal Tracking

**Status:** FROZEN

UPBS meal tracking uses QR-based scanning.

The current foundation explicitly identifies:

    QR-based meal tracking

---

## UPBS-BR-034 — Adhibasa Meal Scanning

**Status:** FROZEN

Meal scanning during Adhibasa is optional.

---

## UPBS-BR-035 — Day 1–Day 3 Meal Scanning

**Status:** FROZEN

Meal scans are recorded for:

    Day 1
    Day 2
    Day 3

using QR-based tracking.

---

## UPBS-BR-036 — Meal Types

**Status:** FROZEN

The supported meal types are:

    Breakfast
    Lunch
    Dinner

---

## UPBS-BR-037 — Meal Scan Does Not Equal Registration

**Status:** SOURCE-ALIGNED

A meal scan represents meal participation.

It shall not create a new UPBS registration.

---

## UPBS-BR-038 — Meal Scan Does Not Create Membership

**Status:** SOURCE-ALIGNED

Meal participation shall not create or modify NSS membership.

---

# 11. Attendance / Participation Rules

## UPBS-BR-039 — Event Attendance

**Status:** FROZEN

UPBS attendance is captured once for the event.

The existing project source explicitly states:

    Attendance
    Captured once for the event

---

## UPBS-BR-040 — Attendance Is Separate From Registration

**Status:** SOURCE-ALIGNED

Registration represents intended/approved participation.

Attendance represents actual participation.

The two concepts shall not be treated as identical.

---

## UPBS-BR-041 — Attendance Is Separate From Meal Scan

**Status:** SOURCE-ALIGNED

Event attendance and meal scanning are distinct operational concepts.

A meal scan shall not silently overwrite or redefine event attendance.

---

# 12. Event-Day Rules

## UPBS-BR-042 — Adhibasa

**Status:** FROZEN

Adhibasa is an established UPBS event session.

The current source provides special treatment for meal scanning during
Adhibasa.

---

## UPBS-BR-043 — Day 1

**Status:** FROZEN FOUNDATION / OPERATIONS PENDING

Day 1 is an established UPBS event session.

Detailed Day 1 operational rules are not fully frozen by this document.

---

## UPBS-BR-044 — Day 2

**Status:** FROZEN FOUNDATION / OPERATIONS PENDING

Day 2 is an established UPBS event session.

Detailed Day 2 operational rules are not fully frozen by this document.

---

## UPBS-BR-045 — Day 3

**Status:** FROZEN FOUNDATION / OPERATIONS PENDING

Day 3 is an established UPBS event session.

Detailed Day 3 operational rules are not fully frozen by this document.

---

# 13. Historical Rules

## UPBS-BR-046 — Historical Preservation

**Status:** SOURCE-ALIGNED

UPBS historical records shall be preserved.

The NSS ERP architecture follows:

    History Never Deleted

Therefore completed UPBS events and their significant participation records
shall remain historically traceable.

---

## UPBS-BR-047 — No Physical Deletion

**Status:** SOURCE-ALIGNED

Normal administrative operations shall not physically delete historical
UPBS participation records.

---

## UPBS-BR-048 — Historical Event Independence

**Status:** SOURCE-ALIGNED

A new UPBS event shall not rewrite historical registration, delegate,
Prasad, accommodation, or guest-reference records belonging to a previous
UPBS event.

---

# 14. Identity Rules

## UPBS-BR-049 — One Permanent NSS Identity

**Status:** FROZEN

The NSS identity model remains authoritative.

UPBS does not create a permanent identity.

---

## UPBS-BR-050 — Sangha Sevi ID

**Status:** FROZEN

Where the participant is an NSS member, the existing Sangha Sevi ID remains
the authoritative membership identifier.

---

## UPBS-BR-051 — UPBS Registration ID

**Status:** SOURCE-ALIGNED

UPBS registration has its own event-participation identity.

This identity is not a replacement for Sangha Sevi ID.

---

# 15. Event Re-Participation

## UPBS-BR-052 — Multiple UPBS Events

**Status:** SOURCE-ALIGNED

A person may participate in different UPBS events over time.

Each event participation shall remain associated with its own event.

Example:

    Person
       │
       ├── UPBS 2025 → Registration
       │
       └── UPBS 2026 → Registration

Historical event records remain independent.

---

# 16. Committee Rules

## UPBS-BR-053 — Committee Management

**Status:** IN SCOPE / DETAILED RULES PENDING

Committee Management is part of the UPBS functional scope.

The current source does not provide a complete UPBS-specific committee
business-rule set in the frozen seven-table foundation.

---

## UPBS-BR-054 — Unified Governance Model

**Status:** SOURCE-ALIGNED

Where UPBS committees require organizational governance, the common NSS
Unified Body Governance Model shall be reused.

UPBS shall not create a parallel organizational governance architecture.

---

# 17. Volunteer Rules

## UPBS-BR-055 — UPBS Volunteer Structure

**Status:** PENDING

UPBS Volunteer Structure is not yet fully frozen.

The project baseline explicitly lists:

    UPBS Volunteer Structure

among pending major operational modules.

Therefore this document does not freeze:

- Volunteer categories
- Eligibility
- Assignment
- Approval
- Shift management
- Volunteer attendance
- Volunteer replacement
- Volunteer reporting

---

## UPBS-BR-056 — Sevak Integration

**Status:** SOURCE-ALIGNED

Where UPBS Seva participation involves an existing Sevak, the authoritative
Sevak/Seva framework shall be reused.

The UPBS Module shall not create a duplicate permanent Sevak identity.

---

# 18. Day 1–Day 3 Operational Rules

## UPBS-BR-057 — Detailed Operations Pending

**Status:** PENDING

The current project baseline explicitly identifies:

    UPBS Day 1 Operations
    UPBS Day 2 Operations
    UPBS Day 3 Operations

as pending major operational modules.

Therefore this document does not invent detailed rules for those operations.

---

# 19. Security Rules

## UPBS-BR-058 — Role-Based Access

**Status:** SOURCE-ALIGNED

UPBS operations shall use the common NSS ERP RBAC architecture.

UPBS shall not create an independent authorization system.

---

## UPBS-BR-059 — Operational Role Separation

**Status:** SOURCE-ALIGNED

Access to functions such as:

- Registration
- Accommodation
- Delegate verification
- Meal scanning
- Guest management
- Reports

may be separated according to authorized roles.

The final permission matrix shall be defined by the common Administration/
RBAC design.

---

# 20. Audit Rules

## UPBS-BR-060 — Significant Change Audit

**Status:** SOURCE-ALIGNED

Significant UPBS administrative changes shall be auditable.

The common NSS audit framework applies.

---

## UPBS-BR-061 — Historical Corrections

**Status:** SOURCE-ALIGNED

Historical UPBS records shall not be silently overwritten when an
exceptional correction is required.

Corrections shall follow the common audit/correction standards.

---

# 21. Data Integrity Rules

## UPBS-BR-062 — Valid Event Reference

**Status:** SOURCE-ALIGNED

Every UPBS registration must belong to a valid UPBS event.

---

## UPBS-BR-063 — Valid Accommodation Context

**Status:** SOURCE-ALIGNED

Accommodation allocation must remain associated with a valid UPBS event/
registration context.

---

## UPBS-BR-064 — Valid Camp

**Status:** SOURCE-ALIGNED

An accommodation allocation must reference a valid camp where camp
allocation is applicable.

---

## UPBS-BR-065 — Valid Guest Reference

**Status:** FROZEN

A guest reference must identify the required reference Sangha Sevi.

---

# 22. Financial Boundary

## UPBS-BR-066 — UPBS Financial Data

**Status:** SOURCE-ALIGNED

UPBS may capture information necessary for event registration and approved
UPBS charges.

Actual financial accounting belongs to the common Finance architecture.

---

## UPBS-BR-067 — No Parallel Financial Ledger

**Status:** SOURCE-ALIGNED

The UPBS Module shall not create a separate financial ledger.

---

# 23. Notification Boundary

## UPBS-BR-068 — Notifications

**Status:** SOURCE-ALIGNED

UPBS event notifications may be provided through the common NSS ERP
notification framework.

The UPBS Module shall not create a separate notification engine.

---

# 24. Mobile / QR Operations

## UPBS-BR-069 — Mobile-Friendly Operations

**Status:** SOURCE-ALIGNED

UPBS operational workflows should support mobile-friendly usage,
particularly for:

- Registration
- Delegate verification
- Meal scanning
- Accommodation operations
- Event operations

The project UI philosophy emphasizes simple, mobile-friendly interfaces
with minimal training requirements.

---

# 25. Rules Not Yet Frozen

The following areas are explicitly not frozen by this business-rule
document:

```text
UPBS Day 1 detailed operations
UPBS Day 2 detailed operations
UPBS Day 3 detailed operations
Complete volunteer structure
Detailed accommodation capacity rules
Detailed camp allocation rules
Detailed committee structure
Advanced security workflows
Transport
Logistics
Detailed financial workflow
```

These shall not be implemented as frozen business rules without further
approval.

---

# 26. Frozen Rule Summary

| Rule Area                | Status                 |
| ------------------------ | ---------------------- |
| UPBS Event               | FROZEN                 |
| Event Sessions           | FROZEN                 |
| Registration             | FROZEN                 |
| Before-UPBS Registration | FROZEN                 |
| During-UPBS Registration | FROZEN                 |
| Delegate Package         | FROZEN                 |
| Prasad Only              | FROZEN                 |
| Delegate Only            | PROHIBITED             |
| Delegate Card            | FROZEN                 |
| Prasad Patra             | FROZEN                 |
| Accommodation Foundation | FROZEN                 |
| Camp Foundation          | FROZEN                 |
| Guest Management         | FROZEN                 |
| Reference Sangha Sevi    | MANDATORY              |
| Meal Tracking            | FROZEN                 |
| QR Meal Tracking         | FROZEN                 |
| Adhibasa Meal Scan       | OPTIONAL               |
| Day 1–Day 3 Meal Scan    | REQUIRED/RECORDED      |
| Event Attendance         | FROZEN                 |
| Historical Preservation  | FROZEN PRINCIPLE       |
| Committee Operations     | DETAILED RULES PENDING |
| Volunteer Structure      | PENDING                |
| Day 1 Operations         | PENDING                |
| Day 2 Operations         | PENDING                |
| Day 3 Operations         | PENDING                |

---

# 27. Frozen UPBS Foundation

The current business-rule foundation maps to:

```text
UPBS Event
    │
    ▼
Registration
    │
    ├── Delegate Card
    │
    ├── Prasad Patra
    │
    ├── Accommodation
    │       │
    │       ▼
    │     Camp
    │
    └── Guest Reference
            │
            ▼
      Reference Sangha Sevi
```

---

# 28. Core UPBS Participation Rule

The central participation rule is:

```text
NSS Identity
     ↓
UPBS Event
     ↓
UPBS Registration
     ↓
Participation Package
     │
     ├── Delegate Package
     │      ├── Delegate Card
     │      └── Prasad Patra
     │
     └── Prasad Only
```

---

# 29. Identity Separation Principle

The system shall preserve the distinction:

```text
Person
    ≠
NSS Membership
    ≠
UPBS Registration
    ≠
Delegate Card
    ≠
Prasad Patra
```

Each represents a different business concept.

---

# 30. No Duplicate Identity Principle

UPBS shall reuse:

```text
Person
Membership
Sangha Sevi
Sevak
Governance
Notification
Audit
Finance
```

where applicable.

The module shall not create duplicate enterprise-level identities.

---

# 31. Source Alignment

The current project source establishes the UPBS foundation as:

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

for a total of seven frozen foundation tables.

The same source establishes:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

as the UPBS event structure, with registration before or during UPBS,
QR-based meal tracking, Breakfast/Lunch/Dinner, accommodation, and guest
management with mandatory Reference Sangha Sevi.

It also establishes:

```text
Delegate Package
    =
Delegate Card
+
Prasad Patra

Prasad Only
    =
Allowed

Delegate Only
    =
Not Allowed
```

The project baseline separately identifies UPBS Day 1/2/3 Operations and
Volunteer Structure as pending major operational modules.

---

# 32. Status

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
