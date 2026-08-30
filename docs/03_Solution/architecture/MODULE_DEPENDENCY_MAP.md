# NSS ERP — Module Dependency Map

**Document ID:** SOL-ARCH-007  
**Version:** 0.1.0  
**Status:** DRAFT — DEPENDENCY MAP  
**Parent Documents:**
- DATABASE_DESIGN_STANDARDS.md
- Project Module Inventory
- Programme & Event Domain Model
- Programme & Event Cross-Module Review
- Individual Module Design / ERD / Business Rules / Table Design documents

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the dependency relationships among the NSS ERP
modules.

It distinguishes three different concepts:

1. **Logical/domain dependency**
2. **Runtime/service dependency**
3. **Physical DDL/FK dependency**

These must not be treated as identical.

A module may consume another module's business capability without
requiring a physical foreign key to that module.

---

# 2. Governing Database Principle

The project database standard requires:

```text
Module A
    │
    └── FK → Module B internal PK
```

Cross-module foreign keys:

* reference the internal PK;
* do not reference business IDs;
* require the referenced table to exist before the referencing table;
* must not introduce circular DDL dependencies;
* must have explicit ON DELETE behavior;
* do not transfer ownership of the referenced entity.

Therefore the dependency graph used for **DDL sequencing** is not
necessarily identical to the broader application dependency graph.

---

# 3. Module Inventory

The current documented module inventory is:

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

**Important:** Module number is an inventory identifier, not an
implementation sequence number.

---

# 4. Dependency Categories

## 4.1 HARD-DB

A physical FK dependency exists or is expected.

Example:

```text
Membership
    ↓ FK
Person
```

The referenced table must exist before the referencing table's FK can be
created.

---

## 4.2 RUNTIME

The module consumes another module's service or business capability,
but a direct physical FK is not necessarily required.

Example:

```text
Reports
    ↓
Attendance
```

Reports consumes Attendance data but does not own Attendance.

---

## 4.3 DOMAIN

The module depends on another domain's business rules or authoritative
identity.

Example:

```text
Programme & Events
    ↓
Organization
```

because Event Organizer is an Organization.

---

## 4.4 CROSS-CUTTING

The module consumes shared platform infrastructure.

Examples:

```text
Authentication
Administration
Audit
Foundation
```

These relationships should not automatically be interpreted as direct
business FK dependencies.

---

# 5. Foundation

Foundation is the base infrastructure module.

It provides common mechanisms including:

* master data;
* geographic hierarchy;
* system configuration;
* centralized business identifier sequencing.

The project standard identifies `id_sequence_master` as the Foundation
sequence mechanism and `master_category` / `master_data` as the generic
master framework.

Therefore:

```text
Foundation
    ↑
    │
Many business modules
```

Foundation is a major upstream dependency.

---

# 6. Person

Person is the authoritative identity domain for individuals.

Modules requiring individual identity consume Person.

```text
Person
   ↑
   ├── Membership
   ├── Family
   ├── Governance
   ├── Attendance
   ├── Kishor
   ├── Kumari
   ├── Sevak
   ├── UPBS
   └── Programme & Events where participant identity is required
```

The project principle remains:

```text
Person ≠ Member
```

---

# 7. Organization

Organization is the authoritative organizational identity domain.

It includes organizational concepts such as:

```text
Kendra
Anchalika
Zilla
Sakha
Patha Chakra
```

The Programme & Event architecture explicitly confirms that these are
Organization concepts, not Event Location Types. 

Organization therefore becomes an important dependency for:

* Governance;
* Membership;
* Attendance;
* Administration scope;
* Finance;
* Programme & Events;
* UPBS;
* Sevak;
* Reports.

---

# 8. Membership

Membership depends on Person and Organization.

Logical relationship:

```text
Person
   │
   ▼
Membership
   │
   ▼
Organization
```

The existing database standard already identifies Membership → Person and
Organization → Foundation as common cross-module relationships. 

---

# 9. Family

Family consumes Person identity and membership context where applicable.

Conceptually:

```text
Person
   ↓
Family
   ↓
Membership / youth-domain visibility
```

Family does not own Person or Membership.

---

# 10. Attendance

Attendance consumes:

* Person;
* Organization;
* Membership context where applicable;
* Event context where applicable.

The existing common database standards identify Attendance references to
Person and Organization. 

