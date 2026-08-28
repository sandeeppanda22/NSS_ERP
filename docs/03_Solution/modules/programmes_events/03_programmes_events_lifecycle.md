# NSS ERP — Programmes & Events Lifecycle

**Document ID:** SOL-MOD21-003  
**Version:** 0.1.0  
**Status:** DRAFT — LIFECYCLE DESIGN  
**Parent Documents:**
- SOL-EVT-001 — Programme & Event Domain Model
- SOL-EVT-002 — Event Entity Reconciliation
- SOL-MOD21-002 — Programmes & Events Logical ERD
- SOL-MOD21-004 — Programmes & Events Business Rules

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle model for the common Programme &
Event architecture.

It translates the approved logical and business-rule concepts into:

- Event states
- State transitions
- Transition guards
- Actions
- Authorization points
- Cancellation
- Rescheduling
- Completion
- Post-event reconciliation
- Historical preservation

This document does not freeze PostgreSQL implementation details.

---

# 2. Lifecycle Scope

The lifecycle defined here applies to the common Event Instance.

It does not replace domain-specific lifecycle rules owned by:

- UPBS
- Kishor
- Sevak
- Attendance
- Finance
- Organization

Where a domain requires additional lifecycle states or workflows, those
remain domain-owned.

---

# 3. Lifecycle Principles

The Event lifecycle follows these principles:

1. A Programme Type is configuration/definition.
2. An Event is an actual occurrence.
3. Event identity is preserved throughout its lifecycle.
4. Cancellation does not mean deletion.
5. Rescheduling does not create an unrelated Event identity unless an
   explicitly approved domain rule requires it.
6. Completion preserves historical information.
7. Actual attendance remains Attendance-owned.
8. Financial processing remains Finance-owned.
9. Authorization uses common RBAC.
10. Lifecycle changes are auditable.
11. Domain-specific lifecycle rules remain domain-owned.

---

# 4. Conceptual Lifecycle

The common lifecycle is:

```text
                 ┌──────────────┐
                 │    DRAFT     │
                 └──────┬───────┘
                        │
                        │ publish
                        ▼
                 ┌──────────────┐
                 │  PUBLISHED   │
                 └──────┬───────┘
                        │
                        │ event starts
                        ▼
                 ┌──────────────┐
                 │    ACTIVE    │
                 └──────┬───────┘
                        │
                        │ event completes
                        ▼
                 ┌──────────────┐
                 │  COMPLETED   │
                 └──────────────┘

Cancellation may occur before completion:

DRAFT ──────────────► CANCELLED
PUBLISHED ──────────► CANCELLED
ACTIVE ─────────────► CANCELLED
```

Rescheduling is treated as a lifecycle operation rather than necessarily
as a permanent Event state:

```text
PUBLISHED
    │
    └── reschedule
           │
           ▼
      schedule history
           │
           ▼
      PUBLISHED / ACTIVE
```

---

# 5. Lifecycle States

The common conceptual states are:

| State       | Meaning                                     |
| ----------- | ------------------------------------------- |
| `DRAFT`     | Event is being prepared                     |
| `PUBLISHED` | Event is officially published               |
| `ACTIVE`    | Event is currently taking place             |
| `COMPLETED` | Event has concluded                         |
| `CANCELLED` | Event will not proceed / has been cancelled |

These states are currently logical candidates.

The final physical status vocabulary remains subject to approval.

---

# 6. DRAFT

## 6.1 Meaning

`DRAFT` represents an Event that has been created but has not yet been
officially published.

A Draft Event may be incomplete.

Examples of information being prepared:

* Event name
* schedule
* organizer
* location
* sessions
* programme-specific configuration
* financial configuration
* participation configuration

---

# 7. DRAFT Entry

An Event enters `DRAFT` when an authorized Event creator creates an Event
Instance.

Conceptually:

```text
PROGRAMME_TYPE
      │
      │ create occurrence
      ▼
EVENT
      │
      ▼
DRAFT
```

---

# 8. DRAFT Actions

While in `DRAFT`, authorized users may perform applicable preparation
activities.

Examples:

* define schedule;
* define location;
* define organizer;
* configure sessions;
* configure programme-specific information;
* establish financial linkage where required;
* configure participation rules.

Exact permissions remain governed by Administration/RBAC.

---

# 9. DRAFT → PUBLISHED

Transition:

```text
DRAFT
   │
   │ Publish
   ▼
PUBLISHED
```

## Guard Conditions

The Event must satisfy all mandatory publication requirements.

Potential requirements include:

* valid Programme Type;
* valid organizer;
* valid schedule;
* valid location where required;
* required domain-specific configuration;
* required authorization.

The exact mandatory-field matrix remains PENDING.

---

# 10. Publication Action

When an Event is published:

1. Event state changes to `PUBLISHED`.
2. The publication action is audited.
3. Applicable notification mechanisms may be triggered.
4. Visibility rules begin applying according to the published state.

The Event domain does not create a separate notification system.

---

# 11. PUBLISHED

`PUBLISHED` means the Event has been officially announced/activated for
its intended audience but has not yet started.

The Event remains subject to:

* authorization;
* cancellation;
* rescheduling;
* applicable programme rules.

---

# 12. PUBLISHED → ACTIVE

Transition:

```text
PUBLISHED
    │
    │ event begins
    ▼
ACTIVE
```

The transition may occur:

* automatically based on schedule; or
* manually by an authorized user.

The final mechanism is PENDING.

---

# 13. ACTIVE

`ACTIVE` means the Event is currently taking place.

During this state:

* Event sessions may be active;
* Attendance may be recorded;
* programme-specific operational activities may occur;
* financial activity may continue according to Finance rules.

---

# 14. ACTIVE → COMPLETED

Transition:

```text
ACTIVE
   │
   │ complete
   ▼
COMPLETED
```

Completion shall occur when the Event's operational activities have
concluded.

Where a programme requires post-event reconciliation, completion may
require the applicable reconciliation process.

---

# 15. COMPLETED

`COMPLETED` represents a historical Event that has concluded.

A completed Event remains available for:

* reporting;
* historical reference;
* audit;
* attendance analysis;
* financial reporting;
* programme analysis.

---

# 16. Post-Completion Corrections

A completed Event shall not be freely editable.

Where a correction is required:

1. the correction must be authorized;
2. the original state must remain auditable;
3. the correction must preserve historical integrity.

Exact correction workflow remains PENDING.

---

# 17. Cancellation

Cancellation is a terminal business outcome for an Event that will not
proceed or has been stopped.

The conceptual transitions are:

```text
DRAFT ──────────────► CANCELLED

PUBLISHED ──────────► CANCELLED

ACTIVE ─────────────► CANCELLED
```

Whether cancellation from `ACTIVE` is permitted for every Programme Type
is domain-dependent.

---

# 18. Cancellation Guard

Cancellation requires appropriate authority.

The user performing cancellation must have the applicable permission
under Administration/RBAC.

The cancellation action must be auditable.

---

# 19. Cancellation Action

When an Event is cancelled:

1. The Event remains historically identifiable.
2. The state becomes `CANCELLED`.
3. Cancellation reason should be recorded where required.
4. The cancellation action is audited.
5. Applicable notifications may be generated.
6. Existing attendance/financial records are not physically deleted.
7. Programme-specific cancellation rules remain applicable.

---

# 20. Cancellation Does Not Mean Deletion

The following is prohibited:

```text
CANCELLED EVENT
       ↓
DELETE EVENT
```

Instead:

```text
EVENT
  ↓
CANCELLED
  ↓
HISTORICALLY PRESERVED
```

This follows the project's general historical-preservation principles.

---

# 21. Rescheduling

Rescheduling changes the planned Event schedule while preserving the
Event's logical identity.

Conceptually:

```text
EVENT-001
   │
   ├── Original Schedule
   │
   └── Revised Schedule
```

The exact physical schedule-history mechanism remains PENDING.

---

# 22. Rescheduling Operation

A rescheduling operation shall:

1. require appropriate authorization;
2. preserve the Event identity;
3. preserve the previous schedule;
4. record the new schedule;
5. record the reason where required;
6. create an audit record;
7. trigger applicable notifications;
8. preserve relevant participation/attendance information.

