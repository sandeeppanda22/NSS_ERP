# NSS ERP — Programmes & Events Cross-Module Review

**Document ID:** SOL-EVT-006  
**Version:** 1.1.0  
**Status:** FROZEN — CROSS-MODULE REVIEW COMPLETE  
**Parent Documents:**
- SOL-EVT-001 — Programme & Event Domain Model
- SOL-EVT-002 — Event Entity Reconciliation
- SOL-EVT-003 — Programmes & Events Logical ERD
- SOL-EVT-004 — Programmes & Events Business Rules
- SOL-EVT-005 — Programmes & Events Lifecycle

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document reviews the proposed common Programme & Event architecture
against the existing NSS ERP modules.

The purpose is to determine:

1. whether the common Event model is compatible with existing modules;
2. which existing module remains authoritative for each related concern;
3. whether existing domain-specific Event concepts can map to the common
   model;
4. whether any existing business rule would be lost;
5. whether a standalone Programme & Events module is justified;
6. whether the architecture should proceed toward physical implementation.

This is a cross-module review.

It does **not** create or freeze database tables.

---

# 2. Review Principle

The review follows the established project ownership principle:

> A common framework may provide shared infrastructure, but it shall not
> absorb domain-specific business ownership merely to simplify the data
> model.

Therefore the review distinguishes:

```text
COMMON EVENT
     │
     ├── shared Event identity
     ├── shared lifecycle
     ├── shared organizer reference
     ├── shared location context
     └── shared Event Sessions
     
DOMAIN MODULES
     │
     ├── UPBS-specific rules
     ├── Kishor-specific rules
     └── Sevak-specific rules
```

---

# 3. Existing Module Context

The current project contains 20 documented modules:

1. Administration
2. Attendance
3. Audit
4. Authentication
5. Backup & Technical
6. Family
7. Foundation
8. Finance
9. Governance
10. Heritage
11. Kishor
12. Kumari
13. Mahila
14. Membership
15. Organization
16. Person
17. Publications
18. Reports
19. Sevak
20. UPBS

The Programme & Event architecture is being evaluated as a potential
additional module.

**No Module #21 decision is frozen by this document.**

---

# 4. Common Event Architecture Under Review

The proposed common model is:

```text
PROGRAMME_TYPE
      │
      │ 1:N
      ▼
EVENT
 ├── ORGANIZER → ORGANIZATION
 ├── LOCATION
 ├── EVENT_SESSION
 ├── ATTENDANCE
 ├── FINANCIAL_SCOPE
 └── DOMAIN EXTENSIONS
        ├── UPBS
        ├── KISHOR
        └── SEVAK
```

The model is intended to provide common Event infrastructure without
duplicating domain-specific entities.

---

# 5. Programme Type Review

The current proposed Programme Types include:

| Programme Type           | Default Organizer       |
| ------------------------ | ----------------------- |
| Kishor Puja              | Kendra                  |
| Janmoutsaba              | Kendra                  |
| Saradiya Alochana Chakra | Kendra                  |
| UPBS                     | Kendra                  |
| Rasoutsaba               | Ekamra Saraswata Sangha |

These are programme definitions.

They are not individual Event records.

---

# 6. Annual Recurring Programme Review

The identified recurring programmes can be represented as:

```text
PROGRAMME TYPE
      │
      ├── Event 2027
      ├── Event 2028
      ├── Event 2029
      └── ...
```

This avoids creating separate physical Event structures for every
programme.

The model therefore supports the identified annual recurring
programmes without requiring:

```text
kishor_puja_event
janmoutsaba_event
saradiya_event
upbs_event
rasoutsaba_event
```

as independent common Event entities.

---

# 7. Kendra / Sakha / Patha Chakra Review

The following distinction is confirmed:

```text
Kendra
Sakha
Patha Chakra
```

are **Organization concepts**, not Event Location concepts.

Therefore:

```text
EVENT
   │
   ├── organizer → ORGANIZATION
   │
   └── location → physical/geographic location
```

is the correct conceptual separation.

---

# 8. Patha Chakra Review

Patha Chakra is a permanent Organization.