The common Programme & Event architecture explicitly preserves
Attendance as a separate owner.

Therefore:

```text
Programme & Events
       ↓
    Event context
       ↓
   Attendance
```

does not mean Programme & Events owns attendance.

---

# 11. Authentication

Authentication provides identity verification and credential security.

It depends logically on Person/Membership identity according to the
existing authentication design.

Authentication owns credential-specific security.

It does not own:

* authorization roles;
* permissions;
* organizational scope.

---

# 12. Administration

Administration owns the authorization/RBAC side of the security model.

The existing split is:

```text
Authentication
    ↓
WHO ARE YOU?

Administration
    ↓
WHAT CAN YOU DO?
WHERE CAN YOU DO IT?
```

Administration therefore consumes Authentication identity.

Event authorization uses the existing Administration/RBAC framework and
does not create an independent permission architecture.

## 12.1 Correspondence Register Capability

Administration also owns the Correspondence Register (CORR-DECISION-003),
which introduces three additional tables:

```text
correspondence
correspondence_document
correspondence_finance_reference
```

This capability adds the following dependencies to Administration:

* Person (FK: sender, recipient, responsible person)
* Organization (FK: sender, recipient, responsible organization)
* Foundation.master_data (FK: medium, status)
* Foundation.document_master (FK: via correspondence_document)
* Foundation.id_sequence_master (application/service — no FK)
* Finance.financial_transaction (optional FK via correspondence_finance_reference — deferred)

The Correspondence Register is a reusable platform capability (CORR-ARCH-002).
Any module may use it to associate official communications with its business
records without transferring ownership to Administration. 

---

# 13. Audit

Audit is a cross-cutting module.

It consumes actor identity and records system/business events according
to the centralized audit architecture.

The project standards explicitly identify Authentication as a common
cross-module audit-identity dependency while leaving the exact audit FK
bootstrapping order open. 

Therefore:

```text
Many modules
    ↓
Audit
```

should not automatically be interpreted as:

```text
Audit must be physically created first
```

because the project already recognizes an audit FK bootstrapping problem.

---

# 14. Governance

Governance consumes:

* Person;
* Organization;
* Administration/RBAC where authorization is required.

Conceptually:

```text
Person
   ↓
Governance
   ↑
Organization
```

Governance does not own Person or Organization.

---

# 15. Heritage

Heritage consumes Foundation and Person-related identity/document
capabilities according to its frozen design.

It does not create duplicate Person identity.

---

# 16. Kishor

Kishor consumes the common identity and organizational domains and may
consume the common Programme & Event architecture.

The common Event model represents:

```text
Programme Type
    KISHOR_PUJA
       ↓
Event Instance
    Kishor Puja 2027
```

Kishor-specific participant and programme rules remain Kishor-owned.


Therefore:

```text
Programme & Events
        ↓
Kishor
```

is primarily a domain/runtime relationship, not automatically a
physical FK direction.

---

# 17. Kumari

Kumari consumes:

* Person;
* Organization;
* Membership;
* Family context where applicable.

It does not own those identity domains.

---

# 18. Mahila

Mahila currently has no independent physical table ownership requiring
a separate database dependency layer in the common architecture.

It consumes relevant:

* Organization;
* Person;
* Membership;
* Governance

capabilities.

---

# 19. Sevak

Sevak consumes:

* Person;
* Membership;
* Organization;
* Attendance;
* Administration/RBAC;
* Programme/Event infrastructure where the common model is adopted.

Existing Sevak rules explicitly distinguish:

```text
Eligibility
≠
Visibility
≠
Intention
≠
Probable Attendance
≠
Actual Attendance
```

and keep Attendance separate. 

Sevak also has its own Event-specific rules including host Sakha,
publication, cancellation, rescheduling, intention and reconciliation.

Therefore the common Event layer must not erase Sevak-specific behavior.

---

# 20. UPBS

UPBS consumes:

* Person;
* Organization;
* Membership;
* Programme & Events;
* Finance where required.

The existing UPBS design already has `upbs_event` plus
UPBS-specific entities such as:

```text
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

These remain UPBS-owned until explicit reconciliation.

The common Event model provides the common Event context rather than
silently replacing these structures. 

---

# 21. Finance

Finance is an independent business domain.

The Programme & Event architecture supports:

```text
Programme Type
      ↓
