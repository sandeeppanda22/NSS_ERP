# NSS ERP — Programmes & Events Logical ERD

**Document ID:** SOL-MOD21-002  
**Version:** 0.1.0  
**Status:** DRAFT — LOGICAL ERD  
**Parent Documents:**
- SOL-EVT-001 — Programme & Event Domain Model
- SOL-EVT-002 — Event Entity Reconciliation

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the logical entity relationship model for the
proposed common NSS Programme & Event architecture.

It translates the architectural model and reconciliation findings into
a logical entity structure.

This document does **not** freeze:

- PostgreSQL table names
- UUID primary keys
- foreign-key names
- indexes
- constraints
- DDL
- API contracts
- UI structures

Those decisions belong to the subsequent physical table-design phase.

---

# 2. Design Principles

The logical model follows these principles:

1. Programme Type and Event Instance are separate concepts.
2. An Event Instance represents one actual occurrence.
3. Organizer is an Organization.
4. Event Location is separate from Organization Type.
5. Kendra, Sakha Sangha and Patha Chakra are Organization concepts.
6. Patha Chakra → Sakha Sangha is an Organization lifecycle transition.
7. Event Sessions may be used where a programme requires them.
8. Domain-specific programme entities remain domain-owned.
9. Attendance remains Attendance-owned.
10. Financial Scope remains Finance-owned.
11. Financial Year remains Finance-owned and follows 01 April–31 March.
12. A common Event entity must not absorb domain-specific business rules.
13. One physical table must eventually have one owning module.
14. Existing UPBS/Kishor/Sevak structures are not silently replaced.

---

# 3. Logical Entity Overview

The proposed common model consists of the following logical entities:

```text
PROGRAMME_TYPE
      │
      │ 1:N
      ▼
EVENT
      │
      ├── EVENT_SESSION
      │
      ├── EVENT_LOCATION
      │
      ├── ATTENDANCE
      │
      ├── FINANCIAL_SCOPE
      │
      └── DOMAIN_EXTENSION
             ├── UPBS
             ├── KISHOR
             └── SEVAK
```

The exact physical ownership of the common entities remains OPEN.

---

# 4. PROGRAMME_TYPE

## 4.1 Purpose

`PROGRAMME_TYPE` represents the reusable definition/configuration of an
NSS programme.

Examples:

```text
KISHOR_PUJA
JANMOUTSABA
SARADIYA_ALOCHANA_CHAKRA
UPBS
RASOUTSABA
```

It is not an individual event occurrence.

---

## 4.2 Logical Attributes

Candidate logical attributes:

```text
programme_type
    ├── programme_code
    ├── programme_name
    ├── description
    ├── default_organizer
    ├── recurrence_configuration
    ├── programme_classification
    └── active_status
```

These are logical concepts only.

Exact physical columns remain OPEN.

---

# 5. PROGRAMME_TYPE → ORGANIZATION

A Programme Type may have a default organizer.

Relationship:

```text
PROGRAMME_TYPE
      │
      │ default organizer
      ▼
ORGANIZATION
```

Current configuration:

| Programme Type           | Default Organizer       |
| ------------------------ | ----------------------- |
| KISHOR_PUJA              | Kendra                  |
| JANMOUTSABA              | Kendra                  |
| SARADIYA_ALOCHANA_CHAKRA | Kendra                  |
| UPBS                     | Kendra                  |
| RASOUTSABA               | Ekamra Saraswata Sangha |

This does not mean that the organizer is an Event Location.

---

# 6. EVENT

## 6.1 Purpose

`EVENT` represents one actual occurrence of a Programme Type.

Example:

```text
PROGRAMME_TYPE
    UPBS
       │
       ▼
EVENT
    UPBS 2027
```

The following year's occurrence is a separate logical Event:

```text
UPBS
 ├── UPBS 2027
 ├── UPBS 2028
 └── UPBS 2029
```

---

## 6.2 Candidate Logical Attributes

```text
EVENT
    ├── programme_type
    ├── event_name
    ├── event_code
    ├── event_start
    ├── event_end
    ├── status
    ├── organizer
    ├── location
    ├── description
    └── historical/audit context
```

These are candidate logical attributes, not frozen database columns.

---

# 7. PROGRAMME_TYPE → EVENT

Relationship:

```text
PROGRAMME_TYPE
      │
      │ 1:N
      ▼
EVENT
```

Meaning:

> One Programme Type may produce many Event Instances.

Example:

```text
KISHOR_PUJA
    │
    ├── Kishor Puja 2027
    ├── Kishor Puja 2028
    └── Kishor Puja 2029
```