NSS may have multiple Patha Chakras in the same way that it may have
multiple Sakha Sanghas.

A Patha Chakra may later be transformed into a Sakha Sangha through the
Organization lifecycle.

Therefore:

```text
PATHA_CHAKRA
      │
      │ Organization lifecycle
      ▼
SAKHA
```

This transformation does not belong to the Event domain.

The Event framework shall reference the Organization state applicable to
the Event.

---

# 9. UPBS Review

## 9.1 Existing Domain

UPBS already contains event-related concepts and business processes.

The common Event architecture must therefore be evaluated as an
integration layer rather than a replacement by assumption.

---

# 10. UPBS Event Mapping

The proposed logical mapping is:

```text
PROGRAMME_TYPE
      UPBS
        │
        ▼
EVENT
      UPBS 2027
        │
        ├── Organizer → Kendra
        ├── Location
        ├── Event Sessions
        ├── Attendance
        ├── Financial Scope
        └── UPBS-specific extension
```

This is compatible with the common Event architecture at the logical
level.

---

# 11. UPBS Sessions

UPBS provides a strong validation case for the common Event Session
concept.

The existing programme structure includes session/day concepts such as:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

These can logically map to:

```text
EVENT
   ├── EVENT_SESSION
   │      └── ADHIBASA
   ├── EVENT_SESSION
   │      └── DAY_1
   ├── EVENT_SESSION
   │      └── DAY_2
   └── EVENT_SESSION
          └── DAY_3
```

The meaning and operational rules of these sessions remain UPBS-owned.

---

# 12. UPBS-Specific Data

The following concepts remain UPBS-owned:

* registration;
* delegate card;
* Prasad Patra;
* accommodation;
* camp;
* guest reference;
* other UPBS-specific operational information.

The common Event model should not absorb these concepts.

---

# 13. UPBS `upbs_event` Reconciliation

The existing `upbs_event` concept requires explicit reconciliation.

Possible future strategies include:

### Option A

```text
Common EVENT
      │
      ▼
UPBS Event Extension
```

### Option B

```text
Common EVENT
      │
      ▼
UPBS-specific event reference
```

### Option C

Another approved mapping based on detailed implementation analysis.

**No migration strategy is frozen.**

The existing UPBS structure must not be deleted or renamed as a result of
this review alone.

---

# 14. UPBS Verdict

**Result: COMPATIBLE**

The common Event model can represent UPBS at the logical level while
preserving UPBS-specific ownership.

No fundamental architectural conflict was identified.

**Implementation migration remains OPEN.**

---

# 15. Kishor Review

Kishor has its own programme-specific concepts and rules.

The common architecture proposes:

```text
PROGRAMME_TYPE
    KISHOR_PUJA
        │
        ▼
EVENT
        │
        └── KISHOR-specific extension
```

Kishor-specific participation and programme rules remain Kishor-owned.

---

# 16. Kishor Event Mapping

The proposed mapping is:

```text
KISHOR_PUJA
      │
      ▼
Kishor Event Instance
      │
      ├── Organizer → Kendra
      ├── Location
      ├── Attendance
      ├── Finance
      └── Kishor-specific information
```

This is logically compatible with the common model.

---

# 17. Kishor Existing Structure

Any existing Kishor event identity must be reconciled before physical
implementation.

The common Event architecture does not automatically replace existing
Kishor entities.

---

# 18. Kishor Verdict

**Result: COMPATIBLE**

The common Event model can provide shared Event identity while leaving
Kishor-specific rules under the Kishor module.

**Migration remains OPEN.**

---

# 19. Sevak Review

Sevak is particularly important because its Event model contains
domain-specific behavior that must not be lost.

Existing Sevak concepts include:

* Event creation;
* configurable frequency;
* host Sakha;
* intention;
* probable attendance;
* actual attendance;
* publication;
* cancellation;
* rescheduling;
* reconciliation.

---

# 20. Sevak Event Mapping

The common mapping is:

```text
PROGRAMME / SEVAK EVENT
          │
          ▼
COMMON EVENT
    │
    ├── Organizer → Organization
    ├── Location
    │
    └── SEVAK EXTENSION
          ├── host Sakha
          ├── intention
          ├── probable attendance
          └── other Sevak-specific rules
```

