# NSS ERP — Programmes & Events Table Design

**Document ID:** SOL-MOD21-005  
**Version:** 0.1.0  
**Status:** DRAFT — TABLE DESIGN  
**Module:** Programmes & Events  
**Module Number:** 21

---

# 1. Purpose

This document defines the logical table-design boundary for the
Programmes & Events Module.

It translates the approved:

- Module Overview;
- Logical ERD;
- Lifecycle;
- Business Rules;

into candidate physical entities and ownership boundaries.

This document does **not** contain PostgreSQL DDL.

The project database methodology is:

```text
Business Rules
      ↓
ERD
      ↓
Table Design
      ↓
PostgreSQL DDL
      ↓
Django Models
      ↓
FastAPI
      ↓
UI
```

The table-design layer must not introduce schema decisions unsupported by
the preceding documentation.

---

# 2. Status of Physical Design

The Programme & Events architecture previously established that
PostgreSQL DDL, exact table names, PK/FK definitions and physical
implementation were not frozen at the architecture stage.

This document therefore freezes the **logical table ownership and
candidate entity boundaries**, while identifying remaining physical
decisions as PENDING where appropriate.

---

# 3. Table Ownership Principle

Each physical table shall have exactly one owning module.

For Programme & Events:

```text
Programme & Events
        │
        ├── common Programme Type
        ├── common Event
        ├── common Event Session
        ├── Event Location
        └── Event History
```

Other modules retain ownership of their entities:

```text
Organization → Organization
Person       → Person
Attendance   → Attendance
Finance      → Financial Scope / financial entities
UPBS         → UPBS-specific entities
Kishor       → Kishor-specific entities
Sevak        → Sevak-specific entities
Audit        → Audit
Administration → RBAC
Authentication → User identity
```

The common Event design must not duplicate these domains.

---

# 4. Candidate Table Inventory

The current logical candidate table inventory is:

|  # | Candidate Table        | Owner              | Status                        |
| -: | ---------------------- | ------------------ | ----------------------------- |
|  1 | programme_type         | Programme & Events | Candidate                     |
|  2 | event                  | Programme & Events | Candidate                     |
|  3 | event_day              | Programme & Events | Candidate                     |
|  4 | event_session          | Programme & Events | Candidate                     |
|  5 | event_registration     | Programme & Events | Candidate                     |
|  6 | event_location         | Programme & Events | Candidate                     |
|  7 | event_history          | Programme & Events | Candidate                     |
|  8 | financial_scope        | Finance            | Existing Finance ownership    |
|  9 | attendance entities    | Attendance         | Existing Attendance ownership |
| 10 | UPBS Event extension   | UPBS               | Existing/domain-specific      |
| 11 | Kishor Event extension | Kishor             | Domain-specific               |
| 12 | Sevak Event extension  | Sevak              | Existing/domain-specific      |

Only the first seven are candidates for common Programme & Events
physical tables.

---

# 5. programme_type

## 5.1 Purpose

`programme_type` represents the reusable definition of a programme.

Examples:

```text
KISHOR_PUJA
JANMOUTSABA
SARADIYA_ALOCHANA_CHAKRA
UPBS
RASOUTSABA
```

One Programme Type may have multiple Event Instances.

---

## 5.2 Logical Structure

```text
programme_type
-------------------------
programme_type_pk
programme_code
programme_name
programme_classification
default_organizer_pk
recurrence_configuration
default_session_configuration
status
audit columns
```

These are logical candidates, not final PostgreSQL column definitions.

---

## 5.3 Relationships

```text
programme_type
      │
      ├── default organizer → organization
      │
      └──< event
```

---

# 6. Programme Type Code

The Programme Type requires a stable business identifier/code.

Examples:

```text
KISHOR_PUJA
JANMOUTSABA
SARADIYA_ALOCHANA_CHAKRA
UPBS
RASOUTSABA
```

The exact code-generation mechanism remains a physical implementation
decision.

---

# 7. Programme Type Status

Programme Type requires lifecycle/configuration status.

The exact status vocabulary is **PENDING** until resolved in the
Lifecycle/Business Rules documentation.

