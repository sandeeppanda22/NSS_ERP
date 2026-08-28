# NSS ERP — Programme & Event Domain Model

**Document ID:** SOL-EVT-001  
**Version:** 0.1.0  
**Status:** DRAFT — ARCHITECTURAL ANALYSIS  
**Domain:** Programme & Event  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the working conceptual model for programmes and
events across NSS ERP.

It is an architectural analysis document. It does **not** yet freeze
physical PostgreSQL tables, API contracts, or UI structures.

The purpose is to establish a common model that can be used by multiple
NSS programmes while preserving domain-specific business rules.

---

# 2. Core Architectural Principle

A programme/event shall not require a separate module or table merely
because it has a different name or annual occurrence.

The common model distinguishes:

1. Programme Type
2. Event Instance
3. Event Session
4. Organizer Organization
5. Event Location
6. Financial Scope
7. Domain-specific extension

Conceptually:

```text
Organization
      │
      │ organizer
      ▼
Programme Type
      │
      │ creates
      ▼
Event Instance
   │       │
   │       ├── Event Location
   │       ├── Financial Scope
   │       └── Event Sessions
   │
   └── Domain-specific extension
```

---

# 3. Programme Type

## 3.1 Definition

A Programme Type represents the reusable definition/configuration of a
recurring or repeatable NSS programme.

It is distinct from an individual occurrence.

Example:

```text
Programme Type:
    KISHOR_PUJA
```

is different from:

```text
Event Instance:
    Kishor Puja 2027
```

The exact physical representation of Programme Type remains **OPEN**.

---

# 4. Initial Programme Types

The following five annual recurring programmes are the current project
working set:

| Programme Type           | Default Organizer       |
| ------------------------ | ----------------------- |
| KISHOR_PUJA              | Kendra                  |
| JANMOUTSABA              | Kendra                  |
| SARADIYA_ALOCHANA_CHAKRA | Kendra                  |
| UPBS                     | Kendra                  |
| RASOUTSABA               | Ekamra Saraswata Sangha |

These organizer assignments are current project configuration decisions.
They are not claims that the Bye-Law itself defines these ERP fields.

---

# 5. Event Instance

An Event Instance represents one actual occurrence of a Programme Type.

Example:

```text
Programme Type:
    UPBS

Event Instance:
    UPBS 2027
```

Another occurrence:

```text
Programme Type:
    UPBS

Event Instance:
    UPBS 2028
```

Each occurrence has its own:

* date/time
* status
* organizer context
* physical location
* sessions where applicable
* participation/attendance context
* financial context where required
* historical/audit identity

---

# 6. Programme Type vs Event Instance

The distinction is mandatory for the conceptual model.

```text
PROGRAMME TYPE
    │
    │ recurrence / creation
    ▼
EVENT INSTANCE
    │
    ├── 2027 occurrence
    ├── 2028 occurrence
    └── 2029 occurrence
```

The annual nature of a programme does not mean that a single Event Instance
is reused across years.

Each occurrence must retain its own history.

---

# 7. Organizer

Every Programme Type may have a configured default organizer.

The organizer is an **Organization**, not an Event Location.

Conceptually:

```text
programme_type
      │
      └── default_organizer
              │
              ▼
         Organization
```

For an Event Instance, the effective organizer should normally be
resolved from the Programme Type.

Whether an explicitly approved Event-level organizer override is permitted
remains **OPEN**.

---

# 8. Event Location

Event Location is a separate concept from Organization Type.

A Kendra, Sakha Sangha, or Patha Chakra is an organization.

Therefore it is incorrect to model:

```text
event_location_type = KENDRA
event_location_type = SAKHA
event_location_type = PATHA_CHAKRA
```

as the generic Event Location model.

Instead:

```text
Event
   │
   └── event_location
           │
           └── physical/geographic location
```

An organization may own, operate, or be associated with a physical
location, and an Event may take place at that location.

These are separate relationships.

---

# 9. Organization vs Event Location

The architectural distinction is:

```text
ORGANIZATION
    │
    ├── KENDRA
    ├── SAKHA_SANGHA
    └── PATHA_CHAKRA


EVENT
    │
    ├── organizer → ORGANIZATION
    │
    └── location  → PHYSICAL / GEOGRAPHIC LOCATION
```

A Kendra may organize an event.

A Kendra may also have premises where the event is held.

The two facts must not be conflated.

---

# 10. Location Snapshot

The frozen Sevak source establishes:

```text
"The host Sakha's registered location is used."
"A historical location snapshot is retained by the Event framework."
"The Sevak module does not create a separate venue table for this purpose."
```

Therefore Event Location is a point-in-time snapshot:

```text
event
  └── location snapshot at time of event creation
```

This preserves historical accuracy when an organization's address changes.

The exact physical structure (flat columns on event vs. separate
event_location entity) is a table-design decision, not frozen here.

---

# 11. Organization Types

The Organization Module remains authoritative for organizational identity
and organizational type.

The current project terminology includes:

* KENDRA
* ANCHALIKA
* ZILLA
* SAKHA
* PATHA_CHAKRA

Organization Type is configurable master data.

Patha Chakra is therefore an organization type, not an Event Type or
Programme Type.

---

# 12. Patha Chakra

Patha Chakra is a **permanent organization**.

NSS may have multiple Patha Chakras, just as it may have multiple Sakha
Sanghas.

A future approved organizational transformation may change a particular
Patha Chakra into a Sakha Sangha:

```text
Patha Chakra
     │
     │ approved organizational transformation
     ▼
Sakha Sangha
```

This is an **Organization lifecycle transformation**, not an Event
lifecycle transition.

The transformation:

- Preserves the organization's identity and history
- Changes organizational type/status
- Does not delete the Patha Chakra record
- Does not create a brand-new Sakha record from scratch

Historical records retain their historical organizational context.

The exact transformation workflow belongs to the Organization Module.

---

# 13. Event Sessions

An Event may contain zero or more Event Sessions/Segments.

Conceptually:

```text
EVENT
  │
  └── EVENT SESSION
```

This is particularly useful for UPBS.

The current UPBS design identifies:

* ADHIBASA
* DAY_1
* DAY_2
* DAY_3

Therefore:

```text
UPBS 2027
    │
    ├── ADHIBASA
    ├── DAY_1
    ├── DAY_2
    └── DAY_3
```

The common Event Session concept should be evaluated before retaining a
UPBS-only physical session structure.

Not all events require sessions. A single-day event may have zero sessions.

Session types are configurable per programme type.

---

# 14. UPBS as a Validation Case

UPBS should participate in the common Programme/Event model without
losing its dedicated business domain.

Conceptually:

```text
PROGRAMME TYPE
    UPBS
      │
      ▼
EVENT INSTANCE
    UPBS 2027
      │
      ├── ADHIBASA
      ├── DAY_1
      ├── DAY_2
      └── DAY_3
      │
      ├── UPBS Registration
      ├── Delegate Card
      ├── Prasad Patra
      ├── Accommodation
      ├── Guest Reference
      └── other UPBS-specific operations
```

The common Event layer owns common Event identity/lifecycle concepts.

The UPBS Module owns UPBS-specific business entities.

---

# 15. UPBS Existing Table Boundary

The existing UPBS documentation identifies a dedicated UPBS foundation
including:

* `upbs_event`
* `upbs_registration`
* `delegate_card`
* `prasad_patra`
* `accommodation_allocation`
* `camp_master`
* `guest_reference`

These existing designs must not be silently replaced.

Before DDL changes, an explicit reconciliation must determine which
information is:

1. common Event information,
2. UPBS-specific information,
3. an extension of a common Event entity, or
4. a candidate for eventual migration.

No physical-table migration is frozen by this document.

---

# 16. Kishor Validation Case

Kishor Puja is an annual event/activity.

The common model therefore represents it as:

```text
PROGRAMME TYPE
    KISHOR_PUJA
        │
        ▼
EVENT INSTANCE
    Kishor Puja 2027
```