This preserves the distinction between common Event infrastructure and
Sevak domain behavior.

---

# 21. Sevak Host Sakha

Sevak requires a registered Sakha as host according to its existing
domain rules.

This becomes:

```text
SEVAK EVENT
      │
      └── host_sakha
              │
              ▼
          ORGANIZATION
              │
              └── SAKHA
```

This must not become a universal Event requirement.

---

# 22. Sevak Organizer vs Host

The review confirms that:

```text
Organizer
    ≠
Host Sakha
```

may be valid.

Therefore the common Event architecture must not collapse these into one
universal field for all programmes.

---

# 23. Sevak Location

The existing Sevak design uses the host Sakha's registered location and
preserves relevant historical location information.

The common Event model can accommodate this through:

```text
SEVAK EVENT
    │
    ├── host_sakha
    │
    └── Event Location
```

The universal location-snapshot strategy remains a physical-design
decision.

---

# 24. Sevak Verdict

**Result: COMPATIBLE**

The common Event model can provide shared identity and lifecycle while
preserving the existing Sevak-specific rules.

This is an important validation because Sevak demonstrates that a common
Event must support domain extensions rather than impose one universal
workflow.

---

# 25. Attendance Review

Attendance is an independent domain.

The common Event architecture should provide the context:

```text
EVENT
   │
   ▼
ATTENDANCE
```

Attendance remains responsible for:

* attendance records;
* attendance calculation;
* attendance correction;
* attendance reconciliation;
* cross-Sakha attendance behavior;
* attendance-specific business rules.

---

# 26. Attendance Ownership

The Event architecture shall not create:

```text
event_attendance
```

merely to support common Event behavior if that duplicates the
Attendance module's existing ownership.

The exact physical relationship will be resolved during the eventual
database design.

---

# 27. Cross-Organization Attendance

A person may attend an Event organized or hosted by another Organization.

Example:

```text
Member of Sakha A
       │
       ▼
Attends Event at Sakha B
```

This does not imply:

```text
Membership transfer
Organization transfer
Sakha change
```

The common Event architecture supports this distinction.

---

# 28. Attendance Verdict

**Result: COMPATIBLE**

The common Event model provides a useful Event context while Attendance
retains complete ownership of attendance behavior.

---

# 29. Finance Review

Finance is a separate documented module.

The Finance architecture explicitly distinguishes:

```text
Organization
    ≠
Financial Scope
```

and supports event-related financial management.

---

# 30. Event Finance Mapping

The proposed relationship is:

```text
EVENT
   │
   ▼
FINANCIAL_SCOPE
   │
   ▼
FINANCE
```

Finance remains the owner of:

* Financial Year;
* Financial Scope;
* transactions;
* funds;
* receipts;
* payments;
* transfers;
* financial lifecycle;
* financial authorization.

---

# 31. Event Financial Year

All financial activity associated with an Event follows the Finance
Financial Year:

```text
01 April YYYY
      ↓
31 March YYYY+1
```

It is not based on calendar year.

Example:

```text
Event:
15 March 2028

Financial Year:
2027–28
```

subject to Finance's authoritative determination.

---

# 32. Multiple Event Financial Scopes

Different Events may have independent Financial Scopes where required.

For example:

```text
UPBS 2027
      ↓
UPBS Financial Scope

Kishor Puja 2027
      ↓
Kishor Puja Financial Scope
```

The exact cardinality and creation rules remain Finance-owned.

---

# 33. Special Event Finance

The common Event architecture also supports one-off/special Events that
require their own financial management.

The Event does not own the financial records.

Finance remains authoritative.

---

# 34. Finance Verdict

**Result: COMPATIBLE**

The common Event model aligns with the existing Finance architecture
without creating a duplicate finance layer.

---

# 35. Organization Review

Organization is a foundational domain for the common Event model.

The Event architecture consumes Organization identity.

It does not create organizational identity.

---

# 36. Organization Concepts Used by Events

Events may reference Organizations such as:

* Kendra;
* Anchalika;
* Zilla;
* Sakha;
* Patha Chakra;
* other approved Organization Types.