Event Instance
      ↓
Financial Scope
      ↓
Finance
```

Finance remains authoritative for:

* Financial Year;
* Financial Scope;
* funds;
* transactions;
* receipts;
* payments;
* transfers;
* financial lifecycle.

The Event architecture explicitly states that financial activity uses
the Financial Year model:

```text
01 April → 31 March
```

and not calendar-year accounting. 

---

# 22. Finance vs Event Dependency

This relationship must be interpreted carefully.

```text
Event ─────► Financial Scope
```

does not mean:

```text
Event owns Finance
```

and Finance does not own Event.

They are separate domains joined through an integration relationship.

The exact physical FK direction is therefore a DDL-phase decision unless
already frozen in the Finance table design.

---

# 23. Reports

Reports is primarily a consumer.

It may read:

* Membership;
* Attendance;
* Finance;
* Governance;
* Organization;
* Programme & Events;
* UPBS;
* Kishor;
* Sevak.

Therefore:

```text
Reports
    ↓
reads from many domains
```

does not imply that all those domains physically depend on Reports.

Reports should normally be treated as a downstream runtime consumer.

---

# 24. Backup & Technical

Backup & Technical is cross-cutting infrastructure.

It does not become a business dependency of every module merely because
it backs up their data.

Therefore:

```text
Business Modules
      ↓
Backup / Technical infrastructure
```

is an infrastructure relationship rather than a normal business FK
dependency.

---

# 25. Programme & Events — Upstream Dependencies

The proposed Programme & Events domain consumes:

### Identity

```text
Person
```

where individual identity is required.

### Organization

```text
Organization
```

for Organizer and organizational context.

### Authorization

```text
Administration
Authentication
```

for authenticated and authorized actions.

### Audit

```text
Audit
```

for lifecycle auditing.

### Attendance

```text
Attendance
```

for actual attendance integration.

### Finance

```text
Finance
```

for Financial Scope and financial integration where required.

### Foundation

```text
Foundation
```

for approved common/master infrastructure where applicable.

---

# 26. Programme & Events — Downstream Consumers

The proposed common Event layer is intended to be consumed by:

```text
Kishor
UPBS
Sevak
Attendance
Finance
Reports
future programmes
```

However, the direction differs by relationship.

For example:

```text
Event → Attendance context
Event → Financial Scope
```

does not mean Attendance or Finance are subordinate modules.

---

# 27. Core Logical Dependency Graph

The current logical architecture is:

```text
                         FOUNDATION
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
             PERSON     ORGANIZATION   AUTHENTICATION
               │             │             │
               │             │             ▼
               │             │        ADMINISTRATION
               │             │             │
               ├──────┬──────┴─────────────┤
               │      │                    │
               ▼      ▼                    ▼
          MEMBERSHIP  GOVERNANCE          AUDIT
               │
       ┌───────┼────────┬─────────┐
       ▼       ▼        ▼         ▼
    FAMILY   KISHOR   KUMARI    SEVAK
                 \       |        /
                  \      |       /
                   ▼     ▼      ▼
                  PROGRAMME & EVENTS
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          ATTENDANCE    FINANCE      REPORTS
              │
              ▼
          DOMAIN REPORTING
```

This is a **logical relationship map**, not a DDL creation order.

---

# 28. Programme & Events — Important Direction

The common Event layer is intended to become infrastructure for domain
consumers.

Therefore:

```text
Programme & Events
       ↓
   UPBS / Kishor / Sevak
```

is a **runtime/domain dependency**.

But if an existing UPBS/Kishor/Sevak table already contains an Event FK,
the physical FK dependency may be:

```text
Common Event table
       ↓
UPBS extension
```

The exact direction must be resolved during physical reconciliation.

---

# 29. UPBS Reconciliation Requirement

Existing `upbs_event` must not be assumed to become a direct extension
table automatically.

Before physical implementation:

1. map existing UPBS event fields;
2. identify common Event fields;
3. identify UPBS-specific fields;
4. identify existing FK relationships;
5. determine migration strategy;
6. preserve historical data.

The common Event domain model explicitly requires this reconciliation. 

---

# 30. Kishor Reconciliation Requirement

The same principle applies to Kishor.

No existing Kishor Event structure should be removed merely because a
common Event architecture exists.

---

# 31. Sevak Reconciliation Requirement

Sevak requires especially careful reconciliation because its frozen rules
include:

* manual Event creation;
* host Sakha;
* configurable frequency;
* intention;
* probable attendance;
* actual attendance;
* cancellation;
* rescheduling;
* reconciliation;
* completion;
* historical preservation. 

These rules must remain intact.

---

# 32. Attendance Dependency Clarification

The Event architecture must not create a circular dependency:

```text
Event
   ↓