A later occurrence is a separate Event Instance:

```text
KISHOR_PUJA
    ├── Kishor Puja 2027
    ├── Kishor Puja 2028
    └── Kishor Puja 2029
```

Kishor-specific participant and participation rules remain owned by the
Kishor domain.

The common Event model must not replace those domain-specific rules.

---

# 17. Sevak Validation Case

The existing Sevak business rules define distinct event types including:

* `SAKHA_SEVAK_SANGHA_SESSION`
* `ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA`

These have distinct eligibility, attendance, notification, reporting
and dashboard behavior.

The existing rules also define:

* manual event creation
* configurable event frequency
* host Sakha
* event lifecycle
* cancellation
* rescheduling
* intention
* probable attendance
* actual attendance
* post-event reconciliation
* historical preservation

Therefore the common Event model should provide the common Event shell
without collapsing these Sevak-specific rules.

---

# 18. Event Eligibility Is Not Attendance

The common architecture must preserve the distinction:

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

The Event model must not make these concepts interchangeable.

Attendance remains owned by the Attendance domain.

---

# 19. Event Cancellation and Rescheduling

The existing Sevak event rules establish that:

* published/confirmed events can be cancelled
* events can be rescheduled
* event identity is retained during rescheduling
* historical scheduling information is preserved
* existing attendance is preserved
* intention responses may require reconfirmation
* post-event reconciliation occurs before completion
* post-completion corrections follow centralized audit/approval

These principles are candidates for common Event lifecycle behavior.

However, they are currently proven/frozen in the Sevak domain and must
be validated before being declared universal across every Programme Type.

---

# 20. Common Event Lifecycle

Baseline states applicable to all programme events:

```text
DRAFT
  ↓
PUBLISHED
  ↓
ACTIVE
  ↓
COMPLETED
```

With branches:

```text
PUBLISHED → CANCELLED
PUBLISHED → RESCHEDULED → PUBLISHED
```

Domain-specific extensions:

- Sevak: Adds RECONCILIATION between ACTIVE and COMPLETED
- UPBS: Session-level status tracking
- Kishor: Registration period status within PUBLISHED

The common model does not dictate domain-specific lifecycle extensions.

---

# 21. Event and Finance

Each Programme/Event may have its own Financial Scope where required.

Conceptually:

```text
Programme Type
      │
      ▼
Event Instance
      │
      ▼
Financial Scope
      │
      ├── Funds
      ├── Transactions
      ├── Receipts
      ├── Payments
      └── Transfers
```

Examples:

```text
UPBS 2027
    └── Financial Scope: UPBS 2027

Kishor Puja 2027
    └── Financial Scope: Kishor Puja 2027

Janmoutsaba 2027
    └── Financial Scope: Janmoutsaba 2027

Saradiya Alochana Chakra 2027
    └── Financial Scope: Saradiya Alochana Chakra 2027

Rasoutsaba 2027
    └── Financial Scope: Rasoutsaba 2027
```

The Finance Module remains authoritative for financial records.

An event does not create a separate financial accounting system.

---

# 22. Financial Year

All financial activity associated with an Event remains subject to the
Finance Module's Financial Year model.

Financial Year:

```text
01 April YYYY
      ↓
31 March YYYY+1
```

The event's calendar date does not change the Financial Year rules.

Financial transactions belong to the applicable Financial Year, not the
calendar year, even when an event spans March 31.

---

# 23. Event and Attendance

The relationship is:

```text
EVENT
  │
  └── Attendance
```

Attendance records actual participation.

The Event domain does not become the owner of attendance records.

Where a Programme requires domain-specific participation or eligibility,
that remains with the relevant domain.

Exception: weekly_sangha_puja remains independent and does not participate
in this model.

---

# 24. Event and Notifications

Event lifecycle changes may trigger notifications.

Conceptually:

```text
Event
  │
  ├── Published
  ├── Cancelled
  └── Rescheduled
        │
        ▼
Notification capability
```

Notification infrastructure remains a shared capability, not a
Programme-specific notification system.

---

# 25. Event and Governance / RBAC