The exact permitted organizer types may vary by Programme Type.

---

# 37. Organization Lifecycle Independence

Organization lifecycle remains independent.

For example:

```text
Patha Chakra
      ↓
approved transformation
      ↓
Sakha
```

does not represent an Event lifecycle transition.

---

# 38. Organization Verdict

**Result: COMPATIBLE**

The common Event model correctly consumes Organization rather than
reimplementing it.

---

# 39. Administration Review

Administration owns the common RBAC/authorization infrastructure.

The Event architecture shall use:

```text
User
 ↓
Role
 ↓
Permission
 ↓
Organizational Scope
 ↓
Event Action
```

It shall not create Event-specific role or permission tables.

---

# 40. Administration Verdict

**Result: COMPATIBLE**

No authorization duplication is required.

---

# 41. Authentication Review

Authentication provides identity and credential/security services.

The Event architecture consumes authenticated user identity.

It does not create:

* user accounts;
* passwords;
* sessions;
* credentials.

---

# 42. Authentication Verdict

**Result: COMPATIBLE**

No conflict identified.

---

# 43. Audit Review

Event lifecycle changes require centralized auditing.

Relevant operations include:

* creation;
* publication;
* cancellation;
* rescheduling;
* completion;
* significant organizer changes;
* significant location changes.

Audit remains owned by the Audit module.

---

# 44. Audit Verdict

**Result: COMPATIBLE**

The Event architecture consumes the centralized Audit infrastructure and
does not create a duplicate audit system.

---

# 45. Reports Review

Reports should consume Event information for reporting and analytics.

Examples include:

```text
Programme-wise Events
Event attendance
Event participation
Event financial reporting
Annual programme reporting
Organization-wise event reporting
```

Reports does not own Event identity.

---

# 46. Reports Verdict

**Result: COMPATIBLE**

Reports can consume the common Event model without owning its underlying
business entities.

---

# 47. Backup & Technical Review

Backup & Technical remains responsible for technical backup and
infrastructure concerns.

It does not require an independent Event representation.

Event data falls under the general backup strategy.

---

# 48. Backup & Technical Verdict

**Result: COMPATIBLE**

No separate Event-specific backup architecture is required.

---

# 49. Foundation Review

Foundation provides common infrastructure and master-data capabilities.

The Event architecture may consume appropriate Foundation master data.

However, the common Event model should not use Foundation as a reason to
create generic catch-all Event structures.

---

# 50. Person Review

Person provides identity for individuals participating in Events.

The Event architecture shall reference Person where required.

It shall not duplicate Person identity.

---

# 51. Membership Review

Membership remains authoritative for membership status and
organizational membership.

Event participation does not automatically create or modify membership.

---

# 52. Governance Review

Governance may interact with Event-related authority and organizational
processes.

However, the common Event lifecycle shall not duplicate Governance's
organizational governance processes.

---

# 53. Other Module Review

The following modules may consume or interact with Events without
requiring ownership of the common Event framework:

```text
Family
Heritage
Kumari
Mahila
Publications
```

Any domain-specific Event requirement remains with the relevant module.

---

# 54. Common Event Ownership Boundary

The review establishes the following conceptual boundary:

```text
                 COMMON EVENT
                      │
        ┌─────────────┼─────────────┐
        │             │             │
      UPBS          KISHOR        SEVAK
        │             │             │
 domain rules     domain rules   domain rules
```

The common layer should own only concepts genuinely common across
programmes.

---

# 55. What the Common Event Layer Should Own

Candidate common ownership:

* Programme Type;
* Event identity;
* common Event lifecycle;
* organizer reference;
* Event Location context;
* Event Session concept;
* common Event audit integration;
* common Event notification hooks;
* common Event authorization integration.

Physical ownership remains to be decided.

---

# 56. What the Common Event Layer Should NOT Own

It should not own:

* Person identity;
* Organization identity;
* Membership;
* Attendance records;
* financial transactions;
* Financial Scope implementation;
* UPBS registration;
* UPBS accommodation;
* Kishor-specific rules;
* Sevak-specific host/eligibility rules;
* RBAC;
* Authentication;
* Audit framework.

