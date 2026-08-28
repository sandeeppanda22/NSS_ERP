# NSS ERP — UPBS Module Overview

**Document ID:** SOL-UPBS-001  
**Version:** 1.0.0  
**Status:** DRAFT — SOURCE ALIGNED  
**Module:** Utkala Pradeshika Bhakta Sammilani (UPBS)  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

The UPBS Module manages the digital operational foundation of the Utkala
Pradeshika Bhakta Sammilani (UPBS).

The module provides support for:

- UPBS event management
- Registration
- Delegate management
- Delegate Cards
- Prasad Patra
- Accommodation
- Camp allocation
- Guest/reference management
- Event-day operations
- Meal tracking
- Committee management
- Volunteer operations
- UPBS reporting

The current frozen foundation covers the core registration and event
infrastructure.

Detailed Day 1, Day 2, Day 3 operational workflows and the complete
volunteer structure require separate design where not already frozen.

---

# 2. UPBS Module Scope

The UPBS module is centered around the UPBS event.

```text
UPBS
│
├── Event
├── Registration
├── Delegate Card
├── Prasad Patra
├── Accommodation
├── Camp
├── Guest Reference
├── Committees
├── Volunteers
├── Event-Day Operations
├── Meal Tracking
└── Reports
```

---

# 3. Current Frozen Foundation

The current UPBS database foundation consists of seven tables:

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

These form the current frozen UPBS registration foundation.

---

# 4. UPBS Event Structure

The current UPBS event structure is:

```text
UPBS
│
├── ADHIBASA
├── DAY_1
├── DAY_2
└── DAY_3
```

These are the established UPBS event sessions.

---

# 5. Adhibasa

Adhibasa is the pre-event/preparatory UPBS phase.

The existing source identifies Adhibasa activities including:

* Registration
* Accommodation
* Seva-Puja
* Sri Sri Thakur Camp Visit
* Adhibasa Puja
* Lunch
* Dinner

The detailed operational implementation shall follow the applicable UPBS
rules.

---

# 6. Day 1

Day 1 is one of the core UPBS event sessions.

The current foundation recognizes Day 1 as an event session.

Detailed Day 1 operational workflows should be documented separately where
they are not already frozen.

---

# 7. Day 2

Day 2 is one of the core UPBS event sessions.

The current foundation recognizes Day 2 as an event session.

Detailed Day 2 operational workflows should be documented separately where
they are not already frozen.

---

# 8. Day 3

Day 3 is one of the core UPBS event sessions.

The current foundation recognizes Day 3 as an event session.

Detailed Day 3 operational workflows should be documented separately where
they are not already frozen.

---

# 9. UPBS Registration

Registration is a central UPBS function.

Registration may be completed:

* Before UPBS
* During UPBS

This capability is part of the existing UPBS foundation.

---

# 10. Registration Types

The current event model supports different participation/package concepts,
including:

```text
Delegate Package
Prasad Only
```

The exact registration options and validation rules shall follow the frozen
UPBS registration rules.

---

# 11. Delegate Package

The Delegate Package contains:

```text
Delegate Card
+
Prasad Patra
```

This relationship is established in the current UPBS rules.

---

# 12. Prasad Only

Prasad Only registration is supported.

A participant may register for Prasad without becoming a Delegate.

---

# 13. Delegate Only

The current rule states:

```text
Delegate Only
=
Not Allowed
```

A Delegate Package includes the associated Prasad Patra.

---

# 14. Delegate Card

The UPBS Module provides Delegate Card management.

The Delegate Card is associated with the UPBS registration.

The card is used as an important identification mechanism during UPBS.

---

# 15. Delegate Card at Entrances

At UPBS entrances:

```text
Delegate Card
      ↓
Shown to Security
      ↓
Verification
```

Security verification is part of the existing UPBS operational foundation.

---

# 16. Prasad Patra

Prasad Patra is a dedicated UPBS participation artifact.

The current foundation contains:

```text
prasad_patra
```

and the Delegate Package includes Prasad Patra.

---

# 17. Accommodation

