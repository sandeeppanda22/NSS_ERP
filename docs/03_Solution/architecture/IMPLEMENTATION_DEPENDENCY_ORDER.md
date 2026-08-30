# NSS ERP — Implementation Dependency Order

**Document ID:** SOL-ARCH-008  
**Version:** 1.0.0  
**Status:** FROZEN — IMPLEMENTATION TIER ORDER  
**Parent Documents:**
- DATABASE_DESIGN_STANDARDS.md
- MODULE_DEPENDENCY_MAP.md
- Programme & Events Cross-Module Review
- Individual Module Design / ERD / Business Rules / Table Design documents

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the recommended implementation order for the NSS
ERP.

The project follows a **vertical-slice implementation strategy**:

```text
Module
  ↓
Database
  ↓
API
  ↓
UI
  ↓
Integration / Validation
```

The purpose of this document is to determine which module should be
implemented when, while respecting:

* frozen business ownership;
* cross-module dependencies;
* PostgreSQL FK requirements;
* authentication and authorization dependencies;
* audit requirements;
* Finance dependencies;
* common Programme & Event architecture;
* existing domain-specific modules.

---

# 2. Important Distinction

The following are different concepts:

```text
Module Number
      ≠
Implementation Tier
      ≠
DDL Creation Order
      ≠
Runtime Dependency
```

Module numbering identifies the project inventory.

Implementation tiers group modules for practical development.

DDL creation order determines when physical tables/FKs can be created.

Runtime dependency describes application-level consumption.

---

# 3. Current Module Inventory

The current project contains 22 module domains:

|  # | Module             | Status   |
| -: | ------------------ | -------- |
| 01 | Administration     | Existing |
| 02 | Attendance         | Existing |
| 03 | Audit              | Existing |
| 04 | Authentication     | Existing |
| 05 | Backup & Technical | Existing |
| 06 | Family             | Existing |
| 07 | Finance            | Existing |
| 08 | Foundation         | Existing |
| 09 | Governance         | Existing |
| 10 | Heritage           | Existing |
| 11 | Kishor             | Existing |
| 12 | Kumari             | Existing |
| 13 | Mahila             | Existing |
| 14 | Membership         | Existing |
| 15 | Organization       | Existing |
| 16 | Person             | Existing |
| 17 | Publications       | Existing |
| 18 | Reports            | Existing |
| 19 | Sevak              | Existing |
| 20 | UPBS               | Existing |
| 21 | Programme & Events | Proposed |
| 22 | Assets & Property  | Existing |

**Module #21 is architecturally justified but remains pending formal
module freeze.**

**Module #22 (Assets & Property) documentation complete (SOL-AP-001
through SOL-AP-005). 7 module-owned tables. Tier position OPEN pending
final dependency-graph review.**

---

# 4. Implementation Strategy

Each module shall be implemented as a vertical slice:

```text
┌──────────────────────────┐
│        MODULE            │
├──────────────────────────┤
│ Database                 │
│   ↓                      │
│ API                      │
│   ↓                      │
│ UI                       │
│   ↓                      │
│ Integration / Validation │
└──────────────────────────┘
```

The project shall avoid the following approach:

```text
All 21 Databases
       ↓
All 21 APIs
       ↓
All 21 UIs
```

unless a future architectural decision explicitly requires it.

---

# 5. Dependency Classes

Implementation ordering considers four dependency classes.

## 5.1 Foundation Dependency

The module requires common infrastructure or master data.

## 5.2 Identity Dependency

The module requires Person, Membership, Authentication or related
identity infrastructure.

## 5.3 Organizational Dependency

The module requires Organization or organizational scope.

## 5.4 Domain Integration Dependency

The module consumes another business domain.

Examples:

```text
Event → Finance
Event → Attendance
UPBS → Programme & Events
Sevak → Attendance
Reports → Finance
```

A domain integration dependency does not automatically mean the consumed
module must be completely implemented first.

---