Attendance
   ↓
Event
```

If physical FKs would produce such a cycle, the DDL design must use the
project's approved dependency-resolution strategy rather than violating
the no-circular-FK rule.

---

# 33. Finance Dependency Clarification

Likewise, Finance and Event must not be forced into a physical circular
FK simply because both domains reference one another logically.

The logical relationship:

```text
Event
   ↔
Financial Scope
```

must be translated into a non-circular physical model during DDL design.

---

# 34. Audit Dependency Clarification

Audit is a known special case.

The project database standards already identify:

```text
Audit FK bootstrapping order
```

as an open DDL issue because audit columns may reference identity
structures whose own creation depends on other modules.

Therefore Audit should not be artificially moved to the beginning or end
of the implementation sequence without resolving that bootstrapping
strategy.

---

# 35. Physical DDL Dependency Rules

The eventual DDL sequence shall obey:

```text
Referenced table
       ↓
Referencing table
```

and:

```text
NO CIRCULAR FK CREATION
```

The project standard explicitly requires this. 

---

# 36. DDL Dependency vs Implementation Order

These are different:

### DDL Dependency

Determines:

> Which table must exist before another table's FK can be created?

### Module Implementation Order

Determines:

> Which module should we build as a complete vertical slice first?

A module can therefore be implemented before another module even when
some cross-module FK is deferred or introduced later, provided the
implementation strategy explicitly supports it.

---

# 37. Vertical-Slice Principle

The project's agreed implementation approach is:

```text
Module
   ↓
Database
   ↓
API
   ↓
UI
```

This means we should not build:

```text
All DB
   ↓
All API
   ↓
All UI
```

Instead:

```text
Module A
   DB → API → UI

Module B
   DB → API → UI
```

Cross-module interfaces are then reconciled as dependencies mature.

---

# 38. Recommended Core Implementation Spine

Based on the currently frozen dependencies, the core vertical sequence
remains:

```text
Foundation
    ↓
Person
    ↓
Organization
    ↓
Family / Membership
    ↓
Authentication
    ↓
Administration
    ↓
Audit
    ↓
Attendance / Governance
```

The exact ordering of Family vs Membership, Authentication vs other
security components, and Audit bootstrapping remains subject to the
individual DDL dependency decisions.

---

# 39. Programme & Events Position

Programme & Events should not simply be placed at the end of the
project.

Its role is:

```text
Core domains
      ↓
Programme & Events
      ↓
UPBS / Kishor / Sevak / future programmes
```

Therefore its implementation should occur after the minimum upstream
domains needed to give it stable identity and authorization semantics.

---

# 40. Finance Position

Finance should remain an independent vertical slice.

It should not be physically embedded inside Programme & Events.

The relationship should be:

```text
Finance
   ↕
Programme & Events
```

with each module retaining ownership of its own business data.

---

# 41. Recommended Tier Concept

The current tier concept should therefore be understood as:

```text
TIER 1
Foundation

TIER 2
Person, Organization

TIER 3
Heritage

TIER 4
Family, Membership

TIER 5
Authentication, Administration, Audit

TIER 6
Attendance, Governance

TIER 7
Programme & Events

TIER 8
Kumari, Kishor, Sevak

TIER 9
Mahila

TIER 10
Publications, UPBS

TIER 11
Finance

TIER 12
Reports, Backup & Technical
```

**Status: PROPOSED — NOT YET FROZEN.**

This is an implementation grouping, not a strict FK graph.

---

# 42. Why Programme & Events Is Before UPBS/Kishor/Sevak

The common Event architecture is intended to provide shared Event
infrastructure for those domains.

Existing domain rules can remain intact while consuming the common Event
identity.

Therefore:

```text
Programme & Events
        ↓
UPBS
Kishor
Sevak
```

is the preferred logical direction.

---

# 43. Why Programme & Events Does Not Own Attendance

Even though Attendance may consume Event context:

```text
Event
   ↓