Accommodation is a core UPBS function.

The existing foundation contains:

```text
accommodation_allocation
```

and:

```text
camp_master
```

These support accommodation/camp allocation.

---

# 18. Camp Management

UPBS accommodation uses defined camps.

Camp information is maintained through:

```text
camp_master
```

The detailed camp allocation workflow belongs to the UPBS operational
design.

---

# 19. Guest Management

The UPBS foundation supports guest management.

A guest may be associated with a reference Sangha Sevi.

The existing rule requires:

```text
Reference Sangha Sevi
```

for guest management.

---

# 20. Reference Sangha Sevi

The reference person for a guest shall use the authoritative Sangha Sevi
identity.

The UPBS Module shall not create a duplicate member identity system.

---

# 21. Meal Tracking

UPBS supports meal tracking.

The current foundation identifies:

```text
Breakfast
Lunch
Dinner
```

as meal types.

---

# 22. QR-Based Meal Tracking

Meal tracking is designed around QR-based verification.

For Day 1–Day 3:

```text
Participant
    ↓
QR / Delegate Identification
    ↓
Meal Scan
    ↓
Meal Record
```

The current source identifies QR-based meal scans for UPBS meal tracking.

---

# 23. Adhibasa Meal Tracking

For Adhibasa, meal scans are optional according to the existing foundation.

---

# 24. Day 1–Day 3 Meal Tracking

For Day 1, Day 2, and Day 3, meal scans are recorded through QR-based
tracking.

Supported meals:

```text
Breakfast
Lunch
Dinner
```

---

# 25. Committee Management

The UPBS module includes Committee Management.

The existing project module overview identifies:

```text
Committee Dashboard
```

as a UPBS capability.

---

# 26. Unified Governance Model

UPBS committees should use the common NSS Unified Body Governance Model
where applicable.

The project architecture has replaced separate committee-member models
with the generalized:

```text
body_master
body_member_assignment
position_master
```

architecture.

This allows future UPBS committees to be represented without creating a
separate schema for every committee.

---

# 27. Possible UPBS Committees

The generalized governance architecture can support UPBS committees such as:

```text
UPBS Central Committee
UPBS Registration Committee
UPBS Accommodation Committee
UPBS Security Committee
```

and other approved UPBS committees.

These are examples of the extensible governance model, not a new frozen
committee list.

---

# 28. Volunteer Management

Volunteer operations are part of the broader UPBS scope.

The current project architecture identifies:

```text
UPBS Volunteers
```

as a separate operational area requiring detailed design.

---

# 29. Sevak and UPBS Volunteers

Sevak Sangha participation and UPBS Seva assignment are distinct concepts.

The Sevak rules explicitly provide a separate UPBS Seva approval path:

```text
Sevak
   ↓
UPBS Seva Category
   ↓
UPBS Seva Head
   ↓
Kendra Submission
   ↓
Parichalak / President Approval
   ↓
Approved Assignment
```

Therefore the UPBS Module should consume approved Sevak/Seva information
rather than creating another Sevak identity.

---

# 30. Event Operations

The UPBS Module is more than registration.

It ultimately supports the operational lifecycle of the event:

```text
Planning
   ↓
Registration
   ↓
Adhibasa
   ↓
Day 1
   ↓
Day 2
   ↓
Day 3
   ↓
Completion
   ↓
Reports
```

Detailed operational rules for each stage shall be documented separately
where not already frozen.

---

# 31. Registration Dashboard

The UPBS Dashboard should provide high-level visibility such as:

```text
Registrations
Accommodation
Prasad
Committees
Volunteers
Delegate Search
Accommodation Search
Reports
```

This structure is already reflected in the project UI source.

---

# 32. Registration Search

Authorized users should be able to search UPBS registrations.

Possible search criteria include:

```text
Sangha Sevi ID
Member Name
Registration ID
Delegate Card
Registration Type
Sakha
Accommodation
```

The exact search fields shall follow the detailed UPBS UI design.

---

# 33. Delegate Search

Authorized UPBS users should be able to search delegate records.