No undocumented status values shall be introduced during DDL generation.

---

# 8. Programme Type Organizer

A Programme Type may have a default organizer.

Relationship:

```text
programme_type
      │
      └── default_organizer
                  ↓
             organization
```

Organizer is an Organization.

The Programme & Events module does not create a duplicate organizer
master.

---

# 9. event

## 9.1 Purpose

`event` represents an actual occurrence of a Programme Type.

Examples:

```text
Kishor Puja 2027
Janmoutsaba 2027
UPBS 2027
Rasoutsaba 2027
```

---

## 9.2 Logical Structure

```text
event
-------------------------
event_pk
programme_type_pk
event_code
event_name
organizer_organization_pk
event_location_pk
start_datetime
end_datetime
status
audit columns
```

The exact physical columns and names remain subject to final DDL
authoring.

---

# 10. Event → Programme Type

Relationship:

```text
programme_type
      │
      │ 1:N
      ▼
event
```

Every Event belongs to one Programme Type.

A Programme Type may have many Event Instances.

---

# 11. Event Organizer

The Event organizer is an Organization.

Logical relationship:

```text
event.organizer
       ↓
organization
```

This follows the established architectural baseline that Organizer is
Organization and is separate from Event Location.

---

# 12. Event Location

## 12.1 Purpose

`event_location` represents the physical/geographical place associated
with an Event.

It is not an Organization Type.

The architecture explicitly distinguishes Event Location from
Organization Type.

---

## 12.2 Logical Structure

Potential structure:

```text
event_location
-------------------------
event_location_pk
location_name
address / location reference
geographic references
status
audit columns
```

The exact representation remains **PENDING**.

---

# 13. Event Location and Organization

A location may be associated with an Organization.

However:

```text
organization
      ≠
event_location
```

For example:

```text
Organizer:
Kendra

Event Location:
Sakha premises
```

The two concepts remain independently represented.

---

# 14. Kendra / Sakha / Patha Chakra

The table design shall not create:

```text
kendra_event_location
sakha_event_location
patha_chakra_event_location
```

as generic location tables.

These remain Organization concepts.

Relevant Organization Types include:

```text
KENDRA
SAKHA
PATHACHAKRA
```

Organization owns those concepts.

---

# 15. Patha Chakra

Patha Chakra is a permanent Organization.

It is not a Programme & Events table.

A future transformation:

```text
PATHA CHAKRA
      ↓
SAKHA
```

belongs to Organization lifecycle management.

Programme & Events only consumes the resulting Organization identity.

---

# 16. event_session

## 16.1 Purpose

`event_session` represents an optional subdivision of an Event.

Example:

```text
UPBS 2027
   ├── ADHIBASA
   ├── DAY_1
   ├── DAY_2
   └── DAY_3
```

UPBS provides existing support for this concept.

---

## 16.2 Logical Structure

```text
event_session
-------------------------
event_session_pk
event_pk
session_code
session_name
sequence_no
start_datetime
end_datetime
status
audit columns
```

The exact fields remain subject to lifecycle/business-rule validation.

---

# 17. Event → Event Session

Relationship:

```text
event
  │
  │ 1:N
  ▼
event_session
```

An Event may have zero or more Sessions.

A simple Event may have no Sessions.

---

# 18. Common Session vs Domain Session

The common `event_session` concept must not replace programme-specific
session rules.

For example:

```text
Common:
event_session

UPBS:
UPBS-specific session behavior
```

The common table represents common Event session identity only.

---

# 19. event_history

## 19.1 Purpose

`event_history` is the candidate historical record for significant Event
lifecycle changes.

Potential events include:

* creation;
* publication;
* cancellation;
* rescheduling;
* completion;
* significant corrections.

---

## 19.2 Logical Structure

```text
event_history
-------------------------
event_history_pk
event_pk
previous_state
new_state
previous_start_datetime
new_start_datetime
reason
changed_by
changed_at
audit context
```

The exact physical structure remains PENDING.

---

# 20. Event History Principle

History must preserve the Event identity.

Rescheduling does not create an unrelated Event.

Cancellation does not delete the Event.

Completion does not delete the Event.