An Event Instance belongs to one Programme Type.

---

# 8. EVENT → ORGANIZATION

An Event has an organizer.

Relationship:

```text
EVENT
   │
   │ organizer
   ▼
ORGANIZATION
```

The organizer is therefore an Organization entity.

The logical model does not impose a universal requirement that the
organizer must be:

* Kendra
* Sakha
* Patha Chakra
* any other specific Organization Type

The applicable rule may depend on the Programme Type.

---

# 9. Organizer Override

The Programme Type has a default organizer.

The Event may potentially have an explicit organizer override.

Conceptually:

```text
PROGRAMME_TYPE
      │
      └── default_organizer
                │
                ▼
          ORGANIZATION


EVENT
      │
      └── effective_organizer
                │
                ▼
          ORGANIZATION
```

Whether Event-level override is permitted remains **OPEN**.

---

# 10. EVENT_LOCATION

Event Location represents the physical/geographic place where an Event
occurs.

It is deliberately separate from Organization.

Conceptually:

```text
EVENT
   │
   │ location
   ▼
EVENT_LOCATION
```

Candidate logical information:

```text
EVENT_LOCATION
    ├── address
    ├── geographic reference
    ├── location name
    └── historical snapshot information
```

Exact representation remains OPEN.

---

# 11. Organization ≠ Event Location

The following distinction is mandatory:

```text
ORGANIZATION
    ├── KENDRA
    ├── SAKHA
    └── PATHA_CHAKRA
```

versus:

```text
EVENT_LOCATION
    ├── physical address
    ├── geographic location
    └── historical location information
```

Therefore:

```text
event_location_type = KENDRA
```

is not the proposed common model.

---

# 12. Patha Chakra

Patha Chakra is an Organization Type.

It is therefore represented through:

```text
EVENT
   │
   └── organizer
          │
          ▼
      ORGANIZATION
          │
          └── organization_type
                  = PATHA_CHAKRA
```

Patha Chakra is not an Event Location Type.

---

# 13. Patha Chakra Transformation

The transformation:

```text
PATHA_CHAKRA
      │
      │ approved organization lifecycle transition
      ▼
SAKHA
```

belongs to the Organization domain.

It is not represented as an Event transition.

The Event model only references the Organization in its current valid
state.

---

# 14. EVENT_SESSION

`EVENT_SESSION` represents a logical segment/session within an Event.

Relationship:

```text
EVENT
   │
   │ 1:N
   ▼
EVENT_SESSION
```

Example:

```text
UPBS 2027
   │
   ├── ADHIBASA
   ├── DAY_1
   ├── DAY_2
   └── DAY_3
```

---

# 15. Event Session Is Optional

Not every Event requires sessions.

Therefore:

```text
EVENT
   │
   ├── zero sessions
   │
   └── one or more sessions
```

A single-session Event does not require artificial session records unless
the programme design requires them.

---

# 16. EVENT_SESSION Candidate Attributes

Logical candidates:

```text
EVENT_SESSION
    ├── event
    ├── session_code
    ├── session_name
    ├── sequence
    ├── start_time
    ├── end_time
    └── status
```

These are not frozen physical fields.

---

# 17. UPBS Mapping

UPBS provides the strongest current validation case for Event Sessions.

Logical mapping:

```text
PROGRAMME_TYPE
    UPBS
      │
      ▼
EVENT
    UPBS 2027
      │
      ├── EVENT_SESSION
      │     └── ADHIBASA
      │
      ├── EVENT_SESSION
      │     └── DAY_1
      │
      ├── EVENT_SESSION
      │     └── DAY_2
      │
      └── EVENT_SESSION
            └── DAY_3
```

UPBS-specific entities remain outside the common Event entity.

---

# 18. UPBS Domain Extension

The logical relationship is:

```text
EVENT
   │
   │ 1:1 / 1:0..1 candidate
   ▼
UPBS_EVENT_EXTENSION
```

This is a conceptual extension only.

Existing UPBS entities remain UPBS-owned:

```text
UPBS
 ├── Registration
 ├── Delegate Card
 ├── Prasad Patra
 ├── Accommodation
 ├── Camp
 └── Guest Reference
```

Whether the existing `upbs_event` becomes this extension or is replaced
by a reference to common Event is **OPEN**.

No migration is frozen.

---

# 19. Kishor Domain Extension

Logical relationship:

```text
EVENT
   │
   │ 1:0..1 candidate
   ▼
KISHOR_EVENT_EXTENSION
```