Delegate identification should support the Delegate Card.

---

# 34. Accommodation Search

Authorized UPBS users should be able to locate accommodation allocations.

Possible search dimensions include:

```text
Registration
Delegate
Camp
Accommodation Allocation
```

---

# 35. Reports

The UPBS Module shall support operational reporting.

Examples include:

```text
Registration Report
Delegate Report
Prasad Report
Accommodation Report
Camp Report
Meal Report
Committee Report
Volunteer Report
```

Detailed report definitions belong to the Reports/UPBS solution design.

---

# 36. Event Identity

Each UPBS event shall have a unique event identity.

The authoritative event entity is:

```text
upbs_event
```

---

# 37. Registration Identity

Each UPBS registration shall have its own registration identity.

The authoritative registration entity is:

```text
upbs_registration
```

UPBS registration is an event participation record.

It does not replace NSS Membership identity.

---

# 38. NSS Membership vs UPBS Registration

These are distinct concepts:

```text
NSS Membership
    =
Permanent NSS membership identity

UPBS Registration
    =
Participation in a particular UPBS event
```

A person may participate in multiple UPBS events over time through separate
event registrations.

---

# 39. Sangha Sevi Identity

Where a registrant is an NSS Member, the existing Sangha Sevi identity
shall be reused.

UPBS shall not create another permanent NSS membership identity.

---

# 40. Guest Identity

Guests are handled through the UPBS guest/reference model.

The reference Sangha Sevi relationship is retained.

---

# 41. History

UPBS historical records shall be preserved.

The project-wide principle is:

```text
History Never Deleted
```

Therefore past UPBS registrations, delegate records, accommodation
records, and other significant operational history shall remain traceable.

---

# 42. Audit

UPBS operations shall follow the common NSS ERP audit standards.

Significant changes should preserve:

```text
Who
What
When
Previous Value
New Value
Reason
```

where applicable.

---

# 43. Security

UPBS operational data shall be protected according to the common security
and RBAC framework.

Examples include:

```text
Registration data
Accommodation data
Guest information
Delegate information
Meal information
```

---

# 44. Role-Based Access

Different UPBS functions may require different roles.

Examples:

```text
UPBS Administrator
Registration Team
Accommodation Team
Committee Members
Security
Volunteer Coordinators
Reports Users
```

The exact permission matrix shall be defined through the common
Administration/RBAC framework and detailed UPBS design.

---

# 45. Member-Facing UPBS

Members should be able to interact with UPBS through the ERP according to
the applicable registration and event-access rules.

Potential member functions include:

```text
UPBS Information
Registration
Registration Status
Delegate Information
Accommodation Information
Prasad Information
Event Information
```

Exact member workflows require detailed UI/functional design.

---

# 46. Mobile-Friendly Operations

UPBS operations should support mobile-friendly workflows.

This is particularly important for:

```text
Registration
Delegate Verification
Meal Scanning
Accommodation Verification
Security
Volunteer Operations
```

The overall NSS UI philosophy is:

```text
Traditional
Spiritual
Simple
Mobile Friendly
Accessible to Elder Members
Minimal Training Required
```

---

# 47. QR-Based Operations

QR technology is applicable to UPBS operational verification.

The current source explicitly identifies QR-based meal tracking.

Future QR uses must not be assumed without separate requirements.

---

# 48. Registration Before UPBS

Participants may register before the UPBS event.

This supports advance planning for:

```text
Delegates
Prasad
Accommodation
Meals
Event Operations
```

---

# 49. Registration During UPBS

The system also supports registration during UPBS.

The operational UI should therefore support on-site registration.

---

# 50. Event-Day Operations

The UPBS module should eventually provide operational dashboards for:

```text
Adhibasa
Day 1
Day 2
Day 3
```

Each event day may have its own operational tasks.

---

# 51. Current Scope vs Detailed Operational Design

The current module overview establishes the foundation.

Detailed rules for:

```text
UPBS Day 1
UPBS Day 2
UPBS Day 3
Volunteer Structure
```