Authorization shall use the existing Administration/RBAC framework.

The Event domain shall not create independent roles or permissions.

```text
Administration / Governance
          │
          ▼
     Authorization
          │
          ▼
         Event
```

---

# 26. Domain Extensions

A common Event model must not force all programmes into identical
business rules.

Example:

```text
Common Event
      │
      ├── Kishor-specific participation
      │
      ├── UPBS registration/accommodation/prasad
      │
      ├── Sevak eligibility/intention/attendance rules
      │
      ├── Mahila activities (common event directly)
      │
      └── future programme-specific rules
```

The common layer provides identity and shared lifecycle concepts.

Domain modules retain domain ownership.

---

# 27. Mahila Validation Case

The existing Mahila documentation states:

* Mahila activities use the common Event architecture
* No mahila_event table is required
* Event types include: MAHILA_MEETING, MAHILA_DISCOURSE, MAHILA_TRAINING,
  MAHILA_SEMINAR, MAHILA_EDUCATIONAL_ACTIVITY, SEVA_PUJA
* Event type master values belong to the Event module
* Conditional mahila_activity table only if common model proves
  insufficient

Mahila is the strongest consumer of the common Event model.

---

# 28. Event Interface Contract

Any entity that represents an "event" SHALL conform to:

```text
EVENT INTERFACE

Required:
  - Unique event identity (PK)
  - Event type/programme classification
  - Organizer (organization reference)
  - Event date or date range
  - Status (conforming to common lifecycle)
  - Audit trail (created_at/by, updated_at/by)

Optional:
  - Event location (snapshot)
  - Financial scope
  - Sessions
  - Description/remarks
```

Conforming tables:

| Table              | Module              | Conforms? |
| ------------------ | ------------------- | --------- |
| event              | Programmes & Events | YES       |
| kishor_event       | Kishor              | YES       |
| upbs_event         | UPBS                | YES       |
| weekly_sangha_puja | Attendance          | NO        |

---

# 29. Existing Table Reconciliation Summary

## kishor_event

| kishor_event column  | Maps to common concept       |
| -------------------- | ---------------------------- |
| kishor_event_pk      | event_pk                     |
| event_name           | event_name                   |
| financial_year       | financial_year               |
| event_date           | event_start_date             |
| host_organization_pk | organizer_organization_pk    |
| location_pk          | event location (snapshot)    |
| status               | status                       |

All kishor_event columns are generic. Candidate for absorption.

Decision: NOT YET FROZEN.

## upbs_event

| upbs_event concept      | Maps to common concept       |
| ----------------------- | ---------------------------- |
| Event PK                | event_pk                     |
| Event identity          | event_name                   |
| Event/session           | event_session (common)       |
| Event date/time         | event_start_date / end_date  |
| Event status            | status                       |

UPBS additionally requires session-level structure.

Decision: NOT YET FROZEN.

---

# 30. Table Ownership Principle

The project database standards require one physical owner for each table
and prohibit independent duplication of shared tables.

Therefore:

* A common Event table, if frozen, must have exactly one owner.
* UPBS must not recreate the common Event table.
* Kishor must not recreate the common Event table.
* Sevak must not recreate the common Event table.
* Finance must reference Event rather than duplicate it.
* Attendance must reference Event rather than duplicate it.

The exact owner/module is still OPEN.

---

# 31. Annual Recurrence

Annual recurrence is a property/configuration of a Programme Type, not a
requirement to reuse the same Event Instance.

```text
Programme Type
    │
    ├── 2027 Event
    ├── 2028 Event
    └── 2029 Event
```

The exact automatic-generation behavior is NOT frozen.

Existing Sevak rules specifically state that events are manually created
and that frequency is configurable rather than hard-coded.

Therefore the common model must not automatically impose an annual
scheduler on all programmes.

---

# 32. What This Domain Does NOT Own