The extension would contain only Kishor-specific information.

Kishor participation rules remain owned by the Kishor Module.

The exact existing Kishor event structure must be reconciled before
physical design.

---

# 20. Sevak Domain Extension

Logical relationship:

```text
EVENT
   │
   │ 1:0..1 candidate
   ▼
SEVAK_EVENT_EXTENSION
```

Candidate Sevak-specific information includes:

* event type
* host Sakha
* intention configuration
* probable attendance
* Sevak-specific eligibility
* event-specific operational configuration

These remain Sevak-owned.

---

# 21. Sevak Host Organization

Sevak has a specific existing rule:

```text
Sevak Event
     │
     └── Host Sakha
```

The common Event model therefore supports:

```text
EVENT
   │
   └── organizer → ORGANIZATION

SEVAK_EVENT_EXTENSION
   │
   └── host_sakha → ORGANIZATION
```

The two relationships are not necessarily identical.

This is important because:

```text
Organizer ≠ Host
```

may be valid in the common architecture.

---

# 22. Sevak Location Rule

Sevak currently uses the host Sakha's registered location and captures
the location as a historical snapshot.

Therefore:

```text
SEVAK_EVENT_EXTENSION
       │
       └── host_sakha
                │
                ▼
          ORGANIZATION

EVENT
       │
       └── location
```

The common Event model does not require every programme to derive its
location from its host Organization.

---

# 23. Attendance Relationship

Attendance remains an independent domain.

Logical relationship:

```text
EVENT
   │
   │ 1:N
   ▼
ATTENDANCE
```

The Attendance Module owns actual attendance records.

The Event model does not create its own attendance system.

---

# 24. Participation vs Attendance

The logical model must preserve:

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

Therefore:

```text
EVENT
 ├── participation/eligibility context
 └── ATTENDANCE
```

must remain logically separate.

Domain-specific participation rules remain with their owning module.

---

# 25. Cross-Organization Attendance

Attendance at an Event does not change organizational affiliation.

Example:

```text
Person
   │
   ├── Member of Sakha A
   │
   └── Attends Event hosted by Sakha B
```

This means:

```text
Attend Event
    ≠
Change Membership
    ≠
Change Organization
```

The logical model therefore does not create an Organization relationship
through Event attendance.

---

# 26. Financial Scope Relationship

Finance owns Financial Scope.

Logical relationship:

```text
EVENT
   │
   │ 0..N / scope rules pending
   ▼
FINANCIAL_SCOPE
```

The exact cardinality remains OPEN because the Finance design allows
financial scope to be independently defined and potentially span years.

---

# 27. Event Finance

Examples:

```text
UPBS 2027
      │
      ▼
Financial Scope
      │
      └── Finance Module
```

Similarly:

```text
Kishor Puja 2027
Janmoutsaba 2027
Saradiya Alochana Chakra 2027
Rasoutsaba 2027
```

may each have a Financial Scope where required.

---

# 28. Financial Year

Event dates do not define the financial year.

Finance remains based on:

```text
01 April YYYY
       ↓
31 March YYYY+1
```

All Event-related financial transactions follow the Finance Module's
Financial Year model.

The Event entity does not own Financial Year.

---

# 29. Event Lifecycle

The common logical Event lifecycle is currently proposed as:

```text
DRAFT
  │
  ▼
PUBLISHED
  │
  ▼
ACTIVE
  │
  ▼
COMPLETED
```

with possible branches:

```text
DRAFT ─────────────→ CANCELLED
PUBLISHED ─────────→ CANCELLED
PUBLISHED ─────────→ RESCHEDULED
ACTIVE ────────────→ CANCELLED
```

These statuses and transitions are **candidate logical concepts only**.

The final common lifecycle must be reconciled with domain-specific
lifecycles.

---

# 30. Historical Event Identity

An Event must retain historical identity.

Rescheduling should not automatically create a new unrelated Event
identity if the business rule considers it the same occurrence.

Conceptually:

```text
EVENT-001
    │
    ├── Original schedule
    │
    └── Rescheduled schedule
```

Historical changes should remain auditable.

Exact implementation remains OPEN.

---

# 31. Event Reconciliation

After an Event occurs, a programme may require reconciliation.

Conceptually:

```text
EVENT
   │
   ▼
EVENT RECONCILIATION
   │
   ├── Attendance reconciliation
   ├── Participation reconciliation
   └── Programme-specific reconciliation
```

Whether a universal `EVENT_RECONCILIATION` entity is necessary remains
OPEN.