# 6. Tier 1 — Foundation

```text
TIER 1
Foundation
```

Foundation is the recommended first vertical slice.

It provides common infrastructure used by the rest of the ERP.

The first implementation sequence is:

```text
Foundation Database
        ↓
Foundation API
        ↓
Foundation UI
        ↓
Validation
```

---

# 7. Foundation Exit Criteria

Before proceeding to Tier 2:

* Foundation database is operational;
* master-data framework is functional;
* required geographic hierarchy is functional;
* system settings are functional;
* ID sequence functionality is functional;
* Foundation API is usable;
* basic administrative UI is functional;
* database standards are validated.

---

# 8. Tier 2 — Person and Organization

```text
TIER 2
Person
Organization
```

These are the two major identity/structural domains.

They may be developed as two closely coordinated vertical slices.

Recommended sequence:

```text
Person
   DB → API → UI
        ↓
Organization
   DB → API → UI
```

or in parallel where the physical dependency analysis permits.

---

# 9. Person

Person provides the authoritative individual identity.

Downstream consumers include:

* Membership;
* Family;
* Attendance;
* Governance;
* Authentication;
* Kishor;
* Kumari;
* Sevak;
* UPBS;
* Finance-related identity;
* Programme & Events where participant identity is required.

---

# 10. Organization

Organization provides organizational identity and structure.

It is required by:

* Membership;
* Governance;
* Attendance;
* Administration scope;
* Finance;
* UPBS;
* Sevak;
* Programme & Events;
* Reports.

The distinction remains:

```text
Organization
    ≠
Event Location
```

Kendra, Sakha and Patha Chakra remain Organization Types.

---

# 11. Tier 2 Exit Criteria

Before Tier 3:

* Person identity operational;
* Organization hierarchy operational;
* organization types operational;
* required geographic relationships operational;
* APIs operational;
* basic UI operational;
* cross-module references validated.

---

# 12. Tier 3 — Heritage

```text
TIER 3
Heritage
```

Heritage consumes Foundation and Person-related capabilities.

Recommended vertical slice:

```text
Heritage DB
   ↓
Heritage API
   ↓
Heritage UI
   ↓
Validation
```

---

# 13. Tier 4 — Family and Membership

```text
TIER 4
Family
Membership
```

These modules depend strongly on Person and Organization.

Recommended sequence:

```text
Person
   ↓
Organization
   ↓
Family
   ↓
Membership
```

Membership is especially important because later operational modules
consume membership identity/status.

---

# 14. Membership Exit Criteria

Before proceeding to security/operational modules:

* Person-to-membership relationship operational;
* Organization membership relationship operational;
* membership status/lifecycle operational;
* required membership identifiers operational;
* API and UI validated.

---

# 15. Tier 5 — Authentication, Administration and Audit

```text
TIER 5
Authentication
Administration
Audit
```

These modules form the security and accountability layer.

---

# 16. Authentication

Authentication answers:

```text
WHO ARE YOU?
```

It provides:

* user identity;
* credential management;
* account lifecycle;
* authentication mechanisms.

Recommended sequence:

```text
Authentication DB
      ↓
Authentication API
      ↓
Authentication UI
```

---

# 17. Administration

Administration answers:

```text
WHAT CAN YOU DO?
WHERE CAN YOU DO IT?
```

It provides:

* roles;
* permissions;
* role-permission mapping;
* user-role mapping;
* organizational authorization scope.

Logical dependency:

```text
Authentication
      ↓
Administration
```

---

# 18. Audit

Audit provides centralized accountability.

However, Audit has a special DDL concern because many business tables
contain audit references.

Therefore:

```text
Audit
   =
Cross-cutting infrastructure
```

rather than treating it as an ordinary downstream module.

The exact physical audit-FK bootstrapping mechanism remains subject to the
database implementation plan.

---

# 19. Tier 5 Exit Criteria

Before operational modules proceed:

* authentication functional;
* authorization functional;
* organizational scope functional;
* audit mechanism functional;
* RBAC validated;
* authenticated API access operational;
* audit events demonstrably recorded.

---

# 20. Tier 6 — Attendance and Governance

```text
TIER 6
Attendance
Governance
```

These modules depend on the core identity and organizational structure.

They may be implemented as independent vertical slices.

---

# 21. Attendance

Attendance consumes:

* Person;
* Organization;
* Membership;
* Event context when Programme & Events becomes available.

Attendance remains authoritative for:

* attendance records;
* attendance calculations;
* attendance corrections;
* attendance reconciliation.

It does not become owned by Programme & Events.

---

# 22. Governance

Governance consumes:

* Person;
* Organization;
* Administration/RBAC;
* relevant membership context.

Governance remains responsible for governance-specific business rules.

---

# 23. Tier 6 Exit Criteria

* attendance core operational;
* governance core operational;
* authorization integrated;
* audit integrated;
* Person/Organization relationships validated.

---

# 24. Tier 7 — Programme & Events

```text
TIER 7
Programme & Events
```

**Status: PROPOSED IMPLEMENTATION POSITION**

Programme & Events is the common Event architecture.

It is intended to provide shared infrastructure for:

* recurring programmes;
* special events;
* Event lifecycle;
* organizer;
* Event Location;
* Event Session;
* domain-specific Event extensions.

---

# 25. Programme & Events Dependencies

The common Event layer consumes or integrates with:

```text
Person
Organization
Administration
Authentication
Audit
Attendance
Finance
Foundation
```

However, these are not all equivalent physical FK dependencies.

The exact DDL dependency must be resolved when Module #21 enters its
database phase.

---

# 26. Programme & Events Consumers

The common Event architecture is intended to support:

```text
Programme & Events
        │
        ├── UPBS
        ├── Kishor
        ├── Sevak
        ├── Reports
        └── Future Programmes
```

Existing domain-specific Event structures must be reconciled before
physical migration.

---

# 27. Why Programme & Events Is Not at the End

Programme & Events is infrastructure for several programme modules.

Therefore it should not be implemented after all programme modules if
those modules are expected to use the common Event model.

The preferred direction is:

```text
Core Identity
      ↓
Programme & Events
      ↓
Programme-specific modules
```

---

# 28. Programme & Events Entry Criteria

Before starting its database phase:

1. Module #21 ownership formally accepted.
2. Programme/Event architecture accepted.
3. UPBS Event reconciliation completed.
4. Kishor Event reconciliation completed.
5. Sevak Event reconciliation completed.
6. Event/Attendance integration resolved.
7. Event/Finance integration resolved.
8. Organizer model confirmed.
9. Event Location model confirmed.
10. Event Session model confirmed.

---

# 29. Tier 8 — Kumari, Kishor and Sevak

```text
TIER 8
Kumari
Kishor
Sevak
```

These are domain-specific programme/person lifecycle modules.

---

# 30. Kumari

Kumari consumes:

* Person;
* Organization;
* Membership;
* relevant guardian/family context.

It remains independent of Programme & Events where a specific
programme does not require Event integration.

---

# 31. Kishor

Kishor can consume:

```text
Programme & Events
```

for common Event identity and lifecycle.

Kishor-specific business rules remain owned by Kishor.

---

# 32. Sevak

Sevak can consume:

```text
Programme & Events
Attendance
Membership
Organization
Person
```

Sevak-specific intention, probable attendance, host Sakha and other
rules remain Sevak-owned.

---

# 33. Deferred Implementation Note

The previous project plan marked:

```text
Kumari
Kishor
Sevak
```

as deferred.

That status may remain during early core implementation if the project
chooses to prioritize foundational modules.

Deferral does not invalidate their dependency position.

---

# 34. Tier 9 — Mahila

```text
TIER 9
Mahila
```

Mahila currently has no dedicated physical table ownership in the
existing architecture.