---

# 23. Rescheduling and Event State

Rescheduling is not necessarily a permanent Event state.

For example:

```text
PUBLISHED
   │
   ├── reschedule
   │
   ▼
PUBLISHED
```

The Event remains published while its schedule changes.

A Programme Type may impose a temporary state such as `RESCHEDULED`,
but this is not yet frozen as a universal persistent state.

---

# 24. Rescheduling and Attendance

Existing attendance must not be silently reassigned or deleted merely
because an Event is rescheduled.

The Attendance Module remains responsible for attendance interpretation.

This is particularly important for programmes such as Sevak where
attendance and intention have explicit domain rules.

---

# 25. Rescheduling and Finance

Rescheduling does not automatically create a new Financial Scope.

Existing financial records remain Finance-owned.

Any financial consequences of rescheduling shall be handled through
Finance business rules.

---

# 26. Event Completion and Reconciliation

Some programmes require post-event reconciliation.

Conceptually:

```text
ACTIVE
   │
   ▼
Operational Completion
   │
   ▼
Reconciliation
   │
   ▼
COMPLETED
```

Whether reconciliation is a mandatory prerequisite for a particular
Programme Type is domain-specific.

---

# 27. Attendance Reconciliation

Where applicable, post-event processing may reconcile:

* expected participation;
* actual participation;
* attendance records;
* legitimate corrections.

Attendance remains Attendance-owned.

The Event lifecycle only coordinates the lifecycle dependency.

---

# 28. Finance Reconciliation

Where applicable, post-event financial reconciliation remains Finance
responsibility.

The Event lifecycle shall not define financial settlement rules.

---

# 29. Domain-Specific Lifecycle

A domain may impose additional lifecycle requirements.

Example:

```text
COMMON EVENT
     │
     ├── UPBS-specific lifecycle
     │
     ├── Kishor-specific lifecycle
     │
     └── Sevak-specific lifecycle
```

The common Event state must not invalidate domain-specific workflow.

---

# 30. UPBS Lifecycle Integration

UPBS may require operational stages such as:

```text
Event Preparation
      ↓
Registration
      ↓
Delegate Processing
      ↓
Accommodation / Camp Operations
      ↓
Programme Sessions
      ↓
Completion
```

These are UPBS-domain processes.

They do not become mandatory common Event states.

---

# 31. Kishor Lifecycle Integration

Kishor-specific preparation, participation and programme workflows remain
owned by the Kishor Module.

The common Event lifecycle provides only the shared Event occurrence
state.

---

# 32. Sevak Lifecycle Integration

Sevak has domain-specific lifecycle requirements including:

* event creation;
* publication;
* intention;
* probable attendance;
* actual attendance;
* cancellation;
* rescheduling;
* reconciliation.

These remain Sevak-owned.

The common Event lifecycle provides the shared Event identity and
high-level state.

---

# 33. Organizer Changes

Changing an Event organizer after publication shall require
authorization.

Whether organizer changes are permitted after publication is PENDING.

If permitted:

1. previous organizer must remain historically recoverable;
2. new organizer must be valid;
3. the change must be audited.

---

# 34. Location Changes

Changing an Event location after publication shall require appropriate
authorization.

If permitted:

1. previous location must remain historically recoverable where required;
2. new location must be valid;
3. the change must be audited;
4. applicable notifications may be triggered.

The universal location-snapshot implementation remains PENDING.

---

# 35. Session Changes

Adding, removing or modifying Event Sessions after publication shall
follow the applicable authorization rules.

For a Programme such as UPBS, session changes must not violate
UPBS-specific operational rules.

---

# 36. Programme Type Deactivation

Deactivating a Programme Type does not alter historical Events.

Example:

```text
PROGRAMME_TYPE
    inactive
       │
       ├── historical Event 2027 → preserved
       ├── historical Event 2028 → preserved
       └── future Event creation → governed by configuration
```

---

# 37. Event Identity

An Event's identity remains stable throughout:

```text
DRAFT
  ↓
PUBLISHED
  ↓
ACTIVE
  ↓
COMPLETED
```

and through:

```text
RESCHEDULE
CANCEL
CORRECT
```

unless an explicitly approved business rule defines otherwise.

---

# 38. Event History

The lifecycle must preserve the history of significant transitions.

At minimum, the following changes should be auditable:

* creation;
* publication;
* cancellation;
* rescheduling;
* completion;
* organizer changes;
* location changes;
* significant session changes.

The exact history implementation remains PENDING.

---

# 39. Authorization

Lifecycle transitions consume the Administration/RBAC framework.

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

The Event domain shall not define independent roles or permissions.

---

# 40. Transition Authorization Matrix

The following matrix is intentionally provisional:

| Transition            | Authorization                |
| --------------------- | ---------------------------- |
| Create → DRAFT        | Event creation permission    |
| DRAFT → PUBLISHED     | Event publication permission |
| PUBLISHED → ACTIVE    | System/authorized transition |
| ACTIVE → COMPLETED    | Event completion permission  |
| DRAFT → CANCELLED     | Cancellation permission      |
| PUBLISHED → CANCELLED | Cancellation permission      |
| ACTIVE → CANCELLED    | Domain-dependent             |
| Reschedule            | Rescheduling permission      |

Exact RBAC permission codes remain PENDING.

---

# 41. Notification Hooks

Lifecycle transitions may generate notifications.

| Lifecycle Event             | Possible Notification |
| --------------------------- | --------------------- |
| Published                   | Event published       |
| Cancelled                   | Event cancelled       |
| Rescheduled                 | Schedule changed      |
| Significant location change | Location changed      |
| Completed                   | Event completed       |

The actual notification policy is outside this lifecycle document.

---

# 42. Attendance Hook

Potential lifecycle integration:

```text
PUBLISHED
     ↓
ACTIVE
     ↓
Attendance collection
     ↓
Operational completion
     ↓
Attendance reconciliation
```

Attendance records remain owned by the Attendance Module.

---

# 43. Finance Hook

Potential lifecycle integration:

```text
Event
  ↓
Financial Scope
  ↓
Financial transactions
  ↓
Finance reconciliation
```

Finance determines:

* Financial Year;
* transaction states;
* approvals;
* funds;
* receipts;
* payments;
* transfers;
* settlement.

The Event lifecycle does not override Finance lifecycle rules.

---

# 44. Financial Year

All financial activity associated with an Event follows:

```text
01 April
   ↓
31 March
```

The Event calendar year is not the Financial Year.

For example:

```text
Event:
15 March 2028

Financial Year:
2027–28
```

subject to Finance's authoritative determination.

---

# 45. Special Event Lifecycle

A one-off/special Event may use the same common lifecycle:

```text
DRAFT
  ↓
PUBLISHED
  ↓
ACTIVE
  ↓
COMPLETED
```

or:

```text
DRAFT
  ↓
CANCELLED
```

No separate lifecycle engine is required merely because an Event is
special.

---

# 46. Annual Programme Lifecycle

An annual Programme Type creates independent Event Instances.

Example:

```text
KISHOR_PUJA
    │
    ├── 2027 Event
    ├── 2028 Event
    └── 2029 Event
```

Each occurrence has its own lifecycle.

Cancellation of one year's Event does not deactivate the Programme Type.

---

# 47. Programme Type vs Event Lifecycle

Programme Type lifecycle:

```text
ACTIVE
   │
   └── INACTIVE
```

Event lifecycle:

```text
DRAFT
  ↓
PUBLISHED
  ↓
ACTIVE
  ↓
COMPLETED
```

These are independent concepts.

---

# 48. Organization Lifecycle Independence

Organization lifecycle is independent of Event lifecycle.

Example:

```text
Patha Chakra
      ↓
Sakha
```

does not mean:

```text
Event
      ↓
new Event
```

The Organization Module owns the organizational transition.

---

# 49. Cross-Organization Event

An Event may be organized by one Organization and attended by persons
from other Organizations.

This does not change membership or organizational affiliation.

---

# 50. Historical Organization State

Where an Event references an Organization, historical reporting may need
to determine the organizational context applicable at the time of the
Event.

The exact historical organization snapshot strategy remains PENDING.