---

# 57. Five Initial Programmes — Consolidated Mapping

| Programme                | Organizer               | Common Event | Domain Extension        | Finance |
| ------------------------ | ----------------------- | ------------ | ----------------------- | ------- |
| Kishor Puja              | Kendra                  | Yes          | Kishor                  | Finance |
| Janmoutsaba              | Kendra                  | Yes          | None currently required | Finance |
| Saradiya Alochana Chakra | Kendra                  | Yes          | None currently required | Finance |
| UPBS                     | Kendra                  | Yes          | UPBS                    | Finance |
| Rasoutsaba               | Ekamra Saraswata Sangha | Yes          | None currently required | Finance |

This is a logical mapping, not a physical table commitment.

---

# 58. Special Event Mapping

The common architecture should also support:

```text
SPECIAL EVENT
     │
     ├── Organizer
     ├── Location
     ├── Schedule
     ├── Attendance
     └── Financial Scope where required
```

The final mechanism for representing a Special Event without an existing
Programme Type remains PENDING.

---

# 59. Common Event Architecture — Strengths

The review identifies the following benefits:

### 59.1 Avoids Duplicate Event Infrastructure

Instead of creating separate common structures for every programme:

```text
Kishor Event
UPBS Event
Sevak Event
Janmoutsaba Event
Rasoutsaba Event
```

the architecture provides:

```text
Common Event
     +
Domain Extensions
```

### 59.2 Preserves Domain Ownership

UPBS, Kishor and Sevak retain their own specialized rules.

### 59.3 Integrates Finance

Every programme can use Finance without embedding finance logic in the
Event module.

### 59.4 Integrates Attendance

Events provide context while Attendance retains attendance ownership.

### 59.5 Supports Future Programmes

A future Programme Type can use the common Event infrastructure where
appropriate.

---

# 60. Identified Risks

The review identifies the following risks.

## Risk 1 — Over-Generalization

A common Event model could become too generic and lose meaningful
programme-specific semantics.

**Mitigation:** use explicit domain extensions.

---

## Risk 2 — Premature Migration

Existing UPBS/Kishor/Sevak structures could be migrated before their
business rules are fully reconciled.

**Mitigation:** no migration until explicit module-by-module mapping is
approved.

---

## Risk 3 — Ownership Ambiguity

A common Event table could become shared without a clear owner.

**Mitigation:** one physical owner must be designated before DDL.

---

## Risk 4 — Event Location Confusion

Organization Types could incorrectly become Event Locations.

**Mitigation:** preserve:

```text
Organization ≠ Event Location
```

---

## Risk 5 — Finance Coupling

Event design could accidentally reproduce financial entities.

**Mitigation:** Event references Finance; Finance owns financial records.

---

# 61. Cross-Module Dependency Summary

```text
                         ORGANIZATION
                              │
                              │ organizer
                              ▼
PROGRAMME_TYPE ───────────► EVENT
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
         ATTENDANCE        FINANCE          DOMAIN
         Module            Module          Extensions
                                             │
                                      ┌──────┼──────┐
                                      ▼      ▼      ▼
                                    UPBS   KISHOR  SEVAK
```

Supporting services:

```text
Authentication
      ↓
Administration / RBAC
      ↓
Event Authorization

Event
      ↓
Audit

Event
      ↓
Notifications

Event
      ↓
Reports
```

---

# 62. Compatibility Matrix