Attendance
```

Attendance remains the authoritative owner of actual attendance.

This is explicitly preserved by the Programme/Event architecture. 

---

# 44. Why Programme & Events Does Not Own Finance

Similarly:

```text
Event
   ↓
Financial Scope
   ↓
Finance
```

means Event identifies the financial context.

Finance owns:

```text
Financial Scope
Funds
Transactions
Receipts
Payments
Transfers
```

and all financial activity remains on the 01 April–31 March Financial
Year model. 

---

# 45. Why Organization Comes Before Programme & Events

Every Event Organizer is an Organization:

```text
Event
   ↓
Organizer
   ↓
Organization
```

The common Event architecture explicitly defines Organizer as an
Organization and separates it from physical Event Location. 

Therefore Organization is a fundamental upstream dependency.

---

# 46. Why Patha Chakra Does Not Become an Event Dependency

Patha Chakra is an Organization Type.

Its future transformation:

```text
Patha Chakra
      ↓
Sakha
```

is an Organization lifecycle concern.

It does not require Programme & Events to own or implement that
transformation.

---

# 47. Reports as Downstream Consumer

Reports should normally be implemented after the source domains it must
report on are sufficiently stable.

Therefore:

```text
Source Modules
      ↓
Reports
```

is preferable to making Reports an upstream dependency.

---

# 48. Backup as Infrastructure

Backup & Technical is not a normal business-domain dependency.

It supports the entire application.

Therefore its position in the implementation sequence should be based on
technical/infrastructure requirements rather than business FK ordering.

---

# 49. Authentication / Administration Special Case

Authentication and Administration are separate modules.

The existing project design distinguishes:

```text
Authentication
    WHO ARE YOU?

Administration
    WHAT CAN YOU DO?
    WHERE CAN YOU DO IT?
```

Therefore:

```text
Authentication
       ↓
Administration
```

is the normal logical direction.

---

# 50. Audit Special Case

Audit is cross-cutting and cannot be treated as a simple ordinary
downstream module because audit columns are present across business
tables.

The project standards explicitly leave the audit FK bootstrapping order
open.

Therefore:

```text
Audit dependency
    = CROSS-CUTTING
```

rather than:

```text
Audit = simply Module #9
```

for DDL purposes.

---

# 51. Dependency Matrix

| Module             | Foundation | Person | Organization | Membership | Auth/Admin | Attendance | Finance | Events |
| ------------------ | ---------: | -----: | -----------: | ---------: | ---------: | ---------: | ------: | -----: |
| Foundation         |          — |        |              |            |            |            |         |        |
| Person             |          ✓ |      — |              |            |            |            |         |        |
| Organization       |          ✓ |        |            — |            |            |            |         |        |
| Family             |          ✓ |      ✓ |              |          ✓ |            |            |         |        |
| Membership         |          ✓ |      ✓ |            ✓ |          — |            |            |         |        |
| Authentication     |          ✓ |      ✓ |              |          ✓ |          — |            |         |        |
| Administration     |          ✓ |      ✓ |            ✓ |            |          ✓ |            |      ✓* |        |
| Audit              |          ✓ |        |              |            |          ✓ |            |         |        |
| Attendance         |          ✓ |      ✓ |            ✓ |          ✓ |          ✓ |          — |         |      ✓ |
| Governance         |          ✓ |      ✓ |            ✓ |            |          ✓ |            |         |        |
| Kishor             |          ✓ |      ✓ |            ✓ |          ✓ |          ✓ |          ✓ |         |      ✓ |
| Kumari             |          ✓ |      ✓ |            ✓ |          ✓ |          ✓ |            |         |        |
| Sevak              |          ✓ |      ✓ |            ✓ |          ✓ |          ✓ |          ✓ |         |      ✓ |
| UPBS               |          ✓ |      ✓ |            ✓ |          ✓ |          ✓ |          ✓ |       ✓ |      ✓ |
| Finance            |          ✓ |        |            ✓ |            |          ✓ |            |       — |      ✓ |
| Programme & Events |          ✓ |     ✓* |            ✓ |            |          ✓ |         ✓* |      ✓* |      — |
| Reports            |          ✓ |     ✓* |           ✓* |         ✓* |         ✓* |         ✓* |      ✓* |     ✓* |
| Backup & Technical |          ✓ |        |              |            |            |            |         |        |

`*` indicates primarily runtime/domain consumption or integration rather
than a confirmed physical FK.

---

# 52. Important Interpretation of the Matrix

A checkmark does **not** automatically mean:

```text
physical FK
```

It means the module has a meaningful logical/runtime dependency or
integration relationship.

The physical table design will determine which relationships become
actual FKs.

---

# 53. Current Hard Dependency Candidates

The strongest known physical dependency relationships include:

```text
Person
   ↑
