# NSS ERP — Event Entity Reconciliation

**Document ID:** SOL-EVT-002  
**Version:** 0.1.0  
**Status:** DRAFT — ARCHITECTURAL RECONCILIATION  
**Parent Document:** SOL-EVT-001 — Programme & Event Domain Model  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document reconciles the event-related concepts already present in
the NSS ERP solution documents against the proposed common Programme &
Event domain model.

The purpose is to determine:

- which event concepts are genuinely common;
- which concepts remain domain-specific;
- which existing event structures may be candidates for integration with
  a common Event entity;
- which concepts must not be generalized;
- where existing module ownership must be preserved;
- what remains OPEN before any physical Event tables are frozen.

This document does **not** modify or replace any existing frozen table
design.

No physical table migration is approved by this document.

---

# 2. Governing Principle

The project database standard establishes:

> Each physical table has exactly one owning module.

Cross-module consumption shall occur through references rather than
independent table duplication.

Therefore, if a common Event entity is eventually frozen:

```text
Common Event
     │
     ├── UPBS references it
     ├── Kishor references it
     ├── Sevak references it
     ├── Attendance references it
     └── Finance references it
```

and not:

```text
UPBS       → own duplicate Event
Kishor     → own duplicate Event
Sevak      → own duplicate Event
Attendance → own duplicate Event
Finance    → own duplicate Event
```

The existing database standards explicitly prohibit table duplication and
require a single physical owner.

---

# 3. Reconciliation Scope

The following domains are included:

1. Programme & Event
2. UPBS
3. Kishor
4. Sevak
5. Attendance
6. Finance
7. Organization
8. Mahila

The current reconciliation is based on the available project documents.
Where a physical table design cannot be verified from the available
source material, the item remains OPEN rather than being inferred.

---

# 4. Common Programme & Event Model

The current architectural proposal is:

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
      │
      ├── Event Session(s)
      ├── Event Location
      ├── Attendance
      ├── Financial Scope
      └── Domain-specific extension
```

The distinction between Programme Type and Event Instance is important.

Example:

```text
Programme Type
    UPBS

        ↓

Event Instance
    UPBS 2027
```

The next year's occurrence is a separate Event Instance:

```text
UPBS
 ├── UPBS 2027
 ├── UPBS 2028
 └── UPBS 2029
```

---

# 5. Reconciliation Result — High Level

| Domain             | Event Concept                 | Common Event Candidate | Domain-Specific | Current Decision                         |
| ------------------ | ----------------------------- | ---------------------: | --------------: | ---------------------------------------- |
| UPBS               | UPBS Event                    |                      ✓ |               ✓ | Reconcile existing `upbs_event`          |
| Kishor             | Kishor Puja                   |                      ✓ |               ✓ | Reconcile existing Kishor event identity |
| Sevak              | Sevak Sangha events           |                      ✓ |               ✓ | Common shell + Sevak-specific rules      |
| Attendance         | Actual attendance             |                      — |               ✓ | Remains Attendance-owned                 |
| Finance            | Financial Scope               |                      — |               ✓ | Remains Finance-owned                    |
| Organization       | Organizer / host organization |                      — |               ✓ | Organization-owned                       |
| Mahila             | Programme/event references    |                      ✓ |               ✓ | Reconcile after common model             |
| Programme & Events | Programme/Event identity      |                      ✓ |               — | Candidate common ownership               |

---

# 6. UPBS Reconciliation

## 6.1 Existing UPBS Event Concept

The existing UPBS foundation identifies:

```text
upbs_event
upbs_registration
delegate_card
prasad_patra
accommodation_allocation
camp_master
guest_reference
```

The existing project schema review records these as the UPBS module's
frozen foundation.

The current Programme & Event model proposes:

```text
programme_type
event
event_session
```

Therefore the key question is:

```text
upbs_event
    ?
    ↓
common event
```

This is a reconciliation question, not an approved migration.

---

## 6.2 UPBS Information That Is Clearly Domain-Specific

The following concepts are inherently UPBS-specific:

```text
UPBS Registration
Delegate Card
Prasad Patra
Accommodation Allocation
Camp
Guest Reference
```

They should remain owned by UPBS.

Conceptually:

```text
Common Event
      │
      ▼