| Module             | Relationship                      | Result        |
| ------------------ | --------------------------------- | ------------- |
| Foundation         | Common infrastructure/master data | COMPATIBLE    |
| Person             | Person identity                   | COMPATIBLE    |
| Organization       | Organizer / organization identity | COMPATIBLE    |
| Family             | Participant context               | COMPATIBLE    |
| Membership         | Membership context                | COMPATIBLE    |
| Authentication     | User identity                     | COMPATIBLE    |
| Administration     | Authorization/RBAC                | COMPATIBLE    |
| Audit              | Lifecycle audit                   | COMPATIBLE    |
| Attendance         | Actual attendance                 | COMPATIBLE    |
| Finance            | Financial Scope / transactions    | COMPATIBLE    |
| Governance         | Governance authority              | COMPATIBLE    |
| Heritage           | Domain interaction                | COMPATIBLE    |
| Kishor             | Programme-specific Event          | COMPATIBLE    |
| Kumari             | Programme interaction             | COMPATIBLE    |
| Mahila             | Programme/Event consumer          | COMPATIBLE    |
| Publications       | Programme/Event consumer          | COMPATIBLE    |
| Reports            | Event reporting                   | COMPATIBLE    |
| Sevak              | Domain-specific Event             | COMPATIBLE    |
| UPBS               | Domain-specific Event             | COMPATIBLE    |
| Backup & Technical | Infrastructure                    | COMPATIBLE    |

---

# 63. Does the Common Event Architecture Replace Existing Modules?

**No.**

The proposed architecture does not replace:

* UPBS;
* Kishor;
* Sevak;
* Attendance;
* Finance;
* Organization;
* Administration;
* Audit.

It provides a common Event foundation consumed by those modules.

---

# 64. Does Every Programme Need a New Module?

**No.**

A new Programme Type does not automatically require a new ERP module.

A Programme Type can use the common Event framework without requiring
new physical domain tables.

A dedicated module is justified only when the programme has substantial
domain-specific data, rules, lifecycle or workflows.

---

# 65. Does Every Programme Need an Event Extension?

**No.**

A Programme may use the common Event entity directly if it has no
additional domain-specific data.

For example:

```text
Janmoutsaba
    ↓
Common Event
```

may be sufficient unless further requirements are identified.

---

# 66. Does Every Event Need Finance?

**No.**

The common Event model supports Finance integration.

A Financial Scope exists only where financial management is required.

---

# 67. Does Every Event Need Attendance?

**No.**

The Event architecture can integrate with Attendance where the programme
requires attendance.

Attendance requirements remain programme/domain-specific.

---

# 68. Does Every Event Need Sessions?

**No.**

Sessions are optional.

UPBS demonstrates a strong use case, but a simple one-day programme need
not create artificial sessions.

---

# 69. Module #21 Assessment

The review finds that a common Programme & Event domain has:

* multiple independent programme consumers;
* common Event identity requirements;
* common lifecycle requirements;
* common organizer/location concepts;
* Finance integration;
* Attendance integration;
* notification integration;
* reporting requirements;
* domain-specific extensions.

Therefore a dedicated Programme & Events ownership boundary is
**architecturally justified**.

However:

> The formal Module #21 designation should be made only after the
> project accepts this cross-module review and freezes ownership.

---

# 70. Recommended Ownership Decision

The recommended architecture is:

```text
MODULE #21 — PROGRAMMES & EVENTS
```

with responsibility for:

```text
Programme Type
Event
Event Lifecycle
Event Location
Event Session
Common Event Integration
```

while retaining existing ownership:

```text
UPBS       → UPBS-specific Event data
Kishor     → Kishor-specific Event data
Sevak      → Sevak-specific Event data
Attendance → Attendance
Finance    → Financial Scope and finance
Organization → Organization
Administration → RBAC
Audit      → Audit
Reports    → Reporting
```

This is a recommended architectural decision, not yet a physical
database decision.

---

# 71. Recommended Module Position

If Module #21 is formally accepted, it should conceptually sit after the
existing domain modules in the documentation inventory.

The implementation dependency is different from the documentation
number.

The common Event module depends conceptually on:

```text
Organization
Person
Attendance
Finance
Administration
Audit
```

and provides infrastructure consumed by:

```text
UPBS
Kishor
Sevak
Reports
future programmes
```

Therefore it should not be treated as a simple sequential dependency
based only on its module number.

---

# 72. Recommended Implementation Timing

The Programme & Events module should **not immediately enter physical
DDL implementation**.

Before database implementation, the project should first:

1. accept the common Event architecture;
2. freeze Module #21 ownership;
3. reconcile existing UPBS event structures;
4. reconcile existing Kishor event structures;
5. reconcile existing Sevak event structures;
6. identify any missing common business rules;
7. then prepare physical table design.

---