Membership

Foundation
   ↑
Organization

Person
   ↑
Governance

Organization
   ↑
Governance

Person
   ↑
Attendance

Organization
   ↑
Attendance

Person
   ↑
Administration (Correspondence Register)

Organization
   ↑
Administration (Correspondence Register)

Foundation.document_master
   ↑
Administration (Correspondence Register)
```

These align with the existing database standards. 

Additional module-specific FKs are defined by each frozen table-design
document.

---

# 54. Programme & Events Hard Dependency Candidates

At the common architecture level, likely physical references include:

```text
Event
   → Organization
```

and potentially:

```text
Event
   → Programme Type
Event
   → Location
```

while:

```text
Event
   ↔ Attendance
Event
   ↔ Finance
```

require explicit physical design to avoid circular dependencies.

These are **not physical tables yet**.

---

# 55. No New Tables from This Document

This dependency map does not authorize creation of:

```text
event
programme_type
event_session
event_location
event_lifecycle_history
```

or any other new physical entity.

The Programme & Event architecture is still at the architecture/inventory
stage.

---

# 56. No API Dependency Contract Yet

This document does not freeze API endpoints.

API contracts remain part of the later:

```text
Database
    ↓
API
```

phase.

---

# 57. No UI Dependency Contract Yet

The UI will consume APIs and module capabilities later.

No UI implementation dependency is frozen by this document.

---

# 58. Current Dependency Decision

The project should adopt the following distinction:

```text
MODULE NUMBER
    ≠
IMPLEMENTATION ORDER
    ≠
DDL ORDER
    ≠
RUNTIME DEPENDENCY
```

This is the central purpose of this document.

---

# 59. Recommended Implementation Principle

For each module:

```text
1. Confirm module design is frozen enough
2. Resolve its direct physical dependencies
3. Build its database layer
4. Build its API
5. Build its UI
6. Integrate with already-built modules
7. Run cross-module validation
```

This preserves the vertical-slice strategy.

---

# 60. Programme & Events Implementation Gate

Before Programme & Events enters its database phase, the following must
be completed:

1. Module #21 ownership formally accepted.
2. Existing UPBS Event structure reconciled.
3. Existing Kishor Event structure reconciled.
4. Existing Sevak Event structure reconciled.
5. Event ↔ Attendance physical relationship resolved.
6. Event ↔ Finance physical relationship resolved.
7. Event Location ownership resolved.
8. Programme Type physical representation resolved.
9. Event Session physical representation resolved.
10. Audit FK strategy applicable to Event tables resolved.

---

# 61. Current Status

```text
MODULE INVENTORY:
22 modules including Programme & Events and Assets & Property

MODULE #21:
ARCHITECTURALLY JUSTIFIED
RECONCILIATION COMPLETE (SOL-EVT-007)

MODULE #22:
DOCUMENTATION COMPLETE (SOL-AP-001 to SOL-AP-005)

LOGICAL DEPENDENCY MAP:
DEFINED

RUNTIME DEPENDENCIES:
DEFINED AT HIGH LEVEL

PHYSICAL FK DEPENDENCIES:
PARTIALLY DEFINED

DDL ORDER:
NOT FROZEN

IMPLEMENTATION TIERS:
FROZEN (IMPLEMENTATION-TIER-001, SOL-ARCH-008 v1.0.0)

DATABASE IMPLEMENTATION:
NOT STARTED

API:
NOT STARTED

UI:
NOT STARTED
```

---

# 62. Next Step

The next action should **not** be creating Programme & Event tables.

The next action should be:

```text
Review the 22-module dependency map
        ↓
Resolve any dependency-order conflicts
        ↓
Freeze implementation tiers
        ↓
Select the first module
        ↓
Begin:
    Database
       ↓
    API
       ↓
    UI
```

The first actual implementation module should then be selected from the
dependency-safe foundation spine.

# End of Document