This is consistent with existing domain lifecycle rules, including the
Sevak Event requirements for preserving identity and rescheduling
history.

---

# 21. Financial Scope

Financial Scope is **not owned by Programme & Events**.

Ownership:

```text
Finance
```

Logical relationship:

```text
event
   ↓
financial_scope
```

where financial management requires an Event-level Financial Scope.

The Finance module remains authoritative for:

* Financial Year;
* Financial Scope;
* funds;
* transactions;
* receipts;
* payments;
* transfers.

---

# 22. Financial Year

Event financial integration follows:

```text
01 April → 31 March
```

The Event module must not introduce a separate calendar-year financial
model.

Example:

```text
Event:
15 March 2028

Financial Year:
2027–28
```

subject to Finance's authoritative Financial Year determination.

---

# 23. Finance Table Ownership

Programme & Events shall not create:

```text
event_transaction
event_receipt
event_payment
event_fund
```

Finance owns financial entities.

---

# 24. Attendance Ownership

Attendance remains owned by Attendance.

Programme & Events shall not create:

```text
event_attendance
```

as a replacement for the Attendance module.

The Event provides context to Attendance.

---

# 25. Attendance Integration

Logical relationship:

```text
event
   ↓
attendance
```

The physical FK direction is **PENDING** until the Attendance and
Programme & Events table designs are reconciled.

This is important because the project requires avoidance of circular FK
creation.

---

# 26. UPBS Integration

UPBS retains ownership of its programme-specific data.

The common model provides:

```text
programme_type
event
event_session
event_location
```

where applicable.

UPBS retains its specific structures.

Examples include:

```text
registration
delegate
accommodation
camp
prasad
guest-related entities
```

Existing UPBS structures must be reconciled before migration.

The architecture explicitly requires this reconciliation before physical
Event tables are frozen.

---

# 27. Kishor Integration

Kishor consumes the common Event identity where applicable.

Kishor-specific participant and programme information remains Kishor
owned.

No duplicate generic Event table shall be created inside Kishor merely
because Kishor has its own Event-specific behavior.

---

# 28. Sevak Integration

Sevak retains its domain-specific Event behavior.

Existing Sevak rules include:

* two distinct operational Event types;
* host Sakha;
* configurable frequency;
* intention;
* probable attendance;
* actual attendance;
* cancellation;
* rescheduling;
* reconciliation;
* completion.

These remain Sevak-owned business rules.

---

# 29. Sevak Host Sakha

The Sevak domain may reference the Organization representing the host
Sakha.

This does not mean:

```text
event.organizer_type = SAKHA
```

The host Sakha is an Organization relationship.

The common Event model must not impose host-Sakha semantics on every
programme.

---

# 30. Person References

The common Event tables should not duplicate Person identity.

Where Event-level user/actor references are needed, they shall use the
authoritative Person/Authentication/Audit architecture as appropriate.

No duplicate:

```text
event_person
```

table is frozen at this stage.

---

# 31. Authentication and Authorization

Programme & Events consumes common Authentication and Administration.

It does not own:

```text
user_account
role
permission
user_role
admin_scope
```

Authorization is governed by the central RBAC architecture.

---

# 32. Audit Columns

The project database standard requires auditability.

Candidate common tables shall include the standard audit fields required
by the database standard.

However, the exact physical FK target and audit bootstrapping strategy
remain subject to the project-wide DDL strategy.

The database standards explicitly identify audit-FK bootstrapping as an
implementation concern.

---

# 33. Soft Deletion

Physical deletion of historically meaningful Event data shall not be
used to represent normal lifecycle transitions.

Examples:

```text
CANCELLED
COMPLETED
```

remain records.

The final physical deletion/soft-delete fields follow the project-wide
database standard.

---

# 34. Candidate Primary Keys

All candidate Programme & Events tables shall use the project-standard
UUID-based internal primary-key convention.

Candidate:

```text
programme_type_pk
event_pk
event_session_pk
event_location_pk
event_history_pk
```

The exact generation mechanism is resolved during physical DDL authoring.

The project database standards freeze UUID for `_pk` columns.

---

# 35. Candidate Foreign Keys