# 73. No Database Tables Created by This Review

This document does not authorize creation of:

```text
programme_type
event
event_session
event_location
event_lifecycle_history
```

or any other physical table.

Those remain future design candidates.

---

# 74. No API Design

API design remains deferred until the physical database design is
completed.

The project sequence remains:

```text
Architecture
    ↓
Business Rules
    ↓
Lifecycle
    ↓
Database Design
    ↓
API
    ↓
UI
```

---

# 75. No UI Design

UI design remains deferred.

The common Event UI should only be designed after:

* ownership;
* lifecycle;
* database;
* API

are established.

---

# 76. Final Review Verdict

## Common Programme & Event Architecture

**STATUS: ARCHITECTURALLY JUSTIFIED**

The common model is compatible with the current module structure.

No fundamental conflict was identified with:

* UPBS;
* Kishor;
* Sevak;
* Attendance;
* Finance;
* Organization;
* Administration;
* Authentication;
* Audit;
* Reports;
* Backup & Technical.

The key architectural rule is:

```text
COMMON EVENT INFRASTRUCTURE
            +
DOMAIN-SPECIFIC EXTENSIONS
```

rather than:

```text
ONE GENERIC EVENT TABLE
        +
ALL PROGRAMME-SPECIFIC DATA
```

---

# 77. Decision Required

The next governance decision is:

> **Approve Programme & Events as Module #21 and authorize physical
> database-design work at the appropriate implementation stage.**

Until that approval:

```text
Module #21 = PROPOSED
Physical tables = NOT FROZEN
DDL = NOT AUTHORIZED
API = NOT AUTHORIZED
UI = NOT AUTHORIZED
```

---

# 78. Recommended Next Step

If Module #21 is approved, the next documentation action is to update:

```text
docs/03_Solution/modules/
```

and the project module inventory to include:

```text
21. Programmes & Events
```

Then prepare its formal module documentation set.

The **database table design should still be deferred until we are ready
to implement this module in the vertical module-wise sequence.**

---

# 79. Status

```text
DOCUMENT STATUS:
FROZEN — CROSS-MODULE REVIEW COMPLETE

VERSION:
1.1.0

COMMON EVENT ARCHITECTURE:
ARCHITECTURALLY JUSTIFIED

RECONCILIATION GATES:
ALL CLOSED (7/7) — see SOL-EVT-007

UPBS:
COMPATIBLE

KISHOR:
COMPATIBLE

SEVAK:
COMPATIBLE

ATTENDANCE:
COMPATIBLE (Weekly Sangha Puja remains Attendance-owned)

FINANCE:
COMPATIBLE

ORGANIZATION:
COMPATIBLE

ADMINISTRATION:
COMPATIBLE

AUDIT:
COMPATIBLE

REPORTS:
COMPATIBLE

BACKUP & TECHNICAL:
COMPATIBLE

MODULE #21:
CONFIRMED — Programmes & Events

PHYSICAL DATABASE:
NOT STARTED (deferred to implementation tier)

API:
NOT STARTED

UI:
NOT STARTED

ADDITIONAL PROGRAMME TYPES CONFIRMED:
Janmotsaba (1-day, Kendra or Sakha-organized)
Rasautsab (5-day, Sakha-organized)
UPBS (3-day, Kendra)

NEW CANDIDATE TABLES (per SOL-EVT-007):
event_day
event_registration

NEXT:
DB STANDARDS → FK GRAPH → DDL ORDER → FOUNDATION VERTICAL SLICE
```

# 80. Reconciliation Closure

All 7 reconciliation gates closed. Formal decisions recorded in
SOL-EVT-007 (PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md).

Key outcomes:

- Common Event architecture confirmed (Gates A–D)
- Event Session optional, organiser-defined (Gate E, P&E-ARCH-002)
- Weekly Sangha Puja remains Attendance-owned (Gate F)
- Common Registration confirmed (Gate G, P&E-ARCH-001)
- Janmotsaba (1-day) and Rasautsab (5-day) confirmed as programme types
- `event_day` and `event_registration` added as candidate common tables
- No Attendance dependency tier change
- No new P&E → Attendance FK

# End of Document