UPBS
 ├── Registration
 ├── Delegate Card
 ├── Prasad Patra
 ├── Accommodation
 ├── Camp
 └── Guest Reference
```

The common Event entity must not absorb these business concepts merely
to make the schema look generic.

---

# 7. UPBS Sessions

UPBS already has a session structure:

```text
ADHIBASA
DAY_1
DAY_2
DAY_3
```

The Programme & Event domain model proposes:

```text
event
   │
   └── event_session
```

Therefore:

```text
UPBS 2027
 ├── ADHIBASA
 ├── DAY_1
 ├── DAY_2
 └── DAY_3
```

is a strong validation case for a reusable Event Session concept.

However, the exact common table and ownership remain OPEN.

---

# 8. UPBS Organizer

The current project decision is:

```text
UPBS
    → Kendra
```

The common model represents this as an Organization relationship:

```text
event.organizer
       ↓
Organization
       ↓
Kendra
```

The organizer is therefore not an Event Type and not an Event Location.

---

# 9. UPBS Location

UPBS requires an actual physical event location.

The common model therefore separates:

```text
Organizer
    → Organization

Location
    → Physical / Geographic Location
```

The Event Location must not be represented as:

```text
KENDRA
SAKHA
PATHA_CHAKRA
```

Those are organization types.

---

# 10. Kishor Reconciliation

Kishor Puja is an annual event/activity.

The common model represents:

```text
Programme Type
    KISHOR_PUJA
        │
        ▼
Event Instance
    Kishor Puja 2027
```

A later occurrence is a new Event Instance.

```text
KISHOR_PUJA
 ├── Kishor Puja 2027
 ├── Kishor Puja 2028
 └── Kishor Puja 2029
```

Kishor-specific participation remains owned by the Kishor module.

The common Event model must not replace Kishor participant or
participation rules.

---

# 11. Kishor Reconciliation Decision

The existing Kishor design must be inspected during the physical-schema
reconciliation to determine whether its event identity:

1. can directly reference a common Event;
2. should become a Kishor Event extension;
3. already contains information that should remain entirely Kishor-owned.

No migration is approved here.

The terminology is permanently:

```text
Kishor
KISHOR
kishor
```

not:

```text
Kishore
KISHORE
kishore
```

---

# 12. Sevak Reconciliation

Sevak contains the strongest existing event lifecycle model.

The frozen Sevak rules identify two event types:

```text
SAKHA_SEVAK_SANGHA_SESSION

ANCHALIKA_ZILLA_SEVAK_SANGHA_PUJA
```

These are explicitly distinct in:

* attendance
* notifications
* eligibility
* reporting
* dashboards

Therefore, the common Event model must not erase the distinction.

---

# 13. Sevak Event Creation

Sevak currently defines:

* manual event creation;
* configurable frequency;
* host Sakha;
* location snapshot;
* DRAFT;
* PUBLISHED/CONFIRMED.

No automatic recurring event generation is frozen for Sevak.

This produces an important architectural rule:

> A common Programme/Event framework must not automatically impose a
> recurrence scheduler on every programme.

Programme recurrence may be configured, but Event creation behavior
remains subject to programme-specific rules.

---

# 14. Sevak Host Rule

Sevak currently requires:

```text
Every event requires a registered Sakha as host.
```

The host Sakha's registered location is used, with the location captured
as a historical snapshot.

This is a **Sevak-specific rule**.

It must NOT become a universal common Event requirement.

For example:

```text
UPBS
    Organizer → Kendra
    Location  → actual physical location
```

while:

```text
Sevak Sangha Session
    Host → Sakha
    Location → host Sakha location snapshot
```

Both can coexist under the common Event model.

---

# 15. Sevak Location Snapshot

The Sevak requirement that the event location is captured at creation
for historical integrity is important.

The common Event model should therefore keep **historical location
preservation** as a candidate common principle.

However:

```text
Sevak location snapshot
```

must not automatically be interpreted as:

```text
All Event Types must use an Organization's location.
```

That distinction remains.

---

# 16. Sevak Lifecycle

The existing Sevak lifecycle is:

```text
DRAFT
   ↓