Logical candidate relationships include:

```text
event.programme_type_pk
    → programme_type.programme_type_pk

programme_type.default_organizer_pk
    → organization.organization_pk

event.organizer_organization_pk
    → organization.organization_pk

event.event_location_pk
    → event_location.event_location_pk

event_session.event_pk
    → event.event_pk

event_history.event_pk
    → event.event_pk
```

Potential integration references:

```text
event
    → financial_scope

event
    → attendance
```

remain subject to cross-module DDL reconciliation.

---

# 36. Cross-Module FK Rule

Where a physical FK is introduced, it shall reference the authoritative
internal PK of the owning module.

It shall not reference:

* business code;
* display name;
* organization name;
* programme name;
* Event name.

The project database standard requires cross-module FKs to reference
internal PKs.

---

# 37. ON DELETE Strategy

Cross-module FK deletion behavior shall follow the project-wide database
standard.

Historically meaningful Event relationships should normally not cascade
destructively.

Exact `ON DELETE` behavior remains subject to final DDL review.

---

# 38. Index Candidates

Potential indexes include:

```text
programme_type.programme_code
programme_type.status

event.programme_type_pk
event.organizer_organization_pk
event.event_location_pk
event.status
event.start_datetime

event_session.event_pk
event_session.start_datetime

event_history.event_pk
event_history.changed_at
```

These are **index candidates**, not yet frozen DDL.

Final indexes shall be determined during physical database authoring.

---

# 39. Uniqueness Candidates

Potential uniqueness rules include:

```text
programme_type.programme_code
```

and potentially an Event business identifier.

The exact Event uniqueness rule is **PENDING**.

The design must not assume that:

```text
event_name + year
```

is universally unique.

---

# 40. Event Code

An Event may require a stable business identifier.

The exact format is PENDING.

Possible implementation concepts include:

```text
Programme Code + occurrence identifier
```

but this document does not freeze a particular format.

---

# 41. Recurrence Configuration

Programme Type may contain recurrence configuration.

However, recurrence must not automatically generate Events unless the
business rules explicitly authorize such behavior.

Existing Sevak rules require manual Event creation and configurable
frequency.

Therefore automatic annual Event generation is not a universal frozen
rule.

---

# 42. Annual Recurring Programme Model

The intended structure is:

```text
programme_type
      │
      ├── event 2027
      ├── event 2028
      └── event 2029
```

This applies to recurring programmes such as:

```text
Kishor Puja
Janmoutsaba
Saradiya Alochana Chakra
UPBS
Rasoutsaba
```

---

# 43. Special Event Model

A Special Event should use the same common Event entity.

It does not automatically require:

```text
special_event
```

as a separate table.

A separate extension is justified only if the Special Event domain later
requires additional independent entities or business rules.

---

# 44. Notification Ownership

The Programme & Events tables shall not create a duplicate notification
system.

Event lifecycle operations may invoke shared notification capability.

Notification infrastructure remains outside this module's table
ownership.

---

# 45. Reporting Ownership

Reports consumes Event data.

Programme & Events does not create duplicate reporting tables solely for
standard reports.

Report-specific materialized structures, views or aggregates are
implementation decisions for the Reports module.

---

# 46. Proposed Physical Table Set

Subject to final reconciliation, the common Programme & Events physical
table set is proposed as:

```text
programme_type
event
event_day
event_session
event_registration
event_location
event_history
```

This is the **current candidate set**, not yet production DDL.

The reconciliation gates (A–G) are now CLOSED per
SOL-EVT-007 (PROGRAMMES_EVENTS_RECONCILIATION_DECISIONS.md).

---

# 47. Explicitly Not Proposed

The following are not part of the current common table set:

```text
event_attendance
event_transaction
event_receipt
event_payment
event_participant
event_notification
kendra_event
sakha_event
patha_chakra_event
```

unless later business-rule or reconciliation work demonstrates a genuine
common requirement.

---

# 48. Domain Extension Pattern

The intended architecture is:

```text
COMMON
────────────────────────────
programme_type
event
event_day
event_session
event_registration
event_location
event_history
        │
        ├──────── UPBS extension
        ├──────── Kishor extension
        └──────── Sevak extension
```