It may instead be implemented through domain-specific workflows.

---

# 32. Notification Relationship

Notification is a shared capability.

Logical relationship:

```text
EVENT
   │
   ├── Published
   ├── Cancelled
   └── Rescheduled
          │
          ▼
    Notification Capability
```

No Event-specific notification table is proposed at this stage.

---

# 33. Authorization Relationship

Event authorization uses the existing Administration/RBAC model.

Logical relationship:

```text
USER
 │
 ▼
ROLE / PERMISSION
 │
 ▼
EVENT ACTION
```

The Event domain does not own:

* roles;
* permissions;
* user accounts;
* organizational authorization infrastructure.

---

# 34. Common Logical ERD

The current proposed logical ERD is:

```text
                         ORGANIZATION
                         /          \
                        /            \
                       ▼              ▼
              default organizer    organizer
                    │                 │
                    │                 │
                    ▼                 ▼
              PROGRAMME_TYPE ─────── EVENT
                    │                  │
                    │ 1:N             │
                    │                 ├──────────────► EVENT_LOCATION
                    │                 │
                    │                 ├──────────────► EVENT_SESSION
                    │                 │
                    │                 ├──────────────► ATTENDANCE
                    │                 │
                    │                 ├──────────────► FINANCIAL_SCOPE
                    │                 │
                    │                 ├──────────────► UPBS EXTENSION
                    │                 │
                    │                 ├──────────────► KISHOR EXTENSION
                    │                 │
                    │                 └──────────────► SEVAK EXTENSION
                    │
                    ▼
              Programme Configuration
```

---

# 35. Simplified Relationship View

```text
PROGRAMME_TYPE
      │
      │ 1:N
      ▼
EVENT
 ├──────── 0..N EVENT_SESSION
 │
 ├──────── 0..1 EVENT_LOCATION
 │
 ├──────── 0..N ATTENDANCE
 │
 ├──────── 0..N FINANCIAL_SCOPE
 │
 ├──────── 0..1 UPBS_EXTENSION
 │
 ├──────── 0..1 KISHOR_EXTENSION
 │
 └──────── 0..1 SEVAK_EXTENSION

EVENT
 │
 └──────── ORGANIZATION
              ↑
              │
           organizer
```

Cardinalities shown above are **logical candidates**, not frozen
physical constraints.

---

# 36. Five Initial Programme Mappings

## 36.1 Kishor Puja

```text
PROGRAMME_TYPE
    KISHOR_PUJA
        │
        ▼
EVENT
    Kishor Puja 2027
        │
        ├── Organizer → Kendra
        ├── Location
        ├── Attendance
        ├── Financial Scope
        └── Kishor Extension
```

---

## 36.2 Janmoutsaba

```text
PROGRAMME_TYPE
    JANMOUTSABA
        │
        ▼
EVENT
    Janmoutsaba 2027
        │
        ├── Organizer → Kendra
        ├── Location
        ├── Attendance
        └── Financial Scope
```

---

## 36.3 Saradiya Alochana Chakra

```text
PROGRAMME_TYPE
    SARADIYA_ALOCHANA_CHAKRA
        │
        ▼
EVENT
    Saradiya Alochana Chakra 2027
        │
        ├── Organizer → Kendra
        ├── Location
        ├── Attendance
        └── Financial Scope
```

---

## 36.4 UPBS

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
        │     ├── ADHIBASA
        │     ├── DAY_1
        │     ├── DAY_2
        │     └── DAY_3
        │
        ├── Attendance
        ├── Financial Scope
        └── UPBS Extension
              ├── Registration
              ├── Delegate Card
              ├── Prasad Patra
              ├── Accommodation
              ├── Camp
              └── Guest Reference
```

---

## 36.5 Rasoutsaba

```text
PROGRAMME_TYPE
    RASOUTSABA
        │
        ▼
EVENT
    Rasoutsaba 2027
        │
        ├── Organizer → Ekamra Saraswata Sangha
        ├── Location
        ├── Attendance
        └── Financial Scope