PUBLISHED / CONFIRMED
   ↓
CANCELLED
   OR
RESCHEDULED
   ↓
Event Occurs
   ↓
Attendance
   ↓
Reconciliation
   ↓
COMPLETED
```

Historical identity and attendance are preserved.

This is a strong candidate for a common Event lifecycle baseline.

However, exact universal status values remain OPEN.

---

# 17. Cancellation and Rescheduling

Sevak freezes:

* cancellation;
* rescheduling;
* preservation of original event identity;
* preservation of historical scheduling;
* intention reconfirmation after rescheduling;
* preservation of existing attendance;
* audit of changes.

These principles are strong candidates for common Event infrastructure.

They should be validated against other programmes before being declared
universal.

---

# 18. Event Completion

Sevak defines a reconciliation period after the event.

During reconciliation:

* attendance may be completed;
* legitimate attendees may be added;
* attendance may be corrected;
* probable vs actual attendance may be reviewed;
* inactive Sevak attendance may trigger reactivation review.

After completion:

* event history remains;
* attendance remains;
* intentions remain historical;
* normal editing is restricted;
* corrections follow centralized approval/audit.

This suggests that **Event Completion + Reconciliation** is a strong
candidate for common Event lifecycle infrastructure.

---

# 19. Attendance Reconciliation

The common model must preserve the Sevak distinction:

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
Event
 ├── Eligibility / participation context
 └── Attendance
```

must remain logically separate.

Attendance remains owned by the Attendance Module.

---

# 20. Cross-Organizational Attendance

Sevak rules allow a Sevak from another Anchalika/Zilla to attend a
published larger event without changing organizational affiliation.

This is important for the common Event model:

> Event participation must not imply an organizational transfer.

Therefore:

```text
Attend Event
      ≠
Change Organization
      ≠
Change Membership Sakha
```

This principle should be preserved.

---

# 21. Finance Reconciliation

Finance is a separate domain.

The current architecture defines:

```text
Programme/Event
       ↓
Financial Scope
       ↓
Financial Records
```

A programme or event may have its own financial scope.

The Event module must not own:

* financial transactions;
* receipts;
* payments;
* funds;
* transfers;
* financial-year records.

Finance remains authoritative.

All financial reporting uses the project's Financial Year:

```text
01 April
   ↓
31 March
```

---

# 22. Event-Specific Finance

The five current annual programmes can therefore have independent
financial scopes:

```text
Kishor Puja 2027
    → Financial Scope

Janmoutsaba 2027
    → Financial Scope

Saradiya Alochana Chakra 2027
    → Financial Scope

UPBS 2027
    → Financial Scope

Rasoutsaba 2027
    → Financial Scope
```

This does not make any of these programmes an Organization.

---

# 23. Organization Reconciliation

Organization remains authoritative for:

* organizational identity;
* organization type;
* hierarchy;
* organizational lifecycle.

The common Event model consumes Organization.

```text
Event
   │
   └── organizer
           ↓
      Organization
```

It must not recreate organization records.

---

# 24. Patha Chakra

Patha Chakra is an Organization Type.

It is not:

* Event Type;
* Event Location Type;
* Programme Type.

The current project decision is that Patha Chakra is a permanent
organization and NSS may have multiple Patha Chakras.

Future transformation:

```text
Patha Chakra
      ↓
approved transformation
      ↓
Sakha Sangha
```

is an Organization lifecycle concern.

The Event model does not own this transformation.

---

# 25. Event Location vs Organization

The reconciliation confirms four separate concepts:

```text
Organization
    = organizational entity

Organization Type
    = Kendra / Sakha / Patha Chakra / etc.

Organizer
    = Organization responsible for the Event

Event Location
    = physical/geographic place where the Event occurs
```

These must not be collapsed.

---

# 26. Mahila Reconciliation

Mahila currently references common event concepts rather than requiring
a separate generic event architecture.

The common Event model is therefore a candidate consumer for Mahila
programme/event activities.

However, no Mahila-specific physical event table should be introduced
until the common Event model and Mahila requirements are reconciled.