It therefore does not require a conventional database-first vertical
slice equivalent to a table-owning module.

Its implementation may consist primarily of:

* configuration;
* workflows;
* permissions;
* domain integration;
* reporting;
* documentation.

---

# 35. Tier 10 — Publications and UPBS

```text
TIER 10
Publications
UPBS
```

Publications currently has no new common Event tables.

UPBS has significant domain-specific entities.

UPBS should consume the common Event architecture after the Event
reconciliation is complete.

---

# 36. UPBS Entry Criteria

Before UPBS physical implementation:

* common Event ownership resolved;
* UPBS Event reconciliation complete;
* UPBS-specific entities preserved;
* Finance integration defined;
* Organization relationships validated;
* Attendance integration validated.

---

# 37. Tier 11 — Finance

```text
TIER 11
Finance
```

Finance is a major independent business domain.

It is already documentation-complete.

Its implementation remains:

```text
Finance DB
   ↓
Finance API
   ↓
Finance UI
```

---

# 38. Finance Financial Year

Finance shall use:

```text
01 April → 31 March
```

for every financial-year process.

Calendar year shall not be substituted for Financial Year.

---

# 39. Finance Scope

Finance distinguishes:

```text
Organization
      ≠
Financial Scope
```

An Organization may have multiple Financial Scopes.

Special Events may also have dedicated Financial Scopes where required.

Finance remains the authoritative owner of those concepts.

---

# 40. Finance and Programme & Events

The relationship is:

```text
Event
  ↓
Financial Scope
  ↓
Finance
```

where financial management is required.

Finance does not become part of the Event module.

Programme & Events does not own financial transactions.

---

# 41. Tier 12 — Reports and Backup & Technical

```text
TIER 12
Reports
Backup & Technical
```

These are downstream/cross-cutting modules.

---

# 42. Reports

Reports consumes information from multiple modules.

It should therefore be implemented after the major source domains are
stable enough to support the required reports.

Reports does not own source-domain entities.

---

# 43. Backup & Technical

Backup & Technical is infrastructure-oriented.

Its position should be driven by:

* deployment requirements;
* backup requirements;
* operational readiness;
* recovery requirements;
* technical administration.

It is not a normal business FK dependency.

---

# 44. Implementation Tiers

The frozen implementation tier order is:

```text
TIER 1   Foundation

TIER 2   Person, Organization

TIER 3   Heritage

TIER 4   Family, Membership

TIER 5   Authentication, Administration, Audit

TIER 6   Attendance, Governance, Assets & Property

TIER 7   Programme & Events

TIER 8   Kumari, Kishor, Sevak

TIER 9   Mahila

TIER 10  Publications, UPBS

TIER 11  Finance

TIER 12  Reports, Backup & Technical
```

**Status: FROZEN (IMPLEMENTATION-TIER-001)**

### Freeze conditions

- Module count: 22
- Tier placement reflects physical/schema dependency, not business
  importance or workflow sequence
- Assets & Property at Tier 6: depends on Foundation + Person +
  Organization (all available by Tier 2); no hard FK to Finance
- Finance at Tier 11: owns financial transactions; upstream modules
  associate with Finance via optional cross-reference, not hard FK
  prerequisite
- P&E at Tier 7: common event capability after core identity/member
  foundations are established
- Correspondence remains an Administration capability (Tier 5), not a
  separate module
- Seva remains within the Sevak module (Tier 8), not a separate module
- Weekly Sangha Puja remains Attendance-owned (Tier 6), no P&E
  dependency
- Pending module-level DDL decisions (ORG-PENDING-001, MEM-PENDING-001,
  ATT-PENDING-001, P&E candidates) do not invalidate the tier freeze —
  they affect individual module DDL, not tier ordering

---

# 45. Important: Tier Does Not Mean Strict FK Order

For example:

```text
Programme & Events
       ↔
Finance
```

is an integration relationship.

It does not automatically mean:

```text
Finance MUST be completely implemented
before Programme & Events
```