```

---

# 37. Domain Ownership Map

| Logical Entity / Concept | Proposed Owner                 |
| ------------------------ | ------------------------------ |
| Programme Type           | Programme & Events — candidate |
| Event                    | Programme & Events — candidate |
| Event Session            | Programme & Events — candidate |
| Event Location           | Programme & Events — candidate |
| UPBS extension           | UPBS                           |
| Kishor extension         | Kishor                         |
| Sevak extension          | Sevak                          |
| Actual Attendance        | Attendance                     |
| Financial Scope          | Finance                        |
| Financial Transactions   | Finance                        |
| Organization             | Organization                   |
| Organization Type        | Organization                   |
| User Account             | Authentication                 |
| Roles / Permissions      | Administration                 |
| Audit                    | Audit                          |

This ownership map is provisional until the module itself is formally
frozen.

---

# 38. Existing Table Reconciliation

The following existing concepts require explicit mapping during physical
design:

| Existing Concept              | Candidate Common Mapping | Status    |
| ----------------------------- | ------------------------ | --------- |
| `upbs_event`                  | EVENT / UPBS extension   | OPEN      |
| Kishor event identity         | EVENT / Kishor extension | OPEN      |
| Sevak event                   | EVENT / Sevak extension  | OPEN      |
| Attendance event reference    | EVENT                    | Candidate |
| Finance event/scope reference | EVENT / Financial Scope  | Candidate |
| Organization organizer        | ORGANIZATION             | Supported |

No existing table is deleted or renamed by this ERD.

---

# 39. What Is Frozen at Logical Level

The following architectural relationships are sufficiently supported:

1. Programme Type is distinct from Event Instance.
2. Event belongs to a Programme Type.
3. Event organizer is an Organization.
4. Event Location is distinct from Organization Type.
5. Kendra/Sakha/Patha Chakra are Organization concepts.
6. Patha Chakra transformation belongs to Organization lifecycle.
7. Event Sessions are required conceptually for programmes such as UPBS.
8. Attendance remains separate.
9. Finance remains separate.
10. Domain-specific programme extensions remain possible.
11. Existing domain tables must not be silently duplicated or replaced.

---

# 40. What Remains Open

The following are intentionally NOT frozen:

1. Physical table names.
2. Physical primary keys.
3. Physical foreign keys.
4. Event Location table design.
5. Programme Type physical representation.
6. Event Session physical representation.
7. Event status vocabulary.
8. Universal Event lifecycle.
9. Event-level organizer override.
10. Event-to-Financial-Scope cardinality.
11. Common Event reconciliation entity.
12. UPBS migration/extension strategy.
13. Kishor migration/extension strategy.
14. Sevak migration/extension strategy.
15. Exact ownership of common Event entities.
16. Whether Programme & Events becomes Module #21.

---

# 41. Explicit Non-Decisions

This ERD does NOT authorize:

* `CREATE TABLE event`;
* `CREATE TABLE programme_type`;
* renaming `upbs_event`;
* deleting any existing event table;
* migrating UPBS;
* migrating Kishor;
* migrating Sevak;
* creating generic attendance tables;
* creating generic finance tables;
* creating generic registration tables;
* API development;
* UI development.

Those decisions follow the business-rules and lifecycle phases.

---

# 42. Recommended Next Step

The next artifact should be:

```text
PROGRAMMES_EVENTS_BUSINESS_RULES.md
```

The Business Rules document must resolve the remaining logical questions
before physical table design.

It should specifically address:

1. Programme Type creation and maintenance.
2. Event creation.
3. Organizer rules.
4. Event Location rules.
5. Event Session rules.
6. Annual/recurrent programme behaviour.
7. Event publication.
8. Event cancellation.
9. Event rescheduling.
10. Event completion.
11. Historical preservation.
12. Event participation.
13. Attendance integration.
14. Finance integration.
15. UPBS extension rules.
16. Kishor extension rules.
17. Sevak extension rules.
18. Authorization.
19. Notifications.
20. Cross-organization participation.
21. Patha Chakra organizational distinction.
22. Event-specific Financial Scope.

---

# 43. Status

```text
DOCUMENT STATUS:
DRAFT — LOGICAL ERD

VERSION:
0.1.0

COMMON EVENT:
LOGICALLY SUPPORTED

PROGRAMME TYPE:
LOGICALLY SUPPORTED

EVENT SESSION:
LOGICAL CANDIDATE

EVENT LOCATION:
SEPARATE FROM ORGANIZATION

PATHA_CHAKRA:
ORGANIZATION TYPE

ATTENDANCE:
SEPARATE DOMAIN

FINANCE:
SEPARATE DOMAIN

UPBS:
DOMAIN EXTENSION CANDIDATE

KISHOR:
DOMAIN EXTENSION CANDIDATE

SEVAK:
DOMAIN EXTENSION CANDIDATE

PHYSICAL TABLE DESIGN:
NOT FROZEN

MODULE #21:
NOT YET FROZEN

NEXT:
PROGRAMMES_EVENTS_BUSINESS_RULES.md
```

# End of Document