should be documented in subsequent UPBS solution documents where not already
frozen.

---

# 52. Current Frozen Tables

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

Total:

```text
7
```

These are the current frozen UPBS foundation tables.

---

# 53. No Duplicate Membership Tables

The UPBS Module shall not duplicate:

```text
person
sangha_sevi
membership
family
```

UPBS references the existing NSS identity/foundation.

---

# 54. No Duplicate Governance Tables

UPBS committees should reuse the common governance/body architecture.

No separate:

```text
upbs_committee_member
```

model should be created merely because a committee belongs to UPBS.

---

# 55. No Duplicate Sevak Identity

UPBS volunteer/seva operations shall reference the established Sevak/Seva
framework where applicable.

UPBS shall not create another permanent volunteer identity without approved
requirements.

---

# 56. UPBS and Finance

The UPBS Module may generate financial information related to:

```text
Registration
Prasad
Accommodation
Other approved UPBS charges
```

Actual financial transactions shall follow the common Finance architecture.

The UPBS Module shall not create a parallel financial ledger.

---

# 57. UPBS and Reports

Operational UPBS reports may be generated from UPBS data.

Financial reports remain subject to Finance ownership.

---

# 58. Current Functional Areas

| Area                         | Status                   |
| ---------------------------- | ------------------------ |
| UPBS Event                   | FROZEN FOUNDATION        |
| Registration                 | FROZEN FOUNDATION        |
| Delegate Card                | FROZEN FOUNDATION        |
| Prasad Patra                 | FROZEN FOUNDATION        |
| Accommodation                | FROZEN FOUNDATION        |
| Camp                         | FROZEN FOUNDATION        |
| Guest Reference              | FROZEN FOUNDATION        |
| Committee Dashboard          | IN SCOPE                 |
| Volunteer Dashboard          | IN SCOPE                 |
| Meal Tracking                | FROZEN FOUNDATION        |
| Adhibasa                     | FROZEN FOUNDATION        |
| Day 1 Operations             | REQUIRES DETAILED DESIGN |
| Day 2 Operations             | REQUIRES DETAILED DESIGN |
| Day 3 Operations             | REQUIRES DETAILED DESIGN |
| Detailed Volunteer Structure | REQUIRES DETAILED DESIGN |
| Detailed Finance Workflow    | FUTURE/SEPARATE          |

---

# 59. Member-Facing Concept

```text
Member
  │
  ▼
UPBS
  │
  ├── Event Information
  ├── Registration
  ├── Delegate Information
  ├── Accommodation
  ├── Prasad
  └── UPBS Updates
```

---

# 60. Operational Concept

```text
UPBS Administrator
       │
       ▼
UPBS Dashboard
       │
       ├── Registration
       ├── Delegates
       ├── Accommodation
       ├── Prasad
       ├── Committees
       ├── Volunteers
       ├── Meals
       └── Reports
```

---

# 61. Event Lifecycle Concept

```text
UPBS Planning
      │
      ▼
Registration Open
      │
      ▼
Registration
      │
      ▼
Accommodation / Prasad / Delegate
      │
      ▼
Adhibasa
      │
      ▼
Day 1
      │
      ▼
Day 2
      │
      ▼
Day 3
      │
      ▼
Completion
      │
      ▼
Reports / Historical Record
```

---

# 62. Architecture Principle

The UPBS Module follows:

```text
Existing NSS Identity
        ↓
UPBS Event
        ↓
Event Registration
        ↓
Participation Artifacts
        ↓
Event Operations
        ↓
Reports
```

---

# 63. Current Database Principle

The current UPBS foundation remains:

```text
7 Frozen Tables
```

The module documentation shall not introduce new tables simply to represent
future capabilities.

---

# 64. Future Expansion

Future approved UPBS requirements may introduce additional operational
entities for:

```text
Day 1 Operations
Day 2 Operations
Day 3 Operations
Volunteer Management
Advanced Meal Operations
Security Operations
Transport
Event Logistics
```

Each requires separate business-rule and schema design.

---

# 65. Status

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
