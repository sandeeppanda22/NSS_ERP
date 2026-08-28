# NSS ERP — Programmes & Events Module Overview

**Document ID:** SOL-MOD21-001  
**Version:** 0.1.0  
**Status:** DRAFT — MODULE DOCUMENTATION  
**Module:** Programmes & Events  
**Module Number:** 21

---

# 1. Purpose

The Programmes & Events Module provides the common ERP framework for
NSS programmes and event instances.

The module separates:

- **Programme Type** — the reusable definition of a programme;
- **Event** — an actual occurrence of a programme;
- **Event Session** — an optional subdivision of an Event;
- **Organizer** — the Organization responsible for organizing the Event;
- **Event Location** — the physical/geographical location where the Event
  takes place.

The module provides common Event infrastructure while preserving
programme-specific ownership in modules such as UPBS, Kishor and Sevak.

---

# 2. Architectural Position

The module sits between the common organizational/identity infrastructure
and domain-specific programme modules.

```text
Foundation
    │
    ├── Person
    │
    └── Organization
             │
             ▼
      Programmes & Events
             │
       ┌─────┼─────┐
       ▼     ▼     ▼
      UPBS  Kishor Sevak
```

The module also integrates with:

```text
Attendance
Finance
Administration
Authentication
Audit
Reports
```

The module does not take ownership of those domains.

---

# 3. Core Principle

The ERP shall use a **common Event architecture** rather than creating
separate common Event tables for every programme.

Conceptually:

```text
Programme Type
      │
      ├── Event Instance 2027
      ├── Event Instance 2028
      └── Event Instance 2029
```

A programme does not automatically require a dedicated ERP module.

A programme requires a separate module only when it has substantial
domain-specific entities, business rules, workflows or lifecycle
requirements.

---

# 4. Programme Type

A Programme Type represents a reusable definition of a programme.

Examples include:

* Kishor Puja
* Janmoutsaba
* Saradiya Alochana Chakra
* UPBS
* Rasoutsaba

A Programme Type is not itself an Event.

Example:

```text
PROGRAMME TYPE
    UPBS
      │
      ├── UPBS 2027
      ├── UPBS 2028
      └── UPBS 2029
```

Each occurrence is an independent Event Instance.

---

# 5. Initial Programme Types

The initial identified recurring programmes are:

| Programme Type           | Organizer               |
| ------------------------ | ----------------------- |
| Kishor Puja              | Kendra                  |
| Janmoutsaba              | Kendra                  |
| Saradiya Alochana Chakra | Kendra                  |
| UPBS                     | Kendra                  |
| Rasoutsaba               | Ekamra Saraswata Sangha |

The organizer shown here represents the normal/default organizing
authority.

The final physical configuration and whether organizer can vary by Event
remain subject to the module business rules.

---

# 6. Annual Recurring Programmes

Annual recurrence does not require a separate Event table for every
programme.

Instead:

```text
PROGRAMME TYPE
      │
      ├── EVENT — 2027
      ├── EVENT — 2028
      ├── EVENT — 2029
      └── ...
```

Each Event has its own:

* lifecycle;
* schedule;
* organizer context;
* location;
* sessions where applicable;
* attendance integration;
* financial integration where applicable.

---

# 7. Event

An Event represents an actual occurrence.

Examples:

```text
Kishor Puja — 2027
UPBS — 2027
Rasoutsaba — 2027
Janmoutsaba — 2028
```

The Event is the operational entity against which other modules may
integrate.

---

# 8. Event Lifecycle

The common Event lifecycle is:

```text
DRAFT
  ↓
PUBLISHED
  ↓
ACTIVE
  ↓
COMPLETED
```

Cancellation may occur before completion:

```text
DRAFT ───────────► CANCELLED
PUBLISHED ───────► CANCELLED
ACTIVE ──────────► CANCELLED
```

Rescheduling is treated as an Event operation and preserves the Event
identity.

---

# 9. Event Identity

The identity of an Event remains stable throughout its lifecycle.

For example:

```text
UPBS 2027
    │
    ├── Draft
    ├── Published
    ├── Rescheduled
    ├── Active
    └── Completed
```

Rescheduling does not automatically create a new unrelated Event.

Historical lifecycle changes must remain auditable.

---

# 10. Organizer

Organizer is an **Organization**.

The Event architecture therefore represents:

```text
EVENT
   │
   └── ORGANIZER
          │
          ▼
      ORGANIZATION
```

Examples:

```text
Kishor Puja
    Organizer → Kendra

UPBS
    Organizer → Kendra

Rasoutsaba
    Organizer → Ekamra Saraswata Sangha
```

The common Event module does not create a separate organizer entity that
duplicates Organization.

---

# 11. Organization Type Is Not Event Location

The following are Organization concepts:

```text
Kendra
Sakha
Patha Chakra
```

They are **not** Event Location Types.

The distinction is:

```text
ORGANIZATION
    Kendra
    Sakha
    Patha Chakra

EVENT LOCATION
    Physical/geographical place
```

An Event may be organized by a Kendra and take place at a physical
location associated with a Sakha, Patha Chakra, or another place.

---

# 12. Patha Chakra

Patha Chakra is a permanent Organization.

NSS may have multiple Patha Chakras in the same way it may have multiple
Sakha Sanghas.

A Patha Chakra may later be transformed into a Sakha through the
Organization lifecycle.

Conceptually:

```text
Patha Chakra
      │
      │ Organization transformation
      ▼
Sakha
```

This transformation belongs to the Organization Module.

It is not an Event lifecycle transition.

---

# 13. Event Location

Event Location represents where an Event physically takes place.

It is separate from:

* Organizer;
* Organization Type;
* Membership;
* Financial Scope.

The common Event model therefore distinguishes:

```text
Organizer
    ↓
Organization

Location
    ↓
Physical / geographical place
```

The exact historical location-snapshot implementation is subject to the
table-design phase.

---

# 14. Event Sessions

An Event may contain zero or more Event Sessions.

Example:

```text
UPBS
 │
 ├── Adhibasa
 ├── Day 1
 ├── Day 2
 └── Day 3
```

Sessions are optional.

A simple Event may have no separate sessions.

Programme-specific session semantics remain owned by the relevant domain
module.

---

# 15. UPBS Integration

UPBS is a major consumer of the common Event architecture.

Conceptually:

```text
PROGRAMME TYPE
     UPBS
       │
       ▼
COMMON EVENT
       │
       ├── Organizer → Kendra
       ├── Location
       ├── Sessions
       └── UPBS-specific extension
```

UPBS-specific concepts remain UPBS-owned, including its registration,
delegate, accommodation, camp and other programme-specific entities.

The common Event architecture does not automatically replace existing
UPBS structures.

---

# 16. Kishor Integration

Kishor may use the common Event framework for Kishor programme events.

Conceptually:

```text
KISHOR PUJA
      │
      ▼
COMMON EVENT
      │
      └── Kishor-specific information
```

Kishor-specific business rules remain owned by the Kishor Module.

---

# 17. Sevak Integration

Sevak has significant Event-specific business rules.

The common Event architecture provides:

* Event identity;
* common lifecycle;
* organizer;
* location;
* common Event context.

Sevak retains its domain-specific concepts, including where applicable:

* host Sakha;
* intention;
* probable attendance;
* actual attendance;
* cancellation;
* rescheduling;
* reconciliation.

The common Event module shall not flatten these concepts into generic
Event fields.

---

# 18. Attendance Integration

Attendance remains an independent module.

The Event provides context for attendance where required:

```text
EVENT
  │
  ▼
ATTENDANCE
```

Attendance remains authoritative for:

* attendance records;
* attendance calculation;
* correction;
* reconciliation;
* cross-Sakha attendance behavior.

The Programme & Events Module does not own attendance records.

---

# 19. Finance Integration

An Event may have financial activity.

The relationship is:

```text
EVENT
  │
  ▼
FINANCIAL SCOPE
  │
  ▼
FINANCE
```

Finance remains authoritative for:

* Financial Year;
* Financial Scope;
* funds;
* transactions;
* receipts;
* payments;
* transfers;
* financial approval;
* settlement.

The Event module does not create duplicate financial entities.

---

# 20. Financial Year

All Event-related financial activity follows the Finance Financial Year:

```text
01 April
   ↓
31 March
```

The calendar year is not the ERP Financial Year.

For example:

```text
Event Date:
15 March 2028

Financial Year:
2027–28
```

subject to Finance's authoritative determination.

---

# 21. Financial Scope

An Event does not automatically imply one universal Financial Scope.

Finance may establish an appropriate Financial Scope based on the
financial requirements of the Event.

An Organization and a Financial Scope remain separate concepts:

```text
Organization
    ≠
Financial Scope
```

Multiple Financial Scopes may exist where required by Finance rules.

---

# 22. Special Events

The common Event architecture supports special/one-off Events.

Example:

```text
SPECIAL EVENT
      │
      ├── Organizer
      ├── Location
      ├── Schedule
      ├── Sessions where required
      ├── Attendance where required
      └── Finance where required
```

A special Event does not automatically require a new ERP module.

---

# 23. Organizer and Event Location

The Event model deliberately separates:

| Concept           | Owner              |
| ----------------- | ------------------ |
| Organizer         | Organization       |
| Organization Type | Organization       |
| Event Location    | Programme & Events |
| Attendance        | Attendance         |
| Financial Scope   | Finance            |
| Person identity   | Person             |
| Authorization     | Administration     |
| Audit             | Audit              |

This ownership separation is fundamental to the architecture.

---

# 24. Authorization

Event lifecycle actions use the common Administration/RBAC framework.

The Event module does not create its own authorization system.

Conceptually:

```text
USER
  ↓
ROLE
  ↓
PERMISSION
  ↓
ORGANIZATIONAL SCOPE
  ↓
EVENT ACTION
```

Applicable actions include:

* create;
* publish;
* cancel;
* reschedule;
* complete;
* authorized correction.

Exact permission codes are defined during the business-rule and
implementation phases.

---

# 25. Authentication

Authentication provides the identity of the user performing Event
operations.

The Event Module does not own:

* credentials;
* passwords;
* authentication sessions;
* user accounts.

---

# 26. Audit

Significant Event lifecycle operations must be auditable.

Examples:

* creation;
* publication;
* cancellation;
* rescheduling;
* completion;
* significant organizer changes;
* significant location changes.

Audit remains owned by the centralized Audit Module.

---

# 27. Notifications

Event lifecycle changes may generate notifications.

Examples:

* Event published;
* Event cancelled;
* Event rescheduled;
* significant location change;
* Event completed.

The Event Module does not create a separate notification infrastructure.

Notification capability remains shared infrastructure.

---

# 28. Reports

Reports may consume Event information for:

* programme reports;
* Event reports;
* attendance reporting;
* financial reporting;
* organization-wise Event reporting;
* annual programme reporting.

Reports does not own Event identity.

---

# 29. Historical Preservation

Event records must be preserved historically.

Cancellation is not physical deletion.

Completion is not archival deletion.

Rescheduling must preserve relevant historical information.

Conceptually:

```text
EVENT
  ↓
CANCELLED / COMPLETED
  ↓
HISTORICALLY PRESERVED
```

---

# 30. Domain Ownership

The common Event module owns common Event concepts.

Domain modules own domain-specific concepts.

```text
COMMON
Programme Type
Event
Event Lifecycle
Event Location
Event Session
        │
        ├── UPBS extension
        ├── Kishor extension
        └── Sevak extension
```

This prevents the common Event entity from becoming a generic
catch-all table.

---

# 31. No Programme-Specific Common Tables

The architecture intentionally avoids creating generic Event tables such
as:

```text
kishor_puja_event
janmoutsaba_event
saradiya_event
upbs_event
rasoutsaba_event
```

for concepts that are genuinely common.

Programme-specific extensions may still be required where a programme has
unique business data.

---

# 32. Future Programme Types

Future programmes can be added as Programme Types without automatically
creating a new ERP module.

Evaluation:

```text
New Programme
      │
      ▼
Can common Event model represent it?
      │
   ┌──┴──┐
  YES    NO
   │      │
Common   Domain-specific
Event    extension/module
```

---

# 33. Module Responsibilities

The Programme & Events Module is responsible for:

1. Programme Type definition;
2. Event identity;
3. Event lifecycle;
4. Event schedule;
5. Event Location;
6. Event Sessions;
7. Organizer relationship;
8. Event lifecycle history;
9. Event-level integration hooks;
10. Event-related reporting context.

---

# 34. Explicitly Out of Scope

The module does not own:

* Person identity;
* Organization identity;
* Membership;
* Attendance records;
* Financial transactions;
* Financial Scope implementation;
* Authentication;
* RBAC;
* Audit infrastructure;
* UPBS registration;
* UPBS accommodation;
* Kishor-specific participant rules;
* Sevak-specific attendance/intention rules.

---

# 35. Dependency Summary

The common Event module integrates with:

```text
Foundation
    ↓
Person
    ↓
Organization
    ↓
Administration / Authentication
    ↓
Audit
    ↓
Programme & Events
    ↓
Attendance
Finance
Reports
```

The exact physical FK dependency graph is defined separately during the
ERD and table-design stages.

---

# 36. Module Consumers

Primary consumers include:

```text
UPBS
Kishor
Sevak
Attendance
Finance
Reports
Future Programme Types
```

The consumer relationship does not transfer ownership of their business
data.

---

# 37. Module Documentation Set

The formal Programme & Events module documentation consists of:

```text
programmes_events/
├── 01_programmes_events_module_overview.md
├── 02_programmes_events_erd.md
├── 03_programmes_events_lifecycle.md
├── 04_programmes_events_business_rules.md
└── 05_programmes_events_table_design.md
```

These documents form the Module #21 documentation package.

---

# 38. Relationship to Architecture Documents

Cross-module architecture remains documented under:

```text
docs/03_Solution/architecture/
```

including:

```text
PROGRAMME_EVENT_DOMAIN_MODEL.md
EVENT_ENTITY_RECONCILIATION.md
PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md
MODULE_DEPENDENCY_MAP.md
IMPLEMENTATION_DEPENDENCY_ORDER.md
```

The Module #21 documents provide the formal module-level specification.

---

# 39. Documentation Phase

The Programme & Events module is currently in the documentation phase.

The sequence is:

```text
01 Overview
    ↓
02 ERD
    ↓
03 Lifecycle
    ↓
04 Business Rules
    ↓
05 Table Design
    ↓
Cross-module consistency review
    ↓
Documentation freeze
```

No production database implementation begins until this documentation
phase is complete.

---

# 40. Database Implementation Deferred

This document does not authorize production database creation.

Physical database implementation will begin only after:

* the module documentation is frozen;
* table design is approved;
* cross-module dependencies are validated;
* DDL strategy is approved.

---

# 41. API Implementation Deferred

API implementation follows the database phase.

The API shall implement the frozen business rules and lifecycle rather
than independently redefining them.

---

# 42. UI Implementation Deferred

UI implementation follows the API phase.

The UI shall expose only:

* valid lifecycle transitions;
* authorized operations;
* approved Event workflows.

---

# 43. Module #21 Status

```text
Module Number:
21

Module Name:
Programmes & Events

Architecture:
ARCHITECTURALLY JUSTIFIED

Module Documentation:
IN PROGRESS

Database:
NOT IMPLEMENTED

API:
NOT IMPLEMENTED

UI:
NOT IMPLEMENTED

Primary Role:
COMMON PROGRAMME & EVENT INFRASTRUCTURE

Primary Consumers:
UPBS
KISHOR
SEVAK
ATTENDANCE
FINANCE
REPORTS
FUTURE PROGRAMMES

Financial Year:
01 APRIL – 31 MARCH

Organization Types:
KENDRA
SAKHA
PATHA CHAKRA

Event Location:
SEPARATE FROM ORGANIZATION TYPE

Next Document:
02_programmes_events_erd.md
```