unless the physical database design establishes such a requirement.

The same principle applies to Attendance.

---

# 46. DDL Ordering

The physical DDL phase must independently determine:

```text
Referenced Table
      ↓
Referencing Table
```

without circular FK creation.

Where a cross-module FK cannot be created immediately, the project shall
use the approved database strategy rather than violating the dependency
rules.

---

# 47. Audit Bootstrapping

Audit remains a known special case.

The implementation team must resolve the audit FK bootstrapping strategy
before generating final production DDL.

Possible strategies may include:

* staged FK creation;
* two-pass DDL;
* deferred cross-module constraint creation.

The final approach is not frozen by this document.

---

# 48. Vertical Slice Completion Criteria

A module is considered implemented only when:

### Database

* schema created;
* migrations reproducible;
* constraints validated;
* indexes validated;
* audit integration validated.

### API

* CRUD/business operations implemented;
* authorization integrated;
* validation implemented;
* error handling implemented;
* audit integration implemented.

### UI

* primary workflows implemented;
* authorization respected;
* validation implemented;
* errors surfaced;
* module workflows usable.

### Integration

* cross-module relationships tested;
* existing modules unaffected;
* audit verified;
* reporting impact verified where applicable.

---

# 49. Module Implementation Template

Every module should follow:

```text
MODULE
│
├── 1. Database
│     ├── migration
│     ├── constraints
│     ├── indexes
│     └── seed/reference data
│
├── 2. API
│     ├── endpoints
│     ├── validation
│     ├── authorization
│     └── audit
│
├── 3. UI
│     ├── list
│     ├── detail
│     ├── create/edit
│     └── workflow
│
└── 4. Integration
      ├── cross-module tests
      ├── security tests
      └── regression tests
```

---

# 50. Recommended First Implementation

The first actual vertical slice should be:

```text
TIER 1
FOUNDATION
```

Sequence:

```text
Foundation Database
        ↓
Foundation API
        ↓
Foundation UI
        ↓
Foundation Integration / Validation
```

Only after Foundation is operational should the project move to Person
and Organization.

---

# 51. First Vertical Slice Does Not Mean All Foundation Features

Foundation implementation should be limited to the approved Foundation
scope.

Do not use the first slice as an opportunity to introduce unrelated
future infrastructure.

The frozen Foundation table design and business rules remain the
authority.

---

# 52. Second Vertical Slice

After Foundation:

```text
PERSON
```

Recommended:

```text
Person Database
      ↓
Person API
      ↓
Person UI
      ↓
Person Validation
```

---

# 53. Third Vertical Slice

Then:

```text
ORGANIZATION
```

Recommended:

```text
Organization Database
      ↓
Organization API
      ↓
Organization UI
      ↓
Organization Validation
```

---

# 54. Cross-Module Validation

After each vertical slice:

```text
New Module
    ↓
Existing Modules
    ↓
Dependency Tests
    ↓
Regression Tests
```

This is particularly important for:

* Person;
* Organization;
* Membership;
* Authentication;
* Attendance;
* Finance;
* Programme & Events.

---

# 55. Programme & Events Special Gate

Programme & Events should not be started simply because it appears in
Tier 7.

Before implementation, its architecture must be promoted from:

```text
PROPOSED MODULE #21
```

to:

```text
FROZEN MODULE #21
```

and the module-specific implementation documents must be created under:

```text
docs/03_Solution/modules/programmes_events/
```

At that point its database/API/UI work can begin.

---

# 56. Finance Special Gate

Finance already has its architecture documentation set.

Before implementation:

```text
Finance documentation
        ↓
DDL dependency verification
        ↓
Finance Database
        ↓
Finance API
        ↓
Finance UI
```

All Finance implementation must preserve:

```text
Financial Year = 01 April – 31 March
```

and the distinction:

```text
Financial Scope ≠ Organization
```

---

# 57. No Calendar-Year Finance

The implementation must not introduce:

```text
January → December
```

as the primary ERP financial-year model.

Any Event occurring between January and March belongs to the Financial
Year that began the previous April.

---

# 58. Special Events

Special Events use the common Event architecture.

They do not require a separate implementation tier.

Where finance is required:

```text
Special Event
      ↓
Financial Scope
      ↓
Finance
```

---

# 59. Annual Recurring Programmes

The following can use the common Programme & Event architecture:

```text
Kishor Puja
Janmoutsaba
Saradiya Alochana Chakra
UPBS
Rasoutsaba
```

The annual occurrence is an Event Instance.

The Programme Type remains the reusable definition.

---

# 60. Organizer Rules

The common Event architecture must preserve:

```text
Organizer → Organization
```

Examples:

```text
Kishor Puja
    Organizer → Kendra

Janmoutsaba
    Organizer → Kendra

Saradiya Alochana Chakra
    Organizer → Kendra

UPBS
    Organizer → Kendra

Rasoutsaba
    Organizer → Ekamra Saraswata Sangha
```

These are logical relationships.

---

# 61. Organization Type Rules

The following remain Organization concepts:

```text
Kendra
Sakha
Patha Chakra
```

They shall not be implemented as:

```text
Event Location Type
```

or:

```text
Venue Type
```

---

# 62. Patha Chakra Transformation

Patha Chakra is a permanent Organization.

It may later be transformed into a Sakha through Organization lifecycle
rules.

This does not alter the Event lifecycle.

---

# 63. Future Programme Types

A future programme may be added without automatically creating a new
module.

The evaluation should be:

```text
Does it need additional domain entities/rules?
        │
   ┌────┴────┐
   │         │
  No        Yes
   │         │
Common       Domain Module
Event        / Extension
```

---

# 64. Future Module Principle

A new module should be created only where there is genuine domain
ownership requiring:

* independent entities;
* business rules;
* lifecycle;
* authorization;
* reporting;
* workflows;
* or substantial domain-specific behavior.

A programme name alone does not justify a module.

---

# 65. Dependency Review Before Each Module

Before starting a module, confirm:

```text
1. Frozen design exists
2. Table design exists
3. Direct FK dependencies identified
4. Runtime dependencies identified
5. Authorization dependencies identified
6. Audit dependencies identified
7. Integration points identified
```

---

# 66. Change Control

If implementation discovers a dependency not present in this document:

```text
Implementation discovery
        ↓
Dependency review
        ↓
Architecture/documentation update
        ↓
Approval
        ↓
Implementation
```

Do not silently change the dependency architecture in code.

---

# 67. No Premature Physical Design

This document does not create physical database tables.

In particular, it does not authorize:

```text
event
programme_type
event_session
event_location
```

or any other Programme & Event tables.

---

# 68. No Premature API Design

No API endpoint is frozen by this document.

API contracts are created during the module's vertical implementation
phase.

---

# 69. No Premature UI Design

No UI screen is frozen by this document.

UI work begins only after the module database and API contracts are
sufficiently stable.

---

# 70. Current Implementation Spine

The recommended high-level spine is:

```text
Foundation
    ↓
Person
    ↓
Organization
    ↓
Heritage
    ↓
Family / Membership
    ↓
Authentication / Administration / Audit
    ↓
Attendance / Governance
    ↓
Programme & Events
    ↓
Kumari / Kishor / Sevak
    ↓
Mahila
    ↓
Publications / UPBS
    ↓
Finance
    ↓
Reports / Backup & Technical
```

This is a **recommended implementation grouping**, not a statement that
every arrow is a physical FK dependency.

---

# 71. Current Tier Status