The domain-specific extension remains owned by the domain module.

---

# 49. Existing Table Reconciliation

The cross-module reconciliation required before physical DDL is now
COMPLETE. All 7 gates closed per SOL-EVT-007 (2026-08-28).

Summary of reconciliation decisions:

- Gate A: P&E owns common Event entity
- Gate B: `upbs_event` → P&E common Event extension
- Gate C: Kishor → P&E common Event extension
- Gate D: Sevak → P&E common Event extension
- Gate E: Event Session optional, organiser-defined (P&E-ARCH-002)
- Gate F: Weekly Sangha Puja remains Attendance-owned (no change)
- Gate G: Registration = common P&E infrastructure (P&E-ARCH-001)

The field-level reconciliation (exact column mapping from existing
UPBS/Kishor/Sevak event tables to common Event) remains a DDL-phase
activity.

---

# 50. Physical Table Decisions Still Pending

The following remain PENDING:

1. Final physical table names.
2. Exact column list.
3. Exact data types.
4. Exact PK generation.
5. Exact FK list.
6. Event Location representation.
7. Event History representation.
8. Event/Attendance FK direction.
9. Event/Finance FK direction.
10. Event/Financial Scope cardinality.
11. Event Session commonality across programmes.
12. Event recurrence storage.
13. Event business identifier format.
14. Event uniqueness constraints.
15. Location snapshot strategy.
16. Organizer snapshot strategy.
17. Migration of existing UPBS Event data.
18. Migration of existing Kishor Event data.
19. Migration of existing Sevak Event data.

---

# 51. No DDL in This Document

This document does not contain:

```text
CREATE TABLE
ALTER TABLE
CREATE INDEX
CREATE TRIGGER
CREATE VIEW
```

Those belong to the physical database implementation layer.

---

# 52. Database-First Implementation Gate

After this document and the other Programme & Events documentation are
approved:

```text
Business Rules
      ↓
ERD
      ↓
Table Design
      ↓
Cross-Module Reconciliation
      ↓
Physical DDL
```

Only then may PostgreSQL tables be created.

---

# 53. Documentation Traceability

This document derives from:

```text
01_programmes_events_module_overview.md
02_programmes_events_erd.md
03_programmes_events_lifecycle.md
04_programmes_events_business_rules.md
```

and cross-module architecture:

```text
PROGRAMME_EVENT_DOMAIN_MODEL.md
EVENT_ENTITY_RECONCILIATION.md
PROGRAMMES_EVENTS_CROSS_MODULE_REVIEW.md
```

The project traceability standard requires downstream solution artifacts
to preserve traceability to their governing layers.

---

# 54. Documentation Freeze Requirement

The Programme & Events module shall not be considered documentation
complete until all five module documents have been reviewed together:

```text
01 Overview
02 ERD
03 Lifecycle
04 Business Rules
05 Table Design
```

The consistency review shall verify:

* terminology;
* ownership;
* cardinality;
* lifecycle;
* business rules;
* table candidates;
* cross-module dependencies;
* unresolved decisions.

---

# 55. Module #21 Table Design Status

```text
MODULE:
Programmes & Events

MODULE NUMBER:
21

TABLE DESIGN:
DRAFT

COMMON TABLE CANDIDATES:
7

programme_type:
CANDIDATE

event:
CANDIDATE

event_day:
CANDIDATE

event_session:
CANDIDATE

event_registration:
CANDIDATE

event_location:
CANDIDATE

event_history:
CANDIDATE

FINANCE:
SEPARATE OWNER

ATTENDANCE:
SEPARATE OWNER

ORGANIZATION:
SEPARATE OWNER

UPBS:
DOMAIN EXTENSION

KISHOR:
DOMAIN EXTENSION

SEVAK:
DOMAIN EXTENSION

POSTGRESQL DDL:
NOT STARTED

RECONCILIATION GATES:
ALL CLOSED (7/7) — SOL-EVT-007

DOCUMENTATION FREEZE:
PENDING

NEXT:
DB STANDARDS → FK GRAPH → DDL ORDER
```