---

# 51. Lifecycle Error Handling

An invalid lifecycle transition shall be rejected.

Examples:

```text
COMPLETED → ACTIVE
```

or:

```text
CANCELLED → ACTIVE
```

shall not be allowed unless an explicit approved transition exists.

---

# 52. Invalid Transition Principle

The lifecycle engine shall validate:

1. current state;
2. requested transition;
3. user authorization;
4. organizational scope;
5. programme-specific rules;
6. required preconditions.

---

# 53. Concurrent Lifecycle Changes

Where multiple users attempt conflicting lifecycle changes, the system
must prevent inconsistent final state.

Exact concurrency implementation is a technical design concern and
remains outside this document.

---

# 54. Audit Requirement

Every significant lifecycle transition shall produce an auditable
record.

At minimum:

```text
Event
Action
Actor
Timestamp
Previous State
New State
```

Additional information may be recorded where required.

---

# 55. No Independent Event Audit

The Event domain shall use the centralized Audit architecture.

It shall not create an independent Event audit framework.

---

# 56. Soft Delete

Lifecycle cancellation or deactivation shall not be implemented as
physical deletion.

Historical business records remain preserved.

---

# 57. Lifecycle State Machine

The current logical state machine is:

```text
                         ┌──────────────┐
                         │    DRAFT     │
                         └──────┬───────┘
                                │
                       publish  │
                                ▼
                         ┌──────────────┐
                         │  PUBLISHED   │
                         └──────┬───────┘
                                │
                       start    │
                                ▼
                         ┌──────────────┐
                         │    ACTIVE    │
                         └──────┬───────┘
                                │
                      complete  │
                                ▼
                         ┌──────────────┐
                         │  COMPLETED   │
                         └──────────────┘


DRAFT ───────────────► CANCELLED
PUBLISHED ───────────► CANCELLED
ACTIVE ──────────────► CANCELLED


PUBLISHED
    │
    └──── RESCHEDULE ────► PUBLISHED

ACTIVE
    │
    └──── RESCHEDULE ────► ACTIVE / PUBLISHED
                           (domain/configuration dependent)
```

---

# 58. Lifecycle Transition Table

| Current State | Action     | Target State     | Notes                      |
| ------------- | ---------- | ---------------- | -------------------------- |
| —             | Create     | DRAFT            | Authorized creation        |
| DRAFT         | Publish    | PUBLISHED        | Publication guards         |
| DRAFT         | Cancel     | CANCELLED        | Authorized                 |
| PUBLISHED     | Start      | ACTIVE           | Scheduled/authorized       |
| PUBLISHED     | Cancel     | CANCELLED        | Authorized                 |
| PUBLISHED     | Reschedule | PUBLISHED        | Preserve history           |
| ACTIVE        | Complete   | COMPLETED        | Completion guards          |
| ACTIVE        | Cancel     | CANCELLED        | Domain-dependent           |
| ACTIVE        | Reschedule | ACTIVE/PUBLISHED | Domain-dependent           |
| COMPLETED     | Correct    | COMPLETED        | Authorized correction only |
| CANCELLED     | —          | —                | Terminal by default        |

---

# 59. Terminal States

The default terminal states are:

```text
COMPLETED
CANCELLED
```

A terminal state should not be reopened without an explicit approved
business rule.

---

# 60. Reopening

Whether a cancelled or completed Event can be reopened is **PENDING**.

If future business rules permit reopening, it must:

* require explicit authorization;
* preserve prior state;
* record the reason;
* create an audit record;
* preserve historical transitions.

---

# 61. Lifecycle and API

The lifecycle defined here will later become API-level operations such
as:

```text
Create Event
Publish Event
Cancel Event
Reschedule Event
Start Event
Complete Event
```

Exact endpoint names and contracts belong to the API phase.

---

# 62. Lifecycle and UI

The UI shall expose only transitions that:

* are valid for the current state;
* the user is authorized to perform;
* satisfy programme-specific rules.

The UI shall not independently implement lifecycle logic.

---

# 63. Physical Database Implications

The lifecycle suggests that the eventual physical design will need to
represent at least:

* Event identity;
* current lifecycle state;
* schedule;
* organizer;
* location;
* Programme Type;
* audit information.

The exact tables, columns, indexes and constraints remain outside this
document.

---

# 64. Pending Decisions

The following lifecycle decisions remain OPEN:

| #  | Decision                                    |
| -- | ------------------------------------------- |
| 1  | Exact physical state vocabulary             |
| 2  | Automatic vs manual PUBLISHED → ACTIVE      |
| 3  | Whether `RESCHEDULED` is a persistent state |
| 4  | Exact cancellation reason model             |
| 5  | Exact schedule-history model                |
| 6  | Organizer-change rules                      |
| 7  | Location-change rules                       |
| 8  | Universal reconciliation requirement        |
| 9  | Reopening cancelled Events                  |
| 10 | Reopening completed Events                  |
| 11 | Exact RBAC permission matrix                |
| 12 | Event Session lifecycle                     |
| 13 | Historical Organization snapshot strategy   |
| 14 | Universal Event Location snapshot strategy  |
| 15 | Automatic annual Event generation           |

---

# 65. Lifecycle Safety Rules

The following shall not be violated:

1. Event identity must be preserved.
2. Historical Event data must not be physically deleted.
3. Cancellation must remain auditable.
4. Rescheduling must preserve relevant history.
5. Completion must preserve historical identity.
6. Attendance must remain Attendance-owned.
7. Finance must remain Finance-owned.
8. Authorization must remain Administration-owned.
9. Audit must remain centralized.
10. Organization lifecycle must remain Organization-owned.

---

# 66. Recommended Physical Lifecycle Representation

No physical schema is frozen yet.

However, the eventual table design should support:

```text
EVENT
 ├── current lifecycle state
 ├── scheduled start/end
 ├── organizer
 ├── location
 └── audit metadata

EVENT_LIFECYCLE_HISTORY
 ├── Event
 ├── previous state
 ├── new state
 ├── action
 ├── actor
 ├── timestamp
 └── reason
```

`EVENT_LIFECYCLE_HISTORY` is a **design candidate**, not a frozen table.

---

# 67. Domain Lifecycle Overlay

The common lifecycle should be understood as:

```text
                    COMMON EVENT LIFECYCLE
                             │
            ┌────────────────┼────────────────┐
            │                │                │
           UPBS            KISHOR           SEVAK
            │                │                │
      domain rules      domain rules      domain rules
      & workflows       & workflows       & workflows
```

The common lifecycle is the shared foundation.

It does not erase domain-specific workflow.

---

# 68. Final Lifecycle Model

The current recommended model is:

```text
                PROGRAMME TYPE
                       │
                       │ create
                       ▼
                    DRAFT
                       │
                       │ publish
                       ▼
                  PUBLISHED
                    │     │
                    │     └── reschedule
                    │
                    │ start
                    ▼
                   ACTIVE
                  /      \
                 /        \
                /          \ complete
               /            \
              ▼              ▼
         CANCELLED       COMPLETED
```

With:

```text
Attendance → Attendance Module
Finance → Finance Module
Authorization → Administration
Identity → Person / Authentication
Organization → Organization
Audit → Audit
Notifications → Shared Infrastructure
```

---

# 69. Status

```text
DOCUMENT STATUS:
DRAFT — LIFECYCLE DESIGN

VERSION:
0.1.0

COMMON STATES:
LOGICALLY DEFINED

DRAFT:
SUPPORTED

PUBLISHED:
SUPPORTED

ACTIVE:
SUPPORTED

COMPLETED:
SUPPORTED

CANCELLED:
SUPPORTED

RESCHEDULING:
SUPPORTED AS OPERATION

ATTENDANCE:
SEPARATE DOMAIN

FINANCE:
SEPARATE DOMAIN

FINANCIAL YEAR:
01 APRIL – 31 MARCH

DOMAIN OVERLAYS:
SUPPORTED

PHYSICAL TABLE DESIGN:
NOT FROZEN

MODULE #21:
NOT YET FROZEN

NEXT:
PROGRAMMES_EVENTS_TABLE_DESIGN.md
```

# End of Document