```text
Attendance records              → Attendance module
Financial transactions          → Finance module
Participant registration rules  → Domain modules (Kishor, UPBS)
Domain business logic           → Domain modules
Authorization/permissions       → Administration / RBAC
Notifications                   → Shared platform capability
Weekly Sangha Puja              → Attendance module (independent)
Organization hierarchy          → Organization module
Organization types              → Organization module
Person identity                 → Person module
Geographic master data          → Foundation module
```

---

# 33. Proposed Logical Model

```text
                    ORGANIZATION
                         │
                         │ organizer
                         ▼
                  PROGRAMME TYPE
                         │
                         │ creates
                         ▼
                    EVENT INSTANCE
                   /     |      \
                  /      |       \
                 ▼       ▼        ▼
           LOCATION  SESSION   FINANCE
           (snapshot)          │
                               ▼
                        FINANCIAL SCOPE

EVENT INSTANCE
      │
      ├── ATTENDANCE (consumes event identity)
      │
      └── DOMAIN EXTENSION
             ├── KISHOR
             ├── UPBS
             ├── SEVAK
             └── MAHILA (direct use)
```

---

# 34. Open Decisions

The following remain intentionally OPEN:

1. Whether Programme Type is a physical table or configured master.
2. Whether Programme & Events becomes a standalone module (Module #21).
3. Exact common Event table fields.
4. Exact Event Location representation (flat vs. entity).
5. Whether organizer can be overridden per Event Instance.
6. Whether Event Sessions are universally applicable.
7. Whether existing upbs_event becomes an extension of common Event.
8. Whether existing kishor_event is absorbed into common Event.
9. Whether existing Sevak events map directly to common Event.
10. Common vs domain-specific Event status values.
11. Common recurrence model.
12. Common Event participation model.
13. Event-level authorization matrix.
14. Event-to-Organization relationship rules.
15. Historical location snapshot structure.

---

# 35. Explicit Non-Decisions

This document does NOT freeze:

* PostgreSQL DDL
* table names
* primary keys
* foreign keys
* API endpoints
* UI screens
* notification tables
* generic registration tables
* generic attendance tables
* automatic annual event generation
* migration of existing UPBS/Kishor/Sevak tables

---

# 36. Validation Status

| Area                                | Status                                 |
| ----------------------------------- | -------------------------------------- |
| Common Event concept                | SUPPORTED / STRONGLY INDICATED         |
| Programme Type concept              | ARCHITECTURAL PROPOSAL                 |
| Event Instance concept              | ARCHITECTURAL PROPOSAL                 |
| Event Session concept               | SUPPORTED by UPBS; common use OPEN     |
| Organizer = Organization            | ARCHITECTURAL BASELINE                 |
| Event Location ≠ Organization Type  | ARCHITECTURAL BASELINE                 |
| Patha Chakra = Organization Type    | PROJECT BASELINE                       |
| Patha Chakra → Sakha transformation | REQUIREMENT; workflow OPEN             |
| Finance per Event                   | ALIGNED with Finance design            |
| Attendance separate                 | ALIGNED with existing rules            |
| UPBS domain extension               | STRONGLY INDICATED                     |
| Common physical Event table         | NOT YET FROZEN                         |
| New Programme & Events module       | NOT YET FROZEN                         |

---

# 37. Next Artifact

Before creating any physical Event tables, the next document should be:

**EVENT_ENTITY_RECONCILIATION.md**

It shall compare the existing event-related designs in:

1. UPBS
2. Kishor
3. Sevak
4. Attendance
5. Finance
6. Organization
7. Mahila

and identify:

* common fields
* duplicate fields
* domain-specific fields
* existing PKs
* existing FKs
* lifecycle conflicts
* candidate common Event entity
* candidate extension entities

Only after this reconciliation should the project decide whether
Programme & Events becomes Module #21 and freeze its ERD/table design.

---

# 38. Status

```text
DOCUMENT STATUS:
DRAFT — ARCHITECTURAL ANALYSIS

VERSION:
0.1.0

PHYSICAL TABLE DESIGN:
NOT FROZEN

MODULE STATUS:
NOT YET FROZEN

NEXT:
EVENT_ENTITY_RECONCILIATION.md
```