Mahila-specific business rules remain Mahila-owned.

---

# 27. Common vs Domain-Specific Matrix

| Concept              |          Common Event |         UPBS |          Kishor |                Sevak | Attendance |       Finance |
| -------------------- | --------------------: | -----------: | --------------: | -------------------: | ---------: | ------------: |
| Event identity       |           ✓ candidate |   references |      references |           references |   consumes |    references |
| Programme Type       |           ✓ candidate |     consumes |        consumes |             consumes |          — |      consumes |
| Organizer            |                     ✓ |       Kendra |          Kendra | domain-specific host |          — | scope context |
| Event Location       |           ✓ candidate |     specific |        specific |      host-Sakha rule |          — |             — |
| Event Session        |           ✓ candidate | ✓ strong use |        possible |             possible |          — |             — |
| Event Status         |           ✓ candidate |     specific |        specific |   ✓ frozen lifecycle |          — |             — |
| Attendance           |                     — |     consumes |        consumes |             consumes |  **owner** |             — |
| Financial Scope      |                     — |     consumes |        consumes |             consumes |          — |     **owner** |
| Registration         |                     — |    **owner** | domain-specific |                    — |          — |             — |
| Delegate Card        |                     — |    **owner** |               — |                    — |          — |             — |
| Prasad Patra         |                     — |    **owner** |               — |                    — |          — |             — |
| Accommodation        |                     — |    **owner** |               — |                    — |          — |             — |
| Event Intention      |             candidate |            — |               — |     **owner/domain** |          — |             — |
| Event Reconciliation |             candidate |            — |               — |     **owner/domain** |   consumes |             — |
| Event Audit          | common infrastructure |     consumes |        consumes |             consumes |   consumes |      consumes |

---

# 28. Existing UPBS Event vs Common Event

Current status:

```text
upbs_event
    │
    ├── Common event fields?       OPEN
    ├── UPBS-specific fields?     OPEN
    └── Migration/extension?      OPEN
```

No replacement is authorized.

---

# 29. Existing Kishor Event vs Common Event

Current status:

```text
Kishor event identity
    │
    ├── Common event fields?       OPEN
    ├── Kishor-specific fields?   OPEN
    └── Extension/reference?      OPEN
```

No replacement is authorized.

---

# 30. Existing Sevak Event vs Common Event

Current status:

```text
Sevak Event
    │
    ├── Common identity/lifecycle → candidate
    ├── Sevak eligibility        → Sevak-owned
    ├── Intention                → Sevak/domain-owned
    ├── Probable attendance      → Sevak/domain-owned
    ├── Host Sakha rule          → Sevak-owned
    └── Reconciliation           → candidate common infrastructure
```

The distinction between common infrastructure and Sevak rules must be
preserved.

---

# 31. Candidate Common Event Responsibilities

The reconciliation supports the following as candidates for common
ownership:

```text
Event Identity

Programme Type Association

Event Date / Time

Event Status

Organizer Reference

Event Location Reference

Event Session / Segment

Publication / Visibility State

Cancellation

Rescheduling History

Completion / Reconciliation Framework

Historical Event Identity
```

These remain candidates until the common Event ERD is frozen.

---

# 32. Explicitly Domain-Specific Responsibilities

The following should remain outside the generic Event entity unless a
future separate design proves otherwise:

### UPBS

```text
Registration
Delegate Card
Prasad Patra
Accommodation
Camp
Guest Reference
UPBS-specific operations
```

### Kishor

```text
Kishor participant rules
Kishor participation rules
Kishor-specific lifecycle
```

### Sevak

```text
Eligibility
Intention
Probable Attendance
Host Sakha rules
Reactivation Review
Seva Assignment
Sevak-specific event rules
```

### Attendance

```text
Actual Attendance
Attendance records
Attendance corrections
Attendance reporting
```

### Finance

```text
Financial Scope
Funds
Transactions
Receipts
Payments
Transfers
Financial Year
```

### Organization

```text
Organization identity
Organization type
Organization hierarchy
Patha Chakra lifecycle
Sakha lifecycle
```

---

# 33. Candidate Common Entity Structure

At conceptual level only:

```text
PROGRAMME_TYPE
      │
      │ 1:N
      ▼
EVENT
      │
      ├── organizer → ORGANIZATION
      │
      ├── location → PHYSICAL LOCATION
      │
      ├── sessions → EVENT SESSION
      │
      ├── attendance → ATTENDANCE
      │
      └── financial scope → FINANCE
```

No physical table names or columns are frozen here.

---

# 34. Important Architectural Constraint

The common Event model must **not become a universal business-rule
container**.

For example, it would be incorrect to require every Event to have:

```text
Host Sakha
Male-only eligibility
Sevak intention
Probable attendance
UPBS registration
Delegate Card
Prasad Patra
Accommodation
```

Those are domain-specific.

The common model provides the common event identity and shared
infrastructure.

---

# 35. Reconciliation Outcome

The evidence supports the existence of a common Event concept.

It also supports retaining domain-specific Event extensions.

The recommended architecture is therefore:

```text
                    PROGRAMME TYPE
                          │
                          ▼
                         EVENT
                    ┌─────┼─────┐
                    │     │     │
                    ▼     ▼     ▼
                  UPBS  KISHOR SEVAK
                    │     │     │
                    └─────┼─────┘
                          │
                    Common Event
                    Infrastructure
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         Attendance     Finance   Notifications
```

This is the preferred architecture, subject to final ERD validation.

---

# 36. What We Should NOT Do Yet

Do not yet:

* rename `upbs_event`;
* delete existing Kishor event structures;
* create a generic registration table;
* create a generic attendance table;
* move Sevak event rules into a new module;
* create Event DDL;
* create Event API contracts;
* freeze Event status values universally;
* freeze automatic recurrence;
* declare Programme & Events as Module #21.

These require the next design stage.

---

# 37. Remaining Architectural Questions

The reconciliation leaves the following questions:

1. What is the exact common Event identity?
2. Is Programme Type a physical table or configuration/master data?
3. Does the common Event have a physical Event Location FK?
4. How is historical location preserved?
5. Can organizer be overridden per Event Instance?
6. Is Event Session a universal entity?
7. Does UPBS `upbs_event` become an extension/reference to Event?
8. Does Kishor use the common Event identity directly?
9. Does Sevak use the common Event identity directly?
10. Which Event statuses are universal?
11. Which lifecycle transitions are universal?
12. Which event concepts remain programme-specific?
13. What is the exact ownership of the common Event tables?
14. Does this justify a standalone Programme & Events module?

---

# 38. Recommended Decision

Based on the current evidence:

> **Proceed with a common Programme & Event architecture.**

The evidence is strong enough to justify continuing the design.

However:

> **Do not yet freeze the physical common Event tables.**

The next step is to resolve the remaining entity-level questions in the
Programme & Event ERD.

---

# 39. Proposed Next Artifact

The next document should be:

```text
03_programmes_events_erd.md
```

However, it should initially be marked:

```text
DRAFT — LOGICAL ERD
```

and must not freeze PostgreSQL DDL until:

* UPBS reconciliation is accepted;
* Kishor reconciliation is accepted;
* Sevak mapping is accepted;
* Event Location is resolved;
* Event Session is resolved;
* Programme Type representation is resolved;
* table ownership is resolved.

---

# 40. Status

```text
DOCUMENT STATUS:
DRAFT — ARCHITECTURAL RECONCILIATION

VERSION:
0.1.0

COMMON EVENT CONCEPT:
SUPPORTED

PROGRAMME TYPE:
SUPPORTED AS ARCHITECTURAL CONCEPT

COMMON EVENT TABLE:
NOT FROZEN

EVENT SESSION:
CANDIDATE COMMON ENTITY

EVENT LOCATION:
SEPARATE FROM ORGANIZATION

PATHA_CHAKRA:
ORGANIZATION TYPE

UPBS EVENT MIGRATION:
NOT FROZEN

KISHOR EVENT MIGRATION:
NOT FROZEN

SEVAK EVENT MAPPING:
NOT FROZEN

MODULE #21:
NOT YET FROZEN

NEXT:
PROGRAMMES & EVENTS LOGICAL ERD
```