```text
TIER 1
Foundation
STATUS: RECOMMENDED FIRST

TIER 2
Person, Organization
STATUS: RECOMMENDED

TIER 3
Heritage
STATUS: RECOMMENDED

TIER 4
Family, Membership
STATUS: RECOMMENDED

TIER 5
Authentication, Administration, Audit
STATUS: RECOMMENDED

TIER 6
Attendance, Governance
STATUS: RECOMMENDED

TIER 7
Programme & Events
STATUS: PROPOSED / MODULE #21 PENDING FREEZE

TIER 8
Kumari, Kishor, Sevak
STATUS: DEFERRED / DOMAIN IMPLEMENTATION

TIER 9
Mahila
STATUS: CONFIGURATION / INTEGRATION

TIER 10
Publications, UPBS
STATUS: RECOMMENDED

TIER 11
Finance
STATUS: DOCUMENTATION COMPLETE / IMPLEMENTATION PENDING

TIER 12
Reports, Backup & Technical
STATUS: DOWNSTREAM / INFRASTRUCTURE
```

---

# 72. First Implementation Decision

The architecture phase is now sufficiently mature to begin the first
vertical slice.

The recommended first module is:

```text
FOUNDATION
```

The implementation work should therefore move to:

```text
Foundation
    ↓
Database
    ↓
API
    ↓
UI
```

---

# 73. Foundation Database Phase

Before writing SQL, review and freeze:

* Foundation table design;
* Foundation business rules;
* Foundation ERD;
* database standards;
* audit-column strategy;
* master-data strategy;
* geographic hierarchy;
* ID sequence strategy.

Only then generate migrations.

---

# 74. Foundation API Phase

After database validation:

* define API contracts;
* implement service layer;
* implement validation;
* implement authorization where applicable;
* implement audit;
* test database/API integration.

---

# 75. Foundation UI Phase

After API contracts stabilize:

* implement Foundation administrative screens;
* master data screens;
* geographic management;
* system settings;
* sequence/configuration management where applicable.

---

# 76. Foundation Completion Gate

Foundation is complete only when:

```text
Database ✓
API      ✓
UI       ✓
Tests    ✓
Audit    ✓
Security ✓
Integration ✓
```

---

# 77. Architecture Freeze Point

After this document is approved:

```text
Architecture Planning
        ↓
IMPLEMENTATION
```

New architecture documents should only be introduced when an actual
architectural issue is discovered.

---

# 78. Final Recommendation

The project should now transition from planning to implementation.

The recommended immediate sequence is:

```text
1. Freeze implementation dependency order
2. Select Foundation
3. Foundation Database
4. Foundation API
5. Foundation UI
6. Foundation validation
7. Move to Person
```

No Programme & Event physical tables should be created at this stage.

No Finance physical implementation should be started merely because
Finance is documentation-complete.

---

# 79. Status

**DOCUMENT STATUS:**  
FROZEN — IMPLEMENTATION TIER ORDER

**VERSION:**  
1.0.0

**MODULE INVENTORY:**  
22

**IMPLEMENTATION STRATEGY:**  
VERTICAL SLICE

**TIER MODEL:**  
12 FROZEN TIERS (IMPLEMENTATION-TIER-001)

**FIRST IMPLEMENTATION:**  
FOUNDATION

**PROGRAMME & EVENTS:**  
MODULE #21 — RECONCILIATION COMPLETE (SOL-EVT-007) / IMPLEMENTATION DEFERRED TO TIER 11

**ASSETS & PROPERTY:**  
MODULE #22 — DOCUMENTATION COMPLETE (SOL-AP-001 to SOL-AP-005) / IMPLEMENTATION AT TIER 6

**FINANCE:**  
DOCUMENTATION COMPLETE / IMPLEMENTATION DEFERRED TO TIER 10

**IMPLEMENTATION TIERS:**  
FROZEN (IMPLEMENTATION-TIER-001)

**PHYSICAL DDL:**  
FOUNDATION TIER 1 COMPLETE (SOL-ARCH-010)

**API:**  
NOT STARTED

**UI:**  
NOT STARTED

**NEXT:**  
FOUNDATION API LAYER → FOUNDATION UI → TIER 2 (PERSON + ORGANIZATION)
